from flaskr_new import fridge_service


def test_update_dashboard_item_logs_consume_delta(monkeypatch):
    calls = []

    monkeypatch.setattr(fridge_service.fridge_repo, "get_item", lambda item_id: {"product_id": 7, "current_amount": 120, "unit": "g", "name": "Milk", "brand": "Brand"})
    monkeypatch.setattr(fridge_service.fridge_repo, "update_amount", lambda item_id, current_amount: 1)
    monkeypatch.setattr(fridge_service.product_repo, "update_product", lambda product_id, name, brand: 0)
    monkeypatch.setattr(fridge_service, "log_consume", lambda product_id, amount, unit, note=None: calls.append(("consume", product_id, amount, unit, note)) or 11)
    monkeypatch.setattr(fridge_service, "log_refill", lambda product_id, amount, unit, note=None: calls.append(("refill", product_id, amount, unit, note)) or 12)

    fridge_service.update_dashboard_item(3, current_amount=90, unit="g")

    assert calls == [("consume", 7, 30.0, "g", "update_dashboard_item consume delta")]


def test_update_dashboard_item_logs_refill_delta(monkeypatch):
    calls = []

    monkeypatch.setattr(fridge_service.fridge_repo, "get_item", lambda item_id: {"product_id": 7, "current_amount": 120, "unit": "g", "name": "Milk", "brand": "Brand"})
    monkeypatch.setattr(fridge_service.fridge_repo, "update_amount", lambda item_id, current_amount: 1)
    monkeypatch.setattr(fridge_service.product_repo, "update_product", lambda product_id, name, brand: 0)
    monkeypatch.setattr(fridge_service, "log_consume", lambda product_id, amount, unit, note=None: calls.append(("consume", product_id, amount, unit, note)) or 11)
    monkeypatch.setattr(fridge_service, "log_refill", lambda product_id, amount, unit, note=None: calls.append(("refill", product_id, amount, unit, note)) or 12)

    fridge_service.update_dashboard_item(3, current_amount=150, unit="g")

    assert calls == [("refill", 7, 30.0, "g", "update_dashboard_item refill delta")]
