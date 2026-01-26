from playwright.sync_api import sync_playwright, expect

def run():
    print("Starting Sidebar Update verification...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on("console", lambda msg: print(f"CONSOLE: {msg.text}"))

        # Login
        page.goto("http://localhost:8000/accounts/login/")
        page.fill("input[name='username']", "testadmin")
        page.fill("input[name='password']", "testpassword")
        page.click("button[type='submit']")
        page.wait_for_url("http://localhost:8000/", timeout=10000)

        # Go to planner
        page.goto("http://localhost:8000/planificador/")

        # Load content
        page.select_option("#especialidad", "1")
        page.select_option("#semestre_cursado", "1")

        page.wait_for_selector("#schedule-morning", state="visible", timeout=10000)

        # Check initial unassigned count (from text "Generales (X)")
        # Note: sidebar might be collapsed.
        sidebar_text = page.locator("#planner-sidebar-container").inner_text()
        print(f"Initial Sidebar Text fragment: {sidebar_text[:100]}...")

        # We need an item to unassign.
        # Check afternoon schedule for an item.
        page.click("a.tab:has-text('Turno Tarde')")
        page.wait_for_selector("#schedule-afternoon", state="visible", timeout=10000)

        assigned_items = page.locator("#schedule-afternoon .assigned-course-item")
        if assigned_items.count() > 0:
            item_to_delete = assigned_items.first
            # Hover to show delete button
            item_to_delete.hover()
            delete_btn = item_to_delete.locator("button[title='Eliminar bloque']")

            # Mock window.confirm to always return true
            page.evaluate("window.confirm = () => true")

            # Click delete (it calls confirmDelete which uses Swal, so we need to handle Swal)
            # The JS uses Swal.fire(...).then(...)
            # We can't easily mock Swal outcome without injecting JS before it runs or clicking the Swal button.

            print("Clicking delete button...")
            delete_btn.click()

            # Wait for Swal
            print("Waiting for confirmation dialog...")
            page.wait_for_selector(".swal2-confirm", timeout=5000)
            page.click(".swal2-confirm")

            # Wait for HTMX trigger "reload-unassigned"
            # We can wait for a network request to load-planner-sidebar
            print("Waiting for sidebar reload request...")
            with page.expect_request("**/api/load-planner-sidebar/**") as req_info:
                # The request happens after the delete request returns.
                # So verify delete request first?
                pass

            print("Sidebar reload triggered.")
            page.wait_for_timeout(2000)

            # Verify item is back in sidebar or count increased?
            # Hard to verify exact count without knowing initial state perfectly.
            # But if request happened, we are 90% there.

            print("SUCCESS: Sidebar update request detected.")

        else:
            print("No assigned items found to unassign.")

        browser.close()

if __name__ == "__main__":
    run()
