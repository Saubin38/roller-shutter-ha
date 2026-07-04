"""Client HTTP pour l'API RollerShutter (Spring Boot)."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import async_timeout

from .const import API_KEY_HEADER, REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class RollerShutterApiError(Exception):
    """Erreur générique lors d'un appel à l'API."""


class RollerShutterApiAuthError(RollerShutterApiError):
    """Erreur d'authentification (401/403)."""


class RollerShutterApiClient:
    """Client asynchrone pour le RollerShutterActionController."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        api_key: str,
        ssl: bool = False,
        api_path: str = "/api/rhollershutter",
    ) -> None:
        self._session = session
        scheme = "https" if ssl else "http"
        self._base_url = f"{scheme}://{host}:{port}{api_path}"
        self._api_key = api_key

    @property
    def _headers(self) -> dict[str, str]:
        return {API_KEY_HEADER: self._api_key} if self._api_key else {}

    async def _request(self, method: str, path: str) -> Any:
        url = f"{self._base_url}{path}"
        try:
            async with async_timeout.timeout(REQUEST_TIMEOUT):
                async with self._session.request(
                    method, url, headers=self._headers
                ) as resp:
                    if resp.status in (401, 403):
                        raise RollerShutterApiAuthError(
                            f"Authentification refusée ({resp.status}) sur {url}"
                        )
                    if resp.status >= 400:
                        text = await resp.text()
                        raise RollerShutterApiError(
                            f"Erreur API {resp.status} sur {url}: {text}"
                        )
                    if resp.content_type == "application/json":
                        return await resp.json()
                    return await resp.text()
        except RollerShutterApiError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise RollerShutterApiError(
                f"Impossible de contacter l'API ({url}): {err}"
            ) from err

    # --- Lecture ---

    async def async_get_all(self) -> list[dict[str, Any]]:
        """Récupère l'état de tous les volets."""
        result = await self._request("GET", "/all")
        return result or []

    # --- Actions par nom ---

    async def async_open(self, name: str) -> dict[str, Any]:
        return await self._request("PUT", f"/open/name/{name}")

    async def async_close(self, name: str) -> dict[str, Any]:
        return await self._request("PUT", f"/close/name/{name}")

    async def async_stop(self, name: str) -> dict[str, Any]:
        return await self._request("PUT", f"/stop/name/{name}")

    async def async_airing(self, name: str) -> dict[str, Any]:
        return await self._request("PUT", f"/airing/name/{name}")

    async def async_intermediate_position(self, name: str) -> dict[str, Any]:
        return await self._request("PUT", f"/intermediatePosition/name/{name}")

    async def async_set_close_percent(self, name: str, percent: int) -> dict[str, Any]:
        """percent: 0 = ouvert, 100 = fermé (convention de l'API)."""
        percent = max(0, min(100, int(percent)))
        return await self._request("PUT", f"/closePercent/name/{name}/{percent}")
