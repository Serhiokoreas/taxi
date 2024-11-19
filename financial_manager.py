from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict
import aiomysql
from db import get_db_connection


@dataclass
class FinancialRecord:
    date: str
    amount: float
    trip_type: str
    discount_applied: float = 0
    bonus_points_used: int = 0


class FinancialManager:
    async def add_trip_record(self, record: FinancialRecord):
        connection = await get_db_connection()
        async with connection.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO financial_records (date, amount, trip_type, discount_applied, bonus_points_used)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (record.date, record.amount, record.trip_type, record.discount_applied, record.bonus_points_used)
            )
        connection.close()

    async def get_average_profit(self, period: str) -> float:
        connection = await get_db_connection()
        async with connection.cursor() as cursor:
            if period == 'day':
                query = "SELECT AVG(amount) FROM financial_records WHERE date = CURDATE()"
            elif period == 'week':
                query = "SELECT AVG(amount) FROM financial_records WHERE WEEK(date) = WEEK(CURDATE())"
            else:
                query = "SELECT AVG(amount) FROM financial_records WHERE MONTH(date) = MONTH(CURDATE())"

            await cursor.execute(query)
            result = await cursor.fetchone()
        connection.close()
        return result[0] if result else 0.0
