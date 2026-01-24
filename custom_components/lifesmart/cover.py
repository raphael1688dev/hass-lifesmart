"""Support for LifeSmart covers."""
import logging
from homeassistant.components.cover import (
    CoverEntity,
    CoverDeviceClass,
    CoverEntityFeature,
    ATTR_POSITION,
)

from . import LifeSmartDevice

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up lifesmart dooya cover devices."""
    if discovery_info is None:
        return
    dev = discovery_info.get("dev")
    param = discovery_info.get("param")
    devices = []
    # 這裡原代碼只處理了 P1，保留原邏輯
    idx = "P1"
    if idx in dev['data']:
        devices.append(LifeSmartCover(dev, idx, dev['data'][idx], param))
    add_entities(devices)


class LifeSmartCover(LifeSmartDevice, CoverEntity):
    """LifeSmart cover devices."""

    def __init__(self, dev, idx, val, param):
        """Init LifeSmart cover device."""
        super().__init__(dev, idx, val, param)
        self._attr_name = dev['name']
        
        # [修復] 添加 unique_id，移除 self.entity_id
        # 這樣可以讓你在 UI 中改名和分配區域
        self._attr_unique_id = (dev['devtype'] + "_" + dev['agt'] + "_" + dev['me']).lower()
        
        self._pos = val['val']
        
        # [修復] 使用標準枚舉類型
        self._attr_device_class = CoverDeviceClass.CURTAIN

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self._pos

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self.current_cover_position <= 0
        
    @property
    def supported_features(self):
        """Flag supported features."""
        # 明確宣告支援開啟、關閉、停止和設定位置
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    # [關鍵修復] 轉為異步方法，防止阻塞主線程
    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self.hass.async_add_executor_job(self._close_cover_sync)

    def _close_cover_sync(self):
        super()._lifesmart_epset(self, "0xCF", 0, "P2")

    # [關鍵修復] 轉為異步方法
    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self.hass.async_add_executor_job(self._open_cover_sync)

    def _open_cover_sync(self):
        super()._lifesmart_epset(self, "0xCF", 100, "P2")

    # [關鍵修復] 轉為異步方法
    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self.hass.async_add_executor_job(self._stop_cover_sync)

    def _stop_cover_sync(self):
        super()._lifesmart_epset(self, "0xCE", 0x80, "P2")

    # [關鍵修復] 轉為異步方法
    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        await self.hass.async_add_executor_job(self._set_cover_position_sync, kwargs)

    def _set_cover_position_sync(self, kwargs):
        position = kwargs.get(ATTR_POSITION)
        super()._lifesmart_epset(self, "0xCF", position, "P2")
