#!/usr/bin/env python3
"""
Strategic Wrestler — update from GitHub Releases, serve on localhost,
optionally start the local Auto-Clip server (port 5057).

Requires Python 3 stdlib only for the main app.
Clip server optional: pip install flask flask-cors  (+ ffmpeg on PATH)

Repo: CannonFodderrr/Strategic-Wrestler
"""
from __future__ import annotations

import json
import os
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# --- Config ---
GITHUB_REPO = "CannonFodderrr/Strategic-Wrestler"
HTML_NAME = "index.html"
HTML_FALLBACK_NAME = "indexSW.html"  # migration from older pack
VERSION_FILE = "version.txt"
PORT = 2231
CLIP_PORT = 5057
USER_AGENT = "StrategicWrestler-Updater/1.0"
TIMEOUT = 30
# --------------

ROOT = Path(__file__).resolve().parent
VERSION_PATH = ROOT / VERSION_FILE


def log(msg: str) -> None:
    print(msg, flush=True)


def html_path() -> Path:
    primary = ROOT / HTML_NAME
    if primary.is_file():
        return primary
    fallback = ROOT / HTML_FALLBACK_NAME
    if fallback.is_file():
        return fallback
    return primary


def read_local_version() -> str:
    if VERSION_PATH.is_file():
        return VERSION_PATH.read_text(encoding="utf-8", errors="replace").strip()
    return ""


def write_local_version(tag: str) -> None:
    VERSION_PATH.write_text(tag.strip() + "\n", encoding="utf-8")


def normalize_tag(tag: str) -> str:
    t = (tag or "").strip()
    if t.lower().startswith("v") and len(t) > 1 and t[1].isdigit():
        return t[1:]
    return t


def version_is_newer(remote: str, local: str) -> bool:
    r, loc = normalize_tag(remote), normalize_tag(local)
    if not r:
        return False
    if not loc:
        return True
    if r == loc:
        return False

    def parts(s: str):
        out = []
        for p in s.replace("-", ".").split("."):
            if p.isdigit():
                out.append(int(p))
            else:
                out.append(p)
        return out

    try:
        rp, lp = parts(r), parts(loc)
        n = max(len(rp), len(lp))
        rp += [0] * (n - len(rp))
        lp += [0] * (n - len(lp))
        return rp > lp
    except Exception:
        return r != loc


def http_get_json(url: str):
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_download(url: str, dest: Path) -> None:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"})
    with urlopen(req, timeout=TIMEOUT) as resp:
        data = resp.read()
    if len(data) < 1000:
        raise RuntimeError("Downloaded file is too small — not a valid HTML app")
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(dest)


def find_html_asset(release: dict):
    assets = release.get("assets") or []
    exact = None
    any_html = None
    for a in assets:
        name = (a.get("name") or "")
        url = a.get("browser_download_url")
        if not url:
            continue
        low = name.lower()
        if low == HTML_NAME.lower() or low == HTML_FALLBACK_NAME.lower():
            exact = (url, name)
        elif low.endswith(".html") and any_html is None:
            any_html = (url, name)
    if exact:
        return exact
    if any_html:
        return any_html
    return None, None


def check_and_update(skip: bool = False) -> None:
    if skip:
        log("  Update check skipped (--offline / SW_SKIP_UPDATE).")
        return
    if os.environ.get("SW_SKIP_UPDATE", "").strip().lower() in ("1", "true", "yes"):
        log("  Update check skipped (SW_SKIP_UPDATE).")
        return

    local = read_local_version()
    log(f"  Local version:  {local or '(none yet)'}")
    api = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    log(f"  Checking GitHub: {GITHUB_REPO} …")
    try:
        release = http_get_json(api)
    except HTTPError as e:
        if e.code == 404:
            log("  No GitHub Release found yet (404). Using the HTML already in this folder.")
            log("  (Create a Release and attach index.html — see GITHUB-RELEASES-HOWTO.txt)")
            return
        log(f"  Update check failed (HTTP {e.code}). Starting with current files.")
        return
    except (URLError, TimeoutError, OSError) as e:
        log(f"  Update check failed (network): {e}")
        log("  Starting with current files (offline OK).")
        return
    except Exception as e:
        log(f"  Update check failed: {e}")
        return

    tag = (release.get("tag_name") or "").strip()
    if not tag:
        log("  Latest release has no tag name. Skipping.")
        return

    log(f"  Latest release: {tag}")
    if not version_is_newer(tag, local):
        log("  Already up to date.")
        return

    asset_url, asset_name = find_html_asset(release)
    if not asset_url:
        asset_url = f"https://github.com/{GITHUB_REPO}/releases/download/{tag}/{HTML_NAME}"
        asset_name = HTML_NAME
        log("  No HTML asset listed on the release — trying direct download URL.")

    dest = ROOT / HTML_NAME
    log(f"  Downloading {asset_name or HTML_NAME} → {HTML_NAME} …")
    try:
        http_download(asset_url, dest)
    except HTTPError as e:
        # Try legacy name on the release
        if asset_name != HTML_FALLBACK_NAME:
            try:
                alt = f"https://github.com/{GITHUB_REPO}/releases/download/{tag}/{HTML_FALLBACK_NAME}"
                log(f"  Retry as {HTML_FALLBACK_NAME} …")
                http_download(alt, dest)
            except Exception:
                log(f"  Download failed (HTTP {e.code}). Attach index.html to the GitHub Release.")
                return
        else:
            log(f"  Download failed (HTTP {e.code}). Attach index.html to the GitHub Release.")
            return
    except Exception as e:
        log(f"  Download failed: {e}")
        return

    write_local_version(tag)
    log(f"  Updated {HTML_NAME} → {tag}")
    log("  (Your season data is NOT in this file — Drive/local backups are unchanged.)")


def clip_deps_available() -> bool:
    try:
        import flask  # noqa: F401
        import flask_cors  # noqa: F401
        return True
    except ImportError:
        return False


def ensure_clip_dependencies(argv: list[str]) -> bool:
    """Install flask + flask-cors via pip if missing. Returns True if importable afterward."""
    if clip_deps_available():
        return True
    if "--no-clips" in argv:
        return False
    if os.environ.get("SW_SKIP_CLIP_INSTALL", "").strip().lower() in ("1", "true", "yes"):
        log("  Clip deps missing; auto-install skipped (SW_SKIP_CLIP_INSTALL).")
        return False
    log("  Clip server dependencies missing — installing flask flask-cors …")
    log("  (one-time; requires network)")
    import subprocess
    cmds = [
        [sys.executable, "-m", "pip", "install", "--user", "flask", "flask-cors"],
        [sys.executable, "-m", "pip", "install", "flask", "flask-cors"],
    ]
    last_err = None
    for cmd in cmds:
        try:
            log("  Running: " + " ".join(cmd))
            subprocess.check_call(cmd)
            # Clear cached failed imports if any
            for mod in ("flask", "flask_cors"):
                sys.modules.pop(mod, None)
            if clip_deps_available():
                log("  Clip dependencies installed.")
                return True
        except Exception as e:
            last_err = e
            log(f"  Install attempt failed: {e}")
    log("  Could not install clip dependencies automatically.")
    if last_err:
        log(f"  Last error: {last_err}")
    log("  Manual fix:  python -m pip install flask flask-cors")
    log("  Also install ffmpeg and ensure it is on PATH.")
    return False


def want_clip_server(argv: list[str]) -> bool:
    if "--no-clips" in argv:
        return False
    if "--with-clips" in argv:
        return True
    env = os.environ.get("SW_WITH_CLIPS", "").strip().lower()
    if env in ("0", "false", "no"):
        return False
    if env in ("1", "true", "yes"):
        return True
    # Default: try to run clip server (install deps if needed)
    return True


def start_clip_server_if_requested(argv: list[str]) -> None:
    if "--no-clips" in argv or os.environ.get("SW_WITH_CLIPS", "").strip().lower() in ("0", "false", "no"):
        log("  Clip server skipped (--no-clips / SW_WITH_CLIPS=0).")
        return
    if not ensure_clip_dependencies(argv):
        log("  Clip server skipped (dependencies unavailable). Auto-Clip Connect will show install help.")
        return
    # Warn if ffmpeg missing (clips still need it)
    try:
        import shutil
        if not shutil.which("ffmpeg"):
            log("  Warning: ffmpeg not found on PATH — clip cutting will fail until it is installed.")
    except Exception:
        pass
    os.environ["SW_ROOT"] = str(ROOT)
    try:
        sys.path.insert(0, str(ROOT))
        import clip_server  # type: ignore
        ok, msg = clip_server.start_background()
        if ok:
            log(f"  {msg}")
            log(f"  SW Admin → Auto-Clip: Connect (http://localhost:{CLIP_PORT})")
        else:
            log(f"  Clip server not started: {msg}")
    except Exception as e:
        log(f"  Clip server not started: {e}")


def serve() -> None:
    path = html_path()
    if not path.is_file():
        log("")
        log(f"  ERROR: {HTML_NAME} (or {HTML_FALLBACK_NAME}) not found in:")
        log(f"  {ROOT}")
        log("")
        log("  Put index.html here, or publish a GitHub Release with that file attached.")
        log("")
        input("  Press Enter to exit…")
        sys.exit(1)

    name = path.name
    ver = read_local_version() or str(int(time.time()))
    ver_q = ver.replace(" ", "_")
    open_url = f"http://localhost:{PORT}/{name}?v={ver_q}"

    log("")
    log("  Strategic Wrestler")
    log("  ------------------")
    log(f"  Folder: {ROOT}")
    log(f"  File:   {path} ({path.stat().st_size} bytes)")
    log(f"  URL:    {open_url}")
    log(f"  AI Library (clips): {ROOT / 'AI Library' / 'Clips'}")
    log("")
    log("  Keep this window open while you use the program.")
    log("  Close this window when you are finished.")
    log("")

    os.chdir(ROOT)
    log(f"  Starting local server on port {PORT} …")
    try:
        from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
        import threading

        class NoCacheHandler(SimpleHTTPRequestHandler):
            extensions_map = {
                **getattr(SimpleHTTPRequestHandler, "extensions_map", {}),
                ".html": "text/html; charset=utf-8",
                ".htm": "text/html; charset=utf-8",
                ".js": "application/javascript",
                ".json": "application/json",
                ".css": "text/css",
            }

            def end_headers(self):
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                super().end_headers()

            def log_message(self, fmt, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", PORT), NoCacheHandler)

        def _open_browser():
            time.sleep(0.4)
            try:
                webbrowser.open(open_url)
            except Exception:
                pass

        threading.Thread(target=_open_browser, daemon=True).start()

        log("  Server running.")
        log("  If the page looks old: hard-refresh (Ctrl+Shift+R) or open:")
        log(f"    {open_url}")
        log("")
        server.serve_forever()
    except OSError as e:
        log(f"  Could not bind port {PORT}: {e}")
        log("  Is another copy of SW already running? Close it, or change PORT in update_and_serve.py.")
        input("  Press Enter to exit…")
        sys.exit(1)
    except KeyboardInterrupt:
        log("\n  Server stopped.")


def main() -> None:
    skip = "--offline" in sys.argv or "-o" in sys.argv
    log("")
    log("  Strategic Wrestler launcher")
    log("  ---------------------------")
    check_and_update(skip=skip)
    start_clip_server_if_requested(sys.argv)
    serve()


if __name__ == "__main__":
    main()
