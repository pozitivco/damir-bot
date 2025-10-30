import os
import json
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputFile,
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

# -------- states --------
WAIT_GO, ASK_NAME, ASK_COUNT = range(3)

# -------- Google Sheets setup --------
def gs_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON", "").strip()
    if not creds_json:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON не задан")
    info = json.loads(creds_json)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)

def gs_worksheet():
    sheet_id = os.environ.get("SHEET_ID", "").strip()
    if not sheet_id:
        raise RuntimeError("SHEET_ID не задан")
    gc = gs_client()
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet("Записи")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title="Записи", rows=1000, cols=8)
        ws.append_row(["Время", "Telegram ID", "Юзернейм", "Имя", "Количество"], value_input_option="RAW")
    return ws

# -------- handlers --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("Отлично. Подскажи, как тебя зовут")
    return ASK_NAME

async def got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data["name"] = name
    text = (
        f"Гуд, {name}! 🙌\n\n"
        "Сколько человек будет с тобой?\n"
        "(напиши число — если ты придёшь один/одна, то просто напиши «1»)"
    )
    await update.message.reply_text(text)
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

    name = context.user_data.get("name", "").strip()
    user = update.effective_user
    tg_id = user.id if user else ""
    username = f"@{user.username}" if user and user.username else ""

    # запись в Google Sheets
    ws = gs_worksheet()
    ws.append_row(
        [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            tg_id,
            username,
            name,
            count,
        ],
        value_input_option="RAW",
    )

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
        "Там будут все новости по концерту — "
        "[тык](https://t.me/+xkFENZGOXv44N2Zi)"
    )
    image_path = "poster.jpg"  # положи файл рядом с bot.py (или убери, если не нужен)
    if os.path.exists(image_path):
        with open(image_path, "rb") as img:
            await q.message.reply_photo(photo=InputFile(img), caption=msg5, parse_mode="Markdown")
    else:
        await q.message.reply_text(msg5, parse_mode="Markdown")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Регистрация отменена.")
    return ConversationHandler.END

# -------- app --------
def main():
    token = os.environ.get("BOT_TOKEN", "").strip()
    public_url = os.environ.get("PUBLIC_URL", "").rstrip("/")
    secret = os.environ.get("WEBHOOK_SECRET", "").strip()
    if not token or not public_url or not secret:
        raise RuntimeError("Нужно задать BOT_TOKEN, PUBLIC_URL и WEBHOOK_SECRET в переменных окружения.")

    app = ApplicationBuilder().token(token).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAIT_GO: [CallbackQueryHandler(on_go_pressed, pattern="^go$")],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)],
            ASK_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_count)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(on_go_pressed, pattern="^go$"))
    app.add_handler(CallbackQueryHandler(on_kaif_pressed, pattern="^kaif$"))

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