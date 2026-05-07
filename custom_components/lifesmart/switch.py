"""lifesmart switch (Config Flow Edition)."""
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.core import callback, HomeAssistant
from homeassistant.config_entries import ConfigEntry

from . import LifeSmartDevice
from .const import DOMAIN, SWTICH_TYPES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """透過 Config Entry 設定 LifeSmart 開關設備"""
    # 從 hass.data 取得在 __init__.py 中初始化的資料
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    param = entry_data["param"]
    devices_list = entry_data.get("devices", [])
    exclude_items = entry_data.get("exclude_items", [])
    
    devices = []
    
    for dev in devices_list:
        if dev['me'] in exclude_items:
            continue
            
        if dev['devtype'] in SWTICH_TYPES:
            # 確保 agt 字串乾淨，與 Dispatcher 和 Unique ID 匹配
            dev['agt'] = dev['agt'].replace("_", "")
            
            for idx in dev.get('data', {}):
                # 篩選出屬於開關的通訊埠
                if idx in ["L1", "L2", "L3", "P1", "P2", "P3"]:
                    devices.append(LifeSmartSwitch(dev, idx, dev['data'][idx], param))
                    
    async_add_entities(devices)

class LifeSmartSwitch(LifeSmartDevice, SwitchEntity):
    """Representation of a LifeSmart Switch."""

    def __init__(self, dev, idx, val, param):
        """Initialize the switch."""
        super().__init__(dev, idx, val, param)
        self._attr_unique_id = f"{dev['devtype']}_{dev['agt']}_{dev['me']}_{idx}".lower()
        self._attr_is_on = False 
        
        # 根據系統啟動時撈到的數據更新初始狀態
        self._update_from_data(val)

    def _update_from_data(self, data):
        """根據數據更新狀態，加入嚴格的型別安全防護"""
        if not isinstance(data, dict):
            # 若系統初始撈到的 val 只是純數值或字串 (例如 "1" 或 0)
            if isinstance(data, (int, str)):
                try:
                    self._attr_is_on = (int(data) == 1)
                except ValueError:
                    pass
            return

        # 處理 dict 格式的 payload
        if 'type' in data:
            try:
                type_val = data['type']
                # 處理 16 進位字串 "0x81" 或 10 進位字串 "129" 或整數 129
                if isinstance(type_val, str):
                    type_val = int(type_val, 16) if type_val.startswith('0x') else int(type_val)
                self._attr_is_on = (type_val % 2 == 1)
            except (ValueError, TypeError):
                _LOGGER.warning("無法解析的 type 值: %s", data['type'])
        elif 'val' in data:
            try:
                self._attr_is_on = (int(data['val']) == 1)
            except (ValueError, TypeError):
                pass

    async def async_added_to_hass(self):
        """訂閱 WebSocket 更新"""
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

    @callback
    def _handle_update(self, data):
        """處理 WebSocket 推送過來的即時狀態更新"""
        self._update_from_data(data)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """開啟設備 (完全非同步操作)"""
        # 直接呼叫父類別的非同步 epset，"0x81" 代表開啟
        if await self.async_lifesmart_epset("0x81", 1, self._idx) == 0:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """關閉設備 (完全非同步操作)"""
        # "0x80" 代表關閉
        if await self.async_lifesmart_epset("0x80", 0, self._idx) == 0:
            self._attr_is_on = False
            self.async_write_ha_state()
