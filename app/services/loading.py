"""The database side of loading: an idempotent upsert into dataset_records.

    INSERT ... ON CONFLICT (dataset_id, row_key) DO UPDATE ... WHERE data IS DISTINCT FROM new data

* A key that does not exist yet is INSERTED.
* A key that exists with different data is UPDATED.
* A key that exists with identical data is left alone (UNCHANGED: no write at all).

So loading the same file twice changes nothing the second time. Everything runs in
the caller's transaction: if anything fails afterwards, nothing was loaded.
"""
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import func, literal_column
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import DatasetRecord


@dataclass
class LoadResult:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0


def upsert_records(
    session: Session, dataset_id: int, chunks: Iterable[list[dict]]
) -> LoadResult:
    """Upsert prepared records, chunk by chunk. Does not commit."""
    table = DatasetRecord.__table__
    result = LoadResult()
    for chunk in chunks:
        rows = [
            {"dataset_id": dataset_id, "row_key": r["row_key"], "data": r["data"]} for r in chunk
        ]
        insert_statement = insert(table).values(rows)
        statement = insert_statement.on_conflict_do_update(
            index_elements=[table.c.dataset_id, table.c.row_key],
            set_={"data": insert_statement.excluded.data, "updated_at": func.now()},
            where=table.c.data.is_distinct_from(insert_statement.excluded.data),
        ).returning(literal_column("(xmax = 0)").label("was_inserted"))

        changed = session.execute(statement).all()  # only inserted and updated rows come back
        inserted = sum(1 for (was_inserted,) in changed if was_inserted)
        result.inserted += inserted
        result.updated += len(changed) - inserted
        result.unchanged += len(rows) - len(changed)
    return result
