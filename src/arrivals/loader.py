from pathlib import Path

import pandas as pd


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
        df = pd.read_excel(latest_file, header=header, engine="openpyxl")
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
            df = pd.read_excel(file, header=header, engine="openpyxl")
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
        df = pd.read_excel(mapping_file, engine="openpyxl")
    except PermissionError as error:
        raise PermissionError(
            f"\nНет доступа к справочнику: {mapping_file.name}\n\n"
            f"Закрой файл product_mapping.xlsx в Excel и перезапусти Streamlit."
        ) from error

    df.columns = df.columns.str.strip()

    return df