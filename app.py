import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import os
import json

# --- 頁面設定 ---
st.set_page_config(
    page_title="農業氣象預報",
    page_icon="🌦️",
    layout="wide"
)

# --- 資料庫設定與自動生成 ---
DB_FILE = 'data.db'
JSON_FILE = 'F-A0010-001.json'

def setup_database():
    """
    檢查資料庫是否存在，如果不存在，則建立並從JSON檔案填充它。
    """
    if not os.path.exists(DB_FILE):
        st.info("正在建立並初始化資料庫... 這只需要在首次啟動時執行。")
        
        # 1. 建立資料庫表格 (來自 create_db.py)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS weather (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT,
            min_temp REAL,
            max_temp REAL,
            description TEXT
        )
        ''')
        conn.commit()
        
        # 2. 從 JSON 填充資料 (來自 process_data.py)
        try:
            with open(JSON_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for location in data['cwaopendata']['resources']['resource']['data']['agrWeatherForecasts']['weatherForecasts']['location']:
                location_name = location['locationName']
                min_temp = float(location['weatherElements']['MinT']['daily'][0]['temperature'])
                max_temp = float(location['weatherElements']['MaxT']['daily'][0]['temperature'])
                description = location['weatherElements']['Wx']['daily'][0]['weather']

                if location_name and min_temp is not None and max_temp is not None and description:
                    cursor.execute('''
                    INSERT INTO weather (location, min_temp, max_temp, description)
                    VALUES (?, ?, ?, ?)
                    ''', (location_name, min_temp, max_temp, description))
            
            conn.commit()
            st.success("資料庫已成功建立並填充資料！")
        except FileNotFoundError:
            st.error(f"錯誤：找不到 '{JSON_FILE}'。請確保此檔案與 app.py 在同一個目錄下。")
            return False
        except Exception as e:
            st.error(f"處理JSON或資料庫時發生錯誤：{e}")
            return False
        finally:
            conn.close()
    return True

# --- 資料載入與處理 ---
@st.cache_data
def load_data():
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM weather", conn)
        
        if df.empty:
            st.error("資料庫是空的。")
            return None, []
            
        # 模擬經緯度數據
        mock_coords = {
            '北部地區': [25.033, 121.565], '中部地區': [24.148, 120.674],
            '南部地區': [22.999, 120.213], '東北部地區': [24.746, 121.745],
            '東部地區': [23.987, 121.604], '東南部地區': [22.75, 121.15]
        }
        
        df['coords'] = df['location'].map(mock_coords)
        df = df.dropna(subset=['coords'])

        if df.empty:
            st.warning("資料庫中的地點無法對應到任何已知座標。")
            return pd.DataFrame(columns=['id', 'location', 'min_temp', 'max_temp', 'description', 'coords', 'lat', 'lon', 'date']), list(mock_coords.keys())

        df = df.reset_index(drop=True)
        coords_df = pd.DataFrame(df['coords'].tolist(), columns=['lat', 'lon'])
        df = pd.concat([df, coords_df], axis=1)
        
        # 模擬日期數據
        today = datetime.now().date()
        df['date'] = [today + timedelta(days=i % 3) for i in range(len(df))]
        
        return df, sorted(list(df['location'].unique()))
    
    except Exception as e:
        st.error(f"讀取資料時發生錯誤：{e}")
        return None, []
    
    finally:
        if 'conn' in locals():
            conn.close()

# --- 主程式流程 ---
if not setup_database():
    st.stop() # 如果資料庫設定失敗，則停止執行

df, location_options = load_data()

if df is not None:
    if not df.empty:
        st.success("已載入氣象資料！")
    
    # --- 側邊欄 (Sidebar) ---
    with st.sidebar:
        st.header("篩選條件")
        
        # 1. 日期範圍選擇器
        # 注意：我們的模擬資料只有幾天，但功能是完整的
        default_start = datetime.now().date()
        default_end = default_start + timedelta(days=13)
        
        date_range = st.date_input(
            "選擇日期範圍 (預設未來兩週)",
            (default_start, default_end),
            min_value=default_start - timedelta(days=30),
            max_value=default_end + timedelta(days=30),
            format="YYYY-MM-DD",
        )
        
        # 確保有選擇範圍
        if len(date_range) != 2:
            st.stop()
            
        start_date, end_date = date_range

        # 2. 地區選擇
        selected_location = st.selectbox(
            "選擇地區",
            options=["全部地區"] + location_options,
            index=0
        )

        # 3. 農業資訊 Checkbox
        show_degree_day = st.checkbox("顯示農業資訊 (Degree Day)", value=True)

    # --- 主畫面 (Main Area) ---
    st.title("一週農業氣象預報 + 農業積溫資料")

    # 資料篩選
    if selected_location == "全部地區":
        filtered_df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
    else:
        filtered_df = df[(df['location'] == selected_location) & (df['date'] >= start_date) & (df['date'] <= end_date)]

    if filtered_df.empty:
        st.warning("在此篩選條件下無資料。")
    else:
        # 版面配置：左欄寬，右欄窄
        col1, col2 = st.columns([3, 1.5])

        with col1:
            # --- 地圖區塊 ---
            st.subheader("氣象站點地圖")
            map_center = [23.973, 120.979] # 台灣中心點
            
            # 建立 Folium 地圖
            m = folium.Map(location=map_center, zoom_start=7)

            # 在地圖上加上標記
            for _, row in filtered_df.iterrows():
                if pd.notna(row['lat']) and pd.notna(row['lon']):
                    # 根據溫度設定標記顏色
                    temp_color = "orange" if row['max_temp'] > 30 else "green"
                    
                    popup_html = f"""
                    <b>地點:</b> {row['location']}<br>
                    <b>最高溫:</b> {row['max_temp']}°C<br>
                    <b>最低溫:</b> {row['min_temp']}°C<br>
                    <b>天氣:</b> {row['description']}
                    """
                    
                    folium.Marker(
                        location=[row['lat'], row['lon']],
                        popup=folium.Popup(popup_html, max_width=200),
                        tooltip=row['location'],
                        icon=folium.Icon(color=temp_color, icon="cloud"),
                    ).add_to(m)

            # 在 Streamlit 中顯示地圖
            st_folium(m, width=700, height=500)

        with col2:
            # --- 右側數據欄 (Metrics) ---
            st.subheader("數據統計")
            
            # 計算統計值
            avg_max_temp = filtered_df['max_temp'].mean()
            avg_min_temp = filtered_df['min_temp'].mean()
            
            # 模擬農業數據
            gdd_base = 10 # 生長基溫假設為 10°C
            avg_temp = (avg_max_temp + avg_min_temp) / 2
            gdd = max(0, avg_temp - gdd_base) * (len(filtered_df.date.unique())) # 乘以天數
            
            # 模擬濕度數據
            mock_humidity = np.random.uniform(60, 95)

            st.metric(label="平均最高溫", value=f"{avg_max_temp:.1f} °C")
            st.metric(label="平均最低溫", value=f"{avg_min_temp:.1f} °C")
            
            if show_degree_day:
                st.markdown("---")
                st.subheader("農業專用指標 (模擬)")
                st.metric(label="平均度日 (GDD)", value=f"{gdd:.1f}", help="生長度日 (Growing Degree Days)，計算方式: (平均溫度 - 生長基溫) * 天數")
                st.metric(label="最大累積濕度/溫度", value=f"{mock_humidity:.1f} %")

        # 顯示詳細資料表格
        st.subheader("詳細氣象資料")
        st.dataframe(filtered_df[['date', 'location', 'min_temp', 'max_temp', 'description']].rename(columns={
            'date': '日期', 'location': '地點', 'min_temp': '最低溫', 'max_temp': '最高溫', 'description': '天氣概況'
        }))

else:
    st.info("正在等待資料載入...")