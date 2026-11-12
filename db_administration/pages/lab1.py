# Администрирование больших данных

# Лабораторная работа №1  

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

import os
import pandas as pd
from sqlalchemy import create_engine, types, URL, inspect, text
from db_administration.loaders import (
    load_data, 
    load_to_staging, 
    load_to_ods,
    load_to_dds
)
from db_administration.connection import get_db_engine

DB_USER = "postgres"
DB_PASSWORD = "postgres"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "music_db"


def load_data_to_sql(engine, file_path, table_name, schema_name):
    inspector = inspect(engine)

    if inspector.has_table(table_name, schema = schema_name):
        with engine.connect() as connection:
            query = text(f"SELECT 1 FROM {schema_name}.{table_name} LIMIT 1")
            count = connection.execute(query).first()
            if count is not None:
                print(
                f"[SOURCE] Таблица {schema_name}.{table_name} "
                f"уже содержит {count} записей."
            )
                return
        print(
            f"[Загрузка] Таблица {schema_name}.{table_name} "
            "существует, но пуста. Выполняем загрузку."
        )
    else:
        print(
            f"[Загрузка] Таблица {schema_name}.{table_name} "
            "не найдена. Создаём её."
        )

        
    df = load_data(file_path)
    
    dtype_mapping = {col: types.TEXT for col in df.columns}

    df.to_sql(
            name=table_name,
            con=engine,
            schema=schema_name,
            if_exists="append",
            index=False,
            dtype=dtype_mapping
        )
    print(f"Загружено {len(df)} строк в source.music_tracks")

def main():
    # соединение с бд
    engine = get_db_engine()

    # из csv -> sql
    load_data_to_sql(
        engine=engine,
        file_path="music_project.csv",
        table_name="music_tracks",
        schema_name="source"
    )
    # создание staging слоя 
    load_to_staging()

    # создание слоя ods
    load_to_ods("2025-01-06", "2025-01-12")

    # создания слоя dds
    load_to_dds()
if __name__ == "__main__":
    main()


"""
1. Факты и измерения
Факты - прослушивание трека пользователем (событие прослушивания)
Измерения: кто слушал, что слушал, когда слушал, где слушал, кто исполнитель,
какой жанр,

2. Уровень детализации фактов
Одна строка - одно прослушивания

3. выделить основные сущности предметной области
таблица фактов - прослушивания треков,
пользователи, назв треков, артисты, жанры, города, время

4. нормализовать измерения;

5. определить первичные и внешние ключи;

6. определить типы данных;

7. создать физическую структуру хранилища;

8. реализовать загрузку данных из ODS в разработанное хранилище.

"""
