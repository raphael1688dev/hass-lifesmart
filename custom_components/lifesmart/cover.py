"""Support for LifeSmart covers (Config Flow Edition)."""
import logging
from homeassistant.components.cover import (
    CoverEntity,
    CoverDeviceClass,
    CoverEntityFeature,
    ATTR_POSITION,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.core import callback, HomeAssistant
from homeassistant.config_entries import ConfigEntry

from . import LifeSmartDevice
from .const import DOMAIN, COVER_TYPES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """透過 Config Entry 設定 LifeSmart 窗簾設備"""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    param = entry_data["param"]
    devices_list = entry_data.get("devices", [])
    exclude_items = entry_data.get("exclude_items", [])
    
    devices = []
    
    for dev in devices_list:
        if dev['me'] in exclude_items:
            continue
            
        if dev['devtype'] in COVER_TYPES:
            # 確保 agt 是乾淨的，對齊 Dispatcher
            dev['agt'] = dev['agt'].replace("_", "")
            # 根據 API，DOOYA 窗簾狀態在 P1
            idx = "P1"
            if idx in dev.get('data', {}):
                devices.append(LifeSmartCover(dev, idx, dev['data'][idx], param))
        
    async_add_entities(devices)

class LifeSmartCover(LifeSmartDevice, CoverEntity):
    """LifeSmart cover devices."""

    def __init__(self, dev, idx, val, param):
        """Init LifeSmart cover device."""
        super().__init__(dev, idx, val, param)
        self._attr_name = dev['name']
        
        clean_agt = dev['agt'].replace("_", "")
        self._attr_unique_id = f"{dev['devtype']}_{clean_agt}_{dev['me']}".lower()
        
        self._attr_device_class = CoverDeviceClass.CURTAIN
        self._attr_current_cover_position = 0
        self._attr_is_opening = False
        self._attr_is_closing = False
        self._attr_is_closed = False

        self._update_state(val)

    def _update_state(self, data):
        """根據 DOOYA 窗簾 API 規範進行位元運算解析"""
        if not isinstance(data, dict):
            return

        raw_val = data.get('val')
        raw_type = data.get('type')
        
        if raw_val is None or raw_type is None:
            return

        try:
            val_int = int(raw_val)
            type_int = int(raw_type, 16) if isinstance(raw_type, str) and raw_type.startswith('0x') else int(raw_type)
        except (ValueError, TypeError):
            _LOGGER.warning("無法解析的窗簾數據: %s", data)
            return

        is_moving = (type_int % 2 == 1)
        pos = val_int & 0x7F
        
        if pos <= 100:
            self._attr_current_cover_position = pos

        self._attr_is_closed = (self._attr_current_cover_position == 0)

        if is_moving:
            self._attr_is_opening = (val_int & 0x80) == 0x80
            self._attr_is_closing = not self._attr_is_opening
        else:
            self._attr_is_opening = False
            self._attr_is_closing = False

    async def async_added_to_hass(self):
        clean_agt = self._agt.replace("_", "")
        uid = f"{self._devtype}_{clean_agt}_{self._me}_p1".lower()
        
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"lifesmart_update_{uid}",
                self._handle_update
            )
        )

    @callback
    def _handle_update(self, data):
        self._update_state(data)
        self.async_write_ha_state()

    @property
    def supported_features(self):
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    async def async_close_cover(self, **kwargs):
        if await self.async_lifesmart_epset("0xCF", 0, "P2") == 0:
            self._attr_is_closing = True
            self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        if await self.async_lifesmart_epset("0xCF", 100, "P2") == 0:
            self._attr_is_opening = True
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        if await self.async_lifesmart_epset("0xCE", 128, "P2") == 0:
            self._attr_is_opening = False
            self._attr_is_closing = False
            self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs):
        position = kwargs.get(ATTR_POSITION)
        if position is not None:
            await self.async_lifesmart_epset("0xCF", position, "P2")
