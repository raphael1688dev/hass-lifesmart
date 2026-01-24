"""Support for the LifeSmart climate devices."""
import logging
import time
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
)
from homeassistant.const import (
    UnitOfTemperature,
    PRECISION_WHOLE,
)

from . import LifeSmartDevice

_LOGGER = logging.getLogger(__name__)

LIFESMART_STATE_LIST = [
    HVACMode.OFF,
    HVACMode.AUTO,
    HVACMode.FAN_ONLY,
    HVACMode.COOL,
    HVACMode.HEAT,
    HVACMode.DRY
]

LIFESMART_STATE_LIST2 = [
    HVACMode.OFF,
    HVACMode.HEAT
]

FAN_MODES = [FAN_LOW, FAN_MEDIUM, FAN_HIGH]
GET_FAN_SPEED = {FAN_LOW: 15, FAN_MEDIUM: 45, FAN_HIGH: 76}

AIR_TYPES = ["V_AIR_P"]
THER_TYPES = ["SL_CP_DN"]

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up LifeSmart Climate devices."""
    if discovery_info is None:
        return
    dev = discovery_info.get("dev")
    param = discovery_info.get("param")
    devices = []
    # 稍微優化判斷邏輯，防止 Key Error
    if "T" not in dev['data'] and "P3" not in dev['data']:
        return
    devices.append(LifeSmartClimateDevice(dev, "idx", "0", param))
    add_entities(devices)

class LifeSmartClimateDevice(LifeSmartDevice, ClimateEntity):
    """LifeSmart climate devices, include air conditioner, heater."""

    def __init__(self, dev, idx, val, param):
        """Init LifeSmart climate device."""
        super().__init__(dev, idx, val, param)
        self._attr_name = dev['name']
        cdata = dev['data']
        
        # [修復] 使用 unique_id，移除 self.entity_id 的強制賦值
        self._attr_unique_id = (dev['devtype'] + "_" + dev['agt'] + "_" + dev['me']).lower().replace(":","_").replace("@","_")
        
        # 根據設備類型初始化屬性
        if dev['devtype'] in AIR_TYPES:
            self._attr_hvac_modes = LIFESMART_STATE_LIST
            # 判斷當前模式
            if cdata['O']['type'] % 2 == 0:
                self._attr_hvac_mode = HVACMode.OFF
            else:
                val_idx = cdata['MODE']['val']
                if 0 <= val_idx < len(LIFESMART_STATE_LIST):
                    self._attr_hvac_mode = LIFESMART_STATE_LIST[val_idx]
                else:
                    self._attr_hvac_mode = HVACMode.AUTO # Fallback
            
            # 更新額外屬性，並做邊界檢查
            last_mode_idx = cdata['MODE']['val']
            if 0 <= last_mode_idx < len(LIFESMART_STATE_LIST):
                self._attr_extra_state_attributes.update({"last_mode": LIFESMART_STATE_LIST[last_mode_idx]})
            
            self._attr_current_temperature = cdata['T']['v']
            self._attr_target_temperature = cdata['tT']['v']
            self._attr_min_temp = 10
            self._attr_max_temp = 35
            self._fanspeed = cdata['F']['val']
        else:
            self._attr_hvac_modes = LIFESMART_STATE_LIST2
            # 判斷加熱器模式
            if cdata['P1']['type'] % 2 == 0:
                self._attr_hvac_mode = HVACMode.OFF
            else:
                self._attr_hvac_mode = HVACMode.HEAT
            
            if cdata['P2']['type'] % 2 == 0:
                self._attr_extra_state_attributes.setdefault('Heating', "false")
            else:
                self._attr_extra_state_attributes.setdefault('Heating', "true")
            
            self._attr_current_temperature = cdata['P4']['val'] / 10
            self._attr_target_temperature = cdata['P3']['val'] / 10
            self._attr_min_temp = 5
            self._attr_max_temp = 35

    @property
    def precision(self):
        return PRECISION_WHOLE

    @property
    def temperature_unit(self):
        return UnitOfTemperature.CELSIUS

    @property
    def target_temperature_step(self):
        return 1

    @property
    def fan_mode(self):
        if self._fanspeed < 30:
            return FAN_LOW
        elif 30 <= self._fanspeed < 65:
            return FAN_MEDIUM
        else:
            return FAN_HIGH

    @property
    def fan_modes(self):
        return FAN_MODES

    @property
    def supported_features(self):
        """Return the list of supported features."""
        features = ClimateEntityFeature.TARGET_TEMPERATURE
        
        # [修復] 明確宣告支持 TURN_ON / TURN_OFF，符合新版規範
        features |= ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        
        if self._devtype in AIR_TYPES:
            features |= ClimateEntityFeature.FAN_MODE
        return features

    # [關鍵修復] 轉為異步方法，並將阻塞操作放入 Executor
    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        await self.hass.async_add_executor_job(self._set_temperature_sync, kwargs)

    def _set_temperature_sync(self, kwargs):
        new_temp = int(kwargs['temperature'] * 10)
        _LOGGER.info("set_temperature: %s", str(new_temp))
        if self._devtype in AIR_TYPES:
            super()._lifesmart_epset(self, "0x88", new_temp, "tT")
        else:
            super()._lifesmart_epset(self, "0x88", new_temp, "P3")

    # [關鍵修復] 轉為異步方法
    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        await self.hass.async_add_executor_job(self._set_fan_mode_sync, fan_mode)

    def _set_fan_mode_sync(self, fan_mode):
        super()._lifesmart_epset(self, "0xCE", GET_FAN_SPEED[fan_mode], "F")

    # [關鍵修復] 處理 time.sleep 的阻塞問題
    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target operation mode."""
        await self.hass.async_add_executor_job(self._set_hvac_mode_sync, hvac_mode)

    def _set_hvac_mode_sync(self, hvac_mode):
        if self._devtype in AIR_TYPES:
            if hvac_mode == HVACMode.OFF:
                super()._lifesmart_epset(self, "0x80", 0, "O")
                return
            
            # 如果是從關閉狀態開啟，需要先發送開啟指令
            if self.hvac_mode == HVACMode.OFF:
                if super()._lifesmart_epset(self, "0x81", 1, "O") == 0:
                    time.sleep(2) # 這裡在 Executor 中執行，是安全的
                else:
                    return
            
            if hvac_mode in LIFESMART_STATE_LIST:
                super()._lifesmart_epset(self, "0xCE", LIFESMART_STATE_LIST.index(hvac_mode), "MODE")
        else:
            if hvac_mode == HVACMode.OFF:
                super()._lifesmart_epset(self, "0x80", 0, "P1")
                time.sleep(1) # 安全
                super()._lifesmart_epset(self, "0x80", 0, "P2")
                return
            else:
                if super()._lifesmart_epset(self, "0x81", 1, "P1") == 0:
                    time.sleep(2) # 安全
                else:
                    return

    async def async_turn_on(self):
        """Turn on."""
        await self.hass.async_add_executor_job(self._turn_on_sync)

    def _turn_on_sync(self):
        super()._lifesmart_epset(self, "0x81", 1, "O")

    async def async_turn_off(self):
        """Turn off."""
        await self.hass.async_add_executor_job(self._turn_off_sync)

    def _turn_off_sync(self):
        super()._lifesmart_epset(self, "0x80", 0, "O")
