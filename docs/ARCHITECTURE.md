# Архитектура BIBICALL Analytics

Документ разделяет фактически существующую переходную архитектуру и целевое
направление. TARGET не означает, что перечисленные сервисы уже реализованы.

## CURRENT: переходный Excel-контур

```text
1С
  → ручной Excel-отчёт
  → loader
  → очистка и normalization
  → validation и quality diagnostics
  → business calculations и rules
  → Streamlit presentation
  → пользовательский Excel-export
```

Текущий ОСГ-контур читает последний `.xlsx` из `data/raw`, преобразует Excel-
колонки в рабочие поля, сохраняет Source SKU, формирует Analytical SKU, считает
сроки и ОСГ, затем строит пользовательские представления.

### Назначение существующих модулей

| Слой | Текущий модуль | Ответственность |
|---|---|---|
| Loader | `src/loader.py` | Поиск последнего `.xlsx`, исключение `~$`, чтение с `header=7` |
| Transformer | `src/osg/transformer.py` | Колонки, Source/Analytical SKU, даты, вес, категории, служебные строки |
| Calculator | `src/osg/calculator.py` | Полный срок жизни, `days_left`, ОСГ % и управляемая `calculation_date` |
| Rules | `src/osg/rules.py` | Риски, разделение `>100/<=100`, urgent sales, KPI «Внимание» |
| Validation | `src/validator.py` | Обязательные поля, даты, вес, срок жизни, ОСГ, expired goods |
| Quality | `src/osg/quality.py` | Неразрушающая диагностика количеств, null, дублей, SKU и fallback |
| Presentation | `src/osg/presentation.py` | Сортировка пользовательских представлений |
| Exporter | `src/osg/exporter.py` | Форматированный XLSX без pandas index и с цветами риска |
| Page | `src/osg/page.py` | Оркестрация, UI-фильтры, KPI, график, таблицы и загрузки |

`src/osg/page.py` пока содержит часть UI-агрегаций и собирает pipeline в
`prepare_data()`. Это факт текущей переходной реализации, а не образец целевого
service layer.

## TARGET: API и стабильная входная модель

```text
1С HTTP/JSON API
  ├→ products
  ├→ product_series
  ├→ barcodes
  └→ stocks
  → ingestion / API adapter
  → link and contract validation by source IDs
  → validation + ETL/service layer
  → normalized data model / storage
  → business calculation layer
  → Streamlit presentation layer
```

Главный принцип миграции:

> Смена Excel на JSON/API не должна требовать переписывания бизнес-формул ОСГ.

Меняться прежде всего должны ingestion и data adapter. API-ответ преобразуется
в стабильную модель полей, после чего существующие, покрытые тестами calculation
и rules получают эквивалентные нормализованные данные.

OSG API — не один плоский JSON, а четыре связанные сущности:

```text
PRODUCT → PRODUCT SERIES → STOCK SNAPSHOT
    └──────── BARCODE
```

На тестовом этапе читаемые control fields могут дублироваться между endpoint.
Их наличие помогает сверять связи, но не превращает `product_name` или
`series_name` в технические ключи.

В traceability layer поле `product_series.gtd_number` обозначает номер таможенной
декларации товара и не является technical/business key. Оно не смешивается с
документом движения 1С «ГТД по импорту БР... от ...», который относится к
таможенным начислениям и финансовому движению и не является physical receipt.
Если stocks возвращает `gtd_number`, это duplicated control field; canonical
приоритет `product_series` требует подтверждения программиста 1С.

### Целевые границы ответственности

- **Ingestion/API adapter** принимает products, product_series, barcodes и stocks
  раздельно; отвечает за HTTP, авторизацию, пагинацию, JSON и ошибки транспорта.
- **Link validation** проверяет `product_id`, `series_id`, characteristic и другие
  source IDs. При наличии `series_id` запрещено связывать series только по имени.
- **Validation/ETL** проверяет контракт, типы, обязательность, баланс количеств и
  приводит source values к стабильным полям без скрытой потери данных. Canonical
  и duplicated control fields сохраняются раздельно до принятого правила.
- **Storage** хранит реальные снимки с `stock_date`, source identifiers и
  traceability, включая series attributes. Конкретная СУБД пока не выбрана.
- **Business calculation layer** рассчитывает ОСГ, риск и бизнес-представления и
  не знает, пришли данные из Excel или API.
- **Presentation layer** применяет пользовательские фильтры, форматирование и
  визуализацию, не переопределяя business rules.

## Ограничения текущего состояния

- Надёжного `stock_date` в legacy Excel нет.
- Excel-header и названия колонок являются частью временного адаптера.
- Исторический выбор снимка в Streamlit ещё не реализован, хотя calculator уже
  принимает явную `calculation_date`.
- Окончательные storage и JSON schema не проектируются до реального ответа 1С.
- Стабильность `series_id` и canonical priority expiry/shelf-life пока не
  подтверждены.

Все открытые вопросы модели перечислены в `docs/osg/OSG_DATA_MODEL.md`.
