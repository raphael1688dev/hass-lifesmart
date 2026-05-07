"""Support for LifeSmart binary sensors (Config Flow Edition)."""
import logging
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
    ENTITY_ID_FORMAT,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.core import callback, HomeAssistant
from homeassistant.config_entries import ConfigEntry

from . import LifeSmartDevice
from .const import DOMAIN, BINARY_SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

GUARD_SENSOR = ["SL_SC_G", "SL_SC_BG", "SL_DF_GG"]
MOTION_SENSOR = ["SL_SC_MHW", "SL_SC_BM", "SL_SC_CM", "SL_DF_MM"]
SMOKE_SENSOR = ["SL_P_A", "SLPA"]

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """透過 Config Entry 設定 LifeSmart 二元感測器"""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    param = entry_data["param"]
    devices_list = entry_data.get("devices", [])
    exclude_items = entry_data.get("exclude_items", [])
    
    devices = []
    for dev in devices_list:
        if dev['me'] in exclude_items:
            continue
            
        if dev['devtype'] in BINARY_SENSOR_TYPES:
            dev['agt'] = dev['agt'].replace("_", "")
            for idx in dev.get('data', {}):
                if idx in ["M", "G", "B", "AXS", "P1"]:
                    devices.append(LifeSmartBinarySensor(dev, idx, dev['data'][idx], param))
            
    async_add_entities(devices)

class LifeSmartBinarySensor(LifeSmartDevice, BinarySensorEntity):
    """Representation of LifeSmartBinarySensor."""

    def __init__(self, dev, idx, val, param):
        super().__init__(dev, idx, val, param)
        
        self.entity_id = ENTITY_ID_FORMAT.format((dev['devtype'] + "_" + dev['agt'] + "_" + dev['me'] + "_" + idx).lower())
        
        clean_agt = dev['agt'].replace("_", "")
        self._attr_unique_id = f"{dev['devtype']}_{clean_agt}_{dev['me']}_{idx}".lower()

        devtype = dev['devtype']
        
        if devtype in GUARD_SENSOR:
            self._attr_device_class = BinarySensorDeviceClass.DOOR
        elif devtype in MOTION_SENSOR:
            self._attr_device_class = BinarySensorDeviceClass.MOTION
        elif devtype in SMOKE_SENSOR:
            self._attr_device_class = BinarySensorDeviceClass.SMOKE
        else:
            self._attr_device_class = None
            
        self._update_state(val)

    def _update_state(self, data):
        raw_val = None
        
        if not isinstance(data, dict):
            raw_val = data
        else:
            if 'val' in data:
                raw_val = data['val']
            elif 'type' in data:
                try:
                    t = int(data['type'], 16) if isinstance(data['type'], str) and data['type'].startswith('0x') else int(data['type'])
                    raw_val = t % 2
                except (ValueError, TypeError):
                    pass

        if raw_val is None:
            return

        try:
            val_int = int(raw_val)
        except (ValueError, TypeError):
            _LOGGER.warning("無法將感測器狀態轉換為整數: %s", raw_val)
            return

        if self._attr_device_class == BinarySensorDeviceClass.DOOR:
            self._attr_is_on = (val_int == 0)
        else:
            self._attr_is_on = (val_int == 1)

    async def async_added_to_hass(self):
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"lifesmart_update_{self._attr_unique_id}",
                self._handle_update
            )
        )

    @callback
    def _handle_update(self, data):
        self._update_state(data)
        self.async_write_ha_state()

    @property
    def is_on(self):
        return self._attr_is_on
