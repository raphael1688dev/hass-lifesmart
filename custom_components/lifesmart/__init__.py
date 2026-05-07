"""lifesmart by @raphael1688dev (Config Flow Edition)"""
import json
import time
import hashlib
import logging
import asyncio
import aiohttp

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback, HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo

from .const import *

_LOGGER = logging.getLogger(__name__)

def generate_signature(sdata):
    return hashlib.md5(sdata.encode(encoding='UTF-8')).hexdigest()

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
        _LOGGER.error("EpGetAll Error: %s", e)
    return False

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LifeSmart from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    param = {
        'appkey': entry.data[CONF_LIFESMART_APPKEY], 
        'apptoken': entry.data[CONF_LIFESMART_APPTOKEN],
        'usertoken': entry.data[CONF_LIFESMART_USERTOKEN], 
        'userid': entry.data[CONF_LIFESMART_USERID]
    }
    
    # 處理排除清單 (字串轉陣列)
    exclude_str = entry.data.get(CONF_EXCLUDE_ITEMS, "")
    exclude_items = [x.strip() for x in exclude_str.split(",") if x.strip()]
    
    devices = await async_lifesmart_EpGetAll(hass, param['appkey'], param['apptoken'], param['usertoken'], param['userid'])
    if not devices:
        _LOGGER.error("無法獲取設備清單")
        return False

    # 將資料存入 hass.data 供各平台提取
    hass.data[DOMAIN][entry.entry_id] = {
        "param": param,
        "devices": devices,
        "exclude_items": exclude_items
    }

    # 啟動 WebSocket
    manager = LifeSmartStatesManager(hass, param, exclude_items)
    hass.data[DOMAIN][entry.entry_id]["manager"] = manager
    await manager.start()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, manager.stop))

    # 透過 ConfigEntry 載入所有平台
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        manager = hass.data[DOMAIN][entry.entry_id].get("manager")
        if manager:
            await manager.stop()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

class LifeSmartDevice(Entity):
    """基礎設備類別保持不變，保留 DeviceInfo"""
    def __init__(self, dev, idx, val, param):
        self._dev_name = dev['name'] 
        self._attr_name = f"{dev['name']}_{idx}"
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

        # [關鍵修復] 直接將 DeviceInfo 賦值給內部屬性，HA 就會無條件吃掉它
        # 同時移除 via_device，避免因為網關不存在而導致實體被拒絕綁定
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._me)},
            name=self._dev_name,
            manufacturer="LifeSmart",
            model=self._devtype,
            serial_number=self._me,              # 正確載入序號
            sw_version=dev.get('ver')            # 安全載入版本號
        )
        #[重要提醒] 請將原本這裡的 `@property def device_info(self): ...` 整段刪除！

    #@property
    #def device_info(self) -> DeviceInfo:
    #    """實作設備資訊以支援 HA Device Registry"""
    #    return DeviceInfo(
    #        # identifiers 是 HA 內部用來綁定 Entities 的核心
    #        identifiers={(DOMAIN, self._me)},
    #        
    #        # 以下欄位會顯示在前端 UI 的裝置資訊中
    #        name=self._dev_name,
    #        manufacturer="LifeSmart",
    #        model=self._devtype,
    #        serial_number=self._me,         # 將 'me' 作為序號顯示
    #        sw_version=self._sw_version,    # 顯示軟體版本 (如有)
    #        
    #        # via_device 可以建立拓樸關係，標示此設備是透過哪個網關連線的
    #        via_device=(DOMAIN, self._agt), 
    #    )

    async def async_lifesmart_epset(self, type_val, val, idx):
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
            _LOGGER.error("EpSet Error: %s", e)
            return -1


class LifeSmartStatesManager:
    """WebSocket 狀態管理器 (非同步版)"""
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
                async with session.ws_connect(url, heartbeat=30.0) as ws:
                    self._ws = ws
                    _LOGGER.info("LifeSmart WebSocket 已連線")
                    
                    tick = int(time.time())
                    sdata = f"method:WbAuth,time:{tick},userid:{self.param['userid']},usertoken:{self.param['usertoken']},appkey:{self.param['appkey']},apptoken:{self.param['apptoken']}"
                    sign = generate_signature(sdata)
                    auth_msg = {
                        "id": 1, "method": "WbAuth", 
                        "system": {"ver": "1.0", "lang": "en", "userid": self.param['userid'], "appkey": self.param['appkey'], "time": tick, "sign": sign}
                    }
                    await ws.send_json(auth_msg)

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get('type') == 'io':
                                self.handle_event(data['msg'])
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
            except Exception as e:
                _LOGGER.error("LifeSmart WebSocket 錯誤: %s", e)
            
            if self._run:
                await asyncio.sleep(10)

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
                async with session.ws_connect(url, heartbeat=30.0) as ws:
                    self._ws = ws
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
                pass
            if self._run:
                await asyncio.sleep(10)

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
