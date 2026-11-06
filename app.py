import streamlit as st
import pandas as pd
import math
import folium
from streamlit_js_eval import get_geolocation
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

st.set_page_config(layout="wide")
st.title("🚌 青森市 バス停案内アプリ (Streamlit Cloud公開用・決定版)")

# ── 1. 青森市公式の GTFSデータ (stops.txt) を自動で読み込む ──
try:
    df_gtfs = pd.read_csv("stops.txt", encoding="utf-8")
    df_bus_stops = df_gtfs[['stop_name', 'stop_lat', 'stop_lon']].copy()
    df_bus_stops.columns = ['バス停名', 'lat', 'lon']
    df_bus_stops = df_bus_stops.drop_duplicates(subset=['バス停名']).reset_index(drop=True)
except FileNotFoundError:
    st.error("【エラー】'stops.txt' が見つかりません。同じフォルダに置いてください。")
    st.stop()

# 高精度な距離計算関数（ヒュベニの公式）
def cal_distance(lat1, lon1, lat2, lon2):
    rad_lat1, rad_lon1 = math.radians(lat1), math.radians(lon1)
    rad_lat2, rad_lon2 = math.radians(lat2), math.radians(lon2)
    lat_diff, lon_diff = rad_lat1 - rad_lat2, rad_lon1 - rad_lon2
    lat_ave = (rad_lat1 + rad_lat2) / 2.0
    a, b = 6378137.0, 6356752.314245
    e2 = (a**2 - b**2) / (a**2)
    sin_lat_ave = math.sin(lat_ave)
    w = math.sqrt(1.0 - e2 * sin_lat_ave**2)
    m = a * (1.0 - e2) / (w**3)
    n = a / w
    distance_m = math.sqrt((lat_diff * m)**2 + (lon_diff * n * math.cos(lat_ave))**2)
    return distance_m / 1000.0

# 🌐 2. GPSによる現在地の自動取得
loc = get_geolocation()
if loc:
    current_lat = loc['coords']['latitude']
    current_lon = loc['coords']['longitude']
else:
    current_lat, current_lon = 40.7836, 140.7869 # 初期値（青森大学周辺：幸畑）

# セッション状態を使って目的地の座標を保持
if "t_lat" not in st.session_state:
    st.session_state.t_lat, st.session_state.t_lon = 40.8294, 140.7339 # 初期値は青森駅

# 🎯 3. サイドバーで目的地の入力方法を選択
st.sidebar.header("🏁 目的地の設定")
input_method = st.sidebar.radio("目的地の指定方法を選んでください：", ("地図上をタップして選ぶ", "住所や施設名を入力する"))

# ── 住所入力モード ──
if input_method == "住所や施設名を入力する":
    address_input = st.sidebar.text_input("住所や施設名を入力（例：青森市役所、新青森駅）", "")
    if address_input:
        try:
            geolocator = Nominatim(user_agent="aomori_bus_app_cloud")
            location_res = geolocator.geocode(f"青森県 {address_input}")
            if location_res:
                st.session_state.t_lat = location_res.latitude
                st.session_state.t_lon = location_res.longitude
                st.sidebar.success("🔍 目的地を特定しました！")
        except:
            st.sidebar.error("検索エラーが発生しました。")

# 🔍 4. 近くのバス停を探す計算
df_bus_stops['現在地からの距離(km)'] = df_bus_stops.apply(lambda row: cal_distance(current_lat, current_lon, row['lat'], row['lon']), axis=1)
nearest_current = df_bus_stops.loc[df_bus_stops['現在地からの距離(km)'].idxmin()]

df_bus_stops['目的地からの距離(km)'] = df_bus_stops.apply(lambda row: cal_distance(st.session_state.t_lat, st.session_state.t_lon, row['lat'], row['lon']), axis=1)
nearest_target = df_bus_stops.loc[df_bus_stops['目的地からの距離(km)'].idxmin()]

# 📢 5. 画面のレイアウト
col_info, col_map = st.columns([1, 2]) # 左をすっきり、右の地図を広く

with col_info:
    st.subheader("📌 案内結果")
    st.write(f"🔵 **現在地** に一番近いバス停:\n**{nearest_current['バス停名']}** ({nearest_current['現在地からの距離(km)']:.2f} km)")
    st.write("---")
    st.info(f"🏁 **目的地** に一番近いバス停:\n\n**{nearest_target['バス停名']}**\n(約 {nearest_target['目的地からの距離(km)']:.2f} km)")
    
    if input_method == "地図上をタップして選ぶ":
        st.markdown("💡 **スマホ・自宅Wi-Fiで開いたときの操作法**:\n右の地図上の行きたい場所を**タップ（クリック）**してください。緑の目的地ピンが移動し、最寄りのバス停が自動計算されます。")

with col_map:
    st.subheader("🗺️ 周辺地図（公開後、正常表示されます）")
    
    # クラウド公開時にも100%安全に表示できる「OpenStreetMap」をベースに構築
    m = folium.Map(location=[st.session_state.t_lat, st.session_state.t_lon], zoom_start=13)
    
    # 現在地に青いピン
    folium.Marker([current_lat, current_lon], tooltip="現在地", icon=folium.Icon(color="blue", icon="user")).add_to(m)
    # 目的地に緑のピン
    folium.Marker([st.session_state.t_lat, st.session_state.t_lon], tooltip="目的地", icon=folium.Icon(color="green", icon="flag")).add_to(m)
    
    # 周辺のバス停を赤いドット（サークルマーカー）で全プロット（動作を軽くするため）
    for _, row in df_bus_stops.iterrows():
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=5,
            popup=row['バス停名'],
            color="red",
            fill=True,
            fill_color="red"
        ).add_to(m)
    
    # Streamlit上で動く動的地図を出力し、クリックを監視
    map_data = st_folium(m, width="100%", height=600)
    
    # 地図がタップされたら、目的地の座標を上書きして再描画
    if input_method == "地図上をタップして選ぶ" and map_data and map_data.get("last_clicked"):
        clicked = map_data["last_clicked"]
        st.session_state.t_lat = clicked["lat"]
        st.session_state.t_lon = clicked["lng"]
        st.rerun()
