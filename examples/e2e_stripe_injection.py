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
        
        # 3. Navigate to a real Stripe Elements demo
        demo_url = "https://stripe.dev/elements-examples/"
        print(f"[Playwright] Navigating to {demo_url} ...")
        await page.goto(demo_url)
        
        # 4. Wait for Stripe's cross-origin iframes to load
        print("[Playwright] Waiting 8 seconds for Stripe iframes to load...")
        await asyncio.sleep(8)
        
        # 5. Instantiate the AegisBrowserInjector and connect via CDP
        print("[Aegis Injector] Connecting via CDP to inject payment info...")
        injector = AegisBrowserInjector(tracker)
        
        # This will attach to the active browser on port 9222, traverse the DOM (including iframes),
        # and inject the card number, expiry, and CVV.
        success = await injector.inject_payment_info(seal_id, cdp_url="http://localhost:9222")
        
        if success:
            print("[Aegis Injector] ✅ SUCCESS! Card details injected into Stripe iframe.")
        else:
            print("[Aegis Injector] ❌ FAILED! Could not find Stripe input fields.")
            
        print("[Playwright] Leaving browser open for 10 seconds for visual inspection...")
        await asyncio.sleep(10)
        
        # 6. Cleanup
        await browser.close()
        tracker.close()

if __name__ == "__main__":
    asyncio.run(run_stripe_injection_test())
