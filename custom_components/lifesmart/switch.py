"""lifesmart switch."""
import logging
from homeassistant.components.switch import (
    SwitchEntity,
)
# [修復] 正確導入調度器連接函數
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import LifeSmartDevice

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Find and return lifesmart switches."""
    if discovery_info is None:
        return
    dev = discovery_info.get("dev")
    param = discovery_info.get("param")
    devices = []
    
    for idx in dev['data']:
        if idx in ["L1", "L2", "L3", "P1", "P2", "P3"]:
            devices.append(LifeSmartSwitch(dev, idx, dev['data'][idx], param))
            
    add_entities(devices)
    return True

class LifeSmartSwitch(LifeSmartDevice, SwitchEntity):
    """Representation of a LifeSmart Switch."""

    def __init__(self, dev, idx, val, param):
        """Initialize the switch."""
        super().__init__(dev, idx, val, param)
        self._attr_name = dev['name'] + "_" + idx
        self._attr_unique_id = (dev['devtype'] + "_" + dev['agt'] + "_" + dev['me'] + "_" + idx).lower()
        
        # 根據數據初始化狀態
        self._update_from_data(val)

    def _update_from_data(self, data):
        """根據數據更新狀態"""
        if 'type' in data:
            # 依據文檔: type 為奇數表示開，偶數表示關
            if data['type'] % 2 == 1:
                self._attr_is_on = True
            else:
                self._attr_is_on = False
        elif 'val' in data:
            # Fallback
            self._attr_is_on = (data['val'] == 1)

    async def async_added_to_hass(self):
        """訂閱更新"""
        # [修復] 使用正確的 async_dispatcher_connect 呼叫方式
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"lifesmart_update_{self._attr_unique_id}",
                self._handle_update
            )
        )

    @property
    def is_on(self):
        return self._attr_is_on

    @property
    def should_poll(self):
        return False

    async def _handle_update(self, data):
        """處理 WebSocket 推送過來的更新"""
        self._update_from_data(data)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self.hass.async_add_executor_job(self._turn_on_sync)

    def _turn_on_sync(self):
        # 開啟指令: 0x81
        if super()._lifesmart_epset(self, "0x81", 1, self._idx) == 0:
            self._attr_is_on = True
            self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self.hass.async_add_executor_job(self._turn_off_sync)

    def _turn_off_sync(self):
        # 關閉指令: 0x80 (符合文檔)
        if super()._lifesmart_epset(self, "0x80", 0, self._idx) == 0:
            self._attr_is_on = False
            self.schedule_update_ha_state()
