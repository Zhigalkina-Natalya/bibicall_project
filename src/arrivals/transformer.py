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

MONTHS_EN = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Очищает названия колонок.
    """
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()
    return df


def normalize_text(value) -> str:
    """
    Нормализует текст для сопоставления.
    """
    if pd.isna(value):
        return ""

    text = str(value).upper()
    text = text.replace("Ё", "Е")
    text = text.replace("ГР.", "Г")
    text = text.replace("Г.", "Г")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def parse_year(value) -> pd.Int64Dtype:
    """
    Извлекает год из значений:
    - 2020
    - 2026 г.
    """
    if pd.isna(value):
        return pd.NA

    match = re.search(r"\d{4}", str(value))

    if not match:
        return pd.NA

    return int(match.group(0))


def parse_month_name(value) -> str:
    """
    Очищает месяц:
    - Январь 2026 г. -> Январь
    - Январь -> Январь
    """
    if pd.isna(value):
        return ""

    text = str(value).strip()
    text = re.sub(r"\d{4}", "", text)
    text = text.replace("г.", "")
    text = text.replace("г", "")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def parse_week_start(value) -> pd.Timestamp:
    """
    Извлекает дату начала недели.

    Поддерживает:
    - Excel datetime
    - 13.01.2020
    - Неделя с 12.01.2026
    """
    if pd.isna(value):
        return pd.NaT

    if isinstance(value, (pd.Timestamp,)):
        return value

    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if not pd.isna(parsed):
        return parsed

    text = str(value)

    match = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)

    if not match:
        return pd.NaT

    return pd.to_datetime(match.group(1), format="%d.%m.%Y", errors="coerce")


def parse_etd(value, year: int | None = None) -> pd.Timestamp:
    """
    Преобразует ETD из файла Дениэла.

    Поддерживает:
    - 19-Nov
    - 21-Jan
    - 19.11.2025
    """
    if pd.isna(value):
        return pd.NaT

    if isinstance(value, pd.Timestamp):
        return value

    text = str(value).strip()

    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if not pd.isna(parsed):
        if year and parsed.year == 1900:
            return parsed.replace(year=year)
        return parsed

    match = re.search(r"(\d{1,2})[-.\s]+([A-Za-zА-Яа-я]+)", text)

    if not match or not year:
        return pd.NaT

    day = int(match.group(1))
    month_text = match.group(2).upper()

    month = MONTHS_EN.get(month_text) or MONTHS_RU.get(month_text)

    if not month:
        return pd.NaT

    return pd.Timestamp(year=year, month=month, day=day)


def prepare_mapping(mapping_df: pd.DataFrame) -> pd.DataFrame:
    """
    Готовит справочник товаров.
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
        raise ValueError(f"В справочнике нет колонок: {missing_columns}")

    mapping_df["Ключ_группа"] = mapping_df["Номенклатурная группа"].apply(normalize_text)
    mapping_df["Ключ_номенклатура"] = mapping_df["Номенклатура"].apply(normalize_text)

    if "SKU Daniel" in mapping_df.columns:
        mapping_df["Ключ_Daniel"] = mapping_df["SKU Daniel"].apply(normalize_text)

    return mapping_df


def enrich_with_mapping(
        df: pd.DataFrame,
        mapping_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Добавляет Категорию, SKU, Формулу, Вес, Квант по 1С-номенклатуре.
    """
    df = df.copy()
    mapping_df = prepare_mapping(mapping_df)

    df["Ключ_группа"] = df["Номенклатурная группа"].apply(normalize_text)
    df["Ключ_номенклатура"] = df["Номенклатура"].apply(normalize_text)

    mapping_columns = [
        "Ключ_группа",
        "Ключ_номенклатура",
        "Категория",
        "SKU",
        "Формула",
        "Вес",
        "Квант, шт",
        "SKU Daniel",
    ]

    df = df.merge(
        mapping_df[mapping_columns],
        how="left",
        on=["Ключ_группа", "Ключ_номенклатура"],
    )

    return df


def enrich_with_daniel_mapping(
        df: pd.DataFrame,
        mapping_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Добавляет Категорию, SKU, Формулу, Вес, Квант по SKU Daniel.

    Важно:
    в справочнике один SKU Daniel может встречаться несколько раз
    из-за разных вариантов названий в 1С.
    Для файла Дениэла нам нужна только одна уникальная связка SKU Daniel -> SKU.
    """
    df = df.copy()
    mapping_df = prepare_mapping(mapping_df)

    if "Ключ_Daniel" not in mapping_df.columns:
        raise ValueError("В product_mapping.xlsx нет колонки 'SKU Daniel'.")

    df["SKU Daniel"] = df["SKU Daniel"].astype(str).str.strip()
    df["Ключ_Daniel"] = df["SKU Daniel"].apply(normalize_text)

    mapping_columns = [
        "Ключ_Daniel",
        "Номенклатурная группа",
        "Номенклатура",
        "Категория",
        "SKU",
        "Формула",
        "Вес",
        "Квант, шт",
    ]

    daniel_mapping = (
        mapping_df[mapping_columns]
        .dropna(subset=["Ключ_Daniel"])
        .drop_duplicates(subset=["Ключ_Daniel"], keep="first")
    )

    df = df.merge(
        daniel_mapping,
        how="left",
        on="Ключ_Daniel",
    )

    return df


def transform_history_arrivals(
        df: pd.DataFrame,
        mapping_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Преобразует исторический файл приходов 2020-2025.
    """
    if df.empty:
        return pd.DataFrame()

    df = clean_columns(df)

    df = df.rename(columns={
        "№ Контейнера": "Контейнер",
        "№ контейнера": "Контейнер",
        "Количество, шт": "Количество, шт",
        "Количество,шт": "Количество, шт",
    })

    df["Год"] = df["По годам"].apply(parse_year)
    df["Месяц"] = df["По месяцам"].apply(parse_month_name)
    df["Дата начала недели"] = df["По неделям"].apply(parse_week_start)
    df["Номер недели"] = df["Дата начала недели"].dt.isocalendar().week.astype("Int64")

    df["Тип данных"] = "Факт"
    df["Источник"] = "История 2020-2025"

    return prepare_final_arrivals_columns(df)


def transform_actual_arrivals(
        df: pd.DataFrame,
        mapping_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Преобразует еженедельный файл фактических приходов из 1С.
    """
    if df.empty:
        return pd.DataFrame()

    df = clean_columns(df)

    df = df.rename(columns={
        "Характеристика номенклатуры": "Контейнер",
        "Количество (в ед. хранения": "Количество, шт",
        "Количество (в ед. хранения)": "Количество, шт",
        "Количество": "Количество, шт",
        "Количество, шт": "Количество, шт",
    })

    df = df[
        ~df.astype(str)
        .apply(lambda row: row.str.upper().str.contains("ИТОГ").any(), axis=1)
    ]

    df["Год"] = df["По годам"].apply(parse_year)
    df["Месяц"] = df["По месяцам"].apply(parse_month_name)
    df["Дата начала недели"] = df["По неделям"].apply(parse_week_start)
    df["Номер недели"] = df["Дата начала недели"].dt.isocalendar().week.astype("Int64")

    df = enrich_with_mapping(df, mapping_df)

    df["Тип данных"] = "Факт"
    df["Источник"] = "Факт 1С"

    return prepare_final_arrivals_columns(df)


def transform_daniel_arrivals(
        df: pd.DataFrame,
        mapping_df: pd.DataFrame,
        arrival_days: int = 70,
) -> pd.DataFrame:
    """
    Преобразует файл Дениэла с отправками контейнеров.

    N14, N18, N28, NC4 и т.д. → ETD + 70 дней = ожидаемый приход на склад.
    Buck, Oats, Rice, Corn → ETD + 14 дней = ожидаемый приход на склад.
    """
    if df.empty:
        return pd.DataFrame()

    df = clean_columns(df)

    df = df.rename(columns={
        "Год отправки": "Год отправки",
        "Месяц отправки": "Месяц отправки",
        "Количество упаковок": "Количество упаковок",
        "Контейнер": "Контейнер",
        "Единица": "Единица",
    })

    df["Год отправки"] = df["Год отправки"].apply(parse_year)
    df["Месяц отправки"] = df["Месяц отправки"].astype(str).str.strip()
    df["ETD"] = df.apply(
        lambda row: parse_etd(row["ETD"], row["Год отправки"]),
        axis=1,
    )

    short_delivery_skus = [
        "BUCK",
        "OATS",
        "RICE",
        "CORN",
    ]

    df["SKU Daniel normalized"] = df["SKU Daniel"].apply(normalize_text)

    df["Срок доставки, дней"] = df["SKU Daniel normalized"].apply(
        lambda sku: 14 if sku in short_delivery_skus else arrival_days
    )

    df["Дата начала недели"] = (
            df["ETD"]
            + pd.to_timedelta(df["Срок доставки, дней"], unit="D")
    )
    df["Дата начала недели"] = (
            df["Дата начала недели"]
            - pd.to_timedelta(df["Дата начала недели"].dt.weekday, unit="D")
    )

    df["Год"] = df["Дата начала недели"].dt.year
    df["Месяц"] = df["Дата начала недели"].dt.month
    df["Номер недели"] = df["Дата начала недели"].dt.isocalendar().week.astype("Int64")

    df = enrich_with_daniel_mapping(df, mapping_df)

    df["Количество упаковок"] = pd.to_numeric(
        df["Количество упаковок"],
        errors="coerce",
    ).fillna(0)

    df["Квант, шт"] = pd.to_numeric(df["Квант, шт"], errors="coerce")

    # Важно:
    # НЭННИ в файле Дениэла указываются в упаковках/cases,
    # поэтому переводим в штуки через квант.
    #
    # Каши Buck/Oats/Rice/Corn в файле Дениэла уже указаны в штуках,
    # поэтому НЕ умножаем их на квант.
    df["Количество, шт"] = df.apply(
        lambda row: (
            row["Количество упаковок"]
            if row["SKU Daniel normalized"] in short_delivery_skus
            else row["Количество упаковок"] * row["Квант, шт"]
        ),
        axis=1,
    )

    df["Тип данных"] = "План"
    df["Источник"] = "План Дениэл"

    return prepare_final_arrivals_columns(df)


def prepare_final_arrivals_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Приводит приход к единой структуре.
    """
    df = df.copy()

    if "Контейнер" not in df.columns:
        df["Контейнер"] = ""

    if "Месяц" not in df.columns:
        df["Месяц"] = ""

    df["Контейнер"] = df["Контейнер"].astype(str).str.strip()
    df["Количество, шт"] = pd.to_numeric(df["Количество, шт"], errors="coerce").fillna(0)
    df["Вес"] = pd.to_numeric(df["Вес"], errors="coerce")
    df["Квант, шт"] = pd.to_numeric(df["Квант, шт"], errors="coerce")

    df["Количество, кг"] = df["Количество, шт"] * df["Вес"] / 1000
    df["Количество, упак"] = df["Количество, шт"] / df["Квант, шт"]

    final_columns = [
        "Тип данных",
        "Источник",
        "Контрагент",
        "Номенклатурная группа",
        "Номенклатура",
        "Категория",
        "SKU",
        "SKU Daniel",
        "Формула",
        "Вес",
        "Квант, шт",
        "Контейнер",
        "Год",
        "Месяц",
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

    return df[existing_columns]
