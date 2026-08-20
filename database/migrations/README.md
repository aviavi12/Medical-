# Database migrations

The MVP creates tables directly via `python -m database.init_db` (SQLAlchemy
`create_all`). For production, add Alembic here:

```bash
pip install alembic
alembic init database/migrations
```

and generate revisions from `database/models.py`. The schema is authored for
PostgreSQL; the SQLite dev fallback shares the same models.
