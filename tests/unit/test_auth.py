from __future__ import annotations

from unittest.mock import MagicMock, patch

from gateway.core.auth import (
    GoogleAccessTokenAuth,
    GoogleIDTokenAuth,
    StaticTokenAuth,
)


class TestStaticTokenAuth:
    async def test_returns_bearer_header(self):
        auth = StaticTokenAuth("my-secret")
        headers = await auth.get_headers()
        assert headers == {"Authorization": "Bearer my-secret"}

    async def test_returns_same_token_every_time(self):
        auth = StaticTokenAuth("fixed")
        h1 = await auth.get_headers()
        h2 = await auth.get_headers()
        assert h1 == h2


class TestGoogleIDTokenAuth:
    @patch("gateway.core.auth.google.oauth2.id_token.fetch_id_token")
    @patch("gateway.core.auth.google.auth.transport.requests.Request")
    async def test_fetches_id_token(self, mock_request_cls, mock_fetch):
        mock_fetch.return_value = "id-token-123"
        auth = GoogleIDTokenAuth(audience="https://agent.run.app")
        headers = await auth.get_headers()
        assert headers == {"Authorization": "Bearer id-token-123"}
        mock_fetch.assert_called_once_with(
            mock_request_cls.return_value, "https://agent.run.app"
        )


class TestGoogleAccessTokenAuth:
    @patch("gateway.core.auth.google.auth.default")
    @patch("gateway.core.auth.google.auth.transport.requests.Request")
    async def test_fetches_access_token(self, mock_request_cls, mock_default):
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.token = "access-token-456"
        mock_default.return_value = (mock_creds, "project-id")

        auth = GoogleAccessTokenAuth()
        headers = await auth.get_headers()
        assert headers == {"Authorization": "Bearer access-token-456"}

    @patch("gateway.core.auth.google.auth.default")
    @patch("gateway.core.auth.google.auth.transport.requests.Request")
    async def test_refreshes_expired_credentials(self, mock_request_cls, mock_default):
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.token = "refreshed-token"
        mock_default.return_value = (mock_creds, "project-id")

        auth = GoogleAccessTokenAuth()
        await auth.get_headers()
        mock_creds.refresh.assert_called_once()

    @patch("gateway.core.auth.google.auth.default")
    @patch("gateway.core.auth.google.auth.transport.requests.Request")
    async def test_custom_scopes(self, mock_request_cls, mock_default):
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.token = "tok"
        mock_default.return_value = (mock_creds, "proj")

        scopes = ["https://www.googleapis.com/auth/custom"]
        GoogleAccessTokenAuth(scopes=scopes)
        mock_default.assert_called_once_with(scopes=scopes)
