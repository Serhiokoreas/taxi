from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

scheduler = BackgroundScheduler()

def schedule_trip_reminder(context, user_id, trip_info, trip_id):
    """Планирование напоминания о поездке"""
    # Допустим, в базе данных у нас хранится дата поездки в формате YYYY-MM-DD
    query = "SELECT date FROM trips WHERE id = %s"
    trip_date = execute_query(query, (trip_id,), fetchone=True)
    if not trip_date:
        return

    job_time = datetime.strptime(trip_date[0], '%Y-%m-%d') - timedelta(hours=1)

    scheduler.add_job(
        send_reminder,
        'date',
        run_date=job_time,
        args=[context, user_id, trip_info]
    )
    scheduler.start()

def send_reminder(context, user_id, trip_info):
    """Отправка напоминания пользователю"""
    context.bot.send_message(
        chat_id=user_id,
        text=f"🚨 Напоминание: ваша поездка {trip_info} начнется через час!"
    )
