import pandas as pd


def format_unique_values(values, limit: int = 30) -> str:
    """
    Красиво форматирует список уникальных значений для текста ошибки.

    :param values: список или Series со значениями
    :param limit: сколько значений показывать максимум
    :return: строка со значениями
    """
    clean_values = (
        pd.Series(values)
        .dropna()
        .astype(str)
        .str.strip()
    )

    clean_values = clean_values[
        ~clean_values.isin(["", "nan", "None", "<NA>"])
    ]

    unique_values = sorted(clean_values.unique())

    if not unique_values:
        return "нет значений для отображения"

    shown_values = unique_values[:limit]
    text = "; ".join(shown_values)

    if len(unique_values) > limit:
        text += f"; ... и ещё {len(unique_values) - limit}"

    return text


def validate_required_columns(df: pd.DataFrame) -> list[str]:
    """
    Проверяет наличие обязательных колонок в итоговой таблице продаж.

    :param df: обработанная таблица продаж
    :return: список ошибок
    """
    errors = []

    required_columns = [
        "Тип данных",
        "Источник",
        "Канал",
        "Канал название",
        "Контрагент",
        "Страна",
        "Номенклатура",
        "Категория",
        "SKU",
        "Формула",
        "Вес",
        "Квант, шт",
        "Год",
        "Квартал",
        "Месяц",
        "Дата начала недели",
        "Номер недели",
        "Количество, шт",
        "Количество, кг",
        "Количество, упак",
    ]

    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        errors.append(
            "❌ В обработанной таблице продаж отсутствуют обязательные колонки: "
            f"{missing_columns}"
        )

    return errors


def validate_unknown_customers(df: pd.DataFrame) -> list[str]:
    """
    Проверяет, есть ли контрагенты, которых нет в customer_mapping.xlsx.

    Признаки проблемы:
    - Канал = 'Не определено'
    - нет страны
    - нет статуса
    """
    errors = []

    if "Канал" not in df.columns or "Контрагент" not in df.columns:
        return errors

    unknown_customers = df[
        df["Канал"].astype(str).str.strip().isin(["", "Не определено", "nan"])
        | df["Страна"].isna()
        ]

    if not unknown_customers.empty:
        values = format_unique_values(unknown_customers["Контрагент"])

        errors.append(
            "❌ Есть контрагенты, которые не найдены в "
            "data/reference/customer_mapping.xlsx.\n\n"
            f"Проверь и добавь в справочник:\n{values}"
        )

    return errors


def validate_unknown_products(df: pd.DataFrame) -> list[str]:
    """
    Проверяет, есть ли товары, которые не сопоставились с product_mapping.xlsx.

    Признаки проблемы:
    - пустая категория
    - пустой SKU
    - пустая формула
    """
    errors = []

    required_columns = [
        "Номенклатура",
        "Категория",
        "SKU",
        "Формула",
    ]

    if any(column not in df.columns for column in required_columns):
        return errors

    unknown_products = df[
        df["Категория"].isna()
        | df["SKU"].isna()
        | df["Формула"].isna()
        | df["Категория"].astype(str).str.strip().isin(["", "nan", "None"])
        | df["SKU"].astype(str).str.strip().isin(["", "nan", "None"])
        | df["Формула"].astype(str).str.strip().isin(["", "nan", "None"])
        ]

    if not unknown_products.empty:
        values = format_unique_values(unknown_products["Номенклатура"])

        errors.append(
            "❌ Есть номенклатура, которая не сопоставилась с "
            "data/reference/product_mapping.xlsx.\n\n"
            "Что сделать:\n"
            "1. Если это обычный товар — добавь его на лист 'Лист1'.\n"
            "2. Если это набор — добавь его состав на лист 'set_mapping'.\n\n"
            f"Проблемная номенклатура:\n{values}"
        )

    return errors


def validate_weights(df: pd.DataFrame) -> list[str]:
    """
    Проверяет, заполнен ли вес.

    Без веса нельзя корректно считать кг и доли 400/800.
    """
    errors = []

    if "Вес" not in df.columns:
        return errors

    bad_weight = df[
        df["Вес"].isna()
        | (pd.to_numeric(df["Вес"], errors="coerce") <= 0)
        ]

    if not bad_weight.empty:
        values = format_unique_values(bad_weight["Номенклатура"])

        errors.append(
            "❌ Есть строки без веса или с весом 0.\n\n"
            "Из-за этого нельзя корректно посчитать продажи в кг.\n\n"
            f"Проверь товары:\n{values}"
        )

    return errors


def validate_quant(df: pd.DataFrame) -> list[str]:
    """
    Проверяет, заполнен ли квант.

    Без кванта нельзя корректно считать количество упаковок/коробов.
    """
    errors = []

    if "Квант, шт" not in df.columns:
        return errors

    bad_quant = df[
        df["Квант, шт"].isna()
        | (pd.to_numeric(df["Квант, шт"], errors="coerce") <= 0)
        ]

    if not bad_quant.empty:
        values = format_unique_values(bad_quant["Номенклатура"])

        errors.append(
            "❌ Есть строки без кванта или с квантом 0.\n\n"
            "Из-за этого нельзя корректно посчитать продажи в упаковках.\n\n"
            f"Проверь товары:\n{values}"
        )

    return errors


def validate_dates(df: pd.DataFrame) -> list[str]:
    """
    Проверяет, распознались ли год, квартал, месяц, дата начала недели и номер недели.
    Показывает, в каком файле и по каким строкам есть проблема.
    """
    errors = []

    date_columns = [
        "Год",
        "Квартал",
        "Месяц",
        "Дата начала недели",
        "Номер недели",
    ]

    missing_columns = [
        column for column in date_columns
        if column not in df.columns
    ]

    if missing_columns:
        return errors

    bad_dates = df[
        df["Год"].isna()
        | df["Квартал"].isna()
        | df["Дата начала недели"].isna()
        | df["Номер недели"].isna()
        ].copy()

    if not bad_dates.empty:
        show_columns = [
            "Файл_источник",
            "Источник",
            "Контрагент",
            "Номенклатура",
            "Год",
            "Месяц",
            "Дата начала недели",
            "Номер недели",
        ]

        existing_columns = [
            column for column in show_columns
            if column in bad_dates.columns
        ]

        examples = (
            bad_dates[existing_columns]
            .drop_duplicates()
            .head(20)
            .to_string(index=False)
        )

        errors.append(
            "❌ Есть строки, где не распознались год, квартал, дата недели "
            "или номер недели.\n\n"
            "Проверь исходные колонки 'По годам', 'По месяцам', 'По неделям' "
            "в файле, который указан ниже.\n\n"
            f"Количество проблемных строк: {len(bad_dates)}\n\n"
            f"Примеры строк:\n\n```text\n{examples}\n```"
        )

    return errors


def validate_quantities(df: pd.DataFrame) -> list[str]:
    """
    Проверяет количество продаж.

    В e-com могут быть возвраты со знаком минус.
    Поэтому отрицательные значения не считаем ошибкой,
    но отдельно предупреждаем о них.
    """
    errors = []

    quantity_columns = [
        "Количество, шт",
        "Количество, кг",
        "Количество, упак",
    ]

    if any(column not in df.columns for column in quantity_columns):
        return errors

    bad_quantity = df[
        df["Количество, шт"].isna()
        | df["Количество, кг"].isna()
        | df["Количество, упак"].isna()
        ]

    if not bad_quantity.empty:
        values = format_unique_values(bad_quantity["Номенклатура"])

        errors.append(
            "❌ Есть строки, где не рассчитались количества в шт / кг / упак.\n\n"
            f"Проверь товары:\n{values}"
        )

    negative_quantity = df[
        pd.to_numeric(df["Количество, шт"], errors="coerce") < 0
        ]

    if not negative_quantity.empty:
        errors.append(
            "⚠️ В данных есть отрицательные количества.\n\n"
            f"Количество строк с отрицательным количеством: {len(negative_quantity)}.\n\n"
            "Это может быть нормально, если это возвраты. "
            "Но лучше проверить, что это действительно возвраты, а не ошибка выгрузки."
        )

    return errors


def validate_channels(df: pd.DataFrame) -> list[str]:
    """
    Проверяет, что канал продаж относится к ожидаемым значениям.

    Ожидаемые значения:
    - sales
    - manufacturer
    - free
    """
    errors = []

    if "Канал" not in df.columns:
        return errors

    allowed_channels = [
        "sales",
        "manufacturer",
        "free",
    ]

    unknown_channels = df[
        ~df["Канал"].astype(str).isin(allowed_channels)
        & ~df["Канал"].astype(str).isin(["Не определено", "nan", "None", ""])
        ]

    if not unknown_channels.empty:
        values = format_unique_values(unknown_channels["Канал"])

        errors.append(
            "⚠️ Есть каналы, которых нет в ожидаемом списке.\n\n"
            "Ожидаемые каналы: sales, manufacturer, free.\n\n"
            f"Найденные значения:\n{values}"
        )

    return errors


def validate_duplicate_rows(df: pd.DataFrame) -> list[str]:
    """
    Предупреждает о возможных дублях.

    Дубль — это строки с одинаковыми:
    источник, контрагент, номенклатура, неделя, количество.

    Это не всегда ошибка:
    один и тот же товар мог быть отгружен одному клиенту несколько раз в одну неделю.
    Но если дубли идут из одного и того же файла, стоит проверить, не загружен ли файл дважды.
    """
    errors = []

    duplicate_columns = [
        "Источник",
        "Контрагент",
        "Номенклатура",
        "Дата начала недели",
        "Количество, шт",
    ]

    if any(column not in df.columns for column in duplicate_columns):
        return errors

    duplicated_rows = df[df.duplicated(subset=duplicate_columns, keep=False)].copy()

    if not duplicated_rows.empty:
        show_columns = [
            "Файл_источник",
            "Источник",
            "Контрагент",
            "Номенклатура",
            "Дата начала недели",
            "Количество, шт",
        ]

        existing_columns = [
            column for column in show_columns
            if column in duplicated_rows.columns
        ]

        examples = (
            duplicated_rows[existing_columns]
            .sort_values(existing_columns)
            .head(30)
            .to_string(index=False)
        )

        errors.append(
            "⚠️ Есть возможные дубли строк продаж.\n\n"
            f"Количество строк-дублей: {len(duplicated_rows)}.\n\n"
            "Это не всегда ошибка: один и тот же товар мог быть отгружен "
            "одному клиенту несколько раз в одну неделю одинаковым количеством.\n\n"
            "Но стоит проверить, не загружен ли один и тот же файл дважды.\n\n"
            f"Примеры дублей:\n\n```text\n{examples}\n```"
        )

    return errors


def validate_sales_data(df: pd.DataFrame) -> list[str]:
    """
    Запускает все проверки обработанной таблицы продаж.

    :param df: итоговая таблица продаж
    :return: список ошибок и предупреждений
    """
    errors = []

    if df.empty:
        errors.append("⚠️ Таблица продаж пустая. Проверь исходные файлы.")
        return errors

    errors.extend(validate_required_columns(df))

    # Если нет обязательных колонок, остальные проверки могут упасть.
    if any(error.startswith("❌ В обработанной таблице") for error in errors):
        return errors

    errors.extend(validate_unknown_customers(df))
    errors.extend(validate_unknown_products(df))
    errors.extend(validate_weights(df))
    errors.extend(validate_quant(df))
    errors.extend(validate_dates(df))
    errors.extend(validate_quantities(df))
    errors.extend(validate_channels(df))
    # errors.extend(validate_duplicate_rows(df))

    return errors


def split_errors_and_warnings(messages: list[str]) -> tuple[list[str], list[str]]:
    """
    Делит сообщения на ошибки и предупреждения.

    Ошибки начинаются с ❌.
    Предупреждения начинаются с ⚠️.
    """
    errors = [
        message for message in messages
        if message.startswith("❌")
    ]

    warnings = [
        message for message in messages
        if message.startswith("⚠️")
    ]

    return errors, warnings
