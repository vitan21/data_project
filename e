[33mcommit a85b45b6158f07bf48664cceac2e821973cdf588[m[33m ([m[1;36mHEAD[m[33m -> [m[1;32mmain[m[33m, [m[1;31morigin/main[m[33m)[m
Author: Viktor <vitya_dolgochin@mail.ru>
Date:   Fri Nov 13 00:04:18 2026 +0600

    end 1-st lab

[1mdiff --git a/data_analytic/pages/lab1.py b/data_analytic/pages/lab1.py[m
[1mindex 48951d9..cf5c804 100644[m
[1m--- a/data_analytic/pages/lab1.py[m
[1m+++ b/data_analytic/pages/lab1.py[m
[36m@@ -512,11 +512,11 @@[m [mst.markdown("## Предлагаемый алгоритм очистки дан[m
 cleaning_rules = [[m
     # неверное название к[m
 [m
[31m-    # проущенный значение id[m
[32m+[m[32m    # проПущенный значение id[m
     {[m
         "id": "RULE-01", # уникальный id правила[m
         "problem_type": "Пропущенное значение", # проблема[m
[31m-        "columns": ["record_id", "userID"], # признак | группа признаков[m
[32m+[m[32m        "columns": ["userID"], # признак | группа признаков[m
         "condition_type": "IS_NULL", # критерий выявления[m
         "condition_params": None, # параметры для условия[m
         "action": "DROP_ROW", # способ обработки[m
[36m@@ -572,22 +572,10 @@[m [mcleaning_rules = [[m
         "decription": "Сохранение первой записи"[m
     },[m
 [m
[31m-    # # дубликат действий[m
[31m-    # {[m
[31m-    #     "id": "RULE-04",[m
[31m-    #     "problem_type": "Дубликат",[m
[31m-    #     "columns": ["userID", "Track", "time", "Day"],[m
[31m-    #     "condition_type": "DUPLICATE",[m
[31m-    #     "condition_params": None,[m
[31m-    #     "action": "DROP_DUPLICATE",[m
[31m-    #     "action_params": {[m
[31m-    #         "keep": "last"[m
[31m-    #     },[m
[31m-    #     "decription": "Сохранение последней записи"[m
[31m-    # },[m
 [m
 [m
[31m-    # некорректный значение времени[m
[32m+[m
[32m+[m[32m    # некорректное значение времени[m
     {[m
         "id": "RULE-05",[m
         "problem_type": "Некорректное значение",[m
[36m@@ -648,5 +636,19 @@[m [mcleaning_rules = [[m
         "decription": "Исключение записей пользователя"[m
     },[m
 [m
[32m+[m
[32m+[m[32m    # # дубликат действий[m
[32m+[m[32m    # {[m
[32m+[m[32m    #     "id": "RULE-04",[m
[32m+[m[32m    #     "problem_type": "Дубликат",[m
[32m+[m[32m    #     "columns": ["userID", "Track", "time", "Day"],[m
[32m+[m[32m    #     "condition_type": "DUPLICATE",[m
[32m+[m[32m    #     "condition_params": None,[m
[32m+[m[32m    #     "action": "DROP_DUPLICATE",[m
[32m+[m[32m    #     "action_params": {[m
[32m+[m[32m    #         "keep": "last"[m
[32m+[m[32m    #     },[m
[32m+[m[32m    #     "decription": "Сохранение последней записи"[m
[32m+[m[32m    # },[m
 ][m
 [m
[1mdiff --git a/db_administration/__pycache__/generate_data.cpython-313.pyc b/db_administration/__pycache__/generate_data.cpython-313.pyc[m
[1mnew file mode 100644[m
[1mindex 0000000..667392d[m
Binary files /dev/null and b/db_administration/__pycache__/generate_data.cpython-313.pyc differ
[1mdiff --git a/db_administration/__pycache__/loaders.cpython-313.pyc b/db_administration/__pycache__/loaders.cpython-313.pyc[m
[1mindex 503b8fc..ee31d64 100644[m
Binary files a/db_administration/__pycache__/loaders.cpython-313.pyc and b/db_administration/__pycache__/loaders.cpython-313.pyc differ
[1mdiff --git a/db_administration/generate_data.py b/db_administration/generate_data.py[m
[1mnew file mode 100644[m
[1mindex 0000000..044efc3[m
[1m--- /dev/null[m
[1m+++ b/db_administration/generate_data.py[m
[36m@@ -0,0 +1,137 @@[m
[32m+[m[32mimport sys[m
[32m+[m[32mfrom pathlib import Path[m
[32m+[m
[32m+[m[32mROOT_DIR = Path(__file__).resolve().parents[2][m
[32m+[m[32msys.path.insert(0, str(ROOT_DIR))[m
[32m+[m
[32m+[m[32mfrom faker import Faker[m
[32m+[m[32mimport random[m
[32m+[m[32mfrom datetime import date, datetime, timedelta[m
[32m+[m[32mimport pandas as pd[m
[32m+[m
[32m+[m
[32m+[m[32mfake = Faker("en_US")[m
[32m+[m[32m# пул данных[m
[32m+[m[32mcities = [fake.city() for _ in range(15)][m
[32m+[m[32martists = [fake.name() for _ in range(25)][m
[32m+[m[32mtracks = [fake.sentence(nb_words=3).rstrip(".").title() for _ in range(40)][m
[32m+[m[32mgenres = ["Pop", "Rock", "Hip-Hop", "Jazz", "Electronic", "R&B", "Classical"][m
[32m+[m[32musers = [f"btuser{i:03d}" for i in range(1,101)][m
[32m+[m[41m [m
[32m+[m
[32m+[m[32m# генерация партии синтетических данных[m
[32m+[m[32mdef generate_batch ([m
[32m+[m[32m    n_records: int, # число записей[m
[32m+[m[32m    start_date: str, # начальная дата[m
[32m+[m[32m    end_date: str, # конечная дата[m
[32m+[m[32m    batch_number: int, # номер партии[m
[32m+[m[32m    start_record_id: int=1000000, # id записи[m
[32m+[m[32m    error_rate: float = 0.03, # доля ошибок[m
[32m+[m[32m    seed: int = 42 # нач знач генератора[m
[32m+[m[32m):[m
[32m+[m[32m    if n_records <= 0:[m
[32m+[m[32m        raise ValueError("Количество записей должно быть > 0")[m
[32m+[m[41m    [m
[32m+[m[32m    if not 0 <= error_rate <= 1:[m
[32m+[m[32m        raise ValueError("Доля ошибок должна лежать в диапазоне от 0 до 1")[m
[32m+[m
[32m+[m[32m    start = date.fromisoformat(start_date)[m
[32m+[m[32m    end = date.fromisoformat(end_date)[m
[32m+[m
[32m+[m[32m    if start > end:[m
[32m+[m[32m        raise ValueError("Начальная дата позже конечной")[m
[32m+[m
[32m+[m[32m    random.seed(seed + batch_number)[m
[32m+[m[32m    Faker.seed(seed + batch_number)[m
[32m+[m
[32m+[m[32m    date_range = [[m
[32m+[m[32m        start + timedelta(days=i)[m
[32m+[m[32m        for i in range((end-start).days + 1)[m
[32m+[m[32m    ][m
[32m+[m
[32m+[m[32m    records = [][m
[32m+[m
[32m+[m[32m    # создание записи[m
[32m+[m[32m    for i in range(n_records):[m
[32m+[m[32m        record_id = start_record_id + i[m
[32m+[m
[32m+[m[32m        user_id = random.choice(users)[m
[32m+[m
[32m+[m[32m        track = random.choice(tracks)[m
[32m+[m
[32m+[m[32m        artist = random.choice(artists)[m
[32m+[m
[32m+[m[32m        genre = random.choice(genres)[m
[32m+[m
[32m+[m[32m        city = random.choice(cities)[m
[32m+[m
[32m+[m[32m        time_value = ([m
[32m+[m[32m            f"{random.randint(0, 23):02d}:"[m
[32m+[m[32m            f"{random.randint(0, 59):02d}:"[m
[32m+[m[32m            f"{random.randint(0, 59):02d}"[m
[32m+[m[32m        )[m
[32m+[m[32m        dt_value = random.choice(date_range)[m
[32m+[m
[32m+[m[32m        day_name = dt_value.strftime("%A")[m
[32m+[m
[32m+[m[32m        # добавление ошибок[m
[32m+[m[32m        if random.random() < error_rate:[m
[32m+[m[32m            error_type = random.choice([[m
[32m+[m[32m                "missing_user",[m
[32m+[m[32m                "missing_track",[m
[32m+[m[32m                "missing_artist",[m
[32m+[m[32m                "missing_genre",[m
[32m+[m[32m                "missing_city",[m
[32m+[m[32m                "invalid_time",[m
[32m+[m[32m                "invalid_day"[m
[32m+[m[32m                "teleport"[m
[32m+[m[32m            ])[m
[32m+[m[32m            if error_type == "missing_user":[m
[32m+[m[32m                user_id = ""[m
[32m+[m[32m            elif error_type == "missing_track":[m