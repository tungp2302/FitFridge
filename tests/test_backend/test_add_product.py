import pytest

from flaskr_new import create_app, db


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / "add_product.sqlite"
    app = create_app({"TESTING": True, "DATABASE": str(database_path)})

    with app.app_context():
        db.init_db()
        db.get_db().execute(
            "INSERT INTO user (username, password) VALUES (?, ?)",
            ("testuser", "pw"),
        )
        db.get_db().commit()

    yield app


def test_add_product_page_renders_server_side_search_form(app):
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 1

        response = client.get("/fridge/add")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    # Server-rendered search: a POST form with the search action, no client JS endpoint.
    assert 'name="action" value="search"' in page
    assert "/api/products/search" not in page
    assert "<script" not in page
