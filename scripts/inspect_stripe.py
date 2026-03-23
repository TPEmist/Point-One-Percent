import asyncio
from playwright.async_api import async_playwright

async def inspect():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://stripe.dev/elements-examples/")
        await asyncio.sleep(5)
        for i, frame in enumerate(page.frames):
            print(f"Frame {i}: url={frame.url}")
            inputs = await frame.query_selector_all("input")
            for inp in inputs:
                name = await inp.get_attribute("name")
                id_attr = await inp.get_attribute("id")
                auto = await inp.get_attribute("autocomplete")
                print(f"  Input: name={name}, id={id_attr}, autocomplete={auto}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect())
