import pandas as pd


RISK_LEVELS = [
    "Свежий 🟢",
    "Хороший 🟢",
    "Норма 🟡",
    "Внимание 🟡",
    "Пограничный 🟠",
    "Горящий 🔴",
    "Критично 🔴",
    "Списание ⚫",
    "Ошибка",
]


def get_risk_level(osg: float) -> str:
    """
    Возвращает существующий уровень риска по ОСГ.
    """
    if pd.isna(osg):
        return "Ошибка"
    if osg >= 75:
        return "Свежий 🟢"
    if osg >= 70:
        return "Хороший 🟢"
    if osg >= 66:
        return "Норма 🟡"
    if osg >= 60:
        return "Внимание 🟡"
    if osg >= 50:
        return "Пограничный 🟠"
    if osg >= 40:
        return "Горящий 🔴"
    if osg >= 20:
        return "Критично 🔴"
    return "Списание ⚫"


def count_attention_groups(df: pd.DataFrame) -> int:
    """Counts analytical groups in the Attention range: 60 <= OSG < 66."""
    return int(
        ((df["ОСГ %"] >= 60) & (df["ОСГ %"] < 66)).sum()
    )


def filter_analytical_stock(df: pd.DataFrame) -> pd.DataFrame:
    """
    Применяет порог основной аналитики: Остаток > 100.
    """
    return df.loc[df["Остаток"] > 100].copy()


def split_stock_views(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Делит полный набор на основную аналитику и малые остатки без потери строк.
    """
    main_stock = df.loc[df["Остаток"] > 100].copy()
    small_stock = df.loc[df["Остаток"] <= 100].copy()
    return main_stock, small_stock


def validate_and_split_stock(
        df: pd.DataFrame,
        validation_func,
) -> tuple[list[str], pd.DataFrame, pd.DataFrame]:
    """
    Сначала проверяет полный набор, затем формирует два представления.
    """
    errors = validation_func(df)
    main_stock, small_stock = split_stock_views(df)
    return errors, main_stock, small_stock


def build_urgent_sales(df: pd.DataFrame) -> pd.DataFrame:
    """
    Формирует срочные продажи из уже отфильтрованной основной аналитики.

    Снача агрегирует все технические строки аналитической группы,
    затем применяет условия по ОСГ и свободному остатку.
    """
    grouped = (
        df
        .groupby(["Категория", "SKU", "Срок годности"], as_index=False)
        .agg({
            "Остаток": "sum",
            "Зарезервировано": "sum",
            "Свободный остаток": "sum",
            "ОСГ %": "min",
        })
    )

    urgent_sales = grouped.loc[
        (grouped["ОСГ %"] < 60)
        & (grouped["Свободный остаток"] > 0)
    ].copy()

    nonzero_stock = urgent_sales["Остаток"].where(
        urgent_sales["Остаток"].ne(0)
    )
    urgent_sales["Доля резерва, %"] = (
        urgent_sales["Зарезервировано"] / nonzero_stock * 100
    )

    return urgent_sales.sort_values(
        ["ОСГ %", "Свободный остаток"],
        ascending=[True, False],
    )
