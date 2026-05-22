import pandas as pd

CATEGORY_ORDER = [
    "АМАЛТЕЯ",
    "КАШИ",
    "НЭННИ 400",
    "НЭННИ 800",
    "НЭННИ + каша",
    "НЭННИ + пюре",
]

FORMULA_ORDER = [
    "АМАЛТЕЯ",
    "КАША гречневая",
    "КАША овсяная",
    "КАША рисовая",
    "КАША-кукурузная",
    "НЭННИ Классика",
    "НЭННИ 1",
    "НЭННИ 2",
    "НЭННИ 3",
    "НЭННИ 4",
]

FORMULA_DANIEL_ORDER = [
    "A",
    "Buck",
    "Oats",
    "Rice",
    "Corn",
    "NC",
    "N1",
    "N2",
    "N3",
    "N4",
]

SKU_DANIEL_ORDER = [
    "A",
    "Buck",
    "Oats",
    "Rice",
    "Corn",
    "NC4",
    "NC8",
    "N14",
    "N18",
    "N24",
    "N28",
    "N34",
    "N38",
    "N44",
    "N48",
]

CHANNEL_ORDER = [
    "Покупатели",
    "Изготовители",
    "Даром",
]

MONTH_ORDER = {
    "Январь": 1,
    "Февраль": 2,
    "Март": 3,
    "Апрель": 4,
    "Май": 5,
    "Июнь": 6,
    "Июль": 7,
    "Август": 8,
    "Сентябрь": 9,
    "Октябрь": 10,
    "Ноябрь": 11,
    "Декабрь": 12,
}


def get_value_column(unit: str) -> str:
    """
    Возвращает колонку количества по выбранной единице измерения.

    :param unit: шт / кг / упак
    :return: название колонки
    """
    if unit == "кг":
        return "Количество, кг"

    if unit == "упак":
        return "Количество, упак"

    return "Количество, шт"


def get_share_value_column(unit: str) -> str:
    """
    Возвращает колонку для расчета долей.

    Важно:
    доли 400/800 нельзя считать в штуках,
    потому что 400 г и 800 г в штуках сравнивать некорректно.

    Если пользователь выбрал 'шт', для долей автоматически берем кг.
    """
    if unit == "упак":
        return "Количество, упак"

    return "Количество, кг"


def format_number(value: float) -> str:
    """
    Форматирует число с пробелами в тысячах.

    1234567 -> 1 234 567
    """
    if pd.isna(value):
        return "0"

    return f"{value:,.0f}".replace(",", " ")


def format_percent(value: float) -> str:
    """
    Форматирует процент.

    0.2845 -> 28,45%
    """
    if pd.isna(value):
        return ""

    return f"{value:.2%}".replace(".", ",")


def get_ordered_values(values, order_list: list[str]) -> list[str]:
    """
    Возвращает значения в бизнес-порядке.

    Значения из order_list идут первыми,
    остальные добавляются в конец по алфавиту.
    """
    values = [value for value in values if not pd.isna(value)]
    values = list(dict.fromkeys(values))

    ordered = [item for item in order_list if item in values]
    other = sorted([item for item in values if item not in ordered])

    return ordered + other


def add_period_column(
        df: pd.DataFrame,
        period_type: str,
) -> tuple[pd.DataFrame, str]:
    """
    Добавляет колонку 'Период' для графиков и таблиц.

    :param df: таблица продаж
    :param period_type: По годам / По кварталам / По месяцам
    :return: df с колонкой Период и название колонки сортировки
    """
    df = df.copy()

    if df.empty:
        df["Период"] = ""
        return df, "Период"

    if period_type == "По кварталам":
        df["Период"] = (
                df["Год"].astype("Int64").astype(str)
                + " Q"
                + df["Квартал"].astype("Int64").astype(str)
        )
        sort_column = "Дата начала недели"

    elif period_type == "По месяцам":
        df["Период"] = (
                df["Год"].astype("Int64").astype(str)
                + "-"
                + df["Месяц номер"].astype("Int64").astype(str).str.zfill(2)
        )
        sort_column = "Дата начала недели"

    else:
        df["Период"] = df["Год"].astype("Int64").astype(str)
        sort_column = "Год"

    return df, sort_column


def make_sales_dynamic_chart_data(
        df: pd.DataFrame,
        period_type: str,
        group_by: str,
        value_column: str,
) -> pd.DataFrame:
    """
    Готовит данные для графика динамики продаж.

    :param df: отфильтрованная таблица продаж
    :param period_type: По годам / По кварталам / По месяцам
    :param group_by: колонка группировки графика
    :param value_column: колонка значения
    :return: таблица для графика
    """
    if df.empty:
        return pd.DataFrame()

    df, sort_column = add_period_column(df, period_type)

    chart_df = (
        df
        .groupby(
            ["Период", sort_column, group_by],
            as_index=False,
            observed=True,
            dropna=False,
        )[value_column]
        .sum()
        .sort_values(sort_column)
    )

    return chart_df


def make_sku_table(
        df: pd.DataFrame,
        period_type: str,
        value_column: str,
) -> pd.DataFrame:
    """
    Делает сводную таблицу продаж по SKU.

    Строки:
    - Категория
    - Формула
    - SKU

    Колонки:
    - период: год / квартал / месяц
    """
    if df.empty:
        return pd.DataFrame()

    df, _ = add_period_column(df, period_type)

    table = (
        df
        .pivot_table(
            index=[
                "Категория",
                "Формула",
                "SKU",
            ],
            columns="Период",
            values=value_column,
            aggfunc="sum",
            fill_value=0,
            observed=True,
        )
        .reset_index()
    )

    table.columns.name = None

    period_columns = [
        column for column in table.columns
        if column not in ["Категория", "Формула", "SKU"]
    ]

    table["ИТОГО"] = table[period_columns].sum(axis=1)

    table = table.sort_values(
        [
            "Категория",
            "Формула",
            "SKU",
        ],
        kind="stable",
    )

    total_row = {
        "Категория": "ИТОГО",
        "Формула": "",
        "SKU": "",
    }

    for column in period_columns + ["ИТОГО"]:
        total_row[column] = table[column].sum()

    table = pd.concat(
        [table, pd.DataFrame([total_row])],
        ignore_index=True,
    )

    return table


def make_formula_table(
        df: pd.DataFrame,
        period_type: str,
        value_column: str,
) -> pd.DataFrame:
    """
    Делает сводную таблицу продаж по формулам.

    Строки:
    - Категория
    - Формула

    Колонки:
    - период: год / квартал / месяц
    """
    if df.empty:
        return pd.DataFrame()

    df, _ = add_period_column(df, period_type)

    table = (
        df
        .pivot_table(
            index=[
                "Категория",
                "Формула",
            ],
            columns="Период",
            values=value_column,
            aggfunc="sum",
            fill_value=0,
            observed=True,
        )
        .reset_index()
    )

    table.columns.name = None

    period_columns = [
        column for column in table.columns
        if column not in ["Категория", "Формула"]
    ]

    table["ИТОГО"] = table[period_columns].sum(axis=1)

    table = table.sort_values(
        [
            "Категория",
            "Формула",
        ],
        kind="stable",
    )

    total_row = {
        "Категория": "ИТОГО",
        "Формула": "",
    }

    for column in period_columns + ["ИТОГО"]:
        total_row[column] = table[column].sum()

    table = pd.concat(
        [table, pd.DataFrame([total_row])],
        ignore_index=True,
    )

    return table


def make_nenni_weight_share_table(
        df: pd.DataFrame,
        period_type: str,
        unit: str,
) -> pd.DataFrame:
    """
    Делает таблицу долей НЭННИ 400 / 800 по формулам.

    Доли считаются только в кг или упаковках.
    Если пользователь выбрал штуки, автоматически считаем в кг.

    Пример результата:
    Формула | Вес | 2022 | 2023 | 2024 | 2025 | 2026
    NC     | 400 | 19%  | ...
    NC     | 800 | 81%  | ...
    """
    if df.empty:
        return pd.DataFrame()

    value_column = get_share_value_column(unit)

    nenni_df = df[
        df["Категория"].astype(str).str.contains("НЭННИ", na=False)
    ].copy()

    if nenni_df.empty:
        return pd.DataFrame()

    nenni_df, _ = add_period_column(nenni_df, period_type)

    grouped = (
        nenni_df
        .groupby(
            [
                "Период",
                "formula Daniel",
                "Вес",
            ],
            as_index=False,
            observed=True,
        )[value_column]
        .sum()
    )

    total_by_formula = (
        grouped
        .groupby(
            [
                "Период",
                "formula Daniel",
            ],
            as_index=False,
            observed=True,
        )[value_column]
        .sum()
        .rename(columns={value_column: "Итого формула"})
    )

    grouped = grouped.merge(
        total_by_formula,
        how="left",
        on=[
            "Период",
            "formula Daniel",
        ],
    )

    grouped["Доля"] = grouped[value_column] / grouped["Итого формула"]

    table = (
        grouped
        .pivot_table(
            index=[
                "formula Daniel",
                "Вес",
            ],
            columns="Период",
            values="Доля",
            aggfunc="sum",
            fill_value=0,
            observed=True,
        )
        .reset_index()
    )

    table.columns.name = None

    table = table.rename(columns={
        "formula Daniel": "Формула",
    })

    table = table.sort_values(
        by=[
            "Формула",
            "Вес",
        ],
        key=lambda col: col.map(
            {value: index for index, value in enumerate(FORMULA_DANIEL_ORDER)}
        ).fillna(999)
        if col.name == "Формула"
        else col,
        kind="stable",
    )

    return table


def make_nenni_800_share_table(
        df: pd.DataFrame,
        period_type: str,
        unit: str,
) -> pd.DataFrame:
    """
    Делает таблицу доли 800 г внутри каждой формулы НЭННИ.

    Пример:
    Формула | 2022 | 2023 | 2024 | 2025 | 2026
    NC8     | 89%  | ...
    N18     | 86%  | ...

    В строках показываем SKU Daniel 800 г:
    NC8, N18, N28, N38, N48.
    """
    if df.empty:
        return pd.DataFrame()

    value_column = get_share_value_column(unit)

    nenni_df = df[
        df["Категория"].astype(str).str.contains("НЭННИ", na=False)
    ].copy()

    if nenni_df.empty:
        return pd.DataFrame()

    nenni_df, _ = add_period_column(nenni_df, period_type)

    grouped = (
        nenni_df
        .groupby(
            [
                "Период",
                "formula Daniel",
                "SKU Daniel",
                "Вес",
            ],
            as_index=False,
            observed=True,
        )[value_column]
        .sum()
    )

    total_by_formula = (
        grouped
        .groupby(
            [
                "Период",
                "formula Daniel",
            ],
            as_index=False,
            observed=True,
        )[value_column]
        .sum()
        .rename(columns={value_column: "Итого формула"})
    )

    grouped = grouped.merge(
        total_by_formula,
        how="left",
        on=[
            "Период",
            "formula Daniel",
        ],
    )

    grouped = grouped[
        pd.to_numeric(grouped["Вес"], errors="coerce") == 800
        ].copy()

    grouped["Доля 800"] = grouped[value_column] / grouped["Итого формула"]

    table = (
        grouped
        .pivot_table(
            index=[
                "SKU Daniel",
            ],
            columns="Период",
            values="Доля 800",
            aggfunc="sum",
            fill_value=0,
            observed=True,
        )
        .reset_index()
    )

    table.columns.name = None

    table = table.rename(columns={
        "SKU Daniel": "Формула",
    })

    table["Порядок"] = table["Формула"].map(
        {value: index for index, value in enumerate(SKU_DANIEL_ORDER)}
    ).fillna(999)

    table = (
        table
        .sort_values("Порядок", kind="stable")
        .drop(columns=["Порядок"])
    )

    return table


def make_nenni_400_800_summary(
        df: pd.DataFrame,
        unit: str,
        years: list[int] | None = None,
) -> pd.DataFrame:
    """
    Делает компактную таблицу долей 400 и 800 по формуле.

    Пример:
        400      800
    NC  19,83%   80,17%
    N1  13,90%   86,10%

    Если years переданы — считаем только по выбранным годам.
    """
    if df.empty:
        return pd.DataFrame()

    value_column = get_share_value_column(unit)

    nenni_df = df[
        df["Категория"].astype(str).str.contains("НЭННИ", na=False)
    ].copy()

    if years:
        nenni_df = nenni_df[
            nenni_df["Год"].astype("Int64").isin(years)
        ].copy()

    if nenni_df.empty:
        return pd.DataFrame()

    grouped = (
        nenni_df
        .groupby(
            [
                "formula Daniel",
                "Вес",
            ],
            as_index=False,
            observed=True,
        )[value_column]
        .sum()
    )

    total_by_formula = (
        grouped
        .groupby(
            "formula Daniel",
            as_index=False,
            observed=True,
        )[value_column]
        .sum()
        .rename(columns={value_column: "Итого формула"})
    )

    grouped = grouped.merge(
        total_by_formula,
        how="left",
        on="formula Daniel",
    )

    grouped["Доля"] = grouped[value_column] / grouped["Итого формула"]

    table = (
        grouped
        .pivot_table(
            index="formula Daniel",
            columns="Вес",
            values="Доля",
            aggfunc="sum",
            fill_value=0,
            observed=True,
        )
        .reset_index()
    )

    table.columns.name = None

    table = table.rename(columns={
        "formula Daniel": "Формула",
        400: "400",
        800: "800",
        400.0: "400",
        800.0: "800",
    })

    for column in ["400", "800"]:
        if column not in table.columns:
            table[column] = 0

    table = table[
        [
            "Формула",
            "400",
            "800",
        ]
    ]

    table["Порядок"] = table["Формула"].map(
        {value: index for index, value in enumerate(FORMULA_DANIEL_ORDER)}
    ).fillna(999)

    table = (
        table
        .sort_values("Порядок", kind="stable")
        .drop(columns=["Порядок"])
    )

    return table


def make_cereal_share_table(
        df: pd.DataFrame,
        period_type: str,
        unit: str,
) -> pd.DataFrame:
    """
    Делает таблицу долей каш внутри категории КАШИ.

    Пример:
    Формула | 2023 | 2024 | 2025 | 2026
    Buck    | 27%  | ...
    Oats    | 30%  | ...
    Rice    | 21%  | ...
    Corn    | 20%  | ...

    Доли считаем в кг или упаковках.
    Если пользователь выбрал штуки, автоматически считаем в кг.
    """
    if df.empty:
        return pd.DataFrame()

    value_column = get_share_value_column(unit)

    cereal_df = df[
        df["Категория"].astype(str).str.contains("КАШ", na=False)
    ].copy()

    if cereal_df.empty:
        return pd.DataFrame()

    cereal_df, _ = add_period_column(cereal_df, period_type)

    formula_column = (
        "formula Daniel"
        if "formula Daniel" in cereal_df.columns
        else "Формула"
    )

    grouped = (
        cereal_df
        .groupby(
            [
                "Период",
                formula_column,
            ],
            as_index=False,
            observed=True,
        )[value_column]
        .sum()
    )

    total_by_period = (
        grouped
        .groupby(
            "Период",
            as_index=False,
            observed=True,
        )[value_column]
        .sum()
        .rename(columns={value_column: "Итого каши"})
    )

    grouped = grouped.merge(
        total_by_period,
        how="left",
        on="Период",
    )

    grouped["Доля"] = grouped[value_column] / grouped["Итого каши"]

    table = (
        grouped
        .pivot_table(
            index=formula_column,
            columns="Период",
            values="Доля",
            aggfunc="sum",
            fill_value=0,
            observed=True,
        )
        .reset_index()
    )

    table.columns.name = None

    table = table.rename(columns={
        formula_column: "Формула",
    })

    table["Порядок"] = table["Формула"].map(
        {value: index for index, value in enumerate(FORMULA_DANIEL_ORDER)}
    ).fillna(999)

    table = (
        table
        .sort_values("Порядок", kind="stable")
        .drop(columns=["Порядок"])
    )

    return table


def make_kpi_values(
        df: pd.DataFrame,
        value_column: str,
        current_year: int,
) -> dict:
    """
    Считает KPI для страницы продаж.

    :param df: отфильтрованная таблица продаж
    :param value_column: колонка количества
    :param current_year: текущий год
    :return: словарь KPI
    """
    if df.empty:
        return {
            "total": 0,
            "current_year": 0,
            "history": 0,
            "forecast": 0,
        }

    current_year_df = df[
        df["Год"].astype("Int64") == current_year
        ].copy()

    history_df = df[
        df["Год"].astype("Int64") < current_year
        ].copy()

    forecast_df = df[
        df["Тип данных"].astype(str).str.contains("прогноз", case=False, na=False)
    ].copy()

    return {
        "total": df[value_column].sum(),
        "current_year": current_year_df[value_column].sum(),
        "history": history_df[value_column].sum(),
        "forecast": forecast_df[value_column].sum(),
    }


def add_total_row(
        table: pd.DataFrame,
        text_columns: list[str],
        total_label: str = "ИТОГО",
) -> pd.DataFrame:
    """
    Добавляет итоговую строку в любую числовую таблицу.

    :param table: таблица
    :param text_columns: текстовые колонки, которые не суммируем
    :param total_label: подпись итоговой строки
    :return: таблица с итогом
    """
    if table.empty:
        return table

    numeric_columns = [
        column for column in table.columns
        if column not in text_columns
    ]

    total_row = {
        column: ""
        for column in text_columns
    }

    if text_columns:
        total_row[text_columns[0]] = total_label

    for column in numeric_columns:
        total_row[column] = pd.to_numeric(
            table[column],
            errors="coerce",
        ).sum()

    return pd.concat(
        [table, pd.DataFrame([total_row])],
        ignore_index=True,
    )
