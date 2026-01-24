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
        
        # [修復] 添加 unique_id，移除 entity_id 強制賦值
        self._attr_unique_id = (dev['devtype'] + "_" + dev['agt'] + "_" + dev['me'] + "_" + idx).lower()
        
        # [修復] 使用現代屬性 _attr_is_on
        if val['type'] % 2 == 1:
            self._attr_is_on = True
        else:
            self._attr_is_on = False

    # [關鍵修復] 轉為異步方法，防止阻塞主線程
    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self.hass.async_add_executor_job(self._turn_on_sync)

    def _turn_on_sync(self):
        if super()._lifesmart_epset(self, "0x81", 1, self._idx) == 0:
            self._attr_is_on = True
            self.schedule_update_ha_state()

    # [關鍵修復] 轉為異步方法
    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self.hass.async_add_executor_job(self._turn_off_sync)

    def _turn_off_sync(self):
        if super()._lifesmart_epset(self, "0x81", 0, self._idx) == 0:
            self._attr_is_on = False
            self.schedule_update_ha_state()
