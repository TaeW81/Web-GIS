"""최소 지도 테스트 - st_folium이 정상 작동하는지 확인"""
import streamlit as st
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="지도 테스트", layout="wide")
st.title("🗺️ 최소 지도 테스트")

# 가장 기본적인 folium 지도 (서울 중심)
m = folium.Map(location=[37.5665, 126.9780], zoom_start=12)

st.write("--- 아래에 지도가 보여야 합니다 ---")

# 가장 단순한 st_folium 호출
result = st_folium(m, width=700, height=500)

st.write("--- 위에 지도가 보여야 합니다 ---")
st.write("st_folium 반환값:", result)
