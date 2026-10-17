
import pytest
from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key",
        WTF_CSRF_ENABLED=False,
    )

    with flask_app.test_client() as client:
        yield client


def test_login_page_opens(client):
    response = client.get("/login")
    assert response.status_code == 200


def test_forgot_password_page_opens(client):
    response = client.get("/forgot-password")
    assert response.status_code == 200


def test_invalid_reset_token_redirects(client):
    response = client.get(
        "/reset-password/invalid-test-token",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/forgot-password" in response.headers["Location"]



def test_logout_clears_session(client):
    # Set up a logged-in session
    with client.session_transaction() as session:
        session["user_id"] = 123
        session["user_name"] = "Test User"
        session["role"] = "customer"

    # Fetch a page to obtain a CSRF token, if your app exposes one
    page = client.get("/")
    assert page.status_code == 200

    with client.session_transaction() as session:
        csrf_token = session.get("_csrf_token")

    # Submit logout with the CSRF token
    headers = {}
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token

    response = client.post(
        "/logout",
        headers=headers,
        follow_redirects=False,
    )

    assert response.status_code == 302

    with client.session_transaction() as session:
        assert "user_id" not in session
        assert "user_name" not in session
        assert "role" not in session
