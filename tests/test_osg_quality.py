import unittest

import pandas as pd

from src.osg.quality import (
    build_sku_normalization_table,
    find_duplicate_key_rows,
    find_missing_expiry_date,
    find_missing_sku,
    find_negative_quantities,
    find_non_numeric_quantities,
    find_null_quantities,
    find_quantity_balance_issues,
    find_sku_name_collisions,
    find_technical_sku_issues,
    find_unknown_categories,
    find_unresolved_sku,
    run_quality_diagnostics,
)


class QualityDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({
            "Склад": ["A", "A", "A", "A"],
            "SKU_исходный": ["Товар 1", "* Товар 1", "Товар 3", "Товар 4"],
            "SKU": ["Товар 1", "Товар 1", None, "  Товар  4"],
            "Контейнер": ["1", "1", "2", "3"],
            "Срок годности": [
                pd.Timestamp("2027-01-01"),
                pd.Timestamp("2027-01-01"),
                pd.NaT,
                pd.Timestamp("2027-01-01"),
            ],
            "Остаток": [100, 50, -1, "ошибка"],
            "Зарезервировано": [10, None, 0, 1],
            "Свободный остаток": [90, 50, -1, 2],
            "Категория": ["НЭННИ 800", "НЭННИ 800", "Не определено", "Печенье"],
        })

    def test_quantity_and_required_field_diagnostics(self):
        self.assertEqual(len(find_missing_sku(self.df)), 1)
        self.assertEqual(len(find_missing_expiry_date(self.df)), 1)
        self.assertEqual(len(find_unknown_categories(self.df)), 1)
        self.assertEqual(len(find_non_numeric_quantities(self.df)), 1)
        self.assertEqual(len(find_negative_quantities(self.df)), 1)

        nulls = find_null_quantities(self.df)
        self.assertEqual(len(nulls["Зарезервировано"]), 1)
        self.assertEqual(len(nulls["Свободный остаток"]), 0)

    def test_balance_only_checks_complete_numeric_rows(self):
        result = find_quantity_balance_issues(self.df)

        self.assertEqual(len(result), 0)

        changed = self.df.copy()
        changed.loc[0, "Свободный остаток"] = 89
        self.assertEqual(len(find_quantity_balance_issues(changed)), 1)

    def test_duplicate_key_is_diagnostic_only(self):
        result = find_duplicate_key_rows(self.df)

        self.assertEqual(len(result), 2)
        self.assertEqual(len(self.df), 4)

    def test_sku_diagnostics(self):
        issues = find_technical_sku_issues(self.df)

        self.assertEqual(len(issues["leading_star"]), 0)
        self.assertEqual(len(issues["edge_spaces"]), 1)
        self.assertEqual(len(issues["repeated_spaces"]), 1)
        self.assertEqual(len(find_unresolved_sku(self.df)), 1)

        mapping = build_sku_normalization_table(self.df)
        self.assertEqual(len(mapping), 4)
        self.assertEqual(len(find_sku_name_collisions(self.df)), 2)

    def test_full_quality_summary_does_not_change_data(self):
        before = self.df.copy(deep=True)

        summary = run_quality_diagnostics(self.df)

        self.assertEqual(summary["Строк"], 4)
        self.assertEqual(summary["Пустой SKU"], 1)
        self.assertEqual(summary["Null в резерве"], 1)
        self.assertEqual(summary["Настоящий fallback 730"], 3)
        pd.testing.assert_frame_equal(self.df, before)


if __name__ == "__main__":
    unittest.main()
