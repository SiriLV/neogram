from __future__ import annotations
import asyncio as _asyncio
import inspect as _inspect
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field as _dataclass_field
from typing import Any, BinaryIO, Callable, ClassVar, Dict, List, Optional, Tuple, Union
from curl_cffi import CurlMime as _CurlMime
from curl_cffi.requests import Session as _CurlSession
from curl_cffi.requests import AsyncSession as _AsyncSession

logger = logging.getLogger("neogram")
API_VERSION = "10.0"
DEFAULT_API_URL = "https://api.telegram.org"


# ── Exceptions ─────────────────────────────────────────────────────────────────
class TelegramAPIError(Exception):
    """Raised when the Telegram API returns an error response
    Attributes:
        error_code: HTTP-like error code from Telegram (400, 401, 403, 429, 500, …)
        description: Human-readable error description from Telegram
        parameters: Optional dict with extra info (e.g. {"retry_after": 30})
        method: The API method name that caused the error (set by _request)
        retry_after: Convenience shortcut for parameters.get("retry_after")
    """
    def __init__(self, error_code: int, description: str, parameters: Optional[dict] = None):
        super().__init__(f"[{error_code}] {description}")
        self.error_code = error_code
        self.description = description
        self.parameters = parameters or {}
        self.method: str = ""
        self.retry_after: Optional[int] = self.parameters.get("retry_after")

TelegramError = TelegramAPIError

class StopPropagation(Exception):
    """Raise inside a handler to stop further handlers from running for this update"""

class InputFile:
    """Wrapper for uploading files to Telegram. Accepts a file path (str), raw bytes, or an open file-like object"""
    __slots__ = ("source", "filename")
    def __init__(self, source: Union[str, bytes, BinaryIO], filename: Optional[str] = None):
        self.source = source
        if filename is None and isinstance(source, str):
            filename = os.path.basename(source)
        self.filename = filename or "file"

    def open(self) -> Tuple[str, BinaryIO]:
        if isinstance(self.source, str):
            return self.filename, open(self.source, "rb")
        if isinstance(self.source, (bytes, bytearray)):
            import io
            return self.filename, io.BytesIO(self.source)
        return self.filename, self.source

def _value_to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, TelegramObject):
        return value.to_dict()
    if isinstance(value, dict):
        return {k: _value_to_jsonable(v) for k, v in value.items() if v is not None}
    if isinstance(value, (list, tuple)):
        return [_value_to_jsonable(v) for v in value]
    return value


@dataclass
class TelegramObject:
    """Base class for all Telegram API types
    Provides from_dict (deserialization) and to_dict (serialization)
    with automatic field renaming (type_val → type, from_user → from, …)
    """
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Optional["TelegramObject"]:
        if data is None:
            return None
        meta = getattr(cls, "_FIELD_META", {})
        kwargs: Dict[str, Any] = {}
        for json_key, value in data.items():
            entry = meta.get(json_key, {})
            kwargs[entry.get("py", json_key)] = _decode_value(value, entry)
        valid = {f for f in getattr(cls, "__dataclass_fields__", {}) if not f.startswith("_")}
        return cls(**{k: v for k, v in kwargs.items() if k in valid}, **{f: None for f in valid if f not in kwargs})

    def to_dict(self) -> dict:
        meta = getattr(self, "_FIELD_META", {})
        py2json = {info.get("py", k): k for k, info in meta.items()}
        return {py2json.get(k, k): _value_to_jsonable(v) for k, v in self.__dict__.items() if v is not None}

    def __repr__(self) -> str:
        parts = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items() if v is not None)
        return f"{self.__class__.__name__}({parts})"

def _resolve_class(name: str, value: Any) -> Optional[type]:
    """Resolve a type name to its class, using union dispatch if available"""
    disp = _UNION_DISPATCH.get(name)
    if disp and isinstance(value, dict):
        disc_val = value.get(disp["discriminator"])
        target = (disp["map"].get(str(disc_val) if disc_val is not None else None) or disp.get("fallback"))
        if target:
            return _TYPE_REGISTRY.get(target)
    return _TYPE_REGISTRY.get(name)

def _decode_value(value: Any, meta: dict) -> Any:
    if value is None:
        return None
    if meta.get("is_list") and isinstance(value, list):
        inner_obj = meta.get("list_inner_object")
        def _nested(v, depth):
            if not isinstance(v, list):
                return v
            if depth == 1:
                result = []
                for item in v:
                    if inner_obj and isinstance(item, dict):
                        cls = _resolve_class(inner_obj, item)
                        if cls:
                            result.append(cls.from_dict(item))
                        else:
                            result.append(item)
                    else:
                        result.append(item)
                return result
            return [_nested(item, depth - 1) for item in v]
        return _nested(value, meta.get("list_depth") or 1)
    if meta.get("is_object") and isinstance(value, dict):
        cls = _resolve_class(meta.get("inner_object") or "", value)
        if cls:
            return cls.from_dict(value)
    return value

_TYPE_REGISTRY: Dict[str, type] = {}
_UNION_DISPATCH: Dict[str, Dict[str, Any]] = {}

def _register_type(cls):
    _TYPE_REGISTRY[cls.__name__] = cls
    return cls

# ── Telegram API types ───────────────────────────────────────────────────────

@_register_type
@dataclass
class Update(TelegramObject):
    """This object represents an incoming update. At most one of the optional fields can be present in any given update."""
    update_id: int
    message: Optional["Message"] = None
    edited_message: Optional["Message"] = None
    channel_post: Optional["Message"] = None
    edited_channel_post: Optional["Message"] = None
    business_connection: Optional["BusinessConnection"] = None
    business_message: Optional["Message"] = None
    edited_business_message: Optional["Message"] = None
    deleted_business_messages: Optional["BusinessMessagesDeleted"] = None
    guest_message: Optional["Message"] = None
    message_reaction: Optional["MessageReactionUpdated"] = None
    message_reaction_count: Optional["MessageReactionCountUpdated"] = None
    inline_query: Optional["InlineQuery"] = None
    chosen_inline_result: Optional["ChosenInlineResult"] = None
    callback_query: Optional["CallbackQuery"] = None
    shipping_query: Optional["ShippingQuery"] = None
    pre_checkout_query: Optional["PreCheckoutQuery"] = None
    purchased_paid_media: Optional["PaidMediaPurchased"] = None
    poll: Optional["Poll"] = None
    poll_answer: Optional["PollAnswer"] = None
    my_chat_member: Optional["ChatMemberUpdated"] = None
    chat_member: Optional["ChatMemberUpdated"] = None
    chat_join_request: Optional["ChatJoinRequest"] = None
    chat_boost: Optional["ChatBoostUpdated"] = None
    removed_chat_boost: Optional["ChatBoostRemoved"] = None
    managed_bot: Optional["ManagedBotUpdated"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "update_id": {"py": "update_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message": {"py": "message", "is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "edited_message": {"py": "edited_message", "is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "channel_post": {"py": "channel_post", "is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "edited_channel_post": {"py": "edited_channel_post", "is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "business_connection": {"py": "business_connection", "is_object": True, "inner_object": 'BusinessConnection', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "business_message": {"py": "business_message", "is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "edited_business_message": {"py": "edited_business_message", "is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "deleted_business_messages": {"py": "deleted_business_messages", "is_object": True, "inner_object": 'BusinessMessagesDeleted', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "guest_message": {"py": "guest_message", "is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message_reaction": {"py": "message_reaction", "is_object": True, "inner_object": 'MessageReactionUpdated', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message_reaction_count": {"py": "message_reaction_count", "is_object": True, "inner_object": 'MessageReactionCountUpdated', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "inline_query": {"py": "inline_query", "is_object": True, "inner_object": 'InlineQuery', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chosen_inline_result": {"py": "chosen_inline_result", "is_object": True, "inner_object": 'ChosenInlineResult', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "callback_query": {"py": "callback_query", "is_object": True, "inner_object": 'CallbackQuery', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "shipping_query": {"py": "shipping_query", "is_object": True, "inner_object": 'ShippingQuery', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "pre_checkout_query": {"py": "pre_checkout_query", "is_object": True, "inner_object": 'PreCheckoutQuery', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "purchased_paid_media": {"py": "purchased_paid_media", "is_object": True, "inner_object": 'PaidMediaPurchased', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "poll": {"py": "poll", "is_object": True, "inner_object": 'Poll', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "poll_answer": {"py": "poll_answer", "is_object": True, "inner_object": 'PollAnswer', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "my_chat_member": {"py": "my_chat_member", "is_object": True, "inner_object": 'ChatMemberUpdated', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat_member": {"py": "chat_member", "is_object": True, "inner_object": 'ChatMemberUpdated', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat_join_request": {"py": "chat_join_request", "is_object": True, "inner_object": 'ChatJoinRequest', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat_boost": {"py": "chat_boost", "is_object": True, "inner_object": 'ChatBoostUpdated', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "removed_chat_boost": {"py": "removed_chat_boost", "is_object": True, "inner_object": 'ChatBoostRemoved', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "managed_bot": {"py": "managed_bot", "is_object": True, "inner_object": 'ManagedBotUpdated', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class WebhookInfo(TelegramObject):
    """Describes the current status of a webhook."""
    url: str
    has_custom_certificate: bool
    pending_update_count: int
    ip_address: Optional[str] = None
    last_error_date: Optional[int] = None
    last_error_message: Optional[str] = None
    last_synchronization_error_date: Optional[int] = None
    max_connections: Optional[int] = None
    allowed_updates: Optional[List[str]] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "url": {"py": "url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "has_custom_certificate": {"py": "has_custom_certificate", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "pending_update_count": {"py": "pending_update_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "ip_address": {"py": "ip_address", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "last_error_date": {"py": "last_error_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "last_error_message": {"py": "last_error_message", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "last_synchronization_error_date": {"py": "last_synchronization_error_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "max_connections": {"py": "max_connections", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "allowed_updates": {"py": "allowed_updates", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": None, "list_depth": 1},
    }


@_register_type
@dataclass
class User(TelegramObject):
    """This object represents a Telegram user or bot."""
    id: int
    is_bot: bool
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None
    is_premium: Optional[bool] = None
    added_to_attachment_menu: Optional[bool] = None
    can_join_groups: Optional[bool] = None
    can_read_all_group_messages: Optional[bool] = None
    supports_guest_queries: Optional[bool] = None
    supports_inline_queries: Optional[bool] = None
    can_connect_to_business: Optional[bool] = None
    has_main_web_app: Optional[bool] = None
    has_topics_enabled: Optional[bool] = None
    allows_users_to_create_topics: Optional[bool] = None
    can_manage_bots: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_bot": {"py": "is_bot", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "first_name": {"py": "first_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "last_name": {"py": "last_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "username": {"py": "username", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "language_code": {"py": "language_code", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_premium": {"py": "is_premium", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "added_to_attachment_menu": {"py": "added_to_attachment_menu", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_join_groups": {"py": "can_join_groups", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_read_all_group_messages": {"py": "can_read_all_group_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "supports_guest_queries": {"py": "supports_guest_queries", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "supports_inline_queries": {"py": "supports_inline_queries", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_connect_to_business": {"py": "can_connect_to_business", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "has_main_web_app": {"py": "has_main_web_app", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "has_topics_enabled": {"py": "has_topics_enabled", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "allows_users_to_create_topics": {"py": "allows_users_to_create_topics", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_manage_bots": {"py": "can_manage_bots", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class Chat(TelegramObject):
    """This object represents a chat."""
    id: int
    type_val: str
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_forum: Optional[bool] = None
    is_direct_messages: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "username": {"py": "username", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "first_name": {"py": "first_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "last_name": {"py": "last_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_forum": {"py": "is_forum", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_direct_messages": {"py": "is_direct_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatFullInfo(TelegramObject):
    """This object contains full information about a chat."""
    id: int
    type_val: str
    accent_color_id: int
    max_reaction_count: int
    accepted_gift_types: "AcceptedGiftTypes"
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_forum: Optional[bool] = None
    is_direct_messages: Optional[bool] = None
    photo: Optional["ChatPhoto"] = None
    active_usernames: Optional[List[str]] = None
    birthdate: Optional["Birthdate"] = None
    business_intro: Optional["BusinessIntro"] = None
    business_location: Optional["BusinessLocation"] = None
    business_opening_hours: Optional["BusinessOpeningHours"] = None
    personal_chat: Optional["Chat"] = None
    parent_chat: Optional["Chat"] = None
    available_reactions: Optional[List["ReactionType"]] = None
    background_custom_emoji_id: Optional[str] = None
    profile_accent_color_id: Optional[int] = None
    profile_background_custom_emoji_id: Optional[str] = None
    emoji_status_custom_emoji_id: Optional[str] = None
    emoji_status_expiration_date: Optional[int] = None
    bio: Optional[str] = None
    has_private_forwards: Optional[bool] = None
    has_restricted_voice_and_video_messages: Optional[bool] = None
    join_to_send_messages: Optional[bool] = None
    join_by_request: Optional[bool] = None
    description: Optional[str] = None
    invite_link: Optional[str] = None
    pinned_message: Optional["Message"] = None
    permissions: Optional["ChatPermissions"] = None
    can_send_paid_media: Optional[bool] = None
    slow_mode_delay: Optional[int] = None
    unrestrict_boost_count: Optional[int] = None
    message_auto_delete_time: Optional[int] = None
    has_aggressive_anti_spam_enabled: Optional[bool] = None
    has_hidden_members: Optional[bool] = None
    has_protected_content: Optional[bool] = None
    has_visible_history: Optional[bool] = None
    sticker_set_name: Optional[str] = None
    can_set_sticker_set: Optional[bool] = None
    custom_emoji_sticker_set_name: Optional[str] = None
    linked_chat_id: Optional[int] = None
    location: Optional["ChatLocation"] = None
    rating: Optional["UserRating"] = None
    first_profile_audio: Optional["Audio"] = None
    unique_gift_colors: Optional["UniqueGiftColors"] = None
    paid_message_star_count: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "username": {"py": "username", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "first_name": {"py": "first_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "last_name": {"py": "last_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_forum": {"py": "is_forum", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_direct_messages": {"py": "is_direct_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "accent_color_id": {"py": "accent_color_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "max_reaction_count": {"py": "max_reaction_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo": {"py": "photo", "is_object": True, "inner_object": 'ChatPhoto', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "active_usernames": {"py": "active_usernames", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": None, "list_depth": 1},
        "birthdate": {"py": "birthdate", "is_object": True, "inner_object": 'Birthdate', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "business_intro": {"py": "business_intro", "is_object": True, "inner_object": 'BusinessIntro', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "business_location": {"py": "business_location", "is_object": True, "inner_object": 'BusinessLocation', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "business_opening_hours": {"py": "business_opening_hours", "is_object": True, "inner_object": 'BusinessOpeningHours', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "personal_chat": {"py": "personal_chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parent_chat": {"py": "parent_chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "available_reactions": {"py": "available_reactions", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'ReactionType', "list_depth": 1},
        "background_custom_emoji_id": {"py": "background_custom_emoji_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "profile_accent_color_id": {"py": "profile_accent_color_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "profile_background_custom_emoji_id": {"py": "profile_background_custom_emoji_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "emoji_status_custom_emoji_id": {"py": "emoji_status_custom_emoji_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "emoji_status_expiration_date": {"py": "emoji_status_expiration_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "bio": {"py": "bio", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "has_private_forwards": {"py": "has_private_forwards", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "has_restricted_voice_and_video_messages": {"py": "has_restricted_voice_and_video_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "join_to_send_messages": {"py": "join_to_send_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "join_by_request": {"py": "join_by_request", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "description": {"py": "description", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "invite_link": {"py": "invite_link", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "pinned_message": {"py": "pinned_message", "is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "permissions": {"py": "permissions", "is_object": True, "inner_object": 'ChatPermissions', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "accepted_gift_types": {"py": "accepted_gift_types", "is_object": True, "inner_object": 'AcceptedGiftTypes', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_send_paid_media": {"py": "can_send_paid_media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "slow_mode_delay": {"py": "slow_mode_delay", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "unrestrict_boost_count": {"py": "unrestrict_boost_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message_auto_delete_time": {"py": "message_auto_delete_time", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "has_aggressive_anti_spam_enabled": {"py": "has_aggressive_anti_spam_enabled", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "has_hidden_members": {"py": "has_hidden_members", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "has_protected_content": {"py": "has_protected_content", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "has_visible_history": {"py": "has_visible_history", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "sticker_set_name": {"py": "sticker_set_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_set_sticker_set": {"py": "can_set_sticker_set", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "custom_emoji_sticker_set_name": {"py": "custom_emoji_sticker_set_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "linked_chat_id": {"py": "linked_chat_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "location": {"py": "location", "is_object": True, "inner_object": 'ChatLocation', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "rating": {"py": "rating", "is_object": True, "inner_object": 'UserRating', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "first_profile_audio": {"py": "first_profile_audio", "is_object": True, "inner_object": 'Audio', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "unique_gift_colors": {"py": "unique_gift_colors", "is_object": True, "inner_object": 'UniqueGiftColors', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "paid_message_star_count": {"py": "paid_message_star_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class Message(TelegramObject):
    """This object represents a message."""
    message_id: int
    date: int
    chat: "Chat"
    message_thread_id: Optional[int] = None
    direct_messages_topic: Optional["DirectMessagesTopic"] = None
    from_user: Optional["User"] = None
    sender_chat: Optional["Chat"] = None
    sender_boost_count: Optional[int] = None
    sender_business_bot: Optional["User"] = None
    sender_tag: Optional[str] = None
    guest_query_id: Optional[str] = None
    business_connection_id: Optional[str] = None
    forward_origin: Optional["MessageOrigin"] = None
    is_topic_message: Optional[bool] = None
    is_automatic_forward: Optional[bool] = None
    reply_to_message: Optional["Message"] = None
    external_reply: Optional["ExternalReplyInfo"] = None
    quote: Optional["TextQuote"] = None
    reply_to_story: Optional["Story"] = None
    reply_to_checklist_task_id: Optional[int] = None
    reply_to_poll_option_id: Optional[str] = None
    via_bot: Optional["User"] = None
    guest_bot_caller_user: Optional["User"] = None
    guest_bot_caller_chat: Optional["Chat"] = None
    edit_date: Optional[int] = None
    has_protected_content: Optional[bool] = None
    is_from_offline: Optional[bool] = None
    is_paid_post: Optional[bool] = None
    media_group_id: Optional[str] = None
    author_signature: Optional[str] = None
    paid_star_count: Optional[int] = None
    text: Optional[str] = None
    entities: Optional[List["MessageEntity"]] = None
    link_preview_options: Optional["LinkPreviewOptions"] = None
    suggested_post_info: Optional["SuggestedPostInfo"] = None
    effect_id: Optional[str] = None
    animation: Optional["Animation"] = None
    audio: Optional["Audio"] = None
    document: Optional["Document"] = None
    live_photo: Optional["LivePhoto"] = None
    paid_media: Optional["PaidMediaInfo"] = None
    photo: Optional[List["PhotoSize"]] = None
    sticker: Optional["Sticker"] = None
    story: Optional["Story"] = None
    video: Optional["Video"] = None
    video_note: Optional["VideoNote"] = None
    voice: Optional["Voice"] = None
    caption: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    show_caption_above_media: Optional[bool] = None
    has_media_spoiler: Optional[bool] = None
    checklist: Optional["Checklist"] = None
    contact: Optional["Contact"] = None
    dice: Optional["Dice"] = None
    game: Optional["Game"] = None
    poll: Optional["Poll"] = None
    venue: Optional["Venue"] = None
    location: Optional["Location"] = None
    new_chat_members: Optional[List["User"]] = None
    left_chat_member: Optional["User"] = None
    chat_owner_left: Optional["ChatOwnerLeft"] = None
    chat_owner_changed: Optional["ChatOwnerChanged"] = None
    new_chat_title: Optional[str] = None
    new_chat_photo: Optional[List["PhotoSize"]] = None
    delete_chat_photo: Optional[bool] = None
    group_chat_created: Optional[bool] = None
    supergroup_chat_created: Optional[bool] = None
    channel_chat_created: Optional[bool] = None
    message_auto_delete_timer_changed: Optional["MessageAutoDeleteTimerChanged"] = None
    migrate_to_chat_id: Optional[int] = None
    migrate_from_chat_id: Optional[int] = None
    pinned_message: Optional["MaybeInaccessibleMessage"] = None
    invoice: Optional["Invoice"] = None
    successful_payment: Optional["SuccessfulPayment"] = None
    refunded_payment: Optional["RefundedPayment"] = None
    users_shared: Optional["UsersShared"] = None
    chat_shared: Optional["ChatShared"] = None
    gift: Optional["GiftInfo"] = None
    unique_gift: Optional["UniqueGiftInfo"] = None
    gift_upgrade_sent: Optional["GiftInfo"] = None
    connected_website: Optional[str] = None
    write_access_allowed: Optional["WriteAccessAllowed"] = None
    passport_data: Optional["PassportData"] = None
    proximity_alert_triggered: Optional["ProximityAlertTriggered"] = None
    boost_added: Optional["ChatBoostAdded"] = None
    chat_background_set: Optional["ChatBackground"] = None
    checklist_tasks_done: Optional["ChecklistTasksDone"] = None
    checklist_tasks_added: Optional["ChecklistTasksAdded"] = None
    direct_message_price_changed: Optional["DirectMessagePriceChanged"] = None
    forum_topic_created: Optional["ForumTopicCreated"] = None
    forum_topic_edited: Optional["ForumTopicEdited"] = None
    forum_topic_closed: Optional["ForumTopicClosed"] = None
    forum_topic_reopened: Optional["ForumTopicReopened"] = None
    general_forum_topic_hidden: Optional["GeneralForumTopicHidden"] = None
    general_forum_topic_unhidden: Optional["GeneralForumTopicUnhidden"] = None
    giveaway_created: Optional["GiveawayCreated"] = None
    giveaway: Optional["Giveaway"] = None
    giveaway_winners: Optional["GiveawayWinners"] = None
    giveaway_completed: Optional["GiveawayCompleted"] = None
    managed_bot_created: Optional["ManagedBotCreated"] = None
    paid_message_price_changed: Optional["PaidMessagePriceChanged"] = None
    poll_option_added: Optional["PollOptionAdded"] = None
    poll_option_deleted: Optional["PollOptionDeleted"] = None
    suggested_post_approved: Optional["SuggestedPostApproved"] = None
    suggested_post_approval_failed: Optional["SuggestedPostApprovalFailed"] = None
    suggested_post_declined: Optional["SuggestedPostDeclined"] = None
    suggested_post_paid: Optional["SuggestedPostPaid"] = None
    suggested_post_refunded: Optional["SuggestedPostRefunded"] = None
    video_chat_scheduled: Optional["VideoChatScheduled"] = None
    video_chat_started: Optional["VideoChatStarted"] = None
    video_chat_ended: Optional["VideoChatEnded"] = None
    video_chat_participants_invited: Optional["VideoChatParticipantsInvited"] = None
    web_app_data: Optional["WebAppData"] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "message_id": {"py": "message_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message_thread_id": {"py": "message_thread_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "direct_messages_topic": {"py": "direct_messages_topic", "is_object": True, "inner_object": 'DirectMessagesTopic', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "from": {"py": "from_user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "sender_chat": {"py": "sender_chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "sender_boost_count": {"py": "sender_boost_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "sender_business_bot": {"py": "sender_business_bot", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "sender_tag": {"py": "sender_tag", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "date": {"py": "date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "guest_query_id": {"py": "guest_query_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "business_connection_id": {"py": "business_connection_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat": {"py": "chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "forward_origin": {"py": "forward_origin", "is_object": True, "inner_object": 'MessageOrigin', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_topic_message": {"py": "is_topic_message", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_automatic_forward": {"py": "is_automatic_forward", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_to_message": {"py": "reply_to_message", "is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "external_reply": {"py": "external_reply", "is_object": True, "inner_object": 'ExternalReplyInfo', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "quote": {"py": "quote", "is_object": True, "inner_object": 'TextQuote', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_to_story": {"py": "reply_to_story", "is_object": True, "inner_object": 'Story', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_to_checklist_task_id": {"py": "reply_to_checklist_task_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_to_poll_option_id": {"py": "reply_to_poll_option_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "via_bot": {"py": "via_bot", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "guest_bot_caller_user": {"py": "guest_bot_caller_user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "guest_bot_caller_chat": {"py": "guest_bot_caller_chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "edit_date": {"py": "edit_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "has_protected_content": {"py": "has_protected_content", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_from_offline": {"py": "is_from_offline", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_paid_post": {"py": "is_paid_post", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "media_group_id": {"py": "media_group_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "author_signature": {"py": "author_signature", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "paid_star_count": {"py": "paid_star_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "text": {"py": "text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "entities": {"py": "entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "link_preview_options": {"py": "link_preview_options", "is_object": True, "inner_object": 'LinkPreviewOptions', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "suggested_post_info": {"py": "suggested_post_info", "is_object": True, "inner_object": 'SuggestedPostInfo', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "effect_id": {"py": "effect_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "animation": {"py": "animation", "is_object": True, "inner_object": 'Animation', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "audio": {"py": "audio", "is_object": True, "inner_object": 'Audio', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "document": {"py": "document", "is_object": True, "inner_object": 'Document', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "live_photo": {"py": "live_photo", "is_object": True, "inner_object": 'LivePhoto', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "paid_media": {"py": "paid_media", "is_object": True, "inner_object": 'PaidMediaInfo', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo": {"py": "photo", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'PhotoSize', "list_depth": 1},
        "sticker": {"py": "sticker", "is_object": True, "inner_object": 'Sticker', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "story": {"py": "story", "is_object": True, "inner_object": 'Story', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "video": {"py": "video", "is_object": True, "inner_object": 'Video', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "video_note": {"py": "video_note", "is_object": True, "inner_object": 'VideoNote', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "voice": {"py": "voice", "is_object": True, "inner_object": 'Voice', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "show_caption_above_media": {"py": "show_caption_above_media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "has_media_spoiler": {"py": "has_media_spoiler", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "checklist": {"py": "checklist", "is_object": True, "inner_object": 'Checklist', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "contact": {"py": "contact", "is_object": True, "inner_object": 'Contact', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "dice": {"py": "dice", "is_object": True, "inner_object": 'Dice', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "game": {"py": "game", "is_object": True, "inner_object": 'Game', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "poll": {"py": "poll", "is_object": True, "inner_object": 'Poll', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "venue": {"py": "venue", "is_object": True, "inner_object": 'Venue', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "location": {"py": "location", "is_object": True, "inner_object": 'Location', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "new_chat_members": {"py": "new_chat_members", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'User', "list_depth": 1},
        "left_chat_member": {"py": "left_chat_member", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat_owner_left": {"py": "chat_owner_left", "is_object": True, "inner_object": 'ChatOwnerLeft', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat_owner_changed": {"py": "chat_owner_changed", "is_object": True, "inner_object": 'ChatOwnerChanged', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "new_chat_title": {"py": "new_chat_title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "new_chat_photo": {"py": "new_chat_photo", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'PhotoSize', "list_depth": 1},
        "delete_chat_photo": {"py": "delete_chat_photo", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "group_chat_created": {"py": "group_chat_created", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "supergroup_chat_created": {"py": "supergroup_chat_created", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "channel_chat_created": {"py": "channel_chat_created", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message_auto_delete_timer_changed": {"py": "message_auto_delete_timer_changed", "is_object": True, "inner_object": 'MessageAutoDeleteTimerChanged', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "migrate_to_chat_id": {"py": "migrate_to_chat_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "migrate_from_chat_id": {"py": "migrate_from_chat_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "pinned_message": {"py": "pinned_message", "is_object": True, "inner_object": 'MaybeInaccessibleMessage', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "invoice": {"py": "invoice", "is_object": True, "inner_object": 'Invoice', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "successful_payment": {"py": "successful_payment", "is_object": True, "inner_object": 'SuccessfulPayment', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "refunded_payment": {"py": "refunded_payment", "is_object": True, "inner_object": 'RefundedPayment', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "users_shared": {"py": "users_shared", "is_object": True, "inner_object": 'UsersShared', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat_shared": {"py": "chat_shared", "is_object": True, "inner_object": 'ChatShared', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "gift": {"py": "gift", "is_object": True, "inner_object": 'GiftInfo', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "unique_gift": {"py": "unique_gift", "is_object": True, "inner_object": 'UniqueGiftInfo', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "gift_upgrade_sent": {"py": "gift_upgrade_sent", "is_object": True, "inner_object": 'GiftInfo', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "connected_website": {"py": "connected_website", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "write_access_allowed": {"py": "write_access_allowed", "is_object": True, "inner_object": 'WriteAccessAllowed', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "passport_data": {"py": "passport_data", "is_object": True, "inner_object": 'PassportData', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "proximity_alert_triggered": {"py": "proximity_alert_triggered", "is_object": True, "inner_object": 'ProximityAlertTriggered', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "boost_added": {"py": "boost_added", "is_object": True, "inner_object": 'ChatBoostAdded', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat_background_set": {"py": "chat_background_set", "is_object": True, "inner_object": 'ChatBackground', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "checklist_tasks_done": {"py": "checklist_tasks_done", "is_object": True, "inner_object": 'ChecklistTasksDone', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "checklist_tasks_added": {"py": "checklist_tasks_added", "is_object": True, "inner_object": 'ChecklistTasksAdded', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "direct_message_price_changed": {"py": "direct_message_price_changed", "is_object": True, "inner_object": 'DirectMessagePriceChanged', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "forum_topic_created": {"py": "forum_topic_created", "is_object": True, "inner_object": 'ForumTopicCreated', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "forum_topic_edited": {"py": "forum_topic_edited", "is_object": True, "inner_object": 'ForumTopicEdited', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "forum_topic_closed": {"py": "forum_topic_closed", "is_object": True, "inner_object": 'ForumTopicClosed', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "forum_topic_reopened": {"py": "forum_topic_reopened", "is_object": True, "inner_object": 'ForumTopicReopened', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "general_forum_topic_hidden": {"py": "general_forum_topic_hidden", "is_object": True, "inner_object": 'GeneralForumTopicHidden', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "general_forum_topic_unhidden": {"py": "general_forum_topic_unhidden", "is_object": True, "inner_object": 'GeneralForumTopicUnhidden', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "giveaway_created": {"py": "giveaway_created", "is_object": True, "inner_object": 'GiveawayCreated', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "giveaway": {"py": "giveaway", "is_object": True, "inner_object": 'Giveaway', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "giveaway_winners": {"py": "giveaway_winners", "is_object": True, "inner_object": 'GiveawayWinners', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "giveaway_completed": {"py": "giveaway_completed", "is_object": True, "inner_object": 'GiveawayCompleted', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "managed_bot_created": {"py": "managed_bot_created", "is_object": True, "inner_object": 'ManagedBotCreated', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "paid_message_price_changed": {"py": "paid_message_price_changed", "is_object": True, "inner_object": 'PaidMessagePriceChanged', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "poll_option_added": {"py": "poll_option_added", "is_object": True, "inner_object": 'PollOptionAdded', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "poll_option_deleted": {"py": "poll_option_deleted", "is_object": True, "inner_object": 'PollOptionDeleted', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "suggested_post_approved": {"py": "suggested_post_approved", "is_object": True, "inner_object": 'SuggestedPostApproved', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "suggested_post_approval_failed": {"py": "suggested_post_approval_failed", "is_object": True, "inner_object": 'SuggestedPostApprovalFailed', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "suggested_post_declined": {"py": "suggested_post_declined", "is_object": True, "inner_object": 'SuggestedPostDeclined', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "suggested_post_paid": {"py": "suggested_post_paid", "is_object": True, "inner_object": 'SuggestedPostPaid', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "suggested_post_refunded": {"py": "suggested_post_refunded", "is_object": True, "inner_object": 'SuggestedPostRefunded', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "video_chat_scheduled": {"py": "video_chat_scheduled", "is_object": True, "inner_object": 'VideoChatScheduled', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "video_chat_started": {"py": "video_chat_started", "is_object": True, "inner_object": 'VideoChatStarted', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "video_chat_ended": {"py": "video_chat_ended", "is_object": True, "inner_object": 'VideoChatEnded', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "video_chat_participants_invited": {"py": "video_chat_participants_invited", "is_object": True, "inner_object": 'VideoChatParticipantsInvited', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "web_app_data": {"py": "web_app_data", "is_object": True, "inner_object": 'WebAppData', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class MessageId(TelegramObject):
    """This object represents a unique message identifier."""
    message_id: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "message_id": {"py": "message_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InaccessibleMessage(TelegramObject):
    """This object describes a message that was deleted or is otherwise inaccessible to the bot."""
    chat: "Chat"
    message_id: int
    date: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "chat": {"py": "chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message_id": {"py": "message_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "date": {"py": "date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class MessageEntity(TelegramObject):
    """This object represents one special entity in a text message. For example, hashtags, usernames, URLs, etc."""
    type_val: str
    offset: int
    length: int
    url: Optional[str] = None
    user: Optional["User"] = None
    language: Optional[str] = None
    custom_emoji_id: Optional[str] = None
    unix_time: Optional[int] = None
    date_time_format: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "offset": {"py": "offset", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "length": {"py": "length", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "url": {"py": "url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user": {"py": "user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "language": {"py": "language", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "custom_emoji_id": {"py": "custom_emoji_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "unix_time": {"py": "unix_time", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "date_time_format": {"py": "date_time_format", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class TextQuote(TelegramObject):
    """This object contains information about the quoted part of a message that is replied to by the given message."""
    text: str
    position: int
    entities: Optional[List["MessageEntity"]] = None
    is_manual: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "text": {"py": "text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "entities": {"py": "entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "position": {"py": "position", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_manual": {"py": "is_manual", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ExternalReplyInfo(TelegramObject):
    """This object contains information about a message that is being replied to, which may come from another chat or forum topic."""
    origin: "MessageOrigin"
    chat: Optional["Chat"] = None
    message_id: Optional[int] = None
    link_preview_options: Optional["LinkPreviewOptions"] = None
    animation: Optional["Animation"] = None
    audio: Optional["Audio"] = None
    document: Optional["Document"] = None
    live_photo: Optional["LivePhoto"] = None
    paid_media: Optional["PaidMediaInfo"] = None
    photo: Optional[List["PhotoSize"]] = None
    sticker: Optional["Sticker"] = None
    story: Optional["Story"] = None
    video: Optional["Video"] = None
    video_note: Optional["VideoNote"] = None
    voice: Optional["Voice"] = None
    has_media_spoiler: Optional[bool] = None
    checklist: Optional["Checklist"] = None
    contact: Optional["Contact"] = None
    dice: Optional["Dice"] = None
    game: Optional["Game"] = None
    giveaway: Optional["Giveaway"] = None
    giveaway_winners: Optional["GiveawayWinners"] = None
    invoice: Optional["Invoice"] = None
    location: Optional["Location"] = None
    poll: Optional["Poll"] = None
    venue: Optional["Venue"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "origin": {"py": "origin", "is_object": True, "inner_object": 'MessageOrigin', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat": {"py": "chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message_id": {"py": "message_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "link_preview_options": {"py": "link_preview_options", "is_object": True, "inner_object": 'LinkPreviewOptions', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "animation": {"py": "animation", "is_object": True, "inner_object": 'Animation', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "audio": {"py": "audio", "is_object": True, "inner_object": 'Audio', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "document": {"py": "document", "is_object": True, "inner_object": 'Document', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "live_photo": {"py": "live_photo", "is_object": True, "inner_object": 'LivePhoto', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "paid_media": {"py": "paid_media", "is_object": True, "inner_object": 'PaidMediaInfo', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo": {"py": "photo", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'PhotoSize', "list_depth": 1},
        "sticker": {"py": "sticker", "is_object": True, "inner_object": 'Sticker', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "story": {"py": "story", "is_object": True, "inner_object": 'Story', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "video": {"py": "video", "is_object": True, "inner_object": 'Video', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "video_note": {"py": "video_note", "is_object": True, "inner_object": 'VideoNote', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "voice": {"py": "voice", "is_object": True, "inner_object": 'Voice', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "has_media_spoiler": {"py": "has_media_spoiler", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "checklist": {"py": "checklist", "is_object": True, "inner_object": 'Checklist', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "contact": {"py": "contact", "is_object": True, "inner_object": 'Contact', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "dice": {"py": "dice", "is_object": True, "inner_object": 'Dice', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "game": {"py": "game", "is_object": True, "inner_object": 'Game', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "giveaway": {"py": "giveaway", "is_object": True, "inner_object": 'Giveaway', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "giveaway_winners": {"py": "giveaway_winners", "is_object": True, "inner_object": 'GiveawayWinners', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "invoice": {"py": "invoice", "is_object": True, "inner_object": 'Invoice', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "location": {"py": "location", "is_object": True, "inner_object": 'Location', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "poll": {"py": "poll", "is_object": True, "inner_object": 'Poll', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "venue": {"py": "venue", "is_object": True, "inner_object": 'Venue', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ReplyParameters(TelegramObject):
    """Describes reply parameters for the message that is being sent."""
    message_id: int
    chat_id: Optional[Union[int, str]] = None
    allow_sending_without_reply: Optional[bool] = None
    quote: Optional[str] = None
    quote_parse_mode: Optional[str] = None
    quote_entities: Optional[List["MessageEntity"]] = None
    quote_position: Optional[int] = None
    checklist_task_id: Optional[int] = None
    poll_option_id: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "message_id": {"py": "message_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat_id": {"py": "chat_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "allow_sending_without_reply": {"py": "allow_sending_without_reply", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "quote": {"py": "quote", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "quote_parse_mode": {"py": "quote_parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "quote_entities": {"py": "quote_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "quote_position": {"py": "quote_position", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "checklist_task_id": {"py": "checklist_task_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "poll_option_id": {"py": "poll_option_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class MessageOriginUser(TelegramObject):
    """The message was originally sent by a known user."""
    type_val: str
    date: int
    sender_user: "User"
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "date": {"py": "date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "sender_user": {"py": "sender_user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class MessageOriginHiddenUser(TelegramObject):
    """The message was originally sent by an unknown user."""
    type_val: str
    date: int
    sender_user_name: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "date": {"py": "date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "sender_user_name": {"py": "sender_user_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class MessageOriginChat(TelegramObject):
    """The message was originally sent on behalf of a chat to a group chat."""
    type_val: str
    date: int
    sender_chat: "Chat"
    author_signature: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "date": {"py": "date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "sender_chat": {"py": "sender_chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "author_signature": {"py": "author_signature", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class MessageOriginChannel(TelegramObject):
    """The message was originally sent to a channel chat."""
    type_val: str
    date: int
    chat: "Chat"
    message_id: int
    author_signature: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "date": {"py": "date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat": {"py": "chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message_id": {"py": "message_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "author_signature": {"py": "author_signature", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PhotoSize(TelegramObject):
    """This object represents one size of a photo or a file / sticker thumbnail."""
    file_id: str
    file_unique_id: str
    width: int
    height: int
    file_size: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "file_id": {"py": "file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_unique_id": {"py": "file_unique_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "width": {"py": "width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "height": {"py": "height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_size": {"py": "file_size", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class Animation(TelegramObject):
    """This object represents an animation file (GIF or H.264/MPEG-4 AVC video without sound)."""
    file_id: str
    file_unique_id: str
    width: int
    height: int
    duration: int
    thumbnail: Optional["PhotoSize"] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "file_id": {"py": "file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_unique_id": {"py": "file_unique_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "width": {"py": "width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "height": {"py": "height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "duration": {"py": "duration", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail": {"py": "thumbnail", "is_object": True, "inner_object": 'PhotoSize', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_name": {"py": "file_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "mime_type": {"py": "mime_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_size": {"py": "file_size", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class Audio(TelegramObject):
    """This object represents an audio file to be treated as music by the Telegram clients."""
    file_id: str
    file_unique_id: str
    duration: int
    performer: Optional[str] = None
    title: Optional[str] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    thumbnail: Optional["PhotoSize"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "file_id": {"py": "file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_unique_id": {"py": "file_unique_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "duration": {"py": "duration", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "performer": {"py": "performer", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_name": {"py": "file_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "mime_type": {"py": "mime_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_size": {"py": "file_size", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail": {"py": "thumbnail", "is_object": True, "inner_object": 'PhotoSize', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class Document(TelegramObject):
    """This object represents a general file (as opposed to photos , voice messages and audio files )."""
    file_id: str
    file_unique_id: str
    thumbnail: Optional["PhotoSize"] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "file_id": {"py": "file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_unique_id": {"py": "file_unique_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail": {"py": "thumbnail", "is_object": True, "inner_object": 'PhotoSize', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_name": {"py": "file_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "mime_type": {"py": "mime_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_size": {"py": "file_size", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class LivePhoto(TelegramObject):
    """This object represents a live photo."""
    file_id: str
    file_unique_id: str
    width: int
    height: int
    duration: int
    photo: Optional[List["PhotoSize"]] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "photo": {"py": "photo", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'PhotoSize', "list_depth": 1},
        "file_id": {"py": "file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_unique_id": {"py": "file_unique_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "width": {"py": "width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "height": {"py": "height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "duration": {"py": "duration", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "mime_type": {"py": "mime_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_size": {"py": "file_size", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class Story(TelegramObject):
    """This object represents a story."""
    chat: "Chat"
    id: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "chat": {"py": "chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class VideoQuality(TelegramObject):
    """This object represents a video file of a specific quality."""
    file_id: str
    file_unique_id: str
    width: int
    height: int
    codec: str
    file_size: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "file_id": {"py": "file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_unique_id": {"py": "file_unique_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "width": {"py": "width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "height": {"py": "height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "codec": {"py": "codec", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_size": {"py": "file_size", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class Video(TelegramObject):
    """This object represents a video file."""
    file_id: str
    file_unique_id: str
    width: int
    height: int
    duration: int
    thumbnail: Optional["PhotoSize"] = None
    cover: Optional[List["PhotoSize"]] = None
    start_timestamp: Optional[int] = None
    qualities: Optional[List["VideoQuality"]] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "file_id": {"py": "file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_unique_id": {"py": "file_unique_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "width": {"py": "width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "height": {"py": "height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "duration": {"py": "duration", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail": {"py": "thumbnail", "is_object": True, "inner_object": 'PhotoSize', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "cover": {"py": "cover", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'PhotoSize', "list_depth": 1},
        "start_timestamp": {"py": "start_timestamp", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "qualities": {"py": "qualities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'VideoQuality', "list_depth": 1},
        "file_name": {"py": "file_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "mime_type": {"py": "mime_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_size": {"py": "file_size", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class VideoNote(TelegramObject):
    """This object represents a video message (available in Telegram apps as of v.4.0 )."""
    file_id: str
    file_unique_id: str
    length: int
    duration: int
    thumbnail: Optional["PhotoSize"] = None
    file_size: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "file_id": {"py": "file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_unique_id": {"py": "file_unique_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "length": {"py": "length", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "duration": {"py": "duration", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail": {"py": "thumbnail", "is_object": True, "inner_object": 'PhotoSize', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_size": {"py": "file_size", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class Voice(TelegramObject):
    """This object represents a voice note."""
    file_id: str
    file_unique_id: str
    duration: int
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "file_id": {"py": "file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_unique_id": {"py": "file_unique_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "duration": {"py": "duration", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "mime_type": {"py": "mime_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_size": {"py": "file_size", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PaidMediaInfo(TelegramObject):
    """Describes the paid media added to a message."""
    star_count: int
    paid_media: List["PaidMedia"]
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "star_count": {"py": "star_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "paid_media": {"py": "paid_media", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'PaidMedia', "list_depth": 1},
    }


@_register_type
@dataclass
class PaidMediaLivePhoto(TelegramObject):
    """The paid media is a live photo ."""
    type_val: str
    live_photo: "LivePhoto"
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "live_photo": {"py": "live_photo", "is_object": True, "inner_object": 'LivePhoto', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PaidMediaPhoto(TelegramObject):
    """The paid media is a photo."""
    type_val: str
    photo: List["PhotoSize"]
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo": {"py": "photo", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'PhotoSize', "list_depth": 1},
    }


@_register_type
@dataclass
class PaidMediaPreview(TelegramObject):
    """The paid media isn't available before the payment."""
    type_val: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "width": {"py": "width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "height": {"py": "height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "duration": {"py": "duration", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PaidMediaVideo(TelegramObject):
    """The paid media is a video."""
    type_val: str
    video: "Video"
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "video": {"py": "video", "is_object": True, "inner_object": 'Video', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class Contact(TelegramObject):
    """This object represents a phone contact."""
    phone_number: str
    first_name: str
    last_name: Optional[str] = None
    user_id: Optional[int] = None
    vcard: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "phone_number": {"py": "phone_number", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "first_name": {"py": "first_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "last_name": {"py": "last_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user_id": {"py": "user_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "vcard": {"py": "vcard", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class Dice(TelegramObject):
    """This object represents an animated emoji that displays a random value."""
    emoji: str
    value: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "emoji": {"py": "emoji", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "value": {"py": "value", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PollMedia(TelegramObject):
    """At most one of the optional fields can be present in any given object."""
    animation: Optional["Animation"] = None
    audio: Optional["Audio"] = None
    document: Optional["Document"] = None
    live_photo: Optional["LivePhoto"] = None
    location: Optional["Location"] = None
    photo: Optional[List["PhotoSize"]] = None
    sticker: Optional["Sticker"] = None
    venue: Optional["Venue"] = None
    video: Optional["Video"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "animation": {"py": "animation", "is_object": True, "inner_object": 'Animation', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "audio": {"py": "audio", "is_object": True, "inner_object": 'Audio', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "document": {"py": "document", "is_object": True, "inner_object": 'Document', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "live_photo": {"py": "live_photo", "is_object": True, "inner_object": 'LivePhoto', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "location": {"py": "location", "is_object": True, "inner_object": 'Location', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo": {"py": "photo", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'PhotoSize', "list_depth": 1},
        "sticker": {"py": "sticker", "is_object": True, "inner_object": 'Sticker', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "venue": {"py": "venue", "is_object": True, "inner_object": 'Venue', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "video": {"py": "video", "is_object": True, "inner_object": 'Video', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PollOption(TelegramObject):
    """This object contains information about one answer option in a poll."""
    persistent_id: str
    text: str
    voter_count: int
    text_entities: Optional[List["MessageEntity"]] = None
    media: Optional["PollMedia"] = None
    added_by_user: Optional["User"] = None
    added_by_chat: Optional["Chat"] = None
    addition_date: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "persistent_id": {"py": "persistent_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "text": {"py": "text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "text_entities": {"py": "text_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "media": {"py": "media", "is_object": True, "inner_object": 'PollMedia', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "voter_count": {"py": "voter_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "added_by_user": {"py": "added_by_user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "added_by_chat": {"py": "added_by_chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "addition_date": {"py": "addition_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputPollOption(TelegramObject):
    """This object contains information about one answer option in a poll to be sent."""
    text: str
    text_parse_mode: Optional[str] = None
    text_entities: Optional[List["MessageEntity"]] = None
    media: Optional["InputPollOptionMedia"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "text": {"py": "text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "text_parse_mode": {"py": "text_parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "text_entities": {"py": "text_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "media": {"py": "media", "is_object": True, "inner_object": 'InputPollOptionMedia', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PollAnswer(TelegramObject):
    """This object represents an answer of a user in a non-anonymous poll."""
    poll_id: str
    option_ids: List[int]
    option_persistent_ids: List[str]
    voter_chat: Optional["Chat"] = None
    user: Optional["User"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "poll_id": {"py": "poll_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "voter_chat": {"py": "voter_chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user": {"py": "user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "option_ids": {"py": "option_ids", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": None, "list_depth": 1},
        "option_persistent_ids": {"py": "option_persistent_ids", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": None, "list_depth": 1},
    }


@_register_type
@dataclass
class Poll(TelegramObject):
    """This object contains information about a poll."""
    id: str
    question: str
    options: List["PollOption"]
    total_voter_count: int
    is_closed: bool
    is_anonymous: bool
    type_val: str
    allows_multiple_answers: bool
    allows_revoting: bool
    members_only: bool
    question_entities: Optional[List["MessageEntity"]] = None
    country_codes: Optional[List[str]] = None
    correct_option_ids: Optional[List[int]] = None
    explanation: Optional[str] = None
    explanation_entities: Optional[List["MessageEntity"]] = None
    explanation_media: Optional["PollMedia"] = None
    open_period: Optional[int] = None
    close_date: Optional[int] = None
    description: Optional[str] = None
    description_entities: Optional[List["MessageEntity"]] = None
    media: Optional["PollMedia"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "question": {"py": "question", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "question_entities": {"py": "question_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "options": {"py": "options", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'PollOption', "list_depth": 1},
        "total_voter_count": {"py": "total_voter_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_closed": {"py": "is_closed", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_anonymous": {"py": "is_anonymous", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "allows_multiple_answers": {"py": "allows_multiple_answers", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "allows_revoting": {"py": "allows_revoting", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "members_only": {"py": "members_only", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "country_codes": {"py": "country_codes", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": None, "list_depth": 1},
        "correct_option_ids": {"py": "correct_option_ids", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": None, "list_depth": 1},
        "explanation": {"py": "explanation", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "explanation_entities": {"py": "explanation_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "explanation_media": {"py": "explanation_media", "is_object": True, "inner_object": 'PollMedia', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "open_period": {"py": "open_period", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "close_date": {"py": "close_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "description": {"py": "description", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "description_entities": {"py": "description_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "media": {"py": "media", "is_object": True, "inner_object": 'PollMedia', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChecklistTask(TelegramObject):
    """Describes a task in a checklist."""
    id: int
    text: str
    text_entities: Optional[List["MessageEntity"]] = None
    completed_by_user: Optional["User"] = None
    completed_by_chat: Optional["Chat"] = None
    completion_date: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "text": {"py": "text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "text_entities": {"py": "text_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "completed_by_user": {"py": "completed_by_user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "completed_by_chat": {"py": "completed_by_chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "completion_date": {"py": "completion_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class Checklist(TelegramObject):
    """Describes a checklist."""
    title: str
    tasks: List["ChecklistTask"]
    title_entities: Optional[List["MessageEntity"]] = None
    others_can_add_tasks: Optional[bool] = None
    others_can_mark_tasks_as_done: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title_entities": {"py": "title_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "tasks": {"py": "tasks", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'ChecklistTask', "list_depth": 1},
        "others_can_add_tasks": {"py": "others_can_add_tasks", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "others_can_mark_tasks_as_done": {"py": "others_can_mark_tasks_as_done", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputChecklistTask(TelegramObject):
    """Describes a task to add to a checklist."""
    id: int
    text: str
    parse_mode: Optional[str] = None
    text_entities: Optional[List["MessageEntity"]] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "text": {"py": "text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "text_entities": {"py": "text_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
    }


@_register_type
@dataclass
class InputChecklist(TelegramObject):
    """Describes a checklist to create."""
    title: str
    tasks: List["InputChecklistTask"]
    parse_mode: Optional[str] = None
    title_entities: Optional[List["MessageEntity"]] = None
    others_can_add_tasks: Optional[bool] = None
    others_can_mark_tasks_as_done: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title_entities": {"py": "title_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "tasks": {"py": "tasks", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'InputChecklistTask', "list_depth": 1},
        "others_can_add_tasks": {"py": "others_can_add_tasks", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "others_can_mark_tasks_as_done": {"py": "others_can_mark_tasks_as_done", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChecklistTasksDone(TelegramObject):
    """Describes a service message about checklist tasks marked as done or not done."""
    checklist_message: Optional["Message"] = None
    marked_as_done_task_ids: Optional[List[int]] = None
    marked_as_not_done_task_ids: Optional[List[int]] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "checklist_message": {"py": "checklist_message", "is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "marked_as_done_task_ids": {"py": "marked_as_done_task_ids", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": None, "list_depth": 1},
        "marked_as_not_done_task_ids": {"py": "marked_as_not_done_task_ids", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": None, "list_depth": 1},
    }


@_register_type
@dataclass
class ChecklistTasksAdded(TelegramObject):
    """Describes a service message about tasks added to a checklist."""
    tasks: List["ChecklistTask"]
    checklist_message: Optional["Message"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "checklist_message": {"py": "checklist_message", "is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "tasks": {"py": "tasks", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'ChecklistTask', "list_depth": 1},
    }


@_register_type
@dataclass
class Location(TelegramObject):
    """This object represents a point on the map."""
    latitude: float
    longitude: float
    horizontal_accuracy: Optional[float] = None
    live_period: Optional[int] = None
    heading: Optional[int] = None
    proximity_alert_radius: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "latitude": {"py": "latitude", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "longitude": {"py": "longitude", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "horizontal_accuracy": {"py": "horizontal_accuracy", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "live_period": {"py": "live_period", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "heading": {"py": "heading", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "proximity_alert_radius": {"py": "proximity_alert_radius", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class Venue(TelegramObject):
    """This object represents a venue."""
    location: "Location"
    title: str
    address: str
    foursquare_id: Optional[str] = None
    foursquare_type: Optional[str] = None
    google_place_id: Optional[str] = None
    google_place_type: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "location": {"py": "location", "is_object": True, "inner_object": 'Location', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "address": {"py": "address", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "foursquare_id": {"py": "foursquare_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "foursquare_type": {"py": "foursquare_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "google_place_id": {"py": "google_place_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "google_place_type": {"py": "google_place_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class WebAppData(TelegramObject):
    """Describes data sent from a Web App to the bot."""
    data: str
    button_text: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "data": {"py": "data", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "button_text": {"py": "button_text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ProximityAlertTriggered(TelegramObject):
    """This object represents the content of a service message, sent whenever a user in the chat triggers a proximity alert set by another user."""
    traveler: "User"
    watcher: "User"
    distance: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "traveler": {"py": "traveler", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "watcher": {"py": "watcher", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "distance": {"py": "distance", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class MessageAutoDeleteTimerChanged(TelegramObject):
    """This object represents a service message about a change in auto-delete timer settings."""
    message_auto_delete_time: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "message_auto_delete_time": {"py": "message_auto_delete_time", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ManagedBotCreated(TelegramObject):
    """This object contains information about the bot that was created to be managed by the current bot."""
    bot: "User"
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "bot": {"py": "bot", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ManagedBotUpdated(TelegramObject):
    """This object contains information about the creation, token update, or owner update of a bot that is managed by the current bot."""
    user: "User"
    bot: "User"
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "user": {"py": "user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "bot": {"py": "bot", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PollOptionAdded(TelegramObject):
    """Describes a service message about an option added to a poll."""
    option_persistent_id: str
    option_text: str
    poll_message: Optional["MaybeInaccessibleMessage"] = None
    option_text_entities: Optional[List["MessageEntity"]] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "poll_message": {"py": "poll_message", "is_object": True, "inner_object": 'MaybeInaccessibleMessage', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "option_persistent_id": {"py": "option_persistent_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "option_text": {"py": "option_text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "option_text_entities": {"py": "option_text_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
    }


@_register_type
@dataclass
class PollOptionDeleted(TelegramObject):
    """Describes a service message about an option deleted from a poll."""
    option_persistent_id: str
    option_text: str
    poll_message: Optional["MaybeInaccessibleMessage"] = None
    option_text_entities: Optional[List["MessageEntity"]] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "poll_message": {"py": "poll_message", "is_object": True, "inner_object": 'MaybeInaccessibleMessage', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "option_persistent_id": {"py": "option_persistent_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "option_text": {"py": "option_text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "option_text_entities": {"py": "option_text_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
    }


@_register_type
@dataclass
class ChatBoostAdded(TelegramObject):
    """This object represents a service message about a user boosting a chat."""
    boost_count: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "boost_count": {"py": "boost_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BackgroundFillSolid(TelegramObject):
    """The background is filled using the selected color."""
    type_val: str
    color: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "color": {"py": "color", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BackgroundFillGradient(TelegramObject):
    """The background is a gradient fill."""
    type_val: str
    top_color: int
    bottom_color: int
    rotation_angle: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "top_color": {"py": "top_color", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "bottom_color": {"py": "bottom_color", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "rotation_angle": {"py": "rotation_angle", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BackgroundFillFreeformGradient(TelegramObject):
    """The background is a freeform gradient that rotates after every message in the chat."""
    type_val: str
    colors: List[int]
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "colors": {"py": "colors", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": None, "list_depth": 1},
    }


@_register_type
@dataclass
class BackgroundTypeFill(TelegramObject):
    """The background is automatically filled based on the selected colors."""
    type_val: str
    fill: "BackgroundFill"
    dark_theme_dimming: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "fill": {"py": "fill", "is_object": True, "inner_object": 'BackgroundFill', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "dark_theme_dimming": {"py": "dark_theme_dimming", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BackgroundTypeWallpaper(TelegramObject):
    """The background is a wallpaper in the JPEG format."""
    type_val: str
    document: "Document"
    dark_theme_dimming: int
    is_blurred: Optional[bool] = None
    is_moving: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "document": {"py": "document", "is_object": True, "inner_object": 'Document', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "dark_theme_dimming": {"py": "dark_theme_dimming", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_blurred": {"py": "is_blurred", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_moving": {"py": "is_moving", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BackgroundTypePattern(TelegramObject):
    """The background is a .PNG or .TGV (gzipped subset of SVG with MIME type “application/x-tgwallpattern”) pattern to be combined with the background fill chosen by the user."""
    type_val: str
    document: "Document"
    fill: "BackgroundFill"
    intensity: int
    is_inverted: Optional[bool] = None
    is_moving: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "document": {"py": "document", "is_object": True, "inner_object": 'Document', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "fill": {"py": "fill", "is_object": True, "inner_object": 'BackgroundFill', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "intensity": {"py": "intensity", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_inverted": {"py": "is_inverted", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_moving": {"py": "is_moving", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BackgroundTypeChatTheme(TelegramObject):
    """The background is taken directly from a built-in chat theme."""
    type_val: str
    theme_name: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "theme_name": {"py": "theme_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatBackground(TelegramObject):
    """This object represents a chat background."""
    type_val: "BackgroundType"
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": True, "inner_object": 'BackgroundType', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ForumTopicCreated(TelegramObject):
    """This object represents a service message about a new forum topic created in the chat."""
    name: str
    icon_color: int
    icon_custom_emoji_id: Optional[str] = None
    is_name_implicit: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "name": {"py": "name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "icon_color": {"py": "icon_color", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "icon_custom_emoji_id": {"py": "icon_custom_emoji_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_name_implicit": {"py": "is_name_implicit", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ForumTopicClosed(TelegramObject):
    """This object represents a service message about a forum topic closed in the chat. Currently holds no information."""
    pass


@_register_type
@dataclass
class ForumTopicEdited(TelegramObject):
    """This object represents a service message about an edited forum topic."""
    name: Optional[str] = None
    icon_custom_emoji_id: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "name": {"py": "name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "icon_custom_emoji_id": {"py": "icon_custom_emoji_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ForumTopicReopened(TelegramObject):
    """This object represents a service message about a forum topic reopened in the chat. Currently holds no information."""
    pass


@_register_type
@dataclass
class GeneralForumTopicHidden(TelegramObject):
    """This object represents a service message about General forum topic hidden in the chat. Currently holds no information."""
    pass


@_register_type
@dataclass
class GeneralForumTopicUnhidden(TelegramObject):
    """This object represents a service message about General forum topic unhidden in the chat. Currently holds no information."""
    pass


@_register_type
@dataclass
class SharedUser(TelegramObject):
    """This object contains information about a user that was shared with the bot using a KeyboardButtonRequestUsers button."""
    user_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo: Optional[List["PhotoSize"]] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "user_id": {"py": "user_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "first_name": {"py": "first_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "last_name": {"py": "last_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "username": {"py": "username", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo": {"py": "photo", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'PhotoSize', "list_depth": 1},
    }


@_register_type
@dataclass
class UsersShared(TelegramObject):
    """This object contains information about the users whose identifiers were shared with the bot using a KeyboardButtonRequestUsers button."""
    request_id: int
    users: List["SharedUser"]
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "request_id": {"py": "request_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "users": {"py": "users", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'SharedUser', "list_depth": 1},
    }


@_register_type
@dataclass
class ChatShared(TelegramObject):
    """This object contains information about a chat that was shared with the bot using a KeyboardButtonRequestChat button."""
    request_id: int
    chat_id: int
    title: Optional[str] = None
    username: Optional[str] = None
    photo: Optional[List["PhotoSize"]] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "request_id": {"py": "request_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat_id": {"py": "chat_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "username": {"py": "username", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo": {"py": "photo", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'PhotoSize', "list_depth": 1},
    }


@_register_type
@dataclass
class WriteAccessAllowed(TelegramObject):
    """This object represents a service message about a user allowing a bot to write messages after adding it to the attachment menu, launching a Web App from a link, or accepting an explicit request from a Web App sent by the method requestWriteAccess ."""
    from_request: Optional[bool] = None
    web_app_name: Optional[str] = None
    from_attachment_menu: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "from_request": {"py": "from_request", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "web_app_name": {"py": "web_app_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "from_attachment_menu": {"py": "from_attachment_menu", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class VideoChatScheduled(TelegramObject):
    """This object represents a service message about a video chat scheduled in the chat."""
    start_date: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "start_date": {"py": "start_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class VideoChatStarted(TelegramObject):
    """This object represents a service message about a video chat started in the chat. Currently holds no information."""
    pass


@_register_type
@dataclass
class VideoChatEnded(TelegramObject):
    """This object represents a service message about a video chat ended in the chat."""
    duration: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "duration": {"py": "duration", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class VideoChatParticipantsInvited(TelegramObject):
    """This object represents a service message about new members invited to a video chat."""
    users: List["User"]
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "users": {"py": "users", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'User', "list_depth": 1},
    }


@_register_type
@dataclass
class PaidMessagePriceChanged(TelegramObject):
    """Describes a service message about a change in the price of paid messages within a chat."""
    paid_message_star_count: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "paid_message_star_count": {"py": "paid_message_star_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class DirectMessagePriceChanged(TelegramObject):
    """Describes a service message about a change in the price of direct messages sent to a channel chat."""
    are_direct_messages_enabled: bool
    direct_message_star_count: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "are_direct_messages_enabled": {"py": "are_direct_messages_enabled", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "direct_message_star_count": {"py": "direct_message_star_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class SuggestedPostApproved(TelegramObject):
    """Describes a service message about the approval of a suggested post."""
    send_date: int
    suggested_post_message: Optional["Message"] = None
    price: Optional["SuggestedPostPrice"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "suggested_post_message": {"py": "suggested_post_message", "is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "price": {"py": "price", "is_object": True, "inner_object": 'SuggestedPostPrice', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "send_date": {"py": "send_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class SuggestedPostApprovalFailed(TelegramObject):
    """Describes a service message about the failed approval of a suggested post. Currently, only caused by insufficient user funds at the time of approval."""
    price: "SuggestedPostPrice"
    suggested_post_message: Optional["Message"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "suggested_post_message": {"py": "suggested_post_message", "is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "price": {"py": "price", "is_object": True, "inner_object": 'SuggestedPostPrice', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class SuggestedPostDeclined(TelegramObject):
    """Describes a service message about the rejection of a suggested post."""
    suggested_post_message: Optional["Message"] = None
    comment: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "suggested_post_message": {"py": "suggested_post_message", "is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "comment": {"py": "comment", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class SuggestedPostPaid(TelegramObject):
    """Describes a service message about a successful payment for a suggested post."""
    currency: str
    suggested_post_message: Optional["Message"] = None
    amount: Optional[int] = None
    star_amount: Optional["StarAmount"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "suggested_post_message": {"py": "suggested_post_message", "is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "currency": {"py": "currency", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "amount": {"py": "amount", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "star_amount": {"py": "star_amount", "is_object": True, "inner_object": 'StarAmount', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class SuggestedPostRefunded(TelegramObject):
    """Describes a service message about a payment refund for a suggested post."""
    reason: str
    suggested_post_message: Optional["Message"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "suggested_post_message": {"py": "suggested_post_message", "is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reason": {"py": "reason", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class GiveawayCreated(TelegramObject):
    """This object represents a service message about the creation of a scheduled giveaway."""
    prize_star_count: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "prize_star_count": {"py": "prize_star_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class Giveaway(TelegramObject):
    """This object represents a message about a scheduled giveaway."""
    chats: List["Chat"]
    winners_selection_date: int
    winner_count: int
    only_new_members: Optional[bool] = None
    has_public_winners: Optional[bool] = None
    prize_description: Optional[str] = None
    country_codes: Optional[List[str]] = None
    prize_star_count: Optional[int] = None
    premium_subscription_month_count: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "chats": {"py": "chats", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'Chat', "list_depth": 1},
        "winners_selection_date": {"py": "winners_selection_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "winner_count": {"py": "winner_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "only_new_members": {"py": "only_new_members", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "has_public_winners": {"py": "has_public_winners", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "prize_description": {"py": "prize_description", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "country_codes": {"py": "country_codes", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": None, "list_depth": 1},
        "prize_star_count": {"py": "prize_star_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "premium_subscription_month_count": {"py": "premium_subscription_month_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class GiveawayWinners(TelegramObject):
    """This object represents a message about the completion of a giveaway with public winners."""
    chat: "Chat"
    giveaway_message_id: int
    winners_selection_date: int
    winner_count: int
    winners: List["User"]
    additional_chat_count: Optional[int] = None
    prize_star_count: Optional[int] = None
    premium_subscription_month_count: Optional[int] = None
    unclaimed_prize_count: Optional[int] = None
    only_new_members: Optional[bool] = None
    was_refunded: Optional[bool] = None
    prize_description: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "chat": {"py": "chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "giveaway_message_id": {"py": "giveaway_message_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "winners_selection_date": {"py": "winners_selection_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "winner_count": {"py": "winner_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "winners": {"py": "winners", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'User', "list_depth": 1},
        "additional_chat_count": {"py": "additional_chat_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "prize_star_count": {"py": "prize_star_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "premium_subscription_month_count": {"py": "premium_subscription_month_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "unclaimed_prize_count": {"py": "unclaimed_prize_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "only_new_members": {"py": "only_new_members", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "was_refunded": {"py": "was_refunded", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "prize_description": {"py": "prize_description", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class GiveawayCompleted(TelegramObject):
    """This object represents a service message about the completion of a giveaway without public winners."""
    winner_count: int
    unclaimed_prize_count: Optional[int] = None
    giveaway_message: Optional["Message"] = None
    is_star_giveaway: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "winner_count": {"py": "winner_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "unclaimed_prize_count": {"py": "unclaimed_prize_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "giveaway_message": {"py": "giveaway_message", "is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_star_giveaway": {"py": "is_star_giveaway", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class LinkPreviewOptions(TelegramObject):
    """Describes the options used for link preview generation."""
    is_disabled: Optional[bool] = None
    url: Optional[str] = None
    prefer_small_media: Optional[bool] = None
    prefer_large_media: Optional[bool] = None
    show_above_text: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "is_disabled": {"py": "is_disabled", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "url": {"py": "url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "prefer_small_media": {"py": "prefer_small_media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "prefer_large_media": {"py": "prefer_large_media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "show_above_text": {"py": "show_above_text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class SuggestedPostPrice(TelegramObject):
    """Describes the price of a suggested post."""
    currency: str
    amount: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "currency": {"py": "currency", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "amount": {"py": "amount", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class SuggestedPostInfo(TelegramObject):
    """Contains information about a suggested post."""
    state: str
    price: Optional["SuggestedPostPrice"] = None
    send_date: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "state": {"py": "state", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "price": {"py": "price", "is_object": True, "inner_object": 'SuggestedPostPrice', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "send_date": {"py": "send_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class SuggestedPostParameters(TelegramObject):
    """Contains parameters of a post that is being suggested by the bot."""
    price: Optional["SuggestedPostPrice"] = None
    send_date: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "price": {"py": "price", "is_object": True, "inner_object": 'SuggestedPostPrice', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "send_date": {"py": "send_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class DirectMessagesTopic(TelegramObject):
    """Describes a topic of a direct messages chat."""
    topic_id: int
    user: Optional["User"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "topic_id": {"py": "topic_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user": {"py": "user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class UserProfilePhotos(TelegramObject):
    """This object represent a user's profile pictures."""
    total_count: int
    photos: List[List["PhotoSize"]]
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "total_count": {"py": "total_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photos": {"py": "photos", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'PhotoSize', "list_depth": 2},
    }


@_register_type
@dataclass
class UserProfileAudios(TelegramObject):
    """This object represents the audios displayed on a user's profile."""
    total_count: int
    audios: List["Audio"]
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "total_count": {"py": "total_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "audios": {"py": "audios", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'Audio', "list_depth": 1},
    }


@_register_type
@dataclass
class File(TelegramObject):
    """This object represents a file ready to be downloaded. The file can be downloaded via the link https://api.telegram.org/file/bot<token>/<file_path> . It is guaranteed that the link will be valid for at least 1 hour. When the link expires, a new one can be requested by calling getFile ."""
    file_id: str
    file_unique_id: str
    file_size: Optional[int] = None
    file_path: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "file_id": {"py": "file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_unique_id": {"py": "file_unique_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_size": {"py": "file_size", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_path": {"py": "file_path", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class WebAppInfo(TelegramObject):
    """Describes a Web App ."""
    url: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "url": {"py": "url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ReplyKeyboardMarkup(TelegramObject):
    """This object represents a custom keyboard with reply options (see Introduction to bots for details and examples). Not supported in channels and for messages sent on behalf of a business account."""
    keyboard: List[List["KeyboardButton"]]
    is_persistent: Optional[bool] = None
    resize_keyboard: Optional[bool] = None
    one_time_keyboard: Optional[bool] = None
    input_field_placeholder: Optional[str] = None
    selective: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "keyboard": {"py": "keyboard", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'KeyboardButton', "list_depth": 2},
        "is_persistent": {"py": "is_persistent", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "resize_keyboard": {"py": "resize_keyboard", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "one_time_keyboard": {"py": "one_time_keyboard", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_field_placeholder": {"py": "input_field_placeholder", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "selective": {"py": "selective", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class KeyboardButton(TelegramObject):
    """This object represents one button of the reply keyboard. At most one of the fields other than text , icon_custom_emoji_id , and style must be used to specify the type of the button. For simple text buttons, String can be used instead of this object to specify the button text."""
    text: str
    icon_custom_emoji_id: Optional[str] = None
    style: Optional[str] = None
    request_users: Optional["KeyboardButtonRequestUsers"] = None
    request_chat: Optional["KeyboardButtonRequestChat"] = None
    request_managed_bot: Optional["KeyboardButtonRequestManagedBot"] = None
    request_contact: Optional[bool] = None
    request_location: Optional[bool] = None
    request_poll: Optional["KeyboardButtonPollType"] = None
    web_app: Optional["WebAppInfo"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "text": {"py": "text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "icon_custom_emoji_id": {"py": "icon_custom_emoji_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "style": {"py": "style", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "request_users": {"py": "request_users", "is_object": True, "inner_object": 'KeyboardButtonRequestUsers', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "request_chat": {"py": "request_chat", "is_object": True, "inner_object": 'KeyboardButtonRequestChat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "request_managed_bot": {"py": "request_managed_bot", "is_object": True, "inner_object": 'KeyboardButtonRequestManagedBot', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "request_contact": {"py": "request_contact", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "request_location": {"py": "request_location", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "request_poll": {"py": "request_poll", "is_object": True, "inner_object": 'KeyboardButtonPollType', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "web_app": {"py": "web_app", "is_object": True, "inner_object": 'WebAppInfo', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class KeyboardButtonRequestUsers(TelegramObject):
    """This object defines the criteria used to request suitable users. Information about the selected users will be shared with the bot when the corresponding button is pressed. More about requesting users »"""
    request_id: int
    user_is_bot: Optional[bool] = None
    user_is_premium: Optional[bool] = None
    max_quantity: Optional[int] = None
    request_name: Optional[bool] = None
    request_username: Optional[bool] = None
    request_photo: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "request_id": {"py": "request_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user_is_bot": {"py": "user_is_bot", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user_is_premium": {"py": "user_is_premium", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "max_quantity": {"py": "max_quantity", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "request_name": {"py": "request_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "request_username": {"py": "request_username", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "request_photo": {"py": "request_photo", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class KeyboardButtonRequestChat(TelegramObject):
    """This object defines the criteria used to request a suitable chat. Information about the selected chat will be shared with the bot when the corresponding button is pressed. The bot will be granted requested rights in the chat if appropriate. More about requesting chats » ."""
    request_id: int
    chat_is_channel: bool
    chat_is_forum: Optional[bool] = None
    chat_has_username: Optional[bool] = None
    chat_is_created: Optional[bool] = None
    user_administrator_rights: Optional["ChatAdministratorRights"] = None
    bot_administrator_rights: Optional["ChatAdministratorRights"] = None
    bot_is_member: Optional[bool] = None
    request_title: Optional[bool] = None
    request_username: Optional[bool] = None
    request_photo: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "request_id": {"py": "request_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat_is_channel": {"py": "chat_is_channel", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat_is_forum": {"py": "chat_is_forum", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat_has_username": {"py": "chat_has_username", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat_is_created": {"py": "chat_is_created", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user_administrator_rights": {"py": "user_administrator_rights", "is_object": True, "inner_object": 'ChatAdministratorRights', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "bot_administrator_rights": {"py": "bot_administrator_rights", "is_object": True, "inner_object": 'ChatAdministratorRights', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "bot_is_member": {"py": "bot_is_member", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "request_title": {"py": "request_title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "request_username": {"py": "request_username", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "request_photo": {"py": "request_photo", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class KeyboardButtonRequestManagedBot(TelegramObject):
    """This object defines the parameters for the creation of a managed bot. Information about the created bot will be shared with the bot using the update managed_bot and a Message with the field managed_bot_created ."""
    request_id: int
    suggested_name: Optional[str] = None
    suggested_username: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "request_id": {"py": "request_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "suggested_name": {"py": "suggested_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "suggested_username": {"py": "suggested_username", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class KeyboardButtonPollType(TelegramObject):
    """This object represents type of a poll, which is allowed to be created and sent when the corresponding button is pressed."""
    type_val: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ReplyKeyboardRemove(TelegramObject):
    """Upon receiving a message with this object, Telegram clients will remove the current custom keyboard and display the default letter-keyboard. By default, custom keyboards are displayed until a new keyboard is sent by a bot. An exception is made for one-time keyboards that are hidden immediately after the user presses a button (see ReplyKeyboardMarkup ). Not supported in channels and for messages sent on behalf of a business account."""
    remove_keyboard: bool
    selective: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "remove_keyboard": {"py": "remove_keyboard", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "selective": {"py": "selective", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineKeyboardMarkup(TelegramObject):
    """This object represents an inline keyboard that appears right next to the message it belongs to."""
    inline_keyboard: List[List["InlineKeyboardButton"]]
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "inline_keyboard": {"py": "inline_keyboard", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'InlineKeyboardButton', "list_depth": 2},
    }


@_register_type
@dataclass
class InlineKeyboardButton(TelegramObject):
    """This object represents one button of an inline keyboard. Exactly one of the fields other than text , icon_custom_emoji_id , and style must be used to specify the type of the button."""
    text: str
    icon_custom_emoji_id: Optional[str] = None
    style: Optional[str] = None
    url: Optional[str] = None
    callback_data: Optional[str] = None
    web_app: Optional["WebAppInfo"] = None
    login_url: Optional["LoginUrl"] = None
    switch_inline_query: Optional[str] = None
    switch_inline_query_current_chat: Optional[str] = None
    switch_inline_query_chosen_chat: Optional["SwitchInlineQueryChosenChat"] = None
    copy_text: Optional["CopyTextButton"] = None
    callback_game: Optional["CallbackGame"] = None
    pay: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "text": {"py": "text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "icon_custom_emoji_id": {"py": "icon_custom_emoji_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "style": {"py": "style", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "url": {"py": "url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "callback_data": {"py": "callback_data", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "web_app": {"py": "web_app", "is_object": True, "inner_object": 'WebAppInfo', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "login_url": {"py": "login_url", "is_object": True, "inner_object": 'LoginUrl', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "switch_inline_query": {"py": "switch_inline_query", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "switch_inline_query_current_chat": {"py": "switch_inline_query_current_chat", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "switch_inline_query_chosen_chat": {"py": "switch_inline_query_chosen_chat", "is_object": True, "inner_object": 'SwitchInlineQueryChosenChat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "copy_text": {"py": "copy_text", "is_object": True, "inner_object": 'CopyTextButton', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "callback_game": {"py": "callback_game", "is_object": True, "inner_object": 'CallbackGame', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "pay": {"py": "pay", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class LoginUrl(TelegramObject):
    """This object represents a parameter of the inline keyboard button used to automatically authorize a user. Serves as a great replacement for the Telegram Login Widget when the user is coming from Telegram. All the user needs to do is tap/click a button and confirm that they want to log in:"""
    url: str
    forward_text: Optional[str] = None
    bot_username: Optional[str] = None
    request_write_access: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "url": {"py": "url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "forward_text": {"py": "forward_text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "bot_username": {"py": "bot_username", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "request_write_access": {"py": "request_write_access", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class SwitchInlineQueryChosenChat(TelegramObject):
    """This object represents an inline button that switches the current user to inline mode in a chosen chat, with an optional default inline query."""
    query: Optional[str] = None
    allow_user_chats: Optional[bool] = None
    allow_bot_chats: Optional[bool] = None
    allow_group_chats: Optional[bool] = None
    allow_channel_chats: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "query": {"py": "query", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "allow_user_chats": {"py": "allow_user_chats", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "allow_bot_chats": {"py": "allow_bot_chats", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "allow_group_chats": {"py": "allow_group_chats", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "allow_channel_chats": {"py": "allow_channel_chats", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class CopyTextButton(TelegramObject):
    """This object represents an inline keyboard button that copies specified text to the clipboard."""
    text: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "text": {"py": "text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class CallbackQuery(TelegramObject):
    """This object represents an incoming callback query from a callback button in an inline keyboard . If the button that originated the query was attached to a message sent by the bot, the field message will be present. If the button was attached to a message sent via the bot (in inline mode ), the field inline_message_id will be present. Exactly one of the fields data or game_short_name will be present."""
    id: str
    from_user: "User"
    chat_instance: str
    message: Optional["MaybeInaccessibleMessage"] = None
    inline_message_id: Optional[str] = None
    data: Optional[str] = None
    game_short_name: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "from": {"py": "from_user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message": {"py": "message", "is_object": True, "inner_object": 'MaybeInaccessibleMessage', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "inline_message_id": {"py": "inline_message_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat_instance": {"py": "chat_instance", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "data": {"py": "data", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "game_short_name": {"py": "game_short_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ForceReply(TelegramObject):
    """Upon receiving a message with this object, Telegram clients will display a reply interface to the user (act as if the user has selected the bot's message and tapped 'Reply'). This can be extremely useful if you want to create user-friendly step-by-step interfaces without having to sacrifice privacy mode . Not supported in channels and for messages sent on behalf of a user account."""
    force_reply: bool
    input_field_placeholder: Optional[str] = None
    selective: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "force_reply": {"py": "force_reply", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_field_placeholder": {"py": "input_field_placeholder", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "selective": {"py": "selective", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatPhoto(TelegramObject):
    """This object represents a chat photo."""
    small_file_id: str
    small_file_unique_id: str
    big_file_id: str
    big_file_unique_id: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "small_file_id": {"py": "small_file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "small_file_unique_id": {"py": "small_file_unique_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "big_file_id": {"py": "big_file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "big_file_unique_id": {"py": "big_file_unique_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatInviteLink(TelegramObject):
    """Represents an invite link for a chat."""
    invite_link: str
    creator: "User"
    creates_join_request: bool
    is_primary: bool
    is_revoked: bool
    name: Optional[str] = None
    expire_date: Optional[int] = None
    member_limit: Optional[int] = None
    pending_join_request_count: Optional[int] = None
    subscription_period: Optional[int] = None
    subscription_price: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "invite_link": {"py": "invite_link", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "creator": {"py": "creator", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "creates_join_request": {"py": "creates_join_request", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_primary": {"py": "is_primary", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_revoked": {"py": "is_revoked", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "name": {"py": "name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "expire_date": {"py": "expire_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "member_limit": {"py": "member_limit", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "pending_join_request_count": {"py": "pending_join_request_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "subscription_period": {"py": "subscription_period", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "subscription_price": {"py": "subscription_price", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatAdministratorRights(TelegramObject):
    """Represents the rights of an administrator in a chat."""
    is_anonymous: bool
    can_manage_chat: bool
    can_delete_messages: bool
    can_manage_video_chats: bool
    can_restrict_members: bool
    can_promote_members: bool
    can_change_info: bool
    can_invite_users: bool
    can_post_stories: bool
    can_edit_stories: bool
    can_delete_stories: bool
    can_post_messages: Optional[bool] = None
    can_edit_messages: Optional[bool] = None
    can_pin_messages: Optional[bool] = None
    can_manage_topics: Optional[bool] = None
    can_manage_direct_messages: Optional[bool] = None
    can_manage_tags: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "is_anonymous": {"py": "is_anonymous", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_manage_chat": {"py": "can_manage_chat", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_delete_messages": {"py": "can_delete_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_manage_video_chats": {"py": "can_manage_video_chats", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_restrict_members": {"py": "can_restrict_members", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_promote_members": {"py": "can_promote_members", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_change_info": {"py": "can_change_info", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_invite_users": {"py": "can_invite_users", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_post_stories": {"py": "can_post_stories", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_edit_stories": {"py": "can_edit_stories", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_delete_stories": {"py": "can_delete_stories", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_post_messages": {"py": "can_post_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_edit_messages": {"py": "can_edit_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_pin_messages": {"py": "can_pin_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_manage_topics": {"py": "can_manage_topics", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_manage_direct_messages": {"py": "can_manage_direct_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_manage_tags": {"py": "can_manage_tags", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatMemberUpdated(TelegramObject):
    """This object represents changes in the status of a chat member."""
    chat: "Chat"
    from_user: "User"
    date: int
    old_chat_member: "ChatMember"
    new_chat_member: "ChatMember"
    invite_link: Optional["ChatInviteLink"] = None
    via_join_request: Optional[bool] = None
    via_chat_folder_invite_link: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "chat": {"py": "chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "from": {"py": "from_user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "date": {"py": "date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "old_chat_member": {"py": "old_chat_member", "is_object": True, "inner_object": 'ChatMember', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "new_chat_member": {"py": "new_chat_member", "is_object": True, "inner_object": 'ChatMember', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "invite_link": {"py": "invite_link", "is_object": True, "inner_object": 'ChatInviteLink', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "via_join_request": {"py": "via_join_request", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "via_chat_folder_invite_link": {"py": "via_chat_folder_invite_link", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatMemberOwner(TelegramObject):
    """Represents a chat member that owns the chat and has all administrator privileges."""
    status: str
    user: "User"
    is_anonymous: bool
    custom_title: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "status": {"py": "status", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user": {"py": "user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_anonymous": {"py": "is_anonymous", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "custom_title": {"py": "custom_title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatMemberAdministrator(TelegramObject):
    """Represents a chat member that has some additional privileges."""
    status: str
    user: "User"
    can_be_edited: bool
    is_anonymous: bool
    can_manage_chat: bool
    can_delete_messages: bool
    can_manage_video_chats: bool
    can_restrict_members: bool
    can_promote_members: bool
    can_change_info: bool
    can_invite_users: bool
    can_post_stories: bool
    can_edit_stories: bool
    can_delete_stories: bool
    can_post_messages: Optional[bool] = None
    can_edit_messages: Optional[bool] = None
    can_pin_messages: Optional[bool] = None
    can_manage_topics: Optional[bool] = None
    can_manage_direct_messages: Optional[bool] = None
    can_manage_tags: Optional[bool] = None
    custom_title: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "status": {"py": "status", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user": {"py": "user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_be_edited": {"py": "can_be_edited", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_anonymous": {"py": "is_anonymous", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_manage_chat": {"py": "can_manage_chat", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_delete_messages": {"py": "can_delete_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_manage_video_chats": {"py": "can_manage_video_chats", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_restrict_members": {"py": "can_restrict_members", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_promote_members": {"py": "can_promote_members", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_change_info": {"py": "can_change_info", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_invite_users": {"py": "can_invite_users", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_post_stories": {"py": "can_post_stories", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_edit_stories": {"py": "can_edit_stories", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_delete_stories": {"py": "can_delete_stories", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_post_messages": {"py": "can_post_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_edit_messages": {"py": "can_edit_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_pin_messages": {"py": "can_pin_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_manage_topics": {"py": "can_manage_topics", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_manage_direct_messages": {"py": "can_manage_direct_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_manage_tags": {"py": "can_manage_tags", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "custom_title": {"py": "custom_title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatMemberMember(TelegramObject):
    """Represents a chat member that has no additional privileges or restrictions."""
    status: str
    user: "User"
    tag: Optional[str] = None
    until_date: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "status": {"py": "status", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "tag": {"py": "tag", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user": {"py": "user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "until_date": {"py": "until_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatMemberRestricted(TelegramObject):
    """Represents a chat member that is under certain restrictions in the chat. Supergroups only."""
    status: str
    user: "User"
    is_member: bool
    can_send_messages: bool
    can_send_audios: bool
    can_send_documents: bool
    can_send_photos: bool
    can_send_videos: bool
    can_send_video_notes: bool
    can_send_voice_notes: bool
    can_send_polls: bool
    can_send_other_messages: bool
    can_add_web_page_previews: bool
    can_react_to_messages: bool
    can_edit_tag: bool
    can_change_info: bool
    can_invite_users: bool
    can_pin_messages: bool
    can_manage_topics: bool
    until_date: int
    tag: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "status": {"py": "status", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "tag": {"py": "tag", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user": {"py": "user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_member": {"py": "is_member", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_send_messages": {"py": "can_send_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_send_audios": {"py": "can_send_audios", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_send_documents": {"py": "can_send_documents", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_send_photos": {"py": "can_send_photos", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_send_videos": {"py": "can_send_videos", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_send_video_notes": {"py": "can_send_video_notes", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_send_voice_notes": {"py": "can_send_voice_notes", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_send_polls": {"py": "can_send_polls", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_send_other_messages": {"py": "can_send_other_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_add_web_page_previews": {"py": "can_add_web_page_previews", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_react_to_messages": {"py": "can_react_to_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_edit_tag": {"py": "can_edit_tag", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_change_info": {"py": "can_change_info", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_invite_users": {"py": "can_invite_users", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_pin_messages": {"py": "can_pin_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_manage_topics": {"py": "can_manage_topics", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "until_date": {"py": "until_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatMemberLeft(TelegramObject):
    """Represents a chat member that isn't currently a member of the chat, but may join it themselves."""
    status: str
    user: "User"
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "status": {"py": "status", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user": {"py": "user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatMemberBanned(TelegramObject):
    """Represents a chat member that was banned in the chat and can't return to the chat or view chat messages."""
    status: str
    user: "User"
    until_date: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "status": {"py": "status", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user": {"py": "user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "until_date": {"py": "until_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatJoinRequest(TelegramObject):
    """Represents a join request sent to a chat."""
    chat: "Chat"
    from_user: "User"
    user_chat_id: int
    date: int
    bio: Optional[str] = None
    invite_link: Optional["ChatInviteLink"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "chat": {"py": "chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "from": {"py": "from_user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user_chat_id": {"py": "user_chat_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "date": {"py": "date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "bio": {"py": "bio", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "invite_link": {"py": "invite_link", "is_object": True, "inner_object": 'ChatInviteLink', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatPermissions(TelegramObject):
    """Describes actions that a non-administrator user is allowed to take in a chat."""
    can_send_messages: Optional[bool] = None
    can_send_audios: Optional[bool] = None
    can_send_documents: Optional[bool] = None
    can_send_photos: Optional[bool] = None
    can_send_videos: Optional[bool] = None
    can_send_video_notes: Optional[bool] = None
    can_send_voice_notes: Optional[bool] = None
    can_send_polls: Optional[bool] = None
    can_send_other_messages: Optional[bool] = None
    can_add_web_page_previews: Optional[bool] = None
    can_react_to_messages: Optional[bool] = None
    can_edit_tag: Optional[bool] = None
    can_change_info: Optional[bool] = None
    can_invite_users: Optional[bool] = None
    can_pin_messages: Optional[bool] = None
    can_manage_topics: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "can_send_messages": {"py": "can_send_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_send_audios": {"py": "can_send_audios", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_send_documents": {"py": "can_send_documents", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_send_photos": {"py": "can_send_photos", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_send_videos": {"py": "can_send_videos", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_send_video_notes": {"py": "can_send_video_notes", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_send_voice_notes": {"py": "can_send_voice_notes", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_send_polls": {"py": "can_send_polls", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_send_other_messages": {"py": "can_send_other_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_add_web_page_previews": {"py": "can_add_web_page_previews", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_react_to_messages": {"py": "can_react_to_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_edit_tag": {"py": "can_edit_tag", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_change_info": {"py": "can_change_info", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_invite_users": {"py": "can_invite_users", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_pin_messages": {"py": "can_pin_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_manage_topics": {"py": "can_manage_topics", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class Birthdate(TelegramObject):
    """Describes the birthdate of a user."""
    day: int
    month: int
    year: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "day": {"py": "day", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "month": {"py": "month", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "year": {"py": "year", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BusinessIntro(TelegramObject):
    """Contains information about the start page settings of a Telegram Business account."""
    title: Optional[str] = None
    message: Optional[str] = None
    sticker: Optional["Sticker"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message": {"py": "message", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "sticker": {"py": "sticker", "is_object": True, "inner_object": 'Sticker', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BusinessLocation(TelegramObject):
    """Contains information about the location of a Telegram Business account."""
    address: str
    location: Optional["Location"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "address": {"py": "address", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "location": {"py": "location", "is_object": True, "inner_object": 'Location', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BusinessOpeningHoursInterval(TelegramObject):
    """Describes an interval of time during which a business is open."""
    opening_minute: int
    closing_minute: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "opening_minute": {"py": "opening_minute", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "closing_minute": {"py": "closing_minute", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BusinessOpeningHours(TelegramObject):
    """Describes the opening hours of a business."""
    time_zone_name: str
    opening_hours: List["BusinessOpeningHoursInterval"]
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "time_zone_name": {"py": "time_zone_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "opening_hours": {"py": "opening_hours", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'BusinessOpeningHoursInterval', "list_depth": 1},
    }


@_register_type
@dataclass
class UserRating(TelegramObject):
    """This object describes the rating of a user based on their Telegram Star spendings."""
    level: int
    rating: int
    current_level_rating: int
    next_level_rating: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "level": {"py": "level", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "rating": {"py": "rating", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "current_level_rating": {"py": "current_level_rating", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "next_level_rating": {"py": "next_level_rating", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class StoryAreaPosition(TelegramObject):
    """Describes the position of a clickable area within a story."""
    x_percentage: float
    y_percentage: float
    width_percentage: float
    height_percentage: float
    rotation_angle: float
    corner_radius_percentage: float
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "x_percentage": {"py": "x_percentage", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "y_percentage": {"py": "y_percentage", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "width_percentage": {"py": "width_percentage", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "height_percentage": {"py": "height_percentage", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "rotation_angle": {"py": "rotation_angle", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "corner_radius_percentage": {"py": "corner_radius_percentage", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class LocationAddress(TelegramObject):
    """Describes the physical address of a location."""
    country_code: str
    state: Optional[str] = None
    city: Optional[str] = None
    street: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "country_code": {"py": "country_code", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "state": {"py": "state", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "city": {"py": "city", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "street": {"py": "street", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class StoryAreaTypeLocation(TelegramObject):
    """Describes a story area pointing to a location. Currently, a story can have up to 10 location areas."""
    type_val: str
    latitude: float
    longitude: float
    address: Optional["LocationAddress"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "latitude": {"py": "latitude", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "longitude": {"py": "longitude", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "address": {"py": "address", "is_object": True, "inner_object": 'LocationAddress', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class StoryAreaTypeSuggestedReaction(TelegramObject):
    """Describes a story area pointing to a suggested reaction. Currently, a story can have up to 5 suggested reaction areas."""
    type_val: str
    reaction_type: "ReactionType"
    is_dark: Optional[bool] = None
    is_flipped: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reaction_type": {"py": "reaction_type", "is_object": True, "inner_object": 'ReactionType', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_dark": {"py": "is_dark", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_flipped": {"py": "is_flipped", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class StoryAreaTypeLink(TelegramObject):
    """Describes a story area pointing to an HTTP or tg:// link. Currently, a story can have up to 3 link areas."""
    type_val: str
    url: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "url": {"py": "url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class StoryAreaTypeWeather(TelegramObject):
    """Describes a story area containing weather information. Currently, a story can have up to 3 weather areas."""
    type_val: str
    temperature: float
    emoji: str
    background_color: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "temperature": {"py": "temperature", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "emoji": {"py": "emoji", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "background_color": {"py": "background_color", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class StoryAreaTypeUniqueGift(TelegramObject):
    """Describes a story area pointing to a unique gift. Currently, a story can have at most 1 unique gift area."""
    type_val: str
    name: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "name": {"py": "name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class StoryArea(TelegramObject):
    """Describes a clickable area on a story media."""
    position: "StoryAreaPosition"
    type_val: "StoryAreaType"
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "position": {"py": "position", "is_object": True, "inner_object": 'StoryAreaPosition', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "type": {"py": "type_val", "is_object": True, "inner_object": 'StoryAreaType', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatLocation(TelegramObject):
    """Represents a location to which a chat is connected."""
    location: "Location"
    address: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "location": {"py": "location", "is_object": True, "inner_object": 'Location', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "address": {"py": "address", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ReactionTypeEmoji(TelegramObject):
    """The reaction is based on an emoji."""
    type_val: str
    emoji: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "emoji": {"py": "emoji", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ReactionTypeCustomEmoji(TelegramObject):
    """The reaction is based on a custom emoji."""
    type_val: str
    custom_emoji_id: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "custom_emoji_id": {"py": "custom_emoji_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ReactionTypePaid(TelegramObject):
    """The reaction is paid."""
    type_val: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ReactionCount(TelegramObject):
    """Represents a reaction added to a message along with the number of times it was added."""
    type_val: "ReactionType"
    total_count: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": True, "inner_object": 'ReactionType', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "total_count": {"py": "total_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class MessageReactionUpdated(TelegramObject):
    """This object represents a change of a reaction on a message performed by a user."""
    chat: "Chat"
    message_id: int
    date: int
    old_reaction: List["ReactionType"]
    new_reaction: List["ReactionType"]
    user: Optional["User"] = None
    actor_chat: Optional["Chat"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "chat": {"py": "chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message_id": {"py": "message_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user": {"py": "user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "actor_chat": {"py": "actor_chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "date": {"py": "date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "old_reaction": {"py": "old_reaction", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'ReactionType', "list_depth": 1},
        "new_reaction": {"py": "new_reaction", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'ReactionType', "list_depth": 1},
    }


@_register_type
@dataclass
class MessageReactionCountUpdated(TelegramObject):
    """This object represents reaction changes on a message with anonymous reactions."""
    chat: "Chat"
    message_id: int
    date: int
    reactions: List["ReactionCount"]
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "chat": {"py": "chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message_id": {"py": "message_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "date": {"py": "date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reactions": {"py": "reactions", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'ReactionCount', "list_depth": 1},
    }


@_register_type
@dataclass
class ForumTopic(TelegramObject):
    """This object represents a forum topic."""
    message_thread_id: int
    name: str
    icon_color: int
    icon_custom_emoji_id: Optional[str] = None
    is_name_implicit: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "message_thread_id": {"py": "message_thread_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "name": {"py": "name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "icon_color": {"py": "icon_color", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "icon_custom_emoji_id": {"py": "icon_custom_emoji_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_name_implicit": {"py": "is_name_implicit", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class GiftBackground(TelegramObject):
    """This object describes the background of a gift."""
    center_color: int
    edge_color: int
    text_color: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "center_color": {"py": "center_color", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "edge_color": {"py": "edge_color", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "text_color": {"py": "text_color", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class Gift(TelegramObject):
    """This object represents a gift that can be sent by the bot."""
    id: str
    sticker: "Sticker"
    star_count: int
    upgrade_star_count: Optional[int] = None
    is_premium: Optional[bool] = None
    has_colors: Optional[bool] = None
    total_count: Optional[int] = None
    remaining_count: Optional[int] = None
    personal_total_count: Optional[int] = None
    personal_remaining_count: Optional[int] = None
    background: Optional["GiftBackground"] = None
    unique_gift_variant_count: Optional[int] = None
    publisher_chat: Optional["Chat"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "sticker": {"py": "sticker", "is_object": True, "inner_object": 'Sticker', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "star_count": {"py": "star_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "upgrade_star_count": {"py": "upgrade_star_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_premium": {"py": "is_premium", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "has_colors": {"py": "has_colors", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "total_count": {"py": "total_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "remaining_count": {"py": "remaining_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "personal_total_count": {"py": "personal_total_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "personal_remaining_count": {"py": "personal_remaining_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "background": {"py": "background", "is_object": True, "inner_object": 'GiftBackground', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "unique_gift_variant_count": {"py": "unique_gift_variant_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "publisher_chat": {"py": "publisher_chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class Gifts(TelegramObject):
    """This object represent a list of gifts."""
    gifts: List["Gift"]
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "gifts": {"py": "gifts", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'Gift', "list_depth": 1},
    }


@_register_type
@dataclass
class UniqueGiftModel(TelegramObject):
    """This object describes the model of a unique gift."""
    name: str
    sticker: "Sticker"
    rarity_per_mille: int
    rarity: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "name": {"py": "name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "sticker": {"py": "sticker", "is_object": True, "inner_object": 'Sticker', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "rarity_per_mille": {"py": "rarity_per_mille", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "rarity": {"py": "rarity", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class UniqueGiftSymbol(TelegramObject):
    """This object describes the symbol shown on the pattern of a unique gift."""
    name: str
    sticker: "Sticker"
    rarity_per_mille: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "name": {"py": "name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "sticker": {"py": "sticker", "is_object": True, "inner_object": 'Sticker', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "rarity_per_mille": {"py": "rarity_per_mille", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class UniqueGiftBackdropColors(TelegramObject):
    """This object describes the colors of the backdrop of a unique gift."""
    center_color: int
    edge_color: int
    symbol_color: int
    text_color: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "center_color": {"py": "center_color", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "edge_color": {"py": "edge_color", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "symbol_color": {"py": "symbol_color", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "text_color": {"py": "text_color", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class UniqueGiftBackdrop(TelegramObject):
    """This object describes the backdrop of a unique gift."""
    name: str
    colors: "UniqueGiftBackdropColors"
    rarity_per_mille: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "name": {"py": "name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "colors": {"py": "colors", "is_object": True, "inner_object": 'UniqueGiftBackdropColors', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "rarity_per_mille": {"py": "rarity_per_mille", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class UniqueGiftColors(TelegramObject):
    """This object contains information about the color scheme for a user's name, message replies and link previews based on a unique gift."""
    model_custom_emoji_id: str
    symbol_custom_emoji_id: str
    light_theme_main_color: int
    light_theme_other_colors: List[int]
    dark_theme_main_color: int
    dark_theme_other_colors: List[int]
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "model_custom_emoji_id": {"py": "model_custom_emoji_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "symbol_custom_emoji_id": {"py": "symbol_custom_emoji_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "light_theme_main_color": {"py": "light_theme_main_color", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "light_theme_other_colors": {"py": "light_theme_other_colors", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": None, "list_depth": 1},
        "dark_theme_main_color": {"py": "dark_theme_main_color", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "dark_theme_other_colors": {"py": "dark_theme_other_colors", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": None, "list_depth": 1},
    }


@_register_type
@dataclass
class UniqueGift(TelegramObject):
    """This object describes a unique gift that was upgraded from a regular gift."""
    gift_id: str
    base_name: str
    name: str
    number: int
    model: "UniqueGiftModel"
    symbol: "UniqueGiftSymbol"
    backdrop: "UniqueGiftBackdrop"
    is_premium: Optional[bool] = None
    is_burned: Optional[bool] = None
    is_from_blockchain: Optional[bool] = None
    colors: Optional["UniqueGiftColors"] = None
    publisher_chat: Optional["Chat"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "gift_id": {"py": "gift_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "base_name": {"py": "base_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "name": {"py": "name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "number": {"py": "number", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "model": {"py": "model", "is_object": True, "inner_object": 'UniqueGiftModel', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "symbol": {"py": "symbol", "is_object": True, "inner_object": 'UniqueGiftSymbol', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "backdrop": {"py": "backdrop", "is_object": True, "inner_object": 'UniqueGiftBackdrop', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_premium": {"py": "is_premium", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_burned": {"py": "is_burned", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_from_blockchain": {"py": "is_from_blockchain", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "colors": {"py": "colors", "is_object": True, "inner_object": 'UniqueGiftColors', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "publisher_chat": {"py": "publisher_chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class GiftInfo(TelegramObject):
    """Describes a service message about a regular gift that was sent or received."""
    gift: "Gift"
    owned_gift_id: Optional[str] = None
    convert_star_count: Optional[int] = None
    prepaid_upgrade_star_count: Optional[int] = None
    is_upgrade_separate: Optional[bool] = None
    can_be_upgraded: Optional[bool] = None
    text: Optional[str] = None
    entities: Optional[List["MessageEntity"]] = None
    is_private: Optional[bool] = None
    unique_gift_number: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "gift": {"py": "gift", "is_object": True, "inner_object": 'Gift', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "owned_gift_id": {"py": "owned_gift_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "convert_star_count": {"py": "convert_star_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "prepaid_upgrade_star_count": {"py": "prepaid_upgrade_star_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_upgrade_separate": {"py": "is_upgrade_separate", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_be_upgraded": {"py": "can_be_upgraded", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "text": {"py": "text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "entities": {"py": "entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "is_private": {"py": "is_private", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "unique_gift_number": {"py": "unique_gift_number", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class UniqueGiftInfo(TelegramObject):
    """Describes a service message about a unique gift that was sent or received."""
    gift: "UniqueGift"
    origin: str
    last_resale_currency: Optional[str] = None
    last_resale_amount: Optional[int] = None
    owned_gift_id: Optional[str] = None
    transfer_star_count: Optional[int] = None
    next_transfer_date: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "gift": {"py": "gift", "is_object": True, "inner_object": 'UniqueGift', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "origin": {"py": "origin", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "last_resale_currency": {"py": "last_resale_currency", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "last_resale_amount": {"py": "last_resale_amount", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "owned_gift_id": {"py": "owned_gift_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "transfer_star_count": {"py": "transfer_star_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "next_transfer_date": {"py": "next_transfer_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class OwnedGiftRegular(TelegramObject):
    """Describes a regular gift owned by a user or a chat."""
    type_val: str
    gift: "Gift"
    send_date: int
    owned_gift_id: Optional[str] = None
    sender_user: Optional["User"] = None
    text: Optional[str] = None
    entities: Optional[List["MessageEntity"]] = None
    is_private: Optional[bool] = None
    is_saved: Optional[bool] = None
    can_be_upgraded: Optional[bool] = None
    was_refunded: Optional[bool] = None
    convert_star_count: Optional[int] = None
    prepaid_upgrade_star_count: Optional[int] = None
    is_upgrade_separate: Optional[bool] = None
    unique_gift_number: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "gift": {"py": "gift", "is_object": True, "inner_object": 'Gift', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "owned_gift_id": {"py": "owned_gift_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "sender_user": {"py": "sender_user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "send_date": {"py": "send_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "text": {"py": "text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "entities": {"py": "entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "is_private": {"py": "is_private", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_saved": {"py": "is_saved", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_be_upgraded": {"py": "can_be_upgraded", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "was_refunded": {"py": "was_refunded", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "convert_star_count": {"py": "convert_star_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "prepaid_upgrade_star_count": {"py": "prepaid_upgrade_star_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_upgrade_separate": {"py": "is_upgrade_separate", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "unique_gift_number": {"py": "unique_gift_number", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class OwnedGiftUnique(TelegramObject):
    """Describes a unique gift received and owned by a user or a chat."""
    type_val: str
    gift: "UniqueGift"
    send_date: int
    owned_gift_id: Optional[str] = None
    sender_user: Optional["User"] = None
    is_saved: Optional[bool] = None
    can_be_transferred: Optional[bool] = None
    transfer_star_count: Optional[int] = None
    next_transfer_date: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "gift": {"py": "gift", "is_object": True, "inner_object": 'UniqueGift', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "owned_gift_id": {"py": "owned_gift_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "sender_user": {"py": "sender_user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "send_date": {"py": "send_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_saved": {"py": "is_saved", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_be_transferred": {"py": "can_be_transferred", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "transfer_star_count": {"py": "transfer_star_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "next_transfer_date": {"py": "next_transfer_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class OwnedGifts(TelegramObject):
    """Contains the list of gifts received and owned by a user or a chat."""
    total_count: int
    gifts: List["OwnedGift"]
    next_offset: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "total_count": {"py": "total_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "gifts": {"py": "gifts", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'OwnedGift', "list_depth": 1},
        "next_offset": {"py": "next_offset", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BotAccessSettings(TelegramObject):
    """This object describes the access settings of a bot."""
    is_access_restricted: bool
    added_users: Optional[List["User"]] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "is_access_restricted": {"py": "is_access_restricted", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "added_users": {"py": "added_users", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'User', "list_depth": 1},
    }


@_register_type
@dataclass
class AcceptedGiftTypes(TelegramObject):
    """This object describes the types of gifts that can be gifted to a user or a chat."""
    unlimited_gifts: bool
    limited_gifts: bool
    unique_gifts: bool
    premium_subscription: bool
    gifts_from_channels: bool
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "unlimited_gifts": {"py": "unlimited_gifts", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "limited_gifts": {"py": "limited_gifts", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "unique_gifts": {"py": "unique_gifts", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "premium_subscription": {"py": "premium_subscription", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "gifts_from_channels": {"py": "gifts_from_channels", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class StarAmount(TelegramObject):
    """Describes an amount of Telegram Stars."""
    amount: int
    nanostar_amount: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "amount": {"py": "amount", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "nanostar_amount": {"py": "nanostar_amount", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BotCommand(TelegramObject):
    """This object represents a bot command."""
    command: str
    description: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "command": {"py": "command", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "description": {"py": "description", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BotCommandScopeDefault(TelegramObject):
    """Represents the default scope of bot commands. Default commands are used if no commands with a narrower scope are specified for the user."""
    type_val: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BotCommandScopeAllPrivateChats(TelegramObject):
    """Represents the scope of bot commands, covering all private chats."""
    type_val: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BotCommandScopeAllGroupChats(TelegramObject):
    """Represents the scope of bot commands, covering all group and supergroup chats."""
    type_val: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BotCommandScopeAllChatAdministrators(TelegramObject):
    """Represents the scope of bot commands, covering all group and supergroup chat administrators."""
    type_val: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BotCommandScopeChat(TelegramObject):
    """Represents the scope of bot commands, covering a specific chat."""
    type_val: str
    chat_id: Union[int, str]
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat_id": {"py": "chat_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BotCommandScopeChatAdministrators(TelegramObject):
    """Represents the scope of bot commands, covering all administrators of a specific group or supergroup chat."""
    type_val: str
    chat_id: Union[int, str]
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat_id": {"py": "chat_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BotCommandScopeChatMember(TelegramObject):
    """Represents the scope of bot commands, covering a specific member of a group or supergroup chat."""
    type_val: str
    chat_id: Union[int, str]
    user_id: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat_id": {"py": "chat_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user_id": {"py": "user_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BotName(TelegramObject):
    """This object represents the bot's name."""
    name: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "name": {"py": "name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BotDescription(TelegramObject):
    """This object represents the bot's description."""
    description: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "description": {"py": "description", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BotShortDescription(TelegramObject):
    """This object represents the bot's short description."""
    short_description: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "short_description": {"py": "short_description", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class MenuButtonCommands(TelegramObject):
    """Represents a menu button, which opens the bot's list of commands."""
    type_val: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class MenuButtonWebApp(TelegramObject):
    """Represents a menu button, which launches a Web App ."""
    type_val: str
    text: str
    web_app: "WebAppInfo"
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "text": {"py": "text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "web_app": {"py": "web_app", "is_object": True, "inner_object": 'WebAppInfo', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class MenuButtonDefault(TelegramObject):
    """Describes that no specific value for the menu button was set."""
    type_val: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatBoostSourcePremium(TelegramObject):
    """The boost was obtained by subscribing to Telegram Premium or by gifting a Telegram Premium subscription to another user."""
    source: str
    user: "User"
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "source": {"py": "source", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user": {"py": "user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatBoostSourceGiftCode(TelegramObject):
    """The boost was obtained by the creation of Telegram Premium gift codes to boost a chat. Each such code boosts the chat 4 times for the duration of the corresponding Telegram Premium subscription."""
    source: str
    user: "User"
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "source": {"py": "source", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user": {"py": "user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatBoostSourceGiveaway(TelegramObject):
    """The boost was obtained by the creation of a Telegram Premium or a Telegram Star giveaway. This boosts the chat 4 times for the duration of the corresponding Telegram Premium subscription for Telegram Premium giveaways and prize_star_count / 500 times for one year for Telegram Star giveaways."""
    source: str
    giveaway_message_id: int
    user: Optional["User"] = None
    prize_star_count: Optional[int] = None
    is_unclaimed: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "source": {"py": "source", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "giveaway_message_id": {"py": "giveaway_message_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user": {"py": "user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "prize_star_count": {"py": "prize_star_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_unclaimed": {"py": "is_unclaimed", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatBoost(TelegramObject):
    """This object contains information about a chat boost."""
    boost_id: str
    add_date: int
    expiration_date: int
    source: "ChatBoostSource"
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "boost_id": {"py": "boost_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "add_date": {"py": "add_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "expiration_date": {"py": "expiration_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "source": {"py": "source", "is_object": True, "inner_object": 'ChatBoostSource', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatBoostUpdated(TelegramObject):
    """This object represents a boost added to a chat or changed."""
    chat: "Chat"
    boost: "ChatBoost"
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "chat": {"py": "chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "boost": {"py": "boost", "is_object": True, "inner_object": 'ChatBoost', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatBoostRemoved(TelegramObject):
    """This object represents a boost removed from a chat."""
    chat: "Chat"
    boost_id: str
    remove_date: int
    source: "ChatBoostSource"
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "chat": {"py": "chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "boost_id": {"py": "boost_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "remove_date": {"py": "remove_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "source": {"py": "source", "is_object": True, "inner_object": 'ChatBoostSource', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatOwnerLeft(TelegramObject):
    """Describes a service message about the chat owner leaving the chat."""
    new_owner: Optional["User"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "new_owner": {"py": "new_owner", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChatOwnerChanged(TelegramObject):
    """Describes a service message about an ownership change in the chat."""
    new_owner: "User"
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "new_owner": {"py": "new_owner", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class UserChatBoosts(TelegramObject):
    """This object represents a list of boosts added to a chat by a user."""
    boosts: List["ChatBoost"]
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "boosts": {"py": "boosts", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'ChatBoost', "list_depth": 1},
    }


@_register_type
@dataclass
class BusinessBotRights(TelegramObject):
    """Represents the rights of a business bot."""
    can_reply: Optional[bool] = None
    can_read_messages: Optional[bool] = None
    can_delete_sent_messages: Optional[bool] = None
    can_delete_all_messages: Optional[bool] = None
    can_edit_name: Optional[bool] = None
    can_edit_bio: Optional[bool] = None
    can_edit_profile_photo: Optional[bool] = None
    can_edit_username: Optional[bool] = None
    can_change_gift_settings: Optional[bool] = None
    can_view_gifts_and_stars: Optional[bool] = None
    can_convert_gifts_to_stars: Optional[bool] = None
    can_transfer_and_upgrade_gifts: Optional[bool] = None
    can_transfer_stars: Optional[bool] = None
    can_manage_stories: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "can_reply": {"py": "can_reply", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_read_messages": {"py": "can_read_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_delete_sent_messages": {"py": "can_delete_sent_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_delete_all_messages": {"py": "can_delete_all_messages", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_edit_name": {"py": "can_edit_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_edit_bio": {"py": "can_edit_bio", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_edit_profile_photo": {"py": "can_edit_profile_photo", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_edit_username": {"py": "can_edit_username", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_change_gift_settings": {"py": "can_change_gift_settings", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_view_gifts_and_stars": {"py": "can_view_gifts_and_stars", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_convert_gifts_to_stars": {"py": "can_convert_gifts_to_stars", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_transfer_and_upgrade_gifts": {"py": "can_transfer_and_upgrade_gifts", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_transfer_stars": {"py": "can_transfer_stars", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "can_manage_stories": {"py": "can_manage_stories", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BusinessConnection(TelegramObject):
    """Describes the connection of the bot with a business account."""
    id: str
    user: "User"
    user_chat_id: int
    date: int
    is_enabled: bool
    rights: Optional["BusinessBotRights"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user": {"py": "user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user_chat_id": {"py": "user_chat_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "date": {"py": "date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "rights": {"py": "rights", "is_object": True, "inner_object": 'BusinessBotRights', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_enabled": {"py": "is_enabled", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class BusinessMessagesDeleted(TelegramObject):
    """This object is received when messages are deleted from a connected business account."""
    business_connection_id: str
    chat: "Chat"
    message_ids: List[int]
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "business_connection_id": {"py": "business_connection_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat": {"py": "chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message_ids": {"py": "message_ids", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": None, "list_depth": 1},
    }


@_register_type
@dataclass
class SentWebAppMessage(TelegramObject):
    """Describes an inline message sent by a Web App on behalf of a user."""
    inline_message_id: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "inline_message_id": {"py": "inline_message_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class SentGuestMessage(TelegramObject):
    """Describes an inline message sent by a guest bot."""
    inline_message_id: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "inline_message_id": {"py": "inline_message_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PreparedInlineMessage(TelegramObject):
    """Describes an inline message to be sent by a user of a Mini App."""
    id: str
    expiration_date: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "expiration_date": {"py": "expiration_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PreparedKeyboardButton(TelegramObject):
    """Describes a keyboard button to be used by a user of a Mini App."""
    id: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ResponseParameters(TelegramObject):
    """Describes why a request was unsuccessful."""
    migrate_to_chat_id: Optional[int] = None
    retry_after: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "migrate_to_chat_id": {"py": "migrate_to_chat_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "retry_after": {"py": "retry_after", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputMediaAnimation(TelegramObject):
    """Represents an animation file (GIF or H.264/MPEG-4 AVC video without sound) to be sent."""
    type_val: str
    media: str
    thumbnail: Optional[str] = None
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    show_caption_above_media: Optional[bool] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[int] = None
    has_spoiler: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "media": {"py": "media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail": {"py": "thumbnail", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "show_caption_above_media": {"py": "show_caption_above_media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "width": {"py": "width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "height": {"py": "height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "duration": {"py": "duration", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "has_spoiler": {"py": "has_spoiler", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputMediaAudio(TelegramObject):
    """Represents an audio file to be treated as music to be sent."""
    type_val: str
    media: str
    thumbnail: Optional[str] = None
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    duration: Optional[int] = None
    performer: Optional[str] = None
    title: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "media": {"py": "media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail": {"py": "thumbnail", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "duration": {"py": "duration", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "performer": {"py": "performer", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputMediaDocument(TelegramObject):
    """Represents a general file to be sent."""
    type_val: str
    media: str
    thumbnail: Optional[str] = None
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    disable_content_type_detection: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "media": {"py": "media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail": {"py": "thumbnail", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "disable_content_type_detection": {"py": "disable_content_type_detection", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputMediaLivePhoto(TelegramObject):
    """Represents a live photo to be sent."""
    type_val: str
    media: str
    photo: str
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    show_caption_above_media: Optional[bool] = None
    has_spoiler: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "media": {"py": "media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo": {"py": "photo", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "show_caption_above_media": {"py": "show_caption_above_media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "has_spoiler": {"py": "has_spoiler", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputMediaLocation(TelegramObject):
    """Represents a location to be sent."""
    type_val: str
    latitude: float
    longitude: float
    horizontal_accuracy: Optional[float] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "latitude": {"py": "latitude", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "longitude": {"py": "longitude", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "horizontal_accuracy": {"py": "horizontal_accuracy", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputMediaPhoto(TelegramObject):
    """Represents a photo to be sent."""
    type_val: str
    media: str
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    show_caption_above_media: Optional[bool] = None
    has_spoiler: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "media": {"py": "media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "show_caption_above_media": {"py": "show_caption_above_media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "has_spoiler": {"py": "has_spoiler", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputMediaSticker(TelegramObject):
    """Represents a sticker file to be sent."""
    type_val: str
    media: str
    emoji: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "media": {"py": "media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "emoji": {"py": "emoji", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputMediaVenue(TelegramObject):
    """Represents a venue to be sent."""
    type_val: str
    latitude: float
    longitude: float
    title: str
    address: str
    foursquare_id: Optional[str] = None
    foursquare_type: Optional[str] = None
    google_place_id: Optional[str] = None
    google_place_type: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "latitude": {"py": "latitude", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "longitude": {"py": "longitude", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "address": {"py": "address", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "foursquare_id": {"py": "foursquare_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "foursquare_type": {"py": "foursquare_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "google_place_id": {"py": "google_place_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "google_place_type": {"py": "google_place_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputMediaVideo(TelegramObject):
    """Represents a video to be sent."""
    type_val: str
    media: str
    thumbnail: Optional[str] = None
    cover: Optional[str] = None
    start_timestamp: Optional[int] = None
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    show_caption_above_media: Optional[bool] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[int] = None
    supports_streaming: Optional[bool] = None
    has_spoiler: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "media": {"py": "media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail": {"py": "thumbnail", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "cover": {"py": "cover", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "start_timestamp": {"py": "start_timestamp", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "show_caption_above_media": {"py": "show_caption_above_media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "width": {"py": "width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "height": {"py": "height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "duration": {"py": "duration", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "supports_streaming": {"py": "supports_streaming", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "has_spoiler": {"py": "has_spoiler", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputFile(TelegramObject):
    """This object represents the contents of a file to be uploaded. Must be posted using multipart/form-data in the usual way that files are uploaded via the browser."""
    pass


@_register_type
@dataclass
class InputPaidMediaLivePhoto(TelegramObject):
    """The paid media to send is a live photo."""
    type_val: str
    media: str
    photo: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "media": {"py": "media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo": {"py": "photo", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputPaidMediaPhoto(TelegramObject):
    """The paid media to send is a photo."""
    type_val: str
    media: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "media": {"py": "media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputPaidMediaVideo(TelegramObject):
    """The paid media to send is a video."""
    type_val: str
    media: str
    thumbnail: Optional[str] = None
    cover: Optional[str] = None
    start_timestamp: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[int] = None
    supports_streaming: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "media": {"py": "media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail": {"py": "thumbnail", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "cover": {"py": "cover", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "start_timestamp": {"py": "start_timestamp", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "width": {"py": "width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "height": {"py": "height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "duration": {"py": "duration", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "supports_streaming": {"py": "supports_streaming", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputProfilePhotoStatic(TelegramObject):
    """A static profile photo in the .JPG format."""
    type_val: str
    photo: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo": {"py": "photo", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputProfilePhotoAnimated(TelegramObject):
    """An animated profile photo in the MPEG4 format."""
    type_val: str
    animation: str
    main_frame_timestamp: Optional[float] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "animation": {"py": "animation", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "main_frame_timestamp": {"py": "main_frame_timestamp", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputStoryContentPhoto(TelegramObject):
    """Describes a photo to post as a story."""
    type_val: str
    photo: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo": {"py": "photo", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputStoryContentVideo(TelegramObject):
    """Describes a video to post as a story."""
    type_val: str
    video: str
    duration: Optional[float] = None
    cover_frame_timestamp: Optional[float] = None
    is_animation: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "video": {"py": "video", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "duration": {"py": "duration", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "cover_frame_timestamp": {"py": "cover_frame_timestamp", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_animation": {"py": "is_animation", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class Sticker(TelegramObject):
    """This object represents a sticker."""
    file_id: str
    file_unique_id: str
    type_val: str
    width: int
    height: int
    is_animated: bool
    is_video: bool
    thumbnail: Optional["PhotoSize"] = None
    emoji: Optional[str] = None
    set_name: Optional[str] = None
    premium_animation: Optional["File"] = None
    mask_position: Optional["MaskPosition"] = None
    custom_emoji_id: Optional[str] = None
    needs_repainting: Optional[bool] = None
    file_size: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "file_id": {"py": "file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_unique_id": {"py": "file_unique_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "width": {"py": "width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "height": {"py": "height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_animated": {"py": "is_animated", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_video": {"py": "is_video", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail": {"py": "thumbnail", "is_object": True, "inner_object": 'PhotoSize', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "emoji": {"py": "emoji", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "set_name": {"py": "set_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "premium_animation": {"py": "premium_animation", "is_object": True, "inner_object": 'File', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "mask_position": {"py": "mask_position", "is_object": True, "inner_object": 'MaskPosition', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "custom_emoji_id": {"py": "custom_emoji_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "needs_repainting": {"py": "needs_repainting", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_size": {"py": "file_size", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class StickerSet(TelegramObject):
    """This object represents a sticker set."""
    name: str
    title: str
    sticker_type: str
    stickers: List["Sticker"]
    thumbnail: Optional["PhotoSize"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "name": {"py": "name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "sticker_type": {"py": "sticker_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "stickers": {"py": "stickers", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'Sticker', "list_depth": 1},
        "thumbnail": {"py": "thumbnail", "is_object": True, "inner_object": 'PhotoSize', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class MaskPosition(TelegramObject):
    """This object describes the position on faces where a mask should be placed by default."""
    point: str
    x_shift: float
    y_shift: float
    scale: float
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "point": {"py": "point", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "x_shift": {"py": "x_shift", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "y_shift": {"py": "y_shift", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "scale": {"py": "scale", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputSticker(TelegramObject):
    """This object describes a sticker to be added to a sticker set."""
    sticker: str
    format: str
    emoji_list: List[str]
    mask_position: Optional["MaskPosition"] = None
    keywords: Optional[List[str]] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "sticker": {"py": "sticker", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "format": {"py": "format", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "emoji_list": {"py": "emoji_list", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": None, "list_depth": 1},
        "mask_position": {"py": "mask_position", "is_object": True, "inner_object": 'MaskPosition', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "keywords": {"py": "keywords", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": None, "list_depth": 1},
    }


@_register_type
@dataclass
class InlineQuery(TelegramObject):
    """This object represents an incoming inline query. When the user sends an empty query, your bot could return some default or trending results."""
    id: str
    from_user: "User"
    query: str
    offset: str
    chat_type: Optional[str] = None
    location: Optional["Location"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "from": {"py": "from_user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "query": {"py": "query", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "offset": {"py": "offset", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat_type": {"py": "chat_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "location": {"py": "location", "is_object": True, "inner_object": 'Location', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultsButton(TelegramObject):
    """This object represents a button to be shown above inline query results. You must use exactly one of the optional fields."""
    text: str
    web_app: Optional["WebAppInfo"] = None
    start_parameter: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "text": {"py": "text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "web_app": {"py": "web_app", "is_object": True, "inner_object": 'WebAppInfo', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "start_parameter": {"py": "start_parameter", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultArticle(TelegramObject):
    """Represents a link to an article or web page."""
    type_val: str
    id: str
    title: str
    input_message_content: "InputMessageContent"
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    url: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    thumbnail_width: Optional[int] = None
    thumbnail_height: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_message_content": {"py": "input_message_content", "is_object": True, "inner_object": 'InputMessageContent', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "url": {"py": "url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "description": {"py": "description", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_url": {"py": "thumbnail_url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_width": {"py": "thumbnail_width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_height": {"py": "thumbnail_height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultPhoto(TelegramObject):
    """Represents a link to a photo. By default, this photo will be sent by the user with optional caption. Alternatively, you can use input_message_content to send a message with the specified content instead of the photo."""
    type_val: str
    id: str
    photo_url: str
    thumbnail_url: str
    photo_width: Optional[int] = None
    photo_height: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    show_caption_above_media: Optional[bool] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional["InputMessageContent"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo_url": {"py": "photo_url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_url": {"py": "thumbnail_url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo_width": {"py": "photo_width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo_height": {"py": "photo_height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "description": {"py": "description", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "show_caption_above_media": {"py": "show_caption_above_media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_message_content": {"py": "input_message_content", "is_object": True, "inner_object": 'InputMessageContent', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultGif(TelegramObject):
    """Represents a link to an animated GIF file. By default, this animated GIF file will be sent by the user with optional caption. Alternatively, you can use input_message_content to send a message with the specified content instead of the animation."""
    type_val: str
    id: str
    gif_url: str
    thumbnail_url: str
    gif_width: Optional[int] = None
    gif_height: Optional[int] = None
    gif_duration: Optional[int] = None
    thumbnail_mime_type: Optional[str] = None
    title: Optional[str] = None
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    show_caption_above_media: Optional[bool] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional["InputMessageContent"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "gif_url": {"py": "gif_url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "gif_width": {"py": "gif_width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "gif_height": {"py": "gif_height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "gif_duration": {"py": "gif_duration", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_url": {"py": "thumbnail_url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_mime_type": {"py": "thumbnail_mime_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "show_caption_above_media": {"py": "show_caption_above_media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_message_content": {"py": "input_message_content", "is_object": True, "inner_object": 'InputMessageContent', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultMpeg4Gif(TelegramObject):
    """Represents a link to a video animation (H.264/MPEG-4 AVC video without sound). By default, this animated MPEG-4 file will be sent by the user with optional caption. Alternatively, you can use input_message_content to send a message with the specified content instead of the animation."""
    type_val: str
    id: str
    mpeg4_url: str
    thumbnail_url: str
    mpeg4_width: Optional[int] = None
    mpeg4_height: Optional[int] = None
    mpeg4_duration: Optional[int] = None
    thumbnail_mime_type: Optional[str] = None
    title: Optional[str] = None
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    show_caption_above_media: Optional[bool] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional["InputMessageContent"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "mpeg4_url": {"py": "mpeg4_url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "mpeg4_width": {"py": "mpeg4_width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "mpeg4_height": {"py": "mpeg4_height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "mpeg4_duration": {"py": "mpeg4_duration", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_url": {"py": "thumbnail_url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_mime_type": {"py": "thumbnail_mime_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "show_caption_above_media": {"py": "show_caption_above_media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_message_content": {"py": "input_message_content", "is_object": True, "inner_object": 'InputMessageContent', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultVideo(TelegramObject):
    """Represents a link to a page containing an embedded video player or a video file. By default, this video file will be sent by the user with an optional caption. Alternatively, you can use input_message_content to send a message with the specified content instead of the video."""
    type_val: str
    id: str
    video_url: str
    mime_type: str
    thumbnail_url: str
    title: str
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    show_caption_above_media: Optional[bool] = None
    video_width: Optional[int] = None
    video_height: Optional[int] = None
    video_duration: Optional[int] = None
    description: Optional[str] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional["InputMessageContent"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "video_url": {"py": "video_url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "mime_type": {"py": "mime_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_url": {"py": "thumbnail_url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "show_caption_above_media": {"py": "show_caption_above_media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "video_width": {"py": "video_width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "video_height": {"py": "video_height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "video_duration": {"py": "video_duration", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "description": {"py": "description", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_message_content": {"py": "input_message_content", "is_object": True, "inner_object": 'InputMessageContent', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultAudio(TelegramObject):
    """Represents a link to an MP3 audio file. By default, this audio file will be sent by the user. Alternatively, you can use input_message_content to send a message with the specified content instead of the audio."""
    type_val: str
    id: str
    audio_url: str
    title: str
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    performer: Optional[str] = None
    audio_duration: Optional[int] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional["InputMessageContent"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "audio_url": {"py": "audio_url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "performer": {"py": "performer", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "audio_duration": {"py": "audio_duration", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_message_content": {"py": "input_message_content", "is_object": True, "inner_object": 'InputMessageContent', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultVoice(TelegramObject):
    """Represents a link to a voice recording in an .OGG container encoded with OPUS. By default, this voice recording will be sent by the user. Alternatively, you can use input_message_content to send a message with the specified content instead of the the voice message."""
    type_val: str
    id: str
    voice_url: str
    title: str
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    voice_duration: Optional[int] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional["InputMessageContent"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "voice_url": {"py": "voice_url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "voice_duration": {"py": "voice_duration", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_message_content": {"py": "input_message_content", "is_object": True, "inner_object": 'InputMessageContent', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultDocument(TelegramObject):
    """Represents a link to a file. By default, this file will be sent by the user with an optional caption. Alternatively, you can use input_message_content to send a message with the specified content instead of the file. Currently, only .PDF and .ZIP files can be sent using this method."""
    type_val: str
    id: str
    title: str
    document_url: str
    mime_type: str
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    description: Optional[str] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional["InputMessageContent"] = None
    thumbnail_url: Optional[str] = None
    thumbnail_width: Optional[int] = None
    thumbnail_height: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "document_url": {"py": "document_url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "mime_type": {"py": "mime_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "description": {"py": "description", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_message_content": {"py": "input_message_content", "is_object": True, "inner_object": 'InputMessageContent', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_url": {"py": "thumbnail_url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_width": {"py": "thumbnail_width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_height": {"py": "thumbnail_height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultLocation(TelegramObject):
    """Represents a location on a map. By default, the location will be sent by the user. Alternatively, you can use input_message_content to send a message with the specified content instead of the location."""
    type_val: str
    id: str
    latitude: float
    longitude: float
    title: str
    horizontal_accuracy: Optional[float] = None
    live_period: Optional[int] = None
    heading: Optional[int] = None
    proximity_alert_radius: Optional[int] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional["InputMessageContent"] = None
    thumbnail_url: Optional[str] = None
    thumbnail_width: Optional[int] = None
    thumbnail_height: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "latitude": {"py": "latitude", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "longitude": {"py": "longitude", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "horizontal_accuracy": {"py": "horizontal_accuracy", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "live_period": {"py": "live_period", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "heading": {"py": "heading", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "proximity_alert_radius": {"py": "proximity_alert_radius", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_message_content": {"py": "input_message_content", "is_object": True, "inner_object": 'InputMessageContent', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_url": {"py": "thumbnail_url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_width": {"py": "thumbnail_width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_height": {"py": "thumbnail_height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultVenue(TelegramObject):
    """Represents a venue. By default, the venue will be sent by the user. Alternatively, you can use input_message_content to send a message with the specified content instead of the venue."""
    type_val: str
    id: str
    latitude: float
    longitude: float
    title: str
    address: str
    foursquare_id: Optional[str] = None
    foursquare_type: Optional[str] = None
    google_place_id: Optional[str] = None
    google_place_type: Optional[str] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional["InputMessageContent"] = None
    thumbnail_url: Optional[str] = None
    thumbnail_width: Optional[int] = None
    thumbnail_height: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "latitude": {"py": "latitude", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "longitude": {"py": "longitude", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "address": {"py": "address", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "foursquare_id": {"py": "foursquare_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "foursquare_type": {"py": "foursquare_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "google_place_id": {"py": "google_place_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "google_place_type": {"py": "google_place_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_message_content": {"py": "input_message_content", "is_object": True, "inner_object": 'InputMessageContent', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_url": {"py": "thumbnail_url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_width": {"py": "thumbnail_width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_height": {"py": "thumbnail_height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultContact(TelegramObject):
    """Represents a contact with a phone number. By default, this contact will be sent by the user. Alternatively, you can use input_message_content to send a message with the specified content instead of the contact."""
    type_val: str
    id: str
    phone_number: str
    first_name: str
    last_name: Optional[str] = None
    vcard: Optional[str] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional["InputMessageContent"] = None
    thumbnail_url: Optional[str] = None
    thumbnail_width: Optional[int] = None
    thumbnail_height: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "phone_number": {"py": "phone_number", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "first_name": {"py": "first_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "last_name": {"py": "last_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "vcard": {"py": "vcard", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_message_content": {"py": "input_message_content", "is_object": True, "inner_object": 'InputMessageContent', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_url": {"py": "thumbnail_url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_width": {"py": "thumbnail_width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "thumbnail_height": {"py": "thumbnail_height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultGame(TelegramObject):
    """Represents a Game ."""
    type_val: str
    id: str
    game_short_name: str
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "game_short_name": {"py": "game_short_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultCachedPhoto(TelegramObject):
    """Represents a link to a photo stored on the Telegram servers. By default, this photo will be sent by the user with an optional caption. Alternatively, you can use input_message_content to send a message with the specified content instead of the photo."""
    type_val: str
    id: str
    photo_file_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    show_caption_above_media: Optional[bool] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional["InputMessageContent"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo_file_id": {"py": "photo_file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "description": {"py": "description", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "show_caption_above_media": {"py": "show_caption_above_media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_message_content": {"py": "input_message_content", "is_object": True, "inner_object": 'InputMessageContent', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultCachedGif(TelegramObject):
    """Represents a link to an animated GIF file stored on the Telegram servers. By default, this animated GIF file will be sent by the user with an optional caption. Alternatively, you can use input_message_content to send a message with specified content instead of the animation."""
    type_val: str
    id: str
    gif_file_id: str
    title: Optional[str] = None
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    show_caption_above_media: Optional[bool] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional["InputMessageContent"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "gif_file_id": {"py": "gif_file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "show_caption_above_media": {"py": "show_caption_above_media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_message_content": {"py": "input_message_content", "is_object": True, "inner_object": 'InputMessageContent', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultCachedMpeg4Gif(TelegramObject):
    """Represents a link to a video animation (H.264/MPEG-4 AVC video without sound) stored on the Telegram servers. By default, this animated MPEG-4 file will be sent by the user with an optional caption. Alternatively, you can use input_message_content to send a message with the specified content instead of the animation."""
    type_val: str
    id: str
    mpeg4_file_id: str
    title: Optional[str] = None
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    show_caption_above_media: Optional[bool] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional["InputMessageContent"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "mpeg4_file_id": {"py": "mpeg4_file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "show_caption_above_media": {"py": "show_caption_above_media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_message_content": {"py": "input_message_content", "is_object": True, "inner_object": 'InputMessageContent', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultCachedSticker(TelegramObject):
    """Represents a link to a sticker stored on the Telegram servers. By default, this sticker will be sent by the user. Alternatively, you can use input_message_content to send a message with the specified content instead of the sticker."""
    type_val: str
    id: str
    sticker_file_id: str
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional["InputMessageContent"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "sticker_file_id": {"py": "sticker_file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_message_content": {"py": "input_message_content", "is_object": True, "inner_object": 'InputMessageContent', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultCachedDocument(TelegramObject):
    """Represents a link to a file stored on the Telegram servers. By default, this file will be sent by the user with an optional caption. Alternatively, you can use input_message_content to send a message with the specified content instead of the file."""
    type_val: str
    id: str
    title: str
    document_file_id: str
    description: Optional[str] = None
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional["InputMessageContent"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "document_file_id": {"py": "document_file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "description": {"py": "description", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_message_content": {"py": "input_message_content", "is_object": True, "inner_object": 'InputMessageContent', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultCachedVideo(TelegramObject):
    """Represents a link to a video file stored on the Telegram servers. By default, this video file will be sent by the user with an optional caption. Alternatively, you can use input_message_content to send a message with the specified content instead of the video."""
    type_val: str
    id: str
    video_file_id: str
    title: str
    description: Optional[str] = None
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    show_caption_above_media: Optional[bool] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional["InputMessageContent"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "video_file_id": {"py": "video_file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "description": {"py": "description", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "show_caption_above_media": {"py": "show_caption_above_media", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_message_content": {"py": "input_message_content", "is_object": True, "inner_object": 'InputMessageContent', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultCachedVoice(TelegramObject):
    """Represents a link to a voice message stored on the Telegram servers. By default, this voice message will be sent by the user. Alternatively, you can use input_message_content to send a message with the specified content instead of the voice message."""
    type_val: str
    id: str
    voice_file_id: str
    title: str
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional["InputMessageContent"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "voice_file_id": {"py": "voice_file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_message_content": {"py": "input_message_content", "is_object": True, "inner_object": 'InputMessageContent', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InlineQueryResultCachedAudio(TelegramObject):
    """Represents a link to an MP3 audio file stored on the Telegram servers. By default, this audio file will be sent by the user. Alternatively, you can use input_message_content to send a message with the specified content instead of the audio."""
    type_val: str
    id: str
    audio_file_id: str
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional["InputMessageContent"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "audio_file_id": {"py": "audio_file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption": {"py": "caption", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "caption_entities": {"py": "caption_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "reply_markup": {"py": "reply_markup", "is_object": True, "inner_object": 'InlineKeyboardMarkup', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "input_message_content": {"py": "input_message_content", "is_object": True, "inner_object": 'InputMessageContent', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputTextMessageContent(TelegramObject):
    """Represents the content of a text message to be sent as the result of an inline query."""
    message_text: str
    parse_mode: Optional[str] = None
    entities: Optional[List["MessageEntity"]] = None
    link_preview_options: Optional["LinkPreviewOptions"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "message_text": {"py": "message_text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "parse_mode": {"py": "parse_mode", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "entities": {"py": "entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "link_preview_options": {"py": "link_preview_options", "is_object": True, "inner_object": 'LinkPreviewOptions', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputLocationMessageContent(TelegramObject):
    """Represents the content of a location message to be sent as the result of an inline query."""
    latitude: float
    longitude: float
    horizontal_accuracy: Optional[float] = None
    live_period: Optional[int] = None
    heading: Optional[int] = None
    proximity_alert_radius: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "latitude": {"py": "latitude", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "longitude": {"py": "longitude", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "horizontal_accuracy": {"py": "horizontal_accuracy", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "live_period": {"py": "live_period", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "heading": {"py": "heading", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "proximity_alert_radius": {"py": "proximity_alert_radius", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputVenueMessageContent(TelegramObject):
    """Represents the content of a venue message to be sent as the result of an inline query."""
    latitude: float
    longitude: float
    title: str
    address: str
    foursquare_id: Optional[str] = None
    foursquare_type: Optional[str] = None
    google_place_id: Optional[str] = None
    google_place_type: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "latitude": {"py": "latitude", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "longitude": {"py": "longitude", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "address": {"py": "address", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "foursquare_id": {"py": "foursquare_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "foursquare_type": {"py": "foursquare_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "google_place_id": {"py": "google_place_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "google_place_type": {"py": "google_place_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputContactMessageContent(TelegramObject):
    """Represents the content of a contact message to be sent as the result of an inline query."""
    phone_number: str
    first_name: str
    last_name: Optional[str] = None
    vcard: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "phone_number": {"py": "phone_number", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "first_name": {"py": "first_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "last_name": {"py": "last_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "vcard": {"py": "vcard", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class InputInvoiceMessageContent(TelegramObject):
    """Represents the content of an invoice message to be sent as the result of an inline query."""
    title: str
    description: str
    payload: str
    currency: str
    prices: List["LabeledPrice"]
    provider_token: Optional[str] = None
    max_tip_amount: Optional[int] = None
    suggested_tip_amounts: Optional[List[int]] = None
    provider_data: Optional[str] = None
    photo_url: Optional[str] = None
    photo_size: Optional[int] = None
    photo_width: Optional[int] = None
    photo_height: Optional[int] = None
    need_name: Optional[bool] = None
    need_phone_number: Optional[bool] = None
    need_email: Optional[bool] = None
    need_shipping_address: Optional[bool] = None
    send_phone_number_to_provider: Optional[bool] = None
    send_email_to_provider: Optional[bool] = None
    is_flexible: Optional[bool] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "description": {"py": "description", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "payload": {"py": "payload", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "provider_token": {"py": "provider_token", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "currency": {"py": "currency", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "prices": {"py": "prices", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'LabeledPrice', "list_depth": 1},
        "max_tip_amount": {"py": "max_tip_amount", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "suggested_tip_amounts": {"py": "suggested_tip_amounts", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": None, "list_depth": 1},
        "provider_data": {"py": "provider_data", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo_url": {"py": "photo_url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo_size": {"py": "photo_size", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo_width": {"py": "photo_width", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo_height": {"py": "photo_height", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "need_name": {"py": "need_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "need_phone_number": {"py": "need_phone_number", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "need_email": {"py": "need_email", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "need_shipping_address": {"py": "need_shipping_address", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "send_phone_number_to_provider": {"py": "send_phone_number_to_provider", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "send_email_to_provider": {"py": "send_email_to_provider", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_flexible": {"py": "is_flexible", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ChosenInlineResult(TelegramObject):
    """Represents a result of an inline query that was chosen by the user and sent to their chat partner."""
    result_id: str
    from_user: "User"
    query: str
    location: Optional["Location"] = None
    inline_message_id: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "result_id": {"py": "result_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "from": {"py": "from_user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "location": {"py": "location", "is_object": True, "inner_object": 'Location', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "inline_message_id": {"py": "inline_message_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "query": {"py": "query", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class LabeledPrice(TelegramObject):
    """This object represents a portion of the price for goods or services."""
    label: str
    amount: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "label": {"py": "label", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "amount": {"py": "amount", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class Invoice(TelegramObject):
    """This object contains basic information about an invoice."""
    title: str
    description: str
    start_parameter: str
    currency: str
    total_amount: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "description": {"py": "description", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "start_parameter": {"py": "start_parameter", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "currency": {"py": "currency", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "total_amount": {"py": "total_amount", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ShippingAddress(TelegramObject):
    """This object represents a shipping address."""
    country_code: str
    state: str
    city: str
    street_line1: str
    street_line2: str
    post_code: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "country_code": {"py": "country_code", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "state": {"py": "state", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "city": {"py": "city", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "street_line1": {"py": "street_line1", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "street_line2": {"py": "street_line2", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "post_code": {"py": "post_code", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class OrderInfo(TelegramObject):
    """This object represents information about an order."""
    name: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    shipping_address: Optional["ShippingAddress"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "name": {"py": "name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "phone_number": {"py": "phone_number", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "email": {"py": "email", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "shipping_address": {"py": "shipping_address", "is_object": True, "inner_object": 'ShippingAddress', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ShippingOption(TelegramObject):
    """This object represents one shipping option."""
    id: str
    title: str
    prices: List["LabeledPrice"]
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "prices": {"py": "prices", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'LabeledPrice', "list_depth": 1},
    }


@_register_type
@dataclass
class SuccessfulPayment(TelegramObject):
    """This object contains basic information about a successful payment. Note that if the buyer initiates a chargeback with the relevant payment provider following this transaction, the funds may be debited from your balance. This is outside of Telegram's control."""
    currency: str
    total_amount: int
    invoice_payload: str
    telegram_payment_charge_id: str
    provider_payment_charge_id: str
    subscription_expiration_date: Optional[int] = None
    is_recurring: Optional[bool] = None
    is_first_recurring: Optional[bool] = None
    shipping_option_id: Optional[str] = None
    order_info: Optional["OrderInfo"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "currency": {"py": "currency", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "total_amount": {"py": "total_amount", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "invoice_payload": {"py": "invoice_payload", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "subscription_expiration_date": {"py": "subscription_expiration_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_recurring": {"py": "is_recurring", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "is_first_recurring": {"py": "is_first_recurring", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "shipping_option_id": {"py": "shipping_option_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "order_info": {"py": "order_info", "is_object": True, "inner_object": 'OrderInfo', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "telegram_payment_charge_id": {"py": "telegram_payment_charge_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "provider_payment_charge_id": {"py": "provider_payment_charge_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class RefundedPayment(TelegramObject):
    """This object contains basic information about a refunded payment."""
    currency: str
    total_amount: int
    invoice_payload: str
    telegram_payment_charge_id: str
    provider_payment_charge_id: Optional[str] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "currency": {"py": "currency", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "total_amount": {"py": "total_amount", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "invoice_payload": {"py": "invoice_payload", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "telegram_payment_charge_id": {"py": "telegram_payment_charge_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "provider_payment_charge_id": {"py": "provider_payment_charge_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class ShippingQuery(TelegramObject):
    """This object contains information about an incoming shipping query."""
    id: str
    from_user: "User"
    invoice_payload: str
    shipping_address: "ShippingAddress"
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "from": {"py": "from_user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "invoice_payload": {"py": "invoice_payload", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "shipping_address": {"py": "shipping_address", "is_object": True, "inner_object": 'ShippingAddress', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PreCheckoutQuery(TelegramObject):
    """This object contains information about an incoming pre-checkout query."""
    id: str
    from_user: "User"
    currency: str
    total_amount: int
    invoice_payload: str
    shipping_option_id: Optional[str] = None
    order_info: Optional["OrderInfo"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "from": {"py": "from_user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "currency": {"py": "currency", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "total_amount": {"py": "total_amount", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "invoice_payload": {"py": "invoice_payload", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "shipping_option_id": {"py": "shipping_option_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "order_info": {"py": "order_info", "is_object": True, "inner_object": 'OrderInfo', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PaidMediaPurchased(TelegramObject):
    """This object contains information about a paid media purchase."""
    from_user: "User"
    paid_media_payload: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "from": {"py": "from_user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "paid_media_payload": {"py": "paid_media_payload", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class RevenueWithdrawalStatePending(TelegramObject):
    """The withdrawal is in progress."""
    type_val: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class RevenueWithdrawalStateSucceeded(TelegramObject):
    """The withdrawal succeeded."""
    type_val: str
    date: int
    url: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "date": {"py": "date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "url": {"py": "url", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class RevenueWithdrawalStateFailed(TelegramObject):
    """The withdrawal failed and the transaction was refunded."""
    type_val: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class AffiliateInfo(TelegramObject):
    """Contains information about the affiliate that received a commission via this transaction."""
    commission_per_mille: int
    amount: int
    affiliate_user: Optional["User"] = None
    affiliate_chat: Optional["Chat"] = None
    nanostar_amount: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "affiliate_user": {"py": "affiliate_user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "affiliate_chat": {"py": "affiliate_chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "commission_per_mille": {"py": "commission_per_mille", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "amount": {"py": "amount", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "nanostar_amount": {"py": "nanostar_amount", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class TransactionPartnerUser(TelegramObject):
    """Describes a transaction with a user."""
    type_val: str
    transaction_type: str
    user: "User"
    affiliate: Optional["AffiliateInfo"] = None
    invoice_payload: Optional[str] = None
    subscription_period: Optional[int] = None
    paid_media: Optional[List["PaidMedia"]] = None
    paid_media_payload: Optional[str] = None
    gift: Optional["Gift"] = None
    premium_subscription_duration: Optional[int] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "transaction_type": {"py": "transaction_type", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user": {"py": "user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "affiliate": {"py": "affiliate", "is_object": True, "inner_object": 'AffiliateInfo', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "invoice_payload": {"py": "invoice_payload", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "subscription_period": {"py": "subscription_period", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "paid_media": {"py": "paid_media", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'PaidMedia', "list_depth": 1},
        "paid_media_payload": {"py": "paid_media_payload", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "gift": {"py": "gift", "is_object": True, "inner_object": 'Gift', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "premium_subscription_duration": {"py": "premium_subscription_duration", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class TransactionPartnerChat(TelegramObject):
    """Describes a transaction with a chat."""
    type_val: str
    chat: "Chat"
    gift: Optional["Gift"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "chat": {"py": "chat", "is_object": True, "inner_object": 'Chat', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "gift": {"py": "gift", "is_object": True, "inner_object": 'Gift', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class TransactionPartnerAffiliateProgram(TelegramObject):
    """Describes the affiliate program that issued the affiliate commission received via this transaction."""
    type_val: str
    commission_per_mille: int
    sponsor_user: Optional["User"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "sponsor_user": {"py": "sponsor_user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "commission_per_mille": {"py": "commission_per_mille", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class TransactionPartnerFragment(TelegramObject):
    """Describes a withdrawal transaction with Fragment."""
    type_val: str
    withdrawal_state: Optional["RevenueWithdrawalState"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "withdrawal_state": {"py": "withdrawal_state", "is_object": True, "inner_object": 'RevenueWithdrawalState', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class TransactionPartnerTelegramAds(TelegramObject):
    """Describes a withdrawal transaction to the Telegram Ads platform."""
    type_val: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class TransactionPartnerTelegramApi(TelegramObject):
    """Describes a transaction with payment for paid broadcasting ."""
    type_val: str
    request_count: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "request_count": {"py": "request_count", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class TransactionPartnerOther(TelegramObject):
    """Describes a transaction with an unknown source or recipient."""
    type_val: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class StarTransaction(TelegramObject):
    """Describes a Telegram Star transaction. Note that if the buyer initiates a chargeback with the payment provider from whom they acquired Stars (e.g., Apple, Google) following this transaction, the refunded Stars will be deducted from the bot's balance. This is outside of Telegram's control."""
    id: str
    amount: int
    date: int
    nanostar_amount: Optional[int] = None
    source: Optional["TransactionPartner"] = None
    receiver: Optional["TransactionPartner"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "id": {"py": "id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "amount": {"py": "amount", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "nanostar_amount": {"py": "nanostar_amount", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "date": {"py": "date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "source": {"py": "source", "is_object": True, "inner_object": 'TransactionPartner', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "receiver": {"py": "receiver", "is_object": True, "inner_object": 'TransactionPartner', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class StarTransactions(TelegramObject):
    """Contains a list of Telegram Star transactions."""
    transactions: List["StarTransaction"]
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "transactions": {"py": "transactions", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'StarTransaction', "list_depth": 1},
    }


@_register_type
@dataclass
class PassportData(TelegramObject):
    """Describes Telegram Passport data shared with the bot by the user."""
    data: List["EncryptedPassportElement"]
    credentials: "EncryptedCredentials"
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "data": {"py": "data", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'EncryptedPassportElement', "list_depth": 1},
        "credentials": {"py": "credentials", "is_object": True, "inner_object": 'EncryptedCredentials', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PassportFile(TelegramObject):
    """This object represents a file uploaded to Telegram Passport. Currently all Telegram Passport files are in JPEG format when decrypted and don't exceed 10MB."""
    file_id: str
    file_unique_id: str
    file_size: int
    file_date: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "file_id": {"py": "file_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_unique_id": {"py": "file_unique_id", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_size": {"py": "file_size", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_date": {"py": "file_date", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class EncryptedPassportElement(TelegramObject):
    """Describes documents or other Telegram Passport elements shared with the bot by the user."""
    type_val: str
    hash: str
    data: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    files: Optional[List["PassportFile"]] = None
    front_side: Optional["PassportFile"] = None
    reverse_side: Optional["PassportFile"] = None
    selfie: Optional["PassportFile"] = None
    translation: Optional[List["PassportFile"]] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "data": {"py": "data", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "phone_number": {"py": "phone_number", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "email": {"py": "email", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "files": {"py": "files", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'PassportFile', "list_depth": 1},
        "front_side": {"py": "front_side", "is_object": True, "inner_object": 'PassportFile', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "reverse_side": {"py": "reverse_side", "is_object": True, "inner_object": 'PassportFile', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "selfie": {"py": "selfie", "is_object": True, "inner_object": 'PassportFile', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "translation": {"py": "translation", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'PassportFile', "list_depth": 1},
        "hash": {"py": "hash", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class EncryptedCredentials(TelegramObject):
    """Describes data required for decrypting and authenticating EncryptedPassportElement . See the Telegram Passport Documentation for a complete description of the data decryption and authentication processes."""
    data: str
    hash: str
    secret: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "data": {"py": "data", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "hash": {"py": "hash", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "secret": {"py": "secret", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PassportElementErrorDataField(TelegramObject):
    """Represents an issue in one of the data fields that was provided by the user. The error is considered resolved when the field's value changes."""
    source: str
    type_val: str
    field_name: str
    data_hash: str
    message: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "source": {"py": "source", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "field_name": {"py": "field_name", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "data_hash": {"py": "data_hash", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message": {"py": "message", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PassportElementErrorFrontSide(TelegramObject):
    """Represents an issue with the front side of a document. The error is considered resolved when the file with the front side of the document changes."""
    source: str
    type_val: str
    file_hash: str
    message: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "source": {"py": "source", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_hash": {"py": "file_hash", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message": {"py": "message", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PassportElementErrorReverseSide(TelegramObject):
    """Represents an issue with the reverse side of a document. The error is considered resolved when the file with reverse side of the document changes."""
    source: str
    type_val: str
    file_hash: str
    message: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "source": {"py": "source", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_hash": {"py": "file_hash", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message": {"py": "message", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PassportElementErrorSelfie(TelegramObject):
    """Represents an issue with the selfie with a document. The error is considered resolved when the file with the selfie changes."""
    source: str
    type_val: str
    file_hash: str
    message: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "source": {"py": "source", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_hash": {"py": "file_hash", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message": {"py": "message", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PassportElementErrorFile(TelegramObject):
    """Represents an issue with a document scan. The error is considered resolved when the file with the document scan changes."""
    source: str
    type_val: str
    file_hash: str
    message: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "source": {"py": "source", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_hash": {"py": "file_hash", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message": {"py": "message", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PassportElementErrorFiles(TelegramObject):
    """Represents an issue with a list of scans. The error is considered resolved when the list of files containing the scans changes."""
    source: str
    type_val: str
    file_hashes: List[str]
    message: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "source": {"py": "source", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_hashes": {"py": "file_hashes", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": None, "list_depth": 1},
        "message": {"py": "message", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PassportElementErrorTranslationFile(TelegramObject):
    """Represents an issue with one of the files that constitute the translation of a document. The error is considered resolved when the file changes."""
    source: str
    type_val: str
    file_hash: str
    message: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "source": {"py": "source", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_hash": {"py": "file_hash", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message": {"py": "message", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PassportElementErrorTranslationFiles(TelegramObject):
    """Represents an issue with the translated version of a document. The error is considered resolved when a file with the document translation change."""
    source: str
    type_val: str
    file_hashes: List[str]
    message: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "source": {"py": "source", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "file_hashes": {"py": "file_hashes", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": None, "list_depth": 1},
        "message": {"py": "message", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class PassportElementErrorUnspecified(TelegramObject):
    """Represents an issue in an unspecified place. The error is considered resolved when new data is added."""
    source: str
    type_val: str
    element_hash: str
    message: str
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "source": {"py": "source", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "type": {"py": "type_val", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "element_hash": {"py": "element_hash", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "message": {"py": "message", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class Game(TelegramObject):
    """This object represents a game. Use BotFather to create and edit games, their short names will act as unique identifiers."""
    title: str
    description: str
    photo: List["PhotoSize"]
    text: Optional[str] = None
    text_entities: Optional[List["MessageEntity"]] = None
    animation: Optional["Animation"] = None
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "title": {"py": "title", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "description": {"py": "description", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "photo": {"py": "photo", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'PhotoSize', "list_depth": 1},
        "text": {"py": "text", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "text_entities": {"py": "text_entities", "is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageEntity', "list_depth": 1},
        "animation": {"py": "animation", "is_object": True, "inner_object": 'Animation', "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


@_register_type
@dataclass
class CallbackGame(TelegramObject):
    """A placeholder, currently holds no information. Use BotFather to set up your game."""
    pass


@_register_type
@dataclass
class GameHighScore(TelegramObject):
    """This object represents one row of the high scores table for a game."""
    position: int
    user: "User"
    score: int
    _FIELD_META: ClassVar[Dict[str, dict]] = {
        "position": {"py": "position", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
        "user": {"py": "user", "is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0},
        "score": {"py": "score", "is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0},
    }


# MaybeInaccessibleMessage: union of Message, InaccessibleMessage
class _MaybeInaccessibleMessageHelper:
    """Union dispatcher for MaybeInaccessibleMessage. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct MaybeInaccessibleMessage subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'MaybeInaccessibleMessage', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

MaybeInaccessibleMessage: Any = Union["Message", "InaccessibleMessage"]  # type: ignore[misc]
"""This object describes a message that can be inaccessible to the bot. It can be one of"""
MaybeInaccessibleMessage_from_dict = _MaybeInaccessibleMessageHelper.from_dict


# MessageOrigin: union of MessageOriginUser, MessageOriginHiddenUser, MessageOriginChat, MessageOriginChannel
class _MessageOriginHelper:
    """Union dispatcher for MessageOrigin. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct MessageOrigin subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'MessageOrigin', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

MessageOrigin: Any = Union["MessageOriginUser", "MessageOriginHiddenUser", "MessageOriginChat", "MessageOriginChannel"]  # type: ignore[misc]
"""This object describes the origin of a message. It can be one of"""
MessageOrigin_from_dict = _MessageOriginHelper.from_dict


# PaidMedia: union of PaidMediaLivePhoto, PaidMediaPhoto, PaidMediaPreview, PaidMediaVideo
class _PaidMediaHelper:
    """Union dispatcher for PaidMedia. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct PaidMedia subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'PaidMedia', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

PaidMedia: Any = Union["PaidMediaLivePhoto", "PaidMediaPhoto", "PaidMediaPreview", "PaidMediaVideo"]  # type: ignore[misc]
"""This object describes paid media. Currently, it can be one of"""
PaidMedia_from_dict = _PaidMediaHelper.from_dict


# InputPollMedia: union of InputMediaAnimation, InputMediaAudio, InputMediaDocument, InputMediaLivePhoto, InputMediaLocation, InputMediaPhoto, InputMediaVenue, InputMediaVideo
class _InputPollMediaHelper:
    """Union dispatcher for InputPollMedia. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct InputPollMedia subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'InputPollMedia', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

InputPollMedia: Any = Union["InputMediaAnimation", "InputMediaAudio", "InputMediaDocument", "InputMediaLivePhoto", "InputMediaLocation", "InputMediaPhoto", "InputMediaVenue", "InputMediaVideo"]  # type: ignore[misc]
"""This object represents the content of a poll description or a quiz explanation to be sent. It should be one of"""
InputPollMedia_from_dict = _InputPollMediaHelper.from_dict


# InputPollOptionMedia: union of InputMediaAnimation, InputMediaLivePhoto, InputMediaLocation, InputMediaPhoto, InputMediaSticker, InputMediaVenue, InputMediaVideo
class _InputPollOptionMediaHelper:
    """Union dispatcher for InputPollOptionMedia. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct InputPollOptionMedia subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'InputPollOptionMedia', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

InputPollOptionMedia: Any = Union["InputMediaAnimation", "InputMediaLivePhoto", "InputMediaLocation", "InputMediaPhoto", "InputMediaSticker", "InputMediaVenue", "InputMediaVideo"]  # type: ignore[misc]
"""This object represents the content of a poll option to be sent. It should be one of"""
InputPollOptionMedia_from_dict = _InputPollOptionMediaHelper.from_dict


# BackgroundFill: union of BackgroundFillSolid, BackgroundFillGradient, BackgroundFillFreeformGradient
class _BackgroundFillHelper:
    """Union dispatcher for BackgroundFill. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct BackgroundFill subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'BackgroundFill', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

BackgroundFill: Any = Union["BackgroundFillSolid", "BackgroundFillGradient", "BackgroundFillFreeformGradient"]  # type: ignore[misc]
"""This object describes the way a background is filled based on the selected colors. Currently, it can be one of"""
BackgroundFill_from_dict = _BackgroundFillHelper.from_dict


# BackgroundType: union of BackgroundTypeFill, BackgroundTypeWallpaper, BackgroundTypePattern, BackgroundTypeChatTheme
class _BackgroundTypeHelper:
    """Union dispatcher for BackgroundType. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct BackgroundType subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'BackgroundType', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

BackgroundType: Any = Union["BackgroundTypeFill", "BackgroundTypeWallpaper", "BackgroundTypePattern", "BackgroundTypeChatTheme"]  # type: ignore[misc]
"""This object describes the type of a background. Currently, it can be one of"""
BackgroundType_from_dict = _BackgroundTypeHelper.from_dict


# ChatMember: union of ChatMemberOwner, ChatMemberAdministrator, ChatMemberMember, ChatMemberRestricted, ChatMemberLeft, ChatMemberBanned
class _ChatMemberHelper:
    """Union dispatcher for ChatMember. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct ChatMember subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'ChatMember', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

ChatMember: Any = Union["ChatMemberOwner", "ChatMemberAdministrator", "ChatMemberMember", "ChatMemberRestricted", "ChatMemberLeft", "ChatMemberBanned"]  # type: ignore[misc]
"""This object contains information about one member of a chat. Currently, the following 6 types of chat members are supported:"""
ChatMember_from_dict = _ChatMemberHelper.from_dict


# StoryAreaType: union of StoryAreaTypeLocation, StoryAreaTypeSuggestedReaction, StoryAreaTypeLink, StoryAreaTypeWeather, StoryAreaTypeUniqueGift
class _StoryAreaTypeHelper:
    """Union dispatcher for StoryAreaType. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct StoryAreaType subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'StoryAreaType', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

StoryAreaType: Any = Union["StoryAreaTypeLocation", "StoryAreaTypeSuggestedReaction", "StoryAreaTypeLink", "StoryAreaTypeWeather", "StoryAreaTypeUniqueGift"]  # type: ignore[misc]
"""Describes the type of a clickable area on a story. Currently, it can be one of"""
StoryAreaType_from_dict = _StoryAreaTypeHelper.from_dict


# ReactionType: union of ReactionTypeEmoji, ReactionTypeCustomEmoji, ReactionTypePaid
class _ReactionTypeHelper:
    """Union dispatcher for ReactionType. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct ReactionType subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'ReactionType', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

ReactionType: Any = Union["ReactionTypeEmoji", "ReactionTypeCustomEmoji", "ReactionTypePaid"]  # type: ignore[misc]
"""This object describes the type of a reaction. Currently, it can be one of"""
ReactionType_from_dict = _ReactionTypeHelper.from_dict


# OwnedGift: union of OwnedGiftRegular, OwnedGiftUnique
class _OwnedGiftHelper:
    """Union dispatcher for OwnedGift. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct OwnedGift subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'OwnedGift', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

OwnedGift: Any = Union["OwnedGiftRegular", "OwnedGiftUnique"]  # type: ignore[misc]
"""This object describes a gift received and owned by a user or a chat. Currently, it can be one of"""
OwnedGift_from_dict = _OwnedGiftHelper.from_dict


# BotCommandScope: union of BotCommandScopeDefault, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats, BotCommandScopeAllChatAdministrators, BotCommandScopeChat, BotCommandScopeChatAdministrators, BotCommandScopeChatMember
class _BotCommandScopeHelper:
    """Union dispatcher for BotCommandScope. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct BotCommandScope subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'BotCommandScope', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

BotCommandScope: Any = Union["BotCommandScopeDefault", "BotCommandScopeAllPrivateChats", "BotCommandScopeAllGroupChats", "BotCommandScopeAllChatAdministrators", "BotCommandScopeChat", "BotCommandScopeChatAdministrators", "BotCommandScopeChatMember"]  # type: ignore[misc]
"""This object represents the scope to which bot commands are applied. Currently, the following 7 scopes are supported:"""
BotCommandScope_from_dict = _BotCommandScopeHelper.from_dict


# MenuButton: union of MenuButtonCommands, MenuButtonWebApp, MenuButtonDefault
class _MenuButtonHelper:
    """Union dispatcher for MenuButton. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct MenuButton subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'MenuButton', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

MenuButton: Any = Union["MenuButtonCommands", "MenuButtonWebApp", "MenuButtonDefault"]  # type: ignore[misc]
"""This object describes the bot's menu button in a private chat. It should be one of"""
MenuButton_from_dict = _MenuButtonHelper.from_dict


# ChatBoostSource: union of ChatBoostSourcePremium, ChatBoostSourceGiftCode, ChatBoostSourceGiveaway
class _ChatBoostSourceHelper:
    """Union dispatcher for ChatBoostSource. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct ChatBoostSource subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'ChatBoostSource', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

ChatBoostSource: Any = Union["ChatBoostSourcePremium", "ChatBoostSourceGiftCode", "ChatBoostSourceGiveaway"]  # type: ignore[misc]
"""This object describes the source of a chat boost. It can be one of"""
ChatBoostSource_from_dict = _ChatBoostSourceHelper.from_dict


# InputMedia: union of InputMediaAnimation, InputMediaAudio, InputMediaDocument, InputMediaLivePhoto, InputMediaPhoto, InputMediaVideo
class _InputMediaHelper:
    """Union dispatcher for InputMedia. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct InputMedia subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'InputMedia', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

InputMedia: Any = Union["InputMediaAnimation", "InputMediaAudio", "InputMediaDocument", "InputMediaLivePhoto", "InputMediaPhoto", "InputMediaVideo"]  # type: ignore[misc]
"""This object represents the content of a media message to be sent. It should be one of"""
InputMedia_from_dict = _InputMediaHelper.from_dict


# InputPaidMedia: union of InputPaidMediaLivePhoto, InputPaidMediaPhoto, InputPaidMediaVideo
class _InputPaidMediaHelper:
    """Union dispatcher for InputPaidMedia. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct InputPaidMedia subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'InputPaidMedia', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

InputPaidMedia: Any = Union["InputPaidMediaLivePhoto", "InputPaidMediaPhoto", "InputPaidMediaVideo"]  # type: ignore[misc]
"""This object describes the paid media to be sent. Currently, it can be one of"""
InputPaidMedia_from_dict = _InputPaidMediaHelper.from_dict


# InputProfilePhoto: union of InputProfilePhotoStatic, InputProfilePhotoAnimated
class _InputProfilePhotoHelper:
    """Union dispatcher for InputProfilePhoto. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct InputProfilePhoto subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'InputProfilePhoto', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

InputProfilePhoto: Any = Union["InputProfilePhotoStatic", "InputProfilePhotoAnimated"]  # type: ignore[misc]
"""This object describes a profile photo to set. Currently, it can be one of"""
InputProfilePhoto_from_dict = _InputProfilePhotoHelper.from_dict


# InputStoryContent: union of InputStoryContentPhoto, InputStoryContentVideo
class _InputStoryContentHelper:
    """Union dispatcher for InputStoryContent. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct InputStoryContent subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'InputStoryContent', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

InputStoryContent: Any = Union["InputStoryContentPhoto", "InputStoryContentVideo"]  # type: ignore[misc]
"""This object describes the content of a story to post. Currently, it can be one of"""
InputStoryContent_from_dict = _InputStoryContentHelper.from_dict


# InlineQueryResult: union of InlineQueryResultCachedAudio, InlineQueryResultCachedDocument, InlineQueryResultCachedGif, InlineQueryResultCachedMpeg4Gif, InlineQueryResultCachedPhoto, InlineQueryResultCachedSticker, InlineQueryResultCachedVideo, InlineQueryResultCachedVoice, InlineQueryResultArticle, InlineQueryResultAudio, InlineQueryResultContact, InlineQueryResultGame, InlineQueryResultDocument, InlineQueryResultGif, InlineQueryResultLocation, InlineQueryResultMpeg4Gif, InlineQueryResultPhoto, InlineQueryResultVenue, InlineQueryResultVideo, InlineQueryResultVoice
class _InlineQueryResultHelper:
    """Union dispatcher for InlineQueryResult. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct InlineQueryResult subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'InlineQueryResult', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

InlineQueryResult: Any = Union["InlineQueryResultCachedAudio", "InlineQueryResultCachedDocument", "InlineQueryResultCachedGif", "InlineQueryResultCachedMpeg4Gif", "InlineQueryResultCachedPhoto", "InlineQueryResultCachedSticker", "InlineQueryResultCachedVideo", "InlineQueryResultCachedVoice", "InlineQueryResultArticle", "InlineQueryResultAudio", "InlineQueryResultContact", "InlineQueryResultGame", "InlineQueryResultDocument", "InlineQueryResultGif", "InlineQueryResultLocation", "InlineQueryResultMpeg4Gif", "InlineQueryResultPhoto", "InlineQueryResultVenue", "InlineQueryResultVideo", "InlineQueryResultVoice"]  # type: ignore[misc]
"""This object represents one result of an inline query. Telegram clients currently support results of the following 20 types:"""
InlineQueryResult_from_dict = _InlineQueryResultHelper.from_dict


# InputMessageContent: union of InputTextMessageContent, InputLocationMessageContent, InputVenueMessageContent, InputContactMessageContent, InputInvoiceMessageContent
class _InputMessageContentHelper:
    """Union dispatcher for InputMessageContent. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct InputMessageContent subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'InputMessageContent', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

InputMessageContent: Any = Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]  # type: ignore[misc]
"""This object represents the content of a message to be sent as a result of an inline query. Telegram clients currently support the following 5 types:"""
InputMessageContent_from_dict = _InputMessageContentHelper.from_dict


# RevenueWithdrawalState: union of RevenueWithdrawalStatePending, RevenueWithdrawalStateSucceeded, RevenueWithdrawalStateFailed
class _RevenueWithdrawalStateHelper:
    """Union dispatcher for RevenueWithdrawalState. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct RevenueWithdrawalState subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'RevenueWithdrawalState', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

RevenueWithdrawalState: Any = Union["RevenueWithdrawalStatePending", "RevenueWithdrawalStateSucceeded", "RevenueWithdrawalStateFailed"]  # type: ignore[misc]
"""This object describes the state of a revenue withdrawal operation. Currently, it can be one of"""
RevenueWithdrawalState_from_dict = _RevenueWithdrawalStateHelper.from_dict


# TransactionPartner: union of TransactionPartnerUser, TransactionPartnerChat, TransactionPartnerAffiliateProgram, TransactionPartnerFragment, TransactionPartnerTelegramAds, TransactionPartnerTelegramApi, TransactionPartnerOther
class _TransactionPartnerHelper:
    """Union dispatcher for TransactionPartner. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct TransactionPartner subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'TransactionPartner', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

TransactionPartner: Any = Union["TransactionPartnerUser", "TransactionPartnerChat", "TransactionPartnerAffiliateProgram", "TransactionPartnerFragment", "TransactionPartnerTelegramAds", "TransactionPartnerTelegramApi", "TransactionPartnerOther"]  # type: ignore[misc]
"""This object describes the source of a transaction, or its recipient for outgoing transactions. Currently, it can be one of"""
TransactionPartner_from_dict = _TransactionPartnerHelper.from_dict


# PassportElementError: union of PassportElementErrorDataField, PassportElementErrorFrontSide, PassportElementErrorReverseSide, PassportElementErrorSelfie, PassportElementErrorFile, PassportElementErrorFiles, PassportElementErrorTranslationFile, PassportElementErrorTranslationFiles, PassportElementErrorUnspecified
class _PassportElementErrorHelper:
    """Union dispatcher for PassportElementError. Supports from_dict() for automatic subtype resolution."""
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Any:
        """Deserialize dict into the correct PassportElementError subtype based on the dispatch table."""
        if data is None:
            return None
        return _decode_value(data, {'is_object': True, 'inner_object': 'PassportElementError', 'is_list': False, 'list_inner_object': None, 'list_depth': 0})

PassportElementError: Any = Union["PassportElementErrorDataField", "PassportElementErrorFrontSide", "PassportElementErrorReverseSide", "PassportElementErrorSelfie", "PassportElementErrorFile", "PassportElementErrorFiles", "PassportElementErrorTranslationFile", "PassportElementErrorTranslationFiles", "PassportElementErrorUnspecified"]  # type: ignore[misc]
"""This object represents an error in the Telegram Passport element which was submitted that should be resolved by the user. It should be one of:"""
PassportElementError_from_dict = _PassportElementErrorHelper.from_dict


# ── Union dispatch table ─────────────────────────────────────────────────────

_UNION_DISPATCH.update({
    "MaybeInaccessibleMessage": {"discriminator": "date", "map": {"0": "InaccessibleMessage"}, "fallback": "Message"},
    "MessageOrigin": {"discriminator": "type", "map": {"channel": "MessageOriginChannel", "chat": "MessageOriginChat", "hidden_user": "MessageOriginHiddenUser", "user": "MessageOriginUser"}},
    "PaidMedia": {"discriminator": "type", "map": {"live_photo": "PaidMediaLivePhoto", "photo": "PaidMediaPhoto", "preview": "PaidMediaPreview", "video": "PaidMediaVideo"}},
    "InputPollMedia": {"discriminator": "disable_content_type_detection", "map": {"True": "InputMediaDocument"}},
    "BackgroundFill": {"discriminator": "type", "map": {"freeform_gradient": "BackgroundFillFreeformGradient", "gradient": "BackgroundFillGradient", "solid": "BackgroundFillSolid"}},
    "BackgroundType": {"discriminator": "type", "map": {"chat_theme": "BackgroundTypeChatTheme", "fill": "BackgroundTypeFill", "pattern": "BackgroundTypePattern", "wallpaper": "BackgroundTypeWallpaper"}},
    "ChatMember": {"discriminator": "status", "map": {"administrator": "ChatMemberAdministrator", "creator": "ChatMemberOwner", "kicked": "ChatMemberBanned", "left": "ChatMemberLeft", "member": "ChatMemberMember", "restricted": "ChatMemberRestricted"}},
    "StoryAreaType": {"discriminator": "type", "map": {"link": "StoryAreaTypeLink", "location": "StoryAreaTypeLocation", "suggested_reaction": "StoryAreaTypeSuggestedReaction", "unique_gift": "StoryAreaTypeUniqueGift", "weather": "StoryAreaTypeWeather"}},
    "ReactionType": {"discriminator": "type", "map": {"custom_emoji": "ReactionTypeCustomEmoji", "emoji": "ReactionTypeEmoji", "paid": "ReactionTypePaid"}},
    "OwnedGift": {"discriminator": "type", "map": {"regular": "OwnedGiftRegular", "unique": "OwnedGiftUnique"}},
    "ChatBoostSource": {"discriminator": "source", "map": {"gift_code": "ChatBoostSourceGiftCode", "giveaway": "ChatBoostSourceGiveaway", "premium": "ChatBoostSourcePremium"}},
    "InputMedia": {"discriminator": "disable_content_type_detection", "map": {"True": "InputMediaDocument"}},
    "RevenueWithdrawalState": {"discriminator": "type", "map": {"failed": "RevenueWithdrawalStateFailed", "pending": "RevenueWithdrawalStatePending", "succeeded": "RevenueWithdrawalStateSucceeded"}},
    "TransactionPartner": {"discriminator": "type", "map": {"affiliate_program": "TransactionPartnerAffiliateProgram", "chat": "TransactionPartnerChat", "fragment": "TransactionPartnerFragment", "other": "TransactionPartnerOther", "telegram_ads": "TransactionPartnerTelegramAds", "telegram_api": "TransactionPartnerTelegramApi", "user": "TransactionPartnerUser"}},
})

# ── Auto-generated from Bot API 10.0 ───────────────────────────────────
_UPDATE_KINDS: List[str] = ['message', 'edited_message', 'channel_post', 'edited_channel_post', 'business_connection', 'business_message', 'edited_business_message', 'deleted_business_messages', 'guest_message', 'message_reaction', 'message_reaction_count', 'inline_query', 'chosen_inline_result', 'callback_query', 'shipping_query', 'pre_checkout_query', 'purchased_paid_media', 'poll', 'poll_answer', 'my_chat_member', 'chat_member', 'chat_join_request', 'chat_boost', 'removed_chat_boost', 'managed_bot']
_MESSAGE_CONTENT_TYPES: List[str] = ['direct_messages_topic', 'sender_tag', 'reply_to_checklist_task_id', 'reply_to_poll_option_id', 'is_paid_post', 'text', 'animation', 'audio', 'document', 'live_photo', 'paid_media', 'photo', 'sticker', 'story', 'video', 'video_note', 'voice', 'checklist', 'contact', 'dice', 'game', 'poll', 'venue', 'location', 'new_chat_members', 'left_chat_member', 'new_chat_title', 'new_chat_photo', 'delete_chat_photo', 'group_chat_created', 'supergroup_chat_created', 'channel_chat_created', 'pinned_message', 'invoice', 'successful_payment', 'gift', 'unique_gift', 'gift_upgrade_sent', 'passport_data', 'giveaway', 'suggested_post_approved', 'suggested_post_approval_failed', 'suggested_post_declined', 'suggested_post_paid', 'suggested_post_refunded']


# ── Multipart helpers ─────────────────────────────────────────────────────────
def _is_filelike(v: Any) -> bool:
    return isinstance(v, InputFile) or hasattr(v, "read") or isinstance(v, (bytes, bytearray))

def _has_any_file(v: Any) -> bool:
    if _is_filelike(v):
        return True
    if isinstance(v, TelegramObject):
        return any(_has_any_file(x) for x in v.__dict__.values() if x is not None)
    if isinstance(v, dict):
        return any(_has_any_file(x) for x in v.values() if x is not None)
    if isinstance(v, (list, tuple)):
        return any(_has_any_file(x) for x in v)
    return False

def _attach_file(v: Any, files: Dict[str, Any]) -> str:
    key = f"_a{len(files)}"
    if isinstance(v, InputFile):
        files[key] = v.open()
    elif isinstance(v, (bytes, bytearray)):
        files[key] = (key, bytes(v))
    else:
        files[key] = (os.path.basename(getattr(v, "name", "") or "") or key, v)
    return f"attach://{key}"

def _to_jsonable_nested(v: Any, files: Dict[str, Any]) -> Any:
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if _is_filelike(v):
        return _attach_file(v, files)
    if isinstance(v, TelegramObject):
        meta = getattr(v, "_FIELD_META", {})
        py2json = {info.get("py", k): k for k, info in meta.items()}
        return {py2json.get(k, k): _to_jsonable_nested(val, files) for k, val in v.__dict__.items() if val is not None}
    if isinstance(v, dict):
        return {k: _to_jsonable_nested(x, files) for k, x in v.items() if x is not None}
    if isinstance(v, (list, tuple)):
        return [_to_jsonable_nested(x, files) for x in v]
    return v

def _files_to_multipart(files: Optional[dict]) -> Optional[Any]:
    if not files:
        return None
    mp = _CurlMime()
    for name, value in files.items():
        filename: Optional[str] = None
        content_type: Optional[str] = None
        if isinstance(value, tuple):
            filename = value[0] if len(value) >= 1 else None
            payload_obj = value[1] if len(value) >= 2 else None
            content_type = value[2] if len(value) >= 3 else None
        else:
            payload_obj, filename = value, os.path.basename(getattr(value, "name", "") or "") or None
        if payload_obj is None:
            continue
        local_path: Optional[str] = None
        data: Optional[bytes] = None
        if isinstance(payload_obj, (bytes, bytearray)):
            data = bytes(payload_obj)
        elif hasattr(payload_obj, "read"):
            try:
                payload_obj.seek(0)
            except Exception:
                pass
            raw = payload_obj.read()
            data = raw.encode("utf-8") if isinstance(raw, str) else raw
            if filename is None:
                filename = os.path.basename(getattr(payload_obj, "name", "") or "") or name
        elif isinstance(payload_obj, str) and os.path.exists(payload_obj):
            local_path = payload_obj
            if filename is None:
                filename = os.path.basename(payload_obj)
        else:
            data = (payload_obj if isinstance(payload_obj, str) else str(payload_obj)).encode("utf-8")
        if filename is None:
            filename = name
        kw: Dict[str, Any] = {"name": name, "filename": filename}
        if content_type:
            kw["content_type"] = content_type
        if local_path is not None:
            kw["local_path"] = local_path
        else:
            kw["data"] = data or b""
        mp.addpart(**kw)
    return mp

def _build_request_parts(payload: Optional[dict]) -> Tuple[Optional[dict], Optional[dict], Optional[dict]]:
    if not payload:
        return None, None, None
    payload = {k: v for k, v in payload.items() if v is not None}
    if not payload:
        return None, None, None
    if not any(_has_any_file(v) for v in payload.values()):
        return {k: _value_to_jsonable(v) for k, v in payload.items()}, None, None
    files: Dict[str, Any] = {}
    data_body: Dict[str, str] = {}
    for k, v in payload.items():
        if isinstance(v, InputFile):
            files[k] = v.open()
        elif isinstance(v, (bytes, bytearray)):
            files[k] = (k, bytes(v))
        elif hasattr(v, "read"):
            files[k] = (os.path.basename(getattr(v, "name", "") or "") or k, v)
        elif isinstance(v, (TelegramObject, dict, list, tuple)):
            data_body[k] = json.dumps(_to_jsonable_nested(v, files), ensure_ascii=False)
        elif isinstance(v, bool):
            data_body[k] = "true" if v else "false"
        else:
            data_body[k] = str(v)
    return None, data_body, files


# ── Content-type detection ────────────────────────────────────────────────────
def _detect_content_type(message: Any) -> Optional[str]:
    """Return the single content type of *message*, or None"""
    if message is None:
        return None
    if getattr(message, "text", None) is not None:
        return "text"
    for ct in _MESSAGE_CONTENT_TYPES:
        if ct == "text":
            continue
        if getattr(message, ct, None) is not None:
            return ct
    return None

def _message_has_content_type(message: Any, content_types: List[str]) -> bool:
    """Check whether *message* matches any of the requested content types"""
    for ct in content_types:
        if ct == "text":
            if getattr(message, "text", None) is not None:
                return True
        elif getattr(message, ct, None) is not None:
            return True
    return False


# ── Bot ───────────────────────────────────────────────────────────────────────
class Bot:
    """Synchronous Telegram Bot API client
    Args:
        token: Bot token from @BotFather.
        api_url: Telegram API base URL (default: https://api.telegram.org)
        timeout: HTTP request timeout in seconds
        impersonate: curl_cffi TLS fingerprint (e.g. "chrome", "safari")
        parse_mode: Default parse mode for messages ("HTML", "MarkdownV2")
        proxies: Dict of proxy settings for curl_cffi
        max_retries: Max number of automatic retries for transport/server errors
        retry_on_flood: Whether to automatically retry on 429 Flood errors
    """
    def __init__(self, token: str, *, api_url: str = DEFAULT_API_URL, timeout: int = 60, impersonate: str = "chrome", parse_mode: Optional[str] = None, proxies: Optional[dict] = None, max_retries: int = 3, retry_on_flood: bool = True):
        if not token:
            raise ValueError("Bot token is required")
        self.token = token
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.parse_mode = parse_mode
        self.max_retries = max_retries
        self.retry_on_flood = retry_on_flood
        self._impersonate = impersonate
        self._proxies = proxies
        self._session = _CurlSession(impersonate=impersonate)
        if proxies:
            self._session.proxies.update(proxies)
        self._handlers: Dict[str, list] = {k: [] for k in _UPDATE_KINDS}
        self._error_handlers: list = []
        self._stop_polling = threading.Event()

    # ── HTTP transport ────────────────────────────────────────────────────────
    def _request(self, method_name: str, payload: Optional[dict] = None) -> Any:
        url = f"{self.api_url}/bot{self.token}/{method_name}"
        json_body, data_body, files = _build_request_parts(payload)
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._session.post(url, json=json_body, data=data_body, multipart=_files_to_multipart(files), timeout=self.timeout)
            except Exception as e:
                last_exc = e
                if attempt < self.max_retries:
                    wait = min(2 ** attempt, 30)
                    logger.warning("Transport error on %s (attempt %d): %s — retry in %ss", method_name, attempt + 1, e, wait)
                    time.sleep(wait)
                    continue
                raise
            try:
                body = resp.json()
            except Exception:
                err = TelegramAPIError(resp.status_code, f"Bad response: {resp.text[:200]}")
                err.method = method_name
                raise err
            if body.get("ok"):
                return body.get("result")
            err_code = body.get("error_code", resp.status_code)
            desc = body.get("description", "Unknown error")
            params = body.get("parameters") or {}
            if err_code == 429 and self.retry_on_flood and attempt < self.max_retries:
                wait = int(params.get("retry_after", 1)) + 1
                logger.warning("Flood wait %ss on %s", wait, method_name)
                time.sleep(wait)
                continue
            if err_code >= 500 and attempt < self.max_retries:
                wait = min(2 ** attempt, 30)
                logger.warning("Server error %d on %s — retry in %ss", err_code, method_name, wait)
                time.sleep(wait)
                continue
            err = TelegramAPIError(err_code, desc, params)
            err.method = method_name
            raise err
        if last_exc:
            raise last_exc
        raise TelegramAPIError(0, f"Exhausted {self.max_retries} retries on {method_name}")

    def _decode_result(self, raw: Any, meta: dict) -> Any:
        return _decode_value(raw, meta)

    # ── Handler registration ──────────────────────────────────────────────────
    def _add_handler(self, kind: str, fn: Callable, **filters) -> None:
        """Register *fn* as a handler for update kind *kind* with optional filters"""
        clean = {k: v for k, v in filters.items() if v is not None}
        self._handlers.setdefault(kind, []).append({"fn": fn, "filters": clean})

    def register_handler(self, kind: str, fn: Callable, *, commands=None, content_types=None, regexp=None, func=None, chat_types=None, user_ids=None, chat_ids=None) -> None:
        """Register a handler programmatically (no decorator needed)"""
        self._add_handler(kind, fn, commands=commands, content_types=content_types, regexp=regexp, func=func, chat_types=chat_types, user_ids=user_ids, chat_ids=chat_ids)

    def error_handler(self, fn: Callable) -> Callable:
        """Register a global error handler: fn(update, exception)"""
        self._error_handlers.append(fn)
        return fn

    # ── Handler decorators ────────────────────────────────────────────────────
    def message_handler(self, commands=None, content_types=None, regexp=None, func=None, chat_types=None, user_ids=None, chat_ids=None):
        """Decorator for incoming messages."""
        def deco(fn):
            self._add_handler("message", fn, commands=commands, content_types=content_types, regexp=regexp, func=func, chat_types=chat_types, user_ids=user_ids, chat_ids=chat_ids)
            return fn
        return deco

    def edited_message_handler(self, commands=None, content_types=None, regexp=None, func=None, chat_types=None, user_ids=None, chat_ids=None):
        def deco(fn):
            self._add_handler("edited_message", fn, commands=commands, content_types=content_types, regexp=regexp, func=func, chat_types=chat_types, user_ids=user_ids, chat_ids=chat_ids)
            return fn
        return deco

    def channel_post_handler(self, commands=None, content_types=None, regexp=None, func=None, chat_types=None, chat_ids=None):
        def deco(fn):
            self._add_handler("channel_post", fn, commands=commands, content_types=content_types, regexp=regexp, func=func, chat_types=chat_types, chat_ids=chat_ids)
            return fn
        return deco

    def edited_channel_post_handler(self, commands=None, content_types=None, regexp=None, func=None, chat_types=None):
        def deco(fn):
            self._add_handler("edited_channel_post", fn, commands=commands, content_types=content_types, regexp=regexp, func=func, chat_types=chat_types)
            return fn
        return deco

    def callback_query_handler(self, func=None, data=None):
        """data: exact string or regex pattern to match callback_query.data"""
        def deco(fn):
            self._add_handler("callback_query", fn, func=func, data=data)
            return fn
        return deco

    def inline_handler(self, func=None, regexp=None):
        def deco(fn):
            self._add_handler("inline_query", fn, func=func, regexp=regexp)
            return fn
        return deco

    def my_chat_member_handler(self, func=None):
        def deco(fn):
            self._add_handler("my_chat_member", fn, func=func)
            return fn
        return deco

    def chat_member_handler(self, func=None):
        def deco(fn):
            self._add_handler("chat_member", fn, func=func)
            return fn
        return deco

    def chat_join_request_handler(self, func=None):
        def deco(fn):
            self._add_handler("chat_join_request", fn, func=func)
            return fn
        return deco

    def poll_handler(self, func=None):
        def deco(fn):
            self._add_handler("poll", fn, func=func)
            return fn
        return deco

    def poll_answer_handler(self, func=None):
        def deco(fn):
            self._add_handler("poll_answer", fn, func=func)
            return fn
        return deco

    def pre_checkout_query_handler(self, func=None):
        def deco(fn):
            self._add_handler("pre_checkout_query", fn, func=func)
            return fn
        return deco

    def shipping_query_handler(self, func=None):
        def deco(fn):
            self._add_handler("shipping_query", fn, func=func)
            return fn
        return deco

    def business_message_handler(self, commands=None, content_types=None, regexp=None, func=None):
        def deco(fn):
            self._add_handler("business_message", fn, commands=commands, content_types=content_types, regexp=regexp, func=func)
            return fn
        return deco

    def edited_business_message_handler(self, commands=None, content_types=None, regexp=None, func=None):
        def deco(fn):
            self._add_handler("edited_business_message", fn, commands=commands, content_types=content_types, regexp=regexp, func=func)
            return fn
        return deco

    def deleted_business_messages_handler(self, func=None):
        def deco(fn):
            self._add_handler("deleted_business_messages", fn, func=func)
            return fn
        return deco

    def chosen_inline_result_handler(self, func=None):
        def deco(fn):
            self._add_handler("chosen_inline_result", fn, func=func)
            return fn
        return deco

    def message_reaction_handler(self, func=None):
        def deco(fn):
            self._add_handler("message_reaction", fn, func=func)
            return fn
        return deco

    def message_reaction_count_handler(self, func=None):
        def deco(fn):
            self._add_handler("message_reaction_count", fn, func=func)
            return fn
        return deco

    def chat_boost_handler(self, func=None):
        def deco(fn):
            self._add_handler("chat_boost", fn, func=func)
            return fn
        return deco

    def removed_chat_boost_handler(self, func=None):
        def deco(fn):
            self._add_handler("removed_chat_boost", fn, func=func)
            return fn
        return deco

    def purchased_paid_media_handler(self, func=None):
        def deco(fn):
            self._add_handler("purchased_paid_media", fn, func=func)
            return fn
        return deco

    # ── Filter matching ───────────────────────────────────────────────────────
    @staticmethod
    def _matches(handler: dict, update_obj: Any) -> bool:
        """Return True if *update_obj* satisfies all filters in *handler*
        Key design notes
        ----------------
        * content_types is checked directly via attribute lookup, NOT through _detect_content_type ordering. This ensures admin / creator messages with extra fields (new in Bot API 10) are never mis-classified
        * user_ids / chat_ids whitelists let you restrict handlers without writing a custom func.
        * Commands: a bare "/" without a word after it is silently rejected
        * chat.type_val is used instead of chat.type because type is renamed to type_val in the generated dataclass
        """
        f = handler["filters"]
        commands = f.get("commands")
        content_types = f.get("content_types")
        regexp = f.get("regexp")
        func = f.get("func")
        chat_types = f.get("chat_types")
        user_ids = f.get("user_ids")
        chat_ids = f.get("chat_ids")
        cb_data = f.get("data")

        # ── commands ──────────────────────────────────────────────────────
        if commands:
            text = getattr(update_obj, "text", None) or ""
            if not text.startswith("/"):
                return False
            parts = text[1:].split()
            if not parts:
                return False
            cmd = parts[0].split("@")[0].lower()
            if cmd not in {c.lstrip("/").lower() for c in commands}:
                return False

        # ── content_types ─────────────────────────────────────────────────
        if content_types is not None:
            if not _message_has_content_type(update_obj, content_types):
                return False

        # ── regexp ────────────────────────────────────────────────────────
        if regexp is not None:
            target = getattr(update_obj, "text", None) or getattr(update_obj, "caption", None)
            if target is None or not re.search(regexp, target):
                return False

        # ── chat_types ────────────────────────────────────────────────────
        if chat_types:
            chat = getattr(update_obj, "chat", None)
            chat_type = getattr(chat, "type_val", None) or getattr(chat, "type", None)
            if chat_type not in chat_types:
                return False

        # ── user_ids whitelist ────────────────────────────────────────────
        if user_ids:
            from_user = getattr(update_obj, "from_user", None)
            uid = getattr(from_user, "id", None)
            if uid not in user_ids:
                return False

        # ── chat_ids whitelist ────────────────────────────────────────────
        if chat_ids:
            chat = getattr(update_obj, "chat", None)
            cid = getattr(chat, "id", None)
            if cid not in chat_ids:
                return False

        # ── callback_query data ───────────────────────────────────────────
        if cb_data is not None:
            cq_data = getattr(update_obj, "data", None) or ""
            if isinstance(cb_data, str):
                if cq_data != cb_data and not re.search(cb_data, cq_data):
                    return False
            elif callable(cb_data):
                if not cb_data(cq_data):
                    return False

        # ── custom predicate ──────────────────────────────────────────────
        if func is not None and not func(update_obj):
            return False

        return True

    # ── Dispatch ──────────────────────────────────────────────────────────────
    def _call_error_handlers(self, update: Any, exc: Exception) -> None:
        for eh in self._error_handlers:
            try:
                eh(update, exc)
            except Exception:
                logger.exception("Error inside error_handler")

    def _dispatch(self, update: "Update") -> None:
        """Dispatch *update* to the first matching handler per update kind
        Behaviour
        ---------
        * First matching handler wins (pyTelegramBotAPI-style)
        * A handler may raise StopPropagation to explicitly stop processing
        * If a handler raises any other exception, it is logged, error handlers are called, and we stop trying further handlers for that kind
        """
        for kind in self._handlers:
            obj = getattr(update, kind, None)
            if obj is None:
                continue
            for handler in self._handlers[kind]:
                if not self._matches(handler, obj):
                    continue
                try:
                    handler["fn"](obj)
                except StopPropagation:
                    pass
                except Exception as e:
                    logger.exception("Handler error in %s: %s", kind, e)
                    self._call_error_handlers(update, e)
                break

    # ── Webhook processing ────────────────────────────────────────────────────
    def process_update(self, update_dict: dict) -> None:
        """Process a single update dict (from webhook JSON body)
        Usage with a web framework::
            @app.post("/webhook")
            def webhook():
                bot.process_update(request.json)
                return "ok"
        """
        upd = Update.from_dict(update_dict)
        if upd is not None:
            self._dispatch(upd)

    # ── Polling ───────────────────────────────────────────────────────────────
    def stop_polling(self) -> None:
        self._stop_polling.set()

    def polling(self, *, timeout: int = 30, allowed_updates: Optional[List[str]] = None, none_stop: bool = True, interval: float = 0.0) -> None:
        offset = 0
        self._stop_polling.clear()
        logger.info("neogram polling started")
        while not self._stop_polling.is_set():
            try:
                updates = self.get_updates(
                    offset=offset, timeout=timeout,
                    allowed_updates=allowed_updates) or []
                for upd in updates:
                    offset = upd.update_id + 1
                    self._dispatch(upd)
                if interval:
                    time.sleep(interval)
            except TelegramAPIError as e:
                logger.error("Telegram API error: %s", e)
                if not none_stop:
                    raise
                time.sleep(3)
            except Exception as e:
                logger.exception("Polling error: %s", e)
                if not none_stop:
                    raise
                time.sleep(3)
        logger.info("neogram polling stopped")

    def infinity_polling(self, **kwargs) -> None:
        kwargs.setdefault("none_stop", True)
        self.polling(**kwargs)


# ── AsyncBot ──────────────────────────────────────────────────────────────────
class AsyncBot(Bot):
    """Asynchronous Telegram Bot API client
    All API methods are coroutines. Use await bot.send_message(...) etc
    Supports async context manager::
        async with AsyncBot(token=...) as bot:
            await bot.send_message(chat_id=123, text="Hello")
    """
    def __init__(self, token: str, **kwargs):
        super().__init__(token, **kwargs)
        self._session = _AsyncSession(impersonate=self._impersonate)
        if self._proxies:
            try:
                self._session.proxies.update(self._proxies)
            except Exception:
                pass

    async def __aenter__(self) -> "AsyncBot":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    async def _arequest(self, method_name: str, payload: Optional[dict] = None) -> Any:
        url = f"{self.api_url}/bot{self.token}/{method_name}"
        json_body, data_body, files = _build_request_parts(payload)
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = await self._session.post(url, json=json_body, data=data_body, multipart=_files_to_multipart(files), timeout=self.timeout)
            except Exception as e:
                last_exc = e
                if attempt < self.max_retries:
                    wait = min(2 ** attempt, 30)
                    logger.warning("Async transport error on %s (attempt %d): %s — retry in %ss", method_name, attempt + 1, e, wait)
                    await _asyncio.sleep(wait)
                    continue
                raise
            try:
                body = resp.json()
            except Exception:
                err = TelegramAPIError(resp.status_code, f"Bad response: {resp.text[:200]}")
                err.method = method_name
                raise err
            if body.get("ok"):
                return body.get("result")
            err_code = body.get("error_code", resp.status_code)
            desc = body.get("description", "Unknown error")
            params = body.get("parameters") or {}
            if err_code == 429 and self.retry_on_flood and attempt < self.max_retries:
                wait = int(params.get("retry_after", 1)) + 1
                logger.warning("Async flood wait %ss on %s", wait, method_name)
                await _asyncio.sleep(wait)
                continue
            if err_code >= 500 and attempt < self.max_retries:
                wait = min(2 ** attempt, 30)
                logger.warning("Async server error %d on %s — retry in %ss", err_code, method_name, wait)
                await _asyncio.sleep(wait)
                continue
            err = TelegramAPIError(err_code, desc, params)
            err.method = method_name
            raise err
        if last_exc:
            raise last_exc
        raise TelegramAPIError(0, f"Exhausted {self.max_retries} retries on {method_name}")

    async def _call_error_handlers_async(self, update: Any, exc: Exception) -> None:
        for eh in self._error_handlers:
            try:
                res = eh(update, exc)
                if _inspect.isawaitable(res):
                    await res
            except Exception:
                logger.exception("Error inside async error_handler")

    async def _adispatch(self, update: "Update") -> None:
        """Async version of _dispatch. Supports both sync and async handlers"""
        for kind in self._handlers:
            obj = getattr(update, kind, None)
            if obj is None:
                continue
            for handler in self._handlers[kind]:
                if not self._matches(handler, obj):
                    continue
                try:
                    res = handler["fn"](obj)
                    if _inspect.isawaitable(res):
                        await res
                except StopPropagation:
                    pass
                except Exception as e:
                    logger.exception("Async handler error in %s: %s", kind, e)
                    await self._call_error_handlers_async(update, e)
                break

    async def process_update(self, update_dict: dict) -> None:
        """Async version of process_update for webhook handling"""
        upd = Update.from_dict(update_dict)
        if upd is not None:
            await self._adispatch(upd)

    async def polling(self, *, timeout: int = 30, allowed_updates: Optional[List[str]] = None, none_stop: bool = True, interval: float = 0.0) -> None:
        offset = 0
        self._stop_polling.clear()
        logger.info("neogram async polling started")
        while not self._stop_polling.is_set():
            try:
                updates = await self.get_updates(offset=offset, timeout=timeout, allowed_updates=allowed_updates) or []
                for upd in updates:
                    offset = upd.update_id + 1
                    await self._adispatch(upd)
                if interval:
                    await _asyncio.sleep(interval)
            except TelegramAPIError as e:
                logger.error("Telegram API error: %s", e)
                if not none_stop:
                    raise
                await _asyncio.sleep(3)
            except Exception as e:
                logger.exception("Polling error: %s", e)
                if not none_stop:
                    raise
                await _asyncio.sleep(3)
        logger.info("neogram async polling stopped")

    async def infinity_polling(self, **kwargs) -> None:
        kwargs.setdefault("none_stop", True)
        await self.polling(**kwargs)

    async def aclose(self) -> None:
        try:
            await self._session.close()
        except Exception:
            pass

# ── Bot API methods (sync) ───────────────────────────────────────────────────

class _BotMethods:
    def get_updates(self, offset: Optional[int] = None, limit: Optional[int] = None, timeout: Optional[int] = None, allowed_updates: Optional[List[str]] = None) -> List["Update"]:
        """Use this method to receive incoming updates using long polling ( wiki ). Returns an Array of Update objects."""
        _payload = {
            "offset": offset,
            "limit": limit,
            "timeout": timeout,
            "allowed_updates": allowed_updates,
        }
        _result = self._request("getUpdates", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'Update', "list_depth": 1})


    def set_webhook(self, url: str, certificate: Optional[Union[str, InputFile]] = None, ip_address: Optional[str] = None, max_connections: Optional[int] = None, allowed_updates: Optional[List[str]] = None, drop_pending_updates: Optional[bool] = None, secret_token: Optional[str] = None) -> bool:
        """Use this method to specify a URL and receive incoming updates via an outgoing webhook. Whenever there is an update for the bot, we will send an HTTPS POST request to the specified URL, containing a JSON-serialized Update . In case of an unsuccessful request (a request with response HTTP status code different from 2XY ), we will repeat the request and give up after a reasonable amount of attempts. Returns True on success."""
        _payload = {
            "url": url,
            "certificate": certificate,
            "ip_address": ip_address,
            "max_connections": max_connections,
            "allowed_updates": allowed_updates,
            "drop_pending_updates": drop_pending_updates,
            "secret_token": secret_token,
        }
        _result = self._request("setWebhook", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def delete_webhook(self, drop_pending_updates: Optional[bool] = None) -> bool:
        """Use this method to remove webhook integration if you decide to switch back to getUpdates . Returns True on success."""
        _payload = {
            "drop_pending_updates": drop_pending_updates,
        }
        _result = self._request("deleteWebhook", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_webhook_info(self) -> "WebhookInfo":
        """Use this method to get current webhook status. Requires no parameters. On success, returns a WebhookInfo object. If the bot is using getUpdates , will return an object with the url field empty."""
        _payload = None
        _result = self._request("getWebhookInfo", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'WebhookInfo', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_me(self) -> "User":
        """A simple method for testing your bot's authentication token. Requires no parameters. Returns basic information about the bot in form of a User object."""
        _payload = None
        _result = self._request("getMe", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def log_out(self) -> bool:
        """Use this method to log out from the cloud Bot API server before launching the bot locally. You must log out the bot before running it locally, otherwise there is no guarantee that the bot will receive updates. After a successful call, you can immediately log in on a local server, but will not be able to log in back to the cloud Bot API server for 10 minutes. Returns True on success. Requires no parameters."""
        _payload = None
        _result = self._request("logOut", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def close(self) -> bool:
        """Use this method to close the bot instance before moving it from one local server to another. You need to delete the webhook before calling this method to ensure that the bot isn't launched again after server restart. The method will return error 429 in the first 10 minutes after the bot is launched. Returns True on success. Requires no parameters."""
        _payload = None
        _result = self._request("close", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_message(self, chat_id: Union[int, str], text: str, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, parse_mode: Optional[str] = None, entities: Optional[List["MessageEntity"]] = None, link_preview_options: Optional["LinkPreviewOptions"] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send text messages. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "text": text,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "entities": entities,
            "link_preview_options": link_preview_options,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("sendMessage", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def forward_message(self, chat_id: Union[int, str], from_chat_id: Union[int, str], message_id: int, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, video_start_timestamp: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None) -> "MessageId":
        """Use this method to forward messages of any kind. Service messages and messages with protected content can't be forwarded. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "from_chat_id": from_chat_id,
            "message_id": message_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "video_start_timestamp": video_start_timestamp,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
        }
        _result = self._request("forwardMessage", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'MessageId', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def forward_messages(self, chat_id: Union[int, str], from_chat_id: Union[int, str], message_ids: List[int], message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None) -> List["MessageId"]:
        """Use this method to forward multiple messages of any kind. If some of the specified messages can't be found or forwarded, they are skipped. Service messages and messages with protected content can't be forwarded. Album grouping is kept for forwarded messages. On success, an array of MessageId of the sent messages is returned."""
        _payload = {
            "chat_id": chat_id,
            "from_chat_id": from_chat_id,
            "message_ids": message_ids,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
        }
        _result = self._request("forwardMessages", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageId', "list_depth": 1})


    def copy_message(self, chat_id: Union[int, str], from_chat_id: Union[int, str], message_id: int, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, video_start_timestamp: Optional[int] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "MessageId":
        """Use this method to copy messages of any kind. Service messages, paid media messages, giveaway messages, giveaway winners messages, and invoice messages can't be copied. A quiz poll can be copied only if the value of the field correct_option_id is known to the bot. The method is analogous to the method forwardMessage , but the copied message doesn't have a link to the original message. Returns the MessageId of the sent message on success."""
        _payload = {
            "chat_id": chat_id,
            "from_chat_id": from_chat_id,
            "message_id": message_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "video_start_timestamp": video_start_timestamp,
            "caption": caption,
            "parse_mode": parse_mode,
            "caption_entities": caption_entities,
            "show_caption_above_media": show_caption_above_media,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("copyMessage", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'MessageId', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def copy_messages(self, chat_id: Union[int, str], from_chat_id: Union[int, str], message_ids: List[int], message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, remove_caption: Optional[bool] = None) -> List["MessageId"]:
        """Use this method to copy messages of any kind. If some of the specified messages can't be found or copied, they are skipped. Service messages, paid media messages, giveaway messages, giveaway winners messages, and invoice messages can't be copied. A quiz poll can be copied only if the value of the field correct_option_id is known to the bot. The method is analogous to the method forwardMessages , but the copied messages don't have a link to the original message. Album grouping is kept for copied messages. On success, an array of MessageId of the sent messages is returned."""
        _payload = {
            "chat_id": chat_id,
            "from_chat_id": from_chat_id,
            "message_ids": message_ids,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "remove_caption": remove_caption,
        }
        _result = self._request("copyMessages", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageId', "list_depth": 1})


    def send_photo(self, chat_id: Union[int, str], photo: Union[Union[str, InputFile], str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, has_spoiler: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send photos. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "photo": photo,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "caption": caption,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "caption_entities": caption_entities,
            "show_caption_above_media": show_caption_above_media,
            "has_spoiler": has_spoiler,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("sendPhoto", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_live_photo(self, chat_id: Union[int, str], live_photo: Union[Union[str, InputFile], str], photo: Union[Union[str, InputFile], str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, has_spoiler: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send live photos. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "live_photo": live_photo,
            "photo": photo,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "caption": caption,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "caption_entities": caption_entities,
            "show_caption_above_media": show_caption_above_media,
            "has_spoiler": has_spoiler,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("sendLivePhoto", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_audio(self, chat_id: Union[int, str], audio: Union[Union[str, InputFile], str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, duration: Optional[int] = None, performer: Optional[str] = None, title: Optional[str] = None, thumbnail: Optional[Union[Union[str, InputFile], str]] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send audio files, if you want Telegram clients to display them in the music player. Your audio must be in the .MP3 or .M4A format. On success, the sent Message is returned. Bots can currently send audio files of up to 50 MB in size, this limit may be changed in the future."""
        _payload = {
            "chat_id": chat_id,
            "audio": audio,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "caption": caption,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "caption_entities": caption_entities,
            "duration": duration,
            "performer": performer,
            "title": title,
            "thumbnail": thumbnail,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("sendAudio", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_document(self, chat_id: Union[int, str], document: Union[Union[str, InputFile], str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, thumbnail: Optional[Union[Union[str, InputFile], str]] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, disable_content_type_detection: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send general files. On success, the sent Message is returned. Bots can currently send files of any type of up to 50 MB in size, this limit may be changed in the future."""
        _payload = {
            "chat_id": chat_id,
            "document": document,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "thumbnail": thumbnail,
            "caption": caption,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "caption_entities": caption_entities,
            "disable_content_type_detection": disable_content_type_detection,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("sendDocument", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_video(self, chat_id: Union[int, str], video: Union[Union[str, InputFile], str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, duration: Optional[int] = None, width: Optional[int] = None, height: Optional[int] = None, thumbnail: Optional[Union[Union[str, InputFile], str]] = None, cover: Optional[Union[Union[str, InputFile], str]] = None, start_timestamp: Optional[int] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, has_spoiler: Optional[bool] = None, supports_streaming: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send video files, Telegram clients support MPEG4 videos (other formats may be sent as Document ). On success, the sent Message is returned. Bots can currently send video files of up to 50 MB in size, this limit may be changed in the future."""
        _payload = {
            "chat_id": chat_id,
            "video": video,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "duration": duration,
            "width": width,
            "height": height,
            "thumbnail": thumbnail,
            "cover": cover,
            "start_timestamp": start_timestamp,
            "caption": caption,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "caption_entities": caption_entities,
            "show_caption_above_media": show_caption_above_media,
            "has_spoiler": has_spoiler,
            "supports_streaming": supports_streaming,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("sendVideo", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_animation(self, chat_id: Union[int, str], animation: Union[Union[str, InputFile], str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, duration: Optional[int] = None, width: Optional[int] = None, height: Optional[int] = None, thumbnail: Optional[Union[Union[str, InputFile], str]] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, has_spoiler: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send animation files (GIF or H.264/MPEG-4 AVC video without sound). On success, the sent Message is returned. Bots can currently send animation files of up to 50 MB in size, this limit may be changed in the future."""
        _payload = {
            "chat_id": chat_id,
            "animation": animation,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "duration": duration,
            "width": width,
            "height": height,
            "thumbnail": thumbnail,
            "caption": caption,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "caption_entities": caption_entities,
            "show_caption_above_media": show_caption_above_media,
            "has_spoiler": has_spoiler,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("sendAnimation", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_voice(self, chat_id: Union[int, str], voice: Union[Union[str, InputFile], str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, duration: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send audio files, if you want Telegram clients to display the file as a playable voice message. For this to work, your audio must be in an .OGG file encoded with OPUS, or in .MP3 format, or in .M4A format (other formats may be sent as Audio or Document ). On success, the sent Message is returned. Bots can currently send voice messages of up to 50 MB in size, this limit may be changed in the future."""
        _payload = {
            "chat_id": chat_id,
            "voice": voice,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "caption": caption,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "caption_entities": caption_entities,
            "duration": duration,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("sendVoice", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_video_note(self, chat_id: Union[int, str], video_note: Union[Union[str, InputFile], str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, duration: Optional[int] = None, length: Optional[int] = None, thumbnail: Optional[Union[Union[str, InputFile], str]] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """As of v.4.0 , Telegram clients support rounded square MPEG4 videos of up to 1 minute long. Use this method to send video messages. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "video_note": video_note,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "duration": duration,
            "length": length,
            "thumbnail": thumbnail,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("sendVideoNote", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_paid_media(self, chat_id: Union[int, str], star_count: int, media: List["InputPaidMedia"], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, payload: Optional[str] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send paid media. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "star_count": star_count,
            "media": media,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "payload": payload,
            "caption": caption,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "caption_entities": caption_entities,
            "show_caption_above_media": show_caption_above_media,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("sendPaidMedia", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_media_group(self, chat_id: Union[int, str], media: List[Any], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, reply_parameters: Optional["ReplyParameters"] = None) -> List["Message"]:
        """Use this method to send a group of photos, live photos, videos, documents or audios as an album. Documents and audio files can be only grouped in an album with messages of the same type. On success, an array of Message objects that were sent is returned."""
        _payload = {
            "chat_id": chat_id,
            "media": media,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "reply_parameters": reply_parameters,
        }
        _result = self._request("sendMediaGroup", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'Message', "list_depth": 1})


    def send_location(self, chat_id: Union[int, str], latitude: float, longitude: float, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, horizontal_accuracy: Optional[float] = None, live_period: Optional[int] = None, heading: Optional[int] = None, proximity_alert_radius: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send point on the map. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "latitude": latitude,
            "longitude": longitude,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "horizontal_accuracy": horizontal_accuracy,
            "live_period": live_period,
            "heading": heading,
            "proximity_alert_radius": proximity_alert_radius,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("sendLocation", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_venue(self, chat_id: Union[int, str], latitude: float, longitude: float, title: str, address: str, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, foursquare_id: Optional[str] = None, foursquare_type: Optional[str] = None, google_place_id: Optional[str] = None, google_place_type: Optional[str] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send information about a venue. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "latitude": latitude,
            "longitude": longitude,
            "title": title,
            "address": address,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "foursquare_id": foursquare_id,
            "foursquare_type": foursquare_type,
            "google_place_id": google_place_id,
            "google_place_type": google_place_type,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("sendVenue", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_contact(self, chat_id: Union[int, str], phone_number: str, first_name: str, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, last_name: Optional[str] = None, vcard: Optional[str] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send phone contacts. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "phone_number": phone_number,
            "first_name": first_name,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "last_name": last_name,
            "vcard": vcard,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("sendContact", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_poll(self, chat_id: Union[int, str], question: str, options: List["InputPollOption"], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, question_parse_mode: Optional[str] = None, question_entities: Optional[List["MessageEntity"]] = None, is_anonymous: Optional[bool] = None, type_val: Optional[str] = None, allows_multiple_answers: Optional[bool] = None, allows_revoting: Optional[bool] = None, shuffle_options: Optional[bool] = None, allow_adding_options: Optional[bool] = None, hide_results_until_closes: Optional[bool] = None, members_only: Optional[bool] = None, country_codes: Optional[List[str]] = None, correct_option_ids: Optional[List[int]] = None, explanation: Optional[str] = None, explanation_parse_mode: Optional[str] = None, explanation_entities: Optional[List["MessageEntity"]] = None, explanation_media: Optional["InputPollMedia"] = None, open_period: Optional[int] = None, close_date: Optional[int] = None, is_closed: Optional[bool] = None, description: Optional[str] = None, description_parse_mode: Optional[str] = None, description_entities: Optional[List["MessageEntity"]] = None, media: Optional["InputPollMedia"] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send a native poll. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "question": question,
            "options": options,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "question_parse_mode": question_parse_mode,
            "question_entities": question_entities,
            "is_anonymous": is_anonymous,
            "type": type_val,
            "allows_multiple_answers": allows_multiple_answers,
            "allows_revoting": allows_revoting,
            "shuffle_options": shuffle_options,
            "allow_adding_options": allow_adding_options,
            "hide_results_until_closes": hide_results_until_closes,
            "members_only": members_only,
            "country_codes": country_codes,
            "correct_option_ids": correct_option_ids,
            "explanation": explanation,
            "explanation_parse_mode": explanation_parse_mode,
            "explanation_entities": explanation_entities,
            "explanation_media": explanation_media,
            "open_period": open_period,
            "close_date": close_date,
            "is_closed": is_closed,
            "description": description,
            "description_parse_mode": description_parse_mode,
            "description_entities": description_entities,
            "media": media,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("sendPoll", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_checklist(self, business_connection_id: str, chat_id: Union[int, str], checklist: "InputChecklist", disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, message_effect_id: Optional[str] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Message":
        """Use this method to send a checklist on behalf of a connected business account. On success, the sent Message is returned."""
        _payload = {
            "business_connection_id": business_connection_id,
            "chat_id": chat_id,
            "checklist": checklist,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "message_effect_id": message_effect_id,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("sendChecklist", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_dice(self, chat_id: Union[int, str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, emoji: Optional[str] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send an animated emoji that will display a random value. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "emoji": emoji,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("sendDice", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_message_draft(self, chat_id: int, draft_id: int, message_thread_id: Optional[int] = None, text: Optional[str] = None, parse_mode: Optional[str] = None, entities: Optional[List["MessageEntity"]] = None) -> "Message":
        """Use this method to stream a partial message to a user while the message is being generated. Note that the streamed draft is ephemeral and acts as a temporary 30-second preview - once the output is finalized, you must call sendMessage with the complete message to persist it in the user's chat. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "draft_id": draft_id,
            "message_thread_id": message_thread_id,
            "text": text,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "entities": entities,
        }
        _result = self._request("sendMessageDraft", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_chat_action(self, chat_id: Union[int, str], action: str, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None) -> bool:
        """Use this method when you need to tell the user that something is happening on the bot's side. The status is set for 5 seconds or less (when a message arrives from your bot, Telegram clients clear its typing status). Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "action": action,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
        }
        _result = self._request("sendChatAction", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_message_reaction(self, chat_id: Union[int, str], message_id: int, reaction: Optional[List["ReactionType"]] = None, is_big: Optional[bool] = None) -> bool:
        """Use this method to change the chosen reactions on a message. Service messages of some types can't be reacted to. Automatically forwarded messages from a channel to its discussion group have the same available reactions as messages in the channel. Bots can't use paid reactions. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "reaction": reaction,
            "is_big": is_big,
        }
        _result = self._request("setMessageReaction", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_user_profile_photos(self, user_id: int, offset: Optional[int] = None, limit: Optional[int] = None) -> "UserProfilePhotos":
        """Use this method to get a list of profile pictures for a user. Returns a UserProfilePhotos object."""
        _payload = {
            "user_id": user_id,
            "offset": offset,
            "limit": limit,
        }
        _result = self._request("getUserProfilePhotos", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'UserProfilePhotos', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_user_profile_audios(self, user_id: int, offset: Optional[int] = None, limit: Optional[int] = None) -> "UserProfileAudios":
        """Use this method to get a list of profile audios for a user. Returns a UserProfileAudios object."""
        _payload = {
            "user_id": user_id,
            "offset": offset,
            "limit": limit,
        }
        _result = self._request("getUserProfileAudios", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'UserProfileAudios', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_user_emoji_status(self, user_id: int, emoji_status_custom_emoji_id: Optional[str] = None, emoji_status_expiration_date: Optional[int] = None) -> bool:
        """Changes the emoji status for a given user that previously allowed the bot to manage their emoji status via the Mini App method requestEmojiStatusAccess . Returns True on success."""
        _payload = {
            "user_id": user_id,
            "emoji_status_custom_emoji_id": emoji_status_custom_emoji_id,
            "emoji_status_expiration_date": emoji_status_expiration_date,
        }
        _result = self._request("setUserEmojiStatus", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_file(self, file_id: str) -> "File":
        """Use this method to get basic information about a file and prepare it for downloading. For the moment, bots can download files of up to 20MB in size. On success, a File object is returned. The file can then be downloaded via the link https://api.telegram.org/file/bot<token>/<file_path> , where <file_path> is taken from the response. It is guaranteed that the link will be valid for at least 1 hour. When the link expires, a new one can be requested by calling getFile again."""
        _payload = {
            "file_id": file_id,
        }
        _result = self._request("getFile", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'File', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def ban_chat_member(self, chat_id: Union[int, str], user_id: int, until_date: Optional[int] = None, revoke_messages: Optional[bool] = None) -> bool:
        """Use this method to ban a user in a group, a supergroup or a channel. In the case of supergroups and channels, the user will not be able to return to the chat on their own using invite links, etc., unless unbanned first. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
            "until_date": until_date,
            "revoke_messages": revoke_messages,
        }
        _result = self._request("banChatMember", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def unban_chat_member(self, chat_id: Union[int, str], user_id: int, only_if_banned: Optional[bool] = None) -> bool:
        """Use this method to unban a previously banned user in a supergroup or channel. The user will not return to the group or channel automatically, but will be able to join via link, etc. The bot must be an administrator for this to work. By default, this method guarantees that after the call the user is not a member of the chat, but will be able to join it. So if the user is a member of the chat they will also be removed from the chat. If you don't want this, use the parameter only_if_banned . Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
            "only_if_banned": only_if_banned,
        }
        _result = self._request("unbanChatMember", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def restrict_chat_member(self, chat_id: Union[int, str], user_id: int, permissions: "ChatPermissions", use_independent_chat_permissions: Optional[bool] = None, until_date: Optional[int] = None) -> bool:
        """Use this method to restrict a user in a supergroup. The bot must be an administrator in the supergroup for this to work and must have the appropriate administrator rights. Pass True for all permissions to lift restrictions from a user. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
            "permissions": permissions,
            "use_independent_chat_permissions": use_independent_chat_permissions,
            "until_date": until_date,
        }
        _result = self._request("restrictChatMember", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def promote_chat_member(self, chat_id: Union[int, str], user_id: int, is_anonymous: Optional[bool] = None, can_manage_chat: Optional[bool] = None, can_delete_messages: Optional[bool] = None, can_manage_video_chats: Optional[bool] = None, can_restrict_members: Optional[bool] = None, can_promote_members: Optional[bool] = None, can_change_info: Optional[bool] = None, can_invite_users: Optional[bool] = None, can_post_stories: Optional[bool] = None, can_edit_stories: Optional[bool] = None, can_delete_stories: Optional[bool] = None, can_post_messages: Optional[bool] = None, can_edit_messages: Optional[bool] = None, can_pin_messages: Optional[bool] = None, can_manage_topics: Optional[bool] = None, can_manage_direct_messages: Optional[bool] = None, can_manage_tags: Optional[bool] = None) -> bool:
        """Use this method to promote or demote a user in a supergroup or a channel. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Pass False for all boolean parameters to demote a user. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
            "is_anonymous": is_anonymous,
            "can_manage_chat": can_manage_chat,
            "can_delete_messages": can_delete_messages,
            "can_manage_video_chats": can_manage_video_chats,
            "can_restrict_members": can_restrict_members,
            "can_promote_members": can_promote_members,
            "can_change_info": can_change_info,
            "can_invite_users": can_invite_users,
            "can_post_stories": can_post_stories,
            "can_edit_stories": can_edit_stories,
            "can_delete_stories": can_delete_stories,
            "can_post_messages": can_post_messages,
            "can_edit_messages": can_edit_messages,
            "can_pin_messages": can_pin_messages,
            "can_manage_topics": can_manage_topics,
            "can_manage_direct_messages": can_manage_direct_messages,
            "can_manage_tags": can_manage_tags,
        }
        _result = self._request("promoteChatMember", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_chat_administrator_custom_title(self, chat_id: Union[int, str], user_id: int, custom_title: str) -> bool:
        """Use this method to set a custom title for an administrator in a supergroup promoted by the bot. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
            "custom_title": custom_title,
        }
        _result = self._request("setChatAdministratorCustomTitle", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_chat_member_tag(self, chat_id: Union[int, str], user_id: int, tag: Optional[str] = None) -> bool:
        """Use this method to set a tag for a regular member in a group or a supergroup. The bot must be an administrator in the chat for this to work and must have the can_manage_tags administrator right. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
            "tag": tag,
        }
        _result = self._request("setChatMemberTag", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def ban_chat_sender_chat(self, chat_id: Union[int, str], sender_chat_id: int) -> bool:
        """Use this method to ban a channel chat in a supergroup or a channel. Until the chat is unbanned , the owner of the banned chat won't be able to send messages on behalf of any of their channels . The bot must be an administrator in the supergroup or channel for this to work and must have the appropriate administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "sender_chat_id": sender_chat_id,
        }
        _result = self._request("banChatSenderChat", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def unban_chat_sender_chat(self, chat_id: Union[int, str], sender_chat_id: int) -> bool:
        """Use this method to unban a previously banned channel chat in a supergroup or channel. The bot must be an administrator for this to work and must have the appropriate administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "sender_chat_id": sender_chat_id,
        }
        _result = self._request("unbanChatSenderChat", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_chat_permissions(self, chat_id: Union[int, str], permissions: "ChatPermissions", use_independent_chat_permissions: Optional[bool] = None) -> bool:
        """Use this method to set default chat permissions for all members. The bot must be an administrator in the group or a supergroup for this to work and must have the can_restrict_members administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "permissions": permissions,
            "use_independent_chat_permissions": use_independent_chat_permissions,
        }
        _result = self._request("setChatPermissions", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def export_chat_invite_link(self, chat_id: Union[int, str]) -> str:
        """Use this method to generate a new primary invite link for a chat; any previously generated primary link is revoked. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns the new invite link as String on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = self._request("exportChatInviteLink", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def create_chat_invite_link(self, chat_id: Union[int, str], name: Optional[str] = None, expire_date: Optional[int] = None, member_limit: Optional[int] = None, creates_join_request: Optional[bool] = None) -> "ChatInviteLink":
        """Use this method to create an additional invite link for a chat. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. The link can be revoked using the method revokeChatInviteLink . Returns the new invite link as ChatInviteLink object."""
        _payload = {
            "chat_id": chat_id,
            "name": name,
            "expire_date": expire_date,
            "member_limit": member_limit,
            "creates_join_request": creates_join_request,
        }
        _result = self._request("createChatInviteLink", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'ChatInviteLink', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def edit_chat_invite_link(self, chat_id: Union[int, str], invite_link: str, name: Optional[str] = None, expire_date: Optional[int] = None, member_limit: Optional[int] = None, creates_join_request: Optional[bool] = None) -> "ChatInviteLink":
        """Use this method to edit a non-primary invite link created by the bot. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns the edited invite link as a ChatInviteLink object."""
        _payload = {
            "chat_id": chat_id,
            "invite_link": invite_link,
            "name": name,
            "expire_date": expire_date,
            "member_limit": member_limit,
            "creates_join_request": creates_join_request,
        }
        _result = self._request("editChatInviteLink", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'ChatInviteLink', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def create_chat_subscription_invite_link(self, chat_id: Union[int, str], subscription_period: int, subscription_price: int, name: Optional[str] = None) -> "ChatInviteLink":
        """Use this method to create a subscription invite link for a channel chat. The bot must have the can_invite_users administrator rights. The link can be edited using the method editChatSubscriptionInviteLink or revoked using the method revokeChatInviteLink . Returns the new invite link as a ChatInviteLink object."""
        _payload = {
            "chat_id": chat_id,
            "subscription_period": subscription_period,
            "subscription_price": subscription_price,
            "name": name,
        }
        _result = self._request("createChatSubscriptionInviteLink", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'ChatInviteLink', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def edit_chat_subscription_invite_link(self, chat_id: Union[int, str], invite_link: str, name: Optional[str] = None) -> "ChatInviteLink":
        """Use this method to edit a subscription invite link created by the bot. The bot must have the can_invite_users administrator rights. Returns the edited invite link as a ChatInviteLink object."""
        _payload = {
            "chat_id": chat_id,
            "invite_link": invite_link,
            "name": name,
        }
        _result = self._request("editChatSubscriptionInviteLink", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'ChatInviteLink', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def revoke_chat_invite_link(self, chat_id: Union[int, str], invite_link: str) -> "ChatInviteLink":
        """Use this method to revoke an invite link created by the bot. If the primary link is revoked, a new link is automatically generated. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns the revoked invite link as ChatInviteLink object."""
        _payload = {
            "chat_id": chat_id,
            "invite_link": invite_link,
        }
        _result = self._request("revokeChatInviteLink", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'ChatInviteLink', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def approve_chat_join_request(self, chat_id: Union[int, str], user_id: int) -> bool:
        """Use this method to approve a chat join request. The bot must be an administrator in the chat for this to work and must have the can_invite_users administrator right. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
        }
        _result = self._request("approveChatJoinRequest", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def decline_chat_join_request(self, chat_id: Union[int, str], user_id: int) -> bool:
        """Use this method to decline a chat join request. The bot must be an administrator in the chat for this to work and must have the can_invite_users administrator right. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
        }
        _result = self._request("declineChatJoinRequest", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_chat_photo(self, chat_id: Union[int, str], photo: Union[str, InputFile]) -> bool:
        """Use this method to set a new profile photo for the chat. Photos can't be changed for private chats. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "photo": photo,
        }
        _result = self._request("setChatPhoto", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def delete_chat_photo(self, chat_id: Union[int, str]) -> bool:
        """Use this method to delete a chat photo. Photos can't be changed for private chats. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = self._request("deleteChatPhoto", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_chat_title(self, chat_id: Union[int, str], title: str) -> bool:
        """Use this method to change the title of a chat. Titles can't be changed for private chats. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "title": title,
        }
        _result = self._request("setChatTitle", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_chat_description(self, chat_id: Union[int, str], description: Optional[str] = None) -> bool:
        """Use this method to change the description of a group, a supergroup or a channel. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "description": description,
        }
        _result = self._request("setChatDescription", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def pin_chat_message(self, chat_id: Union[int, str], message_id: int, business_connection_id: Optional[str] = None, disable_notification: Optional[bool] = None) -> bool:
        """Use this method to add a message to the list of pinned messages in a chat. In private chats and channel direct messages chats, all non-service messages can be pinned. Conversely, the bot must be an administrator with the 'can_pin_messages' right or the 'can_edit_messages' right to pin messages in groups and channels respectively. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "business_connection_id": business_connection_id,
            "disable_notification": disable_notification,
        }
        _result = self._request("pinChatMessage", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def unpin_chat_message(self, chat_id: Union[int, str], business_connection_id: Optional[str] = None, message_id: Optional[int] = None) -> bool:
        """Use this method to remove a message from the list of pinned messages in a chat. In private chats and channel direct messages chats, all messages can be unpinned. Conversely, the bot must be an administrator with the 'can_pin_messages' right or the 'can_edit_messages' right to unpin messages in groups and channels respectively. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "business_connection_id": business_connection_id,
            "message_id": message_id,
        }
        _result = self._request("unpinChatMessage", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def unpin_all_chat_messages(self, chat_id: Union[int, str]) -> bool:
        """Use this method to clear the list of pinned messages in a chat. In private chats and channel direct messages chats, no additional rights are required to unpin all pinned messages. Conversely, the bot must be an administrator with the 'can_pin_messages' right or the 'can_edit_messages' right to unpin all pinned messages in groups and channels respectively. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = self._request("unpinAllChatMessages", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def leave_chat(self, chat_id: Union[int, str]) -> bool:
        """Use this method for your bot to leave a group, supergroup or channel. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = self._request("leaveChat", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_chat(self, chat_id: Union[int, str]) -> "ChatFullInfo":
        """Use this method to get up-to-date information about the chat. Returns a ChatFullInfo object on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = self._request("getChat", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'ChatFullInfo', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_chat_administrators(self, chat_id: Union[int, str], return_bots: Optional[bool] = None) -> List["ChatMember"]:
        """Use this method to get a list of administrators in a chat. Returns an Array of ChatMember objects."""
        _payload = {
            "chat_id": chat_id,
            "return_bots": return_bots,
        }
        _result = self._request("getChatAdministrators", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'ChatMember', "list_depth": 1})


    def get_chat_member_count(self, chat_id: Union[int, str]) -> Any:
        """Use this method to get the number of members in a chat. Returns Int on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = self._request("getChatMemberCount", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_chat_member(self, chat_id: Union[int, str], user_id: int) -> "ChatMember":
        """Use this method to get information about a member of a chat. The method is only guaranteed to work for other users if the bot is an administrator in the chat. Returns a ChatMember object on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
        }
        _result = self._request("getChatMember", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'ChatMember', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_user_personal_chat_messages(self, user_id: int, limit: int) -> List["Message"]:
        """Use this method to get the last messages from the personal chat (i.e., the chat currently added to their profile) of a given user. On success, an array of Message objects is returned."""
        _payload = {
            "user_id": user_id,
            "limit": limit,
        }
        _result = self._request("getUserPersonalChatMessages", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'Message', "list_depth": 1})


    def set_chat_sticker_set(self, chat_id: Union[int, str], sticker_set_name: str) -> bool:
        """Use this method to set a new group sticker set for a supergroup. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Use the field can_set_sticker_set optionally returned in getChat requests to check if the bot can use this method. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "sticker_set_name": sticker_set_name,
        }
        _result = self._request("setChatStickerSet", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def delete_chat_sticker_set(self, chat_id: Union[int, str]) -> bool:
        """Use this method to delete a group sticker set from a supergroup. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Use the field can_set_sticker_set optionally returned in getChat requests to check if the bot can use this method. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = self._request("deleteChatStickerSet", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_forum_topic_icon_stickers(self) -> List["Sticker"]:
        """Use this method to get custom emoji stickers, which can be used as a forum topic icon by any user. Requires no parameters. Returns an Array of Sticker objects."""
        _payload = None
        _result = self._request("getForumTopicIconStickers", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'Sticker', "list_depth": 1})


    def create_forum_topic(self, chat_id: Union[int, str], name: str, icon_color: Optional[int] = None, icon_custom_emoji_id: Optional[str] = None) -> "ForumTopic":
        """Use this method to create a topic in a forum supergroup chat or a private chat with a user. In the case of a supergroup chat the bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator right. Returns information about the created topic as a ForumTopic object."""
        _payload = {
            "chat_id": chat_id,
            "name": name,
            "icon_color": icon_color,
            "icon_custom_emoji_id": icon_custom_emoji_id,
        }
        _result = self._request("createForumTopic", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'ForumTopic', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def edit_forum_topic(self, chat_id: Union[int, str], message_thread_id: int, name: Optional[str] = None, icon_custom_emoji_id: Optional[str] = None) -> bool:
        """Use this method to edit name and icon of a topic in a forum supergroup chat or a private chat with a user. In the case of a supergroup chat the bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights, unless it is the creator of the topic. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_thread_id": message_thread_id,
            "name": name,
            "icon_custom_emoji_id": icon_custom_emoji_id,
        }
        _result = self._request("editForumTopic", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def close_forum_topic(self, chat_id: Union[int, str], message_thread_id: int) -> bool:
        """Use this method to close an open topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights, unless it is the creator of the topic. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_thread_id": message_thread_id,
        }
        _result = self._request("closeForumTopic", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def reopen_forum_topic(self, chat_id: Union[int, str], message_thread_id: int) -> bool:
        """Use this method to reopen a closed topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights, unless it is the creator of the topic. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_thread_id": message_thread_id,
        }
        _result = self._request("reopenForumTopic", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def delete_forum_topic(self, chat_id: Union[int, str], message_thread_id: int) -> bool:
        """Use this method to delete a forum topic along with all its messages in a forum supergroup chat or a private chat with a user. In the case of a supergroup chat the bot must be an administrator in the chat for this to work and must have the can_delete_messages administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_thread_id": message_thread_id,
        }
        _result = self._request("deleteForumTopic", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def unpin_all_forum_topic_messages(self, chat_id: Union[int, str], message_thread_id: int) -> bool:
        """Use this method to clear the list of pinned messages in a forum topic in a forum supergroup chat or a private chat with a user. In the case of a supergroup chat the bot must be an administrator in the chat for this to work and must have the can_pin_messages administrator right in the supergroup. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_thread_id": message_thread_id,
        }
        _result = self._request("unpinAllForumTopicMessages", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def edit_general_forum_topic(self, chat_id: Union[int, str], name: str) -> bool:
        """Use this method to edit the name of the 'General' topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "name": name,
        }
        _result = self._request("editGeneralForumTopic", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def close_general_forum_topic(self, chat_id: Union[int, str]) -> bool:
        """Use this method to close an open 'General' topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = self._request("closeGeneralForumTopic", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def reopen_general_forum_topic(self, chat_id: Union[int, str]) -> bool:
        """Use this method to reopen a closed 'General' topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights. The topic will be automatically unhidden if it was hidden. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = self._request("reopenGeneralForumTopic", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def hide_general_forum_topic(self, chat_id: Union[int, str]) -> bool:
        """Use this method to hide the 'General' topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights. The topic will be automatically closed if it was open. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = self._request("hideGeneralForumTopic", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def unhide_general_forum_topic(self, chat_id: Union[int, str]) -> bool:
        """Use this method to unhide the 'General' topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = self._request("unhideGeneralForumTopic", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def unpin_all_general_forum_topic_messages(self, chat_id: Union[int, str]) -> bool:
        """Use this method to clear the list of pinned messages in a General forum topic. The bot must be an administrator in the chat for this to work and must have the can_pin_messages administrator right in the supergroup. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = self._request("unpinAllGeneralForumTopicMessages", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def answer_callback_query(self, callback_query_id: str, text: Optional[str] = None, show_alert: Optional[bool] = None, url: Optional[str] = None, cache_time: Optional[int] = None) -> bool:
        """Use this method to send answers to callback queries sent from inline keyboards . The answer will be displayed to the user as a notification at the top of the chat screen or as an alert. On success, True is returned."""
        _payload = {
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": show_alert,
            "url": url,
            "cache_time": cache_time,
        }
        _result = self._request("answerCallbackQuery", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def answer_guest_query(self, guest_query_id: str, result: "InlineQueryResult") -> bool:
        """Use this method to reply to a received guest message. On success, a SentGuestMessage object is returned."""
        _payload = {
            "guest_query_id": guest_query_id,
            "result": result,
        }
        _result = self._request("answerGuestQuery", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_user_chat_boosts(self, chat_id: Union[int, str], user_id: int) -> "UserChatBoosts":
        """Use this method to get the list of boosts added to a chat by a user. Requires administrator rights in the chat. Returns a UserChatBoosts object."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
        }
        _result = self._request("getUserChatBoosts", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'UserChatBoosts', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_business_connection(self, business_connection_id: str) -> "BusinessConnection":
        """Use this method to get information about the connection of the bot with a business account. Returns a BusinessConnection object on success."""
        _payload = {
            "business_connection_id": business_connection_id,
        }
        _result = self._request("getBusinessConnection", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'BusinessConnection', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_managed_bot_token(self, user_id: int) -> str:
        """Use this method to get the token of a managed bot. Returns the token as String on success."""
        _payload = {
            "user_id": user_id,
        }
        _result = self._request("getManagedBotToken", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def replace_managed_bot_token(self, user_id: int) -> str:
        """Use this method to revoke the current token of a managed bot and generate a new one. Returns the new token as String on success."""
        _payload = {
            "user_id": user_id,
        }
        _result = self._request("replaceManagedBotToken", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_managed_bot_access_settings(self, user_id: int) -> "BotAccessSettings":
        """Use this method to get the access settings of a managed bot. Returns a BotAccessSettings object on success."""
        _payload = {
            "user_id": user_id,
        }
        _result = self._request("getManagedBotAccessSettings", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'BotAccessSettings', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_managed_bot_access_settings(self, user_id: int, is_access_restricted: bool, added_user_ids: Optional[List[int]] = None) -> "BotAccessSettings":
        """Use this method to change the access settings of a managed bot. Returns True on success."""
        _payload = {
            "user_id": user_id,
            "is_access_restricted": is_access_restricted,
            "added_user_ids": added_user_ids,
        }
        _result = self._request("setManagedBotAccessSettings", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'BotAccessSettings', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_my_commands(self, commands: List["BotCommand"], scope: Optional["BotCommandScope"] = None, language_code: Optional[str] = None) -> bool:
        """Use this method to change the list of the bot's commands. See this manual for more details about bot commands. Returns True on success."""
        _payload = {
            "commands": commands,
            "scope": scope,
            "language_code": language_code,
        }
        _result = self._request("setMyCommands", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def delete_my_commands(self, scope: Optional["BotCommandScope"] = None, language_code: Optional[str] = None) -> bool:
        """Use this method to delete the list of the bot's commands for the given scope and user language. After deletion, higher level commands will be shown to affected users. Returns True on success."""
        _payload = {
            "scope": scope,
            "language_code": language_code,
        }
        _result = self._request("deleteMyCommands", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_my_commands(self, scope: Optional["BotCommandScope"] = None, language_code: Optional[str] = None) -> List["BotCommand"]:
        """Use this method to get the current list of the bot's commands for the given scope and user language. Returns an Array of BotCommand objects. If commands aren't set, an empty list is returned."""
        _payload = {
            "scope": scope,
            "language_code": language_code,
        }
        _result = self._request("getMyCommands", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'BotCommand', "list_depth": 1})


    def set_my_name(self, name: Optional[str] = None, language_code: Optional[str] = None) -> bool:
        """Use this method to change the bot's name. Returns True on success."""
        _payload = {
            "name": name,
            "language_code": language_code,
        }
        _result = self._request("setMyName", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_my_name(self, language_code: Optional[str] = None) -> "BotName":
        """Use this method to get the current bot name for the given user language. Returns BotName on success."""
        _payload = {
            "language_code": language_code,
        }
        _result = self._request("getMyName", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'BotName', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_my_description(self, description: Optional[str] = None, language_code: Optional[str] = None) -> bool:
        """Use this method to change the bot's description, which is shown in the chat with the bot if the chat is empty. Returns True on success."""
        _payload = {
            "description": description,
            "language_code": language_code,
        }
        _result = self._request("setMyDescription", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_my_description(self, language_code: Optional[str] = None) -> "BotDescription":
        """Use this method to get the current bot description for the given user language. Returns BotDescription on success."""
        _payload = {
            "language_code": language_code,
        }
        _result = self._request("getMyDescription", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'BotDescription', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_my_short_description(self, short_description: Optional[str] = None, language_code: Optional[str] = None) -> bool:
        """Use this method to change the bot's short description, which is shown on the bot's profile page and is sent together with the link when users share the bot. Returns True on success."""
        _payload = {
            "short_description": short_description,
            "language_code": language_code,
        }
        _result = self._request("setMyShortDescription", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_my_short_description(self, language_code: Optional[str] = None) -> "BotShortDescription":
        """Use this method to get the current bot short description for the given user language. Returns BotShortDescription on success."""
        _payload = {
            "language_code": language_code,
        }
        _result = self._request("getMyShortDescription", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'BotShortDescription', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_my_profile_photo(self, photo: "InputProfilePhoto") -> bool:
        """Changes the profile photo of the bot. Returns True on success."""
        _payload = {
            "photo": photo,
        }
        _result = self._request("setMyProfilePhoto", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def remove_my_profile_photo(self) -> bool:
        """Removes the profile photo of the bot. Requires no parameters. Returns True on success."""
        _payload = None
        _result = self._request("removeMyProfilePhoto", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_chat_menu_button(self, chat_id: Optional[int] = None, menu_button: Optional["MenuButton"] = None) -> bool:
        """Use this method to change the bot's menu button in a private chat, or the default menu button. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "menu_button": menu_button,
        }
        _result = self._request("setChatMenuButton", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_chat_menu_button(self, chat_id: Optional[int] = None) -> "MenuButton":
        """Use this method to get the current value of the bot's menu button in a private chat, or the default menu button. Returns MenuButton on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = self._request("getChatMenuButton", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'MenuButton', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_my_default_administrator_rights(self, rights: Optional["ChatAdministratorRights"] = None, for_channels: Optional[bool] = None) -> bool:
        """Use this method to change the default administrator rights requested by the bot when it's added as an administrator to groups or channels. These rights will be suggested to users, but they are free to modify the list before adding the bot. Returns True on success."""
        _payload = {
            "rights": rights,
            "for_channels": for_channels,
        }
        _result = self._request("setMyDefaultAdministratorRights", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_my_default_administrator_rights(self, for_channels: Optional[bool] = None) -> "ChatAdministratorRights":
        """Use this method to get the current default administrator rights of the bot. Returns ChatAdministratorRights on success."""
        _payload = {
            "for_channels": for_channels,
        }
        _result = self._request("getMyDefaultAdministratorRights", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'ChatAdministratorRights', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_available_gifts(self) -> "Gifts":
        """Returns the list of gifts that can be sent by the bot to users and channel chats. Requires no parameters. Returns a Gifts object."""
        _payload = None
        _result = self._request("getAvailableGifts", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Gifts', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_gift(self, gift_id: str, user_id: Optional[int] = None, chat_id: Optional[Union[int, str]] = None, pay_for_upgrade: Optional[bool] = None, text: Optional[str] = None, text_parse_mode: Optional[str] = None, text_entities: Optional[List["MessageEntity"]] = None) -> bool:
        """Sends a gift to the given user or channel chat. The gift can't be converted to Telegram Stars by the receiver. Returns True on success."""
        _payload = {
            "gift_id": gift_id,
            "user_id": user_id,
            "chat_id": chat_id,
            "pay_for_upgrade": pay_for_upgrade,
            "text": text,
            "text_parse_mode": text_parse_mode,
            "text_entities": text_entities,
        }
        _result = self._request("sendGift", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def gift_premium_subscription(self, user_id: int, month_count: int, star_count: int, text: Optional[str] = None, text_parse_mode: Optional[str] = None, text_entities: Optional[List["MessageEntity"]] = None) -> bool:
        """Gifts a Telegram Premium subscription to the given user. Returns True on success."""
        _payload = {
            "user_id": user_id,
            "month_count": month_count,
            "star_count": star_count,
            "text": text,
            "text_parse_mode": text_parse_mode,
            "text_entities": text_entities,
        }
        _result = self._request("giftPremiumSubscription", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def verify_user(self, user_id: int, custom_description: Optional[str] = None) -> bool:
        """Verifies a user on behalf of the organization which is represented by the bot. Returns True on success."""
        _payload = {
            "user_id": user_id,
            "custom_description": custom_description,
        }
        _result = self._request("verifyUser", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def verify_chat(self, chat_id: Union[int, str], custom_description: Optional[str] = None) -> bool:
        """Verifies a chat on behalf of the organization which is represented by the bot. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "custom_description": custom_description,
        }
        _result = self._request("verifyChat", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def remove_user_verification(self, user_id: int) -> bool:
        """Removes verification from a user who is currently verified on behalf of the organization represented by the bot. Returns True on success."""
        _payload = {
            "user_id": user_id,
        }
        _result = self._request("removeUserVerification", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def remove_chat_verification(self, chat_id: Union[int, str]) -> bool:
        """Removes verification from a chat that is currently verified on behalf of the organization represented by the bot. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = self._request("removeChatVerification", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def read_business_message(self, business_connection_id: str, chat_id: int, message_id: int) -> bool:
        """Marks incoming message as read on behalf of a business account. Requires the can_read_messages business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "chat_id": chat_id,
            "message_id": message_id,
        }
        _result = self._request("readBusinessMessage", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def delete_business_messages(self, business_connection_id: str, message_ids: List[int]) -> bool:
        """Delete messages on behalf of a business account. Requires the can_delete_sent_messages business bot right to delete messages sent by the bot itself, or the can_delete_all_messages business bot right to delete any message. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "message_ids": message_ids,
        }
        _result = self._request("deleteBusinessMessages", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_business_account_name(self, business_connection_id: str, first_name: str, last_name: Optional[str] = None) -> bool:
        """Changes the first and last name of a managed business account. Requires the can_change_name business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "first_name": first_name,
            "last_name": last_name,
        }
        _result = self._request("setBusinessAccountName", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_business_account_username(self, business_connection_id: str, username: Optional[str] = None) -> bool:
        """Changes the username of a managed business account. Requires the can_change_username business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "username": username,
        }
        _result = self._request("setBusinessAccountUsername", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_business_account_bio(self, business_connection_id: str, bio: Optional[str] = None) -> bool:
        """Changes the bio of a managed business account. Requires the can_change_bio business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "bio": bio,
        }
        _result = self._request("setBusinessAccountBio", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_business_account_profile_photo(self, business_connection_id: str, photo: "InputProfilePhoto", is_public: Optional[bool] = None) -> bool:
        """Changes the profile photo of a managed business account. Requires the can_edit_profile_photo business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "photo": photo,
            "is_public": is_public,
        }
        _result = self._request("setBusinessAccountProfilePhoto", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def remove_business_account_profile_photo(self, business_connection_id: str, is_public: Optional[bool] = None) -> bool:
        """Removes the current profile photo of a managed business account. Requires the can_edit_profile_photo business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "is_public": is_public,
        }
        _result = self._request("removeBusinessAccountProfilePhoto", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_business_account_gift_settings(self, business_connection_id: str, show_gift_button: bool, accepted_gift_types: "AcceptedGiftTypes") -> bool:
        """Changes the privacy settings pertaining to incoming gifts in a managed business account. Requires the can_change_gift_settings business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "show_gift_button": show_gift_button,
            "accepted_gift_types": accepted_gift_types,
        }
        _result = self._request("setBusinessAccountGiftSettings", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_business_account_star_balance(self, business_connection_id: str) -> "StarAmount":
        """Returns the amount of Telegram Stars owned by a managed business account. Requires the can_view_gifts_and_stars business bot right. Returns StarAmount on success."""
        _payload = {
            "business_connection_id": business_connection_id,
        }
        _result = self._request("getBusinessAccountStarBalance", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'StarAmount', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def transfer_business_account_stars(self, business_connection_id: str, star_count: int) -> bool:
        """Transfers Telegram Stars from the business account balance to the bot's balance. Requires the can_transfer_stars business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "star_count": star_count,
        }
        _result = self._request("transferBusinessAccountStars", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_business_account_gifts(self, business_connection_id: str, exclude_unsaved: Optional[bool] = None, exclude_saved: Optional[bool] = None, exclude_unlimited: Optional[bool] = None, exclude_limited_upgradable: Optional[bool] = None, exclude_limited_non_upgradable: Optional[bool] = None, exclude_unique: Optional[bool] = None, exclude_from_blockchain: Optional[bool] = None, sort_by_price: Optional[bool] = None, offset: Optional[str] = None, limit: Optional[int] = None) -> "OwnedGifts":
        """Returns the gifts received and owned by a managed business account. Requires the can_view_gifts_and_stars business bot right. Returns OwnedGifts on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "exclude_unsaved": exclude_unsaved,
            "exclude_saved": exclude_saved,
            "exclude_unlimited": exclude_unlimited,
            "exclude_limited_upgradable": exclude_limited_upgradable,
            "exclude_limited_non_upgradable": exclude_limited_non_upgradable,
            "exclude_unique": exclude_unique,
            "exclude_from_blockchain": exclude_from_blockchain,
            "sort_by_price": sort_by_price,
            "offset": offset,
            "limit": limit,
        }
        _result = self._request("getBusinessAccountGifts", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'OwnedGifts', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_user_gifts(self, user_id: int, exclude_unlimited: Optional[bool] = None, exclude_limited_upgradable: Optional[bool] = None, exclude_limited_non_upgradable: Optional[bool] = None, exclude_from_blockchain: Optional[bool] = None, exclude_unique: Optional[bool] = None, sort_by_price: Optional[bool] = None, offset: Optional[str] = None, limit: Optional[int] = None) -> "OwnedGifts":
        """Returns the gifts owned and hosted by a user. Returns OwnedGifts on success."""
        _payload = {
            "user_id": user_id,
            "exclude_unlimited": exclude_unlimited,
            "exclude_limited_upgradable": exclude_limited_upgradable,
            "exclude_limited_non_upgradable": exclude_limited_non_upgradable,
            "exclude_from_blockchain": exclude_from_blockchain,
            "exclude_unique": exclude_unique,
            "sort_by_price": sort_by_price,
            "offset": offset,
            "limit": limit,
        }
        _result = self._request("getUserGifts", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'OwnedGifts', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_chat_gifts(self, chat_id: Union[int, str], exclude_unsaved: Optional[bool] = None, exclude_saved: Optional[bool] = None, exclude_unlimited: Optional[bool] = None, exclude_limited_upgradable: Optional[bool] = None, exclude_limited_non_upgradable: Optional[bool] = None, exclude_from_blockchain: Optional[bool] = None, exclude_unique: Optional[bool] = None, sort_by_price: Optional[bool] = None, offset: Optional[str] = None, limit: Optional[int] = None) -> "OwnedGifts":
        """Returns the gifts owned by a chat. Returns OwnedGifts on success."""
        _payload = {
            "chat_id": chat_id,
            "exclude_unsaved": exclude_unsaved,
            "exclude_saved": exclude_saved,
            "exclude_unlimited": exclude_unlimited,
            "exclude_limited_upgradable": exclude_limited_upgradable,
            "exclude_limited_non_upgradable": exclude_limited_non_upgradable,
            "exclude_from_blockchain": exclude_from_blockchain,
            "exclude_unique": exclude_unique,
            "sort_by_price": sort_by_price,
            "offset": offset,
            "limit": limit,
        }
        _result = self._request("getChatGifts", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'OwnedGifts', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def convert_gift_to_stars(self, business_connection_id: str, owned_gift_id: str) -> bool:
        """Converts a given regular gift to Telegram Stars. Requires the can_convert_gifts_to_stars business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "owned_gift_id": owned_gift_id,
        }
        _result = self._request("convertGiftToStars", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def upgrade_gift(self, business_connection_id: str, owned_gift_id: str, keep_original_details: Optional[bool] = None, star_count: Optional[int] = None) -> bool:
        """Upgrades a given regular gift to a unique gift. Requires the can_transfer_and_upgrade_gifts business bot right. Additionally requires the can_transfer_stars business bot right if the upgrade is paid. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "owned_gift_id": owned_gift_id,
            "keep_original_details": keep_original_details,
            "star_count": star_count,
        }
        _result = self._request("upgradeGift", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def transfer_gift(self, business_connection_id: str, owned_gift_id: str, new_owner_chat_id: int, star_count: Optional[int] = None) -> bool:
        """Transfers an owned unique gift to another user. Requires the can_transfer_and_upgrade_gifts business bot right. Requires can_transfer_stars business bot right if the transfer is paid. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "owned_gift_id": owned_gift_id,
            "new_owner_chat_id": new_owner_chat_id,
            "star_count": star_count,
        }
        _result = self._request("transferGift", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def post_story(self, business_connection_id: str, content: "InputStoryContent", active_period: int, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, areas: Optional[List["StoryArea"]] = None, post_to_chat_page: Optional[bool] = None, protect_content: Optional[bool] = None) -> "Story":
        """Posts a story on behalf of a managed business account. Requires the can_manage_stories business bot right. Returns Story on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "content": content,
            "active_period": active_period,
            "caption": caption,
            "parse_mode": parse_mode,
            "caption_entities": caption_entities,
            "areas": areas,
            "post_to_chat_page": post_to_chat_page,
            "protect_content": protect_content,
        }
        _result = self._request("postStory", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Story', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def repost_story(self, business_connection_id: str, from_chat_id: int, from_story_id: int, active_period: int, post_to_chat_page: Optional[bool] = None, protect_content: Optional[bool] = None) -> "Story":
        """Reposts a story on behalf of a business account from another business account. Both business accounts must be managed by the same bot, and the story on the source account must have been posted (or reposted) by the bot. Requires the can_manage_stories business bot right for both business accounts. Returns Story on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "from_chat_id": from_chat_id,
            "from_story_id": from_story_id,
            "active_period": active_period,
            "post_to_chat_page": post_to_chat_page,
            "protect_content": protect_content,
        }
        _result = self._request("repostStory", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Story', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def edit_story(self, business_connection_id: str, story_id: int, content: "InputStoryContent", caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, areas: Optional[List["StoryArea"]] = None) -> "Story":
        """Edits a story previously posted by the bot on behalf of a managed business account. Requires the can_manage_stories business bot right. Returns Story on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "story_id": story_id,
            "content": content,
            "caption": caption,
            "parse_mode": parse_mode,
            "caption_entities": caption_entities,
            "areas": areas,
        }
        _result = self._request("editStory", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Story', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def delete_story(self, business_connection_id: str, story_id: int) -> bool:
        """Deletes a story previously posted by the bot on behalf of a managed business account. Requires the can_manage_stories business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "story_id": story_id,
        }
        _result = self._request("deleteStory", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def answer_web_app_query(self, web_app_query_id: str, result: "InlineQueryResult") -> "SentWebAppMessage":
        """Use this method to set the result of an interaction with a Web App and send a corresponding message on behalf of the user to the chat from which the query originated. On success, a SentWebAppMessage object is returned."""
        _payload = {
            "web_app_query_id": web_app_query_id,
            "result": result,
        }
        _result = self._request("answerWebAppQuery", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'SentWebAppMessage', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def save_prepared_inline_message(self, user_id: int, result: "InlineQueryResult", allow_user_chats: Optional[bool] = None, allow_bot_chats: Optional[bool] = None, allow_group_chats: Optional[bool] = None, allow_channel_chats: Optional[bool] = None) -> "PreparedInlineMessage":
        """Stores a message that can be sent by a user of a Mini App. Returns a PreparedInlineMessage object."""
        _payload = {
            "user_id": user_id,
            "result": result,
            "allow_user_chats": allow_user_chats,
            "allow_bot_chats": allow_bot_chats,
            "allow_group_chats": allow_group_chats,
            "allow_channel_chats": allow_channel_chats,
        }
        _result = self._request("savePreparedInlineMessage", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'PreparedInlineMessage', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def save_prepared_keyboard_button(self, user_id: int, button: "KeyboardButton") -> "PreparedKeyboardButton":
        """Stores a keyboard button that can be used by a user within a Mini App. Returns a PreparedKeyboardButton object."""
        _payload = {
            "user_id": user_id,
            "button": button,
        }
        _result = self._request("savePreparedKeyboardButton", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'PreparedKeyboardButton', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def edit_message_text(self, text: str, business_connection_id: Optional[str] = None, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None, parse_mode: Optional[str] = None, entities: Optional[List["MessageEntity"]] = None, link_preview_options: Optional["LinkPreviewOptions"] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Message":
        """Use this method to edit text and game messages. On success, if the edited message is not an inline message, the edited Message is returned, otherwise True is returned. Note that business messages that were not sent by the bot and do not contain an inline keyboard can only be edited within 48 hours from the time they were sent."""
        _payload = {
            "text": text,
            "business_connection_id": business_connection_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "inline_message_id": inline_message_id,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "entities": entities,
            "link_preview_options": link_preview_options,
            "reply_markup": reply_markup,
        }
        _result = self._request("editMessageText", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def edit_message_caption(self, business_connection_id: Optional[str] = None, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Message":
        """Use this method to edit captions of messages. On success, if the edited message is not an inline message, the edited Message is returned, otherwise True is returned. Note that business messages that were not sent by the bot and do not contain an inline keyboard can only be edited within 48 hours from the time they were sent."""
        _payload = {
            "business_connection_id": business_connection_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "inline_message_id": inline_message_id,
            "caption": caption,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "caption_entities": caption_entities,
            "show_caption_above_media": show_caption_above_media,
            "reply_markup": reply_markup,
        }
        _result = self._request("editMessageCaption", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def edit_message_media(self, media: "InputMedia", business_connection_id: Optional[str] = None, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Message":
        """Use this method to edit animation, audio, document, live photo, photo, or video messages, or to add media to text messages. If a message is part of a message album, then it can be edited only to an audio for audio albums, only to a document for document albums and to a photo, a live photo, or a video otherwise. When an inline message is edited, a new file can't be uploaded; use a previously uploaded file via its file_id or specify a URL. On success, if the edited message is not an inline message, the edited Message is returned, otherwise True is returned. Note that business messages that were not sent by the bot and do not contain an inline keyboard can only be edited within 48 hours from the time they were sent."""
        _payload = {
            "media": media,
            "business_connection_id": business_connection_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "inline_message_id": inline_message_id,
            "reply_markup": reply_markup,
        }
        _result = self._request("editMessageMedia", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def edit_message_live_location(self, latitude: float, longitude: float, business_connection_id: Optional[str] = None, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None, live_period: Optional[int] = None, horizontal_accuracy: Optional[float] = None, heading: Optional[int] = None, proximity_alert_radius: Optional[int] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Message":
        """Use this method to edit live location messages. A location can be edited until its live_period expires or editing is explicitly disabled by a call to stopMessageLiveLocation . On success, if the edited message is not an inline message, the edited Message is returned, otherwise True is returned."""
        _payload = {
            "latitude": latitude,
            "longitude": longitude,
            "business_connection_id": business_connection_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "inline_message_id": inline_message_id,
            "live_period": live_period,
            "horizontal_accuracy": horizontal_accuracy,
            "heading": heading,
            "proximity_alert_radius": proximity_alert_radius,
            "reply_markup": reply_markup,
        }
        _result = self._request("editMessageLiveLocation", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def stop_message_live_location(self, business_connection_id: Optional[str] = None, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> bool:
        """Use this method to stop updating a live location message before live_period expires. On success, if the message is not an inline message, the edited Message is returned, otherwise True is returned."""
        _payload = {
            "business_connection_id": business_connection_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "inline_message_id": inline_message_id,
            "reply_markup": reply_markup,
        }
        _result = self._request("stopMessageLiveLocation", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def edit_message_checklist(self, business_connection_id: str, chat_id: Union[int, str], message_id: int, checklist: "InputChecklist", reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Message":
        """Use this method to edit a checklist on behalf of a connected business account. On success, the edited Message is returned."""
        _payload = {
            "business_connection_id": business_connection_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "checklist": checklist,
            "reply_markup": reply_markup,
        }
        _result = self._request("editMessageChecklist", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def edit_message_reply_markup(self, business_connection_id: Optional[str] = None, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Message":
        """Use this method to edit only the reply markup of messages. On success, if the edited message is not an inline message, the edited Message is returned, otherwise True is returned. Note that business messages that were not sent by the bot and do not contain an inline keyboard can only be edited within 48 hours from the time they were sent."""
        _payload = {
            "business_connection_id": business_connection_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "inline_message_id": inline_message_id,
            "reply_markup": reply_markup,
        }
        _result = self._request("editMessageReplyMarkup", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def stop_poll(self, chat_id: Union[int, str], message_id: int, business_connection_id: Optional[str] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Poll":
        """Use this method to stop a poll which was sent by the bot. On success, the stopped Poll is returned."""
        _payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "business_connection_id": business_connection_id,
            "reply_markup": reply_markup,
        }
        _result = self._request("stopPoll", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Poll', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def approve_suggested_post(self, chat_id: int, message_id: int, send_date: Optional[int] = None) -> "Message":
        """Use this method to approve a suggested post in a direct messages chat. The bot must have the 'can_post_messages' administrator right in the corresponding channel chat. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "send_date": send_date,
        }
        _result = self._request("approveSuggestedPost", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def decline_suggested_post(self, chat_id: int, message_id: int, comment: Optional[str] = None) -> bool:
        """Use this method to decline a suggested post in a direct messages chat. The bot must have the 'can_manage_direct_messages' administrator right in the corresponding channel chat. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "comment": comment,
        }
        _result = self._request("declineSuggestedPost", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def delete_message(self, chat_id: Union[int, str], message_id: int) -> bool:
        """Use this method to delete a message, including service messages, with the following limitations: - A message can only be deleted if it was sent less than 48 hours ago. - Service messages about a supergroup, channel, or forum topic creation can't be deleted. - A dice message in a private chat can only be deleted if it was sent more than 24 hours ago. - Bots can delete outgoing messages in private chats, groups, and supergroups. - Bots can delete incoming messages in private chats. - Bots granted can_post_messages permissions can delete outgoing messages in channels. - If the bot is an administrator of a group, it can delete any message there. - If the bot has can_delete_messages administrator right in a supergroup or a channel, it can delete any message there. - If the bot has can_manage_direct_messages administrator right in a channel, it can delete any message in the corresponding direct messages chat. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_id": message_id,
        }
        _result = self._request("deleteMessage", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def delete_messages(self, chat_id: Union[int, str], message_ids: List[int]) -> bool:
        """Use this method to delete multiple messages simultaneously. If some of the specified messages can't be found, they are skipped. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_ids": message_ids,
        }
        _result = self._request("deleteMessages", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def delete_message_reaction(self, chat_id: Union[int, str], message_id: int, user_id: Optional[int] = None, actor_chat_id: Optional[int] = None) -> bool:
        """Use this method to remove a reaction from a message in a group or a supergroup chat. The bot must have the 'can_delete_messages' administrator right in the chat. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "user_id": user_id,
            "actor_chat_id": actor_chat_id,
        }
        _result = self._request("deleteMessageReaction", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def delete_all_message_reactions(self, chat_id: Union[int, str], user_id: Optional[int] = None, actor_chat_id: Optional[int] = None) -> bool:
        """Use this method to remove up to 10000 recent reactions in a group or a supergroup chat added by a given user or chat. The bot must have the 'can_delete_messages' administrator right in the chat. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
            "actor_chat_id": actor_chat_id,
        }
        _result = self._request("deleteAllMessageReactions", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_sticker(self, chat_id: Union[int, str], sticker: Union[Union[str, InputFile], str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, emoji: Optional[str] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send static .WEBP, animated .TGS, or video .WEBM stickers. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "sticker": sticker,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "emoji": emoji,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("sendSticker", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_sticker_set(self, name: str) -> "StickerSet":
        """Use this method to get a sticker set. On success, a StickerSet object is returned."""
        _payload = {
            "name": name,
        }
        _result = self._request("getStickerSet", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'StickerSet', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_custom_emoji_stickers(self, custom_emoji_ids: List[str]) -> List["Sticker"]:
        """Use this method to get information about custom emoji stickers by their identifiers. Returns an Array of Sticker objects."""
        _payload = {
            "custom_emoji_ids": custom_emoji_ids,
        }
        _result = self._request("getCustomEmojiStickers", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'Sticker', "list_depth": 1})


    def upload_sticker_file(self, user_id: int, sticker: Union[str, InputFile], sticker_format: str) -> "File":
        """Use this method to upload a file with a sticker for later use in the createNewStickerSet , addStickerToSet , or replaceStickerInSet methods (the file can be used multiple times). Returns the uploaded File on success."""
        _payload = {
            "user_id": user_id,
            "sticker": sticker,
            "sticker_format": sticker_format,
        }
        _result = self._request("uploadStickerFile", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'File', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def create_new_sticker_set(self, user_id: int, name: str, title: str, stickers: List["InputSticker"], sticker_type: Optional[str] = None, needs_repainting: Optional[bool] = None) -> bool:
        """Use this method to create a new sticker set owned by a user. The bot will be able to edit the sticker set thus created. Returns True on success."""
        _payload = {
            "user_id": user_id,
            "name": name,
            "title": title,
            "stickers": stickers,
            "sticker_type": sticker_type,
            "needs_repainting": needs_repainting,
        }
        _result = self._request("createNewStickerSet", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def add_sticker_to_set(self, user_id: int, name: str, sticker: "InputSticker") -> bool:
        """Use this method to add a new sticker to a set created by the bot. Emoji sticker sets can have up to 200 stickers. Other sticker sets can have up to 120 stickers. Returns True on success."""
        _payload = {
            "user_id": user_id,
            "name": name,
            "sticker": sticker,
        }
        _result = self._request("addStickerToSet", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_sticker_position_in_set(self, sticker: str, position: int) -> bool:
        """Use this method to move a sticker in a set created by the bot to a specific position. Returns True on success."""
        _payload = {
            "sticker": sticker,
            "position": position,
        }
        _result = self._request("setStickerPositionInSet", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def delete_sticker_from_set(self, sticker: str) -> bool:
        """Use this method to delete a sticker from a set created by the bot. Returns True on success."""
        _payload = {
            "sticker": sticker,
        }
        _result = self._request("deleteStickerFromSet", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def replace_sticker_in_set(self, user_id: int, name: str, old_sticker: str, sticker: "InputSticker") -> bool:
        """Use this method to replace an existing sticker in a sticker set with a new one. The method is equivalent to calling deleteStickerFromSet , then addStickerToSet , then setStickerPositionInSet . Returns True on success."""
        _payload = {
            "user_id": user_id,
            "name": name,
            "old_sticker": old_sticker,
            "sticker": sticker,
        }
        _result = self._request("replaceStickerInSet", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_sticker_emoji_list(self, sticker: str, emoji_list: List[str]) -> bool:
        """Use this method to change the list of emoji assigned to a regular or custom emoji sticker. The sticker must belong to a sticker set created by the bot. Returns True on success."""
        _payload = {
            "sticker": sticker,
            "emoji_list": emoji_list,
        }
        _result = self._request("setStickerEmojiList", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_sticker_keywords(self, sticker: str, keywords: Optional[List[str]] = None) -> bool:
        """Use this method to change search keywords assigned to a regular or custom emoji sticker. The sticker must belong to a sticker set created by the bot. Returns True on success."""
        _payload = {
            "sticker": sticker,
            "keywords": keywords,
        }
        _result = self._request("setStickerKeywords", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_sticker_mask_position(self, sticker: str, mask_position: Optional["MaskPosition"] = None) -> bool:
        """Use this method to change the mask position of a mask sticker. The sticker must belong to a sticker set that was created by the bot. Returns True on success."""
        _payload = {
            "sticker": sticker,
            "mask_position": mask_position,
        }
        _result = self._request("setStickerMaskPosition", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_sticker_set_title(self, name: str, title: str) -> bool:
        """Use this method to set the title of a created sticker set. Returns True on success."""
        _payload = {
            "name": name,
            "title": title,
        }
        _result = self._request("setStickerSetTitle", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_sticker_set_thumbnail(self, name: str, user_id: int, format: str, thumbnail: Optional[Union[Union[str, InputFile], str]] = None) -> bool:
        """Use this method to set the thumbnail of a regular or mask sticker set. The format of the thumbnail file must match the format of the stickers in the set. Returns True on success."""
        _payload = {
            "name": name,
            "user_id": user_id,
            "format": format,
            "thumbnail": thumbnail,
        }
        _result = self._request("setStickerSetThumbnail", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_custom_emoji_sticker_set_thumbnail(self, name: str, custom_emoji_id: Optional[str] = None) -> bool:
        """Use this method to set the thumbnail of a custom emoji sticker set. Returns True on success."""
        _payload = {
            "name": name,
            "custom_emoji_id": custom_emoji_id,
        }
        _result = self._request("setCustomEmojiStickerSetThumbnail", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def delete_sticker_set(self, name: str) -> bool:
        """Use this method to delete a sticker set that was created by the bot. Returns True on success."""
        _payload = {
            "name": name,
        }
        _result = self._request("deleteStickerSet", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def answer_inline_query(self, inline_query_id: str, results: List["InlineQueryResult"], cache_time: Optional[int] = None, is_personal: Optional[bool] = None, next_offset: Optional[str] = None, button: Optional["InlineQueryResultsButton"] = None) -> bool:
        """Use this method to send answers to an inline query. On success, True is returned. No more than 50 results per query are allowed."""
        _payload = {
            "inline_query_id": inline_query_id,
            "results": results,
            "cache_time": cache_time,
            "is_personal": is_personal,
            "next_offset": next_offset,
            "button": button,
        }
        _result = self._request("answerInlineQuery", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_invoice(self, chat_id: Union[int, str], title: str, description: str, payload: str, currency: str, prices: List["LabeledPrice"], message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, provider_token: Optional[str] = None, max_tip_amount: Optional[int] = None, suggested_tip_amounts: Optional[List[int]] = None, start_parameter: Optional[str] = None, provider_data: Optional[str] = None, photo_url: Optional[str] = None, photo_size: Optional[int] = None, photo_width: Optional[int] = None, photo_height: Optional[int] = None, need_name: Optional[bool] = None, need_phone_number: Optional[bool] = None, need_email: Optional[bool] = None, need_shipping_address: Optional[bool] = None, send_phone_number_to_provider: Optional[bool] = None, send_email_to_provider: Optional[bool] = None, is_flexible: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Message":
        """Use this method to send invoices. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "title": title,
            "description": description,
            "payload": payload,
            "currency": currency,
            "prices": prices,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "provider_token": provider_token,
            "max_tip_amount": max_tip_amount,
            "suggested_tip_amounts": suggested_tip_amounts,
            "start_parameter": start_parameter,
            "provider_data": provider_data,
            "photo_url": photo_url,
            "photo_size": photo_size,
            "photo_width": photo_width,
            "photo_height": photo_height,
            "need_name": need_name,
            "need_phone_number": need_phone_number,
            "need_email": need_email,
            "need_shipping_address": need_shipping_address,
            "send_phone_number_to_provider": send_phone_number_to_provider,
            "send_email_to_provider": send_email_to_provider,
            "is_flexible": is_flexible,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("sendInvoice", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def create_invoice_link(self, title: str, description: str, payload: str, currency: str, prices: List["LabeledPrice"], business_connection_id: Optional[str] = None, provider_token: Optional[str] = None, subscription_period: Optional[int] = None, max_tip_amount: Optional[int] = None, suggested_tip_amounts: Optional[List[int]] = None, provider_data: Optional[str] = None, photo_url: Optional[str] = None, photo_size: Optional[int] = None, photo_width: Optional[int] = None, photo_height: Optional[int] = None, need_name: Optional[bool] = None, need_phone_number: Optional[bool] = None, need_email: Optional[bool] = None, need_shipping_address: Optional[bool] = None, send_phone_number_to_provider: Optional[bool] = None, send_email_to_provider: Optional[bool] = None, is_flexible: Optional[bool] = None) -> str:
        """Use this method to create a link for an invoice. Returns the created invoice link as String on success."""
        _payload = {
            "title": title,
            "description": description,
            "payload": payload,
            "currency": currency,
            "prices": prices,
            "business_connection_id": business_connection_id,
            "provider_token": provider_token,
            "subscription_period": subscription_period,
            "max_tip_amount": max_tip_amount,
            "suggested_tip_amounts": suggested_tip_amounts,
            "provider_data": provider_data,
            "photo_url": photo_url,
            "photo_size": photo_size,
            "photo_width": photo_width,
            "photo_height": photo_height,
            "need_name": need_name,
            "need_phone_number": need_phone_number,
            "need_email": need_email,
            "need_shipping_address": need_shipping_address,
            "send_phone_number_to_provider": send_phone_number_to_provider,
            "send_email_to_provider": send_email_to_provider,
            "is_flexible": is_flexible,
        }
        _result = self._request("createInvoiceLink", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def answer_shipping_query(self, shipping_query_id: str, ok: bool, shipping_options: Optional[List["ShippingOption"]] = None, error_message: Optional[str] = None) -> bool:
        """If you sent an invoice requesting a shipping address and the parameter is_flexible was specified, the Bot API will send an Update with a shipping_query field to the bot. Use this method to reply to shipping queries. On success, True is returned."""
        _payload = {
            "shipping_query_id": shipping_query_id,
            "ok": ok,
            "shipping_options": shipping_options,
            "error_message": error_message,
        }
        _result = self._request("answerShippingQuery", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def answer_pre_checkout_query(self, pre_checkout_query_id: str, ok: bool, error_message: Optional[str] = None) -> bool:
        """Once the user has confirmed their payment and shipping details, the Bot API sends the final confirmation in the form of an Update with the field pre_checkout_query . Use this method to respond to such pre-checkout queries. On success, True is returned. Note: The Bot API must receive an answer within 10 seconds after the pre-checkout query was sent."""
        _payload = {
            "pre_checkout_query_id": pre_checkout_query_id,
            "ok": ok,
            "error_message": error_message,
        }
        _result = self._request("answerPreCheckoutQuery", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_my_star_balance(self) -> "StarAmount":
        """A method to get the current Telegram Stars balance of the bot. Requires no parameters. On success, returns a StarAmount object."""
        _payload = None
        _result = self._request("getMyStarBalance", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'StarAmount', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_star_transactions(self, offset: Optional[int] = None, limit: Optional[int] = None) -> "StarTransactions":
        """Returns the bot's Telegram Star transactions in chronological order. On success, returns a StarTransactions object."""
        _payload = {
            "offset": offset,
            "limit": limit,
        }
        _result = self._request("getStarTransactions", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'StarTransactions', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def refund_star_payment(self, user_id: int, telegram_payment_charge_id: str) -> bool:
        """Refunds a successful payment in Telegram Stars . Returns True on success."""
        _payload = {
            "user_id": user_id,
            "telegram_payment_charge_id": telegram_payment_charge_id,
        }
        _result = self._request("refundStarPayment", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def edit_user_star_subscription(self, user_id: int, telegram_payment_charge_id: str, is_canceled: bool) -> bool:
        """Allows the bot to cancel or re-enable extension of a subscription paid in Telegram Stars. Returns True on success."""
        _payload = {
            "user_id": user_id,
            "telegram_payment_charge_id": telegram_payment_charge_id,
            "is_canceled": is_canceled,
        }
        _result = self._request("editUserStarSubscription", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_passport_data_errors(self, user_id: int, errors: List["PassportElementError"]) -> bool:
        """Informs a user that some of the Telegram Passport elements they provided contains errors. The user will not be able to re-submit their Passport to you until the errors are fixed (the contents of the field for which you returned the error must change). Returns True on success."""
        _payload = {
            "user_id": user_id,
            "errors": errors,
        }
        _result = self._request("setPassportDataErrors", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    def send_game(self, chat_id: Union[int, str], game_short_name: str, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Message":
        """Use this method to send a game. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "game_short_name": game_short_name,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = self._request("sendGame", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def set_game_score(self, user_id: int, score: int, force: Optional[bool] = None, disable_edit_message: Optional[bool] = None, chat_id: Optional[int] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None) -> "Message":
        """Use this method to set the score of the specified user in a game message. On success, if the message is not an inline message, the Message is returned, otherwise True is returned. Returns an error, if the new score is not greater than the user's current score in the chat and force is False ."""
        _payload = {
            "user_id": user_id,
            "score": score,
            "force": force,
            "disable_edit_message": disable_edit_message,
            "chat_id": chat_id,
            "message_id": message_id,
            "inline_message_id": inline_message_id,
        }
        _result = self._request("setGameScore", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    def get_game_high_scores(self, user_id: int, chat_id: Optional[int] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None) -> List["GameHighScore"]:
        """Use this method to get data for high score tables. Will return the score of the specified user and several of their neighbors in a game. Returns an Array of GameHighScore objects."""
        _payload = {
            "user_id": user_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "inline_message_id": inline_message_id,
        }
        _result = self._request("getGameHighScores", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'GameHighScore', "list_depth": 1})


for _name in dir(_BotMethods):
    if _name.startswith('_'): continue
    setattr(Bot, _name, getattr(_BotMethods, _name))
del _name

# ── Bot API methods (async) ───────────────────────────────────────────────────

class _AsyncBotMethods:
    async def get_updates(self, offset: Optional[int] = None, limit: Optional[int] = None, timeout: Optional[int] = None, allowed_updates: Optional[List[str]] = None) -> List["Update"]:
        """Use this method to receive incoming updates using long polling ( wiki ). Returns an Array of Update objects."""
        _payload = {
            "offset": offset,
            "limit": limit,
            "timeout": timeout,
            "allowed_updates": allowed_updates,
        }
        _result = await self._arequest("getUpdates", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'Update', "list_depth": 1})


    async def set_webhook(self, url: str, certificate: Optional[Union[str, InputFile]] = None, ip_address: Optional[str] = None, max_connections: Optional[int] = None, allowed_updates: Optional[List[str]] = None, drop_pending_updates: Optional[bool] = None, secret_token: Optional[str] = None) -> bool:
        """Use this method to specify a URL and receive incoming updates via an outgoing webhook. Whenever there is an update for the bot, we will send an HTTPS POST request to the specified URL, containing a JSON-serialized Update . In case of an unsuccessful request (a request with response HTTP status code different from 2XY ), we will repeat the request and give up after a reasonable amount of attempts. Returns True on success."""
        _payload = {
            "url": url,
            "certificate": certificate,
            "ip_address": ip_address,
            "max_connections": max_connections,
            "allowed_updates": allowed_updates,
            "drop_pending_updates": drop_pending_updates,
            "secret_token": secret_token,
        }
        _result = await self._arequest("setWebhook", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def delete_webhook(self, drop_pending_updates: Optional[bool] = None) -> bool:
        """Use this method to remove webhook integration if you decide to switch back to getUpdates . Returns True on success."""
        _payload = {
            "drop_pending_updates": drop_pending_updates,
        }
        _result = await self._arequest("deleteWebhook", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_webhook_info(self) -> "WebhookInfo":
        """Use this method to get current webhook status. Requires no parameters. On success, returns a WebhookInfo object. If the bot is using getUpdates , will return an object with the url field empty."""
        _payload = None
        _result = await self._arequest("getWebhookInfo", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'WebhookInfo', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_me(self) -> "User":
        """A simple method for testing your bot's authentication token. Requires no parameters. Returns basic information about the bot in form of a User object."""
        _payload = None
        _result = await self._arequest("getMe", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'User', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def log_out(self) -> bool:
        """Use this method to log out from the cloud Bot API server before launching the bot locally. You must log out the bot before running it locally, otherwise there is no guarantee that the bot will receive updates. After a successful call, you can immediately log in on a local server, but will not be able to log in back to the cloud Bot API server for 10 minutes. Returns True on success. Requires no parameters."""
        _payload = None
        _result = await self._arequest("logOut", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def close(self) -> bool:
        """Use this method to close the bot instance before moving it from one local server to another. You need to delete the webhook before calling this method to ensure that the bot isn't launched again after server restart. The method will return error 429 in the first 10 minutes after the bot is launched. Returns True on success. Requires no parameters."""
        _payload = None
        _result = await self._arequest("close", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_message(self, chat_id: Union[int, str], text: str, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, parse_mode: Optional[str] = None, entities: Optional[List["MessageEntity"]] = None, link_preview_options: Optional["LinkPreviewOptions"] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send text messages. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "text": text,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "entities": entities,
            "link_preview_options": link_preview_options,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("sendMessage", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def forward_message(self, chat_id: Union[int, str], from_chat_id: Union[int, str], message_id: int, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, video_start_timestamp: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None) -> "MessageId":
        """Use this method to forward messages of any kind. Service messages and messages with protected content can't be forwarded. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "from_chat_id": from_chat_id,
            "message_id": message_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "video_start_timestamp": video_start_timestamp,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
        }
        _result = await self._arequest("forwardMessage", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'MessageId', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def forward_messages(self, chat_id: Union[int, str], from_chat_id: Union[int, str], message_ids: List[int], message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None) -> List["MessageId"]:
        """Use this method to forward multiple messages of any kind. If some of the specified messages can't be found or forwarded, they are skipped. Service messages and messages with protected content can't be forwarded. Album grouping is kept for forwarded messages. On success, an array of MessageId of the sent messages is returned."""
        _payload = {
            "chat_id": chat_id,
            "from_chat_id": from_chat_id,
            "message_ids": message_ids,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
        }
        _result = await self._arequest("forwardMessages", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageId', "list_depth": 1})


    async def copy_message(self, chat_id: Union[int, str], from_chat_id: Union[int, str], message_id: int, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, video_start_timestamp: Optional[int] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "MessageId":
        """Use this method to copy messages of any kind. Service messages, paid media messages, giveaway messages, giveaway winners messages, and invoice messages can't be copied. A quiz poll can be copied only if the value of the field correct_option_id is known to the bot. The method is analogous to the method forwardMessage , but the copied message doesn't have a link to the original message. Returns the MessageId of the sent message on success."""
        _payload = {
            "chat_id": chat_id,
            "from_chat_id": from_chat_id,
            "message_id": message_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "video_start_timestamp": video_start_timestamp,
            "caption": caption,
            "parse_mode": parse_mode,
            "caption_entities": caption_entities,
            "show_caption_above_media": show_caption_above_media,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("copyMessage", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'MessageId', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def copy_messages(self, chat_id: Union[int, str], from_chat_id: Union[int, str], message_ids: List[int], message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, remove_caption: Optional[bool] = None) -> List["MessageId"]:
        """Use this method to copy messages of any kind. If some of the specified messages can't be found or copied, they are skipped. Service messages, paid media messages, giveaway messages, giveaway winners messages, and invoice messages can't be copied. A quiz poll can be copied only if the value of the field correct_option_id is known to the bot. The method is analogous to the method forwardMessages , but the copied messages don't have a link to the original message. Album grouping is kept for copied messages. On success, an array of MessageId of the sent messages is returned."""
        _payload = {
            "chat_id": chat_id,
            "from_chat_id": from_chat_id,
            "message_ids": message_ids,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "remove_caption": remove_caption,
        }
        _result = await self._arequest("copyMessages", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'MessageId', "list_depth": 1})


    async def send_photo(self, chat_id: Union[int, str], photo: Union[Union[str, InputFile], str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, has_spoiler: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send photos. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "photo": photo,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "caption": caption,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "caption_entities": caption_entities,
            "show_caption_above_media": show_caption_above_media,
            "has_spoiler": has_spoiler,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("sendPhoto", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_live_photo(self, chat_id: Union[int, str], live_photo: Union[Union[str, InputFile], str], photo: Union[Union[str, InputFile], str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, has_spoiler: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send live photos. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "live_photo": live_photo,
            "photo": photo,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "caption": caption,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "caption_entities": caption_entities,
            "show_caption_above_media": show_caption_above_media,
            "has_spoiler": has_spoiler,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("sendLivePhoto", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_audio(self, chat_id: Union[int, str], audio: Union[Union[str, InputFile], str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, duration: Optional[int] = None, performer: Optional[str] = None, title: Optional[str] = None, thumbnail: Optional[Union[Union[str, InputFile], str]] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send audio files, if you want Telegram clients to display them in the music player. Your audio must be in the .MP3 or .M4A format. On success, the sent Message is returned. Bots can currently send audio files of up to 50 MB in size, this limit may be changed in the future."""
        _payload = {
            "chat_id": chat_id,
            "audio": audio,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "caption": caption,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "caption_entities": caption_entities,
            "duration": duration,
            "performer": performer,
            "title": title,
            "thumbnail": thumbnail,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("sendAudio", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_document(self, chat_id: Union[int, str], document: Union[Union[str, InputFile], str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, thumbnail: Optional[Union[Union[str, InputFile], str]] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, disable_content_type_detection: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send general files. On success, the sent Message is returned. Bots can currently send files of any type of up to 50 MB in size, this limit may be changed in the future."""
        _payload = {
            "chat_id": chat_id,
            "document": document,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "thumbnail": thumbnail,
            "caption": caption,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "caption_entities": caption_entities,
            "disable_content_type_detection": disable_content_type_detection,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("sendDocument", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_video(self, chat_id: Union[int, str], video: Union[Union[str, InputFile], str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, duration: Optional[int] = None, width: Optional[int] = None, height: Optional[int] = None, thumbnail: Optional[Union[Union[str, InputFile], str]] = None, cover: Optional[Union[Union[str, InputFile], str]] = None, start_timestamp: Optional[int] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, has_spoiler: Optional[bool] = None, supports_streaming: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send video files, Telegram clients support MPEG4 videos (other formats may be sent as Document ). On success, the sent Message is returned. Bots can currently send video files of up to 50 MB in size, this limit may be changed in the future."""
        _payload = {
            "chat_id": chat_id,
            "video": video,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "duration": duration,
            "width": width,
            "height": height,
            "thumbnail": thumbnail,
            "cover": cover,
            "start_timestamp": start_timestamp,
            "caption": caption,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "caption_entities": caption_entities,
            "show_caption_above_media": show_caption_above_media,
            "has_spoiler": has_spoiler,
            "supports_streaming": supports_streaming,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("sendVideo", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_animation(self, chat_id: Union[int, str], animation: Union[Union[str, InputFile], str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, duration: Optional[int] = None, width: Optional[int] = None, height: Optional[int] = None, thumbnail: Optional[Union[Union[str, InputFile], str]] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, has_spoiler: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send animation files (GIF or H.264/MPEG-4 AVC video without sound). On success, the sent Message is returned. Bots can currently send animation files of up to 50 MB in size, this limit may be changed in the future."""
        _payload = {
            "chat_id": chat_id,
            "animation": animation,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "duration": duration,
            "width": width,
            "height": height,
            "thumbnail": thumbnail,
            "caption": caption,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "caption_entities": caption_entities,
            "show_caption_above_media": show_caption_above_media,
            "has_spoiler": has_spoiler,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("sendAnimation", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_voice(self, chat_id: Union[int, str], voice: Union[Union[str, InputFile], str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, duration: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send audio files, if you want Telegram clients to display the file as a playable voice message. For this to work, your audio must be in an .OGG file encoded with OPUS, or in .MP3 format, or in .M4A format (other formats may be sent as Audio or Document ). On success, the sent Message is returned. Bots can currently send voice messages of up to 50 MB in size, this limit may be changed in the future."""
        _payload = {
            "chat_id": chat_id,
            "voice": voice,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "caption": caption,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "caption_entities": caption_entities,
            "duration": duration,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("sendVoice", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_video_note(self, chat_id: Union[int, str], video_note: Union[Union[str, InputFile], str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, duration: Optional[int] = None, length: Optional[int] = None, thumbnail: Optional[Union[Union[str, InputFile], str]] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """As of v.4.0 , Telegram clients support rounded square MPEG4 videos of up to 1 minute long. Use this method to send video messages. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "video_note": video_note,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "duration": duration,
            "length": length,
            "thumbnail": thumbnail,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("sendVideoNote", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_paid_media(self, chat_id: Union[int, str], star_count: int, media: List["InputPaidMedia"], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, payload: Optional[str] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send paid media. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "star_count": star_count,
            "media": media,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "payload": payload,
            "caption": caption,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "caption_entities": caption_entities,
            "show_caption_above_media": show_caption_above_media,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("sendPaidMedia", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_media_group(self, chat_id: Union[int, str], media: List[Any], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, reply_parameters: Optional["ReplyParameters"] = None) -> List["Message"]:
        """Use this method to send a group of photos, live photos, videos, documents or audios as an album. Documents and audio files can be only grouped in an album with messages of the same type. On success, an array of Message objects that were sent is returned."""
        _payload = {
            "chat_id": chat_id,
            "media": media,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "reply_parameters": reply_parameters,
        }
        _result = await self._arequest("sendMediaGroup", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'Message', "list_depth": 1})


    async def send_location(self, chat_id: Union[int, str], latitude: float, longitude: float, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, horizontal_accuracy: Optional[float] = None, live_period: Optional[int] = None, heading: Optional[int] = None, proximity_alert_radius: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send point on the map. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "latitude": latitude,
            "longitude": longitude,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "horizontal_accuracy": horizontal_accuracy,
            "live_period": live_period,
            "heading": heading,
            "proximity_alert_radius": proximity_alert_radius,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("sendLocation", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_venue(self, chat_id: Union[int, str], latitude: float, longitude: float, title: str, address: str, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, foursquare_id: Optional[str] = None, foursquare_type: Optional[str] = None, google_place_id: Optional[str] = None, google_place_type: Optional[str] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send information about a venue. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "latitude": latitude,
            "longitude": longitude,
            "title": title,
            "address": address,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "foursquare_id": foursquare_id,
            "foursquare_type": foursquare_type,
            "google_place_id": google_place_id,
            "google_place_type": google_place_type,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("sendVenue", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_contact(self, chat_id: Union[int, str], phone_number: str, first_name: str, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, last_name: Optional[str] = None, vcard: Optional[str] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send phone contacts. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "phone_number": phone_number,
            "first_name": first_name,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "last_name": last_name,
            "vcard": vcard,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("sendContact", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_poll(self, chat_id: Union[int, str], question: str, options: List["InputPollOption"], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, question_parse_mode: Optional[str] = None, question_entities: Optional[List["MessageEntity"]] = None, is_anonymous: Optional[bool] = None, type_val: Optional[str] = None, allows_multiple_answers: Optional[bool] = None, allows_revoting: Optional[bool] = None, shuffle_options: Optional[bool] = None, allow_adding_options: Optional[bool] = None, hide_results_until_closes: Optional[bool] = None, members_only: Optional[bool] = None, country_codes: Optional[List[str]] = None, correct_option_ids: Optional[List[int]] = None, explanation: Optional[str] = None, explanation_parse_mode: Optional[str] = None, explanation_entities: Optional[List["MessageEntity"]] = None, explanation_media: Optional["InputPollMedia"] = None, open_period: Optional[int] = None, close_date: Optional[int] = None, is_closed: Optional[bool] = None, description: Optional[str] = None, description_parse_mode: Optional[str] = None, description_entities: Optional[List["MessageEntity"]] = None, media: Optional["InputPollMedia"] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send a native poll. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "question": question,
            "options": options,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "question_parse_mode": question_parse_mode,
            "question_entities": question_entities,
            "is_anonymous": is_anonymous,
            "type": type_val,
            "allows_multiple_answers": allows_multiple_answers,
            "allows_revoting": allows_revoting,
            "shuffle_options": shuffle_options,
            "allow_adding_options": allow_adding_options,
            "hide_results_until_closes": hide_results_until_closes,
            "members_only": members_only,
            "country_codes": country_codes,
            "correct_option_ids": correct_option_ids,
            "explanation": explanation,
            "explanation_parse_mode": explanation_parse_mode,
            "explanation_entities": explanation_entities,
            "explanation_media": explanation_media,
            "open_period": open_period,
            "close_date": close_date,
            "is_closed": is_closed,
            "description": description,
            "description_parse_mode": description_parse_mode,
            "description_entities": description_entities,
            "media": media,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("sendPoll", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_checklist(self, business_connection_id: str, chat_id: Union[int, str], checklist: "InputChecklist", disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, message_effect_id: Optional[str] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Message":
        """Use this method to send a checklist on behalf of a connected business account. On success, the sent Message is returned."""
        _payload = {
            "business_connection_id": business_connection_id,
            "chat_id": chat_id,
            "checklist": checklist,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "message_effect_id": message_effect_id,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("sendChecklist", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_dice(self, chat_id: Union[int, str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, emoji: Optional[str] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send an animated emoji that will display a random value. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "emoji": emoji,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("sendDice", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_message_draft(self, chat_id: int, draft_id: int, message_thread_id: Optional[int] = None, text: Optional[str] = None, parse_mode: Optional[str] = None, entities: Optional[List["MessageEntity"]] = None) -> "Message":
        """Use this method to stream a partial message to a user while the message is being generated. Note that the streamed draft is ephemeral and acts as a temporary 30-second preview - once the output is finalized, you must call sendMessage with the complete message to persist it in the user's chat. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "draft_id": draft_id,
            "message_thread_id": message_thread_id,
            "text": text,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "entities": entities,
        }
        _result = await self._arequest("sendMessageDraft", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_chat_action(self, chat_id: Union[int, str], action: str, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None) -> bool:
        """Use this method when you need to tell the user that something is happening on the bot's side. The status is set for 5 seconds or less (when a message arrives from your bot, Telegram clients clear its typing status). Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "action": action,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
        }
        _result = await self._arequest("sendChatAction", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_message_reaction(self, chat_id: Union[int, str], message_id: int, reaction: Optional[List["ReactionType"]] = None, is_big: Optional[bool] = None) -> bool:
        """Use this method to change the chosen reactions on a message. Service messages of some types can't be reacted to. Automatically forwarded messages from a channel to its discussion group have the same available reactions as messages in the channel. Bots can't use paid reactions. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "reaction": reaction,
            "is_big": is_big,
        }
        _result = await self._arequest("setMessageReaction", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_user_profile_photos(self, user_id: int, offset: Optional[int] = None, limit: Optional[int] = None) -> "UserProfilePhotos":
        """Use this method to get a list of profile pictures for a user. Returns a UserProfilePhotos object."""
        _payload = {
            "user_id": user_id,
            "offset": offset,
            "limit": limit,
        }
        _result = await self._arequest("getUserProfilePhotos", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'UserProfilePhotos', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_user_profile_audios(self, user_id: int, offset: Optional[int] = None, limit: Optional[int] = None) -> "UserProfileAudios":
        """Use this method to get a list of profile audios for a user. Returns a UserProfileAudios object."""
        _payload = {
            "user_id": user_id,
            "offset": offset,
            "limit": limit,
        }
        _result = await self._arequest("getUserProfileAudios", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'UserProfileAudios', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_user_emoji_status(self, user_id: int, emoji_status_custom_emoji_id: Optional[str] = None, emoji_status_expiration_date: Optional[int] = None) -> bool:
        """Changes the emoji status for a given user that previously allowed the bot to manage their emoji status via the Mini App method requestEmojiStatusAccess . Returns True on success."""
        _payload = {
            "user_id": user_id,
            "emoji_status_custom_emoji_id": emoji_status_custom_emoji_id,
            "emoji_status_expiration_date": emoji_status_expiration_date,
        }
        _result = await self._arequest("setUserEmojiStatus", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_file(self, file_id: str) -> "File":
        """Use this method to get basic information about a file and prepare it for downloading. For the moment, bots can download files of up to 20MB in size. On success, a File object is returned. The file can then be downloaded via the link https://api.telegram.org/file/bot<token>/<file_path> , where <file_path> is taken from the response. It is guaranteed that the link will be valid for at least 1 hour. When the link expires, a new one can be requested by calling getFile again."""
        _payload = {
            "file_id": file_id,
        }
        _result = await self._arequest("getFile", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'File', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def ban_chat_member(self, chat_id: Union[int, str], user_id: int, until_date: Optional[int] = None, revoke_messages: Optional[bool] = None) -> bool:
        """Use this method to ban a user in a group, a supergroup or a channel. In the case of supergroups and channels, the user will not be able to return to the chat on their own using invite links, etc., unless unbanned first. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
            "until_date": until_date,
            "revoke_messages": revoke_messages,
        }
        _result = await self._arequest("banChatMember", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def unban_chat_member(self, chat_id: Union[int, str], user_id: int, only_if_banned: Optional[bool] = None) -> bool:
        """Use this method to unban a previously banned user in a supergroup or channel. The user will not return to the group or channel automatically, but will be able to join via link, etc. The bot must be an administrator for this to work. By default, this method guarantees that after the call the user is not a member of the chat, but will be able to join it. So if the user is a member of the chat they will also be removed from the chat. If you don't want this, use the parameter only_if_banned . Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
            "only_if_banned": only_if_banned,
        }
        _result = await self._arequest("unbanChatMember", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def restrict_chat_member(self, chat_id: Union[int, str], user_id: int, permissions: "ChatPermissions", use_independent_chat_permissions: Optional[bool] = None, until_date: Optional[int] = None) -> bool:
        """Use this method to restrict a user in a supergroup. The bot must be an administrator in the supergroup for this to work and must have the appropriate administrator rights. Pass True for all permissions to lift restrictions from a user. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
            "permissions": permissions,
            "use_independent_chat_permissions": use_independent_chat_permissions,
            "until_date": until_date,
        }
        _result = await self._arequest("restrictChatMember", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def promote_chat_member(self, chat_id: Union[int, str], user_id: int, is_anonymous: Optional[bool] = None, can_manage_chat: Optional[bool] = None, can_delete_messages: Optional[bool] = None, can_manage_video_chats: Optional[bool] = None, can_restrict_members: Optional[bool] = None, can_promote_members: Optional[bool] = None, can_change_info: Optional[bool] = None, can_invite_users: Optional[bool] = None, can_post_stories: Optional[bool] = None, can_edit_stories: Optional[bool] = None, can_delete_stories: Optional[bool] = None, can_post_messages: Optional[bool] = None, can_edit_messages: Optional[bool] = None, can_pin_messages: Optional[bool] = None, can_manage_topics: Optional[bool] = None, can_manage_direct_messages: Optional[bool] = None, can_manage_tags: Optional[bool] = None) -> bool:
        """Use this method to promote or demote a user in a supergroup or a channel. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Pass False for all boolean parameters to demote a user. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
            "is_anonymous": is_anonymous,
            "can_manage_chat": can_manage_chat,
            "can_delete_messages": can_delete_messages,
            "can_manage_video_chats": can_manage_video_chats,
            "can_restrict_members": can_restrict_members,
            "can_promote_members": can_promote_members,
            "can_change_info": can_change_info,
            "can_invite_users": can_invite_users,
            "can_post_stories": can_post_stories,
            "can_edit_stories": can_edit_stories,
            "can_delete_stories": can_delete_stories,
            "can_post_messages": can_post_messages,
            "can_edit_messages": can_edit_messages,
            "can_pin_messages": can_pin_messages,
            "can_manage_topics": can_manage_topics,
            "can_manage_direct_messages": can_manage_direct_messages,
            "can_manage_tags": can_manage_tags,
        }
        _result = await self._arequest("promoteChatMember", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_chat_administrator_custom_title(self, chat_id: Union[int, str], user_id: int, custom_title: str) -> bool:
        """Use this method to set a custom title for an administrator in a supergroup promoted by the bot. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
            "custom_title": custom_title,
        }
        _result = await self._arequest("setChatAdministratorCustomTitle", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_chat_member_tag(self, chat_id: Union[int, str], user_id: int, tag: Optional[str] = None) -> bool:
        """Use this method to set a tag for a regular member in a group or a supergroup. The bot must be an administrator in the chat for this to work and must have the can_manage_tags administrator right. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
            "tag": tag,
        }
        _result = await self._arequest("setChatMemberTag", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def ban_chat_sender_chat(self, chat_id: Union[int, str], sender_chat_id: int) -> bool:
        """Use this method to ban a channel chat in a supergroup or a channel. Until the chat is unbanned , the owner of the banned chat won't be able to send messages on behalf of any of their channels . The bot must be an administrator in the supergroup or channel for this to work and must have the appropriate administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "sender_chat_id": sender_chat_id,
        }
        _result = await self._arequest("banChatSenderChat", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def unban_chat_sender_chat(self, chat_id: Union[int, str], sender_chat_id: int) -> bool:
        """Use this method to unban a previously banned channel chat in a supergroup or channel. The bot must be an administrator for this to work and must have the appropriate administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "sender_chat_id": sender_chat_id,
        }
        _result = await self._arequest("unbanChatSenderChat", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_chat_permissions(self, chat_id: Union[int, str], permissions: "ChatPermissions", use_independent_chat_permissions: Optional[bool] = None) -> bool:
        """Use this method to set default chat permissions for all members. The bot must be an administrator in the group or a supergroup for this to work and must have the can_restrict_members administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "permissions": permissions,
            "use_independent_chat_permissions": use_independent_chat_permissions,
        }
        _result = await self._arequest("setChatPermissions", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def export_chat_invite_link(self, chat_id: Union[int, str]) -> str:
        """Use this method to generate a new primary invite link for a chat; any previously generated primary link is revoked. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns the new invite link as String on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = await self._arequest("exportChatInviteLink", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def create_chat_invite_link(self, chat_id: Union[int, str], name: Optional[str] = None, expire_date: Optional[int] = None, member_limit: Optional[int] = None, creates_join_request: Optional[bool] = None) -> "ChatInviteLink":
        """Use this method to create an additional invite link for a chat. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. The link can be revoked using the method revokeChatInviteLink . Returns the new invite link as ChatInviteLink object."""
        _payload = {
            "chat_id": chat_id,
            "name": name,
            "expire_date": expire_date,
            "member_limit": member_limit,
            "creates_join_request": creates_join_request,
        }
        _result = await self._arequest("createChatInviteLink", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'ChatInviteLink', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def edit_chat_invite_link(self, chat_id: Union[int, str], invite_link: str, name: Optional[str] = None, expire_date: Optional[int] = None, member_limit: Optional[int] = None, creates_join_request: Optional[bool] = None) -> "ChatInviteLink":
        """Use this method to edit a non-primary invite link created by the bot. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns the edited invite link as a ChatInviteLink object."""
        _payload = {
            "chat_id": chat_id,
            "invite_link": invite_link,
            "name": name,
            "expire_date": expire_date,
            "member_limit": member_limit,
            "creates_join_request": creates_join_request,
        }
        _result = await self._arequest("editChatInviteLink", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'ChatInviteLink', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def create_chat_subscription_invite_link(self, chat_id: Union[int, str], subscription_period: int, subscription_price: int, name: Optional[str] = None) -> "ChatInviteLink":
        """Use this method to create a subscription invite link for a channel chat. The bot must have the can_invite_users administrator rights. The link can be edited using the method editChatSubscriptionInviteLink or revoked using the method revokeChatInviteLink . Returns the new invite link as a ChatInviteLink object."""
        _payload = {
            "chat_id": chat_id,
            "subscription_period": subscription_period,
            "subscription_price": subscription_price,
            "name": name,
        }
        _result = await self._arequest("createChatSubscriptionInviteLink", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'ChatInviteLink', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def edit_chat_subscription_invite_link(self, chat_id: Union[int, str], invite_link: str, name: Optional[str] = None) -> "ChatInviteLink":
        """Use this method to edit a subscription invite link created by the bot. The bot must have the can_invite_users administrator rights. Returns the edited invite link as a ChatInviteLink object."""
        _payload = {
            "chat_id": chat_id,
            "invite_link": invite_link,
            "name": name,
        }
        _result = await self._arequest("editChatSubscriptionInviteLink", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'ChatInviteLink', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def revoke_chat_invite_link(self, chat_id: Union[int, str], invite_link: str) -> "ChatInviteLink":
        """Use this method to revoke an invite link created by the bot. If the primary link is revoked, a new link is automatically generated. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns the revoked invite link as ChatInviteLink object."""
        _payload = {
            "chat_id": chat_id,
            "invite_link": invite_link,
        }
        _result = await self._arequest("revokeChatInviteLink", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'ChatInviteLink', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def approve_chat_join_request(self, chat_id: Union[int, str], user_id: int) -> bool:
        """Use this method to approve a chat join request. The bot must be an administrator in the chat for this to work and must have the can_invite_users administrator right. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
        }
        _result = await self._arequest("approveChatJoinRequest", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def decline_chat_join_request(self, chat_id: Union[int, str], user_id: int) -> bool:
        """Use this method to decline a chat join request. The bot must be an administrator in the chat for this to work and must have the can_invite_users administrator right. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
        }
        _result = await self._arequest("declineChatJoinRequest", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_chat_photo(self, chat_id: Union[int, str], photo: Union[str, InputFile]) -> bool:
        """Use this method to set a new profile photo for the chat. Photos can't be changed for private chats. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "photo": photo,
        }
        _result = await self._arequest("setChatPhoto", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def delete_chat_photo(self, chat_id: Union[int, str]) -> bool:
        """Use this method to delete a chat photo. Photos can't be changed for private chats. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = await self._arequest("deleteChatPhoto", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_chat_title(self, chat_id: Union[int, str], title: str) -> bool:
        """Use this method to change the title of a chat. Titles can't be changed for private chats. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "title": title,
        }
        _result = await self._arequest("setChatTitle", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_chat_description(self, chat_id: Union[int, str], description: Optional[str] = None) -> bool:
        """Use this method to change the description of a group, a supergroup or a channel. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "description": description,
        }
        _result = await self._arequest("setChatDescription", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def pin_chat_message(self, chat_id: Union[int, str], message_id: int, business_connection_id: Optional[str] = None, disable_notification: Optional[bool] = None) -> bool:
        """Use this method to add a message to the list of pinned messages in a chat. In private chats and channel direct messages chats, all non-service messages can be pinned. Conversely, the bot must be an administrator with the 'can_pin_messages' right or the 'can_edit_messages' right to pin messages in groups and channels respectively. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "business_connection_id": business_connection_id,
            "disable_notification": disable_notification,
        }
        _result = await self._arequest("pinChatMessage", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def unpin_chat_message(self, chat_id: Union[int, str], business_connection_id: Optional[str] = None, message_id: Optional[int] = None) -> bool:
        """Use this method to remove a message from the list of pinned messages in a chat. In private chats and channel direct messages chats, all messages can be unpinned. Conversely, the bot must be an administrator with the 'can_pin_messages' right or the 'can_edit_messages' right to unpin messages in groups and channels respectively. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "business_connection_id": business_connection_id,
            "message_id": message_id,
        }
        _result = await self._arequest("unpinChatMessage", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def unpin_all_chat_messages(self, chat_id: Union[int, str]) -> bool:
        """Use this method to clear the list of pinned messages in a chat. In private chats and channel direct messages chats, no additional rights are required to unpin all pinned messages. Conversely, the bot must be an administrator with the 'can_pin_messages' right or the 'can_edit_messages' right to unpin all pinned messages in groups and channels respectively. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = await self._arequest("unpinAllChatMessages", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def leave_chat(self, chat_id: Union[int, str]) -> bool:
        """Use this method for your bot to leave a group, supergroup or channel. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = await self._arequest("leaveChat", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_chat(self, chat_id: Union[int, str]) -> "ChatFullInfo":
        """Use this method to get up-to-date information about the chat. Returns a ChatFullInfo object on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = await self._arequest("getChat", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'ChatFullInfo', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_chat_administrators(self, chat_id: Union[int, str], return_bots: Optional[bool] = None) -> List["ChatMember"]:
        """Use this method to get a list of administrators in a chat. Returns an Array of ChatMember objects."""
        _payload = {
            "chat_id": chat_id,
            "return_bots": return_bots,
        }
        _result = await self._arequest("getChatAdministrators", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'ChatMember', "list_depth": 1})


    async def get_chat_member_count(self, chat_id: Union[int, str]) -> Any:
        """Use this method to get the number of members in a chat. Returns Int on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = await self._arequest("getChatMemberCount", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_chat_member(self, chat_id: Union[int, str], user_id: int) -> "ChatMember":
        """Use this method to get information about a member of a chat. The method is only guaranteed to work for other users if the bot is an administrator in the chat. Returns a ChatMember object on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
        }
        _result = await self._arequest("getChatMember", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'ChatMember', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_user_personal_chat_messages(self, user_id: int, limit: int) -> List["Message"]:
        """Use this method to get the last messages from the personal chat (i.e., the chat currently added to their profile) of a given user. On success, an array of Message objects is returned."""
        _payload = {
            "user_id": user_id,
            "limit": limit,
        }
        _result = await self._arequest("getUserPersonalChatMessages", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'Message', "list_depth": 1})


    async def set_chat_sticker_set(self, chat_id: Union[int, str], sticker_set_name: str) -> bool:
        """Use this method to set a new group sticker set for a supergroup. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Use the field can_set_sticker_set optionally returned in getChat requests to check if the bot can use this method. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "sticker_set_name": sticker_set_name,
        }
        _result = await self._arequest("setChatStickerSet", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def delete_chat_sticker_set(self, chat_id: Union[int, str]) -> bool:
        """Use this method to delete a group sticker set from a supergroup. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Use the field can_set_sticker_set optionally returned in getChat requests to check if the bot can use this method. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = await self._arequest("deleteChatStickerSet", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_forum_topic_icon_stickers(self) -> List["Sticker"]:
        """Use this method to get custom emoji stickers, which can be used as a forum topic icon by any user. Requires no parameters. Returns an Array of Sticker objects."""
        _payload = None
        _result = await self._arequest("getForumTopicIconStickers", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'Sticker', "list_depth": 1})


    async def create_forum_topic(self, chat_id: Union[int, str], name: str, icon_color: Optional[int] = None, icon_custom_emoji_id: Optional[str] = None) -> "ForumTopic":
        """Use this method to create a topic in a forum supergroup chat or a private chat with a user. In the case of a supergroup chat the bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator right. Returns information about the created topic as a ForumTopic object."""
        _payload = {
            "chat_id": chat_id,
            "name": name,
            "icon_color": icon_color,
            "icon_custom_emoji_id": icon_custom_emoji_id,
        }
        _result = await self._arequest("createForumTopic", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'ForumTopic', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def edit_forum_topic(self, chat_id: Union[int, str], message_thread_id: int, name: Optional[str] = None, icon_custom_emoji_id: Optional[str] = None) -> bool:
        """Use this method to edit name and icon of a topic in a forum supergroup chat or a private chat with a user. In the case of a supergroup chat the bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights, unless it is the creator of the topic. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_thread_id": message_thread_id,
            "name": name,
            "icon_custom_emoji_id": icon_custom_emoji_id,
        }
        _result = await self._arequest("editForumTopic", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def close_forum_topic(self, chat_id: Union[int, str], message_thread_id: int) -> bool:
        """Use this method to close an open topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights, unless it is the creator of the topic. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_thread_id": message_thread_id,
        }
        _result = await self._arequest("closeForumTopic", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def reopen_forum_topic(self, chat_id: Union[int, str], message_thread_id: int) -> bool:
        """Use this method to reopen a closed topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights, unless it is the creator of the topic. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_thread_id": message_thread_id,
        }
        _result = await self._arequest("reopenForumTopic", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def delete_forum_topic(self, chat_id: Union[int, str], message_thread_id: int) -> bool:
        """Use this method to delete a forum topic along with all its messages in a forum supergroup chat or a private chat with a user. In the case of a supergroup chat the bot must be an administrator in the chat for this to work and must have the can_delete_messages administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_thread_id": message_thread_id,
        }
        _result = await self._arequest("deleteForumTopic", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def unpin_all_forum_topic_messages(self, chat_id: Union[int, str], message_thread_id: int) -> bool:
        """Use this method to clear the list of pinned messages in a forum topic in a forum supergroup chat or a private chat with a user. In the case of a supergroup chat the bot must be an administrator in the chat for this to work and must have the can_pin_messages administrator right in the supergroup. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_thread_id": message_thread_id,
        }
        _result = await self._arequest("unpinAllForumTopicMessages", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def edit_general_forum_topic(self, chat_id: Union[int, str], name: str) -> bool:
        """Use this method to edit the name of the 'General' topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "name": name,
        }
        _result = await self._arequest("editGeneralForumTopic", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def close_general_forum_topic(self, chat_id: Union[int, str]) -> bool:
        """Use this method to close an open 'General' topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = await self._arequest("closeGeneralForumTopic", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def reopen_general_forum_topic(self, chat_id: Union[int, str]) -> bool:
        """Use this method to reopen a closed 'General' topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights. The topic will be automatically unhidden if it was hidden. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = await self._arequest("reopenGeneralForumTopic", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def hide_general_forum_topic(self, chat_id: Union[int, str]) -> bool:
        """Use this method to hide the 'General' topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights. The topic will be automatically closed if it was open. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = await self._arequest("hideGeneralForumTopic", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def unhide_general_forum_topic(self, chat_id: Union[int, str]) -> bool:
        """Use this method to unhide the 'General' topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = await self._arequest("unhideGeneralForumTopic", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def unpin_all_general_forum_topic_messages(self, chat_id: Union[int, str]) -> bool:
        """Use this method to clear the list of pinned messages in a General forum topic. The bot must be an administrator in the chat for this to work and must have the can_pin_messages administrator right in the supergroup. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = await self._arequest("unpinAllGeneralForumTopicMessages", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def answer_callback_query(self, callback_query_id: str, text: Optional[str] = None, show_alert: Optional[bool] = None, url: Optional[str] = None, cache_time: Optional[int] = None) -> bool:
        """Use this method to send answers to callback queries sent from inline keyboards . The answer will be displayed to the user as a notification at the top of the chat screen or as an alert. On success, True is returned."""
        _payload = {
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": show_alert,
            "url": url,
            "cache_time": cache_time,
        }
        _result = await self._arequest("answerCallbackQuery", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def answer_guest_query(self, guest_query_id: str, result: "InlineQueryResult") -> bool:
        """Use this method to reply to a received guest message. On success, a SentGuestMessage object is returned."""
        _payload = {
            "guest_query_id": guest_query_id,
            "result": result,
        }
        _result = await self._arequest("answerGuestQuery", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_user_chat_boosts(self, chat_id: Union[int, str], user_id: int) -> "UserChatBoosts":
        """Use this method to get the list of boosts added to a chat by a user. Requires administrator rights in the chat. Returns a UserChatBoosts object."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
        }
        _result = await self._arequest("getUserChatBoosts", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'UserChatBoosts', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_business_connection(self, business_connection_id: str) -> "BusinessConnection":
        """Use this method to get information about the connection of the bot with a business account. Returns a BusinessConnection object on success."""
        _payload = {
            "business_connection_id": business_connection_id,
        }
        _result = await self._arequest("getBusinessConnection", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'BusinessConnection', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_managed_bot_token(self, user_id: int) -> str:
        """Use this method to get the token of a managed bot. Returns the token as String on success."""
        _payload = {
            "user_id": user_id,
        }
        _result = await self._arequest("getManagedBotToken", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def replace_managed_bot_token(self, user_id: int) -> str:
        """Use this method to revoke the current token of a managed bot and generate a new one. Returns the new token as String on success."""
        _payload = {
            "user_id": user_id,
        }
        _result = await self._arequest("replaceManagedBotToken", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_managed_bot_access_settings(self, user_id: int) -> "BotAccessSettings":
        """Use this method to get the access settings of a managed bot. Returns a BotAccessSettings object on success."""
        _payload = {
            "user_id": user_id,
        }
        _result = await self._arequest("getManagedBotAccessSettings", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'BotAccessSettings', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_managed_bot_access_settings(self, user_id: int, is_access_restricted: bool, added_user_ids: Optional[List[int]] = None) -> "BotAccessSettings":
        """Use this method to change the access settings of a managed bot. Returns True on success."""
        _payload = {
            "user_id": user_id,
            "is_access_restricted": is_access_restricted,
            "added_user_ids": added_user_ids,
        }
        _result = await self._arequest("setManagedBotAccessSettings", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'BotAccessSettings', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_my_commands(self, commands: List["BotCommand"], scope: Optional["BotCommandScope"] = None, language_code: Optional[str] = None) -> bool:
        """Use this method to change the list of the bot's commands. See this manual for more details about bot commands. Returns True on success."""
        _payload = {
            "commands": commands,
            "scope": scope,
            "language_code": language_code,
        }
        _result = await self._arequest("setMyCommands", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def delete_my_commands(self, scope: Optional["BotCommandScope"] = None, language_code: Optional[str] = None) -> bool:
        """Use this method to delete the list of the bot's commands for the given scope and user language. After deletion, higher level commands will be shown to affected users. Returns True on success."""
        _payload = {
            "scope": scope,
            "language_code": language_code,
        }
        _result = await self._arequest("deleteMyCommands", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_my_commands(self, scope: Optional["BotCommandScope"] = None, language_code: Optional[str] = None) -> List["BotCommand"]:
        """Use this method to get the current list of the bot's commands for the given scope and user language. Returns an Array of BotCommand objects. If commands aren't set, an empty list is returned."""
        _payload = {
            "scope": scope,
            "language_code": language_code,
        }
        _result = await self._arequest("getMyCommands", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'BotCommand', "list_depth": 1})


    async def set_my_name(self, name: Optional[str] = None, language_code: Optional[str] = None) -> bool:
        """Use this method to change the bot's name. Returns True on success."""
        _payload = {
            "name": name,
            "language_code": language_code,
        }
        _result = await self._arequest("setMyName", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_my_name(self, language_code: Optional[str] = None) -> "BotName":
        """Use this method to get the current bot name for the given user language. Returns BotName on success."""
        _payload = {
            "language_code": language_code,
        }
        _result = await self._arequest("getMyName", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'BotName', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_my_description(self, description: Optional[str] = None, language_code: Optional[str] = None) -> bool:
        """Use this method to change the bot's description, which is shown in the chat with the bot if the chat is empty. Returns True on success."""
        _payload = {
            "description": description,
            "language_code": language_code,
        }
        _result = await self._arequest("setMyDescription", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_my_description(self, language_code: Optional[str] = None) -> "BotDescription":
        """Use this method to get the current bot description for the given user language. Returns BotDescription on success."""
        _payload = {
            "language_code": language_code,
        }
        _result = await self._arequest("getMyDescription", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'BotDescription', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_my_short_description(self, short_description: Optional[str] = None, language_code: Optional[str] = None) -> bool:
        """Use this method to change the bot's short description, which is shown on the bot's profile page and is sent together with the link when users share the bot. Returns True on success."""
        _payload = {
            "short_description": short_description,
            "language_code": language_code,
        }
        _result = await self._arequest("setMyShortDescription", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_my_short_description(self, language_code: Optional[str] = None) -> "BotShortDescription":
        """Use this method to get the current bot short description for the given user language. Returns BotShortDescription on success."""
        _payload = {
            "language_code": language_code,
        }
        _result = await self._arequest("getMyShortDescription", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'BotShortDescription', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_my_profile_photo(self, photo: "InputProfilePhoto") -> bool:
        """Changes the profile photo of the bot. Returns True on success."""
        _payload = {
            "photo": photo,
        }
        _result = await self._arequest("setMyProfilePhoto", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def remove_my_profile_photo(self) -> bool:
        """Removes the profile photo of the bot. Requires no parameters. Returns True on success."""
        _payload = None
        _result = await self._arequest("removeMyProfilePhoto", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_chat_menu_button(self, chat_id: Optional[int] = None, menu_button: Optional["MenuButton"] = None) -> bool:
        """Use this method to change the bot's menu button in a private chat, or the default menu button. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "menu_button": menu_button,
        }
        _result = await self._arequest("setChatMenuButton", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_chat_menu_button(self, chat_id: Optional[int] = None) -> "MenuButton":
        """Use this method to get the current value of the bot's menu button in a private chat, or the default menu button. Returns MenuButton on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = await self._arequest("getChatMenuButton", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'MenuButton', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_my_default_administrator_rights(self, rights: Optional["ChatAdministratorRights"] = None, for_channels: Optional[bool] = None) -> bool:
        """Use this method to change the default administrator rights requested by the bot when it's added as an administrator to groups or channels. These rights will be suggested to users, but they are free to modify the list before adding the bot. Returns True on success."""
        _payload = {
            "rights": rights,
            "for_channels": for_channels,
        }
        _result = await self._arequest("setMyDefaultAdministratorRights", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_my_default_administrator_rights(self, for_channels: Optional[bool] = None) -> "ChatAdministratorRights":
        """Use this method to get the current default administrator rights of the bot. Returns ChatAdministratorRights on success."""
        _payload = {
            "for_channels": for_channels,
        }
        _result = await self._arequest("getMyDefaultAdministratorRights", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'ChatAdministratorRights', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_available_gifts(self) -> "Gifts":
        """Returns the list of gifts that can be sent by the bot to users and channel chats. Requires no parameters. Returns a Gifts object."""
        _payload = None
        _result = await self._arequest("getAvailableGifts", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Gifts', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_gift(self, gift_id: str, user_id: Optional[int] = None, chat_id: Optional[Union[int, str]] = None, pay_for_upgrade: Optional[bool] = None, text: Optional[str] = None, text_parse_mode: Optional[str] = None, text_entities: Optional[List["MessageEntity"]] = None) -> bool:
        """Sends a gift to the given user or channel chat. The gift can't be converted to Telegram Stars by the receiver. Returns True on success."""
        _payload = {
            "gift_id": gift_id,
            "user_id": user_id,
            "chat_id": chat_id,
            "pay_for_upgrade": pay_for_upgrade,
            "text": text,
            "text_parse_mode": text_parse_mode,
            "text_entities": text_entities,
        }
        _result = await self._arequest("sendGift", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def gift_premium_subscription(self, user_id: int, month_count: int, star_count: int, text: Optional[str] = None, text_parse_mode: Optional[str] = None, text_entities: Optional[List["MessageEntity"]] = None) -> bool:
        """Gifts a Telegram Premium subscription to the given user. Returns True on success."""
        _payload = {
            "user_id": user_id,
            "month_count": month_count,
            "star_count": star_count,
            "text": text,
            "text_parse_mode": text_parse_mode,
            "text_entities": text_entities,
        }
        _result = await self._arequest("giftPremiumSubscription", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def verify_user(self, user_id: int, custom_description: Optional[str] = None) -> bool:
        """Verifies a user on behalf of the organization which is represented by the bot. Returns True on success."""
        _payload = {
            "user_id": user_id,
            "custom_description": custom_description,
        }
        _result = await self._arequest("verifyUser", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def verify_chat(self, chat_id: Union[int, str], custom_description: Optional[str] = None) -> bool:
        """Verifies a chat on behalf of the organization which is represented by the bot. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "custom_description": custom_description,
        }
        _result = await self._arequest("verifyChat", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def remove_user_verification(self, user_id: int) -> bool:
        """Removes verification from a user who is currently verified on behalf of the organization represented by the bot. Returns True on success."""
        _payload = {
            "user_id": user_id,
        }
        _result = await self._arequest("removeUserVerification", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def remove_chat_verification(self, chat_id: Union[int, str]) -> bool:
        """Removes verification from a chat that is currently verified on behalf of the organization represented by the bot. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
        }
        _result = await self._arequest("removeChatVerification", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def read_business_message(self, business_connection_id: str, chat_id: int, message_id: int) -> bool:
        """Marks incoming message as read on behalf of a business account. Requires the can_read_messages business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "chat_id": chat_id,
            "message_id": message_id,
        }
        _result = await self._arequest("readBusinessMessage", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def delete_business_messages(self, business_connection_id: str, message_ids: List[int]) -> bool:
        """Delete messages on behalf of a business account. Requires the can_delete_sent_messages business bot right to delete messages sent by the bot itself, or the can_delete_all_messages business bot right to delete any message. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "message_ids": message_ids,
        }
        _result = await self._arequest("deleteBusinessMessages", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_business_account_name(self, business_connection_id: str, first_name: str, last_name: Optional[str] = None) -> bool:
        """Changes the first and last name of a managed business account. Requires the can_change_name business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "first_name": first_name,
            "last_name": last_name,
        }
        _result = await self._arequest("setBusinessAccountName", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_business_account_username(self, business_connection_id: str, username: Optional[str] = None) -> bool:
        """Changes the username of a managed business account. Requires the can_change_username business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "username": username,
        }
        _result = await self._arequest("setBusinessAccountUsername", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_business_account_bio(self, business_connection_id: str, bio: Optional[str] = None) -> bool:
        """Changes the bio of a managed business account. Requires the can_change_bio business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "bio": bio,
        }
        _result = await self._arequest("setBusinessAccountBio", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_business_account_profile_photo(self, business_connection_id: str, photo: "InputProfilePhoto", is_public: Optional[bool] = None) -> bool:
        """Changes the profile photo of a managed business account. Requires the can_edit_profile_photo business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "photo": photo,
            "is_public": is_public,
        }
        _result = await self._arequest("setBusinessAccountProfilePhoto", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def remove_business_account_profile_photo(self, business_connection_id: str, is_public: Optional[bool] = None) -> bool:
        """Removes the current profile photo of a managed business account. Requires the can_edit_profile_photo business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "is_public": is_public,
        }
        _result = await self._arequest("removeBusinessAccountProfilePhoto", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_business_account_gift_settings(self, business_connection_id: str, show_gift_button: bool, accepted_gift_types: "AcceptedGiftTypes") -> bool:
        """Changes the privacy settings pertaining to incoming gifts in a managed business account. Requires the can_change_gift_settings business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "show_gift_button": show_gift_button,
            "accepted_gift_types": accepted_gift_types,
        }
        _result = await self._arequest("setBusinessAccountGiftSettings", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_business_account_star_balance(self, business_connection_id: str) -> "StarAmount":
        """Returns the amount of Telegram Stars owned by a managed business account. Requires the can_view_gifts_and_stars business bot right. Returns StarAmount on success."""
        _payload = {
            "business_connection_id": business_connection_id,
        }
        _result = await self._arequest("getBusinessAccountStarBalance", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'StarAmount', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def transfer_business_account_stars(self, business_connection_id: str, star_count: int) -> bool:
        """Transfers Telegram Stars from the business account balance to the bot's balance. Requires the can_transfer_stars business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "star_count": star_count,
        }
        _result = await self._arequest("transferBusinessAccountStars", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_business_account_gifts(self, business_connection_id: str, exclude_unsaved: Optional[bool] = None, exclude_saved: Optional[bool] = None, exclude_unlimited: Optional[bool] = None, exclude_limited_upgradable: Optional[bool] = None, exclude_limited_non_upgradable: Optional[bool] = None, exclude_unique: Optional[bool] = None, exclude_from_blockchain: Optional[bool] = None, sort_by_price: Optional[bool] = None, offset: Optional[str] = None, limit: Optional[int] = None) -> "OwnedGifts":
        """Returns the gifts received and owned by a managed business account. Requires the can_view_gifts_and_stars business bot right. Returns OwnedGifts on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "exclude_unsaved": exclude_unsaved,
            "exclude_saved": exclude_saved,
            "exclude_unlimited": exclude_unlimited,
            "exclude_limited_upgradable": exclude_limited_upgradable,
            "exclude_limited_non_upgradable": exclude_limited_non_upgradable,
            "exclude_unique": exclude_unique,
            "exclude_from_blockchain": exclude_from_blockchain,
            "sort_by_price": sort_by_price,
            "offset": offset,
            "limit": limit,
        }
        _result = await self._arequest("getBusinessAccountGifts", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'OwnedGifts', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_user_gifts(self, user_id: int, exclude_unlimited: Optional[bool] = None, exclude_limited_upgradable: Optional[bool] = None, exclude_limited_non_upgradable: Optional[bool] = None, exclude_from_blockchain: Optional[bool] = None, exclude_unique: Optional[bool] = None, sort_by_price: Optional[bool] = None, offset: Optional[str] = None, limit: Optional[int] = None) -> "OwnedGifts":
        """Returns the gifts owned and hosted by a user. Returns OwnedGifts on success."""
        _payload = {
            "user_id": user_id,
            "exclude_unlimited": exclude_unlimited,
            "exclude_limited_upgradable": exclude_limited_upgradable,
            "exclude_limited_non_upgradable": exclude_limited_non_upgradable,
            "exclude_from_blockchain": exclude_from_blockchain,
            "exclude_unique": exclude_unique,
            "sort_by_price": sort_by_price,
            "offset": offset,
            "limit": limit,
        }
        _result = await self._arequest("getUserGifts", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'OwnedGifts', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_chat_gifts(self, chat_id: Union[int, str], exclude_unsaved: Optional[bool] = None, exclude_saved: Optional[bool] = None, exclude_unlimited: Optional[bool] = None, exclude_limited_upgradable: Optional[bool] = None, exclude_limited_non_upgradable: Optional[bool] = None, exclude_from_blockchain: Optional[bool] = None, exclude_unique: Optional[bool] = None, sort_by_price: Optional[bool] = None, offset: Optional[str] = None, limit: Optional[int] = None) -> "OwnedGifts":
        """Returns the gifts owned by a chat. Returns OwnedGifts on success."""
        _payload = {
            "chat_id": chat_id,
            "exclude_unsaved": exclude_unsaved,
            "exclude_saved": exclude_saved,
            "exclude_unlimited": exclude_unlimited,
            "exclude_limited_upgradable": exclude_limited_upgradable,
            "exclude_limited_non_upgradable": exclude_limited_non_upgradable,
            "exclude_from_blockchain": exclude_from_blockchain,
            "exclude_unique": exclude_unique,
            "sort_by_price": sort_by_price,
            "offset": offset,
            "limit": limit,
        }
        _result = await self._arequest("getChatGifts", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'OwnedGifts', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def convert_gift_to_stars(self, business_connection_id: str, owned_gift_id: str) -> bool:
        """Converts a given regular gift to Telegram Stars. Requires the can_convert_gifts_to_stars business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "owned_gift_id": owned_gift_id,
        }
        _result = await self._arequest("convertGiftToStars", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def upgrade_gift(self, business_connection_id: str, owned_gift_id: str, keep_original_details: Optional[bool] = None, star_count: Optional[int] = None) -> bool:
        """Upgrades a given regular gift to a unique gift. Requires the can_transfer_and_upgrade_gifts business bot right. Additionally requires the can_transfer_stars business bot right if the upgrade is paid. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "owned_gift_id": owned_gift_id,
            "keep_original_details": keep_original_details,
            "star_count": star_count,
        }
        _result = await self._arequest("upgradeGift", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def transfer_gift(self, business_connection_id: str, owned_gift_id: str, new_owner_chat_id: int, star_count: Optional[int] = None) -> bool:
        """Transfers an owned unique gift to another user. Requires the can_transfer_and_upgrade_gifts business bot right. Requires can_transfer_stars business bot right if the transfer is paid. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "owned_gift_id": owned_gift_id,
            "new_owner_chat_id": new_owner_chat_id,
            "star_count": star_count,
        }
        _result = await self._arequest("transferGift", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def post_story(self, business_connection_id: str, content: "InputStoryContent", active_period: int, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, areas: Optional[List["StoryArea"]] = None, post_to_chat_page: Optional[bool] = None, protect_content: Optional[bool] = None) -> "Story":
        """Posts a story on behalf of a managed business account. Requires the can_manage_stories business bot right. Returns Story on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "content": content,
            "active_period": active_period,
            "caption": caption,
            "parse_mode": parse_mode,
            "caption_entities": caption_entities,
            "areas": areas,
            "post_to_chat_page": post_to_chat_page,
            "protect_content": protect_content,
        }
        _result = await self._arequest("postStory", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Story', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def repost_story(self, business_connection_id: str, from_chat_id: int, from_story_id: int, active_period: int, post_to_chat_page: Optional[bool] = None, protect_content: Optional[bool] = None) -> "Story":
        """Reposts a story on behalf of a business account from another business account. Both business accounts must be managed by the same bot, and the story on the source account must have been posted (or reposted) by the bot. Requires the can_manage_stories business bot right for both business accounts. Returns Story on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "from_chat_id": from_chat_id,
            "from_story_id": from_story_id,
            "active_period": active_period,
            "post_to_chat_page": post_to_chat_page,
            "protect_content": protect_content,
        }
        _result = await self._arequest("repostStory", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Story', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def edit_story(self, business_connection_id: str, story_id: int, content: "InputStoryContent", caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, areas: Optional[List["StoryArea"]] = None) -> "Story":
        """Edits a story previously posted by the bot on behalf of a managed business account. Requires the can_manage_stories business bot right. Returns Story on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "story_id": story_id,
            "content": content,
            "caption": caption,
            "parse_mode": parse_mode,
            "caption_entities": caption_entities,
            "areas": areas,
        }
        _result = await self._arequest("editStory", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Story', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def delete_story(self, business_connection_id: str, story_id: int) -> bool:
        """Deletes a story previously posted by the bot on behalf of a managed business account. Requires the can_manage_stories business bot right. Returns True on success."""
        _payload = {
            "business_connection_id": business_connection_id,
            "story_id": story_id,
        }
        _result = await self._arequest("deleteStory", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def answer_web_app_query(self, web_app_query_id: str, result: "InlineQueryResult") -> "SentWebAppMessage":
        """Use this method to set the result of an interaction with a Web App and send a corresponding message on behalf of the user to the chat from which the query originated. On success, a SentWebAppMessage object is returned."""
        _payload = {
            "web_app_query_id": web_app_query_id,
            "result": result,
        }
        _result = await self._arequest("answerWebAppQuery", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'SentWebAppMessage', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def save_prepared_inline_message(self, user_id: int, result: "InlineQueryResult", allow_user_chats: Optional[bool] = None, allow_bot_chats: Optional[bool] = None, allow_group_chats: Optional[bool] = None, allow_channel_chats: Optional[bool] = None) -> "PreparedInlineMessage":
        """Stores a message that can be sent by a user of a Mini App. Returns a PreparedInlineMessage object."""
        _payload = {
            "user_id": user_id,
            "result": result,
            "allow_user_chats": allow_user_chats,
            "allow_bot_chats": allow_bot_chats,
            "allow_group_chats": allow_group_chats,
            "allow_channel_chats": allow_channel_chats,
        }
        _result = await self._arequest("savePreparedInlineMessage", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'PreparedInlineMessage', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def save_prepared_keyboard_button(self, user_id: int, button: "KeyboardButton") -> "PreparedKeyboardButton":
        """Stores a keyboard button that can be used by a user within a Mini App. Returns a PreparedKeyboardButton object."""
        _payload = {
            "user_id": user_id,
            "button": button,
        }
        _result = await self._arequest("savePreparedKeyboardButton", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'PreparedKeyboardButton', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def edit_message_text(self, text: str, business_connection_id: Optional[str] = None, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None, parse_mode: Optional[str] = None, entities: Optional[List["MessageEntity"]] = None, link_preview_options: Optional["LinkPreviewOptions"] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Message":
        """Use this method to edit text and game messages. On success, if the edited message is not an inline message, the edited Message is returned, otherwise True is returned. Note that business messages that were not sent by the bot and do not contain an inline keyboard can only be edited within 48 hours from the time they were sent."""
        _payload = {
            "text": text,
            "business_connection_id": business_connection_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "inline_message_id": inline_message_id,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "entities": entities,
            "link_preview_options": link_preview_options,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("editMessageText", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def edit_message_caption(self, business_connection_id: Optional[str] = None, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Message":
        """Use this method to edit captions of messages. On success, if the edited message is not an inline message, the edited Message is returned, otherwise True is returned. Note that business messages that were not sent by the bot and do not contain an inline keyboard can only be edited within 48 hours from the time they were sent."""
        _payload = {
            "business_connection_id": business_connection_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "inline_message_id": inline_message_id,
            "caption": caption,
            "parse_mode": parse_mode if parse_mode is not None else self.parse_mode,
            "caption_entities": caption_entities,
            "show_caption_above_media": show_caption_above_media,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("editMessageCaption", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def edit_message_media(self, media: "InputMedia", business_connection_id: Optional[str] = None, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Message":
        """Use this method to edit animation, audio, document, live photo, photo, or video messages, or to add media to text messages. If a message is part of a message album, then it can be edited only to an audio for audio albums, only to a document for document albums and to a photo, a live photo, or a video otherwise. When an inline message is edited, a new file can't be uploaded; use a previously uploaded file via its file_id or specify a URL. On success, if the edited message is not an inline message, the edited Message is returned, otherwise True is returned. Note that business messages that were not sent by the bot and do not contain an inline keyboard can only be edited within 48 hours from the time they were sent."""
        _payload = {
            "media": media,
            "business_connection_id": business_connection_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "inline_message_id": inline_message_id,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("editMessageMedia", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def edit_message_live_location(self, latitude: float, longitude: float, business_connection_id: Optional[str] = None, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None, live_period: Optional[int] = None, horizontal_accuracy: Optional[float] = None, heading: Optional[int] = None, proximity_alert_radius: Optional[int] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Message":
        """Use this method to edit live location messages. A location can be edited until its live_period expires or editing is explicitly disabled by a call to stopMessageLiveLocation . On success, if the edited message is not an inline message, the edited Message is returned, otherwise True is returned."""
        _payload = {
            "latitude": latitude,
            "longitude": longitude,
            "business_connection_id": business_connection_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "inline_message_id": inline_message_id,
            "live_period": live_period,
            "horizontal_accuracy": horizontal_accuracy,
            "heading": heading,
            "proximity_alert_radius": proximity_alert_radius,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("editMessageLiveLocation", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def stop_message_live_location(self, business_connection_id: Optional[str] = None, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> bool:
        """Use this method to stop updating a live location message before live_period expires. On success, if the message is not an inline message, the edited Message is returned, otherwise True is returned."""
        _payload = {
            "business_connection_id": business_connection_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "inline_message_id": inline_message_id,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("stopMessageLiveLocation", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def edit_message_checklist(self, business_connection_id: str, chat_id: Union[int, str], message_id: int, checklist: "InputChecklist", reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Message":
        """Use this method to edit a checklist on behalf of a connected business account. On success, the edited Message is returned."""
        _payload = {
            "business_connection_id": business_connection_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "checklist": checklist,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("editMessageChecklist", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def edit_message_reply_markup(self, business_connection_id: Optional[str] = None, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Message":
        """Use this method to edit only the reply markup of messages. On success, if the edited message is not an inline message, the edited Message is returned, otherwise True is returned. Note that business messages that were not sent by the bot and do not contain an inline keyboard can only be edited within 48 hours from the time they were sent."""
        _payload = {
            "business_connection_id": business_connection_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "inline_message_id": inline_message_id,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("editMessageReplyMarkup", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def stop_poll(self, chat_id: Union[int, str], message_id: int, business_connection_id: Optional[str] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Poll":
        """Use this method to stop a poll which was sent by the bot. On success, the stopped Poll is returned."""
        _payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "business_connection_id": business_connection_id,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("stopPoll", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Poll', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def approve_suggested_post(self, chat_id: int, message_id: int, send_date: Optional[int] = None) -> "Message":
        """Use this method to approve a suggested post in a direct messages chat. The bot must have the 'can_post_messages' administrator right in the corresponding channel chat. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "send_date": send_date,
        }
        _result = await self._arequest("approveSuggestedPost", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def decline_suggested_post(self, chat_id: int, message_id: int, comment: Optional[str] = None) -> bool:
        """Use this method to decline a suggested post in a direct messages chat. The bot must have the 'can_manage_direct_messages' administrator right in the corresponding channel chat. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "comment": comment,
        }
        _result = await self._arequest("declineSuggestedPost", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def delete_message(self, chat_id: Union[int, str], message_id: int) -> bool:
        """Use this method to delete a message, including service messages, with the following limitations: - A message can only be deleted if it was sent less than 48 hours ago. - Service messages about a supergroup, channel, or forum topic creation can't be deleted. - A dice message in a private chat can only be deleted if it was sent more than 24 hours ago. - Bots can delete outgoing messages in private chats, groups, and supergroups. - Bots can delete incoming messages in private chats. - Bots granted can_post_messages permissions can delete outgoing messages in channels. - If the bot is an administrator of a group, it can delete any message there. - If the bot has can_delete_messages administrator right in a supergroup or a channel, it can delete any message there. - If the bot has can_manage_direct_messages administrator right in a channel, it can delete any message in the corresponding direct messages chat. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_id": message_id,
        }
        _result = await self._arequest("deleteMessage", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def delete_messages(self, chat_id: Union[int, str], message_ids: List[int]) -> bool:
        """Use this method to delete multiple messages simultaneously. If some of the specified messages can't be found, they are skipped. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_ids": message_ids,
        }
        _result = await self._arequest("deleteMessages", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def delete_message_reaction(self, chat_id: Union[int, str], message_id: int, user_id: Optional[int] = None, actor_chat_id: Optional[int] = None) -> bool:
        """Use this method to remove a reaction from a message in a group or a supergroup chat. The bot must have the 'can_delete_messages' administrator right in the chat. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "user_id": user_id,
            "actor_chat_id": actor_chat_id,
        }
        _result = await self._arequest("deleteMessageReaction", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def delete_all_message_reactions(self, chat_id: Union[int, str], user_id: Optional[int] = None, actor_chat_id: Optional[int] = None) -> bool:
        """Use this method to remove up to 10000 recent reactions in a group or a supergroup chat added by a given user or chat. The bot must have the 'can_delete_messages' administrator right in the chat. Returns True on success."""
        _payload = {
            "chat_id": chat_id,
            "user_id": user_id,
            "actor_chat_id": actor_chat_id,
        }
        _result = await self._arequest("deleteAllMessageReactions", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_sticker(self, chat_id: Union[int, str], sticker: Union[Union[str, InputFile], str], business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, emoji: Optional[str] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"]] = None) -> "Message":
        """Use this method to send static .WEBP, animated .TGS, or video .WEBM stickers. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "sticker": sticker,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "emoji": emoji,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("sendSticker", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_sticker_set(self, name: str) -> "StickerSet":
        """Use this method to get a sticker set. On success, a StickerSet object is returned."""
        _payload = {
            "name": name,
        }
        _result = await self._arequest("getStickerSet", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'StickerSet', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_custom_emoji_stickers(self, custom_emoji_ids: List[str]) -> List["Sticker"]:
        """Use this method to get information about custom emoji stickers by their identifiers. Returns an Array of Sticker objects."""
        _payload = {
            "custom_emoji_ids": custom_emoji_ids,
        }
        _result = await self._arequest("getCustomEmojiStickers", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'Sticker', "list_depth": 1})


    async def upload_sticker_file(self, user_id: int, sticker: Union[str, InputFile], sticker_format: str) -> "File":
        """Use this method to upload a file with a sticker for later use in the createNewStickerSet , addStickerToSet , or replaceStickerInSet methods (the file can be used multiple times). Returns the uploaded File on success."""
        _payload = {
            "user_id": user_id,
            "sticker": sticker,
            "sticker_format": sticker_format,
        }
        _result = await self._arequest("uploadStickerFile", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'File', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def create_new_sticker_set(self, user_id: int, name: str, title: str, stickers: List["InputSticker"], sticker_type: Optional[str] = None, needs_repainting: Optional[bool] = None) -> bool:
        """Use this method to create a new sticker set owned by a user. The bot will be able to edit the sticker set thus created. Returns True on success."""
        _payload = {
            "user_id": user_id,
            "name": name,
            "title": title,
            "stickers": stickers,
            "sticker_type": sticker_type,
            "needs_repainting": needs_repainting,
        }
        _result = await self._arequest("createNewStickerSet", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def add_sticker_to_set(self, user_id: int, name: str, sticker: "InputSticker") -> bool:
        """Use this method to add a new sticker to a set created by the bot. Emoji sticker sets can have up to 200 stickers. Other sticker sets can have up to 120 stickers. Returns True on success."""
        _payload = {
            "user_id": user_id,
            "name": name,
            "sticker": sticker,
        }
        _result = await self._arequest("addStickerToSet", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_sticker_position_in_set(self, sticker: str, position: int) -> bool:
        """Use this method to move a sticker in a set created by the bot to a specific position. Returns True on success."""
        _payload = {
            "sticker": sticker,
            "position": position,
        }
        _result = await self._arequest("setStickerPositionInSet", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def delete_sticker_from_set(self, sticker: str) -> bool:
        """Use this method to delete a sticker from a set created by the bot. Returns True on success."""
        _payload = {
            "sticker": sticker,
        }
        _result = await self._arequest("deleteStickerFromSet", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def replace_sticker_in_set(self, user_id: int, name: str, old_sticker: str, sticker: "InputSticker") -> bool:
        """Use this method to replace an existing sticker in a sticker set with a new one. The method is equivalent to calling deleteStickerFromSet , then addStickerToSet , then setStickerPositionInSet . Returns True on success."""
        _payload = {
            "user_id": user_id,
            "name": name,
            "old_sticker": old_sticker,
            "sticker": sticker,
        }
        _result = await self._arequest("replaceStickerInSet", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_sticker_emoji_list(self, sticker: str, emoji_list: List[str]) -> bool:
        """Use this method to change the list of emoji assigned to a regular or custom emoji sticker. The sticker must belong to a sticker set created by the bot. Returns True on success."""
        _payload = {
            "sticker": sticker,
            "emoji_list": emoji_list,
        }
        _result = await self._arequest("setStickerEmojiList", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_sticker_keywords(self, sticker: str, keywords: Optional[List[str]] = None) -> bool:
        """Use this method to change search keywords assigned to a regular or custom emoji sticker. The sticker must belong to a sticker set created by the bot. Returns True on success."""
        _payload = {
            "sticker": sticker,
            "keywords": keywords,
        }
        _result = await self._arequest("setStickerKeywords", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_sticker_mask_position(self, sticker: str, mask_position: Optional["MaskPosition"] = None) -> bool:
        """Use this method to change the mask position of a mask sticker. The sticker must belong to a sticker set that was created by the bot. Returns True on success."""
        _payload = {
            "sticker": sticker,
            "mask_position": mask_position,
        }
        _result = await self._arequest("setStickerMaskPosition", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_sticker_set_title(self, name: str, title: str) -> bool:
        """Use this method to set the title of a created sticker set. Returns True on success."""
        _payload = {
            "name": name,
            "title": title,
        }
        _result = await self._arequest("setStickerSetTitle", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_sticker_set_thumbnail(self, name: str, user_id: int, format: str, thumbnail: Optional[Union[Union[str, InputFile], str]] = None) -> bool:
        """Use this method to set the thumbnail of a regular or mask sticker set. The format of the thumbnail file must match the format of the stickers in the set. Returns True on success."""
        _payload = {
            "name": name,
            "user_id": user_id,
            "format": format,
            "thumbnail": thumbnail,
        }
        _result = await self._arequest("setStickerSetThumbnail", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_custom_emoji_sticker_set_thumbnail(self, name: str, custom_emoji_id: Optional[str] = None) -> bool:
        """Use this method to set the thumbnail of a custom emoji sticker set. Returns True on success."""
        _payload = {
            "name": name,
            "custom_emoji_id": custom_emoji_id,
        }
        _result = await self._arequest("setCustomEmojiStickerSetThumbnail", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def delete_sticker_set(self, name: str) -> bool:
        """Use this method to delete a sticker set that was created by the bot. Returns True on success."""
        _payload = {
            "name": name,
        }
        _result = await self._arequest("deleteStickerSet", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def answer_inline_query(self, inline_query_id: str, results: List["InlineQueryResult"], cache_time: Optional[int] = None, is_personal: Optional[bool] = None, next_offset: Optional[str] = None, button: Optional["InlineQueryResultsButton"] = None) -> bool:
        """Use this method to send answers to an inline query. On success, True is returned. No more than 50 results per query are allowed."""
        _payload = {
            "inline_query_id": inline_query_id,
            "results": results,
            "cache_time": cache_time,
            "is_personal": is_personal,
            "next_offset": next_offset,
            "button": button,
        }
        _result = await self._arequest("answerInlineQuery", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_invoice(self, chat_id: Union[int, str], title: str, description: str, payload: str, currency: str, prices: List["LabeledPrice"], message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, provider_token: Optional[str] = None, max_tip_amount: Optional[int] = None, suggested_tip_amounts: Optional[List[int]] = None, start_parameter: Optional[str] = None, provider_data: Optional[str] = None, photo_url: Optional[str] = None, photo_size: Optional[int] = None, photo_width: Optional[int] = None, photo_height: Optional[int] = None, need_name: Optional[bool] = None, need_phone_number: Optional[bool] = None, need_email: Optional[bool] = None, need_shipping_address: Optional[bool] = None, send_phone_number_to_provider: Optional[bool] = None, send_email_to_provider: Optional[bool] = None, is_flexible: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Message":
        """Use this method to send invoices. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "title": title,
            "description": description,
            "payload": payload,
            "currency": currency,
            "prices": prices,
            "message_thread_id": message_thread_id,
            "direct_messages_topic_id": direct_messages_topic_id,
            "provider_token": provider_token,
            "max_tip_amount": max_tip_amount,
            "suggested_tip_amounts": suggested_tip_amounts,
            "start_parameter": start_parameter,
            "provider_data": provider_data,
            "photo_url": photo_url,
            "photo_size": photo_size,
            "photo_width": photo_width,
            "photo_height": photo_height,
            "need_name": need_name,
            "need_phone_number": need_phone_number,
            "need_email": need_email,
            "need_shipping_address": need_shipping_address,
            "send_phone_number_to_provider": send_phone_number_to_provider,
            "send_email_to_provider": send_email_to_provider,
            "is_flexible": is_flexible,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "suggested_post_parameters": suggested_post_parameters,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("sendInvoice", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def create_invoice_link(self, title: str, description: str, payload: str, currency: str, prices: List["LabeledPrice"], business_connection_id: Optional[str] = None, provider_token: Optional[str] = None, subscription_period: Optional[int] = None, max_tip_amount: Optional[int] = None, suggested_tip_amounts: Optional[List[int]] = None, provider_data: Optional[str] = None, photo_url: Optional[str] = None, photo_size: Optional[int] = None, photo_width: Optional[int] = None, photo_height: Optional[int] = None, need_name: Optional[bool] = None, need_phone_number: Optional[bool] = None, need_email: Optional[bool] = None, need_shipping_address: Optional[bool] = None, send_phone_number_to_provider: Optional[bool] = None, send_email_to_provider: Optional[bool] = None, is_flexible: Optional[bool] = None) -> str:
        """Use this method to create a link for an invoice. Returns the created invoice link as String on success."""
        _payload = {
            "title": title,
            "description": description,
            "payload": payload,
            "currency": currency,
            "prices": prices,
            "business_connection_id": business_connection_id,
            "provider_token": provider_token,
            "subscription_period": subscription_period,
            "max_tip_amount": max_tip_amount,
            "suggested_tip_amounts": suggested_tip_amounts,
            "provider_data": provider_data,
            "photo_url": photo_url,
            "photo_size": photo_size,
            "photo_width": photo_width,
            "photo_height": photo_height,
            "need_name": need_name,
            "need_phone_number": need_phone_number,
            "need_email": need_email,
            "need_shipping_address": need_shipping_address,
            "send_phone_number_to_provider": send_phone_number_to_provider,
            "send_email_to_provider": send_email_to_provider,
            "is_flexible": is_flexible,
        }
        _result = await self._arequest("createInvoiceLink", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def answer_shipping_query(self, shipping_query_id: str, ok: bool, shipping_options: Optional[List["ShippingOption"]] = None, error_message: Optional[str] = None) -> bool:
        """If you sent an invoice requesting a shipping address and the parameter is_flexible was specified, the Bot API will send an Update with a shipping_query field to the bot. Use this method to reply to shipping queries. On success, True is returned."""
        _payload = {
            "shipping_query_id": shipping_query_id,
            "ok": ok,
            "shipping_options": shipping_options,
            "error_message": error_message,
        }
        _result = await self._arequest("answerShippingQuery", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def answer_pre_checkout_query(self, pre_checkout_query_id: str, ok: bool, error_message: Optional[str] = None) -> bool:
        """Once the user has confirmed their payment and shipping details, the Bot API sends the final confirmation in the form of an Update with the field pre_checkout_query . Use this method to respond to such pre-checkout queries. On success, True is returned. Note: The Bot API must receive an answer within 10 seconds after the pre-checkout query was sent."""
        _payload = {
            "pre_checkout_query_id": pre_checkout_query_id,
            "ok": ok,
            "error_message": error_message,
        }
        _result = await self._arequest("answerPreCheckoutQuery", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_my_star_balance(self) -> "StarAmount":
        """A method to get the current Telegram Stars balance of the bot. Requires no parameters. On success, returns a StarAmount object."""
        _payload = None
        _result = await self._arequest("getMyStarBalance", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'StarAmount', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_star_transactions(self, offset: Optional[int] = None, limit: Optional[int] = None) -> "StarTransactions":
        """Returns the bot's Telegram Star transactions in chronological order. On success, returns a StarTransactions object."""
        _payload = {
            "offset": offset,
            "limit": limit,
        }
        _result = await self._arequest("getStarTransactions", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'StarTransactions', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def refund_star_payment(self, user_id: int, telegram_payment_charge_id: str) -> bool:
        """Refunds a successful payment in Telegram Stars . Returns True on success."""
        _payload = {
            "user_id": user_id,
            "telegram_payment_charge_id": telegram_payment_charge_id,
        }
        _result = await self._arequest("refundStarPayment", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def edit_user_star_subscription(self, user_id: int, telegram_payment_charge_id: str, is_canceled: bool) -> bool:
        """Allows the bot to cancel or re-enable extension of a subscription paid in Telegram Stars. Returns True on success."""
        _payload = {
            "user_id": user_id,
            "telegram_payment_charge_id": telegram_payment_charge_id,
            "is_canceled": is_canceled,
        }
        _result = await self._arequest("editUserStarSubscription", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_passport_data_errors(self, user_id: int, errors: List["PassportElementError"]) -> bool:
        """Informs a user that some of the Telegram Passport elements they provided contains errors. The user will not be able to re-submit their Passport to you until the errors are fixed (the contents of the field for which you returned the error must change). Returns True on success."""
        _payload = {
            "user_id": user_id,
            "errors": errors,
        }
        _result = await self._arequest("setPassportDataErrors", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def send_game(self, chat_id: Union[int, str], game_short_name: str, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> "Message":
        """Use this method to send a game. On success, the sent Message is returned."""
        _payload = {
            "chat_id": chat_id,
            "game_short_name": game_short_name,
            "business_connection_id": business_connection_id,
            "message_thread_id": message_thread_id,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
            "message_effect_id": message_effect_id,
            "reply_parameters": reply_parameters,
            "reply_markup": reply_markup,
        }
        _result = await self._arequest("sendGame", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def set_game_score(self, user_id: int, score: int, force: Optional[bool] = None, disable_edit_message: Optional[bool] = None, chat_id: Optional[int] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None) -> "Message":
        """Use this method to set the score of the specified user in a game message. On success, if the message is not an inline message, the Message is returned, otherwise True is returned. Returns an error, if the new score is not greater than the user's current score in the chat and force is False ."""
        _payload = {
            "user_id": user_id,
            "score": score,
            "force": force,
            "disable_edit_message": disable_edit_message,
            "chat_id": chat_id,
            "message_id": message_id,
            "inline_message_id": inline_message_id,
        }
        _result = await self._arequest("setGameScore", _payload)
        return self._decode_result(_result, {"is_object": True, "inner_object": 'Message', "is_list": False, "list_inner_object": None, "list_depth": 0})


    async def get_game_high_scores(self, user_id: int, chat_id: Optional[int] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None) -> List["GameHighScore"]:
        """Use this method to get data for high score tables. Will return the score of the specified user and several of their neighbors in a game. Returns an Array of GameHighScore objects."""
        _payload = {
            "user_id": user_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "inline_message_id": inline_message_id,
        }
        _result = await self._arequest("getGameHighScores", _payload)
        return self._decode_result(_result, {"is_object": False, "inner_object": None, "is_list": True, "list_inner_object": 'GameHighScore', "list_depth": 1})


for _name in dir(_AsyncBotMethods):
    if _name.startswith('_'): continue
    setattr(AsyncBot, _name, getattr(_AsyncBotMethods, _name))
del _name
