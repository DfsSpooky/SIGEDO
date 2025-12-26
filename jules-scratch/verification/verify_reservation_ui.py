import re
from playwright.sync_api import sync_playwright, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # Log in
    page.goto("http://127.0.0.1/accounts/login/")
    page.get_by_label("Usuario o DNI").fill("admin")
    page.get_by_label("Contraseña").fill("admin")
    page.get_by_role("button", name="Iniciar Sesión").click()

    # Wait for navigation to the dashboard after login
    expect(page).to_have_url(re.compile(".*")) # The dashboard is at the root

    # Navigate to the reservations page
    page.goto("http://127.0.0.1/reservas/")

    # Wait for the page to load
    expect(page.get_by_text("Disponibilidad de Equipos")).to_be_visible()

    # Find the first available equipment card
    first_card = page.locator(".equipment-card").first

    # Find the first two available time slots in the card
    available_slots = first_card.locator(".slot-chip.available")

    start_slot = available_slots.nth(0)
    end_slot = available_slots.nth(1)

    start_time = start_slot.inner_text()

    # Get the expected end time from the 'data-franja-end-time' attribute of the second slot
    expected_end_time = end_slot.get_attribute("data-franja-end-time")
    expected_end_time_formatted = expected_end_time.split(":")[0] + ":" + expected_end_time.split(":")[1]

    # Click the start and end slots
    start_slot.click()
    end_slot.click()

    # Verify the confirmation text
    confirmation_text_locator = first_card.locator(".confirmation-text")
    expected_text = f"Reservar de {start_time} a {expected_end_time_formatted}."
    expect(confirmation_text_locator).to_have_text(expected_text)

    # Take a screenshot
    page.screenshot(path="jules-scratch/verification/reservation_ui.png")
    print("Screenshot taken and saved to jules-scratch/verification/reservation_ui.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
