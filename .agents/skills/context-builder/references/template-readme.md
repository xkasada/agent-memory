# {Название проекта}

## Описание
{Краткое описание назначения и функциональности}

## Стек
- {Язык} {версия}
- {Фреймворк} {версия}
- {Другие ключевые зависимости}

## Структура
```
{src/, lib/, app/}/
├── {папка/файл}  # {назначение}
└── ...
```

## Запуск (Windows PowerShell)
```powershell
{команды установки и запуска, например: py -3 -m venv .venv; docker compose up -d}
```

## AI Context (partitioned)

Primary router: `.context/INDEX.md`

- Domains: `.context/domains/<domain>/overview.md`
- Entities: `.context/entities/<Entity>.md`
- Layers: `.context/layers/*.md`
- Contracts: `.context/contracts/*.md`
- Tech: `.context/tech/techstack.md`
- Packs: `.context/packs/<microtask_id>.md`

Do not load the whole `.context/` tree — follow the pack for the current microtask.
