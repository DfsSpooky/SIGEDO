import asyncio
from playwright.async_api import async_playwright, expect

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Login
        await page.goto("http://127.0.0.1:8080/accounts/login/")
        await page.get_by_label("Username").fill("admin")
        await page.get_by_label("Password").fill("admin")
        await page.get_by_role("button", name="login").click()

        # Wait for login to complete by checking for a known element on the dashboard
        await expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()

        # Verify Lista de Credenciales
        await page.goto("http://127.0.0.1:8080/credenciales/")
        await expect(page.get_by_role("heading", name="Generador de Credenciales")).to_be_visible()
        await page.screenshot(path="jules-scratch/verification/credenciales.png")

        # Verify Vista Pública de Horarios
        await page.goto("http://127.0.0.1:8080/horarios/ver/")
        await expect(page.get_by_role("heading", name="Consulta de Horarios")).to_be_visible()

        # Select an option to show the schedule
        # Assuming the first option is a valid one
        await page.select_option("select[name='especialidad']", index=1)

        # Wait for the table to be visible
        await expect(page.get_by_role("table")).to_be_visible()

        await page.screenshot(path="jules-scratch/verification/horarios.png")

        await browser.close()

asyncio.run(main())
