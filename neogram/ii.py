import requests, json, base64, threading, re, bs4
from typing import Union, BinaryIO

#Блок - Нейросети
class OnlySQ:
    def get_models(self, modality: str | list = None, can_tools: bool = None, can_stream: bool = None, status: str = None, max_cost: float = None, return_names: bool = False) -> list:
        """
        Фильтрует модели по заданным параметрам
        Args:
            modality: Модальность ('text', 'image', 'sound') или список модальностей
            can_tools: Фильтр по поддержке инструментов
            can_stream: Фильтр по возможности потоковой передачи
            status: Статус модели (например, 'work')
            max_cost: Максимальная стоимость (включительно)
            return_names: Если True, возвращает названия моделей вместо ключей
        Returns:
            Список отфильтрованных моделей (ключи или названия)
        """
        try:
            response = requests.get('https://api.onlysq.ru/ai/models')
            response.raise_for_status()
            data = response.json()
            filtered_models = []
            for model_key, model_data in data["models"].items():
                matches = True
                if modality is not None:
                    if isinstance(modality, list):
                        if model_data["modality"] not in modality:
                            matches = False
                    else:
                        if model_data["modality"] != modality:
                            matches = False
                if matches and can_tools is not None:
                    model_tools = model_data.get("can-tools", False)
                    if model_tools != can_tools:
                        matches = False
                if matches and can_stream is not None:
                    model_can_stream = model_data.get("can-stream", False)
                    if model_can_stream != can_stream:
                        matches = False
                if matches and status is not None:
                    model_status = model_data.get("status", "")
                    if model_status != status:
                        matches = False
                if matches and max_cost is not None:
                    model_cost = model_data.get("cost", float('inf'))
                    if float(model_cost) > max_cost:
                        matches = False
                if matches:
                    if return_names:
                        filtered_models.append(model_data["name"])
                    else:
                        filtered_models.append(model_key)
            return filtered_models 
        except Exception as e:
            print(f"OnlySQ(get_models): {e}")
            return []

    def generate_answer(self, model: str = "gpt-5.2-chat", messages: dict = None) -> str:
        """Генерация ответа с использованием onlysq"""
        try:
            if messages is None:
                raise ValueError("Забыли указать messages")
            else:
                payload = {"model": model, "request": {"messages": messages}}
                response = requests.post("http://api.onlysq.ru/ai/v2", json=payload, headers={"Authorization":"Bearer openai"})
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"OnlySQ(generate_answer): {e}")
            return "Error"
    
    def generate_image(self, model: str = "flux", prompt: str = None, ratio: str = "16:9", filename: str = 'image.png') -> bool:
        """Генерация фотографии с использованием onlysq"""
        try:
            if prompt is None:
                raise ValueError("Забыли указать prompt")
            else:
                payload = {"model": model, "prompt": prompt, "ratio": ratio}
                response = requests.post("https://api.onlysq.ru/ai/imagen", json=payload, headers={"Authorization":"Bearer openai"})
                if response.status_code == 200:
                    img_bytes = base64.b64decode(response.json()["files"][0])
                    with open(filename, 'wb') as f:
                        f.write(img_bytes)
                    return True
                else:
                    return False
        except Exception as e:
            print(f"OnlySQ(generate_image): {e}")
            return False


class Deef:
    def translate(self, text: str = None, lang: str = "en") -> str:
        """Перевод текста"""
        try:
            if text is None:
                raise ValueError("Забыли указать text")
            base_url = f"https://translate.google.com/m?tl={lang}&sl=auto&q={text}"
            response = requests.get(base_url)
            soup = bs4.BeautifulSoup(response.text, "html.parser")
            translated_div = soup.find('div', class_='result-container')
            return translated_div.text
        except:
            return text

    def short_url(self, long_url: str = None) -> str:
        """Сокращение ссылок"""
        try:
            response = requests.get(f'https://clck.ru/--?url={long_url}')
            response.raise_for_status()
            return response.text.strip()
        except:
            return long_url
    
    def run_in_bg(self, func, *args, **kwargs):
        """Запускает функцию в фоне"""
        def wrapper():
            try:
                func(*args, **kwargs)
            except Exception as e:
                print(f"Error[{func}]: {e}")
        threading.Thread(target=wrapper, daemon=True).start()

    def encode_base64(self, path: str = None) -> str:
        """Кодирует файл в base64"""
        try:
            if path is None:
                raise ValueError("path must be provided and non-empty")
            with open(path, "rb") as file:
                return base64.b64encode(file.read()).decode('utf-8')
        except FileNotFoundError:
            return None
    
    def gen_ai_response(self, model: str = "Qwen3 235B", messages: list = None) -> dict[str]:
        """
        Отправляет запрос к API и возвращает словарь с полной информацией
        Args:
            model: Модель нейросети (Qwen3 235B или GPT OSS 120B)
            messages: Список сообщений в формате [{"role": "...", "content": "..."}]
        Returns:
            dict[str]: Словарь с ключами:
                - reasoning: Размышления модели
                - answer: Финальный ответ модели
                - status: Статус выполнения
                - cluster_info: Информация о кластере (если есть)
        """
        try:
            if messages is None:
                raise ValueError("Забыли указать messages")
            else:
                model_to_cluster = {"Qwen3 235B": "hybrid", "GPT OSS 120B": "nvidia"}
                cluster_mode = model_to_cluster.get(model)
                if cluster_mode is None:
                    raise ValueError(f"Неизвестная модель: {model}, Доступные модели: {list(model_to_cluster.keys())}")
                data = {"model": model, "clusterMode": cluster_mode, "messages": messages, "enableThinking": True}
                url = "https://chat.gradient.network/api/generate"
                response = requests.post(url, json=data, stream=True)
                result = {"reasoning": "", "answer": "", "status": "unknown", "cluster_info": None}
                for line in response.iter_lines():
                    if line:
                        try:
                            json_obj = json.loads(line.decode('utf-8'))
                            message_type = json_obj.get("type")
                            if message_type == "reply":
                                data_content = json_obj.get("data", {})
                                if "reasoningContent" in data_content:
                                    result["reasoning"] += data_content.get("reasoningContent", "")
                                if "content" in data_content:
                                    result["answer"] += data_content.get("content", "")
                            elif message_type == "jobInfo":
                                status = json_obj.get("data", {}).get("status")
                                result["status"] = status
                                if status == "completed":
                                    break
                            elif message_type == "clusterInfo":
                                result["cluster_info"] = json_obj.get("data", {})
                        except json.JSONDecodeError as e:
                            print(f"Ошибка декодирования JSON: {e}")
                            continue
                        except Exception as e:
                            print(f"Неожиданная ошибка: {e}")
                            continue
                return result
        except Exception as e:
            print(f"Deef(gen_ai_response): {e}")
            return {"reasoning": "Error", "answer": "Error", "status": "unknown", "cluster_info": None}
    
    def gen_gpt(self, messages: list = None) -> str:
        """Генерация текста с помощью GPT-4o"""
        try:
            if messages is None:
                raise ValueError("Забыли указать messages")
            else:
                r = requests.post("https://italygpt.it/api/chat", json={"messages": messages, "stream": True}, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36", "Accept": "text/event-stream"})
                if r.status_code == 200:
                    return r.text
                else:
                    return "Error"
        except Exception as e:
            print(f"Deef(gen_gpt): {e}")
            return "Error"


class ChatGPT:
    def __init__(self, url: str, headers: dict):
        self.url = url.rstrip("/")
        self.headers = headers

    def _make_request(self, method: str, endpoint: str, data: dict = None, files: dict = None) -> Union[dict, list]:
        try:
            url = f"{self.url}/{endpoint.lstrip('/')}"
            if files:
                response = requests.request(method=method, url=url, headers=self.headers, files=files, data=data)
            else:
                response = requests.request(method=method, url=url, headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"ChatGPT({endpoint}): {e}")
            return "Error"

    def generate_chat_completion(self, model: str, messages: list, temperature: float = None, max_tokens: int = None, stream: bool = False, **kwargs) -> Union[dict, list]:
        data = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": stream, **kwargs}
        return self._make_request("POST", "chat/completions", data=data)

    def generate_image(self, prompt: str, n: int = 1, size: str = "1024x1024", response_format: str = "url", **kwargs) -> dict:
        data = {"prompt": prompt, "n": n, "size": size, "response_format": response_format, **kwargs}
        return self._make_request("POST", "images/generations", data=data)

    def generate_embedding(self, model: str, input_i: Union[str, list], user: str = None, **kwargs) -> dict:
        data = {"model": model, "input": input_i, "user": user, **kwargs}
        return self._make_request("POST", "embeddings", data=data)

    def generate_transcription(self, file: BinaryIO, model: str, language: str = None, prompt: str = None, response_format: str = "json", temperature: float = 0, **kwargs) -> Union[dict, str]:
        data = {"model": model, "language": language, "prompt": prompt, "response_format": response_format, "temperature": temperature, **kwargs}
        files = {"file": file}
        return self._make_request("POST", "audio/transcriptions", data=data, files=files)

    def generate_translation(self, file: BinaryIO, model: str, prompt: str = None, response_format: str = "json", temperature: float = 0, **kwargs) -> Union[dict, str]:
        data = {"model": model, "prompt": prompt, "response_format": response_format, "temperature": temperature, **kwargs}
        files = {"file": file}
        return self._make_request("POST", "audio/translations", data=data, files=files)
    
    def get_models(self):
        return self._make_request("GET", "models")