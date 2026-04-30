import sqlite3
from datetime import datetime

import click
from flask import current_app, g    # g is a unique object for each request

def init_app(app):
    app.teardown_appcontext(close_db)   # call function when cleanig up after response
    app.cli.add_command(init_db_command)    # adds new command

def init_db():
    db = get_db()

    with current_app.open_resource('schema.sql') as f:      #open file relative to flaskr package
        db.executescript(f.read().decode('utf8'))

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(     # connection to DATABASE conf key
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row  # return rows like dicts, allows collumn access by name

    return g.db

def close_db(e=None):       # closes existing connection
    db = g.pop('db', None)

    if db is not None:
        db.close()

@click.command('init-db')
def init_db_command():
    """Vorhandene Daten loeschen und neue Tabellen anlegen."""
    init_db()
    click.echo('Initialized the database.')

sqlite3.register_converter(     # tells python how to interpret database values
    "timestamp", lambda v: datetime.fromisoformat(v.decode())
)