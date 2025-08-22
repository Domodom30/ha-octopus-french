from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import asyncio
import logging

_LOGGER = logging.getLogger(__name__)

class OctopusCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api, account_number):
        super().__init__(hass, _LOGGER, name="Octopus France", update_interval=asyncio.timedelta(minutes=30))
        self.api = api
        self.account_number = account_number

    async def _async_update_data(self):
        # Récupération
        ledgers = self.api.accounts_and_ledgers()
        electricity = self.api.consumption(self.account_number, "ELECTRICITY")
        gas = self.api.consumption(self.account_number, "GAS")
        invoices = self.api.invoices(self.account_number)

        return {
            "ledgers": ledgers,
            "electricity": electricity,
            "gas": gas,
            "invoices": invoices,
        }
