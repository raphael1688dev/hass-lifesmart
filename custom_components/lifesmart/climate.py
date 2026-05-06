"""Support for the LifeSmart climate devices."""
import logging
import asyncio
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
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.core import callback

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

# 改為非同步 Setup
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up LifeSmart Climate devices."""
    if discovery_info is None:
        return
    dev = discovery_info.get("dev")
    param = discovery_info.get("param")
    region = discovery_info.get("region", "us")
    
    # 優化判斷邏輯，防止 Key Error
    if "T" not in dev.get('data', {}) and "P3" not in dev.get('data', {}):
        return
        
    async_add_entities([LifeSmartClimateDevice(dev, "idx", "0", param, region)])

class LifeSmartClimateDevice(LifeSmartDevice, ClimateEntity):
    """LifeSmart climate devices, include air conditioner, heater."""

    def __init__(self, dev, idx, val, param, region):
        """Init LifeSmart climate device."""
        super().__init__(dev, idx, val, param, region)
        self._attr_name = dev['name']
        cdata = dev['data']
        
        # 確保 agt 是乾淨的，對齊 Dispatcher
        clean_agt = dev['agt'].replace("_", "")
        self._attr_unique_id = f"{dev['devtype']}_{clean_agt}_{dev['me']}".lower()
        
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._fanspeed = 0
        
        # 初始狀態解析
        self._parse_initial_data(cdata)

    def _parse_initial_data(self, cdata):
        """安全解析初始資料"""
        if self._devtype in AIR_TYPES:
            self._attr_hvac_modes = LIFESMART_STATE_LIST
            o_port = cdata.get('O', {})
            mode_port = cdata.get('MODE', {})
            
            # 安全取值與型別轉換
            type_val = o_port.get('type', 0)
            if isinstance(type_val, str):
                type_val = int(type_val, 16) if type_val.startswith('0x') else int(type_val)

            if type_val % 2 == 0:
                self._attr_hvac_mode = HVACMode.OFF
            else:
                val_idx = int(mode_port.get('val', 1))
                if 0 <= val_idx < len(LIFESMART_STATE_LIST):
                    self._attr_hvac_mode = LIFESMART_STATE_LIST[val_idx]
                else:
                    self._attr_hvac_mode = HVACMode.AUTO
            
            # 解析溫度與風速
            t_data = cdata.get('T', {})
            tt_data = cdata.get('tT', {})
            self._attr_current_temperature = t_data.get('v', t_data.get('val', 0) / 10.0)
            self._attr_target_temperature = tt_data.get('v', tt_data.get('val', 0) / 10.0)
            self._fanspeed = int(cdata.get('F', {}).get('val', 0))
            
            self._attr_min_temp = 10
            self._attr_max_temp = 35
        else:
            self._attr_hvac_modes = LIFESMART_STATE_LIST2
            p1_port = cdata.get('P1', {})
            p2_port = cdata.get('P2', {})
            
            type_val = p1_port.get('type', 0)
            if isinstance(type_val, str):
                type_val = int(type_val, 16) if type_val.startswith('0x') else int(type_val)

            if type_val % 2 == 0:
                self._attr_hvac_mode = HVACMode.OFF
            else:
                self._attr_hvac_mode = HVACMode.HEAT
            
            p4_data = cdata.get('P4', {})
            p3_data = cdata.get('P3', {})
            self._attr_current_temperature = p4_data.get('v', p4_data.get('val', 0) / 10.0)
            self._attr_target_temperature = p3_data.get('v', p3_data.get('val', 0) / 10.0)
            
            self._attr_min_temp = 5
            self._attr_max_temp = 35

    async def async_added_to_hass(self):
        """訂閱 WebSocket 更新。
        由於 Climate 設備涉及多個 IO ports，我們需要訂閱所有相關的 Ports。
        """
        listen_ports = ["O", "MODE", "F", "tT", "T"] if self._devtype in AIR_TYPES else ["P1", "P2", "P3", "P4"]
        clean_agt = self._agt.replace("_", "")
        
        for port in listen_ports:
            uid = f"{self._devtype}_{clean_agt}_{self._me}_{port}".lower()
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"lifesmart_update_{uid}",
                    self._handle_update
                )
            )

    @callback
    def _handle_update(self, data):
        """處理 WebSocket 推送過來的單一 IO 更新"""
        idx = data.get('idx')
        val = data.get('val')
        v = data.get('v')
        
        try:
            val_int = int(val) if val is not None else None
        except ValueError:
            val_int = None

        if self._devtype in AIR_TYPES:
            if idx == "O":
                type_val = data.get('type', 0)
                if isinstance(type_val, str):
                    type_val = int(type_val, 16) if type_val.startswith('0x') else int(type_val)
                if type_val % 2 == 0:
                    self._attr_hvac_mode = HVACMode.OFF
            elif idx == "MODE" and val_int is not None:
                if 0 <= val_int < len(LIFESMART_STATE_LIST):
                    self._attr_hvac_mode = LIFESMART_STATE_LIST[val_int]
            elif idx == "T":
                self._attr_current_temperature = v if v is not None else (val_int / 10.0 if val_int else None)
            elif idx == "tT":
                self._attr_target_temperature = v if v is not None else (val_int / 10.0 if val_int else None)
            elif idx == "F" and val_int is not None:
                self._fanspeed = val_int
        else: # THER_TYPES
            if idx == "P1":
                type_val = data.get('type', 0)
                if isinstance(type_val, str):
                    type_val = int(type_val, 16) if type_val.startswith('0x') else int(type_val)
                if type_val % 2 == 0:
                    self._attr_hvac_mode = HVACMode.OFF
                else:
                    self._attr_hvac_mode = HVACMode.HEAT
            elif idx == "P4":
                self._attr_current_temperature = v if v is not None else (val_int / 10.0 if val_int else None)
            elif idx == "P3":
                self._attr_target_temperature = v if v is not None else (val_int / 10.0 if val_int else None)
                
        self.async_write_ha_state()

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
        features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        if self._devtype in AIR_TYPES:
            features |= ClimateEntityFeature.FAN_MODE
        return features

    # 全部改為原生非同步方法 (Native Async)
    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        new_temp = int(kwargs['temperature'] * 10)
        if self._devtype in AIR_TYPES:
            await self.async_lifesmart_epset("0x88", new_temp, "tT")
        else:
            await self.async_lifesmart_epset("0x88", new_temp, "P3")

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        await self.async_lifesmart_epset("0xCE", GET_FAN_SPEED[fan_mode], "F")

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target operation mode."""
        if self._devtype in AIR_TYPES:
            if hvac_mode == HVACMode.OFF:
                await self.async_lifesmart_epset("0x80", 0, "O")
                return
            
            # 如果是從關閉狀態開啟，先發送開啟指令並使用非阻塞等待
            if self.hvac_mode == HVACMode.OFF:
                if await self.async_lifesmart_epset("0x81", 1, "O") == 0:
                    await asyncio.sleep(2) # [修復] 使用無阻塞的 asyncio.sleep
                else:
                    return
            
            if hvac_mode in LIFESMART_STATE_LIST:
                await self.async_lifesmart_epset("0xCE", LIFESMART_STATE_LIST.index(hvac_mode), "MODE")
        else:
            if hvac_mode == HVACMode.OFF:
                await self.async_lifesmart_epset("0x80", 0, "P1")
                await asyncio.sleep(1)
                await self.async_lifesmart_epset("0x80", 0, "P2")
            else:
                await self.async_lifesmart_epset("0x81", 1, "P1")

    async def async_turn_on(self):
        """Turn on."""
        # [修復] 根據 API 規範正確區分通訊埠口
        if self._devtype in AIR_TYPES:
            await self.async_lifesmart_epset("0x81", 1, "O")
        else:
            await self.async_lifesmart_epset("0x81", 1, "P1")

    async def async_turn_off(self):
        """Turn off."""
        # [修復] 根據 API 規範正確區分通訊埠口
        if self._devtype in AIR_TYPES:
            await self.async_lifesmart_epset("0x80", 0, "O")
        else:
            await self.async_lifesmart_epset("0x80", 0, "P1")
            await asyncio.sleep(1)
            await self.async_lifesmart_epset("0x80", 0, "P2")
