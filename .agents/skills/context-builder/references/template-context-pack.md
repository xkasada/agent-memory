# Context Pack — {microtask_id}

```yaml
context_pack:
  microtask_id: {MT-02}
  domain: {billing}
  entities: [{Invoice}]
  layers: [{application}, {infrastructure}]
  must_read:
    - .context/INDEX.md
    - .context/domains/{billing}/overview.md
    - .context/entities/{Invoice}.md
  optional:
    - .context/contracts/{billing-auth}.md
  do_not_read:
    - .context/domains/**
    - .context/tech/techstack.md
```

## Why this pack
{1–3 bullets: почему эти файлы и не другие}

## Role hints
- backend: {focus}
- frontend: {focus or n/a}
- devops: {focus or n/a}
