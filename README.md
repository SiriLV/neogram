# 📚 Документация neogram v9.4

**Установка:**

`pip install neogram` -> Для Windows и Linux
- - - - -
`pip3 install neogram` -> Для Mac

## 1. Основной класс `Bot`
__Находится в корне пакета. Отвечает за взаимодействие с серверами Telegram.__

**Инициализация:**
```python
from neogram import Bot
bot = Bot(token="YOUR_TOKEN", timeout=60)
```

**Основные методы (синхронные):**

| Метод | Описание | Аргументы |
|:---|:---|:---|
| `get_updates` | Получение входящих обновлений (Long Polling). | `offset`, `timeout`, `allowed_updates` |
| `send_message` | Отправка текстового сообщения. | `chat_id`, `text`, `parse_mode`, `reply_markup`, `reply_parameters` |
| `send_photo` | Отправка фото. | `chat_id`, `photo` (str/bytes/IO), `caption` |
| `send_video` | Отправка видео. | `chat_id`, `video`, `caption`, `supports_streaming` |
| `send_document` | Отправка файла. | `chat_id`, `document`, `caption` |
| `send_audio` | Отправка аудио (MP3). | `chat_id`, `audio`, `performer`, `title` |
| `send_voice` | Отправка голосового сообщения (OGG/OPUS). | `chat_id`, `voice` |
| `answer_callback_query` | Ответ на нажатие инлайн-кнопки. | `callback_query_id`, `text`, `show_alert` |
| `edit_message_text` | Редактирование текста сообщения. | `chat_id`, `message_id`, `text`, `reply_markup` |
| `delete_message` | Удаление сообщения. | `chat_id`, `message_id` |
| `copy_message` | Копирование сообщения (аналог пересылки без заголовка). | `chat_id`, `from_chat_id`, `message_id` |

*Примечание: В библиотеке реализованы все методы Telegram Bot API (включая работу со стикерами, платежами, играми и паспортом).*

## 2. Типы данных (Data Classes)
Библиотека использует типизированные классы для всех объектов Telegram.

**Важные особенности именования полей:**
В Python есть зарезервированные слова, которые конфликтуют с полями Telegram API. Библиотека автоматически преобразует их:
*   `type` ➝ **`type_val`** (например, в `Chat`, `MessageEntity`, `InputFile`).
*   `from` ➝ **`from_user`** (например, в `Message`, `CallbackQuery`).
*   `filter` ➝ **`filter_val`**.

**Пример структуры `Update`:**
*   `update.message` (Message)
*   `update.callback_query` (CallbackQuery)
*   `update.inline_query` (InlineQuery)

## 3. Модуль нейросетей (AI)
Классы для интеграции с внешними AI-сервисами.

### Класс `OnlySQ`
Интерфейс к сервису OnlySQ. Для пользования потребуетя api ключ: https://my.onlysq.ru/
*   `get_models(...)`: Получить список доступных моделей.
*   `generate_answer(model, messages)`: Генерация текста (чат).
*   `generate_image(model, prompt, ...)`: Генерация изображений.

### Класс `Deef`
Набор утилит и альтернативных API.
*   `translate(text, lang)`: Перевод текста (через Google Translate).
*   `short_url(long_url)`: Сокращение ссылок (clck.ru).
*   `perplexity_ask(model, query)`: Генерация через PerplexityAI
*   `encode_base64(path)`: Кодирование файла в base64.
*   `run_in_bg(func, ...)`: Запуск функции в отдельном потоке.

### Класс `ChatGPT`
Прямая обертка над OpenAI-compatible API.
*   `generate_chat_completion(...)`: Чат-комплишн.
*   `generate_image(...)`: DALL-E.

---

# 🛠 Примеры использования (17 примеров)

### 1) Базовый бот: Эхо и Фото
```python
import time
import sys
from neogram import (
    Bot, Update, ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton, 
    TelegramError, ReplyParameters
)

TOKEN = "ВАШ_ТОКЕН" 
bot = Bot(token=TOKEN, timeout=30)

def get_main_keyboard():
    btn1 = KeyboardButton(text="📸 Пришли фото")
    btn2 = KeyboardButton(text="❓ Помощь")
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[btn1, btn2]], 
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )
    return keyboard

def handle_message(update: Update):
    msg = update.message
    user = msg.from_user
    chat_id = msg.chat.id
    text = msg.text
    print(f"Got message from {user.first_name}: {text}")

    if text == "/start":
        bot.send_message(
            chat_id=chat_id,
            text=f"Привет, {user.first_name}! Я бот на neogram",
            reply_markup=get_main_keyboard()
        )
    elif text == "📸 Пришли фото":
        try:
            bot.send_chat_action(chat_id=chat_id, action="upload_photo")
            with open("cat.jpg", "rb") as photo_file:
                bot.send_photo(
                    chat_id=chat_id, 
                    photo=photo_file, 
                    caption="Вот ваш котик!",
                    reply_parameters=ReplyParameters(message_id=msg.message_id)
                )
        except FileNotFoundError:
            bot.send_message(chat_id=chat_id, text="Файл cat.jpg не найден")
        except Exception as e:
            bot.send_message(chat_id=chat_id, text=f"Ошибка: {e}")
    elif text == "❓ Помощь":
        inline_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Официальная дока", url="https://core.telegram.org/bots/api")],
            [InlineKeyboardButton(text="Автор скрипта", callback_data="author_info")]
        ])
        bot.send_message(chat_id=chat_id, text="Выберите действие:", reply_markup=inline_kb)
    else:
        bot.send_message(
            chat_id=chat_id,
            text=f"Вы написали: {text}",
            reply_parameters=ReplyParameters(message_id=msg.message_id)
        )

def handle_callback(update: Update):
    cb = update.callback_query
    if cb.data == "author_info":
        bot.answer_callback_query(callback_query_id=cb.id, text="SiriLV", show_alert=True)
        bot.edit_message_text(
            chat_id=cb.message.chat.id,
            message_id=cb.message.message_id,
            text="Автор этого чуда: SiriLV"
        )

def main():
    print("Бот запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message", "callback_query"])
            if not updates: continue
            for update in updates:
                offset = update.update_id + 1
                if update.message and update.message.text:
                    handle_message(update)
                elif update.callback_query:
                    handle_callback(update)
        except TelegramError as e:
            print(f"Telegram API Error: {e}")
            time.sleep(2)
        except KeyboardInterrupt:
            sys.exit(0)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
```

### 2) Расширенные клавиатуры и файлы из памяти
```python
import time
import sys
import io
from neogram import (
    Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton, ReplyParameters,
    TelegramError, InputFile
)

TOKEN = "ВАШ_ТОКЕН"
bot = Bot(token=TOKEN, timeout=30)

def get_main_keyboard():
    """Клавиатура с разными типами кнопок"""
    row1 = [KeyboardButton(text="🎛 Inline тест"), KeyboardButton(text="📄 Документ")]
    row2 = [KeyboardButton(text="📱 Мой контакт", request_contact=True)]
    return ReplyKeyboardMarkup(
        keyboard=[row1, row2],
        resize_keyboard=True,
        input_field_placeholder="Тестируем возможности..."
    )

def handle_text(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text
    print(f"[{msg.from_user.first_name}]: {text}")

    if text == "/start":
        bot.send_message(
            chat_id=chat_id,
            text="<b>Расширенный тест бота.</b>\nВыберите действие:",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    elif text == "🎛 Inline тест":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🍎 Яблоко", callback_data="fruit_apple"),
                InlineKeyboardButton(text="🍌 Банан", callback_data="fruit_banana")
            ],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")]
        ])
        bot.send_message(chat_id=chat_id, text="Выберите фрукт (тест callback_data):", reply_markup=kb)
    elif text == "📄 Документ":
        bot.send_chat_action(chat_id=chat_id, action="upload_document")
        fake_file = io.BytesIO(b"Hello! This is a generated text file.")
        fake_file.name = "test_log.txt"
        bot.send_document(
            chat_id=chat_id,
            document=fake_file,
            caption="Этот файл создан в оперативной памяти Python",
            reply_parameters=ReplyParameters(message_id=msg.message_id)
        )
    elif msg.contact:
        bot.send_message(chat_id=chat_id, text=f"Получен контакт: {msg.contact.first_name} ({msg.contact.phone_number})")
    else:
        bot.send_message(chat_id=chat_id, text="Используйте кнопки меню.", reply_parameters=ReplyParameters(message_id=msg.message_id))

def handle_callback(update: Update):
    cb = update.callback_query
    data = cb.data
    chat_id = cb.message.chat.id
    msg_id = cb.message.message_id
    print(f"Callback: {data}")

    if data.startswith("fruit_"):
        fruit = data.split("_")[1]
        bot.answer_callback_query(callback_query_id=cb.id, text=f"Вы выбрали {fruit}!", show_alert=False)
        new_text = f"Выбор сделан: <b>{fruit.upper()}</b>"
        back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Вернуться", callback_data="reset_menu")]])
        bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=new_text, parse_mode="HTML", reply_markup=back_kb)
    elif data == "reset_menu":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🍎 Яблоко", callback_data="fruit_apple"), InlineKeyboardButton(text="🍌 Банан", callback_data="fruit_banana")],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")]
        ])
        bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text="Выберите фрукт заново:", reply_markup=kb)
    elif data == "close_menu":
        bot.answer_callback_query(callback_query_id=cb.id, text="Меню закрыто")
        bot.delete_message(chat_id=chat_id, message_id=msg_id)

def main():
    print("🤖 Advanced Bot Test запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message", "callback_query"])
            if not updates: continue
            for update in updates:
                offset = update.update_id + 1
                if update.message:
                    handle_text(update)
                elif update.callback_query:
                    handle_callback(update)
        except TelegramError as e:
            print(f"⚠ API Error: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)
        except Exception as e:
            print(f"🔥 Critical Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
```

### 3) Инлайн-режим, Дайсы и Опросы
```python
import time
import sys
import uuid
from neogram import (
    Bot, Update, InlineQueryResultArticle, InputTextMessageContent,
    InputPollOption, TelegramError
)

TOKEN = "ВАШ_ТОКЕН"
bot = Bot(token=TOKEN, timeout=45)

def handle_inline_query(update: Update):
    query = update.inline_query
    text = query.query or "Пусто"
    query_id = query.id
    print(f"Inline Query: {text}")

    # ВАЖНО: Используем type_val вместо type
    result_1 = InlineQueryResultArticle(
        type_val="article", 
        id=str(uuid.uuid4()),
        title="📢 Кричалка",
        description=f"Отправить: {text.upper()}",
        input_message_content=InputTextMessageContent(message_text=f"Я КРИЧУ: {text.upper()}!!!")
    )
    result_2 = InlineQueryResultArticle(
        type_val="article", 
        id=str(uuid.uuid4()),
        title="🖌 Жирный HTML",
        description="Отправить жирным шрифтом",
        input_message_content=InputTextMessageContent(message_text=f"<b>{text}</b>", parse_mode="HTML")
    )
    result_3 = InlineQueryResultArticle(
        type_val="article", 
        id=str(uuid.uuid4()),
        title="🔗 Ссылка на Google",
        description="Отправить ссылку поиска",
        input_message_content=InputTextMessageContent(message_text=f"Вот что я нашел: https://www.google.com/search?q={text}")
    )
    
    try:
        bot.answer_inline_query(inline_query_id=query_id, results=[result_1, result_2, result_3], cache_time=1)
    except Exception as e:
        print(f"Ошибка Inline: {e}")

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text
    if text == "/start":
        bot.send_message(
            chat_id=chat_id,
            text="Тестируем:\n1. Напиши <code>@username_бота текст</code>\n2. Жми /dice\n3. Жми /poll",
            parse_mode="HTML"
        )
    elif text == "/dice":
        bot.send_dice(chat_id=chat_id, emoji="🎰")
    elif text == "/poll":
        options = [
            InputPollOption(text="Python 🐍"),
            InputPollOption(text="JavaScript ☕"),
            InputPollOption(text="C++ ⚙️")
        ]
        bot.send_poll(
            chat_id=chat_id,
            question="На чем написан этот генератор?",
            options=options,
            is_anonymous=False,
            type="quiz",
            correct_option_id=0
        )

def main():
    print("🚀 Inline & Methods Test запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message", "inline_query"])
            if not updates: continue
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
        except Exception as e:
            print(f"Critical: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
```

### 4) Тест медиа-файлов (Байтовые потоки)
```python
import time
import sys
import io
from neogram import Bot, Update, TelegramError, ReplyParameters, InputFile

TOKEN = "ВАШ_ТОКЕН"
bot = Bot(token=TOKEN, timeout=45)
# Минимальный валидный GIF
VALID_GIF_BYTES = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'

def create_virtual_file(name: str, content: bytes) -> io.BytesIO:
    file_obj = io.BytesIO(content)
    file_obj.name = name 
    return file_obj

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text
    
    if text == "/start":
        bot.send_message(chat_id=chat_id, text="Тест медиа-файлов.\nЖми /test_all для проверки всего сразу.")
    elif text == "/test_all":
        print("Отправляю документ...")
        doc = create_virtual_file("log.txt", b"System log: OK\nStatus: Active")
        bot.send_document(chat_id=chat_id, document=doc, caption="📄 <b>Текстовый документ</b>", parse_mode="HTML")
        time.sleep(1)

        print("Отправляю фото...")
        photo = create_virtual_file("pixel.gif", VALID_GIF_BYTES)
        bot.send_photo(chat_id=chat_id, photo=photo, caption="📸 <b>Микро-фото (1x1 px)</b>", parse_mode="HTML")
        time.sleep(1)

        print("Отправляю аудио...")
        audio_file = create_virtual_file("song.mp3", VALID_GIF_BYTES) 
        bot.send_audio(
            chat_id=chat_id,
            audio=audio_file,
            performer="Генератор Бот",
            title="Симфония Байтов",
            thumbnail=create_virtual_file("thumb.jpg", VALID_GIF_BYTES)
        )
        time.sleep(1)

        print("Отправляю войс...")
        voice_file = create_virtual_file("voice.ogg", b"Random noise bytes for test")
        bot.send_voice(chat_id=chat_id, voice=voice_file, caption="🗣 Голосовое (шум)")
        bot.send_message(chat_id=chat_id, text="✅ Тест медиа завершен!")

def main():
    print("📀 Media Test запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
            if not updates: continue
            for update in updates:
                offset = update.update_id + 1
                if update.message and update.message.text:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"Crit: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
```

### 5) Альбомы, URL-фото и Команды
```python
import time
import sys
from neogram import Bot, Update, TelegramError, InputMediaPhoto, BotCommand

TOKEN = "ВАШ_ТОКЕН"
bot = Bot(token=TOKEN, timeout=45)
IMG_1 = "https://www.python.org/static/community_logos/python-logo-master-v3-TM.png"
IMG_2 = "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1200px-Python-logo-notext.svg.png"

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text
    print(f"[{msg.from_user.first_name}]: {text}")

    if text == "/start":
        bot.send_message(chat_id=chat_id, text="Финальный тест фич:\n/url - Фото по ссылке\n/album - Альбом\n/geo - Геолокация\n/menu - Установить кнопку Меню")
    elif text == "/url":
        bot.send_chat_action(chat_id=chat_id, action="upload_photo")
        bot.send_photo(chat_id=chat_id, photo=IMG_1, caption="Это логотип Python, загруженный по ссылке!")
    elif text == "/album":
        bot.send_chat_action(chat_id=chat_id, action="upload_photo")
        # ВАЖНО: используем type_val
        media_1 = InputMediaPhoto(type_val="photo", media=IMG_1, caption="Лого с текстом")
        media_2 = InputMediaPhoto(type_val="photo", media=IMG_2, caption="Лого без текста")
        bot.send_media_group(chat_id=chat_id, media=[media_1, media_2])
    elif text == "/geo":
        bot.send_location(chat_id=chat_id, latitude=48.8584, longitude=2.2945)
        bot.send_message(chat_id=chat_id, text="Это Париж!")
    elif text == "/menu":
        commands = [
            BotCommand(command="start", description="Перезапуск"),
            BotCommand(command="url", description="Тест ссылки"),
            BotCommand(command="album", description="Тест альбома"),
            BotCommand(command="geo", description="Тест карты")
        ]
        success = bot.set_my_commands(commands=commands)
        if success:
            bot.send_message(chat_id=chat_id, text="✅ Меню команд обновлено!")

def main():
    print("🌐 URL & Features Test запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
            if not updates: continue
            for update in updates:
                offset = update.update_id + 1
                if update.message and update.message.text:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"Critical: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
```

### 6) Групповые функции, Реакции, Закрепы
```python
import time
import sys
from neogram import Bot, Update, TelegramError, ReactionTypeEmoji, ChatPermissions

TOKEN = "ВАШ_ТОКЕН"
bot = Bot(token=TOKEN, timeout=45)

def handle_group_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text
    msg_id = msg.message_id
    
    if text == "/fire":
        try:
            # type_val="emoji"
            reaction = ReactionTypeEmoji(type_val="emoji", emoji="🔥")
            bot.set_message_reaction(chat_id=chat_id, message_id=msg_id, reaction=[reaction])
        except TelegramError as e:
            print(f"Ошибка реакции: {e}")
    elif text == "/pin":
        try:
            bot.pin_chat_message(chat_id=chat_id, message_id=msg_id)
            bot.send_message(chat_id=chat_id, text="📌 Сообщение закреплено!")
        except TelegramError as e:
            bot.send_message(chat_id=chat_id, text=f"Нужны права админа: {e}")
    elif text == "/invite":
        try:
            expire = int(time.time()) + 3600 
            link = bot.create_chat_invite_link(chat_id=chat_id, name="Секретная ссылка", expire_date=expire, member_limit=1)
            bot.send_message(chat_id=chat_id, text=f"🎫 Ссылка:\n{link.invite_link}")
        except TelegramError as e:
            bot.send_message(chat_id=chat_id, text=f"Ошибка: {e}")
    elif text == "/sticker":
        sticker_url = "https://www.gstatic.com/webp/gallery/1.webp"
        try:
            bot.send_sticker(chat_id=chat_id, sticker=sticker_url)
        except Exception as e:
            bot.send_message(chat_id=chat_id, text=f"Ошибка стикера: {e}")

def handle_private_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text
    if text == "/start":
        bot.send_message(chat_id=chat_id, text="Добавь меня в группу и сделай админом!")
    elif text == "/me":
        photos = bot.get_user_profile_photos(user_id=msg.from_user.id, limit=1)
        if photos.total_count > 0:
            file_id = photos.photos[0][-1].file_id
            bot.send_photo(chat_id=chat_id, photo=file_id, caption="Я нашел твою аватарку!")
        else:
            bot.send_message(chat_id=chat_id, text="У тебя нет аватарки.")

def main():
    print("👮 Admin & Group Test запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
            if not updates: continue
            for update in updates:
                offset = update.update_id + 1
                if update.message:
                    chat_type = update.message.chat.type_val
                    if chat_type in ["group", "supergroup"]:
                        handle_group_message(update)
                    else:
                        handle_private_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"Critical: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
```

### 7) Редактирование медиа, Спойлеры
```python
import time
import sys
from neogram import Bot, Update, TelegramError, InputMediaPhoto, InputMediaDocument

TOKEN = "ВАШ_ТОКЕН"
bot = Bot(token=TOKEN, timeout=45)
IMG_1 = "https://www.python.org/static/community_logos/python-logo-master-v3-TM.png"
IMG_2 = "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1200px-Python-logo-notext.svg.png"

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text
    
    if text and text.startswith("/start"):
        args = text.split()
        if len(args) > 1:
            bot.send_message(chat_id=chat_id, text=f"Промокод: <b>{args[1]}</b>", parse_mode="HTML")
        else:
            bot.send_message(chat_id=chat_id, text="Старт. Попробуй: /dice, /spoiler, /media")
    elif text == "/spoiler":
        html_text = "Текст.\n<span class='tg-spoiler'>Секретный спойлер!</span>"
        bot.send_message(chat_id=chat_id, text=html_text, parse_mode="HTML")
    elif text == "/dice":
        sent_msg = bot.send_dice(chat_id=chat_id, emoji="🎲")
        value = sent_msg.dice.value
        time.sleep(3)
        bot.send_message(
            chat_id=chat_id, 
            text=f"Выпало: <b>{value}</b>!", 
            parse_mode="HTML",
            reply_parameters={"message_id": sent_msg.message_id}
        )
    elif text == "/media":
        sent_msg = bot.send_photo(chat_id=chat_id, photo=IMG_1, caption="Картинка 1 (Python)")
        time.sleep(2)
        new_media = InputMediaPhoto(type_val="photo", media=IMG_2, caption="🔄 Картинка заменилась.")
        try:
            bot.edit_message_media(chat_id=chat_id, message_id=sent_msg.message_id, media=new_media)
        except TelegramError as e:
            print(f"Ошибка смены медиа: {e}")

def main():
    print("💎 Modern Features Test запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
            if not updates: continue
            for update in updates:
                offset = update.update_id + 1
                if update.message:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"Critical: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
```

### 8) Живая локация и Форумы
```python
import time
import sys
from neogram import Bot, Update, TelegramError, ReplyParameters

TOKEN = "ВАШ_ТОКЕН"
bot = Bot(token=TOKEN, timeout=45)

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text
    
    if text == "/live":
        lat = 55.751244
        lon = 37.618423
        sent_msg = bot.send_location(chat_id=chat_id, latitude=lat, longitude=lon, live_period=60)
        bot.send_message(chat_id=chat_id, text="🚕 Я поехал!")
        for i in range(1, 4):
            time.sleep(2)
            lat += 0.0005 
            lon += 0.0005
            try:
                bot.edit_message_live_location(chat_id=chat_id, message_id=sent_msg.message_id, latitude=lat, longitude=lon)
            except TelegramError: pass
        time.sleep(1)
        bot.stop_message_live_location(chat_id=chat_id, message_id=sent_msg.message_id)
        bot.send_message(chat_id=chat_id, text="🏁 Приехали.")
    elif text == "/topic":
        if msg.chat.type_val == "private":
            bot.send_message(chat_id=chat_id, text="Только для супергрупп с темами!")
            return
        try:
            topic = bot.create_forum_topic(chat_id=chat_id, name="Генератор Python Topic", icon_color=7322096)
            thread_id = topic.message_thread_id
            bot.send_message(chat_id=chat_id, message_thread_id=thread_id, text=f"👋 Тема: <b>{topic.name}</b>", parse_mode="HTML")
            time.sleep(3)
            bot.close_forum_topic(chat_id=chat_id, message_thread_id=thread_id)
            bot.edit_forum_topic(chat_id=chat_id, message_thread_id=thread_id, name="[CLOSED] Генератор")
        except TelegramError as e:
            bot.send_message(chat_id=chat_id, text=f"Ошибка форума: {e}")
    elif text == "/clean":
        if msg.chat.type_val != "private":
            bot.unpin_all_chat_messages(chat_id=chat_id)
            bot.send_message(chat_id=chat_id, text="🧹 Сообщения откреплены.")

def main():
    print("🌍 Geo & Business Test запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
            if not updates: continue
            for update in updates:
                offset = update.update_id + 1
                if update.message:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"Critical: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
```

### 9) Платежи (Invoices)
```python
import time
import sys
from neogram import Bot, Update, TelegramError, LabeledPrice, PreCheckoutQuery

TOKEN = "ВАШ_ТОКЕН_БОТА"
PROVIDER_TOKEN = "ВАШ_ТОКЕН_ПЛАТЕЖКИ" # Из BotFather
bot = Bot(token=TOKEN, timeout=45)

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text

    if msg.successful_payment:
        pay = msg.successful_payment
        bot.send_message(chat_id=chat_id, text=f"✅ Оплата прошла: {pay.total_amount/100} {pay.currency}")
        return

    if not text: return
    if text == "/buy":
        prices = [LabeledPrice(label="Товар", amount=10000)] # 100.00 RUB
        try:
            bot.send_invoice(
                chat_id=chat_id,
                title="Супер Товар",
                description="Описание товара",
                payload="sku_123",
                provider_token=PROVIDER_TOKEN,
                currency="RUB",
                prices=prices,
                start_parameter="buy_test",
                is_flexible=False
            )
        except TelegramError as e:
            bot.send_message(chat_id=chat_id, text=f"Ошибка: {e}")
    elif text == "/webhook":
        info = bot.get_webhook_info()
        bot.send_message(chat_id=chat_id, text=f"URL: {info.url}")

def handle_pre_checkout(update: Update):
    query = update.pre_checkout_query
    bot.answer_pre_checkout_query(pre_checkout_query_id=query.id, ok=True)

def main():
    print("💳 Payment Test запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message", "pre_checkout_query"])
            if not updates: continue
            for update in updates:
                offset = update.update_id + 1
                if update.pre_checkout_query:
                    handle_pre_checkout(update)
                elif update.message:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"Critical: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
```

### 10) Telegram Stars и WebApps
```python
import time
import sys
from neogram import (
    Bot, Update, TelegramError, LabeledPrice, WebAppInfo, 
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, 
    InlineKeyboardButton, InputPaidMediaPhoto
)

TOKEN = "ВАШ_ТОКЕН"
bot = Bot(token=TOKEN, timeout=45)

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text

    if msg.successful_payment and msg.successful_payment.currency == "XTR":
        bot.send_message(chat_id=chat_id, text=f"✨ Получено {msg.successful_payment.total_amount} Звезд!")
        return
    if msg.web_app_data:
        bot.send_message(chat_id=chat_id, text=f"📱 Данные WebApp: {msg.web_app_data.data}")
        return
    if not text: return

    if text == "/stars":
        try:
            bot.send_invoice(
                chat_id=chat_id,
                title="Подписка",
                description="Оплата Stars",
                payload="stars_1",
                provider_token="", # Пусто для XTR
                currency="XTR",
                prices=[LabeledPrice(label="1 Звезда", amount=1)],
                start_parameter="stars"
            )
        except TelegramError as e:
            bot.send_message(chat_id=chat_id, text=f"Ошибка: {e}")
    elif text == "/paid_media":
        try:
            media = InputPaidMediaPhoto(type_val="photo", media="https://www.python.org/static/community_logos/python-logo-master-v3-TM.png")
            bot.send_paid_media(chat_id=chat_id, star_count=1, media=[media], caption="🔒 Платное фото")
        except TelegramError as e:
            bot.send_message(chat_id=chat_id, text=f"Ошибка: {e}")
    elif text == "/webapp":
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Open WebApp", web_app=WebAppInfo(url="https://webviewdemo.telegram.org"))]], resize_keyboard=True)
        bot.send_message(chat_id=chat_id, text="Тест WebApp:", reply_markup=kb)

def handle_pre_checkout(update: Update):
    query = update.pre_checkout_query
    bot.answer_pre_checkout_query(pre_checkout_query_id=query.id, ok=True)

def main():
    print("✨ Stars & WebApp Test запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message", "pre_checkout_query"])
            if not updates: continue
            for update in updates:
                offset = update.update_id + 1
                if update.pre_checkout_query:
                    handle_pre_checkout(update)
                elif update.message:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"Crit: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
```

### 11) Стикеры и Настройки меню
```python
import time
import sys
import io
from neogram import Bot, Update, TelegramError, MenuButtonWebApp, MenuButtonDefault, WebAppInfo, InputSticker

TOKEN = "ВАШ_ТОКЕН"
bot = Bot(token=TOKEN, timeout=45)
# Валидный PNG 1x1 пиксель (для примера нужен 512x512, но проверим механику)
VALID_PNG = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    user_id = msg.from_user.id
    text = msg.text

    if text == "/menu_web":
        btn = MenuButtonWebApp(type_val="web_app", text="Google", web_app=WebAppInfo(url="https://google.com"))
        bot.set_chat_menu_button(chat_id=chat_id, menu_button=btn)
        bot.send_message(chat_id=chat_id, text="✅ Кнопка меню изменена!")
    elif text == "/menu_def":
        btn = MenuButtonDefault(type_val="default")
        bot.set_chat_menu_button(chat_id=chat_id, menu_button=btn)
        bot.send_message(chat_id=chat_id, text="🔙 Меню сброшено.")
    elif text == "/new_pack":
        pack_name = f"test_{int(time.time())}_by_{bot.get_me().username}"
        try:
            f = io.BytesIO(VALID_PNG)
            f.name = "sticker.png"
            uploaded = bot.upload_sticker_file(user_id=user_id, sticker=f, sticker_format="static")
            sticker_def = InputSticker(sticker=uploaded.file_id, format="static", emoji_list=["😎"])
            
            bot.create_new_sticker_set(user_id=user_id, name=pack_name, title="Test Pack", stickers=[sticker_def])
            bot.send_message(chat_id=chat_id, text=f"Пак создан: t.me/addstickers/{pack_name}")
        except TelegramError as e:
            bot.send_message(chat_id=chat_id, text=f"Ошибка: {e}")

def main():
    print("⚙️ Settings & Stickers Test запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
            if not updates: continue
            for update in updates:
                offset = update.update_id + 1
                if update.message:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"Critical: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
```

### 12) Подарки и Черновики
```python
import time
import sys
import uuid
from neogram import Bot, Update, TelegramError, InlineQueryResultArticle, InputTextMessageContent

TOKEN = "ВАШ_ТОКЕН"
bot = Bot(token=TOKEN, timeout=45)

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    user_id = msg.from_user.id
    text = msg.text

    if text == "/gift":
        try:
            bot.send_gift(user_id=user_id, gift_id="123", text="Держи подарок! 🎁")
        except TelegramError as e:
            bot.send_message(chat_id=chat_id, text=f"Ошибка подарка (нужен баланс): {e}")
    elif text == "/draft":
        result = InlineQueryResultArticle(
            type_val="article",
            id=str(uuid.uuid4()),
            title="🔥 Заготовка",
            input_message_content=InputTextMessageContent(message_text="Сообщение из черновика")
        )
        try:
            prepared = bot.save_prepared_inline_message(user_id=user_id, result=result, allow_user_chats=True)
            bot.send_message(chat_id=chat_id, text=f"Черновик создан! ID: {prepared.id}")
        except TelegramError as e:
            bot.send_message(chat_id=chat_id, text=f"Ошибка: {e}")

def main():
    print("🎁 Gifts & Drafts Test запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
            if not updates: continue
            for update in updates:
                offset = update.update_id + 1
                if update.message:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"Critical: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
```

### 13) Заявки на вступление и Бизнес
```python
import time
import sys
from neogram import Bot, Update, TelegramError

TOKEN = "ВАШ_ТОКЕН"
bot = Bot(token=TOKEN, timeout=45)

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text
    
    if text == "/link":
        if msg.chat.type_val == "private":
            bot.send_message(chat_id=chat_id, text="Только для групп!")
            return
        try:
            invite = bot.create_chat_invite_link(chat_id=chat_id, name="Закрытый клуб", creates_join_request=True)
            bot.send_message(chat_id=chat_id, text=f"Ссылка с одобрением:\n{invite.invite_link}")
        except TelegramError as e:
            bot.send_message(chat_id=chat_id, text=f"Ошибка: {e}")
    elif text == "/info":
        info = bot.get_chat(chat_id=chat_id)
        bot.send_message(chat_id=chat_id, text=f"ID: {info.id}, Title: {info.title}")

def handle_join_request(update: Update):
    req = update.chat_join_request
    print(f"Заявка от {req.from_user.first_name}")
    try:
        bot.approve_chat_join_request(chat_id=req.chat.id, user_id=req.from_user.id)
        bot.send_message(chat_id=req.from_user.id, text="Заявка одобрена!")
    except Exception as e:
        print(f"Ошибка: {e}")

def handle_business(update: Update):
    bc = update.business_connection
    if bc.is_enabled:
        bot.send_message(chat_id=bc.user.id, text=f"Бизнес подключен: {bc.id}")

def main():
    print("🔐 Access & Business Test запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message", "chat_join_request", "business_connection"])
            if not updates: continue
            for update in updates:
                offset = update.update_id + 1
                if update.message:
                    handle_message(update)
                elif update.chat_join_request:
                    handle_join_request(update)
                elif update.business_connection:
                    handle_business(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"Critical: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
```

### 14) Скачивание файлов и Модерация
```python
import time
import sys
from neogram import Bot, Update, TelegramError, ChatPermissions, ForceReply

TOKEN = "ВАШ_ТОКЕН"
bot = Bot(token=TOKEN, timeout=45)

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text

    if msg.document:
        try:
            file_info = bot.get_file(file_id=msg.document.file_id)
            url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}"
            bot.send_message(chat_id=chat_id, text=f"Ссылка на файл: {url}")
        except TelegramError as e:
            bot.send_message(chat_id=chat_id, text=f"Ошибка: {e}")
    elif text == "/quiz":
        bot.send_message(chat_id=chat_id, text="Твой вопрос?", reply_markup=ForceReply(force_reply=True))
    elif text == "/mute":
        if msg.reply_to_message:
            perms = ChatPermissions(can_send_messages=False)
            until = int(time.time()) + 60
            bot.restrict_chat_member(chat_id=chat_id, user_id=msg.reply_to_message.from_user.id, permissions=perms, until_date=until)
            bot.send_message(chat_id=chat_id, text="Мут на 1 минуту.")
    elif text == "/unmute" and msg.reply_to_message:
        perms = ChatPermissions(can_send_messages=True)
        bot.restrict_chat_member(chat_id=chat_id, user_id=msg.reply_to_message.from_user.id, permissions=perms)
        bot.send_message(chat_id=chat_id, text="Размучен.")

def main():
    print("🛡 Moderation & Download Test запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
            if not updates: continue
            for update in updates:
                offset = update.update_id + 1
                if update.message:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"Critical: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
```

### 15) Логирование
```python
import logging
from neogram import Bot

TOKEN = "ВАШ_ТОКЕН"
bot = Bot(token=TOKEN, timeout=45)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def main():
    logging.info("Бот запускается...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
            if not updates: continue
            for update in updates:
                offset = update.update_id + 1
                # Обработка...
        except Exception as e:
            logging.error(f"Ошибка: {e}")

if __name__ == "__main__":
    main()
```

### 16) Опросы и Игры
```python
import time
import sys
from neogram import Bot, Update, TelegramError, InputPollOption

TOKEN = "ВАШ_ТОКЕН"
bot = Bot(token=TOKEN, timeout=45)

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text

    if text == "/poll":
        bot.send_poll(
            chat_id=chat_id,
            question="Цвет?",
            options=[InputPollOption(text="Красный"), InputPollOption(text="Синий")],
            is_anonymous=False
        )
    elif text == "/game":
        try:
            bot.send_game(chat_id=chat_id, game_short_name="test_game")
        except TelegramError as e:
            bot.send_message(chat_id=chat_id, text=f"Ошибка (нужна игра в BotFather): {e}")

def handle_poll_answer(update: Update):
    ans = update.poll_answer
    print(f"Голос от {ans.user.first_name}: {ans.option_ids}")

def main():
    print("📡 Events & Games Test запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message", "poll_answer"])
            if not updates: continue
            for update in updates:
                offset = update.update_id + 1
                if update.poll_answer:
                    handle_poll_answer(update)
                elif update.message:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"Critical: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
```

### 17) Копирование, Удаление, Цитирование
```python
import time
import sys
from neogram import Bot, Update, TelegramError, ReplyParameters

TOKEN = "ВАШ_ТОКЕН"
bot = Bot(token=TOKEN, timeout=45)

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text
    if not text: return

    if text == "/copy" and msg.reply_to_message:
        target = msg.reply_to_message.message_id
        bot.copy_message(chat_id=chat_id, from_chat_id=chat_id, message_id=target, caption="Копия!")
    elif text == "/delete":
        sent = bot.send_message(chat_id=chat_id, text="Удалюсь через 3с...")
        time.sleep(3)
        bot.delete_message(chat_id=chat_id, message_id=sent.message_id)
        bot.send_message(chat_id=chat_id, text="Удалено.")
    elif text == "/quote":
        sent = bot.send_message(chat_id=chat_id, text="Строка 1\nСтрока 2\nСтрока 3")
        time.sleep(1)
        bot.send_message(
            chat_id=chat_id,
            text="Ответ на Строку 2",
            reply_parameters=ReplyParameters(message_id=sent.message_id, quote="Строка 2")
        )

def main():
    print("✂️ Copy, Delete & Quote Test запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
            if not updates: continue
            for update in updates:
                offset = update.update_id + 1
                if update.message:
                    handle_message(update)
        except TelegramError as e:
            print(f"API Error: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"Critical: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
```

**Лицензия проекта: MIT** | __Почта для связи: siriteamrs@gmail.com__