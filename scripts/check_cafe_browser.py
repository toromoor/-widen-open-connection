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
    assert page.locator("#visitNotice").inner_text() == "This visit is local and temporary. Changing moods clears the current conversation, unfinished activity, and any finished keepsake; make a new one whenever you wish. Nothing is saved or sent. All six experimental moods are available in this local prototype."
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
        assert page.locator("#cafeConversation").is_visible() == (mood == "cafe")
        single_room = page.locator("#experience").evaluate("(el) => el.classList.contains('single-room')")
        assert single_room == (mood != "cafe")
        grid_columns = page.locator("#experience").evaluate("(el) => getComputedStyle(el).gridTemplateColumns.trim().split(/\\s+/).length")
        expected_columns = 1 if width <= 720 or mood != "cafe" else 2
        assert grid_columns == expected_columns, f"{mood} layout has {grid_columns} columns at {width}px"
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

    # Hair on Fire is an evidence desk, not a five-checkbox form or a truth score.
    page.locator("[data-mood='fire']").click()
    page.get_by_role("button", name="Open the evidence desk").click()
    fire_case = page.locator("#activity .fire-case")
    assert fire_case.count() == 1
    assert "FICTIONAL PRACTICE CASE" in fire_case.inner_text()
    assert "not a real event" in fire_case.inner_text().lower()
    assert "score" not in fire_case.inner_text().lower()
    clues = page.locator("#activity .fire-clue")
    assert clues.count() == 3
    origin, measure, echo = clues.nth(0), clues.nth(1), clues.nth(2)
    assert origin.locator(".fire-choices").get_attribute("role") == "group"
    assert origin.locator(".fire-feedback").get_attribute("aria-live") == "polite"
    assert page.locator("#fireProgress").get_attribute("aria-live") == "polite"
    origin.get_by_role("button", name="Choose reading: It shows only that a screenshot exists").click()
    origin.get_by_role("button", name="Compare this clue").click()
    assert "does not identify who created it" in origin.locator(".fire-feedback").inner_text()
    page.get_by_role("button", name="Build a cautious reading").click()
    assert "INCOMPLETE REVIEW" in page.locator("#fireVerdict").inner_text()
    assert page.locator("#fireCarry").is_disabled()
    measure.get_by_role("button", name="Choose reading: It is an undefined reach claim").click()
    measure.get_by_role("button", name="Compare this clue").click()
    echo.get_by_role("button", name="Choose reading: Leave this clue open").click()
    echo.get_by_role("button", name="Compare this clue").click()
    assert "You left this clue open" in echo.locator(".fire-feedback").inner_text()
    assert "3 of 3 clues compared" in page.locator("#fireProgress").inner_text()
    page.get_by_role("button", name="Build a cautious reading").click()
    assert "UNVERIFIED — NOT DISPROVED" in page.locator("#fireVerdict").inner_text()
    page.locator("#leave").click()
    assert "UNVERIFIED — NOT DISPROVED" not in page.locator("#keepsakeLine").inner_text()
    page.get_by_role("button", name="Carry this cautious reading").click()
    page.locator("#leave").click()
    assert "UNVERIFIED — NOT DISPROVED" in page.locator("#keepsakeLine").inner_text()
    # A changed clue invalidates the old carried reading and receipt.
    origin.get_by_role("button", name="Choose reading: It proves the claim is false").click()
    assert page.locator("#keepsakeLine").inner_text() == ""
    assert page.locator("#fireCarry").is_disabled()
    assert "Your reading changed" in page.locator("#fireVerdict").inner_text()
    assert "2 of 3 clues compared" in page.locator("#fireProgress").inner_text()
    origin.get_by_role("button", name="Compare this clue").click()
    page.get_by_role("button", name="Build a cautious reading").click()
    assert "UNVERIFIED — NOT DISPROVED" in page.locator("#fireVerdict").inner_text()
    page.get_by_role("button", name="Carry this cautious reading").click()
    page.locator("#leave").click()
    assert "UNVERIFIED — NOT DISPROVED" in page.locator("#keepsakeLine").inner_text()
    source = page.locator("details.fire-source")
    source.locator("summary").click()
    dig = page.get_by_role("link", name="Digital Inquiry Group · About Civic Online Reasoning")
    assert dig.get_attribute("href") == "https://cor.inquirygroup.org/about/"
    assert dig.get_attribute("target") == "_blank"
    assert "noopener" in dig.get_attribute("rel") and "noreferrer" in dig.get_attribute("rel")
    assert dig.get_attribute("aria-describedby") == "fireSourceRoleNote fireNewTabNote"
    page.get_by_role("button", name="Inspect provenance").click()
    assert "fictional training case" in page.locator("#evidence").inner_text().lower()

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

    # Curiosity is a source-grounded object encounter, not a questionnaire.
    page.locator("[data-mood='curiosity']").click()
    page.get_by_role("button", name="Examine the object").click()
    page.screenshot(path=str(ARTIFACTS / f"curiosity-object-{name}.png"), full_page=True)
    artifact = page.locator("#activity .artifact-card")
    assert artifact.count() == 1
    assert "A SURVIVING COPY · 3 NOVEMBER 1992" in artifact.inner_text()
    assert "not a transcript of the page as first published in 1991" in artifact.inner_text()
    assert "The WorldWideWeb (W3) is a wide-area hypermedia information retrieval initiative" in artifact.locator("blockquote").inner_text()
    assert page.locator("#activity details.artifact-sources").count() == 1
    page.locator("details.artifact-sources summary").click()
    assert page.locator("details.artifact-sources").evaluate("(el) => el.open")
    w3c = page.get_by_role("link", name="W3C archive copy · 3 Nov 1992")
    cern_record = page.get_by_role("link", name="CERN historical record · what survives")
    cern_history = page.get_by_role("link", name="CERN · where the web was born")
    assert w3c.get_attribute("href") == "https://www.w3.org/History/19921103-hypertext/hypertext/WWW/TheProject.html"
    assert cern_record.get_attribute("href") == "https://cds.cern.ch/record/1997535"
    assert cern_history.get_attribute("href") == "https://home.cern/science/computing/the-birth-of-the-web/where-web-was-born/"
    for link, note_id in [(w3c, "curiosityW3cRole"), (cern_record, "curiosityCernRecordRole"), (cern_history, "curiosityCernHistoryRole")]:
        assert link.get_attribute("aria-describedby") == f"{note_id} curiosityExternalLinkNote"
        assert "noopener" in link.get_attribute("rel") and "noreferrer" in link.get_attribute("rel")
    page.locator("details.artifact-back summary").click()
    assert page.locator("details.artifact-back").evaluate("(el) => el.open")
    assert "not proof of the exact first wording" in page.locator("details.artifact-back").inner_text()
    assert "no screenshots of that original page exist" in page.locator("details.artifact-back").inner_text()
    access = page.get_by_role("button", name="Look through the access lens")
    discovery = page.get_by_role("button", name="Look through the discovery lens")
    stewardship = page.get_by_role("button", name="Look through the stewardship lens")
    for lens, prompt in [(access, "Who is included in universal access"), (discovery, "Who or what makes it discoverable"), (stewardship, "Who keeps a link alive")]:
        lens.click()
        assert lens.get_attribute("aria-pressed") == "true"
        assert prompt in page.locator("#curiosityLensResult").inner_text()
    access.click()
    curiosity_input = page.locator("#curiosityQuestion")
    assert page.get_by_label("Your question (optional)").count() == 1
    assert curiosity_input.get_attribute("maxlength") == "240"
    assert curiosity_input.get_attribute("aria-describedby") == "curiosityQuestionNote"
    assert page.locator("#curiosityQuestionNote").is_visible()
    assert "nothing is saved, sent, or shown to another visitor" in page.locator("#curiosityQuestionNote").inner_text()
    assert page.locator("#curiosityQuestionResult").get_attribute("aria-live") == "polite"
    carry_button = page.get_by_role("button", name="Carry my question")
    carry_style = carry_button.evaluate("(el) => { const s = getComputedStyle(el); return {color: s.color, background: s.backgroundColor}; }")
    assert carry_style["color"] == "rgb(255, 241, 213)", carry_style
    assert carry_style["background"] == "rgb(41, 35, 30)", carry_style
    page.get_by_role("button", name="Carry my question").click()
    assert "Write a question first" in page.locator("#curiosityQuestionResult").inner_text()
    assert curiosity_input.evaluate("(el) => document.activeElement === el")
    hostile_question = "<img src=x onerror=alert(1)>"
    curiosity_input.fill(hostile_question)
    page.get_by_role("button", name="Carry my question").click()
    assert hostile_question in page.locator("#curiosityQuestionResult").inner_text()
    assert "Access lens" in page.locator("#curiosityQuestionResult").inner_text()
    assert page.locator("#activity img").count() == 0
    page.locator("#leave").click()
    assert hostile_question in page.locator("#keepsakeLine").inner_text()
    curiosity_input.fill("An edited question that is not carried yet")
    assert "not on the receipt yet" in page.locator("#curiosityQuestionResult").inner_text()
    page.locator("#leave").click()
    assert "An edited question" not in page.locator("#keepsakeLine").inner_text()
    assert hostile_question not in page.locator("#keepsakeLine").inner_text()
    page.get_by_role("button", name="Carry my question").click()
    assert "An edited question that is not carried yet" in page.locator("#curiosityQuestionResult").inner_text()
    page.locator("#explore").click()
    page.locator("#explore").click()
    assert page.locator("#curiosityQuestion").input_value() == "An edited question that is not carried yet"
    assert page.get_by_role("button", name="Look through the access lens").get_attribute("aria-pressed") == "true"
    assert "For your visit receipt" in page.locator("#curiosityQuestionResult").inner_text()
    page.locator("[data-mood='party']").click()
    assert page.locator("#keepsakeLine").inner_text() == ""
    page.locator("[data-mood='curiosity']").click()
    page.get_by_role("button", name="Examine the object").click()
    assert page.locator("#curiosityQuestion").input_value() == ""
    assert page.get_by_role("button", name="Look through the access lens").get_attribute("aria-pressed") == "false"

    # Current Events is one dated story with an inspectable source trail, not a feed.
    page.locator("[data-mood='events']").click()
    page.get_by_role("button", name="Open one story").click()
    story = page.locator("#activity .event-story")
    assert story.count() == 1
    assert "ONE STORY · ARCHIVE SNAPSHOT · 8 NOV 2026" in story.inner_text()
    assert "Swift’s final descent" in story.inner_text()
    assert "do not provide a confirmed debris-recovery account" in story.inner_text()
    trail = story.locator("details.source-card")
    assert trail.count() == 1
    assert not trail.evaluate("(el) => el.open")
    trail.locator("summary").click()
    assert trail.evaluate("(el) => el.open")
    assert "not two independent tracking measurements" in trail.inner_text()
    assert "thermospheric density" in story.inner_text()
    assert "not a second observation" in story.inner_text()
    # The provenance panel must use the same snapshot date as the visible story.
    page.get_by_role("button", name="What is this based on?").click()
    evidence = page.locator("#evidence").inner_text()
    assert "Archive snapshot dated 8 November 2026" in evidence
    assert "Archive snapshot dated 6 November 2026" not in evidence
    assert "Cecilia Chirenti, Robert Nemiroff, Jerry Bonnell, and Keighley Rockcliffe" in trail.inner_text()
    page.screenshot(path=str(ARTIFACTS / f"events-story-{name}.png"), full_page=True)
    nasa_mission = page.get_by_role("link", name="NASA mission update · Alise Fisher · 2 Nov 2026, updated 4 Nov")
    swift_archive = page.get_by_role("link", name="NASA Swift Archive · public observation data")
    ccmc = page.get_by_role("link", name="NASA CCMC · Swift re-entry modelling challenge + public data · updated 8 Nov 2026")
    assert swift_archive.get_attribute("href") == "https://swift.gsfc.nasa.gov/archive/"
    assert nasa_mission.get_attribute("href") == "https://science.nasa.gov/blogs/swift/2026/11/02/nasas-swift-observatory-to-re-enter-atmosphere/"
    nasa_apod = page.get_by_role("link", name="NASA APOD · “A Farewell to Swift” · 6 Nov 2026")
    assert nasa_apod.get_attribute("href") == "https://science.nasa.gov/image-article/apod-2026-november-6-a-farewell-to-swift/"
    reuters = page.get_by_role("link", name="Reuters · Steve Gorman · 4 Nov 2026, updated 5 Nov")
    assert reuters.get_attribute("href") == "https://www.reuters.com/science/nasas-22-year-old-swift-satellite-telescope-falls-orbit-fiery-finale-2026-11-04/"
    role_notes = ((nasa_mission, "missionRoleNote"), (swift_archive, "archiveRoleNote"), (ccmc, "ccmcRoleNote"), (nasa_apod, "apodRoleNote"), (reuters, "reutersRoleNote"))
    for link, note_id in role_notes:
        assert link.get_attribute("aria-describedby") == f"{note_id} externalLinkNote"
        assert page.locator("#externalLinkNote").inner_text() == "Opens in a new tab."
        assert page.locator(f"#{note_id}").is_visible()
    assert "U.S. Space Force confirmed" in page.locator("#missionRoleNote").inner_text()
    assert "public search and retrieval routes" in page.locator("#archiveRoleNote").inner_text()
    assert ccmc.get_attribute("href") == "https://ccmc.gsfc.nasa.gov/swift-challenge/index.php"
    assert "thermospheric-density uncertainty" in page.locator("#ccmcRoleNote").inner_text()
    assert "not an independent observation" in page.locator("#ccmcRoleNote").inner_text()
    assert "not re-entry tracking" in page.locator("#archiveRoleNote").inner_text()
    assert "Two publishers, five links" in trail.inner_text()
    assert "Retrospective image and mission context" in page.locator("#apodRoleNote").inner_text()
    assert "not a separate re-entry confirmation" in page.locator("#apodRoleNote").inner_text()
    assert "same U.S. Space Force confirmation" in page.locator("#reutersRoleNote").inner_text()
    for link in (nasa_mission, swift_archive, ccmc, nasa_apod, reuters):
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

    # Conversation belongs to Café au Lait, not the Cozy or Curiosity rooms.
    page.locator("[data-mood='cafe']").click()
    assert page.locator("#cafeConversation").is_visible()

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

    # Mood switching is a disclosed reset boundary for the local conversation.
    page.locator("#join").click()
    page.locator("#dialogueInput").fill("A thought that should not cross moods")
    page.get_by_role("button", name="Answer", exact=True).click()
    assert "A thought that should not cross moods" in page.locator("#chat").inner_text()
    page.locator("[data-mood='party']").click()
    assert page.locator("#cafeConversation").is_hidden()
    assert page.locator("#chat .bubble").count() == 1
    assert "A thought that should not cross moods" not in page.locator("#chat").text_content()
    assert page.locator("#dialogueChoices").is_hidden()
    assert page.locator("#join").get_attribute("aria-expanded") == "false"
    assert page.locator("#headline").evaluate("(el) => document.activeElement === el")

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

    page.locator("[data-mood='fire']").click()
    page.locator("#explore").click()
    page.locator("details.fire-source summary").click()
    page.locator(".fire-clue").first.get_by_role("button", name="Choose reading: It shows only that a screenshot exists").click()
    fire_metrics = page.evaluate("""() => {
        const style = (selector) => {
            const css = getComputedStyle(document.querySelector(selector));
            return {borderStyle: css.borderTopStyle, borderWidth: css.borderTopWidth,
                    background: css.backgroundColor, color: css.color};
        };
        return {
            caseFile: style(".fire-case"), clue: style(".fire-clue"),
            choice: style(".fire-choice[aria-pressed='true']"),
            verdict: style(".fire-verdict"), source: style(".fire-source"),
            link: style(".fire-source a"),
            linkDecoration: getComputedStyle(document.querySelector(".fire-source a")).textDecorationLine
        };
    }""")
    for name in ("caseFile", "clue", "choice", "verdict", "source"):
        metric = fire_metrics[name]
        assert metric["borderStyle"] == "solid" and metric["borderWidth"] != "0px", f"forced-colors Hair on Fire {name} boundary missing: {metric}"
        assert metric["background"] != "rgba(0, 0, 0, 0)", f"forced-colors Hair on Fire {name} background missing: {metric}"
    assert "underline" in fire_metrics["linkDecoration"], fire_metrics
    assert fire_metrics["link"]["color"] != "rgba(0, 0, 0, 0)", fire_metrics
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
