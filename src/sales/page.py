import pandas as pd
import plotly.express as px
import streamlit as st

from src.config import (
    CUSTOMER_MAPPING_FILE,
    PRODUCT_MAPPING_FILE,
    SALES_ACTUAL_DIR,
    SALES_HISTORY_DIR,
    SALES_MANUAL_FORECAST_DIR,
    SALES_PROCESSED_FILE,
)

from src.sales.calculator import (
    CHANNEL_ORDER,
    CATEGORY_ORDER,
    FORMULA_DANIEL_ORDER,
    FORMULA_ORDER,
    format_number,
    format_percent,
    get_ordered_values,
    get_value_column,
    make_cereal_share_table,
    make_formula_table,
    make_kpi_values,
    make_nenni_400_800_summary,
    make_nenni_800_share_table,
    make_nenni_weight_share_table,
    make_sales_dynamic_chart_data,
    make_sku_table,
)

from src.sales.loader import (
    load_customer_mapping,
    load_product_mapping,
    load_processed_sales,
    load_sales_actual,
    load_sales_history,
    load_set_mapping,
    save_processed_sales,
)

from src.sales.transformer import (
    combine_sales_data,
    transform_manual_forecast,
    transform_sales_actual,
    transform_sales_history,
)

from src.sales.validator import (
    split_errors_and_warnings,
    validate_sales_data,
)


def format_table_numbers(table: pd.DataFrame) -> dict:
    """
    Возвращает словарь форматирования для числовых колонок таблицы.

    :param table: таблица для отображения
    :return: словарь форматирования
    """
    formatters = {}

    for column in table.columns:
        if pd.api.types.is_numeric_dtype(table[column]):
            formatters[column] = lambda value: format_number(value)

    return formatters


def format_share_table(table: pd.DataFrame) -> dict:
    """
    Возвращает форматирование для таблиц долей.

    :param table: таблица долей
    :return: словарь форматирования
    """
    formatters = {}

    text_columns = [
        "Формула",
        "Вес",
    ]

    for column in table.columns:
        if column not in text_columns:
            formatters[column] = lambda value: format_percent(value)

    return formatters


def highlight_total_row(row):
    """
    Подсвечивает итоговую строку в таблицах.
    """
    first_value = str(row.iloc[0])

    if first_value.startswith("ИТОГО"):
        return [
            "background-color: #b71c1c; color: white; font-weight: bold"
        ] * len(row)

    return [""] * len(row)


def clear_sales_processed_file() -> None:
    """
    Удаляет обработанный parquet-файл продаж.

    Нужно, когда изменились:
    - исходные Excel-файлы;
    - product_mapping.xlsx;
    - customer_mapping.xlsx;
    - логика обработки в коде.
    """
    if SALES_PROCESSED_FILE.exists():
        SALES_PROCESSED_FILE.unlink()


@st.cache_data(show_spinner="Загружаем и обрабатываем продажи...")
def prepare_sales_data(force_reload: bool = False) -> pd.DataFrame:
    """
    Загружает и обрабатывает данные продаж.

    Логика:
    - если есть sales_processed.parquet и не нажата принудительная перезагрузка,
      читаем быстрый parquet;
    - если parquet нет или нужна перезагрузка,
      читаем Excel-файлы, обрабатываем и сохраняем parquet.

    :param force_reload: принудительно перечитать Excel-файлы
    :return: итоговая таблица продаж
    """
    if not force_reload:
        processed_df = load_processed_sales(SALES_PROCESSED_FILE)

        if not processed_df.empty:
            return processed_df

    product_mapping_df = load_product_mapping(PRODUCT_MAPPING_FILE)
    set_mapping_df = load_set_mapping(PRODUCT_MAPPING_FILE)
    customer_mapping_df = load_customer_mapping(CUSTOMER_MAPPING_FILE)

    history_raw = load_sales_history(SALES_HISTORY_DIR)
    actual_raw = load_sales_actual(SALES_ACTUAL_DIR)

    # Ручной прогноз пока может быть пустым.
    # Используем общий загрузчик факта, потому что будущий шаблон пока не утверждён.
    manual_forecast_raw = load_sales_history(SALES_MANUAL_FORECAST_DIR)

    history_df = transform_sales_history(
        df=history_raw,
        product_mapping_df=product_mapping_df,
        customer_mapping_df=customer_mapping_df,
    )

    actual_df = transform_sales_actual(
        df=actual_raw,
        product_mapping_df=product_mapping_df,
        set_mapping_df=set_mapping_df,
        customer_mapping_df=customer_mapping_df,
    )

    manual_forecast_df = transform_manual_forecast(
        df=manual_forecast_raw,
        product_mapping_df=product_mapping_df,
        customer_mapping_df=customer_mapping_df,
    )

    df = combine_sales_data(
        history_df=history_df,
        actual_df=actual_df,
        manual_forecast_df=manual_forecast_df,
    )

    if not df.empty:
        save_processed_sales(df, SALES_PROCESSED_FILE)

    return df


def get_filter_options(df: pd.DataFrame, column: str, order: list[str] | None = None):
    """
    Возвращает значения для фильтра.

    :param df: таблица продаж
    :param column: название колонки
    :param order: бизнес-порядок значений
    :return: список значений
    """
    if column not in df.columns:
        return []

    values = df[column].dropna().astype(str).unique()

    if order:
        return get_ordered_values(values, order)

    return sorted(values)


def apply_filters(
        df: pd.DataFrame,
        selected_channels: list[str],
        selected_years: list[int],
        selected_categories: list[str],
        selected_formulas: list[str],
        selected_countries: list[str],
        selected_customers: list[str],
        selected_data_types: list[str],
) -> pd.DataFrame:
    """
    Применяет выбранные фильтры к таблице продаж.
    """
    filtered_df = df.copy()

    if selected_channels:
        filtered_df = filtered_df[
            filtered_df["Канал название"].astype(str).isin(selected_channels)
        ]

    if selected_years:
        filtered_df = filtered_df[
            filtered_df["Год"].astype("Int64").isin(selected_years)
        ]

    if selected_categories:
        filtered_df = filtered_df[
            filtered_df["Категория"].astype(str).isin(selected_categories)
        ]

    if selected_formulas:
        filtered_df = filtered_df[
            filtered_df["Формула"].astype(str).isin(selected_formulas)
        ]

    if selected_countries:
        filtered_df = filtered_df[
            filtered_df["Страна"].astype(str).isin(selected_countries)
        ]

    if selected_customers:
        filtered_df = filtered_df[
            filtered_df["Контрагент"].astype(str).isin(selected_customers)
        ]

    if selected_data_types:
        filtered_df = filtered_df[
            filtered_df["Тип данных"].astype(str).isin(selected_data_types)
        ]

    return filtered_df


def show_validation_messages(df: pd.DataFrame) -> None:
    """
    Показывает ошибки и предупреждения по данным.
    """
    messages = validate_sales_data(df)
    errors, warnings = split_errors_and_warnings(messages)

    if errors:
        st.error("Есть ошибки в данных продаж")
        with st.expander("Показать ошибки", expanded=True):
            for error in errors:
                st.markdown(error)

    else:
        st.success("Проверка продаж пройдена: критичных ошибок нет")

    if warnings:
        st.warning("Есть предупреждения по данным продаж")
        with st.expander("Показать предупреждения", expanded=False):
            for warning in warnings:
                st.markdown(warning)


def show_kpi(df: pd.DataFrame, value_column: str, unit: str) -> None:
    """
    Показывает KPI-блоки.
    """
    current_year = pd.Timestamp.today().year

    kpi = make_kpi_values(
        df=df,
        value_column=value_column,
        current_year=current_year,
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        label=f"Всего, {unit}",
        value=format_number(kpi["total"]),
    )

    col2.metric(
        label=f"{current_year}, {unit}",
        value=format_number(kpi["current_year"]),
    )

    col3.metric(
        label=f"История до {current_year}, {unit}",
        value=format_number(kpi["history"]),
    )

    col4.metric(
        label=f"Прогноз, {unit}",
        value=format_number(kpi["forecast"]),
    )


MONTH_SHORT_NAMES = {
    1: "янв",
    2: "фев",
    3: "мар",
    4: "апр",
    5: "май",
    6: "июн",
    7: "июл",
    8: "авг",
    9: "сен",
    10: "окт",
    11: "ноя",
    12: "дек",
}


def configure_period_axis(
        fig,
        chart_df: pd.DataFrame,
        period_type: str,
        sort_column: str,
):
    """
    Делает ось X читабельной:
    - по годам: 2022, 2023, 2024;
    - по кварталам: К1, К2, К3, К4 + год снизу;
    - по месяцам: янв, фев, мар + год снизу.
    """
    period_order = (
        chart_df[["Период", sort_column]]
        .drop_duplicates()
        .sort_values(sort_column)["Период"]
        .tolist()
    )

    if period_type == "По кварталам":
        tick_text = [
            "К" + period.split("-К")[-1]
            for period in period_order
        ]

        year_map = {
            period: period.split("-К")[0]
            for period in period_order
        }

    elif period_type == "По месяцам":
        tick_text = []

        for period in period_order:
            month_number = int(period.split("-")[-1])
            tick_text.append(MONTH_SHORT_NAMES.get(month_number, str(month_number)))

        year_map = {
            period: period.split("-")[0]
            for period in period_order
        }

    else:
        tick_text = period_order
        year_map = {}

    fig.update_xaxes(
        type="category",
        tickmode="array",
        tickvals=period_order,
        ticktext=tick_text,
        tickangle=0,
        categoryorder="array",
        categoryarray=period_order,
    )

    if period_type in ["По кварталам", "По месяцам"]:
        year_positions = {}

        for period in period_order:
            year = year_map[period]
            year_positions.setdefault(year, []).append(period)

        for year, periods in year_positions.items():
            middle_period = periods[len(periods) // 2]

            fig.add_annotation(
                x=middle_period,
                y=-0.22,
                text=year,
                showarrow=False,
                xref="x",
                yref="paper",
                font=dict(size=12),
            )

        fig.update_layout(
            xaxis_title="",
            margin=dict(b=130),
        )

    else:
        fig.update_layout(
            xaxis_title="Год",
            margin=dict(b=80),
        )

    return fig


@st.cache_data(show_spinner=False)
def make_cached_chart_data(
        df: pd.DataFrame,
        period_type: str,
        group_by: str,
        value_column: str,
) -> pd.DataFrame:
    """
    Кэширует уже агрегированные данные для графика.

    Это быстрее, чем каждый раз группировать большую таблицу при переключении.
    """
    chart_df = make_sales_dynamic_chart_data(
        df=df,
        period_type=period_type,
        group_by=group_by,
        value_column=value_column,
    )

    return chart_df


def show_dynamic_chart(
        df: pd.DataFrame,
        period_type: str,
        group_by: str,
        value_column: str,
        unit: str,
) -> None:
    """
    Показывает график динамики продаж.
    """
    chart_df = make_cached_chart_data(
        df=df,
        period_type=period_type,
        group_by=group_by,
        value_column=value_column,
    )

    if chart_df.empty:
        st.info("Нет данных для графика по выбранным фильтрам.")
        return

    sort_column = "Период_сортировка"

    fig = px.bar(
        chart_df,
        x="Период",
        y=value_column,
        color=group_by,
        title=f"Динамика продаж: {period_type.lower()} | группировка: {group_by}",
    )

    fig.update_layout(
        barmode="stack",
        yaxis_title=unit,
        height=560 if period_type != "По годам" else 520,
    )

    fig.update_traces(
        hovertemplate="%{x}<br>%{y:,.0f}<extra></extra>",
    )

    fig = configure_period_axis(
        fig=fig,
        chart_df=chart_df,
        period_type=period_type,
        sort_column=sort_column,
    )

    st.plotly_chart(
        fig,
        width="stretch",
    )


def get_number_column_config(table: pd.DataFrame) -> dict:
    """
    Готовит быстрое форматирование числовых колонок для st.dataframe.

    Это быстрее, чем pandas Styler.
    """
    config = {}

    text_columns = [
        "Категория",
        "Формула",
        "SKU",
    ]

    for column in table.columns:
        if column not in text_columns and pd.api.types.is_numeric_dtype(table[column]):
            config[column] = st.column_config.NumberColumn(
                column,
                format="%d",
            )

    return config


def show_sku_table(
        df: pd.DataFrame,
        period_type: str,
        value_column: str,
) -> None:
    """
    Показывает таблицу продаж по SKU.
    """
    table = make_sku_table(
        df=df,
        period_type=period_type,
        value_column=value_column,
    )

    if table.empty:
        st.info("Нет данных для таблицы по SKU.")
        return

    st.caption(
        f"Строк в таблице: {len(table):,}".replace(",", " ")
    )

    st.dataframe(
        table,
        width="stretch",
        height=600,
        column_config=get_number_column_config(table),
    )


def show_formula_table(
        df: pd.DataFrame,
        period_type: str,
        value_column: str,
) -> None:
    """
    Показывает таблицу продаж по формулам.
    """
    table = make_formula_table(
        df=df,
        period_type=period_type,
        value_column=value_column,
    )

    if table.empty:
        st.info("Нет данных для таблицы по формулам.")
        return

    st.caption(
        f"Строк в таблице: {len(table):,}".replace(",", " ")
    )

    st.dataframe(
        table,
        width="stretch",
        height=520,
        column_config=get_number_column_config(table),
    )


def show_share_tables(
        df: pd.DataFrame,
        period_type: str,
        unit: str,
        selected_years: list[int],
) -> None:
    """
    Показывает таблицы долей.
    """
    with st.expander("🍼 НЭННИ: доли 400 г / 800 г по формулам", expanded=False):
        table = make_nenni_weight_share_table(
            df=df,
            period_type=period_type,
            unit=unit,
        )

        if table.empty:
            st.info("Нет данных для расчёта долей НЭННИ.")
        else:
            st.caption(
                "Доли считаются в кг или упаковках. "
                "Если выбраны штуки, для долей автоматически используются кг."
            )

            st.dataframe(
                table.style.format(format_share_table(table)),
                width="stretch",
                height=420,
            )

    with st.expander("🍼 НЭННИ: доля 800 г внутри формул", expanded=False):
        table = make_nenni_800_share_table(
            df=df,
            period_type=period_type,
            unit=unit,
        )

        if table.empty:
            st.info("Нет данных для расчёта доли 800 г.")
        else:
            st.caption(
                "Доля 800 г считается от общего объёма формулы: 400 г + 800 г."
            )

            st.dataframe(
                table.style.format(format_share_table(table)),
                width="stretch",
                height=420,
            )

    with st.expander("🍼 НЭННИ: итоговая доля 400 г / 800 г", expanded=False):
        table = make_nenni_400_800_summary(
            df=df,
            unit=unit,
            years=selected_years,
        )

        if table.empty:
            st.info("Нет данных для итоговой доли 400/800.")
        else:
            st.caption(
                "Итоговая доля считается по выбранным годам и фильтрам."
            )

            st.dataframe(
                table.style.format(format_share_table(table)),
                width="stretch",
                height=360,
            )

    with st.expander("🥣 КАШИ: доли внутри категории", expanded=False):
        table = make_cereal_share_table(
            df=df,
            period_type=period_type,
            unit=unit,
        )

        if table.empty:
            st.info("Нет данных для расчёта долей каш.")
        else:
            st.caption(
                "Доли каш считаются внутри категории КАШИ."
            )

            st.dataframe(
                table.style.format(format_share_table(table)),
                width="stretch",
                height=420,
            )


def show_debug_block(df: pd.DataFrame) -> None:
    """
    Показывает служебную информацию для проверки загрузки.
    """
    with st.expander("🔎 Проверка загруженных данных", expanded=False):
        st.write("Строк:", len(df))

        if "Год" in df.columns:
            st.write(
                "Годы:",
                sorted(df["Год"].dropna().astype(int).unique()),
            )

        if "Источник" in df.columns:
            st.write(
                "Источники:",
                sorted(df["Источник"].dropna().astype(str).unique()),
            )

        if "Канал название" in df.columns:
            st.write(
                "Каналы:",
                sorted(df["Канал название"].dropna().astype(str).unique()),
            )

        st.dataframe(df.head(100), width="stretch")


def show():
    """
    Страница Продажи прогноз.
    """
    st.markdown("## 📈 ПРОДАЖИ прогноз")
    st.caption(
        "История продаж, факт текущего года, ручной прогноз и аналитика долей"
    )

    reload_col1, reload_col2, reload_col3 = st.columns([1, 1.8, 3.2])

    with reload_col1:
        force_reload = st.button("🔄 Обновить данные")

    with reload_col2:
        clear_cache = st.button("🧹 Очистить кэш и пересобрать")

    if clear_cache:
        clear_sales_processed_file()
        st.cache_data.clear()
        st.rerun()

    try:
        df = prepare_sales_data(force_reload=force_reload)

    except Exception as error:
        st.error("Ошибка загрузки или обработки продаж")
        with st.expander("Показать ошибку", expanded=True):
            st.exception(error)
        return

    if df.empty:
        st.warning("Нет данных по продажам. Проверь файлы в папках data/sales.")
        return

    show_validation_messages(df)

    st.divider()

    main_col, filter_col = st.columns([5, 1.25])

    with filter_col:
        st.subheader("Фильтры")

        channels = get_filter_options(
            df,
            "Канал название",
            CHANNEL_ORDER,
        )

        selected_channels = st.multiselect(
            "Канал",
            channels,
            default=channels,
        )

        years = sorted(
            df["Год"].dropna().astype(int).unique()
        )

        selected_years = st.multiselect(
            "Года",
            years,
            default=years,
        )

        period_type = st.selectbox(
            "Период графика",
            [
                "По годам",
                "По кварталам",
                "По месяцам",
            ],
            index=0,
        )

        group_by = st.selectbox(
            "Группировка графика",
            [
                "Тип данных",
                "Канал название",
                "Категория",
                "Формула",
            ],
            index=2,
        )

        unit = st.radio(
            "Единица измерения",
            [
                "шт",
                "кг",
                "упак",
            ],
            index=1,
        )

        categories = get_filter_options(
            df,
            "Категория",
            CATEGORY_ORDER,
        )

        selected_categories = st.multiselect(
            "Категория",
            categories,
            default=categories,
        )

        formulas = get_filter_options(
            df,
            "Формула",
            FORMULA_ORDER,
        )

        selected_formulas = st.multiselect(
            "Формула",
            formulas,
            default=formulas,
        )

        countries = get_filter_options(
            df,
            "Страна",
        )

        selected_countries = st.multiselect(
            "Страна",
            countries,
            default=countries,
        )

        customers = get_filter_options(
            df,
            "Контрагент",
        )

        selected_customers = st.multiselect(
            "Контрагент",
            customers,
            default=customers,
        )

        data_types = get_filter_options(
            df,
            "Тип данных",
        )

        selected_data_types = st.multiselect(
            "Тип данных",
            data_types,
            default=data_types,
        )

    filtered_df = apply_filters(
        df=df,
        selected_channels=selected_channels,
        selected_years=selected_years,
        selected_categories=selected_categories,
        selected_formulas=selected_formulas,
        selected_countries=selected_countries,
        selected_customers=selected_customers,
        selected_data_types=selected_data_types,
    )

    value_column = get_value_column(unit)

    with main_col:
        if filtered_df.empty:
            st.warning("По выбранным фильтрам данных нет.")
            return

        show_kpi(
            df=filtered_df,
            value_column=value_column,
            unit=unit,
        )

        st.divider()

        with st.expander("📈 Динамика продаж", expanded=True):
            show_dynamic_chart(
                df=filtered_df,
                period_type=period_type,
                group_by=group_by,
                value_column=value_column,
                unit=unit,
            )

        st.divider()

        st.markdown("### Детализация")

        detail_block = st.radio(
            "Что показать ниже",
            [
                "Не показывать тяжелые таблицы",
                "Продажи по SKU",
                "Продажи по формулам",
                "Доли НЭННИ и каш",
                "Проверка загруженных данных",
            ],
            horizontal=True,
        )

        if detail_block == "Продажи по SKU":
            st.warning(
                "Таблица по SKU может быть тяжелой при выборе периода по месяцам. "
                "Для ускорения лучше сначала сузить фильтры."
            )

            show_sku_table(
                df=filtered_df,
                period_type=period_type,
                value_column=value_column,
            )

        elif detail_block == "Продажи по формулам":
            show_formula_table(
                df=filtered_df,
                period_type=period_type,
                value_column=value_column,
            )

        elif detail_block == "Доли НЭННИ и каш":
            show_share_tables(
                df=filtered_df,
                period_type=period_type,
                unit=unit,
                selected_years=selected_years,
            )

        elif detail_block == "Проверка загруженных данных":
            show_debug_block(filtered_df)
