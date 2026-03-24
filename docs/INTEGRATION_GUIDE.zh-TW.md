[English](./INTEGRATION_GUIDE.md) | [中文](./INTEGRATION_GUIDE.zh-TW.md)

# Aegis 整合指南

> **給 Agent 開發者**，想要將 Aegis 作為財務中間層嵌入 Agentic 工作流程的實戰參考。  
> 本指南涵蓋三種整合模式：**OpenClaw/NemoClaw System Prompt**、**直接 Python SDK / gemini-cli**，以及**瀏覽器 Agent 中間層（Playwright / browser-use / Skyvern）**。

---

## 1. OpenClaw / NemoClaw — System Prompt 設定

最重要的防護層在於 **System Prompt 層級**：明確指示 Agent 在執行任何支付動作之前，*必須*先呼叫 Aegis，而不是直接嘗試填入真實憑證。

### 推薦的 System Prompt 片段

將以下區塊加入你的 OpenClaw 或 NemoClaw 身份設定檔（如 `IDENTITY.md` 或 Agent 設定中的 system prompt 欄位）：

```markdown
## 財務安全協議（必須遵守）

你正在「Aegis 支付護欄協議」下運行。以下規則**不可協商**：

1. **在嘗試任何購買、訂閱、捐款、API 額度加值或任何金融交易之前，
   你必須呼叫 `request_virtual_card` MCP 工具**以取得授權。

2. **絕對不可使用**儲存在你的上下文、記憶或檔案中的信用卡號碼、
   PAN 卡號或任何真實支付憑證。這些資訊從不提供給你。

3. **如果 `request_virtual_card` 回傳拒絕，立即停止支付流程。**
   不可以用不同的理由重試。請向使用者回報拒絕原因。

4. **如果你發現自己陷入迴圈**（對同一筆失敗交易重試超過一次），
   你必須停下來並請求人類介入，而非繼續嘗試。

5. Aegis 回傳的卡號將是遮罩格式（如 `****-****-****-4242`）。
   **不可嘗試查找或還原完整卡號。**
```

### OpenClaw：註冊 Aegis 為 MCP 工具

```bash
openclaw mcp add aegis -- uv run python -m aegis.mcp_server
```

或加入 `~/.openclaw/mcp_servers.json`：

```json
{
  "aegis": {
    "command": "uv",
    "args": ["run", "python", "-m", "aegis.mcp_server"],
    "cwd": "/path/to/Project-Aegis",
    "env": {
      "AEGIS_ALLOWED_CATEGORIES": "[\"aws\", \"cloudflare\", \"openai\", \"github\"]",
      "AEGIS_MAX_PER_TX": "100.0",
      "AEGIS_MAX_DAILY": "500.0",
      "AEGIS_BLOCK_LOOPS": "true",
      "AEGIS_GUARDRAIL_ENGINE": "llm",
      "AEGIS_LLM_API_KEY": "sk-your-openai-api-key"
    }
  }
}
```

### NemoClaw（NVIDIA 安全沙箱）：特別注意事項

NemoClaw 的 `OpenShell` 運行時限制寫入存取範圍，僅允許 `/sandbox/` 與 `/tmp/`。

```bash
# 步驟一：在沙箱內複製 Aegis
nemoclaw my-assistant connect
cd /sandbox
git clone https://github.com/TPEmist/Project-Aegis.git
cd Project-Aegis && uv sync --all-extras

# 步驟二：連接沙箱後，在內部註冊 MCP server
openclaw mcp add aegis -- uv run python -m aegis.mcp_server

# 步驟三：設定環境變數（aegis_state.db 將寫入 /sandbox/Project-Aegis/）
export AEGIS_ALLOWED_CATEGORIES='["aws", "openai"]'
export AEGIS_MAX_PER_TX=50.0
export AEGIS_MAX_DAILY=200.0
export AEGIS_GUARDRAIL_ENGINE=llm
export AEGIS_LLM_API_KEY=sk-your-openai-api-key
```

> **NemoClaw 提示：** 上方的 System Prompt 片段在 NemoClaw 情境中尤為關鍵，因為沙箱內的 Agent 擁有更廣泛的系統層級權限。Aegis 成為沙箱內的最後一道財務防線。

---

## 2. gemini-cli / Python 腳本整合

對於使用 `gemini-cli` 或直接 Python Agent 迴圈的自動化腳本，可以將 `AegisClient` 直接作為支付中間層嵌入。

### 模式一：AegisClient 作為腳本中間層

```python
import asyncio
from aegis.client import AegisClient
from aegis.providers.stripe_mock import MockStripeProvider
from aegis.core.models import GuardrailPolicy, PaymentIntent

async def run_automated_workflow():
    # 1. 在腳本開頭初始化 Aegis
    policy = GuardrailPolicy(
        allowed_categories=["SaaS", "API", "Cloud"],
        max_amount_per_tx=50.0,
        max_daily_budget=200.0,
        block_hallucination_loops=True
    )
    client = AegisClient(
        provider=MockStripeProvider(),  # 正式環境換成 StripeIssuingProvider
        policy=policy,
        db_path="aegis_state.db"
    )

    # 2. 需要付款時，透過 Aegis 進行申請
    intent = PaymentIntent(
        agent_id="gemini-script-001",
        requested_amount=15.0,
        target_vendor="openai",
        reasoning="補充 API 額度以繼續資料管線的執行。"
    )

    seal = await client.process_payment(intent)

    if seal.status == "Rejected":
        print(f"🛑 支付被阻擋：{seal.rejection_reason}")
        return  # 停止腳本 — 不要嘗試繞道

    print(f"✅ 已核准。Seal: {seal.seal_id} | 卡號：****-****-****-{seal.card_number[-4:]}")

    # 3. 使用 seal_id 執行交易（用後即焚機制啟動）
    result = await client.execute_payment(seal.seal_id, 15.0)
    print(f"執行結果：{result['status']}")

asyncio.run(run_automated_workflow())
```

### 模式二：LangChain Tool Call（適用於 gemini-cli 工具整合）

如果你的 `gemini-cli` 提示使用工具呼叫，可以將 Aegis 封裝為 LangChain `BaseTool`：

```python
from aegis.tools.langchain import AegisPaymentTool
from aegis.client import AegisClient
from aegis.providers.stripe_mock import MockStripeProvider
from aegis.core.models import GuardrailPolicy

policy = GuardrailPolicy(
    allowed_categories=["SaaS", "API"],
    max_amount_per_tx=50.0,
    max_daily_budget=200.0,
    block_hallucination_loops=True
)
client = AegisClient(MockStripeProvider(), policy)

# 在 Agent 工具清單中註冊
aegis_tool = AegisPaymentTool(client=client, agent_id="gemini-agent")

# 工具接受：requested_amount、target_vendor、reasoning
result = await aegis_tool._arun(
    requested_amount=15.0,
    target_vendor="openai",
    reasoning="需要 API 額度以繼續處理使用者請求。"
)
print(result)
# → "Payment approved. Card Issued: ****-****-****-4242, Expiry: 03/27, ..."
```

---

## 3. 瀏覽器 Agent 中間層（Playwright / browser-use / Skyvern）

操作真實網站的瀏覽器 Agent 需要在填入支付表單之前，先攔截結帳流程並向 Aegis 申請虛擬卡。

### 架構說明

```
┌──────────────────────────────────────────────────────┐
│                  Agent 協調器                         │
│  (OpenClaw / NemoClaw / 自訂 asyncio 迴圈)           │
└───────────────────────┬──────────────────────────────┘
                        │
          導航、找到結帳頁面
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│              瀏覽器 Agent 層                           │
│  (Playwright, browser-use, Skyvern)                  │
│                                                       │
│  1. 偵測到支付表單 / 付費牆                            │
│  2. 擷取：金額、供應商、上下文                          │
│  3. ─── 暫停導航 ────────────────────────────────────►│
└───────────────────────┬──────────────────────────────┘
                        │  request_virtual_card(amount, vendor, reasoning)
                        ▼
┌──────────────────────────────────────────────────────┐
│                 Aegis（本函式庫）                      │
│                                                       │
│  • GuardrailEngine：關鍵字 + 可選 LLM 語意審核         │
│  • 預算執行：每日上限 + 單筆上限                        │
│  • 核發 VirtualSeal：一次性虛擬卡，用後即焚             │
│  • 回傳：遮罩後的卡號 + seal_id                        │
└───────────────────────┬──────────────────────────────┘
                        │  Seal 核准
                        ▼
┌──────────────────────────────────────────────────────┐
│              瀏覽器 Agent 層（繼續）                   │
│                                                       │
│  4. 可信任的本地程式從 DB 取得真實卡片資訊              │
│     (透過 state_tracker.get_seal_details — 非 LLM)    │
│  5. page.fill("#card_number", real_pan)               │
│  6. page.fill("#cvv", real_cvv)                       │
│  7. page.click("#submit")                             │
│  8. execute_payment(seal_id) → 虛擬卡銷毀              │
└──────────────────────────────────────────────────────┘
```

### 真實實作範例（Playwright）

以下是基於 [`examples/agent_vault_flow.py`](../examples/agent_vault_flow.py) 的可運行實作：

```python
import asyncio
from playwright.async_api import async_playwright
from aegis.client import AegisClient
from aegis.providers.stripe_mock import MockStripeProvider
from aegis.core.models import PaymentIntent, GuardrailPolicy

async def browser_agent_with_aegis():
    # 1. 初始化 Aegis
    policy = GuardrailPolicy(
        allowed_categories=["Donation", "SaaS", "Wikipedia"],
        max_amount_per_tx=30.0,
        max_daily_budget=50.0
    )
    client = AegisClient(MockStripeProvider(), policy, db_path="aegis_state.db")

    # 2. 瀏覽器 Agent 偵測到結帳頁面，申請授權
    intent = PaymentIntent(
        agent_id="playwright-agent-001",
        requested_amount=25.0,
        target_vendor="Wikipedia",
        reasoning="我需要透過 $25 捐款支持開放知識。"
    )
    seal = await client.process_payment(intent)

    if seal.status.lower() == "rejected":
        print(f"🛑 Aegis 阻擋了支付：{seal.rejection_reason}")
        return  # 瀏覽器 Agent 停止 — 不嘗試填入表單

    print(f"✅ Aegis 已核准。Seal: {seal.seal_id}")
    # Agent 的上下文只看到遮罩後的卡號 — 絕不是真實 PAN
    print(f"   Agent 日誌中的卡號：****-****-****-{seal.card_number[-4:]}")

    # 3. 可信任的本地程式將真實憑證填入瀏覽器
    #    （此程式碼跑在本地執行環境，不在 LLM 上下文中）
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("https://donate.wikimedia.org/")

        # 關鍵：真實卡片資訊從 DB 取得，絕不從 LLM 輸出讀取
        details = client.state_tracker.get_seal_details(seal.seal_id)

        await page.fill("#card_number", details["card_number"])
        await page.fill("#cvv", details["cvv"])
        await page.fill("#expiry", details["expiration_date"])
        await page.click("#submit-donation")

    # 4. 標記 Seal 為已使用（用後即焚機制）
    await client.execute_payment(seal.seal_id, 25.0)
    print("🔥 虛擬卡已銷毀。交易完成。")

asyncio.run(browser_agent_with_aegis())
```

### 適用於 browser-use / Skyvern 的調整

如果你使用 `browser-use` 或 Skyvern（以更高層次的視覺推理運作），模式完全相同 — 在送出表單前攔截：

```python
# browser-use 整合的偽代碼
class AegisCheckoutInterceptor:
    def __init__(self, aegis_client: AegisClient):
        self.client = aegis_client

    async def on_checkout_detected(self, amount: float, vendor: str, context: str):
        """當 browser-use 偵測到支付表單時呼叫。"""
        intent = PaymentIntent(
            agent_id="browser-use-agent",
            requested_amount=amount,
            target_vendor=vendor,
            reasoning=context  # browser-use 對於為何付款的視覺描述
        )
        seal = await self.client.process_payment(intent)

        if seal.status == "Rejected":
            raise PaymentBlockedError(f"Aegis 拒絕了：{seal.rejection_reason}")

        return seal  # 將 seal 傳回給 browser-use 完成結帳

    async def on_checkout_complete(self, seal_id: str, amount: float):
        """browser-use 成功送出表單後呼叫。"""
        await self.client.execute_payment(seal_id, amount)
```

---

## 延伸閱讀

- [README.zh-TW.md](../README.zh-TW.md) — 主要概述與快速上手（繁體中文版）
- [examples/agent_vault_flow.py](../examples/agent_vault_flow.py) — 完整 Playwright 瀏覽器注入範例
- [examples/e2e_demo.py](../examples/e2e_demo.py) — 純 SDK 端對端展示（無瀏覽器）
- [CONTRIBUTING.md](../CONTRIBUTING.md) — 如何新增支付供應商或護欄引擎
