from src.loader import load_latest_file
from src.osg.transformer import (
    clean_columns,
    rename_columns,
    remove_service_rows,
    convert_dates,
    extract_weight,
    transform_category,
    prepare_final_columns,
)
from src.osg.calculator import calculate_osg
from src.exporter import save_to_excel
from src.config import RAW_DATA_DIR, PROCESSED_DATA_DIR
from src.validator import run_all_checks


def main():
    """
    Основной сценарий обработки отчёта ОСГ:
    1. Загружает файл из 1С
    2. Преобразует колонки
    3. Считает ОСГ
    4. Проверяет ошибки
    5. Сохраняет результат
    """
    df = load_latest_file(RAW_DATA_DIR)

    print("Колонки в файле:")
    print(df.columns.tolist())

    print("Файл загружен")
    print(f"Строк: {len(df)}")

    df = clean_columns(df)
    df = rename_columns(df)
    df = remove_service_rows(df)
    df = convert_dates(df)
    df = extract_weight(df)
    df = transform_category(df)

    print("Преобразования выполнены")

    print("\nПроверка данных ДО расчёта:")
    print(df[["SKU", "Категория", "Вес", "Срок годности"]].head(10))

    df = calculate_osg(df)

    print("ОСГ рассчитан")

    print("\nПроверка ПОСЛЕ расчёта:")
    print(df[["SKU", "Категория", "days_left", "total_days", "ОСГ %"]].head(10))

    errors = run_all_checks(df)

    if errors:
        print("\n⚠️ Найдены ошибки:")
        for error in errors:
            print(f"- {error}")
    else:
        print("\n✅ Проверка пройдена: ошибок не найдено")

    df = prepare_final_columns(df)

    save_to_excel(df, PROCESSED_DATA_DIR)

    print("\nФайл сохранён в processed")


if __name__ == "__main__":
    main()
