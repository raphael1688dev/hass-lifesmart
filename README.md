# LifeSmart Integration for Home Assistant

A modern, high-performance, and fully asynchronous custom component to integrate LifeSmart smart home devices into Home Assistant.

**Important Note**: The API endpoints are configured for the **US Server** (`api.us.ilifesmart.com`). If your account is in a different region, please update the URLs in `__init__.py`.

## Major Updates (V2.1.0)
* **Modern UI Setup (Config Flow)**: Configure the integration directly through the Home Assistant UI.
* **Device Registry Support**: Entities are grouped into **Devices** with serial numbers and model info.
* **Real-time WebSocket Sync**: Instant state updates via persistent connection.
* **Smart Ghost Entity Filtering**: Automatically removes non-existent ports (e.g., P2/P3 on a 1-gang switch).

---

## How to use Config Flow
Instead of editing `configuration.yaml`, follow these steps to set up the integration:

1. **Install**: Copy the `lifesmart` folder to `custom_components/`.
2. **Restart**: Restart Home Assistant to detect the new component.
3. **Add Integration**: 
   * Go to **Settings** > **Devices & Services**.
   * Click **+ Add Integration** at the bottom right.
   * Search for **LifeSmart**.
4. **Setup**: A dialog will appear asking for your credentials.
   * **App Key / App Token**: Your developer credentials.
   * **User ID / User Token**: Your specific account credentials (see below on how to get these).
   * **Exclude**: (Optional) List of `me` IDs to ignore, separated by commas.
5. **Submit**: Once verified, your devices will appear in the **Devices** tab automatically.

---

## How to get LifeSmart API Credentials
To use this integration, you need four pieces of information: `appkey`, `apptoken`, `userid`, and `usertoken`.

### Prerequisites
* **App Key / App Token**: Register an account on the [LifeSmart Developer Portal](https://open.ilifesmart.com/) to obtain these.
* **Account Email/Password**: Your standard LifeSmart App login.

### Step 1: Obtain Temporary Token & UserID
Use `curl` (Terminal/CMD) to call the login endpoint. Replace placeholders with your actual data.

**Endpoint**: `https://api.ilifesmart.com/app/auth.login`

```bash
curl -X POST "[https://api.ilifesmart.com/app/auth.login](https://api.ilifesmart.com/app/auth.login)" \
-H "Content-Type: application/json" \
-d '{
  "uid": "YOUR_EMAIL",
  "pwd": "YOUR_PASSWORD",
  "appkey": "YOUR_APP_KEY"
}'
```

From the response, save: "token", "userid", and "rgn".

###  Step 2: Obtain Permanent User Token
Now, exchange the temporary token for a permanent usertoken.
Endpoint: https://api.ilifesmart.com/app/auth.do_auth

```bash
curl -X POST "[https://api.ilifesmart.com/app/auth.do_auth](https://api.ilifesmart.com/app/auth.do_auth)" \
-H "Content-Type: application/json" \
-d '{
  "userid": "USER_ID_FROM_STEP_1",
  "token": "TOKEN_FROM_STEP_1",
  "appkey": "YOUR_APP_KEY",
  "rgn": "RGN_FROM_STEP_1"
}'
```

Final Result: The response will contain the "usertoken". Use this along with your userid and developer keys in the Home Assistant setup dialog.
