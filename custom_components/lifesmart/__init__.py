"""lifesmart by @skyzhishui (Final Fix with Dispatcher)"""
import urllib.request
import json
import time
import hashlib
import logging
import threading
import websocket
import asyncio

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.components.climate.const import HVACMode, FAN_HIGH, FAN_LOW, FAN_MEDIUM
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.dispatcher import async_dispatcher_send

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

def lifesmart_EpGetAll(appkey, apptoken, usertoken, userid):
    url = "https://api.us.ilifesmart.com/app/api.EpGetAll"
    tick = int(time.time())
    sdata = "method:EpGetAll,time:"+str(tick)+",userid:"+userid+",usertoken:"+usertoken+",appkey:"+appkey+",apptoken:"+apptoken
    sign = hashlib.md5(sdata.encode(encoding='UTF-8')).hexdigest()
    send_values = {
      "id": 1, "method": "EpGetAll",
      "system": {"ver": "1.0", "lang": "en", "userid": userid, "appkey": appkey, "time": tick, "sign": sign}
    }
    header = {'Content-Type': 'application/json'}
    try:
        req = urllib.request.Request(url=url, data=json.dumps(send_values).encode('utf-8'), headers=header, method='POST')
        response = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
        if response['code'] == 0:
            return response['message']
        return False
    except Exception as e:
        _LOGGER.error("EpGetAll error: %s", e)
        return False

def lifesmart_Sendkeys(appkey, apptoken, usertoken, userid, agt, ai, me, category, brand, keys):
    url = "https://api.us.ilifesmart.com/app/irapi.SendKeys"
    tick = int(time.time())
    sdata = "method:SendKeys,agt:"+agt+",ai:"+ai+",brand:"+brand+",category:"+category+",keys:"+keys+",me:"+me+",time:"+str(tick)+",userid:"+userid+",usertoken:"+usertoken+",appkey:"+appkey+",apptoken:"+apptoken
    sign = hashlib.md5(sdata.encode(encoding='UTF-8')).hexdigest()
    send_values = {
      "id": 1, "method": "SendKeys",
      "params": {"agt": agt, "me": me, "category": category, "brand": brand, "ai": ai, "keys": keys},
      "system": {"ver": "1.0", "lang": "en", "userid": userid, "appkey": appkey, "time": tick, "sign": sign}
    }
    header = {'Content-Type': 'application/json'}
    req = urllib.request.Request(url=url, data=json.dumps(send_values).encode('utf-8'), headers=header, method='POST')
    return json.loads(urllib.request.urlopen(req).read().decode('utf-8'))

def lifesmart_Sendackeys(appkey, apptoken, usertoken, userid, agt, ai, me, category, brand, keys, power, mode, temp, wind, swing):
    url = "https://api.us.ilifesmart.com/app/irapi.SendACKeys"
    tick = int(time.time())
    sdata = "method:SendACKeys,agt:"+agt+",ai:"+ai+",brand:"+brand+",category:"+category+",keys:"+keys+",me:"+me+",mode:"+str(mode)+",power:"+str(power)+",swing:"+str(swing)+",temp:"+str(temp)+",wind:"+str(wind)+",time:"+str(tick)+",userid:"+userid+",usertoken:"+usertoken+",appkey:"+appkey+",apptoken:"+apptoken
    sign = hashlib.md5(sdata.encode(encoding='UTF-8')).hexdigest()
    send_values = {
      "id": 1, "method": "SendACKeys",
      "params": {"agt": agt, "me": me, "category": category, "brand": brand, "ai": ai, "keys": keys, "power": power, "mode": mode, "temp": temp, "wind": wind, "swing": swing},
      "system": {"ver": "1.0", "lang": "en", "userid": userid, "appkey": appkey, "time": tick, "sign": sign}
    }
    header = {'Content-Type': 'application/json'}
    req = urllib.request.Request(url=url, data=json.dumps(send_values).encode('utf-8'), headers=header, method='POST')
    return json.loads(urllib.request.urlopen(req).read().decode('utf-8'))

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the lifesmart component."""
    if DOMAIN not in config: return True
    conf = config[DOMAIN]
    param = {
        'appkey': conf[CONF_LIFESMART_APPKEY], 'apptoken': conf[CONF_LIFESMART_APPTOKEN],
        'usertoken': conf[CONF_LIFESMART_USERTOKEN], 'userid': conf[CONF_LIFESMART_USERID]
    }
    exclude_items = conf.get(CONF_EXCLUDE_ITEMS, [])
    
    # [Fix] 異步獲取設備
    devices = await hass.async_add_executor_job(lifesmart_EpGetAll, param['appkey'], param['apptoken'], param['usertoken'], param['userid'])
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
            discovery.load_platform(hass, platform, DOMAIN, {"dev": dev, "param": param}, config)

    async def async_send_keys(call):
        await hass.async_add_executor_job(lifesmart_Sendkeys, param['appkey'], param['apptoken'], param['usertoken'], param['userid'], call.data['agt'], call.data['ai'], call.data['me'], call.data['category'], call.data['brand'], call.data['keys'])
    
    async def async_send_ackeys(call):
        await hass.async_add_executor_job(lifesmart_Sendackeys, param['appkey'], param['apptoken'], param['usertoken'], param['userid'], call.data['agt'], call.data['ai'], call.data['me'], call.data['category'], call.data['brand'], call.data['keys'], call.data['power'], call.data['mode'], call.data['temp'], call.data['wind'], call.data['swing'])

    hass.services.async_register(DOMAIN, 'send_keys', async_send_keys)
    hass.services.async_register(DOMAIN, 'send_ackeys', async_send_ackeys)

    @callback
    def handle_event_in_main_thread(msg):
        # [Debug] 打印收到的訊息，幫助排查
        _LOGGER.debug(f"LifeSmart WS Event: {msg}")
        
        data = msg['msg']
        if data['idx'] == "s" or data['me'] in exclude_items: return
        
        devtype = data['devtype']
        agt = data['agt'].replace("_", "")
        idx = data['idx']
        
        # 構建 Unique ID (必須與 switch.py 一致)
        unique_id = (devtype + "_" + agt + "_" + data['me'] + "_" + idx).lower()
        
        # 使用 Dispatcher 發送更新信號給對應的實體
        async_dispatcher_send(hass, f"lifesmart_update_{unique_id}", data)

    def on_message(ws, message):
        if not message: return
        try:
            msg = json.loads(message)
            if msg.get('type') != "io": return
            hass.add_job(handle_event_in_main_thread, msg)
        except Exception as e:
            _LOGGER.error(f"WS Decode Error: {e}")

    def on_error(ws, error):
        _LOGGER.error(f"WS Error: {error}")

    def on_close(ws, *args):
        _LOGGER.debug("WS Closed")

    def on_open(ws):
        tick = int(time.time())
        sdata = "method:WbAuth,time:"+str(tick)+",userid:"+param['userid']+",usertoken:"+param['usertoken']+",appkey:"+param['appkey']+",apptoken:"+param['apptoken']
        sign = hashlib.md5(sdata.encode(encoding='UTF-8')).hexdigest()
        send_values = {"id": 1, "method": "WbAuth", "system": {"ver": "1.0", "lang": "en", "userid": param['userid'], "appkey": param['appkey'], "time": tick, "sign": sign}}
        ws.send(json.dumps(send_values))

    ws = websocket.WebSocketApp("wss://api.us.ilifesmart.com:8443/wsapp/", on_message=on_message, on_error=on_error, on_close=on_close)
    ws.on_open = on_open
    
    manager = LifeSmartStatesManager(ws)
    hass.data[LifeSmart_STATE_MANAGER] = manager
    manager.start_keep_alive()

    def stop_lifesmart(event):
        manager.stop_keep_alive()
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_lifesmart)
    return True

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

    @staticmethod
    def _lifesmart_epset(self, type, val, idx):
        url = "https://api.us.ilifesmart.com/app/api.EpSet"
        tick = int(time.time())
        sdata = "method:EpSet,agt:"+ self._agt +",idx:"+idx+",me:"+self._me+",type:"+type+",val:"+str(val)+",time:"+str(tick)+",userid:"+self._userid+",usertoken:"+self._usertoken+",appkey:"+self._appkey+",apptoken:"+self._apptoken
        sign = hashlib.md5(sdata.encode(encoding='UTF-8')).hexdigest()
        send_values = {
          "id": 1, "method": "EpSet",
          "system": {"ver": "1.0", "lang": "en", "userid": self._userid, "appkey": self._appkey, "time": tick, "sign": sign},
          "params": {"agt": self._agt, "me": self._me, "idx": idx, "type": type, "val": val}
        }
        header = {'Content-Type': 'application/json'}
        try:
            req = urllib.request.Request(url=url, data=json.dumps(send_values).encode('utf-8'), headers=header, method='POST')
            response = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
            return response['code']
        except Exception:
            return -1

class LifeSmartStatesManager(threading.Thread):
    def __init__(self, ws):
        threading.Thread.__init__(self)
        self._run = False
        self._ws = ws
    def run(self):
        while self._run:
            self._ws.run_forever()
            time.sleep(10)
    def start_keep_alive(self):
        self._run = True
        self.start()
    def stop_keep_alive(self):
        self._run = False
        self._ws.close()
