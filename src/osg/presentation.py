import pandas as pd


def _sort_with_expiry(
        df: pd.DataFrame,
        leading_columns: list[str],
) -> pd.DataFrame:
    result = df.copy()
    result["_expiry_sort"] = pd.to_datetime(
        result["Срок годности"],
        format="%d.%m.%Y",
        errors="coerce",
    )
    return (
        result
        .sort_values(
            [*leading_columns, "_expiry_sort"],
            ascending=True,
            kind="stable",
            na_position="last",
        )
        .drop(columns="_expiry_sort")
    )


def sort_small_stock_view(df: pd.DataFrame) -> pd.DataFrame:
    """Sorts small stock for display by SKU, warehouse and expiry date."""
    return _sort_with_expiry(df, ["SKU", "Склад"])


def sort_full_stock_view(df: pd.DataFrame) -> pd.DataFrame:
    """Sorts full stock for display by category, SKU, warehouse and expiry."""
    return _sort_with_expiry(df, ["Категория", "SKU", "Склад"])
