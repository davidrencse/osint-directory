import pytest

from app.core import store


@pytest.fixture(autouse=True)
def temp_store(tmp_path):
    store.use_database(tmp_path / "test.db")
    yield
