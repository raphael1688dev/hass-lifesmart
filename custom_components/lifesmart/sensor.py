"""Support for lifesmart sensors."""
import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfTemperature,
    UnitOfIlluminance, # 使用新的 Illuminance 單位
    PERCENTAGE,
    CONCENTRATION_PARTS_PER_MILLION,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
)

from . import LifeSmartDevice

_LOGGER = logging.getLogger(__name__)

GAS_SENSOR_TYPES = ["SL_SC_WA ", "SL_SC_CH", "SL_SC_CP", "ELIQ_EM"]
OT_SENSOR_TYPES = ["SL_SC_MHW", "SL_SC_BM", "SL_SC_G", "SL_SC_BG", "SL_SC_THL", "SL_SC_BE", "SL_SC_CQ"] # 加入 Env sensor 類型

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Perform the setup for LifeSmart devices."""
    if discovery_info is None:
        return
    dev = discovery_info.get("dev")
    param = discovery_info.get("param")
    region = discovery_info.get("region", "us") # 配合之前的非同步架構
    devices = []
    
    # 針對感測器過濾不要的 IDX
    for idx in dev.get('data', {}):
        if idx not in ["L1", "L2", "L3", "P1", "P2", "RGB", "RGBW", "OP", "CL", "ST"]: 
            devices.append(LifeSmartSensor(dev, idx, dev['data'][idx], param, region))
        # 特別處理 Env Sensor 的 P1/P2，因為在開關中 P1/P2 通常代表按鍵
        elif dev['devtype'] in OT_SENSOR_TYPES and idx in ["P1", "P2"]:
            devices.append(LifeSmartSensor(dev, idx, dev['data'][idx], param, region))
                
    async_add_entities(devices)

class LifeSmartSensor(LifeSmartDevice, SensorEntity):
    """Representation of a LifeSmartSensor."""

    def __init__(self, dev, idx, val, param, region):
        """Initialize the LifeSmartSensor."""
        super().__init__(dev, idx, val, param, region)
        self._attr_name = f"{dev['name']}_{idx}"
        
        # 確保 agt 是乾淨的，與 Dispatcher 匹配
        clean_agt = dev['agt'].replace("_", "")
        self._attr_unique_id = f"{dev['devtype']}_{clean_agt}_{dev['me']}_{idx}".lower()
        
        devtype = dev['devtype']
        
        self._attr_device_class = None
        self._attr_native_unit_of_measurement = None
        self._attr_state_class = SensorStateClass.MEASUREMENT
        
        if devtype in GAS_SENSOR_TYPES:
             # 燃氣類通常不需要測量單位，或者可以在此自定義
             pass 
        else:
            if idx == "T" or (devtype == "SL_SC_CQ" and idx == "P1"): # 處理 SL_SC_CQ 的溫度
                self._attr_device_class = SensorDeviceClass.TEMPERATURE
                self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            elif idx == "H" or (devtype == "SL_SC_CQ" and idx == "P2"): # 處理 SL_SC_CQ 的濕度
                self._attr_device_class = SensorDeviceClass.HUMIDITY
                self._attr_native_unit_of_measurement = PERCENTAGE
            elif idx == "Z":
                self._attr_device_class = SensorDeviceClass.ILLUMINANCE
                self._attr_native_unit_of_measurement = UnitOfIlluminance.LUX
            elif idx == "V" or idx == "P5": # P5 通常是 Env sensor 的電量
                self._attr_device_class = SensorDeviceClass.BATTERY
                self._attr_native_unit_of_measurement = PERCENTAGE
            elif idx == "P3":
                self._attr_device_class = SensorDeviceClass.CO2 
                self._attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
            elif idx == "P4":
                self._attr_device_class = SensorDeviceClass.PM25 # 或是 TVOC，取決於具體設備
                self._attr_native_unit_of_measurement = CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER

        self._update_value(val)

    def _update_value(self, data):
        """Internal helper to update value with safety checks."""
        if not isinstance(data, dict):
            # 防呆：如果 data 不是字典，直接嘗試轉換
            try:
                self._attr_native_value = float(data)
            except (ValueError, TypeError):
                pass
            return

        if self._devtype in GAS_SENSOR_TYPES:
            self._attr_native_value = data.get('val')
            return

        # 優先取用 API 已經轉換好的 'v' 值
        if 'v' in data:
            self._attr_native_value = data['v']
        elif 'val' in data:
            # 如果沒有 'v'，必須根據 API 規格手動轉換 'val'
            raw_val = data['val']
            try:
                if self._attr_device_class in [SensorDeviceClass.TEMPERATURE, SensorDeviceClass.HUMIDITY]:
                    # 溫濕度通常需要除以 10
                    self._attr_native_value = float(raw_val) / 10.0
                elif self._attr_device_class == SensorDeviceClass.PM25 and self._devtype == "SL_SC_CQ":
                    # TVOC 原始值需要除以 1000
                    self._attr_native_value = float(raw_val) / 1000.0
                else:
                    self._attr_native_value = raw_val
            except (ValueError, TypeError):
                _LOGGER.error("無法轉換感測器數值: %s", data)

    # 配合 Dispatcher 處理 WebSocket 更新
    async def async_added_to_hass(self):
        """訂閱 WebSocket 更新"""
        from homeassistant.helpers.dispatcher import async_dispatcher_connect
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"lifesmart_update_{self._attr_unique_id}",
                self._handle_update
            )
        )

    @from homeassistant.core import callback
    def _handle_update(self, data):
        """處理 WebSocket 推送過來的更新"""
        self._update_value(data)
        self.async_write_ha_state()
