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

    from .asaai import routes_asaai
    app.register_blueprint(routes_asaai.asaai_bp)

    from .meal_tracker_repo import ensure_schema as ensure_meal_tracker_schema
    from .fridge_repo import ensure_schema as ensure_fridge_schema
    from .app_settings_repo import ensure_schema as ensure_app_settings_schema
    with app.app_context():
        ensure_fridge_schema()
        ensure_meal_tracker_schema()
        ensure_app_settings_schema()

    from .routes import bp as frontend_bp
    app.register_blueprint(frontend_bp)

    return app
