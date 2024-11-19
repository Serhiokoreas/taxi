from config import ADMIN_IDS

def is_admin(user_id):
    """Проверить, является ли пользователь админом"""
    return user_id in ADMIN_IDS

def broadcast_message(context, message):
    """Рассылка сообщения всем пользователям"""
    query = "SELECT user_id FROM users WHERE banned = 0"
    user_ids = execute_query(query, fetchall=True)
    if not user_ids:
        return

    for user_id in user_ids:
        try:
            context.bot.send_message(chat_id=user_id[0], text=message)
        except Exception as e:
            print(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
