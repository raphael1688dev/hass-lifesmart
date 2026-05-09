"""lifesmart by @skyzhishui (Config Flow Edition with Device Registry Fix)"""
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
    """LifeSmart 設備基礎類別"""
    
    # 啟用新版 HA 命名規範：實體名稱 = 設備名稱 + 索引名稱
    _attr_has_entity_name = True

    def __init__(self, dev, idx, val, param):
        self._agt = dev['agt'].replace("_", "")
        self._me = str(dev['me']) # 確保為字串
        self._devtype = dev['devtype']
        self._idx = idx
        
        # 1. 設定 Unique ID (這是與 Device 綁定的唯一金鑰)
        self._attr_unique_id = f"{self._devtype}_{self._agt}_{self._me}_{idx}".lower()
        
        # 2. 設定 Device Info (這會產生設備卡片並顯示序號，已移除 via_device)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._me)},
            name=dev['name'],
            manufacturer="LifeSmart",
            model=self._devtype,
            serial_number=self._me,
            sw_version=dev.get('ver'),
        )
        
        # 3. 設定實體顯示名稱 (在設備頁面顯示如 "L1", "P1")
        self._attr_name = idx 
        
        # API 參數與屬性
        self._appkey = param['appkey']
        self._apptoken = param['apptoken']
        self._usertoken = param['usertoken']
        self._userid = param['userid']
        self._attr_extra_state_attributes = {
            "agt": self._agt, 
            "me": self._me, 
            "idx": self._idx, 
            "devtype": self._devtype
        }
        self._attr_should_poll = False

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
    def __init__(self, hass, param, exclude_items):
        self.hass = hass
        self.param = param
        self.exclude_items = exclude_items
        self._ws = None
        self._run = False

    async def start(self):
        self._run = True
        self.hass.loop.create_task(self.ws_loop())

    #async def stop(self):
    #    self._run = False
    #    if self._ws:
    #        await self._ws.close()
    # 加入 event=None 來接收 HA 傳遞的關機事件物件，
    # 預設為 None 是為了相容我們在卸載整合 (async_unload_entry) 時不帶參數的呼叫。
    async def stop(self, event=None):
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
