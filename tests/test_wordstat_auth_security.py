from pathlib import Path

from src import wordstat_auth


class _TokenResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "access_token": "synthetic-wordstat-secret-token",
            "expires_in": 3600,
        }


def test_wordstat_exchange_does_not_persist_or_print_access_token(monkeypatch, tmp_path, capsys):
    synthetic_module_path = tmp_path / "wordstat_auth.py"
    synthetic_module_path.write_text("# synthetic module path\n", encoding="utf-8")
    monkeypatch.setattr(wordstat_auth, "__file__", str(synthetic_module_path))
    monkeypatch.setattr(wordstat_auth.requests, "post", lambda *_args, **_kwargs: _TokenResponse())
    monkeypatch.setattr(wordstat_auth.config, "client_id", "synthetic-client")
    monkeypatch.setattr(wordstat_auth.config, "client_secret", "synthetic-secret")

    token = wordstat_auth.exchange_code_for_token("synthetic-code")

    output = capsys.readouterr().out
    assert token == "synthetic-wordstat-secret-token"
    assert token not in output
    assert not (tmp_path / "wordstat_token.json").exists()


def test_repository_does_not_contain_wordstat_token_file():
    repository_root = Path(__file__).resolve().parents[1]

    assert not (repository_root / "src" / "wordstat_token.json").exists()
