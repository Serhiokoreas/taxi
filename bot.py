import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from database import execute_query, increment_loyalty_points, check_loyalty_reward, ban_user, unban_user
from scheduler import schedule_trip_reminder
from config import BOT_TOKEN, TRIP_TYPES, MAX_SEATS, ADMIN_IDS
from utils import is_admin, broadcast_message

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


# Функции для пользователей
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начальное сообщение"""
    user_id = update.message.from_user.id

    # Если пользователь - админ
    if is_admin(user_id):
        keyboard = [
            [InlineKeyboardButton("📋 Управление расписанием", callback_data='admin_schedule')],
            [InlineKeyboardButton("🔒 Управление пользователями", callback_data='admin_users')],
            [InlineKeyboardButton("📢 Сделать объявление", callback_data='admin_announcement')],
            [InlineKeyboardButton("📞 Просмотреть пассажиров", callback_data='admin_view_passengers')],
            [InlineKeyboardButton("↩️ Выйти из админменю", callback_data='start')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Добро пожаловать в админпанель. Выберите действие:", reply_markup=reply_markup)
        return

    # Обычное меню для клиентов
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


async def book_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка запроса на бронирование"""
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
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data='start')]])
        )
        return

    # Предложить выбор даты поездки
    keyboard = [
        [InlineKeyboardButton(f"Дата: {trip[1]} (ID: {trip[0]})",
                              callback_data=f"confirm_booking_{trip_type}_{trip[0]}")]
        for trip in trips
    ]
    keyboard.append([InlineKeyboardButton("Назад", callback_data='start')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="Выберите дату поездки:",
        reply_markup=reply_markup
    )


async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение бронирования места"""
    query = update.callback_query
    data = query.data.split('_')
    trip_type, trip_id = data[2], data[3]
    user_id = query.from_user.id

    # Уведомить о бронировании нескольких мест
    context.user_data['trip_id'] = trip_id
    keyboard = [
        [InlineKeyboardButton("Забронировать 2 места", callback_data='multi_booking_2')],
        [InlineKeyboardButton("Забронировать 3 места", callback_data='multi_booking_3')],
        [InlineKeyboardButton("Забронировать 4 места", callback_data='multi_booking_4')],
        [InlineKeyboardButton("Отменить", callback_data='cancel_booking')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=(
            "🚖 Если вы хотите забронировать более 1 места, свяжитесь с нами по телефону +79999999999.\n"
            "Выберите количество мест или отмените запрос:"
        ),
        reply_markup=reply_markup
    )


async def handle_multi_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка бронирования нескольких мест"""
    query = update.callback_query
    admin_id = ADMIN_IDS[0]
    user_id = query.from_user.id
    num_seats = int(query.data.split('_')[-1])
    trip_id = context.user_data.get('trip_id')

    # Уведомить админа
    context.bot.send_message(
        chat_id=admin_id,
        text=f"❗ Пользователь {user_id} запросил бронирование {num_seats} мест на поездку ID {trip_id}.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Подтвердить {num_seats} места",
                                  callback_data=f"admin_confirm_{trip_id}_{num_seats}")],
            [InlineKeyboardButton("Отменить", callback_data='admin_cancel_multi_booking')]
        ])
    )

    await query.edit_message_text("Запрос на бронирование отправлен администратору.")


# Административные функции
async def admin_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление расписанием"""
    query = update.callback_query
    trips = execute_query("SELECT id, trip_type, date FROM trips", fetchall=True)
    if not trips:
        await query.edit_message_text("Расписание пусто.")
        return

    text = "📋 Текущее расписание:\n\n"
    for trip_id, trip_type, date in trips:
        text += f"ID {trip_id}: {TRIP_TYPES[trip_type]}, дата {date}\n"

    keyboard = [[InlineKeyboardButton("Добавить поездку", callback_data='add_trip')],
                [InlineKeyboardButton("Удалить поездку", callback_data='remove_trip')],
                [InlineKeyboardButton("Назад", callback_data='start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)


async def admin_view_passengers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр номеров телефонов пассажиров"""
    query = update.callback_query
    passengers = execute_query(
        "SELECT bookings.user_id, users.phone FROM bookings "
        "JOIN users ON bookings.user_id = users.user_id", fetchall=True
    )
    if not passengers:
        await query.edit_message_text("Нет пассажиров для отображения.")
        return

    text = "📞 Список пассажиров:\n\n"
    for user_id, phone in passengers:
        text += f"ID {user_id}: 📱 {phone}\n"

    await query.edit_message_text(text)


# Основной запуск
def main():
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(book_trip, pattern='^book_to_ufa$|^book_from_ufa$'))
    application.add_handler(CallbackQueryHandler(confirm_booking, pattern='^confirm_booking_.*'))
    application.add_handler(CallbackQueryHandler(handle_multi_booking, pattern='^multi_booking_.*'))
    application.add_handler(CallbackQueryHandler(admin_schedule, pattern='^admin_schedule$'))
    application.add_handler(CallbackQueryHandler(admin_view_passengers, pattern='^admin_view_passengers$'))

    application.run_polling()


if __name__ == "__main__":
    main()
