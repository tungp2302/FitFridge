"""Repository-Funktionen fuer die Fridge-/Dashboard-Daten."""

from ..db import get_db


def list_items():
    return get_db().execute(
        "SELECT p.id, title, body, created, author_id, username"
        " FROM post p JOIN user u ON p.author_id = u.id"
        " ORDER BY created DESC"
    ).fetchall()


def get_item(item_id):
    return get_db().execute(
        "SELECT p.id, title, body, created, author_id, username"
        " FROM post p JOIN user u ON p.author_id = u.id"
        " WHERE p.id = ?",
        (item_id,),
    ).fetchone()


def create_item(title, body, author_id):
    db = get_db()
    db.execute(
        "INSERT INTO post (title, body, author_id) VALUES (?, ?, ?)",
        (title, body, author_id),
    )
    db.commit()


def update_item(item_id, title, body):
    db = get_db()
    db.execute(
        "UPDATE post SET title = ?, body = ? WHERE id = ?",
        (title, body, item_id),
    )
    db.commit()


def delete_item(item_id):
    db = get_db()
    db.execute("DELETE FROM post WHERE id = ?", (item_id,))
    db.commit()
