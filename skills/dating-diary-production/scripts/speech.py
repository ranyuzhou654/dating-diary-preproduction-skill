"""Speech-duration estimate shared by the production scripts.

Same rules as dating-diary-preproduction/scripts/check_dialogue_timing.py — keep them in sync.
"""
import re

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
