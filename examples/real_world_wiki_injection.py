import os
import asyncio
from playwright.async_api import async_playwright
from aegis.client import AegisClient
from aegis.providers.byoc_local import LocalVaultProvider
from aegis.core.models import PaymentIntent, GuardrailPolicy
from aegis.injector import AegisBrowserInjector

async def real_world_wiki_test():
    # 1. 初始化 Aegis 安全金庫 (使用 Stripe 測試卡號)
    os.environ['AEGIS_BYOC_NUMBER'] = '4242424242424242'
    os.environ['AEGIS_BYOC_EXP_MONTH'] = '12'
    os.environ['AEGIS_BYOC_EXP_YEAR'] = '2030'
    os.environ['AEGIS_BYOC_CVV'] = '123'

    policy = GuardrailPolicy(
        allowed_categories=["Donation", "SaaS", "Wikipedia"],
        max_amount_per_tx=100.0,
        max_daily_budget=200.0
    )
    provider = LocalVaultProvider()
    client = AegisClient(provider, policy, db_path="aegis_state.db")

    # 2. Agent 發起支付請求
    intent = PaymentIntent(
        agent_id="real-world-agent",
        requested_amount=15.0,
        target_vendor="Wikipedia",
        reasoning="Testing Aegis injection on a real-world production site (Wikipedia)."
    )
    seal = await client.process_payment(intent)
    
    print(f"[Aegis] Seal issued for {intent.target_vendor}. Starting browser...")

    # 3. 啟動瀏覽器並導航至 Wikipedia 捐款頁
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False) # Headed mode for visibility
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        # 使用更穩定的 LandingPage URL，直接帶入金額與支付方式參數
        url = "https://donate.wikimedia.org/w/index.php?title=Special:LandingPage&country=US&uselang=en&payment_method=cc&amount=25"
        print(f"[Aegis] Navigating to: {url}")
        
        # 監聽新 Frame 建立
        page.on("frameattached", lambda frame: print(f"[Debug] Frame Attached: {frame.url[:60]}"))
        page.on("framenavigated", lambda frame: print(f"[Debug] Frame Navigated: {frame.url[:60]}"))

        await page.goto(url, wait_until="load")

        # --- 關鍵步驟：直接等待支付表單加載 ---
        print("[Aegis] Waiting for payment form (including potentially dynamic iframes)...")
        # Wikipedia 可能會偵測自動化，我們多等一下
        await asyncio.sleep(20)
        
        print(f"--- Debug: Final Frames List ({len(page.frames)}) ---")
        for i, f in enumerate(page.frames):
            print(f"Frame {i}: {f.url}")
        print("------------------------------------------")
        
        # 4. 執行 Aegis 注入器 (穿透 Iframe)
        injector = AegisBrowserInjector(client.state_tracker, page)
        print(f"[Aegis] Injecting credentials for Seal: {seal.seal_id}...")
        await injector.inject_payment_info(seal.seal_id)

        # 5. 截圖存證
        screenshot_path = "wikipedia_real_proof.png"
        await page.screenshot(path=screenshot_path)
        print(f"[Aegis] 📸 Screenshot saved: {screenshot_path}")

        print("[Aegis] Showcase completed. Closing browser in 5 seconds...")
        await asyncio.sleep(5)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(real_world_wiki_test())
