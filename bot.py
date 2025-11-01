import os
import json
import asyncio
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputFile,
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeChat,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import gspread
from google.oauth2.service_account import Credentials


# -----------------------------------
#  Состояния
# -----------------------------------
WAIT_GO, ASK_NAME, ASK_COUNT = range(3)
BROADCAST_WAIT_CONTENT, BROADCAST_CONFIRM = range(1001, 1003)

# -----------------------------------
#  Настройки
# -----------------------------------
ADMIN_IDS = {int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()}


# -----------------------------------
#  Google Sheets
# -----------------------------------
def gs_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON", "").strip()
    if not creds_json:
        raise RuntimeError("Не задан GOOGLE_CREDENTIALS_JSON")
    info = json.loads(creds_json)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)


def gs_ws(sheet_name: str, headers: list):
    sheet_id = os.environ.get("SHEET_ID", "").strip()
    if not sheet_id:
        raise RuntimeError("Не задан SHEET_ID")
    gc = gs_client()
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=2000, cols=max(8, len(headers)))
        ws.append_row(headers)
    return ws


def add_subscriber(chat_id, username, first_name):
    ws = gs_ws("Подписчики", ["chat_id", "username", "first_name", "subscribed_at"])
    existing = ws.col_values(1)
    if str(chat_id) not in existing:
        ws.append_row([
            str(chat_id),
            username or "",
            first_name or "",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ])


def remove_subscriber(chat_id):
    ws = gs_ws("Подписчики", ["chat_id", "username", "first_name", "subscribed_at"])
    cells = ws.findall(str(chat_id), in_column=1)
    for c in reversed(cells):
        ws.delete_rows(c.row)


def all_chat_ids():
    ws = gs_ws("Подписчики", ["chat_id", "username", "first_name", "subscribed_at"])
    vals = ws.col_values(1)
    return [int(x) for x in vals[1:] if x.isdigit()]


# -----------------------------------
#  Меню команд
# -----------------------------------
async def set_user_commands(app):
    commands = [
        BotCommand("start", "Регистрация на концерт"),
        BotCommand("help", "Помощь и контакты"),
        BotCommand("unsubscribe", "Отписаться от уведомлений"),
    ]
    await app.bot.set_my_commands(commands, scope=BotCommandScopeDefault())


async def set_admin_commands(app, admin_ids):
    commands = [
        BotCommand("broadcast", "Создать рассылку"),
        BotCommand("stats", "Показать статистику"),
        BotCommand("cancel", "Отменить рассылку"),
    ]
    for aid in admin_ids:
        try:
            await app.bot.set_my_commands(commands, scope=BotCommandScopeChat(aid))
        except Exception:
            pass


async def post_init(app):
    await set_user_commands(app)
    await set_admin_commands(app, ADMIN_IDS)


# -----------------------------------
#  Регистрация пользователей
# -----------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_subscriber(
        chat_id=user.id,
        username=f"@{user.username}" if user.username else "",
        first_name=user.first_name or "",
    )

    text = (
        "Добро пожаловать в регистрацию на Презентацию альбома и Birthday party by Damir Mate — 25 ноября!\n\n"
        "Это будет особенный вечер. Я очень рад, что ты решил(а) разделить его со мной.\n\n"
        "Мы презентуем для тебя альбом, сыграем уже вышедшие треки и, конечно, отпразднуем мою дрху вместе в нашем теплом кругу.\n\n"
        "Кликни \"Я иду!\", чтобы зарегистрироваться"
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Я иду!", callback_data="go")]])
    await update.message.reply_text(text, reply_markup=keyboard)
    return WAIT_GO


async def on_go_pressed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Отлично. Подскажи, как тебя зовут?")
    return ASK_NAME


async def got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data["name"] = name
    await update.message.reply_text(
        f"Гуд, {name}! 🙌\n\n"
        "Сколько человек будет с тобой?\n"
        "(напиши число — если ты придёшь один/одна, то просто напиши «1»)"
    )
    return ASK_COUNT


async def got_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    try:
        count = int(raw)
        if count <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Напиши, пожалуйста, целое положительное число. Пример: 1")
        return ASK_COUNT

    name = context.user_data.get("name", "")
    user = update.effective_user

    ws = gs_ws("Записи", ["Время", "Telegram ID", "Юзернейм", "Имя", "Количество"])
    ws.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        user.id,
        f"@{user.username}" if user.username else "",
        name,
        count,
    ])

    msg4 = (
        f"Спасибо, {name}!\n\n"
        "До встречи, мы во всю готовимся, чтобы выдать лучший звук.\n\n"
        "📅 Когда: 25 ноября, 19:00\n"
        "📍 Где: Клуб ТехникаБезОпасности\n"
        "🫂 Формат: Donation\n"
        "🏠 Адрес: Сущевская улица, 23с10\n"
        "🚇 Метро: Менделеевская\n\n"
        "Буду очень ждать 🤎"
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Кайф", callback_data="kaif")]])
    await update.message.reply_text(msg4, reply_markup=keyboard)
    return ConversationHandler.END


async def on_kaif_pressed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    msg5 = (
        "Раз кайф, то подпишись на мою телегу :)\n\n"
        "Там будут все новости по концерту — [тык](https://t.me/+xkFENZGOXv44N2Zi)"
    )
    if os.path.exists("poster.jpg"):
        with open("poster.jpg", "rb") as f:
            await q.message.reply_photo(photo=InputFile(f), caption=msg5, parse_mode="Markdown")
    else:
        await q.message.reply_text(msg5, parse_mode="Markdown")


# -----------------------------------
#  3-шаговая рассылка с предпросмотром и кнопкой отмены
# -----------------------------------
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or user.id not in ADMIN_IDS:
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Отменить рассылку", callback_data="cancel_broadcast")]
    ])
    await update.message.reply_text(
        "Ок, прикрепи фото, видео или текст для рассылки.\nКогда будешь готов — просто отправь сообщение.",
        reply_markup=keyboard,
    )
    return BROADCAST_WAIT_CONTENT


async def broadcast_collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    kind, file_id = "text", None
    caption = msg.caption or msg.text or " "

    if msg.photo:
        kind, file_id = "photo", msg.photo[-1].file_id
    elif msg.video:
        kind, file_id = "video", msg.video.file_id
    elif msg.animation:
        kind, file_id = "animation", msg.animation.file_id
    elif msg.document:
        kind, file_id = "document", msg.document.file_id

    context.user_data.update({"kind": kind, "file_id": file_id, "caption": caption})

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Всё ок, выкладывай", callback_data="confirm_broadcast"),
            InlineKeyboardButton("✏️ Исправить", callback_data="edit_broadcast"),
        ],
        [InlineKeyboardButton("🚫 Отменить рассылку", callback_data="cancel_broadcast")],
    ])

    if kind == "photo":
        await msg.reply_photo(file_id, caption=f"ПРЕДПРОСМОТР:\n\n{caption}", reply_markup=keyboard)
    elif kind == "video":
        await msg.reply_video(file_id, caption=f"ПРЕДПРОСМОТР:\n\n{caption}", reply_markup=keyboard)
    elif kind == "animation":
        await msg.reply_animation(file_id, caption=f"ПРЕДПРОСМОТР:\n\n{caption}", reply_markup=keyboard)
    elif kind == "document":
        await msg.reply_document(file_id, caption=f"ПРЕДПРОСМОТР:\n\n{caption}", reply_markup=keyboard)
    else:
        await msg.reply_text(f"ПРЕДПРОСМОТР:\n\n{caption}", reply_markup=keyboard)

    return BROADCAST_CONFIRM


async def broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kind = context.user_data.get("kind")
    file_id = context.user_data.get("file_id")
    caption = context.user_data.get("caption")

    ids = all_chat_ids()
    sent, fail = 0, 0

    for cid in ids:
        try:
            if kind == "photo":
                await context.bot.send_photo(chat_id=cid, photo=file_id, caption=caption)
            elif kind == "video":
                await context.bot.send_video(chat_id=cid, video=file_id, caption=caption)
            elif kind == "animation":
                await context.bot.send_animation(chat_id=cid, animation=file_id, caption=caption)
            elif kind == "document":
                await context.bot.send_document(chat_id=cid, document=file_id, caption=caption)
            else:
                await context.bot.send_message(chat_id=cid, text=caption)
            sent += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)

    await query.message.reply_text(f"✅ Рассылка завершена. Отправлено: {sent}, ошибок: {fail}")
    return ConversationHandler.END


async def broadcast_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Отменить рассылку", callback_data="cancel_broadcast")]
    ])
    await query.message.reply_text("Пришли исправленный текст и/или медиа.", reply_markup=keyboard)
    return BROADCAST_WAIT_CONTENT


async def broadcast_cancel_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("🚫 Рассылка отменена.")
    return ConversationHandler.END


async def broadcast_cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Рассылка отменена.")
    return ConversationHandler.END


def add_broadcast_handlers(app):
    conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start)],
        states={
            BROADCAST_WAIT_CONTENT: [MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_collect)],
            BROADCAST_CONFIRM: [
                CallbackQueryHandler(broadcast_confirm, pattern="^confirm_broadcast$"),
                CallbackQueryHandler(broadcast_edit, pattern="^edit_broadcast$"),
                CallbackQueryHandler(broadcast_cancel_button, pattern="^cancel_broadcast$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", broadcast_cancel_command),
            CallbackQueryHandler(broadcast_cancel_button, pattern="^cancel_broadcast$"),
        ],
    )
    app.add_handler(conv)


# -----------------------------------
#  Основной запуск
# -----------------------------------
def main():
    token = os.environ.get("BOT_TOKEN")
    public_url = os.environ.get("PUBLIC_URL").rstrip("/")
    secret = os.environ.get("WEBHOOK_SECRET")
    if not all([token, public_url, secret]):
        raise RuntimeError("Не заданы BOT_TOKEN / PUBLIC_URL / WEBHOOK_SECRET")

    app = ApplicationBuilder().token(token).build()

    reg_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAIT_GO: [CallbackQueryHandler(on_go_pressed, pattern="^go$")],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)],
            ASK_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_count)],
        },
        fallbacks=[],
    )
    app.add_handler(reg_conv)
    app.add_handler(CallbackQueryHandler(on_kaif_pressed, pattern="^kaif$"))

    add_broadcast_handlers(app)
    app.add_handler(CommandHandler("stats", lambda u, c: u.message.reply_text(f"Подписчиков: {len(all_chat_ids())}")))

    app.post_init = post_init

    port = int(os.environ.get("PORT", "10000"))
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=secret,
        secret_token=secret,
        webhook_url=f"{public_url}/{secret}",
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()