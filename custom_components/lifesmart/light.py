"""Support for LifeSmart Gateway Light (Config Flow Edition)."""
import logging
import homeassistant.util.color as color_util
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.core import callback, HomeAssistant
from homeassistant.config_entries import ConfigEntry

from . import LifeSmartDevice
from .const import DOMAIN, LIGHT_SWITCH_TYPES, SPOT_TYPES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """透過 Config Entry 設定 LifeSmart 燈光設備"""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    param = entry_data["param"]
    devices_list = entry_data.get("devices", [])
    exclude_items = entry_data.get("exclude_items", [])
    
    devices = []
    valid_idxs = ["RGB", "RGBW", "dark", "dark1", "dark2", "dark3", "bright", "bright1", "bright2", "bright3"]
    
    for dev in devices_list:
        if dev['me'] in exclude_items:
            continue
            
        if dev['devtype'] in SPOT_TYPES or dev['devtype'] in LIGHT_SWITCH_TYPES:
            dev['agt'] = dev['agt'].replace("_", "")
            for idx in dev.get('data', {}):
                if idx in valid_idxs:
                    devices.append(LifeSmartLight(dev, idx, dev['data'][idx], param))
            
    async_add_entities(devices)

class LifeSmartLight(LifeSmartDevice, LightEntity):
    """Representation of a LifeSmartLight."""

    def __init__(self, dev, idx, val, param):
        """Initialize the LifeSmartLight."""
        super().__init__(dev, idx, val, param)
        self._attr_name = f"{dev['name']}_{idx}"
        
        clean_agt = dev['agt'].replace("_", "")
        #self._attr_unique_id = f"{dev['devtype']}_{clean_agt}_{dev['me']}_{idx}".lower()
        # 新增這行
        self.entity_id = f"light.{dev['devtype']}_{dev['me']}_{idx}".lower()
        
        self._attr_supported_color_modes = {ColorMode.HS}
        self._attr_color_mode = ColorMode.HS
        
        self._attr_is_on = False
        self._attr_hs_color = None
        self._attr_brightness = 255
        
        self._update_state(val)

    def _update_state(self, data):
        if not isinstance(data, dict):
            return

        type_val = data.get('type', 0)
        val_int = data.get('val', 0)

        if isinstance(type_val, str):
            type_val = int(type_val, 16) if type_val.startswith('0x') else int(type_val)

        try:
            val_int = int(val_int)
        except (ValueError, TypeError):
            return

        self._attr_is_on = (type_val % 2 == 1)

        if val_int > 1:
            b = val_int & 0xFF
            g = (val_int >> 8) & 0xFF
            r = (val_int >> 16) & 0xFF
            
            if r > 0 or g > 0 or b > 0:
                self._attr_hs_color = color_util.color_RGB_to_hs(r, g, b)
                self._attr_brightness = max(r, g, b)

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

    @property
    def hs_color(self):
        return self._attr_hs_color

    @property
    def brightness(self):
        return self._attr_brightness

    async def async_turn_on(self, **kwargs):
        hs_color = kwargs.get(ATTR_HS_COLOR, self._attr_hs_color or (0, 0))
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness or 255)

        if ATTR_HS_COLOR in kwargs or ATTR_BRIGHTNESS in kwargs:
            rgb = color_util.color_hsv_to_RGB(hs_color[0], hs_color[1], brightness / 255 * 100)
            r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
            color_val = (r << 16) | (g << 8) | b
            
            if await self.async_lifesmart_epset("0xFF", color_val, self._idx) == 0:
                self._attr_hs_color = hs_color
                self._attr_brightness = brightness
                self._attr_is_on = True
        else:
            if await self.async_lifesmart_epset("0x81", 1, self._idx) == 0:
                self._attr_is_on = True
                
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        if await self.async_lifesmart_epset("0x80", 0, self._idx) == 0:
            self._attr_is_on = False
            self.async_write_ha_state()
