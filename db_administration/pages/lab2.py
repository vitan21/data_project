# 1. Генерация синтетических данных
# принимает кол-во записей
# генерация данных согласно предм. области и типам атрибтуов
#  формирование значений атрибута dt для посл. инкрементальной загрузки
# возможн формирования неск посл. партий данных
# сохранение результатов  генерации для дальн загрузки в таблицу-иссточник
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from datetime import date, datetime, timedelta


import pandas as pd
from faker import Faker
import random
from sqlalchemy import inspect, text, types

from db_administration.generate_data import generate_batch
from db_administration.connection import get_db_engine
from db_administration.loaders import (
    load_data,
    load_to_ods,
    load_to_dds
)

from db_administration.loaders import load_data

from db_administration.analytical_data_mart import load_mart
from db_administration.clickhouse_transfer import (
    transfer_mart_to_clickhouse
)

df_s = load_data("music_project.csv")


def add_dt_to_source():
    engine = get_db_engine()

    with engine.begin() as connection:
        # добавляем атрибут dt
        connection.execute(text("""
            ALTER TABLE source.music_tracks
            ADD COLUMN IF NOT EXISTS dt DATE
        """))
        # обновляем данные для несуществующий значений
        connection.execute(text("""
            UPDATE source.music_tracks
            SET dt = CASE LOWER(BTRIM("Day"))
                WHEN 'monday'    THEN DATE '2025-01-06'
                WHEN 'tuesday'   THEN DATE '2025-01-07'
                WHEN 'wednesday' THEN DATE '2025-01-08'
                WHEN 'thursday'  THEN DATE '2025-01-09'
                WHEN 'friday'    THEN DATE '2025-01-10'
                WHEN 'saturday'  THEN DATE '2025-01-11'
                WHEN 'sunday'    THEN DATE '2025-01-12'
                ELSE NULL
            END
            WHERE dt IS NULL;
        """))

# загрузка данных с учетом поля dt
def load_data_to_sql_with_dt(engine, file_path, table_name, schema_name):
    inspector = inspect(engine)

    
    df = load_data(file_path)
    
    if "dt" not in df.columns:
        raise ValueError(
            "В CSV отсутствует обязательный столбец dt."
        )
    # dt -> DATE
    df["dt"] = pd.to_datetime(
        df["dt"],
        errors="raise"
    ).dt.date

    # Определяем период загружаемой партии
    start_date = df["dt"].min()
    end_date = df["dt"].max()

    # Удаляем предыдущую версию партии из SOURCE
    with engine.begin() as connection:
        deleted = connection.execute(
            text("""
                DELETE FROM source.music_tracks
                WHERE dt BETWEEN :start_date AND :end_date
            """),
            {
                "start_date": start_date,
                "end_date": end_date
            }
        )

        print(
            f"[SOURCE] Удалено старых записей: {deleted.rowcount}"
        )


    # Все исходные атрибуты сохраняем как TEXT,
    # dt сохраняем как DATE.
    dtype_mapping = {col: types.TEXT for col in df.columns if col != "dt"}

    dtype_mapping["dt"] = types.DATE()

    # Проверяем наличие таблицы
    if not inspector.has_table(table_name, schema=schema_name):
        print(
            f"[SOURCE] Создание таблицы "
            f"{schema_name}.{table_name}"
        )
    else:
        print(
            f"[SOURCE] Добавление новой партии "
            f"в {schema_name}.{table_name}"
        )

    # Добавляем данные, не удаляя старые
    df.to_sql(
        name=table_name,
        con=engine,
        schema=schema_name,
        if_exists="append",
        index=False,
        dtype=dtype_mapping
    )

    print(
        f"[SOURCE] Загружено {len(df)} строк "
        f"из файла {file_path}"
    )

def load_to_staging_with_dt():
    engine = get_db_engine()

    with engine.begin() as connection:

        connection.execute(
            text("CREATE SCHEMA IF NOT EXISTS staging")
        )

        # создаем табл по структуре source
        connection.execute(
            text(
            "CREATE TABLE IF NOT EXISTS staging.music_tracks (LIKE"
            " source.music_tracks INCLUDING ALL)"
            )
        )

        connection.execute(text("""
            ALTER TABLE staging.music_tracks
            ADD COLUMN IF NOT EXISTS dt DATE
        """))

        # очистка staging перед повторной загрузкой
        connection.execute(
            text("TRUNCATE TABLE staging.music_tracks")
        )

        # переносим все записи без преобразований
        connection.execute(
            text("""
                INSERT INTO staging.music_tracks 
                SELECT *
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
        raise ValueError(
        "[STAGING !Ошибка] Количество записей в слоях не совпадает."
        )


        

def main():

    engine = get_db_engine()

    # добавление атрибута dt в source.music_tracks
    add_dt_to_source()

    # csv -> sql для партий данных
    # 1 партия
    print("------ Загрузка 1-ой партии данных ------")
    load_data_to_sql_with_dt(
        engine=engine,
        file_path="generated_batches/music_batch_01.csv",
        table_name="music_tracks",
        schema_name="source"
    )
    # sql -> staging
    load_to_staging_with_dt()

    # staging -> ods
    load_to_ods("2025-01-13", "2025-01-25")
    
    # 2 партия
    print("------ Загрузка 2-ой партии данных ------")
    load_data_to_sql_with_dt(
        engine=engine,
        file_path="generated_batches/music_batch_02.csv",
        table_name="music_tracks",
        schema_name="source"
    )
    # sql -> staging
    load_to_staging_with_dt()

    #staging -> ods
    load_to_ods("2025-02-01", "2025-02-27")

    # Создание аналитической витрины
    load_mart("2025-01-06", "2025-01-12")
    load_mart("2025-01-13", "2025-01-25")
    load_mart("2025-02-01", "2025-02-27")

    # перенос витрины -> ClickHouse
    transfer_mart_to_clickhouse()

if __name__ == "__main__":
    main()
    
