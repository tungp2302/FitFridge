import pytest

from flaskr_new import create_app, db
from flaskr_new import app_settings_repo
from flaskr_new.asaai.ollama_client import resolve_ollama_model


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / "app_settings.sqlite"
    app = create_app({"TESTING": True, "DATABASE": str(database_path)})

    with app.app_context():
        db.init_db()
        db.get_db().execute(
            "INSERT INTO user (username, password) VALUES (?, ?)",
            ("testuser", "pw"),
        )
        db.get_db().commit()

    yield app


@pytest.fixture()
def app_context(app):
    with app.app_context():
        yield


def test_app_settings_roundtrip(app_context):
    settings = app_settings_repo.get_settings(1)
    assert settings["llm_model"] == "qwen3.5:latest"

    saved = app_settings_repo.save_settings(1, llm_model="gemma3:1b")
    assert saved["llm_model"] == "gemma3:1b"
    assert app_settings_repo.get_settings(1)["llm_model"] == "gemma3:1b"


def test_resolve_ollama_model_uses_user_setting(app):
    with app.app_context():
        app_settings_repo.save_settings(1, llm_model="qwen3:4b")

    with app.test_request_context("/"):
        from flask import g

        g.user = {"id": 1}
        assert resolve_ollama_model() == "qwen3:4b"


def test_settings_page_saves_llm_model(app):
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 1

        response = client.post(
            "/settings",
            data={"llm_model": "gemma3:1b"},
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert b"Einstellungen gespeichert." in response.data

    with app.app_context():
        assert app_settings_repo.get_settings(1)["llm_model"] == "gemma3:1b"


def test_settings_page_tests_llm_model_success(app, monkeypatch):
    monkeypatch.setattr(
        "flaskr_new.routes.test_ollama_model",
        lambda model: {
            "ok": True,
            "model": model,
            "base_url": "http://127.0.0.1:11434",
            "installed": True,
            "generated": True,
            "installed_models": [model],
            "response": "ok",
        },
    )

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 1

        response = client.post(
            "/settings",
            data={"llm_model": "gemma3:1b", "action": "test_llm"},
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert b"LLM-Test erfolgreich" in response.data
    assert b"gemma3:1b" in response.data
    assert b"Antwortet: ja" in response.data


def test_settings_page_tests_llm_model_failure(app, monkeypatch):
    def fake_test_ollama_model(model):
        raise RuntimeError("Ollama offline")

    monkeypatch.setattr("flaskr_new.routes.test_ollama_model", fake_test_ollama_model)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 1

        response = client.post(
            "/settings",
            data={"llm_model": "gemma3:1b", "action": "test_llm"},
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert b"LLM-Test fehlgeschlagen" in response.data
    assert b"Ollama offline" in response.data
