---
name: context-builder
description: >-
  Строит и поддерживает партиционированный проектный контекст в memory-vault:
  тонкий INDEX-router, domains/entities/layers/contracts как raw-заметки
  Raw/Projects/<project>/, узкие context_pack под микротаски. Активировать при
  создании/обновлении контекста, decompose фичи, выборе «что читать» агенту.
  Цель — не грузить весь проект, а адресный pack (как partition prune).
  Хранилище — источник правды; .context/ в репозитории не ведётся (кроме packs).
  Не использовать для написания прикладного кода.
---

# Context Builder (Partitioned Context, vault-native)

Цель скилла: агент по задаче сразу знает **какой узкий контекст читать**, а не
сканирует весь репозиторий.

Метафора: дерево поиска / partition prune (HDFS) — сначала выбираем partition,
потом читаем только его + тонкий корневой индекс.

## Где живёт контекст

- **Источник правды — memory-vault** (MCP): `Wiki/Projects/<project>/` (скомпилировано)
  и `Raw/Projects/<project>/` (raw-заметки).
- Запись/чтение — только через `vault_*` (см. `context-curator`).
- В репозитории проекта `.context/` **не ведётся** — ни INDEX, ни domains.
  Единственный локальный артефакт — `context_pack`:
  `.context/packs/<microtask_id>.md` (самодостаточный бандл с **встроенным
  содержимым** из vault, не список путей).

## Host OS

Скилл под **Windows PowerShell** (`py -3` / `python`). Папки —
`New-Item -ItemType Directory -Force`, `Test-Path`. Не использовать `mkdir -p`,
`ls`, `cat`, `python3`.

## When to use

- Новый проект / legacy → создать проектный контекст в vault (`ensure`)
- Фича большая → нужна карта доменов перед decompose
- `sys-analyst` пишет микротаску → нужен `context_pack` (`serve`)
- Контекст раздулся / AI читает не то → переразбить партиции (`recut`)
- После изменений домена / после цикла микротаски → обновить заметки (`sync`/`refresh`)

## When NOT to use

- Чтобы сгенерировать один гигантский "CONTEXT.md" «на всё»
- Чтобы заменить TZ / TASK_BOARD / STATE
- Чтобы документировать каждую функцию в коде

## Целевая структура (в vault)

```text
Raw/Projects/<project>/          # raw-заметки (пишет context-curator через MCP)
  INDEX.md                       # тонкий router
  tech/
    techstack.md
    runtime.md
  domains/<domain>.md            # ГЛАВНАЯ ось (business), dense 100–300 строк
  entities/<Entity>.md           # точечный lookup → где живёт
  layers/<layer>.md              # вторичная ось (поперечный срез)
  contracts/<a>-<b>.md           # границы между доменами
Wiki/Projects/<project>/         # компилируется project-ingest (не редактировать руками)
```

Типы (`kind` для `vault_stage_note`): `index`/`context` (верхний уровень),
`domain`→`domains/`, `entity`→`entities/`, `layer`→`layers/`, `contract`→`contracts/`,
`tech`→`tech/`, `module`→`modules/`, `artifact`→`artifacts/`, либо имя папки.

## Partitioning rules (обязательные)

1. **Главная ось = business domain / bounded context**, не папки репозитория слепо.
2. **Вторичная ось = layer** (`presentation` | `application` | `domain` | `infrastructure`).
3. **Entities** — точечный lookup, не дамп всей модели.
4. **Чужой домен** читают только через `contracts/*`, не его `overview` целиком.
5. Leaf domain: **~100–300 строк**. Больше — дели домен (split partition).
6. `INDEX`: **< ~100 строк**. Только router + карта.
7. Microtask pack: обычно **3–7 источников**, не весь проект.
8. Не плодить крошечные файлы по 10 строк без нужды.
9. Dense markdown: таблицы, пути, инварианты; без воды.

### Как резать большую систему

1. Выдели 3–9 доменов по бизнес-возможностям (`auth`, `billing`, `export`…).
2. Если домен толстый — дели сначала по sub-capability, не по слоям.
3. Слой добавляй как фильтр внутри домена / по роли агента.
4. Сущности с overlap → явно укажи owner-domain + contract.

## Agent load protocol (для любого агента mesh)

1. Прочитай `context_pack` микротаски (из TZ / `.context/packs/<id>.md`).
2. Нужны детали — `vault_search_catalog` → `vault_read_note` по конкретным заметкам.
3. **Stop** — не читай соседние домены «на всякий случай».

### Role defaults (вторичный фильтр)

| Роль | Добавить к domain pack | Обычно не читать |
|------|------------------------|------------------|
| sys-analyst | domain, entities, contracts | глубокий infra dump |
| tester | domain + AC-related entities, contracts | unrelated domains |
| backend | domain, `application`/`domain`/`infrastructure`, entities | `presentation` без нужды |
| frontend | domain, `presentation`, API contracts | `db`/infra internals |
| devops | `infrastructure`, `tech/runtime`, compose/CI | business entity details |
| reviewer | pack микротаски + затронутые contracts | весь проект |
| docs-writer | pack + INDEX | secrets/runtime internals |

## Context Pack format (inline content)

Pack — самодостаточный: исполнитель читает его без доступа к vault.

```markdown
# context_pack: MT-02
domain: billing
entities: [Invoice, Customer]
layers: [application, infrastructure]
role: backend
sources: [Domain Billing, Entity Invoice, Layer Application]

## Domain: Billing
<выжимка релевантного содержимого>

## Entity: Invoice
<поля, инварианты, где живёт>

## Layer: Application
<как устроен слой в этом домене>
```

Правила pack:

- Заголовки `sources` — для провенанса ([[wikilink]]-заголовки заметок).
- Пак **не ссылается на пути**, а **содержит** нужный контекст.
- `do_not_read`-защита сохраняется на уровне инструкции исполнителю.
- pack составляет **sys-analyst** вместе с `context-curator` (`serve`);
  curator отдаёт файл, analyst финализирует в TZ.
- implement/review агенты следуют pack, а не «исследуют репо».

## Recipe

### Mode A — Bootstrap (новый / пустой контекст)

1. Оцени размер и стек (README, compose, package.json/pyproject, дерево).
2. `vault_stage_note`: `INDEX`, 1–3 ключевых `domain`, нужные `entity`, `tech`.
3. `vault_project_ingest(<project>)`.
4. Проверь: по INDEX агент отвечает «куда идти за X» без чтения всего.

### Mode B — Partition / re-cut (система уже большая)

1. Прочитай текущий проектный контекст (`vault_read_project`).
2. Предложи карту доменов (3–9) и owner entities.
3. Пере-стейджи монолиты по `domains/`, `entities/`, `contracts/`.
4. Сделай INDEX тонким router.

### Mode C — Pack for microtask (основной режим mesh)

Вход: `microtask_id`, title/goal, optional owners.

1. Найди релевантные заметки (`vault_search_catalog` + `vault_read_project`).
2. Прочитай их (`vault_read_note`); определи `domain`, `entities[]`, `layers[]`.
3. Собери inline-бандл (3–7 источников) и запиши `.context/packs/<microtask_id>.md`.
4. Если заметок нет — стейджи stub и пометь `TBD`, не выдумывай факты.

### Mode D — Sync / refresh after change

1. Обнови затронутый domain/entity/contract (`vault_stage_note`, перезапись).
2. `vault_project_ingest(<project>)`.
3. Не переписывай все партиции.

## Legacy scripts (deprecated)

Скрипты старой `.context/`-модели (`collect_context.py`,
`scaffold_context_tree.py`, `resolve_context_pack.py`, `generate_full_context.py`)
больше не используются: контекст пишется в vault через MCP. Оставлять `.context/`
дерево в репозитории не нужно.

## Validation checklist

- [ ] В vault есть `Raw/Projects/<project>/INDEX.md` (router) или явный TBD stub
- [ ] Каждый домен на доске фичи имеет заметку или явный TBD
- [ ] Нет обязательного чтения «всего проекта»
- [ ] У микротаски есть `.context/packs/<id>.md` с **встроенным** контентом
- [ ] Frontend-pack не тащит db-schema; backend-pack не тащит весь presentation
- [ ] Cross-domain только через `contracts/`
- [ ] Версии стека указаны в `tech/techstack.md`
- [ ] После серии записей вызван `vault_project_ingest`

## Important Rules

- **Partition first, read second**
- **Один pack — одна микротаска**
- **INDEX всегда дешёвый**
- **Не выдумывать домены/сущности** — либо код/доки, либо TBD
- **Vault — источник правды; `.context/` в репо — только packs**
- **Минимум воды**

## Mesh integration

- `context-curator`: `ensure`/`sync`/`serve`/`refresh`/`recut` (владелец контекста)
- `sys-analyst` / decompose: опирается на проектный INDEX; в каждую микротаску
  пишет `domain`, `entities[]`, `layers[]`
- `sys-analyst` / microtask-tz: финализирует `context_pack` (inline) в TZ
- implement / tester / reviewer / devops: читают pack, не делают full-repo discovery
- `team-lead`: в Task указывает `microtask_id` и обязательность следования pack
