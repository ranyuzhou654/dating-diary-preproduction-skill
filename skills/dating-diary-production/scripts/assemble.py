#!/usr/bin/env python3
"""Build a rough cut from the selected takes: trim, normalise, hard-cut concat.

  python3 assemble.py <project_dir> [--width 1080 --height 1920 --fps 24]

Reads 10_production/segments.json and 10_production/selection.json (from pick_takes.py).
Each take is trimmed to [in, out] (default 0 → the segment's usable seconds), scaled/padded
to the target size, re-encoded (H.264 + AAC 48 kHz stereo; silent audio added if a take has
none), then joined with hard cuts. Output: 12_rough_cut/rough_cut.mp4.

This is a timing check for the edit, not the final master: music, subtitles, the voice
pass and fine trims happen in the editor (see references/post-production.md).
"""
import argparse
import json
import os
import subprocess
import sys


def has_audio(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip()
    return bool(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1920)
    ap.add_argument("--fps", type=int, default=24)
    a = ap.parse_args()
    P = a.project
    segs = json.load(open(os.path.join(P, "10_production/segments.json"), encoding="utf-8"))["segments"]
    sel = json.load(open(os.path.join(P, "10_production/selection.json"), encoding="utf-8"))
    work = os.path.join(P, "12_rough_cut/parts")
    os.makedirs(work, exist_ok=True)
    vf = (f"scale={a.width}:{a.height}:force_original_aspect_ratio=decrease,"
          f"pad={a.width}:{a.height}:(ow-iw)/2:(oh-ih)/2,fps={a.fps},format=yuv420p")
    parts = []
    for seg in segs:
        g = seg["id"]
        if g not in sel:
            sys.exit(f"{g}: no take selected — run pick_takes.py first")
        s = sel[g]
        src = os.path.join(P, s["file"])
        t_in, t_out = float(s.get("in", 0)), float(s.get("out", seg["use_seconds"]))
        dur = max(0.1, t_out - t_in)
        out = os.path.join(work, f"{g}.mp4")
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{t_in:.3f}", "-t", f"{dur:.3f}", "-i", src]
        if not has_audio(src):
            cmd += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v", "-map", "1:a"]
        cmd += ["-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", "-shortest", out]
        subprocess.run(cmd, check=True)
        parts.append(out)
        print(f"{g}: {s['file']} [{t_in:.2f}–{t_out:.2f}s]")
    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for p in parts)
    final = os.path.join(P, "12_rough_cut/rough_cut.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", final], check=True)
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", final],
                         capture_output=True, text=True).stdout.strip()
    print(f"\nrough cut → {final} ({float(dur):.1f}s)")

    # production manifest: everything downstream (editor, voice pass) needs in one place
    st_p = os.path.join(P, "10_production/production_state.json")
    jobs = json.load(open(st_p, encoding="utf-8"))["jobs"] if os.path.exists(st_p) else []
    man = {
        "rough_cut": "12_rough_cut/rough_cut.mp4",
        "rough_cut_seconds": round(float(dur), 2),
        "segments": [{
            "id": seg["id"], "layer": seg["layer"], "shot_ids": seg["shot_ids"],
            "duration": seg["duration"], "use_seconds": seg["use_seconds"],
            "prompt_file": seg["prompt_file"], "pictures": seg["pictures"],
            "takes": [{"seed": j["seed"], "status": j["status"], "files": j["files"], "error": j.get("error")}
                      for j in jobs if j["segment"] == seg["id"]],
            "selected": sel.get(seg["id"]),
            "warnings": seg.get("warnings", []),
        } for seg in segs],
    }
    with open(os.path.join(P, "10_production/production_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    print("production manifest → 10_production/production_manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
