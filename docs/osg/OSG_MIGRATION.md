# ОСГ: миграция Legacy Excel → JSON/API 1С

Документ задаёт безопасное направление миграции без переписывания бизнес-логики
с нуля. Окончательная JSON schema утверждается только после получения реального
тестового ответа программиста 1С.

## Legacy Excel contract

Сейчас `src/loader.py` выбирает последний `.xlsx` из `data/raw`, исключает файлы
`~$` и читает заголовок с восьмой строки (`header=7`). `src/osg/transformer.py`
переименовывает Excel-колонки, сохраняет source values и приводит их к рабочей
модели. Это временный source adapter.

Legacy Excel не содержит надёжного `stock_date`. Конечная дата периода внутри
старого отчёта не должна использоваться как дата снимка.

Старый корневой `MIGRATION_OSG.md` остаётся техническим паспортом и историческим
baseline. Он синхронизирован с текущим фактом подключения quality diagnostics,
но не удаляется.

## KEEP

При переходе сохраняются и проверяются regression/equivalence tests:

- формула ОСГ и календарная `calculation_date`;
- risk thresholds и актуальные названия уровней;
- концепция Source SKU / Analytical SKU;
- подтверждённые normalization mappings;
- validation до фильтров, способных скрыть проблему;
- data-quality diagnostics и контроль баланса;
- агрегация `Категория + Analytical SKU + expiry` для urgent sales;
- основная аналитика `>100` и малые остатки `<=100`;
- urgent-sale rule `OSG <60` и aggregated free stock `>0`;
- тесты бизнес-логики и контроль сохранения количеств.

Legacy shelf-life rules остаются временно для совместимости и сравнения, пока не
подтверждено API-поле.

## REPLACE/REMOVE AFTER API

После подтверждения API и equivalence tests заменяются:

- поиск последнего Excel-файла и зависимость от `mtime`;
- `pd.read_excel`, `header=7` и `openpyxl` как ingestion механика;
- Excel-specific названия и дубли колонок `В ед. хранения`;
- разбор строки срока `ДД.ММ.ГГГГ 0:00:00` как обязательный путь;
- определение legacy report date по имени/metadata файла;
- зависимость от технического конечного периода отчёта 1С;
- другие преобразования, необходимые только для конкретной формы Excel.

Удаление выполняется только после параллельного сравнения Excel и API на одном
снимке. Legacy loader до этого не удаляется.

## Предварительные API endpoints

```http
GET /api/v1/stocks
GET /api/v1/products
GET /api/v1/barcodes
```

Это ожидаемые методы контракта, а не уже реализованный API-клиент.

## Требования к JSON

- стабильные типы полей;
- даты в `YYYY-MM-DD`;
- количества и проценты передаются числами, не строками;
- отсутствующее значение передаётся `null`;
- одна запись массива соответствует одной записи данных;
- идентификаторы желательно передавать строками;
- pagination при большом объёме;
- `meta/count` для контроля полноты, если возможно;
- реальный `stock_date` для каждого снимка;
- source IDs и source names для traceability.

## Последовательность миграции

1. Получить реальный JSON без догадок о schema.
2. Зафиксировать поля, типы, nullable и бизнес-ключ вместе с программистом 1С.
3. Сохранить тестовый ответ как обезличенный contract fixture.
4. Реализовать API adapter, возвращающий стабильную входную модель ОСГ.
5. Выполнять validation до business/display filters.
6. На одинаковом снимке сравнить строки, количества, даты, SKU, shelf life, ОСГ,
   риск и агрегаты Excel vs API.
7. Подключить регулярное хранение снимков с реальным `stock_date`.
8. Переключить Streamlit на service layer только после принятия расхождений.
9. Удалять Excel-specific adapter отдельным решением после периода стабилизации.

## OPEN DECISION

- точная stocks/products/barcodes schema;
- авторизация, timeout, retry и частота загрузки;
- pagination и `meta/count`;
- реальный business key записи;
- семантика `stock_date`;
- null semantics quantities;
- characteristic/container;
- series/batch model;
- shelf-life source priority;
- структура целевого хранения.
