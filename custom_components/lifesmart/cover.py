"""Support for LifeSmart covers."""
import logging
from homeassistant.components.cover import (
    CoverEntity,
    CoverDeviceClass,
    CoverEntityFeature,
    ATTR_POSITION,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.core import callback

from . import LifeSmartDevice

_LOGGER = logging.getLogger(__name__)

# 改用非同步 Setup
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up lifesmart dooya cover devices."""
    if discovery_info is None:
        return
        
    dev = discovery_info.get("dev")
    param = discovery_info.get("param")
    region = discovery_info.get("region", "us")
    
    devices = []
    # 根據 API，DOOYA 窗簾狀態在 P1，控制在 P2
    idx = "P1"
    if idx in dev.get('data', {}):
        devices.append(LifeSmartCover(dev, idx, dev['data'][idx], param, region))
        
    async_add_entities(devices)

class LifeSmartCover(LifeSmartDevice, CoverEntity):
    """LifeSmart cover devices."""

    def __init__(self, dev, idx, val, param, region):
        """Init LifeSmart cover device."""
        super().__init__(dev, idx, val, param, region)
        self._attr_name = dev['name']
        
        # [修復] 確保 agt 是乾淨的，對齊 Dispatcher
        clean_agt = dev['agt'].replace("_", "")
        self._attr_unique_id = f"{dev['devtype']}_{clean_agt}_{dev['me']}".lower()
        
        self._attr_device_class = CoverDeviceClass.CURTAIN
        self._attr_current_cover_position = 0
        self._attr_is_opening = False
        self._attr_is_closing = False
        self._attr_is_closed = False

        # 初始狀態解析
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

        # 1. 判斷馬達是否正在運作 (type % 2 == 1 表示運行中)
        is_moving = (type_int % 2 == 1)

        # 2. 解析開合度百分比 (val & 0x7F)
        pos = val_int & 0x7F
        # API 規範：大於 100 代表無法獲取位置，因此只在 <=100 時更新
        if pos <= 100:
            self._attr_current_cover_position = pos

        # 3. 判斷完全關閉的狀態
        self._attr_is_closed = (self._attr_current_cover_position == 0)

        # 4. 解析運行方向 (val & 0x80 == 0x80 表示開啟中)
        if is_moving:
            self._attr_is_opening = (val_int & 0x80) == 0x80
            self._attr_is_closing = not self._attr_is_opening
        else:
            self._attr_is_opening = False
            self._attr_is_closing = False

    async def async_added_to_hass(self):
        """訂閱 WebSocket 更新 (監聽 P1 埠口)"""
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
        """處理 WebSocket 狀態推送"""
        self._update_state(data)
        self.async_write_ha_state()

    @property
    def supported_features(self):
        """Flag supported features."""
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    # 全部改為完全非同步 (Native Async)，發送控制指令至 P2 埠口
    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        # 0xCF, 0 代表關閉
        if await self.async_lifesmart_epset("0xCF", 0, "P2") == 0:
            self._attr_is_closing = True
            self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        # 0xCF, 100 代表完全開啟
        if await self.async_lifesmart_epset("0xCF", 100, "P2") == 0:
            self._attr_is_opening = True
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        # 0xCE, 0x80 (即128) 代表停止
        if await self.async_lifesmart_epset("0xCE", 128, "P2") == 0:
            self._attr_is_opening = False
            self._attr_is_closing = False
            self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs):
        """Set cover to a specific position."""
        position = kwargs.get(ATTR_POSITION)
        if position is not None:
            # 0xCF, 百分比 代表開啟至特定位置
            await self.async_lifesmart_epset("0xCF", position, "P2")
