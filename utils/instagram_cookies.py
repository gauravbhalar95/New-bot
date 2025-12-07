import os
import json
import asyncio
from playwright.async_api import async_playwright

from config import INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD

RAW_JSON_COOKIES = "cookies/instagram_raw.json"
NETSCAPE_COOKIES = "cookies/instagram_cookies.txt"

COOKIES_FILE = NETSCAPE_COOKIES

# Convert JSON cookies → Netscape format
def convert_to_netscape(json_file, output_file):
    try:
        with open(json_file, "r") as f:
            cookies = json.load(f)

        with open(output_file, "w") as f:
            f.write("# Netscape HTTP Cookie File\n")
            for c in cookies:
                domain = c.get("domain", "")
                flag = "TRUE" if domain.startswith(".") else "FALSE"
                path = c.get("path", "/")
                secure = "TRUE" if c.get("secure") else "FALSE"
                expiry = c.get("expires", 0)
                name = c.get("name", "")
                value = c.get("value", "")

                f.write(
                    f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n"
                )

        print("✅ Netscape cookies generated:", output_file)
    except Exception as e:
        print("❌ Cookie conversion failed:", e)


# Fetch cookies using Playwright
async def fetch_instagram_cookies(username, password):
    print("🔄 Logging in to Instagram...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto("https://www.instagram.com/accounts/login/")
            await page.wait_for_timeout(5000)

            await page.fill("input[name='username']", username)
            await page.fill("input[name='password']", password)
            await page.click("button[type='submit']")
            await page.wait_for_timeout(8000)

            cookies = await context.cookies()

            with open(RAW_JSON_COOKIES, "w") as f:
                json.dump(cookies, f, indent=4)

            print("✅ Raw cookies saved:", RAW_JSON_COOKIES)

            convert_to_netscape(RAW_JSON_COOKIES, NETSCAPE_COOKIES)

        except Exception as e:
            print("❌ Instagram login failed:", e)

        await browser.close()


# Auto refresh cookies every 7 days
async def auto_refresh_cookies():
    while True:
        print("♻ Auto-refreshing Instagram Cookies...")
        await fetch_instagram_cookies(
            INSTAGRAM_USERNAME,
            INSTAGRAM_PASSWORD
        )

        await asyncio.sleep(7 * 24 * 60 * 60)  # 7 days