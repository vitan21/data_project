
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from db_administration.loaders import load_data
import streamlit as st
import pandas as pd
import plotly.express as px



# Нормализация 



def normalization(df):
    df_normalized = df.copy()

    # нормализация атрибутов
    df_normalized.columns = df_normalized.columns.str.strip()

    text_columns = df_normalized.select_dtypes(
        include=["string", "object"]
    ).columns

    # нормализация данных
    for col in text_columns:
        df_normalized[col] = (
            df_normalized[col]
            .astype("string")
            .str.strip()
            .str.casefold()
            )
    return df_normalized

print("Программа запущена")

# Подгрузка данных
db_url = "music_project.csv"
df = load_data(db_url)
print("Данные загружены")
print(df.head(7))

# бд
index = df.index
columns = df.columns
values = df.values

st.set_page_config(
    page_title="Аналитический дэшборд", layout="wide", page_icon="data.png"
)
st.title("Аналитический дэшборд", text_alignment="center")
st.html("<br>")






# ---------------
# кол-во записей
df_len = len(df)
st.markdown(f"## 1. Количество записей: {df_len}")

# ---------------
# кол-во атрибутов
df_atr_len = len(columns)
st.markdown(f"## 2. Количество атрибутов: {df_atr_len}")
st.dataframe([columns], width="content", hide_index=True)

# ---------------
# Типы данных
st.markdown(f"## 3. Типы данных: ")
st.dataframe(df.dtypes, width="content")

# ---------------
# Заполненность атрибутов
st.markdown(f"## 4. Заполненность атрибутов:")
st.dataframe(df.count(), width="content")

# ---------------
# Количество и доля пропущенных значений
missing_values_count = df.isna().sum()
missing_values_percent = ((df.isna().sum() / df_len) * 100).round(2)
missing_df = pd.DataFrame(
    {
    "Количество пропусков": missing_values_count,
    "Доля пропусков, %": missing_values_percent,
}
)
st.markdown("## 5. Количество || доля пропущенных значений ")
st.dataframe(missing_df, width="content")

fig = px.bar(
    data_frame = missing_df,
    x = df.columns,
    y = "Доля пропусков, %",
    title = "Доля пропусков по признакам",
    text = "Доля пропусков, %",
    color_continuous_scale="Blues"
)
fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
fig.update_layout(
    xaxis_title = "Признак",
    yaxis_title = "Доля пропусков, %",
    yaxis_range = [0, max(missing_values_percent) * 1.1]
)
st.plotly_chart(fig, width="content")

# ---------------
# нормализованная бд
df_normalized = normalization(df)
df_normalized = df_normalized.rename(
    columns = {
        "Unnamed: 0": "record_id"
    }
)

# ---------------
# Наличие полных дубликатов
all_keys = list(df_normalized.columns[1:])
duplicates = df_normalized.duplicated(
    subset=all_keys,
    keep=False
)
duplicates_count = duplicates.sum()
duplicates_percent = (
    ((duplicates_count / len(df_normalized) * 100)).round(2)
    if len(df_normalized) else 0
)
st.markdown(f"## 6. Полные дубликанты")

dup_col1, dup_col2 = st.columns(2)
dup_col1.metric("Количество", int(duplicates_count))
dup_col2.metric("Доля, %", duplicates_percent)

if duplicates_count > 0:
    st.dataframe(
        df_normalized.loc[duplicates].drop(
            columns=["record_id"],
            errors="ignore"
        ).sort_values(
            by=all_keys,
            kind="stable"
        ),
        width="content",
    )

# ---------------
# наличие потенциальных дубликатов
potential_keys = ["userID", "Track", "artist", "Day", "time"]
if all(key in df_normalized.columns for key in potential_keys):
    duplicates_potential = df_normalized.duplicated(
        subset=potential_keys,
        keep=False
    )
    duplicates_potential_count = duplicates_potential.sum()
    duplicates_potential_percent = (
        ((duplicates_potential_count / len(df_normalized) * 100)).round(2)
        if len(df_normalized) else 0
    )
    st.markdown(f"## 7. Потенциальные дубликанты")
    dup_pot_col1, dup_pot_col2 = st.columns(2)
    dup_pot_col1.metric("Количество", int(duplicates_potential_count))
    dup_pot_col2.metric("Доля", duplicates_potential_percent)

    if duplicates_potential_count > 0:
        st.dataframe(
            df_normalized.loc[duplicates_potential].drop(
                columns=["record_id"],
                errors="ignore"
            ).sort_values(
                by=potential_keys,
                kind="stable"
            ),
            width="content"
        )
else:
    st.warning(f"columns <{[key for key in potential_keys]}> not found")

# ---------------
# количество уникальных значений;
st.markdown("## 8. Количество уникальных значений")
unique_values = df_normalized.nunique()
unique_df = pd.DataFrame(
    {"Количество значений": unique_values}
)
st.dataframe(unique_df, width="content")

# ---------------
# распределения числовых признаков
# количество записей по часам
st.markdown("## 9. Распределения числовых признаков")
# все часы
if "time" in df_normalized.columns:
    hours = pd.to_numeric(
        df_normalized["time"]
        .astype("string")
        .str.extract(r"^(\d{1,2}):")[0]
    )
    # оставляем только часы от 0 до 23
    hours = hours[hours.between(0, 23)].dropna().astype(int)

    hours_data = (
        hours.value_counts()
        .reindex(range(24), fill_value=0)
        .rename_axis("Час")
        .reset_index(name="Количество записей")
    )
    
    # отформатируем запись времени
    hours_data["Время"] = hours_data["Час"].astype(int).map(lambda h: f"{h:02d}:00")
    
    fig_hours = px.bar(
            data_frame = hours_data,
            x = "Время",
            y = "Количество записей",
            title = "Распределение записей по часам",
            text = "Количество записей",
            color = "Количество записей",
            color_continuous_scale="Teal"
        )
    fig_hours.update_traces(
        textposition="outside",
        outsidetextfont=dict(size=10, color='black'),
        insidetextfont=dict(size=10, color='white')
    )

    st.plotly_chart(fig_hours)
else:
    st.warning("column <time> not found")

# ---------------
# распределения категориальных признаков
st.markdown("## 10. Распределения категориальных признаков")

# 3 категории
distribution_attrs = ["genre", "City", "Day"]

cols_attrs_plot = st.columns(3) # 3 графика распределения
for col, attr in zip(cols_attrs_plot, distribution_attrs):
    # st.dataframe(df_normalized[attr].value_counts())

    counts_category = (
        df_normalized[attr].value_counts(dropna=False)
    )
    
    fig_category = px.bar(
        data_frame = counts_category,
        x = counts_category.index.astype(str),
        y = counts_category.values,
        title = f"Распределение <{attr}>"
    )
    fig_category.update_layout(
        xaxis_title = f"{attr}",
        yaxis_title = "Количество записей"
    )
    col.plotly_chart(fig_category, width="content")

# -------------
# выбросы и аномальные значения
# Метод межвартильного размаха IQR
# необычная частота записей от пользователя

if "userID" in df_normalized.columns:
    user_counts = df_normalized["userID"
    ].value_counts().reset_index(name="Количество записей")
    Q1 = user_counts["Количество записей"].quantile(0.25)
    Q3 = user_counts["Количество записей"].quantile(0.75)
    IQR = Q3 - Q1
    
    upper_limit = Q3 + 1.5 * IQR
    
    unusual_users = user_counts[
        user_counts["Количество записей"] > upper_limit
        ].sort_values("Количество записей", ascending=False)
    st.metric("Верхняя граница по методу IQR:", upper_limit)
    st.metric("Подозрительных пользователей:", len(unusual_users))

    fig_users = px.histogram(
        unusual_users,
        x="Количество записей",
        title="Распределение количества записей на пользователя",
        labels={"Количество записей": "Записей на пользователя"},
        nbins=10
    )
    st.plotly_chart(fig_users, width="content")
    with st.expander("Показать пользователей выше границы IQR"):
        st.dataframe(unusual_users, width="content")
else:
    st.warning("column <userID> not found")

# атрибуты, связанные с событиями пользователей
events_columns = ["userID", "City", "Day", "time"]
events = df_normalized.copy()
if all(key in events.columns for key in events_columns):
    events = events.dropna(subset=events_columns)
    time_str = events["time"].astype(str)
    time_format = pd.to_datetime(
        time_str,
        format = "%H:%M:%S",
        errors="coerce"
    )
    events["Секунды"] = (
        time_format.dt.hour * 3600 + time_format.dt.minute * 60 + time_format.dt.second
    )
else:
    st.warning(f"columns not found")


# ---------------
# поиск подозрительных значений времени
# 2. вроде как нету ничего необычного -> см. распр. зап. по часам
# 3. проверим на "100 треков" от юзера за короткий промежуток времени
def find_suspicious_activity_by_time(time, records):
    events_act = events.copy()
    
    # группировка по пользователю и дню недели
    suspicious_cases = []
    for (user_id, day), group in events_act.groupby(["userID", "Day"]):
        seconds = sorted(group["Секунды"].astype(int).tolist())

        left = 0 # самое раннее событие в текущем окне

        for right in range(len(seconds)): # right - текущ событие
            while seconds[right] - seconds[left] > time: # разница во врем м/у концом и началом
                left += 1

            count = right - left + 1 # число событий м/у 2мя границами

            if count >= records:
                suspicious_cases.append({
                    "userID": user_id,
                    "Day": day,
                    "Начало подозрительной активности": (
                        f"{seconds[left] // 3600:02d}:"
                        f"{(seconds[left] % 3600) // 60:02d}:"
                        f"{seconds[left] % 60:02d}"
                    ),
                    "Конец подозрительной активности": (
                        f"{seconds[right] // 3600:02d}:"
                        f"{(seconds[right] % 3600) // 60:02d}:"
                        f"{seconds[right] % 60:02d}"
                    ),
                    "Количество записей": count
                })
                # Находим только первое окно для этого пользователя и дня
                # break

    return suspicious_cases, events_act

suspicious_time = 20
suspicious_records = 10
suspicious_activity, suspicious_activity_events = find_suspicious_activity_by_time(suspicious_time, suspicious_records)
st.markdown(f"## 11. Аномальная активность пользователей") 
st.metric(f"Всего строк для анализа:", len(suspicious_activity_events))
suspicious_activity_df = pd.DataFrame(suspicious_activity)
st.markdown(
    f"### Условия поиска:  \n"
    f"Пользователь сделал <{suspicious_records}> записей за промежуток "
    f"времени в <{suspicious_time}> секунд"
)
st.markdown("### Результаты анализа: ")
if len(suspicious_activity_df) == 0:
    st.write(
        f"Подозрительных пользователь не найдено. "        
    )
else:
    st.success(
        f"Найдена подозрительная активность"
    )

    st.metric(f"Подозрительных случаев:", len(suspicious_activity_df))
    st.dataframe(suspicious_activity_df, width="content")
    
# ---------------
# географическая телепортация
# условие: один пользователь - один город ; без интервала времени
def find_geo_teleportation():
    events_geo = events.copy()
    events_geo = events_geo.sort_values("Секунды")
    # группируем 
    grouped = events_geo.groupby(["userID","Day"])
    # собираем города
    cities = grouped["City"].apply(lambda x: list(x.unique())).reset_index()
    # фильтруем тех, у кого +2 уник города
    cities_filtered = cities[cities["City"].str.len() >= 2]

    cities_filtered = cities_filtered.rename(
        columns={
            "City": "Города"
        }
    )
    
    return cities_filtered, events_geo

geo_teleportation, geo_teleportation_events = find_geo_teleportation()
geo_teleportation_df = pd.DataFrame(geo_teleportation)
st.write(f"## Географическая телепортация") 
st.metric(f"Всего строк для анализа:", len(geo_teleportation_events))
if len(geo_teleportation_df) == 0:
    st.write(f"Подозрительных пользователь не найдено ")
else:
    st.success(f"Найдено подозрительное перемещение")
    st.metric(f"Подозрительных случаев:", len(geo_teleportation_df))
    st.dataframe(geo_teleportation_df, width="content")

# ---------------
# некорректные форматы;

# time: должен соответствовать формату HH:MM:SS;
# Day: должен содержать допустимое название дня недели;
# названия атрибутов содержат пробелы
# text: текстовые поля содержат пробелы

# формат был реализован ранее при поиске различных событий
# повторим здесь тоже самое

# 1 проверка формата времени

format_issues = {}
time_parsed = pd.to_datetime(
    df_normalized["time"].astype(str).str.strip(),
    format = "%H:%M:%S",
    errors="coerce"
)
format_issues["Некорректное время"] = df_normalized.loc[
    time_parsed.isna() & df_normalized["time"].notna(),
    ["userID", "time"]
]

# 2 проверка дней недели
valid_days = {
    "Monday", "Tuesday", "Wednesday", "Thursday","Friday",
    "Saturday", "Sunday"
}
format_issues["Некорректные дни недели"] = df.loc[
    ~df["Day"].astype(str).str.strip().isin(valid_days) &
    df["Day"].notna(), ["  userID", "Day"]
]

# 3 в названии атрибута пробел
format_issues["Некорректное название атрибуирв"] = [
    col for col in df.columns if col.strip() != col
]

# 4 текстовые поля содержат пробелы
text_columns = ["Track", "artist", "genre", "  City  ", "Day"]
# поиск таких строк
for col in text_columns:
    text_spaces = (
        df[col].notna() & df[col].astype(str).ne(
            df[col].astype(str).str.strip()
        )
    )

    format_issues[f"Некорректные текстовые значения атрибута '{col}'"] = df.loc[
        text_spaces, [col]
    ]

st.markdown("## 12. Некорректные форматы")

for issue, data in format_issues.items():
    # st.markdown(f"### {issue}")
    st.metric(issue, len(data))
    if len(data) != 0: 
        st.dataframe(data)

# ---------------
# потенциально противоречивые значения;
# Повторяющиеся идентификаторы записей
# Один трек - несколько исполнителей или жанров

# 1.Повторяющиеся идентификаторы записей
duplicate_ids = df_normalized[df_normalized["record_id"].duplicated(keep=False)]
st.markdown("## 13. Потенциально противоречивые значения")
st.write("### Повторяющиеся идентификаторы записей")
st.metric("Повторяющихся record_id", len(duplicate_ids))

# 2.Один трек - несколько исполнителей или жанров
track_conflicts = (
    df_normalized.dropna(subset=["Track"])
    .groupby("Track")
    .agg(
        Количество_исполнителей = ("artist", "nunique"),
        Количество_жанров = ("genre", "nunique")
    )
    .reset_index()
)
track_conflicts = track_conflicts[
    (track_conflicts["Количество_исполнителей"] > 1)
    | (track_conflicts["Количество_жанров"] > 1)
]
st.markdown("### Один трек - несколько исполнителей или жанров")
st.dataframe(track_conflicts)


# Предлагаемый алгоритм очистки данных
st.markdown("## Предлагаемый алгоритм очистки данных")




# полные дубликанты
# некорректные форматы
# противоречивые значения

# таблица метаданных
cleaning_rules = [
    # неверное название к

    # проущенный значение id
    {
        "id": "RULE-01", # уникальный id правила
        "problem_type": "Пропущенное значение", # проблема
        "columns": ["record_id", "userID"], # признак | группа признаков
        "condition_type": "IS_NULL", # критерий выявления
        "condition_params": None, # параметры для условия
        "action": "DROP_ROW", # способ обработки
        "action_params": None, # если заполение -> то указать параметры заполения
        "description": "Исключение записи" # решение проблемы
        
    },

    # пропущенное значение ["Track", "artist", "genre"]
    {
        "id": "RULE-02",
        "problem_type": "Пропущенное значение",
        "columns": ["Track", "artist", "genre"],
        "condition_type": "IS_NULL",
        "condition_params": None,
        "action": "FILL_VALUE",
        "action_params": {
            "value": "unknown"
        },
        "decription": "Заполнение значения 'заглушкой'"
    },

    # пропущенное значение ["City"]
    # если город псутой - восстановим по userID или вставим заглушку
    {
        "id": "RULE-03",
        "problem_type": "Пропущенное значение",
        "columns": ["City"],
        "condition_type": "IS_NULL",
        "condition_params": {
            "group_by": "userID",
            "fallback": "unknown"
        },
        "action": "FILL_VALUE",
        "action_params": {
            "value": "unknown"
        },
        "decription": "Заполнение значения по историческим данным или 'заглушкой'"
    },


    # дубликат записи
    {
        "id": "RULE-04",
        "problem_type": "Дубликат",
        "columns": "ALL",
        "condition_type": "DUPLICATE",
        "condition_params": None,
        "action": "DROP_DUPLICATE",
        "action_params": {
            "keep": "first"
        },
        "decription": "Сохранение первой записи"
    },

    # # дубликат действий
    # {
    #     "id": "RULE-04",
    #     "problem_type": "Дубликат",
    #     "columns": ["userID", "Track", "time", "Day"],
    #     "condition_type": "DUPLICATE",
    #     "condition_params": None,
    #     "action": "DROP_DUPLICATE",
    #     "action_params": {
    #         "keep": "last"
    #     },
    #     "decription": "Сохранение последней записи"
    # },


    # некорректный значение времени
    {
        "id": "RULE-05",
        "problem_type": "Некорректное значение",
        "columns": ["time"],
        "condition_type": "INVALID_TIME_FORMAT",
        "condition_params": {"format": "%H:%M:%S"},
        "action": "TRANSFORM",
        "action_params": None,
        "decription": "Приведение значения к стандарту"
    },


    # несогласованная категория
    {
        "id": "RULE-06",
        "problem_type": "Некорректное значение",
        "columns": ["Day"],
        "condition_type": "NOT_IN_CATEGORIES",
        "condition_params": [
            "Monday", "Tuesday", "Wednesday","Thursday",
            "Friday", "Saturday", "Sunday"
        ],
        "action": "TRANSFORM",
        "action_params": None,
        "decription": "Приведение значения к допустимой категории"
    },

    # аномальная активность
    {
        "id": "RULE-07",
        "problem_type": "Подозрительная активность",
        "columns": ["userID", "time", "Day"],
        "condition_type": "LIMIT_EXCEEDED",
        "condition_params": {
            "max_time_sec": 20,
            "max_recorsds": 10,
        },
        "action": "TEMPORARY_BAN_LOGS",
        "action_params": {
            "timeout_duration_sec": 300
        },
        # исключаем логи юзерав последующие 300сек* после обнаружения
        "decription": "Ограничение всех последующих записей пользователя"
    },

    # географическая телепортация
    {
        "id": "RULE-08",
        "problem_type": "Подозрительное перемещение",
        "columns": ["userID", "City", "Day"],
        "condition_type": "MULTY_CITY_PER_USER",
        "condition_params": None,
        "action": "TEMPORARY_BAN_LOGS",
        "action_params": {
            "timeout_duration_day": 1
        },
        # исключаем все записи юзера в этот день
        "decription": "Исключение записей пользователя"
    },

]

