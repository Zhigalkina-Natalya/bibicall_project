import unittest

import pandas as pd

from src.osg.presentation import sort_full_stock_view, sort_small_stock_view


class OsgPresentationSortingTests(unittest.TestCase):
    def test_small_stock_sorts_by_sku_warehouse_and_expiry(self):
        df = pd.DataFrame({
            "SKU": ["Яблоко", "Абрикос", "Абрикос", "Абрикос"],
            "Склад": ["А", "Б", "А", "А"],
            "Срок годности": [
                "01.01.2027", "01.01.2027", "01.02.2027", "01.01.2027",
            ],
        })

        result = sort_small_stock_view(df)

        self.assertEqual(result["SKU"].tolist(), [
            "Абрикос", "Абрикос", "Абрикос", "Яблоко",
        ])
        self.assertEqual(result["Склад"].tolist()[:3], ["А", "А", "Б"])
        self.assertEqual(
            result["Срок годности"].tolist()[:2],
            ["01.01.2027", "01.02.2027"],
        )

    def test_full_stock_sorts_by_category_first(self):
        df = pd.DataFrame({
            "Категория": ["Ягоды", "Каши", "Каши"],
            "SKU": ["А", "Я", "А"],
            "Склад": ["А", "А", "Б"],
            "Срок годности": ["01.01.2027", "01.01.2027", "01.01.2027"],
        })

        result = sort_full_stock_view(df)

        self.assertEqual(result["Категория"].tolist(), ["Каши", "Каши", "Ягоды"])
        self.assertEqual(result["SKU"].tolist(), ["А", "Я", "А"])


if __name__ == "__main__":
    unittest.main()
