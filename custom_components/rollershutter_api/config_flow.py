"""Config flow pour Roller Shutter API."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigEntry, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RollerShutterApiAuthError, RollerShutterApiClient, RollerShutterApiError
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

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_API_PATH, default=DEFAULT_API_PATH): cv.string,
    }
)


class RollerShutterApiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Gère le flux de configuration depuis l'UI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Première (et seule) étape : hôte, port, clé API."""
        errors: dict[str, str] = {}

        if user_input is not None:
            unique_id = f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            client = RollerShutterApiClient(
                session=session,
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                api_key=user_input[CONF_API_KEY],
                ssl=user_input[CONF_SSL],
                api_path=user_input[CONF_API_PATH],
            )

            try:
                await client.async_get_all()
            except RollerShutterApiAuthError:
                errors["base"] = "invalid_auth"
            except RollerShutterApiError as err:
                _LOGGER.debug("Connexion échouée lors du config_flow: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Roller Shutter API ({user_input[CONF_HOST]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return RollerShutterApiOptionsFlow(config_entry)


class RollerShutterApiOptionsFlow(OptionsFlow):
    """Permet d'ajuster la fréquence de rafraîchissement après coup."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self._config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=current): cv.positive_int,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
