#!/usr/bin/env python3
"""Exact-checkout, two-context Chromium smoke test for the WIDEN Empty Chair.

This test runs the committed HTML from the checked-out branch as a file:// URL.
It exercises real DOM, real browser layout and independently separated browser
contexts. It does NOT verify people, signatures, or two physical phones.
"""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "prototypes" / "night-cafe-empty-chair-encounter-v2.html"
ARTIFACTS = ROOT / "artifacts"


def make_page(browser, label, width=390):
    ctx = browser.new_context(
        viewport={"width": width, "height": 844},
        is_mobile=width < 600, has_touch=width < 600,
        device_scale_factor=1, reduced_motion="reduce",
        accept_downloads=True,
    )
    page = ctx.new_page()
    errs, requests = [], []
    page.on("pageerror", lambda error: errs.append(str(error)))
    page.on("request", lambda request: requests.append(request.url)
            if not request.url.startswith("file:") else None)
    page.goto(PAGE.as_uri(), wait_until="load")
    assert "Night Café" in page.title()
    return ctx, page, errs, requests


def no_overflow(page, name):
    overflow = page.evaluate("document.documentElement.scrollWidth-window.innerWidth")
    assert overflow <= 2, f"{name}: horizontal overflow {overflow}px"


def export(page):
    return json.loads(page.locator("#outgoing").input_value())


def check(browser, width):
    a_ctx, a, a_err, a_requests = make_page(browser, "A", width)
    b_ctx, b, b_err, b_requests = make_page(browser, "B", width)
    try:
        # A creates a real first contribution, with no simulated guest.
        question = "Who gets heard when anyone can publish?" + (" Q" * 70)
        a.locator("#starter-question").fill(question)
        a.locator("#starter-note").fill("I wonder whether access alone is enough.")
        a.locator("#create-capsule").click()
        assert a.evaluate("document.activeElement.id") == "thread"
        first = export(a)
        assert len(first["contributions"]) == 1
        assert question == first["contributions"][0]["question"]
        assert "unsigned" in first["disclosure"]
        assert "tamper evidence" in first["disclosure"]
        assert a.locator(".paper-sheet").count() == 1
        no_overflow(a, "A one paper")

        # B can inspect without accepting; keyboard focus moves to full preview.
        b.locator("#open-mode").click()
        b.locator("#incoming").fill(json.dumps(first))
        b.locator("#inspect-capsule").click()
        assert b.evaluate("document.activeElement.id") == "import-preview"
        preview = b.locator("#import-preview").inner_text()
        assert question in preview and "no signature or tamper evidence" in preview
        assert b.locator("#decline-capsule").is_visible()
        b.locator("#decline-capsule").click()
        assert not b.locator("#accept-capsule").is_visible()
        assert not b.locator(".paper-sheet").count()
        assert "Import declined" in b.locator("#open-feedback").inner_text()
        no_overflow(b, "B declined import")

        # File-picker flow; B accepts, contributes independent words, re-exports.
        b.locator("#incoming-file").set_input_files({
            "name":"widen-capsule.json", "mimeType":"application/json",
            "buffer":json.dumps(first).encode("utf-8")
        })
        assert b.evaluate("document.activeElement.id") == "import-preview"
        b.locator("#accept-capsule").click()
        assert b.locator(".paper-sheet").count() == 1
        assert b.locator("#continue-panel").is_visible()
        b.locator("#reply-voice").select_option("ai")
        b.locator("#reply-thought").fill("I disagree: publishing is not the same as being discovered.")
        b.locator("#reply-question").fill("What would make a quieter voice discoverable?")
        b.locator("#add-reply").click()
        second = export(b)
        assert len(second["contributions"]) == 2
        assert second["contributions"][0] == first["contributions"][0]
        assert second["contributions"][1]["voice"] == "ai"
        assert second["contributions"][1]["text"].startswith("I disagree")
        assert "editable" in b.locator(".paper-caption").inner_text() or "does not verify" in b.locator(".paper-caption").inner_text()
        assert b.locator(".paper-sheet").count() == 2
        assert b.locator(".paper-sheet-label").nth(1).text_content().strip() == "Most recent contribution · 2"
        assert b.locator(".thread-item").count() == 2
        sheet_font = b.locator(".paper-sheet-words").evaluate_all(
            "els=>els.map(el=>getComputedStyle(el).fontSize)"
        )
        assert sheet_font[0] == sheet_font[1], "papers must have equal type"
        no_overflow(b, "B returned second paper")
        ARTIFACTS.mkdir(exist_ok=True)
        b.screenshot(path=str(ARTIFACTS / f"empty-chair-two-papers-{width}.png"), full_page=True)

        # A can read the returned full history without changing anything.
        a.locator("#open-mode").click()
        a.locator("#incoming").fill(json.dumps(second))
        a.locator("#inspect-capsule").click()
        assert a.evaluate("document.activeElement.id") == "import-preview"
        full = a.locator("#import-preview").inner_text()
        assert "CONTRIBUTION 1" in full and "CONTRIBUTION 2" in full
        assert question in full and "I disagree" in full
        a.locator("#accept-capsule").click()
        a.locator("#read-only").click()
        assert export(a)["contributions"] == second["contributions"]
        # A optionally replies: third sheet must not be mislabelled second.
        a.locator("#reply-thought").fill("That matters. Perhaps discovery is the harder problem.")
        a.locator("#add-reply").click()
        third = export(a)
        assert len(third["contributions"]) == 3
        assert third["contributions"][:2] == second["contributions"]
        assert a.locator(".paper-sheet").count() == 2
        assert a.locator(".paper-sheet-label").nth(1).text_content().strip() == "Most recent contribution · 3"
        assert a.locator(".thread-item").count() == 3
        no_overflow(a, "A three voices")

        # No fake integrity: a forged author and injected text are visibly
        # disclosed as UNVERIFIED, text remains inert, but import still works.
        tampered = json.loads(json.dumps(first))
        tampered["contributions"][0]["by"] = "Tim Berners-Lee"
        tampered["contributions"][0]["question"] = '<img src=x onerror="window.hacked=1">'
        b.locator("#open-mode").click()
        b.locator("#incoming").fill(json.dumps(tampered))
        b.locator("#inspect-capsule").click()
        assert "Tim Berners-Lee" in b.locator("#import-preview").inner_text()
        assert "unverified" in b.locator("#import-preview").inner_text().lower()
        b.locator("#accept-capsule").click()
        assert b.locator(".thread-question").get_by_text("<img", exact=False).count() >= 1
        assert b.locator("img[src=x]").count() == 0
        assert not b.evaluate("Boolean(window.hacked)")
        no_overflow(b, "B tampered input")

        # Malformed JSON must be rejected with a clear failure message.
        b.locator("#open-mode").click()
        b.locator("#incoming").fill("{bad")
        b.locator("#inspect-capsule").click()
        assert "not valid JSON" in b.locator("#open-feedback").inner_text()
        assert not b.locator("#accept-capsule").is_visible()

        # Screenshot + browser/runtime safety boundaries.
        assert not a_err and not b_err, f"JS errors: A={a_err} B={b_err}"
        assert not a_requests and not b_requests, f"Unrequested network: {a_requests+b_requests}"
        assert a.evaluate("localStorage.length") == 0 and b.evaluate("localStorage.length") == 0
        print(f"PASS exact-checkout Chromium {width}px: two-context handoff, file import, pre-accept focus, decline, paper geometry, three turns, tamper disclosure, XSS, overflow, offline")
    finally:
        a_ctx.close()
        b_ctx.close()


if __name__ == "__main__":
    assert PAGE.is_file(), PAGE
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            check(browser, 390)
            check(browser, 1280)
        finally:
            browser.close()
