import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from database import execute_query, increment_loyalty_points, check_loyalty_reward
from scheduler import schedule_trip_reminder
from config import BOT_TOKEN, TRIP_TYPES, MAX_SEATS, ADMIN_IDS
from utils import is_admin, broadcast_message

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


# Функционал пользователя
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начальное сообщение"""
    keyboard = [
        [InlineKeyboardButton("Посмотреть расписание", callback_data='view_schedule')],
        [InlineKeyboardButton("Забронировать место", callback_data='book_seat')],
        [InlineKeyboardButton("Мои бронирования", callback_data='my_bookings')],
        [InlineKeyboardButton("Условия лояльности", callback_data='loyalty_info')],
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
            "SELECT id, date, passengers FROM trips WHERE trip_type = %s",
            (trip_type,),
            fetchall=True
        )
        if trips:
            for trip_id, date, passengers in trips:
                passengers_list = passengers.split(',') if passengers else []
                available_seats = MAX_SEATS - len(passengers_list)
                schedule_text += f"📆 Дата: {date}, свободно мест: {available_seats} (ID поездки: {trip_id})\n"
        else:
            schedule_text += "Нет запланированных поездок\n"
        schedule_text += "\n"

    keyboard = [[InlineKeyboardButton("Назад", callback_data='start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=schedule_text,
        reply_markup=reply_markup
    )


async def loyalty_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о программе лояльности"""
    query = update.callback_query
    user_id = query.from_user.id
    points = execute_query(
        "SELECT loyalty_points FROM users WHERE user_id = %s",
        (user_id,),
        fetchone=True
    )
    points_text = points[0] if points else 0
    text = (
        f"🏆 Условия программы лояльности:\n"
        f"Каждая 6-я поездка — бесплатно!\n\n"
        f"Ваши текущие баллы: {points_text}\n"
    )
    keyboard = [[InlineKeyboardButton("Назад", callback_data='start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup
    )


async def book_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Забронировать место на поездку"""
    query = update.callback_query
    user_id = query.from_user.id
    trip_type = query.data.split('_')[-1]  # Получаем направление ('to_ufa' или 'from_ufa')

    trips = execute_query(
        "SELECT id, date, passengers FROM trips WHERE trip_type = %s",
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
        [InlineKeyboardButton(f"Дата: {trip[1]} (ID: {trip[0]})",
                              callback_data=f"confirm_booking_{trip_type}_{trip[0]}")]
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
    trip_type, trip_id = data[2], data[3]
    user_id = query.from_user.id

    trip = execute_query(
        "SELECT passengers FROM trips WHERE id = %s",
        (trip_id,),
        fetchone=True
    )
    passengers = trip[0].split(',') if trip and trip[0] else []

    if len(passengers) >= MAX_SEATS:
        await query.edit_message_text(
            text="❌ К сожалению, на эту поездку больше нет мест.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data='book_seat')]])
        )
        return

    context.user_data['booking'] = {'trip_type': trip_type, 'trip_id': trip_id}
    await query.edit_message_text(text="📍 Укажите ваш адрес отправления (ответным сообщением):")


async def handle_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение адреса бронирования"""
    address = update.message.text
    booking = context.user_data.get('booking')
    if not booking:
        await update.message.reply_text("❌ Ошибка: отсутствуют данные бронирования.")
        return

    trip_type = booking['trip_type']
    trip_id = booking['trip_id']
    user_id = update.message.from_user.id

    execute_query(
        "INSERT INTO bookings (user_id, trip_id, address) VALUES (%s, %s, %s)",
        (user_id, trip_id, address)
    )
    passengers = execute_query(
        "SELECT passengers FROM trips WHERE id = %s",
        (trip_id,),
        fetchone=True
    )[0]
    updated_passengers = f"{passengers},{user_id}" if passengers else str(user_id)
    execute_query(
        "UPDATE trips SET passengers = %s WHERE id = %s",
        (updated_passengers, trip_id)
    )

    # Система лояльности
    increment_loyalty_points(user_id)
    if check_loyalty_reward(user_id):
        await update.message.reply_text("🎉 Вы получили бесплатную поездку! Поздравляем!")

    schedule_trip_reminder(context, user_id, f"{TRIP_TYPES[trip_type]} (ID: {trip_id})", trip_id)
    await update.message.reply_text("✅ Бронирование успешно выполнено!")


# Админ-функционал
async def admin_announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сделать объявление"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Доступ запрещен.")
        return

    announcement = ' '.join(context.args)
    broadcast_message(context, announcement)
    await update.message.reply_text("📢 Объявление отправлено всем пользователям.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ошибок"""
    logging.error(msg="Exception while handling update:", exc_info=context.error)
    if update and isinstance(update, Update) and update.message:
        await update.message.reply_text("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")


# Основной запуск
def main():
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(show_schedule, pattern='^view_schedule$'))
    application.add_handler(CallbackQueryHandler(loyalty_info, pattern='^loyalty_info$'))
    application.add_handler(CommandHandler("announce", admin_announce))

    # Обработчик ошибок
    application.add_error_handler(error_handler)

    application.run_polling()



if __name__ == "__main__":
    main()
