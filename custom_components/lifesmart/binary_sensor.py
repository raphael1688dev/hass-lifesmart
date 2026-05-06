"""Support for LifeSmart binary sensors."""
import logging
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
    ENTITY_ID_FORMAT,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.core import callback

from . import LifeSmartDevice

_LOGGER = logging.getLogger(__name__)

# 支援的設備清單 (根據 API 文件可以擴充 DEFED 系列如 SL_DF_GG, SL_DF_MM)
GUARD_SENSOR = ["SL_SC_G", "SL_SC_BG", "SL_DF_GG"]
MOTION_SENSOR = ["SL_SC_MHW", "SL_SC_BM", "SL_SC_CM", "SL_DF_MM"]
SMOKE_SENSOR = ["SL_P_A", "SLPA"] # 文件中煙霧感測器也可能是 SLPA

# 改用非同步 setup
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Perform the setup for lifesmart devices."""
    if discovery_info is None:
        return
        
    dev = discovery_info.get("dev")
    param = discovery_info.get("param")
    region = discovery_info.get("region", "us") # 配合最新架構接收 region
    
    devices = []
    for idx in dev.get('data', {}):
        # API 文件中 M=Motion, G=Guard, B=Button, AXS=Vibration, P1=Smoke
        if idx in ["M", "G", "B", "AXS", "P1"]:
            devices.append(LifeSmartBinarySensor(dev, idx, dev['data'][idx], param, region))
            
    async_add_entities(devices)

class LifeSmartBinarySensor(LifeSmartDevice, BinarySensorEntity):
    """Representation of LifeSmartBinarySensor."""

    def __init__(self, dev, idx, val, param, region):
        super().__init__(dev, idx, val, param, region)
        
        # 保持與現有自動化的兼容性
        self.entity_id = ENTITY_ID_FORMAT.format((dev['devtype'] + "_" + dev['agt'] + "_" + dev['me'] + "_" + idx).lower())
        
        # [修復] 確保 agt 是乾淨的，與 __init__.py 中的 dispatcher 訊號完全一致
        clean_agt = dev['agt'].replace("_", "")
        self._attr_unique_id = f"{dev['devtype']}_{clean_agt}_{dev['me']}_{idx}".lower()

        devtype = dev['devtype']
        
        if devtype in GUARD_SENSOR:
            self._attr_device_class = BinarySensorDeviceClass.DOOR
        elif devtype in MOTION_SENSOR:
            self._attr_device_class = BinarySensorDeviceClass.MOTION
        elif devtype in SMOKE_SENSOR:
            self._attr_device_class = BinarySensorDeviceClass.SMOKE
        else:
            # 預設給予一個通用的感測器類別或留空
            self._attr_device_class = None
            
        # 初始狀態判斷邏輯
        self._update_state(val)

    def _update_state(self, data):
        """Internal method to update state based on value with type safety."""
        raw_val = None
        
        if not isinstance(data, dict):
            # 如果傳入的是純數值 (例如系統初次啟動時的 fallback)
            raw_val = data
        else:
            # 如果是 WebSocket 推送的 JSON payload
            if 'val' in data:
                raw_val = data['val']
            elif 'type' in data:
                # 兼容某些 API 靠 type % 2 決定狀態的感測器 (如 DEFED 系列)
                try:
                    t = int(data['type'], 16) if isinstance(data['type'], str) and data['type'].startswith('0x') else int(data['type'])
                    raw_val = t % 2
                except (ValueError, TypeError):
                    pass

        # 若無法解析出有用的數值，則直接返回，保持原狀態
        if raw_val is None:
            return

        try:
            val_int = int(raw_val)
        except (ValueError, TypeError):
            _LOGGER.warning("無法將感測器狀態轉換為整數: %s", raw_val)
            return

        # 狀態判定邏輯
        # 門窗傳感器通常是: 0=閉合(Off), 1=打開(On)
        # 但依照您原有的特殊反向邏輯：val == 0 時判定為開啟 (True)
        if self._attr_device_class == BinarySensorDeviceClass.DOOR:
            self._attr_is_on = (val_int == 0)
        else:
            # 其他傳感器 (如人體、煙霧) 正常邏輯：val == 1 為觸發 (True)
            self._attr_is_on = (val_int == 1)

    # [關鍵修復] 實作 WebSocket 更新訂閱
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
        """處理 WebSocket 推送過來的更新"""
        self._update_state(data)
        self.async_write_ha_state()

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._attr_is_on
