import asyncio
from playwright.async_api import async_playwright
from aegis.core.state import AegisStateTracker
from aegis.injector import AegisBrowserInjector

async def run_stripe_injection_test():
    db_path = ":memory:"
    seal_id = "test-stripe-seal-001"
    
    # 1. Prepare fake card data in the database
    tracker = AegisStateTracker(db_path=db_path)
    print("[Aegis DB] Inserting test virtual card into Vault...")
    tracker.record_seal(
        seal_id=seal_id,
        amount=50.0,
        vendor="Stripe Demo",
        status="Issued",
        card_number="4242424242424242",
        cvv="123",
        expiration_date="12/30"
    )
    
    # 2. Launch browser with CDP port open
    print("[Playwright] Launching browser with --remote-debugging-port=9222...")
    async with async_playwright() as p:
        # We launch a persistent context or normal browser with the debug port
        browser = await p.chromium.launch(
            headless=False,
            args=["--remote-debugging-port=9222"]
        )
        
        page = await browser.new_page()
        import os
        # 3. Navigate to Wikimedia donate page
        demo_url = "https://payments.wikimedia.org/index.php?title=Special:GravyGateway&appeal=JimmyQuote&country=US&currency=USD&payment_method=cc&recurring=0&gateway=gravy&uselang=en&amount=3.1&wmf_medium=spontaneous&wmf_campaign=spontaneous&wmf_source=fr-redir.default%7Edefault%7Edefault%7Edefault%7Econtrol.cc&wmf_key=vw_1512%7Evh_945%7EotherAmt_0%7EvalidateError_1%7Eptf_1%7Etime_7&referrer=www.google.com%2F"
        print(f"[Playwright] Navigating to {demo_url} ...")
        try:
            await page.goto(demo_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"Navigation error: {e}")
        
        # 4. Wait for Stripe's cross-origin iframes to load
        print("[Playwright] Waiting 10 seconds for Wikimedia page to load fully...")
        await asyncio.sleep(10)
        
        # 5. Instantiate the AegisBrowserInjector and connect via CDP
        print("[Aegis Injector] Connecting via CDP to inject payment info...")
        injector = AegisBrowserInjector(tracker)
        
        success = await injector.inject_payment_info(seal_id, cdp_url="http://localhost:9222")
        
        if success:
            print("[Aegis Injector] ✅ SUCCESS! Card details injected into Wiki frame.")
        else:
            print("[Aegis Injector] ❌ FAILED! Could not find input fields.")
            
        # Save screenshot for proof in correct Artifact Path
        screenshot_path = "/Users/tpemist/.gemini/antigravity/brain/511eb8dc-e470-4195-995a-2d214717f5e9/wiki_proof.png"
        await page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")
            
        print("[Playwright] Leaving browser open for 5 seconds for visual inspection...")
        await asyncio.sleep(5)
        
        # 6. Cleanup
        await browser.close()
        tracker.close()

if __name__ == "__main__":
    asyncio.run(run_stripe_injection_test())
