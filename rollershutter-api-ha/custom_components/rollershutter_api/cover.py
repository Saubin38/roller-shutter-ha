"""Plateforme cover pour l'intégration Roller Shutter API."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    PLATFORM_SCHEMA,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import RollerShutterApiClient, RollerShutterApiError
from .const import (
    CONF_API_KEY,
    CONF_API_PATH,
    CONF_SSL,
    DEFAULT_API_PATH,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_AIRING = "airing"
SERVICE_INTERMEDIATE_POSITION = "intermediate_position"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_API_PATH, default=DEFAULT_API_PATH): cv.string,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Initialise la plateforme cover à partir de configuration.yaml."""

    session = async_get_clientsession(hass)
    client = RollerShutterApiClient(
        session=session,
        host=config[CONF_HOST],
        port=config[CONF_PORT],
        api_key=config[CONF_API_KEY],
        ssl=config[CONF_SSL],
        api_path=config[CONF_API_PATH],
    )

    async def _async_update_data() -> dict[str, dict[str, Any]]:
        try:
            shutters = await client.async_get_all()
        except RollerShutterApiError as err:
            raise UpdateFailed(f"Erreur lors de la mise à jour: {err}") from err
        # Indexé par nom pour un accès rapide depuis chaque entité
        return {shutter["name"]: shutter for shutter in shutters}

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=_async_update_data,
        update_interval=timedelta(seconds=config[CONF_SCAN_INTERVAL]),
    )

    # Plateforme configurée via YAML (pas de config entry) : on force
    # simplement un premier rafraîchissement des données.
    await coordinator.async_refresh()

    if coordinator.data is None:
        _LOGGER.warning(
            "Aucune donnée reçue de l'API à l'initialisation, "
            "les volets apparaîtront dès que l'API répondra."
        )

    entities = [
        RollerShutterCoverEntity(coordinator, client, name)
        for name in (coordinator.data or {})
    ]
    async_add_entities(entities)

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
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        client: RollerShutterApiClient,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._client = client
        self._shutter_name = name
        self._attr_unique_id = f"{DOMAIN}_{name}"
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
        """HA: 0 = fermé, 100 = ouvert. L'API: 0 = ouvert, 100 = fermé."""
        data = self._data
        if data is None or data.get("closePercent") is None:
            return None
        return 100 - int(data["closePercent"])

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
        ha_position = kwargs[ATTR_POSITION]
        api_percent = 100 - ha_position
        await self._client.async_set_close_percent(self._shutter_name, api_percent)
        await self.coordinator.async_request_refresh()

    async def async_airing(self) -> None:
        """Service personnalisé : entrouvre le volet pour aérer."""
        await self._client.async_airing(self._shutter_name)
        await self.coordinator.async_request_refresh()

    async def async_intermediate_position(self) -> None:
        """Service personnalisé : place le volet en position intermédiaire."""
        await self._client.async_intermediate_position(self._shutter_name)
        await self.coordinator.async_request_refresh()
