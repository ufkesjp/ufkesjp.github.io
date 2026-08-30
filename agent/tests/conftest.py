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
