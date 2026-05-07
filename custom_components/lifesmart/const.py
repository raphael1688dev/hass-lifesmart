"""Constants for the LifeSmart integration."""
DOMAIN = 'lifesmart'

CONF_LIFESMART_APPKEY = "appkey"
CONF_LIFESMART_APPTOKEN = "apptoken"
CONF_LIFESMART_USERTOKEN = "usertoken"
CONF_LIFESMART_USERID = "userid"
CONF_EXCLUDE_ITEMS = "exclude"

PLATFORMS = ["switch", "light", "climate", "sensor", "binary_sensor", "cover"]

# 設備類型列表
SWTICH_TYPES = ["SL_SF_RC", "SL_SW_RC", "SL_SW_IF3", "SL_SF_IF3", "SL_SW_CP3", "SL_SW_RC3", "SL_SW_IF2", "SL_SF_IF2", "SL_SW_CP2", "SL_SW_FE2", "SL_SW_RC2", "SL_SW_ND2", "SL_MC_ND2", "SL_SW_IF1", "SL_SF_IF1", "SL_SW_CP1", "SL_SW_FE1", "SL_OL_W", "SL_SW_RC1", "SL_SW_ND1", "SL_MC_ND1", "SL_SW_ND3", "SL_MC_ND3", "SL_SW_ND2", "SL_MC_ND2", "SL_SW_ND1", "SL_MC_ND1", "SL_S", "SL_SPWM", "SL_P_SW", "SL_SW_DM1", "SL_SW_MJ2", "SL_SW_MJ1", "SL_OL", "SL_OL_3C", "SL_OL_DE", "SL_OL_UK", "SL_OL_UL", "OD_WE_OT1", "SL_NATURE"]
LIGHT_SWITCH_TYPES = ["SL_OL_W"]
SPOT_TYPES = ["MSL_IRCTL", "OD_WE_IRCTL", "SL_SPOT"]
BINARY_SENSOR_TYPES = ["SL_SC_G", "SL_SC_BG", "SL_SC_MHW ", "SL_SC_BM", "SL_SC_CM", "SL_P_A", "SL_DF_GG", "SL_DF_MM"]
COVER_TYPES = ["SL_DOOYA"]
GAS_SENSOR_TYPES = ["SL_SC_WA ", "SL_SC_CH", "SL_SC_CP", "ELIQ_EM"]
EV_SENSOR_TYPES = ["SL_SC_THL", "SL_SC_BE", "SL_SC_CQ"]
OT_SENSOR_TYPES = ["SL_SC_MHW", "SL_SC_BM", "SL_SC_G", "SL_SC_BG"]
LOCK_TYPES = ["SL_LK_LS", "SL_LK_GTM", "SL_LK_AG", "SL_LK_SG", "SL_LK_YL"]
CLIMATE_TYPES = ["V_AIR_P", "SL_CP_DN"]
