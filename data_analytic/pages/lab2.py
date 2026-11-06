# # import streamlit as st
# # st.markdown("DATA 2 LAB")
# import os
# print(os.getcwd())


# from db_administration.loaders import load_data

# db_url = "music_project.csv"
# df = load_data(db_url)

# print(df)

import os
import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
from db_administration.loaders import load_data
db_url = "music_project.csv"
df = load_data(db_url)
print(df)
# print("Текущая директория:", os.getcwd())
# print("Файл lab2:", os.path.abspath(__file__))
# print("Пути поиска Python:")
# for path in sys.path:
#     print(path)