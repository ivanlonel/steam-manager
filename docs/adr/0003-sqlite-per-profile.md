# One SQLite database per profile

The application is installed by people who should not have to run a database server, and its
workload is mixed: per-app refresh in place, the user's own edits, and foreign keys across about
seventy tables. Each profile therefore gets its own SQLite file, accessed only through
SQLAlchemy, holding both the catalog and that account's data so that foreign keys and stored
views can span them.

## Considered options

- DuckDB: better at whole-catalog aggregation, but its SQLAlchemy dialect is third-party, Alembic
  support is thin and row-by-row updates are its weak side. It can still read a profile, by
  attaching the SQLite file or through the Parquet export.
- PostgreSQL: the most capable engine, but every user would have to install and run a server.
- Several accounts in one database with a shared catalog: saves disk when accounts share a PC,
  but every view needs an account filter and per-account view columns stop being possible.

## Consequences

- A second account on the same machine stores its own copy of the catalog.
- SQLite cannot alter tables freely, which is one reason Steam tables are rebuilt rather than
  migrated (see ADR 0002).
