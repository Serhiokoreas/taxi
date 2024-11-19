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
