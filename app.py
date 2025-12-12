import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta

# --- 頁面設定 ---
st.set_page_config(
    page_title="農業氣象預報",
    page_icon="🌦️",
    layout="wide"
)

# --- 資料載入與處理 ---
@st.cache_data
def load_data():
    try:
        conn = sqlite3.connect('data.db')
        # 確保 process_data.py 已經執行過
        try:
            df = pd.read_sql_query("SELECT * FROM weather", conn)
            if df.empty:
                st.error("資料庫是空的，請先執行 `process_data.py` 來填充數據。")
                return None, None
        except pd.io.sql.DatabaseError:
            st.error("找不到 'weather' 表格，請先執行 `create_db.py` 和 `process_data.py`。")
            return None, None
            
        # 模擬經緯度數據 (因為原始資料沒有)
        # 注意：這些是大概位置，不是精確座標
        mock_coords = {
            '北部地區': [25.033, 121.565], # 以臺北為代表
            '中部地區': [24.148, 120.674], # 以臺中為代表
            '南部地區': [22.999, 120.213], # 以臺南為代表
            '東北部地區': [24.746, 121.745], # 以宜蘭為代表
            '東部地區': [23.987, 121.604], # 以花蓮為代表
            '東南部地區': [22.75, 121.15],  # 以臺東為代表
            # 保留縣市以備未來擴充
            '宜蘭縣': [24.746, 121.745], '桃園市': [24.993, 121.301], '新竹縣': [24.804, 121.011],
            '苗栗縣': [24.560, 120.821], '彰化縣': [24.079, 120.544], '南投縣': [23.918, 120.982],
            '雲林縣': [23.709, 120.431], '嘉義縣': [23.453, 120.576], '屏東縣': [22.549, 120.591],
            '臺東縣': [22.992, 121.059], '花蓮縣': [23.987, 121.604], '澎湖縣': [23.571, 119.566],
            '基隆市': [25.128, 121.742], '新竹市': [24.813, 120.968], '嘉義市': [23.479, 120.444],
            '臺北市': [25.033, 121.565], '高雄市': [22.627, 120.301], '新北市': [25.017, 121.463],
            '臺中市': [24.148, 120.674], '臺南市': [22.999, 120.213], '連江縣': [26.151, 119.954],
            '金門縣': [24.437, 118.319]
        }
        df['coords'] = df['location'].map(mock_coords)
        
        # 移除沒有對應座標的資料列，並重新賦值
        df = df.dropna(subset=['coords'])

        # 如果過濾後為空，提前返回
        if df.empty:
            st.warning("沒有任何地點資料有對應的座標，無法繼續。")
            # 仍然返回一個帶有正確欄位的空dataframe，以防後續操作出錯
            return pd.DataFrame(columns=['id', 'location', 'min_temp', 'max_temp', 'description', 'coords', 'lat', 'lon', 'date']), list(mock_coords.keys())

        # 將座標拆分為 lat 和 lon，使用更安全的方式
        df = df.reset_index(drop=True)
        coords_df = pd.DataFrame(df['coords'].tolist(), columns=['lat', 'lon'])
        df = pd.concat([df, coords_df], axis=1)
        
        # 模擬日期數據 (因為原始資料只有一天)
        today = datetime.now().date()
        df['date'] = [today + timedelta(days=i % 3) for i in range(len(df))] # 模擬3天的數據
        
        return df, list(mock_coords.keys())
    finally:
        if 'conn' in locals() and conn:
            conn.close()

df, location_options = load_data()

if df is not None:
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