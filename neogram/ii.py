#ii.py
import json
import base64
import threading
import uuid
import logging
from typing import Union, BinaryIO, Optional, Generator
from urllib.parse import quote as url_quote
import bs4
from curl_cffi import requests as curl_requests
from curl_cffi.requests import Session as CurlSession
logger = logging.getLogger("neogram")


class OnlySQ:
    '''Клиент API OnlySQ для генерации текста и изображений. Ключ брать тут: https://my.onlysq.ru/'''
    def __init__(self, key: str):
        self.key = key
        self._base_url = "https://api.onlysq.ru"

    def get_models(self, modality: Optional[Union[str, list]] = None, can_tools: Optional[bool] = None, can_think: Optional[bool] = None, can_stream: Optional[bool] = None, status: Optional[str] = None, max_cost: Optional[float] = None, return_names: bool = False) -> list:
        '''Получает и фильтрует доступные модели'''
        try:
            response = curl_requests.get(f"{self._base_url}/ai/models", timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"OnlySQ.get_models: {e}")
            return []
        filtered = []
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

    def generate_answer(self, model: str = "gpt-5.2-chat", messages: Optional[list] = None) -> str:
        '''Генерация текстового ответа.'''
        if not messages:
            raise ValueError("OnlySQ.generate_answer: messages обязателен")
        try:
            payload = {"model": model, "request": {"messages": messages}}
            response = curl_requests.post(f"{self._base_url}/ai/v2", json=payload, headers={"Authorization": f"Bearer {self.key}"}, timeout=60)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"OnlySQ.generate_answer: {e}")
            return f"Error: {e}"

    def generate_image(self, model: str = "flux", prompt: Optional[str] = None, ratio: str = "16:9", filename: str = "image.png") -> bool:
        '''Генерация изображения'''
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
            logger.error(f"OnlySQ.generate_image: {e}")
            return False


class Deef:
    '''Набор полезных утилит: перевод, сокращение ссылок, фоновые задачи'''
    def translate(self, text: str = None, lang: str = "en") -> str:
        '''Перевод текста через Google Translate'''
        if not text:
            return text or ""
        try:
            url = f"https://translate.google.com/m?tl={lang}&sl=auto&q={url_quote(text)}"
            response = curl_requests.get(url, timeout=10)
            soup = bs4.BeautifulSoup(response.text, "html.parser")
            result = soup.find("div", class_="result-container")
            if result:
                return result.text
            return text
        except Exception as e:
            logger.warning(f"Deef.translate: {e}")
            return text

    def short_url(self, long_url: str = None) -> str:
        '''Сокращение ссылки через clck.ru'''
        if not long_url:
            return long_url or ""
        try:
            response = curl_requests.get(f"https://clck.ru/--?url={url_quote(long_url, safe='')}", timeout=10)
            response.raise_for_status()
            return response.text.strip()
        except Exception as e:
            logger.warning(f"Deef.short_url: {e}")
            return long_url

    def run_in_bg(self, func, *args, **kwargs) -> threading.Thread:
        '''Запускает функцию в фоновом потоке. Возвращает Thread'''
        def wrapper():
            try:
                func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Deef.run_in_bg({getattr(func, '__name__', '?')}): {e}")
        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
        return thread

    def encode_base64(self, path: str = None) -> Optional[str]:
        '''Кодирует файл в base64'''
        if not path:
            raise ValueError("Deef.encode_base64: path обязателен")
        try:
            with open(path, "rb") as file:
                return base64.b64encode(file.read()).decode("utf-8")
        except FileNotFoundError:
            logger.error(f"Deef.encode_base64: файл не найден: {path}")
            return None

    def perplexity_ask(self, model: str, query: str) -> dict:
        '''Запрос к Perplexity AI. Если модель не найдена — используется turbo.
        Args:
            model: Название модели (например "o3pro", "turbo", "auto")
            query: Текст запроса
        Returns:
            {"text": "ответ", "urls": ["url1", "url2", ...]}
            При ошибке: {"text": "Error", "urls": []}
        Пример:
            deef = Deef()
            result = deef.perplexity_ask("turbo", "Столица Франции?")
            print(result["text"])
            for url in result["urls"]:
                print(url)
        '''
        ERROR_RESULT = {"text": "Error", "urls": []}
        BASE_URL = "https://www.perplexity.ai"
        MODE_API_MAP = {
            "search": "copilot",
            "research": "research",
            "agentic_research": "agentic_research",
            "studio": "studio",
            "study": "study",
            "document_review": "document_review",
            "browser_agent": "browser_agent",
            "asi": "asi"}
        try:
            try:
                with CurlSession(impersonate="chrome") as config_session:
                    config_resp = config_session.get(f"{BASE_URL}/rest/models/config", params={"config_schema": "v1", "version": "2.18", "source": "default"}, timeout=15)
                    config_json = config_resp.json() if config_resp.status_code == 200 and config_resp.content else {}
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
            with CurlSession(headers=headers, timeout=300, impersonate="chrome") as session:
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
                    "query_str": query}
                response = session.post(f"{BASE_URL}/rest/sse/perplexity_ask", json=payload)
                if response.status_code >= 400:
                    logger.error(f"Deef.perplexity_ask: HTTP {response.status_code}")
                    return ERROR_RESULT
                content = response.content
                if isinstance(content, bytes):
                    content = content.decode("utf-8")
            full_text = ""
            urls = []
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
            logger.error(f"Deef.perplexity_ask: {e}")
            return ERROR_RESULT


class ChatGPT:
    '''Клиент для OpenAI-совместимых API'''
    def __init__(self, url: str, headers: dict, impersonate: str = None):
        self.url = url.rstrip("/")
        self.headers = headers
        self._session = CurlSession(impersonate=impersonate)
        self._session.headers.update(headers)

    def _make_request(self, method: str, endpoint: str, data: Optional[dict] = None, files: Optional[dict] = None) -> Union[dict, list]:
        '''Выполняет HTTP-запрос к API'''
        url = f"{self.url}/{endpoint.lstrip('/')}"
        try:
            if files:
                response = self._session.request(method=method, url=url, files=files, data=data, timeout=120)
            else:
                response = self._session.request(method=method, url=url, json=data, timeout=120)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"ChatGPT({endpoint}): {e}")
            return {"error": str(e)}

    def generate_chat_completion(self, model: str, messages: list, temperature: Optional[float] = None, max_tokens: Optional[int] = None, stream: bool = False, **kwargs) -> dict:
        '''Генерация ответа в чате'''
        data = {"model": model, "messages": messages, "stream": stream, **kwargs}
        if temperature is not None:
            data["temperature"] = temperature
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
        return self._make_request("POST", "chat/completions", data=data)

    def generate_image(self, prompt: str, n: int = 1, size: str = "1024x1024", response_format: str = "url", **kwargs) -> dict:
        '''Генерация изображения'''
        data = {"prompt": prompt, "n": n, "size": size, "response_format": response_format, **kwargs}
        return self._make_request("POST", "images/generations", data=data)

    def generate_embedding(self, model: str, input_data: Union[str, list], user: Optional[str] = None, **kwargs) -> dict:
        '''Генерация embedding-вектора'''
        data = {"model": model, "input": input_data, **kwargs}
        if user:
            data["user"] = user
        return self._make_request("POST", "embeddings", data=data)

    def generate_transcription(self, file: BinaryIO, model: str, language: Optional[str] = None, prompt: Optional[str] = None, response_format: str = "json", temperature: float = 0, **kwargs) -> Union[dict, str]:
        '''Транскрипция аудио'''
        data = {"model": model, "response_format": response_format, "temperature": temperature, **kwargs}
        if language:
            data["language"] = language
        if prompt:
            data["prompt"] = prompt
        return self._make_request("POST", "audio/transcriptions", data=data, files={"file": file})

    def generate_translation(self, file: BinaryIO, model: str, prompt: Optional[str] = None, response_format: str = "json", temperature: float = 0, **kwargs) -> Union[dict, str]:
        '''Перевод аудио'''
        data = {"model": model, "response_format": response_format, "temperature": temperature, **kwargs}
        if prompt:
            data["prompt"] = prompt
        return self._make_request("POST", "audio/translations", data=data, files={"file": file})

    def get_models(self) -> dict:
        '''Список доступных моделей'''
        return self._make_request("GET", "models")