#!/usr/bin/env python3
"""Drive the MiniMax H3 reference-to-video workflow from segments.json.

Two backends (config key "backend"):

  zealman  — the zealman ComfyUI panel image on AutoDL (default port 6008, the URL you open in
             the browser). Jobs go through the panel's workflow API: the workflow is a saved
             card on the panel's「API 生成」page, addressed by "workflow_id"; each job only
             sends "node:field" input values. References are uploaded with
             /api/comfy/upload/file and written into the card's LoadImage nodes.
  comfyui  — a bare ComfyUI (/prompt, /history, /view) with a locally exported API workflow.

No third-party dependencies (standard library only).

  python3 comfy_run.py check    [<project_dir>] --config comfy.json [--start]
  python3 comfy_run.py inspect  --config comfy.json [--write]      # find node ids in the workflow
  python3 comfy_run.py submit   <project_dir> --config comfy.json [--only G1,G3] [--takes 3] [--force] [--retry-failed]
  python3 comfy_run.py wait     <project_dir> --config comfy.json   # poll, download, record
  python3 comfy_run.py run      <project_dir> --config comfy.json [same options as submit] [--start]
  python3 comfy_run.py status   <project_dir>

`run` is serial when "serial" is true (default for zealman): free VRAM → submit one take →
wait → download → next. That is what the panel itself does for the U series; queueing many
heavy H3 jobs back to back tends to run out of memory after the first one.

State lives in <project_dir>/10_production/production_state.json. Renders are downloaded to
<project_dir>/11_renders/<G>/ the moment each job finishes: prompt ids only live in ComfyUI's
memory and are gone after a restart, and files on a rented box disappear with the instance.
"""
import argparse
import copy
import datetime as dt
import json
import mimetypes
import os
import random
import re
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zlib

STATE = "10_production/production_state.json"
SEGMENTS = "10_production/segments.json"
REF_RE = re.compile(r"^(?P<pre>.*ref_image_)(?P<i>\d+)$")
LOST_AFTER_IDLE_POLLS = 3


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


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def load_config(path):
    cfg = load(path)
    cfg["base_url"] = os.environ.get("COMFY_URL", cfg.get("base_url", "")).rstrip("/")
    if not cfg["base_url"] or "YOUR-" in cfg["base_url"]:
        sys.exit("base_url missing: set it in the config or the COMFY_URL environment variable")
    cfg.setdefault("backend", "comfyui")
    if cfg["backend"] not in ("zealman", "comfyui"):
        sys.exit(f'unknown backend "{cfg["backend"]}" (use "zealman" or "comfyui")')
    if zealman(cfg) and not cfg.get("workflow_id"):
        sys.exit('backend "zealman" needs "workflow_id": the name of the saved card on the panel\'s API page')
    cfg.setdefault("serial", zealman(cfg))
    cfg["_dir"] = os.path.dirname(os.path.abspath(path))
    return cfg


def zealman(cfg):
    return cfg.get("backend") == "zealman"


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
    if raw:
        return data
    res = json.loads(data or b"{}")
    if isinstance(res, dict) and res.get("success") is False:
        raise RuntimeError(f"{method} {path} → {res.get('error') or res.get('message') or res}")
    return res


def multipart(fields, file_field, filename, content):
    boundary = uuid.uuid4().hex
    ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
             for k, v in fields]
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
                 f"Content-Type: {ctype}\r\n\r\n".encode() + content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), {"Content-Type": f"multipart/form-data; boundary={boundary}"}


def upload(cfg, content, name, subfolder):
    """Upload bytes to ComfyUI's input dir; returns the value a LoadImage node needs."""
    if zealman(cfg):
        # the panel's upload has no subfolder field: keep names unique with an episode prefix
        body, h = multipart([("overwrite", "true")], "file", f"{subfolder.replace('/', '__')}__{name}", content)
        res = http(cfg, "POST", "/api/comfy/upload/file", body, h)
    else:
        body, h = multipart([("overwrite", "true"), ("type", "input"), ("subfolder", subfolder)], "image", name, content)
        res = http(cfg, "POST", "/upload/image", body, h)
    sub = res.get("subfolder") or ""
    return f"{sub}/{res['name']}" if sub else res["name"]


def blank_png(w=64, h=64):
    """Plain white PNG for reference slots a segment does not use (the panel does the same)."""
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    rows = b"".join(b"\x00" + b"\xff" * 3 * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


# ---------------------------------------------------------------- server state
def ensure_ready(cfg, start=False):
    """Returns a one-line description of the server; starts ComfyUI on the panel if allowed."""
    if not zealman(cfg):
        stats = http(cfg, "GET", "/system_stats")
        dev = (stats.get("devices") or [{}])[0]
        return f"device: {dev.get('name', '?')}  VRAM free: {round((dev.get('vram_free') or 0) / 2**30, 1)} GB"
    if http(cfg, "GET", "/api/health").get("status") != "ok":
        raise RuntimeError("panel /api/health is not ok")
    gpu = http(cfg, "GET", "/api/gpu/info")
    if not gpu.get("hasGPU"):
        raise RuntimeError("the AutoDL instance is in no-GPU mode (无卡模式): power it on with a GPU in the AutoDL console")
    g = (gpu.get("gpus") or [{}])[0]
    desc = f"GPU: {g.get('name', '?')}  VRAM used {g.get('memory_used_mb', '?')}/{g.get('memory_total_mb', '?')} MB"
    st = http(cfg, "GET", "/api/comfy/status")
    if st.get("running"):
        return desc
    if not st.get("starting"):
        if not (start or cfg.get("auto_start", True)):
            raise RuntimeError("ComfyUI is not running on the panel; rerun with --start (or set \"auto_start\": true)")
        body = {"pluginSeries": cfg["plugin_series"]} if cfg.get("plugin_series") else {}
        body.update(cfg.get("start_options") or {})
        print(f"starting ComfyUI on the panel {json.dumps(body, ensure_ascii=False)} …")
        http(cfg, "POST", "/api/comfy/start", body, timeout=300)
    for _ in range(int(cfg.get("start_timeout_seconds", 180) / 3)):
        st = http(cfg, "GET", "/api/comfy/status")
        if st.get("running"):
            return desc
        time.sleep(3)
    raise RuntimeError(f"ComfyUI did not become ready in time (last status: {st})")


def free_memory(cfg):
    path = "/api/comfy/proxy/free" if zealman(cfg) else "/free"
    try:
        http(cfg, "POST", path, {"unload_models": True, "free_memory": True})
    except RuntimeError as e:   # never blocks generation, same as the panel
        print(f"  (free memory failed, continuing: {e})")


def queue_busy(cfg):
    if zealman(cfg):
        return bool(http(cfg, "GET", "/api/comfy/queue-status").get("busy"))
    q = http(cfg, "GET", "/queue")
    return bool(q.get("queue_running") or q.get("queue_pending"))


def resolve_workflow_id(cfg):
    if "_wf_id" in cfg:
        return cfg["_wf_id"]
    want = cfg["workflow_id"]
    items = http(cfg, "GET", "/api/workflow/list").get("workflows", [])
    for w in items:
        if want in (w.get("id"), w.get("name")) or want.removesuffix(".json") == w.get("id"):
            cfg["_wf_id"] = w["id"]
            return w["id"]
    names = ", ".join(w.get("id", "?") for w in items) or "(none)"
    raise RuntimeError(f'workflow card "{want}" is not saved on the panel. Import it on the「API 生成」page first. '
                       f"Saved cards: {names}")


def template(cfg):
    if "_template" not in cfg:
        if zealman(cfg):
            wid = resolve_workflow_id(cfg)
            cfg["_template"] = http(cfg, "GET", "/api/workflow/config/" + urllib.parse.quote(wid))["workflow_template"]
        else:
            cfg["_template"] = load(cfg_path(cfg, cfg["workflow_api"]))
    return cfg["_template"]


# ---------------------------------------------------------------- workflow mapping
def ref_slots(inputs, prefix=None):
    """[(index, input_name, source_node_id|None)] for the reference-image inputs, by index.

    Handles both ref_image_0 and the newer grouped ref_images.ref_image_0 naming, and never
    matches look-alikes such as ref_image_size.
    """
    out = []
    for k, v in inputs.items():
        mm = REF_RE.match(k)
        if mm and (not prefix or mm.group("pre") == prefix):
            out.append((int(mm.group("i")), k, v[0] if isinstance(v, list) and v else None))
    return sorted(out)


def discover(wf):
    """Best-effort guess of which node does what in an API-format workflow."""
    m = {}
    for nid, n in sorted(wf.items(), key=lambda kv: (len(kv[0]), kv[0])):
        ct = n.get("class_type", "")
        title = (n.get("_meta") or {}).get("title", "")
        ins = n.get("inputs", {})
        if ref_slots(ins):
            m.setdefault("conditioning", nid)
        if (ct == "CR Prompt Text" or "prompt" in title.lower()) and isinstance(ins.get("prompt"), str):
            m.setdefault("prompt", nid)
        if "duration" in title.lower() and isinstance(ins.get("value"), (int, float)):
            m.setdefault("duration", nid)
        if ct == "RandomNoise" or ("noise_seed" in ins and not isinstance(ins["noise_seed"], list)):
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
    auto = discover(wf)
    m = {**auto, **{k: v for k, v in (cfg.get("nodes") or {}).items() if v}}
    missing = [k for k in ("conditioning", "prompt", "duration", "noise", "save") if not m.get(k)]
    if missing:
        raise RuntimeError(f"cannot find node(s) {missing} in the workflow; run `inspect` and set them under \"nodes\"")
    for k, nid in m.items():
        if nid not in wf:
            raise RuntimeError(f'config nodes.{k} = "{nid}" does not exist in the workflow')
    return m


def slots_of(cfg, wf, m):
    slots = ref_slots(wf[m["conditioning"]]["inputs"], cfg.get("ref_input_prefix") or None)
    if not slots:
        raise RuntimeError(f"node #{m['conditioning']} has no ref_image_N inputs")
    return slots


def card_slots(cfg, wf, m):
    """zealman: the card's reference slots must each be fed by their own LoadImage node."""
    slots = slots_of(cfg, wf, m)
    srcs = [s for _, _, s in slots]
    bad = [k for _, k, s in slots if not s or wf.get(s, {}).get("class_type") != "LoadImage"]
    if bad or len(set(srcs)) != len(srcs):
        raise RuntimeError(f"every reference input of #{m['conditioning']} must be wired to its own LoadImage node "
                           f"(check {', '.join(bad) or 'duplicate sources'}); fix the workflow and re-save the card")
    return slots


def patch_workflow(cfg, wf, m, prompt_text, duration, seed, ref_names, prefix):
    """comfyui backend: full API workflow with the references re-wired to new LoadImage nodes."""
    wf = copy.deepcopy(wf)
    inp = cfg.get("inputs") or {}
    wf[m["prompt"]]["inputs"][inp.get("prompt", "prompt")] = prompt_text
    wf[m["duration"]]["inputs"][inp.get("duration", "value")] = duration
    wf[m["noise"]]["inputs"][inp.get("seed", "noise_seed")] = seed
    wf[m["save"]]["inputs"][inp.get("save_prefix", "filename_prefix")] = prefix

    cond = wf[m["conditioning"]]["inputs"]
    slots = slots_of(cfg, wf, m)
    pre = REF_RE.match(slots[0][1]).group("pre")
    for _, k, _ in slots:
        del cond[k]
    for src in {s for _, _, s in slots if s}:   # drop LoadImage nodes nothing uses any more
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


def input_values(cfg, m, slots, prompt_text, duration, seed, ref_names, blank, prefix):
    """zealman backend: the "node:field" overrides sent with /api/workflow/generate."""
    inp = cfg.get("inputs") or {}
    iv = {f"{m['prompt']}:{inp.get('prompt', 'prompt')}": prompt_text,
          f"{m['duration']}:{inp.get('duration', 'value')}": duration,
          f"{m['noise']}:{inp.get('seed', 'noise_seed')}": seed,
          f"{m['save']}:{inp.get('save_prefix', 'filename_prefix')}": prefix}
    for i, (_, _, src) in enumerate(slots):
        iv[f"{src}:image"] = ref_names[i] if i < len(ref_names) else blank
    return iv


# ---------------------------------------------------------------- jobs
def paths(proj):
    return os.path.join(proj, SEGMENTS), os.path.join(proj, STATE)


def load_state(proj):
    p = paths(proj)[1]
    return load(p) if os.path.exists(p) else {"jobs": [], "uploads": {}}


def plan(a, cfg, segs, st, slot_count=None):
    """List of segment ids to submit, one entry per take to add."""
    takes = a.takes or cfg.get("takes_per_segment", 3)
    max_fail = cfg.get("max_resubmits", 2)
    only = set(a.only.split(",")) if a.only else None
    todo, too_many = [], []
    for seg in segs["segments"]:
        g = seg["id"]
        if only and g not in only:
            continue
        if not os.path.exists(os.path.join(a.project, seg["prompt_file"])):
            print(f"{g}: prompt file missing, skipped (write it and run validate_video_prompts.py first)")
            continue
        if slot_count is not None and len(seg["pictures"]) > slot_count:
            too_many.append(f"{g} ({len(seg['pictures'])})")
            continue
        jobs = [j for j in st["jobs"] if j["segment"] == g]
        failed = sum(j["status"] == "error" for j in jobs)
        if failed > max_fail and not a.retry_failed:
            print(f"{g}: {failed} failed jobs — not resubmitting (limit {max_fail}); fix the cause, then use --retry-failed")
            continue
        have = 0 if a.force else sum(j["status"] in ("queued", "done") for j in jobs)
        n = max(0, takes - have)
        if not n:
            print(f"{g}: already has {have} take(s), skipped (use --force or --takes)")
        todo += [g] * n
    if too_many:
        raise RuntimeError(f"the workflow has {slot_count} reference slots but {', '.join(too_many)} need more. "
                           f"Rebuild with `build_segments.py <project> --max-refs {slot_count}` and rewrite those "
                           f"prompts, or add LoadImage slots to the workflow and re-save it")
    return todo


class Submitter:
    def __init__(self, a, cfg):
        self.a, self.cfg = a, cfg
        self.segs = load(paths(a.project)[0])
        self.st_p = paths(a.project)[1]
        self.st = load_state(a.project)
        self.wf = template(cfg)
        self.m = mapping(cfg, self.wf)
        self.slots = card_slots(cfg, self.wf, self.m) if zealman(cfg) else None
        ep = self.segs.get("episode") or self.segs.get("project_id") or "episode"
        self.sub = f"dating_diary/{ep}"
        self.by_id = {s["id"]: s for s in self.segs["segments"]}

    def plan(self):
        return plan(self.a, self.cfg, self.segs, self.st, len(self.slots) if self.slots else None)

    def ref_names(self, seg):
        names = []
        for pic in seg["pictures"]:
            lp = os.path.join(self.a.project, pic["path"])
            key = f"{self.cfg['backend']}|{pic['path']}|{os.path.getmtime(lp)}"
            if key not in self.st["uploads"]:
                with open(lp, "rb") as f:
                    remote = pic["path"].replace("\\", "/").strip("/").replace("/", "__")
                    self.st["uploads"][key] = upload(self.cfg, f.read(), remote, self.sub)
                save(self.st_p, self.st)
            names.append(self.st["uploads"][key])
        return names

    def blank(self):
        key = f"{self.cfg['backend']}|__blank__"
        if key not in self.st["uploads"]:
            self.st["uploads"][key] = upload(self.cfg, blank_png(), "dd_blank.png", self.sub)
        return self.st["uploads"][key]

    def submit(self, g):
        cfg, seg = self.cfg, self.by_id[g]
        prompt_text = json.dumps(load(os.path.join(self.a.project, seg["prompt_file"])), ensure_ascii=False, indent=2)
        names = self.ref_names(seg)
        seed = random.randrange(1, 2**48)
        prefix = f"{self.sub}/{g}/{g}_s{seed}"
        if cfg.get("serial") or cfg.get("free_before_each", False):
            free_memory(cfg)
        if zealman(cfg):
            iv = input_values(cfg, self.m, self.slots, prompt_text, seg["duration"], seed, names, self.blank(), prefix)
            res = http(cfg, "POST", "/api/workflow/generate",
                       {"workflow_id": resolve_workflow_id(cfg), "input_values": iv, "client_id": "dating-diary"})
        else:
            job_wf = patch_workflow(cfg, self.wf, self.m, prompt_text, seg["duration"], seed, names, prefix)
            res = http(cfg, "POST", "/prompt",
                       {"prompt": job_wf, "client_id": self.st.setdefault("client_id", uuid.uuid4().hex)})
            if res.get("node_errors"):
                raise RuntimeError(f"{g}: ComfyUI rejected the workflow: "
                                   f"{json.dumps(res['node_errors'], ensure_ascii=False)[:1500]}")
        self.st["jobs"].append({"segment": g, "seed": seed, "prompt_id": res["prompt_id"], "status": "queued",
                                "backend": cfg["backend"], "duration": seg["duration"], "refs": len(names),
                                "queued_at": now(), "files": []})
        save(self.st_p, self.st)
        print(f"{g}: queued seed {seed} ({len(names)} refs, {seg['duration']}s) → {res['prompt_id']}")


def poll(cfg, j):
    """-> ("pending"|"done"|"error", [file descriptors], error text)"""
    if zealman(cfg):
        r = http(cfg, "GET", "/api/workflow/result?prompt_id=" + urllib.parse.quote(j["prompt_id"]))
        if r.get("error"):
            return "error", [], json.dumps(r["error"], ensure_ascii=False)[:1500]
        if r.get("pending", True):
            return "pending", [], None
        files = [x for x in r.get("results", []) if x.get("url") and x.get("type") in ("video", "image", "audio")]
        videos = [x for x in files if x["type"] == "video"]
        return "done", videos or files, None
    h = http(cfg, "GET", f"/history/{j['prompt_id']}").get(j["prompt_id"])
    if not h:
        return "pending", [], None
    if (h.get("status") or {}).get("status_str", "success") == "error":
        msgs = [x for x in (h.get("status") or {}).get("messages", []) if x[0] == "execution_error"]
        return "error", [], json.dumps(msgs, ensure_ascii=False)[:1500]
    files = []
    for node_out in h.get("outputs", {}).values():
        for lst in node_out.values():
            if isinstance(lst, list):
                files += [x for x in lst if isinstance(x, dict) and "filename" in x]
    real = [x for x in files if x.get("type") == "output"]
    return "done", real or files, None


def fetch(cfg, f):
    if zealman(cfg):
        return f.get("filename") or f["url"].split("/")[-1], http(cfg, "GET", urllib.parse.quote(f["url"], safe="/"),
                                                                 raw=True, timeout=600)
    q = urllib.parse.urlencode({"filename": f["filename"], "subfolder": f.get("subfolder", ""), "type": f.get("type", "output")})
    return f["filename"], http(cfg, "GET", f"/view?{q}", raw=True, timeout=600)


def wait_jobs(a, cfg, quiet=False):
    st_p = paths(a.project)[1]
    st = load_state(a.project)
    segs = {s["id"]: s for s in load(paths(a.project)[0])["segments"]}
    poll_s = cfg.get("poll_seconds", 15)
    deadline = time.time() + 60 * cfg.get("timeout_minutes", 240)
    idle = 0
    while True:
        pending = [j for j in st["jobs"] if j["status"] == "queued"]
        if not pending:
            return 0
        for j in pending:
            state, files, err = poll(cfg, j)
            if state == "pending":
                continue
            if state == "error":
                j.update(status="error", error=err, done_at=now())
                print(f"{j['segment']} seed {j['seed']}: ERROR {err[:300]}")
            else:
                out_dir = os.path.join(a.project, segs[j["segment"]]["render_dir"])
                os.makedirs(out_dir, exist_ok=True)
                for f in files:
                    name, data = fetch(cfg, f)
                    base = name.split("/")[-1]
                    tag = f"{j['segment']}_s{j['seed']}"
                    local = os.path.join(out_dir, base if base.startswith(tag) else f"{tag}_{base}")
                    with open(local, "wb") as fh:
                        fh.write(data)
                    j["files"].append(os.path.relpath(local, a.project))
                j.update(status="done", done_at=now())
                print(f"{j['segment']} seed {j['seed']}: done → {', '.join(j['files']) or '(no files?)'}")
            save(st_p, st)
        still = [j for j in st["jobs"] if j["status"] == "queued"]
        if not still:
            return 0
        if time.time() > deadline:
            print("timeout reached; jobs are still queued on the server — run `wait` again later")
            return 1
        # a queued job the server no longer knows about (ComfyUI restarted, history evicted) looks
        # exactly like a job that is still running — except that the queue is empty.
        idle = 0 if queue_busy(cfg) else idle + 1
        if idle >= LOST_AFTER_IDLE_POLLS:
            for j in still:
                j.update(status="error", error="lost: the server has no record of this job (ComfyUI restarted?)",
                         done_at=now())
                print(f"{j['segment']} seed {j['seed']}: LOST — will be resubmitted by the next `run`")
            save(st_p, st)
            return 0
        if not quiet:
            print(f"  … {len(still)} job(s) still running")
        time.sleep(poll_s)


# ---------------------------------------------------------------- commands
def cmd_inspect(a):
    cfg = load_config(a.config)
    wf = template(cfg)
    print(describe(wf))
    auto = discover(wf)
    print("\nsuggested nodes:", json.dumps(auto, indent=2))
    if auto.get("conditioning"):
        slots = ref_slots(wf[auto["conditioning"]]["inputs"])
        print("reference slots:", ", ".join(f"{k} ← #{s}" for _, k, s in slots))
    if a.write:
        raw = load(a.config)
        raw["nodes"] = {**auto, **{k: v for k, v in (raw.get("nodes") or {}).items() if v}}
        save(a.config, raw)
        print(f"written to {a.config} — check them against the node numbers you see in ComfyUI")
    return 0


def cmd_check(a):
    cfg = load_config(a.config)
    print(f"{cfg['backend']} at {cfg['base_url']} | {ensure_ready(cfg, a.start)}")
    print("ComfyUI is running")
    wf = template(cfg)
    m = mapping(cfg, wf)
    print("node mapping:", m)
    if zealman(cfg):
        print(f"workflow card: {resolve_workflow_id(cfg)}")
        slots = card_slots(cfg, wf, m)
        n_slots = len(slots)
        print(f"{n_slots} reference slots: " + ", ".join(f"{k} ← LoadImage #{s}" for _, k, s in slots))
        try:
            av = http(cfg, "GET", "/api/comfy/plugin-availability")
            letter = resolve_workflow_id(cfg)[:1].upper()
            ok = not av.get("restricted") or letter in (av.get("series") or []) or any(
                resolve_workflow_id(cfg).startswith(p) for p in av.get("workflowPrefixes") or [])
            if not ok:
                print(f"WARNING: ComfyUI runs the plugin profile {av.get('label')} ({av.get('series')}); series "
                      f"{letter} is disabled. Restart it with that series (\"plugin_series\" in the config).")
        except RuntimeError:
            pass
        clip = " ".join(str(n.get("inputs", {}).get("clip_name", "")) for n in wf.values())
        if "nvfp4" in clip.lower():
            try:
                arch = http(cfg, "GET", "/api/gpu/profile").get("arch")
                if arch and arch != "blackwell":
                    print(f"WARNING: the text encoder is NVFP4 but this GPU is {arch}; NVFP4 only runs natively on "
                          f"Blackwell (RTX 50xx). Expect it to be slow or to fail.")
            except RuntimeError:
                pass
    else:
        slots = slots_of(cfg, wf, m)
        ct = wf[m["conditioning"]]["class_type"]
        info = http(cfg, "GET", "/object_info/" + urllib.parse.quote(ct)).get(ct, {})
        decl = {**(info.get("input", {}).get("required") or {}), **(info.get("input", {}).get("optional") or {})}
        fixed = [k for k in decl if REF_RE.match(k)]
        n_slots = len(fixed) or None
        print(f"{ct}: " + (f"declares {len(fixed)} reference inputs" if fixed else
                           "reference inputs grow dynamically (no fixed count)"))
    seg_p = paths(a.project)[0] if a.project else None
    if seg_p and os.path.exists(seg_p):
        need = max(len(s["pictures"]) for s in load(seg_p)["segments"])
        if n_slots and need > n_slots:
            print(f"FAIL: a segment needs {need} references but the workflow has {n_slots} slots. Rebuild with "
                  f"`build_segments.py <project> --max-refs {n_slots}` (or add slots to the workflow).")
            return 1
        print(f"largest segment needs {need} references — OK")
    return 0


def cmd_submit(a, cfg=None):
    cfg = cfg or load_config(a.config)
    ensure_ready(cfg, getattr(a, "start", False))
    s = Submitter(a, cfg)
    todo = s.plan()
    if zealman(cfg) and len(todo) > 1:
        print("note: queueing several H3 jobs at once can run out of memory; `run` submits them one at a time")
    for g in todo:
        s.submit(g)
    print(f"{len(todo)} job(s) queued")
    return 0


def cmd_wait(a, cfg=None):
    cfg = cfg or load_config(a.config)
    rc = wait_jobs(a, cfg)
    cmd_status(a)
    return rc


def cmd_run(a):
    cfg = load_config(a.config)
    ensure_ready(cfg, a.start)
    if not cfg.get("serial"):
        cmd_submit(a, cfg)
        return cmd_wait(a, cfg)
    if wait_jobs(a, cfg):              # finish whatever an earlier session left queued
        return 1
    todo = Submitter(a, cfg).plan()
    print(f"{len(todo)} job(s) to run, one at a time")
    for i, g in enumerate(todo, 1):
        s = Submitter(a, cfg)          # re-read state: the previous job was recorded by wait_jobs
        print(f"[{i}/{len(todo)}] ", end="")
        s.submit(g)
        if wait_jobs(a, cfg, quiet=True):
            return 1
    free_memory(cfg)
    cmd_status(a)
    return 0


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
    p.add_argument("--start", action="store_true", help="start ComfyUI on the panel if it is not running")
    for name in ("submit", "run"):
        p = sub.add_parser(name); p.add_argument("project"); p.add_argument("--config", required=True)
        p.add_argument("--only"); p.add_argument("--takes", type=int); p.add_argument("--force", action="store_true")
        p.add_argument("--retry-failed", action="store_true", help="resubmit segments past the failure limit")
        p.add_argument("--start", action="store_true", help="start ComfyUI on the panel if it is not running")
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
