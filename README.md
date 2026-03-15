# 📚 Документация neogram v9.6

**neogram** — Python-библиотека для работы с Telegram Bot API

**Установка:**

`pip install neogram #Windows, venv`

`pip3 install neogram #MacOS, Linux`

---

## 1. Основной класс `Bot`

**Инициализация:**
```python
from neogram import Bot

bot = Bot(token="YOUR_TOKEN", timeout=60)

# С TLS-фингерпринтом браузера (обход ограничений):
bot = Bot(token="YOUR_TOKEN", timeout=60, impersonate="chrome")
```

| Параметр | Тип | По умолчанию | Описание |
|:---|:---|:---|:---|
| `token` | `str` | — | Telegram Bot Token от @BotFather |
| `timeout` | `int` | `60` | Таймаут запросов в секундах |
| `impersonate` | `str` | `None` | TLS-фингерпринт: `"chrome"`, `"firefox"`, `"safari"` и др. |

**Основные методы (синхронные):**

| Метод | Описание | Обязательные аргументы |
|:---|:---|:---|
| `get_updates` | Получение обновлений (Long Polling) | — (все опциональны) |
| `send_message` | Отправка текстового сообщения | `chat_id`, `text` |
| `send_photo` | Отправка фото | `chat_id`, `photo` |
| `send_video` | Отправка видео | `chat_id`, `video` |
| `send_document` | Отправка файла | `chat_id`, `document` |
| `send_audio` | Отправка аудио (MP3) | `chat_id`, `audio` |
| `send_voice` | Отправка голосового (OGG/OPUS) | `chat_id`, `voice` |
| `send_sticker` | Отправка стикера | `chat_id`, `sticker` |
| `send_location` | Отправка геолокации | `chat_id`, `latitude`, `longitude` |
| `send_poll` | Отправка опроса | `chat_id`, `question`, `options` |
| `send_dice` | Отправка дайса | `chat_id` |
| `send_media_group` | Отправка альбома | `chat_id`, `media` |
| `send_invoice` | Отправка счёта на оплату | `chat_id`, `title`, `description`, `payload`, `currency`, `prices` |
| `forward_message` | Пересылка сообщения | `chat_id`, `from_chat_id`, `message_id` |
| `copy_message` | Копирование сообщения | `chat_id`, `from_chat_id`, `message_id` |
| `edit_message_text` | Редактирование текста | `text` + (`chat_id`+`message_id` или `inline_message_id`) |
| `edit_message_media` | Замена медиа в сообщении | `media` + идентификатор сообщения |
| `delete_message` | Удаление сообщения | `chat_id`, `message_id` |
| `answer_callback_query` | Ответ на нажатие инлайн-кнопки | `callback_query_id` |
| `answer_inline_query` | Ответ на инлайн-запрос | `inline_query_id`, `results` |
| `get_me` | Информация о боте | — |
| `get_file` | Получение файла по ID | `file_id` |
| `get_chat` | Информация о чате | `chat_id` |
| `get_chat_member` | Информация о участнике | `chat_id`, `user_id` |
| `ban_chat_member` | Бан пользователя | `chat_id`, `user_id` |
| `restrict_chat_member` | Ограничение прав | `chat_id`, `user_id`, `permissions` |
| `set_my_commands` | Установка команд бота | `commands` |
| `set_chat_menu_button` | Кнопка меню чата | — |
| `create_chat_invite_link` | Создание пригласительной ссылки | `chat_id` |
| `pin_chat_message` | Закрепление сообщения | `chat_id`, `message_id` |
| `send_chat_action` | Статус "печатает..." | `chat_id`, `action` |
| `get_webhook_info` | Статус вебхука | — |

*В библиотеке реализованы **все** методы Telegram Bot API, включая стикеры, платежи, Stars, игры, Passport, форумы, бизнес-функции и истории.*

---

## 2. Типы данных (Data Classes)
Библиотека использует типизированные `@dataclass`-классы для всех объектов Telegram. Все наследуют `TelegramObject`.

**Переименованные поля (зарезервированные слова Python):**

| Telegram API | neogram | Где используется |
|:---|:---|:---|
| `type` | **`type_val`** | `Chat`, `MessageEntity`, `Sticker`, `InlineQueryResult*` и др. |
| `from` | **`from_user`** | `Message`, `CallbackQuery`, `InlineQuery` и др. |
| `filter` | **`filter_val`** | (редко) |

При вызове `to_dict()` поля автоматически конвертируются обратно (`type_val` → `type`, `from_user` → `from`).

**Ключевые классы:**

| Класс | Описание |
|:---|:---|
| `Update` | Входящее обновление (`.message`, `.callback_query`, `.inline_query` и т.д.) |
| `Message` | Сообщение (`.text`, `.from_user`, `.chat`, `.photo`, `.document` и др.) |
| `User` | Пользователь (`.id`, `.first_name`, `.username`) |
| `Chat` | Чат (`.id`, `.type_val`, `.title`) |
| `CallbackQuery` | Нажатие инлайн-кнопки (`.data`, `.from_user`, `.message`) |
| `InlineKeyboardMarkup` | Инлайн-клавиатура (`.inline_keyboard`) |
| `InlineKeyboardButton` | Кнопка (`.text`, `.callback_data`, `.url`) |
| `ReplyKeyboardMarkup` | Обычная клавиатура (`.keyboard`, `.resize_keyboard`) |
| `KeyboardButton` | Кнопка (`.text`, `.request_contact`) |
| `ReplyParameters` | Параметры ответа (`.message_id`, `.quote`) |
| `PhotoSize` / `Document` / `Audio` / `Video` / `Voice` | Медиа-файлы |
| `TelegramError` | Исключение API (`.error_code`, `.description`, `.method`, `.retry_after`) |

**Сериализация / десериализация:**
```python
from neogram import User, Message

# dict → объект
user = User.from_dict({"id": 123, "is_bot": False, "first_name": "Ivan"})
print(user.first_name)  # "Ivan"

# объект → dict
d = user.to_dict()
print(d)  # {"id": 123, "is_bot": False, "first_name": "Ivan"}

# Список
users = User.from_dict([{...}, {...}])  # → List[User]
```

---

## 3. Модуль AI и утилит
Классы для интеграции с внешними AI-сервисами

### Класс `OnlySQ`
Интерфейс к сервису OnlySQ. API-ключ: https://my.onlysq.ru/

```python
from neogram import OnlySQ

sq = OnlySQ(key="YOUR_API_KEY")

# Список моделей
models = sq.get_models(modality="text", status="work", return_names=True)

# Генерация текста
answer = sq.generate_answer(model="gpt-5.2-chat", messages=[{"role": "user", "content": "Привет!"}])
print(answer)

# Генерация изображения
success = sq.generate_image(model="flux", prompt="кот в космосе", filename="cat.png")
```

| Метод | Возврат | Описание |
|:---|:---|:---|
| `get_models(modality, can_tools, can_think, status, max_cost, return_names)` | `list` | Фильтрация моделей |
| `generate_answer(model, messages)` | `str` | Генерация текста |
| `generate_image(model, prompt, ratio, filename)` | `bool` | Генерация изображения |


### Класс `Deef`
Набор утилит и альтернативных API.

```python
from neogram import Deef

deef = Deef()

# Перевод текста
translated = deef.translate("Hello world", lang="ru")

# Сокращение ссылок
short = deef.short_url("https://very-long-url.com/path/to/page")

# Perplexity AI
result = deef.perplexity_ask("turbo", "Столица Франции?")
print(result["text"])   # "Столица Франции — Париж..."
print(result["urls"])   # ["https://...", "https://..."]

# Base64
b64 = deef.encode_base64("photo.jpg")

# Фоновый запуск
thread = deef.run_in_bg(some_function, arg1, arg2)
```

| Метод | Возврат | Описание |
|:---|:---|:---|
| `translate(text, lang)` | `str` | Перевод через Google Translate |
| `short_url(long_url)` | `str` | Сокращение ссылки (clck.ru) |
| `perplexity_ask(model, query)` | `dict` | `{"text": "...", "urls": [...]}` — ответ Perplexity AI |
| `encode_base64(path)` | `str \| None` | Кодирование файла в base64 |
| `run_in_bg(func, *args, **kwargs)` | `Thread` | Запуск функции в отдельном потоке |


### Класс `ChatGPT` (алиас: `OpenAI`)
Обёртка над OpenAI-совместимым API через curl_cffi.

```python
from neogram import ChatGPT  # или: from neogram import OpenAI

client = ChatGPT(url="https://api.openai.com/v1", headers={"Authorization": "Bearer YOUR_KEY"}, impersonate="chrome")

# Чат
resp = client.generate_chat_completion(model="gpt-4", messages=[{"role": "user", "content": "Привет!"}], temperature=0.8)

# Генерация изображения
images = client.generate_image(prompt="sunset over mountains")

# Список моделей
models = client.get_models()
```

| Метод | Описание |
|:---|:---|
| `generate_chat_completion(model, messages, temperature, max_tokens, stream, **kwargs)` | Чат-комплишн |
| `generate_image(prompt, n, size, response_format, **kwargs)` | Генерация изображений |
| `generate_embedding(model, input_data, user, **kwargs)` | Embedding-вектор |
| `generate_transcription(file, model, language, **kwargs)` | Транскрипция аудио |
| `generate_translation(file, model, **kwargs)` | Перевод аудио |
| `get_models()` | Список доступных моделей |

---

## 4. Обработка ошибок

```python
from neogram import Bot, TelegramError

bot = Bot(token="YOUR_TOKEN")

try:
    bot.send_message(chat_id=0, text="test")
except TelegramError as e:
    print(e.method)       # "sendMessage"
    print(e.error_code)   # 400
    print(e.description)  # "Bad Request: chat not found"
    print(e.retry_after)  # None (или секунды при rate limit)
    print(str(e))         # "[sendMessage] 400: Bad Request: chat not found (Неверные параметры запроса)"
```

Коды ошибок с подсказками:

| Код | Подсказка |
|:---|:---|
| 400 | Неверные параметры запроса |
| 401 | Невалидный токен бота |
| 403 | Бот заблокирован или нет прав |
| 404 | Метод не найден |
| 409 | Конфликт: два процесса на одном боте |
| 429 | Слишком много запросов (rate limit) |
| 500 | Внутренняя ошибка Telegram |

---

# 🛠 Примеры использования

### 1) Эхо-бот с клавиатурой
```python
import time
import sys
from neogram import Bot, Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, TelegramError, ReplyParameters

TOKEN = "Token"
bot = Bot(token=TOKEN, timeout=30)

def get_main_keyboard():
    return ReplyKeyboardMarkup( keyboard=[[KeyboardButton(text="📸 Пришли фото"), KeyboardButton(text="❓ Помощь")]], resize_keyboard=True, input_field_placeholder="Выберите действие...")

def handle_message(update: Update):
    msg = update.message
    user = msg.from_user
    chat_id = msg.chat.id
    text = msg.text
    print(f"[{user.first_name}]: {text}")
    if text == "/start":
        bot.send_message(chat_id=chat_id, text=f"Привет, {user.first_name}! Я бот на neogram 🚀", reply_markup=get_main_keyboard())
    elif text == "📸 Пришли фото":
        try:
            bot.send_chat_action(chat_id=chat_id, action="upload_photo")
            with open("cat.jpg", "rb") as photo_file:
                bot.send_photo(chat_id=chat_id, photo=photo_file, caption="Вот ваш котик! 🐱", reply_parameters=ReplyParameters(message_id=msg.message_id))
        except FileNotFoundError:
            bot.send_message(chat_id=chat_id, text="Файл cat.jpg не найден")
    elif text == "❓ Помощь":
        inline_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📖 Документация", url="https://core.telegram.org/bots/api")], [InlineKeyboardButton(text="👨‍💻 Автор", callback_data="author_info")]])
        bot.send_message(chat_id=chat_id, text="Выберите действие:", reply_markup=inline_kb)
    else:
        bot.send_message(chat_id=chat_id, text=f"Вы написали: {text}", reply_parameters=ReplyParameters(message_id=msg.message_id))

def handle_callback(update: Update):
    cb = update.callback_query
    if cb.data == "author_info":
        bot.answer_callback_query(callback_query_id=cb.id, text="neogram by SiriLV", show_alert=True)
        bot.edit_message_text(chat_id=cb.message.chat.id, message_id=cb.message.message_id, text="Автор: <b>SiriLV</b>", parse_mode="HTML")

def main():
    print("🤖 Бот запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message", "callback_query"])
            if not updates:
                continue
            for update in updates:
                offset = update.update_id + 1
                if update.message and update.message.text:
                    handle_message(update)
                elif update.callback_query:
                    handle_callback(update)
        except TelegramError as e:
            print(f"⚠ API Error: {e}")
            time.sleep(2)
        except KeyboardInterrupt:
            sys.exit(0)
        except Exception as e:
            print(f"🔥 Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
```

### 2) Инлайн-кнопки и файлы из памяти
```python
import time
import sys
import io
from neogram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyParameters, TelegramError

TOKEN = "Token"
bot = Bot(token=TOKEN, timeout=30)

def handle_text(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text
    if text == "/start":
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🎛 Inline тест"), KeyboardButton(text="📄 Документ")], [KeyboardButton(text="📱 Мой контакт", request_contact=True)]], resize_keyboard=True)
        bot.send_message(chat_id=chat_id, text="<b>Выберите действие:</b>", parse_mode="HTML", reply_markup=kb)
    elif text == "🎛 Inline тест":
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🍎 Яблоко", callback_data="fruit_apple"), InlineKeyboardButton(text="🍌 Банан", callback_data="fruit_banana")], [InlineKeyboardButton(text="❌ Закрыть", callback_data="close")]])
        bot.send_message(chat_id=chat_id, text="Выберите фрукт:", reply_markup=kb)
    elif text == "📄 Документ":
        bot.send_chat_action(chat_id=chat_id, action="upload_document")
        fake_file = io.BytesIO(b"Hello from neogram!")
        fake_file.name = "test.txt"
        bot.send_document(chat_id=chat_id, document=fake_file, caption="Файл из оперативной памяти")

def handle_callback(update: Update):
    cb = update.callback_query
    chat_id = cb.message.chat.id
    msg_id = cb.message.message_id
    if cb.data.startswith("fruit_"):
        fruit = cb.data.split("_")[1]
        bot.answer_callback_query(callback_query_id=cb.id, text=f"Выбрано: {fruit}")
        bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=f"Выбор: <b>{fruit}</b>", parse_mode="HTML")
    elif cb.data == "close":
        bot.delete_message(chat_id=chat_id, message_id=msg_id)

def main():
    print("🤖 Бот запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message", "callback_query"])
            if not updates:
                continue
            for update in updates:
                offset = update.update_id + 1
                if update.message:
                    handle_text(update)
                elif update.callback_query:
                    handle_callback(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

### 3) Инлайн-режим, Дайсы и Опросы
```python
import time
import sys
import uuid
from neogram import Bot, Update, InlineQueryResultArticle, InputTextMessageContent, InputPollOption, TelegramError

TOKEN = "Token"
bot = Bot(token=TOKEN, timeout=45)

def handle_inline_query(update: Update):
    query = update.inline_query
    text = query.query or "Пусто"
    results = [InlineQueryResultArticle(type_val="article", id=str(uuid.uuid4()), title="📢 Кричалка", description=f"Отправить: {text.upper()}", input_message_content=InputTextMessageContent(message_text=f"Я КРИЧУ: {text.upper()}!!!")),
        InlineQueryResultArticle(type_val="article", id=str(uuid.uuid4()), title="🖌 Жирный HTML", input_message_content=InputTextMessageContent(message_text=f"<b>{text}</b>", parse_mode="HTML"))]
    bot.answer_inline_query(inline_query_id=query.id, results=results, cache_time=1)

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text
    if text == "/dice":
        bot.send_dice(chat_id=chat_id, emoji="🎰")
    elif text == "/poll":
        bot.send_poll(chat_id=chat_id, question="Лучший язык?", options=[InputPollOption(text="Python 🐍"), InputPollOption(text="JS ☕"), InputPollOption(text="C++ ⚙️")], is_anonymous=False, type_val="quiz", correct_option_id=0)

def main():
    print("🤖 Бот запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message", "inline_query"])
            if not updates:
                continue
            for update in updates:
                offset = update.update_id + 1
                if update.inline_query:
                    handle_inline_query(update)
                elif update.message and update.message.text:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

### 4) Альбомы и URL-фото
```python
import time
import sys
from neogram import Bot, Update, TelegramError, InputMediaPhoto, BotCommand

TOKEN = "Token"
bot = Bot(token=TOKEN, timeout=45)

IMG_1 = "https://www.python.org/static/community_logos/python-logo-master-v3-TM.png"
IMG_2 = "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1200px-Python-logo-notext.svg.png"

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text
    if text == "/url":
        bot.send_photo(chat_id=chat_id, photo=IMG_1, caption="Фото по ссылке!")
    elif text == "/album":
        bot.send_media_group(chat_id=chat_id, media=[InputMediaPhoto(type_val="photo", media=IMG_1, caption="Лого 1"), InputMediaPhoto(type_val="photo", media=IMG_2, caption="Лого 2")])
    elif text == "/geo":
        bot.send_location(chat_id=chat_id, latitude=48.8584, longitude=2.2945)
    elif text == "/menu":
        bot.set_my_commands(commands=[BotCommand(command="url", description="Фото по ссылке"), BotCommand(command="album", description="Альбом"), BotCommand(command="geo", description="Геолокация")])
        bot.send_message(chat_id=chat_id, text="✅ Команды обновлены!")

def main():
    print("🤖 Бот запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
            if not updates:
                continue
            for update in updates:
                offset = update.update_id + 1
                if update.message and update.message.text:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

### 5) Реакции, Закрепы, Пригласительные ссылки
```python
import time
import sys
from neogram import Bot, Update, TelegramError, ReactionTypeEmoji

TOKEN = "Token"
bot = Bot(token=TOKEN, timeout=45)

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text
    msg_id = msg.message_id
    if text == "/fire":
        reaction = ReactionTypeEmoji(type_val="emoji", emoji="🔥")
        bot.set_message_reaction(chat_id=chat_id, message_id=msg_id, reaction=[reaction])
    elif text == "/pin":
        bot.pin_chat_message(chat_id=chat_id, message_id=msg_id)
        bot.send_message(chat_id=chat_id, text="📌 Закреплено!")
    elif text == "/invite":
        if msg.chat.type_val == "private":
            bot.send_message(chat_id=chat_id, text="❌ Только для групп!")
            return
        link = bot.create_chat_invite_link(chat_id=chat_id, name="Секретная ссылка", member_limit=1)
        bot.send_message(chat_id=chat_id, text=f"🎫 {link.invite_link}")

def main():
    print("🤖 Бот запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
            if not updates:
                continue
            for update in updates:
                offset = update.update_id + 1
                if update.message and update.message.text:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

### 6) Живая локация
```python
import time
import sys
from neogram import Bot, Update, TelegramError

TOKEN = "Token"
bot = Bot(token=TOKEN, timeout=45)

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    if msg.text == "/live":
        lat, lon = 55.751244, 37.618423
        sent = bot.send_location(chat_id=chat_id, latitude=lat, longitude=lon, live_period=60)
        bot.send_message(chat_id=chat_id, text="🚕 Поехали!")
        for _ in range(5):
            time.sleep(2)
            lat += 0.0005
            lon += 0.0005
            try:
                bot.edit_message_live_location(chat_id=chat_id, message_id=sent.message_id, latitude=lat, longitude=lon)
            except TelegramError:
                break
        bot.stop_message_live_location(chat_id=chat_id, message_id=sent.message_id)
        bot.send_message(chat_id=chat_id, text="🏁 Приехали!")

def main():
    print("🤖 Бот запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
            if not updates:
                continue
            for update in updates:
                offset = update.update_id + 1
                if update.message and update.message.text:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

### 7) Платежи (Stars)
```python
import time
import sys
from neogram import Bot, Update, TelegramError, LabeledPrice

TOKEN = "Token"
bot = Bot(token=TOKEN, timeout=45)

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    if msg.successful_payment:
        pay = msg.successful_payment
        bot.send_message(chat_id=chat_id, text=f"✅ Получено {pay.total_amount} ⭐")
        return
    if msg.text == "/stars":
        bot.send_invoice(chat_id=chat_id, title="Подписка", description="Оплата Stars", payload="stars_1", provider_token="", currency="XTR", prices=[LabeledPrice(label="1 Звезда", amount=1)])

def handle_pre_checkout(update: Update):
    bot.answer_pre_checkout_query(pre_checkout_query_id=update.pre_checkout_query.id, ok=True)

def main():
    print("💳 Бот запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message", "pre_checkout_query"])
            if not updates:
                continue
            for update in updates:
                offset = update.update_id + 1
                if update.pre_checkout_query:
                    handle_pre_checkout(update)
                elif update.message:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

### 8) Модерация (Мут/Размут)
```python
import time
import sys
from neogram import Bot, Update, TelegramError, ChatPermissions, ForceReply

TOKEN = "Token"
bot = Bot(token=TOKEN, timeout=45)

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text
    if text == "/mute" and msg.reply_to_message:
        perms = ChatPermissions(can_send_messages=False)
        until = int(time.time()) + 60
        bot.restrict_chat_member(chat_id=chat_id, user_id=msg.reply_to_message.from_user.id, permissions=perms, until_date=until)
        bot.send_message(chat_id=chat_id, text="🔇 Мут на 1 минуту")
    elif text == "/unmute" and msg.reply_to_message:
        perms = ChatPermissions(can_send_messages=True, can_send_polls=True)
        bot.restrict_chat_member(chat_id=chat_id, user_id=msg.reply_to_message.from_user.id, permissions=perms)
        bot.send_message(chat_id=chat_id, text="🔊 Размучен")
    elif text == "/quiz":
        bot.send_message(chat_id=chat_id, text="Ваш вопрос?", reply_markup=ForceReply(force_reply=True))

def main():
    print("🤖 Бот запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
            if not updates:
                continue
            for update in updates:
                offset = update.update_id + 1
                if update.message and update.message.text:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

### 9) Скачивание файлов
```python
import sys
import time
from neogram import Bot, Update, TelegramError

TOKEN = "Token"
bot = Bot(token=TOKEN, timeout=45)

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    if msg.document:
        file_info = bot.get_file(file_id=msg.document.file_id)
        url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}"
        bot.send_message(chat_id=chat_id, text=f"📥 Ссылка: {url}")
    elif msg.photo:
        biggest = msg.photo[-1]
        file_info = bot.get_file(file_id=biggest.file_id)
        url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}"
        bot.send_message(chat_id=chat_id, text=f"📸 Фото: {url}")

def main():
    print("🤖 Бот запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
            if not updates:
                continue
            for update in updates:
                offset = update.update_id + 1
                if update.message:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

### 10) AI-бот с OnlySQ
```python
import time
import sys
from neogram import Bot, Update, TelegramError, OnlySQ

TOKEN = "Token"
ONLYSQ_KEY = "OnlySQ_Token"

bot = Bot(token=TOKEN, timeout=60)
ai = OnlySQ(key=ONLYSQ_KEY)
user_histories = {}

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    user_id = msg.from_user.id
    text = msg.text
    if text == "/start":
        user_histories[user_id] = []
        bot.send_message(chat_id=chat_id, text="🤖 AI-бот на OnlySQ. Просто напишите сообщение!")
        return
    if text == "/clear":
        user_histories[user_id] = []
        bot.send_message(chat_id=chat_id, text="🧹 История очищена")
        return
    bot.send_chat_action(chat_id=chat_id, action="typing")
    history = user_histories.setdefault(user_id, [])
    history.append({"role": "user", "content": text})
    answer = ai.generate_answer(model="gpt-5.2-chat", messages=history)
    history.append({"role": "assistant", "content": answer})
    if len(history) > 20:
        user_histories[user_id] = history[-20:]
    bot.send_message(chat_id=chat_id, text=answer, parse_mode="Markdown")

def main():
    print("🤖 AI-бот запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
            if not updates:
                continue
            for update in updates:
                offset = update.update_id + 1
                if update.message and update.message.text:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

### 11) Perplexity-бот с источниками
```python
import time
import sys
from neogram import Bot, Update, TelegramError, Deef

TOKEN = "Token"
bot = Bot(token=TOKEN, timeout=60)
deef = Deef()

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text
    if text == "/start":
        bot.send_message(chat_id=chat_id, text="🔍 Perplexity-бот. Задайте вопрос!")
        return
    if not text or text.startswith("/"):
        return
    bot.send_chat_action(chat_id=chat_id, action="typing")
    result = deef.perplexity_ask("turbo", text)
    answer = result["text"]
    urls = result["urls"]
    response = answer
    if urls:
        response += "\n\n📎 <b>Источники:</b>"
        for i, url in enumerate(urls[:5], 1):
            response += f"\n{i}. {url}"
    if len(response) > 4096:
        response = response[:4093] + "..."
    bot.send_message(chat_id=chat_id, text=response, parse_mode="HTML")

def main():
    print("🔍 Perplexity-бот запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
            if not updates:
                continue
            for update in updates:
                offset = update.update_id + 1
                if update.message and update.message.text:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

### 12) Копирование, Удаление, Цитирование
```python
import time
from neogram import Bot, Update, TelegramError, ReplyParameters

TOKEN = "Token"
bot = Bot(token=TOKEN, timeout=45)

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text
    if text == "/copy" and msg.reply_to_message:
        bot.copy_message(chat_id=chat_id, from_chat_id=chat_id, message_id=msg.reply_to_message.message_id)
    elif text == "/delete":
        sent = bot.send_message(chat_id=chat_id, text="Удалюсь через 3с...")
        time.sleep(3)
        bot.delete_message(chat_id=chat_id, message_id=sent.message_id)
    elif text == "/quote":
        sent = bot.send_message(chat_id=chat_id, text="Строка 1\nСтрока 2\nСтрока 3")
        time.sleep(1)
        bot.send_message(chat_id=chat_id, text="Ответ на Строку 2", reply_parameters=ReplyParameters(message_id=sent.message_id, quote="Строка 2"))

def main():
    print("🤖 AI-бот запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
            if not updates:
                continue
            for update in updates:
                offset = update.update_id + 1
                if update.message and update.message.text:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

### 13) Заявки на вступление
```python
from neogram import Bot, Update, TelegramError

TOKEN = "ВАШ_ТОКЕН"
bot = Bot(token=TOKEN, timeout=45)

def handle_join_request(update: Update):
    req = update.chat_join_request
    print(f"Заявка от {req.from_user.first_name}")
    bot.approve_chat_join_request(chat_id=req.chat.id, user_id=req.from_user.id)
    bot.send_message(chat_id=req.from_user.id, text="✅ Добро пожаловать!")

def main():
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["chat_join_request"])
            if not updates:
                continue
            for update in updates:
                offset = update.update_id + 1
                if update.chat_join_request:
                    handle_join_request(update)
        except TelegramError as e:
            print(f"API Error: {e}")
```

---

**Лицензия:** MIT | **Контакт:** siriteamrs@gmail.com