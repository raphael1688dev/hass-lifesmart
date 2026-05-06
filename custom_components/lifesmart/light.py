"""Support for LifeSmart Gateway Light."""
import logging
import homeassistant.util.color as color_util
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.core import callback

from . import LifeSmartDevice

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Perform the setup for LifeSmart devices."""
    if discovery_info is None:
        return
        
    dev = discovery_info.get("dev")
    param = discovery_info.get("param")
    region = discovery_info.get("region", "us")
    
    devices = []
    # 支援的 RGB/指示燈埠口
    valid_idxs = ["RGB", "RGBW", "dark", "dark1", "dark2", "dark3", "bright", "bright1", "bright2", "bright3"]
    
    for idx in dev.get('data', {}):
        if idx in valid_idxs:
            devices.append(LifeSmartLight(dev, idx, dev['data'][idx], param, region))
            
    async_add_entities(devices)

class LifeSmartLight(LifeSmartDevice, LightEntity):
    """Representation of a LifeSmartLight."""

    def __init__(self, dev, idx, val, param, region):
        """Initialize the LifeSmartLight."""
        super().__init__(dev, idx, val, param, region)
        self._attr_name = f"{dev['name']}_{idx}"
        
        # 確保 agt 乾淨，對齊 Dispatcher
        clean_agt = dev['agt'].replace("_", "")
        self._attr_unique_id = f"{dev['devtype']}_{clean_agt}_{dev['me']}_{idx}".lower()
        
        # 宣告支援的顏色模式 (Hue, Saturation)
        self._attr_supported_color_modes = {ColorMode.HS}
        self._attr_color_mode = ColorMode.HS
        
        self._attr_is_on = False
        self._attr_hs_color = None
        self._attr_brightness = 255
        
        self._update_state(val)

    def _update_state(self, data):
        """解析 API 回傳的狀態與 32-bit 顏色數值"""
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

        # 狀態判斷：type 奇數為開，偶數為關
        self._attr_is_on = (type_val % 2 == 1)

        # 顏色解析：依照 LifeSmart 規範拆解 32-bit RGB
        if val_int > 1: # 排除單純的開關訊號 0 或 1
            b = val_int & 0xFF
            g = (val_int >> 8) & 0xFF
            r = (val_int >> 16) & 0xFF
            
            # 將 RGB 轉回 Home Assistant 慣用的 HS 顏色與亮度
            if r > 0 or g > 0 or b > 0:
                self._attr_hs_color = color_util.color_RGB_to_hs(r, g, b)
                self._attr_brightness = max(r, g, b)

    async def async_added_to_hass(self):
        """訂閱 WebSocket 更新"""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"lifesmart_update_{self._attr_unique_id}",
                self._handle_update
            )
        )

    @callback
    def _handle_update(self, data):
        """處理狀態推送"""
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
        """Turn the light on, setting color and brightness via Bitwise Shift."""
        
        # 取得目標顏色與亮度 (若無提供，則使用當前值或預設值)
        hs_color = kwargs.get(ATTR_HS_COLOR, self._attr_hs_color or (0, 0))
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness or 255)

        # 只要有設定顏色或亮度，就必須組裝成 32-bit Integer 發送
        if ATTR_HS_COLOR in kwargs or ATTR_BRIGHTNESS in kwargs:
            # 依據亮度計算實際的 RGB 數值
            rgb = color_util.color_hsv_to_RGB(hs_color[0], hs_color[1], brightness / 255 * 100)
            
            # API 規範：Bit 16~23(Red), Bit 8~15(Green), Bit 0~7(Blue)
            r = int(rgb[0])
            g = int(rgb[1])
            b = int(rgb[2])
            color_val = (r << 16) | (g << 8) | b
            
            # type="0xff" 代表開啟並設定顏色
            if await self.async_lifesmart_epset("0xFF", color_val, self._idx) == 0:
                self._attr_hs_color = hs_color
                self._attr_brightness = brightness
                self._attr_is_on = True
        else:
            # 純粹開啟指令
            if await self.async_lifesmart_epset("0x81", 1, self._idx) == 0:
                self._attr_is_on = True
                
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        if await self.async_lifesmart_epset("0x80", 0, self._idx) == 0:
            self._attr_is_on = False
            self.async_write_ha_state()
