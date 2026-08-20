import unittest
from datetime import date

import pandas as pd

from src.osg.calculator import (
    calculate_osg,
    get_nenni_shelf_life_days,
    get_shelf_life,
    get_shelf_life_rule,
)
from src.osg.transformer import transform_category


class ShelfLifeTests(unittest.TestCase):
    def test_category_shelf_life_rules(self):
        cases = {
            "ПЕЧЕНЬЕ": 365,
            "БИБИКАША": 456,
            "ПЮРЕ МОЛОЧНОЕ": 547,
            "МЯСНЫЕ КОНСЕРВЫ": 730,
            "АМАЛТЕЯ": 1080,
            "ПЮРЕ ТВОРОЖНОЕ": 730,
            "ПЮРЕ РЫБНЫЕ консервы": 730,
        }

        for category, expected_days in cases.items():
            with self.subTest(category=category):
                row = pd.Series({"Категория": category, "SKU": "Тест"})
                self.assertEqual(get_shelf_life(row), expected_days)

    def test_cottage_puree_source_variants_normalize_to_confirmed_730(self):
        source = pd.DataFrame({
            "Категория_исходная": ["ТВОРОЖНОЕ ПЮРЕ", "ПЮРЕ ТВОРОЖНОЕ"],
            "SKU": ["Пюре творожное 80 г.", "Пюре творожное 80 г."],
            "Вес": [80, 80],
        })

        normalized = transform_category(source)
        rules = normalized.apply(get_shelf_life_rule, axis=1).tolist()

        self.assertEqual(
            normalized["Категория"].tolist(),
            ["ПЮРЕ ТВОРОЖНОЕ", "ПЮРЕ ТВОРОЖНОЕ"],
        )
        self.assertEqual(rules, [
            ("Категория: ПЮРЕ ТВОРОЖНОЕ", 730),
            ("Категория: ПЮРЕ ТВОРОЖНОЕ", 730),
        ])

    def test_nenni_shelf_life_rules(self):
        cases = {
            "НЭННИ Классика 400 гр.": 912,
            "НЭННИ Классика 800 гр.": 912,
            "НЭННИ .3 с пребиотиками 400 г.": 912,
            "НЭННИ .3 с пребиотиками 800 г.": 912,
            "НЭННИ 1 400 г.": 912,
            "НЭННИ 1 800 г.": 912,
            "НЭННИ 2 400 г.": 912,
            "НЭННИ 2 800 г.": 912,
            "НЭННИ 3 400 г.": 912,
            "НЭННИ 3 800 г.": 912,
            "НЭННИ 4 400 гр.": 730,
            "НЭННИ 4 800 гр.": 730,
        }

        for sku, expected_days in cases.items():
            with self.subTest(sku=sku):
                self.assertEqual(
                    get_nenni_shelf_life_days(sku),
                    expected_days,
                )

    def test_unknown_product_uses_existing_fallback_730(self):
        row = pd.Series({
            "Категория": "НЕИЗВЕСТНАЯ КАТЕГОРИЯ",
            "SKU": "Неизвестный товар",
        })

        rule, days = get_shelf_life_rule(row)

        self.assertEqual(rule, "Fallback 730")
        self.assertEqual(days, 730)

    def test_confirmed_730_rules_are_not_reported_as_fallback(self):
        cases = [
            ("ПЮРЕ ТВОРОЖНОЕ", "Пюре творожное"),
            ("ПЮРЕ РЫБНЫЕ консервы", "Пюре 80 г. Треска"),
            ("ПЮРЕ МЯСНЫЕ консервы", "Пюре 80 г. Говядина"),
            ("НЭННИ 400", "НЭННИ 4 400 г."),
            ("НЭННИ 800", "НЭННИ 4 800 г."),
        ]

        for category, sku in cases:
            with self.subTest(category=category, sku=sku):
                rule, days = get_shelf_life_rule(pd.Series({
                    "Категория": category,
                    "SKU": sku,
                }))
                self.assertEqual(days, 730)
                self.assertNotEqual(rule, "Fallback 730")

    def test_confirmed_nenni_3_rules_use_912(self):
        for sku in ["НЭННИ 3 400 г.", "НЭННИ 3 800 г."]:
            with self.subTest(sku=sku):
                rule, days = get_shelf_life_rule(pd.Series({
                    "Категория": "НЭННИ",
                    "SKU": sku,
                }))
                self.assertEqual(rule, "НЭННИ по SKU")
                self.assertEqual(days, 912)

    def test_unknown_nenni_uses_existing_fallback_730(self):
        row = pd.Series({
            "Категория": "НЭННИ 800",
            "SKU": "НЭННИ 5 800 г.",
        })

        rule, days = get_shelf_life_rule(row)

        self.assertEqual(rule, "Fallback 730")
        self.assertEqual(days, 730)


class CalculateOsgTests(unittest.TestCase):
    def test_fixed_calculation_date_controls_days_left_and_osg(self):
        df = pd.DataFrame({
            "Категория": ["ПЕЧЕНЬЕ"],
            "SKU": ["Печенье 100 г."],
            "Срок годности": [pd.Timestamp("2027-05-22")],
        })

        result = calculate_osg(
            df,
            calculation_date=date(2026, 5, 22),
        )

        self.assertEqual(result.loc[0, "days_left"], 365)
        self.assertEqual(result.loc[0, "total_days"], 365)
        self.assertAlmostEqual(result.loc[0, "ОСГ %"], 100.0)

    def test_boundary_and_expired_values_are_not_clipped(self):
        calculation_date = date(2026, 5, 22)
        df = pd.DataFrame({
            "Категория": ["ПЕЧЕНЬЕ"] * 4,
            "SKU": ["Печенье"] * 4,
            "Срок годности": [
                pd.Timestamp("2027-02-20"),  # 274 / 365 = 75.068...
                pd.Timestamp("2026-05-22"),  # 0%
                pd.Timestamp("2026-05-21"),  # отрицательный ОСГ
                pd.Timestamp("2027-05-23"),  # больше 100%
            ],
        })

        result = calculate_osg(df, calculation_date=calculation_date)

        self.assertEqual(result["days_left"].tolist(), [274, 0, -1, 366])
        self.assertAlmostEqual(result.loc[0, "ОСГ %"], 274 / 365 * 100)
        self.assertEqual(result.loc[1, "ОСГ %"], 0)
        self.assertLess(result.loc[2, "ОСГ %"], 0)
        self.assertGreater(result.loc[3, "ОСГ %"], 100)

    def test_calculation_uses_calendar_date_not_time_of_day(self):
        df = pd.DataFrame({
            "Категория": ["ПЕЧЕНЬЕ"],
            "SKU": ["Печенье"],
            "Срок годности": [pd.Timestamp("2027-05-22")],
        })

        morning = calculate_osg(
            df.copy(),
            calculation_date=pd.Timestamp("2026-05-22 08:00:00"),
        )
        evening = calculate_osg(
            df.copy(),
            calculation_date=pd.Timestamp("2026-05-22 23:59:59"),
        )

        self.assertEqual(morning.loc[0, "days_left"], evening.loc[0, "days_left"])
        self.assertEqual(morning.loc[0, "ОСГ %"], evening.loc[0, "ОСГ %"])


if __name__ == "__main__":
    unittest.main()
