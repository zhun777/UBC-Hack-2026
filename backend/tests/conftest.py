import os
import tempfile
from pathlib import Path

# Settings are read when config is imported, so set them before importing anything else.
os.environ.update({
    "CHAIN_MODE": "fake",
    "WALLET_MODE": "test",
    "SGD_PER_USD": "1.35",
    "MIN_POINTS_TO_SPEND": "100",
    "WATCHER_INTERVAL_SECONDS": "0.1",
    "DB_PATH": str(Path(tempfile.mkdtemp(prefix="app-backend-tests-")) / "test.db"),
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import chain  # noqa: E402
import config  # noqa: E402
import main  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The API with an empty database, fake chain and a running watcher, fresh for each test."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    chain.get_chain.cache_clear()
    with TestClient(main.app) as test_client:
        yield test_client
    chain.get_chain.cache_clear()
