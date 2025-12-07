from playwright.async_api import async_playwright
import json
import asyncio
import os

COOKIES_FILE = "instagram_cookies.json"

async def fetch_instagram_cookies(username, password):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://www.instagram.com/accounts/login/")
        await page.wait_for_timeout(5000)

        await page.fill("input[name='username']", username)
        await page.fill("input[name='password']", password)
        await page.click("button[type='submit']")
        await page.wait_for_timeout(8000)

        cookies = await context.cookies()
        with open(COOKIES_FILE, "w") as f:
            json.dump(cookies, f, indent=4)

        await browser.close()

async def load_cookies_to_instaloader(loader):
    if os.path.exists(COOKIES_FILE):
        with open(COOKIES_FILE, "r") as f:
            cookies = json.load(f)

        for c in cookies:
            loader.context._session.cookies.set(
                c["name"], c["value"], domain=c["domain"]
            )

    return loader