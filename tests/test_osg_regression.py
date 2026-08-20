import hashlib
import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from src.loader import load_latest_file
from src.osg.calculator import calculate_osg
from src.osg.quality import (
    QUANTITY_COLUMNS,
    find_duplicate_key_rows,
    find_fallback_shelf_life_rows,
    find_missing_expiry_date,
    find_missing_sku,
    find_negative_quantities,
    find_non_numeric_quantities,
    find_null_quantities,
    find_quantity_balance_issues,
    find_unknown_categories,
    find_technical_sku_issues,
)
from src.osg.rules import (
    build_urgent_sales,
    filter_analytical_stock,
    get_risk_level,
    split_stock_views,
)
from src.osg.transformer import (
    clean_columns,
    convert_dates,
    extract_weight,
    normalize_data_types,
    normalize_sku,
    remove_service_rows,
    rename_columns,
    transform_category,
)


PROJECT_DIR = Path(__file__).resolve().parents[1]
BASELINE_FILE = PROJECT_DIR / "data" / "raw" / "osg_2026_05_22.xlsx"
CURRENT_TECHNICAL_SKU_FILE = (
    PROJECT_DIR / "data" / "raw" / "osg_2026_08_20.xlsx"
)
REGRESSION_CALCULATION_DATE = date(2026, 5, 22)


def prepare_osg_data(path: Path, calculation_date) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_excel(path, header=7, engine="openpyxl")
    df = clean_columns(raw.copy())
    df = rename_columns(df)
    df = normalize_sku(df)
    df = normalize_data_types(df)
    df = remove_service_rows(df)
    df = convert_dates(df)
    df = extract_weight(df)
    df = transform_category(df)
    df = calculate_osg(df, calculation_date=calculation_date)
    df["Риск"] = df["ОСГ %"].apply(get_risk_level)
    return raw, df


def grouped_digest(df: pd.DataFrame, keys: list[str]) -> str:
    grouped = (
        df.groupby(keys, dropna=False)[QUANTITY_COLUMNS]
        .sum()
        .reset_index()
        .sort_values(keys)
    )

    records = []
    for row in grouped.to_dict("records"):
        record = {}
        for key, value in row.items():
            if isinstance(value, pd.Timestamp):
                value = value.strftime("%Y-%m-%d")
            elif isinstance(value, float) and value.is_integer():
                value = int(value)
            record[key] = value
        records.append(record)

    payload = json.dumps(
        records,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class LegacyExcelRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not BASELINE_FILE.exists():
            raise FileNotFoundError(
                f"Не найден локальный regression-файл: {BASELINE_FILE}"
            )

        cls.raw, cls.df = prepare_osg_data(
            BASELINE_FILE,
            REGRESSION_CALCULATION_DATE,
        )

    def test_loader_reads_139_rows_from_isolated_baseline_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            copied_file = Path(temp_dir) / BASELINE_FILE.name
            shutil.copy2(BASELINE_FILE, copied_file)
            temporary_excel_file = Path(temp_dir) / f"~${BASELINE_FILE.name}"
            temporary_excel_file.touch()
            loaded = load_latest_file(Path(temp_dir))

        self.assertEqual(len(loaded), 139)

    def test_baseline_dimensions_after_normalization(self):
        self.assertEqual(len(self.raw), 139)
        self.assertEqual(len(self.df), 137)
        self.assertEqual(self.df["SKU_исходный"].nunique(), 45)
        self.assertEqual(self.df["SKU"].nunique(), 45)
        self.assertEqual(self.df["Склад"].nunique(), 4)
        self.assertEqual(self.df["Контейнер"].nunique(), 48)
        self.assertEqual(self.df["Категория"].nunique(), 11)

    def test_normalization_preserves_rows_parties_and_quantity_totals(self):
        before = rename_columns(clean_columns(self.raw.copy()))
        before = remove_service_rows(before)
        after = self.df

        self.assertEqual(len(before), len(after))
        self.assertEqual(
            before["Срок годности"].astype(str).tolist(),
            after["Срок годности_исходная"].astype(str).tolist(),
        )
        self.assertEqual(
            before["Контейнер"].astype(str).str.strip().tolist(),
            after["Контейнер"].tolist(),
        )

        for column in QUANTITY_COLUMNS:
            with self.subTest(column=column):
                self.assertEqual(
                    float(pd.to_numeric(before[column], errors="coerce").sum()),
                    float(after[column].sum()),
                )

    def test_quantity_baseline(self):
        self.assertEqual(float(self.df["Остаток"].sum()), 584272.0)
        self.assertEqual(float(self.df["Зарезервировано"].sum()), 28449.0)
        self.assertEqual(float(self.df["Свободный остаток"].sum()), 555823.0)

    def test_all_warehouse_category_and_sku_aggregates(self):
        self.assertEqual(
            grouped_digest(self.df, ["Склад"]),
            "6372fc9719ecda6b7cbdf0c849cb5ad3d6c608e6ffd00861a0df74079d667565",
        )
        self.assertEqual(
            grouped_digest(self.df, ["Категория"]),
            "c7c061a31b7db764e4f1b6d52902a3d7d411c84184a5c7233a7334c5f4dd5dcd",
        )
        self.assertEqual(
            grouped_digest(self.df, ["SKU"]),
            "d0222197ec573c953f912b6e8a640cbf5cab4938b7cfc0b4483117bcd4cb7f4b",
        )

    def test_date_dependent_baseline(self):
        self.assertEqual(int(self.df["days_left"].min()), 69)
        self.assertEqual(int(self.df["days_left"].max()), 789)
        self.assertEqual(int(self.df["days_left"].sum()), 67940)
        self.assertAlmostEqual(
            float(self.df["ОСГ %"].sum()),
            9733.305257795331,
        )
        self.assertEqual(self.df["Риск"].value_counts().to_dict(), {
            "Свежий 🟢": 71,
            "Хороший 🟢": 20,
            "Внимание 🟡": 16,
            "Пограничный 🟠": 9,
            "Горящий 🔴": 7,
            "Критично 🔴": 7,
            "Норма 🟡": 5,
            "Списание ⚫": 2,
        })

    def test_existing_stock_filter_and_group_kpi_baseline(self):
        filtered = filter_analytical_stock(self.df)
        self.assertEqual(len(filtered), 107)
        self.assertEqual(len(self.df) - len(filtered), 30)

        grouped = filtered.groupby(
            ["Категория", "SKU", "Срок годности"],
            as_index=False,
        ).agg({
            "Остаток": "sum",
            "Зарезервировано": "sum",
            "Свободный остаток": "sum",
            "ОСГ %": "min",
        })
        grouped["Риск"] = grouped["ОСГ %"].apply(get_risk_level)

        self.assertEqual(len(grouped), 84)
        self.assertEqual(
            grouped["Риск"].value_counts().to_dict(),
            {
                "Свежий 🟢": 55,
                "Хороший 🟢": 13,
                "Внимание 🟡": 7,
                "Горящий 🔴": 3,
                "Норма 🟡": 3,
                "Пограничный 🟠": 2,
                "Критично 🔴": 1,
            },
        )
        self.assertEqual(int((grouped["ОСГ %"] < 50).sum()), 4)
        self.assertEqual(
            int(((grouped["ОСГ %"] >= 50) & (grouped["ОСГ %"] < 60)).sum()),
            2,
        )
        self.assertAlmostEqual(float(grouped["ОСГ %"].mean()), 77.21150631011218)
        self.assertEqual(float(grouped["Свободный остаток"].sum()), 554996.0)

    def test_control_sku_container_and_expiry_rows(self):
        controls = [
            ("НЭННИ 1 800 г.", "1226", "2028-06-15", 4668.0, 912),
            ("НЭННИ 2 800 г.", "1216", "2028-04-15", 996.0, 912),
            ("НЭННИ Классика 400 гр.", "1215", "2028-04-01", 720.0, 912),
            ("Флоупак печенье Грушевое, 1 шт.", "9", "2027-04-17", 15556.0, 365),
            ("Шоубокс печенье Грушевое, 1 шт.", "3", "2027-05-15", 10200.0, 365),
            ("Печенье Тыква, 150 г.", "4", "2027-02-04", 886.0, 365),
        ]

        for sku, container, expiry, stock, total_days in controls:
            with self.subTest(sku=sku, container=container, expiry=expiry):
                rows = self.df[
                    (self.df["SKU"] == sku)
                    & (self.df["Контейнер"] == container)
                    & (self.df["Срок годности"] == pd.Timestamp(expiry))
                ]
                self.assertEqual(len(rows), 1)
                self.assertEqual(float(rows.iloc[0]["Остаток"]), stock)
                self.assertEqual(int(rows.iloc[0]["total_days"]), total_days)

    def test_zk_nenni_is_normalized_and_uses_confirmed_912_days(self):
        rows = self.df[
            self.df["SKU_исходный"].astype(str).str.contains("(ЗК)", regex=False)
        ]

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.iloc[0]["SKU"], "НЭННИ 3 800 г.")
        self.assertEqual(int(rows.iloc[0]["total_days"]), 912)
        self.assertEqual(len(find_fallback_shelf_life_rows(rows)), 0)

    def test_quality_baseline_before_and_after_stock_filter(self):
        full = self.df
        filtered = filter_analytical_stock(full)

        expected = {
            "full": {
                "missing_sku": 0,
                "missing_expiry": 0,
                "non_numeric": 0,
                "negative": 0,
                "unknown_category": 0,
                "null_total": 0,
                "null_reserved": 88,
                "null_free": 3,
                "balance": 0,
                "duplicates": 0,
                "fallback": 0,
            },
            "filtered": {
                "missing_sku": 0,
                "missing_expiry": 0,
                "non_numeric": 0,
                "negative": 0,
                "unknown_category": 0,
                "null_total": 0,
                "null_reserved": 60,
                "null_free": 2,
                "balance": 0,
                "duplicates": 0,
                "fallback": 0,
            },
        }

        for label, data in [("full", full), ("filtered", filtered)]:
            with self.subTest(dataset=label):
                nulls = find_null_quantities(data)
                actual = {
                    "missing_sku": len(find_missing_sku(data)),
                    "missing_expiry": len(find_missing_expiry_date(data)),
                    "non_numeric": len(find_non_numeric_quantities(data)),
                    "negative": len(find_negative_quantities(data)),
                    "unknown_category": len(find_unknown_categories(data)),
                    "null_total": len(nulls["Остаток"]),
                    "null_reserved": len(nulls["Зарезервировано"]),
                    "null_free": len(nulls["Свободный остаток"]),
                    "balance": len(find_quantity_balance_issues(data)),
                    "duplicates": len(find_duplicate_key_rows(data)),
                    "fallback": len(find_fallback_shelf_life_rows(data)),
                }
                self.assertEqual(actual, expected[label])


class CurrentTechnicalSkuRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CURRENT_TECHNICAL_SKU_FILE.exists():
            raise FileNotFoundError(
                "Не найден файл с подтверждёнными техническими SKU: "
                f"{CURRENT_TECHNICAL_SKU_FILE}"
            )

        cls.raw, cls.df = prepare_osg_data(
            CURRENT_TECHNICAL_SKU_FILE,
            date(2026, 8, 20),
        )

    def test_actual_technical_sku_variants_are_normalized(self):
        expected = {
            "* НЭННИ .3 с пребиотиками 800 г.": "НЭННИ .3 с пребиотиками 800 г.",
            "* НЭННИ 1 400 г.": "НЭННИ 1 400 г.",
            "* НЭННИ 1 800 г.": "НЭННИ 1 800 г.",
            "* НЭННИ 2 800 г": "НЭННИ 2 800 г.",
            "* НЭННИ  4 400 гр.": "НЭННИ 4 400 гр.",
        }

        for source_name, analytical_sku in expected.items():
            with self.subTest(source_name=source_name):
                rows = self.df[self.df["SKU_исходный"] == source_name]
                self.assertGreater(len(rows), 0)
                self.assertEqual(rows["SKU"].unique().tolist(), [analytical_sku])

    def test_detail_rows_and_quantities_are_preserved(self):
        cleaned = rename_columns(clean_columns(self.raw.copy()))
        cleaned = remove_service_rows(cleaned)

        self.assertEqual(len(cleaned), 149)
        self.assertEqual(len(self.df), 149)
        self.assertEqual(cleaned["Номенклатура"].nunique() if "Номенклатура" in cleaned else cleaned["SKU"].nunique(), 49)
        self.assertEqual(self.df["SKU"].nunique(), 44)

        for column in QUANTITY_COLUMNS:
            with self.subTest(column=column):
                self.assertEqual(
                    float(pd.to_numeric(cleaned[column], errors="coerce").sum()),
                    float(self.df[column].sum()),
                )

        issues = find_technical_sku_issues(self.df)
        self.assertEqual({key: len(value) for key, value in issues.items()}, {
            "leading_star": 0,
            "edge_spaces": 0,
            "repeated_spaces": 0,
        })

    def test_summary_has_no_separate_star_sku(self):
        summary = self.df.groupby("SKU", as_index=False).agg({
            "Остаток": "sum",
            "Зарезервировано": "sum",
            "Свободный остаток": "sum",
            "ОСГ %": "min",
        })

        self.assertFalse(summary["SKU"].str.startswith("*").any())
        self.assertEqual(len(summary), 44)

    def test_stock_split_preserves_rows_and_quantity_totals(self):
        main_stock, small_stock = split_stock_views(self.df)

        self.assertEqual(len(main_stock), 108)
        self.assertEqual(len(small_stock), 41)
        self.assertEqual(len(main_stock) + len(small_stock), len(self.df))

        expected_sums = {
            "Остаток": (559587.0, 1201.0, 560788.0),
            "Зарезервировано": (26881.0, 321.0, 27202.0),
            "Свободный остаток": (532706.0, 880.0, 533586.0),
        }
        for column, (main_sum, small_sum, full_sum) in expected_sums.items():
            with self.subTest(column=column):
                self.assertEqual(float(main_stock[column].sum()), main_sum)
                self.assertEqual(float(small_stock[column].sum()), small_sum)
                self.assertEqual(float(self.df[column].sum()), full_sum)
                self.assertEqual(main_sum + small_sum, full_sum)

    def test_current_urgent_sales_contains_rabbit_after_aggregation(self):
        main_stock = filter_analytical_stock(self.df)
        urgent_sales = build_urgent_sales(main_stock)

        self.assertEqual(len(urgent_sales), 4)
        self.assertEqual(urgent_sales["SKU"].nunique(), 4)
        self.assertEqual(set(urgent_sales["SKU"]), {
            "НЭННИ .3 с пребиотиками 400 г.",
            "НЭННИ Классика 800 гр.",
            "Пюре 80 г. Кролик в сливочном соусе",
            "Пюре 80 г. Печень в сливочном соусе",
        })

        rabbit = urgent_sales.loc[
            urgent_sales["SKU"] == "Пюре 80 г. Кролик в сливочном соусе"
        ].iloc[0]
        self.assertAlmostEqual(float(rabbit["ОСГ %"]), 50.95890410958904)
        self.assertEqual(float(rabbit["Остаток"]), 281.0)
        self.assertEqual(float(rabbit["Зарезервировано"]), 252.0)
        self.assertEqual(float(rabbit["Свободный остаток"]), 29.0)
        self.assertAlmostEqual(
            float(rabbit["Доля резерва, %"]),
            252 / 281 * 100,
        )


if __name__ == "__main__":
    unittest.main()
