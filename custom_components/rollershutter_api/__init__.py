"""Intégration Roller Shutter API."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RollerShutterApiClient, RollerShutterApiError
from .const import (
    CONF_API_KEY,
    CONF_API_PATH,
    CONF_SSL,
    DEFAULT_API_PATH,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SSL,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialise l'intégration à partir d'une config entry (UI)."""

    session = async_get_clientsession(hass)
    client = RollerShutterApiClient(
        session=session,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        api_key=entry.data[CONF_API_KEY],
        ssl=entry.data.get(CONF_SSL, DEFAULT_SSL),
        api_path=entry.data.get(CONF_API_PATH, DEFAULT_API_PATH),
    )

    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    async def _async_update_data() -> dict[str, dict[str, Any]]:
        try:
            shutters = await client.async_get_all()
        except RollerShutterApiError as err:
            raise UpdateFailed(f"Erreur lors de la mise à jour: {err}") from err
        return {shutter["name"]: shutter for shutter in shutters}

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=_async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recharge l'intégration si les options changent (ex: scan_interval)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Décharge proprement l'intégration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
