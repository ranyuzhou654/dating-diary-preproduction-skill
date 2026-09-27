#!/usr/bin/env python3
"""Estimate how long dialogue takes to say, and flag shots/scripts that are too short.

Usage:
  python3 check_dialogue_timing.py 02_script/script.json
  python3 check_dialogue_timing.py 03_storyboard/shots.json [--write]

Accepted inputs:
  * script.json: {"claimed_duration": 11.5, "lines": [{"speaker": "...", "text": "..."}]}
  * shots.json:  [ {shot}, ... ]  or  {"shots": [ ... ]}
    each shot may carry "dialogue_lines" (preferred) or "dialogue" (plain string),
    and "duration_hint".

--write  stores est_speech_seconds back into each shot (shots mode only).
Exit code 0 = all OK, 1 = at least one FAIL, 2 = bad input.
"""
import argparse
import json
import re
import sys

ZH_CHARS_PER_SEC = 4.5
EN_WORDS_PER_SEC = 2.5
SPEAKER_SWITCH_PAUSE = 0.3
ELLIPSIS_PAUSE = 0.3
MIN_LINE_SECONDS = 0.6

CJK = re.compile(r"[㐀-鿿豈-﫿]")
LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")
ELLIPSIS = re.compile(r"……|\.\.\.|…")


def line_seconds(text: str) -> float:
    text = text or ""
    zh = len(CJK.findall(text))
    en = len(LATIN_WORD.findall(text))
    if zh == 0 and en == 0:
        return 0.0
    secs = zh / ZH_CHARS_PER_SEC + en / EN_WORDS_PER_SEC
    secs += ELLIPSIS_PAUSE * len(ELLIPSIS.findall(text))
    return round(max(secs, MIN_LINE_SECONDS), 2)


def lines_seconds(lines) -> float:
    total, prev = 0.0, None
    for ln in lines:
        s = line_seconds(ln.get("text", ""))
        if s == 0:
            continue
        if prev is not None and ln.get("speaker") != prev:
            total += SPEAKER_SWITCH_PAUSE
        total += s
        prev = ln.get("speaker")
    return round(total, 2)


def shot_lines(shot):
    if shot.get("dialogue_lines"):
        return shot["dialogue_lines"]
    d = shot.get("dialogue") or ""
    if not d or d.strip() in ("无", "N/A", "none"):
        return []
    # "男主：xxx\n女主：yyy" style
    out = []
    for part in re.split(r"\n+", d.strip()):
        m = re.match(r"^\s*([^:：]{1,12})[:：]\s*(.+)$", part)
        out.append({"speaker": m.group(1) if m else None, "text": (m.group(2) if m else part).strip("“”\"")})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    try:
        data = json.load(open(a.path, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: cannot read {a.path}: {e}")
        return 2

    shots = data if isinstance(data, list) else data.get("shots") if isinstance(data, dict) else None
    ok = True
    if shots is not None:
        total_need = total_hint = 0.0
        print(f"{'shot':<6}{'hint':>7}{'need':>7}  result")
        for sh in shots:
            need = lines_seconds(shot_lines(sh))
            hint = float(sh.get("duration_hint") or 0)
            total_need += max(need, hint)
            total_hint += hint
            res = "OK" if hint >= need else f"FAIL (+{need - hint:.1f}s)"
            ok &= hint >= need
            print(f"{sh.get('shot_id', '?'):<6}{hint:>7.1f}{need:>7.1f}  {res}")
            if a.write:
                sh["est_speech_seconds"] = need
        print(f"\nsum of duration_hint: {total_hint:.1f}s | minimum needed: {total_need:.1f}s")
        if a.write:
            json.dump(data, open(a.path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print(f"est_speech_seconds written to {a.path}")
    elif isinstance(data, dict) and ("lines" in data or "dialogue_lines" in data):
        lines = data.get("lines") or data.get("dialogue_lines")
        need = lines_seconds(lines)
        claimed = data.get("claimed_duration") or data.get("total_duration")
        for ln in lines:
            print(f"{line_seconds(ln.get('text', '')):>5.1f}s  {ln.get('speaker')}: {ln.get('text')}")
        print(f"\ndialogue alone needs ≈ {need:.1f}s (pauses between speakers included; action beats not included)")
        if claimed is not None:
            ok = float(claimed) >= need
            print(f"script claims {float(claimed):.1f}s → {'OK' if ok else 'FAIL: too short for its dialogue'}")
    else:
        print("ERROR: unrecognised format (need shots list, {shots:[...]}, or {lines:[...]})")
        return 2
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
