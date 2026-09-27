#!/usr/bin/env python3
"""Choose one take per segment and write 10_production/selection.json.

Photoreal segments: sample frames from each take and score identity against the
segment's character model sheets (InsightFace, same method as face_check.py); the
take with the highest score wins. Fantasy segments, or when InsightFace is not
installed: the first finished take wins. Takes shorter than the segment's usable
length are ranked last.

This only checks identity and length — not acting or dialogue. Any entry you edit
and mark "locked": true is never overwritten.

  python3 pick_takes.py <project_dir> [--frames 4]
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def probe_seconds(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
                             capture_output=True, text=True, check=True).stdout
        return float(json.loads(out)["format"]["duration"])
    except Exception:  # noqa: BLE001
        return None


def face_app():
    try:
        from insightface.app import FaceAnalysis
    except ImportError:
        return None
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(640, 640))
    return app


def embs(app, img_path):
    import cv2
    img = cv2.imread(img_path)
    return [f.normed_embedding for f in app.get(img)] if img is not None else []


def score_take(app, video, ref_embs, n_frames, length):
    import numpy as np
    best = {c: 0.0 for c in ref_embs}
    with tempfile.TemporaryDirectory() as td:
        for i in range(n_frames):
            t = length * (i + 1) / (n_frames + 1)
            fp = os.path.join(td, f"f{i}.png")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1", fp], check=False)
            if not os.path.exists(fp):
                continue
            for e in embs(app, fp):
                for c, refs in ref_embs.items():
                    if refs:
                        best[c] = max(best[c], max(float(np.dot(e, r)) for r in refs))
    return round(sum(best.values()) / max(len(best), 1), 3), best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--frames", type=int, default=4)
    a = ap.parse_args()
    P = a.project
    segs = load(os.path.join(P, "10_production/segments.json"))
    st = load(os.path.join(P, "10_production/production_state.json"))
    sel_p = os.path.join(P, "10_production/selection.json")
    sel = load(sel_p) if os.path.exists(sel_p) else {}
    app = None
    need_faces = any(s["layer"] == "reality" for s in segs["segments"])
    if need_faces:
        app = face_app()
        if app is None:
            print("InsightFace not installed → first take is used for every segment")

    for seg in segs["segments"]:
        g = seg["id"]
        if sel.get(g, {}).get("locked"):
            print(f"{g}: locked, kept {sel[g]['file']}")
            continue
        takes = [j for j in st["jobs"] if j["segment"] == g and j["status"] == "done" and j["files"]]
        vids = [(j, next((f for f in j["files"] if f.lower().endswith((".mp4", ".mov", ".webm", ".mkv"))), j["files"][0])) for j in takes]
        if not vids:
            print(f"{g}: no finished take")
            continue
        ranked = []
        ref_embs = None
        if app and seg["layer"] == "reality":
            ref_embs = {}
            for p in seg["pictures"]:
                if p["role"].startswith("model sheet"):
                    ref_embs[p["asset_id"]] = embs(app, os.path.join(P, p["path"]))
        for j, f in vids:
            fp = os.path.join(P, f)
            length = probe_seconds(fp) or 0
            short = length + 0.05 < seg["use_seconds"]
            if ref_embs:
                sc, detail = score_take(app, fp, ref_embs, a.frames, length or seg["duration"])
            else:
                sc, detail = None, None
            ranked.append({"file": f, "seed": j["seed"], "seconds": round(length, 2), "too_short": short,
                           "score": sc, "detail": detail})
        ranked.sort(key=lambda r: (r["too_short"], -(r["score"] or 0)))
        best = ranked[0]
        sel[g] = {"file": best["file"], "seed": best["seed"], "in": 0.0, "out": seg["use_seconds"],
                  "method": "face_score" if best["score"] is not None else "first_take",
                  "candidates": ranked, "locked": False}
        flag = "  (all takes shorter than needed!)" if best["too_short"] else ""
        print(f"{g}: {best['file']}  score={best['score']}{flag}")
    with open(sel_p, "w", encoding="utf-8") as f:
        json.dump(sel, f, ensure_ascii=False, indent=2)
    print(f"\n→ {sel_p}  (edit 'file'/'in'/'out' and set \"locked\": true to override)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
