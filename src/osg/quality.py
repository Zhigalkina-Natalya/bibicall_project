import re

import pandas as pd

from src.osg.calculator import get_shelf_life_rule


QUANTITY_COLUMNS = [
    "Остаток",
    "Зарезервировано",
    "Свободный остаток",
]

PROPOSED_DUPLICATE_KEY = [
    "Склад",
    "SKU",
    "Контейнер",
    "Срок годности",
]


def find_missing_sku(df: pd.DataFrame) -> pd.DataFrame:
    sku = df["SKU"]
    mask = sku.isna() | sku.astype("string").str.strip().eq("").fillna(False)
    return df.loc[mask].copy()


def find_missing_expiry_date(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[df["Срок годности"].isna()].copy()


def find_unknown_categories(df: pd.DataFrame) -> pd.DataFrame:
    category = df["Категория"]
    normalized = category.astype("string").str.strip()
    mask = (
        category.isna()
        | normalized.eq("").fillna(False)
        | normalized.str.upper().eq("НЕ ОПРЕДЕЛЕНО").fillna(False)
    )
    return df.loc[mask].copy()


def find_non_numeric_quantities(df: pd.DataFrame) -> pd.DataFrame:
    mask = pd.Series(False, index=df.index)

    for column in QUANTITY_COLUMNS:
        values = df[column]
        mask |= values.notna() & pd.to_numeric(values, errors="coerce").isna()

    return df.loc[mask].copy()


def find_negative_quantities(df: pd.DataFrame) -> pd.DataFrame:
    mask = pd.Series(False, index=df.index)

    for column in QUANTITY_COLUMNS:
        values = pd.to_numeric(df[column], errors="coerce")
        mask |= values.lt(0).fillna(False)

    return df.loc[mask].copy()


def find_null_quantities(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        column: df.loc[df[column].isna()].copy()
        for column in QUANTITY_COLUMNS
    }


def find_quantity_balance_issues(df: pd.DataFrame) -> pd.DataFrame:
    total = pd.to_numeric(df["Остаток"], errors="coerce")
    reserved = pd.to_numeric(df["Зарезервировано"], errors="coerce")
    free = pd.to_numeric(df["Свободный остаток"], errors="coerce")

    complete = total.notna() & reserved.notna() & free.notna()
    mismatch = complete & ((total - reserved - free).abs() > 1e-9)

    return df.loc[mismatch].copy()


def find_duplicate_key_rows(df: pd.DataFrame) -> pd.DataFrame:
    existing_key = [
        column for column in PROPOSED_DUPLICATE_KEY
        if column in df.columns
    ]

    if len(existing_key) != len(PROPOSED_DUPLICATE_KEY):
        return df.iloc[0:0].copy()

    return df.loc[
        df.duplicated(subset=existing_key, keep=False)
    ].copy()


def find_fallback_shelf_life_rows(df: pd.DataFrame) -> pd.DataFrame:
    mask = df.apply(
        lambda row: get_shelf_life_rule(row)[0] == "Fallback 730",
        axis=1,
    )
    return df.loc[mask].copy()


def find_technical_sku_issues(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    sku = df["SKU"].fillna("").astype(str)

    return {
        "leading_star": df.loc[sku.str.match(r"^\s*\*")].copy(),
        "edge_spaces": df.loc[sku.ne(sku.str.strip())].copy(),
        "repeated_spaces": df.loc[sku.str.contains(r"\s{2,}", regex=True)].copy(),
    }


def find_unresolved_sku(df: pd.DataFrame) -> pd.DataFrame:
    if "SKU_исходный" not in df.columns:
        return df.iloc[0:0].copy()

    raw = df["SKU_исходный"]
    normalized = df["SKU"]
    raw_has_value = raw.notna() & raw.astype("string").str.strip().ne("").fillna(False)
    normalized_missing = (
        normalized.isna()
        | normalized.astype("string").str.strip().eq("").fillna(False)
    )

    return df.loc[raw_has_value & normalized_missing].copy()


def get_sku_normalization_reason(raw_name, normalized_name) -> str:
    if pd.isna(raw_name):
        return "исходное название отсутствует"

    raw_text = str(raw_name)
    reasons = []

    if re.match(r"^\s*\*", raw_text):
        reasons.append("ведущая техническая *")
    if raw_text != raw_text.strip():
        reasons.append("пробелы по краям")
    if re.search(r"\s{2,}", raw_text.strip()):
        reasons.append("повторные пробелы")
    if re.search(r"\s+г$", raw_text.strip(), flags=re.IGNORECASE):
        reasons.append("нормализация точки после г")
    if "(ЗК)" in raw_text.upper():
        reasons.append("подтверждённое бизнес-соответствие (ЗК)")

    if not reasons and str(raw_name) != str(normalized_name):
        reasons.append("техническая нормализация")

    return "; ".join(reasons) if reasons else "без изменений"


def build_sku_normalization_table(df: pd.DataFrame) -> pd.DataFrame:
    if "SKU_исходный" not in df.columns:
        return pd.DataFrame(
            columns=["source_name", "analytical_sku", "reason"]
        )

    result = (
        df[["SKU_исходный", "SKU"]]
        .drop_duplicates()
        .rename(columns={
            "SKU_исходный": "source_name",
            "SKU": "analytical_sku",
        })
    )
    result["reason"] = result.apply(
        lambda row: get_sku_normalization_reason(
            row["source_name"],
            row["analytical_sku"],
        ),
        axis=1,
    )

    return result.sort_values(
        ["analytical_sku", "source_name"],
        na_position="last",
    ).reset_index(drop=True)


def find_sku_name_collisions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Показывает аналитические SKU, полученные из нескольких исходных названий.

    Наличие строки в результате не означает ошибку: подтверждённые технические
    варианты также образуют такое совпадение и требуют просмотра причины.
    """
    mapping = build_sku_normalization_table(df)
    if mapping.empty:
        return mapping

    counts = mapping.groupby("analytical_sku")["source_name"].transform("size")
    return mapping.loc[counts > 1].reset_index(drop=True)


def run_quality_diagnostics(df: pd.DataFrame) -> dict[str, int]:
    """
    Выполняет все диагностические проверки по переданному полному набору.

    Функция ничего не исправляет и не заменяет null нулями.
    """
    nulls = find_null_quantities(df)
    technical = find_technical_sku_issues(df)

    return {
        "Строк": len(df),
        "Пустой SKU": len(find_missing_sku(df)),
        "Пустой срок годности": len(find_missing_expiry_date(df)),
        "Неизвестная категория": len(find_unknown_categories(df)),
        "Нечисловые количества": len(find_non_numeric_quantities(df)),
        "Отрицательные количества": len(find_negative_quantities(df)),
        "Null в остатке": len(nulls["Остаток"]),
        "Null в резерве": len(nulls["Зарезервировано"]),
        "Null в свободном остатке": len(nulls["Свободный остаток"]),
        "Нарушение баланса количеств": len(find_quantity_balance_issues(df)),
        "Строки-дубликаты предполагаемого ключа": len(find_duplicate_key_rows(df)),
        "Настоящий fallback 730": len(find_fallback_shelf_life_rows(df)),
        "Не нормализованный SKU": len(find_unresolved_sku(df)),
        "Техническая * после нормализации": len(technical["leading_star"]),
        "Крайние пробелы после нормализации": len(technical["edge_spaces"]),
        "Повторные пробелы после нормализации": len(technical["repeated_spaces"]),
    }
