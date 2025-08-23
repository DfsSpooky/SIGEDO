import asyncio
from playwright.async_api import async_playwright, Page, expect

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Login
        await page.goto("http://127.0.0.1:8000/accounts/login/")
        await page.get_by_label("Usuario o DNI").fill("admin")
        await page.get_by_label("Contraseña").fill("admin")
        await page.get_by_role("button", name="Iniciar Sesión").click()
        await page.wait_for_url("http://127.0.0.1:8000/")

        # Perfil
        await page.goto("http://127.0.0.1:8000/perfil/")
        await page.screenshot(path="jules-scratch/verification/perfil.png")

        # Reservas
        await page.goto("http://127.0.0.1:8000/reservas/")
        await page.screenshot(path="jules-scratch/verification/reservas.png")

        # Credenciales
        await page.goto("http://127.0.0.1:8000/credenciales/")
        await page.screenshot(path="jules-scratch/verification/credenciales.png")

        # Horarios
        await page.goto("http://127.0.0.1:8000/horarios/ver/")
        # This will fail if there are no 'especialidades'
        try:
            await page.get_by_label("Ver horario de:").select_option(index=1)
            await page.wait_for_load_state('networkidle')
        except Exception as e:
            print(f"Could not select specialty, maybe there are none? {e}")
        await page.screenshot(path="jules-scratch/verification/horarios.png")

        await browser.close()

asyncio.run(main())
