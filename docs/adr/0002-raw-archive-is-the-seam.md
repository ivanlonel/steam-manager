# The raw archive sits between every source and the database

A full catalog takes four to six hours to download, Steam adds fields without notice, and the
notebooks this project grew out of found loader bugs only after the fact. So a source never
writes to the database: it only stores raw answers in the raw archive, and one loader turns
archived answers into rows. A sync, a rebuild and an import of Kaggle files are therefore the
same code path, and a loader or schema fix is applied by replaying the archive instead of
downloading again.

## Considered options

- Load directly and keep the archive as a side copy: fewer steps per sync, but the Kaggle import
  and the rebuild become separate loaders that can drift from the main one.
- Map answers onto ORM objects and merge them: least code, far too slow for 200,000 apps across
  more than sixty tables.

## Consequences

- Steam tables are never migrated: after a schema change they are dropped and rebuilt from the
  archive. Only tables holding the user's own data go through Alembic migrations.
- The archive roughly doubles the disk a profile needs; it can be deleted at the cost of
  downloading again after the next loader change.
