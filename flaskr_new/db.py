import sqlite3
from datetime import datetime

import click
from flask import current_app, g


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(exception=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()


# schema.sql ist die einzige Quelle der Tabellen-Definitionen (alles als
# CREATE TABLE IF NOT EXISTS). apply_schema() legt beim App-Start fehlende
# Tabellen an, ohne Daten zu loeschen; init_db() verwirft vorher alles und
# baut die DB komplett neu auf (kompletter Reset, auch in den Tests).
_DROP_TABLES = """
DROP TABLE IF EXISTS fridge_item;
DROP TABLE IF EXISTS meal_tracker_entry;
DROP TABLE IF EXISTS meal_tracker_settings;
DROP TABLE IF EXISTS app_settings;
DROP TABLE IF EXISTS product;
DROP TABLE IF EXISTS user;
"""


def apply_schema():
    db = get_db()
    with current_app.open_resource("schema.sql") as file:
        db.executescript(file.read().decode("utf8"))
    db.commit()


def init_db():
    db = get_db()
    db.executescript(_DROP_TABLES)
    db.commit()
    apply_schema()


@click.command("init-db")
def init_db_command():
    """Vorhandene Daten loeschen und alle Tabellen neu anlegen."""
    init_db()
    click.echo("Initialized the database.")


sqlite3.register_converter(
    "timestamp", lambda value: datetime.fromisoformat(value.decode())
)
