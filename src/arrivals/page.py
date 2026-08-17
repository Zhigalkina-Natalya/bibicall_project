from io import BytesIO
import pandas as pd
import plotly.express as px
import streamlit as st

from src.arrivals.calculator import (
    get_value_column,
    make_week_label,
    normalize_container,
    replace_plan_with_fact,
)
from src.arrivals.loader import (
    load_all_excel_files,
    load_latest_excel_file,
    load_product_mapping,
)
from src.arrivals.transformer import (
    transform_actual_arrivals,
    transform_daniel_arrivals,
    transform_history_arrivals,
)
from src.config import (
    ARRIVALS_ACTUAL_DIR,
    ARRIVALS_DANIEL_DIR,
    ARRIVALS_HISTORY_DIR,
    PRODUCT_MAPPING_FILE,
)

CATEGORY_ORDER = [
    "АМАЛТЕЯ",
    "КАШИ",
    "НЭННИ 400",
    "НЭННИ 800",
]

FORMULA_ORDER = [
    "АМАЛТЕЯ",
    "КАШИ",
    "НЭННИ Классика",
    "НЭННИ 1",
    "НЭННИ 2",
    "НЭННИ 3",
    "НЭННИ 4",
]

DANIEL_SKU_ORDER = [
    "NC4",
    "N14",
    "N24",
    "N34",
    "N44",
    "NC8",
    "N18",
    "N28",
    "N38",
    "N48",
    "Buck",
    "Oats",
    "Rice",
    "Corn",
]


@st.cache_data
def prepare_arrivals_data() -> pd.DataFrame:
    """
    Загружает историю, факт 1С и план Дениэла.
    """
    mapping_df = load_product_mapping(PRODUCT_MAPPING_FILE)

    history_raw = load_all_excel_files(
        ARRIVALS_HISTORY_DIR,
        header=0,
    )

    actual_raw = load_latest_excel_file(
        ARRIVALS_ACTUAL_DIR,
        header=6,
    )

    daniel_raw = load_latest_excel_file(
        ARRIVALS_DANIEL_DIR,
        header=0,
    )

    history_df = transform_history_arrivals(history_raw, mapping_df)
    actual_df = transform_actual_arrivals(actual_raw, mapping_df)
    daniel_df = transform_daniel_arrivals(daniel_raw, mapping_df)

    df = pd.concat(
        [history_df, actual_df, daniel_df],
        ignore_index=True,
    )

    if df.empty:
        return df

    df["Контейнер"] = df["Контейнер"].apply(normalize_container)
    df["Контейнер"] = df["Контейнер"].astype(str).str.strip()
    df["Источник"] = df["Источник"].fillna("Не указан")
    df["Категория"] = df["Категория"].fillna("Не определено")
    df["Формула"] = df["Формула"].fillna("Не определено")
    df["SKU"] = df["SKU"].fillna("Не определено")

    df = make_week_label(df)

    return df


def format_number(value: float) -> str:
    """
    Форматирует число с пробелами:
    30648 -> 30 648
    """
    if pd.isna(value):
        return "0"

    return f"{value:,.0f}".replace(",", " ")


def get_period_column(df: pd.DataFrame, period_type: str) -> tuple[pd.DataFrame, str]:
    """
    Добавляет короткую колонку периода для графиков.
    """
    df = df.copy()

    df["Дата начала недели"] = pd.to_datetime(
        df["Дата начала недели"],
        errors="coerce",
    )

    if period_type == "По годам":
        df["Период"] = df["Год"].astype(int).astype(str)
        df["Период_сортировка"] = df["Год"].astype(int)
    else:
        year = df["Дата начала недели"].dt.year.astype(int)
        quarter = df["Дата начала недели"].dt.quarter.astype(int)

        df["Период"] = year.astype(str) + "-К" + quarter.astype(str)
        df["Период_сортировка"] = year * 10 + quarter

    df["Период"] = df["Период"].astype(str)

    return df, "Период_сортировка"


def get_ordered_values(values, order_list):
    """
    Возвращает значения в бизнес-порядке, а неизвестные добавляет в конец.
    """
    values = list(values)

    ordered = [item for item in order_list if item in values]
    other = sorted([item for item in values if item not in ordered])

    return ordered + other


def make_finance_table(
        df: pd.DataFrame,
        value_column: str,
        current_year: int,
) -> pd.DataFrame:
    """
    Таблица для финансового ассистента:
    факт 1С + весь незаменённый план Дениэла.
    Если плановая дата прошла, но факта нет — строка остаётся и получает статус задержки.
    """
    today = pd.Timestamp.today().normalize()

    finance_df = df[
        df["Источник"].isin(["Факт 1С", "План Дениэл"])
    ].copy()

    finance_df = finance_df[
        finance_df["Год"].astype("Int64").isin([current_year, current_year + 1])
    ].copy()

    if finance_df.empty:
        return pd.DataFrame()

    finance_df["SKU Daniel"] = finance_df["SKU Daniel"].fillna("").astype(str).str.strip()
    finance_df = finance_df[finance_df["SKU Daniel"] != ""]

    finance_df["Год"] = finance_df["Год"].astype("Int64").astype(str)
    finance_df["Квартал"] = finance_df["Дата начала недели"].dt.quarter
    finance_df["Месяц"] = finance_df["Дата начала недели"].dt.month
    finance_df["№ недели"] = finance_df["Номер недели"]
    finance_df["№ конт"] = finance_df["Контейнер"]

    finance_df["Статус"] = finance_df.apply(
        lambda row: (
            "✅ Факт"
            if row["Источник"] == "Факт 1С"
            else (
                "⚠️ Плановая дата прошла, факта нет"
                if row["Дата начала недели"] < today
                else "🟡 План"
            )
        ),
        axis=1,
    )

    table = (
        finance_df
        .pivot_table(
            index=[
                "Год",
                "Квартал",
                "Месяц",
                "№ недели",
                "№ конт",
                "Статус",
            ],
            columns="SKU Daniel",
            values=value_column,
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
    )

    table.columns.name = None

    base_columns = [
        "Год",
        "Квартал",
        "Месяц",
        "№ недели",
        "№ конт",
        "Статус",
    ]

    sku_columns = [col for col in table.columns if col not in base_columns]

    ordered_sku_columns = [
        sku for sku in DANIEL_SKU_ORDER
        if sku in sku_columns
    ]

    other_sku_columns = sorted([
        sku for sku in sku_columns
        if sku not in ordered_sku_columns
    ])

    final_sku_columns = ordered_sku_columns + other_sku_columns

    table = table[base_columns + final_sku_columns]

    current_year_rows = table[table["Год"] == str(current_year)]

    if not current_year_rows.empty:
        total_row = {
            "Год": f"ИТОГ {current_year}",
            "Квартал": "ИТОГ",
            "Месяц": "",
            "№ недели": "",
            "№ конт": "",
            "Статус": "",
        }

        for col in final_sku_columns:
            total_row[col] = current_year_rows[col].sum()

        table = pd.concat(
            [
                table[table["Год"] == str(current_year)],
                pd.DataFrame([total_row]),
                table[table["Год"] == str(current_year + 1)],
            ],
            ignore_index=True,
        )

    text_columns = [
        "Год",
        "Квартал",
        "Месяц",
        "№ недели",
        "№ конт",
        "Статус",
    ]

    for column in text_columns:
        if column in table.columns:
            table[column] = table[column].astype(str)

    return table


def style_finance_table(row):
    """
    Подсветка финансовой таблицы:
    - факт — зелёный
    - план — мягкий квартальный цвет
    - просроченный план без факта — розовый
    - итог — тёмно-красный
    """
    if str(row.get("Год", "")).startswith("ИТОГ"):
        return ["background-color: #b71c1c; color: white; font-weight: bold"] * len(row)

    status = row.get("Статус", "")

    if status == "✅ Факт":
        return ["background-color: #eaf7ea"] * len(row)

    if status == "⚠️ Плановая дата прошла, факта нет":
        return ["background-color: #fde2e2; color: #7a1f1f"] * len(row)

    try:
        quarter = int(row.get("Квартал", 0))
    except ValueError:
        quarter = 0

    colors = {
        1: "background-color: #eef5ff",
        2: "background-color: #eefaf1",
        3: "background-color: #fff8e6",
        4: "background-color: #f7eefc",
    }

    return [colors.get(quarter, "")] * len(row)


def dataframe_to_excel_bytes(df: pd.DataFrame) -> bytes:
    """
    Готовит Excel-файл для скачивания.
    """
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="План поставок")

    return output.getvalue()


def show():
    """
    Страница ПРИХОДЫ.
    """
    try:
        df = prepare_arrivals_data()

    except Exception as error:
        st.error("Ошибка загрузки данных")
        with st.expander("Показать ошибку", expanded=True):
            st.exception(error)
        return

    if df.empty:
        st.warning("Нет данных по приходам.")
        return

    df_all = df.copy()
    df = replace_plan_with_fact(df)

    st.markdown("## 🚢 ПРИХОДЫ")
    st.caption("История, факт 1С и план Дениэла с автоматической заменой плана фактом по контейнеру")

    with st.expander("🔎 Проверка загруженных данных", expanded=False):
        st.write("Строк:", len(df))
        st.write("Годы:", sorted(df["Год"].dropna().astype(int).unique()))
        st.write("Типы:", sorted(df["Тип данных"].dropna().unique()))
        st.write("Источники:", sorted(df["Источник"].dropna().unique()))
        st.dataframe(df.head(80), width="stretch")

    main_col, filter_col = st.columns([5, 1.25])

    with filter_col:
        st.subheader("Фильтры")

        years = sorted(df["Год"].dropna().astype(int).unique())

        selected_years = st.multiselect(
            "Год",
            years,
            default=years,
        )

        period_type = st.selectbox(
            "Период графика",
            [
                "По годам",
                "По кварталам",
            ],
            index=0,
        )

        categories = get_ordered_values(
            df["Категория"].dropna().unique(),
            CATEGORY_ORDER,
        )

        selected_categories = st.multiselect(
            "Категория",
            categories,
            default=categories,
        )

        formulas = get_ordered_values(
            df["Формула"].dropna().unique(),
            FORMULA_ORDER,
        )

        selected_formulas = st.multiselect(
            "Формула",
            formulas,
            default=formulas,
        )

        data_types = sorted(df["Тип данных"].dropna().unique())

        selected_data_types = st.multiselect(
            "Тип данных",
            data_types,
            default=data_types,
        )

        unit = st.radio(
            "Единица измерения",
            [
                "шт",
                "кг",
                "уп",
            ],
        )

        group_by = st.selectbox(
            "Группировка графиков",
            [
                "Тип данных",
                "Категория",
                "Формула",
            ],
        )

    filtered_df = df[
        df["Год"].astype("Int64").isin(selected_years)
        & df["Категория"].isin(selected_categories)
        & df["Формула"].isin(selected_formulas)
        & df["Тип данных"].isin(selected_data_types)
        ].copy()

    value_column = get_value_column(unit)

    current_year = pd.Timestamp.today().year

    kpi_df = filtered_df[
        filtered_df["Год"].astype("Int64") == current_year
        ].copy()

    if filtered_df.empty:
        with main_col:
            st.warning("По выбранным фильтрам данных нет.")
        return

    with main_col:
        total_value = kpi_df[value_column].sum()

        fact_value = kpi_df[
            kpi_df["Тип данных"] == "Факт"
            ][value_column].sum()

        plan_value = kpi_df[
            kpi_df["Тип данных"] == "План"
            ][value_column].sum()

        container_count = (
            kpi_df["Контейнер"]
            .replace(["", "nan", "None"], pd.NA)
            .dropna()
            .nunique()
        )

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(f"Всего за {current_year}", format_number(total_value))
        col2.metric(f"Факт за {current_year}", format_number(fact_value))
        col3.metric(f"План за {current_year}", format_number(plan_value))
        col4.metric(f"Контейнеров за {current_year}", container_count)

        st.divider()

        chart_df, sort_column = get_period_column(filtered_df, period_type)

        with st.expander("📈 Динамика приходов", expanded=True):
            period_chart = (
                chart_df
                .groupby(
                    ["Период", sort_column, group_by],
                    as_index=False,
                    dropna=False,
                )[value_column]
                .sum()
                .sort_values(sort_column)
            )

            if period_type == "По кварталам":
                period_chart["Год_графика"] = period_chart["Период"].str[:4]
                period_chart["Квартал_графика"] = (
                        "К" + period_chart["Период"].str[-1]
                )

                period_order = (
                    period_chart[["Период", sort_column]]
                    .drop_duplicates()
                    .sort_values(sort_column)["Период"]
                    .tolist()
                )

                tick_text = [
                    "К" + period[-1]
                    for period in period_order
                ]

                fig_period = px.bar(
                    period_chart,
                    x="Период",
                    y=value_column,
                    color=group_by,
                    title=f"Приходы: по кварталам | группировка: {group_by}",
                )

                fig_period.update_xaxes(
                    type="category",
                    tickmode="array",
                    tickvals=period_order,
                    ticktext=tick_text,
                    tickangle=0,
                    categoryorder="array",
                    categoryarray=period_order,
                )

                year_positions = (
                    period_chart[["Период", "Год_графика"]]
                    .drop_duplicates()
                    .groupby("Год_графика")["Период"]
                    .apply(list)
                    .to_dict()
                )

                for year, periods in year_positions.items():
                    middle_period = periods[len(periods) // 2]

                    fig_period.add_annotation(
                        x=middle_period,
                        y=-0.18,
                        text=year,
                        showarrow=False,
                        xref="x",
                        yref="paper",
                        font=dict(size=12),
                    )

                fig_period.update_layout(
                    barmode="stack",
                    xaxis_title="",
                    yaxis_title=unit,
                    height=560,
                    margin=dict(b=120),
                )

            else:
                period_order = (
                    period_chart[["Период", sort_column]]
                    .drop_duplicates()
                    .sort_values(sort_column)["Период"]
                    .tolist()
                )

                fig_period = px.bar(
                    period_chart,
                    x="Период",
                    y=value_column,
                    color=group_by,
                    title=f"Приходы: по годам | группировка: {group_by}",
                )

                fig_period.update_xaxes(
                    type="category",
                    tickmode="array",
                    tickvals=period_order,
                    ticktext=period_order,
                    tickangle=0,
                    categoryorder="array",
                    categoryarray=period_order,
                )

                fig_period.update_layout(
                    barmode="stack",
                    xaxis_title="Год",
                    yaxis_title=unit,
                    height=520,
                    margin=dict(b=80),
                )

            st.plotly_chart(
                fig_period,
                width="stretch",
            )

        with st.expander("🧾 Сверка по контейнерам", expanded=False):
            current_year = pd.Timestamp.today().year

            unit_suffix = {
                "шт": "шт",
                "кг": "кг",
                "уп": "уп",
            }[unit]

            plan_column_name = f"План, {unit_suffix}"
            fact_column_name = f"Факт, {unit_suffix}"
            diff_column_name = f"Разница, {unit_suffix}"

            compare_df = df_all[
                (df_all["Год"].astype("Int64") == current_year)
                & (df_all["Источник"].isin(["Факт 1С", "План Дениэл"]))
                ].copy()

            compare_df["Контейнер"] = compare_df["Контейнер"].apply(normalize_container)

            # Для сверки по контейнерам берём только строки, где контейнер указан
            compare_df = compare_df[
                compare_df["Контейнер"].notna()
                & (~compare_df["Контейнер"].isin(["", "nan", "None"]))
                ].copy()

            plan_containers = set(
                compare_df[
                    compare_df["Источник"] == "План Дениэл"
                    ]["Контейнер"]
            )

            fact_containers = set(
                compare_df[
                    compare_df["Источник"] == "Факт 1С"
                    ]["Контейнер"]
            )

            all_containers = sorted(
                plan_containers.union(fact_containers),
                key=lambda x: int(x) if str(x).isdigit() else str(x),
            )

            rows = []

            for container in all_containers:
                plan_part = compare_df[
                    (compare_df["Источник"] == "План Дениэл")
                    & (compare_df["Контейнер"] == container)
                    ]

                fact_part = compare_df[
                    (compare_df["Источник"] == "Факт 1С")
                    & (compare_df["Контейнер"] == container)
                    ]

                plan_sku = set(plan_part["SKU"].dropna().astype(str))
                fact_sku = set(fact_part["SKU"].dropna().astype(str))

                if not plan_part.empty and not fact_part.empty:
                    if plan_sku == fact_sku:
                        status = "✅ План совпал с фактом"
                    else:
                        status = "⚠️ Состав изменился"
                elif not plan_part.empty:
                    status = "🟡 Только план"
                else:
                    status = "🔵 Только факт"

                rows.append({
                    "Контейнер": container,
                    "Статус": status,
                    "План SKU": ", ".join(sorted(plan_sku)),
                    "Факт SKU": ", ".join(sorted(fact_sku)),
                    plan_column_name: plan_part[value_column].sum(),
                    fact_column_name: fact_part[value_column].sum(),
                    diff_column_name: (
                            fact_part[value_column].sum()
                            - plan_part[value_column].sum()
                    ),
                })

            container_compare = pd.DataFrame(rows)

            def highlight_status(row):
                status = row["Статус"]

                if status == "✅ План совпал с фактом":
                    return ["background-color: #d4edda"] * len(row)

                if status == "⚠️ Состав изменился":
                    return ["background-color: #f8d7da"] * len(row)

                if status == "🟡 Только план":
                    return ["background-color: #fff3cd"] * len(row)

                if status == "🔵 Только факт":
                    return ["background-color: #d1ecf1"] * len(row)

                return [""] * len(row)

            if container_compare.empty:
                st.info("Нет данных для сверки контейнеров.")
            else:
                st.dataframe(
                    container_compare
                    .style
                    .apply(highlight_status, axis=1)
                    .format({
                        plan_column_name: lambda x: format_number(x),
                        fact_column_name: lambda x: format_number(x),
                        diff_column_name: lambda x: format_number(x),
                    }),
                    width="stretch",
                    height=600,
                )

        with st.expander("📌 План ПОСТАВОК vs факт + незакрытый план", expanded=True):
            current_year = pd.Timestamp.today().year

            unit_suffix = {
                "шт": "шт",
                "кг": "кг",
                "уп": "уп",
            }[unit]

            plan_column_name = f"План, {unit_suffix}"
            forecast_column_name = f"Факт + незакрытый план, {unit_suffix}"
            deviation_column_name = f"Отклонение, {unit_suffix}"

            full_year_plan = df_all[
                (df_all["Год"].astype("Int64") == current_year)
                & (df_all["Источник"] == "План Дениэл")
                ].copy()

            year_df = df[
                (df["Год"].astype("Int64") == current_year)
                & (df["Источник"].isin(["Факт 1С", "План Дениэл"]))
                ].copy()

            combined_plan_fact = year_df.copy()

            plan_table = (
                full_year_plan
                .groupby(["Категория", "SKU", "Формула"], as_index=False)
                .agg({value_column: "sum"})
                .rename(columns={value_column: plan_column_name})
            )

            forecast_table = (
                combined_plan_fact
                .groupby(["Категория", "SKU", "Формула"], as_index=False)
                .agg({value_column: "sum"})
                .rename(columns={value_column: forecast_column_name})
            )

            plan_vs_fact = plan_table.merge(
                forecast_table,
                how="outer",
                on=["Категория", "SKU", "Формула"],
            )

            plan_vs_fact[plan_column_name] = plan_vs_fact[plan_column_name].fillna(0)
            plan_vs_fact[forecast_column_name] = plan_vs_fact[forecast_column_name].fillna(0)

            plan_vs_fact[deviation_column_name] = (
                    plan_vs_fact[forecast_column_name]
                    - plan_vs_fact[plan_column_name]
            )

            plan_vs_fact = plan_vs_fact.sort_values(["Категория", "SKU"])

            total_forecast_value = plan_vs_fact[forecast_column_name].sum()
            total_plan_value = plan_vs_fact[plan_column_name].sum()
            total_deviation = plan_vs_fact[deviation_column_name].sum()

            total_row = {
                "Категория": "ИТОГО",
                "SKU": "",
                "Формула": "",
                plan_column_name: total_plan_value,
                forecast_column_name: total_forecast_value,
                deviation_column_name: total_deviation,
            }

            plan_vs_fact = pd.concat(
                [plan_vs_fact, pd.DataFrame([total_row])],
                ignore_index=True,
            )

            st.markdown(
                f"""
                **Итого по {current_year} году:**  
                План = **{format_number(total_plan_value)} {unit_suffix}**  
                Факт + незакрытый план = **{format_number(total_forecast_value)} {unit_suffix}**  
                Отклонение = **{format_number(total_deviation)} {unit_suffix}**
                """
            )

            def highlight_row(row):
                if row.get("Категория") == "ИТОГО":
                    return [
                        "background-color: #b71c1c; color: white; font-weight: bold"
                    ] * len(row)

                deviation = row[deviation_column_name]

                if pd.isna(deviation):
                    return [""] * len(row)

                if deviation > 0:
                    return [
                        "background-color: #d4edda; color: #155724"
                    ] * len(row)

                if deviation < 0:
                    return [
                        "background-color: #f8d7da; color: #721c24"
                    ] * len(row)

                return [
                    "background-color: #fff3cd; color: #856404"
                ] * len(row)

            st.dataframe(
                plan_vs_fact.style
                .format({
                    plan_column_name: lambda x: format_number(x),
                    forecast_column_name: lambda x: format_number(x),
                    deviation_column_name: lambda x: format_number(x),
                })
                .apply(
                    highlight_row,
                    axis=1,
                ),
                width="stretch",
                height=500,
            )

        with st.expander("💼 Таблица ПЛАН ПОСТАТОК для финансового ассистента", expanded=True):
            current_year = pd.Timestamp.today().year

            finance_table = make_finance_table(
                df=df,
                value_column=value_column,
                current_year=current_year,
            )

            if finance_table.empty:
                st.info("Нет данных для финансовой таблицы.")
            else:
                base_columns = [
                    "Год",
                    "Квартал",
                    "Месяц",
                    "№ недели",
                    "№ конт",
                    "Статус",
                ]

                value_format = {
                    col: lambda x: format_number(x)
                    for col in finance_table.columns
                    if col not in base_columns
                }

                st.dataframe(
                    finance_table
                    .style
                    .apply(style_finance_table, axis=1)
                    .format(value_format),
                    width="stretch",
                    height=600,
                )

                excel_bytes = dataframe_to_excel_bytes(finance_table)

                st.download_button(
                    label="📥 Скачать таблицу в Excel",
                    data=excel_bytes,
                    file_name=f"finance_arrivals_plan_{current_year}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

        # with st.expander("📦 Таблица по SKU и контейнерам", expanded=True):
        #     table = (
        #         filtered_df
        #         .groupby(
        #             [
        #                 "Тип данных",
        #                 "Источник",
        #                 "Год",
        #                 "Номер недели",
        #                 "Дата начала недели",
        #                 "Категория",
        #                 "SKU",
        #                 "Формула",
        #                 "Контейнер",
        #             ],
        #             as_index=False,
        #             dropna=False,
        #         )
        #         .agg({
        #             "Количество, шт": "sum",
        #             "Количество, кг": "sum",
        #             "Количество, упак": "sum",
        #         })
        #         .sort_values(
        #             [
        #                 "Дата начала недели",
        #                 "Тип данных",
        #                 "Контейнер",
        #                 "SKU",
        #             ]
        #         )
        #     )
        #
        #     table["Дата начала недели"] = (
        #         table["Дата начала недели"]
        #         .dt.strftime("%d.%m.%Y")
        #     )
        #
        #     numeric_columns = [
        #         "Количество, шт",
        #         "Количество, кг",
        #         "Количество, упак",
        #     ]
        #
        #     for column in numeric_columns:
        #         table[column] = table[column].round(0)
        #
        #     st.dataframe(
        #         table.style.format({
        #             "Количество, шт": lambda x: format_number(x),
        #             "Количество, кг": lambda x: format_number(x),
        #             "Количество, упак": lambda x: format_number(x),
        #         }),
        #         width="stretch",
        #         height=600,
        #     )

        # with st.expander("📊 Сводка по группировке", expanded=False):
        #     summary_chart = (
        #         filtered_df
        #         .groupby(
        #             [group_by, "Тип данных"],
        #             as_index=False,
        #             dropna=False,
        #         )[value_column]
        #         .sum()
        #     )
        #
        #     if group_by == "Категория":
        #         order = get_ordered_values(summary_chart[group_by].unique(), CATEGORY_ORDER)
        #         summary_chart[group_by] = pd.Categorical(
        #             summary_chart[group_by],
        #             categories=order,
        #             ordered=True,
        #         )
        #         summary_chart = summary_chart.sort_values(group_by)
        #
        #     elif group_by == "Формула":
        #         order = get_ordered_values(summary_chart[group_by].unique(), FORMULA_ORDER)
        #         summary_chart[group_by] = pd.Categorical(
        #             summary_chart[group_by],
        #             categories=order,
        #             ordered=True,
        #         )
        #         summary_chart = summary_chart.sort_values(group_by)
        #
        #     else:
        #         summary_chart = summary_chart.sort_values(group_by)
        #
        #     fig_summary = px.bar(
        #         summary_chart,
        #         x=group_by,
        #         y=value_column,
        #         color="Тип данных",
        #         title=f"Сводка | {group_by}",
        #     )
        #
        #     fig_summary.update_layout(
        #         barmode="stack",
        #         yaxis_title=unit,
        #         height=520,
        #     )
        #
        #     st.plotly_chart(fig_summary, width="stretch")
