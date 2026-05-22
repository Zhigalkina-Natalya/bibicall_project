from pathlib import Path

import pandas as pd


def load_latest_file(folder: Path) -> pd.DataFrame:
    """
    Загружает последний Excel-файл из папки raw.

    В отчёте 1С реальные заголовки таблицы находятся на 8-й строке Excel.
    В pandas нумерация начинается с 0, поэтому используем header=7.
    """
    files = list(folder.glob("*.xlsx"))

    if not files:
        raise FileNotFoundError(f"В папке {folder} нет Excel-файлов .xlsx")

    latest_file = max(files, key=lambda x: x.stat().st_mtime)

    print(f"📂 Загружаем файл: {latest_file.name}")

    try:
        df = pd.read_excel(latest_file, header=7, engine="openpyxl")
    except KeyError as error:
        raise ValueError(
            f"\nФайл {latest_file.name} не удалось прочитать как корректный .xlsx.\n"
            f"Скорее всего, выгрузка из 1С сохранена в нестандартном формате.\n\n"
            f"Что сделать:\n"
            f"1. Открой файл в Excel.\n"
            f"2. Нажми: Файл → Сохранить как.\n"
            f"3. Выбери формат: Книга Excel (*.xlsx).\n"
            f"4. Сохрани файл заново в папку data/raw.\n"
            f"5. Запусти poetry run python main.py ещё раз.\n"
        ) from error

    return df
