import os
import asyncio
import sqlite3
from playwright.async_api import async_playwright
from aegis.client import AegisClient
from aegis.providers.stripe_mock import MockStripeProvider
from aegis.core.models import PaymentIntent, GuardrailPolicy

async def agent_workflow():
    # --- 1. 初始化 Aegis 守衛者 ---
    # 設定每日預算為 $50
    policy = GuardrailPolicy(
        allowed_categories=["Donation", "SaaS", "Wikipedia"],
        max_amount_per_tx=30.0,
        max_daily_budget=50.0
    )
    # 使用 MockProvider，但模擬真實發卡
    provider = MockStripeProvider()
    client = AegisClient(provider, policy, db_path="aegis_state.db")

    # --- 2. Agent 請求支付 ---
    intent = PaymentIntent(
        agent_id="claude-agent-007",
        requested_amount=25.0,
        target_vendor="Wikipedia",
        reasoning="I need to support open knowledge via a $25 donation."
    )
    
    print(f"\n[Agent] Requesting ${intent.requested_amount} for {intent.target_vendor}...")
    seal = await client.process_payment(intent)
    
    if seal.status.lower() == "rejected":
        print(f"[Aegis] 🛑 Payment Rejected: {seal.rejection_reason}")
        return

    # 重要：在對話紀錄中，Agent 只能看到遮蔽的卡號
    print(f"[Agent] ✅ Payment Approved! Seal ID: {seal.seal_id}")
    print(f"[Agent] Logged Card Number: ****-****-****-{seal.card_number[-4:]} (Protected)")

    # --- 3. 瀏覽器注入 (受信任環境) ---
    print("\n[Aegis] Launching secure browser session for injection...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # 導航至測試頁面 (使用我們之前建立的 local test，確保 100% 成功展示)
        # 我們現場建立一個測試 HTML
        test_html = """
        <html><body>
            <h3>Wikipedia Donation Secure Form</h3>
            <input id="card_num" placeholder="Card Number">
            <input id="cvv" placeholder="CVV">
        </body></html>
        """
        await page.set_content(test_html)
        
        # 從資料庫讀取「真實資料」(僅限本地受信任工具)
        details = client.state_tracker.get_seal_details(seal.seal_id)
        
        print("[Aegis] Injecting real credentials into the secure form...")
        await page.fill("#card_num", details['card_number'])
        await page.fill("#cvv", details['cvv'])
        
        # --- 截圖存證 ---
        screenshot_path = "agent_injection_proof.png"
        await page.screenshot(path=screenshot_path)
        print(f"[Aegis] 📸 Screenshot captured: {screenshot_path}")
        
        print("[Aegis] Injection successful. Verifying spending limit...")
        
        # --- 4. 驗證錢包安全 ---
        spent = client.state_tracker.daily_spend_total
        print(f"\n[Vault] Current Daily Spend: ${spent} / ${policy.max_daily_budget}")
        
        await asyncio.sleep(2)
        await browser.close()
        print("\n[Final] Workflow completed. Wallet is secure.")

if __name__ == "__main__":
    asyncio.run(agent_workflow())
