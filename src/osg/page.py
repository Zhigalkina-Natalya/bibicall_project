import re
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from src.config import RAW_DATA_DIR
from src.loader import load_latest_file
from src.osg.calculator import calculate_osg
from src.osg.exporter import export_osg_table
from src.osg.quality import run_quality_diagnostics
from src.osg.presentation import sort_full_stock_view, sort_small_stock_view
from src.osg.rules import (
    RISK_LEVELS,
    build_urgent_sales,
    count_attention_groups,
    get_risk_level,
    validate_and_split_stock,
)
from src.osg.transformer import (
    clean_columns,
    rename_columns,
    remove_service_rows,
    convert_dates,
    extract_weight,
    transform_category,
    normalize_data_types,
    normalize_sku,
)
from src.validator import run_all_checks


@st.cache_data
def prepare_data() -> pd.DataFrame:
    """
    Загружает последний файл из папки raw,
    выполняет преобразования и считает ОСГ.
    """
    df = load_latest_file(RAW_DATA_DIR)

    df = clean_columns(df)
    df = rename_columns(df)
    df = normalize_sku(df)
    df = normalize_data_types(df)
    df = remove_service_rows(df)
    df = convert_dates(df)
    df = extract_weight(df)
    df = transform_category(df)
    df = calculate_osg(df)

    return df


def get_report_date() -> str:
    """
    Определяет дату отчёта из имени последнего файла формата osg_YYYY_MM_DD.xlsx.
    Если дату найти не удалось, возвращает сегодняшнюю дату.
    """
    files = [
        file for file in RAW_DATA_DIR.glob("*.xls*")
        if not file.name.startswith("~$")
    ]

    if not files:
        return datetime.today().strftime("%d.%m.%Y")

    latest_file = max(files, key=lambda x: x.stat().st_mtime)
    match = re.search(r"(\d{4})_(\d{2})_(\d{2})", latest_file.name)

    if not match:
        return datetime.today().strftime("%d.%m.%Y")

    year, month, day = match.groups()
    return f"{day}.{month}.{year}"


def color_osg(val):
    """
    Возвращает цвет ячейки для ОСГ %.
    """
    if pd.isna(val):
        return ""

    if val >= 75:
        return "background-color: #006400; color: white"
    if val >= 70:
        return "background-color: #2ecc71; color: black"
    if val >= 66:
        return "background-color: #b8e986; color: black"
    if val >= 60:
        return "background-color: #f1c40f; color: black"
    if val >= 50:
        return "background-color: #f39c12; color: black"
    if val >= 40:
        return "background-color: #e74c3c; color: white"
    if val >= 20:
        return "background-color: #c0392b; color: white"
    return "background-color: #2c2c2c; color: white"


def format_int(value) -> str:
    """
    Форматирует целые числа с пробелом в тысячах.
    """
    if pd.isna(value):
        return ""
    return f"{int(round(value)):,.0f}".replace(",", " ")


def format_percent(value) -> str:
    """
    Форматирует процент до 2 знаков после запятой.
    """
    if pd.isna(value):
        return ""

    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") + "%"


def format_weight(value) -> str:
    """
    Форматирует вес.
    """
    if pd.isna(value):
        return ""

    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def style_table(df: pd.DataFrame, osg_column: str):
    """
    Применяет формат чисел и цвет ОСГ.
    """
    formatters = {
        "Остаток": format_int,
        "Зарезервировано": format_int,
        "Свободный остаток": format_int,
        "Вес": format_weight,
        osg_column: format_percent,
    }
    if "Доля резерва, %" in df.columns:
        formatters["Доля резерва, %"] = format_percent

    return (
        df.style
        .format(formatters)
        .map(color_osg, subset=[osg_column])
    )


def get_avg_osg_color(value: float) -> str:
    """
    Возвращает цвет для среднего ОСГ.
    """
    if pd.isna(value):
        return "#34495e"

    if value >= 70:
        return "#2ecc71"

    if value >= 60:
        return "#f39c12"

    return "#e74c3c"


def kpi_color(label, value, color):
    """
    Рисует KPI-блок с цветным значением.
    """
    return f"""
        <div style='text-align: center;'>
            <div style='font-size: 13px; color: #777;'>{label}</div>
            <div style='font-size: 28px; font-weight: 700; color: {color};'>
                {value}
            </div>
        </div>
    """


def show_excel_download(
        df: pd.DataFrame,
        sheet_name: str,
        file_name: str,
        key: str,
        risk_values: pd.Series | None = None,
) -> None:
    """Displays a download button for a formatted XLSX table."""
    st.download_button(
        label="⬇️ Скачать Excel",
        data=export_osg_table(df, sheet_name, risk_values=risk_values),
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=key,
    )


def show():
    """
    Отображает страницу ОСГ.
    """
    full_df = prepare_data()
    full_df["Риск"] = full_df["ОСГ %"].apply(get_risk_level)
    quality_summary = run_quality_diagnostics(full_df)

    errors, df, small_stock_df = validate_and_split_stock(
        full_df,
        run_all_checks,
    )

    df_view = df.copy()
    df_view["Срок годности"] = df_view["Срок годности"].dt.strftime("%d.%m.%Y")
    df_view["ОСГ %"] = df_view["ОСГ %"].round(2)

    report_date = get_report_date()
    export_date = pd.to_datetime(
        report_date,
        format="%d.%m.%Y",
    ).strftime("%Y-%m-%d")

    header_col1, header_col2 = st.columns([3, 1])

    with header_col1:
        st.markdown("## 📦 ОСГ: анализ остатков")

    with header_col2:
        st.markdown(f"**на {report_date}**")

    main_col, filter_col = st.columns([5, 1.2])

    with filter_col:
        st.subheader("Фильтры")

        categories = sorted(df_view["Категория"].dropna().unique())
        selected_categories = st.multiselect(
            "Категория",
            categories,
            default=categories,
        )

        warehouses = sorted(df_view["Склад"].dropna().unique())
        selected_warehouses = st.multiselect(
            "Склад",
            warehouses,
            default=warehouses,
        )

        risk_levels = RISK_LEVELS

        selected_risks = st.multiselect(
            "Риск",
            risk_levels,
            default=risk_levels,
        )

    filtered_df = df_view[
        df_view["Категория"].isin(selected_categories)
        & df_view["Склад"].isin(selected_warehouses)
        & df_view["Риск"].isin(selected_risks)
        ]

    kpi_table = (
        filtered_df
        .groupby(["Категория", "SKU", "Срок годности"], as_index=False)
        .agg({
            "Остаток": "sum",
            "Зарезервировано": "sum",
            "Свободный остаток": "sum",
            "ОСГ %": "min",
        })
    )

    critical_count = len(kpi_table[kpi_table["ОСГ %"] < 50])
    risk_count = len(
        kpi_table[
            (kpi_table["ОСГ %"] >= 50)
            & (kpi_table["ОСГ %"] < 60)
            ]
    )
    attention_count = count_attention_groups(kpi_table)
    avg_osg = kpi_table["ОСГ %"].mean()
    total_free = kpi_table["Свободный остаток"].sum()

    with main_col:
        col1, col2, col3, col4, col5 = st.columns(5)

        col1.markdown(
            kpi_color("🔴 Критично (<50%)", critical_count, "#e74c3c"),
            unsafe_allow_html=True,
        )

        col2.markdown(
            kpi_color("🟠 Риск (50–60%)", risk_count, "#f39c12"),
            unsafe_allow_html=True,
        )

        col3.markdown(
            kpi_color("🟡 Внимание (60–<66%)", attention_count, "#f1c40f"),
            unsafe_allow_html=True,
        )

        col4.markdown(
            kpi_color(
                "🟢 Средний ОСГ",
                format_percent(avg_osg),
                get_avg_osg_color(avg_osg),
            ),
            unsafe_allow_html=True,
        )

        col5.markdown(
            kpi_color("Свободный остаток", format_int(total_free), "#34495e"),
            unsafe_allow_html=True,
        )

        st.divider()

        with st.expander("📊 Остатки по категориям", expanded=True):
            category_chart = (
                filtered_df
                .groupby("Категория", as_index=False)["Свободный остаток"]
                .sum()
                .sort_values("Свободный остаток", ascending=False)
            )

            category_chart["Свободный остаток, тыс."] = (
                    category_chart["Свободный остаток"] / 1000
            )

            category_chart["Подпись"] = (
                category_chart["Свободный остаток, тыс."]
                .map(
                    lambda x: (
                            f"{x:.2f}"
                            .rstrip("0")
                            .rstrip(".")
                            .replace(".", ",")
                            + " тыс."
                    )
                )
            )

            fig_category = px.bar(
                category_chart,
                x="Категория",
                y="Свободный остаток, тыс.",
                title="Свободный остаток по категориям",
                text="Подпись",
            )

            fig_category.update_traces(
                textposition="inside",
                textfont=dict(color="white"),
                hovertemplate="%{text}<extra></extra>",
            )

            fig_category.update_layout(
                yaxis_title="тыс. шт",
            )

            st.plotly_chart(fig_category, width="stretch")

        with st.expander("🚨 Что нужно срочно продать", expanded=True):
            urgent_sales = build_urgent_sales(filtered_df)

            urgent_sales["Риск"] = urgent_sales["ОСГ %"].apply(get_risk_level)

            urgent_sales = urgent_sales[
                [
                    "Категория",
                    "SKU",
                    "Срок годности",
                    "ОСГ %",
                    "Риск",
                    "Остаток",
                    "Зарезервировано",
                    "Свободный остаток",
                    "Доля резерва, %",
                ]
            ]

            st.dataframe(
                style_table(urgent_sales, "ОСГ %"),
                width="stretch",
                hide_index=True,
            )
            show_excel_download(
                urgent_sales,
                "Срочные продажи",
                f"osg_urgent_sales_{export_date}.xlsx",
                "download_osg_urgent_sales",
            )

        with st.container():
            with st.expander("⚠️ SKU по ОСГ с риском", expanded=True):
                risk_table = (
                    filtered_df
                    .groupby(["Категория", "SKU", "Срок годности"], as_index=False)
                    .agg({
                        "Остаток": "sum",
                        "Зарезервировано": "sum",
                        "Свободный остаток": "sum",
                        "ОСГ %": "min",
                    })
                    .sort_values("ОСГ %")
                )

                risk_table["Риск"] = risk_table["ОСГ %"].apply(get_risk_level)

                risk_table = risk_table[
                    [
                        "Категория",
                        "SKU",
                        "Срок годности",
                        "ОСГ %",
                        "Риск",
                        "Остаток",
                        "Зарезервировано",
                        "Свободный остаток",
                    ]
                ]

                st.dataframe(
                    style_table(risk_table, "ОСГ %"),
                    width="stretch",
                    hide_index=True,
                )
                show_excel_download(
                    risk_table,
                    "SKU по риску",
                    f"osg_risk_sku_{export_date}.xlsx",
                    "download_osg_risk_sku",
                )

        with st.container():
            with st.expander("📋 Сводная таблица по категориям и SKU", expanded=True):
                pivot_table = (
                    filtered_df
                    .groupby(["Категория", "SKU"], as_index=False)
                    .agg({
                        "Остаток": "sum",
                        "Зарезервировано": "sum",
                        "Свободный остаток": "sum",
                        "ОСГ %": "min",
                    })
                    .sort_values(["Категория", "ОСГ %"])
                )

                pivot_table = pivot_table.rename(columns={"ОСГ %": "min ОСГ %"})

                st.dataframe(
                    style_table(pivot_table, "min ОСГ %"),
                    width="stretch",
                    hide_index=True,
                )
                show_excel_download(
                    pivot_table,
                    "Сводная по SKU",
                    f"osg_summary_sku_{export_date}.xlsx",
                    "download_osg_summary_sku",
                    risk_values=pivot_table["min ОСГ %"].apply(
                        get_risk_level
                    ),
                )

        with st.expander(
                f"📦 Малые остатки ≤ 100 шт. ({len(small_stock_df)})",
                expanded=False,
        ):
            st.caption(
                "Позиции сохранены для контроля склада и возможного использования "
                "для образцов, маркетинга, благотворительности или внутренних нужд."
            )

            small_stock_view = small_stock_df.copy()
            small_stock_view["Срок годности"] = (
                small_stock_view["Срок годности"].dt.strftime("%d.%m.%Y")
            )
            small_stock_view["ОСГ %"] = small_stock_view["ОСГ %"].round(2)
            small_stock_view = sort_small_stock_view(small_stock_view)
            small_stock_view = small_stock_view[[
                "Склад",
                "Категория",
                "SKU",
                "Контейнер",
                "Срок годности",
                "ОСГ %",
                "Остаток",
                "Зарезервировано",
                "Свободный остаток",
            ]]

            st.dataframe(
                style_table(small_stock_view, "ОСГ %"),
                width="stretch",
                hide_index=True,
            )
            show_excel_download(
                small_stock_view,
                "Малые остатки",
                f"osg_small_stock_{export_date}.xlsx",
                "download_osg_small_stock",
                risk_values=small_stock_df["Риск"],
            )

        with st.expander("📋 Полная таблица со складами", expanded=False):
            clean_df = filtered_df.copy()

            clean_df = clean_df.drop(
                columns=[
                    "Unnamed: 0",
                    "Категория_исходная",
                    "Срок годности_исходная",
                ],
                errors="ignore",
            )

            clean_df = clean_df.rename(columns={"total_days": "days_total"})
            clean_df = sort_full_stock_view(clean_df)

            final_columns = [
                "Склад",
                "Контейнер",
                "Вес",
                "Категория",
                "SKU",
                "Срок годности",
                "ОСГ %",
                "Риск",
                "Остаток",
                "Зарезервировано",
                "Свободный остаток",
                "days_left",
                "days_total",
            ]

            clean_df = clean_df[final_columns]

            st.dataframe(
                style_table(clean_df, "ОСГ %"),
                width="stretch",
                hide_index=True,
            )
            show_excel_download(
                clean_df,
                "Остатки по складам",
                f"osg_full_stock_{export_date}.xlsx",
                "download_osg_full_stock",
            )

        with st.expander("🧮 Калькулятор ОСГ", expanded=False):
            calculator_df = df.copy()
            calculator_df = calculator_df[calculator_df["Остаток"] > 100]

            st.markdown("#### 1. Узнать дату наступления нужного % ОСГ")

            calc_col1, calc_col2, calc_col3 = st.columns(3)

            selected_sku = calc_col1.selectbox(
                "Выберите SKU",
                sorted(calculator_df["SKU"].dropna().unique()),
                key="calc_sku_1",
            )

            sku_df = calculator_df[calculator_df["SKU"] == selected_sku]

            selected_expiry = calc_col2.selectbox(
                "Выберите срок годности",
                sorted(
                    sku_df["Срок годности"]
                    .dropna()
                    .dt.strftime("%d.%m.%Y")
                    .unique()
                ),
                key="calc_expiry_1",
            )

            target_osg = calc_col3.number_input(
                "Введите % ОСГ",
                min_value=0.0,
                max_value=100.0,
                value=60.0,
                step=0.1,
                key="target_osg",
            )

            expiry_date = pd.to_datetime(selected_expiry, format="%d.%m.%Y")

            selected_row = sku_df[
                sku_df["Срок годности"] == expiry_date
                ].iloc[0]

            total_days = selected_row["total_days"]
            days_left_target = total_days * (target_osg / 100)
            target_date = expiry_date - pd.to_timedelta(days_left_target, unit="D")

            st.success(
                f"Дата наступления ОСГ {format_percent(target_osg)}: "
                f"{target_date.strftime('%d.%m.%Y')}"
            )

            st.divider()

            st.markdown("#### 2. Узнать ОСГ на выбранную дату")

            calc_col4, calc_col5, calc_col6 = st.columns(3)

            selected_sku_2 = calc_col4.selectbox(
                "Выберите SKU",
                sorted(calculator_df["SKU"].dropna().unique()),
                key="calc_sku_2",
            )

            sku_df_2 = calculator_df[calculator_df["SKU"] == selected_sku_2]

            selected_expiry_2 = calc_col5.selectbox(
                "Выберите срок годности",
                sorted(
                    sku_df_2["Срок годности"]
                    .dropna()
                    .dt.strftime("%d.%m.%Y")
                    .unique()
                ),
                key="calc_expiry_2",
            )

            selected_date = calc_col6.date_input(
                "Введите дату",
                format="DD.MM.YYYY",
                key="calc_date_2",
            )

            expiry_date_2 = pd.to_datetime(selected_expiry_2, format="%d.%m.%Y")
            selected_date = pd.to_datetime(selected_date)

            selected_row_2 = sku_df_2[
                sku_df_2["Срок годности"] == expiry_date_2
                ].iloc[0]

            total_days_2 = selected_row_2["total_days"]
            days_left_2 = (expiry_date_2 - selected_date).days
            osg_on_date = (days_left_2 / total_days_2) * 100

            st.success(
                f"ОСГ на дату {selected_date.strftime('%d.%m.%Y')}: "
                f"{format_percent(osg_on_date)}"
            )

        st.divider()

        if errors:
            st.error("Есть ошибки в данных")
            for error in errors:
                st.write(f"• {error}")
        else:
            st.success("Проверка пройдена: ошибок не найдено")

        with st.expander("🔎 Диагностика качества полного набора", expanded=False):
            quality_table = pd.DataFrame(
                quality_summary.items(),
                columns=["Проверка", "Количество строк"],
            )
            st.dataframe(quality_table, width="stretch", hide_index=True)
