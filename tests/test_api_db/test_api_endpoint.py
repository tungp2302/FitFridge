from werkzeug.security import generate_password_hash

from flaskr_new import db, fridge_service


def _login(client):
    # create user and set session user_id
    connection = db.get_db()
    cursor = connection.execute(
        "INSERT INTO user (username, password) VALUES (?, ?)",
        ("api-user", generate_password_hash("pw")),
    )
    connection.commit()
    user_id = cursor.lastrowid

    with client.session_transaction() as session:
        session["user_id"] = user_id


def test_api_health(app):
    client = app.test_client()
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_api_post_fridge_requires_auth(app):
    client = app.test_client()
    response = client.post("/api/fridge", json={"query": "3017620422003"})
    assert response.status_code == 401


def test_api_fridge_crud_happy_path(app, monkeypatch):
    with app.app_context():
        monkeypatch.setattr(
            fridge_service,
            "lookup_product",
            lambda query: {
                "name": "Nutella",
                "brand": "Ferrero",
                "barcode": "3017620422003",
                "kcal_per_100g": 539.0,
                "protein_per_100g": 6.3,
                "fat_per_100g": 30.9,
                "carbs_per_100g": 57.5,
                "total_amount": 400.0,
                "unit": "g",
            },
        )

        client = app.test_client()
        _login(client)

        create_resp = client.post("/api/fridge", json={"query": "nutella"})
        assert create_resp.status_code == 201
        created = create_resp.get_json()
        item_id = created["id"]

        list_resp = client.get("/api/fridge")
        assert list_resp.status_code == 200
        assert len(list_resp.get_json()) == 1

        update_resp = client.put(f"/api/fridge/{item_id}", json={"current_amount": 250.0})
        assert update_resp.status_code == 200
        assert update_resp.get_json()["current_amount"] == 250.0

        delete_resp = client.delete(f"/api/fridge/{item_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.get_json()["deleted"] is True