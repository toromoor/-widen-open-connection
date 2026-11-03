from pathlib import Path
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
        page.locator("#join").click()
        assert page.locator("#dialogueChoices").count() == 1
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
