"""lifesmart by @skyzhishui (Optimized Async Version with Dispatcher)"""
import json
import time
import hashlib
import logging
import asyncio
import aiohttp

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.components.climate.const import HVACMode, FAN_HIGH, FAN_LOW, FAN_MEDIUM
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

CONF_LIFESMART_APPKEY = "appkey"
CONF_LIFESMART_APPTOKEN = "apptoken"
CONF_LIFESMART_USERTOKEN = "usertoken"
CONF_LIFESMART_USERID = "userid"
CONF_EXCLUDE_ITEMS = "exclude"

DOMAIN = 'lifesmart'
LifeSmart_STATE_MANAGER = 'lifesmart_wss'

# 設備類型列表 (保持原樣)
SWTICH_TYPES = ["SL_SF_RC", "SL_SW_RC", "SL_SW_IF3", "SL_SF_IF3", "SL_SW_CP3", "SL_SW_RC3", "SL_SW_IF2", "SL_SF_IF2", "SL_SW_CP2", "SL_SW_FE2", "SL_SW_RC2", "SL_SW_ND2", "SL_MC_ND2", "SL_SW_IF1", "SL_SF_IF1", "SL_SW_CP1", "SL_SW_FE1", "SL_OL_W", "SL_SW_RC1", "SL_SW_ND1", "SL_MC_ND1", "SL_SW_ND3", "SL_MC_ND3", "SL_SW_ND2", "SL_MC_ND2", "SL_SW_ND1", "SL_MC_ND1", "SL_S", "SL_SPWM", "SL_P_SW", "SL_SW_DM1", "SL_SW_MJ2", "SL_SW_MJ1", "SL_OL", "SL_OL_3C", "SL_OL_DE", "SL_OL_UK", "SL_OL_UL", "OD_WE_OT1", "SL_NATURE"]
LIGHT_SWITCH_TYPES = ["SL_OL_W"]
SPOT_TYPES = ["MSL_IRCTL", "OD_WE_IRCTL", "SL_SPOT"]
BINARY_SENSOR_TYPES = ["SL_SC_G", "SL_SC_BG", "SL_SC_MHW ", "SL_SC_BM", "SL_SC_CM", "SL_P_A"]
COVER_TYPES = ["SL_DOOYA"]
GAS_SENSOR_TYPES = ["SL_SC_WA ", "SL_SC_CH", "SL_SC_CP", "ELIQ_EM"]
EV_SENSOR_TYPES = ["SL_SC_THL", "SL_SC_BE", "SL_SC_CQ"]
OT_SENSOR_TYPES = ["SL_SC_MHW", "SL_SC_BM", "SL_SC_G", "SL_SC_BG"]
LOCK_TYPES = ["SL_LK_LS", "SL_LK_GTM", "SL_LK_AG", "SL_LK_SG", "SL_LK_YL"]
CLIMATE_TYPES = ["V_AIR_P", "SL_CP_DN"]

# 通用 MD5 簽名產生器
def generate_signature(sdata):
    return hashlib.md5(sdata.encode(encoding='UTF-8')).hexdigest()

# 全面改用 aiohttp 進行非同步 HTTP 請求 (維持美國伺服器)
async def async_lifesmart_EpGetAll(hass, appkey, apptoken, usertoken, userid):
    url = "https://api.us.ilifesmart.com/app/api.EpGetAll"
    tick = int(time.time())
    sdata = f"method:EpGetAll,time:{tick},userid:{userid},usertoken:{usertoken},appkey:{appkey},apptoken:{apptoken}"
    sign = generate_signature(sdata)
    send_values = {
      "id": 1, "method": "EpGetAll",
      "system": {"ver": "1.0", "lang": "en", "userid": userid, "appkey": appkey, "time": tick, "sign": sign}
    }
    
    session = async_get_clientsession(hass)
    try:
        async with session.post(url, json=send_values) as response:
            res = await response.json()
            if res.get('code') == 0:
                return res.get('message')
    except Exception as e:
        _LOGGER.error("EpGetAll error: %s", e)
    return False

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the lifesmart component."""
    if DOMAIN not in config: return True
    conf = config[DOMAIN]
    
    param = {
        'appkey': conf[CONF_LIFESMART_APPKEY], 'apptoken': conf[CONF_LIFESMART_APPTOKEN],
        'usertoken': conf[CONF_LIFESMART_USERTOKEN], 'userid': conf[CONF_LIFESMART_USERID]
    }
    exclude_items = conf.get(CONF_EXCLUDE_ITEMS, [])
    
    devices = await async_lifesmart_EpGetAll(hass, param['appkey'], param['apptoken'], param['usertoken'], param['userid'])
    if not devices: return True

    for dev in devices:
        if dev['me'] in exclude_items: continue
        devtype = dev['devtype']
        dev['agt'] = dev['agt'].replace("_", "")
        platform = None
        
        if devtype in SWTICH_TYPES: platform = "switch"
        elif devtype in BINARY_SENSOR_TYPES: platform = "binary_sensor"
        elif devtype in COVER_TYPES: platform = "cover"
        elif devtype in SPOT_TYPES: platform = "light"
        elif devtype in CLIMATE_TYPES: platform = "climate"
        elif devtype in GAS_SENSOR_TYPES or devtype in EV_SENSOR_TYPES or devtype in OT_SENSOR_TYPES: platform = "sensor"
        elif devtype in LIGHT_SWITCH_TYPES: platform = "light"
        
        if platform:
            hass.async_create_task(
                discovery.async_load_platform(hass, platform, DOMAIN, {"dev": dev, "param": param}, config)
            )

    # 啟動基於 aiohttp 的非同步 WebSocket 管理器
    manager = LifeSmartStatesManager(hass, param, exclude_items)
    hass.data[LifeSmart_STATE_MANAGER] = manager
    await manager.start()

    async def stop_lifesmart(event):
        await manager.stop()
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_lifesmart)
    
    return True

# 基礎 Entity 類別 (修復 staticmethod 與同步 I/O 問題)
class LifeSmartDevice(Entity):
    def __init__(self, dev, idx, val, param):
        self._attr_name = dev['name'] + "_" + idx
        self._appkey = param['appkey']
        self._apptoken = param['apptoken']
        self._usertoken = param['usertoken']
        self._userid = param['userid']
        self._agt = dev['agt']
        self._me = dev['me']
        self._idx = idx
        self._devtype = dev['devtype']
        self._attr_extra_state_attributes = {"agt": self._agt, "me": self._me, "idx": self._idx, "devtype": self._devtype}
        self._attr_should_poll = False

    # =============== [新增這一段開始] ===============
    @property
    def device_info(self):
        """Return the device info. 告訴 HA 這些實體屬於哪個硬體設備"""
        return {
            "identifiers": {(DOMAIN, self._me)},      # 關鍵：以設備的 'me' 作為唯一識別碼
            "name": self._dev_name,                   # 設備的總名稱
            "manufacturer": "LifeSmart",              # 製造商名稱
            "model": self._devtype,                   # 設備型號
            "via_device": (DOMAIN, self._agt),        # 標示此設備是透過哪個智慧中心連接的
        }
    # =============== [新增這一段結束] ===============

    async def async_lifesmart_epset(self, type_val, val, idx):
        """非同步呼叫 API，避免阻塞 HA 事件迴圈"""
        url = "https://api.us.ilifesmart.com/app/api.EpSet"
        tick = int(time.time())
        sdata = f"method:EpSet,agt:{self._agt},idx:{idx},me:{self._me},type:{type_val},val:{val},time:{tick},userid:{self._userid},usertoken:{self._usertoken},appkey:{self._appkey},apptoken:{self._apptoken}"
        sign = generate_signature(sdata)
        send_values = {
          "id": 1, "method": "EpSet",
          "system": {"ver": "1.0", "lang": "en", "userid": self._userid, "appkey": self._appkey, "time": tick, "sign": sign},
          "params": {"agt": self._agt, "me": self._me, "idx": idx, "type": type_val, "val": val}
        }
        
        session = async_get_clientsession(self.hass)
        try:
            async with session.post(url, json=send_values) as response:
                res = await response.json()
                return res.get('code', -1)
        except Exception as e:
            _LOGGER.error("EpSet error: %s", e)
            return -1

# 改用 aiohttp WS，徹底放棄會阻塞的 threading 模式
class LifeSmartStatesManager:
    def __init__(self, hass, param, exclude_items):
        self.hass = hass
        self.param = param
        self.exclude_items = exclude_items
        self._ws = None
        self._run = False

    async def start(self):
        self._run = True
        self.hass.loop.create_task(self.ws_loop())

    async def stop(self):
        self._run = False
        if self._ws:
            await self._ws.close()

    async def ws_loop(self):
        url = "wss://api.us.ilifesmart.com:8443/wsapp/"
        session = async_get_clientsession(self.hass)
        
        while self._run:
            try:
                # 啟用 heartbeat 定期發送 Ping，防止被 Server 端主動斷連
                async with session.ws_connect(url, heartbeat=30.0) as ws:
                    self._ws = ws
                    _LOGGER.info("LifeSmart WebSocket Connected")
                    
                    tick = int(time.time())
                    sdata = f"method:WbAuth,time:{tick},userid:{self.param['userid']},usertoken:{self.param['usertoken']},appkey:{self.param['appkey']},apptoken:{self.param['apptoken']}"
                    sign = generate_signature(sdata)
                    auth_msg = {"id": 1, "method": "WbAuth", "system": {"ver": "1.0", "lang": "en", "userid": self.param['userid'], "appkey": self.param['appkey'], "time": tick, "sign": sign}}
                    await ws.send_json(auth_msg)

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get('type') == 'io':
                                self.handle_event(data['msg'])
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
            except Exception as e:
                _LOGGER.error("LifeSmart WS Error: %s", e)
            
            if self._run:
                await asyncio.sleep(10) # 斷線後延遲重連

    def handle_event(self, data):
        if data.get('idx') == "s" or data.get('me') in self.exclude_items:
            return
            
        devtype = data.get('devtype')
        agt = data.get('agt', '').replace("_", "")
        idx = data.get('idx')
        me = data.get('me')
        
        if devtype and agt and idx and me:
            unique_id = f"{devtype}_{agt}_{me}_{idx}".lower()
            async_dispatcher_send(self.hass, f"lifesmart_update_{unique_id}", data)
