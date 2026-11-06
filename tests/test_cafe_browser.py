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
                assert page.locator("#headline").evaluate("(el) => document.activeElement === el")
                page.locator("#explore").click()
                assert page.locator("#explore").get_attribute("aria-expanded") == "true"
                assert page.locator("#activity").is_visible()
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
            assert "Your question:" in cafe_status.inner_text()
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
            nasa_mission = page.get_by_role("link", name="NASA mission update · Alise Fisher · 2 Nov 2026, updated 4 Nov")
            assert nasa_mission.get_attribute("href") == "https://science.nasa.gov/blogs/swift/2026/11/02/nasas-swift-observatory-to-re-enter-atmosphere/"
            nasa_apod = page.get_by_role("link", name="NASA APOD · “A Farewell to Swift” · 6 Nov 2026")
            assert nasa_apod.get_attribute("href") == "https://science.nasa.gov/image-article/apod-2026-november-6-a-farewell-to-swift/"
            reuters = page.get_by_role("link", name="Reuters · Steve Gorman · 4 Nov 2026, updated 5 Nov")
            assert reuters.get_attribute("href") == "https://www.reuters.com/science/nasas-22-year-old-swift-satellite-telescope-falls-orbit-fiery-finale-2026-11-04/"
            for link in (nasa_mission, nasa_apod, reuters):
                assert "noopener" in link.get_attribute("rel") and "noreferrer" in link.get_attribute("rel")
            event_question = story.locator(".event-question")
            assert event_question.get_attribute("role") == "status"
            assert event_question.get_attribute("aria-live") == "polite"
            page.get_by_role("button", name="Carry this question into the café").click()
            assert "For your visit receipt" in event_question.inner_text()
            page.locator("#leave").click()
            assert "What remains when an instrument goes quiet?" in page.locator("#keepsakeLine").inner_text()
            # Curiosity remains a separate local thought experiment.
            page.locator('[data-mood="curiosity"]').click()
            page.locator("#explore").click()
            # Exercise local-only input and composition, not just mood navigation.
            page.locator("#activity input").fill("A person who listens before speaking")
            page.get_by_role("button", name="Reflect locally").click()
            assert "Your words stay in this browser" in page.locator("#activity").inner_text()
            page.locator('[data-mood="party"]').click()
            page.locator("#explore").click()
            page.get_by_role("button", name="Invent my holiday").click()
            assert "The Day of Lost Socks" in page.locator("#activity").inner_text()
            page.locator("#leave").click()
            assert "The Day of Lost Socks" in page.locator("#keepsakeLine").inner_text()
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
            assert page.locator("#join").get_attribute("aria-expanded") == "true"
            assert page.locator("#dialogueChoices").is_visible()
            assert page.locator("#dialogueInput").evaluate("(el) => document.activeElement === el")
            # Mood switching must discard an unfinished local conversation,
            # remove its temporary controls, and put focus on the new heading.
            page.locator("#join").click()
            page.locator("#dialogueInput").fill("Unfinished private thought")
            page.locator('[data-mood="party"]').click()
            assert page.locator("#dialogueChoices").is_hidden()
            assert page.locator("#join").get_attribute("aria-expanded") == "false"
            assert page.locator("#headline").evaluate("(el) => document.activeElement === el")
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
            # Rebuilding the persistent choices group across turns must not stack Escape handlers.
            page.locator("#join").click()
            page.locator("#dialogueInput").fill("First thought")
            page.get_by_role("button", name="Answer", exact=True).click()
            page.locator("#dialogueInput").fill("Second thought")
            page.get_by_role("button", name="Answer", exact=True).click()
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
            assert not errors, errors
            assert not outbound, outbound
            assert page.evaluate("localStorage.length") == 0
            print(f"PASS exact checkout Chromium: {width}x{height}, six moods, keyboard Escape, dialogue, keepsake, offline")
            context.close()
        browser.close()
    

if __name__ == '__main__':
    main()
