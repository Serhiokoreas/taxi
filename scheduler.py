from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

scheduler = BackgroundScheduler()

def schedule_trip_reminder(context, user_id, trip_info, trip_date):
    """Планирование напоминания о поездке"""
    job_time = datetime.strptime(trip_date, '%Y-%m-%d') - timedelta(hours=1)

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
