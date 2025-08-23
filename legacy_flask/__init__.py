import os  # noqa: F401
from flask import Flask
from .config import Config
from .extensions import db, migrate, configure_logging
from . import models  # noqa: F401

from .webhooks.routes import webhooks_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config())

    # init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    configure_logging(app)

    # blueprints
    app.register_blueprint(webhooks_bp, url_prefix="/webhooks")

    @app.get("/healthz")
    def healthz():
        return {"ok": True}, 200

    return app
