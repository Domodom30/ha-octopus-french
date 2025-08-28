"""The Octopus French integration."""

from datetime import datetime
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SCAN_INTERVAL, CONF_EMAIL, CONF_PASSWORD
from .utils.logger import LOGGER

PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Octopus French from a config entry."""
    
    coordinator = OctopusFrenchDataUpdateCoordinator(
        hass,
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
    )
    
    await coordinator.async_config_entry_first_refresh()
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

class OctopusFrenchDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Octopus French data."""

    def __init__(self, hass, email, password):
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        
        self.email = email
        self.password = password
        self.api = None
        self.account_number = None
        self.electricity_point_id = None
        self.gas_point_id = None

    async def _async_update_data(self):
        """Fetch data from Octopus French API."""
        from .lib.octopus_french import OctopusFrench
        
        if self.api is None:
            self.api = OctopusFrench(self.email, self.password)
            if not await self.api.login():
                raise Exception("Failed to login to Octopus French")
        
        try:
            data = await self.api.account()
            
            # Store account info for first time
            if not self.account_number:
                self.account_number = data.get("account_number")
                self.electricity_point_id = data.get("electricity_point_id")
                self.gas_point_id = data.get("gas_point_id")
            
            # Les données sont déjà traitées par octopus_spain.py, on les utilise directement
            return {
                "account_number": self.account_number,
                "electricity_point_id": self.electricity_point_id,
                "gas_point_id": self.gas_point_id,
                "solar_wallet": data.get("octopus_solar_wallet"),
                "electricity_balance": data.get("octopus_electricity"),
                "gas_balance": data.get("octopus_gaz"),
                "pot_balance": data.get("octopus_pot"),
                "electricity_measurements": data.get("electricity_measurements", {}),
                "gas_measurements": data.get("gas_measurements", {}),
                "last_update": datetime.now().isoformat()
            }
            
        except Exception as err:
            LOGGER.error("Error updating Octopus French data: %s", err)
            raise
