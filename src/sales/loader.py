from pathlib import Path

import pandas as pd


def get_valid_excel_files(folder: Path) -> list[Path]:
    """
    Возвращает список настоящих Excel-файлов из папки.

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


def load_all_excel_files(
        folder: Path,
        header: int = 0,
        source_name: str = "",
) -> pd.DataFrame:
    """
    Загружает все Excel-файлы из папки и объединяет их в одну таблицу.

    :param folder: папка с Excel-файлами
    :param header: номер строки с заголовками, начиная с 0
    :param source_name: название источника данных
    :return: объединенный DataFrame
    """
    files = get_valid_excel_files(folder)

    if not files:
        return pd.DataFrame()

    dataframes = []

    for file in files:
        print(f"📂 Загружаем файл продаж: {file.name}")

        try:
            df = pd.read_excel(
                file,
                header=header,
                engine="openpyxl",
            )
        except PermissionError as error:
            raise PermissionError(
                f"\nНет доступа к файлу: {file.name}\n\n"
                f"Что сделать:\n"
                f"1. Закрой файл в Excel.\n"
                f"2. Убедись, что файл не открыт другим пользователем.\n"
                f"3. Перезапусти Streamlit.\n"
            ) from error

        df = df.dropna(how="all")

        # Удаляем полностью пустые или служебные Unnamed-колонки.
        df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]

        df["Файл_источник"] = file.name

        if source_name:
            df["Источник"] = source_name

        dataframes.append(df)

    return pd.concat(dataframes, ignore_index=True)


def load_sales_history(folder: Path) -> pd.DataFrame:
    """
    Загружает исторические продажи 2020-2025.

    Исторический файл уже подготовлен вручную,
    поэтому обычно читается с первой строки.
    """
    return load_all_excel_files(
        folder=folder,
        header=0,
        source_name="История продаж",
    )


def load_excel_file_with_flexible_header(
        file: Path,
        header_options: list[int],
        source_name: str = "",
) -> pd.DataFrame:
    """
    Загружает Excel-файл, пробуя несколько вариантов строки заголовков.

    Это нужно для выгрузок 1С, где:
    - в одном файле заголовки могут быть на 8-й строке;
    - в другом файле заголовки могут быть на 9-й строке.

    :param file: путь к Excel-файлу
    :param header_options: варианты header для pandas
    :param source_name: название источника
    :return: DataFrame
    """
    required_any_columns = [
        "Контрагент",
        "Комиссионер",
        "Номенклатура",
    ]

    quantity_any_columns = [
        "Количество (в базовых единицах)",
        "Количество",
        "Приход",
    ]

    last_df = pd.DataFrame()

    for header in header_options:
        try:
            df = pd.read_excel(
                file,
                header=header,
                engine="openpyxl",
            )
        except PermissionError as error:
            raise PermissionError(
                f"\nНет доступа к файлу: {file.name}\n\n"
                f"Что сделать:\n"
                f"1. Закрой файл в Excel.\n"
                f"2. Убедись, что файл не открыт другим пользователем.\n"
                f"3. Перезапусти Streamlit.\n"
            ) from error

        df = df.dropna(how="all")
        df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]
        df.columns = df.columns.astype(str).str.strip()

        last_df = df.copy()

        has_base_columns = any(column in df.columns for column in required_any_columns)
        has_quantity_column = any(column in df.columns for column in quantity_any_columns)

        if has_base_columns and has_quantity_column:
            df["Файл_источник"] = file.name

            if source_name:
                df["Источник"] = source_name

            return df

    raise ValueError(
        f"\nНе удалось определить строку заголовков в файле: {file.name}\n\n"
        f"Пробовали варианты header={header_options}.\n\n"
        f"Последние найденные колонки:\n{list(last_df.columns)}\n\n"
        f"Что проверить:\n"
        f"1. В файле должны быть колонки Контрагент/Комиссионер, Номенклатура.\n"
        f"2. Должна быть колонка количества: "
        f"'Количество (в базовых единицах)' или 'Приход'.\n"
    )


def load_sales_actual(folder: Path) -> pd.DataFrame:
    """
    Загружает фактические продажи текущего года.

    Файлы 1С могут отличаться:
    - обычный файл: заголовки на 8-й строке Excel -> header=7;
    - e-com файл: заголовки на 9-й строке Excel -> header=8.

    Поэтому пробуем оба варианта.
    """
    files = get_valid_excel_files(folder)

    if not files:
        return pd.DataFrame()

    dataframes = []

    for file in files:
        print(f"📂 Загружаем файл фактических продаж: {file.name}")

        df = load_excel_file_with_flexible_header(
            file=file,
            header_options=[7, 8],
            source_name="Факт 1С",
        )

        dataframes.append(df)

    return pd.concat(dataframes, ignore_index=True)


def load_product_mapping(mapping_file: Path) -> pd.DataFrame:
    """
    Загружает основной справочник номенклатуры из product_mapping.xlsx.

    Используется лист 'Лист1'.
    """
    if not mapping_file.exists():
        raise FileNotFoundError(
            f"Не найден справочник товаров: {mapping_file}\n\n"
            f"Проверь, что файл product_mapping.xlsx лежит в папке data/reference."
        )

    try:
        df = pd.read_excel(
            mapping_file,
            sheet_name="Лист1",
            engine="openpyxl",
        )
    except PermissionError as error:
        raise PermissionError(
            f"\nНет доступа к справочнику: {mapping_file.name}\n\n"
            f"Закрой файл product_mapping.xlsx в Excel и перезапусти Streamlit."
        ) from error

    df.columns = df.columns.astype(str).str.strip()
    df = df.dropna(how="all")

    return df


def load_set_mapping(mapping_file: Path) -> pd.DataFrame:
    """
    Загружает справочник наборов из product_mapping.xlsx.

    Используется лист 'set_mapping'.
    """
    if not mapping_file.exists():
        raise FileNotFoundError(
            f"Не найден справочник товаров: {mapping_file}\n\n"
            f"Проверь, что файл product_mapping.xlsx лежит в папке data/reference."
        )

    try:
        df = pd.read_excel(
            mapping_file,
            sheet_name="set_mapping",
            engine="openpyxl",
        )
    except ValueError as error:
        raise ValueError(
            f"\nВ файле product_mapping.xlsx не найден лист 'set_mapping'.\n\n"
            f"Что сделать:\n"
            f"1. Открой product_mapping.xlsx.\n"
            f"2. Проверь, что есть лист с точным названием: set_mapping.\n"
            f"3. Сохрани файл и перезапусти Streamlit.\n"
        ) from error
    except PermissionError as error:
        raise PermissionError(
            f"\nНет доступа к справочнику: {mapping_file.name}\n\n"
            f"Закрой файл product_mapping.xlsx в Excel и перезапусти Streamlit."
        ) from error

    df.columns = df.columns.astype(str).str.strip()
    df = df.dropna(how="all")

    return df


def load_customer_mapping(mapping_file: Path) -> pd.DataFrame:
    """
    Загружает справочник контрагентов.

    Используется файл customer_mapping.xlsx.
    """
    if not mapping_file.exists():
        raise FileNotFoundError(
            f"Не найден справочник контрагентов: {mapping_file}\n\n"
            f"Проверь, что файл customer_mapping.xlsx лежит в папке data/reference."
        )

    try:
        df = pd.read_excel(
            mapping_file,
            engine="openpyxl",
        )
    except PermissionError as error:
        raise PermissionError(
            f"\nНет доступа к справочнику: {mapping_file.name}\n\n"
            f"Закрой файл customer_mapping.xlsx в Excel и перезапусти Streamlit."
        ) from error

    df.columns = df.columns.astype(str).str.strip()
    df = df.dropna(how="all")

    return df


def save_processed_sales(df: pd.DataFrame, output_file: Path) -> None:
    """
    Сохраняет обработанные продажи в parquet.

    Parquet нужен, чтобы приложение быстрее запускалось
    и не перечитывало тяжелые Excel-файлы каждый раз.
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    df.to_parquet(
        output_file,
        index=False,
        engine="pyarrow",
    )


def load_processed_sales(processed_file: Path) -> pd.DataFrame:
    """
    Загружает ранее обработанные продажи из parquet.
    """
    if not processed_file.exists():
        return pd.DataFrame()

    return pd.read_parquet(
        processed_file,
        engine="pyarrow",
    )
