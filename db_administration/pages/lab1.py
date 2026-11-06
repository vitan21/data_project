# Администрирование больших данных

# Лабораторная работа №1  

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

import os
import pandas as pd
from sqlalchemy import create_engine, types, URL, inspect, text
from db_administration.loaders import load_data, load_to_staging

from db_administration.connection import get_db_engine

DB_USER = "postgres"
DB_PASSWORD = "postgres"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "music_db"


def load_data_to_sql(engine,file_path,table_name, schema_name):
    inspector = inspect(engine)

    if inspector.has_table(table_name, schema = schema_name):
        with engine.connect() as connection:
            query = text(f"SELECT 1 FROM {schema_name}.{table_name} LIMIT 1")
            count = connection.execute(query).first()
            if count is not None:
                print(
                f"[Пропуск] Таблица {schema_name}.{table_name} "
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
    
    
if __name__ == "__main__":
    main()

