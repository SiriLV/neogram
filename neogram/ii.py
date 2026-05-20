"""neogram — набор клиентов для различных AI-сервисов.

Классы:
    OnlySQ — клиент API OnlySQ
    Deef — утилиты: перевод, сокращение ссылок, фоновые задачи, Perplexity, Toolbaz
    Qwen — клиент chat.qwen.ai
    ChatGPT — универсальный клиент для OpenAI-совместимых API
"""
import base64
import datetime
import hashlib
import hmac
import json
import logging
import random
import re
import string
import threading
import time
import uuid
from typing import BinaryIO, Dict, Iterator, List, Optional, Tuple, Union
from urllib.parse import quote as url_quote
from urllib.parse import unquote, urlparse
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
from curl_cffi.requests import Session
__all__ = ["OnlySQ", "Deef", "Qwen", "ChatGPT", "OpenAI"]
logger = logging.getLogger("neogram")


# ---------------------------------------------------------------------------
#  OnlySQ
# ---------------------------------------------------------------------------
class OnlySQ:
    """Клиент API OnlySQ для генерации текста и изображений. Ключ брать тут: https://my.onlysq.ru/"""
    def __init__(self, key: str):
        self.key = key
        self._base_url = "https://api.onlysq.ru"

    def get_models(self, modality: Optional[Union[str, List[str]]] = None, can_tools: Optional[bool] = None, can_think: Optional[bool] = None, can_stream: Optional[bool] = None, status: Optional[str] = None, max_cost: Optional[float] = None, return_names: bool = False) -> List[str]:
        """Получает и фильтрует доступные модели"""
        try:
            response = curl_requests.get(f"{self._base_url}/ai/models", timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error("OnlySQ.get_models: %s", e)
            return []
        filtered: List[str] = []
        for model_key, model_data in data.get("models", {}).items():
            if modality is not None:
                if isinstance(modality, list):
                    if model_data.get("modality") not in modality:
                        continue
                elif model_data.get("modality") != modality:
                    continue
            if can_tools is not None and model_data.get("can-tools", False) != can_tools:
                continue
            if can_think is not None and model_data.get("can-think", False) != can_think:
                continue
            if can_stream is not None and model_data.get("can-stream", False) != can_stream:
                continue
            if status is not None and model_data.get("status", "") != status:
                continue
            if max_cost is not None:
                try:
                    if float(model_data.get("cost", float("inf"))) > max_cost:
                        continue
                except (TypeError, ValueError):
                    continue
            filtered.append(model_data.get("name", model_key) if return_names else model_key)
        return filtered

    def generate_answer(self, model: str = "gpt-5.2-chat", messages: Optional[List[dict]] = None, timeout: int = 120) -> str:
        """Генерация текстового ответа
        Args:
            model: Имя модели
            messages: Список сообщений
            timeout: Таймаут запроса в секундах
        """
        if not messages:
            raise ValueError("OnlySQ.generate_answer: messages обязателен")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                payload = {"model": model, "request": {"messages": messages}}
                response = curl_requests.post(f"{self._base_url}/ai/v2", json=payload, headers={"Authorization": f"Bearer {self.key}"}, timeout=timeout)
                if response.status_code >= 500:
                    body = response.text[:500] if response.text else ""
                    logger.warning("OnlySQ.generate_answer: server error HTTP %s (attempt %d/%d): %s", response.status_code, attempt + 1, max_retries, body)
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return f"Error: HTTP {response.status_code} — {body}"
                if response.status_code >= 400:
                    body = response.text[:500] if response.text else ""
                    logger.error("OnlySQ.generate_answer: HTTP %s — %s", response.status_code, body)
                    return f"Error: HTTP {response.status_code} — {body}"
                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    return "Error: empty choices in response"
                content = choices[0].get("message", {}).get("content")
                if content is None:
                    return "Error: no content in response"
                return content
            except Exception as e:
                logger.error("OnlySQ.generate_answer: %s", e)
                return f"Error: {e}"
        return "Error: all retries exhausted"

    def generate_image(self, model: str = "flux", prompt: Optional[str] = None, ratio: str = "16:9", filename: str = "image.png") -> bool:
        """Генерация изображения"""
        if not prompt:
            raise ValueError("OnlySQ.generate_image: prompt обязателен")
        try:
            payload = {"model": model, "prompt": prompt, "ratio": ratio}
            response = curl_requests.post(f"{self._base_url}/ai/imagen", json=payload, headers={"Authorization": f"Bearer {self.key}"}, timeout=120)
            if response.status_code == 200:
                files_data = response.json().get("files", [])
                if not files_data:
                    return False
                img_bytes = base64.b64decode(files_data[0])
                with open(filename, "wb") as f:
                    f.write(img_bytes)
                return True
            return False
        except Exception as e:
            logger.error("OnlySQ.generate_image: %s", e)
            return False


# ---------------------------------------------------------------------------
#  Deef
# ---------------------------------------------------------------------------
class Deef:
    """Набор полезных утилит: перевод, сокращение ссылок, фоновые задачи"""
    def translate(self, text: Optional[str] = None, lang: str = "en") -> str:
        """Перевод текста через Google Translate"""
        if not text:
            return text or ""
        try:
            url = f"https://translate.google.com/m?tl={lang}&sl=auto&q={url_quote(text)}"
            response = curl_requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")
            result = soup.find("div", class_="result-container")
            if result:
                return result.text
            return text
        except Exception as e:
            logger.warning("Deef.translate: %s", e)
            return text

    def short_url(self, long_url: Optional[str] = None) -> str:
        """Сокращение ссылки через clck.ru"""
        if not long_url:
            return long_url or ""
        try:
            response = curl_requests.get(f"https://clck.ru/--?url={url_quote(long_url, safe='')}", timeout=10)
            response.raise_for_status()
            return response.text.strip()
        except Exception as e:
            logger.warning("Deef.short_url: %s", e)
            return long_url

    def run_in_bg(self, func, *args, **kwargs) -> threading.Thread:
        """Запускает функцию в фоновом потоке. Возвращает Thread"""
        def wrapper():
            try:
                func(*args, **kwargs)
            except Exception as e:
                logger.error("Deef.run_in_bg(%s): %s", getattr(func, "__name__", "?"), e)
        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
        return thread

    def encode_base64(self, path: Optional[str] = None) -> Optional[str]:
        """Кодирует файл в base64"""
        if not path:
            raise ValueError("Deef.encode_base64: path обязателен")
        try:
            with open(path, "rb") as file:
                return base64.b64encode(file.read()).decode("utf-8")
        except FileNotFoundError:
            logger.error("Deef.encode_base64: файл не найден: %s", path)
            return None
        except OSError as e:
            logger.error("Deef.encode_base64: ошибка чтения файла %s: %s", path, e)
            return None

    def perplexity_ask(self, prompt: Optional[str] = None, model: str = "auto") -> dict:
        """Запрос к Perplexity AI
        Если модель не найдена — используется turbo
        Args:
            prompt: Текст запроса.
            model: Название модели (например ``"o3pro"``, ``"turbo"``, ``"auto"``).
        Returns:
            ``{"text": "ответ", "urls": ["url1", ...]}`` при успехе,
            ``{"text": "Error", "urls": []}`` при ошибке.
        Example::
            deef = Deef()
            result = deef.perplexity_ask("Столица Франции?", model="turbo")
            print(result["text"])
            for url in result["urls"]:
                print(url)
        """
        ERROR_RESULT: Dict[str, object] = {"text": "Error", "urls": []}
        BASE_URL = "https://www.perplexity.ai"
        MODE_API_MAP = {"search": "copilot", "research": "research", "agentic_research": "agentic_research", "studio": "studio", "study": "study", "document_review": "document_review", "browser_agent": "browser_agent", "asi": "asi"}
        if prompt is None:
            raise ValueError("Забыли указать prompt")
        try:
            try:
                with Session(impersonate="chrome") as config_session:
                    config_resp = config_session.get(f"{BASE_URL}/rest/models/config", params={"config_schema": "v1", "version": "2.18", "source": "default"}, timeout=15)
                    config_json = (config_resp.json() if config_resp.status_code == 200 and config_resp.content else {})
            except Exception:
                config_json = {}
            models_map = config_json.get("models", {})
            default_models = config_json.get("default_models", {})
            available_models = list(models_map.keys())

            def resolve_mode(model_name: str) -> str:
                info = models_map.get(model_name, {})
                raw_mode = info.get("mode", "search")
                return MODE_API_MAP.get(raw_mode, "copilot")

            if model not in available_models:
                model = default_models.get("search", available_models[0] if available_models else "turbo")
            api_mode = resolve_mode(model)
            frontend_uid = str(uuid.uuid4())
            frontend_context_uuid = str(uuid.uuid4())
            visitor_id = str(uuid.uuid4())
            headers = {
                "accept": "text/event-stream",
                "accept-language": "en-US,en;q=0.9",
                "cache-control": "no-cache",
                "content-type": "application/json",
                "origin": BASE_URL,
                "referer": f"{BASE_URL}/",
                "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
                "x-perplexity-request-reason": "perplexity-query-state-provider"}
            with Session(headers=headers, timeout=300, impersonate="chrome") as session:
                resp = session.get(f"{BASE_URL}/api/auth/session")
                try:
                    user_id = resp.json().get("user", {}).get("id") if resp.content else None
                except (json.JSONDecodeError, ValueError):
                    user_id = None
                if model == "auto":
                    model = "pplx_pro" if user_id else default_models.get("search", "turbo")
                    api_mode = resolve_mode(model)
                payload = {
                    "params": {
                        "attachments": [],
                        "language": "en-US",
                        "timezone": "America/New_York",
                        "followup_source": "link",
                        "search_focus": "internet",
                        "source": "default",
                        "sources": ["edgar", "social", "web", "scholar"],
                        "frontend_uuid": frontend_uid,
                        "mode": api_mode,
                        "model_preference": model,
                        "visitor_id": visitor_id,
                        "frontend_context_uuid": frontend_context_uuid,
                        "prompt_source": "user",
                        "query_source": "followup",
                        "use_schematized_api": True,
                        "supported_block_use_cases": [
                            "answer_modes", "media_items", "knowledge_cards",
                            "inline_entity_cards", "place_widgets", "finance_widgets",
                            "prediction_market_widgets", "sports_widgets",
                            "flight_status_widgets", "news_widgets", "shopping_widgets",
                            "jobs_widgets", "search_result_widgets", "inline_images",
                            "inline_assets", "placeholder_cards", "diff_blocks",
                            "inline_knowledge_cards", "entity_group_v2",
                            "refinement_filters", "canvas_mode", "maps_preview",
                            "answer_tabs", "price_comparison_widgets", "preserve_latex",
                            "generic_onboarding_widgets", "in_context_suggestions"],
                        "version": "2.18"},
                    "query_str": prompt}
                response = session.post(f"{BASE_URL}/rest/sse/perplexity_ask", json=payload)
                if response.status_code >= 400:
                    logger.error("Deef.perplexity_ask: HTTP %s", response.status_code)
                    return ERROR_RESULT
                content = response.content
                if isinstance(content, bytes):
                    content = content.decode("utf-8")
            full_text = ""
            urls: List[str] = []
            for line in content.split("\n"):
                line = line.strip()
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if not data_str or data_str == "[DONE]":
                    continue
                try:
                    json_data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                for block in json_data.get("blocks", []):
                    intended_usage = block.get("intended_usage", "")
                    if intended_usage == "sources_answer_mode":
                        web_results = block.get("sources_mode_block", {}).get("web_results", [])
                        for wr in web_results:
                            url = wr.get("url", "")
                            if url and url not in urls:
                                urls.append(url)
                        continue
                    if intended_usage != "ask_text_0_markdown":
                        continue
                    diff_block = block.get("diff_block", {})
                    if diff_block.get("field") != "markdown_block":
                        continue
                    for patch in diff_block.get("patches", []):
                        value = patch.get("value", "")
                        if isinstance(value, dict) and "chunks" in value:
                            text = "".join(value.get("chunks", []))
                            if text and len(text) > len(full_text):
                                full_text = text
                        elif patch.get("op") == "add" and isinstance(value, str) and value:
                            full_text += value
            return {"text": full_text or "Error", "urls": urls}
        except Exception as e:
            logger.error("Deef.perplexity_ask: %s", e)
            return ERROR_RESULT

    def toolchat(self, prompt: Optional[str] = None, model: str = "toolbaz-v4.5-fast") -> str:
        """Генерация ответа используя Toolbaz
        Доступные модели: gemini-3-flash, gemini-3.1-flash-lite, gemini-2.5-pro,
        gemini-2.5-flash, deepseek-v3.1, deepseek-v3, deepseek-r1, gpt-5.2,
        gpt-5, gpt-oss-120b, o3-mini, gpt-4o-latest, claude-sonnet-4,
        grok-4-fast, toolbaz-v4.5-fast, toolbaz-v4, Llama-4-Maverick
        """
        if prompt is None:
            raise ValueError("Забыли указать prompt")
        TOOLBAZ_HEADERS = {
            "accept": "*/*",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://toolbaz.com",
            "referer": "https://toolbaz.com/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"}

        def _random_str(length: int) -> str:
            return "".join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789") for _ in range(length))

        def _create_token() -> str:
            data = {
                "bR6wF": {"nV5kP": TOOLBAZ_HEADERS["user-agent"], "lQ9jX": "ru-RU", "sD2zR": "1920x1080", "tY4hL": "Europe/Moscow", "pL8mC": "Win32", "cQ3vD": 24, "hK7jN": 8},
                "uT4bX": {"mM9wZ": [{"x": random.randint(0, 1920), "y": random.randint(0, 1080)} for _ in range(20)], "kP8jY": [random.choice(string.ascii_letters) for _ in range(10)]},
                "tuTcS": int(time.time()),
                "tDfxy": -7,
                "RtyJt": _random_str(36),
                "extra": {"random_str": _random_str(50), "timestamp": str(datetime.datetime.now(datetime.timezone.utc)), "version": "1.0.0"}}
            return _random_str(6) + base64.b64encode(json.dumps(data).encode()).decode()

        try:
            with Session(impersonate="chrome120") as session:
                session.cookies.set("SessionID", "ERfvMHDEY5Fo1TTJu1W7hIZSA9dHcVyJCb5m")
                token_data = {"session_id": "ERfvMHDEY5Fo1TTJu1W7hIZSA9dHcVyJCb5m", "token": _create_token()}
                token_response = session.post("https://data.toolbaz.com/token.php", data=token_data, headers=TOOLBAZ_HEADERS)
                token_json = token_response.json()
                if not token_json.get("token"):
                    logger.error("Deef.toolchat: не удалось получить токен Toolbaz")
                    return "Error"
                payload = {"text": prompt, "capcha": token_json["token"], "model": model, "session_id": "ERfvMHDEY5Fo1TTJu1W7hIZSA9dHcVyJCb5m"}
                response = session.post("https://data.toolbaz.com/writing.php", data=payload, headers=TOOLBAZ_HEADERS)
                if response.status_code == 200:
                    return response.text
                logger.error("Deef.toolchat: HTTP %s от writing.php", response.status_code)
                return "Error"
        except Exception as e:
            logger.error("Deef.toolchat: %s", e)
            return "Error"
    
    def deepinfra(self, messages: List[dict], model: str = "zai-org/GLM-5.1", temperature: float = 0.7, max_tokens: int = 4000, timeout: int = 30) -> dict:
        """Чат-запрос к DeepInfra API
        Args:
            messages: Список сообщений в формате OpenAI([{"role": "user", "content": "..."}])
            model: Идентификатор модели (по умолчанию zai-org/GLM-5.1)
            temperature: Температура генерации (0.0 — 1.0)
            max_tokens: Максимальное количество токенов в ответе
            timeout: Таймаут запроса в секундах
        Returns:
            dict — JSON-ответ от DeepInfra API при успехе
            dict с ключом "error" при ошибке
        """
        _DEEPINFRA_HEADERS = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept-Language": "en,fr-FR;q=0.9,fr;q=0.8,es-ES;q=0.7,es;q=0.6,en-US;q=0.5,am;q=0.4,de;q=0.3",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Origin": "https://deepinfra.com",
            "Pragma": "no-cache",
            "Referer": "https://deepinfra.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "X-Deepinfra-Source": "web-embed",
            "accept": "text/event-stream",
            "sec-ch-ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"'}
        payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        try:
            response = curl_requests.post(url="https://api.deepinfra.com/v1/openai/chat/completions", json=payload, headers=_DEEPINFRA_HEADERS, impersonate="chrome131", timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Deef.deepinfra: %s", e)
            return {"error": str(e)}


# ---------------------------------------------------------------------------
#  Qwen
# ---------------------------------------------------------------------------
class Qwen:
    """Класс для работы с моделями Qwen"""
    SUPPORTED_CHAT_TYPES = frozenset({"t2t", "search", "t2i", "deep_research", "artifacts", "learn", "image_edit"})
    IMAGE_MIME_MAP: Dict[str, str] = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif", ".bmp": "image/bmp", ".svg": "image/svg+xml"}
    def __init__(self, proxy: Optional[str] = None):
        self._proxy = proxy
        self._models_cache: Optional[List[Dict]] = None
        self._models_cache_time: float = 0.0
        self._models_cache_ttl: int = 600

    # -- модели -------------------------------------------------------------
    def fetch_models(self) -> List[Dict]:
        """Вернуть список доступных моделей"""
        if self._models_cache is not None and (time.time() - self._models_cache_time) < self._models_cache_ttl:
            return self._models_cache
        try:
            with Session(impersonate="chrome136", proxy=self._proxy, timeout=30) as s:
                r = s.get("https://chat.qwen.ai/api/models", headers={"Accept": "application/json"})
                r.raise_for_status()
                raw = r.json().get("data", [])
        except Exception as exc:
            if self._models_cache is not None:
                return self._models_cache
            raise RuntimeError(f"Cannot fetch models: {exc}") from exc
        models: List[Dict] = []
        for m in raw:
            meta = m.get("info", {}).get("meta", {})
            caps = meta.get("capabilities", {})
            models.append({
                "id": m["id"],
                "name": m.get("name", m["id"]),
                "capabilities": {"vision": caps.get("vision", False), "thinking": caps.get("thinking", False), "search": caps.get("search", False)},
                "chat_types": meta.get("chat_type", []),
                "thinking_format": meta.get("thinking_format", "summary"),
                "is_visitor_active": m.get("info", {}).get("is_visitor_active", False)})
        self._models_cache = models
        self._models_cache_time = time.time()
        return models

    # -- LZW-компрессия для cookies -----------------------------------------
    @staticmethod
    def _lzw(data: str) -> str:
        """LZW-компрессия в кастомный base64 для cookie ssxmod_itna"""
        if not data:
            return ""
        bits = 6
        chars = "DGi0YA7BemWnQjCl4_bR3f8SKIF9tUz/xhr2oEOgPpac=61ZqwTudLkM5vHyNXsVJ"
        dictionary: Dict[str, int] = {}
        dict_to_create: Dict[str, bool] = {}
        w = ""
        result: List[str] = []
        value = 0
        pos = 0
        enlarge_in = 2
        dict_size = 3
        num_bits = 2

        def emit(code: int) -> None:
            nonlocal value, pos
            for _ in range(num_bits):
                value = (value << 1) | (code & 1)
                if pos == bits - 1:
                    result.append(chars[value])
                    value = 0
                    pos = 0
                else:
                    pos += 1
                code >>= 1

        def emit_raw(ch: str) -> None:
            nonlocal value, pos, enlarge_in, num_bits
            code = ord(ch)
            if code < 256:
                for _ in range(num_bits):
                    value = value << 1
                    if pos == bits - 1:
                        result.append(chars[value])
                        value = 0
                        pos = 0
                    else:
                        pos += 1
                for _ in range(8):
                    value = (value << 1) | (code & 1)
                    if pos == bits - 1:
                        result.append(chars[value])
                        value = 0
                        pos = 0
                    else:
                        pos += 1
                    code >>= 1
            else:
                emit(1)
                code = ord(ch)
                for _ in range(16):
                    value = (value << 1) | (code & 1)
                    if pos == bits - 1:
                        result.append(chars[value])
                        value = 0
                        pos = 0
                    else:
                        pos += 1
                    code >>= 1

        for c in data:
            if c not in dictionary:
                dictionary[c] = dict_size
                dict_size += 1
                dict_to_create[c] = True
            wc = w + c
            if wc in dictionary:
                w = wc
                continue
            if w in dict_to_create:
                emit_raw(w[0])
                enlarge_in -= 1
                if enlarge_in == 0:
                    enlarge_in = 1 << num_bits
                    num_bits += 1
                del dict_to_create[w]
            else:
                emit(dictionary[w])
            enlarge_in -= 1
            if enlarge_in == 0:
                enlarge_in = 1 << num_bits
                num_bits += 1
            dictionary[wc] = dict_size
            dict_size += 1
            w = c

        if w:
            if w in dict_to_create:
                emit_raw(w[0])
                enlarge_in -= 1
                if enlarge_in == 0:
                    enlarge_in = 1 << num_bits
                    num_bits += 1
            else:
                emit(dictionary[w])
            enlarge_in -= 1

        emit(2)
        while pos:
            value <<= 1
            if pos == bits - 1:
                result.append(chars[value])
                break
            pos += 1
        return "".join(result)

    # -- cookies / авторизация ----------------------------------------------
    def _make_cookies(self) -> Dict[str, str]:
        """Сгенерировать ssxmod-куки для гостевого режима"""
        did = "".join(random.choice("0123456789abcdef") for _ in range(20))
        ts = int(time.time() * 1000)

        def _rh() -> int:
            return random.randint(0, 0xFFFFFFFF)

        fields = [did, "websdk-2.3.15d", str(ts), "91", "1|15", "zh-CN", "-480", "16705151|12791", "1470|956|283|797|158|0|1470|956|1470|798|0|0", "5", "MacIntel", "10", "ANGLE (Apple, ANGLE Metal Renderer: Apple M4, Unspecified Version)|Google Inc. (Apple)", "30|30", "0", "28", f"5|{_rh()}", _rh(), _rh(), "1", "0", "1", "0", "P", "0", "0", "0", "416", "Google Inc.", "8", "-1|0|0|0|0", _rh(),  "11", ts, _rh(), "0", random.randint(10, 100)]
        raw = "^".join(map(str, fields))
        itna = "1-" + self._lzw(raw)
        itna2 = "1-" + self._lzw("^".join(map(str, [fields[0], fields[1], fields[23], 0, "", 0, "", "", 0, 0, 0, fields[32], fields[33], 0, 0, 0, 0, 0])))
        return {"ssxmod_itna": itna, "ssxmod_itna2": itna2}

    @staticmethod
    def _get_midtoken(session: Session) -> str:
        """Получить bx-umidtoken для авторизации запросов"""
        r = session.get("https://sg-wum.alibaba.com/w/wu.json")
        r.raise_for_status()
        m = re.search(r"(?:umx\.wu|__fycb)\('([^']+)'\)", r.text)
        if not m:
            raise RuntimeError("Failed to extract bx-umidtoken")
        return m.group(1)

    # -- OSS ----------------------------------------------------------------
    @staticmethod
    def _oss_headers(method: str, date_rfc2616: str, sts: dict, content_type: str) -> Dict[str, str]:
        """Сформировать заголовки для загрузки файла в Alibaba Cloud OSS"""
        bucket = sts.get("bucketname", "qwen-webui-prod")
        fpath = sts.get("file_path", "")
        ak_id = sts["access_key_id"]
        ak_secret = sts["access_key_secret"]
        sec_token = sts["security_token"]
        oss_headers_str = f"x-oss-security-token:{sec_token}\n"
        canonical_resource = f"/{bucket}/{fpath}"
        string_to_sign = f"{method}\n\n{content_type}\n{date_rfc2616}\n{oss_headers_str}{canonical_resource}"
        signature = base64.b64encode(hmac.new(ak_secret.encode(), string_to_sign.encode(), hashlib.sha1).digest()).decode()
        return {"Content-Type": content_type, "Date": date_rfc2616, "Authorization": f"OSS {ak_id}:{signature}", "x-oss-security-token": sec_token}

    # -- работа с изображениями ---------------------------------------------
    @classmethod
    def _detect_image_type(cls, data: bytes) -> Tuple[str, str]:
        """Определить расширение и MIME-тип изображения по сигнатуре файла"""
        if len(data) < 2:
            return ".bin", "application/octet-stream"
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return ".png", "image/png"
        if data[:3] == b"\xff\xd8\xff":
            return ".jpg", "image/jpeg"
        if data[:4] == b"RIFF" and len(data) > 11 and data[8:12] == b"WEBP":
            return ".webp", "image/webp"
        if data[:4] == b"GIF8":
            return ".gif", "image/gif"
        return ".bin", "application/octet-stream"

    @classmethod
    def _download_image(cls, session: Session, url: str, timeout: int = 120) -> Tuple[bytes, str, str]:
        """Скачать изображение по URL или раскодировать data-URI. Returns: Кортеж (bytes, filename, mime)"""
        if url.startswith("data:"):
            header, b64 = url.split(",", 1)
            mime = "application/octet-stream"
            m = re.match(r"data:([^;,]+)", header)
            if m:
                mime = m.group(1)
            data = base64.b64decode(b64)
            ext = next((k for k, v in cls.IMAGE_MIME_MAP.items() if v == mime), ".bin")
            return data, f"upload{ext}", mime
        r = session.get(url, impersonate="chrome136", timeout=timeout, headers={"Accept": "*/*"})
        r.raise_for_status()
        data = r.content
        fname: Optional[str] = None
        parsed = urlparse(url)
        path = unquote(parsed.path)
        if path and "/" in path:
            basename = path.rsplit("/", 1)[-1]
            if "." in basename and len(basename) < 256:
                fname = basename
        ct = r.headers.get("Content-Type", "").split(";")[0].strip()
        mime = ct if ct and "/" in ct else None
        if not mime or mime == "application/octet-stream":
            _, mime = cls._detect_image_type(data)
        if not fname:
            ext = next((k for k, v in cls.IMAGE_MIME_MAP.items() if v == mime), ".bin")
            fname = f"upload{ext}"
        return data, fname, mime

    def _upload_image(self, session: Session, file_bytes: bytes, filename: str, mime: str, extra_headers: Dict[str, str]) -> dict:
        """Загрузить изображение в OSS Qwen и вернуть объект файла для API"""
        fsize = len(file_bytes)
        r = session.post("https://chat.qwen.ai/api/v2/files/getstsToken", json={"filename": filename, "filesize": fsize, "filetype": "image"}, headers=extra_headers)
        r.raise_for_status()
        res = r.json()
        if not res.get("success"):
            err_details = res.get("data", {}).get("details", "")
            if "401" in err_details or "Unauthorized" in err_details:
                raise RuntimeError("Guest mode does not support uploading this file type.")
            raise RuntimeError(f"STS token failed: {res}")
        sts_data = res["data"]
        file_url = sts_data["file_url"]
        file_id = sts_data["file_id"]
        date_rfc2616 = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        oss_h = self._oss_headers("PUT", date_rfc2616, sts_data, mime)
        endpoint = sts_data.get("endpoint", "oss-accelerate.aliyuncs.com")
        bucket = sts_data.get("bucketname", "qwen-webui-prod")
        oss_url = f"https://{bucket}.{endpoint}/{sts_data.get('file_path', '')}"
        with Session(impersonate="chrome136", timeout=120) as oss_s:
            r = oss_s.put(oss_url, data=file_bytes, headers=oss_h)
            r.raise_for_status()
        now_ms = int(time.time() * 1000)
        return {
            "type": "image",
            "file": {
                "created_at": now_ms,
                "data": {},
                "filename": filename,
                "hash": None,
                "id": file_id,
                "meta": {"name": filename, "size": fsize, "content_type": mime},
                "update_at": now_ms},
            "id": file_id,
            "url": file_url,
            "name": filename,
            "collection_name": "",
            "progress": 0,
            "status": "uploaded",
            "greenNet": "success",
            "size": fsize,
            "error": "",
            "itemId": str(uuid.uuid4()),
            "file_type": mime,
            "showType": "image",
            "file_class": "vision",
            "uploadTaskId": str(uuid.uuid4())}

    @staticmethod
    def _collect_image_refs(content) -> List[str]:
        """Собрать URL изображений из content-списка последнего user-сообщения"""
        refs: List[str] = []
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    url = part.get("image_url", {}).get("url", "")
                    if url:
                        refs.append(url)
        return refs

    # -- чат ----------------------------------------------------------------
    def chat(self, model: str = "qwen3.6-plus", messages: Optional[List[dict]] = None, stream: bool = False, ctype: str = "t2t", size: Optional[str] = None, think: bool = True) -> Union[str, Iterator]:
        """Чат с моделями Qwen
        Args:
            model: Имя модели (по умолчанию qwen3.6-plus)
            messages: Список сообщений в формате OpenAI
            stream: True — вернуть итератор чанков, False — полный ответ строкой
            ctype: Режим чата: t2t, search, t2i, deep_research, artifacts, learn, image_edit
            size: Размер для t2i / image_edit (например "16:9", "9:16", "1:1")
            think: Включить режим размышлений (по умолчанию True)
        Returns:
            str — если stream=False
            iterator — если stream=True (yield str или dict с type="thinking"/type="image")
        """
        if messages is None:
            messages = []
        messages = list(messages)
        chat_type = ctype.strip()
        if chat_type not in self.SUPPORTED_CHAT_TYPES:
            raise ValueError(f"Unsupported chat type: '{chat_type}'. Supported: {sorted(self.SUPPORTED_CHAT_TYPES)}")
        try:
            all_models = self.fetch_models()
        except Exception:
            all_models = []
        model_info = next((m for m in all_models if m["id"] == model), None)
        user_text = ""
        image_urls: List[str] = []
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            c = msg.get("content", "")
            if isinstance(c, str):
                user_text = c
            elif isinstance(c, list):
                texts = [p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"]
                user_text = "\n".join(texts)
                image_urls = self._collect_image_refs(c)
            break
        effective_model = model
        if model_info and image_urls and not model_info["capabilities"].get("vision", False):
            for m in all_models:
                if not m.get("is_visitor_active", True):
                    continue
                if m["capabilities"].get("vision", False) and chat_type in m.get("chat_types", []):
                    effective_model = m["id"]
                    model_info = m
                    break
            else:
                for m in all_models:
                    if not m.get("is_visitor_active", True):
                        continue
                    if m["capabilities"].get("vision", False):
                        effective_model = m["id"]
                        model_info = m
                        break
        effective_chat_type = chat_type
        if model_info and chat_type not in model_info.get("chat_types", []):
            if "t2t" in model_info.get("chat_types", []):
                effective_chat_type = "t2t"
            else:
                supported = model_info.get("chat_types", [])
                if supported:
                    effective_chat_type = supported[0]
        thinking_format = (model_info or {}).get("thinking_format", "summary") or "summary"
        if effective_chat_type == "deep_research":
            feature_config = {"thinking_enabled": True, "auto_thinking": True, "thinking_mode": "Auto", "thinking_format": thinking_format, "output_schema": "phase", "research_mode": "deep", "auto_search": True}
        elif effective_chat_type == "search":
            feature_config = {"thinking_enabled": True, "auto_thinking": True, "thinking_mode": "Auto", "thinking_format": thinking_format, "output_schema": "phase", "research_mode": "normal", "auto_search": True}
        elif think:
            feature_config = {"thinking_enabled": True, "auto_thinking": False, "thinking_mode": "Thinking", "thinking_format": thinking_format, "output_schema": "phase", "research_mode": "normal", "auto_search": True}
        else:
            feature_config = {"thinking_enabled": False, "output_schema": "phase", "thinking_budget": 81920}
        session = Session(impersonate="chrome136", timeout=300)

        def _do_request():
            ck = self._make_cookies()
            session.headers.update({
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.5",
                "Content-Type": "application/json",
                "Origin": "https://chat.qwen.ai",
                "Referer": "https://chat.qwen.ai/c/guest",
                "X-Source": "web",
                "Cookie": f'ssxmod_itna={ck["ssxmod_itna"]};ssxmod_itna2={ck["ssxmod_itna2"]}'})
            midtoken = self._get_midtoken(session)
            extra_headers = {"bx-umidtoken": midtoken, "bx-v": "2.5.31"}
            files: List[dict] = []
            if image_urls:
                for url in image_urls:
                    try:
                        img_bytes, fname, mime = self._download_image(session, url)
                        fobj = self._upload_image(session, img_bytes, fname, mime, extra_headers)
                        files.append(fobj)
                    except Exception as exc:
                        logger.warning("Qwen.chat: не удалось загрузить изображение %s: %s", url, exc)
            r = session.post("https://chat.qwen.ai/api/v2/chats/new", json={"title": "New Chat", "models": [effective_model], "chat_mode": "guest", "chat_type": effective_chat_type, "timestamp": int(time.time() * 1000)}, headers=extra_headers)
            r.raise_for_status()
            chat_data = r.json()
            if not (chat_data.get("success") and chat_data.get("data", {}).get("id")):
                raise RuntimeError(f"Failed to create chat: {chat_data}")
            chat_id = chat_data["data"]["id"]
            msg_id = str(uuid.uuid4())
            now_ms = int(time.time() * 1000)
            user_msg: Dict = {
                "fid": msg_id,
                "parentId": None,
                "childrenIds": [],
                "role": "user",
                "content": user_text,
                "user_action": "chat",
                "files": files,
                "timestamp": now_ms,
                "models": [effective_model],
                "chat_type": effective_chat_type,
                "feature_config": feature_config,
                "sub_chat_type": effective_chat_type,
                "parent_id": None}
            if effective_chat_type != "t2t":
                user_msg["extra"] = {"meta": {"subChatType": effective_chat_type}}
            body: Dict = {
                "stream": True,
                "version": "2.1",
                "incremental_output": True,
                "chat_id": chat_id,
                "chat_mode": "guest",
                "model": effective_model,
                "parent_id": None,
                "messages": [user_msg],
                "timestamp": now_ms}
            if size and effective_chat_type in ("t2i", "image_edit"):
                body["size"] = size
            r = session.post(f"https://chat.qwen.ai/api/v2/chat/completions?chat_id={chat_id}", json=body, headers=extra_headers, stream=True)
            r.raise_for_status()
            return r

        def _stream_iter():
            try:
                r = _do_request()
                thinking_active = False
                for line in r.iter_lines():
                    if not line:
                        continue
                    line = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
                    line = line.strip()
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload == "[DONE]":
                        return
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if "response.created" in chunk or "response.info" in chunk:
                        continue
                    err = chunk.get("error")
                    if err:
                        raise RuntimeError(f'{err.get("code")}: {err.get("details")}')
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    phase = delta.get("phase")
                    content = delta.get("content")
                    if phase == "think":
                        thinking_active = True
                    elif phase == "answer":
                        thinking_active = False
                    if content:
                        if thinking_active:
                            yield {"type": "thinking", "content": content}
                        elif phase == "image_gen":
                            yield {"type": "image", "content": content, "extra": delta.get("extra", {})}
                        else:
                            yield content
            finally:
                try:
                    session.close()
                except Exception:
                    pass

        if stream:
            return _stream_iter()
        parts: List[str] = []
        thinking_parts: List[str] = []
        image_parts: List[dict] = []
        try:
            for chunk in _stream_iter():
                if isinstance(chunk, str):
                    parts.append(chunk)
                elif isinstance(chunk, dict):
                    chunk_type = chunk.get("type", "")
                    if chunk_type == "thinking":
                        thinking_parts.append(chunk["content"])
                    elif chunk_type == "image":
                        image_parts.append(chunk)
        except Exception:
            logger.error("Qwen.chat: stream iteration failed")
            return "Error"
        finally:
            try:
                session.close()
            except Exception:
                pass
        result = "".join(parts)
        if image_parts:
            img_urls = [img["content"] for img in image_parts]
            if result:
                result += "\n"
            for url in img_urls:
                result += f"[IMAGE: {url}]\n"
            result = result.rstrip("\n")
        if thinking_parts:
            thinking_text = "".join(thinking_parts)
            result = f"<think=>{thinking_text}</think=>{result}"
        return result


# ---------------------------------------------------------------------------
#  ChatGPT
# ---------------------------------------------------------------------------
class ChatGPT:
    """Клиент для OpenAI-совместимых API"""
    def __init__(self, url: str, headers: dict, impersonate: Optional[str] = None):
        self.url = url.rstrip("/")
        self.headers = headers
        self._session = Session(impersonate=impersonate)
        self._session.headers.update(headers)

    def close(self):
        """Закрыть сессию и освободить ресурсы"""
        try:
            self._session.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _make_request(self, method: str, endpoint: str, data: Optional[dict] = None, files: Optional[dict] = None) -> Union[dict, list]:
        """Выполняет HTTP-запрос к API"""
        url = f"{self.url}/{endpoint.lstrip('/')}"
        try:
            if files:
                response = self._session.request(method=method, url=url, files=files, data=data, timeout=120)
            else:
                response = self._session.request(method=method, url=url, json=data, timeout=120)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("ChatGPT(%s): %s", endpoint, e)
            return {"error": str(e)}

    def generate_chat_completion(self, model: str, messages: list, temperature: Optional[float] = None, max_tokens: Optional[int] = None, stream: bool = False, **kwargs) -> dict:
        """Генерация ответа в чате"""
        data: dict = {"model": model, "messages": messages, "stream": stream, **kwargs}
        if temperature is not None:
            data["temperature"] = temperature
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
        return self._make_request("POST", "chat/completions", data=data)

    def generate_image(self, prompt: str, n: int = 1, size: str = "1024x1024", response_format: str = "url", **kwargs) -> dict:
        """Генерация изображения"""
        data: dict = {"prompt": prompt, "n": n, "size": size, "response_format": response_format, **kwargs}
        return self._make_request("POST", "images/generations", data=data)

    def generate_embedding(self, model: str, input_data: Union[str, list], user: Optional[str] = None, **kwargs) -> dict:
        """Генерация embedding-вектора"""
        data: dict = {"model": model, "input": input_data, **kwargs}
        if user:
            data["user"] = user
        return self._make_request("POST", "embeddings", data=data)

    def generate_transcription(self, file: BinaryIO, model: str, language: Optional[str] = None, prompt: Optional[str] = None, response_format: str = "json", temperature: float = 0, **kwargs) -> Union[dict, str]:
        """Транскрипция аудио"""
        data: dict = {"model": model, "response_format": response_format, "temperature": temperature, **kwargs}
        if language:
            data["language"] = language
        if prompt:
            data["prompt"] = prompt
        return self._make_request("POST", "audio/transcriptions", data=data, files={"file": file})

    def generate_translation(self, file: BinaryIO, model: str, prompt: Optional[str] = None, response_format: str = "json", temperature: float = 0, **kwargs) -> Union[dict, str]:
        """Перевод аудио"""
        data: dict = {"model": model, "response_format": response_format, "temperature": temperature, **kwargs}
        if prompt:
            data["prompt"] = prompt
        return self._make_request("POST", "audio/translations", data=data, files={"file": file})

    def get_models(self) -> dict:
        """Список доступных моделей"""
        return self._make_request("GET", "models")

OpenAI = ChatGPT