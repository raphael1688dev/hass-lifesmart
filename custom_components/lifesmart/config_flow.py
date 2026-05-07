"""Config flow for LifeSmart."""
import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, CONF_LIFESMART_APPKEY, CONF_LIFESMART_APPTOKEN, CONF_LIFESMART_USERTOKEN, CONF_LIFESMART_USERID, CONF_EXCLUDE_ITEMS

class LifeSmartConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LifeSmart."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # 使用者填完資料後，建立 Config Entry
            return self.async_create_entry(title=f"LifeSmart ({user_input[CONF_LIFESMART_USERID]})", data=user_input)

        # 定義 UI 輸入表單
        data_schema = vol.Schema({
            vol.Required(CONF_LIFESMART_APPKEY): str,
            vol.Required(CONF_LIFESMART_APPTOKEN): str,
            vol.Required(CONF_LIFESMART_USERTOKEN): str,
            vol.Required(CONF_LIFESMART_USERID): str,
            vol.Optional(CONF_EXCLUDE_ITEMS, default=""): str,
        })

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
