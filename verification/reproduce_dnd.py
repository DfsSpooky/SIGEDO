from playwright.sync_api import sync_playwright, expect

def run():
    print("Starting Drag & Drop verification...")
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

        # Wait for sidebar to appear (it's part of the template now)
        page.wait_for_selector("#planner-sidebar-container", timeout=10000)

        # Switch to Afternoon
        page.click("a.tab:has-text('Turno Tarde')")
        page.wait_for_selector("#schedule-afternoon", state="visible", timeout=10000)
        page.wait_for_timeout(1000)

        assigned_items = page.locator("#schedule-afternoon .assigned-course-item")

        if assigned_items.count() > 0:
            source = assigned_items.first
            target = page.locator("#schedule-afternoon .drop-zone:not(:has(.assigned-course-item))").last

            print(f"Dragging from Source to Target")

            source.scroll_into_view_if_needed()
            target.scroll_into_view_if_needed()

            # Manual drag
            box_source = source.bounding_box()
            box_target = target.bounding_box()

            page.mouse.move(box_source['x'] + box_source['width'] / 2, box_source['y'] + box_source['height'] / 2)
            page.mouse.down()
            page.wait_for_timeout(200) # Wait a bit
            page.mouse.move(box_target['x'] + box_target['width'] / 2, box_target['y'] + box_target['height'] / 2, steps=10)
            page.wait_for_timeout(200) # Wait a bit before drop
            page.mouse.up()

            # Wait a bit for log
            page.wait_for_timeout(2000)

            # Check for console logs indicating reload?
            # We don't have console logs for network triggers unless we spy on network.
            # But we can check if drag succeeded visually.
            if target.locator(".assigned-course-item").count() > 0:
                print("SUCCESS: Item moved to target.")
            else:
                print("FAILURE: Item did not move to target.")

        else:
            print("No items in afternoon schedule to drag.")

        browser.close()

if __name__ == "__main__":
    run()
