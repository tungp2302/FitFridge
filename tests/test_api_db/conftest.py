from pathlib import Path

import pytest

from flaskr_new import create_app
from flaskr_new import db


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / "test.sqlite"
    app = create_app({"TESTING": True, "DATABASE": str(database_path)})

    with app.app_context():
        db.init_db()

    yield app


@pytest.fixture()
def app_context(app):
    with app.app_context():
        yield
