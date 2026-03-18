<div align="center">

# neogram

**Современная Python-библиотека для Telegram Bot API**

Синхронная, типизированная обёртка над Telegram Bot API на базе `curl_cffi`.
Поддерживает все методы API, включает AI-утилиты и работает без лишних зависимостей.

</div>

---

## Содержание

- [Установка](#установка)
- [Быстрый старт](#быстрый-старт)
- [Класс Bot](#класс-bot)
  - [Инициализация](#инициализация)
  - [Сообщения](#сообщения)
  - [Медиафайлы](#медиафайлы)
  - [Редактирование и удаление](#редактирование-и-удаление)
  - [Клавиатуры и колбэки](#клавиатуры-и-колбэки)
  - [Инлайн-режим](#инлайн-режим)
  - [Управление чатом](#управление-чатом)
  - [Команды и настройки бота](#команды-и-настройки-бота)
  - [Вебхук](#вебхук)
  - [Платежи и Stars](#платежи-и-stars)
  - [Реакции](#реакции)
- [Отправка файлов](#отправка-файлов)
- [Типы данных](#типы-данных)
  - [Переименованные поля](#переименованные-поля)
  - [Основные классы](#основные-классы)
  - [Сериализация](#сериализация)
- [Обработка ошибок](#обработка-ошибок)
- [AI-утилиты](#ai-утилиты)
  - [OnlySQ](#onlysq)
  - [Deef](#deef)
  - [ChatGPT / OpenAI](#chatgpt--openai)
- [Примеры](#примеры)

---

## Установка

```bash
pip install neogram          # Windows, venv
pip3 install neogram         # macOS, Linux
```

**Требования:** Python 3.8+, `curl_cffi >= 0.14.0`, `bs4 >= 0.0.2`

---

## Быстрый старт

Минимальный рабочий бот — от установки до ответа на сообщение:

```python
import time
import sys
from neogram import Bot, Update, TelegramError

bot = Bot(token="YOUR_TOKEN")

def main():
    print("Бот запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30)
            if not updates:
                continue
            for update in updates:
                offset = update.update_id + 1
                if update.message and update.message.text:
                    bot.send_message(
                        chat_id=update.message.chat.id,
                        text=f"Вы написали: {update.message.text}"
                    )
        except TelegramError as e:
            print(f"Ошибка: {e}")
            time.sleep(2)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

---

## Класс Bot

Основной класс для работы с Telegram Bot API. Каждый вызов метода — синхронный HTTP-запрос к API.

### Инициализация

```python
from neogram import Bot

bot = Bot(token="YOUR_TOKEN")

# С увеличенным таймаутом (нужен при долгом long polling)
bot = Bot(token="YOUR_TOKEN", timeout=120)

# С TLS-фингерпринтом браузера (помогает при сетевых ограничениях)
bot = Bot(token="YOUR_TOKEN", impersonate="chrome")
```

| Параметр | Тип | По умолчанию | Описание |
|:---|:---|:---|:---|
| `token` | `str` | — | Токен бота от [@BotFather](https://t.me/BotFather) |
| `timeout` | `int` | `60` | Таймаут HTTP-запросов в секундах |
| `impersonate` | `str \| None` | `None` | TLS-фингерпринт: `"chrome"`, `"firefox"`, `"safari"` и др. |

> **Заметка.** `impersonate` — параметр `curl_cffi`. Позволяет маскировать запросы под конкретный браузер на уровне TLS. Актуально при работе через VPN или в средах с ограничениями.

---

### Сообщения

```python
# Простое текстовое сообщение
bot.send_message(chat_id=123456, text="Привет!")

# С HTML-разметкой
bot.send_message(chat_id=123456, text="<b>Жирный</b> текст", parse_mode="HTML")

# С Markdown
bot.send_message(chat_id=123456, text="*Жирный* текст", parse_mode="Markdown")

# Ответ на сообщение (цитата)
from neogram import ReplyParameters
bot.send_message(
    chat_id=123456,
    text="Отвечаю на ваше сообщение",
    reply_parameters=ReplyParameters(message_id=msg_id)
)

# Цитата конкретного фрагмента
bot.send_message(
    chat_id=123456,
    text="Именно про это и говорю",
    reply_parameters=ReplyParameters(message_id=msg_id, quote="фрагмент текста")
)

# Пересылка и копирование
bot.forward_message(chat_id=target_id, from_chat_id=source_id, message_id=msg_id)
bot.copy_message(chat_id=target_id, from_chat_id=source_id, message_id=msg_id)
```

| Метод | Обязательные параметры |
|:---|:---|
| `send_message` | `chat_id`, `text` |
| `forward_message` | `chat_id`, `from_chat_id`, `message_id` |
| `copy_message` | `chat_id`, `from_chat_id`, `message_id` |
| `copy_messages` | `chat_id`, `from_chat_id`, `message_ids` |
| `forward_messages` | `chat_id`, `from_chat_id`, `message_ids` |
| `send_chat_action` | `chat_id`, `action` |

**Значения `action` для `send_chat_action`:** `"typing"`, `"upload_photo"`, `"upload_video"`, `"upload_document"`, `"upload_voice"`, `"find_location"`, `"record_video_note"`, `"upload_video_note"`.

---

### Медиафайлы

```python
# Фото
bot.send_photo(chat_id=123456, photo="https://example.com/image.jpg")
bot.send_photo(chat_id=123456, photo="file_id_from_telegram")
with open("photo.jpg", "rb") as f:
    bot.send_photo(chat_id=123456, photo=f, caption="Подпись")

# Видео
bot.send_video(chat_id=123456, video=open("video.mp4", "rb"))

# Документ
bot.send_document(chat_id=123456, document=open("file.pdf", "rb"))

# Аудио (MP3)
bot.send_audio(chat_id=123456, audio=open("song.mp3", "rb"))

# Голосовое сообщение (OGG/OPUS)
bot.send_voice(chat_id=123456, voice=open("voice.ogg", "rb"))

# Видеосообщение-кружок
bot.send_video_note(chat_id=123456, video_note=open("circle.mp4", "rb"))

# GIF / анимация
bot.send_animation(chat_id=123456, animation=open("anim.gif", "rb"))

# Стикер
bot.send_sticker(chat_id=123456, sticker="sticker_file_id")

# Геолокация
bot.send_location(chat_id=123456, latitude=55.7558, longitude=37.6176)

# Живая геолокация (обновляется в реальном времени)
sent = bot.send_location(chat_id=123456, latitude=55.75, longitude=37.61, live_period=3600)
bot.edit_message_live_location(chat_id=123456, message_id=sent.message_id, latitude=55.76, longitude=37.62)
bot.stop_message_live_location(chat_id=123456, message_id=sent.message_id)

# Место (venue)
bot.send_venue(chat_id=123456, latitude=55.75, longitude=37.61, title="Красная площадь", address="Москва")

# Контакт
bot.send_contact(chat_id=123456, phone_number="+79001234567", first_name="Иван")

# Дайс
bot.send_dice(chat_id=123456)               # обычный кубик
bot.send_dice(chat_id=123456, emoji="🎰")   # слот-машина

# Опрос
from neogram import InputPollOption
bot.send_poll(
    chat_id=123456,
    question="Ваш любимый язык?",
    options=[InputPollOption(text="Python"), InputPollOption(text="JavaScript")],
    is_anonymous=False
)

# Викторина (quiz)
bot.send_poll(
    chat_id=123456,
    question="Сколько будет 2+2?",
    options=[InputPollOption(text="3"), InputPollOption(text="4"), InputPollOption(text="5")],
    type_val="quiz",
    correct_option_id=1,
    is_anonymous=True
)

# Альбом (до 10 файлов)
from neogram import InputMediaPhoto, InputMediaVideo
bot.send_media_group(chat_id=123456, media=[
    InputMediaPhoto(type_val="photo", media="url_or_file_id", caption="Фото 1"),
    InputMediaPhoto(type_val="photo", media="url_or_file_id_2"),
])

# Платный медиаконтент
from neogram import InputPaidMediaPhoto
bot.send_paid_media(chat_id=123456, star_count=10, media=[
    InputPaidMediaPhoto(type_val="photo", media="file_id")
])
```

| Метод | Обязательные параметры |
|:---|:---|
| `send_photo` | `chat_id`, `photo` |
| `send_video` | `chat_id`, `video` |
| `send_document` | `chat_id`, `document` |
| `send_audio` | `chat_id`, `audio` |
| `send_voice` | `chat_id`, `voice` |
| `send_video_note` | `chat_id`, `video_note` |
| `send_animation` | `chat_id`, `animation` |
| `send_sticker` | `chat_id`, `sticker` |
| `send_location` | `chat_id`, `latitude`, `longitude` |
| `send_venue` | `chat_id`, `latitude`, `longitude`, `title`, `address` |
| `send_contact` | `chat_id`, `phone_number`, `first_name` |
| `send_poll` | `chat_id`, `question`, `options` |
| `send_dice` | `chat_id` |
| `send_media_group` | `chat_id`, `media` |
| `send_paid_media` | `chat_id`, `star_count`, `media` |

---

### Редактирование и удаление

```python
# Изменить текст
bot.edit_message_text(chat_id=123456, message_id=msg_id, text="Новый текст")

# Изменить подпись под медиа
bot.edit_message_caption(chat_id=123456, message_id=msg_id, caption="Новая подпись")

# Заменить медиафайл целиком
from neogram import InputMediaPhoto
bot.edit_message_media(
    chat_id=123456,
    message_id=msg_id,
    media=InputMediaPhoto(type_val="photo", media="new_file_id")
)

# Изменить только клавиатуру
bot.edit_message_reply_markup(chat_id=123456, message_id=msg_id, reply_markup=new_kb)

# Удалить сообщение
bot.delete_message(chat_id=123456, message_id=msg_id)

# Удалить несколько сразу
bot.delete_messages(chat_id=123456, message_ids=[msg_id_1, msg_id_2, msg_id_3])

# Закрепить / открепить
bot.pin_chat_message(chat_id=123456, message_id=msg_id)
bot.unpin_chat_message(chat_id=123456, message_id=msg_id)
bot.unpin_all_chat_messages(chat_id=123456)
```

---

### Клавиатуры и колбэки

```python
from neogram import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, ForceReply
)

# Инлайн-клавиатура
kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="✅ Да", callback_data="yes"),
        InlineKeyboardButton(text="❌ Нет", callback_data="no"),
    ],
    [InlineKeyboardButton(text="🌐 Открыть сайт", url="https://example.com")],
    [InlineKeyboardButton(text="🔍 Поиск", switch_inline_query="запрос")],
])
bot.send_message(chat_id=123456, text="Выберите:", reply_markup=kb)

# Обычная клавиатура
kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📍 Моя геолокация", request_location=True)],
        [KeyboardButton(text="📱 Мой контакт", request_contact=True)],
        [KeyboardButton(text="ℹ️ Помощь")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие..."
)
bot.send_message(chat_id=123456, text="Меню:", reply_markup=kb)

# Убрать клавиатуру
bot.send_message(chat_id=123456, text="Клавиатура убрана", reply_markup=ReplyKeyboardRemove())

# Принудительный ответ
bot.send_message(chat_id=123456, text="Введите имя:", reply_markup=ForceReply())

# Ответ на нажатие кнопки (обязательно в обработчике callback_query)
bot.answer_callback_query(callback_query_id=cb.id, text="Принято!")
bot.answer_callback_query(callback_query_id=cb.id, text="Внимание!", show_alert=True)
```

---

### Инлайн-режим

```python
from neogram import (
    InlineQueryResultArticle, InlineQueryResultPhoto,
    InputTextMessageContent
)
import uuid

def handle_inline(update):
    query = update.inline_query
    results = [
        InlineQueryResultArticle(
            type_val="article",
            id=str(uuid.uuid4()),
            title="Заголовок результата",
            description="Описание под заголовком",
            input_message_content=InputTextMessageContent(
                message_text="Текст, который будет отправлен"
            )
        )
    ]
    bot.answer_inline_query(
        inline_query_id=query.id,
        results=results,
        cache_time=1
    )
```

Доступные типы результатов: `InlineQueryResultArticle`, `InlineQueryResultPhoto`, `InlineQueryResultGif`, `InlineQueryResultVideo`, `InlineQueryResultAudio`, `InlineQueryResultDocument`, `InlineQueryResultLocation`, `InlineQueryResultContact`, `InlineQueryResultGame` и кэшированные варианты (`InlineQueryResultCached*`).

---

### Управление чатом

```python
# Информация
me = bot.get_me()
chat = bot.get_chat(chat_id=123456)
member = bot.get_chat_member(chat_id=123456, user_id=789)
admins = bot.get_chat_administrators(chat_id=123456)
count = bot.get_chat_member_count(chat_id=123456)

# Ограничение / бан
from neogram import ChatPermissions
bot.restrict_chat_member(
    chat_id=123456,
    user_id=789,
    permissions=ChatPermissions(can_send_messages=False),
    until_date=int(time.time()) + 3600   # на 1 час
)
bot.ban_chat_member(chat_id=123456, user_id=789)
bot.unban_chat_member(chat_id=123456, user_id=789)

# Права администратора
bot.promote_chat_member(
    chat_id=123456,
    user_id=789,
    can_delete_messages=True,
    can_restrict_members=True
)
bot.set_chat_administrator_custom_title(chat_id=123456, user_id=789, custom_title="Модератор")

# Пригласительные ссылки
link = bot.create_chat_invite_link(chat_id=123456, name="Разовая", member_limit=1)
print(link.invite_link)  # "https://t.me/+..."

bot.export_chat_invite_link(chat_id=123456)      # обновить основную ссылку
bot.revoke_chat_invite_link(chat_id=123456, invite_link="https://t.me/+...")

# Заявки на вступление
bot.approve_chat_join_request(chat_id=123456, user_id=789)
bot.decline_chat_join_request(chat_id=123456, user_id=789)

# Настройки чата
bot.set_chat_title(chat_id=123456, title="Новое название")
bot.set_chat_description(chat_id=123456, description="Описание чата")
bot.set_chat_permissions(chat_id=123456, permissions=ChatPermissions(can_send_messages=True))
```

---

### Команды и настройки бота

```python
from neogram import BotCommand, BotCommandScopeAllPrivateChats

# Установить команды (глобально)
bot.set_my_commands(commands=[
    BotCommand(command="start",  description="Запустить бота"),
    BotCommand(command="help",   description="Помощь"),
    BotCommand(command="cancel", description="Отменить действие"),
])

# Установить команды только для личных чатов
bot.set_my_commands(
    commands=[BotCommand(command="start", description="Старт")],
    scope=BotCommandScopeAllPrivateChats()
)

# Получить / удалить команды
commands = bot.get_my_commands()
bot.delete_my_commands()

# Имя и описание бота
bot.set_my_name(name="Мой Бот")
bot.set_my_description(description="Что умеет этот бот")
bot.set_my_short_description(short_description="Краткое описание")
```

---

### Вебхук

```python
# Установить вебхук
bot.set_webhook(
    url="https://yourdomain.com/webhook",
    allowed_updates=["message", "callback_query"],
    secret_token="your_secret_token"
)

# Статус вебхука
info = bot.get_webhook_info()
print(info.url)
print(info.pending_update_count)

# Удалить вебхук (вернуться к long polling)
bot.delete_webhook(drop_pending_updates=True)
```

---

### Платежи и Stars

```python
from neogram import LabeledPrice

# Отправить счёт (Telegram Stars)
bot.send_invoice(
    chat_id=123456,
    title="Премиум подписка",
    description="Доступ на 30 дней",
    payload="premium_30d",
    provider_token="",    # пустой для Telegram Stars
    currency="XTR",
    prices=[LabeledPrice(label="Подписка", amount=50)]
)

# Подтвердить предоплату (обязательно в обработчике pre_checkout_query)
bot.answer_pre_checkout_query(pre_checkout_query_id=query.id, ok=True)

# Или отклонить с причиной
bot.answer_pre_checkout_query(
    pre_checkout_query_id=query.id,
    ok=False,
    error_message="Товар временно недоступен"
)

# Баланс и транзакции Stars
balance = bot.get_my_star_balance()
transactions = bot.get_star_transactions(limit=10)

# Возврат Stars
bot.refund_star_payment(user_id=789, telegram_payment_charge_id="charge_id")
```

---

### Реакции

```python
from neogram import ReactionTypeEmoji, ReactionTypeCustomEmoji

# Поставить эмодзи-реакцию
reaction = ReactionTypeEmoji(type_val="emoji", emoji="🔥")
bot.set_message_reaction(
    chat_id=123456,
    message_id=msg_id,
    reaction=[reaction]
)

# Убрать реакцию (передать пустой список)
bot.set_message_reaction(chat_id=123456, message_id=msg_id, reaction=[])
```

---

## Отправка файлов

Все медиа-методы принимают файл в одном из форматов:

```python
# 1. file_id — файл уже загружен в Telegram, самый быстрый способ
bot.send_photo(chat_id=123456, photo="AgACAgIAAxkBAAI...")

# 2. URL — Telegram скачает файл сам
bot.send_photo(chat_id=123456, photo="https://example.com/photo.jpg")

# 3. Открытый файл с диска
with open("photo.jpg", "rb") as f:
    bot.send_photo(chat_id=123456, photo=f)

# 4. BytesIO — файл из памяти (нужно задать имя через .name)
import io
buf = io.BytesIO(b"<содержимое файла>")
buf.name = "report.pdf"
bot.send_document(chat_id=123456, document=buf)

# 5. bytes — просто байты
bot.send_document(chat_id=123456, document=b"<содержимое файла>")
```

**Получение прямой ссылки на загруженный файл:**

```python
file = bot.get_file(file_id=msg.document.file_id)
url = f"https://api.telegram.org/file/bot{TOKEN}/{file.file_path}"
```

---

## Типы данных

Все объекты Telegram — типизированные `@dataclass`-классы, наследующие `TelegramObject`. Они автоматически создаются из JSON-ответов API и умеют конвертировать себя обратно.

### Переименованные поля

Некоторые поля Telegram API совпадают с зарезервированными словами Python и переименованы:

| Telegram API | neogram | Где встречается |
|:---|:---|:---|
| `type` | `type_val` | `Chat`, `MessageEntity`, `Sticker`, `Poll`, `InlineQueryResult*`, `ReactionType*` и др. |
| `from` | `from_user` | `Message`, `CallbackQuery`, `InlineQuery`, `ChosenInlineResult` и др. |
| `filter` | `filter_val` | Редкие поля |

> При вызове `.to_dict()` или отправке через методы `Bot` поля автоматически конвертируются обратно в оригинальные имена Telegram API — `type_val` → `type`, `from_user` → `from`.

```python
# Правильно — именно так называются поля в neogram:
msg.from_user.id           # ✓
msg.chat.type_val          # ✓  →  "private" | "group" | "supergroup" | "channel"
sticker.type_val           # ✓  →  "regular" | "mask" | "custom_emoji"

# Так в Telegram API, но в Python это SyntaxError / конфликт:
# msg.from.id              # ✗
# msg.chat.type            # ✗
```

---

### Основные классы

#### Обновления

| Класс | Ключевые поля |
|:---|:---|
| `Update` | `update_id`, `message`, `edited_message`, `callback_query`, `inline_query`, `chosen_inline_result`, `poll_answer`, `chat_join_request`, `my_chat_member`, `chat_member` |
| `Message` | `message_id`, `date`, `chat`, `from_user`, `text`, `photo`, `document`, `sticker`, `video`, `voice`, `reply_to_message`, `forward_origin`, `successful_payment` |
| `CallbackQuery` | `id`, `from_user`, `message`, `data`, `inline_message_id` |
| `InlineQuery` | `id`, `from_user`, `query`, `offset` |

#### Пользователи и чаты

| Класс | Ключевые поля |
|:---|:---|
| `User` | `id`, `is_bot`, `first_name`, `last_name`, `username`, `language_code`, `is_premium` |
| `Chat` | `id`, `type_val`, `title`, `username`, `first_name`, `last_name` |
| `ChatFullInfo` | Все поля `Chat` + `bio`, `description`, `permissions`, `invite_link`, `pinned_message`, `slow_mode_delay` и др. |
| `ChatMemberOwner` | `status`, `user`, `is_anonymous`, `custom_title` |
| `ChatMemberAdministrator` | `status`, `user`, `can_delete_messages`, `can_restrict_members` и др. |
| `ChatMemberRestricted` | `status`, `user`, `until_date`, `can_send_messages` и др. |
| `ChatPermissions` | `can_send_messages`, `can_send_polls`, `can_send_other_messages`, `can_add_web_page_previews`, `can_change_info`, `can_invite_users`, `can_pin_messages` |

#### Клавиатуры

| Класс | Описание |
|:---|:---|
| `InlineKeyboardMarkup` | `inline_keyboard: List[List[InlineKeyboardButton]]` |
| `InlineKeyboardButton` | `text`, `callback_data`, `url`, `switch_inline_query`, `switch_inline_query_current_chat` |
| `ReplyKeyboardMarkup` | `keyboard: List[List[KeyboardButton]]`, `resize_keyboard`, `one_time_keyboard`, `input_field_placeholder` |
| `KeyboardButton` | `text`, `request_contact`, `request_location`, `request_users`, `request_chat` |
| `ReplyKeyboardRemove` | `remove_keyboard=True` |
| `ForceReply` | `force_reply=True`, `input_field_placeholder` |

#### Медиа

| Класс | Ключевые поля |
|:---|:---|
| `PhotoSize` | `file_id`, `file_unique_id`, `width`, `height`, `file_size` |
| `Document` | `file_id`, `file_unique_id`, `file_name`, `mime_type`, `file_size` |
| `Audio` | `file_id`, `duration`, `performer`, `title`, `mime_type` |
| `Video` | `file_id`, `width`, `height`, `duration`, `thumbnail` |
| `Voice` | `file_id`, `duration`, `mime_type` |
| `VideoNote` | `file_id`, `length`, `duration` |
| `Animation` | `file_id`, `width`, `height`, `duration`, `file_name` |
| `Sticker` | `file_id`, `type_val`, `emoji`, `set_name`, `is_animated`, `is_video` |
| `File` | `file_id`, `file_unique_id`, `file_size`, `file_path` |

#### Вспомогательные

| Класс | Описание |
|:---|:---|
| `ReplyParameters` | `message_id`, `chat_id`, `quote`, `quote_parse_mode` |
| `MessageEntity` | `type_val`, `offset`, `length`, `url`, `user` — разметка в тексте |
| `MessageId` | `message_id` — результат `copy_message` |
| `BotCommand` | `command`, `description` |
| `LabeledPrice` | `label`, `amount` |
| `InputPollOption` | `text` |
| `InputMediaPhoto` | `type_val="photo"`, `media`, `caption` |
| `InputMediaVideo` | `type_val="video"`, `media`, `caption`, `duration` |
| `ReactionTypeEmoji` | `type_val="emoji"`, `emoji` |
| `ReactionTypeCustomEmoji` | `type_val="custom_emoji"`, `custom_emoji_id` |
| `LinkPreviewOptions` | `is_disabled`, `url`, `prefer_large_media`, `prefer_small_media` |

---

### Сериализация

Каждый объект умеет конвертироваться из `dict` и обратно:

```python
from neogram import User

# dict → объект
user = User.from_dict({
    "id": 123456,
    "is_bot": False,
    "first_name": "Иван",
    "username": "ivan"
})
print(user.first_name)   # "Иван"
print(user.username)     # "ivan"

# объект → dict (поля автоматически переименовываются обратно в API-названия)
d = user.to_dict()
# {"id": 123456, "is_bot": False, "first_name": "Иван", "username": "ivan"}

# Список dict-ов → список объектов
users = User.from_dict([{"id": 1, "is_bot": False, "first_name": "A"}, ...])
# → List[User]
```

---

## Обработка ошибок

Все ошибки API выбрасывают исключение `TelegramError`:

```python
from neogram import Bot, TelegramError

bot = Bot(token="YOUR_TOKEN")

try:
    bot.send_message(chat_id=0, text="тест")
except TelegramError as e:
    print(e.method)       # "sendMessage"
    print(e.error_code)   # 400
    print(e.description)  # "Bad Request: chat not found"
    print(e.retry_after)  # None или количество секунд при rate limit (429)
    print(str(e))         # "[sendMessage] 400: Bad Request: chat not found (Неверные параметры запроса)"
```

| Код | Причина | Что делать |
|:---|:---|:---|
| `400` | Bad Request | Проверьте параметры запроса |
| `401` | Unauthorized | Токен неверный или отозван |
| `403` | Forbidden | Бот заблокирован пользователем или нет прав в чате |
| `404` | Not Found | Несуществующий метод API |
| `409` | Conflict | Два экземпляра бота работают одновременно |
| `429` | Too Many Requests | Превышен rate limit — ждите `e.retry_after` секунд |
| `500` | Internal Server Error | Ошибка на стороне Telegram, повторите позже |

**Рекомендуемый шаблон main-цикла с правильной обработкой ошибок:**

```python
import time
import sys
from neogram import Bot, TelegramError

bot = Bot(token="YOUR_TOKEN")
offset = 0

while True:
    try:
        updates = bot.get_updates(offset=offset, timeout=30,
                                  allowed_updates=["message", "callback_query"])
        if not updates:
            continue
        for update in updates:
            offset = update.update_id + 1
            # ... обработка обновлений ...

    except TelegramError as e:
        if e.error_code == 429:
            # Rate limit — ждём столько, сколько Telegram просит
            time.sleep(e.retry_after or 5)
        elif e.error_code in (401, 409):
            # Критические ошибки — завершаем
            print(f"Критическая ошибка: {e}")
            sys.exit(1)
        else:
            print(f"API ошибка: {e}")
            time.sleep(2)

    except KeyboardInterrupt:
        print("Остановлено")
        sys.exit(0)

    except Exception as e:
        print(f"Необработанное исключение: {e}")
        time.sleep(5)
```

---

## AI-утилиты

`neogram` включает три класса для работы с AI-сервисами. Они доступны напрямую из пакета.

---

### OnlySQ

Клиент для сервиса [OnlySQ](https://my.onlysq.ru/) — генерация текста и изображений через единый API.

```python
from neogram import OnlySQ

sq = OnlySQ(key="YOUR_API_KEY")
```

#### `get_models()` — список моделей с фильтрацией

```python
# Все текстовые модели в рабочем статусе
models = sq.get_models(modality="text", status="work")
# → ["gpt-5.2-chat", "claude-opus-4", ...]

# Модели с поддержкой инструментов, вернуть читаемые имена
names = sq.get_models(modality="text", can_tools=True, return_names=True)

# Дешевле определённой стоимости
cheap = sq.get_models(max_cost=0.005)
```

| Параметр | Тип | Описание |
|:---|:---|:---|
| `modality` | `str \| list \| None` | `"text"`, `"image"` или список |
| `can_tools` | `bool \| None` | Поддержка вызова инструментов |
| `can_think` | `bool \| None` | Режим «размышления» (thinking) |
| `can_stream` | `bool \| None` | Стриминг |
| `status` | `str \| None` | `"work"`, `"beta"` и др. |
| `max_cost` | `float \| None` | Максимальная стоимость запроса |
| `return_names` | `bool` | `False` (по умолч.) — ключи моделей; `True` — читаемые имена |

#### `generate_answer()` — генерация текста

```python
answer = sq.generate_answer(
    model="gpt-5.2-chat",
    messages=[
        {"role": "system", "content": "Ты краткий помощник."},
        {"role": "user",   "content": "Что такое Python?"}
    ]
)
print(answer)  # "Python — интерпретируемый язык программирования..."
```

| Параметр | Тип | Описание |
|:---|:---|:---|
| `model` | `str` | Ключ модели |
| `messages` | `list[dict]` | История в формате OpenAI: `[{"role": "...", "content": "..."}]` |

#### `generate_image()` — генерация изображения

```python
ok = sq.generate_image(
    model="flux",
    prompt="golden retriever in space, digital art",
    ratio="16:9",
    filename="result.png"
)
if ok:
    print("Сохранено в result.png")
```

| Параметр | Тип | По умолчанию | Описание |
|:---|:---|:---|:---|
| `model` | `str` | `"flux"` | Модель генерации |
| `prompt` | `str` | — | Описание (лучше на английском) |
| `ratio` | `str` | `"16:9"` | Соотношение: `"1:1"`, `"4:3"`, `"16:9"` и др. |
| `filename` | `str` | `"image.png"` | Путь для сохранения |

Возвращает `True` при успехе, `False` при ошибке.

---

### Deef

Набор утилит: перевод, сокращение ссылок, запросы к Perplexity AI, base64, фоновые задачи.

```python
from neogram import Deef

deef = Deef()
```

#### `translate()` — перевод через Google Translate

```python
ru_text = deef.translate("Hello, world!", lang="ru")
# → "Привет, мир!"

en_text = deef.translate("Привет", lang="en")
# → "Hi"
```

| Параметр | Тип | Описание |
|:---|:---|:---|
| `text` | `str` | Исходный текст |
| `lang` | `str` | Код языка цели: `"ru"`, `"en"`, `"de"`, `"fr"`, `"zh-CN"`, `"ja"` и др. |

Язык источника определяется автоматически.

---

#### `short_url()` — сокращение ссылок через clck.ru

```python
short = deef.short_url("https://very-long-url.com/some/path?query=value")
# → "https://clck.ru/AbCdE"
```

---

#### `perplexity_ask()` — запросы к Perplexity AI

Неофициальный клиент, не требует API-ключа. Список доступных моделей загружается динамически из конфига Perplexity.

```python
result = deef.perplexity_ask(model="turbo", query="Кто написал «Войну и мир»?")

print(result["text"])
# "«Войну и мир» написал Лев Николаевич Толстой..."

for url in result["urls"]:
    print(url)
# "https://ru.wikipedia.org/wiki/..."
```

**Формат ответа:**

```python
{
    "text": "Ответ модели...",   # str
    "urls": [                    # List[str] — источники
        "https://source1.com",
        "https://source2.com",
    ]
}
```

При любой ошибке возвращается `{"text": "Error", "urls": []}` — исключение не выбрасывается.

| Параметр | Тип | Описание |
|:---|:---|:---|
| `model` | `str` | `"turbo"`, `"auto"`, `"o3pro"`, `"pplx_pro_upgraded"` и др. Если модель не найдена — используется дефолтная |
| `query` | `str` | Текст запроса |

---

#### `encode_base64()` — кодирование файла

```python
b64 = deef.encode_base64("photo.jpg")
# → "iVBORw0KGgoAAAANSUhEUgAA..."

# Если файл не найден — вернёт None (не выбросит исключение)
```

---

#### `run_in_bg()` — запуск в фоновом потоке

Запускает функцию в daemon-потоке и немедленно возвращает управление. Удобно для долгих операций внутри обработчиков обновлений.

```python
def send_image(chat_id, prompt):
    # Долгая операция — не блокирует polling
    ok = sq.generate_image(model="flux", prompt=prompt, filename="/tmp/img.png")
    if ok:
        with open("/tmp/img.png", "rb") as f:
            bot.send_photo(chat_id=chat_id, photo=f)

# Запускаем не блокируя основной цикл
thread = deef.run_in_bg(send_image, chat_id, "sunset over mountains")
```

| Параметр | Описание |
|:---|:---|
| `func` | Функция для запуска |
| `*args` | Позиционные аргументы функции |
| `**kwargs` | Именованные аргументы функции |

Возвращает `threading.Thread`.

---

### ChatGPT / OpenAI

Обёртка для любого OpenAI-совместимого API. `OpenAI` — псевдоним того же класса.

```python
from neogram import ChatGPT   # или OpenAI — одно и то же

client = ChatGPT(
    url="https://api.openai.com/v1",
    headers={"Authorization": "Bearer YOUR_KEY"},
    impersonate="chrome"   # опционально
)
```

| Параметр | Тип | Описание |
|:---|:---|:---|
| `url` | `str` | Базовый URL API (без `/chat/completions`) |
| `headers` | `dict` | Заголовки: авторизация и др. |
| `impersonate` | `str \| None` | TLS-фингерпринт |

#### Методы

**`generate_chat_completion()`**

```python
resp = client.generate_chat_completion(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Напиши хайку про Python"}],
    temperature=0.9,
    max_tokens=200
)
print(resp["choices"][0]["message"]["content"])
```

**`generate_image()`**

```python
result = client.generate_image(prompt="горный закат, акварель", n=1, size="1024x1024")
print(result["data"][0]["url"])
```

**`generate_embedding()`**

```python
emb = client.generate_embedding(model="text-embedding-3-small", input_data="Hello")
vector = emb["data"][0]["embedding"]
```

**`generate_transcription()`** — транскрипция аудио (Whisper)

```python
with open("audio.mp3", "rb") as f:
    result = client.generate_transcription(file=f, model="whisper-1", language="ru")
print(result["text"])
```

**`generate_translation()`** — перевод аудио в текст

```python
with open("audio.mp3", "rb") as f:
    result = client.generate_translation(file=f, model="whisper-1")
```

**`get_models()`**

```python
models = client.get_models()
for m in models["data"]:
    print(m["id"])
```

---

## Примеры

### Эхо-бот с Reply и Inline клавиатурами

```python
import time
import sys
from neogram import (
    Bot, Update, TelegramError,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyParameters
)

TOKEN = "YOUR_TOKEN"
bot = Bot(token=TOKEN)

def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📸 Фото"), KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Напишите что-нибудь..."
    )

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text

    if text == "/start":
        bot.send_message(
            chat_id=chat_id,
            text=f"Привет, {msg.from_user.first_name}! Я бот на neogram 🚀",
            reply_markup=main_keyboard()
        )
    elif text == "📸 Фото":
        bot.send_chat_action(chat_id=chat_id, action="upload_photo")
        bot.send_photo(
            chat_id=chat_id,
            photo="https://www.python.org/static/community_logos/python-logo-master-v3-TM.png",
            caption="Логотип Python 🐍",
            reply_parameters=ReplyParameters(message_id=msg.message_id)
        )
    elif text == "❓ Помощь":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 Telegram Bot API", url="https://core.telegram.org/bots/api")],
            [InlineKeyboardButton(text="👨‍💻 Автор", callback_data="show_author")],
        ])
        bot.send_message(chat_id=chat_id, text="Чем могу помочь?", reply_markup=kb)
    else:
        bot.send_message(
            chat_id=chat_id,
            text=f"Вы написали: <code>{text}</code>",
            parse_mode="HTML",
            reply_parameters=ReplyParameters(message_id=msg.message_id)
        )

def handle_callback(update: Update):
    cb = update.callback_query
    if cb.data == "show_author":
        bot.answer_callback_query(cb.id, text="neogram by SiriLV", show_alert=True)

def main():
    print("Бот запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30,
                                      allowed_updates=["message", "callback_query"])
            if not updates:
                continue
            for u in updates:
                offset = u.update_id + 1
                if u.message and u.message.text:
                    handle_message(u)
                elif u.callback_query:
                    handle_callback(u)
        except TelegramError as e:
            print(f"Ошибка: {e}")
            time.sleep(2)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

---

### Инлайн-режим и опросы

```python
import time
import sys
import uuid
from neogram import (
    Bot, Update, TelegramError,
    InlineQueryResultArticle, InputTextMessageContent,
    InputPollOption
)

TOKEN = "YOUR_TOKEN"
bot = Bot(token=TOKEN)

def handle_inline(update: Update):
    q = update.inline_query
    text = q.query.strip() or "Пусто"
    bot.answer_inline_query(
        inline_query_id=q.id,
        results=[
            InlineQueryResultArticle(
                type_val="article",
                id=str(uuid.uuid4()),
                title="📢 Кричалка",
                description=f"Отправить: {text.upper()}",
                input_message_content=InputTextMessageContent(
                    message_text=f"Я КРИЧУ: {text.upper()}!!!"
                )
            ),
            InlineQueryResultArticle(
                type_val="article",
                id=str(uuid.uuid4()),
                title="🔠 Жирный текст",
                input_message_content=InputTextMessageContent(
                    message_text=f"<b>{text}</b>",
                    parse_mode="HTML"
                )
            ),
        ],
        cache_time=1
    )

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    if msg.text == "/poll":
        bot.send_poll(
            chat_id=chat_id,
            question="Какой язык лучший?",
            options=[
                InputPollOption(text="Python 🐍"),
                InputPollOption(text="JavaScript ☕"),
                InputPollOption(text="C++ ⚙️"),
            ],
            type_val="quiz",
            correct_option_id=0,
            is_anonymous=False
        )
    elif msg.text == "/dice":
        bot.send_dice(chat_id=chat_id, emoji="🎰")

def main():
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30,
                                      allowed_updates=["message", "inline_query"])
            if not updates:
                continue
            for u in updates:
                offset = u.update_id + 1
                if u.inline_query:
                    handle_inline(u)
                elif u.message and u.message.text:
                    handle_message(u)
        except TelegramError as e:
            print(f"Ошибка: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

---

### Модерация группы

```python
import time
import sys
from neogram import Bot, Update, TelegramError, ChatPermissions, ReactionTypeEmoji

TOKEN = "YOUR_TOKEN"
bot = Bot(token=TOKEN)

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text

    if text == "/mute" and msg.reply_to_message:
        target_id = msg.reply_to_message.from_user.id
        bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=int(time.time()) + 60
        )
        bot.send_message(chat_id=chat_id, text="🔇 Мут на 1 минуту")

    elif text == "/unmute" and msg.reply_to_message:
        target_id = msg.reply_to_message.from_user.id
        bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_id,
            permissions=ChatPermissions(can_send_messages=True, can_send_polls=True)
        )
        bot.send_message(chat_id=chat_id, text="🔊 Мут снят")

    elif text == "/ban" and msg.reply_to_message:
        target_id = msg.reply_to_message.from_user.id
        bot.ban_chat_member(chat_id=chat_id, user_id=target_id)
        bot.send_message(chat_id=chat_id, text="🚫 Пользователь забанен")

    elif text == "/fire":
        bot.set_message_reaction(
            chat_id=chat_id,
            message_id=msg.message_id,
            reaction=[ReactionTypeEmoji(type_val="emoji", emoji="🔥")]
        )

    elif text == "/pin" and msg.reply_to_message:
        bot.pin_chat_message(chat_id=chat_id, message_id=msg.reply_to_message.message_id)

def main():
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30)
            if not updates:
                continue
            for u in updates:
                offset = u.update_id + 1
                if u.message and u.message.text:
                    handle_message(u)
        except TelegramError as e:
            print(f"Ошибка: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

---

### Платежи (Telegram Stars)

```python
import time
import sys
from neogram import Bot, Update, TelegramError, LabeledPrice

TOKEN = "YOUR_TOKEN"
bot = Bot(token=TOKEN)

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id

    if msg.successful_payment:
        pay = msg.successful_payment
        bot.send_message(chat_id=chat_id,
                         text=f"✅ Получено {pay.total_amount} ⭐ Спасибо!")
        return

    if msg.text == "/buy":
        bot.send_invoice(
            chat_id=chat_id,
            title="Премиум доступ",
            description="Разблокирует все функции на 30 дней",
            payload="premium_30d",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="Подписка на 30 дней", amount=50)]
        )

def handle_pre_checkout(update: Update):
    # Нужно ответить в течение 10 секунд
    bot.answer_pre_checkout_query(
        pre_checkout_query_id=update.pre_checkout_query.id,
        ok=True
    )

def main():
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30,
                                      allowed_updates=["message", "pre_checkout_query"])
            if not updates:
                continue
            for u in updates:
                offset = u.update_id + 1
                if u.pre_checkout_query:
                    handle_pre_checkout(u)
                elif u.message:
                    handle_message(u)
        except TelegramError as e:
            print(f"Ошибка: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

---

### AI-бот с историей диалога (OnlySQ)

```python
import time
import sys
from neogram import Bot, Update, TelegramError, OnlySQ

TOKEN = "YOUR_TOKEN"
ONLYSQ_KEY = "YOUR_ONLYSQ_KEY"

bot = Bot(token=TOKEN)
ai = OnlySQ(key=ONLYSQ_KEY)

SYSTEM = "Ты дружелюбный ассистент. Отвечай по-русски, кратко и по делу."
histories: dict = {}

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    user_id = msg.from_user.id
    text = msg.text

    if text == "/start":
        histories[user_id] = []
        bot.send_message(chat_id=chat_id, text="🤖 Привет! Задай любой вопрос.")
        return

    if text == "/clear":
        histories[user_id] = []
        bot.send_message(chat_id=chat_id, text="🧹 История очищена")
        return

    bot.send_chat_action(chat_id=chat_id, action="typing")

    history = histories.setdefault(user_id, [])
    history.append({"role": "user", "content": text})

    answer = ai.generate_answer(
        model="gpt-5.2-chat",
        messages=[{"role": "system", "content": SYSTEM}] + history
    )

    history.append({"role": "assistant", "content": answer})
    if len(history) > 20:
        histories[user_id] = history[-20:]

    bot.send_message(chat_id=chat_id, text=answer, parse_mode="Markdown")

def main():
    print("AI-бот запущен...")
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30,
                                      allowed_updates=["message"])
            if not updates:
                continue
            for u in updates:
                offset = u.update_id + 1
                if u.message and u.message.text:
                    handle_message(u)
        except TelegramError as e:
            print(f"Ошибка: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

---

### Perplexity-бот с источниками

```python
import time
import sys
from neogram import Bot, Update, TelegramError, Deef

TOKEN = "YOUR_TOKEN"
bot = Bot(token=TOKEN)
deef = Deef()

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text

    if text == "/start":
        bot.send_message(chat_id=chat_id, text="🔍 Задайте любой вопрос — отвечу с источниками!")
        return

    if not text or text.startswith("/"):
        return

    bot.send_chat_action(chat_id=chat_id, action="typing")
    result = deef.perplexity_ask("turbo", text)
    answer = result["text"]
    urls = result["urls"]

    if urls:
        sources = "\n".join(f"{i}. {u}" for i, u in enumerate(urls[:5], 1))
        answer += f"\n\n📎 <b>Источники:</b>\n{sources}"

    if len(answer) > 4096:
        answer = answer[:4093] + "..."

    bot.send_message(chat_id=chat_id, text=answer, parse_mode="HTML")

def main():
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30,
                                      allowed_updates=["message"])
            if not updates:
                continue
            for u in updates:
                offset = u.update_id + 1
                if u.message and u.message.text:
                    handle_message(u)
        except TelegramError as e:
            print(f"Ошибка: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

---

### Генерация изображений в фоне

```python
import time
import sys
import tempfile
import os
from neogram import Bot, Update, TelegramError, OnlySQ, Deef, ReplyParameters

TOKEN = "YOUR_TOKEN"
bot = Bot(token=TOKEN)
sq = OnlySQ(key="YOUR_ONLYSQ_KEY")
deef = Deef()

def generate_and_send(chat_id: int, message_id: int, prompt: str):
    """Запускается в фоновом потоке через deef.run_in_bg()"""
    bot.send_chat_action(chat_id=chat_id, action="upload_photo")
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        path = tmp.name
    try:
        ok = sq.generate_image(model="flux", prompt=prompt, ratio="16:9", filename=path)
        if ok:
            with open(path, "rb") as f:
                bot.send_photo(
                    chat_id=chat_id,
                    photo=f,
                    caption=f"`{prompt}`",
                    parse_mode="Markdown",
                    reply_parameters=ReplyParameters(message_id=message_id)
                )
        else:
            bot.send_message(chat_id=chat_id, text="❌ Не удалось сгенерировать изображение")
    finally:
        if os.path.exists(path):
            os.remove(path)

def handle_message(update: Update):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text

    # Команда "арт <описание>"
    if text and text.lower().startswith("арт "):
        raw_prompt = text[4:].strip()
        prompt = deef.translate(raw_prompt, lang="en")   # переводим для лучшего результата
        deef.run_in_bg(generate_and_send, chat_id, msg.message_id, prompt)

def main():
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30,
                                      allowed_updates=["message"])
            if not updates:
                continue
            for u in updates:
                offset = u.update_id + 1
                if u.message and u.message.text:
                    handle_message(u)
        except TelegramError as e:
            print(f"Ошибка: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

---

### Заявки на вступление в группу

```python
import time
import sys
from neogram import Bot, Update, TelegramError

TOKEN = "YOUR_TOKEN"
bot = Bot(token=TOKEN)

def handle_join_request(update: Update):
    req = update.chat_join_request
    user = req.from_user

    bot.approve_chat_join_request(chat_id=req.chat.id, user_id=user.id)

    try:
        bot.send_message(
            chat_id=user.id,
            text=f"✅ {user.first_name}, ваша заявка одобрена! Добро пожаловать."
        )
    except TelegramError:
        pass  # пользователь не начал диалог с ботом

def main():
    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30,
                                      allowed_updates=["chat_join_request"])
            if not updates:
                continue
            for u in updates:
                offset = u.update_id + 1
                if u.chat_join_request:
                    handle_join_request(u)
        except TelegramError as e:
            print(f"Ошибка: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
```

---

## Лицензия

MIT © 2026 SiriLV — [siriteamrs@gmail.com](mailto:siriteamrs@gmail.com)
