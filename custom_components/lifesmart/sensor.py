"""Support for lifesmart sensors."""
import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass, # [新增] 標準設備類別
    SensorStateClass,  # [新增] 狀態類別 (用於長期統計)
)
from homeassistant.const import (
    UnitOfTemperature,
    PERCENTAGE,
    LIGHT_LUX,
    CONCENTRATION_PARTS_PER_MILLION,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
)

from . import LifeSmartDevice

_LOGGER = logging.getLogger(__name__)

GAS_SENSOR_TYPES = ["SL_SC_WA ", "SL_SC_CH", "SL_SC_CP", "ELIQ_EM"]
OT_SENSOR_TYPES = ["SL_SC_MHW", "SL_SC_BM", "SL_SC_G", "SL_SC_BG"]

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Perform the setup for LifeSmart devices."""
    if discovery_info is None:
        return
    dev = discovery_info.get("dev")
    param = discovery_info.get("param")
    devices = []
    
    # 優化迴圈邏輯
    for idx in dev['data']:
        if dev['devtype'] in OT_SENSOR_TYPES and idx in ["Z","V","P3","P4"]:
            devices.append(LifeSmartSensor(dev, idx, dev['data'][idx], param))
        else:
            # 這裡可能需要根據您的原始邏輯篩選，防止重複添加
            # 假設原始邏輯是為了過濾掉非傳感器數據
            if idx not in ["L1","L2","L3","P1","P2","RGB","RGBW"]: 
                devices.append(LifeSmartSensor(dev, idx, dev['data'][idx], param))
                
    add_entities(devices)


class LifeSmartSensor(LifeSmartDevice, SensorEntity):
    """Representation of a LifeSmartSensor."""

    def __init__(self, dev, idx, val, param):
        """Initialize the LifeSmartSensor."""
        super().__init__(dev, idx, val, param)
        self._attr_name = dev['name'] + "_" + idx
        
        # [修復] 添加 unique_id，移除 entity_id
        self._attr_unique_id = (dev['devtype'] + "_" + dev['agt'] + "_" + dev['me'] + "_" + idx).lower()
        
        devtype = dev['devtype']
        
        # [修復] 使用標準枚舉和單位常數
        # 初始化為 None
        self._attr_device_class = None
        self._attr_native_unit_of_measurement = None
        self._attr_state_class = SensorStateClass.MEASUREMENT # 預設為測量值
        
        if devtype in GAS_SENSOR_TYPES:
             # 燃氣類通常是狀態顯示，可能不需要單位
             pass 
        else:
            if idx == "T" or idx == "P1":
                self._attr_device_class = SensorDeviceClass.TEMPERATURE
                self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            elif idx == "H" or idx == "P2":
                self._attr_device_class = SensorDeviceClass.HUMIDITY
                self._attr_native_unit_of_measurement = PERCENTAGE
            elif idx == "Z":
                self._attr_device_class = SensorDeviceClass.ILLUMINANCE
                self._attr_native_unit_of_measurement = LIGHT_LUX
            elif idx == "V":
                self._attr_device_class = SensorDeviceClass.BATTERY
                self._attr_native_unit_of_measurement = PERCENTAGE
            elif idx == "P3":
                self._attr_device_class = SensorDeviceClass.CO2 # 假設 P3 是 CO2，如果是 PM2.5 可改
                self._attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
            elif idx == "P4":
                self._attr_device_class = SensorDeviceClass.PM25 # 假設 P4 是 PM2.5
                self._attr_native_unit_of_measurement = CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER

        # 設定初始值
        self._update_value(val)

    def _update_value(self, val):
        """Internal helper to update value."""
        # 根據原始邏輯判斷取值位置
        if self._devtype in GAS_SENSOR_TYPES:
            self._attr_native_value = val['val']
        else:
            self._attr_native_value = val['v']

    @property
    def unique_id(self):
        """A unique identifier for this entity."""
        return self._attr_unique_id
