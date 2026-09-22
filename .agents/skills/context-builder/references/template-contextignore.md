# .contextignore
# Paths ignored when discovering code for context partitions.
# This does NOT mean agents never read tests — only scaffolding defaults.

# Generated / vendor
node_modules/
dist/
build/
__pycache__/
*.pyc
.venv/
vendor/
target/
coverage/

# IDE / VCS
.idea/
.vscode/
.git/
.DS_Store
Thumbs.db

# Secrets / local env
.env
.env.*
*.pem
*.key

# Logs / local data
*.log
logs/
*.sqlite
*.db

# Heavy binaries / assets
*.png
*.jpg
*.pdf
*.zip
