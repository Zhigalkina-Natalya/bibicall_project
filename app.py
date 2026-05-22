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
        "📊 Приходы, продажи, сток",
        "🚨 Риски OOS",
        "🏥 РОДДОМА",
        "📝 Еженедельный отчет",
    ]
)

# 📌 Роутинг страниц
if page == "🧊 ОСГ":
    show_osg()

elif page == "🚢 ПРИХОДЫ":
    show_arrivals()

elif page == "📈 ПРОДАЖИ прогноз":
    show_sales_forecast()

elif page == "📊 Приходы, продажи, сток":
    st.title("📊 Приходы, продажи, сток")
    st.info("Раздел в разработке")

elif page == "🚨 Риски OOS":
    st.title("🚨 Риски OOS")
    st.info("Раздел в разработке")

elif page == "🏥 РОДДОМА":
    st.title("🏥 РОДДОМА")
    st.info("Раздел в разработке")

elif page == "📝 Еженедельный отчет":
    st.title("📝 Еженедельный отчет")
    st.info("Раздел в разработке")
