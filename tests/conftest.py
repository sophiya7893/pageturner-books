import pytest
from app import app as flask_app
from migrate import migrate


@pytest.fixture
def client(tmp_path):
    database = tmp_path / "test.db"
    migrate(database)
    flask_app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key",
        DATABASE=str(database),
    )
    with flask_app.test_client() as test_client:
        yield test_client
