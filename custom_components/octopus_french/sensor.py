"""Octopus French – Minimal authentication sensor with detailed logs."""

from __future__ import annotations

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from datetime import datetime

from .utils.logger import LOGGER
from .lib.octopus_french import OctopusFrench


class OctopusDummySensor(SensorEntity):
    """Capteur dummy pour forcer l’exécution des logs."""

    def __init__(self):
        self._state = None
        self._name = "Octopus Dummy"

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    async def async_update(self):
        self._state = datetime.now().isoformat()
        LOGGER.debug("[OctopusFR] Capteur dummy mis à jour : %s", self._state)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up Octopus French sensors (authentication only) with detailed logs."""
    email = entry.data.get("email")
    password = entry.data.get("password")


    LOGGER.info("[OctopusFR] Création du client pour %s", email)

    client = OctopusFrench(
        email=email,
        password=password,
        session=async_get_clientsession(hass),
    )

    LOGGER.info("[OctopusFR] Tentative de login...")
    login_success = await client.login()

    if not login_success:
        LOGGER.error("[OctopusFR] Impossible de se connecter pour %s", email)
        return

    LOGGER.info("[OctopusFR] Login réussi pour %s", email)

    LOGGER.info("[OctopusFR] Récupération des comptes...")
    accounts = await client.accounts()

    if not accounts:
        LOGGER.warning("[OctopusFR] Aucun compte récupéré pour %s", email)
        return

    LOGGER.info("[OctopusFR] Comptes récupérés : %s", accounts)

    async_add_entities([OctopusDummySensor()])
    LOGGER.info("[OctopusFR] Capteur dummy créé pour test de logs")
