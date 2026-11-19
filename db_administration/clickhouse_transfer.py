"""
В ClickHouse используем движок MergeTree

Создаем схему и таблицу

"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import clickhouse_connect

from sqlalchemy import text

from db_administration.connection import get_db_engine


def get_clickhouse_client():

    return clickhouse_connect.get_client(
        host="localhost",
        port=8123,
        username="default",
        password="",
        database="default"
    )


def transfer_mart_to_clickhouse():

    pg_engine = get_db_engine()
    ch_client = get_clickhouse_client()

    print("\n[CLICKHOUSE] Начало переноса витрины.")

    # 1. Создание базы и таблицы
    ch_client.command("""
        CREATE DATABASE IF NOT EXISTS analytics
    """)

    ch_client.command("""
        CREATE TABLE IF NOT EXISTS analytics.mart_genre
        (
            date_value Date,
            city_name String,
            genre_name String,
            listening_count UInt64,
            most_listened_song String,
            unique_users UInt64,
            unique_tracks UInt64
        )
        ENGINE = MergeTree()
        ORDER BY (
            date_value,
            city_name,
            genre_name
        )
    """)

    # 2. Чтение данных из PostgreSQL
    df = pd.read_sql_query(
        text("""
            SELECT
                date_value,
                city_name,
                genre_name,
                listening_count,
                most_listened_song,
                unique_users,
                unique_tracks
            FROM mart.mart_genre
            ORDER BY
                date_value,
                city_name,
                genre_name
        """),
        pg_engine
    )

    print(f"[CLICKHOUSE] Получено из PostgreSQL: {len(df)}")

    # 3. Полная очистка целевой витрины
    ch_client.command("""
        TRUNCATE TABLE analytics.mart_genre
    """)

    # 4. Перенос данных
    if not df.empty:
        print(df)
        df["date_value"] = pd.to_datetime(
            df["date_value"]
        ).dt.date

        ch_client.insert_df(
            "mart_genre",
            df,
            database="analytics"
        )

    print(f"[CLICKHOUSE] Перенесено: {len(df)}")

    # 5. Проверка количества записей
    pg_count = len(df)

    ch_count = ch_client.query("""
        SELECT COUNT(*)
        FROM analytics.mart_genre
    """).result_rows[0][0]

    print(f"[POSTGRESQL] Записей: {pg_count}")
    print(f"[CLICKHOUSE] Записей: {ch_count}")

    if pg_count == ch_count:
        print("[SUCCESS] Количество записей совпадает.")
    else:
        raise RuntimeError(
            "Количество записей PostgreSQL и ClickHouse не совпадает."
        )

    print("[CLICKHOUSE] Перенос завершён.")

    ch_client.close()

if __name__ == "__main__":
    transfer_mart_to_clickhouse()