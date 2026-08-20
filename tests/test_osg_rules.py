import unittest

import pandas as pd

from src.osg.rules import (
    RISK_LEVELS,
    build_urgent_sales,
    count_attention_groups,
    filter_analytical_stock,
    get_risk_level,
    split_stock_views,
    validate_and_split_stock,
)


class RiskLevelTests(unittest.TestCase):
    def test_existing_risk_boundaries(self):
        cases = [
            (75, "Свежий 🟢"),
            (74.99, "Хороший 🟢"),
            (70, "Хороший 🟢"),
            (69.99, "Норма 🟡"),
            (66, "Норма 🟡"),
            (65.99, "Внимание 🟡"),
            (60, "Внимание 🟡"),
            (59.99, "Пограничный 🟠"),
            (50, "Пограничный 🟠"),
            (49.99, "Горящий 🔴"),
            (40, "Горящий 🔴"),
            (39.99, "Критично 🔴"),
            (20, "Критично 🔴"),
            (19.99, "Списание ⚫"),
            (float("nan"), "Ошибка"),
        ]

        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(get_risk_level(value), expected)

    def test_attention_kpi_boundaries(self):
        df = pd.DataFrame({"ОСГ %": [59.99, 60.0, 65.99, 66.0]})

        self.assertEqual(count_attention_groups(df), 2)

    def test_error_is_one_internal_status_and_is_available_to_filter(self):
        error_status = get_risk_level(float("nan"))

        self.assertEqual(error_status, "Ошибка")
        self.assertIn(error_status, RISK_LEVELS)
        self.assertNotIn("Ошибка 🚨", RISK_LEVELS)

    def test_main_stock_filter_uses_total_stock_above_100(self):
        df = pd.DataFrame({
            "Остаток": [99, 100, 101],
            "Свободный остаток": [1000, 0, 1],
        })

        result = filter_analytical_stock(df)

        self.assertEqual(result["Остаток"].tolist(), [101])
        self.assertEqual(result["Свободный остаток"].tolist(), [1])

    def test_stock_views_cover_all_rows_without_overlap(self):
        df = pd.DataFrame({"Остаток": [0, 99, 100, 101]})

        main_stock, small_stock = split_stock_views(df)

        self.assertEqual(small_stock["Остаток"].tolist(), [0, 99, 100])
        self.assertEqual(main_stock["Остаток"].tolist(), [101])
        self.assertEqual(len(main_stock) + len(small_stock), len(df))
        self.assertEqual(
            set(main_stock.index).intersection(small_stock.index),
            set(),
        )

    def test_validation_runs_on_full_data_before_split(self):
        df = pd.DataFrame({"Остаток": [100, 101]})
        validated_lengths = []

        def validation_spy(data):
            validated_lengths.append(len(data))
            return ["diagnostic"]

        errors, main_stock, small_stock = validate_and_split_stock(
            df,
            validation_spy,
        )

        self.assertEqual(validated_lengths, [2])
        self.assertEqual(errors, ["diagnostic"])
        self.assertEqual(main_stock["Остаток"].tolist(), [101])
        self.assertEqual(small_stock["Остаток"].tolist(), [100])


class UrgentSalesTests(unittest.TestCase):
    @staticmethod
    def _row(sku, stock, reserved, free, osg, expiry="2027-01-01"):
        return {
            "Категория": "Тест",
            "SKU": sku,
            "Срок годности": expiry,
            "Остаток": stock,
            "Зарезервировано": reserved,
            "Свободный остаток": free,
            "ОСГ %": osg,
        }

    def test_filters_free_stock_and_osg_after_grouping(self):
        df = pd.DataFrame([
            self._row("free_zero", 101, 101, 0, 59),
            self._row("free_one", 101, 100, 1, 59),
            self._row("osg_60", 101, 0, 101, 60),
            self._row("osg_below_60", 101, 0, 101, 59.999),
        ])

        result = build_urgent_sales(df)

        self.assertEqual(set(result["SKU"]), {"free_one", "osg_below_60"})

    def test_aggregates_technical_rows_before_filtering(self):
        df = pd.DataFrame([
            self._row("multi", 101, 101, 0, 58),
            self._row("multi", 102, 101, 1, 57),
        ])

        result = build_urgent_sales(df)

        self.assertEqual(len(result), 1)
        row = result.iloc[0]
        self.assertEqual(row["Остаток"], 203)
        self.assertEqual(row["Зарезервировано"], 202)
        self.assertEqual(row["Свободный остаток"], 1)
        self.assertEqual(row["ОСГ %"], 57)
        self.assertAlmostEqual(row["Доля резерва, %"], 202 / 203 * 100)

    def test_reserve_share_is_safe_for_zero_stock(self):
        df = pd.DataFrame([
            self._row("zero_stock", 0, 0, 1, 50),
        ])

        result = build_urgent_sales(df)

        self.assertEqual(len(result), 1)
        self.assertTrue(pd.isna(result.iloc[0]["Доля резерва, %"]))


if __name__ == "__main__":
    unittest.main()
