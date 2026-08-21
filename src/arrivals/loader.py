from io import BytesIO
from pathlib import Path
import zipfile

import pandas as pd


EXPECTED_SHARED_STRINGS = "xl/sharedStrings.xml"
CASE_MISMATCH_SHARED_STRINGS = "xl/SharedStrings.xml"


class ArrivalsExcelReadError(ValueError):
    """Понятная ошибка чтения структурно некорректного XLSX."""


def _read_excel(file: Path, header: int = 0) -> pd.DataFrame:
    """
    Читает XLSX обычным способом и исправляет только известную ошибку регистра
    sharedStrings во временном представлении в памяти.

    Исходный файл на диске не изменяется.
    """
    try:
        return pd.read_excel(file, header=header, engine="openpyxl")
    except PermissionError:
        raise
    except Exception as original_error:
        try:
            with zipfile.ZipFile(file) as source_zip:
                entries = set(source_zip.namelist())

                required_entries = {
                    "[Content_Types].xml",
                    "xl/workbook.xml",
                    "xl/_rels/workbook.xml.rels",
                }
                missing_required = sorted(required_entries - entries)

                if missing_required:
                    raise ArrivalsExcelReadError(
                        f"Не удалось прочитать Excel-файл приходов: {file.name}. "
                        "Некорректная структура XLSX: отсутствуют обязательные "
                        f"части: {', '.join(missing_required)}."
                    ) from original_error

                has_known_case_mismatch = (
                    EXPECTED_SHARED_STRINGS not in entries
                    and CASE_MISMATCH_SHARED_STRINGS in entries
                )

                if not has_known_case_mismatch:
                    raise ArrivalsExcelReadError(
                        f"Не удалось прочитать Excel-файл приходов: {file.name}. "
                        "Некорректная структура XLSX; известная ошибка регистра "
                        "xl/SharedStrings.xml не обнаружена."
                    ) from original_error

                repaired_stream = BytesIO()

                with zipfile.ZipFile(
                        repaired_stream,
                        mode="w",
                        compression=zipfile.ZIP_DEFLATED,
                ) as repaired_zip:
                    for entry in source_zip.infolist():
                        target_name = (
                            EXPECTED_SHARED_STRINGS
                            if entry.filename == CASE_MISMATCH_SHARED_STRINGS
                            else entry.filename
                        )
                        repaired_zip.writestr(target_name, source_zip.read(entry))

            repaired_stream.seek(0)

            try:
                return pd.read_excel(
                    repaired_stream,
                    header=header,
                    engine="openpyxl",
                )
            except Exception as fallback_error:
                raise ArrivalsExcelReadError(
                    f"Не удалось прочитать Excel-файл приходов: {file.name}. "
                    "Коррекция регистра xl/sharedStrings.xml в памяти не помогла; "
                    "XLSX имеет другую структурную ошибку."
                ) from fallback_error

        except ArrivalsExcelReadError:
            raise
        except (OSError, zipfile.BadZipFile) as zip_error:
            raise ArrivalsExcelReadError(
                f"Не удалось прочитать Excel-файл приходов: {file.name}. "
                "Файл не является корректным XLSX/ZIP-архивом."
            ) from zip_error


def get_valid_excel_files(folder: Path) -> list[Path]:
    """
    Возвращает только настоящие Excel-файлы.

    Исключает:
    - временные файлы Excel, которые начинаются с ~$
    - скрытые/служебные файлы
    """
    if not folder.exists():
        return []

    files = [
        file for file in folder.glob("*.xlsx")
        if not file.name.startswith("~$")
    ]

    return files


def load_latest_excel_file(folder: Path, header: int = 0) -> pd.DataFrame:
    """
    Загружает последний настоящий Excel-файл из папки.
    """
    files = get_valid_excel_files(folder)

    if not files:
        return pd.DataFrame()

    latest_file = max(files, key=lambda file: file.stat().st_mtime)

    print(f"📂 Загружаем файл: {latest_file.name}")

    try:
        df = _read_excel(latest_file, header=header)
    except PermissionError as error:
        raise PermissionError(
            f"\nНет доступа к файлу: {latest_file.name}\n\n"
            f"Что сделать:\n"
            f"1. Закрой этот файл в Excel.\n"
            f"2. Убедись, что в папке нет временного файла, начинающегося с ~$.\n"
            f"3. Перезапусти Streamlit.\n"
        ) from error

    df = df.dropna(how="all")
    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]

    return df


def load_all_excel_files(folder: Path, header: int = 0) -> pd.DataFrame:
    """
    Загружает все настоящие Excel-файлы из папки и объединяет их.
    """
    files = get_valid_excel_files(folder)

    if not files:
        return pd.DataFrame()

    dataframes = []

    for file in files:
        print(f"📂 Загружаем файл: {file.name}")

        try:
            df = _read_excel(file, header=header)
        except PermissionError as error:
            raise PermissionError(
                f"\nНет доступа к файлу: {file.name}\n\n"
                f"Что сделать:\n"
                f"1. Закрой этот файл в Excel.\n"
                f"2. Убедись, что файл не открыт другим пользователем.\n"
                f"3. Перезапусти Streamlit.\n"
            ) from error

        df = df.dropna(how="all")
        df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]
        df["Файл_источник"] = file.name

        dataframes.append(df)

    return pd.concat(dataframes, ignore_index=True)


def load_product_mapping(mapping_file: Path) -> pd.DataFrame:
    """
    Загружает справочник соответствия номенклатуры.
    """
    if not mapping_file.exists():
        raise FileNotFoundError(
            f"Не найден файл справочника: {mapping_file}. "
            f"Создай product_mapping.xlsx в папке data/reference."
        )

    try:
        df = _read_excel(mapping_file)
    except PermissionError as error:
        raise PermissionError(
            f"\nНет доступа к справочнику: {mapping_file.name}\n\n"
            f"Закрой файл product_mapping.xlsx в Excel и перезапусти Streamlit."
        ) from error

    df.columns = df.columns.str.strip()

    return df
