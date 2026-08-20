# ОСГ: логическая модель данных

Модель описывает бизнес-смысл полей независимо от Excel. Названия API являются
предварительными до получения реального JSON.

## Source fields

Source fields должны сохранять значения и идентификаторы 1С без аналитического
переименования.

| Поле | Смысл | Current Excel | Статус |
|---|---|---|---|
| `stock_date` | Реальная дата состояния снимка | Надёжного поля нет | **OPEN DECISION / API required** |
| `warehouse_id` | Стабильный ID склада | Нет | API field |
| `warehouse_name` | Название склада | `Склад` | Mapped |
| `product_id` | Стабильный ID товара 1С | Нет | API field |
| `product_code` | Код/артикул товара | Нет | API field |
| `product_name` | Исходное название, Source SKU | `Номенклатура` | Mapped |
| `product_group` | Исходная группа 1С | `Номенклатурная группа` | Mapped |
| `characteristic_id` | ID характеристики | Нет | API field |
| `characteristic_name` | Название характеристики | `Характеристика номенклатуры` | Partly mapped |
| `series_id` | ID серии/партии | Нет | **OPEN DECISION** |
| `series_name` | Название/номер серии | Нет отдельного поля | **OPEN DECISION** |
| `expiry_date` | Срок годности партии | `Срок годности` | Mapped |
| `production_date` | Дата производства | Нет | Optional API field |
| `shelf_life_days` | Полный срок жизни в днях | Сейчас вычисляется Python | API priority open |
| `quantity_total` | Общий остаток | первое `В ед. хранения` | Mapped |
| `quantity_reserved` | Зарезервированное количество | второе `В ед. хранения` | Mapped, null open |
| `quantity_free` | Свободное количество | третье `В ед. хранения` | Mapped, null open |
| `unit_id` | ID единицы измерения | Нет | API field |
| `unit` | Единица измерения | Не выделена | API field |
| `organization_id` | ID организации | Нет | API field |
| `organization_name` | Название организации | Нет | API field |

После API `product_id` должен стать основным стабильным идентификатором товара.
Наименование нельзя использовать как единственный технический primary key:
названия меняются и содержат технические варианты.

## Normalized fields

| Поле | Текущая колонка | Назначение |
|---|---|---|
| Source SKU | `SKU_исходный` | Неизменённое название для traceability |
| Analytical SKU | `SKU` | Подтверждённое нормализованное имя для аналитики |
| Source Category | `Категория_исходная` | Исходная группа 1С |
| Analytical Category | `Категория` | Категория после правил BIBICALL |
| Warehouse name | `Склад` | Текущее отображаемое имя склада |
| Characteristic/container | `Контейнер` | Текущее текстовое представление характеристики |
| Expiry date | `Срок годности` | Распознанная календарная дата |
| Source expiry | `Срок годности_исходная` | Исходное значение для диагностики парсинга |
| Weight | `Вес` | Вес, извлечённый из Analytical SKU или специального правила |
| Shelf life days | `total_days` | Legacy Python rule; целевое имя `shelf_life_days` |

Analytical values применяются в фильтрах и сводках. Source values сохраняются и
не должны исчезать при нормализации.

## Calculated fields

| Поле | Формула/источник |
|---|---|
| `days_left` | `expiry_date - calculation_date` в календарных днях |
| `OSG %` | `days_left / shelf_life_days × 100` |
| `Risk level` | Единая шкала из `OSG_BUSINESS_RULES.md` |
| `Reserve share %` | `quantity_reserved / quantity_total × 100` |

При нулевом denominator доля резерва остаётся пустой. Семантика `null` quantities
не подменяется автоматически.

## Идентификация строк и агрегирование

- Детальная запись должна сохранять source identifiers склада, товара,
  характеристики и серии/партии, а также expiry date.
- Аналитическое агрегирование не заменяет первичный ключ хранения.
- Текущий предполагаемый duplicate key
  `Склад + Analytical SKU + Контейнер + Срок годности` используется только для
  диагностики и не утверждён как business key.
- Сводка ОСГ агрегирует подтверждённые технические варианты по Analytical SKU,
  сохраняя необходимые измерения конкретного представления.

## OPEN DECISION

1. **Characteristic/container:** всегда ли `characteristic_name` является
   контейнером или включает другие характеристики товара.
2. **Reserved null:** ноль или неизвестное значение.
3. **Free null:** ноль или неизвестное значение.
4. **Series/batch:** какие поля определяют серию и партию и чем они отличаются от
   характеристики и срока годности.
5. **Duplicate policy:** окончательный business key и допустимость повторов.
6. **Shelf life priority:** авторитетность API-поля относительно справочника и
   legacy fallback.
7. **Stock date:** формат ожидается `YYYY-MM-DD`, но реальная семантика должна быть
   подтверждена ответом 1С.
