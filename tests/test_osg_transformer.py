import unittest

import pandas as pd

from src.osg.transformer import (
    clean_columns,
    convert_dates,
    extract_weight,
    normalize_data_types,
    normalize_sku,
    normalize_sku_name,
    remove_service_rows,
    rename_columns,
    transform_category,
)


class SkuNormalizationTests(unittest.TestCase):
    def test_confirmed_technical_variants(self):
        cases = {
            "* НЭННИ 1 800 г.": "НЭННИ 1 800 г.",
            " НЭННИ 1 800 г.": "НЭННИ 1 800 г.",
            "НЭННИ 1 800 г. ": "НЭННИ 1 800 г.",
            "НЭННИ 1  800 г.": "НЭННИ 1 800 г.",
            "* НЭННИ 2 800 г": "НЭННИ 2 800 г.",
            " НЭННИ (ЗК) 3 800 гр.": "НЭННИ 3 800 г.",
        }

        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(normalize_sku_name(source), expected)

    def test_semantically_different_sku_are_not_merged(self):
        sku_400 = normalize_sku_name("НЭННИ 1 400 г.")
        sku_800 = normalize_sku_name("НЭННИ 1 800 г.")
        sku_formula_2 = normalize_sku_name("НЭННИ 2 800 г.")

        self.assertNotEqual(sku_400, sku_800)
        self.assertNotEqual(sku_800, sku_formula_2)

    def test_source_name_is_preserved_and_detail_rows_are_not_merged(self):
        df = pd.DataFrame({
            "SKU": ["* НЭННИ 1 800 г.", " НЭННИ 1  800 г. "],
            "Контейнер": ["A", "B"],
            "Срок годности": [
                pd.Timestamp("2028-04-30"),
                pd.Timestamp("2028-06-10"),
            ],
            "Остаток": [60, 5000],
        })

        result = normalize_sku(df)

        self.assertEqual(len(result), 2)
        self.assertEqual(result["Контейнер"].tolist(), ["A", "B"])
        self.assertEqual(
            result["Срок годности"].tolist(),
            df["Срок годности"].tolist(),
        )
        self.assertEqual(result["Остаток"].tolist(), [60, 5000])
        self.assertEqual(
            result["SKU"].tolist(),
            ["НЭННИ 1 800 г.", "НЭННИ 1 800 г."],
        )
        self.assertEqual(
            result["SKU_исходный"].tolist(),
            ["* НЭННИ 1 800 г.", " НЭННИ 1  800 г. "],
        )

    def test_summary_uses_one_normalized_sku_and_preserves_sums(self):
        df = pd.DataFrame({
            "SKU": ["НЭННИ 1 800 г.", "* НЭННИ 1 800 г."],
            "Остаток": [60, 5000],
            "Зарезервировано": [10, 200],
            "Свободный остаток": [50, 4800],
            "ОСГ %": [80.0, 65.0],
        })

        normalized = normalize_sku(df)
        summary = normalized.groupby("SKU", as_index=False).agg({
            "Остаток": "sum",
            "Зарезервировано": "sum",
            "Свободный остаток": "sum",
            "ОСГ %": "min",
        })

        self.assertEqual(len(summary), 1)
        self.assertEqual(summary.loc[0, "SKU"], "НЭННИ 1 800 г.")
        self.assertEqual(summary.loc[0, "Остаток"], 5060)
        self.assertEqual(summary.loc[0, "Зарезервировано"], 210)
        self.assertEqual(summary.loc[0, "Свободный остаток"], 4850)
        self.assertEqual(summary.loc[0, "ОСГ %"], 65.0)


class TransformerTests(unittest.TestCase):
    def test_columns_are_cleaned_and_renamed(self):
        df = pd.DataFrame(columns=[
            " Склад ",
            " Номенклатурная группа ",
            " Номенклатура ",
            " Срок годности ",
            " Характеристика номенклатуры ",
            " В ед. хранения ",
            " В ед. хранения.1 ",
            " В ед. хранения.2 ",
        ])

        result = rename_columns(clean_columns(df))

        self.assertEqual(result.columns.tolist(), [
            "Склад",
            "Категория_исходная",
            "SKU",
            "Срок годности",
            "Контейнер",
            "Остаток",
            "Зарезервировано",
            "Свободный остаток",
        ])

    def test_expiry_date_parsing_and_invalid_date(self):
        df = pd.DataFrame({
            "Срок годности": ["03.12.2027 0:00:00", "не дата"],
        })

        result = convert_dates(df)

        self.assertEqual(result.loc[0, "Срок годности"], pd.Timestamp("2027-12-03"))
        self.assertTrue(pd.isna(result.loc[1, "Срок годности"]))
        self.assertEqual(
            result["Срок годности_исходная"].tolist(),
            ["03.12.2027 0:00:00", "не дата"],
        )

    def test_service_rows_are_removed(self):
        df = pd.DataFrame({
            "SKU": ["Товар", "Итог", None, None],
            "Остаток": [10, 10, 10, None],
        })

        result = remove_service_rows(df)

        self.assertEqual(result["SKU"].tolist(), ["Товар"])

    def test_container_is_text(self):
        df = pd.DataFrame({"Контейнер": [1215.0, "1141А32", None]})

        result = normalize_data_types(df)

        self.assertEqual(result.loc[0, "Контейнер"], "1215.0")
        self.assertEqual(result.loc[1, "Контейнер"], "1141А32")
        self.assertTrue(pd.isna(result.loc[2, "Контейнер"]))

    def test_weight_rules(self):
        df = pd.DataFrame({
            "SKU": [
                "НЭННИ 1 400 г.",
                "Товар 37,5 г.",
                "Флоупак печенье Грушевое, 1 шт.",
                "Шоубокс печенье Грушевое, 1 шт.",
            ],
        })

        result = extract_weight(df)

        self.assertEqual(result["Вес"].tolist(), [400.0, 37.5, 37.5, 750.0])

    def test_category_rules(self):
        df = pd.DataFrame({
            "Категория_исходная": [
                "НЭННИ",
                "НЭННИ",
                "Печенье",
                "Печенье",
                "МЯСНЫЕ КОНСЕРВЫ",
                "РЫБНЫЕ КОНСЕРВЫ",
                "ТВОРОЖНОЕ ПЮРЕ",
                "Другая категория",
            ],
            "SKU": [
                "НЭННИ 1 400 г.",
                "НЭННИ 1 800 г.",
                "Флоупак печенье Грушевое",
                "Шоубокс печенье Грушевое",
                "Пюре мясное",
                "Пюре рыбное",
                "Пюре творожное",
                "Обычный товар",
            ],
            "Вес": [400, 800, 37.5, 750, 80, 80, 80, 100],
        })

        result = transform_category(df)

        self.assertEqual(result["Категория"].tolist(), [
            "НЭННИ 400",
            "НЭННИ 800",
            "ФЛОУПАК_ПЕЧЕНЬЕ",
            "ШОУБОКС_ПЕЧЕНЬЕ",
            "ПЮРЕ МЯСНЫЕ консервы",
            "ПЮРЕ РЫБНЫЕ консервы",
            "ПЮРЕ ТВОРОЖНОЕ",
            "Другая категория",
        ])


if __name__ == "__main__":
    unittest.main()
