"""scripts/rotate_internal_auth_secret.py (S-06, PT-14 rotation tooling)."""

import importlib.util
from pathlib import Path

import pytest

_SCRIPT_PATH = (
    Path(__file__).parent.parent / "scripts" / "rotate_internal_auth_secret.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "rotate_internal_auth_secret", _SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def rotate_module():
    return _load_script()


class TestRotateScript:
    def test_refuses_to_rotate_with_nothing_to_rotate(
        self, rotate_module, monkeypatch, capsys
    ):
        monkeypatch.setattr(
            "uspto_enriched_citation_mcp.shared_secure_storage.get_internal_auth_secret",
            lambda: None,
        )
        assert rotate_module.main() == 1
        assert "No existing INTERNAL_AUTH_SECRET" in capsys.readouterr().err

    def test_writes_new_comma_old_and_prints_both_steps(
        self, rotate_module, monkeypatch, capsys
    ):
        stored = {}
        monkeypatch.setattr(
            "uspto_enriched_citation_mcp.shared_secure_storage.get_internal_auth_secret",
            lambda: "old-current-secret",
        )

        def _fake_store(secret):
            stored["value"] = secret
            return True

        monkeypatch.setattr(
            "uspto_enriched_citation_mcp.shared_secure_storage.store_internal_auth_secret",
            _fake_store,
        )

        assert rotate_module.main() == 0

        new_value, old_value = stored["value"].split(",")
        assert old_value == "old-current-secret"
        assert new_value != old_value
        assert len(new_value) > 20  # base64 of 32 random bytes

        out = capsys.readouterr().out
        assert f"INTERNAL_AUTH_SECRET={new_value},{old_value}" in out
        assert f"INTERNAL_AUTH_SECRET={new_value}" in out

    def test_a_comma_separated_existing_secret_rotates_only_the_current_one(
        self, rotate_module, monkeypatch, capsys
    ):
        stored = {}
        monkeypatch.setattr(
            "uspto_enriched_citation_mcp.shared_secure_storage.get_internal_auth_secret",
            lambda: "current-secret,stale-secret",
        )
        monkeypatch.setattr(
            "uspto_enriched_citation_mcp.shared_secure_storage.store_internal_auth_secret",
            lambda secret: stored.setdefault("value", secret) or True,
        )

        assert rotate_module.main() == 0

        new_value, old_value = stored["value"].split(",")
        assert old_value == "current-secret"
        assert "stale-secret" not in stored["value"]
