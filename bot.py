import os
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputFile
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
import openpyxl
from openpyxl import Workbook

WAIT_GO, ASK_NAME, ASK_COUNT = range(3)
EXCEL_FILE = "participants.xlsx"

def ensure_excel():
    if not os.path.exists(EXCEL_FILE):
        wb = Workbook()
        ws = wb.active
        ws.title = "Записи"
        ws.append(["Время", "Telegram ID", "Юзернейм", "Имя", "Количество"])
        wb.save(EXCEL_FILE)

ensure_excel()

# ========== Основные шаги ==========

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
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Отлично. Подскажи, как тебя зовут")
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

    wb = openpyxl.load_workbook(EXCEL_FILE)
    ws = wb.active
    user = update.effective_user
    tg_id = user.id if user else ""
    username = f"@{user.username}" if user and user.username else ""
    ws.append([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tg_id, username, name, count])
    wb.save(EXCEL_FILE)

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


# ========== Кнопка "Кайф" ==========

async def on_kaif_pressed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    msg5 = (
        "Раз кайф, то подпишись на мою телегу :)\n\n"
        "Там будут все новости по концерту — "
        "[тык](https://t.me/+xkFENZGOXv44N2Zi)"
    )

    image_path = "poster.jpg"  # путь к картинке
    if os.path.exists(image_path):
        with open(image_path, "rb") as img:
            await query.message.reply_photo(
                photo=InputFile(img),
                caption=msg5,
                parse_mode="Markdown",
            )
    else:
        await query.message.reply_text(msg5, parse_mode="Markdown")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Регистрация отменена.")
    return ConversationHandler.END


def main():
    TOKEN = "8448919693:AAGlEVCTDmQONmU1bsXftzPhIgj4cwJsM9w"
    app = ApplicationBuilder().token(TOKEN).build()

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

    app.run_polling()


if __name__ == "__main__":
    main()