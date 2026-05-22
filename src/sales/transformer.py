import re

import pandas as pd

MONTHS_RU = {
    "ЯНВАРЬ": 1,
    "ФЕВРАЛЬ": 2,
    "МАРТ": 3,
    "АПРЕЛЬ": 4,
    "МАЙ": 5,
    "ИЮНЬ": 6,
    "ИЮЛЬ": 7,
    "АВГУСТ": 8,
    "СЕНТЯБРЬ": 9,
    "ОКТЯБРЬ": 10,
    "НОЯБРЬ": 11,
    "ДЕКАБРЬ": 12,
}

MONTHS_RU_SHORT = {
    "ЯНВ": 1,
    "ФЕВ": 2,
    "МАР": 3,
    "АПР": 4,
    "МАЙ": 5,
    "ИЮН": 6,
    "ИЮЛ": 7,
    "АВГ": 8,
    "СЕН": 9,
    "ОКТ": 10,
    "НОЯ": 11,
    "ДЕК": 12,
}

CHANNEL_NAMES = {
    "sales": "Покупатели",
    "manufacturer": "Изготовители",
    "free": "Даром",
}


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Очищает названия колонок:
    - убирает лишние пробелы;
    - удаляет полностью пустые колонки;
    - удаляет служебные Unnamed-колонки.
    """
    df = df.copy()

    df.columns = df.columns.astype(str).str.strip()

    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]
    df = df.dropna(axis=1, how="all")
    df = df.dropna(how="all")

    return df


def collapse_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Объединяет колонки с одинаковыми названиями.

    Такое бывает после переименования:
    например, если в файле уже была колонка 'Контрагент',
    а колонка 'Комиссионер' тоже переименовалась в 'Контрагент'.

    Логика:
    - если колонка одна — оставляем как есть;
    - если колонок с одним названием несколько —
      берём первое непустое значение по строке.
    """
    df = df.copy()

    if not df.columns.duplicated().any():
        return df

    result_columns = []

    for column in dict.fromkeys(df.columns):
        same_columns = df.loc[:, df.columns == column]

        if same_columns.shape[1] == 1:
            result_columns.append(same_columns.iloc[:, 0].rename(column))
        else:
            combined_column = same_columns.bfill(axis=1).iloc[:, 0]
            combined_column.name = column
            result_columns.append(combined_column)

    return pd.concat(result_columns, axis=1)


def normalize_text(value) -> str:
    """
    Нормализует текст для надежного сопоставления.

    Убирает различия между:
    - НЭННИ 4 400 гр.
    - * НЭННИ 4 400 гр.
    - НЭННИ 4 400 г.
    """
    if pd.isna(value):
        return ""

    text = str(value).upper()
    text = text.replace("Ё", "Е")
    text = text.replace("\xa0", " ")

    # Убираем служебные символы из названий 1С.
    text = text.replace("*", "")
    text = text.replace('"', "")
    text = text.replace("«", "")
    text = text.replace("»", "")

    # Приводим граммы к единому виду и потом убираем обозначение веса.
    text = re.sub(r"\bГР\.", "Г", text)
    text = re.sub(r"\bГР\b", "Г", text)
    text = re.sub(r"\bГ\.", "Г", text)

    # В названиях для сопоставления вес в граммах нам не нужен как текстовая единица,
    # число веса остается: 400, 800, 200.
    text = re.sub(r"\s+Г\b", "", text)

    # Убираем лишние точки и повторные пробелы.
    text = text.replace(".", "")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def parse_year(value) -> pd.Int64Dtype:
    """
    Преобразует год к числу.

    Поддерживает:
    - 2026
    - 2026 г.
    - 2026 г
    """
    if pd.isna(value):
        return pd.NA

    match = re.search(r"\d{4}", str(value))

    if not match:
        return pd.NA

    return int(match.group(0))


def parse_month_name(value) -> str:
    """
    Очищает месяц.

    Пример:
    - Январь 2026 г. -> Январь
    - Декабрь -> Декабрь
    """
    if pd.isna(value):
        return ""

    text = str(value).strip()
    text = re.sub(r"\d{4}", "", text)
    text = text.replace("г.", "")
    text = text.replace("г", "")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def get_month_number(value) -> pd.Int64Dtype:
    """
    Возвращает номер месяца по русскому названию.
    """
    month_name = normalize_text(parse_month_name(value))

    if not month_name:
        return pd.NA

    return MONTHS_RU.get(month_name, pd.NA)


def parse_week_start(value, year=None) -> pd.Timestamp:
    """
    Преобразует колонку 'По неделям' в дату начала недели.

    Поддерживает:
    - Неделя с 19.01.2026
    - 19.01.2026
    - 2026-01-19 00:00:00
    - 14.дек
    - 28.сен
    - Excel-даты

    Если в неделе нет года, берем год из колонки 'По годам'.
    """
    if pd.isna(value):
        return pd.NaT

    if isinstance(value, pd.Timestamp):
        return value.normalize()

    text = str(value).strip()
    text = text.replace("Неделя с", "")
    text = text.replace("неделя с", "")
    text = text.strip()

    # Формат ISO: 2026-01-19 или 2026-01-19 00:00:00
    iso_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)

    if iso_match:
        return pd.to_datetime(
            iso_match.group(1),
            format="%Y-%m-%d",
            errors="coerce",
        ).normalize()

    # Формат: 19.01.2026
    full_date_match = re.search(r"(\d{1,2}\.\d{1,2}\.\d{4})", text)

    if full_date_match:
        return pd.to_datetime(
            full_date_match.group(1),
            format="%d.%m.%Y",
            errors="coerce",
        ).normalize()

    # Формат вроде 14.дек или 28.сен
    short_date_match = re.search(r"(\d{1,2})[.\s-]+([А-Яа-я]+)", text)

    if short_date_match and year:
        day = int(short_date_match.group(1))
        month_text = normalize_text(short_date_match.group(2))[:3]
        month = MONTHS_RU_SHORT.get(month_text)

        if month:
            return pd.Timestamp(
                year=int(year),
                month=month,
                day=day,
            )

    # Последняя попытка для Excel/прочих дат.
    parsed = pd.to_datetime(
        text,
        errors="coerce",
        dayfirst=True,
    )

    if not pd.isna(parsed):
        if year and parsed.year == 1900:
            return parsed.replace(year=int(year)).normalize()

        return parsed.normalize()

    return pd.NaT

def normalize_quantity(value) -> float:
    """
    Преобразует количество в число.

    Поддерживает:
    - 120
    - 120,000
    - 1 200
    - -3,000
    """
    if pd.isna(value):
        return 0.0

    text = str(value).strip()
    text = text.replace("\xa0", "")
    text = text.replace(" ", "")
    text = text.replace(",", ".")

    return pd.to_numeric(text, errors="coerce")


def remove_sales_service_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Удаляет служебные строки из файлов продаж:
    - Итог;
    - Итого;
    - Общий итог;
    - Всего;
    - пустые строки;
    - строки без номенклатуры.
    """
    df = df.copy()
    df = df.dropna(how="all")

    service_words = [
        "ИТОГ",
        "ИТОГО",
        "ОБЩИЙ ИТОГ",
        "ВСЕГО",
    ]

    def is_service_row(row) -> bool:
        row_values = row.astype(str).str.upper().str.strip()

        for value in row_values:
            if value in service_words:
                return True

        return False

    df = df[
        ~df.apply(is_service_row, axis=1)
    ].copy()

    if "Номенклатура" in df.columns:
        df = df[df["Номенклатура"].notna()].copy()
        df = df[
            ~df["Номенклатура"]
            .astype(str)
            .str.upper()
            .str.strip()
            .isin(service_words)
        ].copy()

    return df


def prepare_product_mapping(mapping_df: pd.DataFrame) -> pd.DataFrame:
    """
    Готовит основной справочник номенклатуры.

    Ожидаемый лист: product_mapping.xlsx / Лист1.
    """
    mapping_df = clean_columns(mapping_df)

    required_columns = [
        "Номенклатурная группа",
        "Номенклатура",
        "Категория",
        "SKU",
        "Формула",
        "Вес",
        "Квант, шт",
    ]

    missing_columns = [
        column for column in required_columns
        if column not in mapping_df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"В product_mapping.xlsx / Лист1 нет колонок: {missing_columns}"
        )

    mapping_df["Ключ_номенклатура"] = (
        mapping_df["Номенклатура"].apply(normalize_text)
    )

    mapping_df["Ключ_группа"] = (
        mapping_df["Номенклатурная группа"].apply(normalize_text)
    )

    mapping_df["Вес"] = pd.to_numeric(
        mapping_df["Вес"],
        errors="coerce",
    )

    mapping_df["Квант, шт"] = pd.to_numeric(
        mapping_df["Квант, шт"],
        errors="coerce",
    )

    mapping_columns = [
        "Ключ_номенклатура",
        "Ключ_группа",
        "Категория",
        "SKU",
        "Формула",
        "Вес",
        "Квант, шт",
    ]

    optional_columns = [
        "SKU Daniel",
        "formula Daniel",
    ]

    for column in optional_columns:
        if column in mapping_df.columns:
            mapping_columns.append(column)

    mapping_df = mapping_df[mapping_columns].drop_duplicates(
        subset=["Ключ_номенклатура"],
        keep="first",
    )

    return mapping_df


def prepare_set_mapping(set_mapping_df: pd.DataFrame) -> pd.DataFrame:
    """
    Готовит справочник наборов.

    Ожидаемый лист: product_mapping.xlsx / set_mapping.
    """
    set_mapping_df = clean_columns(set_mapping_df)

    required_columns = [
        "Номенклатура набора",
        "SKU внутри набора",
        "SKU",
        "Количество в наборе",
        "Категория",
        "Формула",
        "Вес",
        "Квант, шт",
    ]

    missing_columns = [
        column for column in required_columns
        if column not in set_mapping_df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"В product_mapping.xlsx / set_mapping нет колонок: {missing_columns}"
        )

    set_mapping_df["Ключ_набора"] = (
        set_mapping_df["Номенклатура набора"].apply(normalize_text)
    )

    set_mapping_df["Количество в наборе"] = pd.to_numeric(
        set_mapping_df["Количество в наборе"],
        errors="coerce",
    ).fillna(1)

    set_mapping_df["Вес"] = pd.to_numeric(
        set_mapping_df["Вес"],
        errors="coerce",
    )

    set_mapping_df["Квант, шт"] = pd.to_numeric(
        set_mapping_df["Квант, шт"],
        errors="coerce",
    )

    return set_mapping_df


def prepare_customer_mapping(customer_df: pd.DataFrame) -> pd.DataFrame:
    """
    Готовит справочник контрагентов.

    Ожидаемый файл: data/reference/customer_mapping.xlsx.
    """
    customer_df = clean_columns(customer_df)

    required_columns = [
        "Контрагент из 1С",
        "Зона для прогноза",
        "Страна",
        "Контрагент",
        "Статус",
    ]

    missing_columns = [
        column for column in required_columns
        if column not in customer_df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"В customer_mapping.xlsx нет колонок: {missing_columns}"
        )

    customer_df["Ключ_контрагент"] = (
        customer_df["Контрагент из 1С"].apply(normalize_text)
    )

    customer_df = customer_df.drop_duplicates(
        subset=["Ключ_контрагент"],
        keep="first",
    )

    customer_columns = [
        "Ключ_контрагент",
        "Зона для прогноза",
        "Страна",
        "Контрагент",
        "Статус",
    ]

    optional_columns = [
        "Зона",
        "Тип",
        "Менеджер покупателя",
    ]

    for column in optional_columns:
        if column in customer_df.columns:
            customer_columns.append(column)

    return customer_df[customer_columns]


def get_quantity_column(df: pd.DataFrame) -> str:
    """
    Определяет колонку с количеством в файле продаж.
    """
    candidates = [
        "Количество (в базовых единицах)",
        "Количество (в базовых единицах);",
        "Количество (в базовых единицах)",
        "Количество",
        "Приход",
    ]

    for column in candidates:
        if column in df.columns:
            return column

    raise ValueError(
        "Не найдена колонка с количеством. "
        "Ожидались: 'Количество (в базовых единицах)', 'Количество' или 'Приход'."
    )


def normalize_base_sales_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Приводит разные выгрузки продаж к базовым колонкам.

    Поддерживает:
    - исторический файл 2020-2025;
    - факт 1С без e-com;
    - факт 1С e-com.

    Важно:
    исторический файл уже может содержать колонку 'Категория',
    но не содержать 'Номенклатурная группа'.
    """
    df = clean_columns(df)

    df = df.rename(columns={
        "Комиссионер": "Контрагент",
        "Номенклатура группа": "Номенклатурная группа",
        "Номенклатурная группа": "Номенклатурная группа",
        "№ Недели": "Номер недели",
        "№ недели": "Номер недели",
    })

    df = collapse_duplicate_columns(df)
    df = remove_sales_service_rows(df)

    # Если это исторический файл, там может не быть 'Номенклатурная группа',
    # но уже есть готовая 'Категория'. Для единой логики создаём группу из категории.
    if "Номенклатурная группа" not in df.columns and "Категория" in df.columns:
        df["Номенклатурная группа"] = df["Категория"]

    quantity_column = get_quantity_column(df)

    df["Количество, шт"] = df[quantity_column].apply(normalize_quantity)
    df["Количество, шт"] = pd.to_numeric(
        df["Количество, шт"],
        errors="coerce",
    ).fillna(0)

    required_columns = [
        "Контрагент",
        "Номенклатурная группа",
        "Номенклатура",
        "По годам",
        "По месяцам",
        "По неделям",
        "Количество, шт",
    ]

    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"В файле продаж нет обязательных колонок: {missing_columns}\n\n"
            f"Найденные колонки в файле:\n{list(df.columns)}"
        )

    df["Год"] = df["По годам"].apply(parse_year)
    df["Месяц"] = df["По месяцам"].apply(parse_month_name)
    df["Месяц номер"] = df["По месяцам"].apply(get_month_number)

    df["Дата начала недели"] = df.apply(
        lambda row: parse_week_start(
            row["По неделям"],
            row["Год"],
        ),
        axis=1,
    )

    df["Номер недели"] = (
        df["Дата начала недели"]
        .dt.isocalendar()
        .week
        .astype("Int64")
    )

    df["Квартал"] = (
        df["Дата начала недели"]
        .dt.quarter
        .astype("Int64")
    )

    df["Ключ_номенклатура"] = df["Номенклатура"].apply(normalize_text)
    df["Ключ_группа"] = df["Номенклатурная группа"].apply(normalize_text)
    df["Ключ_контрагент"] = df["Контрагент"].apply(normalize_text)

    return df


def enrich_with_customers(
        df: pd.DataFrame,
        customer_mapping_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Добавляет канал, страну, нормальное название контрагента и статус.
    """
    df = df.copy()
    customer_mapping_df = prepare_customer_mapping(customer_mapping_df)

    df = df.merge(
        customer_mapping_df,
        how="left",
        on="Ключ_контрагент",
        suffixes=("", "_из_справочника"),
    )

    df["Канал"] = df["Зона для прогноза"].fillna("Не определено")
    df["Канал название"] = df["Канал"].map(CHANNEL_NAMES).fillna(df["Канал"])

    return df


def split_sets_to_sku(
        df: pd.DataFrame,
        set_mapping_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Раскладывает наборы на реальные SKU.

    Если номенклатура есть в set_mapping:
    - исходная строка набора удаляется;
    - вместо нее создаются строки по SKU внутри набора;
    - количество умножается на 'Количество в наборе'.
    """
    df = df.copy()
    set_mapping_df = prepare_set_mapping(set_mapping_df)

    if df.empty or set_mapping_df.empty:
        return df

    set_keys = set(set_mapping_df["Ключ_набора"].dropna().unique())

    normal_df = df[
        ~df["Ключ_номенклатура"].isin(set_keys)
    ].copy()

    sets_df = df[
        df["Ключ_номенклатура"].isin(set_keys)
    ].copy()

    if sets_df.empty:
        return df

    sets_expanded = sets_df.merge(
        set_mapping_df,
        how="left",
        left_on="Ключ_номенклатура",
        right_on="Ключ_набора",
        suffixes=("", "_set"),
    )

    sets_expanded["Номенклатура исходная"] = sets_expanded["Номенклатура"]
    sets_expanded["Номенклатура"] = sets_expanded["SKU внутри набора"]

    sets_expanded["Количество, шт"] = (
            sets_expanded["Количество, шт"]
            * sets_expanded["Количество в наборе"]
    )

    # После разложения набора ключ номенклатуры становится ключом SKU внутри набора.
    sets_expanded["Ключ_номенклатура"] = (
        sets_expanded["Номенклатура"].apply(normalize_text)
    )

    result_df = pd.concat(
        [
            normal_df,
            sets_expanded,
        ],
        ignore_index=True,
    )

    return result_df


def enrich_with_product_mapping(
        df: pd.DataFrame,
        product_mapping_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Добавляет Категорию, SKU, Формулу, Вес и Квант.

    Для обычной номенклатуры подтягиваем данные из Лист1.
    Для разложенных наборов часть колонок уже пришла из set_mapping.
    """
    df = df.copy()
    mapping_df = prepare_product_mapping(product_mapping_df)

    before_columns = set(df.columns)

    df = df.merge(
        mapping_df,
        how="left",
        on="Ключ_номенклатура",
        suffixes=("", "_map"),
    )

    # Если данные уже есть из set_mapping, оставляем их.
    # Если пусто — берем из основного справочника.
    columns_to_fill = [
        "Категория",
        "SKU",
        "Формула",
        "Вес",
        "Квант, шт",
        "SKU Daniel",
        "formula Daniel",
    ]

    for column in columns_to_fill:
        map_column = f"{column}_map"

        if column in before_columns and map_column in df.columns:
            df[column] = df[column].combine_first(df[map_column])

        elif column not in before_columns and map_column in df.columns:
            df[column] = df[map_column]

    drop_columns = [
        column for column in df.columns
        if column.endswith("_map")
    ]

    df = df.drop(columns=drop_columns, errors="ignore")

    return df


def calculate_sales_units(df: pd.DataFrame) -> pd.DataFrame:
    """
    Считает продажи в кг и упаковках.
    """
    df = df.copy()

    df["Вес"] = pd.to_numeric(df["Вес"], errors="coerce")
    df["Квант, шт"] = pd.to_numeric(df["Квант, шт"], errors="coerce")
    df["Количество, шт"] = pd.to_numeric(
        df["Количество, шт"],
        errors="coerce",
    ).fillna(0)

    df["Количество, кг"] = df["Количество, шт"] * df["Вес"] / 1000

    df["Количество, упак"] = (
            df["Количество, шт"] / df["Квант, шт"]
    )

    return df


def prepare_final_sales_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Оставляет финальные колонки для раздела Продажи прогноз.
    """
    df = df.copy()

    final_columns = [
        "Тип данных",
        "Источник",
        "Файл_источник",
        "Канал",
        "Канал название",
        "Контрагент",
        "Страна",
        "Статус",
        "Номенклатурная группа",
        "Номенклатура",
        "Номенклатура исходная",
        "Категория",
        "SKU",
        "Формула",
        "SKU Daniel",
        "formula Daniel",
        "Вес",
        "Квант, шт",
        "Год",
        "Квартал",
        "Месяц",
        "Месяц номер",
        "Дата начала недели",
        "Номер недели",
        "Количество, шт",
        "Количество, кг",
        "Количество, упак",
    ]

    existing_columns = [
        column for column in final_columns
        if column in df.columns
    ]

    df = df[existing_columns]

    text_category_columns = [
        "Тип данных",
        "Источник",
        "Канал",
        "Канал название",
        "Контрагент",
        "Страна",
        "Категория",
        "SKU",
        "Формула",
        "SKU Daniel",
        "formula Daniel",
    ]

    for column in text_category_columns:
        if column in df.columns:
            df[column] = df[column].astype("category")

    return df


def transform_sales_history(
        df: pd.DataFrame,
        product_mapping_df: pd.DataFrame,
        customer_mapping_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Преобразует исторические продажи 2020-2025.

    Исторический файл уже содержит Категорию, SKU, Формулу, Вес,
    но мы дополнительно обогащаем его через product_mapping.xlsx,
    чтобы подтянуть Квант, SKU Daniel и formula Daniel.
    """
    if df.empty:
        return pd.DataFrame()

    df = normalize_base_sales_columns(df)

    df["Тип данных"] = "Факт"

    if "Источник" not in df.columns:
        df["Источник"] = "История продаж"

    if "type" in df.columns and "Канал" not in df.columns:
        df["Канал"] = df["type"]

    df = enrich_with_customers(df, customer_mapping_df)
    df = enrich_with_product_mapping(df, product_mapping_df)
    df = calculate_sales_units(df)
    df = prepare_final_sales_columns(df)

    return df


def transform_sales_actual(
        df: pd.DataFrame,
        product_mapping_df: pd.DataFrame,
        set_mapping_df: pd.DataFrame,
        customer_mapping_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Преобразует фактические продажи текущего года из файлов 1С.

    Поддерживает:
    - файл без e-com;
    - файл e-com;
    - строки с наборами;
    - обычные строки по SKU.
    """
    if df.empty:
        return pd.DataFrame()

    df = normalize_base_sales_columns(df)

    df["Тип данных"] = "Факт"

    if "Источник" not in df.columns:
        df["Источник"] = "Факт 1С"

    df = enrich_with_customers(df, customer_mapping_df)
    df = split_sets_to_sku(df, set_mapping_df)
    df = enrich_with_product_mapping(df, product_mapping_df)
    df = calculate_sales_units(df)
    df = prepare_final_sales_columns(df)

    return df


def transform_manual_forecast(
        df: pd.DataFrame,
        product_mapping_df: pd.DataFrame,
        customer_mapping_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Заготовка под ручной прогноз.

    Сейчас функция готова под будущий файл ручного прогноза.
    Когда утвердим шаблон ручного прогноза, доработаем под него.
    """
    if df.empty:
        return pd.DataFrame()

    df = normalize_base_sales_columns(df)

    df["Тип данных"] = "Ручной прогноз"

    if "Источник" not in df.columns:
        df["Источник"] = "Ручной прогноз"

    df = enrich_with_customers(df, customer_mapping_df)
    df = enrich_with_product_mapping(df, product_mapping_df)
    df = calculate_sales_units(df)
    df = prepare_final_sales_columns(df)

    return df


def combine_sales_data(
        history_df: pd.DataFrame,
        actual_df: pd.DataFrame,
        manual_forecast_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Объединяет историю, факт текущего года и ручной прогноз.
    """
    dataframes = []

    if not history_df.empty:
        dataframes.append(history_df)

    if not actual_df.empty:
        dataframes.append(actual_df)

    if manual_forecast_df is not None and not manual_forecast_df.empty:
        dataframes.append(manual_forecast_df)

    if not dataframes:
        return pd.DataFrame()

    df = pd.concat(dataframes, ignore_index=True)

    df = df.sort_values(
        [
            "Год",
            "Дата начала недели",
            "Категория",
            "SKU",
        ],
        na_position="last",
    )

    return df
