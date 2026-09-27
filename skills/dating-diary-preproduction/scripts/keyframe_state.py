#!/usr/bin/env python3
"""Keyframe generation bookkeeping: which shot is next, how many tries, what failed.

The agent generates images; this script decides what to do next and enforces the
retry cap, so progress survives interrupted sessions.

  init    <project_dir> [--max-attempts 3] [--force]
  next    <project_dir>            -> JSON task for the next shot, or the word DONE
  record  <project_dir> --shot 04 --file 07_keyframes/shot_04_try1.png --status PASS|FAIL
          [--issues "a; b"] [--instruction "..."] [--scores '{"character_consistency": 80}']
  resolve <project_dir> --shot 04 --file <path>   (human picks an image for an exception)
  status  <project_dir>
"""
import argparse
import datetime as dt
import json
import os
import shutil
import sys

STATE = "07_keyframes/keyframe_state.json"
SHOTS = "03_storyboard/shots.json"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def state_path(proj):
    return os.path.join(proj, STATE)


def load_state(proj):
    p = state_path(proj)
    if not os.path.exists(p):
        sys.exit(f"no state file at {p}; run `init` first")
    return load_json(p)


def cmd_init(a):
    p = state_path(a.project)
    if os.path.exists(p) and not a.force:
        print(f"state already exists at {p} (use --force to reset)")
        return 0
    shots = load_json(os.path.join(a.project, SHOTS))
    shots = shots["shots"] if isinstance(shots, dict) else shots
    meta_p = os.path.join(a.project, "00_meta/project.json")
    pid = load_json(meta_p).get("project_id") if os.path.exists(meta_p) else os.path.basename(os.path.abspath(a.project))
    st = {
        "project_id": pid,
        "max_attempts": a.max_attempts,
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "order": [str(s["shot_id"]) for s in shots],
        "shots": {str(s["shot_id"]): {"status": "pending", "layer": s.get("layer"), "attempts": []} for s in shots},
    }
    save_json(p, st)
    print(f"initialised {len(shots)} shots → {p}")
    return 0


def cmd_next(a):
    st = load_state(a.project)
    for sid in st["order"]:
        sh = st["shots"][sid]
        if sh["status"] in ("pending", "fail"):
            n = len(sh["attempts"]) + 1
            last = sh["attempts"][-1] if sh["attempts"] else None
            task = {
                "shot_id": sid,
                "layer": sh.get("layer"),
                "attempt": n,
                "max_attempts": st["max_attempts"],
                "prompt_file": f"05_prompts/shot_{sid}.txt",
                "append_regeneration_instruction": last.get("instruction") if last else None,
                "previous_issues": last.get("issues") if last else [],
                "save_as": f"07_keyframes/shot_{sid}_try{n}.png",
            }
            print(json.dumps(task, ensure_ascii=False, indent=2))
            return 0
    print("DONE")
    return 0


def cmd_record(a):
    st = load_state(a.project)
    sid = str(a.shot)
    if sid not in st["shots"]:
        sys.exit(f"unknown shot {sid}")
    sh = st["shots"][sid]
    if sh["status"] in ("pass", "exception"):
        sys.exit(f"shot {sid} already {sh['status']}; nothing to record")
    fpath = os.path.join(a.project, a.file) if not os.path.isabs(a.file) else a.file
    if not os.path.exists(fpath):
        sys.exit(f"file not found: {fpath} (save the image before recording)")
    status = a.status.upper()
    att = {
        "n": len(sh["attempts"]) + 1,
        "file": os.path.relpath(fpath, a.project),
        "qc": status,
        "issues": [i.strip() for i in (a.issues or "").split(";") if i.strip()],
        "instruction": a.instruction,
        "scores": json.loads(a.scores) if a.scores else None,
        "at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    sh["attempts"].append(att)
    if status == "PASS":
        sh["status"] = "pass"
        final = os.path.join(a.project, f"07_keyframes/shot_{sid}.png")
        shutil.copyfile(fpath, final)
        sh["final"] = os.path.relpath(final, a.project)
        msg = f"shot {sid}: PASS → {sh['final']}"
    elif status == "FAIL":
        if len(sh["attempts"]) >= st["max_attempts"]:
            sh["status"] = "exception"
            msg = f"shot {sid}: FAIL on attempt {att['n']}/{st['max_attempts']} → EXCEPTION, moving on"
        else:
            sh["status"] = "fail"
            msg = f"shot {sid}: FAIL on attempt {att['n']}/{st['max_attempts']} → will retry"
    else:
        sys.exit("--status must be PASS or FAIL")
    save_json(state_path(a.project), st)
    print(msg)
    return 0


def cmd_resolve(a):
    st = load_state(a.project)
    sh = st["shots"][str(a.shot)]
    src = os.path.join(a.project, a.file) if not os.path.isabs(a.file) else a.file
    final = os.path.join(a.project, f"07_keyframes/shot_{a.shot}.png")
    shutil.copyfile(src, final)
    sh.update(status="pass", final=os.path.relpath(final, a.project), resolved_by="human")
    save_json(state_path(a.project), st)
    print(f"shot {a.shot}: resolved by human → {sh['final']}")
    return 0


def cmd_status(a):
    st = load_state(a.project)
    counts = {}
    for sid in st["order"]:
        sh = st["shots"][sid]
        counts[sh["status"]] = counts.get(sh["status"], 0) + 1
        last = sh["attempts"][-1] if sh["attempts"] else {}
        issues = "; ".join(last.get("issues") or [])
        print(f"{sid:<5}{sh['status']:<10}tries={len(sh['attempts'])}  {issues}")
    print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    exc = [s for s in st["order"] if st["shots"][s]["status"] == "exception"]
    if exc:
        print("exceptions (need a human later): " + ", ".join(exc))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("project"); p.add_argument("--max-attempts", type=int, default=3); p.add_argument("--force", action="store_true")
    p = sub.add_parser("next"); p.add_argument("project")
    p = sub.add_parser("record"); p.add_argument("project"); p.add_argument("--shot", required=True); p.add_argument("--file", required=True)
    p.add_argument("--status", required=True); p.add_argument("--issues"); p.add_argument("--instruction"); p.add_argument("--scores")
    p = sub.add_parser("resolve"); p.add_argument("project"); p.add_argument("--shot", required=True); p.add_argument("--file", required=True)
    p = sub.add_parser("status"); p.add_argument("project")
    a = ap.parse_args()
    return {"init": cmd_init, "next": cmd_next, "record": cmd_record, "resolve": cmd_resolve, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
