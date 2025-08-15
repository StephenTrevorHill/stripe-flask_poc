import os, tempfile, uuid, pytest
from app import create_app
from app.extensions import db

@pytest.fixture()
def app():
    # Use a temporary SQLite DB file per test session for isolation
    db_fd, db_path = tempfile.mkstemp()
    os.close(db_fd)
    os.environ["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    os.environ["STRIPE_API_KEY"] = "sk_test_dummy"
    os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_dummy"

    app = create_app()
    app.config.update(
        TESTING=True,
    )

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
    os.unlink(db_path)

@pytest.fixture()
def client(app):
    return app.test_client()
