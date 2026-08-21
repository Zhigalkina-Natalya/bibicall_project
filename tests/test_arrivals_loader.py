import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import pandas as pd

from src.arrivals.loader import (
    ArrivalsExcelReadError,
    get_valid_excel_files,
    load_latest_excel_file,
)


class ArrivalsLoaderTests(unittest.TestCase):
    @staticmethod
    def _load_latest_silently(folder: Path) -> pd.DataFrame:
        with patch("builtins.print"):
            return load_latest_excel_file(folder)

    @staticmethod
    def _write_normal_xlsx(path: Path, value: str = "НЭННИ") -> None:
        df = pd.DataFrame({"SKU": [value], "Количество": [12]})
        with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)

    @staticmethod
    def _make_shared_strings_case_mismatch(path: Path) -> None:
        temporary_path = path.with_suffix(".tmp")

        with zipfile.ZipFile(path) as source_zip:
            with zipfile.ZipFile(
                    temporary_path,
                    mode="w",
                    compression=zipfile.ZIP_DEFLATED,
            ) as target_zip:
                for entry in source_zip.infolist():
                    target_name = (
                        "xl/SharedStrings.xml"
                        if entry.filename == "xl/sharedStrings.xml"
                        else entry.filename
                    )
                    target_zip.writestr(target_name, source_zip.read(entry))

        temporary_path.replace(path)

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_normal_xlsx_is_read_without_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "normal.xlsx"
            self._write_normal_xlsx(file)

            with patch("src.arrivals.loader.BytesIO") as stream_mock:
                result = self._load_latest_silently(Path(directory))

            self.assertEqual(result.loc[0, "SKU"], "НЭННИ")
            self.assertEqual(result.loc[0, "Количество"], 12)
            stream_mock.assert_not_called()

    def test_shared_strings_case_mismatch_is_read_via_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "case_mismatch.xlsx"
            self._write_normal_xlsx(file)
            self._make_shared_strings_case_mismatch(file)

            with zipfile.ZipFile(file) as workbook_zip:
                self.assertIn("xl/SharedStrings.xml", workbook_zip.namelist())
                self.assertNotIn("xl/sharedStrings.xml", workbook_zip.namelist())

            result = self._load_latest_silently(Path(directory))

            self.assertEqual(result.loc[0, "SKU"], "НЭННИ")
            self.assertEqual(result.loc[0, "Количество"], 12)

    def test_fallback_does_not_modify_source_file(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "immutable.xlsx"
            self._write_normal_xlsx(file)
            self._make_shared_strings_case_mismatch(file)
            hash_before = self._sha256(file)
            bytes_before = file.read_bytes()

            self._load_latest_silently(Path(directory))

            self.assertEqual(self._sha256(file), hash_before)
            self.assertEqual(file.read_bytes(), bytes_before)

    def test_corrupted_xlsx_has_clear_diagnostic_error(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "corrupted.xlsx"
            file.write_bytes(b"not an xlsx zip archive")

            with self.assertRaisesRegex(
                    ArrivalsExcelReadError,
                    r"corrupted\.xlsx.*не является корректным XLSX/ZIP",
            ):
                self._load_latest_silently(Path(directory))

    def test_latest_normal_xlsx_is_used_and_temporary_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            old_file = folder / "actual_old.xlsx"
            latest_file = folder / "actual_latest.xlsx"
            temporary_file = folder / "~$actual_latest.xlsx"

            self._write_normal_xlsx(old_file, value="OLD")
            self._write_normal_xlsx(latest_file, value="LATEST")
            self._write_normal_xlsx(temporary_file, value="TEMPORARY")

            os.utime(old_file, (1, 1))
            os.utime(latest_file, (2, 2))
            os.utime(temporary_file, (3, 3))

            valid_files = get_valid_excel_files(folder)
            result = self._load_latest_silently(folder)

            self.assertEqual(set(valid_files), {old_file, latest_file})
            self.assertEqual(result.loc[0, "SKU"], "LATEST")


if __name__ == "__main__":
    unittest.main()
