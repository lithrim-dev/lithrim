"""Narrated recording of the LIVE onboarding teaching flow on :5180.

Reuses zyng's proven narration pipeline (../zyng/out_lithrim_demo/build_bench_demo.py):
  1. synth each narration beat via ElevenLabs  -> out/narration/<id>.mp3 (cached)
  2. drive :5180 LIVE (BYO-Claude), pacing each visual beat to its narration duration,
     capturing wall-clock offsets (so A/V stays synced despite variable agent latency)
  3. transcode the recording to a silent mp4
  4. adelay each beat to its captured offset + amix + mux -> the narrated mp4

Narration = the monitor's own description of what's happening on screen (descriptive,
thesis-forward), authored below in BEATS.

Run with zyng's venv (has playwright 1.60 + zyng's deps + the EL key in zyng/.env):
    /Users/aregee/Workspace/github.com/zyng/.venv/bin/python \
        /Users/aregee/Workspace/github.com/lithrim-bench/scripts/build_onboarding_narrated.py [--resynth]

Prereqs: shell :5180 + BFF :8787 (claude CLI authed) up. EL synth spends a few cents.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ZYNG = Path("/Users/aregee/Workspace/github.com/zyng")
sys.path.insert(0, str(ZYNG))

# Load the EL key from zyng/.env WITHOUT printing it.
import os
_envf = ZYNG / ".env"
if _envf.exists():
    for line in _envf.read_text().splitlines():
        line = line.strip()
        if line.startswith("ELEVENLABS_API_KEY=") and "ELEVENLABS_API_KEY" not in os.environ:
            os.environ["ELEVENLABS_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")

from playwright.sync_api import sync_playwright  # noqa: E402
from zyng.audio import probe_duration            # noqa: E402
from zyng.tts import get_provider                # noqa: E402

OUT = Path("/Users/aregee/Workspace/github.com/lithrim-bench/out")
NARR = OUT / "narration"
TMP = OUT / "_narr_tmp"
SILENT = OUT / "onboarding_silent.mp4"
FINAL = OUT / "onboarding_narrated.mp4"
META = OUT / "onboarding_narration_meta.json"
URL = "http://localhost:5180/"
VIEWPORT = {"width": 1440, "height": 900}
PRE_ROLL_S = 0.5
TAIL_S = 0.7

MSG = (
    "I'm completely new — I don't know anything about AI evaluation OR healthcare. "
    "In plain language, teach me what Lithrim is and what an 'eval', a 'judge', a 'flag', "
    "and 'grounding' mean. Use the ws0_default clinical-scribe agent as a concrete example: "
    "read its real config and run a $0 replay so I see a real result, and build up to the "
    "key insight — the moment an AI judge is confidently WRONG and a deterministic check "
    "overrides it. Define every term before you use it, keep it concrete, and don't invent "
    "features Lithrim doesn't actually have. Walk me through it step by step."
)

# ── Narration beats — the monitor narrating what's happening on screen. ──
BEATS = [
    {"id": "intro",
     "text": "This is Lithrim. Watch what happens when someone who's never heard of AI "
             "evaluation simply talks to it."},
    {"id": "ask",
     "text": "They ask in plain English — I don't know anything about evals or healthcare, "
             "teach me. No setup, no jargon."},
    {"id": "teaching",
     "text": "Lithrim answers by doing. It reads a real agent — a clinical scribe — and shows "
             "the actual judges grading it: a small panel of AI reviewers, each one watching "
             "for a specific kind of mistake, called a flag."},
    {"id": "verdict",
     "text": "Then it runs a real evaluation and returns a verdict — reject. But here's the "
             "idea the whole system is built on. When a confident judge gets it wrong, a "
             "deterministic check, grounded in the source, overrules it. That's what makes "
             "the verdict trustworthy."},
    {"id": "close",
     "text": "From I know nothing, to understanding evals, judges, flags, and grounding — "
             "just by having a conversation. That's the onboarding."},
]

_PANE = """() => {
  const els=[...document.querySelectorAll('*')]
    .filter(e=>e.scrollHeight>e.clientHeight+50 && e.clientHeight>200);
  els.sort((a,b)=>b.scrollHeight-a.scrollHeight);
  return els[0] || null;
}"""


def synth_narration(resynth: bool) -> dict[str, float]:
    NARR.mkdir(parents=True, exist_ok=True)
    print("=== 1/4 synth narration (ElevenLabs) ===")
    durs, prov = {}, None
    for b in BEATS:
        out = NARR / f"{b['id']}.mp3"
        if resynth or not out.exists():
            if prov is None:
                prov = get_provider("elevenlabs", voice="narrator", pronunciation="none")
            if not prov.synth(b["text"], out):
                raise RuntimeError(f"TTS failed on beat {b['id']}")
        durs[b["id"]] = round(probe_duration(out), 3)
        print(f"  {b['id']:<10} {durs[b['id']]:>5.1f}s")
    return durs


def record(durs: dict[str, float], headless: bool) -> tuple[str, dict[str, float]]:
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    offsets: dict[str, float] = {}
    print("\n=== 2/4 + 3/4 record :5180 LIVE conversational flow ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=["--mute-audio"])
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=1,
                                  record_video_dir=str(TMP), record_video_size=VIEWPORT)
        page = ctx.new_page()
        rec_start = time.monotonic()
        page.goto(URL, wait_until="load")
        page.wait_for_timeout(1800)

        def mark(bid):
            offsets[bid] = round(time.monotonic() - rec_start, 3)
            print(f"  beat {bid:<10} @ {offsets[bid]:>6.2f}s")

        def hold(bid, tail=TAIL_S):
            page.wait_for_timeout(int((durs[bid] + tail) * 1000))

        def to_bottom():
            page.evaluate("() => { const e=(%s)(); if(e) e.scrollTop=e.scrollHeight; }" % _PANE)

        def pan_during(bid, tail=TAIL_S, dy=300):
            total_ms = int((durs[bid] + tail) * 1000)
            steps = max(1, total_ms // 700)
            for _ in range(steps):
                page.evaluate("(dy)=>{const e=(%s)(); if(e) e.scrollTop+=dy;}" % _PANE, dy)
                page.wait_for_timeout(700)

        def settle(quiet_ms=4000, max_ms=150000):
            start, last, since = time.monotonic(), -1, None
            while (time.monotonic() - start) * 1000 < max_ms:
                to_bottom()
                cur = page.evaluate("document.body.innerText.length")
                if cur == last:
                    if since is None:
                        since = time.monotonic()
                    elif (time.monotonic() - since) * 1000 >= quiet_ms:
                        return
                else:
                    last, since = cur, None
                page.wait_for_timeout(1000)

        # Shell mode + past the scripted seed
        for sel in ('button:has-text("Shell")', 'text="Shell"'):
            try:
                page.click(sel, timeout=4000); break
            except Exception:
                continue
        page.wait_for_timeout(1000)
        to_bottom(); page.wait_for_timeout(600)

        mark("intro"); hold("intro")          # the shell, before anything

        chat = page.get_by_placeholder("Ask Lithrim", exact=False)
        chat.click(); chat.fill(MSG); page.wait_for_timeout(500)
        page.keyboard.press("Meta+Enter")
        mark("ask")
        # narrate the question while the response streams in at the bottom
        t_ask = time.monotonic()
        while (time.monotonic() - t_ask) < (durs["ask"] + TAIL_S):
            to_bottom(); page.wait_for_timeout(600)
        settle()                                # finish the (variable) stream — silent

        # jump to the novice question, then pan the teaching arc while narrating
        for probe in ("I don't know anything about AI evaluation", "I'm completely new"):
            try:
                page.get_by_text(probe, exact=False).first.scroll_into_view_if_needed(timeout=4000); break
            except Exception:
                continue
        page.wait_for_timeout(900)
        mark("teaching"); pan_during("teaching")

        # the verdict / aha card
        for probe in ("Sample verdict", "REJECT", "verdict"):
            try:
                page.get_by_text(probe, exact=False).first.scroll_into_view_if_needed(timeout=3000); break
            except Exception:
                continue
        page.wait_for_timeout(700)
        mark("verdict"); hold("verdict")

        mark("close"); hold("close", tail=1.3)

        video_path = page.video.path()
        ctx.close(); browser.close()
    return video_path, offsets


def transcode_silent(webm: str):
    print("\n=== 4/4 transcode silent + voice merge ===")
    r = subprocess.run(["ffmpeg", "-y", "-i", webm, "-c:v", "libx264", "-preset", "slow",
                        "-crf", "18", "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart",
                        str(SILENT)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"silent transcode failed:\n{r.stderr[-600:]}")
    print(f"  silent -> {SILENT.name}")


def merge_voice(durs, offsets) -> float:
    trim = max(0.0, offsets["intro"] - PRE_ROLL_S)
    audio_inputs = []
    for b in BEATS:
        audio_inputs += ["-i", str(NARR / f"{b['id']}.mp3")]
    parts, labels = [], []
    for i, b in enumerate(BEATS):
        off_ms = max(0, int(round((offsets[b["id"]] - trim) * 1000)))
        parts.append(f"[{i + 1}:a]adelay={off_ms}|{off_ms}[a{i}]")
        labels.append(f"[a{i}]")
    fc = ";".join(parts) + ";" + "".join(labels) + f"amix=inputs={len(BEATS)}:normalize=0[outa]"
    r = subprocess.run(["ffmpeg", "-y", "-ss", f"{trim:.3f}", "-i", str(SILENT), *audio_inputs,
                        "-filter_complex", fc, "-map", "0:v", "-map", "[outa]",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(FINAL)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"voice merge failed:\n{r.stderr[-800:]}")
    print(f"  final  -> {FINAL.name}")
    return trim


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resynth", action="store_true")
    ap.add_argument("--headed", dest="headless", action="store_false", default=True)
    args = ap.parse_args()
    durs = synth_narration(args.resynth)
    webm, offsets = record(durs, args.headless)
    transcode_silent(webm)
    trim = merge_voice(durs, offsets)
    shutil.rmtree(TMP, ignore_errors=True)
    META.write_text(json.dumps({
        "source": URL, "mode": "LIVE BYO-Claude conversational onboarding",
        "viewport": VIEWPORT, "trim_s": round(trim, 3), "pre_roll_s": PRE_ROLL_S,
        "beats": [{"id": b["id"], "offset_s": round(offsets[b["id"]] - trim, 3),
                   "dur_s": durs[b["id"]], "text": b["text"]} for b in BEATS],
    }, indent=2) + "\n")
    print(f"  meta   -> {META.name}\n=== DONE: {FINAL} ===")


if __name__ == "__main__":
    main()
