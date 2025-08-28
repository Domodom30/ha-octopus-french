"""Sensor platform for Octopus Spain integration."""

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from .const import DOMAIN, ATTRIBUTION, GAS_CONVERSION_FACTOR

SENSOR_TYPES = {
    "solar_wallet": {"name": "Octopus Solar Wallet", "icon": "mdi:solar-power"},
    "electricity_balance": {"name": "Octopus Electricity Balance", "icon": "mdi:lightning-bolt"},
    "gas_balance": {"name": "Octopus Gas Balance", "icon": "mdi:fire"},
    "pot_balance": {"name": "Octopus Pot Balance", "icon": "mdi:piggy-bank"},
    "current_month_total": {"name": "Current Month Electricity Consumption", "icon": "mdi:chart-line"},
    "yearly_total": {"name": "Yearly Electricity Consumption", "icon": "mdi:chart-bar"},
    "gas_current_month": {"name": "Current Month Gas Consumption", "icon": "mdi:fire"},
    "gas_yearly": {"name": "Yearly Gas Consumption", "icon": "mdi:fire"},
    "gas_current_month_m3": {"name": "Current Month Gas Consumption (m³)", "icon": "mdi:fire"},
    "gas_yearly_m3": {"name": "Yearly Gas Consumption (m³)", "icon": "mdi:fire"},
}

BALANCE_SENSORS = ["solar_wallet", "electricity_balance", "gas_balance", "pot_balance"]
ENERGY_SENSORS = ["current_month_total", "yearly_total", "gas_current_month", "gas_yearly"]
GAS_M3_SENSORS = ["gas_current_month_m3", "gas_yearly_m3"]

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Octopus Spain sensors from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    # Capteurs de balance
    balance_sensors = [OctopusBalanceSensor(coordinator, stype) for stype in BALANCE_SENSORS]
    
    # Capteurs de consommation
    energy_sensors = [OctopusEnergySensor(coordinator, stype) for stype in ENERGY_SENSORS]
    
    # Capteurs de conversion gaz kWh -> m³
    gas_m3_sensors = [OctopusGasM3Sensor(coordinator, stype) for stype in GAS_M3_SENSORS]
    
    async_add_entities(balance_sensors + energy_sensors + gas_m3_sensors, False)


class OctopusBalanceSensor(CoordinatorEntity, SensorEntity):
    """Sensor for account balances."""

    def __init__(self, coordinator, sensor_type):
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._config = SENSOR_TYPES[sensor_type]

    @property
    def name(self):
        return self._config["name"]

    @property
    def unique_id(self):
        return f"octopus_spain_{self._sensor_type}"

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        value = data.get(self._sensor_type, 0)
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0

    @property
    def native_unit_of_measurement(self):
        return "€"

    @property
    def device_class(self):
        return SensorDeviceClass.MONETARY

    @property
    def state_class(self):
        return SensorStateClass.TOTAL

    @property
    def icon(self):
        return self._config["icon"]

    @property
    def extra_state_attributes(self):
        return {"attribution": ATTRIBUTION}


class OctopusEnergySensor(CoordinatorEntity, SensorEntity):
    """Sensor for energy consumption data."""

    def __init__(self, coordinator, sensor_type):
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._config = SENSOR_TYPES[sensor_type]

    @property
    def name(self):
        return self._config["name"]

    @property
    def unique_id(self):
        return f"octopus_spain_{self._sensor_type}"

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        
        if self._sensor_type in ["current_month_total", "yearly_total"]:
            measurements = data.get("electricity_measurements", {})
        else:
            measurements = data.get("gas_measurements", {})
        
        value = 0
        if self._sensor_type in ["current_month_total", "gas_current_month"]:
            value = measurements.get("current_month", {}).get("total", 0)
        elif self._sensor_type in ["yearly_total", "gas_yearly"]:
            value = measurements.get("yearly_total", 0)
        
        try:
            return round(float(value), 1)
        except (ValueError, TypeError):
            return 0

    @property
    def native_unit_of_measurement(self):
        return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def device_class(self):
        return SensorDeviceClass.ENERGY

    @property
    def state_class(self):
        return SensorStateClass.TOTAL_INCREASING

    @property
    def icon(self):
        return self._config["icon"]

    @property
    def extra_state_attributes(self):
        attrs = {"attribution": ATTRIBUTION}
        data = self.coordinator.data or {}

        if "last_update" in data:
            attrs["last_update"] = data["last_update"]

        # Données mensuelles pour les capteurs annuels
        if self._sensor_type in ["yearly_total", "gas_yearly"]:
            measurement_type = "electricity_measurements" if self._sensor_type == "yearly_total" else "gas_measurements"
            
            if data.get(measurement_type):
                monthly_data = data[measurement_type].get("monthly_data", [])
                for month_data in monthly_data[-6:]:
                    month = month_data.get("month")
                    total = month_data.get("total", 0)
                    
                    if self._sensor_type == "yearly_total":
                        hp = month_data.get("hp", 0)
                        hc = month_data.get("hc", 0)
                        attrs[f"month_{month}_hp"] = f"{round(float(hp),1)} kWh"
                        attrs[f"month_{month}_hc"] = f"{round(float(hc),1)} kWh"
                    
                    attrs[f"month_{month}"] = f"{round(float(total),1)} kWh"

        return attrs


class OctopusGasM3Sensor(CoordinatorEntity, SensorEntity):
    """Sensor for gas consumption converted to m³."""

    def __init__(self, coordinator, sensor_type):
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._config = SENSOR_TYPES[sensor_type]
        self._source_sensor = "gas_current_month" if sensor_type == "gas_current_month_m3" else "gas_yearly"

    @property
    def name(self):
        return self._config["name"]

    @property
    def unique_id(self):
        return f"octopus_spain_{self._sensor_type}"

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        measurements = data.get("gas_measurements", {})
        
        value = 0
        if self._sensor_type == "gas_current_month_m3":
            value = measurements.get("current_month", {}).get("total", 0)
        elif self._sensor_type == "gas_yearly_m3":
            value = measurements.get("yearly_total", 0)
        
        try:
            # Conversion kWh -> m³
            m3_value = float(value) / GAS_CONVERSION_FACTOR
            return round(m3_value, 1)
        except (ValueError, TypeError):
            return 0

    @property
    def native_unit_of_measurement(self):
        return UnitOfVolume.CUBIC_METERS

    @property
    def device_class(self):
        return SensorDeviceClass.GAS

    @property
    def state_class(self):
        return SensorStateClass.TOTAL_INCREASING

    @property
    def icon(self):
        return self._config["icon"]

    @property
    def extra_state_attributes(self):
        attrs = {
            "attribution": ATTRIBUTION,
            "conversion_factor": GAS_CONVERSION_FACTOR,
            "conversion_formula": "m³ = kWh ÷ 11.29",
            "source_sensor": self._source_sensor,
            "source_value_kwh": self._get_source_value()
        }
        
        data = self.coordinator.data or {}
        if "last_update" in data:
            attrs["last_update"] = data["last_update"]
            
        return attrs

    def _get_source_value(self):
        """Get the original value in kWh from the source sensor."""
        data = self.coordinator.data or {}
        measurements = data.get("gas_measurements", {})
        
        if self._sensor_type == "gas_current_month_m3":
            value = measurements.get("current_month", {}).get("total", 0)
        elif self._sensor_type == "gas_yearly_m3":
            value = measurements.get("yearly_total", 0)
        
        try:
            return round(float(value), 1)
        except (ValueError, TypeError):
            return 0