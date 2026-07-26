from unittest.mock import AsyncMock, patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.auth import router


def test_google_login_not_configured():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    with patch("api.routes.auth.GOOGLE_CLIENT_ID", None):
        response = client.post("/auth/google", json={"credential": "some_token"})
        assert response.status_code == 400
        assert response.json()["detail"] == "Google login is not configured"


def test_google_login_invalid_credential():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    with patch("api.routes.auth.GOOGLE_CLIENT_ID", "dummy_client_id"):
        with patch("api.routes.auth.id_token.verify_oauth2_token", side_effect=ValueError("Invalid token")):
            response = client.post("/auth/google", json={"credential": "invalid_token"})
            assert response.status_code == 401
            assert response.json()["detail"] == "Invalid Google credential"


@pytest.mark.asyncio
async def test_google_login_existing_user():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    dummy_user = AsyncMock()
    dummy_user.id = 123
    dummy_user.email = "test@example.com"
    dummy_user.name = "Test User"
    dummy_user.selected_organization_id = 456
    dummy_user.provider_id = "google_123"

    with patch("api.routes.auth.GOOGLE_CLIENT_ID", "dummy_client_id"):
        with patch("api.routes.auth.id_token.verify_oauth2_token", return_value={
            "email": "test@example.com",
            "name": "Test User",
            "sub": "google_123"
        }):
            with patch("api.routes.auth.db_client.get_user_by_email", return_value=dummy_user):
                with patch("api.routes.auth.create_jwt_token", return_value="dummy_jwt_token"):
                    with patch("api.routes.auth.capture_event") as mock_capture:
                        response = client.post("/auth/google", json={"credential": "valid_token"})
                        assert response.status_code == 200
                        data = response.json()
                        assert data["token"] == "dummy_jwt_token"
                        assert data["user"]["email"] == "test@example.com"
                        assert data["user"]["id"] == 123
                        mock_capture.assert_called_once()


@pytest.mark.asyncio
async def test_google_login_new_user():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    new_user = AsyncMock()
    new_user.id = 999
    new_user.email = "new@example.com"
    new_user.name = "New User"
    new_user.provider_id = "google_999"
    new_user.selected_organization_id = 888

    organization = AsyncMock()
    organization.id = 888
    organization.provider_id = "org_google_999"

    with patch("api.routes.auth.GOOGLE_CLIENT_ID", "dummy_client_id"):
        with patch("api.routes.auth.id_token.verify_oauth2_token", return_value={
            "email": "new@example.com",
            "name": "New User",
            "sub": "google_999"
        }):
            with patch("api.routes.auth.db_client.get_user_by_email", return_value=None):
                with patch("api.routes.auth.db_client.create_user_with_email", return_value=new_user) as mock_create_user:
                    with patch("api.routes.auth.db_client.get_or_create_organization_by_provider_id", return_value=(organization, True)):
                        with patch("api.routes.auth.db_client.add_user_to_organization") as mock_add:
                            with patch("api.routes.auth.db_client.update_user_selected_organization") as mock_select:
                                with patch("api.routes.auth.create_user_configuration_with_mps_key", return_value=None):
                                    with patch("api.routes.auth.create_jwt_token", return_value="new_jwt_token"):
                                        with patch("api.routes.auth.capture_event"):
                                            response = client.post("/auth/google", json={"credential": "valid_token"})
                                            assert response.status_code == 200
                                            data = response.json()
                                            assert data["token"] == "new_jwt_token"
                                            assert data["user"]["email"] == "new@example.com"
                                            mock_create_user.assert_called_once_with(
                                                email="new@example.com",
                                                password_hash="",
                                                name="New User"
                                            )
                                            mock_add.assert_called_once()
                                            mock_select.assert_called_once()
