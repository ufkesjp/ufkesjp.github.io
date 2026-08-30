import shutil

import duckdb
import pytest

from data.seed import DB_PATH
from data.seed import main as seed_main
from ontology.schema import load_ontology


@pytest.fixture(scope="session")
def ontology():
    return load_ontology()


@pytest.fixture(scope="session")
def db_connection():
    if not DB_PATH.exists():
        seed_main()
    con = duckdb.connect(str(DB_PATH), read_only=True)
    yield con
    con.close()


@pytest.fixture
def write_db_connection(tmp_path):
    """A read-write connection to a throwaway copy of the seeded db, so
    tests that propose/approve actions never touch the committed
    eval_boards.duckdb."""
    if not DB_PATH.exists():
        seed_main()
    tmp_db = tmp_path / "test.duckdb"
    shutil.copy(DB_PATH, tmp_db)
    con = duckdb.connect(str(tmp_db))
    yield con
    con.close()
