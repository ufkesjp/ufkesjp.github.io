"""Fixtures and collection wiring for the golden-question eval harness.

Loads agent/evals/questions.yml once, exposes a `--subset smoke|full` CLI
flag (default: full), and parametrizes each of the four category test
functions in test_evals.py off of it via pytest_generate_tests — the
standard pytest way to make parametrization depend on a CLI option decided
at collection time.

At the end of the session, pytest_sessionfinish reads whatever results
test_evals.py accumulated in its RESULTS list and writes
eval_boards/data/scorecard.json. If RESULTS is empty (this file's tests
didn't run — e.g. `uv run pytest agent/tests` only), nothing is written.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb
import pytest
import yaml

from data.seed import DB_PATH
from data.seed import main as seed_main
from ontology.schema import load_ontology
from runtime.env import load_dotenv_if_present, make_client

_QUESTIONS_PATH = Path(__file__).parent / "questions.yml"
_QUESTIONS = yaml.safe_load(_QUESTIONS_PATH.read_text())
_SMOKE_IDS = set(_QUESTIONS["smoke"])
_CATEGORIES = ("answerable", "out_of_scope", "ambiguous", "held_out_results")


def pytest_addoption(parser):
    parser.addoption(
        "--subset",
        choices=["smoke", "full"],
        default="full",
        help=(
            "Run only the 5-question smoke subset (default when iterating) "
            "or the full 30 golden questions. Real API calls either way — "
            "this is most of the weekend's budget, so smoke first."
        ),
    )


def pytest_generate_tests(metafunc):
    subset = metafunc.config.getoption("subset")
    for category in _CATEGORIES:
        fixture_name = f"{category}_case"
        if fixture_name not in metafunc.fixturenames:
            continue
        cases = _QUESTIONS[category]
        if subset == "smoke":
            cases = [c for c in cases if c["id"] in _SMOKE_IDS]
        metafunc.parametrize(fixture_name, cases, ids=[c["id"] for c in cases])


@pytest.fixture(scope="session")
def ontology():
    return load_ontology()


@pytest.fixture(scope="session")
def client():
    load_dotenv_if_present()
    return make_client()


@pytest.fixture(scope="session")
def con(tmp_path_factory):
    """A throwaway copy of the committed db, read-write, so eval runs (which
    call propose_action) never leave pending actions in eval_boards.duckdb."""
    if not DB_PATH.exists():
        seed_main()
    tmp_db = tmp_path_factory.mktemp("evals") / "eval_boards.duckdb"
    shutil.copy(DB_PATH, tmp_db)
    connection = duckdb.connect(str(tmp_db))
    yield connection
    connection.close()


def pytest_sessionfinish(session, exitstatus):
    from . import test_evals  # local import: avoid circularity at collection time

    if not test_evals.RESULTS:
        return
    test_evals.write_scorecard(test_evals.RESULTS, subset=session.config.getoption("subset"))
