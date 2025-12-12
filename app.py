
import streamlit as st
import sqlite3
import pandas as pd

st.title('Weather Data Viewer')

conn = sqlite3.connect('data.db')
df = pd.read_sql_query("SELECT * FROM weather", conn)
conn.close()

st.dataframe(df)
