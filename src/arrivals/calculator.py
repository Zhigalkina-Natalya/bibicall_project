import math

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


def make_container_comparison(
        df: pd.DataFrame,
        value_column: str,
        year: int,
        today: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """
    Формирует сверку плана Дениэла и факта 1С по контейнерам.

    Нумерованные контейнеры сравниваются после агрегации по SKU. Строки плана
    без номера контейнера не группируются и сохраняют исходную детализацию.
    """
    today = (
        pd.Timestamp.today().normalize()
        if today is None
        else pd.Timestamp(today).normalize()
    )

    compare_df = df[
        (df["Год"].astype("Int64") == year)
        & (df["Источник"].isin(["Факт 1С", "План Дениэл"]))
    ].copy()

    if compare_df.empty:
        return pd.DataFrame()

    compare_df["Контейнер"] = compare_df["Контейнер"].apply(normalize_container)
    compare_df["SKU"] = compare_df["SKU"].fillna("").astype(str)

    plan_df = compare_df[compare_df["Источник"] == "План Дениэл"].copy()
    fact_df = compare_df[compare_df["Источник"] == "Факт 1С"].copy()

    plan_numbered = plan_df[plan_df["Контейнер"] != ""]
    fact_numbered = fact_df[fact_df["Контейнер"] != ""]

    plan_containers = set(plan_numbered["Контейнер"])
    fact_containers = set(fact_numbered["Контейнер"])
    all_containers = sorted(
        plan_containers.union(fact_containers),
        key=lambda value: (
            (0, int(value))
            if value.isdigit()
            else (1, value)
        ),
    )

    plan_column = f"План, {value_column}"
    fact_column = f"Факт, {value_column}"
    difference_column = f"Разница, {value_column}"
    rows = []

    for container in all_containers:
        plan_part = plan_numbered[plan_numbered["Контейнер"] == container]
        fact_part = fact_numbered[fact_numbered["Контейнер"] == container]

        plan_by_sku = plan_part.groupby("SKU", dropna=False)[value_column].sum()
        fact_by_sku = fact_part.groupby("SKU", dropna=False)[value_column].sum()
        plan_sku = set(plan_by_sku.index.astype(str))
        fact_sku = set(fact_by_sku.index.astype(str))

        if not plan_part.empty and not fact_part.empty:
            assortment_changed = plan_sku != fact_sku
            common_sku = plan_sku.intersection(fact_sku)
            common_quantity_changed = any(
                not math.isclose(
                    plan_by_sku.loc[sku],
                    fact_by_sku.loc[sku],
                    rel_tol=1e-9,
                    abs_tol=1e-9,
                )
                for sku in common_sku
            )
            total_quantity_changed = not math.isclose(
                plan_part[value_column].sum(),
                fact_part[value_column].sum(),
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
            quantity_changed = common_quantity_changed or total_quantity_changed

            if assortment_changed and quantity_changed:
                status = "⚠️ Изменён ассортимент и количество"
            elif assortment_changed:
                status = "⚠️ Изменён ассортимент"
            elif quantity_changed:
                status = "⚠️ Изменено количество"
            else:
                status = "✅ Совпадает с планом"
        elif not plan_part.empty:
            expected_date = plan_part["Дата начала недели"].max()
            status = (
                "🔴 Плановая дата прошла, факта нет"
                if pd.notna(expected_date) and expected_date < today
                else "🟡 Ожидается приход"
            )
        else:
            status = "🔵 Факт без плана Daniel"

        plan_value = plan_part[value_column].sum()
        fact_value = fact_part[value_column].sum()
        rows.append({
            "Контейнер": container,
            "Дата ожидаемого прихода": plan_part["Дата начала недели"].max(),
            "Статус": status,
            "План SKU": ", ".join(sorted(plan_sku)),
            "Факт SKU": ", ".join(sorted(fact_sku)),
            plan_column: plan_value,
            fact_column: fact_value,
            difference_column: fact_value - plan_value,
        })

    unassigned_plan = plan_df[plan_df["Контейнер"] == ""].sort_values(
        ["Дата начала недели", "SKU"],
        na_position="last",
    )

    for _, plan_row in unassigned_plan.iterrows():
        plan_value = plan_row[value_column]
        rows.append({
            "Контейнер": "",
            "Дата ожидаемого прихода": plan_row["Дата начала недели"],
            "Статус": "⚪ Контейнер не назначен",
            "План SKU": str(plan_row["SKU"]),
            "Факт SKU": "",
            plan_column: plan_value,
            fact_column: 0,
            difference_column: -plan_value,
        })

    return pd.DataFrame(rows)


def add_annual_total_rows(
        table: pd.DataFrame,
        value_columns: list[str],
) -> pd.DataFrame:
    """Добавляет строку ``YYYY ИТОГО`` после каждого года в таблице."""
    if table.empty:
        return table.copy()

    yearly_tables = []

    for year in sorted(table["Год"].astype(int).unique()):
        year_rows = table[table["Год"] == str(year)]
        total_row = {
            "Год": f"{year} ИТОГО",
            "Квартал": "ИТОГ",
            "Месяц": "",
            "№ недели": "",
            "№ конт": "",
            "Статус": "",
        }

        for column in value_columns:
            total_row[column] = year_rows[column].sum()

        yearly_tables.extend([year_rows, pd.DataFrame([total_row])])

    return pd.concat(yearly_tables, ignore_index=True)


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
