"""
МОДУЛЬ ЗАГРУЗКИ ДАННЫХ
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import streamlit as st
import math
import numpy as np
import matplotlib.pyplot as plt
import os
from sqlalchemy import text
from db_administration.connection import get_db_engine


# @st.cache_data(ttl=3600)
def load_data(source_url: str) -> pd.DataFrame:
    if not os.path.exists(source_url):
        raise FileNotFoundError(f"Файл не найден: {source_url}")
    
    data = pd.read_csv(source_url, encoding='utf-8')
    return data

def load_to_staging():
    engine = get_db_engine()

    with engine.begin() as connection:

        # columns = connection.execute(
        #     text("""
        #         SELECT COLUMN_NAME
        #         FROM information_schema.columns
        #         WHERE table_schema = 'source' AND TABLE_NAME = 'music_tracks'
        #     """).fetchall()
        # )

        connection.execute(
            text("CREATE SCHEMA IF NOT EXISTS staging")
        )

        # создаем табл по структуре source
        connection.execute(
            text(
            "CREATE TABLE IF NOT EXISTS staging.music_tracks (LIKE"
            " source.music_tracks INCLUDING ALL, dt DATE)"
            )
        )

        # очистка staging перед повторной загрузкой
        connection.execute(
            text("TRUNCATE TABLE staging.music_tracks")
        )

        # переносим все записи без преобразований
        connection.execute(
            text("""
                INSERT INTO staging.music_tracks 
                SELECT *, 
                    CASE LOWER(BTRIM("Day"))
                        WHEN 'monday'    THEN DATE '2025-01-06'
                        WHEN 'wednesday' THEN DATE '2025-01-08'
                        WHEN 'friday'    THEN DATE '2025-01-10'
                        WHEN 'tuesday'   THEN DATE '2025-01-07'
                        WHEN 'thursday'  THEN DATE '2025-01-09'
                        WHEN 'saturday'  THEN DATE '2025-01-11'
                        WHEN 'sunday'    THEN DATE '2025-01-12'
                        ELSE NULL
                    END AS dt
                FROM source.music_tracks
            """)
        )

        source_count = connection.execute(
            text("SELECT COUNT(*) FROM source.music_tracks")
        ).scalar()

        staging_count = connection.execute(
            text("SELECT COUNT(*) FROM staging.music_tracks")
        ).scalar()

    print(f"Записей в SOURCE: {source_count}")
    print(f"Записей в STAGING: {staging_count}")

    if source_count == staging_count:
        print("[Успех] Данные успешно перенесены в STAGING.")
    else:
        print("[Ошибка] Количество записей в слоях не совпадает.")

def load_to_ods(p_sdt: str, p_edt: str):
    # Инкрементальная загрузка данных из STAGING в ODS за период [p_sdt; p_edt].
    # Параметры принимаются в формате строк 'YYYY-MM-DD'.
    engine = get_db_engine()

    print(f"\n[ODS] Начало загрузки за период c {p_sdt} по {p_edt}")

    with engine.begin() as connection:
        # 1. Создание схемы и таблицы
        connection.execute(
            text("CREATE SCHEMA IF NOT EXISTS ods")
        )
        connection.execute(
            text("""
            CREATE TABLE IF NOT EXISTS ods.music_tracks (
            LIKE staging.music_tracks INCLUDING ALL)
            """)
        )

        # 2. Удаление из ODS ранее загруженных данных за указанный период (Идемпотентность)
        delete_query = text("DELETE FROM ods.music_tracks WHERE dt >= :sdt AND dt <= :edt")
        deleted_rows = connection.execute(delete_query, {"sdt": p_sdt, "edt": p_edt}).rowcount
        print(f"[ODS] Удалено {deleted_rows} старых записей за период.")
        
        # запросы для очистки
        cleaning_rules_querys = text("""
            
            -- 0: фильтрация STAGING по датам периода
            WITH base_data AS (
                SELECT 
                    BTRIM("Unnamed: 0") AS record_id,
                    BTRIM("  userID")    AS user_id,
                    BTRIM("Track")     AS track,
                    BTRIM("artist")    AS artist,
                    BTRIM("genre")     AS genre,
                    BTRIM("  City  ")      AS city,
                    BTRIM("time")      AS time,
                    BTRIM("Day")       AS day,
                    dt
                FROM staging.music_tracks
                WHERE dt >= :sdt AND dt <= :edt
            ),

            -- RULE-01: пропущенный значение userid
            rule_01 AS (
                SELECT * FROM base_data
                WHERE user_id IS NOT NULL AND user_id != ''
            ),

            -- RULE-02: пропущенное значение ["Track", "artist", "genre"]
            rule_02 AS (
                SELECT
                    record_id, user_id, time, day, dt, city
                    COALESCE(NULLIF(track, ''), 'unknown') AS track,
                    COALESCE(NULLIF(artist, ''), 'unknown') AS artist,
                    COALESCE(NULLIF(genre, ''), 'unknown') AS genre
                FROM rule_01
            ),

            -- RULE-03: пропущенное значение ["City"]
            rule_03 AS (
                SELECT
                    record_id, user_id, time, day, dt, track, artist, genre,
                    COALESCE(
                        NULLIF(city, ''), 
                        FIRST_VALUE(NULLIF(city, '')) OVER(
                            PARTITION BY user_id 
                            ORDER BY dt
                            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                        ),
                        'unknown'
                    ) AS city
                FROM rule_02
            ),

            -- RULE-04: дубликат записи
            rule_04 AS (
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER (
                        PARTITION BY record_id, user_id, track, artist, genre, city, time, day 
                        ORDER BY record_id
                    ) as rn FROM rule_03
                ) t WHERE t.rn = 1
            ),

            -- RULE-05: некорректное значение времени
            rule_05 AS (
                SELECT record_id, user_id, track, artist, genre, city, day, dt,
                CASE WHEN time ~ '^([0-1][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$' THEN time ELSE '00:00:00' END AS time
            FROM rule_04
            ),

            -- RULE-06: несогласованная категория
            rule_06 AS (
                SELECT record_id, user_id, track, artist, genre, city, time, dt,
                CASE WHEN LOWER(day) IN ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday') THEN LOWER(day) ELSE 'unknown' END AS day
            FROM rule_05
            ),

            -- RULE-07: Телепортация (уникальные города)
            rule_07 AS (
                SELECT record_id, user_id, track, artist, genre, city, time, day, dt
                FROM (
                    SELECT *, DENSE_RANK() OVER (PARTITION BY user_id, dt ORDER BY city) + 
                              DENSE_RANK() OVER (PARTITION BY user_id, dt ORDER BY city DESC) - 1 as unique_cities
                    FROM rule_06
                ) t WHERE unique_cities = 1
            )

            -- Финальный выбор данных из конвейера для вставки
            SELECT record_id, user_id, track, artist, genre, city, time, day, dt 
            FROM rule_07
        """)
        
        inserted_rows = connection.execute(cleaning_rules_querys, {"sdt": p_sdt, "edt": p_edt}).rowcount
        print(f"[ODS] Успешно загружено и очищено {inserted_rows} строк.")

        # 3. Использование временного объекта для фильтрации и очистки
        connection.execute(text("DROP TABLE IF EXISTS temp_staging_filtered"))
        
        # Загружаем срез данных во временную таблицу
        create_temp_query = text("""
            CREATE TEMP TABLE temp_staging_filtered AS
            SELECT * FROM staging.music_tracks 
            WHERE dt >= :sdt AND dt <= :edt
        """)
        connection.execute(create_temp_query, {"sdt": p_sdt, "edt": p_edt})

        # 4. Применение разработанных правил очистки
        
if __name__ == "__main__":
    df = load_data("music_project.csv")
    print(df.columns)
 
