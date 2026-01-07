# АВТОМАТИЧЕСКИ СГЕНЕРИРОВАННЫЙ ФАЙЛ
from __future__ import annotations
import requests
import json
from .ii import *
from dataclasses import dataclass, field
from typing import List, Optional, Union, Any, Dict, IO, get_type_hints

API_URL = "https://api.telegram.org/bot{token}/{method}"

def _deserialize(value: Any, type_hint: Any) -> Any:
    """Рекурсивно преобразует словари в объекты на основе Type Hint"""
    if value is None: return None
    
    origin = getattr(type_hint, "__origin__", None)
    args = getattr(type_hint, "__args__", [])
    
    if origin is list:
        return [_deserialize(item, args[0]) for item in value]
        
    if origin is Union:
        for arg in args:
            if isinstance(arg, type) and issubclass(arg, TelegramObject) and isinstance(value, dict):
                try:
                    return arg.from_dict(value)
                except:
                    continue
            if getattr(arg, "__origin__", None) is list and isinstance(value, list):
                return _deserialize(value, arg)
    
    if isinstance(type_hint, type) and issubclass(type_hint, TelegramObject) and isinstance(value, dict):
        return type_hint.from_dict(value)
        
    return value

def _clean_obj(obj: Any) -> Any:
    """Очищает объект от None и сериализует вложенные структуры"""
    if isinstance(obj, list):
        return [_clean_obj(x) for x in obj]
    if isinstance(obj, TelegramObject):
        return obj.to_dict()
    if isinstance(obj, dict):
        return {k: _clean_obj(v) for k, v in obj.items() if v is not None}
    return obj

class TelegramObject:
    def to_dict(self):
        result = {}
        for k, v in self.__dict__.items():
            if v is None: continue
            if k == "from_user": k = "from"
            elif k == "type_val": k = "type"
            elif k == "filter_val": k = "filter"
            result[k] = _clean_obj(v)
        return result

    @classmethod
    def from_dict(cls, data: Any):
        if isinstance(data, list):
            return [cls.from_dict(item) for item in data]
        if not isinstance(data, dict):
            return data
        try:
            hints = get_type_hints(cls, globals(), globals())
        except Exception:
            hints = {}
        init_args = {}
        valid_fields = cls.__dataclass_fields__
        for k, v in data.items():
            field_name = k
            if k == "from": field_name = "from_user"
            elif k == "type": field_name = "type_val"
            elif k == "filter": field_name = "filter_val"
            if field_name in valid_fields:
                if field_name in hints:
                    init_args[field_name] = _deserialize(v, hints[field_name])
                else:
                    init_args[field_name] = v
        return cls(**init_args)

class TelegramError(Exception):
    def __init__(self, method, result):
        self.method = method
        self.error_code = result.get('error_code')
        self.description = result.get('description')
        super().__init__(f"Error {self.error_code}: {self.description}")

def _serialize(obj: Any) -> Optional[str]:
    """Финишная сериализация в JSON-строку"""
    if obj is None: return None
    clean_data = _clean_obj(obj)
    return json.dumps(clean_data)

@dataclass
class Update(TelegramObject):
    update_id: int
    message: Optional["Message"] = None
    edited_message: Optional["Message"] = None
    channel_post: Optional["Message"] = None
    edited_channel_post: Optional["Message"] = None
    business_connection: Optional["BusinessConnection"] = None
    business_message: Optional["Message"] = None
    edited_business_message: Optional["Message"] = None
    deleted_business_messages: Optional["BusinessMessagesDeleted"] = None
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

@dataclass
class WebhookInfo(TelegramObject):
    url: str
    has_custom_certificate: bool
    pending_update_count: int
    ip_address: Optional[str] = None
    last_error_date: Optional[int] = None
    last_error_message: Optional[str] = None
    last_synchronization_error_date: Optional[int] = None
    max_connections: Optional[int] = None
    allowed_updates: Optional[List[str]] = None

@dataclass
class User(TelegramObject):
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
    supports_inline_queries: Optional[bool] = None
    can_connect_to_business: Optional[bool] = None
    has_main_web_app: Optional[bool] = None
    has_topics_enabled: Optional[bool] = None

@dataclass
class Chat(TelegramObject):
    id: int
    type_val: str
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_forum: Optional[bool] = None
    is_direct_messages: Optional[bool] = None

@dataclass
class ChatFullInfo(TelegramObject):
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
    available_reactions: Optional[List[Union["ReactionTypeEmoji", "ReactionTypeCustomEmoji", "ReactionTypePaid"]]] = None
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
    unique_gift_colors: Optional["UniqueGiftColors"] = None
    paid_message_star_count: Optional[int] = None

@dataclass
class Message(TelegramObject):
    message_id: int
    date: int
    chat: "Chat"
    message_thread_id: Optional[int] = None
    direct_messages_topic: Optional["DirectMessagesTopic"] = None
    from_user: Optional["User"] = None
    sender_chat: Optional["Chat"] = None
    sender_boost_count: Optional[int] = None
    sender_business_bot: Optional["User"] = None
    business_connection_id: Optional[str] = None
    forward_origin: Optional[Union["MessageOriginUser", "MessageOriginHiddenUser", "MessageOriginChat", "MessageOriginChannel"]] = None
    is_topic_message: Optional[bool] = None
    is_automatic_forward: Optional[bool] = None
    reply_to_message: Optional["Message"] = None
    external_reply: Optional["ExternalReplyInfo"] = None
    quote: Optional["TextQuote"] = None
    reply_to_story: Optional["Story"] = None
    reply_to_checklist_task_id: Optional[int] = None
    via_bot: Optional["User"] = None
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
    new_chat_title: Optional[str] = None
    new_chat_photo: Optional[List["PhotoSize"]] = None
    delete_chat_photo: Optional[bool] = None
    group_chat_created: Optional[bool] = None
    supergroup_chat_created: Optional[bool] = None
    channel_chat_created: Optional[bool] = None
    message_auto_delete_timer_changed: Optional["MessageAutoDeleteTimerChanged"] = None
    migrate_to_chat_id: Optional[int] = None
    migrate_from_chat_id: Optional[int] = None
    pinned_message: Optional[Union["Message", "InaccessibleMessage"]] = None
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
    paid_message_price_changed: Optional["PaidMessagePriceChanged"] = None
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

@dataclass
class MessageId(TelegramObject):
    message_id: int

@dataclass
class InaccessibleMessage(TelegramObject):
    chat: "Chat"
    message_id: int
    date: int

@dataclass
class MaybeInaccessibleMessage(TelegramObject):
    pass

@dataclass
class MessageEntity(TelegramObject):
    type_val: str
    offset: int
    length: int
    url: Optional[str] = None
    user: Optional["User"] = None
    language: Optional[str] = None
    custom_emoji_id: Optional[str] = None

@dataclass
class TextQuote(TelegramObject):
    text: str
    position: int
    entities: Optional[List["MessageEntity"]] = None
    is_manual: Optional[bool] = None

@dataclass
class ExternalReplyInfo(TelegramObject):
    origin: Union["MessageOriginUser", "MessageOriginHiddenUser", "MessageOriginChat", "MessageOriginChannel"]
    chat: Optional["Chat"] = None
    message_id: Optional[int] = None
    link_preview_options: Optional["LinkPreviewOptions"] = None
    animation: Optional["Animation"] = None
    audio: Optional["Audio"] = None
    document: Optional["Document"] = None
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

@dataclass
class ReplyParameters(TelegramObject):
    message_id: int
    chat_id: Optional[Union[int, str]] = None
    allow_sending_without_reply: Optional[bool] = None
    quote: Optional[str] = None
    quote_parse_mode: Optional[str] = None
    quote_entities: Optional[List["MessageEntity"]] = None
    quote_position: Optional[int] = None
    checklist_task_id: Optional[int] = None

@dataclass
class MessageOrigin(TelegramObject):
    pass

@dataclass
class MessageOriginUser(TelegramObject):
    type_val: str
    date: int
    sender_user: "User"

@dataclass
class MessageOriginHiddenUser(TelegramObject):
    type_val: str
    date: int
    sender_user_name: str

@dataclass
class MessageOriginChat(TelegramObject):
    type_val: str
    date: int
    sender_chat: "Chat"
    author_signature: Optional[str] = None

@dataclass
class MessageOriginChannel(TelegramObject):
    type_val: str
    date: int
    chat: "Chat"
    message_id: int
    author_signature: Optional[str] = None

@dataclass
class PhotoSize(TelegramObject):
    file_id: str
    file_unique_id: str
    width: int
    height: int
    file_size: Optional[int] = None

@dataclass
class Animation(TelegramObject):
    file_id: str
    file_unique_id: str
    width: int
    height: int
    duration: int
    thumbnail: Optional["PhotoSize"] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None

@dataclass
class Audio(TelegramObject):
    file_id: str
    file_unique_id: str
    duration: int
    performer: Optional[str] = None
    title: Optional[str] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    thumbnail: Optional["PhotoSize"] = None

@dataclass
class Document(TelegramObject):
    file_id: str
    file_unique_id: str
    thumbnail: Optional["PhotoSize"] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None

@dataclass
class Story(TelegramObject):
    chat: "Chat"
    id: int

@dataclass
class Video(TelegramObject):
    file_id: str
    file_unique_id: str
    width: int
    height: int
    duration: int
    thumbnail: Optional["PhotoSize"] = None
    cover: Optional[List["PhotoSize"]] = None
    start_timestamp: Optional[int] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None

@dataclass
class VideoNote(TelegramObject):
    file_id: str
    file_unique_id: str
    length: int
    duration: int
    thumbnail: Optional["PhotoSize"] = None
    file_size: Optional[int] = None

@dataclass
class Voice(TelegramObject):
    file_id: str
    file_unique_id: str
    duration: int
    mime_type: Optional[str] = None
    file_size: Optional[int] = None

@dataclass
class PaidMediaInfo(TelegramObject):
    star_count: int
    paid_media: List["PaidMedia"]

@dataclass
class PaidMedia(TelegramObject):
    pass

@dataclass
class PaidMediaPreview(TelegramObject):
    type_val: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[int] = None

@dataclass
class PaidMediaPhoto(TelegramObject):
    type_val: str
    photo: List["PhotoSize"]

@dataclass
class PaidMediaVideo(TelegramObject):
    type_val: str
    video: "Video"

@dataclass
class Contact(TelegramObject):
    phone_number: str
    first_name: str
    last_name: Optional[str] = None
    user_id: Optional[int] = None
    vcard: Optional[str] = None

@dataclass
class Dice(TelegramObject):
    emoji: str
    value: int

@dataclass
class PollOption(TelegramObject):
    text: str
    voter_count: int
    text_entities: Optional[List["MessageEntity"]] = None

@dataclass
class InputPollOption(TelegramObject):
    text: str
    text_parse_mode: Optional[str] = None
    text_entities: Optional[List["MessageEntity"]] = None

@dataclass
class PollAnswer(TelegramObject):
    poll_id: str
    option_ids: List[int]
    voter_chat: Optional["Chat"] = None
    user: Optional["User"] = None

@dataclass
class Poll(TelegramObject):
    id: str
    question: str
    options: List["PollOption"]
    total_voter_count: int
    is_closed: bool
    is_anonymous: bool
    type_val: str
    allows_multiple_answers: bool
    question_entities: Optional[List["MessageEntity"]] = None
    correct_option_id: Optional[int] = None
    explanation: Optional[str] = None
    explanation_entities: Optional[List["MessageEntity"]] = None
    open_period: Optional[int] = None
    close_date: Optional[int] = None

@dataclass
class ChecklistTask(TelegramObject):
    id: int
    text: str
    text_entities: Optional[List["MessageEntity"]] = None
    completed_by_user: Optional["User"] = None
    completed_by_chat: Optional["Chat"] = None
    completion_date: Optional[int] = None

@dataclass
class Checklist(TelegramObject):
    title: str
    tasks: List["ChecklistTask"]
    title_entities: Optional[List["MessageEntity"]] = None
    others_can_add_tasks: Optional[bool] = None
    others_can_mark_tasks_as_done: Optional[bool] = None

@dataclass
class InputChecklistTask(TelegramObject):
    id: int
    text: str
    parse_mode: Optional[str] = None
    text_entities: Optional[List["MessageEntity"]] = None

@dataclass
class InputChecklist(TelegramObject):
    title: str
    tasks: List["InputChecklistTask"]
    parse_mode: Optional[str] = None
    title_entities: Optional[List["MessageEntity"]] = None
    others_can_add_tasks: Optional[bool] = None
    others_can_mark_tasks_as_done: Optional[bool] = None

@dataclass
class ChecklistTasksDone(TelegramObject):
    checklist_message: Optional["Message"] = None
    marked_as_done_task_ids: Optional[List[int]] = None
    marked_as_not_done_task_ids: Optional[List[int]] = None

@dataclass
class ChecklistTasksAdded(TelegramObject):
    tasks: List["ChecklistTask"]
    checklist_message: Optional["Message"] = None

@dataclass
class Location(TelegramObject):
    latitude: float
    longitude: float
    horizontal_accuracy: Optional[float] = None
    live_period: Optional[int] = None
    heading: Optional[int] = None
    proximity_alert_radius: Optional[int] = None

@dataclass
class Venue(TelegramObject):
    location: "Location"
    title: str
    address: str
    foursquare_id: Optional[str] = None
    foursquare_type: Optional[str] = None
    google_place_id: Optional[str] = None
    google_place_type: Optional[str] = None

@dataclass
class WebAppData(TelegramObject):
    data: str
    button_text: str

@dataclass
class ProximityAlertTriggered(TelegramObject):
    traveler: "User"
    watcher: "User"
    distance: int

@dataclass
class MessageAutoDeleteTimerChanged(TelegramObject):
    message_auto_delete_time: int

@dataclass
class ChatBoostAdded(TelegramObject):
    boost_count: int

@dataclass
class BackgroundFill(TelegramObject):
    pass

@dataclass
class BackgroundFillSolid(TelegramObject):
    type_val: str
    color: int

@dataclass
class BackgroundFillGradient(TelegramObject):
    type_val: str
    top_color: int
    bottom_color: int
    rotation_angle: int

@dataclass
class BackgroundFillFreeformGradient(TelegramObject):
    type_val: str
    colors: List[int]

@dataclass
class BackgroundType(TelegramObject):
    pass

@dataclass
class BackgroundTypeFill(TelegramObject):
    type_val: str
    fill: Union["BackgroundFillSolid", "BackgroundFillGradient", "BackgroundFillFreeformGradient"]
    dark_theme_dimming: int

@dataclass
class BackgroundTypeWallpaper(TelegramObject):
    type_val: str
    document: "Document"
    dark_theme_dimming: int
    is_blurred: Optional[bool] = None
    is_moving: Optional[bool] = None

@dataclass
class BackgroundTypePattern(TelegramObject):
    type_val: str
    document: "Document"
    fill: Union["BackgroundFillSolid", "BackgroundFillGradient", "BackgroundFillFreeformGradient"]
    intensity: int
    is_inverted: Optional[bool] = None
    is_moving: Optional[bool] = None

@dataclass
class BackgroundTypeChatTheme(TelegramObject):
    type_val: str
    theme_name: str

@dataclass
class ChatBackground(TelegramObject):
    type_val: Union["BackgroundTypeFill", "BackgroundTypeWallpaper", "BackgroundTypePattern", "BackgroundTypeChatTheme"]

@dataclass
class ForumTopicCreated(TelegramObject):
    name: str
    icon_color: int
    icon_custom_emoji_id: Optional[str] = None
    is_name_implicit: Optional[bool] = None

@dataclass
class ForumTopicClosed(TelegramObject):
    pass

@dataclass
class ForumTopicEdited(TelegramObject):
    name: Optional[str] = None
    icon_custom_emoji_id: Optional[str] = None

@dataclass
class ForumTopicReopened(TelegramObject):
    pass

@dataclass
class GeneralForumTopicHidden(TelegramObject):
    pass

@dataclass
class GeneralForumTopicUnhidden(TelegramObject):
    pass

@dataclass
class SharedUser(TelegramObject):
    user_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo: Optional[List["PhotoSize"]] = None

@dataclass
class UsersShared(TelegramObject):
    request_id: int
    users: List["SharedUser"]

@dataclass
class ChatShared(TelegramObject):
    request_id: int
    chat_id: int
    title: Optional[str] = None
    username: Optional[str] = None
    photo: Optional[List["PhotoSize"]] = None

@dataclass
class WriteAccessAllowed(TelegramObject):
    from_request: Optional[bool] = None
    web_app_name: Optional[str] = None
    from_attachment_menu: Optional[bool] = None

@dataclass
class VideoChatScheduled(TelegramObject):
    start_date: int

@dataclass
class VideoChatStarted(TelegramObject):
    pass

@dataclass
class VideoChatEnded(TelegramObject):
    duration: int

@dataclass
class VideoChatParticipantsInvited(TelegramObject):
    users: List["User"]

@dataclass
class PaidMessagePriceChanged(TelegramObject):
    paid_message_star_count: int

@dataclass
class DirectMessagePriceChanged(TelegramObject):
    are_direct_messages_enabled: bool
    direct_message_star_count: Optional[int] = None

@dataclass
class SuggestedPostApproved(TelegramObject):
    send_date: int
    suggested_post_message: Optional["Message"] = None
    price: Optional["SuggestedPostPrice"] = None

@dataclass
class SuggestedPostApprovalFailed(TelegramObject):
    price: "SuggestedPostPrice"
    suggested_post_message: Optional["Message"] = None

@dataclass
class SuggestedPostDeclined(TelegramObject):
    suggested_post_message: Optional["Message"] = None
    comment: Optional[str] = None

@dataclass
class SuggestedPostPaid(TelegramObject):
    currency: str
    suggested_post_message: Optional["Message"] = None
    amount: Optional[int] = None
    star_amount: Optional["StarAmount"] = None

@dataclass
class SuggestedPostRefunded(TelegramObject):
    reason: str
    suggested_post_message: Optional["Message"] = None

@dataclass
class GiveawayCreated(TelegramObject):
    prize_star_count: Optional[int] = None

@dataclass
class Giveaway(TelegramObject):
    chats: List["Chat"]
    winners_selection_date: int
    winner_count: int
    only_new_members: Optional[bool] = None
    has_public_winners: Optional[bool] = None
    prize_description: Optional[str] = None
    country_codes: Optional[List[str]] = None
    prize_star_count: Optional[int] = None
    premium_subscription_month_count: Optional[int] = None

@dataclass
class GiveawayWinners(TelegramObject):
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

@dataclass
class GiveawayCompleted(TelegramObject):
    winner_count: int
    unclaimed_prize_count: Optional[int] = None
    giveaway_message: Optional["Message"] = None
    is_star_giveaway: Optional[bool] = None

@dataclass
class LinkPreviewOptions(TelegramObject):
    is_disabled: Optional[bool] = None
    url: Optional[str] = None
    prefer_small_media: Optional[bool] = None
    prefer_large_media: Optional[bool] = None
    show_above_text: Optional[bool] = None

@dataclass
class SuggestedPostPrice(TelegramObject):
    currency: str
    amount: int

@dataclass
class SuggestedPostInfo(TelegramObject):
    state: str
    price: Optional["SuggestedPostPrice"] = None
    send_date: Optional[int] = None

@dataclass
class SuggestedPostParameters(TelegramObject):
    price: Optional["SuggestedPostPrice"] = None
    send_date: Optional[int] = None

@dataclass
class DirectMessagesTopic(TelegramObject):
    topic_id: int
    user: Optional["User"] = None

@dataclass
class UserProfilePhotos(TelegramObject):
    total_count: int
    photos: List[List["PhotoSize"]]

@dataclass
class File(TelegramObject):
    file_id: str
    file_unique_id: str
    file_size: Optional[int] = None
    file_path: Optional[str] = None

@dataclass
class WebAppInfo(TelegramObject):
    url: str

@dataclass
class ReplyKeyboardMarkup(TelegramObject):
    keyboard: List[List["KeyboardButton"]]
    is_persistent: Optional[bool] = None
    resize_keyboard: Optional[bool] = None
    one_time_keyboard: Optional[bool] = None
    input_field_placeholder: Optional[str] = None
    selective: Optional[bool] = None

@dataclass
class KeyboardButton(TelegramObject):
    text: str
    request_users: Optional["KeyboardButtonRequestUsers"] = None
    request_chat: Optional["KeyboardButtonRequestChat"] = None
    request_contact: Optional[bool] = None
    request_location: Optional[bool] = None
    request_poll: Optional["KeyboardButtonPollType"] = None
    web_app: Optional["WebAppInfo"] = None

@dataclass
class KeyboardButtonRequestUsers(TelegramObject):
    request_id: int
    user_is_bot: Optional[bool] = None
    user_is_premium: Optional[bool] = None
    max_quantity: Optional[int] = None
    request_name: Optional[bool] = None
    request_username: Optional[bool] = None
    request_photo: Optional[bool] = None

@dataclass
class KeyboardButtonRequestChat(TelegramObject):
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

@dataclass
class KeyboardButtonPollType(TelegramObject):
    type_val: Optional[str] = None

@dataclass
class ReplyKeyboardRemove(TelegramObject):
    remove_keyboard: bool
    selective: Optional[bool] = None

@dataclass
class InlineKeyboardMarkup(TelegramObject):
    inline_keyboard: List[List["InlineKeyboardButton"]]

@dataclass
class InlineKeyboardButton(TelegramObject):
    text: str
    url: Optional[str] = None
    callback_data: Optional[str] = None
    web_app: Optional["WebAppInfo"] = None
    login_url: Optional["LoginUrl"] = None
    switch_inline_query: Optional[str] = None
    switch_inline_query_current_chat: Optional[str] = None
    switch_inline_query_chosen_chat: Optional["SwitchInlineQueryChosenChat"] = None
    copy_text: Optional["CopyTextButton"] = None
    callback_game: Optional[Dict] = None
    pay: Optional[bool] = None

@dataclass
class LoginUrl(TelegramObject):
    url: str
    forward_text: Optional[str] = None
    bot_username: Optional[str] = None
    request_write_access: Optional[bool] = None

@dataclass
class SwitchInlineQueryChosenChat(TelegramObject):
    query: Optional[str] = None
    allow_user_chats: Optional[bool] = None
    allow_bot_chats: Optional[bool] = None
    allow_group_chats: Optional[bool] = None
    allow_channel_chats: Optional[bool] = None

@dataclass
class CopyTextButton(TelegramObject):
    text: str

@dataclass
class CallbackQuery(TelegramObject):
    id: str
    from_user: "User"
    chat_instance: str
    message: Optional[Union["Message", "InaccessibleMessage"]] = None
    inline_message_id: Optional[str] = None
    data: Optional[str] = None
    game_short_name: Optional[str] = None

@dataclass
class ForceReply(TelegramObject):
    force_reply: bool
    input_field_placeholder: Optional[str] = None
    selective: Optional[bool] = None

@dataclass
class ChatPhoto(TelegramObject):
    small_file_id: str
    small_file_unique_id: str
    big_file_id: str
    big_file_unique_id: str

@dataclass
class ChatInviteLink(TelegramObject):
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

@dataclass
class ChatAdministratorRights(TelegramObject):
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

@dataclass
class ChatMemberUpdated(TelegramObject):
    chat: "Chat"
    from_user: "User"
    date: int
    old_chat_member: Union["ChatMemberOwner", "ChatMemberAdministrator", "ChatMemberMember", "ChatMemberRestricted", "ChatMemberLeft", "ChatMemberBanned"]
    new_chat_member: Union["ChatMemberOwner", "ChatMemberAdministrator", "ChatMemberMember", "ChatMemberRestricted", "ChatMemberLeft", "ChatMemberBanned"]
    invite_link: Optional["ChatInviteLink"] = None
    via_join_request: Optional[bool] = None
    via_chat_folder_invite_link: Optional[bool] = None

@dataclass
class ChatMember(TelegramObject):
    pass

@dataclass
class ChatMemberOwner(TelegramObject):
    status: str
    user: "User"
    is_anonymous: bool
    custom_title: Optional[str] = None

@dataclass
class ChatMemberAdministrator(TelegramObject):
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
    custom_title: Optional[str] = None

@dataclass
class ChatMemberMember(TelegramObject):
    status: str
    user: "User"
    until_date: Optional[int] = None

@dataclass
class ChatMemberRestricted(TelegramObject):
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
    can_change_info: bool
    can_invite_users: bool
    can_pin_messages: bool
    can_manage_topics: bool
    until_date: int

@dataclass
class ChatMemberLeft(TelegramObject):
    status: str
    user: "User"

@dataclass
class ChatMemberBanned(TelegramObject):
    status: str
    user: "User"
    until_date: int

@dataclass
class ChatJoinRequest(TelegramObject):
    chat: "Chat"
    from_user: "User"
    user_chat_id: int
    date: int
    bio: Optional[str] = None
    invite_link: Optional["ChatInviteLink"] = None

@dataclass
class ChatPermissions(TelegramObject):
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
    can_change_info: Optional[bool] = None
    can_invite_users: Optional[bool] = None
    can_pin_messages: Optional[bool] = None
    can_manage_topics: Optional[bool] = None

@dataclass
class Birthdate(TelegramObject):
    day: int
    month: int
    year: Optional[int] = None

@dataclass
class BusinessIntro(TelegramObject):
    title: Optional[str] = None
    message: Optional[str] = None
    sticker: Optional["Sticker"] = None

@dataclass
class BusinessLocation(TelegramObject):
    address: str
    location: Optional["Location"] = None

@dataclass
class BusinessOpeningHoursInterval(TelegramObject):
    opening_minute: int
    closing_minute: int

@dataclass
class BusinessOpeningHours(TelegramObject):
    time_zone_name: str
    opening_hours: List["BusinessOpeningHoursInterval"]

@dataclass
class UserRating(TelegramObject):
    level: int
    rating: int
    current_level_rating: int
    next_level_rating: Optional[int] = None

@dataclass
class StoryAreaPosition(TelegramObject):
    x_percentage: float
    y_percentage: float
    width_percentage: float
    height_percentage: float
    rotation_angle: float
    corner_radius_percentage: float

@dataclass
class LocationAddress(TelegramObject):
    country_code: str
    state: Optional[str] = None
    city: Optional[str] = None
    street: Optional[str] = None

@dataclass
class StoryAreaType(TelegramObject):
    pass

@dataclass
class StoryAreaTypeLocation(TelegramObject):
    type_val: str
    latitude: float
    longitude: float
    address: Optional["LocationAddress"] = None

@dataclass
class StoryAreaTypeSuggestedReaction(TelegramObject):
    type_val: str
    reaction_type: Union["ReactionTypeEmoji", "ReactionTypeCustomEmoji", "ReactionTypePaid"]
    is_dark: Optional[bool] = None
    is_flipped: Optional[bool] = None

@dataclass
class StoryAreaTypeLink(TelegramObject):
    type_val: str
    url: str

@dataclass
class StoryAreaTypeWeather(TelegramObject):
    type_val: str
    temperature: float
    emoji: str
    background_color: int

@dataclass
class StoryAreaTypeUniqueGift(TelegramObject):
    type_val: str
    name: str

@dataclass
class StoryArea(TelegramObject):
    position: "StoryAreaPosition"
    type_val: "StoryAreaType"

@dataclass
class ChatLocation(TelegramObject):
    location: "Location"
    address: str

@dataclass
class ReactionType(TelegramObject):
    pass

@dataclass
class ReactionTypeEmoji(TelegramObject):
    type_val: str
    emoji: str

@dataclass
class ReactionTypeCustomEmoji(TelegramObject):
    type_val: str
    custom_emoji_id: str

@dataclass
class ReactionTypePaid(TelegramObject):
    type_val: str

@dataclass
class ReactionCount(TelegramObject):
    type_val: Union["ReactionTypeEmoji", "ReactionTypeCustomEmoji", "ReactionTypePaid"]
    total_count: int

@dataclass
class MessageReactionUpdated(TelegramObject):
    chat: "Chat"
    message_id: int
    date: int
    old_reaction: List[Union["ReactionTypeEmoji", "ReactionTypeCustomEmoji", "ReactionTypePaid"]]
    new_reaction: List[Union["ReactionTypeEmoji", "ReactionTypeCustomEmoji", "ReactionTypePaid"]]
    user: Optional["User"] = None
    actor_chat: Optional["Chat"] = None

@dataclass
class MessageReactionCountUpdated(TelegramObject):
    chat: "Chat"
    message_id: int
    date: int
    reactions: List["ReactionCount"]

@dataclass
class ForumTopic(TelegramObject):
    message_thread_id: int
    name: str
    icon_color: int
    icon_custom_emoji_id: Optional[str] = None
    is_name_implicit: Optional[bool] = None

@dataclass
class GiftBackground(TelegramObject):
    center_color: int
    edge_color: int
    text_color: int

@dataclass
class Gift(TelegramObject):
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

@dataclass
class Gifts(TelegramObject):
    gifts: List["Gift"]

@dataclass
class UniqueGiftModel(TelegramObject):
    name: str
    sticker: "Sticker"
    rarity_per_mille: int

@dataclass
class UniqueGiftSymbol(TelegramObject):
    name: str
    sticker: "Sticker"
    rarity_per_mille: int

@dataclass
class UniqueGiftBackdropColors(TelegramObject):
    center_color: int
    edge_color: int
    symbol_color: int
    text_color: int

@dataclass
class UniqueGiftBackdrop(TelegramObject):
    name: str
    colors: "UniqueGiftBackdropColors"
    rarity_per_mille: int

@dataclass
class UniqueGiftColors(TelegramObject):
    model_custom_emoji_id: str
    symbol_custom_emoji_id: str
    light_theme_main_color: int
    light_theme_other_colors: List[int]
    dark_theme_main_color: int
    dark_theme_other_colors: List[int]

@dataclass
class UniqueGift(TelegramObject):
    gift_id: str
    base_name: str
    name: str
    number: int
    model: "UniqueGiftModel"
    symbol: "UniqueGiftSymbol"
    backdrop: "UniqueGiftBackdrop"
    is_premium: Optional[bool] = None
    is_from_blockchain: Optional[bool] = None
    colors: Optional["UniqueGiftColors"] = None
    publisher_chat: Optional["Chat"] = None

@dataclass
class GiftInfo(TelegramObject):
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

@dataclass
class UniqueGiftInfo(TelegramObject):
    gift: "UniqueGift"
    origin: str
    last_resale_currency: Optional[str] = None
    last_resale_amount: Optional[int] = None
    owned_gift_id: Optional[str] = None
    transfer_star_count: Optional[int] = None
    next_transfer_date: Optional[int] = None

@dataclass
class OwnedGift(TelegramObject):
    pass

@dataclass
class OwnedGiftRegular(TelegramObject):
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

@dataclass
class OwnedGiftUnique(TelegramObject):
    type_val: str
    gift: "UniqueGift"
    send_date: int
    owned_gift_id: Optional[str] = None
    sender_user: Optional["User"] = None
    is_saved: Optional[bool] = None
    can_be_transferred: Optional[bool] = None
    transfer_star_count: Optional[int] = None
    next_transfer_date: Optional[int] = None

@dataclass
class OwnedGifts(TelegramObject):
    total_count: int
    gifts: List["OwnedGift"]
    next_offset: Optional[str] = None

@dataclass
class AcceptedGiftTypes(TelegramObject):
    unlimited_gifts: bool
    limited_gifts: bool
    unique_gifts: bool
    premium_subscription: bool
    gifts_from_channels: bool

@dataclass
class StarAmount(TelegramObject):
    amount: int
    nanostar_amount: Optional[int] = None

@dataclass
class BotCommand(TelegramObject):
    command: str
    description: str

@dataclass
class BotCommandScope(TelegramObject):
    pass

@dataclass
class BotCommandScopeDefault(TelegramObject):
    type_val: str

@dataclass
class BotCommandScopeAllPrivateChats(TelegramObject):
    type_val: str

@dataclass
class BotCommandScopeAllGroupChats(TelegramObject):
    type_val: str

@dataclass
class BotCommandScopeAllChatAdministrators(TelegramObject):
    type_val: str

@dataclass
class BotCommandScopeChat(TelegramObject):
    type_val: str
    chat_id: Union[int, str]

@dataclass
class BotCommandScopeChatAdministrators(TelegramObject):
    type_val: str
    chat_id: Union[int, str]

@dataclass
class BotCommandScopeChatMember(TelegramObject):
    type_val: str
    chat_id: Union[int, str]
    user_id: int

@dataclass
class BotName(TelegramObject):
    name: str

@dataclass
class BotDescription(TelegramObject):
    description: str

@dataclass
class BotShortDescription(TelegramObject):
    short_description: str

@dataclass
class MenuButton(TelegramObject):
    pass

@dataclass
class MenuButtonCommands(TelegramObject):
    type_val: str

@dataclass
class MenuButtonWebApp(TelegramObject):
    type_val: str
    text: str
    web_app: "WebAppInfo"

@dataclass
class MenuButtonDefault(TelegramObject):
    type_val: str

@dataclass
class ChatBoostSource(TelegramObject):
    pass

@dataclass
class ChatBoostSourcePremium(TelegramObject):
    source: str
    user: "User"

@dataclass
class ChatBoostSourceGiftCode(TelegramObject):
    source: str
    user: "User"

@dataclass
class ChatBoostSourceGiveaway(TelegramObject):
    source: str
    giveaway_message_id: int
    user: Optional["User"] = None
    prize_star_count: Optional[int] = None
    is_unclaimed: Optional[bool] = None

@dataclass
class ChatBoost(TelegramObject):
    boost_id: str
    add_date: int
    expiration_date: int
    source: Union["ChatBoostSourcePremium", "ChatBoostSourceGiftCode", "ChatBoostSourceGiveaway"]

@dataclass
class ChatBoostUpdated(TelegramObject):
    chat: "Chat"
    boost: "ChatBoost"

@dataclass
class ChatBoostRemoved(TelegramObject):
    chat: "Chat"
    boost_id: str
    remove_date: int
    source: Union["ChatBoostSourcePremium", "ChatBoostSourceGiftCode", "ChatBoostSourceGiveaway"]

@dataclass
class UserChatBoosts(TelegramObject):
    boosts: List["ChatBoost"]

@dataclass
class BusinessBotRights(TelegramObject):
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

@dataclass
class BusinessConnection(TelegramObject):
    id: str
    user: "User"
    user_chat_id: int
    date: int
    is_enabled: bool
    rights: Optional["BusinessBotRights"] = None

@dataclass
class BusinessMessagesDeleted(TelegramObject):
    business_connection_id: str
    chat: "Chat"
    message_ids: List[int]

@dataclass
class ResponseParameters(TelegramObject):
    migrate_to_chat_id: Optional[int] = None
    retry_after: Optional[int] = None

@dataclass
class InputMedia(TelegramObject):
    pass

@dataclass
class InputMediaPhoto(TelegramObject):
    type_val: str
    media: str
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    show_caption_above_media: Optional[bool] = None
    has_spoiler: Optional[bool] = None

@dataclass
class InputMediaVideo(TelegramObject):
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

@dataclass
class InputMediaAnimation(TelegramObject):
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

@dataclass
class InputMediaAudio(TelegramObject):
    type_val: str
    media: str
    thumbnail: Optional[str] = None
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    duration: Optional[int] = None
    performer: Optional[str] = None
    title: Optional[str] = None

@dataclass
class InputMediaDocument(TelegramObject):
    type_val: str
    media: str
    thumbnail: Optional[str] = None
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    disable_content_type_detection: Optional[bool] = None

@dataclass
class InputFile(TelegramObject):
    pass

@dataclass
class InputPaidMedia(TelegramObject):
    pass

@dataclass
class InputPaidMediaPhoto(TelegramObject):
    type_val: str
    media: str

@dataclass
class InputPaidMediaVideo(TelegramObject):
    type_val: str
    media: str
    thumbnail: Optional[str] = None
    cover: Optional[str] = None
    start_timestamp: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[int] = None
    supports_streaming: Optional[bool] = None

@dataclass
class InputProfilePhoto(TelegramObject):
    pass

@dataclass
class InputProfilePhotoStatic(TelegramObject):
    type_val: str
    photo: str

@dataclass
class InputProfilePhotoAnimated(TelegramObject):
    type_val: str
    animation: str
    main_frame_timestamp: Optional[float] = None

@dataclass
class InputStoryContent(TelegramObject):
    pass

@dataclass
class InputStoryContentPhoto(TelegramObject):
    type_val: str
    photo: str

@dataclass
class InputStoryContentVideo(TelegramObject):
    type_val: str
    video: str
    duration: Optional[float] = None
    cover_frame_timestamp: Optional[float] = None
    is_animation: Optional[bool] = None

@dataclass
class Sticker(TelegramObject):
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

@dataclass
class StickerSet(TelegramObject):
    name: str
    title: str
    sticker_type: str
    stickers: List["Sticker"]
    thumbnail: Optional["PhotoSize"] = None

@dataclass
class MaskPosition(TelegramObject):
    point: str
    x_shift: float
    y_shift: float
    scale: float

@dataclass
class InputSticker(TelegramObject):
    sticker: str
    format: str
    emoji_list: List[str]
    mask_position: Optional["MaskPosition"] = None
    keywords: Optional[List[str]] = None

@dataclass
class InlineQuery(TelegramObject):
    id: str
    from_user: "User"
    query: str
    offset: str
    chat_type: Optional[str] = None
    location: Optional["Location"] = None

@dataclass
class InlineQueryResultsButton(TelegramObject):
    text: str
    web_app: Optional["WebAppInfo"] = None
    start_parameter: Optional[str] = None

@dataclass
class InlineQueryResult(TelegramObject):
    pass

@dataclass
class InlineQueryResultArticle(TelegramObject):
    type_val: str
    id: str
    title: str
    input_message_content: Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    url: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    thumbnail_width: Optional[int] = None
    thumbnail_height: Optional[int] = None

@dataclass
class InlineQueryResultPhoto(TelegramObject):
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
    input_message_content: Optional[Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]] = None

@dataclass
class InlineQueryResultGif(TelegramObject):
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
    input_message_content: Optional[Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]] = None

@dataclass
class InlineQueryResultMpeg4Gif(TelegramObject):
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
    input_message_content: Optional[Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]] = None

@dataclass
class InlineQueryResultVideo(TelegramObject):
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
    input_message_content: Optional[Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]] = None

@dataclass
class InlineQueryResultAudio(TelegramObject):
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
    input_message_content: Optional[Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]] = None

@dataclass
class InlineQueryResultVoice(TelegramObject):
    type_val: str
    id: str
    voice_url: str
    title: str
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    voice_duration: Optional[int] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional[Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]] = None

@dataclass
class InlineQueryResultDocument(TelegramObject):
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
    input_message_content: Optional[Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]] = None
    thumbnail_url: Optional[str] = None
    thumbnail_width: Optional[int] = None
    thumbnail_height: Optional[int] = None

@dataclass
class InlineQueryResultLocation(TelegramObject):
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
    input_message_content: Optional[Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]] = None
    thumbnail_url: Optional[str] = None
    thumbnail_width: Optional[int] = None
    thumbnail_height: Optional[int] = None

@dataclass
class InlineQueryResultVenue(TelegramObject):
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
    input_message_content: Optional[Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]] = None
    thumbnail_url: Optional[str] = None
    thumbnail_width: Optional[int] = None
    thumbnail_height: Optional[int] = None

@dataclass
class InlineQueryResultContact(TelegramObject):
    type_val: str
    id: str
    phone_number: str
    first_name: str
    last_name: Optional[str] = None
    vcard: Optional[str] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional[Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]] = None
    thumbnail_url: Optional[str] = None
    thumbnail_width: Optional[int] = None
    thumbnail_height: Optional[int] = None

@dataclass
class InlineQueryResultGame(TelegramObject):
    type_val: str
    id: str
    game_short_name: str
    reply_markup: Optional["InlineKeyboardMarkup"] = None

@dataclass
class InlineQueryResultCachedPhoto(TelegramObject):
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
    input_message_content: Optional[Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]] = None

@dataclass
class InlineQueryResultCachedGif(TelegramObject):
    type_val: str
    id: str
    gif_file_id: str
    title: Optional[str] = None
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    show_caption_above_media: Optional[bool] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional[Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]] = None

@dataclass
class InlineQueryResultCachedMpeg4Gif(TelegramObject):
    type_val: str
    id: str
    mpeg4_file_id: str
    title: Optional[str] = None
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    show_caption_above_media: Optional[bool] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional[Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]] = None

@dataclass
class InlineQueryResultCachedSticker(TelegramObject):
    type_val: str
    id: str
    sticker_file_id: str
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional[Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]] = None

@dataclass
class InlineQueryResultCachedDocument(TelegramObject):
    type_val: str
    id: str
    title: str
    document_file_id: str
    description: Optional[str] = None
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional[Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]] = None

@dataclass
class InlineQueryResultCachedVideo(TelegramObject):
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
    input_message_content: Optional[Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]] = None

@dataclass
class InlineQueryResultCachedVoice(TelegramObject):
    type_val: str
    id: str
    voice_file_id: str
    title: str
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional[Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]] = None

@dataclass
class InlineQueryResultCachedAudio(TelegramObject):
    type_val: str
    id: str
    audio_file_id: str
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None
    input_message_content: Optional[Union["InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent", "InputContactMessageContent", "InputInvoiceMessageContent"]] = None

@dataclass
class InputMessageContent(TelegramObject):
    pass

@dataclass
class InputTextMessageContent(TelegramObject):
    message_text: str
    parse_mode: Optional[str] = None
    entities: Optional[List["MessageEntity"]] = None
    link_preview_options: Optional["LinkPreviewOptions"] = None

@dataclass
class InputLocationMessageContent(TelegramObject):
    latitude: float
    longitude: float
    horizontal_accuracy: Optional[float] = None
    live_period: Optional[int] = None
    heading: Optional[int] = None
    proximity_alert_radius: Optional[int] = None

@dataclass
class InputVenueMessageContent(TelegramObject):
    latitude: float
    longitude: float
    title: str
    address: str
    foursquare_id: Optional[str] = None
    foursquare_type: Optional[str] = None
    google_place_id: Optional[str] = None
    google_place_type: Optional[str] = None

@dataclass
class InputContactMessageContent(TelegramObject):
    phone_number: str
    first_name: str
    last_name: Optional[str] = None
    vcard: Optional[str] = None

@dataclass
class InputInvoiceMessageContent(TelegramObject):
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

@dataclass
class ChosenInlineResult(TelegramObject):
    result_id: str
    from_user: "User"
    query: str
    location: Optional["Location"] = None
    inline_message_id: Optional[str] = None

@dataclass
class SentWebAppMessage(TelegramObject):
    inline_message_id: Optional[str] = None

@dataclass
class PreparedInlineMessage(TelegramObject):
    id: str
    expiration_date: int

@dataclass
class LabeledPrice(TelegramObject):
    label: str
    amount: int

@dataclass
class Invoice(TelegramObject):
    title: str
    description: str
    start_parameter: str
    currency: str
    total_amount: int

@dataclass
class ShippingAddress(TelegramObject):
    country_code: str
    state: str
    city: str
    street_line1: str
    street_line2: str
    post_code: str

@dataclass
class OrderInfo(TelegramObject):
    name: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    shipping_address: Optional["ShippingAddress"] = None

@dataclass
class ShippingOption(TelegramObject):
    id: str
    title: str
    prices: List["LabeledPrice"]

@dataclass
class SuccessfulPayment(TelegramObject):
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

@dataclass
class RefundedPayment(TelegramObject):
    currency: str
    total_amount: int
    invoice_payload: str
    telegram_payment_charge_id: str
    provider_payment_charge_id: Optional[str] = None

@dataclass
class ShippingQuery(TelegramObject):
    id: str
    from_user: "User"
    invoice_payload: str
    shipping_address: "ShippingAddress"

@dataclass
class PreCheckoutQuery(TelegramObject):
    id: str
    from_user: "User"
    currency: str
    total_amount: int
    invoice_payload: str
    shipping_option_id: Optional[str] = None
    order_info: Optional["OrderInfo"] = None

@dataclass
class PaidMediaPurchased(TelegramObject):
    from_user: "User"
    paid_media_payload: str

@dataclass
class RevenueWithdrawalState(TelegramObject):
    pass

@dataclass
class RevenueWithdrawalStatePending(TelegramObject):
    type_val: str

@dataclass
class RevenueWithdrawalStateSucceeded(TelegramObject):
    type_val: str
    date: int
    url: str

@dataclass
class RevenueWithdrawalStateFailed(TelegramObject):
    type_val: str

@dataclass
class AffiliateInfo(TelegramObject):
    commission_per_mille: int
    amount: int
    affiliate_user: Optional["User"] = None
    affiliate_chat: Optional["Chat"] = None
    nanostar_amount: Optional[int] = None

@dataclass
class TransactionPartner(TelegramObject):
    pass

@dataclass
class TransactionPartnerUser(TelegramObject):
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

@dataclass
class TransactionPartnerChat(TelegramObject):
    type_val: str
    chat: "Chat"
    gift: Optional["Gift"] = None

@dataclass
class TransactionPartnerAffiliateProgram(TelegramObject):
    type_val: str
    commission_per_mille: int
    sponsor_user: Optional["User"] = None

@dataclass
class TransactionPartnerFragment(TelegramObject):
    type_val: str
    withdrawal_state: Optional[Union["RevenueWithdrawalStatePending", "RevenueWithdrawalStateSucceeded", "RevenueWithdrawalStateFailed"]] = None

@dataclass
class TransactionPartnerTelegramAds(TelegramObject):
    type_val: str

@dataclass
class TransactionPartnerTelegramApi(TelegramObject):
    type_val: str
    request_count: int

@dataclass
class TransactionPartnerOther(TelegramObject):
    type_val: str

@dataclass
class StarTransaction(TelegramObject):
    id: str
    amount: int
    date: int
    nanostar_amount: Optional[int] = None
    source: Optional[Union["TransactionPartnerUser", "TransactionPartnerFragment", "TransactionPartnerTelegramAds", "TransactionPartnerOther"]] = None
    receiver: Optional[Union["TransactionPartnerUser", "TransactionPartnerFragment", "TransactionPartnerTelegramAds", "TransactionPartnerOther"]] = None

@dataclass
class StarTransactions(TelegramObject):
    transactions: List["StarTransaction"]

@dataclass
class PassportData(TelegramObject):
    data: List["EncryptedPassportElement"]
    credentials: "EncryptedCredentials"

@dataclass
class PassportFile(TelegramObject):
    file_id: str
    file_unique_id: str
    file_size: int
    file_date: int

@dataclass
class EncryptedPassportElement(TelegramObject):
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

@dataclass
class EncryptedCredentials(TelegramObject):
    data: str
    hash: str
    secret: str

@dataclass
class PassportElementError(TelegramObject):
    pass

@dataclass
class PassportElementErrorDataField(TelegramObject):
    source: str
    type_val: str
    field_name: str
    data_hash: str
    message: str

@dataclass
class PassportElementErrorFrontSide(TelegramObject):
    source: str
    type_val: str
    file_hash: str
    message: str

@dataclass
class PassportElementErrorReverseSide(TelegramObject):
    source: str
    type_val: str
    file_hash: str
    message: str

@dataclass
class PassportElementErrorSelfie(TelegramObject):
    source: str
    type_val: str
    file_hash: str
    message: str

@dataclass
class PassportElementErrorFile(TelegramObject):
    source: str
    type_val: str
    file_hash: str
    message: str

@dataclass
class PassportElementErrorFiles(TelegramObject):
    source: str
    type_val: str
    file_hashes: List[str]
    message: str

@dataclass
class PassportElementErrorTranslationFile(TelegramObject):
    source: str
    type_val: str
    file_hash: str
    message: str

@dataclass
class PassportElementErrorTranslationFiles(TelegramObject):
    source: str
    type_val: str
    file_hashes: List[str]
    message: str

@dataclass
class PassportElementErrorUnspecified(TelegramObject):
    source: str
    type_val: str
    element_hash: str
    message: str

@dataclass
class Game(TelegramObject):
    title: str
    description: str
    photo: List["PhotoSize"]
    text: Optional[str] = None
    text_entities: Optional[List["MessageEntity"]] = None
    animation: Optional["Animation"] = None

@dataclass
class CallbackGame(TelegramObject):
    pass

@dataclass
class GameHighScore(TelegramObject):
    position: int
    user: "User"
    score: int


class Bot:
    def __init__(self, token: str, timeout: int = 60):
        self.token = token
        self.session = requests.Session()
        self.timeout = timeout

    def _make_request(self, method: str, params: dict = None, files: dict = None):
        url = API_URL.format(token=self.token, method=method)
        try:
            resp = self.session.post(url, data=params, files=files, timeout=self.timeout)
            json_resp = resp.json()
            if not json_resp.get('ok'):
                raise TelegramError(method, json_resp)
            return json_resp
        except Exception as e:
            if isinstance(e, TelegramError): raise e
            raise TelegramError(method, {'error_code': 0, 'description': str(e)})

    def get_updates(self, offset: Optional[int] = None, limit: Optional[int] = None, timeout: Optional[int] = None, allowed_updates: Optional[List[str]] = None) -> Optional[List["Update"]]:
        """Use this method to receive incoming updates using long polling (wiki). Returns an Array of Update objects."""
        method = 'getUpdates'
        params = {
            'offset': offset,
            'limit': limit,
            'timeout': timeout,
            'allowed_updates': _serialize(allowed_updates),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return [Update.from_dict(x) for x in response['result']]
        return None

    def set_webhook(self, url: Optional[str] = None, certificate: Optional[Union[str, bytes, IO]] = None, ip_address: Optional[str] = None, max_connections: Optional[int] = None, allowed_updates: Optional[List[str]] = None, drop_pending_updates: Optional[bool] = None, secret_token: Optional[str] = None) -> Optional[bool]:
        """Use this method to specify a URL and receive incoming updates via an outgoing webhook. Whenever there is an update for the bot, we will send an HTTPS POST request to the specified URL, containing a JSON-serialized Update. In case of an unsuccessful request (a request with response HTTP status code different from 2XY), we will repeat the request and give up after a reasonable amount of attempts. Returns True on success."""
        method = 'setWebhook'
        if url is None: raise ValueError('url required')
        params = {
            'url': url,
            'ip_address': ip_address,
            'max_connections': max_connections,
            'allowed_updates': _serialize(allowed_updates),
            'drop_pending_updates': drop_pending_updates,
            'secret_token': secret_token,
        }
        params = {k: v for k, v in params.items() if v is not None}
        files = {}
        if certificate is not None:
            if hasattr(certificate, 'read') or isinstance(certificate, bytes):
                files['certificate'] = certificate
            else:
                params['certificate'] = certificate
        response = self._make_request(method, params, files=files)
        return response.get('result')

    def delete_webhook(self, drop_pending_updates: Optional[bool] = None) -> Optional[bool]:
        """Use this method to remove webhook integration if you decide to switch back to getUpdates. Returns True on success."""
        method = 'deleteWebhook'
        params = {
            'drop_pending_updates': drop_pending_updates,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def get_webhook_info(self) -> Optional["WebhookInfo"]:
        """Use this method to get current webhook status. Requires no parameters. On success, returns a WebhookInfo object. If the bot is using getUpdates, will return an object with the url field empty."""
        method = 'getWebhookInfo'
        params = {
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return WebhookInfo.from_dict(response['result'])
        return None

    def get_me(self) -> Optional["User"]:
        """A simple method for testing your bot's authentication token. Requires no parameters. Returns basic information about the bot in form of a User object."""
        method = 'getMe'
        params = {
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return User.from_dict(response['result'])
        return None

    def log_out(self) -> Optional[bool]:
        """Use this method to log out from the cloud Bot API server before launching the bot locally. You must log out the bot before running it locally, otherwise there is no guarantee that the bot will receive updates. After a successful call, you can immediately log in on a local server, but will not be able to log in back to the cloud Bot API server for 10 minutes. Returns True on success. Requires no parameters."""
        method = 'logOut'
        params = {
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def close(self) -> Optional[bool]:
        """Use this method to close the bot instance before moving it from one local server to another. You need to delete the webhook before calling this method to ensure that the bot isn't launched again after server restart. The method will return error 429 in the first 10 minutes after the bot is launched. Returns True on success. Requires no parameters."""
        method = 'close'
        params = {
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def send_message(self, chat_id: Optional[Union[int, str]] = None, text: Optional[str] = None, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, parse_mode: Optional[str] = None, entities: Optional[List["MessageEntity"]] = None, link_preview_options: Optional["LinkPreviewOptions"] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["ForceReply", "InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove"]] = None) -> Optional["Message"]:
        """Use this method to send text messages. On success, the sent Message is returned."""
        method = 'sendMessage'
        if chat_id is None: raise ValueError('chat_id required')
        if text is None: raise ValueError('text required')
        params = {
            'chat_id': _serialize(chat_id),
            'text': text,
            'business_connection_id': business_connection_id,
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'parse_mode': parse_mode,
            'entities': _serialize(entities),
            'link_preview_options': _serialize(link_preview_options),
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'allow_paid_broadcast': allow_paid_broadcast,
            'message_effect_id': message_effect_id,
            'suggested_post_parameters': _serialize(suggested_post_parameters),
            'reply_parameters': _serialize(reply_parameters),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def forward_message(self, chat_id: Optional[Union[int, str]] = None, from_chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, video_start_timestamp: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None) -> Optional["Message"]:
        """Use this method to forward messages of any kind. Service messages and messages with protected content can't be forwarded. On success, the sent Message is returned."""
        method = 'forwardMessage'
        if chat_id is None: raise ValueError('chat_id required')
        if from_chat_id is None: raise ValueError('from_chat_id required')
        if message_id is None: raise ValueError('message_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'from_chat_id': _serialize(from_chat_id),
            'message_id': message_id,
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'video_start_timestamp': video_start_timestamp,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'message_effect_id': message_effect_id,
            'suggested_post_parameters': _serialize(suggested_post_parameters),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def forward_messages(self, chat_id: Optional[Union[int, str]] = None, from_chat_id: Optional[Union[int, str]] = None, message_ids: Optional[List[int]] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None) -> Optional[Any]:
        """Use this method to forward multiple messages of any kind. If some of the specified messages can't be found or forwarded, they are skipped. Service messages and messages with protected content can't be forwarded. Album grouping is kept for forwarded messages. On success, an array of MessageId of the sent messages is returned."""
        method = 'forwardMessages'
        if chat_id is None: raise ValueError('chat_id required')
        if from_chat_id is None: raise ValueError('from_chat_id required')
        if message_ids is None: raise ValueError('message_ids required')
        params = {
            'chat_id': _serialize(chat_id),
            'from_chat_id': _serialize(from_chat_id),
            'message_ids': _serialize(message_ids),
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def copy_message(self, chat_id: Optional[Union[int, str]] = None, from_chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, video_start_timestamp: Optional[int] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["ForceReply", "InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove"]] = None) -> Optional["MessageId"]:
        """Use this method to copy messages of any kind. Service messages, paid media messages, giveaway messages, giveaway winners messages, and invoice messages can't be copied. A quiz poll can be copied only if the value of the field correct_option_id is known to the bot. The method is analogous to the method forwardMessage, but the copied message doesn't have a link to the original message. Returns the MessageId of the sent message on success."""
        method = 'copyMessage'
        if chat_id is None: raise ValueError('chat_id required')
        if from_chat_id is None: raise ValueError('from_chat_id required')
        if message_id is None: raise ValueError('message_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'from_chat_id': _serialize(from_chat_id),
            'message_id': message_id,
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'video_start_timestamp': video_start_timestamp,
            'caption': caption,
            'parse_mode': parse_mode,
            'caption_entities': _serialize(caption_entities),
            'show_caption_above_media': show_caption_above_media,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'allow_paid_broadcast': allow_paid_broadcast,
            'message_effect_id': message_effect_id,
            'suggested_post_parameters': _serialize(suggested_post_parameters),
            'reply_parameters': _serialize(reply_parameters),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return MessageId.from_dict(response['result'])
        return None

    def copy_messages(self, chat_id: Optional[Union[int, str]] = None, from_chat_id: Optional[Union[int, str]] = None, message_ids: Optional[List[int]] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, remove_caption: Optional[bool] = None) -> Optional[Any]:
        """Use this method to copy messages of any kind. If some of the specified messages can't be found or copied, they are skipped. Service messages, paid media messages, giveaway messages, giveaway winners messages, and invoice messages can't be copied. A quiz poll can be copied only if the value of the field correct_option_id is known to the bot. The method is analogous to the method forwardMessages, but the copied messages don't have a link to the original message. Album grouping is kept for copied messages. On success, an array of MessageId of the sent messages is returned."""
        method = 'copyMessages'
        if chat_id is None: raise ValueError('chat_id required')
        if from_chat_id is None: raise ValueError('from_chat_id required')
        if message_ids is None: raise ValueError('message_ids required')
        params = {
            'chat_id': _serialize(chat_id),
            'from_chat_id': _serialize(from_chat_id),
            'message_ids': _serialize(message_ids),
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'remove_caption': remove_caption,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def send_photo(self, chat_id: Optional[Union[int, str]] = None, photo: Optional[Union[Union[str, bytes, IO], str]] = None, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, has_spoiler: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["ForceReply", "InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove"]] = None) -> Optional["Message"]:
        """Use this method to send photos. On success, the sent Message is returned."""
        method = 'sendPhoto'
        if chat_id is None: raise ValueError('chat_id required')
        if photo is None: raise ValueError('photo required')
        params = {
            'chat_id': _serialize(chat_id),
            'business_connection_id': business_connection_id,
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'caption': caption,
            'parse_mode': parse_mode,
            'caption_entities': _serialize(caption_entities),
            'show_caption_above_media': show_caption_above_media,
            'has_spoiler': has_spoiler,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'allow_paid_broadcast': allow_paid_broadcast,
            'message_effect_id': message_effect_id,
            'suggested_post_parameters': _serialize(suggested_post_parameters),
            'reply_parameters': _serialize(reply_parameters),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        files = {}
        if photo is not None:
            if hasattr(photo, 'read') or isinstance(photo, bytes):
                files['photo'] = photo
            else:
                params['photo'] = photo
        response = self._make_request(method, params, files=files)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def send_audio(self, chat_id: Optional[Union[int, str]] = None, audio: Optional[Union[Union[str, bytes, IO], str]] = None, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, duration: Optional[int] = None, performer: Optional[str] = None, title: Optional[str] = None, thumbnail: Optional[Union[Union[str, bytes, IO], str]] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["ForceReply", "InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove"]] = None) -> Optional["Message"]:
        """Use this method to send audio files, if you want Telegram clients to display them in the music player. Your audio must be in the .MP3 or .M4A format. On success, the sent Message is returned. Bots can currently send audio files of up to 50 MB in size, this limit may be changed in the future."""
        method = 'sendAudio'
        if chat_id is None: raise ValueError('chat_id required')
        if audio is None: raise ValueError('audio required')
        params = {
            'chat_id': _serialize(chat_id),
            'business_connection_id': business_connection_id,
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'caption': caption,
            'parse_mode': parse_mode,
            'caption_entities': _serialize(caption_entities),
            'duration': duration,
            'performer': performer,
            'title': title,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'allow_paid_broadcast': allow_paid_broadcast,
            'message_effect_id': message_effect_id,
            'suggested_post_parameters': _serialize(suggested_post_parameters),
            'reply_parameters': _serialize(reply_parameters),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        files = {}
        if audio is not None:
            if hasattr(audio, 'read') or isinstance(audio, bytes):
                files['audio'] = audio
            else:
                params['audio'] = audio
        if thumbnail is not None:
            if hasattr(thumbnail, 'read') or isinstance(thumbnail, bytes):
                files['thumbnail'] = thumbnail
            else:
                params['thumbnail'] = thumbnail
        response = self._make_request(method, params, files=files)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def send_document(self, chat_id: Optional[Union[int, str]] = None, document: Optional[Union[Union[str, bytes, IO], str]] = None, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, thumbnail: Optional[Union[Union[str, bytes, IO], str]] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, disable_content_type_detection: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["ForceReply", "InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove"]] = None) -> Optional["Message"]:
        """Use this method to send general files. On success, the sent Message is returned. Bots can currently send files of any type of up to 50 MB in size, this limit may be changed in the future."""
        method = 'sendDocument'
        if chat_id is None: raise ValueError('chat_id required')
        if document is None: raise ValueError('document required')
        params = {
            'chat_id': _serialize(chat_id),
            'business_connection_id': business_connection_id,
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'caption': caption,
            'parse_mode': parse_mode,
            'caption_entities': _serialize(caption_entities),
            'disable_content_type_detection': disable_content_type_detection,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'allow_paid_broadcast': allow_paid_broadcast,
            'message_effect_id': message_effect_id,
            'suggested_post_parameters': _serialize(suggested_post_parameters),
            'reply_parameters': _serialize(reply_parameters),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        files = {}
        if document is not None:
            if hasattr(document, 'read') or isinstance(document, bytes):
                files['document'] = document
            else:
                params['document'] = document
        if thumbnail is not None:
            if hasattr(thumbnail, 'read') or isinstance(thumbnail, bytes):
                files['thumbnail'] = thumbnail
            else:
                params['thumbnail'] = thumbnail
        response = self._make_request(method, params, files=files)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def send_video(self, chat_id: Optional[Union[int, str]] = None, video: Optional[Union[Union[str, bytes, IO], str]] = None, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, duration: Optional[int] = None, width: Optional[int] = None, height: Optional[int] = None, thumbnail: Optional[Union[Union[str, bytes, IO], str]] = None, cover: Optional[Union[Union[str, bytes, IO], str]] = None, start_timestamp: Optional[int] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, has_spoiler: Optional[bool] = None, supports_streaming: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["ForceReply", "InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove"]] = None) -> Optional["Message"]:
        """Use this method to send video files, Telegram clients support MPEG4 videos (other formats may be sent as Document). On success, the sent Message is returned. Bots can currently send video files of up to 50 MB in size, this limit may be changed in the future."""
        method = 'sendVideo'
        if chat_id is None: raise ValueError('chat_id required')
        if video is None: raise ValueError('video required')
        params = {
            'chat_id': _serialize(chat_id),
            'business_connection_id': business_connection_id,
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'duration': duration,
            'width': width,
            'height': height,
            'start_timestamp': start_timestamp,
            'caption': caption,
            'parse_mode': parse_mode,
            'caption_entities': _serialize(caption_entities),
            'show_caption_above_media': show_caption_above_media,
            'has_spoiler': has_spoiler,
            'supports_streaming': supports_streaming,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'allow_paid_broadcast': allow_paid_broadcast,
            'message_effect_id': message_effect_id,
            'suggested_post_parameters': _serialize(suggested_post_parameters),
            'reply_parameters': _serialize(reply_parameters),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        files = {}
        if video is not None:
            if hasattr(video, 'read') or isinstance(video, bytes):
                files['video'] = video
            else:
                params['video'] = video
        if thumbnail is not None:
            if hasattr(thumbnail, 'read') or isinstance(thumbnail, bytes):
                files['thumbnail'] = thumbnail
            else:
                params['thumbnail'] = thumbnail
        if cover is not None:
            if hasattr(cover, 'read') or isinstance(cover, bytes):
                files['cover'] = cover
            else:
                params['cover'] = cover
        response = self._make_request(method, params, files=files)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def send_animation(self, chat_id: Optional[Union[int, str]] = None, animation: Optional[Union[Union[str, bytes, IO], str]] = None, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, duration: Optional[int] = None, width: Optional[int] = None, height: Optional[int] = None, thumbnail: Optional[Union[Union[str, bytes, IO], str]] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, has_spoiler: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["ForceReply", "InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove"]] = None) -> Optional["Message"]:
        """Use this method to send animation files (GIF or H.264/MPEG-4 AVC video without sound). On success, the sent Message is returned. Bots can currently send animation files of up to 50 MB in size, this limit may be changed in the future."""
        method = 'sendAnimation'
        if chat_id is None: raise ValueError('chat_id required')
        if animation is None: raise ValueError('animation required')
        params = {
            'chat_id': _serialize(chat_id),
            'business_connection_id': business_connection_id,
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'duration': duration,
            'width': width,
            'height': height,
            'caption': caption,
            'parse_mode': parse_mode,
            'caption_entities': _serialize(caption_entities),
            'show_caption_above_media': show_caption_above_media,
            'has_spoiler': has_spoiler,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'allow_paid_broadcast': allow_paid_broadcast,
            'message_effect_id': message_effect_id,
            'suggested_post_parameters': _serialize(suggested_post_parameters),
            'reply_parameters': _serialize(reply_parameters),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        files = {}
        if animation is not None:
            if hasattr(animation, 'read') or isinstance(animation, bytes):
                files['animation'] = animation
            else:
                params['animation'] = animation
        if thumbnail is not None:
            if hasattr(thumbnail, 'read') or isinstance(thumbnail, bytes):
                files['thumbnail'] = thumbnail
            else:
                params['thumbnail'] = thumbnail
        response = self._make_request(method, params, files=files)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def send_voice(self, chat_id: Optional[Union[int, str]] = None, voice: Optional[Union[Union[str, bytes, IO], str]] = None, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, duration: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["ForceReply", "InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove"]] = None) -> Optional["Message"]:
        """Use this method to send audio files, if you want Telegram clients to display the file as a playable voice message. For this to work, your audio must be in an .OGG file encoded with OPUS, or in .MP3 format, or in .M4A format (other formats may be sent as Audio or Document). On success, the sent Message is returned. Bots can currently send voice messages of up to 50 MB in size, this limit may be changed in the future."""
        method = 'sendVoice'
        if chat_id is None: raise ValueError('chat_id required')
        if voice is None: raise ValueError('voice required')
        params = {
            'chat_id': _serialize(chat_id),
            'business_connection_id': business_connection_id,
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'caption': caption,
            'parse_mode': parse_mode,
            'caption_entities': _serialize(caption_entities),
            'duration': duration,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'allow_paid_broadcast': allow_paid_broadcast,
            'message_effect_id': message_effect_id,
            'suggested_post_parameters': _serialize(suggested_post_parameters),
            'reply_parameters': _serialize(reply_parameters),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        files = {}
        if voice is not None:
            if hasattr(voice, 'read') or isinstance(voice, bytes):
                files['voice'] = voice
            else:
                params['voice'] = voice
        response = self._make_request(method, params, files=files)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def send_video_note(self, chat_id: Optional[Union[int, str]] = None, video_note: Optional[Union[Union[str, bytes, IO], str]] = None, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, duration: Optional[int] = None, length: Optional[int] = None, thumbnail: Optional[Union[Union[str, bytes, IO], str]] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["ForceReply", "InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove"]] = None) -> Optional["Message"]:
        """As of v.4.0, Telegram clients support rounded square MPEG4 videos of up to 1 minute long. Use this method to send video messages. On success, the sent Message is returned."""
        method = 'sendVideoNote'
        if chat_id is None: raise ValueError('chat_id required')
        if video_note is None: raise ValueError('video_note required')
        params = {
            'chat_id': _serialize(chat_id),
            'business_connection_id': business_connection_id,
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'duration': duration,
            'length': length,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'allow_paid_broadcast': allow_paid_broadcast,
            'message_effect_id': message_effect_id,
            'suggested_post_parameters': _serialize(suggested_post_parameters),
            'reply_parameters': _serialize(reply_parameters),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        files = {}
        if video_note is not None:
            if hasattr(video_note, 'read') or isinstance(video_note, bytes):
                files['video_note'] = video_note
            else:
                params['video_note'] = video_note
        if thumbnail is not None:
            if hasattr(thumbnail, 'read') or isinstance(thumbnail, bytes):
                files['thumbnail'] = thumbnail
            else:
                params['thumbnail'] = thumbnail
        response = self._make_request(method, params, files=files)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def send_paid_media(self, chat_id: Optional[Union[int, str]] = None, star_count: Optional[int] = None, media: Optional[List["InputPaidMedia"]] = None, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, payload: Optional[str] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["ForceReply", "InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove"]] = None) -> Optional["Message"]:
        """Use this method to send paid media. On success, the sent Message is returned."""
        method = 'sendPaidMedia'
        if chat_id is None: raise ValueError('chat_id required')
        if star_count is None: raise ValueError('star_count required')
        if media is None: raise ValueError('media required')
        params = {
            'chat_id': _serialize(chat_id),
            'star_count': star_count,
            'media': _serialize(media),
            'business_connection_id': business_connection_id,
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'payload': payload,
            'caption': caption,
            'parse_mode': parse_mode,
            'caption_entities': _serialize(caption_entities),
            'show_caption_above_media': show_caption_above_media,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'allow_paid_broadcast': allow_paid_broadcast,
            'suggested_post_parameters': _serialize(suggested_post_parameters),
            'reply_parameters': _serialize(reply_parameters),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def send_media_group(self, chat_id: Optional[Union[int, str]] = None, media: Optional[List["InputMediaAudio, InputMediaDocument, InputMediaPhoto and InputMediaVideo"]] = None, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, reply_parameters: Optional["ReplyParameters"] = None) -> Optional[List["Message"]]:
        """Use this method to send a group of photos, videos, documents or audios as an album. Documents and audio files can be only grouped in an album with messages of the same type. On success, an array of Message objects that were sent is returned."""
        method = 'sendMediaGroup'
        if chat_id is None: raise ValueError('chat_id required')
        if media is None: raise ValueError('media required')
        params = {
            'chat_id': _serialize(chat_id),
            'media': _serialize(media),
            'business_connection_id': business_connection_id,
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'allow_paid_broadcast': allow_paid_broadcast,
            'message_effect_id': message_effect_id,
            'reply_parameters': _serialize(reply_parameters),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return [Message.from_dict(x) for x in response['result']]
        return None

    def send_location(self, chat_id: Optional[Union[int, str]] = None, latitude: Optional[float] = None, longitude: Optional[float] = None, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, horizontal_accuracy: Optional[float] = None, live_period: Optional[int] = None, heading: Optional[int] = None, proximity_alert_radius: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["ForceReply", "InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove"]] = None) -> Optional["Message"]:
        """Use this method to send point on the map. On success, the sent Message is returned."""
        method = 'sendLocation'
        if chat_id is None: raise ValueError('chat_id required')
        if latitude is None: raise ValueError('latitude required')
        if longitude is None: raise ValueError('longitude required')
        params = {
            'chat_id': _serialize(chat_id),
            'latitude': latitude,
            'longitude': longitude,
            'business_connection_id': business_connection_id,
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'horizontal_accuracy': horizontal_accuracy,
            'live_period': live_period,
            'heading': heading,
            'proximity_alert_radius': proximity_alert_radius,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'allow_paid_broadcast': allow_paid_broadcast,
            'message_effect_id': message_effect_id,
            'suggested_post_parameters': _serialize(suggested_post_parameters),
            'reply_parameters': _serialize(reply_parameters),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def send_venue(self, chat_id: Optional[Union[int, str]] = None, latitude: Optional[float] = None, longitude: Optional[float] = None, title: Optional[str] = None, address: Optional[str] = None, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, foursquare_id: Optional[str] = None, foursquare_type: Optional[str] = None, google_place_id: Optional[str] = None, google_place_type: Optional[str] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["ForceReply", "InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove"]] = None) -> Optional["Message"]:
        """Use this method to send information about a venue. On success, the sent Message is returned."""
        method = 'sendVenue'
        if chat_id is None: raise ValueError('chat_id required')
        if latitude is None: raise ValueError('latitude required')
        if longitude is None: raise ValueError('longitude required')
        if title is None: raise ValueError('title required')
        if address is None: raise ValueError('address required')
        params = {
            'chat_id': _serialize(chat_id),
            'latitude': latitude,
            'longitude': longitude,
            'title': title,
            'address': address,
            'business_connection_id': business_connection_id,
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'foursquare_id': foursquare_id,
            'foursquare_type': foursquare_type,
            'google_place_id': google_place_id,
            'google_place_type': google_place_type,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'allow_paid_broadcast': allow_paid_broadcast,
            'message_effect_id': message_effect_id,
            'suggested_post_parameters': _serialize(suggested_post_parameters),
            'reply_parameters': _serialize(reply_parameters),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def send_contact(self, chat_id: Optional[Union[int, str]] = None, phone_number: Optional[str] = None, first_name: Optional[str] = None, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, last_name: Optional[str] = None, vcard: Optional[str] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["ForceReply", "InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove"]] = None) -> Optional["Message"]:
        """Use this method to send phone contacts. On success, the sent Message is returned."""
        method = 'sendContact'
        if chat_id is None: raise ValueError('chat_id required')
        if phone_number is None: raise ValueError('phone_number required')
        if first_name is None: raise ValueError('first_name required')
        params = {
            'chat_id': _serialize(chat_id),
            'phone_number': phone_number,
            'first_name': first_name,
            'business_connection_id': business_connection_id,
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'last_name': last_name,
            'vcard': vcard,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'allow_paid_broadcast': allow_paid_broadcast,
            'message_effect_id': message_effect_id,
            'suggested_post_parameters': _serialize(suggested_post_parameters),
            'reply_parameters': _serialize(reply_parameters),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def send_poll(self, chat_id: Optional[Union[int, str]] = None, question: Optional[str] = None, options: Optional[List["InputPollOption"]] = None, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, question_parse_mode: Optional[str] = None, question_entities: Optional[List["MessageEntity"]] = None, is_anonymous: Optional[bool] = None, type_val: Optional[str] = None, allows_multiple_answers: Optional[bool] = None, correct_option_id: Optional[int] = None, explanation: Optional[str] = None, explanation_parse_mode: Optional[str] = None, explanation_entities: Optional[List["MessageEntity"]] = None, open_period: Optional[int] = None, close_date: Optional[int] = None, is_closed: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["ForceReply", "InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove"]] = None) -> Optional["Message"]:
        """Use this method to send a native poll. On success, the sent Message is returned."""
        method = 'sendPoll'
        if chat_id is None: raise ValueError('chat_id required')
        if question is None: raise ValueError('question required')
        if options is None: raise ValueError('options required')
        params = {
            'chat_id': _serialize(chat_id),
            'question': question,
            'options': _serialize(options),
            'business_connection_id': business_connection_id,
            'message_thread_id': message_thread_id,
            'question_parse_mode': question_parse_mode,
            'question_entities': _serialize(question_entities),
            'is_anonymous': is_anonymous,
            'type': type_val,
            'allows_multiple_answers': allows_multiple_answers,
            'correct_option_id': correct_option_id,
            'explanation': explanation,
            'explanation_parse_mode': explanation_parse_mode,
            'explanation_entities': _serialize(explanation_entities),
            'open_period': open_period,
            'close_date': close_date,
            'is_closed': is_closed,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'allow_paid_broadcast': allow_paid_broadcast,
            'message_effect_id': message_effect_id,
            'reply_parameters': _serialize(reply_parameters),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def send_checklist(self, business_connection_id: Optional[str] = None, chat_id: Optional[int] = None, checklist: Optional["InputChecklist"] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, message_effect_id: Optional[str] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> Optional["Message"]:
        """Use this method to send a checklist on behalf of a connected business account. On success, the sent Message is returned."""
        method = 'sendChecklist'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        if chat_id is None: raise ValueError('chat_id required')
        if checklist is None: raise ValueError('checklist required')
        params = {
            'business_connection_id': business_connection_id,
            'chat_id': chat_id,
            'checklist': _serialize(checklist),
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'message_effect_id': message_effect_id,
            'reply_parameters': _serialize(reply_parameters),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def send_dice(self, chat_id: Optional[Union[int, str]] = None, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, emoji: Optional[str] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["ForceReply", "InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove"]] = None) -> Optional["Message"]:
        """Use this method to send an animated emoji that will display a random value. On success, the sent Message is returned."""
        method = 'sendDice'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'business_connection_id': business_connection_id,
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'emoji': emoji,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'allow_paid_broadcast': allow_paid_broadcast,
            'message_effect_id': message_effect_id,
            'suggested_post_parameters': _serialize(suggested_post_parameters),
            'reply_parameters': _serialize(reply_parameters),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def send_message_draft(self, chat_id: Optional[int] = None, draft_id: Optional[int] = None, text: Optional[str] = None, message_thread_id: Optional[int] = None, parse_mode: Optional[str] = None, entities: Optional[List["MessageEntity"]] = None) -> Optional[bool]:
        """Use this method to stream a partial message to a user while the message is being generated; supported only for bots with forum topic mode enabled. Returns True on success."""
        method = 'sendMessageDraft'
        if chat_id is None: raise ValueError('chat_id required')
        if draft_id is None: raise ValueError('draft_id required')
        if text is None: raise ValueError('text required')
        params = {
            'chat_id': chat_id,
            'draft_id': draft_id,
            'text': text,
            'message_thread_id': message_thread_id,
            'parse_mode': parse_mode,
            'entities': _serialize(entities),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def send_chat_action(self, chat_id: Optional[Union[int, str]] = None, action: Optional[str] = None, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None) -> Optional[bool]:
        """Use this method when you need to tell the user that something is happening on the bot's side. The status is set for 5 seconds or less (when a message arrives from your bot, Telegram clients clear its typing status). Returns True on success."""
        method = 'sendChatAction'
        if chat_id is None: raise ValueError('chat_id required')
        if action is None: raise ValueError('action required')
        params = {
            'chat_id': _serialize(chat_id),
            'action': action,
            'business_connection_id': business_connection_id,
            'message_thread_id': message_thread_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def set_message_reaction(self, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, reaction: Optional[List[Union["ReactionTypeEmoji", "ReactionTypeCustomEmoji", "ReactionTypePaid"]]] = None, is_big: Optional[bool] = None) -> Optional[bool]:
        """Use this method to change the chosen reactions on a message. Service messages of some types can't be reacted to. Automatically forwarded messages from a channel to its discussion group have the same available reactions as messages in the channel. Bots can't use paid reactions. Returns True on success."""
        method = 'setMessageReaction'
        if chat_id is None: raise ValueError('chat_id required')
        if message_id is None: raise ValueError('message_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'message_id': message_id,
            'reaction': _serialize(reaction),
            'is_big': is_big,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def get_user_profile_photos(self, user_id: Optional[int] = None, offset: Optional[int] = None, limit: Optional[int] = None) -> Optional["UserProfilePhotos"]:
        """Use this method to get a list of profile pictures for a user. Returns a UserProfilePhotos object."""
        method = 'getUserProfilePhotos'
        if user_id is None: raise ValueError('user_id required')
        params = {
            'user_id': user_id,
            'offset': offset,
            'limit': limit,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return UserProfilePhotos.from_dict(response['result'])
        return None

    def set_user_emoji_status(self, user_id: Optional[int] = None, emoji_status_custom_emoji_id: Optional[str] = None, emoji_status_expiration_date: Optional[int] = None) -> Optional[bool]:
        """Changes the emoji status for a given user that previously allowed the bot to manage their emoji status via the Mini App method requestEmojiStatusAccess. Returns True on success."""
        method = 'setUserEmojiStatus'
        if user_id is None: raise ValueError('user_id required')
        params = {
            'user_id': user_id,
            'emoji_status_custom_emoji_id': emoji_status_custom_emoji_id,
            'emoji_status_expiration_date': emoji_status_expiration_date,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def get_file(self, file_id: Optional[str] = None) -> Optional["File"]:
        """Use this method to get basic information about a file and prepare it for downloading. For the moment, bots can download files of up to 20MB in size. On success, a File object is returned. The file can then be downloaded via the link https://api.telegram.org/file/bot<token>/<file_path>, where <file_path> is taken from the response. It is guaranteed that the link will be valid for at least 1 hour. When the link expires, a new one can be requested by calling getFile again."""
        method = 'getFile'
        if file_id is None: raise ValueError('file_id required')
        params = {
            'file_id': file_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return File.from_dict(response['result'])
        return None

    def ban_chat_member(self, chat_id: Optional[Union[int, str]] = None, user_id: Optional[int] = None, until_date: Optional[int] = None, revoke_messages: Optional[bool] = None) -> Optional[bool]:
        """Use this method to ban a user in a group, a supergroup or a channel. In the case of supergroups and channels, the user will not be able to return to the chat on their own using invite links, etc., unless unbanned first. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns True on success."""
        method = 'banChatMember'
        if chat_id is None: raise ValueError('chat_id required')
        if user_id is None: raise ValueError('user_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'user_id': user_id,
            'until_date': until_date,
            'revoke_messages': revoke_messages,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def unban_chat_member(self, chat_id: Optional[Union[int, str]] = None, user_id: Optional[int] = None, only_if_banned: Optional[bool] = None) -> Optional[bool]:
        """Use this method to unban a previously banned user in a supergroup or channel. The user will not return to the group or channel automatically, but will be able to join via link, etc. The bot must be an administrator for this to work. By default, this method guarantees that after the call the user is not a member of the chat, but will be able to join it. So if the user is a member of the chat they will also be removed from the chat. If you don't want this, use the parameter only_if_banned. Returns True on success."""
        method = 'unbanChatMember'
        if chat_id is None: raise ValueError('chat_id required')
        if user_id is None: raise ValueError('user_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'user_id': user_id,
            'only_if_banned': only_if_banned,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def restrict_chat_member(self, chat_id: Optional[Union[int, str]] = None, user_id: Optional[int] = None, permissions: Optional["ChatPermissions"] = None, use_independent_chat_permissions: Optional[bool] = None, until_date: Optional[int] = None) -> Optional[bool]:
        """Use this method to restrict a user in a supergroup. The bot must be an administrator in the supergroup for this to work and must have the appropriate administrator rights. Pass True for all permissions to lift restrictions from a user. Returns True on success."""
        method = 'restrictChatMember'
        if chat_id is None: raise ValueError('chat_id required')
        if user_id is None: raise ValueError('user_id required')
        if permissions is None: raise ValueError('permissions required')
        params = {
            'chat_id': _serialize(chat_id),
            'user_id': user_id,
            'permissions': _serialize(permissions),
            'use_independent_chat_permissions': use_independent_chat_permissions,
            'until_date': until_date,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def promote_chat_member(self, chat_id: Optional[Union[int, str]] = None, user_id: Optional[int] = None, is_anonymous: Optional[bool] = None, can_manage_chat: Optional[bool] = None, can_delete_messages: Optional[bool] = None, can_manage_video_chats: Optional[bool] = None, can_restrict_members: Optional[bool] = None, can_promote_members: Optional[bool] = None, can_change_info: Optional[bool] = None, can_invite_users: Optional[bool] = None, can_post_stories: Optional[bool] = None, can_edit_stories: Optional[bool] = None, can_delete_stories: Optional[bool] = None, can_post_messages: Optional[bool] = None, can_edit_messages: Optional[bool] = None, can_pin_messages: Optional[bool] = None, can_manage_topics: Optional[bool] = None, can_manage_direct_messages: Optional[bool] = None) -> Optional[bool]:
        """Use this method to promote or demote a user in a supergroup or a channel. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Pass False for all boolean parameters to demote a user. Returns True on success."""
        method = 'promoteChatMember'
        if chat_id is None: raise ValueError('chat_id required')
        if user_id is None: raise ValueError('user_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'user_id': user_id,
            'is_anonymous': is_anonymous,
            'can_manage_chat': can_manage_chat,
            'can_delete_messages': can_delete_messages,
            'can_manage_video_chats': can_manage_video_chats,
            'can_restrict_members': can_restrict_members,
            'can_promote_members': can_promote_members,
            'can_change_info': can_change_info,
            'can_invite_users': can_invite_users,
            'can_post_stories': can_post_stories,
            'can_edit_stories': can_edit_stories,
            'can_delete_stories': can_delete_stories,
            'can_post_messages': can_post_messages,
            'can_edit_messages': can_edit_messages,
            'can_pin_messages': can_pin_messages,
            'can_manage_topics': can_manage_topics,
            'can_manage_direct_messages': can_manage_direct_messages,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def set_chat_administrator_custom_title(self, chat_id: Optional[Union[int, str]] = None, user_id: Optional[int] = None, custom_title: Optional[str] = None) -> Optional[bool]:
        """Use this method to set a custom title for an administrator in a supergroup promoted by the bot. Returns True on success."""
        method = 'setChatAdministratorCustomTitle'
        if chat_id is None: raise ValueError('chat_id required')
        if user_id is None: raise ValueError('user_id required')
        if custom_title is None: raise ValueError('custom_title required')
        params = {
            'chat_id': _serialize(chat_id),
            'user_id': user_id,
            'custom_title': custom_title,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def ban_chat_sender_chat(self, chat_id: Optional[Union[int, str]] = None, sender_chat_id: Optional[int] = None) -> Optional[bool]:
        """Use this method to ban a channel chat in a supergroup or a channel. Until the chat is unbanned, the owner of the banned chat won't be able to send messages on behalf of any of their channels. The bot must be an administrator in the supergroup or channel for this to work and must have the appropriate administrator rights. Returns True on success."""
        method = 'banChatSenderChat'
        if chat_id is None: raise ValueError('chat_id required')
        if sender_chat_id is None: raise ValueError('sender_chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'sender_chat_id': sender_chat_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def unban_chat_sender_chat(self, chat_id: Optional[Union[int, str]] = None, sender_chat_id: Optional[int] = None) -> Optional[bool]:
        """Use this method to unban a previously banned channel chat in a supergroup or channel. The bot must be an administrator for this to work and must have the appropriate administrator rights. Returns True on success."""
        method = 'unbanChatSenderChat'
        if chat_id is None: raise ValueError('chat_id required')
        if sender_chat_id is None: raise ValueError('sender_chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'sender_chat_id': sender_chat_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def set_chat_permissions(self, chat_id: Optional[Union[int, str]] = None, permissions: Optional["ChatPermissions"] = None, use_independent_chat_permissions: Optional[bool] = None) -> Optional[bool]:
        """Use this method to set default chat permissions for all members. The bot must be an administrator in the group or a supergroup for this to work and must have the can_restrict_members administrator rights. Returns True on success."""
        method = 'setChatPermissions'
        if chat_id is None: raise ValueError('chat_id required')
        if permissions is None: raise ValueError('permissions required')
        params = {
            'chat_id': _serialize(chat_id),
            'permissions': _serialize(permissions),
            'use_independent_chat_permissions': use_independent_chat_permissions,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def export_chat_invite_link(self, chat_id: Optional[Union[int, str]] = None) -> Optional[Any]:
        """Use this method to generate a new primary invite link for a chat; any previously generated primary link is revoked. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns the new invite link as String on success."""
        method = 'exportChatInviteLink'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def create_chat_invite_link(self, chat_id: Optional[Union[int, str]] = None, name: Optional[str] = None, expire_date: Optional[int] = None, member_limit: Optional[int] = None, creates_join_request: Optional[bool] = None) -> Optional["ChatInviteLink"]:
        """Use this method to create an additional invite link for a chat. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. The link can be revoked using the method revokeChatInviteLink. Returns the new invite link as ChatInviteLink object."""
        method = 'createChatInviteLink'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'name': name,
            'expire_date': expire_date,
            'member_limit': member_limit,
            'creates_join_request': creates_join_request,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return ChatInviteLink.from_dict(response['result'])
        return None

    def edit_chat_invite_link(self, chat_id: Optional[Union[int, str]] = None, invite_link: Optional[str] = None, name: Optional[str] = None, expire_date: Optional[int] = None, member_limit: Optional[int] = None, creates_join_request: Optional[bool] = None) -> Optional["ChatInviteLink"]:
        """Use this method to edit a non-primary invite link created by the bot. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns the edited invite link as a ChatInviteLink object."""
        method = 'editChatInviteLink'
        if chat_id is None: raise ValueError('chat_id required')
        if invite_link is None: raise ValueError('invite_link required')
        params = {
            'chat_id': _serialize(chat_id),
            'invite_link': invite_link,
            'name': name,
            'expire_date': expire_date,
            'member_limit': member_limit,
            'creates_join_request': creates_join_request,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return ChatInviteLink.from_dict(response['result'])
        return None

    def create_chat_subscription_invite_link(self, chat_id: Optional[Union[int, str]] = None, subscription_period: Optional[int] = None, subscription_price: Optional[int] = None, name: Optional[str] = None) -> Optional["ChatInviteLink"]:
        """Use this method to create a subscription invite link for a channel chat. The bot must have the can_invite_users administrator rights. The link can be edited using the method editChatSubscriptionInviteLink or revoked using the method revokeChatInviteLink. Returns the new invite link as a ChatInviteLink object."""
        method = 'createChatSubscriptionInviteLink'
        if chat_id is None: raise ValueError('chat_id required')
        if subscription_period is None: raise ValueError('subscription_period required')
        if subscription_price is None: raise ValueError('subscription_price required')
        params = {
            'chat_id': _serialize(chat_id),
            'subscription_period': subscription_period,
            'subscription_price': subscription_price,
            'name': name,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return ChatInviteLink.from_dict(response['result'])
        return None

    def edit_chat_subscription_invite_link(self, chat_id: Optional[Union[int, str]] = None, invite_link: Optional[str] = None, name: Optional[str] = None) -> Optional["ChatInviteLink"]:
        """Use this method to edit a subscription invite link created by the bot. The bot must have the can_invite_users administrator rights. Returns the edited invite link as a ChatInviteLink object."""
        method = 'editChatSubscriptionInviteLink'
        if chat_id is None: raise ValueError('chat_id required')
        if invite_link is None: raise ValueError('invite_link required')
        params = {
            'chat_id': _serialize(chat_id),
            'invite_link': invite_link,
            'name': name,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return ChatInviteLink.from_dict(response['result'])
        return None

    def revoke_chat_invite_link(self, chat_id: Optional[Union[int, str]] = None, invite_link: Optional[str] = None) -> Optional["ChatInviteLink"]:
        """Use this method to revoke an invite link created by the bot. If the primary link is revoked, a new link is automatically generated. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns the revoked invite link as ChatInviteLink object."""
        method = 'revokeChatInviteLink'
        if chat_id is None: raise ValueError('chat_id required')
        if invite_link is None: raise ValueError('invite_link required')
        params = {
            'chat_id': _serialize(chat_id),
            'invite_link': invite_link,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return ChatInviteLink.from_dict(response['result'])
        return None

    def approve_chat_join_request(self, chat_id: Optional[Union[int, str]] = None, user_id: Optional[int] = None) -> Optional[bool]:
        """Use this method to approve a chat join request. The bot must be an administrator in the chat for this to work and must have the can_invite_users administrator right. Returns True on success."""
        method = 'approveChatJoinRequest'
        if chat_id is None: raise ValueError('chat_id required')
        if user_id is None: raise ValueError('user_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'user_id': user_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def decline_chat_join_request(self, chat_id: Optional[Union[int, str]] = None, user_id: Optional[int] = None) -> Optional[bool]:
        """Use this method to decline a chat join request. The bot must be an administrator in the chat for this to work and must have the can_invite_users administrator right. Returns True on success."""
        method = 'declineChatJoinRequest'
        if chat_id is None: raise ValueError('chat_id required')
        if user_id is None: raise ValueError('user_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'user_id': user_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def set_chat_photo(self, chat_id: Optional[Union[int, str]] = None, photo: Optional[Union[str, bytes, IO]] = None) -> Optional[bool]:
        """Use this method to set a new profile photo for the chat. Photos can't be changed for private chats. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns True on success."""
        method = 'setChatPhoto'
        if chat_id is None: raise ValueError('chat_id required')
        if photo is None: raise ValueError('photo required')
        params = {
            'chat_id': _serialize(chat_id),
        }
        params = {k: v for k, v in params.items() if v is not None}
        files = {}
        if photo is not None:
            if hasattr(photo, 'read') or isinstance(photo, bytes):
                files['photo'] = photo
            else:
                params['photo'] = photo
        response = self._make_request(method, params, files=files)
        return response.get('result')

    def delete_chat_photo(self, chat_id: Optional[Union[int, str]] = None) -> Optional[bool]:
        """Use this method to delete a chat photo. Photos can't be changed for private chats. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns True on success."""
        method = 'deleteChatPhoto'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def set_chat_title(self, chat_id: Optional[Union[int, str]] = None, title: Optional[str] = None) -> Optional[bool]:
        """Use this method to change the title of a chat. Titles can't be changed for private chats. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns True on success."""
        method = 'setChatTitle'
        if chat_id is None: raise ValueError('chat_id required')
        if title is None: raise ValueError('title required')
        params = {
            'chat_id': _serialize(chat_id),
            'title': title,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def set_chat_description(self, chat_id: Optional[Union[int, str]] = None, description: Optional[str] = None) -> Optional[bool]:
        """Use this method to change the description of a group, a supergroup or a channel. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Returns True on success."""
        method = 'setChatDescription'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'description': description,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def pin_chat_message(self, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, business_connection_id: Optional[str] = None, disable_notification: Optional[bool] = None) -> Optional[bool]:
        """Use this method to add a message to the list of pinned messages in a chat. In private chats and channel direct messages chats, all non-service messages can be pinned. Conversely, the bot must be an administrator with the 'can_pin_messages' right or the 'can_edit_messages' right to pin messages in groups and channels respectively. Returns True on success."""
        method = 'pinChatMessage'
        if chat_id is None: raise ValueError('chat_id required')
        if message_id is None: raise ValueError('message_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'message_id': message_id,
            'business_connection_id': business_connection_id,
            'disable_notification': disable_notification,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def unpin_chat_message(self, chat_id: Optional[Union[int, str]] = None, business_connection_id: Optional[str] = None, message_id: Optional[int] = None) -> Optional[bool]:
        """Use this method to remove a message from the list of pinned messages in a chat. In private chats and channel direct messages chats, all messages can be unpinned. Conversely, the bot must be an administrator with the 'can_pin_messages' right or the 'can_edit_messages' right to unpin messages in groups and channels respectively. Returns True on success."""
        method = 'unpinChatMessage'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'business_connection_id': business_connection_id,
            'message_id': message_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def unpin_all_chat_messages(self, chat_id: Optional[Union[int, str]] = None) -> Optional[bool]:
        """Use this method to clear the list of pinned messages in a chat. In private chats and channel direct messages chats, no additional rights are required to unpin all pinned messages. Conversely, the bot must be an administrator with the 'can_pin_messages' right or the 'can_edit_messages' right to unpin all pinned messages in groups and channels respectively. Returns True on success."""
        method = 'unpinAllChatMessages'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def leave_chat(self, chat_id: Optional[Union[int, str]] = None) -> Optional[bool]:
        """Use this method for your bot to leave a group, supergroup or channel. Returns True on success."""
        method = 'leaveChat'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def get_chat(self, chat_id: Optional[Union[int, str]] = None) -> Optional["ChatFullInfo"]:
        """Use this method to get up-to-date information about the chat. Returns a ChatFullInfo object on success."""
        method = 'getChat'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return ChatFullInfo.from_dict(response['result'])
        return None

    def get_chat_administrators(self, chat_id: Optional[Union[int, str]] = None) -> Optional[List["ChatMember"]]:
        """Use this method to get a list of administrators in a chat, which aren't bots. Returns an Array of ChatMember objects."""
        method = 'getChatAdministrators'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return [ChatMember.from_dict(x) for x in response['result']]
        return None

    def get_chat_member_count(self, chat_id: Optional[Union[int, str]] = None) -> Optional["Int"]:
        """Use this method to get the number of members in a chat. Returns Int on success."""
        method = 'getChatMemberCount'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Int.from_dict(response['result'])
        return None

    def get_chat_member(self, chat_id: Optional[Union[int, str]] = None, user_id: Optional[int] = None) -> Optional["ChatMember"]:
        """Use this method to get information about a member of a chat. The method is only guaranteed to work for other users if the bot is an administrator in the chat. Returns a ChatMember object on success."""
        method = 'getChatMember'
        if chat_id is None: raise ValueError('chat_id required')
        if user_id is None: raise ValueError('user_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'user_id': user_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return ChatMember.from_dict(response['result'])
        return None

    def set_chat_sticker_set(self, chat_id: Optional[Union[int, str]] = None, sticker_set_name: Optional[str] = None) -> Optional[bool]:
        """Use this method to set a new group sticker set for a supergroup. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Use the field can_set_sticker_set optionally returned in getChat requests to check if the bot can use this method. Returns True on success."""
        method = 'setChatStickerSet'
        if chat_id is None: raise ValueError('chat_id required')
        if sticker_set_name is None: raise ValueError('sticker_set_name required')
        params = {
            'chat_id': _serialize(chat_id),
            'sticker_set_name': sticker_set_name,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def delete_chat_sticker_set(self, chat_id: Optional[Union[int, str]] = None) -> Optional[bool]:
        """Use this method to delete a group sticker set from a supergroup. The bot must be an administrator in the chat for this to work and must have the appropriate administrator rights. Use the field can_set_sticker_set optionally returned in getChat requests to check if the bot can use this method. Returns True on success."""
        method = 'deleteChatStickerSet'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def get_forum_topic_icon_stickers(self) -> Optional[List["Sticker"]]:
        """Use this method to get custom emoji stickers, which can be used as a forum topic icon by any user. Requires no parameters. Returns an Array of Sticker objects."""
        method = 'getForumTopicIconStickers'
        params = {
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return [Sticker.from_dict(x) for x in response['result']]
        return None

    def create_forum_topic(self, chat_id: Optional[Union[int, str]] = None, name: Optional[str] = None, icon_color: Optional[int] = None, icon_custom_emoji_id: Optional[str] = None) -> Optional["ForumTopic"]:
        """Use this method to create a topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights. Returns information about the created topic as a ForumTopic object."""
        method = 'createForumTopic'
        if chat_id is None: raise ValueError('chat_id required')
        if name is None: raise ValueError('name required')
        params = {
            'chat_id': _serialize(chat_id),
            'name': name,
            'icon_color': icon_color,
            'icon_custom_emoji_id': icon_custom_emoji_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return ForumTopic.from_dict(response['result'])
        return None

    def edit_forum_topic(self, chat_id: Optional[Union[int, str]] = None, message_thread_id: Optional[int] = None, name: Optional[str] = None, icon_custom_emoji_id: Optional[str] = None) -> Optional[bool]:
        """Use this method to edit name and icon of a topic in a forum supergroup chat or a private chat with a user. In the case of a supergroup chat the bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights, unless it is the creator of the topic. Returns True on success."""
        method = 'editForumTopic'
        if chat_id is None: raise ValueError('chat_id required')
        if message_thread_id is None: raise ValueError('message_thread_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'message_thread_id': message_thread_id,
            'name': name,
            'icon_custom_emoji_id': icon_custom_emoji_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def close_forum_topic(self, chat_id: Optional[Union[int, str]] = None, message_thread_id: Optional[int] = None) -> Optional[bool]:
        """Use this method to close an open topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights, unless it is the creator of the topic. Returns True on success."""
        method = 'closeForumTopic'
        if chat_id is None: raise ValueError('chat_id required')
        if message_thread_id is None: raise ValueError('message_thread_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'message_thread_id': message_thread_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def reopen_forum_topic(self, chat_id: Optional[Union[int, str]] = None, message_thread_id: Optional[int] = None) -> Optional[bool]:
        """Use this method to reopen a closed topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights, unless it is the creator of the topic. Returns True on success."""
        method = 'reopenForumTopic'
        if chat_id is None: raise ValueError('chat_id required')
        if message_thread_id is None: raise ValueError('message_thread_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'message_thread_id': message_thread_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def delete_forum_topic(self, chat_id: Optional[Union[int, str]] = None, message_thread_id: Optional[int] = None) -> Optional[bool]:
        """Use this method to delete a forum topic along with all its messages in a forum supergroup chat or a private chat with a user. In the case of a supergroup chat the bot must be an administrator in the chat for this to work and must have the can_delete_messages administrator rights. Returns True on success."""
        method = 'deleteForumTopic'
        if chat_id is None: raise ValueError('chat_id required')
        if message_thread_id is None: raise ValueError('message_thread_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'message_thread_id': message_thread_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def unpin_all_forum_topic_messages(self, chat_id: Optional[Union[int, str]] = None, message_thread_id: Optional[int] = None) -> Optional[bool]:
        """Use this method to clear the list of pinned messages in a forum topic in a forum supergroup chat or a private chat with a user. In the case of a supergroup chat the bot must be an administrator in the chat for this to work and must have the can_pin_messages administrator right in the supergroup. Returns True on success."""
        method = 'unpinAllForumTopicMessages'
        if chat_id is None: raise ValueError('chat_id required')
        if message_thread_id is None: raise ValueError('message_thread_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'message_thread_id': message_thread_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def edit_general_forum_topic(self, chat_id: Optional[Union[int, str]] = None, name: Optional[str] = None) -> Optional[bool]:
        """Use this method to edit the name of the 'General' topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights. Returns True on success."""
        method = 'editGeneralForumTopic'
        if chat_id is None: raise ValueError('chat_id required')
        if name is None: raise ValueError('name required')
        params = {
            'chat_id': _serialize(chat_id),
            'name': name,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def close_general_forum_topic(self, chat_id: Optional[Union[int, str]] = None) -> Optional[bool]:
        """Use this method to close an open 'General' topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights. Returns True on success."""
        method = 'closeGeneralForumTopic'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def reopen_general_forum_topic(self, chat_id: Optional[Union[int, str]] = None) -> Optional[bool]:
        """Use this method to reopen a closed 'General' topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights. The topic will be automatically unhidden if it was hidden. Returns True on success."""
        method = 'reopenGeneralForumTopic'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def hide_general_forum_topic(self, chat_id: Optional[Union[int, str]] = None) -> Optional[bool]:
        """Use this method to hide the 'General' topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights. The topic will be automatically closed if it was open. Returns True on success."""
        method = 'hideGeneralForumTopic'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def unhide_general_forum_topic(self, chat_id: Optional[Union[int, str]] = None) -> Optional[bool]:
        """Use this method to unhide the 'General' topic in a forum supergroup chat. The bot must be an administrator in the chat for this to work and must have the can_manage_topics administrator rights. Returns True on success."""
        method = 'unhideGeneralForumTopic'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def unpin_all_general_forum_topic_messages(self, chat_id: Optional[Union[int, str]] = None) -> Optional[bool]:
        """Use this method to clear the list of pinned messages in a General forum topic. The bot must be an administrator in the chat for this to work and must have the can_pin_messages administrator right in the supergroup. Returns True on success."""
        method = 'unpinAllGeneralForumTopicMessages'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def answer_callback_query(self, callback_query_id: Optional[str] = None, text: Optional[str] = None, show_alert: Optional[bool] = None, url: Optional[str] = None, cache_time: Optional[int] = None) -> Optional[Any]:
        """Use this method to send answers to callback queries sent from inline keyboards. The answer will be displayed to the user as a notification at the top of the chat screen or as an alert. On success, True is returned."""
        method = 'answerCallbackQuery'
        if callback_query_id is None: raise ValueError('callback_query_id required')
        params = {
            'callback_query_id': callback_query_id,
            'text': text,
            'show_alert': show_alert,
            'url': url,
            'cache_time': cache_time,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def get_user_chat_boosts(self, chat_id: Optional[Union[int, str]] = None, user_id: Optional[int] = None) -> Optional["UserChatBoosts"]:
        """Use this method to get the list of boosts added to a chat by a user. Requires administrator rights in the chat. Returns a UserChatBoosts object."""
        method = 'getUserChatBoosts'
        if chat_id is None: raise ValueError('chat_id required')
        if user_id is None: raise ValueError('user_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'user_id': user_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return UserChatBoosts.from_dict(response['result'])
        return None

    def get_business_connection(self, business_connection_id: Optional[str] = None) -> Optional["BusinessConnection"]:
        """Use this method to get information about the connection of the bot with a business account. Returns a BusinessConnection object on success."""
        method = 'getBusinessConnection'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        params = {
            'business_connection_id': business_connection_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return BusinessConnection.from_dict(response['result'])
        return None

    def set_my_commands(self, commands: Optional[List["BotCommand"]] = None, scope: Optional[Union["BotCommandScopeDefault", "BotCommandScopeAllPrivateChats", "BotCommandScopeAllGroupChats", "BotCommandScopeAllChatAdministrators", "BotCommandScopeChat", "BotCommandScopeChatAdministrators", "BotCommandScopeChatMember"]] = None, language_code: Optional[str] = None) -> Optional[bool]:
        """Use this method to change the list of the bot's commands. See this manual for more details about bot commands. Returns True on success."""
        method = 'setMyCommands'
        if commands is None: raise ValueError('commands required')
        params = {
            'commands': _serialize(commands),
            'scope': _serialize(scope),
            'language_code': language_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def delete_my_commands(self, scope: Optional[Union["BotCommandScopeDefault", "BotCommandScopeAllPrivateChats", "BotCommandScopeAllGroupChats", "BotCommandScopeAllChatAdministrators", "BotCommandScopeChat", "BotCommandScopeChatAdministrators", "BotCommandScopeChatMember"]] = None, language_code: Optional[str] = None) -> Optional[bool]:
        """Use this method to delete the list of the bot's commands for the given scope and user language. After deletion, higher level commands will be shown to affected users. Returns True on success."""
        method = 'deleteMyCommands'
        params = {
            'scope': _serialize(scope),
            'language_code': language_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def get_my_commands(self, scope: Optional[Union["BotCommandScopeDefault", "BotCommandScopeAllPrivateChats", "BotCommandScopeAllGroupChats", "BotCommandScopeAllChatAdministrators", "BotCommandScopeChat", "BotCommandScopeChatAdministrators", "BotCommandScopeChatMember"]] = None, language_code: Optional[str] = None) -> Optional[List["BotCommand"]]:
        """Use this method to get the current list of the bot's commands for the given scope and user language. Returns an Array of BotCommand objects. If commands aren't set, an empty list is returned."""
        method = 'getMyCommands'
        params = {
            'scope': _serialize(scope),
            'language_code': language_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return [BotCommand.from_dict(x) for x in response['result']]
        return None

    def set_my_name(self, name: Optional[str] = None, language_code: Optional[str] = None) -> Optional[bool]:
        """Use this method to change the bot's name. Returns True on success."""
        method = 'setMyName'
        params = {
            'name': name,
            'language_code': language_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def get_my_name(self, language_code: Optional[str] = None) -> Optional["BotName"]:
        """Use this method to get the current bot name for the given user language. Returns BotName on success."""
        method = 'getMyName'
        params = {
            'language_code': language_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return BotName.from_dict(response['result'])
        return None

    def set_my_description(self, description: Optional[str] = None, language_code: Optional[str] = None) -> Optional[bool]:
        """Use this method to change the bot's description, which is shown in the chat with the bot if the chat is empty. Returns True on success."""
        method = 'setMyDescription'
        params = {
            'description': description,
            'language_code': language_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def get_my_description(self, language_code: Optional[str] = None) -> Optional["BotDescription"]:
        """Use this method to get the current bot description for the given user language. Returns BotDescription on success."""
        method = 'getMyDescription'
        params = {
            'language_code': language_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return BotDescription.from_dict(response['result'])
        return None

    def set_my_short_description(self, short_description: Optional[str] = None, language_code: Optional[str] = None) -> Optional[bool]:
        """Use this method to change the bot's short description, which is shown on the bot's profile page and is sent together with the link when users share the bot. Returns True on success."""
        method = 'setMyShortDescription'
        params = {
            'short_description': short_description,
            'language_code': language_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def get_my_short_description(self, language_code: Optional[str] = None) -> Optional["BotShortDescription"]:
        """Use this method to get the current bot short description for the given user language. Returns BotShortDescription on success."""
        method = 'getMyShortDescription'
        params = {
            'language_code': language_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return BotShortDescription.from_dict(response['result'])
        return None

    def set_chat_menu_button(self, chat_id: Optional[int] = None, menu_button: Optional[Union["MenuButtonCommands", "MenuButtonWebApp", "MenuButtonDefault"]] = None) -> Optional[bool]:
        """Use this method to change the bot's menu button in a private chat, or the default menu button. Returns True on success."""
        method = 'setChatMenuButton'
        params = {
            'chat_id': chat_id,
            'menu_button': _serialize(menu_button),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def get_chat_menu_button(self, chat_id: Optional[int] = None) -> Optional["MenuButton"]:
        """Use this method to get the current value of the bot's menu button in a private chat, or the default menu button. Returns MenuButton on success."""
        method = 'getChatMenuButton'
        params = {
            'chat_id': chat_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return MenuButton.from_dict(response['result'])
        return None

    def set_my_default_administrator_rights(self, rights: Optional["ChatAdministratorRights"] = None, for_channels: Optional[bool] = None) -> Optional[bool]:
        """Use this method to change the default administrator rights requested by the bot when it's added as an administrator to groups or channels. These rights will be suggested to users, but they are free to modify the list before adding the bot. Returns True on success."""
        method = 'setMyDefaultAdministratorRights'
        params = {
            'rights': _serialize(rights),
            'for_channels': for_channels,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def get_my_default_administrator_rights(self, for_channels: Optional[bool] = None) -> Optional["ChatAdministratorRights"]:
        """Use this method to get the current default administrator rights of the bot. Returns ChatAdministratorRights on success."""
        method = 'getMyDefaultAdministratorRights'
        params = {
            'for_channels': for_channels,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return ChatAdministratorRights.from_dict(response['result'])
        return None

    def get_available_gifts(self) -> Optional["Gifts"]:
        """Returns the list of gifts that can be sent by the bot to users and channel chats. Requires no parameters. Returns a Gifts object."""
        method = 'getAvailableGifts'
        params = {
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Gifts.from_dict(response['result'])
        return None

    def send_gift(self, gift_id: Optional[str] = None, user_id: Optional[int] = None, chat_id: Optional[Union[int, str]] = None, pay_for_upgrade: Optional[bool] = None, text: Optional[str] = None, text_parse_mode: Optional[str] = None, text_entities: Optional[List["MessageEntity"]] = None) -> Optional["bool"]:
        """Sends a gift to the given user or channel chat. The gift can't be converted to Telegram Stars by the receiver. Returns True on success."""
        method = 'sendGift'
        if gift_id is None: raise ValueError('gift_id required')
        params = {
            'gift_id': gift_id,
            'user_id': user_id,
            'chat_id': _serialize(chat_id),
            'pay_for_upgrade': pay_for_upgrade,
            'text': text,
            'text_parse_mode': text_parse_mode,
            'text_entities': _serialize(text_entities),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return bool.from_dict(response['result'])
        return None

    def gift_premium_subscription(self, user_id: Optional[int] = None, month_count: Optional[int] = None, star_count: Optional[int] = None, text: Optional[str] = None, text_parse_mode: Optional[str] = None, text_entities: Optional[List["MessageEntity"]] = None) -> Optional[bool]:
        """Gifts a Telegram Premium subscription to the given user. Returns True on success."""
        method = 'giftPremiumSubscription'
        if user_id is None: raise ValueError('user_id required')
        if month_count is None: raise ValueError('month_count required')
        if star_count is None: raise ValueError('star_count required')
        params = {
            'user_id': user_id,
            'month_count': month_count,
            'star_count': star_count,
            'text': text,
            'text_parse_mode': text_parse_mode,
            'text_entities': _serialize(text_entities),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def verify_user(self, user_id: Optional[int] = None, custom_description: Optional[str] = None) -> Optional[bool]:
        """Verifies a user on behalf of the organization which is represented by the bot. Returns True on success."""
        method = 'verifyUser'
        if user_id is None: raise ValueError('user_id required')
        params = {
            'user_id': user_id,
            'custom_description': custom_description,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def verify_chat(self, chat_id: Optional[Union[int, str]] = None, custom_description: Optional[str] = None) -> Optional[bool]:
        """Verifies a chat on behalf of the organization which is represented by the bot. Returns True on success."""
        method = 'verifyChat'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'custom_description': custom_description,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def remove_user_verification(self, user_id: Optional[int] = None) -> Optional[bool]:
        """Removes verification from a user who is currently verified on behalf of the organization represented by the bot. Returns True on success."""
        method = 'removeUserVerification'
        if user_id is None: raise ValueError('user_id required')
        params = {
            'user_id': user_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def remove_chat_verification(self, chat_id: Optional[Union[int, str]] = None) -> Optional[bool]:
        """Removes verification from a chat that is currently verified on behalf of the organization represented by the bot. Returns True on success."""
        method = 'removeChatVerification'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def read_business_message(self, business_connection_id: Optional[str] = None, chat_id: Optional[int] = None, message_id: Optional[int] = None) -> Optional[bool]:
        """Marks incoming message as read on behalf of a business account. Requires the can_read_messages business bot right. Returns True on success."""
        method = 'readBusinessMessage'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        if chat_id is None: raise ValueError('chat_id required')
        if message_id is None: raise ValueError('message_id required')
        params = {
            'business_connection_id': business_connection_id,
            'chat_id': chat_id,
            'message_id': message_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def delete_business_messages(self, business_connection_id: Optional[str] = None, message_ids: Optional[List[int]] = None) -> Optional[bool]:
        """Delete messages on behalf of a business account. Requires the can_delete_sent_messages business bot right to delete messages sent by the bot itself, or the can_delete_all_messages business bot right to delete any message. Returns True on success."""
        method = 'deleteBusinessMessages'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        if message_ids is None: raise ValueError('message_ids required')
        params = {
            'business_connection_id': business_connection_id,
            'message_ids': _serialize(message_ids),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def set_business_account_name(self, business_connection_id: Optional[str] = None, first_name: Optional[str] = None, last_name: Optional[str] = None) -> Optional[bool]:
        """Changes the first and last name of a managed business account. Requires the can_change_name business bot right. Returns True on success."""
        method = 'setBusinessAccountName'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        if first_name is None: raise ValueError('first_name required')
        params = {
            'business_connection_id': business_connection_id,
            'first_name': first_name,
            'last_name': last_name,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def set_business_account_username(self, business_connection_id: Optional[str] = None, username: Optional[str] = None) -> Optional[bool]:
        """Changes the username of a managed business account. Requires the can_change_username business bot right. Returns True on success."""
        method = 'setBusinessAccountUsername'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        params = {
            'business_connection_id': business_connection_id,
            'username': username,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def set_business_account_bio(self, business_connection_id: Optional[str] = None, bio: Optional[str] = None) -> Optional[bool]:
        """Changes the bio of a managed business account. Requires the can_change_bio business bot right. Returns True on success."""
        method = 'setBusinessAccountBio'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        params = {
            'business_connection_id': business_connection_id,
            'bio': bio,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def set_business_account_profile_photo(self, business_connection_id: Optional[str] = None, photo: Optional["InputProfilePhoto"] = None, is_public: Optional[bool] = None) -> Optional[bool]:
        """Changes the profile photo of a managed business account. Requires the can_edit_profile_photo business bot right. Returns True on success."""
        method = 'setBusinessAccountProfilePhoto'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        if photo is None: raise ValueError('photo required')
        params = {
            'business_connection_id': business_connection_id,
            'photo': _serialize(photo),
            'is_public': is_public,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def remove_business_account_profile_photo(self, business_connection_id: Optional[str] = None, is_public: Optional[bool] = None) -> Optional[bool]:
        """Removes the current profile photo of a managed business account. Requires the can_edit_profile_photo business bot right. Returns True on success."""
        method = 'removeBusinessAccountProfilePhoto'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        params = {
            'business_connection_id': business_connection_id,
            'is_public': is_public,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def set_business_account_gift_settings(self, business_connection_id: Optional[str] = None, show_gift_button: Optional[bool] = None, accepted_gift_types: Optional["AcceptedGiftTypes"] = None) -> Optional[bool]:
        """Changes the privacy settings pertaining to incoming gifts in a managed business account. Requires the can_change_gift_settings business bot right. Returns True on success."""
        method = 'setBusinessAccountGiftSettings'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        if show_gift_button is None: raise ValueError('show_gift_button required')
        if accepted_gift_types is None: raise ValueError('accepted_gift_types required')
        params = {
            'business_connection_id': business_connection_id,
            'show_gift_button': show_gift_button,
            'accepted_gift_types': _serialize(accepted_gift_types),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def get_business_account_star_balance(self, business_connection_id: Optional[str] = None) -> Optional["StarAmount"]:
        """Returns the amount of Telegram Stars owned by a managed business account. Requires the can_view_gifts_and_stars business bot right. Returns StarAmount on success."""
        method = 'getBusinessAccountStarBalance'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        params = {
            'business_connection_id': business_connection_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return StarAmount.from_dict(response['result'])
        return None

    def transfer_business_account_stars(self, business_connection_id: Optional[str] = None, star_count: Optional[int] = None) -> Optional[bool]:
        """Transfers Telegram Stars from the business account balance to the bot's balance. Requires the can_transfer_stars business bot right. Returns True on success."""
        method = 'transferBusinessAccountStars'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        if star_count is None: raise ValueError('star_count required')
        params = {
            'business_connection_id': business_connection_id,
            'star_count': star_count,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def get_business_account_gifts(self, business_connection_id: Optional[str] = None, exclude_unsaved: Optional[bool] = None, exclude_saved: Optional[bool] = None, exclude_unlimited: Optional[bool] = None, exclude_limited_upgradable: Optional[bool] = None, exclude_limited_non_upgradable: Optional[bool] = None, exclude_unique: Optional[bool] = None, exclude_from_blockchain: Optional[bool] = None, sort_by_price: Optional[bool] = None, offset: Optional[str] = None, limit: Optional[int] = None) -> Optional["OwnedGifts"]:
        """Returns the gifts received and owned by a managed business account. Requires the can_view_gifts_and_stars business bot right. Returns OwnedGifts on success."""
        method = 'getBusinessAccountGifts'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        params = {
            'business_connection_id': business_connection_id,
            'exclude_unsaved': exclude_unsaved,
            'exclude_saved': exclude_saved,
            'exclude_unlimited': exclude_unlimited,
            'exclude_limited_upgradable': exclude_limited_upgradable,
            'exclude_limited_non_upgradable': exclude_limited_non_upgradable,
            'exclude_unique': exclude_unique,
            'exclude_from_blockchain': exclude_from_blockchain,
            'sort_by_price': sort_by_price,
            'offset': offset,
            'limit': limit,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return OwnedGifts.from_dict(response['result'])
        return None

    def get_user_gifts(self, user_id: Optional[int] = None, exclude_unlimited: Optional[bool] = None, exclude_limited_upgradable: Optional[bool] = None, exclude_limited_non_upgradable: Optional[bool] = None, exclude_from_blockchain: Optional[bool] = None, exclude_unique: Optional[bool] = None, sort_by_price: Optional[bool] = None, offset: Optional[str] = None, limit: Optional[int] = None) -> Optional["OwnedGifts"]:
        """Returns the gifts owned and hosted by a user. Returns OwnedGifts on success."""
        method = 'getUserGifts'
        if user_id is None: raise ValueError('user_id required')
        params = {
            'user_id': user_id,
            'exclude_unlimited': exclude_unlimited,
            'exclude_limited_upgradable': exclude_limited_upgradable,
            'exclude_limited_non_upgradable': exclude_limited_non_upgradable,
            'exclude_from_blockchain': exclude_from_blockchain,
            'exclude_unique': exclude_unique,
            'sort_by_price': sort_by_price,
            'offset': offset,
            'limit': limit,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return OwnedGifts.from_dict(response['result'])
        return None

    def get_chat_gifts(self, chat_id: Optional[Union[int, str]] = None, exclude_unsaved: Optional[bool] = None, exclude_saved: Optional[bool] = None, exclude_unlimited: Optional[bool] = None, exclude_limited_upgradable: Optional[bool] = None, exclude_limited_non_upgradable: Optional[bool] = None, exclude_from_blockchain: Optional[bool] = None, exclude_unique: Optional[bool] = None, sort_by_price: Optional[bool] = None, offset: Optional[str] = None, limit: Optional[int] = None) -> Optional["OwnedGifts"]:
        """Returns the gifts owned by a chat. Returns OwnedGifts on success."""
        method = 'getChatGifts'
        if chat_id is None: raise ValueError('chat_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'exclude_unsaved': exclude_unsaved,
            'exclude_saved': exclude_saved,
            'exclude_unlimited': exclude_unlimited,
            'exclude_limited_upgradable': exclude_limited_upgradable,
            'exclude_limited_non_upgradable': exclude_limited_non_upgradable,
            'exclude_from_blockchain': exclude_from_blockchain,
            'exclude_unique': exclude_unique,
            'sort_by_price': sort_by_price,
            'offset': offset,
            'limit': limit,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return OwnedGifts.from_dict(response['result'])
        return None

    def convert_gift_to_stars(self, business_connection_id: Optional[str] = None, owned_gift_id: Optional[str] = None) -> Optional[bool]:
        """Converts a given regular gift to Telegram Stars. Requires the can_convert_gifts_to_stars business bot right. Returns True on success."""
        method = 'convertGiftToStars'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        if owned_gift_id is None: raise ValueError('owned_gift_id required')
        params = {
            'business_connection_id': business_connection_id,
            'owned_gift_id': owned_gift_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def upgrade_gift(self, business_connection_id: Optional[str] = None, owned_gift_id: Optional[str] = None, keep_original_details: Optional[bool] = None, star_count: Optional[int] = None) -> Optional[bool]:
        """Upgrades a given regular gift to a unique gift. Requires the can_transfer_and_upgrade_gifts business bot right. Additionally requires the can_transfer_stars business bot right if the upgrade is paid. Returns True on success."""
        method = 'upgradeGift'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        if owned_gift_id is None: raise ValueError('owned_gift_id required')
        params = {
            'business_connection_id': business_connection_id,
            'owned_gift_id': owned_gift_id,
            'keep_original_details': keep_original_details,
            'star_count': star_count,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def transfer_gift(self, business_connection_id: Optional[str] = None, owned_gift_id: Optional[str] = None, new_owner_chat_id: Optional[int] = None, star_count: Optional[int] = None) -> Optional[bool]:
        """Transfers an owned unique gift to another user. Requires the can_transfer_and_upgrade_gifts business bot right. Requires can_transfer_stars business bot right if the transfer is paid. Returns True on success."""
        method = 'transferGift'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        if owned_gift_id is None: raise ValueError('owned_gift_id required')
        if new_owner_chat_id is None: raise ValueError('new_owner_chat_id required')
        params = {
            'business_connection_id': business_connection_id,
            'owned_gift_id': owned_gift_id,
            'new_owner_chat_id': new_owner_chat_id,
            'star_count': star_count,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def post_story(self, business_connection_id: Optional[str] = None, content: Optional["InputStoryContent"] = None, active_period: Optional[int] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, areas: Optional[List["StoryArea"]] = None, post_to_chat_page: Optional[bool] = None, protect_content: Optional[bool] = None) -> Optional["Story"]:
        """Posts a story on behalf of a managed business account. Requires the can_manage_stories business bot right. Returns Story on success."""
        method = 'postStory'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        if content is None: raise ValueError('content required')
        if active_period is None: raise ValueError('active_period required')
        params = {
            'business_connection_id': business_connection_id,
            'content': _serialize(content),
            'active_period': active_period,
            'caption': caption,
            'parse_mode': parse_mode,
            'caption_entities': _serialize(caption_entities),
            'areas': _serialize(areas),
            'post_to_chat_page': post_to_chat_page,
            'protect_content': protect_content,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Story.from_dict(response['result'])
        return None

    def repost_story(self, business_connection_id: Optional[str] = None, from_chat_id: Optional[int] = None, from_story_id: Optional[int] = None, active_period: Optional[int] = None, post_to_chat_page: Optional[bool] = None, protect_content: Optional[bool] = None) -> Optional["Story"]:
        """Reposts a story on behalf of a business account from another business account. Both business accounts must be managed by the same bot, and the story on the source account must have been posted (or reposted) by the bot. Requires the can_manage_stories business bot right for both business accounts. Returns Story on success."""
        method = 'repostStory'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        if from_chat_id is None: raise ValueError('from_chat_id required')
        if from_story_id is None: raise ValueError('from_story_id required')
        if active_period is None: raise ValueError('active_period required')
        params = {
            'business_connection_id': business_connection_id,
            'from_chat_id': from_chat_id,
            'from_story_id': from_story_id,
            'active_period': active_period,
            'post_to_chat_page': post_to_chat_page,
            'protect_content': protect_content,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Story.from_dict(response['result'])
        return None

    def edit_story(self, business_connection_id: Optional[str] = None, story_id: Optional[int] = None, content: Optional["InputStoryContent"] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, areas: Optional[List["StoryArea"]] = None) -> Optional["Story"]:
        """Edits a story previously posted by the bot on behalf of a managed business account. Requires the can_manage_stories business bot right. Returns Story on success."""
        method = 'editStory'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        if story_id is None: raise ValueError('story_id required')
        if content is None: raise ValueError('content required')
        params = {
            'business_connection_id': business_connection_id,
            'story_id': story_id,
            'content': _serialize(content),
            'caption': caption,
            'parse_mode': parse_mode,
            'caption_entities': _serialize(caption_entities),
            'areas': _serialize(areas),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Story.from_dict(response['result'])
        return None

    def delete_story(self, business_connection_id: Optional[str] = None, story_id: Optional[int] = None) -> Optional[bool]:
        """Deletes a story previously posted by the bot on behalf of a managed business account. Requires the can_manage_stories business bot right. Returns True on success."""
        method = 'deleteStory'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        if story_id is None: raise ValueError('story_id required')
        params = {
            'business_connection_id': business_connection_id,
            'story_id': story_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def edit_message_text(self, text: Optional[str] = None, business_connection_id: Optional[str] = None, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None, parse_mode: Optional[str] = None, entities: Optional[List["MessageEntity"]] = None, link_preview_options: Optional["LinkPreviewOptions"] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> Optional["Message"]:
        """Use this method to edit text and game messages. On success, if the edited message is not an inline message, the edited Message is returned, otherwise True is returned. Note that business messages that were not sent by the bot and do not contain an inline keyboard can only be edited within 48 hours from the time they were sent."""
        method = 'editMessageText'
        if text is None: raise ValueError('text required')
        params = {
            'text': text,
            'business_connection_id': business_connection_id,
            'chat_id': _serialize(chat_id),
            'message_id': message_id,
            'inline_message_id': inline_message_id,
            'parse_mode': parse_mode,
            'entities': _serialize(entities),
            'link_preview_options': _serialize(link_preview_options),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def edit_message_caption(self, business_connection_id: Optional[str] = None, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None, caption: Optional[str] = None, parse_mode: Optional[str] = None, caption_entities: Optional[List["MessageEntity"]] = None, show_caption_above_media: Optional[bool] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> Optional["Message"]:
        """Use this method to edit captions of messages. On success, if the edited message is not an inline message, the edited Message is returned, otherwise True is returned. Note that business messages that were not sent by the bot and do not contain an inline keyboard can only be edited within 48 hours from the time they were sent."""
        method = 'editMessageCaption'
        params = {
            'business_connection_id': business_connection_id,
            'chat_id': _serialize(chat_id),
            'message_id': message_id,
            'inline_message_id': inline_message_id,
            'caption': caption,
            'parse_mode': parse_mode,
            'caption_entities': _serialize(caption_entities),
            'show_caption_above_media': show_caption_above_media,
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def edit_message_media(self, media: Optional[Union["InputMediaPhoto", "InputMediaVideo", "InputMediaAnimation", "InputMediaAudio", "InputMediaDocument"]] = None, business_connection_id: Optional[str] = None, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> Optional["Message"]:
        """Use this method to edit animation, audio, document, photo, or video messages, or to add media to text messages. If a message is part of a message album, then it can be edited only to an audio for audio albums, only to a document for document albums and to a photo or a video otherwise. When an inline message is edited, a new file can't be uploaded; use a previously uploaded file via its file_id or specify a URL. On success, if the edited message is not an inline message, the edited Message is returned, otherwise True is returned. Note that business messages that were not sent by the bot and do not contain an inline keyboard can only be edited within 48 hours from the time they were sent."""
        method = 'editMessageMedia'
        if media is None: raise ValueError('media required')
        params = {
            'media': _serialize(media),
            'business_connection_id': business_connection_id,
            'chat_id': _serialize(chat_id),
            'message_id': message_id,
            'inline_message_id': inline_message_id,
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def edit_message_live_location(self, latitude: Optional[float] = None, longitude: Optional[float] = None, business_connection_id: Optional[str] = None, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None, live_period: Optional[int] = None, horizontal_accuracy: Optional[float] = None, heading: Optional[int] = None, proximity_alert_radius: Optional[int] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> Optional[Any]:
        """Use this method to edit live location messages. A location can be edited until its live_period expires or editing is explicitly disabled by a call to stopMessageLiveLocation. On success, if the edited message is not an inline message, the edited Message is returned, otherwise True is returned."""
        method = 'editMessageLiveLocation'
        if latitude is None: raise ValueError('latitude required')
        if longitude is None: raise ValueError('longitude required')
        params = {
            'latitude': latitude,
            'longitude': longitude,
            'business_connection_id': business_connection_id,
            'chat_id': _serialize(chat_id),
            'message_id': message_id,
            'inline_message_id': inline_message_id,
            'live_period': live_period,
            'horizontal_accuracy': horizontal_accuracy,
            'heading': heading,
            'proximity_alert_radius': proximity_alert_radius,
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def stop_message_live_location(self, business_connection_id: Optional[str] = None, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> Optional["Message"]:
        """Use this method to stop updating a live location message before live_period expires. On success, if the message is not an inline message, the edited Message is returned, otherwise True is returned."""
        method = 'stopMessageLiveLocation'
        params = {
            'business_connection_id': business_connection_id,
            'chat_id': _serialize(chat_id),
            'message_id': message_id,
            'inline_message_id': inline_message_id,
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def edit_message_checklist(self, business_connection_id: Optional[str] = None, chat_id: Optional[int] = None, message_id: Optional[int] = None, checklist: Optional["InputChecklist"] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> Optional[Any]:
        """Use this method to edit a checklist on behalf of a connected business account. On success, the edited Message is returned."""
        method = 'editMessageChecklist'
        if business_connection_id is None: raise ValueError('business_connection_id required')
        if chat_id is None: raise ValueError('chat_id required')
        if message_id is None: raise ValueError('message_id required')
        if checklist is None: raise ValueError('checklist required')
        params = {
            'business_connection_id': business_connection_id,
            'chat_id': chat_id,
            'message_id': message_id,
            'checklist': _serialize(checklist),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def edit_message_reply_markup(self, business_connection_id: Optional[str] = None, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> Optional["Message"]:
        """Use this method to edit only the reply markup of messages. On success, if the edited message is not an inline message, the edited Message is returned, otherwise True is returned. Note that business messages that were not sent by the bot and do not contain an inline keyboard can only be edited within 48 hours from the time they were sent."""
        method = 'editMessageReplyMarkup'
        params = {
            'business_connection_id': business_connection_id,
            'chat_id': _serialize(chat_id),
            'message_id': message_id,
            'inline_message_id': inline_message_id,
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def stop_poll(self, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None, business_connection_id: Optional[str] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> Optional["Poll"]:
        """Use this method to stop a poll which was sent by the bot. On success, the stopped Poll is returned."""
        method = 'stopPoll'
        if chat_id is None: raise ValueError('chat_id required')
        if message_id is None: raise ValueError('message_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'message_id': message_id,
            'business_connection_id': business_connection_id,
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Poll.from_dict(response['result'])
        return None

    def approve_suggested_post(self, chat_id: Optional[int] = None, message_id: Optional[int] = None, send_date: Optional[int] = None) -> Optional[bool]:
        """Use this method to approve a suggested post in a direct messages chat. The bot must have the 'can_post_messages' administrator right in the corresponding channel chat. Returns True on success."""
        method = 'approveSuggestedPost'
        if chat_id is None: raise ValueError('chat_id required')
        if message_id is None: raise ValueError('message_id required')
        params = {
            'chat_id': chat_id,
            'message_id': message_id,
            'send_date': send_date,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def decline_suggested_post(self, chat_id: Optional[int] = None, message_id: Optional[int] = None, comment: Optional[str] = None) -> Optional[bool]:
        """Use this method to decline a suggested post in a direct messages chat. The bot must have the 'can_manage_direct_messages' administrator right in the corresponding channel chat. Returns True on success."""
        method = 'declineSuggestedPost'
        if chat_id is None: raise ValueError('chat_id required')
        if message_id is None: raise ValueError('message_id required')
        params = {
            'chat_id': chat_id,
            'message_id': message_id,
            'comment': comment,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def delete_message(self, chat_id: Optional[Union[int, str]] = None, message_id: Optional[int] = None) -> Optional[bool]:
        """Use this method to delete a message, including service messages, with the following limitations:- A message can only be deleted if it was sent less than 48 hours ago.- Service messages about a supergroup, channel, or forum topic creation can't be deleted.- A dice message in a private chat can only be deleted if it was sent more than 24 hours ago.- Bots can delete outgoing messages in private chats, groups, and supergroups.- Bots can delete incoming messages in private chats.- Bots granted can_post_messages permissions can delete outgoing messages in channels.- If the bot is an administrator of a group, it can delete any message there.- If the bot has can_delete_messages administrator right in a supergroup or a channel, it can delete any message there.- If the bot has can_manage_direct_messages administrator right in a channel, it can delete any message in the corresponding direct messages chat.Returns True on success."""
        method = 'deleteMessage'
        if chat_id is None: raise ValueError('chat_id required')
        if message_id is None: raise ValueError('message_id required')
        params = {
            'chat_id': _serialize(chat_id),
            'message_id': message_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def delete_messages(self, chat_id: Optional[Union[int, str]] = None, message_ids: Optional[List[int]] = None) -> Optional[bool]:
        """Use this method to delete multiple messages simultaneously. If some of the specified messages can't be found, they are skipped. Returns True on success."""
        method = 'deleteMessages'
        if chat_id is None: raise ValueError('chat_id required')
        if message_ids is None: raise ValueError('message_ids required')
        params = {
            'chat_id': _serialize(chat_id),
            'message_ids': _serialize(message_ids),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def send_sticker(self, chat_id: Optional[Union[int, str]] = None, sticker: Optional[Union[Union[str, bytes, IO], str]] = None, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, emoji: Optional[str] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional[Union["ForceReply", "InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove"]] = None) -> Optional["Message"]:
        """Use this method to send static .WEBP, animated .TGS, or video .WEBM stickers. On success, the sent Message is returned."""
        method = 'sendSticker'
        if chat_id is None: raise ValueError('chat_id required')
        if sticker is None: raise ValueError('sticker required')
        params = {
            'chat_id': _serialize(chat_id),
            'business_connection_id': business_connection_id,
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'emoji': emoji,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'allow_paid_broadcast': allow_paid_broadcast,
            'message_effect_id': message_effect_id,
            'suggested_post_parameters': _serialize(suggested_post_parameters),
            'reply_parameters': _serialize(reply_parameters),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        files = {}
        if sticker is not None:
            if hasattr(sticker, 'read') or isinstance(sticker, bytes):
                files['sticker'] = sticker
            else:
                params['sticker'] = sticker
        response = self._make_request(method, params, files=files)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def get_sticker_set(self, name: Optional[str] = None) -> Optional["StickerSet"]:
        """Use this method to get a sticker set. On success, a StickerSet object is returned."""
        method = 'getStickerSet'
        if name is None: raise ValueError('name required')
        params = {
            'name': name,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return StickerSet.from_dict(response['result'])
        return None

    def get_custom_emoji_stickers(self, custom_emoji_ids: Optional[List[str]] = None) -> Optional[List["Sticker"]]:
        """Use this method to get information about custom emoji stickers by their identifiers. Returns an Array of Sticker objects."""
        method = 'getCustomEmojiStickers'
        if custom_emoji_ids is None: raise ValueError('custom_emoji_ids required')
        params = {
            'custom_emoji_ids': _serialize(custom_emoji_ids),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return [Sticker.from_dict(x) for x in response['result']]
        return None

    def upload_sticker_file(self, user_id: Optional[int] = None, sticker: Optional[Union[str, bytes, IO]] = None, sticker_format: Optional[str] = None) -> Optional["File"]:
        """Use this method to upload a file with a sticker for later use in the createNewStickerSet, addStickerToSet, or replaceStickerInSet methods (the file can be used multiple times). Returns the uploaded File on success."""
        method = 'uploadStickerFile'
        if user_id is None: raise ValueError('user_id required')
        if sticker is None: raise ValueError('sticker required')
        if sticker_format is None: raise ValueError('sticker_format required')
        params = {
            'user_id': user_id,
            'sticker_format': sticker_format,
        }
        params = {k: v for k, v in params.items() if v is not None}
        files = {}
        if sticker is not None:
            if hasattr(sticker, 'read') or isinstance(sticker, bytes):
                files['sticker'] = sticker
            else:
                params['sticker'] = sticker
        response = self._make_request(method, params, files=files)
        if response and 'result' in response:
            return File.from_dict(response['result'])
        return None

    def create_new_sticker_set(self, user_id: Optional[int] = None, name: Optional[str] = None, title: Optional[str] = None, stickers: Optional[List["InputSticker"]] = None, sticker_type: Optional[str] = None, needs_repainting: Optional[bool] = None) -> Optional[bool]:
        """Use this method to create a new sticker set owned by a user. The bot will be able to edit the sticker set thus created. Returns True on success."""
        method = 'createNewStickerSet'
        if user_id is None: raise ValueError('user_id required')
        if name is None: raise ValueError('name required')
        if title is None: raise ValueError('title required')
        if stickers is None: raise ValueError('stickers required')
        params = {
            'user_id': user_id,
            'name': name,
            'title': title,
            'stickers': _serialize(stickers),
            'sticker_type': sticker_type,
            'needs_repainting': needs_repainting,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def add_sticker_to_set(self, user_id: Optional[int] = None, name: Optional[str] = None, sticker: Optional["InputSticker"] = None) -> Optional[bool]:
        """Use this method to add a new sticker to a set created by the bot. Emoji sticker sets can have up to 200 stickers. Other sticker sets can have up to 120 stickers. Returns True on success."""
        method = 'addStickerToSet'
        if user_id is None: raise ValueError('user_id required')
        if name is None: raise ValueError('name required')
        if sticker is None: raise ValueError('sticker required')
        params = {
            'user_id': user_id,
            'name': name,
            'sticker': _serialize(sticker),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def set_sticker_position_in_set(self, sticker: Optional[str] = None, position: Optional[int] = None) -> Optional[bool]:
        """Use this method to move a sticker in a set created by the bot to a specific position. Returns True on success."""
        method = 'setStickerPositionInSet'
        if sticker is None: raise ValueError('sticker required')
        if position is None: raise ValueError('position required')
        params = {
            'sticker': sticker,
            'position': position,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def delete_sticker_from_set(self, sticker: Optional[str] = None) -> Optional[bool]:
        """Use this method to delete a sticker from a set created by the bot. Returns True on success."""
        method = 'deleteStickerFromSet'
        if sticker is None: raise ValueError('sticker required')
        params = {
            'sticker': sticker,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def replace_sticker_in_set(self, user_id: Optional[int] = None, name: Optional[str] = None, old_sticker: Optional[str] = None, sticker: Optional["InputSticker"] = None) -> Optional[bool]:
        """Use this method to replace an existing sticker in a sticker set with a new one. The method is equivalent to calling deleteStickerFromSet, then addStickerToSet, then setStickerPositionInSet. Returns True on success."""
        method = 'replaceStickerInSet'
        if user_id is None: raise ValueError('user_id required')
        if name is None: raise ValueError('name required')
        if old_sticker is None: raise ValueError('old_sticker required')
        if sticker is None: raise ValueError('sticker required')
        params = {
            'user_id': user_id,
            'name': name,
            'old_sticker': old_sticker,
            'sticker': _serialize(sticker),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def set_sticker_emoji_list(self, sticker: Optional[str] = None, emoji_list: Optional[List[str]] = None) -> Optional[bool]:
        """Use this method to change the list of emoji assigned to a regular or custom emoji sticker. The sticker must belong to a sticker set created by the bot. Returns True on success."""
        method = 'setStickerEmojiList'
        if sticker is None: raise ValueError('sticker required')
        if emoji_list is None: raise ValueError('emoji_list required')
        params = {
            'sticker': sticker,
            'emoji_list': _serialize(emoji_list),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def set_sticker_keywords(self, sticker: Optional[str] = None, keywords: Optional[List[str]] = None) -> Optional[bool]:
        """Use this method to change search keywords assigned to a regular or custom emoji sticker. The sticker must belong to a sticker set created by the bot. Returns True on success."""
        method = 'setStickerKeywords'
        if sticker is None: raise ValueError('sticker required')
        params = {
            'sticker': sticker,
            'keywords': _serialize(keywords),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def set_sticker_mask_position(self, sticker: Optional[str] = None, mask_position: Optional["MaskPosition"] = None) -> Optional[bool]:
        """Use this method to change the mask position of a mask sticker. The sticker must belong to a sticker set that was created by the bot. Returns True on success."""
        method = 'setStickerMaskPosition'
        if sticker is None: raise ValueError('sticker required')
        params = {
            'sticker': sticker,
            'mask_position': _serialize(mask_position),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def set_sticker_set_title(self, name: Optional[str] = None, title: Optional[str] = None) -> Optional[bool]:
        """Use this method to set the title of a created sticker set. Returns True on success."""
        method = 'setStickerSetTitle'
        if name is None: raise ValueError('name required')
        if title is None: raise ValueError('title required')
        params = {
            'name': name,
            'title': title,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def set_sticker_set_thumbnail(self, name: Optional[str] = None, user_id: Optional[int] = None, format: Optional[str] = None, thumbnail: Optional[Union[Union[str, bytes, IO], str]] = None) -> Optional[bool]:
        """Use this method to set the thumbnail of a regular or mask sticker set. The format of the thumbnail file must match the format of the stickers in the set. Returns True on success."""
        method = 'setStickerSetThumbnail'
        if name is None: raise ValueError('name required')
        if user_id is None: raise ValueError('user_id required')
        if format is None: raise ValueError('format required')
        params = {
            'name': name,
            'user_id': user_id,
            'format': format,
        }
        params = {k: v for k, v in params.items() if v is not None}
        files = {}
        if thumbnail is not None:
            if hasattr(thumbnail, 'read') or isinstance(thumbnail, bytes):
                files['thumbnail'] = thumbnail
            else:
                params['thumbnail'] = thumbnail
        response = self._make_request(method, params, files=files)
        return response.get('result')

    def set_custom_emoji_sticker_set_thumbnail(self, name: Optional[str] = None, custom_emoji_id: Optional[str] = None) -> Optional[bool]:
        """Use this method to set the thumbnail of a custom emoji sticker set. Returns True on success."""
        method = 'setCustomEmojiStickerSetThumbnail'
        if name is None: raise ValueError('name required')
        params = {
            'name': name,
            'custom_emoji_id': custom_emoji_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def delete_sticker_set(self, name: Optional[str] = None) -> Optional[bool]:
        """Use this method to delete a sticker set that was created by the bot. Returns True on success."""
        method = 'deleteStickerSet'
        if name is None: raise ValueError('name required')
        params = {
            'name': name,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def answer_inline_query(self, inline_query_id: Optional[str] = None, results: Optional[List["InlineQueryResult"]] = None, cache_time: Optional[int] = None, is_personal: Optional[bool] = None, next_offset: Optional[str] = None, button: Optional["InlineQueryResultsButton"] = None) -> Optional[Any]:
        """Use this method to send answers to an inline query. On success, True is returned.No more than 50 results per query are allowed."""
        method = 'answerInlineQuery'
        if inline_query_id is None: raise ValueError('inline_query_id required')
        if results is None: raise ValueError('results required')
        params = {
            'inline_query_id': inline_query_id,
            'results': _serialize(results),
            'cache_time': cache_time,
            'is_personal': is_personal,
            'next_offset': next_offset,
            'button': _serialize(button),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def answer_web_app_query(self, web_app_query_id: Optional[str] = None, result: Optional["InlineQueryResult"] = None) -> Optional[Any]:
        """Use this method to set the result of an interaction with a Web App and send a corresponding message on behalf of the user to the chat from which the query originated. On success, a SentWebAppMessage object is returned."""
        method = 'answerWebAppQuery'
        if web_app_query_id is None: raise ValueError('web_app_query_id required')
        if result is None: raise ValueError('result required')
        params = {
            'web_app_query_id': web_app_query_id,
            'result': _serialize(result),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def save_prepared_inline_message(self, user_id: Optional[int] = None, result: Optional["InlineQueryResult"] = None, allow_user_chats: Optional[bool] = None, allow_bot_chats: Optional[bool] = None, allow_group_chats: Optional[bool] = None, allow_channel_chats: Optional[bool] = None) -> Optional["PreparedInlineMessage"]:
        """Stores a message that can be sent by a user of a Mini App. Returns a PreparedInlineMessage object."""
        method = 'savePreparedInlineMessage'
        if user_id is None: raise ValueError('user_id required')
        if result is None: raise ValueError('result required')
        params = {
            'user_id': user_id,
            'result': _serialize(result),
            'allow_user_chats': allow_user_chats,
            'allow_bot_chats': allow_bot_chats,
            'allow_group_chats': allow_group_chats,
            'allow_channel_chats': allow_channel_chats,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return PreparedInlineMessage.from_dict(response['result'])
        return None

    def send_invoice(self, chat_id: Optional[Union[int, str]] = None, title: Optional[str] = None, description: Optional[str] = None, payload: Optional[str] = None, currency: Optional[str] = None, prices: Optional[List["LabeledPrice"]] = None, message_thread_id: Optional[int] = None, direct_messages_topic_id: Optional[int] = None, provider_token: Optional[str] = None, max_tip_amount: Optional[int] = None, suggested_tip_amounts: Optional[List[int]] = None, start_parameter: Optional[str] = None, provider_data: Optional[str] = None, photo_url: Optional[str] = None, photo_size: Optional[int] = None, photo_width: Optional[int] = None, photo_height: Optional[int] = None, need_name: Optional[bool] = None, need_phone_number: Optional[bool] = None, need_email: Optional[bool] = None, need_shipping_address: Optional[bool] = None, send_phone_number_to_provider: Optional[bool] = None, send_email_to_provider: Optional[bool] = None, is_flexible: Optional[bool] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, suggested_post_parameters: Optional["SuggestedPostParameters"] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> Optional["Message"]:
        """Use this method to send invoices. On success, the sent Message is returned."""
        method = 'sendInvoice'
        if chat_id is None: raise ValueError('chat_id required')
        if title is None: raise ValueError('title required')
        if description is None: raise ValueError('description required')
        if payload is None: raise ValueError('payload required')
        if currency is None: raise ValueError('currency required')
        if prices is None: raise ValueError('prices required')
        params = {
            'chat_id': _serialize(chat_id),
            'title': title,
            'description': description,
            'payload': payload,
            'currency': currency,
            'prices': _serialize(prices),
            'message_thread_id': message_thread_id,
            'direct_messages_topic_id': direct_messages_topic_id,
            'provider_token': provider_token,
            'max_tip_amount': max_tip_amount,
            'suggested_tip_amounts': _serialize(suggested_tip_amounts),
            'start_parameter': start_parameter,
            'provider_data': provider_data,
            'photo_url': photo_url,
            'photo_size': photo_size,
            'photo_width': photo_width,
            'photo_height': photo_height,
            'need_name': need_name,
            'need_phone_number': need_phone_number,
            'need_email': need_email,
            'need_shipping_address': need_shipping_address,
            'send_phone_number_to_provider': send_phone_number_to_provider,
            'send_email_to_provider': send_email_to_provider,
            'is_flexible': is_flexible,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'allow_paid_broadcast': allow_paid_broadcast,
            'message_effect_id': message_effect_id,
            'suggested_post_parameters': _serialize(suggested_post_parameters),
            'reply_parameters': _serialize(reply_parameters),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def create_invoice_link(self, title: Optional[str] = None, description: Optional[str] = None, payload: Optional[str] = None, currency: Optional[str] = None, prices: Optional[List["LabeledPrice"]] = None, business_connection_id: Optional[str] = None, provider_token: Optional[str] = None, subscription_period: Optional[int] = None, max_tip_amount: Optional[int] = None, suggested_tip_amounts: Optional[List[int]] = None, provider_data: Optional[str] = None, photo_url: Optional[str] = None, photo_size: Optional[int] = None, photo_width: Optional[int] = None, photo_height: Optional[int] = None, need_name: Optional[bool] = None, need_phone_number: Optional[bool] = None, need_email: Optional[bool] = None, need_shipping_address: Optional[bool] = None, send_phone_number_to_provider: Optional[bool] = None, send_email_to_provider: Optional[bool] = None, is_flexible: Optional[bool] = None) -> Optional[Any]:
        """Use this method to create a link for an invoice. Returns the created invoice link as String on success."""
        method = 'createInvoiceLink'
        if title is None: raise ValueError('title required')
        if description is None: raise ValueError('description required')
        if payload is None: raise ValueError('payload required')
        if currency is None: raise ValueError('currency required')
        if prices is None: raise ValueError('prices required')
        params = {
            'title': title,
            'description': description,
            'payload': payload,
            'currency': currency,
            'prices': _serialize(prices),
            'business_connection_id': business_connection_id,
            'provider_token': provider_token,
            'subscription_period': subscription_period,
            'max_tip_amount': max_tip_amount,
            'suggested_tip_amounts': _serialize(suggested_tip_amounts),
            'provider_data': provider_data,
            'photo_url': photo_url,
            'photo_size': photo_size,
            'photo_width': photo_width,
            'photo_height': photo_height,
            'need_name': need_name,
            'need_phone_number': need_phone_number,
            'need_email': need_email,
            'need_shipping_address': need_shipping_address,
            'send_phone_number_to_provider': send_phone_number_to_provider,
            'send_email_to_provider': send_email_to_provider,
            'is_flexible': is_flexible,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def answer_shipping_query(self, shipping_query_id: Optional[str] = None, ok: Optional[bool] = None, shipping_options: Optional[List["ShippingOption"]] = None, error_message: Optional[str] = None) -> Optional[Any]:
        """If you sent an invoice requesting a shipping address and the parameter is_flexible was specified, the Bot API will send an Update with a shipping_query field to the bot. Use this method to reply to shipping queries. On success, True is returned."""
        method = 'answerShippingQuery'
        if shipping_query_id is None: raise ValueError('shipping_query_id required')
        if ok is None: raise ValueError('ok required')
        params = {
            'shipping_query_id': shipping_query_id,
            'ok': ok,
            'shipping_options': _serialize(shipping_options),
            'error_message': error_message,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def answer_pre_checkout_query(self, pre_checkout_query_id: Optional[str] = None, ok: Optional[bool] = None, error_message: Optional[str] = None) -> Optional[Any]:
        """Once the user has confirmed their payment and shipping details, the Bot API sends the final confirmation in the form of an Update with the field pre_checkout_query. Use this method to respond to such pre-checkout queries. On success, True is returned. Note: The Bot API must receive an answer within 10 seconds after the pre-checkout query was sent."""
        method = 'answerPreCheckoutQuery'
        if pre_checkout_query_id is None: raise ValueError('pre_checkout_query_id required')
        if ok is None: raise ValueError('ok required')
        params = {
            'pre_checkout_query_id': pre_checkout_query_id,
            'ok': ok,
            'error_message': error_message,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def get_my_star_balance(self) -> Optional[Any]:
        """A method to get the current Telegram Stars balance of the bot. Requires no parameters. On success, returns a StarAmount object."""
        method = 'getMyStarBalance'
        params = {
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def get_star_transactions(self, offset: Optional[int] = None, limit: Optional[int] = None) -> Optional[Any]:
        """Returns the bot's Telegram Star transactions in chronological order. On success, returns a StarTransactions object."""
        method = 'getStarTransactions'
        params = {
            'offset': offset,
            'limit': limit,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def refund_star_payment(self, user_id: Optional[int] = None, telegram_payment_charge_id: Optional[str] = None) -> Optional[bool]:
        """Refunds a successful payment in Telegram Stars. Returns True on success."""
        method = 'refundStarPayment'
        if user_id is None: raise ValueError('user_id required')
        if telegram_payment_charge_id is None: raise ValueError('telegram_payment_charge_id required')
        params = {
            'user_id': user_id,
            'telegram_payment_charge_id': telegram_payment_charge_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def edit_user_star_subscription(self, user_id: Optional[int] = None, telegram_payment_charge_id: Optional[str] = None, is_canceled: Optional[bool] = None) -> Optional[bool]:
        """Allows the bot to cancel or re-enable extension of a subscription paid in Telegram Stars. Returns True on success."""
        method = 'editUserStarSubscription'
        if user_id is None: raise ValueError('user_id required')
        if telegram_payment_charge_id is None: raise ValueError('telegram_payment_charge_id required')
        if is_canceled is None: raise ValueError('is_canceled required')
        params = {
            'user_id': user_id,
            'telegram_payment_charge_id': telegram_payment_charge_id,
            'is_canceled': is_canceled,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def set_passport_data_errors(self, user_id: Optional[int] = None, errors: Optional[List[Dict]] = None) -> Optional[bool]:
        """Informs a user that some of the Telegram Passport elements they provided contains errors. The user will not be able to re-submit their Passport to you until the errors are fixed (the contents of the field for which you returned the error must change). Returns True on success."""
        method = 'setPassportDataErrors'
        if user_id is None: raise ValueError('user_id required')
        if errors is None: raise ValueError('errors required')
        params = {
            'user_id': user_id,
            'errors': _serialize(errors),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def send_game(self, chat_id: Optional[int] = None, game_short_name: Optional[str] = None, business_connection_id: Optional[str] = None, message_thread_id: Optional[int] = None, disable_notification: Optional[bool] = None, protect_content: Optional[bool] = None, allow_paid_broadcast: Optional[bool] = None, message_effect_id: Optional[str] = None, reply_parameters: Optional["ReplyParameters"] = None, reply_markup: Optional["InlineKeyboardMarkup"] = None) -> Optional["Message"]:
        """Use this method to send a game. On success, the sent Message is returned."""
        method = 'sendGame'
        if chat_id is None: raise ValueError('chat_id required')
        if game_short_name is None: raise ValueError('game_short_name required')
        params = {
            'chat_id': chat_id,
            'game_short_name': game_short_name,
            'business_connection_id': business_connection_id,
            'message_thread_id': message_thread_id,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
            'allow_paid_broadcast': allow_paid_broadcast,
            'message_effect_id': message_effect_id,
            'reply_parameters': _serialize(reply_parameters),
            'reply_markup': _serialize(reply_markup),
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return Message.from_dict(response['result'])
        return None

    def set_game_score(self, user_id: Optional[int] = None, score: Optional[int] = None, force: Optional[bool] = None, disable_edit_message: Optional[bool] = None, chat_id: Optional[int] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None) -> Optional[Any]:
        """Use this method to set the score of the specified user in a game message. On success, if the message is not an inline message, the Message is returned, otherwise True is returned. Returns an error, if the new score is not greater than the user's current score in the chat and force is False."""
        method = 'setGameScore'
        if user_id is None: raise ValueError('user_id required')
        if score is None: raise ValueError('score required')
        params = {
            'user_id': user_id,
            'score': score,
            'force': force,
            'disable_edit_message': disable_edit_message,
            'chat_id': chat_id,
            'message_id': message_id,
            'inline_message_id': inline_message_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        return response.get('result')

    def get_game_high_scores(self, user_id: Optional[int] = None, chat_id: Optional[int] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None) -> Optional[List["GameHighScore"]]:
        """Use this method to get data for high score tables. Will return the score of the specified user and several of their neighbors in a game. Returns an Array of GameHighScore objects."""
        method = 'getGameHighScores'
        if user_id is None: raise ValueError('user_id required')
        params = {
            'user_id': user_id,
            'chat_id': chat_id,
            'message_id': message_id,
            'inline_message_id': inline_message_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        response = self._make_request(method, params)
        if response and 'result' in response:
            return [GameHighScore.from_dict(x) for x in response['result']]
        return None

