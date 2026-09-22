# DB Schema

> Not always-read. Prefer domain-local persistence notes in `domains/<domain>/overview.md` / `entities/*`.
> Keep a global schema only if many domains share one DB — and put it under `.context/tech/db-schema.md` or domain infra notes.
> Include in a pack only when the microtask touches persistence.

## Тип БД
{PostgreSQL / MySQL / MongoDB / Redis / etc.} {версия}

## Таблицы / Коллекции

### {table_name}
| Поле | Тип | Nullable | Default | Описание |
|------|-----|----------|---------|----------|
| id | SERIAL/UUID | No | auto | PK |
| | | | | |

## Связи
- {Table1}.{field} → {Table2}.{field} ({тип связи})

## Индексы
| Таблица | Поля | Тип | Описание |
|---------|------|-----|----------|
| | | | |

## Ограничения
- UNIQUE: {список}
- CHECK: {список}
- FK: {список}

## Миграции
| Миграция | Назначение | Дата |
|----------|------------|------|
| 001_init | {описание} | {дата} |

## Правила чтения/записи
- {Что и как читаем}
- {Что и как пишем}
- {Кэширование}