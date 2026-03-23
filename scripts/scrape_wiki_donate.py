import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Use a real-looking user agent
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        url = "https://donate.wikimedia.org/wiki/Special:FundraiserRedirector?campaign=C13_en.wikipedia.org&tier=basic&uselang=en&payment_method=cc"
        print(f"Navigating to {url}...")
        await page.goto(url, wait_until="networkidle")
        
        await asyncio.sleep(5)
        
        # Select an amount radio button (e.g., $25)
        amount_radio = await page.query_selector("input[name='amount'][id^='input_amount_']")
        if amount_radio:
            print(f"Selecting amount radio: {await amount_radio.get_attribute('id')}")
            await amount_radio.click()
            await asyncio.sleep(1)

        # Click "Donate by credit/debit card"
        cc_button = await page.query_selector("button:has-text('Donate by credit/debit card'), button:has-text('credit/debit card')")
        if cc_button:
            print(f"Found Credit Card button. Clicking...")
            await cc_button.click()
            print("Waiting 20s for navigation or dynamic content...")
            await asyncio.sleep(20)
        else:
            print("Credit Card button NOT found.")

        print(f"\nFinal URL: {page.url}")
        
        # Check for any new frames
        frames = page.frames
        print(f"Total frames: {len(frames)}")
        for i, frame in enumerate(frames):
            print(f"\n--- FRAME {i} ---")
            print(f"URL: {frame.url}")
            try:
                # Find all inputs
                inputs = await frame.query_selector_all("input, select, textarea")
                print(f"INPUT COUNT: {len(inputs)}")
                for j, inp in enumerate(inputs):
                    is_visible = await inp.is_visible()
                    tag_name = await inp.evaluate("el => el.tagName")
                    attrs = await inp.evaluate("""(el) => {
                        return {
                            id: el.id,
                            name: el.name,
                            type: el.type,
                            placeholder: el.placeholder,
                            autocomplete: el.autocomplete,
                            ariaLabel: el.getAttribute('aria-label'),
                            className: el.className
                        };
                    }""")
                    if is_visible:
                        print(f"  {tag_name}_{j}: id='{attrs['id']}', name='{attrs['name']}', placeholder='{attrs['placeholder']}', aria-label='{attrs['ariaLabel']}', class='{attrs['className']}'")
            except Exception as e:
                print(f"  Error: {e}")

        # If no fields found, print the body text to see what happened
        if len(page.frames) == 1:
            body_text = await page.inner_text("body")
            print("\n--- BODY TEXT PREVIEW (first 500 chars) ---")
            print(body_text[:500])

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
