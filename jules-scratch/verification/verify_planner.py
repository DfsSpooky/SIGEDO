import re
from playwright.sync_api import sync_playwright, Page, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # 1. Log in
    page.goto("http://localhost:8001/login/")
    page.get_by_placeholder("Nombre de usuario o DNI").fill("admin")
    page.get_by_placeholder("Contraseña").fill("password")
    page.get_by_role("button", name="Acceder").click()
    expect(page).to_have_url(re.compile(".*dashboard"))
    print("Login successful.")

    # 2. Navigate to the planner
    page.goto("http://localhost:8001/planificador/")
    expect(page.get_by_role("heading", name="Planificador de Horarios")).to_be_visible()
    print("Navigated to planner.")

    # 3. Select options to load the planner
    page.get_by_label("Especialidad:").select_option("1") # Assuming ID 1 exists
    page.get_by_label("Semestre:").select_option("1") # Assuming Semestre I is valid

    # Wait for the placeholder to disappear and the body to be visible
    expect(page.locator("#planner-placeholder")).to_be_hidden()
    expect(page.locator("#planner-body")).to_be_visible()
    print("Planner data loaded.")

    page.screenshot(path="jules-scratch/verification/01_planner_initial_state.png")
    print("Initial screenshot taken.")

    # 4. Drag and drop a course
    # Source: First unassigned course
    source = page.locator("#unassigned-especialidad .relative.p-2").first
    expect(source).to_be_visible()

    # Destination: An empty cell in the morning grid
    destination = page.locator("#schedule-grid-manana tr:nth-child(2) > td:nth-child(3)") # Second row, third column (Tuesday)
    expect(destination).to_be_visible()

    source.drag_to(destination)
    print("Drag and drop initiated.")

    # 5. Interact with the dialog
    expect(page.get_by_role("heading", name=re.compile("Asignar"))).to_be_visible()
    # Assign 2 blocks
    page.get_by_label("Número de bloques a asignar").fill("2")
    page.get_by_role("button", name="Asignar").click()
    print("Dialog confirmed.")

    # 6. Wait for the block to appear and take final screenshot
    # The block should now be in the destination cell
    assigned_block = destination.locator(".relative.p-2")
    expect(assigned_block).to_be_visible()
    expect(assigned_block).to_contain_text("2 bloque(s)")
    print("Block successfully assigned.")

    page.screenshot(path="jules-scratch/verification/02_planner_final_state.png")
    print("Final screenshot taken.")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
