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
    page.get_by_role("link", name="Skip to experience").focus()
    page.keyboard.press("Enter")
    assert page.locator("#experience").evaluate("(el) => document.activeElement === el")
    assert page.get_by_role("region", name="Experience panels").count() == 1
    assert page.locator("#experience").evaluate("(el) => getComputedStyle(el).outlineStyle") == "solid"
    assert page.locator("[data-mood]").count() == 6
    assert page.get_by_text("No real participants, accounts, messages, or AI agents are connected.").count() == 0 or "not a live room" in page.locator("aside").inner_text()
    assert page.locator("#keepsakeLine").inner_text() == ""

    # Each mood changes the atmosphere as well as the activity.
    ARTIFACTS.mkdir(exist_ok=True)
    mood_visuals = {}
    mood_backgrounds = {}
    for mood in ("cafe", "curiosity", "events", "cozy", "fire", "party"):
        page.locator(f"[data-mood='{mood}']").click()
        assert page.locator("body").get_attribute("data-active-mood") == mood
        mood_visuals[mood] = page.locator("#visual").evaluate("(el) => getComputedStyle(el).backgroundImage")
        mood_backgrounds[mood] = page.evaluate("getComputedStyle(document.body).backgroundImage")
        page.screenshot(path=str(ARTIFACTS / f"mood-{mood}-{name}.png"), full_page=True)
    assert len(set(mood_visuals.values())) == 6, f"mood hero art is not distinct: {mood_visuals}"
    assert len(set(mood_backgrounds.values())) == 6, f"mood atmospheres are not distinct: {mood_backgrounds}"
    page.locator("[data-mood='cafe']").click()

    # Café: choose a question. This interaction must not send/store the answer.
    page.locator("#explore").click()  # initial label is "Explore this mood"
    page.get_by_role("button", name="What surprised you lately?").click()
    assert "Your question" in page.locator("#activity").inner_text()

    # Claim transparency: mark five distinct unknown fields, never fabricate sources.
    page.locator("[data-mood='fire']").click()
    page.get_by_role("button", name="Inspect the headline").click()
    assert page.locator(".unknown-field button[aria-pressed='false']").count() == 5
    for _ in range(5):
        page.locator(".unknown-field button[aria-pressed='false']").first.click()
    assert "all five missing fields" in page.locator("#activity").inner_text()
    page.get_by_role("button", name="Inspect provenance").click()
    assert "fictional" in page.locator("#evidence").inner_text().lower()

    # Party: a holiday from user selections, then a voluntary keepsake.
    page.locator("[data-mood='party']").click()
    page.get_by_role("button", name="Invent a holiday").click()
    page.get_by_role("button", name="Invent my holiday").click()
    assert "The Day of" in page.locator("#activity").inner_text()
    page.get_by_role("button", name="Make my keepsake").click()
    assert "The Day of" in page.locator("#keepsakeLine").inner_text()

    # Curiosity is a thought experiment, not a news container.
    page.locator("[data-mood='curiosity']").click()
    page.get_by_role("button", name="Try the nameless challenge").click()
    assert page.locator("#activity details.source-card").count() == 0
    page.locator("#activity input").fill("A voice like rain on a window")
    page.get_by_role("button", name="Reflect locally").click()
    assert "Your words stay in this browser" in page.locator("#activity").inner_text()

    # Current Events is one dated story with an inspectable source trail, not a feed.
    page.locator("[data-mood='events']").click()
    page.get_by_role("button", name="Open one story").click()
    story = page.locator("#activity .event-story")
    assert story.count() == 1
    assert "ONE STORY · ARCHIVE SNAPSHOT · 6 NOV 2026" in story.inner_text()
    assert "Swift’s final descent" in story.inner_text()
    assert "do not provide a confirmed debris-recovery account" in story.inner_text()
    trail = story.locator("details.source-card")
    assert trail.count() == 1
    assert not trail.evaluate("(el) => el.open")
    trail.locator("summary").click()
    assert trail.evaluate("(el) => el.open")
    assert "not two independent tracking measurements" in trail.inner_text()
    assert "Cecilia Chirenti, Robert Nemiroff, Jerry Bonnell, and Keighley Rockcliffe" in trail.inner_text()
    page.screenshot(path=str(ARTIFACTS / f"events-story-{name}.png"), full_page=True)
    nasa_mission = page.get_by_role("link", name="NASA mission update · Alise Fisher · 2 Nov 2026, updated 4 Nov")
    assert nasa_mission.get_attribute("href") == "https://science.nasa.gov/blogs/swift/2026/11/02/nasas-swift-observatory-to-re-enter-atmosphere/"
    nasa_apod = page.get_by_role("link", name="NASA APOD · “A Farewell to Swift” · 6 Nov 2026")
    assert nasa_apod.get_attribute("href") == "https://science.nasa.gov/image-article/apod-2026-november-6-a-farewell-to-swift/"
    reuters = page.get_by_role("link", name="Reuters · Steve Gorman · 4 Nov 2026, updated 5 Nov")
    assert reuters.get_attribute("href") == "https://www.reuters.com/science/nasas-22-year-old-swift-satellite-telescope-falls-orbit-fiery-finale-2026-11-04/"
    for link in (nasa_mission, nasa_apod, reuters):
        assert "noopener" in link.get_attribute("rel")
        assert "noreferrer" in link.get_attribute("rel")
    event_question = story.locator(".event-question")
    assert event_question.get_attribute("role") == "status"
    assert event_question.get_attribute("aria-live") == "polite"
    page.get_by_role("button", name="Carry this question into the café").click()
    assert "For your visit receipt" in event_question.inner_text()
    page.get_by_role("button", name="Make my keepsake").click()
    assert "What remains when an instrument goes quiet?" in page.locator("#keepsakeLine").inner_text()
    page.locator("[data-mood='cozy']").click()
    page.get_by_role("button", name="Let the room be quiet").click()
    assert "Nothing to complete" in page.locator("#activity").inner_text()

    # Three rounds with an independent exit/silence choice at every round.
    page.get_by_role("button", name="Try a conversation").click()
    assert page.locator("#join").get_attribute("aria-controls") == "dialogueChoices"
    assert page.locator("#join").get_attribute("aria-expanded") == "true"
    assert page.locator("#dialogueChoices").is_visible()
    assert page.locator("#dialogueChoices").get_attribute("role") == "group"
    page.locator("#dialogueInput").fill("What does listening mean?")
    page.get_by_role("button", name="Answer", exact=True).click()
    page.get_by_role("button", name="Ask something else").click()
    page.locator("#dialogueInput").fill("The question.")
    page.get_by_role("button", name="Answer", exact=True).click()
    assert page.locator("#dialogueChoices").is_hidden()
    assert page.locator("#dialogueChoices button").count() == 0
    assert page.locator("#join").get_attribute("aria-expanded") == "false"
    assert page.locator("#chat .visitor").count() == 3
    assert "scripted, local-only" in page.locator("#chat").inner_text()

    # Restart, then choose silence. No residual input controls.
    page.get_by_role("button", name="Try a conversation").click()
    page.get_by_role("button", name="Stay silent").click()
    assert page.locator("#dialogueChoices").is_hidden()
    assert page.locator("#join").get_attribute("aria-expanded") == "false"
    assert "quiet table" in page.locator("#chat").inner_text()
    page.get_by_role("button", name="Choose silence").click()
    assert "No reply is required" in page.locator("#chat").inner_text()

    # Keyboard accessibility: selected mood and activity expose their state.
    page.locator("[data-mood='cafe']").focus()
    page.keyboard.press("Enter")
    assert page.locator("[data-mood='cafe']").get_attribute("aria-pressed") == "true"
    assert page.locator("#headline").evaluate("(el) => document.activeElement === el")
    page.locator("#explore").focus()
    page.keyboard.press("Enter")
    assert page.locator("#explore").get_attribute("aria-expanded") == "true"
    assert page.locator("#activity").evaluate("(el) => document.activeElement === el")
    assert page.locator("#activity").get_attribute("role") == "region"
    page.locator("#explore").focus()
    page.keyboard.press("Enter")
    assert page.locator("#explore").get_attribute("aria-expanded") == "false"
    assert page.locator("#activity").is_hidden()

    # Keyboard-started conversation must place focus in the reply field.
    page.locator("#join").focus()
    page.keyboard.press("Enter")
    assert page.locator("#dialogueInput").evaluate("(el) => document.activeElement === el")
    assert page.locator("#join").get_attribute("aria-expanded") == "true"
    assert page.locator("#dialogueChoices").is_visible()
    page.locator("#dialogueInput").fill("A thought")
    page.get_by_role("button", name="Answer", exact=True).focus()
    page.keyboard.press("Enter")
    assert page.locator("#dialogueInput").evaluate("(el) => document.activeElement === el")
    page.get_by_role("button", name="Stay silent").focus()
    page.keyboard.press("Enter")
    assert page.locator("#dialogueChoices").is_hidden()
    assert page.locator("#join").get_attribute("aria-expanded") == "false"
    assert page.locator("#join").evaluate("(el) => document.activeElement === el")

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
