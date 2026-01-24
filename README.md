使用说明
==== 
lifesmart 设备接入 HomeAssistant插件

更新说明
-------  
[2022年7月5日累计更新]
* Home Assitant 新版本适配：
  * XXXDevice 改为 XXXEntity 
  * FanSpeed 枚举修改
  * device_state_attributes 改为 extra_state_attributes
  * Climate 类中，统一修改为使用内置属性
   

[2020年12月26日更新]

支持流光开关灯光控制

更新manifest内容以适配新版本home assistant

[2020年8月21日更新]

新增设备支持：

**超能面板**：SL_NATURE

PS：其实就是个开关...

[2020年2月4日更新]

优化实体ID生成逻辑：解决未加入或存在多个智慧中心时，me号可能存在重复的问题。

[2019年12月6日更新]

新增支持设备：

**中央空调面板**：V_AIR_P

**智能门锁反馈信息**：SL_LK_LS、SL_LK_GTM、SL_LK_AG、SL_LK_SG、SL_LK_YL

目前支持的设备：
-------  
1、开关；

2、灯光：目前仅支持超级碗夜灯；

3、万能遥控；

4、窗帘电机（仅支持杜亚电机）

5、动态感应器、门磁、环境感应器、甲醛/燃气感应器

6、空调控制面板

7、智能门锁信息反馈

使用方法：
-------  
1、将lifesmart目录复制到config/custom_components/下

2、在configuration.yaml文件中增加配置：

```
lifesmart:
  appkey: "your_appkey" 
  apptoken: "your_apptoken"
  usertoken: "your_usertoken" 
  userid: "your_userid"
  exclude:
    - "0011" #需屏蔽设备的me值,这个暂时为必填项，可以填任意内容
```

Here is the complete authentication workflow for LifeSmart, formatted in English Markdown. I have included specific commands for both **Linux/macOS** and **Windows (CMD)** to avoid the syntax errors you encountered earlier.

---

# LifeSmart API Authentication Workflow

This guide details the two-step process to obtain a valid `usertoken` for the LifeSmart API.

## Prerequisites

Before you begin, ensure you have the following information:

* **Your Account Email**
* **Your Account Password**
* **App Key** (Obtained from the LifeSmart developer website)

---

## Step 1: Initial Login

**Endpoint:** `https://api.ilifesmart.com/app/auth.login`

**Goal:** Retrieve the temporary `token`, `userid`, and region code (`rgn`).

### Option A: macOS / Linux / PowerShell (Single Line)

```bash
curl -X POST "https://api.ilifesmart.com/app/auth.login" -H "Content-Type: application/json" -d '{"uid": "YOUR_EMAIL", "pwd": "YOUR_PASSWORD", "appkey": "YOUR_APP_KEY"}'

```

### Option B: Windows Command Prompt (CMD)

*Note: Windows CMD requires escaping double quotes (`\"`) inside the JSON.*

```cmd
curl -X POST "https://api.ilifesmart.com/app/auth.login" -H "Content-Type: application/json" -d "{\"uid\": \"YOUR_EMAIL\", \"pwd\": \"YOUR_PASSWORD\", \"appkey\": \"YOUR_APP_KEY\"}"

```

### Expected Response

Save the values from this response for Step 2.

```json
{
  "code": 200,
  "msg": "success",
  "token": "EXAMPLE_TOKEN_123",
  "userid": "EXAMPLE_USER_ID_456",
  "rgn": "sg"
}

```

---

## Step 2: Authorize & Get User Token

**Endpoint:** `https://api.ilifesmart.com/app/auth.do_auth`

**Goal:** Exchange the temporary token for the permanent `usertoken`.

**Required Data from Step 1:**

1. `userid`
2. `token`
3. `rgn`

### Option A: macOS / Linux / PowerShell (Single Line)

```bash
curl -X POST "https://api.ilifesmart.com/app/auth.do_auth" -H "Content-Type: application/json" -d '{"userid": "USER_ID_FROM_STEP_1", "token": "TOKEN_FROM_STEP_1", "appkey": "YOUR_APP_KEY", "rgn": "RGN_FROM_STEP_1"}'

```

### Option B: Windows Command Prompt (CMD)

```cmd
curl -X POST "https://api.ilifesmart.com/app/auth.do_auth" -H "Content-Type: application/json" -d "{\"userid\": \"USER_ID_FROM_STEP_1\", \"token\": \"TOKEN_FROM_STEP_1\", \"appkey\": \"YOUR_APP_KEY\", \"rgn\": \"RGN_FROM_STEP_1\"}"

```

### Expected Response

This contains your final User Token.

```json
{
  "code": 200,
  "msg": "success",
  "usertoken": "YOUR_FINAL_USER_TOKEN"
}

```

---

## Troubleshooting

* **Syntax Errors:** If the command fails to send, ensure you are using the **Single Line** versions provided above.
* **Windows Users:** If using the standard Command Prompt (cmd.exe), you **must** use the "Option B" syntax where inner quotes are escaped like `\"`.
* **App Key:** Ensure the `appkey` is exactly the same in both Step 1 and Step 2.

Would you like me to help you format a request to control a device once you have the `usertoken`?
    
