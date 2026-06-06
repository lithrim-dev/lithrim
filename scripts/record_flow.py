"""Record a live :5180 conversational flow to an mp4 (reuses zyng's Playwright
record_video pattern — see ../zyng/zyng/record.py + ../zyng/out_lithrim_demo/capture_journey.py).

Records the ONBOARDING TEACHING ARC: a total-novice "teach me from zero" message
driven through the real conversational shell (BYO-Claude, $0 API). The view is pinned
to the bottom while the response streams in (so you watch it appear), then it jumps to
the novice question and slowly pans the whole teaching arc.

Run with zyng's venv (it has playwright 1.60 + chromium installed):

    /Users/aregee/Workspace/github.com/zyng/.venv/bin/python \
        /Users/aregee/Workspace/github.com/lithrim-bench/scripts/record_flow.py

Prereqs: the shell on :5180 + the BFF on :8787 (with the claude CLI authed) must be up.
Output: lithrim-bench/out/onboarding_journey_live.mp4 (+ the raw .webm alongside).
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://localhost:5180/"
OUT = Path("/Users/aregee/Workspace/github.com/lithrim-bench/out")
VIDDIR = OUT / "rec_tmp"
W, H = 1440, 900

MSG = (
    "I'm completely new — I don't know anything about AI evaluation OR healthcare. "
    "In plain language, teach me what Lithrim is and what an 'eval', a 'judge', a "
    "'flag', and 'grounding' mean. Use the ws0_default clinical-scribe agent as a "
    "concrete example: read its real config and run a $0 replay so I see a real result, "
    "and build up to the key insight — the moment an AI judge is confidently WRONG and a "
    "deterministic check overrides it. Define every term before you use it, keep it "
    "concrete, and don't invent features Lithrim doesn't actually have. Walk me through "
    "it step by step."
)

# JS: the biggest scrollable element = the conversation pane.
_PANE = """() => {
  const els=[...document.querySelectorAll('*')]
    .filter(e=>e.scrollHeight>e.clientHeight+50 && e.clientHeight>200);
  els.sort((a,b)=>b.scrollHeight-a.scrollHeight);
  return els[0] || null;
}"""


def to_bottom(page):
    page.evaluate("() => { const e=(%s)(); if(e) e.scrollTop=e.scrollHeight; }" % _PANE)


def pin_bottom_until_settle(page, quiet_ms=4500, max_ms=150000):
    """Keep the conversation scrolled to the bottom while the response streams in;
    return once the page text has been stable for quiet_ms."""
    start, last_len, stable_since = time.time(), -1, None
    while (time.time() - start) * 1000 < max_ms:
        to_bottom(page)
        cur = page.evaluate("document.body.innerText.length")
        if cur == last_len:
            if stable_since is None:
                stable_since = time.time()
            elif (time.time() - stable_since) * 1000 >= quiet_ms:
                return True
        else:
            last_len, stable_since = cur, None
        page.wait_for_timeout(1000)
    return False


def read_through(page, steps=44, dy=360, dwell_ms=820):
    """Jump to the novice question, then pan DOWN through the teaching response."""
    for probe in ("I don't know anything about AI evaluation", "I'm completely new"):
        try:
            page.get_by_text(probe, exact=False).first.scroll_into_view_if_needed(timeout=4000)
            break
        except Exception:
            continue
    page.wait_for_timeout(1400)
    for _ in range(steps):
        page.evaluate("(dy) => { const e=(%s)(); if(e) e.scrollTop += dy; }" % _PANE, dy)
        page.wait_for_timeout(dwell_ms)
        at_bottom = page.evaluate(
            "() => { const e=(%s)(); return e ? (e.scrollTop + e.clientHeight >= e.scrollHeight - 4) : true; }" % _PANE
        )
        if at_bottom:
            break


def main():
    VIDDIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=str(VIDDIR),
            record_video_size={"width": W, "height": H},
        )
        page = ctx.new_page()
        print("load :5180")
        page.goto(URL, wait_until="load")
        page.wait_for_timeout(1800)

        for sel in ('button:has-text("Shell")', 'text="Shell"'):
            try:
                page.click(sel, timeout=4000)
                break
            except Exception:
                continue
        page.wait_for_timeout(1000)
        to_bottom(page)          # past the scripted seed, to the chat input
        page.wait_for_timeout(800)

        chat = page.get_by_placeholder("Ask Lithrim", exact=False)
        chat.click()
        chat.fill(MSG)
        page.wait_for_timeout(700)
        page.keyboard.press("Meta+Enter")
        print("sent; pinning to bottom while the teaching arc streams in…")
        page.wait_for_timeout(2000)
        ok = pin_bottom_until_settle(page)
        print(f"stream settled={ok}")
        page.wait_for_timeout(1500)

        print("read-through pan of the teaching arc…")
        read_through(page)
        page.wait_for_timeout(1500)

        video_path = page.video.path()
        ctx.close()
        browser.close()

    webm = Path(video_path)
    mp4 = OUT / "onboarding_journey_live.mp4"
    print(f"webm -> {webm} ({webm.stat().st_size//1024} KB)")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(webm), "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(mp4)],
        check=True,
    )
    print(f"\nVIDEO READY: {mp4} ({mp4.stat().st_size//1024} KB)")


if __name__ == "__main__":
    main()
