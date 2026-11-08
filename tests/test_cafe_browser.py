from pathlib import Path
def main():
    from playwright.sync_api import sync_playwright
    page_path = Path("prototypes/cafe-au-lait-experience.html").resolve()
    assert page_path.is_file(), "Must test the checked-out repository file"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width, height in [(320, 720), (390, 844), (1280, 800)]:
            context = browser.new_context(viewport={"width": width, "height": height}, reduced_motion="reduce")
            page = context.new_page()
            outbound = []
            page.on("request", lambda req: outbound.append(req.url) if not req.url.startswith("file:") else None)
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.goto(page_path.as_uri())
            assert page.title().startswith("WIDEN"), page.title()
            assert page.locator("#visitNotice").inner_text() == "This visit is local and temporary. Changing moods clears the current conversation, unfinished activity, and any finished keepsake; make a new one whenever you wish. Nothing is saved or sent. All six experimental moods are available in this local prototype."
            page.get_by_role("link", name="Skip to experience").focus()
            page.keyboard.press("Enter")
            assert page.locator("#experience").evaluate("(el) => document.activeElement === el")
            assert page.get_by_role("region", name="Experience panels").count() == 1
            assert page.locator("#experience").evaluate("(el) => getComputedStyle(el).outlineStyle") == "solid"
            assert page.locator('[data-mood]').count() == 6
            assert page.locator('#headline').is_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"horizontal overflow at {width}px"
            for mood in ["curiosity", "events", "cozy", "fire", "party", "cafe"]:
                page.locator(f'[data-mood="{mood}"]').click()
                assert page.locator(f'[data-mood="{mood}"]').get_attribute("aria-pressed") == "true"
                assert page.locator("#cafeConversation").is_visible() == (mood == "cafe")
                assert page.locator("#headline").evaluate("(el) => document.activeElement === el")
                assert page.locator("#headline").evaluate("(el) => getComputedStyle(el).outlineStyle") == "solid", f"focused mood heading has no visible focus indicator: {mood}"
                assert page.locator("#headline").evaluate("(el) => getComputedStyle(el).outlineWidth") == "3px"
                page.locator("#explore").click()
                assert page.locator("#explore").get_attribute("aria-expanded") == "true"
                assert page.locator("#activity").is_visible()
                assert page.locator("#activity").evaluate("(el) => document.activeElement === el")
                assert page.locator("#activity").evaluate("(el) => getComputedStyle(el).outlineStyle") == "solid", f"focused activity region has no visible focus indicator: {mood}"
                assert page.locator("#activity").evaluate("(el) => getComputedStyle(el).outlineWidth") == "3px"
                page.locator("#activity").focus()
                page.keyboard.press("Escape")
                assert page.locator("#explore").get_attribute("aria-expanded") == "false"
                assert page.locator("#explore").evaluate("(el) => document.activeElement === el")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"activity overflow {mood} at {width}px"
            # Newly updated local activities must announce their changed text to AT.
            page.locator('[data-mood="cafe"]').click()
            page.locator("#explore").click()
            cafe_status = page.locator("#activity [role=status]")
            assert cafe_status.get_attribute("aria-live") == "polite"
            page.get_by_role("button", name="What surprised you lately?").click()
            prompt_question = "What surprised you lately?"
            assert "Choose Carry my question" in cafe_status.inner_text()
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
            assert cafe_question in cafe_status.inner_text()
            page.locator("#leave").click()
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
            payload = "<img src=x onerror=alert(1)>"
            page.locator("#cafeQuestion").fill(payload)
            page.get_by_role("button", name="Carry my question").click()
            assert payload in cafe_status.inner_text()
            assert page.locator("#activity img").count() == 0
            page.locator("#leave").click()
            assert payload in page.locator("#keepsakeLine").inner_text()
            page.locator('[data-mood="cozy"]').click()
            assert page.locator("#keepsakeLine").inner_text() == ""
            page.locator('[data-mood="cafe"]').click()
            page.locator("#explore").click()
            assert page.locator("#cafeQuestion").input_value() == ""
            page.locator('[data-mood="cozy"]').click()
            page.locator("#explore").click()
            cozy_status = page.locator("#activity [role=status]")
            assert cozy_status.get_attribute("aria-live") == "polite"
            page.get_by_role("button", name="Let the room settle").click()
            assert "The room is quiet" in cozy_status.inner_text()
            # Current Events is a single dated story, not a feed or dashboard.
            page.locator('[data-mood="events"]').click()
            page.locator("#explore").click()
            story = page.locator("#activity .event-story")
            assert story.count() == 1
            assert story.get_attribute("aria-labelledby") == "eventStoryTitle"
            assert page.get_by_role("article", name="Swift’s final descent").count() == 1
            footer = page.locator(".footer").inner_text()
            assert "Some mood prompts are illustrative or fictional" in footer
            assert "Current Events is a dated archive snapshot" in footer
            assert "No source is fetched automatically" in footer
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
                assert "noopener" in link.get_attribute("rel") and "noreferrer" in link.get_attribute("rel")
            event_question = story.locator(".event-question")
            assert event_question.get_attribute("role") == "status"
            assert event_question.get_attribute("aria-live") == "polite"
            page.get_by_role("button", name="Carry this question into the café").click()
            assert "For your visit receipt" in event_question.inner_text()
            page.locator("#leave").click()
            assert "What remains when an instrument goes quiet?" in page.locator("#keepsakeLine").inner_text()
            # Curiosity is a source-grounded object encounter with a voluntary keepsake.
            page.locator('[data-mood="curiosity"]').click()
            page.locator("#explore").click()
            artifact = page.locator("#activity .artifact-card")
            assert artifact.count() == 1
            assert "A SURVIVING COPY · 3 NOVEMBER 1992" in artifact.inner_text()
            assert "not a transcript of the page as first published in 1991" in artifact.inner_text()
            assert "The WorldWideWeb (W3) is a wide-area hypermedia information retrieval initiative" in artifact.locator("blockquote").inner_text()
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
            page.locator('[data-mood="party"]').click()
            assert page.locator("#keepsakeLine").inner_text() == ""
            page.locator('[data-mood="curiosity"]').click()
            page.locator("#explore").click()
            assert page.locator("#curiosityQuestion").input_value() == ""
            assert page.get_by_role("button", name="Look through the access lens").get_attribute("aria-pressed") == "false"

            page.locator('[data-mood="party"]').click()
            page.locator("#explore").click()
            page.get_by_label("Theme").select_option("Unfinished Stories")
            page.get_by_label("Ritual").select_option("leave a story without an ending")
            page.get_by_label("One rule").select_option("no ranking")
            page.get_by_role("button", name="Invent my holiday").click()
            assert "The Day of Unfinished Stories" in page.locator("#activity").inner_text()
            page.locator("#leave").click()
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
            page.locator('[data-mood="fire"]').click()
            page.locator("#explore").click()
            for field in ["Publisher", "Publication date", "Population or sample", "Method", "What would disprove it?"]:
                page.get_by_role("button", name=f"Mark {field} as unknown").click()
                assert page.get_by_role("button", name=f"{field}: UNKNOWN").get_attribute("aria-pressed") == "true"
            assert "all five missing fields" in page.locator("#activity [role=status]").inner_text()
            page.locator("#verify").click()
            assert "fictional example" in page.locator("#evidence").inner_text().lower()
            # Regression: re-opening the same mood starts with fresh UNKNOWN controls.
            # Clicking the already-selected mood is intentionally a no-op; close and reopen.
            page.locator("#explore").click()
            assert page.locator("#explore").get_attribute("aria-expanded") == "false"
            page.locator("#explore").click()
            assert page.locator("#explore").get_attribute("aria-expanded") == "true"
            unknown = page.get_by_role("button", name="Mark Publisher as unknown")
            unknown.click()
            assert page.get_by_role("button", name="Publisher: UNKNOWN").get_attribute("aria-pressed") == "true"
            # Regression: switching moods clears the finished keepsake, as the notice promises.
            page.locator("#leave").click()
            assert page.locator("#keepsakeLine").inner_text().strip()
            page.locator('[data-mood="cafe"]').click()
            assert not page.locator("#keepsakeLine").inner_text().strip()
            page.locator("#join").click()
            assert page.locator("#join").get_attribute("aria-controls") == "dialogueChoices"
            assert page.locator("#join").get_attribute("aria-expanded") == "true"
            assert page.locator("#dialogueChoices").is_visible()
            assert page.locator("#dialogueChoices").get_attribute("role") == "group"
            # Escape exits without a reply, hides the controlled group, and restores focus.
            page.locator("#dialogueInput").focus()
            page.keyboard.press("Escape")
            assert page.locator("#dialogueChoices").is_hidden()
            assert page.locator("#dialogueChoices button").count() == 0
            assert page.locator("#join").get_attribute("aria-expanded") == "false"
            assert page.locator("#join").evaluate("(el) => document.activeElement === el")
            # Replacing a clicked response must focus the replacement input.
            page.locator("#join").click()
            page.get_by_role("button", name="Answer", exact=True).click()
            assert page.locator("#dialogueInput").get_attribute("aria-invalid") == "true"
            assert "Add a thought before choosing Answer" in page.locator("#dialogueInputStatus").inner_text()
            assert page.locator("#dialogueInput").get_attribute("aria-describedby") == "dialogueInputHint dialogueInputStatus"
            assert page.locator("#join").get_attribute("aria-expanded") == "true"
            assert page.locator("#dialogueChoices").is_visible()
            assert page.locator("#dialogueInput").evaluate("(el) => document.activeElement === el")
            page.locator("#dialogueInput").fill("A small thought")
            assert page.locator("#dialogueInput").get_attribute("aria-invalid") is None
            assert page.locator("#dialogueInputStatus").inner_text() == ""
            page.get_by_role("button", name="Answer", exact=True).click()
            assert page.locator("#dialogueInput").evaluate("(el) => document.activeElement === el")
            # The Café conversation belongs to the Café mood, not every room.
            # Switching away discards the unfinished local turn and hides the room;
            # returning to Café restores only its opening line.
            page.locator("#join").click()
            page.locator("#dialogueInput").fill("Unfinished private thought")
            page.locator('[data-mood="party"]').click()
            assert page.locator("#cafeConversation").is_hidden()
            assert page.locator("#dialogueChoices").is_hidden()
            assert page.locator("#join").get_attribute("aria-expanded") == "false"
            assert page.locator("#headline").evaluate("(el) => document.activeElement === el")
            page.locator('[data-mood="cafe"]').click()
            assert page.locator("#cafeConversation").is_visible()
            assert page.locator("#chat .bubble").count() == 1
            assert "Welcome. You can talk" in page.locator("#chat").inner_text()
            assert "Unfinished private thought" not in page.locator("#chat").inner_text()
            page.locator("#join").click()
            assert page.locator("#dialogueChoices").is_visible()
            assert page.locator("#join").get_attribute("aria-expanded") == "true"
            assert "What have you been wondering" in page.locator("#chat").inner_text()
            page.locator("#quiet").click()
            assert page.locator("#dialogueChoices").is_hidden()
            assert page.locator("#join").get_attribute("aria-expanded") == "false"
            # The explicit Stay silent choice must not invent a visitor utterance.
            page.locator("#join").click()
            page.get_by_role("button", name="Stay silent", exact=True).click()
            assert page.locator("#dialogueChoices").is_hidden()
            assert page.locator("#join").get_attribute("aria-expanded") == "false"
            assert page.locator("#chat .bubble.visitor").count() == 0
            assert "Silence is welcome" in page.locator("#chat").inner_text()
            assert page.locator("#join").evaluate("(el) => document.activeElement === el")
            # Rebuilding the persistent choices group across turns must not stack Escape handlers.
            page.locator("#join").click()
            page.locator("#dialogueInput").fill("First thought")
            page.get_by_role("button", name="Answer", exact=True).click()
            redirect = "Could we turn to the question behind this?"
            page.locator("#dialogueInput").fill(redirect)
            page.get_by_role("button", name="Ask something else").click()
            assert redirect in page.locator("#chat .bubble.visitor").nth(1).inner_text()
            assert page.locator("#chat .bubble.visitor").count() == 2
            assert page.locator("#dialogueChoices").is_visible()
            before_escape = page.locator("#chat .bubble").count()
            page.locator("#dialogueInput").focus()
            page.keyboard.press("Escape")
            after_escape = page.locator("#chat .bubble").count()
            assert after_escape == before_escape + 1, f"Escape added {after_escape - before_escape} exit messages; expected exactly one"
            assert page.locator("#dialogueChoices").is_hidden()
            assert page.locator("#join").get_attribute("aria-expanded") == "false"
            assert page.locator("#join").evaluate("(el) => document.activeElement === el")
            page.locator("#leave").click()
            assert "Nothing saved or sent" in page.locator("#keepsakeLine").inner_text()
            # A completed local reply is cleared when the visitor changes moods.
            page.locator("#join").click()
            page.locator("#dialogueInput").fill("A thought that should not cross moods")
            page.get_by_role("button", name="Answer", exact=True).click()
            assert "A thought that should not cross moods" in page.locator("#chat").inner_text()
            # Re-selecting Café is a no-op; leaving Café clears and hides its conversation.
            before_same_mood = page.locator("#chat .bubble").count()
            page.locator('[data-mood="cafe"]').click()
            assert page.locator("#chat .bubble").count() == before_same_mood
            assert "A thought that should not cross moods" in page.locator("#chat").inner_text()
            page.locator('[data-mood="party"]').click()
            assert page.locator("#cafeConversation").is_hidden()
            assert page.locator("#dialogueChoices").is_hidden()
            assert page.locator("#chat .bubble").count() == 1
            assert "A thought that should not cross moods" not in page.locator("#chat").text_content()
            assert page.locator("#join").get_attribute("aria-expanded") == "false"
            page.locator('[data-mood="cozy"]').click()
            assert page.locator("#cafeConversation").is_hidden()
            assert page.locator("#chat .bubble").count() == 1
            assert "A thought that should not cross moods" not in page.locator("#chat").text_content()
            assert page.locator("#dialogueChoices").is_hidden()
            assert page.locator("#join").get_attribute("aria-expanded") == "false"
            assert page.locator("#headline").evaluate("(el) => document.activeElement === el")
            assert not errors, errors
            assert not outbound, outbound
            assert page.evaluate("localStorage.length") == 0
            print(f"PASS exact checkout Chromium: {width}x{height}, six moods, keyboard Escape, dialogue, keepsake, offline")
            context.close()

        # Forced-colors mode: preserve boundaries, selected state, links and focus.
        forced_context = browser.new_context(
            viewport={"width": 390, "height": 844},
            reduced_motion="reduce",
            forced_colors="active",
        )
        forced_page = forced_context.new_page()
        forced_outbound = []
        forced_page.on("request", lambda req: forced_outbound.append(req.url) if not req.url.startswith("file:") else None)
        forced_page.goto(page_path.as_uri())
        assert forced_page.evaluate("matchMedia('(forced-colors: active)').matches")
        forced_page.locator('[data-mood="events"]').focus()
        forced_page.keyboard.press("Enter")
        assert forced_page.locator("#headline").evaluate("(el) => document.activeElement === el")
        assert forced_page.locator("#headline").evaluate("(el) => getComputedStyle(el).outlineStyle") == "solid"
        assert forced_page.locator("#headline").evaluate("(el) => getComputedStyle(el).outlineColor") != "rgba(0, 0, 0, 0)"
        forced_page.locator("#explore").click()
        forced_page.locator("details.source-card summary").click()
        forced_page.locator("#leave").click()
        forced_metrics = forced_page.evaluate("""() => {
            const style = (selector) => {
                const el = document.querySelector(selector);
                const css = getComputedStyle(el);
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
        for name in ["panel", "visual", "mood", "secondary", "source", "event-story", "event-question", "receipt"]:
            metric = forced_metrics[name]
            assert metric["borderStyle"] == "solid" and metric["borderWidth"] != "0px", f"forced-colors {name} boundary missing: {metric}"
            assert metric["background"] != "rgba(0, 0, 0, 0)", f"forced-colors {name} background missing: {metric}"
        assert "underline" in forced_metrics["linkDecoration"], forced_metrics
        assert forced_metrics["link"]["color"] != "rgba(0, 0, 0, 0)", forced_metrics

        forced_page.locator('[data-mood="curiosity"]').click()
        forced_page.locator("#explore").click()
        forced_page.get_by_role("button", name="Look through the access lens").click()
        forced_page.locator("details.artifact-back summary").click()
        artifact_metrics = forced_page.evaluate("""() => {
            const style = (selector) => {
                const el = document.querySelector(selector);
                const css = getComputedStyle(el);
                return {borderStyle: css.borderTopStyle, borderWidth: css.borderTopWidth,
                        background: css.backgroundColor, color: css.color};
            };
            return {
                card: style(".artifact-card"), quote: style(".artifact-quote"),
                lens: style(".artifact-lens[aria-pressed='true']"),
                back: style("details.artifact-back"), question: style(".artifact-question"),
                link: style("details.artifact-sources a"),
                linkDecoration: getComputedStyle(document.querySelector("details.artifact-sources a")).textDecorationLine
            };
        }""")
        for name in ["card", "quote", "lens", "back", "question"]:
            metric = artifact_metrics[name]
            assert metric["borderStyle"] == "solid" and metric["borderWidth"] != "0px", f"forced-colors artifact {name} boundary missing: {metric}"
            assert metric["background"] != "rgba(0, 0, 0, 0)", f"forced-colors artifact {name} background missing: {metric}"
        assert "underline" in artifact_metrics["linkDecoration"], artifact_metrics
        assert artifact_metrics["link"]["color"] != "rgba(0, 0, 0, 0)", artifact_metrics
        assert not forced_outbound, forced_outbound
        forced_context.close()
        print("PASS forced-colors: selected mood, panel boundaries, source links, visible focus and keepsake")
        browser.close()
    

if __name__ == '__main__':
    main()
