import logging
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

def configure_logging(app):
    # Simple JSON-ish structured logs
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '{"level": "%(levelname)s", "msg": "%(message)s", "name": "%(name)s"}'
    )
    handler.setFormatter(formatter)
    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(handler)
