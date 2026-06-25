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

    with app.app_context():
        db.init_db()
        if not app.config.get("TESTING"):
            from . import seed
            seed.seed_demo_data()

    from .routes import bp as frontend_bp
    app.register_blueprint(frontend_bp)

    from .asaai import routes_asaai
    app.register_blueprint(routes_asaai.asaai_bp)

    return app
