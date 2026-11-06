from db_administration.loaders import load_data
import streamlit as st
import pandas as pd
import plotly.express as px



def main():
    # Страницы
    PAGES_MAP = {
        "Высокопроизводительная обработка и анализ данных": {
            "Лабораторная работа №1": st.Page(
                page = "data_analytic/pages/lab1.py",
                title = "Формирование и подготовка данных для аналитической обработки"
                ),
            "Лабораторная работа №2": st.Page(
                page = "data_analytic/pages/lab2.py",
                title = "Разработка процессов преобразования и представления данных"
                )
        },
        "Администрирование больших данных": {
            "Лабораторная работа №1": st.Page(
                page = "db_administration/pages/lab1.py",
                title = "Развертывание и конфигурирование среды хранения данных"
                ),
            "Лабораторная работа №2": st.Page(
                page = "db_administration/pages/lab2.py",
                title = "Организация хранения и управления данными"
                )
        }
    }

    # Инициализируем состояние сессии для хранения выбранной страницы
    if "current_page" not in st.session_state:
        # по умолчанию загружаем саму себя (главную форму)
        first_subject = list(PAGES_MAP.keys())[0]
        first_work = list(PAGES_MAP[first_subject].keys())[0]
        st.session_state.current_page = PAGES_MAP[first_subject][first_work]

    # сайдбар для навигации
    with st.sidebar:
        with st.form(key="sidebar_navigation_form"):
            st.subheader("Дисциплины")
            # выбор предмета
            subject = st.selectbox(
                "Дисциплина", options=list(PAGES_MAP.keys())
            )
            # выбор работы
            work = st.selectbox(
                "Лабораторная работа", options=list(PAGES_MAP[subject].keys())
            )
            submit = st.form_submit_button("Перейти к работе")

            if submit:
                st.session_state.current_page = PAGES_MAP[subject][work]
                st.rerun()
    # передаем страницу в навигацию и запускаем ее
    pg = st.navigation([st.session_state.current_page])
    
    pg.run()
if __name__ == "__main__":
    main()
