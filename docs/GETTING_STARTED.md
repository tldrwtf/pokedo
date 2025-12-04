# Getting Started (Developer)

Prereqs:

- Python 3.11+, pip
- Docker (for postgres) — optional for server dev

Install:
Windows cmd.exe:

```
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

Run CLI examples:

```
python -m pokedo.cli.app init-db
python -m pokedo.cli.app add-task "Finish report" --category work --difficulty medium
python -m pokedo.cli.app add-pokemon "Starter"
```

Run server (dev):

```
uvicorn pokedo.server:app --reload --port 8000
```

Run tests:

```
pytest -q
```

Notes:

- The repo uses a local-first SQLite DB for the CLI; if you start Postgres (via docker-compose), set `DATABASE_URL` accordingly.
