# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

import google.auth
import google.auth.transport.requests
import google.oauth2.id_token

logger = logging.getLogger(__name__)

_DEFAULT_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


class AuthProvider(Protocol):
    async def get_headers(self) -> dict[str, str]: ...


class GoogleIDTokenAuth:
    def __init__(self, audience: str) -> None:
        self._audience = audience
        self._request = google.auth.transport.requests.Request()

    async def get_headers(self) -> dict[str, str]:
        token = await asyncio.to_thread(
            google.oauth2.id_token.fetch_id_token,
            self._request,
            self._audience,
        )
        return {"Authorization": f"Bearer {token}"}


class GoogleAccessTokenAuth:
    def __init__(self, scopes: list[str] | None = None) -> None:
        self._scopes = scopes or _DEFAULT_SCOPES
        self._credentials, _ = google.auth.default(scopes=self._scopes)
        self._request = google.auth.transport.requests.Request()

    async def get_headers(self) -> dict[str, str]:
        if not self._credentials.valid:
            await asyncio.to_thread(self._credentials.refresh, self._request)
        return {"Authorization": f"Bearer {self._credentials.token}"}


class StaticTokenAuth:
    def __init__(self, token: str) -> None:
        self._token = token

    async def get_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}
