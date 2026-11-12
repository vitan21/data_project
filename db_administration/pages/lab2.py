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

from db_administration.generate_data import generate_batch



if __name__ == "__main__":

    batch_1 = generate_batch(
        n_records=5000,
        start_date="2025-01-13",
        end_date="2025-01-25",
        batch_number=1,
        start_record_id=100000,
        error_rate=0.1
    )
    batch_2 = generate_batch(
        n_records=28000,
        start_date="2025-02-01",
        end_date="2025-02-27",
        batch_number=2,
        start_record_id=105000
    )
