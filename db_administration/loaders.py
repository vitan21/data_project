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
        print("[STAGING] Данные успешно перенесены в STAGING.")
    else:
        print("[STAGING !Ошибка] Количество записей в слоях не совпадает.")

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
        connection.execute(text("""
        CREATE TABLE IF NOT EXISTS ods.music_tracks (
            record_id BIGINT,
            user_id TEXT,
            track TEXT,
            artist TEXT,
            genre TEXT,
            city TEXT,
            time TEXT,
            day TEXT,
            dt DATE
        )
    """))

        # 2. Удаление из ODS ранее загруженных данных за указанный период
        delete_query = text("DELETE FROM ods.music_tracks WHERE dt >= :sdt AND dt <= :edt")
        deleted_rows = connection.execute(delete_query, {"sdt": p_sdt, "edt": p_edt}).rowcount
        print(f"[ODS] Удалено {deleted_rows} старых записей за период.")
        
        # запросы для очистки
        cleaning_rules_querys = text("""
            
            -- 0: фильтрация STAGING по датам периода
            INSERT INTO ods.music_tracks (record_id, user_id, track, artist, genre, city, time, day, dt)
            WITH base_data AS (
                SELECT 
                    CAST(BTRIM("Unnamed: 0") AS BIGINT) AS record_id,
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
                    record_id, user_id, time, day, dt, city,
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


            -- RULE-04: некорректное значение времени
            rule_04 AS (
                SELECT record_id, user_id, track, artist, genre, city, day, dt,
                CASE WHEN time ~ '^([0-1][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$' THEN time ELSE '00:00:00' END AS time
            FROM rule_03
            ),

            -- RULE-05: несогласованная категория
            rule_05 AS (
                SELECT record_id, user_id, track, artist, genre, city, time, dt,
                CASE 
                    WHEN LOWER(day) IN ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday') 
                        THEN LOWER(day) 
                        ELSE 'unknown' 
                    END AS day
            FROM rule_04
            ),

            -- RULE-06: Телепортация (уникальные города)
            rule_06 AS (
                SELECT record_id, user_id, track, artist, genre, city, time, day, dt
                FROM (
                    SELECT *, DENSE_RANK() OVER (PARTITION BY user_id, dt ORDER BY city) + 
                              DENSE_RANK() OVER (PARTITION BY user_id, dt ORDER BY city DESC) - 1 as unique_cities
                    FROM rule_05
                ) t WHERE unique_cities = 1
            ),

            -- RULE-07: дубликат записи
            rule_07 AS (
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER (
                        PARTITION BY user_id, track, artist, genre, city, time, day, dt
                        ORDER BY record_id
                    ) AS rn FROM rule_06
                ) t WHERE t.rn = 1
            )

            -- Финальный выбор данных из конвейера для вставки
            SELECT record_id, user_id, track, artist, genre, city, time, day, dt 
            FROM rule_07
            ORDER BY record_id ASC
        """)
        
        inserted_rows = connection.execute(cleaning_rules_querys, {"sdt": p_sdt, "edt": p_edt}).rowcount
        print(f"[ODS] Успешно загружено и очищено {inserted_rows} строк.")

       
def load_to_dds():
    engine = get_db_engine()
    print(f"\n[DDS] Начало загрузки")

    with engine.begin() as connection:
        connection.execute(text(
            "DROP SCHEMA IF EXISTS dds CASCADE"
        ))
        connection.execute(
            text("CREATE SCHEMA IF NOT EXISTS dds")
        )
        # создание таблиц
        connection.execute(
            text("""
                -- пользователи
                CREATE TABLE IF NOT EXISTS dds.users (
                    user_id TEXT UNIQUE NOT NULL
                );
                -- артисты
                CREATE TABLE IF NOT EXISTS dds.artists (
                    artist_id SERIAL PRIMARY KEY,
                    artist_name TEXT UNIQUE NOT NULL
                );
                -- жанры
                CREATE TABLE IF NOT EXISTS dds.genres (
                    genre_id SERIAL PRIMARY KEY,
                    genre_name TEXT UNIQUE NOT NULL
                );
                -- треки
                CREATE TABLE IF NOT EXISTS dds.tracks (
                    track_id SERIAL PRIMARY KEY,
                    track_name TEXT NOT NULL,
                    artist_id INTEGER REFERENCES dds.artists(artist_id),
                    genre_id INTEGER REFERENCES dds.genres(genre_id),
                    UNIQUE (track_name, artist_id, genre_id)
                );
                -- города
                CREATE TABLE IF NOT EXISTS dds.cities (
                    city_id SERIAL PRIMARY KEY,
                    city_name TEXT UNIQUE NOT NULL
                );
                -- время
                CREATE TABLE IF NOT EXISTS dds.datetime (
                    datetime_id SERIAL PRIMARY KEY,
                    date_value DATE NOT NULL,
                    time_value TIME NOT NULL,
                    day_name TEXT NOT NULL,
                    UNIQUE (date_value, time_value, day_name)
                );
                CREATE TABLE dds.facts (
                    fact_id BIGSERIAL PRIMARY KEY,
                    user_id TEXT REFERENCES dds.users(user_id),
                    track_id INTEGER REFERENCES dds.tracks(track_id),
                    city_id INTEGER REFERENCES dds.cities(city_id),
                    datetime_id INTEGER REFERENCES dds.datetime(datetime_id),
                    record_id BIGINT
                );

            """)
        )
        print(f"[DDS] Создание схемы и таблиц")

        # загрузка данных в таблицы
        # пользователи
        result = connection.execute(text("""
            INSERT INTO dds.users (user_id)
            SELECT DISTINCT
                user_id
            FROM ods.music_tracks
        """))
        print(f"[DDS] users: добавлено {result.rowcount} записей")

        # артисты
        result = connection.execute(text("""
            INSERT INTO dds.artists (artist_name)
            SELECT DISTINCT
                artist
            FROM ods.music_tracks
        """))
        print(f"[DDS] artists: добавлено {result.rowcount} записей")

        # жанры
        result = connection.execute(text("""
            INSERT INTO dds.genres (genre_name)
            SELECT DISTINCT
                genre
            FROM ods.music_tracks
        """))
        print(f"[DDS] genres: добавлено {result.rowcount} записей")

        # треки
        result = connection.execute(text("""
            INSERT INTO dds.tracks (
                track_name,
                artist_id,
                genre_id)
            SELECT DISTINCT
                a.track,
                b.artist_id,
                c.genre_id
            FROM ods.music_tracks AS a
            INNER JOIN dds.artists b
                ON b.artist_name = a.artist
            INNER JOIN dds.genres c
                ON c.genre_name = a.genre
        """))
        print(f"[DDS] tracks: добавлено {result.rowcount} записей")

        # города
        result = connection.execute(text("""
            INSERT INTO dds.cities (city_name)
            SELECT DISTINCT
                city
            FROM ods.music_tracks
        """))
        print(f"[DDS] cities: добавлено {result.rowcount} записей")

        # время
        result = connection.execute(text("""
            INSERT INTO dds.datetime (
                date_value,
                time_value,
                day_name    
            )
            SELECT DISTINCT
                dt,
                time::time,
                day
            FROM ods.music_tracks
        """))
        print(f"[DDS] datetime: добавлено {result.rowcount} записей")

        # facts
        result = connection.execute(text("""
            INSERT INTO dds.facts (
                record_id,
                user_id,
                track_id,
                city_id,
                datetime_id
            )
            SELECT
                o.record_id,
                u.user_id,
                t.track_id,
                c.city_id,
                d.datetime_id
            FROM ods.music_tracks o

            INNER JOIN dds.users u ON
                u.user_id = o.user_id

            INNER JOIN dds.artists a ON    
                a.artist_name = o.artist
            
            INNER JOIN dds.genres g ON
                g.genre_name = o.genre
                
            INNER JOIN dds.tracks t ON
                t.track_name = o.track
                AND t.artist_id = a.artist_id
                AND t.genre_id = g.genre_id

            INNER JOIN dds.cities c ON
                c.city_name = o.city

            INNER JOIN dds.datetime d ON
                d.date_value = o.dt
                AND d.time_value = o.time::time
                AND d.day_name = o.day
        """))
        print(
            f"[DDS] facts: добавлено {result.rowcount} фактов]"
        )
        # проверка кол-ва записей
        tables = [
            "users",
            "artists",
            "genres",
            "tracks",
            "cities",
            "datetime"
        ]

        print("\n[DDS] Загрузка завершена. Итоговое количество записей:")
        for table in tables:
            count = connection.execute(
                text(f"SELECT COUNT(*) FROM dds.{table}")
            ).scalar()
            print(f"{table}: {count}")

        print("\n---ПРОВЕРКА---")

        
        # 1 RULE-01: пропущенный значение userid
        user_id_is_null = connection.execute(text("""
            SELECT COUNT(*)
            FROM dds.users
            WHERE user_id IS NULL
        """)).scalar()
        print("Пропущен пользователь: \t", user_id_is_null)

        # 2 RULE-02: пропущенное значение ["track", "artists", "genres"]
        values_is_null = connection.execute(text("""
            SELECT
                (SELECT COUNT(*) FROM dds.tracks WHERE track_name IS NULL) AS null_tracks,
                (SELECT COUNT(*) FROM dds.artists WHERE artist_name IS NULL) AS null_artists,
                (SELECT COUNT(*) FROM dds.genres WHERE genres IS NULL) AS null_genres
        """)).fetchone()

        print(
            f"\nПропуски - треки: {values_is_null.null_tracks}"
            f"\nПропуски - артисты: {values_is_null.null_artists}"
            f"\nПропуски - жанры: {values_is_null.null_genres}"
        )
        # 3 выведем города
        city_is_null = connection.execute(text("""
            SELECT city_name
            FROM dds.cities
        """)).scalars().all()
        print(f"\nГорода: {', '.join(city_is_null)}")

        # # 4 жанры по городам
        # genres_by_city = connection.execute(text("""
        #     SELECT
        #         c.city_name,
        #         g.genre_name,
        #         COUNT(*) AS listening_count
        #     FROM dds.facts f
        #     JOIN dds.cities c
        #         ON f.city_id = c.city_id
        #     JOIN dds.tracks t
        #         ON f.track_id = t.track_id
        #     JOIN dds.genres g
        #         ON t.genre_id = g.genre_id
        #     GROUP BY
        #         c.city_name,
        #         g.genre_name
        #     ORDER BY
        #         c.city_name,
        #         listening_count DESC;
        # """)).fetchall()
        # print(genres_by_city)

        # 5 дубликаты пользователей, исполнителей, жанров, городов
        users_dup = connection.execute(text("""
            SELECT user_id
            FROM dds.users
            GROUP BY user_id
            HAVING COUNT(*) > 1
        """)).scalar()

        artists_dup = connection.execute(text("""
            SELECT artist_name
            FROM dds.artists
            GROUP BY artist_name
            HAVING COUNT(*) > 1
        """)).scalar()

        genres_dup = connection.execute(text("""
            SELECT genre_name
            FROM dds.genres
            GROUP BY genre_name
            HAVING COUNT(*) > 1
        """)).scalar()

        cities_dup = connection.execute(text("""
            SELECT city_name
            FROM dds.cities
            GROUP BY city_name
            HAVING COUNT(*) > 1
        """)).scalar()

        print(f"\nДубликаты - пользователи: {users_dup}")
        print(f"\nДубликаты - артисты: {artists_dup}")
        print(f"\nДубликаты - жанры: {genres_dup}")
        print(f"\nДубликаты - города: {cities_dup}")

if __name__ == "__main__":
    df = load_data("music_project.csv")
    print(df.columns)
    print("fdfd", "\tvvvvv" )
 
