# ОСГ: целевая логическая модель данных

Модель описывает бизнес-смысл данных независимо от legacy Excel. Это TARGET
MODEL, а не утверждённая физическая схема БД или окончательный JSON contract.
Имена, типы, nullable и связи подтверждаются по реальному ответу 1С.

## Логические сущности и связи

```text
PRODUCT
  product_id
      │
      ├──────────────→ BARCODE
      │                 product_id
      │                 characteristic_id (optional)
      │
      └──────────────→ PRODUCT SERIES
                        series_id + product_id
                              │
                              ↓
                         STOCK SNAPSHOT
                         product_id + series_id
                         + warehouse_id + stock_date
```

Это схема связей, а не объявление составных primary keys. Физические ключи и
кардинальности пока не подтверждены.

- `product_id` — предпочтительный стабильный идентификатор товара.
- `series_id` — предпочтительный ключ связи stock row с объектом «Серия
  номенклатуры».
- Наименования товара и серии не используются как единственные технические ключи.
- При отсутствии или нестабильности `series_id` требуется отдельное решение 1С.

## A. STOCK SNAPSHOT

Назначение `GET /api/v1/stocks`: срез остатков на реальную `stock_date`.

### Core stock fields

- `stock_date`
- `warehouse_id`
- `product_id`
- `quantity_total`
- `quantity_reserved`
- `quantity_free`
- `unit`

### Linking fields

- `product_id`
- `characteristic_id`
- `series_id`
- `organization_id`
- `warehouse_id`

### Control/test duplicates

- `product_code`
- `product_name`
- `product_group`
- `warehouse_name`
- `characteristic_name`
- `series_name`
- `expiry_date`
- `organization_name`

### Полный предложенный состав stocks

| Поле | Роль | Комментарий |
|---|---|---|
| `stock_date` | Core | Реальная дата состояния снимка |
| `warehouse_id` | Core/link | Стабильная ссылка на склад |
| `warehouse_name` | Control duplicate | Читаемая сверка склада |
| `product_id` | Core/link | Ссылка на PRODUCT |
| `product_code` | Control duplicate | Код для тестовой сверки |
| `product_name` | Control duplicate | Source SKU для traceability |
| `product_group` | Control duplicate | Исходная группа товара |
| `characteristic_id` | Link | Ссылка на характеристику, если используется |
| `characteristic_name` | Control duplicate | Current usage: номер контейнера |
| `series_id` | Link | Предпочтительная ссылка на PRODUCT SERIES |
| `series_name` | Control duplicate | Читаемая сверка серии |
| `expiry_date` | Control/candidate source | Может дублировать PRODUCT SERIES |
| `production_date` | Candidate source | Логическая принадлежность требует проверки |
| `shelf_life_days` | Candidate source | Может принадлежать PRODUCT или серии |
| `quantity_total` | Core | Общий остаток |
| `quantity_reserved` | Core | Зарезервированное количество; null open |
| `quantity_free` | Core | Свободное количество; null open |
| `unit_id` | Link | ID единицы измерения |
| `unit` | Core | Единица измерения |
| `organization_id` | Link | ID организации |
| `organization_name` | Control duplicate | Читаемая сверка организации |

`expiry_date`, `production_date` и `shelf_life_days` не удаляются из stocks на
этапе тестирования: их дублирование полезно для визуальной сверки и диагностики.
Canonical source определяется позже.

## B. PRODUCT

Назначение `GET /api/v1/products`: справочник номенклатуры и карточки SKU.

Ожидаемые ключевые поля включают `product_id`, `product_code`, `product_name`,
`product_group` и атрибуты карточки товара. `product_id` должен стать стабильной
ссылкой для STOCK, PRODUCT SERIES и BARCODE.

`products.country_of_origin`, если поле приходит, означает общий/справочный
атрибут карточки товара. Оно не считается автоматически равным стране конкретной
серии.

## C. BARCODE

Назначение `GET /api/v1/barcodes`: связь товара и штрихкодов.

- обязательная логическая ссылка: `product_id`;
- `characteristic_id` может участвовать, если штрихкод зависит от характеристики;
- окончательная кардинальность и уникальность barcode подтверждаются JSON.

## D. PRODUCT SERIES

Назначение `GET /api/v1/product_series`: справочник серий номенклатуры и данные
прослеживаемости, которые не должны перегружать каждую stock row.

### Identity/linking

- `series_id`
- `product_id`
- `characteristic_id`

### Human-readable control

- `series_name`
- `product_code`
- `product_name`
- `characteristic_name`

### Traceability

- `series_serial_number`
- `certificate_number`
- `certificate_date`
- `expiry_date`
- `gtd_number`
- `country_of_origin`

### Status

- `deletion_mark`
- `is_active`

`series_serial_number` может быть `null`, если для товарной группы серийный номер
не используется. `gtd_number` ожидаемо может быть `null` для российского товара.

### GTD

В терминологии 1С необходимо различать два разных объекта:

- **«ГТД по импорту БР... от ...»** — документ движения 1С, связанный с
  таможенными начислениями, пошлиной и финансовым движением. Это не номер ГТД
  товара и не physical receipt.
- **`gtd_number` / «Номер ГТД»** — номер таможенной декларации импортированного
  товара. Потенциально это source attribute серии номенклатуры или импортной
  партии.

Предпочтительное место `gtd_number` в TARGET model —
`GET /api/v1/product_series`. Для российского товара значение может быть `null`.
Один номер декларации потенциально может повторяться у нескольких SKU, серий,
сроков годности и контейнеров, если товары оформлялись одной декларацией. Поэтому
неподтверждённая cardinality не используется в модели.

Ни документ «ГТД по импорту», ни `gtd_number` не используются как `series_id`,
technical key, business key серии/контейнера, характеристика или контейнер.
`gtd_number` не участвует в расчёте ОСГ.

Если stocks также возвращает `gtd_number`, это duplicated control field.
Canonical/source-of-truth предпочтительно связывается с `product_series` только
после подтверждения модели программистом 1С.

### Country of origin

- `products.country_of_origin` — общий справочный атрибут товара;
- `product_series.country_of_origin` — атрибут конкретной серии, если именно так
  он хранится в 1С.

Эти значения не взаимозаменяются автоматически. Их canonical priority — TARGET
SEMANTICS / TO VERIFY.

## Canonical fields и control duplicates

На первом этапе одинаковые читаемые поля могут намеренно приходить в нескольких
endpoint: `product_name`, `product_code`, `characteristic_name`, `expiry_date`.

- **Canonical/source-of-truth field** — поле сущности, признанной владельцем
  атрибута после проверки 1С.
- **Duplicated control field** — копия для сверки ссылок и диагностики; она не
  должна молча перезаписывать canonical value.

При несовпадении дубликатов ingestion обязан сохранить оба source value и выдать
диагностику, а не выбирать победителя без правила.

Предварительно `expiry_date` логически предпочтительно относится к фактической
PRODUCT SERIES, если STOCK имеет стабильный `series_id`. Однако до JSON это
**OPEN DECISION — API FIELD PRIORITY**, а stocks.expiry_date остаётся допустимым
контрольным/временным источником.

## Current normalized и calculated fields

| Текущая колонка | Независимый смысл |
|---|---|
| `SKU_исходный` | Source SKU для traceability |
| `SKU` | Analytical SKU |
| `Категория_исходная` | Source product group |
| `Категория` | Analytical Category |
| `Контейнер` | Current business usage характеристики как контейнера |
| `Срок годности` | Parsed expiry date |
| `total_days` | Legacy `shelf_life_days` |
| `days_left` | `expiry_date - calculation_date` |
| `ОСГ %` | `days_left / shelf_life_days × 100` |
| `Риск` | Уровень по единой шкале ОСГ |
| `Доля резерва, %` | `reserved / total × 100` |

### Current Excel mapping

До перехода на API legacy adapter получает:

| Excel source | Текущий нормализованный смысл |
|---|---|
| `Склад` | `warehouse_name` |
| `Номенклатура` | Source SKU / `product_name` |
| `Номенклатурная группа` | Source category / `product_group` |
| `Характеристика номенклатуры` | `characteristic_name`, сейчас отображается как контейнер |
| `Срок годности` | `expiry_date` |
| три колонки `В ед. хранения` | total / reserved / free в установленном порядке |

Excel не содержит надёжных `product_id`, `series_id`, `warehouse_id` и реальную
`stock_date`. Поэтому legacy-сопоставление по текстовым значениям не переносится
в target API как правило идентификации.

### Идентификация и агрегирование

- Детальная запись должна сохранять source identifiers и source values товара,
  склада, характеристики, серии и срока годности.
- Аналитическое агрегирование не заменяет первичный ключ хранения.
- Текущий предполагаемый duplicate key
  `Склад + Analytical SKU + Контейнер + Срок годности` используется только для
  диагностики и не объявляется target business key.
- Правила аналитического groupby остаются бизнес-представлением поверх
  нормализованных данных, а не способом связывания API-сущностей.

## Characteristic, product series и container

Эти понятия нельзя смешивать:

```text
product
  → characteristic (если используется)
      → product series
          → stock
```

- Characteristic — объект/измерение 1С со своим `characteristic_id`.
- Product series — отдельный объект со своим `series_id` и traceability data.
- Container — текущий бизнес-смысл, который сейчас берётся из
  `characteristic_name`.
- GTD не является characteristic, series ID или container.

**CURRENT BUSINESS USAGE:** `characteristic_name` используется как номер
контейнера в Excel-контуре.

**TARGET API / OPEN DECISION:** программист 1С должен подтвердить, что
характеристика всегда и однозначно соответствует контейнеру.

## OPEN DECISION

1. Доступен ли стабильный `series_id` объекта 1С.
2. Всегда ли `characteristic_name` соответствует контейнеру.
3. Точная связь `characteristic ↔ product series`.
4. Может ли одна серия относиться к нескольким характеристикам.
5. Canonical `expiry_date`: stocks или product_series.
6. Canonical `shelf_life_days`: product, product_series или stocks.
7. Источник и принадлежность `production_date`.
8. Priority для `country_of_origin`.
9. Семантика и nullable `series_serial_number`.
10. Семантика сертификата и связь certificate с серией.
11. Место хранения, формат, nullable semantics и cardinality `gtd_number`.
12. Null semantics `quantity_reserved` и `quantity_free`.
13. Окончательный business key и duplicate policy.
14. Реальная семантика `stock_date`.
15. Точная JSON schema, типы и nullable.
16. Pagination и `meta/count`.
17. Target storage model.

## REQUIRES FOLLOW-UP WITH 1C DEVELOPER

1. Подтвердить стабильность и формат `series_id`, а также его наличие в stocks.
2. Подтвердить кардинальность `product ↔ characteristic ↔ series`.
3. Уточнить, является ли `expiry_date` реквизитом серии и одинаково ли он
   заполняется в stocks и product_series.
4. Уточнить источник `production_date`: поле включено в stocks, но отсутствует в
   согласованном перечне product_series.
5. Уточнить источник `shelf_life_days`: поле включено в stocks, но пока не
   закреплено за products или product_series.
6. Уточнить, могут ли `deletion_mark` и `is_active` противоречить друг другу и
   какое поле является canonical status.
7. Подтвердить nullable и формат certificate, GTD и country-of-origin fields.
8. Подтвердить, где хранится `gtd_number`, является ли он реквизитом серии,
   может ли одна series иметь один `gtd_number` и может ли один `gtd_number`
   относиться к нескольким series.
