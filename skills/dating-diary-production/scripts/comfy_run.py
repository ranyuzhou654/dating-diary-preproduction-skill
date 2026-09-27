#!/usr/bin/env python3
"""Drive a remote ComfyUI (MiniMax H3 reference-to-video workflow) from segments.json.

No third-party dependencies (standard library only).

  python3 comfy_run.py check    <project_dir> --config comfy.json
  python3 comfy_run.py inspect  --config comfy.json [--write]      # find node ids in the API workflow
  python3 comfy_run.py submit   <project_dir> --config comfy.json [--only G1,G3] [--takes 3] [--force]
  python3 comfy_run.py wait     <project_dir> --config comfy.json   # poll, download, record
  python3 comfy_run.py run      <project_dir> --config comfy.json [--only ...] [--takes N]   # submit + wait
  python3 comfy_run.py status   <project_dir>

State lives in <project_dir>/10_production/production_state.json, so an interrupted
run can be resumed with `wait` (jobs already queued) or `run` (skips finished takes).
Renders are downloaded to <project_dir>/11_renders/<G>/ as soon as each job finishes,
because files on a rented GPU box disappear when the instance is released.
"""
import argparse
import copy
import datetime as dt
import json
import mimetypes
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

STATE = "10_production/production_state.json"
SEGMENTS = "10_production/segments.json"


# ---------------------------------------------------------------- config / io
def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def load_config(path):
    cfg = load(path)
    cfg["base_url"] = os.environ.get("COMFY_URL", cfg.get("base_url", "")).rstrip("/")
    if not cfg["base_url"]:
        sys.exit("base_url missing: set it in the config or the COMFY_URL environment variable")
    cfg["_dir"] = os.path.dirname(os.path.abspath(path))
    return cfg


def cfg_path(cfg, p):
    return p if os.path.isabs(p) else os.path.join(cfg["_dir"], p)


def auth_headers(cfg):
    a = cfg.get("auth") or {}
    if not a:
        return {}
    token = os.environ.get(a.get("env", "COMFY_TOKEN"), "")
    if not token:
        sys.exit(f"auth configured but environment variable {a.get('env', 'COMFY_TOKEN')} is empty")
    return {a.get("header", "Authorization"): a.get("prefix", "Bearer ") + token}


def http(cfg, method, path, body=None, headers=None, raw=False, timeout=60):
    url = cfg["base_url"] + path
    h = {**auth_headers(cfg), **(headers or {})}
    if body is not None and not isinstance(body, (bytes, bytearray)):
        body = json.dumps(body).encode()
        h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:2000]
        raise RuntimeError(f"{method} {path} → HTTP {e.code}: {detail}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"{method} {path} → cannot reach {cfg['base_url']}: {e.reason}") from None
    return data if raw else json.loads(data or b"{}")


def upload_image(cfg, local_path, subfolder, remote_name=None):
    """remote_name must be unique per episode: many assets share basenames (model_sheet.png)."""
    boundary = uuid.uuid4().hex
    name = remote_name or os.path.basename(local_path)
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    with open(local_path, "rb") as f:
        content = f.read()
    parts = []
    for k, v in (("overwrite", "true"), ("type", "input"), ("subfolder", subfolder)):
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\n'
                 f"Content-Type: {ctype}\r\n\r\n".encode() + content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    res = http(cfg, "POST", "/upload/image", b"".join(parts),
               {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    sub = res.get("subfolder") or ""
    return f"{sub}/{res['name']}" if sub else res["name"]


# ---------------------------------------------------------------- workflow mapping
def discover(wf, ref_prefix="ref_image_"):
    """Best-effort guess of which node does what in an API-format workflow."""
    m = {}
    for nid, n in wf.items():
        ct = n.get("class_type", "")
        title = (n.get("_meta") or {}).get("title", "")
        ins = n.get("inputs", {})
        if any(k.startswith(ref_prefix) for k in ins) and "conditioning" not in m:
            m["conditioning"] = nid
        if (ct == "CR Prompt Text" or "prompt" in title.lower()) and isinstance(ins.get("prompt"), str):
            m.setdefault("prompt", nid)
        if "duration" in title.lower() and isinstance(ins.get("value"), (int, float)):
            m.setdefault("duration", nid)
        if ct in ("RandomNoise",) or ("noise_seed" in ins and not isinstance(ins["noise_seed"], list)):
            m.setdefault("noise", nid)
        if "filename_prefix" in ins and ct not in ("PreviewImage",):
            m.setdefault("save", nid)
    return m


def describe(wf):
    rows = []
    for nid, n in sorted(wf.items(), key=lambda kv: (len(kv[0]), kv[0])):
        title = (n.get("_meta") or {}).get("title", "")
        scalars = {k: v for k, v in n.get("inputs", {}).items() if not isinstance(v, list)}
        short = ", ".join(f"{k}={str(v)[:30]!s}" for k, v in list(scalars.items())[:4])
        rows.append(f"#{nid:<6}{n.get('class_type', ''):<36}{title[:28]:<30}{short}")
    return "\n".join(rows)


def mapping(cfg, wf):
    auto = discover(wf, cfg.get("ref_input_prefix", "ref_image_"))
    m = {**auto, **{k: v for k, v in (cfg.get("nodes") or {}).items() if v}}
    missing = [k for k in ("conditioning", "prompt", "duration", "noise", "save") if not m.get(k)]
    if missing:
        sys.exit(f"cannot find node(s) {missing} in the workflow; run `inspect` and set them under \"nodes\" in the config")
    for k, nid in m.items():
        if nid not in wf:
            sys.exit(f'config nodes.{k} = "{nid}" does not exist in the workflow')
    return m


def patch(cfg, wf, m, prompt_text, duration, seed, ref_names, prefix):
    wf = copy.deepcopy(wf)
    inp = cfg.get("inputs") or {}
    wf[m["prompt"]]["inputs"][inp.get("prompt", "prompt")] = prompt_text
    wf[m["duration"]]["inputs"][inp.get("duration", "value")] = duration
    wf[m["noise"]]["inputs"][inp.get("seed", "noise_seed")] = seed
    wf[m["save"]]["inputs"][inp.get("save_prefix", "filename_prefix")] = prefix

    cond = wf[m["conditioning"]]["inputs"]
    pre = cfg.get("ref_input_prefix", "ref_image_")
    old_sources = [v[0] for k, v in list(cond.items()) if k.startswith(pre) and isinstance(v, list)]
    for k in [k for k in cond if k.startswith(pre)]:
        del cond[k]
    for src in set(old_sources):   # drop old LoadImage nodes no longer used by anything
        still_used = any(isinstance(v, list) and v and v[0] == src
                         for n in wf.values() for v in n.get("inputs", {}).values())
        if not still_used and wf.get(src, {}).get("class_type") == "LoadImage":
            del wf[src]
    for i, name in enumerate(ref_names):
        nid = str(90000 + i)
        wf[nid] = {"class_type": "LoadImage", "inputs": {"image": name, "upload": "image"},
                   "_meta": {"title": f"dd ref {i + 1}"}}
        cond[f"{pre}{i}"] = [nid, 0]
    return wf


# ---------------------------------------------------------------- commands
def paths(proj):
    return os.path.join(proj, SEGMENTS), os.path.join(proj, STATE)


def load_state(proj):
    p = paths(proj)[1]
    return load(p) if os.path.exists(p) else {"jobs": [], "uploads": {}}


def cmd_inspect(a):
    cfg = load_config(a.config)
    wf = load(cfg_path(cfg, cfg["workflow_api"]))
    print(describe(wf))
    auto = discover(wf, cfg.get("ref_input_prefix", "ref_image_"))
    print("\nsuggested nodes:", json.dumps(auto, indent=2))
    if a.write:
        raw = load(a.config)
        raw["nodes"] = {**auto, **{k: v for k, v in (raw.get("nodes") or {}).items() if v}}
        save(a.config, raw)
        print(f"written to {a.config} — check them against the node numbers you see in ComfyUI")
    return 0


def cmd_check(a):
    cfg = load_config(a.config)
    stats = http(cfg, "GET", "/system_stats")
    dev = (stats.get("devices") or [{}])[0]
    print(f"ComfyUI reachable at {cfg['base_url']}  | device: {dev.get('name', '?')}  "
          f"VRAM free: {round((dev.get('vram_free') or 0) / 2**30, 1)} GB")
    wf = load(cfg_path(cfg, cfg["workflow_api"]))
    m = mapping(cfg, wf)
    print("node mapping:", m)
    ct = wf[m["conditioning"]]["class_type"]
    info = http(cfg, "GET", "/object_info/" + urllib.parse.quote(ct)).get(ct, {})
    pre = cfg.get("ref_input_prefix", "ref_image_")
    decl = {**(info.get("input", {}).get("required") or {}), **(info.get("input", {}).get("optional") or {})}
    slots = sorted(k for k in decl if k.startswith(pre))
    print(f"{ct} declares {len(slots)} reference inputs: {', '.join(slots) or '(none found)'}")
    seg_p = paths(a.project)[0] if a.project else None
    if seg_p and os.path.exists(seg_p):
        need = max(len(s["pictures"]) for s in load(seg_p)["segments"])
        if slots and need > len(slots):
            print(f"WARNING: a segment needs {need} references but the node declares {len(slots)}. "
                  f"If the node grows inputs dynamically this may still work; otherwise rebuild segments with "
                  f"--max-refs {len(slots)}.")
        else:
            print(f"largest segment needs {need} references — OK")
    return 0


def cmd_submit(a, cfg=None):
    cfg = cfg or load_config(a.config)
    seg_p, st_p = paths(a.project)
    segs = load(seg_p)
    wf = load(cfg_path(cfg, cfg["workflow_api"]))
    m = mapping(cfg, wf)
    st = load_state(a.project)
    takes = a.takes or cfg.get("takes_per_segment", 3)
    only = set(a.only.split(",")) if a.only else None
    ep = segs.get("episode") or segs.get("project_id") or "episode"
    sub = f"dating_diary/{ep}"
    queued = 0
    for seg in segs["segments"]:
        if only and seg["id"] not in only:
            continue
        pf = os.path.join(a.project, seg["prompt_file"])
        if not os.path.exists(pf):
            print(f"{seg['id']}: prompt file missing, skipped (write it and run validate_video_prompts.py first)")
            continue
        prompt_text = json.dumps(load(pf), ensure_ascii=False, indent=2)
        existing = [j for j in st["jobs"] if j["segment"] == seg["id"] and j["status"] in ("queued", "done")]
        if a.force:
            existing = []
        todo = max(0, takes - len(existing))
        if not todo:
            print(f"{seg['id']}: already has {len(existing)} take(s), skipped (use --force or --takes)")
            continue
        names = []
        for pic in seg["pictures"]:
            lp = os.path.join(a.project, pic["path"])
            key = f"{pic['path']}|{os.path.getmtime(lp)}"
            if key not in st["uploads"]:
                remote = pic["path"].replace("\\", "/").strip("/").replace("/", "__")
                st["uploads"][key] = upload_image(cfg, lp, sub, remote)
            names.append(st["uploads"][key])
        for _ in range(todo):
            seed = random.randrange(1, 2**48)
            prefix = f"{sub}/{seg['id']}/{seg['id']}_s{seed}"
            job_wf = patch(cfg, wf, m, prompt_text, seg["duration"], seed, names, prefix)
            res = http(cfg, "POST", "/prompt", {"prompt": job_wf, "client_id": st.setdefault("client_id", uuid.uuid4().hex)})
            if res.get("node_errors"):
                raise RuntimeError(f"{seg['id']}: ComfyUI rejected the workflow: {json.dumps(res['node_errors'], ensure_ascii=False)[:1500]}")
            st["jobs"].append({"segment": seg["id"], "seed": seed, "prompt_id": res["prompt_id"], "status": "queued",
                               "duration": seg["duration"], "refs": len(names),
                               "queued_at": dt.datetime.now().isoformat(timespec="seconds"), "files": []})
            queued += 1
            save(st_p, st)
            print(f"{seg['id']}: queued seed {seed} ({len(names)} refs, {seg['duration']}s) → {res['prompt_id']}")
    print(f"{queued} job(s) queued")
    return 0


def collect_files(outputs):
    files = []
    for node_out in outputs.values():
        for lst in node_out.values():
            if isinstance(lst, list):
                files += [x for x in lst if isinstance(x, dict) and "filename" in x]
    real = [f for f in files if f.get("type") == "output"]
    return real or files


def cmd_wait(a, cfg=None):
    cfg = cfg or load_config(a.config)
    st_p = paths(a.project)[1]
    st = load_state(a.project)
    segs = {s["id"]: s for s in load(paths(a.project)[0])["segments"]}
    poll = cfg.get("poll_seconds", 15)
    deadline = time.time() + 60 * cfg.get("timeout_minutes", 240)
    while True:
        pending = [j for j in st["jobs"] if j["status"] == "queued"]
        if not pending:
            break
        for j in pending:
            hist = http(cfg, "GET", f"/history/{j['prompt_id']}")
            h = hist.get(j["prompt_id"])
            if not h:
                continue
            status = (h.get("status") or {}).get("status_str", "success")
            if status == "error":
                msgs = [m for m in (h.get("status") or {}).get("messages", []) if m[0] == "execution_error"]
                j.update(status="error", error=json.dumps(msgs, ensure_ascii=False)[:1500])
                print(f"{j['segment']} seed {j['seed']}: ERROR {j['error'][:300]}")
            else:
                out_dir = os.path.join(a.project, segs[j["segment"]]["render_dir"])
                os.makedirs(out_dir, exist_ok=True)
                for f in collect_files(h.get("outputs", {})):
                    q = urllib.parse.urlencode({"filename": f["filename"], "subfolder": f.get("subfolder", ""), "type": f.get("type", "output")})
                    data = http(cfg, "GET", f"/view?{q}", raw=True, timeout=600)
                    base = f["filename"].split("/")[-1]
                    tag = f"{j['segment']}_s{j['seed']}"
                    local = os.path.join(out_dir, base if base.startswith(tag) else f"{tag}_{base}")
                    with open(local, "wb") as fh:
                        fh.write(data)
                    j["files"].append(os.path.relpath(local, a.project))
                j.update(status="done", done_at=dt.datetime.now().isoformat(timespec="seconds"))
                print(f"{j['segment']} seed {j['seed']}: done → {', '.join(j['files']) or '(no files?)'}")
            save(st_p, st)
        if any(j["status"] == "queued" for j in st["jobs"]):
            if time.time() > deadline:
                print("timeout reached; jobs are still queued on the server — run `wait` again later")
                return 1
            q = http(cfg, "GET", "/queue")
            print(f"  … {len(q.get('queue_running', []))} running, {len(q.get('queue_pending', []))} pending on server")
            time.sleep(poll)
    return cmd_status(a)


def cmd_run(a):
    cfg = load_config(a.config)
    cmd_submit(a, cfg)
    return cmd_wait(a, cfg)


def cmd_status(a):
    st = load_state(a.project)
    by = {}
    for j in st["jobs"]:
        by.setdefault(j["segment"], []).append(j)
    for g in sorted(by, key=lambda x: int(x[1:])):
        c = {}
        for j in by[g]:
            c[j["status"]] = c.get(j["status"], 0) + 1
        print(f"{g:<4}" + ", ".join(f"{k} {v}" for k, v in c.items()))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inspect"); p.add_argument("--config", required=True); p.add_argument("--write", action="store_true")
    p = sub.add_parser("check"); p.add_argument("project", nargs="?"); p.add_argument("--config", required=True)
    for name in ("submit", "run"):
        p = sub.add_parser(name); p.add_argument("project"); p.add_argument("--config", required=True)
        p.add_argument("--only"); p.add_argument("--takes", type=int); p.add_argument("--force", action="store_true")
    p = sub.add_parser("wait"); p.add_argument("project"); p.add_argument("--config", required=True)
    p = sub.add_parser("status"); p.add_argument("project")
    a = ap.parse_args()
    try:
        return {"inspect": cmd_inspect, "check": cmd_check, "submit": cmd_submit, "wait": cmd_wait,
                "run": cmd_run, "status": cmd_status}[a.cmd](a)
    except RuntimeError as e:
        print(f"ERROR: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
