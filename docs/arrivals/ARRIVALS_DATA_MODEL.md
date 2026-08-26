# ARRIVALS: логическая модель данных

Модель отделяет исходные значения от аналитических и физические поступления от
финансовых движений. Имена будущего API предварительные: окончательный JSON
контракт создаётся после ответов программиста 1С.

## 1. Общая схема

```text
DanielSnapshot
    └─ DanielSourceRecord

PRODUCT
    └─ PRODUCT SERIES
           ├─ STOCK SNAPSHOT
           └─ ReceiptSourceRecord

MovementSourceRecord
    ├─ ReceiptSourceRecord
    └─ CostMovementRecord

последний подтверждённый план Daniel + валидные физические приходы
    └─ ArrivalAnalyticalRecord
```

`MovementSourceRecord` сохраняет движение 1С до бизнес-классификации. Записи
приходов и затрат — разные типизированные сущности, а не строки одной плоской таблицы
с искусственными нулями.

Целевая связь справочников и прихода:

```text
/receipts                         /product_series
  product_id ───────────────────→ product_id
  series_id  ───────────────────→ series_id
  container/shipment number       series_name
  receipt_datetime                expiry_date
  quantity                        production_date
                                  gtd_number
                                  country_of_origin
```

`container/shipment number` и `gtd_number` — независимые атрибуты. Cardinality
между ними не определяется до подтверждения 1С.

## 2. Исходные и аналитические значения

| Исходное значение | Аналитическое значение | Правило |
|---|---|---|
| Daniel `SKU Daniel` | `analytical_sku` | Mapping без потери исходного SKU |
| 1С `product_name` | `analytical_sku` | Mapping по стабильным полям товара и источника |
| Исходные quantity/unit | `quantity_pieces` | Преобразование только после определения семантики единицы |
| `daniel_etd` | `expected_arrival_date` | +70 смеси / +14 каши |
| Точная дата | `arrival_week_start` | Понедельник как производный срез |
| Характеристика/ссылка источника | `container_number` | Только после подтверждения семантики 1С |

Исходные значения и ID сохраняются для трассировки; аналитические значения не
перезаписывают их.

## 3. DanielSnapshot

Уровень детализации (grain): одна подтверждаемая версия информации Daniel.

| Поле | Обязательность | Значение | Примечания |
|---|---|---|---|
| `snapshot_id` | Да | Стабильный внутренний ID | Первичный ключ |
| `snapshot_date` | Да | Дата версии информации | Не `mtime` |
| `snapshot_version` | Да | Версия внутри даты | Неявный `v1` нормализуется в `1` |
| `status` | Да | draft/confirmed/rejected | В представлении плана только confirmed |
| `raw_source_file_name` | Да | Исходный файл Daniel | Аудит |
| `normalized_source_file_name` | Да | Нормализованный файл | Аудит |
| `received_at` | Желательно | Время получения | Технические метаданные |
| `confirmed_at` | Желательно | Время подтверждения | Технические метаданные |
| `schema_version` | Желательно | Версия нормализованного контракта | Для миграций |

Последний snapshot определяется как максимальная пара
`(snapshot_date, snapshot_version)` среди `status=confirmed`. Snapshots не
суммируются.

## 4. DanielSourceRecord

Уровень детализации (grain): одна исходная строка normalized Daniel в одном snapshot.

| Поле | Обязательность | Источник | Значение | Допускает null | Примечания |
|---|---|---|---|---|---|
| `daniel_record_id` | Да | Генерируется | Внутренний ID записи | Нет | |
| `snapshot_id` | Да | DanielSnapshot | Связь со snapshot | Нет | |
| `source_row_number` | Да | Excel | Трассировка строки | Нет | Не ключ между snapshots |
| `source_sku` | Да | SKU Daniel | Исходный SKU | Нет | |
| `analytical_sku` | Расчётное | Mapping | Аналитический SKU | Да | |
| `source_quantity` | Да | Daniel | Исходное количество | Нет | Не агрегировать |
| `source_unit` | Да | Daniel | Исходная единица | Нет | |
| `quantity_pieces` | Расчётное | Правила единиц | Количество в штуках | Да | |
| `container_number` | Нет | Daniel | Бизнес-связь | Да | Повторы допустимы |
| `daniel_fill_date` | Нет | FILL | План/уточнение фасовки | Да | Не факт 1С |
| `daniel_etd` | Сейчас да | ETD | Плановая отправка | Технически да | Валидировать |
| `booking_number` | Нет | Booking | Номер booking | Да | |
| `carrier_name` | Нет | Carrier | Перевозчик | Да | |
| `ship_name` | Нет | SHIP | Судно | Да | |
| `expected_arrival_date` | Расчётное | ETD + правило | Точная ожидаемая дата | Да | |
| `arrival_week_start` | Расчётное | Ожидаемая дата | Понедельник недели | Да | |
| `raw_extra_fields` | Нет | Raw-архив | BATCH/неизвестный код | Да | Без семантической интерпретации |

`container_number + source_sku` не уникален. Внутренний tracing key может быть
`snapshot_id + source_row_number`, но сопоставление между snapshots не строится
по номеру строки.

## 5. MovementSourceRecord

Grain должен соответствовать минимальному доступному движению 1С. Предпочтение:

```text
1 movement_id или
1 document_line_id × register movement × product × characteristic × series
```

Точный уровень детализации (grain) требует подтверждения 1С. Исходная запись сохраняется до
классификации и не подменяет null нулём.

| Группа полей | Предварительные поля |
|---|---|
| Идентификация | `movement_id`, `document_id`, `document_line_id` |
| Документ | `document_type`, `document_number`, `document_datetime` |
| Движение | `movement_datetime`, `movement_type`, `source_document_id` |
| Товар | `product_id`, `product_code`, `product_name`, `product_group` |
| Детализация | `characteristic_id/name`, `series_id/number`, `container_number` |
| Количество | `quantity`, `unit_id`, `unit_name` |
| Финансы | `cost_amount`, `vat_amount`, `vat_included_in_cost`, `currency` |
| Участники | `supplier_id/name`, `organization_id/name`, `warehouse_id/name` |
| Жизненный цикл | `posted`, `status`, `deleted`, `cancelled`, `last_modified_at` |
| Срок годности | `production_date`, `expiry_date`, `batch_id/number` |

## 6. ReceiptSourceRecord

Уровень детализации (grain): одна подтверждённая количественная строка физического прихода на минимальном
уровне document line/movement и series, если series детализирует строку.

| Поле | Обязательность | Значение | Допускает null | Примечания |
|---|---|---|---|---|
| `receipt_record_id` | Да | Внутренний ID | Нет | |
| `source_record_id` | Да по смыслу | Стабильный source ID записи | Нет | Реальное имя/состав подтверждает 1С |
| `movement_id` | Предпочтительная модель | Стабильный ID движения | Да, если недоступен | Не утверждается как существующее поле |
| `document_id` | Предпочтительная модель | Стабильный ID документа | Да, если недоступен | Запросить 1С |
| `document_line_id` | Предпочтительная модель | Стабильный ID строки | Да, если недоступен | Запросить 1С |
| `document_type/number` | Да | Исходный документ | Нет | |
| `document_datetime` | Да | Дата документа | Нет | Не считается автоматически временем прихода |
| `movement_datetime` | Да | Дата движения | Нет | Семантика уточняется |
| `receipt_datetime` | Да | Фактический приход на склад | Нет | Поле с бизнес-семантикой |
| `receipt_date` | Расчётное | Календарная дата | Нет | |
| `arrival_week_start` | Расчётное | Понедельник недели | Нет | |
| `product_id/code/name` | Да | Исходный товар | Нет | |
| `analytical_sku` | Расчётное | Нормализованный SKU | Да | |
| `characteristic_id/name` | Желательно | Характеристика | Да | |
| `container_number` | Обязательно по бизнес-правилу | Ссылка на контейнер/поставку | Нет для валидного факта | Невалидные значения сохраняются с ошибкой качества |
| `series_id/number` | SHOULD HAVE | Серия и связь с product_series | Да | Стабильность `series_id` подтверждает 1С |
| `quantity` | Да | Физическое количество | Нет | Не заполнять искусственно |
| `unit_id/name` | Да | Единица | Нет | |
| `warehouse_id/name` | Да | Склад | Нет | |
| `supplier_id/name` | Да | Поставщик | Нет | |
| `organization_id/name` | Да | Организация | Нет | |
| `production_date` | Желательно | Факт производства | Да | |
| `expiry_date` | Обязательно, если хранится и доступно | Фактический срок | Да | Может быть canonical в product_series или control duplicate в receipts |
| `document_validity` | Да по смыслу | Действует/отменён/удалён | Нет | Минимальный набор source fields предлагает 1С |
| `last_modified_at` | Желательно | Инкрементальное обновление | Да, если timestamp недоступен | Допустим эквивалентный update marker |
| `data_quality_status/issues` | Расчётное | Ошибки записи | Нет | Не удаляет запись |

Невалидный container reference (`null`, пусто, `0`, `"0"`) создаёт DQ error и
запрещает автоматическое закрытие Daniel plan, но не удаляет факт.

`series_id` — предпочтительная стабильная связь receipt с
`GET /api/v1/product_series`. Если связь подтверждена, `series_name`,
`expiry_date`, `production_date`, `gtd_number` и `country_of_origin` не требуется
автоматически дублировать в receipts. `receipts.expiry_date` и
`receipts.gtd_number` допустимы на тестовом этапе как duplicated control fields.
При расхождении с `product_series` ingestion сохраняет оба source values и
формирует диагностику.

`gtd_number` не является обязательным полем receipt, business key, technical key
или идентификатором контейнера.

## 7. CostMovementRecord

`CostMovementRecord` относится к FUTURE / OPTIONAL ARCHITECTURE и не блокирует
запуск `GET /api/v1/receipts`. Полноценная cost model потребует также данных
бухгалтерской 1С.

Уровень детализации (grain): одна финансовая/налоговая строка движения на уровне, переданном 1С.

| Поле | Обязательность | Значение | Допускает null | Примечания |
|---|---|---|---|---|
| `cost_movement_record_id` | Да | Внутренний ID | Нет | |
| `movement_id` | Желательно | Стабильный ID движения | Да | |
| `document_id/line_id` | Да | Идентификаторы источника | Нет | |
| `document_type/number/datetime` | Да | Регистратор | Нет | |
| `source_document_id` | Желательно | Связь с приходом/источником | Да | Критично для ГТД |
| `product_id/code/name` | Да | Исходный товар | Нет | |
| `characteristic_id/name` | Желательно | Исходная детализация | Да | |
| `series_id/number` | Желательно | Серия | Да | |
| `container_number` | Желательно | Бизнес-связь | Да | Не технический ключ |
| `counterparty_id/name` | Да | Контрагент | Нет | |
| `quantity` | Из источника | Исходное количество | Да | null сохраняется |
| `cost_amount` | Да для cost movement | Стоимость | Нет | Состав уточняется |
| `vat_amount` | Желательно | НДС | Да | Значение уточняется |
| `vat_included_in_cost` | Желательно | Признак включения | Да | |
| `currency` | Желательно | Валюта | Да | |
| `movement_classification` | Расчётное | GTD/transport/etc. | Нет | По подтверждённому справочнику |
| `posted/status/deleted` | Да | Валидность | Нет | |
| `last_modified_at` | Да | Поток изменений | Нет | |

Финансовые движения не создают физическое quantity и не входят в текущие ARRIVALS KPI.

Для документа «ГТД по импорту» `cost_amount` содержит таможенные начисления,
включая налог, сбор и пошлину, а также НДС при его наличии. `vat_amount` содержит
отдельную сумму НДС там, где он начислен. Эти поля не образуют полную landed cost,
поскольку транспортные, складские и другие расходы находятся в бухгалтерской 1С.
Автоматическое сложение receipt cost и GTD cost как полной себестоимости запрещено.

## 8. ArrivalAnalyticalRecord

Производное представление для reconciliation, KPI и Streamlit. Оно не заменяет
исходные таблицы.

| Поле | Расчёт/источник | Значение |
|---|---|---|
| `record_type` | Классификация | plan / receipt |
| `source_record_id` | Источник | Трассировка |
| `snapshot_id` | Daniel | Версия плана |
| `source_sku` | Источник | Исходный SKU |
| `analytical_sku` | Mapping | SKU для аналитики |
| `container_number` | Источник/валидация | Business key для сопоставления |
| `daniel_fill_date` | Daniel | План производства |
| `daniel_etd` | Daniel | План отправки |
| `expected_arrival_date` | Расчётное | Точная ожидаемая дата |
| `receipt_datetime/date` | 1С | Точный факт |
| `arrival_week_start` | Расчётное | Недельный срез |
| `planned_quantity_pieces` | Daniel | План |
| `received_quantity_pieces` | 1С | Факт |
| `reconciliation_status` | Расчётное | Один из утверждённых статусов |
| `data_quality_status` | Расчётное | Валидность связи |

Агрегация исходных строк Daniel разрешена только в соответствующем аналитическом
представлении. Замещение плана фактом применяется только по валидному container_number.

Связь с `product_series` выполняется по `series_id`, а не по `series_name`,
`expiry_date` или `gtd_number`.

## 9. Стабильные ID и business keys

### Daniel

- `snapshot_id + source_row_number` — ID загрузки/трассировки внутри snapshot.
- Ключ сопоставления между snapshots пока не утверждён.
- `container + SKU` не уникален и не является первичным ключом.

### 1С

Запросить, если объекты существуют:

```text
document_id
document_line_id
movement_id
product_id
characteristic_id
series_id
warehouse_id
supplier_id
organization_id
source_document_id
last_modified_at
```

### Контейнер

`container_number` — бизнес-ключ сопоставления Daniel ↔ 1С, но не замена стабильных ID
1С. Его более общая семантика shipment/delivery reference остаётся открытой.

## 10. Семантика null

- Исходное `null` сохраняется как неизвестное/неприменимое значение.
- `null quantity` не преобразуется в ноль до классификации движения.
- Нулевое физическое движение, отсутствующее количество и неколичественное
  движение — разные состояния.
- Допустимость null и обязательность проверяются отдельно для каждого типа записи.

## 11. Предварительные поля API

### Обязательные поля (MUST HAVE)

```text
stable source record/document ID
document_number
document_type
receipt_datetime
product_id
product_code
product_name
quantity
unit_id
unit_name
warehouse_id
warehouse_name
supplier_id
supplier_name
organization_id
organization_name
container / shipment number (API field name requires 1C confirmation)
document validity fields (minimal source set requires 1C confirmation)
update marker or last_modified_at (if technically available)
expiry availability through stable series_id/product_series
receipts.expiry_date as control duplicate (если технически легко получить)
```

Требуется стабильный технический ID записи, позволяющий повторную загрузку,
upsert, перепроведение и отмену без дублей. `document_id`, `document_line_id` и
`movement_id` — предпочтительная модель, а не заявление, что все три объекта
обязательно существуют в конфигурации 1С.

### Желательные поля (SHOULD HAVE)

```text
document_datetime
movement_datetime
characteristic_id
characteristic_name
movement_id
production_date
series_id
series_number
batch_id
batch_number
cost_amount
vat_amount
vat_included_in_cost
currency
order_id
order_number
source_document_id
source_document_line_id
```

Поля receipt-строки `cost_amount`, `vat_amount`, `vat_included_in_cost` и
`currency` остаются SHOULD HAVE: они сохраняются как source facts, не меняют
quantity и не блокируют запуск receipts, если их получение существенно усложняет
endpoint.

`gtd_number` не входит в обязательные поля receipts. При стабильном `series_id`
предпочтительный canonical candidate — `product_series.gtd_number`; временный
дубликат в receipts разрешён только для тестовой сверки.

### Требуют подтверждения 1С (REQUIRES 1C CONFIRMATION)

- точный grain исходного движения;
- реквизит фактической даты прихода;
- типы физического прихода, возврата и корректировки;
- семантика ссылки на контейнер/поставку;
- связь серии и характеристики;
- состав стоимости и НДС разных документов;
- связь ГТД с поступлением и дополнительными расходами;
- протокол удаления, перепроведения и инкрементальных изменений.

## 12. ОТКРЫТЫЕ ТЕХНИЧЕСКИЕ ВОПРОСЫ И ВОПРОСЫ К 1С

1. Можно ли вернуть стабильный `series_id` в каждой строке physical receipt?
2. Какой grain используется, если один SKU документа имеет несколько series?
3. Где хранится номер контейнера/поставки: в characteristic или другом реквизите?
4. Какой datetime является фактической датой поступления на склад?
5. Какие stable IDs доступны для документа, строки документа и движения прихода?
6. Как API передаёт изменения, отмены, удаления и перепроведение physical receipt?

Canonical `gtd_number`, `expiry_date` и другие атрибуты PRODUCT SERIES
подтверждаются в рамках уже сформулированных вопросов OSG и здесь повторно не
дублируются.
