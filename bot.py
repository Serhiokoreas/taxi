import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from database import execute_query
from scheduler import schedule_trip_reminder
from config import BOT_TOKEN, TRIP_TYPES, MAX_SEATS

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начальное сообщение"""
    keyboard = [
        [InlineKeyboardButton("Посмотреть расписание", callback_data='view_schedule')],
        [InlineKeyboardButton("Забронировать место", callback_data='book_seat')],
        [InlineKeyboardButton("Мои бронирования", callback_data='my_bookings')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🚖 Добро пожаловать в систему бронирования такси! Выберите действие:",
        reply_markup=reply_markup
    )


async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать расписание поездок"""
    query = update.callback_query
    schedule_text = "📅 Расписание поездок:\n\n"

    for trip_type, trip_name in TRIP_TYPES.items():
        schedule_text += f"{trip_name}:\n"
        trips = execute_query(
            "SELECT date, passengers FROM trips WHERE trip_type = %s",
            (trip_type,),
            fetchall=True
        )
        if trips:
            for date, passengers in trips:
                passengers_list = passengers.split(',') if passengers else []
                available_seats = MAX_SEATS - len(passengers_list)
                schedule_text += f"📆 Дата: {date}, свободно мест: {available_seats}\n"
        else:
            schedule_text += "Нет запланированных поездок\n"
        schedule_text += "\n"

    keyboard = [[InlineKeyboardButton("Назад", callback_data='start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=schedule_text,
        reply_markup=reply_markup
    )


async def handle_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка бронирования"""
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("В Уфу", callback_data='book_to_ufa')],
        [InlineKeyboardButton("Из Уфы", callback_data='book_from_ufa')],
        [InlineKeyboardButton("Назад", callback_data='start')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="Выберите направление:",
        reply_markup=reply_markup
    )


async def book_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Забронировать место на поездку"""
    query = update.callback_query
    user_id = query.from_user.id
    trip_type = query.data.split('_')[-1]  # Получаем направление ('to_ufa' или 'from_ufa')

    trips = execute_query(
        "SELECT date, passengers FROM trips WHERE trip_type = %s",
        (trip_type,),
        fetchall=True
    )

    if not trips:
        await query.edit_message_text(
            text="❌ Нет доступных поездок для этого направления.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data='book_seat')]])
        )
        return

    keyboard = [
        [InlineKeyboardButton(f"Дата: {trip[0]}", callback_data=f"confirm_booking_{trip_type}_{trip[0]}")]
        for trip in trips
    ]
    keyboard.append([InlineKeyboardButton("Назад", callback_data='book_seat')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="Выберите дату поездки:",
        reply_markup=reply_markup
    )


async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение бронирования"""
    query = update.callback_query
    data = query.data.split('_')
    trip_type, trip_date = data[2], data[3]
    user_id = query.from_user.id

    trip = execute_query(
        "SELECT passengers FROM trips WHERE trip_type = %s AND date = %s",
        (trip_type, trip_date),
        fetchone=True
    )
    passengers = trip[0].split(',') if trip and trip[0] else []

    if len(passengers) >= MAX_SEATS:
        await query.edit_message_text(
            text="❌ К сожалению, на эту поездку больше нет мест.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data='book_seat')]])
        )
        return

    context.user_data['booking'] = {'trip_type': trip_type, 'trip_date': trip_date}
    await query.edit_message_text(text="📍 Укажите ваш адрес отправления (ответным сообщением):")


async def handle_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение адреса бронирования"""
    address = update.message.text
    booking = context.user_data.get('booking')
    if not booking:
        await update.message.reply_text("❌ Ошибка: отсутствуют данные бронирования.")
        return

    trip_type = booking['trip_type']
    trip_date = booking['trip_date']
    user_id = update.message.from_user.id

    execute_query(
        "INSERT INTO bookings (user_id, trip_type, date, address) VALUES (%s, %s, %s, %s)",
        (user_id, trip_type, trip_date, address)
    )
    passengers = execute_query(
        "SELECT passengers FROM trips WHERE trip_type = %s AND date = %s",
        (trip_type, trip_date),
        fetchone=True
    )[0]
    updated_passengers = f"{passengers},{user_id}" if passengers else str(user_id)
    execute_query(
        "UPDATE trips SET passengers = %s WHERE trip_type = %s AND date = %s",
        (updated_passengers, trip_type, trip_date)
    )

    schedule_trip_reminder(context, user_id, f"{TRIP_TYPES[trip_type]} на {trip_date}", trip_date)
    await update.message.reply_text("✅ Бронирование успешно выполнено!")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ошибок"""
    logging.error(msg="Exception while handling update:", exc_info=context.error)
    if update and isinstance(update, Update) and update.message:
        await update.message.reply_text("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")


def main():
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(show_schedule, pattern='^view_schedule$'))
    application.add_handler(CallbackQueryHandler(handle_booking, pattern='^book_seat$'))
    application.add_handler(CallbackQueryHandler(book_trip, pattern='^book_to_ufa$|^book_from_ufa$'))
    application.add_handler(CallbackQueryHandler(confirm_booking, pattern='^confirm_booking_.*'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_address))

    application.add_error_handler(error_handler)

    application.run_polling()


if __name__ == "__main__":
    main()
