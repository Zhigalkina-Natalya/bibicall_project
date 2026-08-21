import ast
from pathlib import Path
import unittest

import pandas as pd

from src.arrivals.calculator import (
    add_annual_total_rows,
    make_container_comparison,
)


class ContainerComparisonTests(unittest.TestCase):
    @staticmethod
    def _row(
            source: str,
            container: str,
            sku: str,
            quantity: float,
            date: str,
    ) -> dict:
        return {
            "Год": 2026,
            "Источник": source,
            "Контейнер": container,
            "SKU": sku,
            "Количество, шт": quantity,
            "Дата начала недели": pd.Timestamp(date),
        }

    def setUp(self):
        rows = [
            self._row("План Дениэл", "1001", "SKU A", 10, "2026-08-10"),
            self._row("Факт 1С", "1001", "SKU A", 10, "2026-08-10"),
            self._row("План Дениэл", "1002", "SKU A", 10, "2026-08-10"),
            self._row("Факт 1С", "1002", "SKU B", 10, "2026-08-10"),
            self._row("План Дениэл", "1003", "SKU A", 10, "2026-08-10"),
            self._row("Факт 1С", "1003", "SKU A", 12, "2026-08-10"),
            self._row("План Дениэл", "1004", "SKU A", 10, "2026-08-10"),
            self._row("Факт 1С", "1004", "SKU A", 12, "2026-08-10"),
            self._row("Факт 1С", "1004", "SKU B", 3, "2026-08-10"),
            self._row("Факт 1С", "1005", "SKU A", 10, "2026-08-10"),
            self._row("План Дениэл", "1006", "SKU A", 10, "2026-09-10"),
            self._row("План Дениэл", "1007", "SKU A", 10, "2026-07-10"),
            self._row("План Дениэл", "", "SKU A", 5, "2026-10-10"),
            self._row("План Дениэл", "", "SKU B", 7, "2026-11-10"),
        ]
        self.result = make_container_comparison(
            pd.DataFrame(rows),
            value_column="Количество, шт",
            year=2026,
            today=pd.Timestamp("2026-08-21"),
        )

    def _status(self, container: str) -> str:
        return self.result.loc[
            self.result["Контейнер"] == container,
            "Статус",
        ].iloc[0]

    def test_exact_match(self):
        self.assertEqual(self._status("1001"), "✅ Совпадает с планом")

    def test_assortment_changed(self):
        self.assertEqual(self._status("1002"), "⚠️ Изменён ассортимент")

    def test_quantity_changed(self):
        self.assertEqual(self._status("1003"), "⚠️ Изменено количество")

    def test_assortment_and_quantity_changed(self):
        self.assertEqual(
            self._status("1004"),
            "⚠️ Изменён ассортимент и количество",
        )

    def test_fact_without_daniel(self):
        self.assertEqual(self._status("1005"), "🔵 Факт без плана Daniel")

    def test_future_numbered_container(self):
        self.assertEqual(self._status("1006"), "🟡 Ожидается приход")

    def test_past_due_numbered_container(self):
        self.assertEqual(
            self._status("1007"),
            "🔴 Плановая дата прошла, факта нет",
        )

    def test_unassigned_rows_are_preserved_separately(self):
        unassigned = self.result[
            self.result["Статус"] == "⚪ Контейнер не назначен"
        ]

        self.assertEqual(len(unassigned), 2)
        self.assertEqual(unassigned["План SKU"].tolist(), ["SKU A", "SKU B"])
        self.assertEqual(unassigned["План, Количество, шт"].sum(), 12)


class FinanceAnnualTotalsTests(unittest.TestCase):
    def test_total_is_added_after_every_year(self):
        table = pd.DataFrame({
            "Год": ["2026", "2026", "2027"],
            "Квартал": [1, 2, 1],
            "Месяц": [1, 4, 1],
            "№ недели": [2, 15, 1],
            "№ конт": ["1201", "1202", "1301"],
            "Статус": ["✅ Факт", "🟡 План", "🟡 План"],
            "N18": [10, 20, 40],
        })

        result = add_annual_total_rows(table, value_columns=["N18"])

        self.assertEqual(
            result["Год"].tolist(),
            ["2026", "2026", "2026 ИТОГО", "2027", "2027 ИТОГО"],
        )
        totals = result[result["Год"].str.endswith("ИТОГО")].set_index("Год")
        self.assertEqual(totals.loc["2026 ИТОГО", "N18"], 30)
        self.assertEqual(totals.loc["2027 ИТОГО", "N18"], 40)


class ArrivalsTablePresentationTests(unittest.TestCase):
    def test_all_active_streamlit_dataframes_hide_index(self):
        page_file = Path(__file__).parents[1] / "src" / "arrivals" / "page.py"
        tree = ast.parse(page_file.read_text(encoding="utf-8"))
        dataframe_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "st"
            and node.func.attr == "dataframe"
        ]

        self.assertEqual(len(dataframe_calls), 4)

        for call in dataframe_calls:
            hide_index = next(
                (keyword.value for keyword in call.keywords if keyword.arg == "hide_index"),
                None,
            )
            self.assertIsInstance(hide_index, ast.Constant)
            self.assertIs(hide_index.value, True)


if __name__ == "__main__":
    unittest.main()
