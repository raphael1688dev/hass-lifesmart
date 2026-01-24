"""Support for LifeSmart binary sensors."""
import logging
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass, # [新增] 引入標準設備類別
    ENTITY_ID_FORMAT,
)

from . import LifeSmartDevice

_LOGGER = logging.getLogger(__name__)

GUARD_SENSOR = ["SL_SC_G", "SL_SC_BG"]
MOTION_SENSOR = ["SL_SC_MHW", "SL_SC_BM", "SL_SC_CM"]
SMOKE_SENSOR = ["SL_P_A"]

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Perform the setup for lifesmart devices."""
    if discovery_info is None:
        return
    dev = discovery_info.get("dev")
    param = discovery_info.get("param")
    devices = []
    for idx in dev['data']:
        if idx in ["M","G","B","AXS","P1"]:
            devices.append(LifeSmartBinarySensor(dev, idx, dev['data'][idx], param))
    add_entities(devices)

class LifeSmartBinarySensor(LifeSmartDevice, BinarySensorEntity):
    """Representation of LifeSmartBinarySensor."""

    def __init__(self, dev, idx, val, param):
        super().__init__(dev, idx, val, param)
        
        # [保留] 為了兼容您現有的自動化，保留舊的 entity_id 生成邏輯
        # 注意：如果未來想改用 UI 命名，可以移除這行
        self.entity_id = ENTITY_ID_FORMAT.format((dev['devtype'] + "_" + dev['agt'] + "_" + dev['me'] + "_" + idx).lower())
        
        # [新增] 關鍵修復：添加 unique_id
        # 這讓 HA 知道這是同一個設備，允許在 UI 中改名和分配區域
        self._attr_unique_id = f"{dev['devtype']}_{dev['agt']}_{dev['me']}_{idx}".lower()

        devtype = dev['devtype']
        
        # [優化] 使用標準 Device Class 枚舉
        if devtype in GUARD_SENSOR:
            self._attr_device_class = BinarySensorDeviceClass.DOOR
        elif devtype in MOTION_SENSOR:
            self._attr_device_class = BinarySensorDeviceClass.MOTION
        else:
            self._attr_device_class = BinarySensorDeviceClass.SMOKE
            
        # 初始狀態判斷邏輯
        self._update_state(val['val'])

    def _update_state(self, val):
        """Internal method to update state based on value."""
        # 門窗傳感器通常是: 0=閉合(Off), 1=打開(On)
        # 但有些 LifeSmart 設備可能邏輯相反，這裡保留您原本的邏輯
        if (val == 1 and self.device_class != BinarySensorDeviceClass.DOOR) or \
           (val == 0 and self.device_class == BinarySensorDeviceClass.DOOR):
            self._attr_is_on = True
        else:
            self._attr_is_on = False

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._attr_is_on
