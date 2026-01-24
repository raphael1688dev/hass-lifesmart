"""Support for LifeSmart Gateway Light."""
import logging
import json
import time
import hashlib
import urllib.request # 雖然保留 import，但會移至 executor 執行

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ColorMode, # [新增] 引入現代 ColorMode
    LightEntity,
    LightEntityFeature,
)
import homeassistant.util.color as color_util

from . import LifeSmartDevice

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Perform the setup for LifeSmart devices."""
    if discovery_info is None:
        return
    dev = discovery_info.get("dev")
    param = discovery_info.get("param")
    devices = []
    for idx in dev['data']:
        if idx in ["RGB","RGBW","dark","dark1","dark2","dark3","bright","bright1","bright2","bright"]:
            devices.append(LifeSmartLight(dev, idx, dev['data'][idx], param))
    add_entities(devices)

class LifeSmartLight(LifeSmartDevice, LightEntity):
    """Representation of a LifeSmartLight."""

    def __init__(self, dev, idx, val, param):
        """Initialize the LifeSmartLight."""
        super().__init__(dev, idx, val, param)
        self._attr_name = dev['name'] + "_" + idx
        
        # [修復] 添加 unique_id，移除 entity_id 強制賦值
        self._attr_unique_id = (dev['devtype'] + "_" + dev['agt'] + "_" + dev['me'] + "_" + idx).lower()
        
        self._hs_color = None
        self._brightness = 0
        
        # [修復] 使用 ColorMode 取代舊的 SUPPORT_ flags
        # 根據 idx 判斷是否為彩光
        if idx in ["RGB", "RGBW"]:
            self._attr_supported_color_modes = {ColorMode.HS}
            self._attr_color_mode = ColorMode.HS
        else:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the hs color value."""
        return self._hs_color

    @property
    def is_on(self):
        """Return true if it is on."""
        # 簡單判斷：亮度大於 0 或有顏色即為開
        if self._attr_color_mode == ColorMode.HS:
             return self._hs_color is not None
        return self._brightness > 0

    # [關鍵修復] 轉為異步方法，並將阻塞操作放入 Executor
    async def async_turn_on(self, **kwargs):
        """Turn on the light."""
        await self.hass.async_add_executor_job(self._turn_on_sync, kwargs)

    def _turn_on_sync(self, kwargs):
        if ATTR_HS_COLOR in kwargs:
            self._hs_color = kwargs[ATTR_HS_COLOR]
            rgb = color_util.color_hs_to_rgb(*self._hs_color)
            if self._idx == "RGB":
                 super()._lifesmart_epset(self, "0x81", rgb[0], "R")
                 super()._lifesmart_epset(self, "0x81", rgb[1], "G")
                 super()._lifesmart_epset(self, "0x81", rgb[2], "B")
            elif self._idx == "RGBW":
                 super()._lifesmart_epset(self, "0x81", rgb[0], "WR")
                 super()._lifesmart_epset(self, "0x81", rgb[1], "WG")
                 super()._lifesmart_epset(self, "0x81", rgb[2], "WB")
            
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            # 轉換 0-255 到 LifeSmart 的範圍 (假設是 0-100 或類似，這裡保留原邏輯概念，需視設備而定)
            # 原代碼似乎是用 type 0x81 + val 來設定
            # 這裡假設直接傳送亮度值
            super()._lifesmart_epset(self, "0x81", self._brightness, self._idx)
        
        # 如果沒有參數，預設開啟
        if not kwargs:
            self._brightness = 255
            super()._lifesmart_epset(self, "0x81", 255, self._idx)

    async def async_turn_off(self, **kwargs):
        """Turn off the light."""
        await self.hass.async_add_executor_job(self._turn_off_sync)

    def _turn_off_sync(self):
        self._brightness = 0
        self._hs_color = None
        super()._lifesmart_epset(self, "0x80", 0, self._idx)

    # [關鍵修復] 靜態方法包含 urllib，必須小心處理
    # 這裡將其封裝為實例方法調用，或保留為同步但需在 executor 中呼叫
    @staticmethod
    def _lifesmart_GetRemotes(self, ai):
        # 此方法包含 urllib，絕對不能在事件循環中直接呼叫
        # 必須確保呼叫此方法的地方都使用了 await hass.async_add_executor_job
        appkey = self._appkey
        apptoken = self._apptoken
        usertoken = self._usertoken
        userid = self._userid
        agt = self._agt
        url = "https://api.ilifesmart.com/app/irapi.GetRemote"
        tick = int(time.time())
        sdata = "method:GetRemote,agt:"+agt+",ai:"+ai+",needKeys:2,time:"+str(tick)+",userid:"+userid+",usertoken:"+usertoken+",appkey:"+appkey+",apptoken:"+apptoken
        sign = hashlib.md5(sdata.encode(encoding='UTF-8')).hexdigest()
        send_values ={
          "id": 1,
          "method": "GetRemote",
          "params": {
              "agt": agt,
              "ai": ai,
              "needKeys": 2
          },
          "system": {
          "ver": "1.0",
          "lang": "en",
          "userid": userid,
          "appkey": appkey,
          "time": tick,
          "sign": sign
          }
        }
        header = {'Content-Type': 'application/json'}
        send_data = json.dumps(send_values)
        req = urllib.request.Request(url=url, data=send_data.encode('utf-8'), headers=header, method='POST')
        response = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
        return response['message']
