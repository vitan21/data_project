# Разработка аналитической витрины
"""
Необходимо:

1. определить назначение витрины и состав аналитических показателей;
2. определить уровень детализации данных;
3. спроектировать и создать таблицу аналитической витрины;
4. реализовать механизм первоначальной и повторной загрузки витрины из DWH;
5. подготовить примеры аналитических запросов к сформированной витрине.

-- Решение
1. Анализ популярности музыкальных жанров в разных городах по дням

2. Одна запись витрины соответствует одному муз. жанру в одном городе
за одну календарную дату

Состав показателей:
    date_value - дата
    city_name - город
    genre_name - жанр
    listening_count - кол-во прослушиваний
    most_listened_song_in_genre - самая популярная песня в жанре
    unique_users - кол-во уникальныз пользователей
    unique_tracks - кол-во уникальных треков
"""

from sqlalchemy import text
from db_administration.connection import get_db_engine


def load_mart(p_sdt: str, p_edt: str):
    engine = get_db_engine()

    print(
        f"[MART] Формирование аналитической витрины"
        f"за период {p_sdt} - {p_edt}"
    )

    with engine.begin() as connection:

        connection.execute(text("""
            CREATE SCHEMA IF NOT EXISTS mart;

            CREATE TABLE IF NOT EXISTS mart.mart_genre (
                date_value DATE NOT NULL,
                city_name TEXT NOT NULL,
                genre_name TEXT NOT NULL,
                listening_count BIGINT NOT NULL,
                most_listened_song TEXT NOT NULL,
                unique_users BIGINT NOT NULL,
                unique_tracks BIGINT NOT NULL,

                PRIMARY KEY (
                    date_value,
                    city_name,
                    genre_name
                )
            );
        """))

        # удаление старых результатов за период
        deleted = connection.execute(text("""
            DELETE FROM mart.mart_genre
            WHERE date_value BETWEEN :sdt AND :edt;
        """), {"sdt": p_sdt, "edt": p_edt})

        print (f"[MART] Удалено старых строк: {deleted.rowcount}")

        # формирование агрегированных данных
        inserted = connection.execute(text("""
            WITH track_stats AS (
                SELECT
                    d.date_value,
                    c.city_name,
                    g.genre_name,
                    t.track_name,
                    COUNT(*) AS track_listens,
                    ROW_NUMBER() OVER (
                        PARTITION BY d.date_value, c.city_name, g.genre_name
                        ORDER BY COUNT(*) DESC, t.track_name ASC
                    ) AS rn
                FROM dds.facts f
                INNER JOIN dds.datetime d ON d.datetime_id = f.datetime_id
                INNER JOIN dds.cities c ON c.city_id = f.city_id
                INNER JOIN dds.tracks t ON t.track_id = f.track_id
                INNER JOIN dds.genres g ON g.genre_id = t.genre_id
                WHERE d.date_value BETWEEN :sdt AND :edt
                GROUP BY d.date_value, c.city_name, g.genre_name, t.track_name
            ),
            genre_stats AS (
                SELECT
                    d.date_value,
                    c.city_name,
                    g.genre_name,
                    COUNT(*) AS listening_count,
                    COUNT(DISTINCT f.user_id) AS unique_users,
                    COUNT(DISTINCT t.track_id) AS unique_tracks
                FROM dds.facts f
                INNER JOIN dds.datetime d ON d.datetime_id = f.datetime_id
                INNER JOIN dds.cities c ON c.city_id = f.city_id
                INNER JOIN dds.tracks t ON t.track_id = f.track_id
                INNER JOIN dds.genres g ON g.genre_id = t.genre_id
                WHERE d.date_value BETWEEN :sdt AND :edt
                GROUP BY d.date_value, c.city_name, g.genre_name
            )
            INSERT INTO mart.mart_genre (
                date_value,
                city_name,
                genre_name,
                listening_count,
                most_listened_song,
                unique_users,
                unique_tracks
            )
            SELECT
                gs.date_value,
                gs.city_name,
                gs.genre_name,
                gs.listening_count,
                ts.track_name AS most_listened_song,
                gs.unique_users,
                gs.unique_tracks
            FROM genre_stats gs
            INNER JOIN track_stats ts
                ON gs.date_value = ts.date_value
                AND gs.city_name = ts.city_name
                AND gs.genre_name = ts.genre_name
                AND ts.rn = 1
            ON CONFLICT (
                date_value,
                city_name,
                genre_name
            )
            DO UPDATE SET
                listening_count = EXCLUDED.listening_count,
                most_listened_song = EXCLUDED.most_listened_song,
                unique_users = EXCLUDED.unique_users,
                unique_tracks = EXCLUDED.unique_tracks;
        """),
        {"sdt": p_sdt, "edt": p_edt})

        print(f"[MART] Сформировано строк: {inserted.rowcount}")

        # проверка кол-ва записей
        total = connection.execute(text("""
            SELECT COUNT(*)
            FROM mart.mart_genre
            WHERE date_value BETWEEN :sdt AND :edt
        """), {"sdt": p_sdt, "edt": p_edt})

        print(f"[MART] Добавлено строк в mart.mart_genre: {total.scalar()}")

         
        """
        -- Популярность жанров за весь период
        SELECT
            genre_name,
            SUM(listening_count) AS total_listenings
        FROM mart.mart_genre
        GROUP BY genre_name
        ORDER BY total_listenings DESC;

        -- Топ 5 городов по кол-ву прослушиваний
        SELECT
            city_name,
            SUM(listening_count) AS total_listenings
        FROM mart.mart_genre
        GROUP BY city_name
        ORDER BY total_listenings DESC
        LIMIT 5;

        --Количество уникальных пользователей по жанрам
        SELECT
            genre_name,
            SUM(unique_users) AS users_by_genre
        FROM mart.mart_genre
        GROUP BY genre_name
        ORDER BY users_by_genre DESC;

        --Динамика прослушиваний по дням
        SELECT
            date_value,
            SUM(listening_count) AS total_listenings
        FROM mart.mart_genre
        GROUP BY date_value
        ORDER BY date_value;

        -- Самый популярный жанр в каждом городе
        SELECT *
        FROM (
            SELECT
                city_name,
                genre_name,
                SUM(listening_count) AS total_listenings,

                ROW_NUMBER() OVER (
                    PARTITION BY city_name
                    ORDER BY SUM(listening_count) DESC
                ) AS rn

            FROM mart.mart_genre

            GROUP BY city_name, genre_name
        ) ranked
        WHERE rn = 1
        ORDER BY city_name;
        """

    
    print("[MART] Витрина успешно обновлена.")
