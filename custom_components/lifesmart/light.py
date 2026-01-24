"""Support for LifeSmart Gateway Light."""
import logging
import json
import time
import hashlib
import urllib.request 

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
import homeassistant.util.color as color_util

from . import LifeSmartDevice

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Perform the setup for LifeSmart devices."""
    if discovery_info is None:
        return
    dev = discovery_info.get("dev")
    param = discovery_info.get("param")
    devices = []
    for idx in dev['data']:
        if idx in ["RGB","RGBW","dark","dark1","dark2","dark3","bright","bright1","bright2","bright"]:
            devices.append(LifeSmartLight(dev, idx, dev['data'][idx], param))
    add_entities(devices)

class LifeSmartLight(LifeSmartDevice, LightEntity):
    """Representation of a LifeSmartLight."""

    def __init__(self, dev, idx, val, param):
        """Initialize the LifeSmartLight."""
        super().__init__(dev, idx, val, param)
        self._attr_name = dev['name'] + "_" + idx
        self._attr_unique_id = (dev['devtype'] + "_" + dev['agt'] + "_" + dev['me'] + "_" + idx).lower()
        
        self._hs_color = None
        self._brightness = 0
        
        if idx in ["RGB", "RGBW"]:
            self._attr_supported_color_modes = {ColorMode.HS}
            self._attr_color_mode = ColorMode.HS
        else:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS

    @property
    def brightness(self):
        return self._brightness

    @property
    def hs_color(self):
        return self._hs_color

    @property
    def is_on(self):
        """Return true if it is on."""
        # 根據文檔: type%2=1 為開
        # 但為了保險，結合 val 判斷
        if self._attr_color_mode == ColorMode.HS:
             return self._hs_color is not None
        return self._brightness > 0

    async def async_turn_on(self, **kwargs):
        """Turn on the light."""
        await self.hass.async_add_executor_job(self._turn_on_sync, kwargs)

    def _turn_on_sync(self, kwargs):
        if ATTR_HS_COLOR in kwargs:
            self._hs_color = kwargs[ATTR_HS_COLOR]
            rgb = color_util.color_hs_to_rgb(*self._hs_color)
            if self._idx == "RGB":
                 super()._lifesmart_epset(self, "0x81", rgb[0], "R")
                 super()._lifesmart_epset(self, "0x81", rgb[1], "G")
                 super()._lifesmart_epset(self, "0x81", rgb[2], "B")
            elif self._idx == "RGBW":
                 super()._lifesmart_epset(self, "0x81", rgb[0], "WR")
                 super()._lifesmart_epset(self, "0x81", rgb[1], "WG")
                 super()._lifesmart_epset(self, "0x81", rgb[2], "WB")
            
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            # 根據文檔 ，設定數值使用 0x81 (或 0xff 設定顏色)
            super()._lifesmart_epset(self, "0x81", self._brightness, self._idx)
        
        if not kwargs:
            self._brightness = 255
            # 文檔: Turn on the light: type=0x81 val=1
            super()._lifesmart_epset(self, "0x81", 1, self._idx)

    async def async_turn_off(self, **kwargs):
        """Turn off the light."""
        await self.hass.async_add_executor_job(self._turn_off_sync)

    def _turn_off_sync(self):
        self._brightness = 0
        self._hs_color = None
        # [關鍵修正] 根據文檔 
        # Turn off the light: type=0x80 val=0
        # 舊代碼錯誤地使用了 0x81
        super()._lifesmart_epset(self, "0x80", 0, self._idx)
