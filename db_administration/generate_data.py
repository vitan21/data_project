import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from faker import Faker
import random
from datetime import date, datetime, timedelta
import pandas as pd
from sqlalchemy import text

from db_administration.loaders import load_data, get_db_engine
df_s = load_data("music_project.csv")



fake = Faker("en_US")
# пул данных
cities = [fake.city() for _ in range(15)]
artists = [fake.name() for _ in range(25)]
tracks = [fake.sentence(nb_words=3).rstrip(".").title() for _ in range(40)]
genres = ["Pop", "Rock", "Hip-Hop", "Jazz", "Electronic", "R&B", "Classical"]
users = [f"btuser{i:03d}" for i in range(1,101)]


# получаем текущий id из бд
def get_next_record_id(engine, schema_name="source", table_name="music_tracks"):
    with engine.begin() as connection:
        max_id = connection.execute(
            text(f"""
                SELECT COALESCE(MAX(CAST("Unnamed: 0" AS BIGINT)), 0)
                FROM {schema_name}.{table_name}
            """)
        ).scalar()
        return max_id + 1

# генерация партии синтетических данных
def generate_batch (
    n_records: int, # число записей
    start_date: str, # начальная дата
    end_date: str, # конечная дата
    batch_number: int, # номер партии
    start_record_id: int=len(df_s), # id записи
    error_rate: float = 0.03, # доля ошибок
    seed: int = 42 # нач знач генератора
):
    if n_records <= 0:
        raise ValueError("Количество записей должно быть > 0")
    
    if not 0 <= error_rate <= 1:
        raise ValueError("Доля ошибок должна лежать в диапазоне от 0 до 1")

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    if start > end:
        raise ValueError("Начальная дата позже конечной")

    random.seed(seed + batch_number)
    Faker.seed(seed + batch_number)

    date_range = [
        start + timedelta(days=i)
        for i in range((end-start).days + 1)
    ]

    records = []

    # Храним город для каждого пользователя на каждую дату
    user_day_cities = {}

    # создание записи
    for i in range(n_records):
        record_id = start_record_id + i

        user_id = random.choice(users)

        track = random.choice(tracks)

        artist = random.choice(artists)

        genre = random.choice(genres)

        dt_value = random.choice(date_range)

        # Для каждого пользователя на конкретную дату
        # закрепляем один город
        user_day_key = (user_id, dt_value)

        if user_day_key not in user_day_cities:
            user_day_cities[user_day_key] = random.choice(cities)
        city = user_day_cities[user_day_key]

        time_value = (
            f"{random.randint(0, 23):02d}:"
            f"{random.randint(0, 59):02d}:"
            f"{random.randint(0, 59):02d}"
        )

        day_name = dt_value.strftime("%A")

        # добавление ошибок
        if random.random() < error_rate:
            error_type = random.choice([
                "missing_user",
                "missing_track",
                "missing_artist",
                "missing_genre",
                "missing_city",
                "invalid_time",
                "invalid_day",
                "teleport"
            ])
            if error_type == "missing_user":
                user_id = ""
            elif error_type == "missing_track":
                track = ""
            elif error_type == "missing_artist":
                artist = ""
            elif error_type == "missing_genre":
                genre = ""
            elif error_type == "missing_city":
                city = ""
            elif error_type == "invalid_time":
                time_value = "01-01-2000"
            elif error_type == "invalid_day":
                day_name = "Mon day " 
            elif error_type == "teleport":
                city = random.choice(
                    [c for c in cities if c != city]
                )
        records.append({
            "Unnamed: 0": record_id, 
            "  userID": user_id, 
            "Track": track, 
            "artist": artist, 
            "genre": genre, 
            "  City  ": city,
            "time": time_value, 
            "Day": day_name,
            "dt": dt_value
        })

    df_gen = pd.DataFrame(records)

    output_dir = Path("generated_batches")
    output_dir.mkdir(exist_ok=True)

    file_path = (
        output_dir / f"music_batch_{batch_number:02d}.csv"
    )
    df_gen.to_csv(
        file_path,
        index=False,
        encoding="utf-8"
    )
    print(f"[GEN] Создана партия № {batch_number}")
    print(f"[GEN] Количество записей: {len(df_gen)}")
    print(f"[GEN] За период: {start_date} - {end_date}")
    print(f"[GEN] Файл: {file_path}\n")

    return df_gen

def main():
    engine = get_db_engine()
    current_record_id = get_next_record_id(engine)
    # создание двух партий данных
    batch_1 = generate_batch(
        n_records=5000,
        start_date="2025-01-13",
        end_date="2025-01-25",
        batch_number=1,
        start_record_id=current_record_id,
        error_rate=0.1
    )
    batch_2 = generate_batch(
        n_records=28000,
        start_date="2025-02-01",
        end_date="2025-02-27",
        batch_number=2,
        start_record_id=current_record_id + len(batch_1)
)

if __name__ == "__main__":
    main()