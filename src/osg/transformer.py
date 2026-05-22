import pandas as pd


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Очистка названий колонок от лишних пробелов.
    """
    df.columns = df.columns.str.strip()
    return df


def rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Переименовывает колонки отчёта 1С в рабочие названия.

    В отчёте 1С три числовые колонки могут называться одинаково:
    'В ед. хранения', 'В ед. хранения.1', 'В ед. хранения.2'.
    """
    df = df.rename(columns={
        "Номенклатурная группа": "Категория_исходная",
        "Номенклатура": "SKU",
        "Срок годности": "Срок годности",
        "Характеристика номенклатуры": "Контейнер",
        "В ед. хранения": "Остаток",
        "В ед. хранения.1": "Зарезервировано",
        "В ед. хранения.2": "Свободный остаток",
    })

    return df


def convert_dates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Преобразует колонку 'Срок годности' в формат даты.

    В выгрузке из 1С дата приходит в формате:
    03.12.2027 0:00:00

    Нам важно читать её как:
    день.месяц.год
    """
    df["Срок годности_исходная"] = df["Срок годности"]

    df["Срок годности"] = (
        df["Срок годности"]
        .astype(str)
        .str.strip()
        .str.replace(" 0:00:00", "", regex=False)
    )

    df["Срок годности"] = pd.to_datetime(
        df["Срок годности"],
        format="%d.%m.%Y",
        errors="coerce"
    )

    return df


def extract_weight(df: pd.DataFrame) -> pd.DataFrame:
    """
    Извлекает вес из SKU.

    Если вес не указан в названии:
    - Флоупак печенье Грушевое = 37.5 г
    - Шоубокс печенье Грушевое = 20 * 37.5 = 750 г
    """
    df["Вес"] = df["SKU"].astype(str).str.extract(r"(\d+(?:[,.]\d+)?)\s*г", expand=False)
    df["Вес"] = df["Вес"].str.replace(",", ".", regex=False)
    df["Вес"] = pd.to_numeric(df["Вес"], errors="coerce")

    sku_upper = df["SKU"].astype(str).str.upper()

    df.loc[
        sku_upper.str.contains("ФЛОУПАК ПЕЧЕНЬЕ ГРУШЕВОЕ", na=False),
        "Вес"
    ] = 37.5

    df.loc[
        sku_upper.str.contains("ШОУБОКС ПЕЧЕНЬЕ ГРУШЕВОЕ", na=False),
        "Вес"
    ] = 20 * 37.5

    return df


def transform_category(df: pd.DataFrame) -> pd.DataFrame:
    """
    Преобразует категории:
    - Флоупак печенье -> ФЛОУПАК_ПЕЧЕНЬЕ
    - Шоубокс печенье -> ШОУБОКС_ПЕЧЕНЬЕ
    - НЭННИ делит на НЭННИ 400 и НЭННИ 800
    - переименовывает отдельные категории пюре
    - остальные категории оставляет без изменений
    """

    def get_category(row):
        base = row["Категория_исходная"]
        base_upper = str(base).upper()
        sku = str(row["SKU"]).upper()

        if "ФЛОУПАК" in sku and "ПЕЧЕНЬЕ" in sku:
            return "ФЛОУПАК_ПЕЧЕНЬЕ"

        if "ШОУБОКС" in sku and "ПЕЧЕНЬЕ" in sku:
            return "ШОУБОКС_ПЕЧЕНЬЕ"

        if "МЯСНЫЕ" in base_upper and "КОНСЕРВЫ" in base_upper:
            return "ПЮРЕ МЯСНЫЕ консервы"

        if "РЫБНЫЕ" in base_upper and "КОНСЕРВЫ" in base_upper:
            return "ПЮРЕ РЫБНЫЕ консервы"

        if "ТВОРОЖНОЕ ПЮРЕ" in base_upper:
            return "ПЮРЕ ТВОРОЖНОЕ"

        if "НЭННИ" in base_upper:
            if row["Вес"] == 400:
                return "НЭННИ 400"
            elif row["Вес"] == 800:
                return "НЭННИ 800"

        return base

    df["Категория"] = df.apply(get_category, axis=1)
    return df


def remove_service_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Удаляет служебные строки из отчёта 1С:
    - полностью пустые строки
    - строку 'Итог'
    - строки без SKU
    """
    df = df.dropna(how="all")

    if "SKU" in df.columns:
        df = df[df["SKU"].notna()]
        df = df[~df["SKU"].astype(str).str.strip().str.upper().eq("ИТОГ")]

    return df


def normalize_data_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Приводит типы данных к стабильному виду для Streamlit и Excel.

    Особенно важно:
    - Контейнер хранить как текст, потому что бывают значения вроде '1141А32'
    """
    df["Контейнер"] = df["Контейнер"].astype(str).str.strip()

    return df


def prepare_final_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Готовит финальную структуру таблицы для выгрузки:
    - убирает служебные колонки
    - оставляет только преобразованную категорию
    - форматирует срок годности как ДД.ММ.ГГГГ
    - приводит ОСГ к удобному виду
    """
    df = df.copy()

    df["Срок годности"] = df["Срок годности"].dt.strftime("%d.%m.%Y")
    df["ОСГ %"] = df["ОСГ %"].round(1)

    final_columns = [
        "Склад",
        "Категория",
        "SKU",
        "Срок годности",
        "Контейнер",
        "Остаток",
        "Зарезервировано",
        "Свободный остаток",
        "Вес",
        "days_left",
        "total_days",
        "ОСГ %",
    ]

    return df[final_columns]
