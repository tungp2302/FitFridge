import sqlite3
from datetime import datetime

import click
from flask import current_app, g

def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

def init_db():
    db = get_db()

    with current_app.open_resource("schema.sql") as file:
        db.executescript(file.read().decode("utf8"))

# Kerntabellen, die nicht von einem eigenen Repo-Modul migriert werden.
# Definitionen muessen mit schema.sql uebereinstimmen; schema.sql bleibt das
# Werkzeug fuer einen kompletten Reset (init-db), diese Anweisungen machen die
# App ohne init-db lauffaehig.
_CORE_SCHEMA = """
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    brand TEXT NOT NULL,
    barcode TEXT UNIQUE NOT NULL,
    kcal_per_100g REAL NOT NULL,
    protein_per_100g REAL NOT NULL,
    fat_per_100g REAL NOT NULL,
    carbs_per_100g REAL NOT NULL,
    expiry_date DATE,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fridge_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_id INTEGER NOT NULL,
    current_amount REAL NOT NULL,
    unit TEXT NOT NULL,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user (id),
    FOREIGN KEY (product_id) REFERENCES product (id)
);

CREATE TABLE IF NOT EXISTS consumption_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    event_type TEXT CHECK(event_type IN ('consume','refill')) NOT NULL,
    amount REAL NOT NULL,
    unit TEXT,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    note TEXT,
    FOREIGN KEY (product_id) REFERENCES product (id)
);
"""

def ensure_core_schema():
    """Legt user/product/fridge_item/consumption_log an, falls sie fehlen."""
    db = get_db()
    db.executescript(_CORE_SCHEMA)
    db.commit()

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

@click.command("init-db")
def init_db_command():
    """Vorhandene Daten loeschen und neue Tabellen anlegen."""
    init_db()
    click.echo("Initialized the database.")

sqlite3.register_converter(
    "timestamp", lambda value: datetime.fromisoformat(value.decode())
)
