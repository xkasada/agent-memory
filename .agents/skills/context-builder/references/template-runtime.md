# Runtime — {project_name}

## How to run locally (Windows PowerShell)
```powershell
{commands}
```

## Services
| Service | Port | Image/path | Healthcheck |
|---------|------|------------|-------------|
| api | {8000} | {…} | {/health} |
| db | {5432} | postgres | |
| redis | {6379} | redis | |

## Compose / CI pointers
- Compose: `{docker-compose.yml}`
- CI: `{.gitlab-ci.yml}` (runner OS may be Linux; host is Windows)

## Env (non-secret descriptions)
| Variable | Required | Description |
|----------|----------|-------------|
| DATABASE_URL | yes | |

## Notes for devops pack
- Prefer this file + infrastructure layer over business entity docs
- Local commands: PowerShell / `py -3` / `docker compose`
