from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

# =========================
# ОСГ
# =========================
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
REFERENCE_DATA_DIR = DATA_DIR / "reference"

# =========================
# ПРИХОДЫ
# =========================
ARRIVALS_DATA_DIR = DATA_DIR / "arrivals"
ARRIVALS_HISTORY_DIR = ARRIVALS_DATA_DIR / "history"
ARRIVALS_ACTUAL_DIR = ARRIVALS_DATA_DIR / "actual"
ARRIVALS_PLAN_DIR = ARRIVALS_DATA_DIR / "plan"
ARRIVALS_DANIEL_DIR = ARRIVALS_DATA_DIR / "daniel"

# =========================
# ПРОДАЖИ / ПРОГНОЗ
# =========================
SALES_DATA_DIR = DATA_DIR / "sales"

SALES_HISTORY_DIR = SALES_DATA_DIR / "history"
SALES_ACTUAL_DIR = SALES_DATA_DIR / "actual"
SALES_MANUAL_FORECAST_DIR = SALES_DATA_DIR / "manual_forecast"
SALES_PROCESSED_DIR = SALES_DATA_DIR / "processed"

SALES_PROCESSED_FILE = SALES_PROCESSED_DIR / "sales_processed.parquet"

# =========================
# СПРАВОЧНИКИ
# =========================
PRODUCT_MAPPING_FILE = REFERENCE_DATA_DIR / "product_mapping.xlsx"
CUSTOMER_MAPPING_FILE = REFERENCE_DATA_DIR / "customer_mapping.xlsx"

# =========================
# ТЕСТОВАЯ ДАТА
# =========================
TODAY_DATE = None