# neogram

**neogram** — это Python-модуль, объединяющий в себе клиент для Telegram Bot API (версия 10.0) и набор клиентов для различных AI-сервисов. Модуль построен поверх `curl_cffi` для обхода TLS-фингерпринтинга и обеспечивает полную типизацию через `dataclass`.

---

## Установка

```bash
pip install neogram
```

### Зависимости

- `curl_cffi` — HTTP-клиент с поддержкой имперсонации браузерных TLS-фингерпринтов
- `beautifulsoup4` — парсинг HTML (для перевода Google Translate в классе `Deef`)

---

## Структура модуля

```
neogram/
├── __init__.py      # Публичный API: реэкспорт всех классов
├── fgram.py         # Telegram Bot API клиент (Bot, AsyncBot, типы Telegram)
└── ii.py            # AI-клиенты (OnlySQ, Deef, Qwen, ChatGPT/OpenAI)
```

---

## Содержание

- [Telegram Bot API (fgram)](#telegram-bot-api-fgram)
  - [Bot — синхронный клиент](#bot--синхронный-клиент)
  - [AsyncBot — асинхронный клиент](#asyncbot--асинхронный-клиент)
  - [Система обработчиков (handlers)](#система-обработчиков-handlers)
  - [Фильтрация обработчиков](#фильтрация-обработчиков)
  - [Polling и Webhook](#polling-и-webhook)
  - [Исключения](#исключения)
  - [TelegramObject — базовый класс типов](#telegramobject--базовый-класс-типов)
  - [InputFile — загрузка файлов](#inputfile--загрузка-файлов)
  - [API-методы Bot](#api-методы-bot)
  - [Типы Telegram API](#типы-telegram-api)
- [AI-клиенты (ii)](#ai-клиенты-ii)
  - [OnlySQ](#onlysq)
  - [Deef](#deef)
  - [Qwen](#qwen)
  - [ChatGPT / OpenAI](#chatgpt--openai)

---

## Telegram Bot API (fgram)

Модуль `fgram.py` предоставляет полную реализацию Telegram Bot API версии **10.0**, включая синхронный (`Bot`) и асинхронный (`AsyncBot`) клиенты, автоматическую сериализацию/десериализацию всех типов Telegram и декораторную систему обработчиков обновлений.

### Bot — синхронный клиент

```python
from neogram import Bot

bot = Bot(
    token="123456:ABC-DEF...",
    api_url="https://api.telegram.org", # по умолчанию
    timeout=60,  # HTTP-таймаут (секунды)
    impersonate="chrome", # TLS-фингерпринт curl_cffi
    parse_mode=None, # "HTML" или "MarkdownV2"
    proxies=None, # {"http": "...", "https": "..."}
    max_retries=3, # число автоповторов при ошибках транспорта
    retry_on_flood=True, # автоповтор при 429 Flood
)
```

**Параметры конструктора:**

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `token` | `str` | — | Токен бота от @BotFather (обязательный) |
| `api_url` | `str` | `https://api.telegram.org` | Базовый URL Telegram API |
| `timeout` | `int` | `60` | HTTP-таймаут запроса в секундах |
| `impersonate` | `str` | `"chrome"` | TLS-фингерпринт для `curl_cffi` (например `"chrome"`, `"safari"`) |
| `parse_mode` | `Optional[str]` | `None` | Режим форматирования по умолчанию (`"HTML"`, `"MarkdownV2"`) |
| `proxies` | `Optional[dict]` | `None` | Словарь прокси-настроек для `curl_cffi` |
| `max_retries` | `int` | `3` | Максимальное число автоматических повторов при транспортных ошибках и ошибках сервера |
| `retry_on_flood` | `bool` | `True` | Автоматический повтор при ошибке 429 (Flood) |

**Особенности транспорта:**
- Использует `curl_cffi.requests.Session` с имперсонацией браузерного TLS-фингерпринта
- Автоматический retry при транспортных ошибках (с exponential backoff до 30 сек)
- Автоматический retry при 429 Flood (ожидание `retry_after + 1` сек)
- Автоматический retry при серверных ошибках 5xx (с exponential backoff)

### AsyncBot — асинхронный клиент

```python
from neogram import AsyncBot

async with AsyncBot(token="123456:ABC-DEF...") as bot:
    me = await bot.get_me()
    await bot.send_message(chat_id=123, text="Hello!")
```

Наследуется от `Bot` и предоставляет асинхронные версии всех API-методов. Все методы-корутины — используйте `await`. Поддерживает асинхронный контекстный менеджер (`async with`).

**Ключевые отличия от синхронного Bot:**
- Использует `curl_cffi.requests.AsyncSession` вместо `Session`
- Все API-методы являются корутинами (`async def`)
- Обработчики могут быть как синхронными, так и асинхронными — диспетчер автоматически определяет и `await`ит результат
- Метод `aclose()` для корректного закрытия сессии
- Polling и `process_update` также асинхронны

### Система обработчиков (handlers)

neogram использует декораторную систему регистрации обработчиков, аналогичную pyTelegramBotAPI. Первый подходящий обработчик для каждого типа обновления выигрывает.

#### Декораторы обработчиков

| Декоратор | Тип обновления | Аргументы фильтрации |
|-----------|---------------|---------------------|
| `@bot.message_handler(...)` | `message` | `commands`, `content_types`, `regexp`, `func`, `chat_types`, `user_ids`, `chat_ids` |
| `@bot.edited_message_handler(...)` | `edited_message` | `commands`, `content_types`, `regexp`, `func`, `chat_types`, `user_ids`, `chat_ids` |
| `@bot.channel_post_handler(...)` | `channel_post` | `commands`, `content_types`, `regexp`, `func`, `chat_types`, `chat_ids` |
| `@bot.edited_channel_post_handler(...)` | `edited_channel_post` | `commands`, `content_types`, `regexp`, `func`, `chat_types` |
| `@bot.callback_query_handler(...)` | `callback_query` | `func`, `data` |
| `@bot.inline_handler(...)` | `inline_query` | `func`, `regexp` |
| `@bot.my_chat_member_handler(...)` | `my_chat_member` | `func` |
| `@bot.chat_member_handler(...)` | `chat_member` | `func` |
| `@bot.chat_join_request_handler(...)` | `chat_join_request` | `func` |
| `@bot.poll_handler(...)` | `poll` | `func` |
| `@bot.poll_answer_handler(...)` | `poll_answer` | `func` |
| `@bot.pre_checkout_query_handler(...)` | `pre_checkout_query` | `func` |
| `@bot.shipping_query_handler(...)` | `shipping_query` | `func` |
| `@bot.business_message_handler(...)` | `business_message` | `commands`, `content_types`, `regexp`, `func` |
| `@bot.edited_business_message_handler(...)` | `edited_business_message` | `commands`, `content_types`, `regexp`, `func` |
| `@bot.deleted_business_messages_handler(...)` | `deleted_business_messages` | `func` |
| `@bot.chosen_inline_result_handler(...)` | `chosen_inline_result` | `func` |
| `@bot.message_reaction_handler(...)` | `message_reaction` | `func` |
| `@bot.message_reaction_count_handler(...)` | `message_reaction_count` | `func` |
| `@bot.chat_boost_handler(...)` | `chat_boost` | `func` |
| `@bot.removed_chat_boost_handler(...)` | `removed_chat_boost` | `func` |
| `@bot.purchased_paid_media_handler(...)` | `purchased_paid_media` | `func` |

#### Обработчик ошибок

```python
@bot.error_handler
def on_error(update, exception):
    print(f"Ошибка: {exception}")
```

#### Программная регистрация

```python
bot.register_handler("message", my_handler, commands=["start"], chat_types=["private"])
```

### Фильтрация обработчиков

Фильтры передаются в декоратор и проверяются при диспетчеризации обновлений. Обновление проходит, только если **все** фильтры совпадают.

| Фильтр | Тип | Описание |
|--------|-----|----------|
| `commands` | `Optional[List[str]]` | Список команд (без `/`). Проверяет, что текст начинается с `/команда` |
| `content_types` | `Optional[List[str]]` | Тип контента сообщения (`"text"`, `"photo"`, `"document"` и т.д.) |
| `regexp` | `Optional[str]` | Regex-паттерн для проверки `message.text` или `message.caption` |
| `func` | `Optional[Callable]` | Произвольная функция-предикат, принимает объект обновления |
| `chat_types` | `Optional[List[str]]` | Тип чата (`"private"`, `"group"`, `"supergroup"`, `"channel"`) |
| `user_ids` | `Optional[List[int]]` | Белый список ID пользователей |
| `chat_ids` | `Optional[List[int]]` | Белый список ID чатов |
| `data` | `Optional[Union[str, Callable]]` | Для callback_query — точное совпадение или regex для `callback_query.data` |

**StopPropagation:** выбросьте `StopPropagation` внутри обработчика, чтобы остановить дальнейшую обработку текущего обновления.

### Polling и Webhook

#### Polling (long polling)

```python
# Синхронный
bot.polling(timeout=30, none_stop=True, interval=0.0)

# Бесконечный polling (none_stop=True по умолчанию)
bot.infinity_polling()

# Остановка polling
bot.stop_polling()
```

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `timeout` | `int` | `30` | Таймаут long polling в секундах |
| `allowed_updates` | `Optional[List[str]]` | `None` | Список типов обновлений для получения |
| `none_stop` | `bool` | `True` | Не останавливаться при ошибках API |
| `interval` | `float` | `0.0` | Задержка между запросами (секунды) |

#### Webhook

```python
# Синхронный
@app.post("/webhook")
def webhook():
    bot.process_update(request.json)
    return "ok"

# Асинхронный
@app.post("/webhook")
async def webhook():
    await bot.process_update(request.json)
    return "ok"
```

### Исключения

#### `TelegramAPIError` (алиас: `TelegramError`)

Выбрасывается при ошибке от Telegram API.

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `error_code` | `int` | HTTP-подобный код ошибки (400, 401, 403, 429, 500 и т.д.) |
| `description` | `str` | Человекочитаемое описание ошибки |
| `parameters` | `dict` | Дополнительные параметры (например `{"retry_after": 30}`) |
| `method` | `str` | Имя API-метода, вызвавшего ошибку |
| `retry_after` | `Optional[int]` | Удобный shortcut для `parameters.get("retry_after")` |

#### `StopPropagation`

Выбросьте внутри обработчика, чтобы остановить диспетчеризацию дальнейших обработчиков для текущего обновления.

### TelegramObject — базовый класс типов

Все типы Telegram API наследуются от `TelegramObject` (dataclass) и предоставляют:

- **`from_dict(data: dict) -> TelegramObject`** — десериализация из JSON (автоматическое переименование полей: `type` → `type_val`, `from` → `from_user` и т.д.)
- **`to_dict() -> dict`** — сериализация в JSON (обратное переименование)
- **Автоматический dispatch union-типов** — полиморфные поля (например `MessageOrigin`, `ChatMember`) автоматически десериализуются в правильный подкласс на основе поля-дискриминатора

### InputFile — загрузка файлов

```python
from neogram import InputFile

# Из пути к файлу
f1 = InputFile("/path/to/photo.jpg")

# Из байтов
f2 = InputFile(b"raw bytes data", filename="document.pdf")

# Из файлового объекта
with open("audio.mp3", "rb") as fh:
    f3 = InputFile(fh)

# Использование
bot.send_document(chat_id=123, document=InputFile("/path/to/file.pdf"))
```

### API-методы Bot

Ниже приведён полный список API-методов, доступных в `Bot` (синхронно) и `AsyncBot` (асинхронно с `await`). Все методы возвращают типизированные объекты Telegram.

#### Обновления и подключение

| Метод | Возвращает | Описание |
|-------|-----------|----------|
| `get_updates(offset, limit, timeout, allowed_updates)` | `List[Update]` | Получение обновлений через long polling |
| `set_webhook(url, certificate, ...)` | `bool` | Установка webhook |
| `delete_webhook(drop_pending_updates)` | `bool` | Удаление webhook |
| `get_webhook_info()` | `WebhookInfo` | Информация о текущем webhook |
| `get_me()` | `User` | Информация о боте |
| `log_out()` | `bool` | Выход из облачного Bot API |
| `close()` | `bool` | Закрытие экземпляра бота на локальном сервере |

#### Отправка сообщений

| Метод | Возвращает | Описание |
|-------|-----------|----------|
| `send_message(chat_id, text, ...)` | `Message` | Отправка текстового сообщения |
| `forward_message(chat_id, from_chat_id, message_id, ...)` | `MessageId` | Пересылка сообщения |
| `forward_messages(chat_id, from_chat_id, message_ids, ...)` | `List[MessageId]` | Пересылка нескольких сообщений |
| `copy_message(chat_id, from_chat_id, message_id, ...)` | `MessageId` | Копирование сообщения |
| `copy_messages(chat_id, from_chat_id, message_ids, ...)` | `List[MessageId]` | Копирование нескольких сообщений |
| `send_photo(chat_id, photo, ...)` | `Message` | Отправка фото |
| `send_audio(chat_id, audio, ...)` | `Message` | Отправка аудио |
| `send_document(chat_id, document, ...)` | `Message` | Отправка документа |
| `send_video(chat_id, video, ...)` | `Message` | Отправка видео |
| `send_animation(chat_id, animation, ...)` | `Message` | Отправка анимации (GIF) |
| `send_voice(chat_id, voice, ...)` | `Message` | Отправка голосового сообщения |
| `send_video_note(chat_id, video_note, ...)` | `Message` | Отправка видео-заметки (кружочек) |
| `send_live_photo(chat_id, live_photo, photo, ...)` | `Message` | Отправка живого фото |
| `send_paid_media(chat_id, star_count, media, ...)` | `Message` | Отправка платного медиа |
| `send_media_group(chat_id, media, ...)` | `List[Message]` | Отправка группы медиа |
| `send_location(chat_id, latitude, longitude, ...)` | `Message` | Отправка локации |
| `send_venue(chat_id, latitude, longitude, title, address, ...)` | `Message` | Отправка места |
| `send_contact(chat_id, phone_number, first_name, ...)` | `Message` | Отправка контакта |
| `send_poll(chat_id, question, options, ...)` | `Message` | Отправка опроса |
| `send_checklist(business_connection_id, chat_id, checklist, ...)` | `Message` | Отправка чек-листа |
| `send_dice(chat_id, ...)` | `Message` | Отправка кубика |
| `send_message_draft(chat_id, draft_id, ...)` | `Message` | Отправка черновика сообщения |
| `send_chat_action(chat_id, action, ...)` | `bool` | Отправка действия «печатает…» |

#### Реакции и действия

| Метод | Возвращает | Описание |
|-------|-----------|----------|
| `set_message_reaction(chat_id, message_id, reaction, is_big)` | `bool` | Установка реакции на сообщение |

#### Редактирование и удаление

| Метод | Возвращает | Описание |
|-------|-----------|----------|
| `edit_message_text(text, ...)` | `Message` | Редактирование текста сообщения |
| `edit_message_caption(...)` | `Message` | Редактирование подписи к медиа |
| `edit_message_reply_markup(...)` | `Message` | Редактирование inline-клавиатуры |
| `delete_message(chat_id, message_id)` | `bool` | Удаление сообщения |
| `delete_messages(chat_id, message_ids)` | `bool` | Удаление нескольких сообщений |
| `delete_message_reaction(chat_id, message_id, ...)` | `bool` | Удаление реакции |

#### Ответы на запросы

| Метод | Возвращает | Описание |
|-------|-----------|----------|
| `answer_callback_query(callback_query_id, ...)` | `bool` | Ответ на callback-запрос |
| `answer_inline_query(inline_query_id, results, ...)` | `bool` | Ответ на inline-запрос |
| `answer_guest_query(guest_query_id, result)` | `bool` | Ответ на guest-запрос |

#### Профили пользователей

| Метод | Возвращает | Описание |
|-------|-----------|----------|
| `get_user_profile_photos(user_id, ...)` | `UserProfilePhotos` | Фото профиля пользователя |
| `get_user_profile_audios(user_id, ...)` | `UserProfileAudios` | Аудио профиля пользователя |
| `set_user_emoji_status(user_id, ...)` | `bool` | Установка emoji-статуса |

#### Файлы

| Метод | Возвращает | Описание |
|-------|-----------|----------|
| `get_file(file_id)` | `File` | Получение информации о файле |

#### Чаты: администрирование участников

| Метод | Возвращает | Описание |
|-------|-----------|----------|
| `ban_chat_member(chat_id, user_id, ...)` | `bool` | Бан участника |
| `unban_chat_member(chat_id, user_id, ...)` | `bool` | Разбан участника |
| `restrict_chat_member(chat_id, user_id, permissions, ...)` | `bool` | Ограничение участника |
| `promote_chat_member(chat_id, user_id, ...)` | `bool` | Повышение участника |
| `set_chat_administrator_custom_title(...)` | `bool` | Установка кастомного титула админа |
| `set_chat_member_tag(chat_id, user_id, tag)` | `bool` | Установка тега участника |
| `ban_chat_sender_chat(chat_id, sender_chat_id)` | `bool` | Бан канала-отправителя |
| `unban_chat_sender_chat(chat_id, sender_chat_id)` | `bool` | Разбан канала-отправителя |

#### Чаты: настройки

| Метод | Возвращает | Описание |
|-------|-----------|----------|
| `set_chat_permissions(chat_id, permissions, ...)` | `bool` | Установка прав чата |
| `export_chat_invite_link(chat_id)` | `str` | Экспорт ссылки-приглашения |
| `create_chat_invite_link(chat_id, ...)` | `ChatInviteLink` | Создание ссылки-приглашения |
| `edit_chat_invite_link(chat_id, invite_link, ...)` | `ChatInviteLink` | Редактирование ссылки-приглашения |
| `create_chat_subscription_invite_link(...)` | `ChatInviteLink` | Создание платной подписки |
| `edit_chat_subscription_invite_link(...)` | `ChatInviteLink` | Редактирование платной подписки |
| `revoke_chat_invite_link(chat_id, invite_link)` | `ChatInviteLink` | Отзыв ссылки-приглашения |
| `approve_chat_join_request(chat_id, user_id)` | `bool` | Одобрение заявки на вступление |
| `decline_chat_join_request(chat_id, user_id)` | `bool` | Отклонение заявки на вступление |
| `set_chat_photo(chat_id, photo)` | `bool` | Установка фото чата |
| `delete_chat_photo(chat_id)` | `bool` | Удаление фото чата |
| `set_chat_title(chat_id, title)` | `bool` | Установка названия чата |
| `set_chat_description(chat_id, description)` | `bool` | Установка описания чата |
| `pin_chat_message(chat_id, message_id, ...)` | `bool` | Закрепление сообщения |
| `unpin_chat_message(chat_id, ...)` | `bool` | Открепление сообщения |
| `unpin_all_chat_messages(chat_id)` | `bool` | Открепление всех сообщений |
| `leave_chat(chat_id)` | `bool` | Выход из чата |
| `get_chat(chat_id)` | `ChatFullInfo` | Получение информации о чате |
| `get_chat_administrators(chat_id, ...)` | `List[ChatMember]` | Список администраторов |
| `get_chat_member_count(chat_id)` | `Any` | Количество участников |
| `get_chat_member(chat_id, user_id)` | `ChatMember` | Информация об участнике |
| `get_user_personal_chat_messages(user_id, limit)` | `List[Message]` | Личные сообщения пользователя |

#### Форумы (топики)

| Метод | Возвращает | Описание |
|-------|-----------|----------|
| `get_forum_topic_icon_stickers()` | `List[Sticker]` | Стикеры для иконок топиков |
| `create_forum_topic(chat_id, name, ...)` | `ForumTopic` | Создание топика |
| `edit_forum_topic(chat_id, message_thread_id, ...)` | `bool` | Редактирование топика |
| `close_forum_topic(chat_id, message_thread_id)` | `bool` | Закрытие топика |
| `reopen_forum_topic(chat_id, message_thread_id)` | `bool` | Повторное открытие топика |
| `delete_forum_topic(chat_id, message_thread_id)` | `bool` | Удаление топика |
| `unpin_all_forum_topic_messages(...)` | `bool` | Открепление всех сообщений в топике |
| `edit_general_forum_topic(chat_id, name)` | `bool` | Редактирование общего топика |
| `close_general_forum_topic(chat_id)` | `bool` | Закрытие общего топика |
| `reopen_general_forum_topic(chat_id)` | `bool` | Повторное открытие общего топика |
| `hide_general_forum_topic(chat_id)` | `bool` | Скрытие общего топика |
| `unhide_general_forum_topic(chat_id)` | `bool` | Отображение общего топика |
| `unpin_all_general_forum_topic_messages(chat_id)` | `bool` | Открепление всех сообщений общего топика |

#### Команды бота и настройки

| Метод | Возвращает | Описание |
|-------|-----------|----------|
| `set_my_commands(commands, scope, language_code)` | `bool` | Установка команд бота |
| `delete_my_commands(scope, language_code)` | `bool` | Удаление команд бота |
| `get_my_commands(scope, language_code)` | `List[BotCommand]` | Получение команд бота |
| `set_my_name(name, language_code)` | `bool` | Установка имени бота |
| `get_my_name(language_code)` | `BotName` | Получение имени бота |
| `set_my_description(description, language_code)` | `bool` | Установка описания бота |
| `get_my_description(language_code)` | `BotDescription` | Получение описания бота |
| `set_my_short_description(...)` | `bool` | Установка краткого описания |
| `get_my_short_description(language_code)` | `BotShortDescription` | Получение краткого описания |
| `set_my_profile_photo(photo)` | `bool` | Установка фото профиля бота |
| `remove_my_profile_photo()` | `bool` | Удаление фото профиля бота |
| `set_chat_menu_button(chat_id, menu_button)` | `bool` | Установка кнопки меню |
| `get_chat_menu_button(chat_id)` | `MenuButton` | Получение кнопки меню |
| `set_my_default_administrator_rights(...)` | `bool` | Установка прав админа по умолчанию |
| `get_my_default_administrator_rights(...)` | `ChatAdministratorRights` | Получение прав админа по умолчанию |

#### Подарки и верификация

| Метод | Возвращает | Описание |
|-------|-----------|----------|
| `get_available_gifts()` | `Gifts` | Список доступных подарков |
| `send_gift(gift_id, ...)` | `bool` | Отправка подарка |
| `gift_premium_subscription(user_id, ...)` | `bool` | Подарок Premium-подписки |
| `verify_user(user_id, ...)` | `bool` | Верификация пользователя |
| `verify_chat(chat_id, ...)` | `bool` | Верификация чата |
| `remove_user_verification(user_id)` | `bool` | Снятие верификации пользователя |
| `remove_chat_verification(chat_id)` | `bool` | Снятие верификации чата |

#### Бизнес-подключения

| Метод | Возвращает | Описание |
|-------|-----------|----------|
| `get_business_connection(business_connection_id)` | `BusinessConnection` | Информация о бизнес-подключении |
| `read_business_message(...)` | `bool` | Чтение бизнес-сообщения |
| `delete_business_messages(...)` | `bool` | Удаление бизнес-сообщений |
| `set_business_account_name(...)` | `bool` | Установка имени бизнес-аккаунта |
| `set_business_account_username(...)` | `bool` | Установка имени пользователя бизнес-аккаунта |
| `set_business_account_bio(...)` | `bool` | Установка био бизнес-аккаунта |
| `set_business_account_profile_photo(...)` | `bool` | Установка фото бизнес-аккаунта |
| `remove_business_account_profile_photo(...)` | `bool` | Удаление фото бизнес-аккаунта |
| `set_business_account_gift_settings(...)` | `bool` | Настройки подарков бизнес-аккаунта |
| `get_business_account_star_balance(...)` | `StarAmount` | Баланс звёзд бизнес-аккаунта |
| `transfer_business_account_stars(...)` | `bool` | Перевод звёзд |
| `get_business_account_gifts(...)` | `OwnedGifts` | Список подарков бизнес-аккаунта |

#### Управляемые боты

| Метод | Возвращает | Описание |
|-------|-----------|----------|
| `get_managed_bot_token(user_id)` | `str` | Получение токена управляемого бота |
| `replace_managed_bot_token(user_id)` | `str` | Замена токена управляемого бота |
| `get_managed_bot_access_settings(user_id)` | `BotAccessSettings` | Настройки доступа управляемого бота |
| `set_managed_bot_access_settings(user_id, ...)` | `BotAccessSettings` | Установка настроек доступа |

#### Boost, стикеры, звёзды, игры и другие

| Метод | Возвращает | Описание |
|-------|-----------|----------|
| `get_user_chat_boosts(chat_id, user_id)` | `UserChatBoosts` | Boost-ы пользователя в чате |
| `set_chat_sticker_set(chat_id, sticker_set_name)` | `bool` | Установка набора стикеров |
| `delete_chat_sticker_set(chat_id)` | `bool` | Удаление набора стикеров |

> Полный список методов включает также все методы для работы со стикерами, звёздами (Star Transactions), играми, платными медиа, паспортными данными и др. — всего более 150 API-методов, соответствующих Bot API 10.0.

### Типы Telegram API

Модуль определяет все типы Telegram Bot API 10.0 как dataclass-ы с `_FIELD_META` для автоматической сериализации. Ниже перечислены основные группы типов (полный список — в `__all__` модуля):

**Базовые:** `TelegramObject`, `Update`, `User`, `Chat`, `ChatFullInfo`, `Message`, `MessageId`

**Сообщения:** `MessageEntity`, `TextQuote`, `ExternalReplyInfo`, `ReplyParameters`, `MessageOrigin*`, `LinkPreviewOptions`, `InaccessibleMessage`, `MaybeInaccessibleMessage`

**Медиа:** `PhotoSize`, `Animation`, `Audio`, `Document`, `Video`, `VideoNote`, `Voice`, `LivePhoto`, `File`, `VideoQuality`

**Платные медиа:** `PaidMediaInfo`, `PaidMedia*`, `InputPaidMedia*`

**Опросы:** `Poll`, `PollOption`, `PollAnswer`, `PollMedia`, `InputPollOption`, `InputPollMedia`, `InputPollOptionMedia`

**Клавиатуры:** `InlineKeyboardMarkup`, `InlineKeyboardButton`, `ReplyKeyboardMarkup`, `KeyboardButton`, `ReplyKeyboardRemove`, `ForceReply`, `KeyboardButtonRequestUsers`, `KeyboardButtonRequestChat`, `KeyboardButtonPollType`

**Inline:** `InlineQuery`, `InlineQueryResult*`, `InputMessageContent*`, `ChosenInlineResult`

**Чаты:** `ChatPermissions`, `ChatPhoto`, `ChatInviteLink`, `ChatAdministratorRights`, `ChatMember*`, `ChatJoinRequest`, `ChatLocation`, `ChatShared`, `ChatBackground`

**Реакции:** `ReactionType*`, `ReactionCount`, `MessageReactionUpdated`, `MessageReactionCountUpdated`

**Форумы:** `ForumTopic`, `ForumTopicCreated`, `ForumTopicEdited`, `ForumTopicClosed`, `ForumTopicReopened`, `GeneralForumTopic*`

**Подарки:** `Gift`, `Gifts`, `GiftInfo`, `GiftBackground`, `UniqueGift*`, `OwnedGift*`, `AcceptedGiftTypes`

**Бизнес:** `BusinessConnection`, `BusinessBotRights`, `BusinessIntro`, `BusinessLocation`, `BusinessOpeningHours*`, `BusinessMessagesDeleted`

**Boost:** `ChatBoost`, `ChatBoostSource*`, `ChatBoostUpdated`, `ChatBoostRemoved`, `UserChatBoosts`

**Платежи:** `Invoice`, `LabeledPrice`, `ShippingAddress`, `ShippingOption`, `ShippingQuery`, `OrderInfo`, `SuccessfulPayment`, `RefundedPayment`, `PreCheckoutQuery`

**Звёзды:** `StarAmount`, `StarTransaction`, `StarTransactions`, `TransactionPartner*`, `RevenueWithdrawalState*`, `AffiliateInfo`

**Паспорт:** `PassportData`, `PassportFile`, `EncryptedPassportElement`, `EncryptedCredentials`, `PassportElementError*`

**Игры:** `Game`, `CallbackGame`, `GameHighScore`

**Прочее:** `WebhookInfo`, `BotCommand`, `BotCommandScope*`, `BotName`, `BotDescription`, `BotShortDescription`, `MenuButton*`, `MaskPosition`, `Sticker`, `StickerSet`, `InputSticker`, `Story*`, `Dice`, `Contact`, `Venue`, `Location`, `ProximityAlertTriggered`, `WebAppData`, `WebAppInfo`, `SentWebAppMessage`, `WriteAccessAllowed`, `ResponseParameters`, `CallbackQuery`

---

## AI-клиенты (ii)

Модуль `ii.py` предоставляет набор клиентов для различных AI-сервисов. Все клиенты используют `curl_cffi` для HTTP-запросов с возможностью имперсонации браузерных TLS-фингерпринтов.

### OnlySQ

Клиент API [OnlySQ](https://my.onlysq.ru/) для генерации текста и изображений.

```python
from neogram import OnlySQ

ai = OnlySQ(key="your-api-key")
```

#### `__init__(key: str)`

| Параметр | Тип | Описание |
|----------|-----|----------|
| `key` | `str` | API-ключ OnlySQ (получить: https://my.onlysq.ru/) |

#### `get_models(modality, can_tools, can_think, can_stream, status, max_cost, return_names) -> List[str]`

Получает и фильтрует доступные модели OnlySQ.

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `modality` | `Optional[Union[str, List[str]]]` | `None` | Модальность модели (фильтр) |
| `can_tools` | `Optional[bool]` | `None` | Поддержка tool calling |
| `can_think` | `Optional[bool]` | `None` | Поддержка режима размышлений |
| `can_stream` | `Optional[bool]` | `None` | Поддержка стриминга |
| `status` | `Optional[str]` | `None` | Статус модели |
| `max_cost` | `Optional[float]` | `None` | Максимальная стоимость |
| `return_names` | `bool` | `False` | Возвращать имена вместо ключей |

#### `generate_answer(model, messages, timeout) -> str`

Генерация текстового ответа. Автоматический retry (3 попытки) при серверных ошибках 5xx с exponential backoff.

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `model` | `str` | `"gpt-5.2-chat"` | Имя модели |
| `messages` | `Optional[List[dict]]` | `None` | Список сообщений (обязательный) |
| `timeout` | `int` | `120` | Таймаут запроса (секунды) |

**Возвращает:** строку с текстом ответа или строку с ошибкой (`"Error: ..."`).

#### `generate_image(model, prompt, ratio, filename) -> bool`

Генерация изображения.

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `model` | `str` | `"flux"` | Имя модели генерации |
| `prompt` | `Optional[str]` | `None` | Текстовый промпт (обязательный) |
| `ratio` | `str` | `"16:9"` | Соотношение сторон |
| `filename` | `str` | `"image.png"` | Имя файла для сохранения |

**Возвращает:** `True` при успешной генерации и сохранении, `False` при ошибке.

---

### Deef

Набор утилит: перевод, сокращение ссылок, фоновые задачи, запросы к Perplexity AI, Toolbaz и DeepInfra.

```python
from neogram import Deef

deef = Deef()
```

#### `translate(text, lang) -> str`

Перевод текста через Google Translate (мобильная версия).

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `text` | `Optional[str]` | `None` | Текст для перевода |
| `lang` | `str` | `"en"` | Целевой язык |

#### `short_url(long_url) -> str`

Сокращение ссылки через clck.ru.

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `long_url` | `Optional[str]` | `None` | Длинная ссылка |

#### `run_in_bg(func, *args, **kwargs) -> threading.Thread`

Запускает функцию в фоновом daemon-потоке. Возвращает объект `Thread`. Ошибки внутри функции логируются, но не пробрасываются.

#### `encode_base64(path) -> Optional[str]`

Кодирует содержимое файла в base64-строку.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `path` | `Optional[str]` | Путь к файлу (обязательный) |

#### `perplexity_ask(prompt, model) -> dict`

Запрос к Perplexity AI через SSE (Server-Sent Events). Автоматически получает конфигурацию моделей, выбирает подходящую и парсит потоковый ответ.

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `prompt` | `Optional[str]` | `None` | Текст запроса (обязательный) |
| `model` | `str` | `"auto"` | Название модели (например `"o3pro"`, `"turbo"`, `"auto"`) |

**Возвращает:**
- При успехе: `{"text": "ответ", "urls": ["url1", ...]}`
- При ошибке: `{"text": "Error", "urls": []}`

#### `toolchat(prompt, model) -> str`

Генерация ответа через Toolbaz. Автоматически получает токен и отправляет запрос.

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `prompt` | `Optional[str]` | `None` | Текст запроса (обязательный) |
| `model` | `str` | `"toolbaz-v4.5-fast"` | Название модели |

**Доступные модели:** `gemini-3-flash`, `gemini-3.1-flash-lite`, `gemini-2.5-pro`, `gemini-2.5-flash`, `deepseek-v3.1`, `deepseek-v3`, `deepseek-r1`, `gpt-5.2`, `gpt-5`, `gpt-oss-120b`, `o3-mini`, `gpt-4o-latest`, `claude-sonnet-4`, `grok-4-fast`, `toolbaz-v4.5-fast`, `toolbaz-v4`, `Llama-4-Maverick`

#### `deepinfra(messages, model, temperature, max_tokens, timeout) -> dict`

Чат-запрос к DeepInfra API.

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `messages` | `List[dict]` | — | Список сообщений в формате OpenAI |
| `model` | `str` | `"zai-org/GLM-5.1"` | Идентификатор модели |
| `temperature` | `float` | `0.7` | Температура генерации (0.0–1.0) |
| `max_tokens` | `int` | `4000` | Максимальное число токенов в ответе |
| `timeout` | `int` | `30` | Таймаут запроса (секунды) |

**Возвращает:** `dict` — JSON-ответ от DeepInfra при успехе, `{"error": "..."}` при ошибке.

---

### Qwen

Клиент для работы с моделями Qwen через [chat.qwen.ai](https://chat.qwen.ai). Поддерживает текст, изображения, поиск, deep research и другие режимы.

```python
from neogram import Qwen

qwen = Qwen()
```

#### `__init__(proxy: Optional[str] = None)`

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `proxy` | `Optional[str]` | `None` | URL прокси-сервера |

#### `fetch_models() -> List[Dict]`

Возвращает список доступных моделей с кэшированием (TTL 10 минут). Каждая модель содержит поля: `id`, `name`, `capabilities` (`vision`, `thinking`, `search`), `chat_types`, `thinking_format`, `is_visitor_active`.

#### `chat(model, messages, stream, ctype, size, think) -> Union[str, Iterator]`

Чат с моделями Qwen. Поддерживает автоматическую загрузку изображений, смену модели при отсутствии vision-поддержки, и автопереключение режима чата.

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `model` | `str` | `"qwen3.6-plus"` | Имя модели |
| `messages` | `Optional[List[dict]]` | `None` | Список сообщений в формате OpenAI |
| `stream` | `bool` | `False` | `True` — вернуть итератор чанков, `False` — полный ответ строкой |
| `ctype` | `str` | `"t2t"` | Режим чата: `t2t`, `search`, `t2i`, `deep_research`, `artifacts`, `learn`, `image_edit` |
| `size` | `Optional[str]` | `None` | Размер для t2i/image_edit (например `"16:9"`, `"9:16"`, `"1:1"`) |
| `think` | `bool` | `True` | Включить режим размышлений |

**Возвращает:**
- `str` — если `stream=False`
- `Iterator` — если `stream=True` (yield `str` или `dict` с `type="thinking"` / `type="image"`)

**Поддерживаемые типы чата (`ctype`):** `t2t`, `search`, `t2i`, `deep_research`, `artifacts`, `learn`, `image_edit`

**Поддержка изображений:** Если в последнем сообщении пользователя есть `image_url`, но модель не поддерживает vision, клиент автоматически переключится на vision-совместимую модель.

**Гостевой режим:** Клиент автоматически генерирует LZW-сжатые cookies (`ssxmod_itna`) и получает `bx-umidtoken` для авторизации запросов без аккаунта. При загрузке изображений используется Alibaba Cloud OSS через STS-токены.

---

### ChatGPT / OpenAI

Универсальный клиент для OpenAI-совместимых API. `OpenAI` — алиас для `ChatGPT`.

```python
from neogram import ChatGPT, OpenAI

client = ChatGPT(
    url="https://api.openai.com/v1",
    headers={"Authorization": "Bearer sk-..."},
    impersonate="chrome")

# OpenAI — то же самое
client = OpenAI(
    url="https://api.openai.com/v1",
    headers={"Authorization": "Bearer sk-..."})
```

#### `__init__(url: str, headers: dict, impersonate: Optional[str] = None)`

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `url` | `str` | — | Базовый URL API (например `https://api.openai.com/v1`) |
| `headers` | `dict` | — | HTTP-заголовки (обычно `Authorization`) |
| `impersonate` | `Optional[str]` | `None` | TLS-фингерпринт для curl_cffi |

Поддерживает контекстный менеджер (`with ChatGPT(...) as client:`).

#### `generate_chat_completion(model, messages, temperature, max_tokens, stream, **kwargs) -> dict`

Генерация ответа в чате.

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `model` | `str` | — | Имя модели |
| `messages` | `list` | — | Список сообщений |
| `temperature` | `Optional[float]` | `None` | Температура генерации |
| `max_tokens` | `Optional[int]` | `None` | Максимальное число токенов |
| `stream` | `bool` | `False` | Потоковый режим |

#### `generate_image(prompt, n, size, response_format, **kwargs) -> dict`

Генерация изображения.

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `prompt` | `str` | — | Текстовый промпт |
| `n` | `int` | `1` | Количество изображений |
| `size` | `str` | `"1024x1024"` | Размер изображения |
| `response_format` | `str` | `"url"` | Формат ответа (`"url"` или `"b64_json"`) |

#### `generate_embedding(model, input_data, user, **kwargs) -> dict`

Генерация embedding-вектора.

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `model` | `str` | — | Имя модели |
| `input_data` | `Union[str, list]` | — | Входные данные |
| `user` | `Optional[str]` | `None` | Идентификатор пользователя |

#### `generate_transcription(file, model, language, prompt, response_format, temperature, **kwargs) -> Union[dict, str]`

Транскрипция аудио (Speech-to-Text).

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `file` | `BinaryIO` | — | Аудиофайл |
| `model` | `str` | — | Имя модели |
| `language` | `Optional[str]` | `None` | Язык аудио |
| `prompt` | `Optional[str]` | `None` | Подсказка для модели |
| `response_format` | `str` | `"json"` | Формат ответа |
| `temperature` | `float` | `0` | Температура |

#### `generate_translation(file, model, prompt, response_format, temperature, **kwargs) -> Union[dict, str]`

Перевод аудио на английский.

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `file` | `BinaryIO` | — | Аудиофайл |
| `model` | `str` | — | Имя модели |
| `prompt` | `Optional[str]` | `None` | Подсказка для модели |
| `response_format` | `str` | `"json"` | Формат ответа |
| `temperature` | `float` | `0` | Температура |

#### `get_models() -> dict`

Получение списка доступных моделей.

---

## Быстрый старт

### Telegram бот (синхронный)

```python
from neogram import Bot

bot = Bot(token="YOUR_BOT_TOKEN")

@bot.message_handler(commands=["start"])
def on_start(message):
    bot.send_message(chat_id=message.chat.id, text="Привет!")

@bot.message_handler(content_types=["text"])
def on_text(message):
    bot.send_message(chat_id=message.chat.id, text=f"Вы написали: {message.text}")

bot.infinity_polling()
```

### Telegram бот (асинхронный)

```python
import asyncio
from neogram import AsyncBot

bot = AsyncBot(token="YOUR_BOT_TOKEN")

@bot.message_handler(commands=["start"])
async def on_start(message):
    await bot.send_message(chat_id=message.chat.id, text="Привет!")

async def main():
    async with bot:
        await bot.infinity_polling()

asyncio.run(main())
```

### AI-генерация текста

```python
from neogram import OnlySQ

ai = OnlySQ(key="your-onlysq-key")
answer = ai.generate_answer(
    model="gpt-5.2-chat",
    messages=[{"role": "user", "content": "Расскажи о Python"}]
)
print(answer)
```

### Qwen чат

```python
from neogram import Qwen

qwen = Qwen()
result = qwen.chat(
    model="qwen3.6-plus",
    messages=[{"role": "user", "content": "Привет!"}]
)
print(result)
```

### Перевод и утилиты

```python
from neogram import Deef

deef = Deef()

# Перевод
translated = deef.translate("Hello world", lang="ru")

# Сокращение ссылки
short = deef.short_url("https://example.com/very/long/url")

# Фоновая задача
thread = deef.run_in_bg(some_function, arg1, arg2)
```

### OpenAI-совместимый API

```python
from neogram import ChatGPT

client = ChatGPT(
    url="https://api.openai.com/v1",
    headers={"Authorization": "Bearer sk-..."}
)

response = client.generate_chat_completion(
    model="gpt-5,5",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response["choices"][0]["message"]["content"])
```

---

## Версия API

- **Telegram Bot API:** `10.0` (константа `API_VERSION`)
- Поддерживаются все типы и методы, включая новые возможности: бизнес-подключения, управляемые боты, подарки, уникальные подарки, чек-листы, платные медиа, live photo, direct messages, guest queries и другие

---

## Логирование

Модуль использует стандартный `logging.getLogger("neogram")`. Настройте уровень логирования для получения отладочной информации:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## Лицензия

Этот проект распространяется под лицензией **MIT**. Подробности см. в файле [LICENSE](LICENSE).