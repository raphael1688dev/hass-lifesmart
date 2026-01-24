"""lifesmart switch."""
import logging
from homeassistant.components.switch import (
    SwitchEntity,
)
from . import LifeSmartDevice

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Find and return lifesmart switches."""
    if discovery_info is None:
        return
    dev = discovery_info.get("dev")
    param = discovery_info.get("param")
    devices = []
    
    # 根據 discovery info 建立實體
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
        
        # [HA 2026 合規修正] 添加 unique_id
        # 這讓您可以在 Home Assistant UI 中更改名稱、圖示和區域
        self._attr_unique_id = (dev['devtype'] + "_" + dev['agt'] + "_" + dev['me'] + "_" + idx).lower()
        
        # [狀態修正] 解決「狀態相反」問題
        # 根據您的回饋與通用邏輯，直接判斷數值：1=開，0=關
        # 原代碼依賴 type 的奇偶數 (type % 2) 在某些設備上會導致反轉
        if val['val'] == 1:
            self._attr_is_on = True
        else:
            self._attr_is_on = False

    # [HA 2026 合規修正] 轉為異步方法 (async)
    # 防止在主線程執行網絡請求導致系統卡頓或崩潰
    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self.hass.async_add_executor_job(self._turn_on_sync)

    def _turn_on_sync(self):
        # 開啟指令：標準為 0x81，數值 1
        if super()._lifesmart_epset(self, "0x81", 1, self._idx) == 0:
            self._attr_is_on = True
            self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self.hass.async_add_executor_job(self._turn_off_sync)

    def _turn_off_sync(self):
        # [OFF 無效修正] 
        # 依據 LifeSmart Device Attribute List 文檔 (Page 6, 7, 15)：
        # "To turn off the switch, issue: type=0x80 val=0"
        # 舊代碼錯誤使用 0x81，導致無法關閉
        if super()._lifesmart_epset(self, "0x80", 0, self._idx) == 0:
            self._attr_is_on = False
            self.schedule_update_ha_state()
