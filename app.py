import io
import re
import urllib.request
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="music_tracks | Data Quality", page_icon="🎵", layout="wide")

st.title("🎵 music_tracks — исследовательский анализ данных")
st.caption("Профилирование структуры, распределений, аномалий и качества исходных данных.")

EXPECTED_RANGES = {
    "popularity": (0, 100),
    "danceability": (0, 1),
    "energy": (0, 1),
    "speechiness": (0, 1),
    "acousticness": (0, 1),
    "instrumentalness": (0, 1),
    "liveness": (0, 1),
    "valence": (0, 1),
    "key": (-1, 11),
    "mode": (0, 1),
    "time_signature": (1, 7),
    "tempo": (0, 300),
    "duration_ms": (1, 3_600_000),
}
TEXT_CANDIDATES = ["track_name", "artists", "artist", "album_name", "track_id", "track_genre", "genre"]
ID_CANDIDATES = ["track_id", "id", "spotify_id", "uri"]

def read_csv_bytes(raw: bytes) -> pd.DataFrame:
    errors = []
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=enc, low_memory=False)
        except Exception as e:
            errors.append(str(e))
    raise ValueError("Не удалось прочитать CSV. " + " | ".join(errors[-2:]))

def load_url(url: str) -> pd.DataFrame:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=45) as response:
        raw = response.read()
    return read_csv_bytes(raw)

def norm_col(c):
    return re.sub(r"\s+", "_", str(c).strip().lower())

def quality_analysis(df: pd.DataFrame):
    n, p = df.shape
    missing = df.isna().sum()
    blank_counts = {}
    for c in df.select_dtypes(include=["object", "string"]).columns:
        blank_counts[c] = df[c].astype("string").str.strip().eq("").sum()
    blanks = pd.Series(blank_counts, dtype="int64").reindex(df.columns, fill_value=0)
    null_or_blank = missing + blanks
    profile = pd.DataFrame({
        "Атрибут": df.columns,
        "Тип данных": [str(df[c].dtype) for c in df.columns],
        "Заполнено": [int(n - null_or_blank[c]) for c in df.columns],
        "Заполненность, %": [round(100 * (n - null_or_blank[c]) / n, 2) if n else 0 for c in df.columns],
        "Пропуски NaN": [int(missing[c]) for c in df.columns],
        "Пустые строки": [int(blanks[c]) for c in df.columns],
        "Уникальных значений": [int(df[c].nunique(dropna=True)) for c in df.columns],
        "Уникальных, включая пропуски": [int(df[c].nunique(dropna=False)) for c in df.columns],
    })
    exact_duplicate_rows = int(df.duplicated().sum())

    issues = []
    def add(severity, category, column, count, detail, recommendation):
        if count:
            issues.append({"Критичность": severity, "Категория": category, "Атрибут": column,
                           "Количество": int(count), "Доля строк, %": round(100 * count / n, 3) if n else 0,
                           "Описание": detail, "Рекомендация": recommendation})

    add("Высокая", "Полные дубликаты", "Все поля", exact_duplicate_rows,
        "Строки полностью совпадают по всем атрибутам.",
        "Проверить происхождение повторов; удалять только после подтверждения правил предметной области.")

    for c in df.columns:
        add("Средняя", "Пропуски", c, int(null_or_blank[c]),
            "Пустые/отсутствующие значения в атрибуте.",
            "Уточнить семантику пропуска; выбрать стратегию заполнения или исключения.")
    # Duplicate IDs
    id_col = next((c for c in df.columns if c.lower() in ID_CANDIDATES), None)
    if id_col:
        nonempty = df[id_col].dropna().astype(str).str.strip()
        dup_mask = nonempty.duplicated(keep=False)
        dup_id_rows = int(dup_mask.sum())
        add("Высокая", "Повтор идентификатора", id_col, dup_id_rows,
            "Идентификатор встречается более одного раза; это может быть повтор записи или особенность источника.",
            "Сопоставить строки с одинаковым ID и проверить отличающиеся поля.")
    # Potential duplicates based on track title and artists
    title_col = next((c for c in df.columns if c.lower() in ["track_name", "track", "title", "name"]), None)
    artist_col = next((c for c in df.columns if c.lower() in ["artists", "artist", "artist_name"]), None)
    if title_col and artist_col:
        keys = df[[title_col, artist_col]].astype("string").apply(lambda s: s.str.strip().str.casefold())
        valid = keys.notna().all(axis=1) & keys.ne("").all(axis=1)
        potential = pd.Series(False, index=df.index)
        potential.loc[valid] = keys.loc[valid].duplicated(keep=False)
        add("Средняя", "Потенциальные дубликаты", f"{title_col} + {artist_col}", int(potential.sum()),
            "Совпадают нормализованные название трека и исполнитель; версии/переиздания могут быть легитимны.",
            "Проверить альбом, длительность и ID; не удалять автоматически.")
    # Numeric coercion anomalies and range checks
    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    for c in df.columns:
        if df[c].dtype == "object":
            nonempty = df[c].dropna().astype(str).str.strip()
            if len(nonempty):
                parsed = pd.to_numeric(nonempty.str.replace(",", ".", regex=False), errors="coerce")
                looks_numeric = nonempty.str.match(r"^[+-]?\d+(?:[.,]\d+)?$").mean()
                if looks_numeric > 0.7 and parsed.isna().any():
                    add("Средняя", "Смешанный формат", c, int(parsed.isna().sum()),
                        "Часть значений выглядит числовой, но не преобразуется в число.",
                        "Проверить разделители, единицы измерения и текстовые маркеры.")
    for c in numeric_cols:
        s = df[c].replace([np.inf, -np.inf], np.nan).dropna()
        if c in EXPECTED_RANGES:
            lo, hi = EXPECTED_RANGES[c]
            count = int(((s < lo) | (s > hi)).sum())
            add("Высокая", "Вне ожидаемого диапазона", c, count,
                f"Значения вне ориентировочного диапазона [{lo}, {hi}]. Диапазон следует сверить с документацией конкретного источника.",
                "Проверить единицы измерения, ошибки импорта и спецификацию признака.")
        if len(s) >= 4:
            q1, q3 = s.quantile([0.25, 0.75])
            iqr = q3 - q1
            if iqr > 0:
                outliers = int(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum())
                add("Низкая", "Статистические выбросы (IQR)", c, outliers,
                    "Наблюдения за пределами Q1 − 1.5×IQR или Q3 + 1.5×IQR; это сигнал для проверки, а не доказательство ошибки.",
                    "Изучить крайние наблюдения и сегменты; не удалять без предметного обоснования.")
    # Semantic checks
    for c in df.columns:
        if c.lower() in ["track_name", "artists", "artist", "album_name", "track_genre", "genre"]:
            s = df[c].dropna().astype(str)
            whitespace = int((s != s.str.strip()).sum())
            add("Низкая", "Лишние пробелы", c, whitespace,
                "Строки содержат пробелы в начале или конце.",
                "Нормализовать пробелы, сохранив исходное значение для аудита.")
            lower = s.str.lower()
            if len(s):
                case_variants = int(s.groupby(lower).nunique().gt(1).sum())
                add("Низкая", "Варианты регистра", c, case_variants,
                    "Есть группы значений, различающиеся регистром, но совпадающие после приведения к нижнему регистру.",
                    "Проверить, являются ли различия только форматированием.")
    # duplicate full-row count includes all repeated copies beyond first
    issue_df = pd.DataFrame(issues, columns=["Критичность", "Категория", "Атрибут", "Количество", "Доля строк, %", "Описание", "Рекомендация"])
    return profile, issue_df, exact_duplicate_rows, null_or_blank

def safe_numeric(df, col):
    return pd.to_numeric(df[col], errors="coerce")

with st.sidebar:
    st.header("Источник данных")
    source_mode = st.radio("Загрузить данные", ["Загрузить CSV-файл", "Указать URL CSV"], index=0)
    uploaded = None
    url = ""
    if source_mode == "Загрузить CSV-файл":
        uploaded = st.file_uploader("Файл music_tracks.csv", type=["csv", "txt"])
    else:
        url = st.text_input("Прямая ссылка на CSV", placeholder="https://.../music_tracks.csv")
        st.caption("Нужна прямая ссылка на CSV-файл, а не HTML-страница репозитория.")
    st.divider()
    st.header("Фильтры")
    st.caption("Фильтры применяются к исследуемой выборке; паспорт источника также показывается для загруженного набора.")

try:
    if source_mode == "Загрузить CSV-файл":
        if uploaded is None:
            st.info("Загрузите CSV-файл, чтобы начать анализ. Рекомендуемый публичный источник описан ниже.")
            st.markdown("**Вариант публичного датасета:** Spotify Tracks Dataset, около 114 тыс. строк и 21 поле, доступен на Hugging Face. Сверьте имя файла и лицензию на странице источника перед использованием.")
            st.markdown("[Открыть карточку датасета на Hugging Face](https://huggingface.co/datasets/maharshipandya/spotify-tracks-dataset)")
            st.stop()
        raw_df = read_csv_bytes(uploaded.getvalue())
    else:
        if not url.strip():
            st.info("Введите прямой URL CSV-файла.")
            st.stop()
        raw_df = load_url(url.strip())

    raw_df.columns = [norm_col(c) for c in raw_df.columns]
    if raw_df.empty:
        st.error("Файл прочитан, но в нём нет строк.")
        st.stop()

    st.success(f"Источник загружен: {raw_df.shape[0]:,} строк × {raw_df.shape[1]:,} столбцов")
    with st.expander("Настройки анализа", expanded=False):
        st.caption("Исходные данные не изменяются автоматически. Нормализация используется только для обнаружения отдельных потенциальных проблем.")

    n, p = raw_df.shape
    profile_all, issues_all, dup_count, missing_all = quality_analysis(raw_df)
    total_missing = int(missing_all.sum())
    missing_cells_pct = (100 * total_missing / (n * p)) if n * p else 0
    exact_dup_pct = (100 * dup_count / n) if n else 0
    affected_issues = int(issues_all["Количество"].sum()) if not issues_all.empty else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Записей", f"{n:,}")
    c2.metric("Атрибутов", f"{p:,}")
    c3.metric("Полные дубликаты", f"{dup_count:,}", f"{exact_dup_pct:.2f}% строк")
    c4.metric("Пропущенные ячейки", f"{total_missing:,}", f"{missing_cells_pct:.2f}% ячеек")
    c5.metric("Атрибуты с пропусками", f"{int((missing_all > 0).sum())}/{p}")

    tabs = st.tabs(["Обзор", "Структура и пропуски", "Числовые признаки", "Категориальные признаки", "Качество данных", "Строки данных", "Выводы"])
    with tabs[0]:
        st.subheader("Паспорт источника")
        left, right = st.columns([1, 1])
        with left:
            st.write("**Размерность**")
            st.dataframe(pd.DataFrame({"Показатель": ["Строки", "Столбцы", "Полные дубликаты", "Ячейки с пропусками/пустыми строками"],
                                       "Значение": [n, p, dup_count, total_missing]}), hide_index=True, use_container_width=True)
        with right:
            type_counts = raw_df.dtypes.astype(str).value_counts().rename_axis("Тип").reset_index(name="Количество атрибутов")
            fig = px.pie(type_counts, names="Тип", values="Количество атрибутов", hole=0.45, title="Типы данных столбцов")
            st.plotly_chart(fig, use_container_width=True)
        st.subheader("Первые строки")
        st.dataframe(raw_df.head(10), use_container_width=True)
        st.download_button("Скачать профиль атрибутов (CSV)", profile_all.to_csv(index=False).encode("utf-8-sig"), "music_tracks_profile.csv", "text/csv")

    with tabs[1]:
        st.subheader("Профиль атрибутов")
        type_filter = st.multiselect("Типы данных", sorted(profile_all["Тип данных"].unique()), default=sorted(profile_all["Тип данных"].unique()))
        filtered_profile = profile_all[profile_all["Тип данных"].isin(type_filter)]
        st.dataframe(filtered_profile, use_container_width=True, hide_index=True)
        st.subheader("Заполненность атрибутов")
        plot_df = profile_all.sort_values("Заполненность, %")
        fig = px.bar(plot_df, x="Заполненность, %", y="Атрибут", orientation="h",
                     color="Заполненность, %", range_x=[0, 100], title="Доля заполненных значений по полям")
        st.plotly_chart(fig, use_container_width=True)
        missing_plot = profile_all[profile_all["Пропуски NaN"] + profile_all["Пустые строки"] > 0].copy()
        if not missing_plot.empty:
            missing_plot["Всего пропусков"] = missing_plot["Пропуски NaN"] + missing_plot["Пустые строки"]
            fig = px.bar(missing_plot.sort_values("Всего пропусков"), x="Всего пропусков", y="Атрибут", orientation="h",
                         title="Количество отсутствующих и пустых значений")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("Не обнаружены NaN и пустые строки в текстовых атрибутах.")

    with tabs[2]:
        st.subheader("Распределения числовых признаков")
        numeric_cols = raw_df.select_dtypes(include=np.number).columns.tolist()
        if not numeric_cols:
            st.warning("В таблице нет столбцов с числовым типом. Проверьте типы при импорте.")
        else:
            selected_num = st.selectbox("Выберите числовой признак", numeric_cols)
            s = safe_numeric(raw_df, selected_num).replace([np.inf, -np.inf], np.nan).dropna()
            if len(s):
                stats = s.describe(percentiles=[.01, .25, .5, .75, .99]).to_frame("Значение")
                stats.loc["Пропусков после преобразования"] = len(raw_df) - len(s)
                st.dataframe(stats, use_container_width=True)
                chart_type = st.radio("Вид графика", ["Гистограмма", "Ящик с усами"], horizontal=True)
                if chart_type == "Гистограмма":
                    fig = px.histogram(pd.DataFrame({selected_num: s}), x=selected_num, marginal="box", nbins=50,
                                       title=f"Распределение: {selected_num}")
                else:
                    fig = px.box(pd.DataFrame({selected_num: s}), x=selected_num, points="outliers",
                                 title=f"Выбросы по IQR: {selected_num}")
                st.plotly_chart(fig, use_container_width=True)
                q1, q3 = s.quantile([.25, .75])
                iqr = q3 - q1
                if iqr > 0:
                    mask = (safe_numeric(raw_df, selected_num) < q1 - 1.5 * iqr) | (safe_numeric(raw_df, selected_num) > q3 + 1.5 * iqr)
                    outlier_rows = raw_df.loc[mask.fillna(False)]
                    st.caption(f"Правило IQR: {len(outlier_rows):,} потенциальных выбросов. Выбросы не обязательно являются ошибками.")
                    with st.expander("Показать строки с выбросами"):
                        st.dataframe(outlier_rows.head(500), use_container_width=True)
            st.subheader("Корреляции числовых признаков")
            if len(numeric_cols) >= 2:
                corr = raw_df[numeric_cols].corr(numeric_only=True)
                fig = px.imshow(corr, text_auto=".2f", aspect="auto", color_continuous_scale="RdBu_r",
                                zmin=-1, zmax=1, title="Матрица корреляций Пирсона")
                st.plotly_chart(fig, use_container_width=True)

    with tabs[3]:
        st.subheader("Распределения категориальных признаков")
        cat_cols = raw_df.select_dtypes(include=["object", "string", "category", "bool"]).columns.tolist()
        if not cat_cols:
            st.warning("Категориальные столбцы не обнаружены.")
        else:
            selected_cat = st.selectbox("Выберите категориальный признак", cat_cols)
            top_n = st.slider("Количество категорий", 5, 50, 15)
            cat_series = raw_df[selected_cat].astype("string").fillna("[ПРОПУСК]").replace("", "[ПУСТАЯ СТРОКА]")
            counts = cat_series.value_counts().head(top_n).rename_axis("Категория").reset_index(name="Количество")
            counts["Доля, %"] = (100 * counts["Количество"] / len(raw_df)).round(2)
            fig = px.bar(counts.sort_values("Количество"), x="Количество", y="Категория", orientation="h",
                         title=f"Топ-{top_n}: {selected_cat}")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(counts.sort_values("Количество", ascending=False), use_container_width=True, hide_index=True)
            st.caption(f"Уникальных значений без пропусков: {raw_df[selected_cat].nunique(dropna=True):,}")

    with tabs[4]:
        st.subheader("Реестр проблем качества")
        if issues_all.empty:
            st.success("Автоматические проверки не выявили проблем по реализованным правилам. Это не гарантирует полного отсутствия ошибок.")
        else:
            sev = st.multiselect("Критичность", ["Высокая", "Средняя", "Низкая"], default=["Высокая", "Средняя", "Низкая"])
            cats = sorted(issues_all["Категория"].unique())
            chosen_cats = st.multiselect("Категории проблем", cats, default=cats)
            issue_view = issues_all[issues_all["Критичность"].isin(sev) & issues_all["Категория"].isin(chosen_cats)]
            st.dataframe(issue_view.sort_values(["Критичность", "Количество"], ascending=[True, False]),
                         use_container_width=True, hide_index=True)
            st.download_button("Скачать реестр проблем (CSV)", issues_all.to_csv(index=False).encode("utf-8-sig"),
                               "music_tracks_quality_issues.csv", "text/csv")
            st.subheader("Проблемы по категориям")
            summary = issues_all.groupby(["Категория", "Критичность"], as_index=False)["Количество"].sum()
            fig = px.bar(summary, x="Категория", y="Количество", color="Критичность", barmode="group",
                         title="Количество срабатываний проверок")
            fig.update_layout(xaxis_tickangle=-35)
            st.plotly_chart(fig, use_container_width=True)
            st.warning("Числа в реестре — срабатывания правил, а не обязательно уникальные строки: одна строка может нарушать несколько правил.")
        st.subheader("Проверки, которые стоит интерпретировать осторожно")
        st.markdown("""
- **IQR-выбросы** — статистический сигнал; редкие музыкальные характеристики могут быть корректными.
- **Потенциальные дубликаты** по названию и исполнителю — версии, ремастеры и переиздания могут быть легитимны.
- **Диапазоны** — ориентировочные правила для распространённых Spotify audio features; сверяйте их с документацией именно вашего источника.
- **Противоречия между полями** не всегда можно определить универсально без бизнес-правил и описания происхождения данных.
""")

    with tabs[5]:
        st.subheader("Исходные записи и поиск")
        search = st.text_input("Поиск по любому текстовому полю")
        view = raw_df
        if search.strip():
            text_cols = view.select_dtypes(include=["object", "string"]).columns
            if len(text_cols):
                mask = pd.Series(False, index=view.index)
                for col in text_cols:
                    mask |= view[col].astype("string").str.contains(search, case=False, na=False, regex=False)
                view = view[mask]
            else:
                st.info("В данных нет текстовых полей для поиска.")
        max_rows = st.slider("Максимум отображаемых строк", 50, 2000, 200, step=50)
        st.write(f"Найдено строк: {len(view):,}")
        st.dataframe(view.head(max_rows), use_container_width=True)
        st.download_button("Скачать текущую выборку (CSV)", view.to_csv(index=False).encode("utf-8-sig"),
                           "music_tracks_filtered.csv", "text/csv")

    with tabs[6]:
        st.subheader("Итоговые выводы")
        completeness = 100 - missing_cells_pct
        st.write(f"- В загруженном источнике **{n:,} строк** и **{p:,} атрибутов**.")
        st.write(f"- Общая заполненность ячеек по NaN и пустым текстовым значениям: **{completeness:.2f}%**.")
        st.write(f"- Полных повторов строк: **{dup_count:,}** ({exact_dup_pct:.2f}% от строк).")
        if (missing_all > 0).any():
            worst = profile_all.sort_values("Заполненность, %").head(min(5, p))
            st.write("- Наименьшая заполненность у полей: " + ", ".join(
                f"`{r['Атрибут']}` ({r['Заполненность, %']:.1f}%)" for _, r in worst.iterrows()) + ".")
        else:
            st.write("- По базовой проверке NaN и пустых строк пропуски не обнаружены.")
        if not issues_all.empty:
            high = issues_all[issues_all["Критичность"] == "Высокая"]
            st.write(f"- Реестр содержит **{len(issues_all)} срабатываний проверок**, в том числе {len(high)} строк реестра с высокой критичностью.")
            st.write("- Перед использованием данных рекомендуется проверить повторяющиеся идентификаторы, диапазоны значений и потенциальные дубликаты, затем документировать решения по обработке.")
        else:
            st.write("- Реализованные проверки не обнаружили проблем; для окончательной оценки необходимы предметные правила и документация источника.")
        st.info("Выводы автоматически формируются по загруженному файлу. Они описывают срабатывания проверок, но не заменяют экспертную проверку и документирование происхождения данных.")

except Exception as e:
    st.error(f"Не удалось выполнить анализ: {e}")
    st.exception(e)
