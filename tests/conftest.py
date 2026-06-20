import json
import os
import shutil
import sys
import pytest

# Make project root importable from tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_REAL_VAULT = os.path.join(os.path.dirname(__file__), "..", "data", "secure_health_vault.json")


@pytest.fixture
def vault_path(tmp_path, monkeypatch):
    """Copy the real vault to a temp file and redirect DATA_PATH there.

    Every test that modifies the vault gets a fresh isolated copy so tests
    never affect each other or the live data file.
    """
    dest = tmp_path / "test_vault.json"
    shutil.copy(_REAL_VAULT, dest)

    import mcp_server.server as srv
    monkeypatch.setattr(srv, "DATA_PATH", str(dest))

    # Ensure taken_today starts clean for every test
    vault = json.loads(dest.read_text())
    for member in vault["family_members"].values():
        for item in member.get("schedule", []):
            item["taken_today"] = False
    vault["logs"] = []
    dest.write_text(json.dumps(vault, indent=2))

    return str(dest)
