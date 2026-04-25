import os

from flask import Flask

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True) # true tells files are relative to instance folder
    app.config.from_mapping(
        SECRET_KEY='dev', # to keep data safe, override "dev"before publish
        DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite'), #database path
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True) # override def config. can be used for a secret key
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    # a simple page that says hello
    @app.route('/hello') #route for /hello,
    def hello():
        return 'Hello, World!' # what gets shown when visiting url

    from . import db
    db.init_app(app)

    from . import auth
    app.register_blueprint(auth.bp)

    from . import blog
    app.register_blueprint(blog.bp)
    app.add_url_rule('/', endpoint='index')

    return app