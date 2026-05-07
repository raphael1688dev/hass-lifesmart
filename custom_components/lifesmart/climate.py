"""Support for the LifeSmart climate devices (Config Flow Edition)."""
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
from homeassistant.core import callback, HomeAssistant
from homeassistant.config_entries import ConfigEntry

from . import LifeSmartDevice
from .const import DOMAIN, CLIMATE_TYPES

_LOGGER = logging.getLogger(__name__)

LIFESMART_STATE_LIST = [
    HVACMode.OFF, HVACMode.AUTO, HVACMode.FAN_ONLY,
    HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY
]

LIFESMART_STATE_LIST2 = [HVACMode.OFF, HVACMode.HEAT]

FAN_MODES = [FAN_LOW, FAN_MEDIUM, FAN_HIGH]
GET_FAN_SPEED = {FAN_LOW: 15, FAN_MEDIUM: 45, FAN_HIGH: 76}

AIR_TYPES = ["V_AIR_P"]
THER_TYPES = ["SL_CP_DN"]

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """透過 Config Entry 設定 LifeSmart 空調設備"""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    param = entry_data["param"]
    devices_list = entry_data.get("devices", [])
    exclude_items = entry_data.get("exclude_items", [])
    
    devices = []
    for dev in devices_list:
        if dev['me'] in exclude_items:
            continue
            
        if dev['devtype'] in CLIMATE_TYPES:
            dev['agt'] = dev['agt'].replace("_", "")
            if "T" not in dev.get('data', {}) and "P3" not in dev.get('data', {}):
                continue
            devices.append(LifeSmartClimateDevice(dev, "idx", "0", param))
            
    async_add_entities(devices)

class LifeSmartClimateDevice(LifeSmartDevice, ClimateEntity):
    """LifeSmart climate devices, include air conditioner, heater."""

    def __init__(self, dev, idx, val, param):
        """Init LifeSmart climate device."""
        super().__init__(dev, idx, val, param)
        self._attr_name = dev['name']
        cdata = dev['data']
        
        clean_agt = dev['agt'].replace("_", "")
        #self._attr_unique_id = f"{dev['devtype']}_{clean_agt}_{dev['me']}".lower()
        # 新增這行
        self.entity_id = f"climate.{dev['devtype']}_{dev['me']}".lower()
        
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._fanspeed = 0
        
        self._parse_initial_data(cdata)

    def _parse_initial_data(self, cdata):
        if self._devtype in AIR_TYPES:
            self._attr_hvac_modes = LIFESMART_STATE_LIST
            o_port = cdata.get('O', {})
            mode_port = cdata.get('MODE', {})
            
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
        else:
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
        if self._fanspeed < 30: return FAN_LOW
        elif 30 <= self._fanspeed < 65: return FAN_MEDIUM
        else: return FAN_HIGH

    @property
    def fan_modes(self):
        return FAN_MODES

    @property
    def supported_features(self):
        features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        if self._devtype in AIR_TYPES:
            features |= ClimateEntityFeature.FAN_MODE
        return features

    async def async_set_temperature(self, **kwargs):
        new_temp = int(kwargs['temperature'] * 10)
        if self._devtype in AIR_TYPES:
            await self.async_lifesmart_epset("0x88", new_temp, "tT")
        else:
            await self.async_lifesmart_epset("0x88", new_temp, "P3")

    async def async_set_fan_mode(self, fan_mode):
        await self.async_lifesmart_epset("0xCE", GET_FAN_SPEED[fan_mode], "F")

    async def async_set_hvac_mode(self, hvac_mode):
        if self._devtype in AIR_TYPES:
            if hvac_mode == HVACMode.OFF:
                await self.async_lifesmart_epset("0x80", 0, "O")
                return
            if self.hvac_mode == HVACMode.OFF:
                if await self.async_lifesmart_epset("0x81", 1, "O") == 0:
                    await asyncio.sleep(2)
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
        if self._devtype in AIR_TYPES:
            await self.async_lifesmart_epset("0x81", 1, "O")
        else:
            await self.async_lifesmart_epset("0x81", 1, "P1")

    async def async_turn_off(self):
        if self._devtype in AIR_TYPES:
            await self.async_lifesmart_epset("0x80", 0, "O")
        else:
            await self.async_lifesmart_epset("0x80", 0, "P1")
            await asyncio.sleep(1)
            await self.async_lifesmart_epset("0x80", 0, "P2")
