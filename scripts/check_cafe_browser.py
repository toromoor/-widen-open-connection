#!/usr/bin/env python3
"""Playwright smoke checks for WIDEN Café au Lait's LOCAL-ONLY experience.

Opens the checked-out HTML as a file:// page; never deploys it and does not
require a server. Asserts user-visible controls work on mobile and desktop.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "prototypes" / "cafe-au-lait-experience.html"
ARTIFACTS = ROOT / "artifacts"


def check(browser, width, height, name):
    page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
    script_errors = []
    external_requests = []
    page.on("pageerror", lambda err: script_errors.append(str(err)))
    page.on("request", lambda req: external_requests.append(req.url) if not req.url.startswith("file:") else None)
    page.goto(HTML.as_uri(), wait_until="load")
    assert "WIDEN" in page.title()
    assert page.locator("[data-mood]").count() == 5
    assert page.get_by_text("No real participants, accounts, messages, or AI agents are connected.").count() == 0 or "not a live room" in page.locator("aside").inner_text()
    assert page.locator("#keepsakeLine").inner_text() == ""

    # Café: choose a question. This interaction must not send/store the answer.
    page.get_by_role("button", name="Ask an open question").click()
    page.get_by_role("button", name="What surprised you lately?").click()
    assert "Your question" in page.locator("#activity").inner_text()

    # Claim transparency: mark five distinct unknown fields, never fabricate sources.
    page.locator("[data-mood='fire']").click()
    page.get_by_role("button", name="Inspect the headline").click()
    assert page.get_by_role("button", name="Mark UNKNOWN").count() == 5
    for _ in range(5):
        page.get_by_role("button", name="Mark UNKNOWN").first.click()
    assert "5 missing fields" in page.locator("#activity").inner_text()
    page.get_by_role("button", name="Inspect provenance").click()
    assert "fictional" in page.locator("#evidence").inner_text().lower()

    # Party: a holiday from user selections, then a voluntary keepsake.
    page.locator("[data-mood='party']").click()
    page.get_by_role("button", name="Invent a holiday").click()
    page.get_by_role("button", name="Invent my holiday").click()
    assert "The Day of" in page.locator("#activity").inner_text()
    page.get_by_role("button", name="Make my keepsake").click()
    assert "The Day of" in page.locator("#keepsakeLine").inner_text()

    # Other moods also open an interaction.
    page.locator("[data-mood='curiosity']").click()
    page.get_by_role("button", name="Try the nameless challenge").click()
    assert "NASA Astronomy Picture of the Day" in page.locator("#activity").inner_text()
    page.locator("[data-mood='cozy']").click()
    page.get_by_role("button", name="Let the room be quiet").click()
    assert "Nothing to complete" in page.locator("#activity").inner_text()

    # Three rounds with an independent exit/silence choice at every round.
    page.get_by_role("button", name="Try a conversation").click()
    assert page.locator("#dialogueChoices").count() == 1
    page.locator("#dialogueInput").fill("What does listening mean?")
    page.get_by_role("button", name="Answer", exact=True).click()
    page.get_by_role("button", name="Ask something else").click()
    page.locator("#dialogueInput").fill("The question.")
    page.get_by_role("button", name="Answer", exact=True).click()
    assert page.locator("#dialogueChoices").count() == 0
    assert page.locator("#chat .visitor").count() == 3
    assert "scripted, local-only" in page.locator("#chat").inner_text()

    # Restart, then choose silence. No residual input controls.
    page.get_by_role("button", name="Try a conversation").click()
    page.get_by_role("button", name="Stay silent").click()
    assert page.locator("#dialogueChoices").count() == 0
    assert "quiet table" in page.locator("#chat").inner_text()
    page.get_by_role("button", name="Choose silence").click()
    assert "No reply is required" in page.locator("#chat").inner_text()

    # Narrow screens should not force horizontal scrolling.
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 2, f"horizontal overflow: {overflow}px for {name}"

    ARTIFACTS.mkdir(exist_ok=True)
    page.screenshot(path=str(ARTIFACTS / f"cafe-{name}.png"), full_page=True)
    assert not script_errors, f"JavaScript exceptions: {script_errors}"
    assert not external_requests, f"Unexpected network requests: {external_requests}"
    page.close()
    print(f"PASS: {name} ({width}x{height}): moods, activities, claim, keepsake, 3-turn dialogue, silence, offline and layout")


if __name__ == "__main__":
    assert HTML.exists(), f"Missing prototype: {HTML}"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            check(browser, 390, 844, "mobile")
            check(browser, 1280, 900, "desktop")
        finally:
            browser.close()
