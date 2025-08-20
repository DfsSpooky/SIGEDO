from playwright.sync_api import sync_playwright, expect

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Navigate to the login page
            page.goto("http://127.0.0.1:8000/accounts/login/")

            # Fill in the login form with corrected labels
            page.get_by_label("Usuario o DNI").fill("admin")
            page.get_by_label("Contraseña").fill("12345")
            page.get_by_role("button", name="Iniciar Sesión").click()

            # Wait for navigation to the dashboard
            expect(page).to_have_url("http://127.0.0.1:8000/")

            # Navigate to the scheduler
            page.goto("http://127.0.0.1:8000/planificador/")
            expect(page).to_have_title("Planificador de Horarios")

            # Select specialty and semester to show the planner
            page.select_option("select#especialidad", index=1)
            page.select_option("select#semestre_cursado", index=1)

            # Wait for the table header to be visible and contain the day names
            header_lunes = page.get_by_role("cell", name="Lunes")
            expect(header_lunes).to_be_visible()

            header_viernes = page.get_by_role("cell", name="Viernes")
            expect(header_viernes).to_be_visible()

            # Take a screenshot of the planner area
            planner_body = page.locator("#planner-body")
            expect(planner_body).to_be_visible()
            planner_body.screenshot(path="jules-scratch/verification/scheduler_header.png")

            print("Verification script ran successfully.")

        except Exception as e:
            print(f"An error occurred: {e}")
            page.screenshot(path="jules-scratch/verification/error.png")

        finally:
            browser.close()

if __name__ == "__main__":
    run_verification()
