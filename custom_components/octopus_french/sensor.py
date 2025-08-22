from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api import OctopusFrenchAPI
from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=30)

async def async_setup_entry(hass, entry, async_add_entities):
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    api = OctopusFrenchAPI(username, password)
    await hass.async_add_executor_job(api.login)

    async def async_update_data():
        try:
            accounts = await hass.async_add_executor_job(api.accounts_ledgers)
            account_number = accounts["data"]["viewer"]["accounts"][0]["number"]

            elec = await hass.async_add_executor_job(api.consumption, account_number, "ELECTRICITY")
            gas = await hass.async_add_executor_job(api.consumption, account_number, "GAS")

            return {
                "accounts": accounts,
                "consumption_elec": elec,
                "consumption_gas": gas,
            }
        except Exception as err:
            raise UpdateFailed(err)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="octopus_french",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    entities = [
        OctopusFrenchSensor(coordinator, "monthly_bill", "Facture totale mensuelle (€)"),
        OctopusFrenchSensor(coordinator, "elec_consumption", "Conso Électricité (kWh)"),
        OctopusFrenchSensor(coordinator, "gas_consumption", "Conso Gaz (kWh)"),
    ]

    async_add_entities(entities)

class OctopusFrenchSensor(SensorEntity):
    def __init__(self, coordinator, sensor_type, name):
        self.coordinator = coordinator
        self._attr_name = name
        self.sensor_type = sensor_type

    @property
    def native_value(self):
        data = self.coordinator.data
        if not data:
            return None

        if self.sensor_type == "monthly_bill":
            ledgers = data["accounts"]["data"]["viewer"]["accounts"][0]["ledgers"]
            return sum(l["balance"] for l in ledgers) / 100  # en €
        if self.sensor_type == "elec_consumption":
            conso = data["consumption_elec"]["data"]["accountConsumption"]["consumption"]
            return sum(c["consumption"] for c in conso)
        if self.sensor_type == "gas_consumption":
            conso = data["consumption_gas"]["data"]["accountConsumption"]["consumption"]
            return sum(c["consumption"] for c in conso)
        return None

    @property
    def should_poll(self):
        return False

    async def async_update(self):
        await self.coordinator.async_request_refresh()
