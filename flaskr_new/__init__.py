import os

from flask import Flask


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev",
        DATABASE=os.path.join(app.instance_path, "flaskr.sqlite"),
    )

    if test_config is None:
        app.config.from_pyfile("config.py", silent=True)
    else:
        app.config.from_mapping(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    from . import db
    db.init_app(app)

    # Uni-Projekt: Daten muessen Neustarts nicht ueberleben. Wir setzen das
    # Schema bei jedem Start frisch auf (mit DROP), damit es immer exakt zu
    # schema.sql passt. Waehrend der Laufzeit ist die Datei-DB persistent und
    # fuer mehrere Accounts geteilt. Anschliessend kommt der demo/demo-Account
    # mit Beispieldaten rein (im Test-Modus nicht, damit Tests sauber starten).
    with app.app_context():
        db.init_db()
        if not app.config.get("TESTING"):
            from . import seed
            seed.seed_demo_data()

    from .routes import bp as frontend_bp
    app.register_blueprint(frontend_bp)

    return app
