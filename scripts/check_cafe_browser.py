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
    assert page.locator("#visitNotice").inner_text() == "This visit is local and temporary. Changing moods clears unfinished activity and any finished keepsake; make a new one whenever you wish. Nothing is saved or sent. All six experimental moods are available in this local prototype."
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

    # Café: choose a prompt or author a question, then carry it into a local keepsake.
    page.locator("#explore").click()  # initial label is "Explore this mood"
    page.get_by_role("button", name="What surprised you lately?").click()
    prompt_question = "What surprised you lately?"
    assert "Choose Carry my question" in page.locator("#activity").inner_text()
    page.locator("#leave").click()
    assert "Take one open question into your day" in page.locator("#keepsakeLine").inner_text()
    assert prompt_question not in page.locator("#keepsakeLine").inner_text()
    page.get_by_role("button", name="Carry my question").click()
    page.locator("#leave").click()
    assert prompt_question in page.locator("#keepsakeLine").inner_text()
    cafe_question = "What changes when we listen?"
    assert page.locator("#cafeQuestion").get_attribute("maxlength") == "180"
    page.locator("#cafeQuestion").fill(cafe_question)
    page.get_by_role("button", name="Carry my question").click()
    assert cafe_question in page.locator("#activity").inner_text()
    page.get_by_role("button", name="Make my keepsake").click()
    assert cafe_question in page.locator("#keepsakeLine").inner_text()
    page.locator("#explore").click()
    page.locator("#explore").click()
    assert page.locator("#cafeQuestion").input_value() == cafe_question
    assert "For your visit receipt" in page.locator("#activity [role=status]").inner_text()
    edited_question = "What changes when we listen twice?"
    page.locator("#cafeQuestion").fill(edited_question)
    assert "not on the receipt yet" in page.locator("#activity [role=status]").inner_text()
    page.locator("#leave").click()
    assert cafe_question not in page.locator("#keepsakeLine").inner_text()
    assert edited_question not in page.locator("#keepsakeLine").inner_text()
    page.get_by_role("button", name="Carry my question").click()
    page.locator("#leave").click()
    assert edited_question in page.locator("#keepsakeLine").inner_text()
    # Visitor text is untrusted data: it must remain text, never become markup.
    payload = "<img src=x onerror=alert(1)>"
    page.locator("#cafeQuestion").fill(payload)
    page.get_by_role("button", name="Carry my question").click()
    assert payload in page.locator("#activity").inner_text()
    assert page.locator("#activity img").count() == 0
    page.get_by_role("button", name="Make my keepsake").click()
    assert payload in page.locator("#keepsakeLine").inner_text()
    page.locator("[data-mood='cozy']").click()
    assert page.locator("#keepsakeLine").inner_text() == ""
    page.locator("[data-mood='cafe']").click()
    page.locator("#explore").click()
    assert page.locator("#cafeQuestion").input_value() == ""

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
    page.get_by_label("Theme").select_option("Unfinished Stories")
    page.get_by_label("Ritual").select_option("leave a story without an ending")
    page.get_by_label("One rule").select_option("no ranking")
    page.get_by_role("button", name="Invent my holiday").click()
    assert "The Day of Unfinished Stories" in page.locator("#activity").inner_text()
    page.get_by_role("button", name="Make my keepsake").click()
    assert "The Day of Unfinished Stories" in page.locator("#keepsakeLine").inner_text()
    page.locator("#explore").click()
    page.locator("#explore").click()
    assert page.get_by_label("Theme").input_value() == "Unfinished Stories"
    assert page.get_by_label("Ritual").input_value() == "leave a story without an ending"
    assert page.get_by_label("One rule").input_value() == "no ranking"
    assert "For your visit receipt" in page.locator("#activity [role=status]").inner_text()
    page.get_by_label("Theme").select_option("Tiny Triumphs")
    assert "choices changed" in page.locator("#activity [role=status]").inner_text()
    page.locator("#leave").click()
    assert "The Day of Unfinished Stories" not in page.locator("#keepsakeLine").inner_text()
    page.get_by_role("button", name="Invent my holiday").click()
    assert "The Day of Tiny Triumphs" in page.locator("#activity").inner_text()
    page.locator("#leave").click()
    assert "The Day of Tiny Triumphs" in page.locator("#keepsakeLine").inner_text()

    # Curiosity is a thought experiment, not a news container.
    page.locator("[data-mood='curiosity']").click()
    page.get_by_role("button", name="Try the nameless challenge").click()
    assert page.locator("#activity details.source-card").count() == 0
    curiosity_input = page.locator("#activity input")
    curiosity_text = "A voice like rain on a window"
    assert curiosity_input.get_attribute("maxlength") == "180"
    assert page.locator("#activity [role='status']").get_attribute("aria-live") == "polite"
    curiosity_input.fill(curiosity_text)
    page.get_by_role("button", name="Reflect locally").click()
    curiosity_result = page.locator("#activity [role='status']")
    assert curiosity_text in curiosity_result.inner_text()
    assert "Your words stay in this browser" in curiosity_result.inner_text()
    hostile_description = "<img src=x onerror=alert(1)>"
    curiosity_input.fill(hostile_description)
    page.get_by_role("button", name="Reflect locally").click()
    assert hostile_description in curiosity_result.inner_text()
    assert page.locator("#activity img").count() == 0

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
    role_notes = ((nasa_mission, "missionRoleNote"), (nasa_apod, "apodRoleNote"), (reuters, "reutersRoleNote"))
    for link, note_id in role_notes:
        assert link.get_attribute("aria-describedby") == f"{note_id} externalLinkNote"
        assert page.locator("#externalLinkNote").inner_text() == "Opens in a new tab."
        assert page.locator(f"#{note_id}").is_visible()
    assert "U.S. Space Force confirmed" in page.locator("#missionRoleNote").inner_text()
    assert "Retrospective image and mission context" in page.locator("#apodRoleNote").inner_text()
    assert "not a separate re-entry confirmation" in page.locator("#apodRoleNote").inner_text()
    assert "same U.S. Space Force confirmation" in page.locator("#reutersRoleNote").inner_text()
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
    page.get_by_role("button", name="Answer", exact=True).click()
    assert page.locator("#dialogueInput").get_attribute("aria-invalid") == "true"
    assert "Add a thought before choosing Answer" in page.locator("#dialogueInputStatus").inner_text()
    assert page.locator("#dialogueInput").get_attribute("aria-describedby") == "dialogueInputHint dialogueInputStatus"
    assert page.locator("#dialogueInput").evaluate("(el) => document.activeElement === el")
    page.locator("#dialogueInput").fill("What does listening mean?")
    assert page.locator("#dialogueInput").get_attribute("aria-invalid") is None
    assert page.locator("#dialogueInputStatus").inner_text() == ""
    page.get_by_role("button", name="Answer", exact=True).click()
    redirect = "Could we talk about the question behind the question?"
    page.locator("#dialogueInput").fill(redirect)
    page.get_by_role("button", name="Ask something else").click()
    assert redirect in page.locator("#chat .visitor").nth(1).inner_text()
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
    assert "Silence is welcome" in page.locator("#chat").inner_text()
    assert page.locator("#chat .visitor").count() == 0
    assert page.locator("#join").evaluate("(el) => document.activeElement === el")
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
    before_silence = page.locator("#chat .visitor").count()
    page.get_by_role("button", name="Stay silent").focus()
    page.keyboard.press("Enter")
    assert page.locator("#dialogueChoices").is_hidden()
    assert page.locator("#join").get_attribute("aria-expanded") == "false"
    assert page.locator("#join").evaluate("(el) => document.activeElement === el")
    assert page.locator("#chat .visitor").count() == before_silence

    # Narrow screens should not force horizontal scrolling.
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 2, f"horizontal overflow: {overflow}px for {name}"

    ARTIFACTS.mkdir(exist_ok=True)
    page.screenshot(path=str(ARTIFACTS / f"cafe-{name}.png"), full_page=True)
    assert not script_errors, f"JavaScript exceptions: {script_errors}"
    assert not external_requests, f"Unexpected network requests: {external_requests}"
    page.close()
    print(f"PASS: {name} ({width}x{height}): moods, activities, claim, keepsake, 3-turn dialogue, silence, offline and layout")



def check_forced_colors(browser):
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        forced_colors="active",
        reduced_motion="reduce",
    )
    page = context.new_page()
    external_requests = []
    page.on("request", lambda req: external_requests.append(req.url) if not req.url.startswith("file:") else None)
    page.goto(HTML.as_uri(), wait_until="load")
    assert page.evaluate("matchMedia('(forced-colors: active)').matches")
    page.locator("[data-mood='events']").focus()
    page.keyboard.press("Enter")
    assert page.locator("#headline").evaluate("(el) => document.activeElement === el")
    assert page.locator("#headline").evaluate("(el) => getComputedStyle(el).outlineStyle") == "solid"
    page.locator("#explore").click()
    page.locator("details.source-card summary").click()
    page.locator("#leave").click()
    metrics = page.evaluate("""() => {
        const style = (selector) => {
            const css = getComputedStyle(document.querySelector(selector));
            return {borderStyle: css.borderTopStyle, borderWidth: css.borderTopWidth,
                    background: css.backgroundColor, color: css.color};
        };
        return {
            panel: style(".panel"),
            visual: style(".visual"),
            mood: style(".mood[aria-pressed='true']"),
            secondary: style("#verify"),
            source: style("details.source-card"),
            "event-story": style(".event-story"),
            "event-question": style(".event-question"),
            link: style("details.source-card a"),
            receipt: style(".receipt"),
            linkDecoration: getComputedStyle(document.querySelector("details.source-card a")).textDecorationLine
        };
    }""")
    for name in ("panel", "visual", "mood", "secondary", "source", "event-story", "event-question", "receipt"):
        metric = metrics[name]
        assert metric["borderStyle"] == "solid" and metric["borderWidth"] != "0px", f"forced-colors {name} boundary missing: {metric}"
        assert metric["background"] != "rgba(0, 0, 0, 0)", f"forced-colors {name} background missing: {metric}"
    assert "underline" in metrics["linkDecoration"], metrics
    assert metrics["link"]["color"] != "rgba(0, 0, 0, 0)", metrics
    assert not external_requests, external_requests
    page.screenshot(path=str(ARTIFACTS / "cafe-forced-colors.png"), full_page=True)
    context.close()
    print("PASS: forced-colors (390x844): selected mood, panel boundaries, source links, focus and keepsake")



if __name__ == "__main__":
    assert HTML.exists(), f"Missing prototype: {HTML}"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            check(browser, 390, 844, "mobile")
            check(browser, 1280, 900, "desktop")
            check_forced_colors(browser)
        finally:
            browser.close()
