#!/usr/bin/env python3
"""Check every 10_production/prompts/G*.json against its segment before anything is rendered.

  python3 validate_video_prompts.py <project_dir> [--only G1,G3]

Errors (exit 1) — must fix:
  * not valid JSON / missing required keys / summary not starting with "[reference generation]"
  * <Picture n> used that does not exist in the segment's picture list
  * a storyboard dialogue line missing from the <d>…</d> tags
  * timestamps not increasing or beyond the segment Duration
  * non_diegetic_music not "N/A"; "No on-screen text" sentence missing
Warnings — review:
  * a picture attached but never referenced
  * [Shot k] count differs from the number of storyboard shots
  * a must_not_have feature mentioned without a negation
"""
import argparse
import json
import os
import re
import sys

REQ = ["subject_definitions", "summary", "retention_analysis", "detailed_description",
       "overall_soundscape", "non_diegetic_music"]
PIC = re.compile(r"<Picture (\d+)>")
DLG = re.compile(r"<d>\s*\[[A-Za-z]+\]\s*(.*?)</d>", re.S)
TS = re.compile(r"At (\d{2}):(\d{2})\.(\d{3})")
SHOT = re.compile(r"\[Shot (\d+)\]")
NEG = re.compile(r"\b(no|without|never|not)\b[^.]{0,40}$", re.I)


def norm(t):
    return re.sub(r"[\s，。,.!！?？…“”\"'、~～—\-]+", "", t or "").lower()


def check(seg, prompt, blocks):
    errs, warns = [], []
    for k in REQ:
        if k not in prompt:
            errs.append(f"missing key {k}")
    if errs:
        return errs, warns
    if not str(prompt["summary"]).startswith("[reference generation]"):
        errs.append('summary must start with "[reference generation]"')
    if str(prompt["non_diegetic_music"]).strip() != "N/A":
        errs.append('non_diegetic_music must be "N/A" (music is added in the edit)')
    text = json.dumps(prompt, ensure_ascii=False)
    desc = prompt["detailed_description"]
    if "no on-screen text" not in desc.lower():
        errs.append('detailed_description must contain "No on-screen text or subtitles."')

    n_pics = len(seg["pictures"])
    used = {int(x) for x in PIC.findall(text)}
    for n in sorted(used):
        if n < 1 or n > n_pics:
            errs.append(f"<Picture {n}> referenced but segment only has {n_pics} pictures")
    for p in seg["pictures"]:
        if p["n"] not in used:
            warns.append(f"Picture {p['n']} ({p['role']}) is attached but never referenced")

    spoken = [norm(x) for x in DLG.findall(desc)]
    joined = "".join(spoken)
    for sh in seg["shots"]:
        for ln in sh.get("dialogue_lines") or []:
            if norm(ln["text"]) and norm(ln["text"]) not in joined:
                errs.append(f"dialogue of shot {sh['shot_id']} missing from <d> tags: {ln['text']}")

    times = [int(m) * 60 + int(s) + int(ms) / 1000 for m, s, ms in TS.findall(desc)]
    for a, b in zip(times, times[1:]):
        if b <= a:
            errs.append(f"timestamps not increasing ({a:.3f} → {b:.3f})")
    if times and times[-1] >= seg["duration"]:
        errs.append(f"last timestamp {times[-1]:.3f}s is beyond Duration {seg['duration']}s")

    n_shots = len(set(SHOT.findall(desc)))
    if n_shots != len(seg["shots"]):
        warns.append(f"{n_shots} [Shot k] markers for {len(seg['shots'])} storyboard shots (merging adjacent shots is fine if intended)")

    low = desc.lower()
    for c in seg["characters"]:
        for bad in (blocks.get(c) or {}).get("must_not_have", []):
            for m in re.finditer(re.escape(bad.lower()), low):
                if not NEG.search(low[max(0, m.start() - 60):m.start()]):
                    warns.append(f"'{bad}' (must_not_have for {c}) appears without a negation")
                    break
    return errs, warns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--only")
    a = ap.parse_args()
    segs = json.load(open(os.path.join(a.project, "10_production/segments.json"), encoding="utf-8"))
    only = set(a.only.split(",")) if a.only else None
    bad = 0
    for seg in segs["segments"]:
        if only and seg["id"] not in only:
            continue
        pf = os.path.join(a.project, seg["prompt_file"])
        if not os.path.exists(pf):
            print(f"{seg['id']}: ERROR prompt file missing ({seg['prompt_file']})")
            bad += 1
            continue
        try:
            prompt = json.load(open(pf, encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"{seg['id']}: ERROR invalid JSON: {e}")
            bad += 1
            continue
        errs, warns = check(seg, prompt, segs.get("character_blocks", {}))
        print(f"{seg['id']}: {'OK' if not errs else 'ERROR'}")
        for e in errs:
            print(f"   ✗ {e}")
        for w in warns:
            print(f"   ! {w}")
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
