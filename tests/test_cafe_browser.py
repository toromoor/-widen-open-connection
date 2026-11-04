from pathlib import Path
def main():
    from playwright.sync_api import sync_playwright
    page_path = Path("prototypes/cafe-au-lait-experience.html").resolve()
    assert page_path.is_file(), "Must test the checked-out repository file"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width, height in [(390, 844), (1280, 800)]:
            context = browser.new_context(viewport={"width": width, "height": height}, reduced_motion="reduce")
            page = context.new_page()
            outbound = []
            page.on("request", lambda req: outbound.append(req.url) if not req.url.startswith("file:") else None)
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.goto(page_path.as_uri())
            assert page.title().startswith("WIDEN"), page.title()
            assert page.locator('[data-mood]').count() == 5
            assert page.locator('#headline').is_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"horizontal overflow at {width}px"
            for mood in ["curiosity", "cozy", "fire", "party", "cafe"]:
                page.locator(f'[data-mood="{mood}"]').click()
                assert page.locator(f'[data-mood="{mood}"]').get_attribute("aria-pressed") == "true"
                assert page.locator("#headline").is_focused()
                page.locator("#explore").click()
                assert page.locator("#explore").get_attribute("aria-expanded") == "true"
                assert page.locator("#activity").is_visible()
                page.locator("#activity").focus()
                page.keyboard.press("Escape")
                assert page.locator("#explore").get_attribute("aria-expanded") == "false"
                assert page.locator("#explore").is_focused()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"activity overflow {mood} at {width}px"
            # Regression: the claim-clinic button must announce its new state.
            page.locator('[data-mood="fire"]').click()
            page.locator("#explore").click()
            unknown = page.get_by_role("button", name="Mark Publisher as unknown")
            unknown.click()
            assert page.get_by_role("button", name="Publisher: UNKNOWN").get_attribute("aria-pressed") == "true"
            # Regression: switching moods clears the finished keepsake, as the notice promises.
            page.locator("#leave").click()
            assert page.locator("#keepsakeLine").inner_text().strip()
            page.locator('[data-mood="cafe"]').click()
            assert not page.locator("#keepsakeLine").inner_text().strip()
            page.locator("#join").click()
            assert page.locator("#dialogueChoices").count() == 1
            # Escape exits without a reply and restores focus.
            page.locator("#dialogueInput").focus()
            page.keyboard.press("Escape")
            assert page.locator("#dialogueChoices").count() == 0
            assert page.locator("#join").is_focused()
            # Replacing a clicked response must focus the replacement input.
            page.locator("#join").click()
            page.get_by_role("button", name="Answer", exact=True).click()
            assert page.locator("#dialogueInput").is_focused()
            page.locator("#quiet").click()
            assert page.locator("#dialogueChoices").count() == 0
            page.locator("#leave").click()
            assert "Nothing saved or sent" in page.locator("#keepsakeLine").inner_text()
            assert not errors, errors
            assert not outbound, outbound
            assert page.evaluate("localStorage.length") == 0
            print(f"PASS exact checkout Chromium: {width}x{height}, five moods, keyboard Escape, dialogue, keepsake, offline")
            context.close()
        browser.close()
    

if __name__ == '__main__':
    main()
