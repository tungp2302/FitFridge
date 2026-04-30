"""Fachlogik fuer den Fridge-Bereich von FitFridge."""

from ...api_db.repositories import fridge_repo


def list_dashboard_items():
    return fridge_repo.list_items()


def get_dashboard_item(item_id):
    return fridge_repo.get_item(item_id)


def create_dashboard_item(title, body, author_id):
    fridge_repo.create_item(title, body, author_id)


def update_dashboard_item(item_id, title, body):
    fridge_repo.update_item(item_id, title, body)


def delete_dashboard_item(item_id):
    fridge_repo.delete_item(item_id)
