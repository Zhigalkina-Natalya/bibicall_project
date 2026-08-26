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

## Target API endpoints

```http
GET /api/v1/products
GET /api/v1/product_series
GET /api/v1/barcodes
GET /api/v1/stocks
```

Назначение:

| Endpoint | Сущность/назначение |
|---|---|
| `/products` | Номенклатура и карточки SKU |
| `/product_series` | Серии, expiry, сертификаты, GTD, страна происхождения |
| `/barcodes` | Связь SKU/характеристик со штрихкодами |
| `/stocks` | Срез остатков на реальную `stock_date` |

Это подтверждённый состав требований, отправленных программисту 1С, но не уже
реализованный API-клиент или окончательная JSON schema.

## Логический порядок первичной загрузки

1. `products`;
2. `product_series`;
3. `barcodes`;
4. `stocks`.

Порядок описывает зависимость проверки ссылок, а не обязательно последовательные
HTTP-вызовы. К моменту проверки stocks ingestion должен уметь проверить
`product_id`, `series_id`, `characteristic_id`, `warehouse_id` и organization
links по доступным справочникам.

На первом этапе читаемые поля могут намеренно повторяться между endpoint для
визуального контроля. Ingestion должен различать canonical field и duplicated
control field, сохранять оба значения при расхождении и выдавать диагностику.

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

Для `product_series` отдельно допускаются nullable `series_serial_number` и
`gtd_number`. Поле `gtd_number` означает номер таможенной декларации товара и
предпочтительно относится к `product_series`, если это подтвердит 1С. Оно не
является идентификатором или business key серии/контейнера и не участвует в
расчёте ОСГ. Для российского товара допускается `null`.

Документ движения 1С **«ГТД по импорту БР... от ...»**, связанный с таможенными
начислениями, пошлиной и финансовым движением, не равен полю «Номер ГТД». Он не
является physical receipt и не используется для идентификации series или
container.

Если `gtd_number` присутствует и в stocks, он сохраняется как duplicated control
field. Предпочтение `product_series` как canonical/source-of-truth утверждается
только после проверки реального JSON и подтверждения программистом 1С.

## Регулярное обновление

Ежедневный контур должен предусматривать:

1. обновление справочников products/product_series/barcodes;
2. получение актуального stock snapshot;
3. контроль ссылочной целостности;
4. диагностику отсутствующих `product_id`, `series_id` и других linking IDs;
5. контроль `meta/count`, если механизм будет доступен;
6. сохранение source values и расхождений duplicated control fields.

## Последовательность миграции

1. Получить реальный JSON без догадок о schema.
2. Зафиксировать поля, типы, nullable и бизнес-ключ вместе с программистом 1С.
3. Сохранить тестовый ответ как обезличенный contract fixture.
4. Реализовать adapters четырёх сущностей и стабильную входную модель ОСГ.
5. Выполнять validation до business/display filters.
6. На одинаковом снимке сравнить строки, количества, даты, SKU, shelf life, ОСГ,
   риск и агрегаты Excel vs API.
7. Подключить регулярное хранение снимков с реальным `stock_date`.
8. Переключить Streamlit на service layer только после принятия расхождений.
9. Удалять Excel-specific adapter отдельным решением после периода стабилизации.

## OPEN DECISION

- стабильность и доступность `series_id`;
- characteristic/container и связь characteristic ↔ series;
- может ли series относиться к нескольким characteristics;
- canonical `expiry_date`;
- canonical `shelf_life_days`;
- source `production_date` и `country_of_origin` priority;
- semantics certificate и series serial number;
- место хранения, формат, nullable semantics и cardinality `gtd_number`;
- точная schema всех четырёх endpoint;
- авторизация, timeout, retry и частота загрузки;
- pagination и `meta/count`;
- реальный business key записи и duplicate policy;
- семантика `stock_date`;
- null semantics quantities;
- структура целевого хранения.

## REQUIRES FOLLOW-UP WITH 1C DEVELOPER

- подтвердить, что stocks всегда может вернуть стабильный `series_id`;
- подтвердить cardinality product/characteristic/series;
- определить canonical endpoint для expiry, production date и shelf life;
- определить согласованную обработку расхождений duplicated control fields;
- уточнить status semantics `deletion_mark` и `is_active`;
- подтвердить nullable и форматы series/certificate/GTD/country fields;
- подтвердить, является ли `gtd_number` реквизитом series, может ли одна series
  иметь один `gtd_number` и может ли один `gtd_number` относиться к нескольким
  series.
