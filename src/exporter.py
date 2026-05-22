from pathlib import Path
import pandas as pd
from datetime import datetime


def save_to_excel(df: pd.DataFrame, folder: Path):
    """
    Сохраняет обработанный файл.

    :param df: DataFrame
    :param folder: папка назначения
    """
    filename = f"osg_report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    path = folder / filename

    df.to_excel(path, index=False)
