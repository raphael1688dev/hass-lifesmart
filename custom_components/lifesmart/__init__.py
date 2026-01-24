async def set_Event(msg):
        if msg['msg']['idx'] != "s" and msg['msg']['me'] not in exclude_items:
            devtype = msg['msg']['devtype']
            agt = msg['msg']['agt'].replace("_","")
            
            # --- Switch 類型 ---
            if devtype in SWTICH_TYPES and msg['msg']['idx'] in ["L1","L2","L3","P1","P2","P3"]:
                enid = "switch."+(devtype + "_" + agt + "_" + msg['msg']['me'] + "_" + msg['msg']['idx']).lower()
                state = hass.states.get(enid)
                if state is None:
                    return
                attrs = dict(state.attributes)
                if msg['msg']['type'] % 2 == 1:
                    hass.states.set(enid, 'on', attrs)
                else:
                    hass.states.set(enid, 'off', attrs)
            
            # --- Binary Sensor 類型 ---
            elif devtype in BINARY_SENSOR_TYPES and msg['msg']['idx'] in ["M","G","B","AXS","P1"]:
                enid = "binary_sensor."+(devtype + "_" + agt + "_" + msg['msg']['me'] + "_" + msg['msg']['idx']).lower()
                state = hass.states.get(enid)
                if state is None:
                    return
                attrs = dict(state.attributes)
                if msg['msg']['val'] == 1:
                    hass.states.set(enid, 'on', attrs)
                else:
                    hass.states.set(enid, 'off', attrs)

            # --- Cover 類型 ---
            elif devtype in COVER_TYPES and msg['msg']['idx'] == "P1":
                enid = "cover."+(devtype + "_" + agt + "_" + msg['msg']['me']).lower()
                state = hass.states.get(enid)
                if state is None:
                    return
                attrs = dict(state.attributes)
                nval = msg['msg']['val']
                ntype = msg['msg']['type']
                attrs['current_position'] = nval & 0x7F
                _LOGGER.debug("websocket_cover_attrs: %s",str(attrs))
                nstat = None
                if ntype % 2 == 0:
                    if nval > 0:
                        nstat = "open"
                    else:
                        nstat = "closed"
                else:
                    if nval & 0x80 == 0x80:
                        nstat = "opening"
                    else:
                        nstat = "closing"
                hass.states.set(enid, nstat, attrs)
            
            # --- EV Sensor 類型 ---
            elif devtype in EV_SENSOR_TYPES:
                enid = "sensor."+(devtype + "_" + agt + "_" + msg['msg']['me'] + "_" + msg['msg']['idx']).lower()
                state = hass.states.get(enid)
                if state is None:
                    return
                attrs = dict(state.attributes)
                hass.states.set(enid, msg['msg']['v'], attrs)
            
            # --- Gas Sensor 類型 ---
            elif devtype in GAS_SENSOR_TYPES and msg['msg']['val'] > 0:
                enid = "sensor."+(devtype + "_" + agt + "_" + msg['msg']['me'] + "_" + msg['msg']['idx']).lower()
                state = hass.states.get(enid)
                if state is None:
                    return
                attrs = dict(state.attributes)
                hass.states.set(enid, msg['msg']['val'], attrs)
            
            # --- Spot / Light Switch 類型 ---
            elif devtype in SPOT_TYPES or devtype in LIGHT_SWITCH_TYPES:
                enid = "light."+(devtype + "_" + agt + "_" + msg['msg']['me'] + "_" + msg['msg']['idx']).lower()
                state = hass.states.get(enid)
                if state is None:
                    return
                attrs = dict(state.attributes)
                if msg['msg']['type'] % 2 == 1:
                    hass.states.set(enid, 'on', attrs)
                else:
                    hass.states.set(enid, 'off', attrs)
            
            # --- Climate 類型 ---
            elif devtype in CLIMATE_TYPES:
                enid = "climate."+(devtype + "_" + agt + "_" + msg['msg']['me']).lower().replace(":","_").replace("@","_")
                state = hass.states.get(enid)
                if state is None:
                    return
                attrs = dict(state.attributes)
                nstat = state.state
                
                _idx = msg['msg']['idx']
                if _idx == "O":
                  if msg['msg']['type'] % 2 == 1:
                    nstat = attrs.get('last_mode', HVACMode.OFF) # 使用 .get 防止 key error
                    hass.states.set(enid, nstat, attrs)
                  else:
                    nstat = HVACMode.OFF
                    hass.states.set(enid, nstat, attrs)
                if _idx == "P1":
                  if msg['msg']['type'] % 2 == 1:
                    nstat = HVACMode.HEAT
                    hass.states.set(enid, nstat, attrs)
                  else:
                    nstat = HVACMode.OFF
                    hass.states.set(enid, nstat, attrs)
                if _idx == "P2":
                  if msg['msg']['type'] % 2 == 1:
                    attrs['Heating'] = "true"
                    hass.states.set(enid, nstat, attrs)
                  else:
                    attrs['Heating'] = "false"
                    hass.states.set(enid, nstat, attrs)
                elif _idx == "MODE":
                  if msg['msg']['type'] == 206:
                    if nstat != HVACMode.OFF:
                      # 增加邊界檢查防止 list index out of range
                      val = msg['msg']['val']
                      if 0 <= val < len(LIFESMART_STATE_LIST):
                          nstat = LIFESMART_STATE_LIST[val]
                    attrs['last_mode'] = nstat
                    hass.states.set(enid, nstat, attrs)
                elif _idx == "F":
                  if msg['msg']['type'] == 206:
                    attrs['fan_mode'] = get_fan_mode(msg['msg']['val'])
                    hass.states.set(enid, nstat, attrs)
                elif _idx == "tT" or _idx == "P3":
                  if msg['msg']['type'] == 136:
                    attrs['temperature'] = msg['msg']['v']
                    hass.states.set(enid, nstat, attrs)
                elif _idx == "T" or _idx == "P4":
                  if msg['msg']['type'] == 8 or msg['msg']['type'] == 9:
                    attrs['current_temperature'] = msg['msg']['v']
                    hass.states.set(enid, nstat, attrs)
            
            # --- Lock 類型 ---
            elif devtype in LOCK_TYPES:
                if msg['msg']['idx'] == "BAT":
                    enid = "sensor."+(devtype + "_" + agt + "_" + msg['msg']['me'] + "_" + msg['msg']['idx']).lower()
                    state = hass.states.get(enid)
                    if state is None: return
                    attrs = dict(state.attributes)
                    hass.states.set(enid, msg['msg']['val'], attrs)
                elif msg['msg']['idx'] == "EVTLO":
                    enid = "binary_sensor."+(devtype + "_" + agt + "_" + msg['msg']['me'] + "_" + msg['msg']['idx']).lower()
                    # 這裡原本沒有獲取 attrs，建議還是加上檢查
                    state = hass.states.get(enid)
                    
                    val = msg['msg']['val']
                    ulk_way = val >> 12
                    ulk_user = val & 0xfff
                    ulk_success = True
                    if ulk_user == 0:
                        ulk_success = False
                    attrs = {"unlocking_way": ulk_way,"unlocking_user": ulk_user,"devtype": devtype,"unlocking_success": ulk_success,"last_time": datetime.datetime.fromtimestamp(msg['msg']['ts']/1000).strftime("%Y-%m-%d %H:%M:%S") }
                    
                    if msg['msg']['type'] % 2 == 1:
                        hass.states.set(enid, 'on', attrs)
                    else:
                        hass.states.set(enid, 'off', attrs)
            
            # --- OT Sensor 類型 ---
            if devtype in OT_SENSOR_TYPES and msg['msg']['idx'] in ["Z","V","P3","P4"]:
                enid = "sensor."+(devtype + "_" + agt + "_" + msg['msg']['me'] + "_" + msg['msg']['idx']).lower()
                state = hass.states.get(enid)
                if state is None: return
                attrs = dict(state.attributes)
                hass.states.set(enid, msg['msg']['v'], attrs)
