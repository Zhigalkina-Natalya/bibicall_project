# ARRIVALS: логическая модель данных

Модель отделяет исходные значения от аналитических и физические поступления от
финансовых движений. Имена будущего API предварительные: окончательный JSON
контракт создаётся после ответов программиста 1С.

## 1. Общая схема

```text
DanielSnapshot
    └─ DanielSourceRecord

MovementSourceRecord
    ├─ ReceiptSourceRecord
    └─ CostMovementRecord

последний подтверждённый план Daniel + валидные физические приходы
    └─ ArrivalAnalyticalRecord
```

`MovementSourceRecord` сохраняет движение 1С до бизнес-классификации. Записи
приходов и затрат — разные типизированные сущности, а не строки одной плоской таблицы
с искусственными нулями.

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
| `movement_id` | Желательно | Стабильный ID движения | Да, если недоступен | Запросить 1С |
| `document_id` | Да | Стабильный ID документа | Нет | |
| `document_line_id` | Да | Стабильный ID строки | Нет | |
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
| `series_id/number` | Желательно | Серия | Да | |
| `quantity` | Да | Физическое количество | Нет | Не заполнять искусственно |
| `unit_id/name` | Да | Единица | Нет | |
| `warehouse_id/name` | Да | Склад | Нет | |
| `supplier_id/name` | Да | Поставщик | Нет | |
| `organization_id/name` | Да | Организация | Нет | |
| `production_date` | Желательно | Факт производства | Да | |
| `expiry_date` | Обязательно, если хранится | Фактический срок | Да | Источник истины после прихода |
| `posted/status/deleted` | Да | Валидность | Нет | |
| `last_modified_at` | Да | Инкрементальное обновление | Нет | |
| `data_quality_status/issues` | Расчётное | Ошибки записи | Нет | Не удаляет запись |

Невалидный container reference (`null`, пусто, `0`, `"0"`) создаёт DQ error и
запрещает автоматическое закрытие Daniel plan, но не удаляет факт.

## 7. CostMovementRecord

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
document_id
document_line_id
document_number
document_type
document_datetime
movement_datetime
product_id
product_code
product_name
characteristic_id
characteristic_name
quantity
unit_id
unit_name
warehouse_id
warehouse_name
supplier_id
supplier_name
organization_id
organization_name
posted
status
deleted/cancelled
last_modified_at
expiry_date (если хранится в 1С)
```

### Желательные поля (SHOULD HAVE)

```text
movement_id
receipt_datetime
production_date
series_id
series_number
batch_id
batch_number
container_number
cost_amount
vat_amount
vat_included_in_cost
currency
order_id
order_number
source_document_id
source_document_line_id
```

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

1. Какой регистр и grain предоставляют физический приход?
2. Есть ли стабильный UUID для документа, строки и движения?
3. Какая дата соответствует фактическому поступлению на склад?
4. Где хранится ссылка на контейнер/поставку и может ли она быть `0`/null в
   корректной записи?
5. Где находятся серия, дата производства и срок годности?
6. Как связать финансовое движение с приходом без эвристики по текстовым полям?
7. Какие статусы означают posted, deleted, cancelled и reposted?
8. Как получать инкрементальные изменения и исправленные прошлые периоды?
9. Какой формат manifest snapshot и где хранить raw payload и версию схемы?
