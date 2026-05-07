"""Support for lifesmart sensors (Config Flow Edition)."""
import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfTemperature,
    UnitOfIlluminance,
    PERCENTAGE,
    CONCENTRATION_PARTS_PER_MILLION,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.core import callback, HomeAssistant
from homeassistant.config_entries import ConfigEntry

from . import LifeSmartDevice
from .const import DOMAIN, GAS_SENSOR_TYPES, EV_SENSOR_TYPES, OT_SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """透過 Config Entry 設定 LifeSmart 感測器設備"""
    # 從 hass.data 取得初始化資料
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    param = entry_data["param"]
    devices_list = entry_data.get("devices", [])
    exclude_items = entry_data.get("exclude_items", [])
    
    devices = []
    
    for dev in devices_list:
        if dev['me'] in exclude_items:
            continue
            
        devtype = dev['devtype']
        # 篩選感測器類型的設備
        if devtype in GAS_SENSOR_TYPES or devtype in EV_SENSOR_TYPES or devtype in OT_SENSOR_TYPES:
            # 確保 agt 字串乾淨
            dev['agt'] = dev['agt'].replace("_", "")
            
            for idx in dev.get('data', {}):
                # 過濾掉屬於開關或窗簾的通訊埠
                if idx not in ["L1", "L2", "L3", "P1", "P2", "RGB", "RGBW", "OP", "CL", "ST"]: 
                    devices.append(LifeSmartSensor(dev, idx, dev['data'][idx], param))
                # 特別處理 Env Sensor / 防護感測器的 P1/P2 (因為在開關中 P1/P2 代表按鍵)
                elif devtype in OT_SENSOR_TYPES and idx in ["P1", "P2"]:
                    devices.append(LifeSmartSensor(dev, idx, dev['data'][idx], param))
                elif devtype in EV_SENSOR_TYPES and idx in ["P1", "P2"]:
                    devices.append(LifeSmartSensor(dev, idx, dev['data'][idx], param))
                
    async_add_entities(devices)

class LifeSmartSensor(LifeSmartDevice, SensorEntity):
    """Representation of a LifeSmartSensor."""

    def __init__(self, dev, idx, val, param):
        """Initialize the LifeSmartSensor."""
        super().__init__(dev, idx, val, param)
        self._attr_name = f"{dev['name']}_{idx}"
        
        # 確保與 Dispatcher 派發的 unique_id 一致
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
            if idx == "T" or (devtype == "SL_SC_CQ" and idx == "P1"): # 處理特殊感測器的溫度埠口
                self._attr_device_class = SensorDeviceClass.TEMPERATURE
                self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            elif idx == "H" or (devtype == "SL_SC_CQ" and idx == "P2"): # 處理特殊感測器的濕度埠口
                self._attr_device_class = SensorDeviceClass.HUMIDITY
                self._attr_native_unit_of_measurement = PERCENTAGE
            elif idx == "Z":
                self._attr_device_class = SensorDeviceClass.ILLUMINANCE
                self._attr_native_unit_of_measurement = UnitOfIlluminance.LUX
            elif idx == "V" or idx == "P5": # P5 通常是 Env sensor 的電池電量
                self._attr_device_class = SensorDeviceClass.BATTERY
                self._attr_native_unit_of_measurement = PERCENTAGE
            elif idx == "P3":
                self._attr_device_class = SensorDeviceClass.CO2 
                self._attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
            elif idx == "P4":
                self._attr_device_class = SensorDeviceClass.PM25 # 或是 TVOC
                self._attr_native_unit_of_measurement = CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER

        # 設定初始數值
        self._update_value(val)

    def _update_value(self, data):
        """處理資料數值更新，加入安全取值與單位轉換"""
        if not isinstance(data, dict):
            # 防呆：如果 data 不是字典，嘗試直接轉換
            try:
                self._attr_native_value = float(data)
            except (ValueError, TypeError):
                pass
            return

        # 燃氣類感測器取 val
        if self._devtype in GAS_SENSOR_TYPES:
            self._attr_native_value = data.get('val')
            return

        # 其他感測器優先取用 API 轉換好的 'v' 值
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
                    # TVOC 原始值通常需要除以 1000
                    self._attr_native_value = float(raw_val) / 1000.0
                else:
                    self._attr_native_value = raw_val
            except (ValueError, TypeError):
                _LOGGER.error("無法轉換感測器數值: %s", data)

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
        """處理 WebSocket 推送過來的即時狀態更新"""
        self._update_value(data)
        self.async_write_ha_state()
