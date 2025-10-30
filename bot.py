import os
from datetime import datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
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

# Состояния диалога
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Сообщение 1 + кнопка "Я иду!"
    text = (
        "Добро пожаловать в регистрацию на Презентацию альбома и Birthday party by Damir Mate — 25 ноября!\n\n"
        "Это будет особенный вечер. Я очень рад, что ты решил(а) разделить его со мной.\n\n"
        "Мы презентуем для тебя альбом, сыграем уже вышедшие треки и, конечно, отпразднуем мою дрху вместе в нашем теплом кругу.\n\n"
        "Кликни \"Я иду!\", чтобы зарегистрироваться"
    )
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Я иду!", callback_data="go")]]
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=keyboard)
    else:
        # На всякий, если /start прилетел как callback или что-то странное
        await update.callback_query.message.reply_text(text, reply_markup=keyboard)
    return WAIT_GO


async def on_go_pressed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Сообщение 2
    await query.message.reply_text("Отлично. Подскажи, как тебя зовут")
    return ASK_NAME


async def got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data["name"] = name

    # Сообщение 3
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

    # Сохраняем в Excel
    wb = openpyxl.load_workbook(EXCEL_FILE)
    ws = wb.active

    user = update.effective_user
    tg_id = user.id if user else ""
    username = f"@{user.username}" if user and user.username else ""

    ws.append([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        tg_id,
        username,
        name,
        count
    ])
    wb.save(EXCEL_FILE)

    # Сообщение 4 (+ фраза про запись)
    msg4 = (
        f"Спасибо, {name}!\n\n"
        "Вы записаны на концерт.\n\n"
        "📅 Когда: 25 ноября, 19:00\n"
        "📍 Где: Клуб ТехникаБезОпасности\n"
        "🏠 Адрес: Сущевская улица, 23с10\n"
        "🚇 Метро: Менделеевская\n\n"
        "Буду очень ждать 🫂🤎"
    )
    await update.message.reply_text(msg4)

    # Сообщение 5
    msg5 = (
        "Раз кайф, то подпишись на мою телегу :)\n\n"
        "Там будут все новости по концерту - тык\n"
        "https://t.me/+xkFENZGOXv44N2Zi"
    )
    await update.message.reply_text(msg5)

    return ConversationHandler.END


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

    # На всякий случай ловим нажатия "Я иду!" вне активного диалога
    app.add_handler(CallbackQueryHandler(on_go_pressed, pattern="^go$"))

    app.run_polling()


if __name__ == "__main__":
    main()