from flask import Flask


def create_app():
    app = Flask(__name__)

    from app.api.routes import api
    app.register_blueprint(api)

    return app