import mysql.connector
from mysql.connector import Error
from config import DB_CONFIG


def get_connection():
    """Установить соединение с базой данных"""
    try:
        connection = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database']
        )
        return connection
    except Error as e:
        print(f"Ошибка подключения к базе данных: {e}")
        return None


def execute_query(query, params=(), fetchone=False, fetchall=False):
    """Выполнение SQL-запроса"""
    connection = get_connection()
    if not connection:
        return None

    try:
        cursor = connection.cursor()
        cursor.execute(query, params)
        connection.commit()

        if fetchone:
            result = cursor.fetchone()
        elif fetchall:
            result = cursor.fetchall()
        else:
            result = None

        cursor.close()
        connection.close()
        return result
    except Error as e:
        print(f"Ошибка выполнения запроса: {e}")
        return None


# Программа лояльности
def increment_loyalty_points(user_id):
    """Увеличить баллы лояльности пользователя"""
    query = """
        INSERT INTO users (user_id, loyalty_points) VALUES (%s, 1)
        ON DUPLICATE KEY UPDATE loyalty_points = loyalty_points + 1
    """
    execute_query(query, (user_id,))


def check_loyalty_reward(user_id):
    """Проверить, достиг ли пользователь награды"""
    query = "SELECT loyalty_points FROM users WHERE user_id = %s"
    points = execute_query(query, (user_id,), fetchone=True)

    if points and points[0] >= 5:  # Каждая 6-я поездка — бесплатная
        reset_loyalty_points(user_id)
        return True
    return False


def reset_loyalty_points(user_id):
    """Сбросить баллы лояльности после награды"""
    query = "UPDATE users SET loyalty_points = 0 WHERE user_id = %s"
    execute_query(query, (user_id,))


# Пользователи
def ban_user(user_id):
    """Заблокировать пользователя"""
    query = "UPDATE users SET banned = 1 WHERE user_id = %s"
    execute_query(query, (user_id,))


def unban_user(user_id):
    """Разблокировать пользователя"""
    query = "UPDATE users SET banned = 0 WHERE user_id = %s"
    execute_query(query, (user_id,))
