import pandas as pd


def normalize_container(value) -> str:
    """
    Приводит номер контейнера к единому виду:
    1215.0 -> 1215
    1215 -> 1215
    """
    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text.lower() in ["nan", "none", ""]:
        return ""

    try:
        number = float(text)
        if number.is_integer():
            return str(int(number))
    except ValueError:
        pass

    return text


def replace_plan_with_fact(df: pd.DataFrame) -> pd.DataFrame:
    """
    Если контейнер уже есть в фактических приходах,
    весь план Дениэла по этому контейнеру убирается.

    Почему так:
    - Дениэл может планировать одну дату прихода;
    - фактически контейнер может прийти позже/раньше;
    - состав контейнера по факту может отличаться от плана;
    - для управленческой картины факт должен заменить план по контейнеру целиком.
    """
    if df.empty:
        return df

    df = df.copy()
    df["Контейнер"] = df["Контейнер"].apply(normalize_container)

    fact_containers = (
        df[
            (df["Тип данных"] == "Факт")
            & (df["Источник"] == "Факт 1С")
            & (df["Контейнер"] != "")
            ]["Контейнер"]
        .drop_duplicates()
    )

    df = df[
        ~(
                (df["Тип данных"] == "План")
                & (df["Источник"] == "План Дениэл")
                & (df["Контейнер"].isin(fact_containers))
        )
    ].copy()

    return df


def get_value_column(unit: str) -> str:
    """
    Возвращает колонку количества в выбранной единице.
    """
    if unit == "кг":
        return "Количество, кг"

    if unit == "уп":
        return "Количество, упак"

    return "Количество, шт"


def make_week_label(df: pd.DataFrame) -> pd.DataFrame:
    """
    Добавляет красивую подпись недели.
    """
    df = df.copy()

    df["Неделя"] = (
            df["Номер недели"].astype(str)
            + " нед. с "
            + df["Дата начала недели"].dt.strftime("%d.%m.%Y")
    )

    return df
