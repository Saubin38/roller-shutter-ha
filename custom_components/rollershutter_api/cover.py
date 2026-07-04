"""Plateforme cover pour l'intégration Roller Shutter API."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .api import RollerShutterApiClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_AIRING = "airing"
SERVICE_INTERMEDIATE_POSITION = "intermediate_position"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée les entités cover à partir du coordinator déjà initialisé."""

    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: DataUpdateCoordinator = data["coordinator"]
    client: RollerShutterApiClient = data["client"]

    known_names: set[str] = set()

    def _add_new_entities() -> None:
        new_names = set(coordinator.data or {}) - known_names
        if not new_names:
            return
        known_names.update(new_names)
        async_add_entities(
            RollerShutterCoverEntity(coordinator, client, name, entry.entry_id)
            for name in new_names
        )

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))

    # Services personnalisés : airing (aération) et position intermédiaire.
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(SERVICE_AIRING, {}, "async_airing")
    platform.async_register_entity_service(
        SERVICE_INTERMEDIATE_POSITION, {}, "async_intermediate_position"
    )


class RollerShutterCoverEntity(CoordinatorEntity, CoverEntity):
    """Représente un volet roulant piloté via l'API."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        client: RollerShutterApiClient,
        name: str,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._client = client
        self._shutter_name = name
        self._attr_unique_id = f"{entry_id}_{name}"
        self._attr_name = name

    @property
    def _data(self) -> dict[str, Any] | None:
        """Retourne les dernières données connues pour ce volet."""
        return (self.coordinator.data or {}).get(self._shutter_name)

    @property
    def available(self) -> bool:
        return super().available and self._data is not None

    @property
    def current_cover_position(self) -> int | None:
        """L'API utilise déjà la convention HA : 0 = fermé, 100 = ouvert."""
        data = self._data
        if data is None or data.get("closePercent") is None:
            return None
        return int(data["closePercent"])

    @property
    def is_closed(self) -> bool | None:
        data = self._data
        if data is None or data.get("closePercent") is None:
            return None
        return int(data["closePercent"]) >= 100

    @property
    def is_closing(self) -> bool | None:
        data = self._data
        return bool(data.get("isActionInProgress")) if data else None

    @property
    def is_opening(self) -> bool | None:
        # L'API ne distingue pas ouverture/fermeture en cours, seulement
        # "action en cours". On ne peut donc pas différencier les deux ici.
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._data or {}
        return {
            "room": data.get("room"),
            "exposure": data.get("exposure"),
            "type": data.get("type"),
            "close_time": data.get("closeTime"),
            "current_position_raw": data.get("currentPosition"),
        }

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._client.async_open(self._shutter_name)
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._client.async_close(self._shutter_name)
        await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._client.async_stop(self._shutter_name)
        await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        position = kwargs[ATTR_POSITION]
        await self._client.async_set_close_percent(self._shutter_name, position)
        await self.coordinator.async_request_refresh()

    async def async_airing(self) -> None:
        """Service personnalisé : entrouvre le volet pour aérer."""
        await self._client.async_airing(self._shutter_name)
        await self.coordinator.async_request_refresh()

    async def async_intermediate_position(self) -> None:
        """Service personnalisé : place le volet en position intermédiaire."""
        await self._client.async_intermediate_position(self._shutter_name)
        await self.coordinator.async_request_refresh()
