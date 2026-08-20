import pandas as pd
from datetime import datetime

# 📌 1. Сроки по категориям (в днях)
CATEGORY_SHELF_LIFE = {
    "ПЕЧЕНЬЕ": 365,
    "БИБИКАША": 456,
    "ПЮРЕ МОЛОЧНОЕ": 547,
    "ПЮРЕ ТВОРОЖНОЕ": 730,
    "МЯСНЫЕ КОНСЕРВЫ": 730,
    "РЫБНЫЕ КОНСЕРВЫ": 730,
    "АМАЛТЕЯ": 1080,
}

# 📌 2. Сроки по SKU НЭННИ (в днях)
NENNI_SHELF_LIFE_DAYS = {
    "НЭННИ КЛАССИКА 400": 912,
    "НЭННИ КЛАССИКА 800": 912,
    "НЭННИ .3 С ПРЕБИОТИКАМИ 400": 912,
    "НЭННИ .3 С ПРЕБИОТИКАМИ 800": 912,
    "НЭННИ 1 400": 912,
    "НЭННИ 1 800": 912,
    "НЭННИ 2 400": 912,
    "НЭННИ 2 800": 912,
    "НЭННИ 3 400": 912,
    "НЭННИ 3 800": 912,
    "НЭННИ 4 400": 730,
    "НЭННИ 4 800": 730,
}


# 🔧 Вспомогательная функция
def normalize_text(text: str) -> str:
    """
    Приводит текст к нормализованному виду:
    - верхний регистр
    - убирает "гр." и "г."
    - убирает лишние пробелы
    """
    if pd.isna(text):
        return ""

    text = str(text).upper()

    text = text.replace("ГР.", "")
    text = text.replace("Г.", "")
    text = text.replace("  ", " ")

    return text.strip()


# 📦 Срок жизни для НЭННИ
def get_nenni_shelf_life_days(sku: str) -> int | None:
    """
    Возвращает срок жизни в днях для SKU НЭННИ.

    :param sku: название SKU
    :return: срок жизни в днях или None
    """
    sku_norm = normalize_text(sku)

    for key, days in NENNI_SHELF_LIFE_DAYS.items():
        if key in sku_norm:
            return days

    return None


# 🧠 Главная логика определения срока
def get_shelf_life_rule(row) -> tuple[str, int]:
    """
    Возвращает название применённого правила и полный срок жизни.

    Отдельное имя правила нужно только для диагностики и тестов.
    Существующие сроки и fallback 730 не изменяются.
    """
    category = normalize_text(row["Категория"])
    sku = row["SKU"]

    if "НЭННИ" in category:
        days = get_nenni_shelf_life_days(sku)
        if days:
            return "НЭННИ по SKU", days

    for key, days in CATEGORY_SHELF_LIFE.items():
        if key in category:
            return f"Категория: {key}", days

    return "Fallback 730", 730


def get_shelf_life(row) -> int:
    """
    Определяет срок жизни:
    - если НЭННИ → по SKU
    - иначе → по категории

    :param row: строка DataFrame
    :return: срок жизни в днях
    """
    _, days = get_shelf_life_rule(row)
    return days


# 📊 Основная функция расчёта ОСГ
def calculate_osg(
        df: pd.DataFrame,
        calculation_date=None,
) -> pd.DataFrame:
    """
    Рассчитывает:
    - дни до окончания срока
    - общий срок жизни
    - ОСГ %

    :param df: DataFrame
    :return: DataFrame с расчётами
    """
    if calculation_date is None:
        calculation_date = datetime.today()

    calculation_date = pd.Timestamp(calculation_date).normalize()

    df["days_left"] = (df["Срок годности"] - calculation_date).dt.days

    df["total_days"] = df.apply(get_shelf_life, axis=1)

    df["ОСГ %"] = (df["days_left"] / df["total_days"]) * 100

    return df
