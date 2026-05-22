import pandas as pd


def validate_required_columns(df: pd.DataFrame) -> list[str]:
    """
    Проверяет наличие обязательных колонок после преобразования.

    :param df: таблица после обработки
    :return: список ошибок
    """
    errors = []

    required_columns = [
        "Склад",
        "Категория_исходная",
        "SKU",
        "Срок годности",
        "Контейнер",
        "Остаток",
        "Зарезервировано",
        "Свободный остаток",
        "Вес",
        "Категория",
        "days_left",
        "total_days",
        "ОСГ %",
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        errors.append(f"Отсутствуют обязательные колонки: {missing_columns}")

    return errors


def validate_dates(df: pd.DataFrame) -> list[str]:
    """
    Проверяет, есть ли строки, где срок годности не распознался как дата.

    :param df: таблица после обработки
    :return: список ошибок
    """
    errors = []

    bad_dates = df[df["Срок годности"].isna()]

    if not bad_dates.empty:
        errors.append(
            f"Не распознаны даты в {len(bad_dates)} строках. "
            f"Проверь колонку 'Срок годности_исходная'."
        )

    return errors


def validate_weight(df: pd.DataFrame) -> list[str]:
    """
    Проверяет, определился ли вес товара.

    :param df: таблица после обработки
    :return: список ошибок
    """
    errors = []

    bad_weight = df[df["Вес"].isna()]

    if not bad_weight.empty:
        errors.append(
            f"Не определился вес в {len(bad_weight)} строках. "
            f"Проверь названия SKU."
        )

    return errors


def validate_shelf_life(df: pd.DataFrame) -> list[str]:
    """
    Проверяет, найден ли срок жизни товара.

    :param df: таблица после обработки
    :return: список ошибок
    """
    errors = []

    bad_shelf_life = df[df["total_days"].isna()]

    if not bad_shelf_life.empty:
        errors.append(
            f"Не найден срок жизни в {len(bad_shelf_life)} строках."
        )

    return errors


def validate_osg(df: pd.DataFrame) -> list[str]:
    """
    Проверяет корректность расчёта ОСГ.

    :param df: таблица после обработки
    :return: список ошибок
    """
    errors = []

    bad_osg = df[df["ОСГ %"].isna()]

    if not bad_osg.empty:
        errors.append(
            f"ОСГ не рассчитался в {len(bad_osg)} строках."
        )

    negative_osg = df[df["ОСГ %"] < 0]

    if not negative_osg.empty:
        errors.append(
            f"Есть товары с истёкшим сроком годности: {len(negative_osg)} строк."
        )

    return errors


def run_all_checks(df: pd.DataFrame) -> list[str]:
    """
    Запускает все проверки качества данных.

    :param df: таблица после обработки
    :return: общий список ошибок
    """
    errors = []

    errors.extend(validate_required_columns(df))

    if errors:
        return errors

    errors.extend(validate_dates(df))
    errors.extend(validate_weight(df))
    errors.extend(validate_shelf_life(df))
    errors.extend(validate_osg(df))

    return errors
