import streamlit as st

from src.arrivals.page import show as show_arrivals
from src.osg.page import show as show_osg
from src.sales.page import show as show_sales_forecast

st.set_page_config(
    page_title="Bibicall Analytics",
    layout="wide",
)

# 📌 Боковое меню
st.sidebar.title("📊 Навигация")

page = st.sidebar.radio(
    "Выберите раздел",
    [
        "🧊 ОСГ",
        "🚢 ПРИХОДЫ",
        "📈 ПРОДАЖИ прогноз",
        "📊 ПРОГНОЗ - приходы, продажи, сток",
        "🚨 Риски OOS, Overstock",
        "🎯 KPI SKU",
        "💰 ДЗ",
        "🏥 РОДДОМА",
        "📝 Еженедельный отчет",
        "🔄 Замена СИСЛИНК",
    ]
)

# 📌 Роутинг страниц
if page == "🧊 ОСГ":
    show_osg()

elif page == "🚢 ПРИХОДЫ":
    show_arrivals()

elif page == "📈 ПРОДАЖИ прогноз":
    show_sales_forecast()

elif page == "📊 ПРОГНОЗ - приходы, продажи, сток":
    st.title("📊 ПРОГНОЗ - приходы, продажи, сток")
    st.info("Раздел в разработке")

elif page == "🚨 Риски OOS, Overstock":
    st.title("🚨 Риски OOS, Overstock")
    st.info("Раздел в разработке")

elif page == "🎯 KPI SKU":
    st.title("🎯 KPI SKU")
    st.info("Раздел в разработке")

elif page == "💰 ДЗ":
    st.title("💰 ДЗ")
    st.info("Раздел в разработке")

elif page == "🏥 РОДДОМА":
    st.title("🏥 РОДДОМА")
    st.info("Раздел в разработке")

elif page == "📝 Еженедельный отчет":
    st.title("📝 Еженедельный отчет")
    st.info("Раздел в разработке")

elif page == "🔄 Замена СИСЛИНК":
    st.title("🔄 Замена СИСЛИНК")
    st.info("Раздел в разработке")