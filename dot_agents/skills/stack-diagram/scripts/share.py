#!/usr/bin/env python3
"""Share a rendered diagram to the public stack-diagram gallery, or delete a shared one.

Usage:
  python3 share.py submit LIGHT.png DARK.png --title T --stack "A=a,B,C" --name N [--github LOGIN] [--icons DIR]
  python3 share.py delete ID
  python3 share.py list

submit  checks the inputs, solves the gallery's proof-of-work challenge, uploads both PNGs
        with the metadata, and saves the post's delete key to
        ~/.config/stack-diagram/gallery.json (mode 0600). Everything sent becomes public.
        --stack lists the technologies; "Name=key" attaches the logo saved under key in
        DIR/manifest.json, the icons dir fetch_icons.py wrote, passed as --icons DIR.
        Only logos from svgl, gilbarbara/logos and devicon are sent.
delete  deletes a post with the key saved there. If the gallery could confirm the post's
        GitHub login, signing in with that account on the gallery site deletes it too.
list    shows the posts saved there

Limits checked before upload: PNGs up to 1 MB each, 16-4000 px a side and 8 megapixels,
both the same size; title 1-80 chars; 1-24 stack names of up to 40 chars; name 1-40;
--github a valid GitHub login.
STACK_DIAGRAM_GALLERY overrides the gallery base URL.
"""
import hashlib, http.client, json, os, pathlib, re, sys, tempfile, time, urllib.error, urllib.parse, urllib.request, uuid

GALLERY = os.environ.get("STACK_DIAGRAM_GALLERY", "https://stacks.caru.moe").rstrip("/")
UA = {"User-Agent": "Mozilla/5.0 (stack-diagram-skill)"}
STORE = pathlib.Path.home() / ".config" / "stack-diagram" / "gallery.json"
LOGIN_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?")
ICON_PREFIXES = ("https://svgl.app/library/", "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/",
                 "https://raw.githubusercontent.com/devicons/devicon/master/icons/")
MAX_SIDE, MAX_PIXELS, MAX_BITS = 4000, 8_000_000, 26   # a 27+ bit challenge outlives its 10 minutes

def usage():
    print(__doc__); sys.exit(1)

def call(method, path, body=None, headers=None):
    """(status, parsed JSON or None); exits with the gallery's error message on 4xx/5xx."""
    req = urllib.request.Request(GALLERY + path, data=body, method=method, headers={**UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            msg = json.loads(raw)["error"]
        except (ValueError, KeyError, TypeError):
            msg = raw.decode("utf-8", "replace").strip()[:200] or e.reason
        sys.exit(f"gallery error {e.code}: {msg}")
    except (OSError, http.client.HTTPException) as e:
        sys.exit(f"cannot reach {GALLERY}: {getattr(e, 'reason', e)}")
    try:
        return status, json.loads(raw) if raw else None
    except ValueError:
        sys.exit(f"unexpected non-JSON response from {GALLERY + path}")

def solve(challenge, bits):
    """Smallest n where sha256(f"{challenge}:{n}") has `bits` leading zero bits -> "challenge:n"."""
    target, n = 1 << (256 - bits), 0
    while int.from_bytes(hashlib.sha256(f"{challenge}:{n}".encode()).digest(), "big") >= target:
        n += 1
    return f"{challenge}:{n}"

def multipart(parts):
    """parts: (name, filename or None, str or bytes) -> (body, content-type header)."""
    boundary = uuid.uuid4().hex
    body = b""
    for name, filename, value in parts:
        head = f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
        if filename:
            head += f'; filename="{filename}"\r\nContent-Type: image/png'
        body += f"{head}\r\n\r\n".encode() + (value if isinstance(value, bytes) else value.encode()) + b"\r\n"
    return body + f"--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"

def read_png(path):
    p = pathlib.Path(path)
    if not p.is_file():
        sys.exit(f"no such file: {path}")
    b = p.read_bytes()
    if not b.startswith(b"\x89PNG\r\n\x1a\n") or b[12:16] != b"IHDR":
        sys.exit(f"not a PNG: {path}")
    if len(b) > 1 << 20:
        sys.exit(f"{path} is {len(b) / (1 << 20):.1f} MB; the gallery takes PNGs up to 1 MB")
    w, h = int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")
    if not (16 <= w <= MAX_SIDE and 16 <= h <= MAX_SIDE and w * h <= MAX_PIXELS):
        sys.exit(f"{path} is {w}x{h}; the gallery takes 16-{MAX_SIDE} px a side and up to "
                 f"{MAX_PIXELS // 1_000_000} megapixels. Re-render with a lower --scale")
    return b, (w, h)

def load():
    return json.loads(STORE.read_text()) if STORE.exists() else []

def save(entries):
    """Swaps in a new file (mkstemp makes it 0600), so a crash never loses the keys already saved."""
    STORE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=STORE.parent, prefix=".gallery-")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(entries, f, indent=2)
        os.replace(tmp, STORE)
    except BaseException:
        pathlib.Path(tmp).unlink(missing_ok=True)
        raise

def stack_items(spec, icons):
    """--stack "Name=key,Name" -> [{name, icon?, iconDark?}], URLs from the icons dir's manifest."""
    manifest, mpath = None, None
    if icons is not None:
        mpath = pathlib.Path(icons) / "manifest.json"
        try:
            manifest = json.loads(mpath.read_text())
        except (OSError, ValueError) as e:
            sys.exit(f"cannot read {mpath}: {e}")
    items = []
    for part in (p.strip() for p in spec.split(",")):
        if not part:
            continue
        name, has_key, key = (s.strip() for s in part.partition("="))
        if not name:
            sys.exit(f"--stack {part!r} has no name before '='")
        item = {"name": name}
        if has_key:
            if manifest is None:
                sys.exit(f"--stack {part!r} names an icon; pass the icons dir with --icons DIR")
            entry = manifest.get(key) if isinstance(manifest, dict) else None
            if not isinstance(entry, dict) or not entry.get("url"):
                sys.exit(f"no icon {key!r} in {mpath}")
            for field, url in (("icon", entry["url"]), ("iconDark", entry.get("dark_url"))):
                if isinstance(url, str) and url.startswith(ICON_PREFIXES):
                    item[field] = url
        items.append(item)
    return items

def opt(args, flag):
    if flag not in args:
        return None
    i = args.index(flag); v = args[i + 1:i + 2]; del args[i:i + 2]
    return v[0] if v else ""

def submit(args):
    title, stack, name, github, icons = [opt(args, f) for f in ("--title", "--stack", "--name", "--github", "--icons")]
    if len(args) != 2 or None in (title, stack, name) or icons == "":
        usage()
    (light, light_size), (dark, dark_size) = read_png(args[0]), read_png(args[1])
    if light_size != dark_size:
        sys.exit(f"the light and dark PNGs differ in size: {light_size} vs {dark_size}")
    title, name = title.strip(), name.strip()
    items = stack_items(stack, icons)
    names = [item["name"] for item in items]
    for flag, s, hi in (("--title", title, 80), ("--name", name, 40)):
        if not 1 <= len(s) <= hi:
            sys.exit(f"{flag} must be 1-{hi} characters (got {len(s)})")
    if not 1 <= len(names) <= 24:
        sys.exit(f"--stack must list 1-24 comma-separated names (got {len(names)})")
    too_long = [s for s in names if len(s) > 40]
    if too_long:
        sys.exit(f"stack names must be up to 40 characters: {', '.join(too_long)}")
    if github is not None and not LOGIN_RE.fullmatch(github):
        sys.exit(f"--github {github!r} is not a valid GitHub login")
    meta = {"title": title, "stack": items, "name": name}
    if github:
        meta["github"] = github
    entries = load()
    save(entries)   # fail before upload if the key store is not writable

    _, ch = call("GET", "/api/challenge")
    challenge, bits = (ch.get("challenge"), ch.get("bits")) if isinstance(ch, dict) else (None, None)
    if not isinstance(challenge, str) or type(bits) is not int or not 0 <= bits <= MAX_BITS:
        sys.exit(f"unexpected challenge from {GALLERY}: {ch!r}")
    print(f"solving proof of work ({bits} bits)...", flush=True)
    proof = solve(challenge, bits)
    body, ctype = multipart([("meta", None, json.dumps(meta)), ("light", "light.png", light),
                             ("dark", "dark.png", dark)])
    # in a header so the gallery can check it before reading the upload
    _, res = call("POST", "/api/stacks", body, {"Content-Type": ctype, "X-Proof-Of-Work": proof})

    entries.append({"id": res["id"], "url": res["url"], "title": title, "deleteKey": res["deleteKey"],
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    save(entries)
    print(f"shared: {res['url']}")
    if res.get("status") == "held":
        print("status: held - it appears in the gallery after a manual review")
    else:
        print(f"status: {res.get('status', 'published')}")
    print(f"delete key saved to {STORE} (delete with: share.py delete {res['id']})")

def delete(post_id):
    entries = load()
    entry = next((e for e in entries if e.get("id") == post_id), None)
    if not entry:
        sys.exit(f"no saved delete key for {post_id!r} in {STORE}.\n"
                 f"If the gallery confirmed the post's GitHub login, sign in with that account on {GALLERY} to delete it.")
    status, _ = call("DELETE", f"/api/stacks/{urllib.parse.quote(post_id, safe='')}",
                     headers={"Authorization": f"Bearer {entry['deleteKey']}"})
    if status != 204:
        sys.exit(f"unexpected response {status} from {GALLERY}; kept the saved key")
    save([e for e in entries if e is not entry])
    print(f"deleted {entry['url']}")

def main():
    args = sys.argv[1:]
    cmd = args.pop(0) if args else None
    if cmd == "submit":
        submit(args)
    elif cmd == "delete" and len(args) == 1:
        delete(args[0])
    elif cmd == "list" and not args:
        entries = load()
        if not entries:
            print(f"no shared diagrams saved in {STORE}")
        for e in entries:
            print(f"{e['id']}  {e['createdAt'][:10]}  {e['title']}  {e['url']}")
    else:
        usage()

if __name__ == "__main__":
    main()
