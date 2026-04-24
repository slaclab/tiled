#!/usr/bin/env python
"""
Generate an Alembic migration for the tiled catalog.

Usage
-----
    uv run python scripts/make_migration.py -m "add_foo_table" --drop-tables foo

How it works
------------
Tiled's initial migration raises NotImplementedError (databases are always
created via ``initialize_database``, never via ``alembic upgrade``).  So the
standard "upgrade to head then autogenerate" approach doesn't work.

Instead this script:

1. Creates a temporary SQLite database via ``initialize_database`` (which
   builds the full current ORM schema including any new tables you just added).
2. Drops the tables you specify with ``--drop-tables`` — those are the *new*
   tables Alembic doesn't know about yet.
3. Stamps the database at the current head revision so Alembic believes it is
   up-to-date.
4. Runs ``alembic revision --autogenerate``, which detects the dropped tables
   as missing and generates CREATE TABLE statements for them.
5. The new migration file is written into
   ``tiled/catalog/migrations/versions/``.

After generation you should also add the new revision ID to ``ALL_REVISIONS``
in ``tiled/catalog/core.py`` (the script will remind you).

The FTS5 shadow tables (``metadata_fts5_*``) are automatically excluded via
the ``include_object`` hook in ``env.py`` so they never appear in the diff.
"""

import argparse
import asyncio
import sys
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Resolve project root relative to this script
REPO_ROOT = Path(__file__).resolve().parent.parent
ALEMBIC_TEMPLATE = REPO_ROOT / "tiled" / "catalog" / "alembic.ini.template"
ALEMBIC_DIR = REPO_ROOT / "tiled" / "catalog" / "migrations"
CORE_PY = REPO_ROOT / "tiled" / "catalog" / "core.py"


def _current_head() -> str:
    """Return the first entry in ALL_REVISIONS (the current migration head)."""
    from tiled.catalog.core import ALL_REVISIONS

    return ALL_REVISIONS[0]


def _write_ini(ini_path: Path, db_uri: str) -> None:
    from tiled.alembic_utils import write_alembic_ini

    write_alembic_ini(ALEMBIC_TEMPLATE, ALEMBIC_DIR, ini_path, db_uri)


async def _setup_db(db_uri: str, drop_tables: list[str]) -> None:
    from tiled.catalog.core import initialize_database

    engine = create_async_engine(db_uri)
    await initialize_database(engine)
    if drop_tables:
        async with engine.begin() as conn:
            for table in drop_tables:
                await conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
                print(f"  Dropped table: {table}")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-m", "--message", required=True, help="Migration message (used in the filename)")
    parser.add_argument(
        "--drop-tables",
        nargs="+",
        default=[],
        metavar="TABLE",
        help="Tables to drop before autogenerate (these are the new tables you added to the ORM)",
    )
    args = parser.parse_args()

    # Lazy import so errors are clear if tiled isn't installed
    try:
        from tiled.catalog.base import Base
    except ImportError:
        print("ERROR: tiled is not installed in the current environment.", file=sys.stderr)
        sys.exit(1)

    head = _current_head()
    print(f"Current migration head: {head}")

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        db_file = td_path / "tiled_autogen.sqlite"
        db_uri = f"sqlite+aiosqlite:///{db_file}"

        print(f"Initializing temp database at {db_file} ...")
        asyncio.run(_setup_db(db_uri, args.drop_tables))

        ini_path = td_path / "alembic.ini"
        _write_ini(ini_path, db_uri)

        cfg = Config(str(ini_path))
        # Inject ORM metadata so env.py can use it for autogenerate
        cfg.attributes["target_metadata"] = Base.metadata

        print(f"Stamping database at revision {head} ...")
        command.stamp(cfg, head)

        print(f"Generating migration: {args.message!r} ...")
        command.revision(cfg, autogenerate=True, message=args.message)

    # Find the newly created file
    versions_dir = ALEMBIC_DIR / "versions"
    files = sorted(versions_dir.glob(f"*_{args.message}.py"), key=lambda p: p.stat().st_mtime)
    if files:
        new_file = files[-1]
        new_rev = new_file.stem.split("_")[0]
        print(f"\nGenerated: {new_file.relative_to(REPO_ROOT)}")
        print(
            f"\nNow add '{new_rev}' to ALL_REVISIONS in tiled/catalog/core.py:\n"
            f"\n    ALL_REVISIONS = [\n"
            f'        "{new_rev}",\n'
            f'        "{head}",\n'
            f"        ...\n"
            f"    ]"
        )
    else:
        print("\nDone. Check tiled/catalog/migrations/versions/ for the new file.")


if __name__ == "__main__":
    main()
