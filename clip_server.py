#!/usr/bin/env python3
"""
Strategic Wrestler — local Auto-Clip server (Flask on 127.0.0.1:5057).

Writes clips under the SW data folder:
  <launcher folder>/AI Library/Clips/<match_folder>/<event>.mp4
  <launcher folder>/AI Library/labels/training_data.jsonl

Requires: pip install flask flask-cors
Requires on PATH: ffmpeg

Started by update_and_serve.py (optional) or standalone:
  python clip_server.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

CLIP_PORT = 5057

# Set by launcher before import, or defaults to this file's parent
ROOT = Path(os.environ.get("SW_ROOT", Path(__file__).resolve().parent))
AI_LIBRARY = ROOT / "AI Library"
CLIPS_DIR = AI_LIBRARY / "Clips"
LABELS_DIR = AI_LIBRARY / "labels"
JSONL_FILE = LABELS_DIR / "training_data.jsonl"

_server = None
_thread = None


def ensure_dirs() -> None:
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    LABELS_DIR.mkdir(parents=True, exist_ok=True)


def create_app():
    try:
        from flask import Flask, request, jsonify
        from flask_cors import CORS
    except ImportError as e:
        raise ImportError(
            "flask and flask-cors are required for the clip server. "
            "Run:  pip install flask flask-cors"
        ) from e

    app = Flask(__name__)
    CORS(app)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "running",
            "output_dir": str(AI_LIBRARY),
            "clips_dir": str(CLIPS_DIR),
            "port": CLIP_PORT,
        }), 200

    @app.route("/clip", methods=["POST"])
    def clip_match():
        if "manifest" not in request.form:
            return jsonify({"error": "No manifest provided"}), 400
        try:
            manifest = json.loads(request.form["manifest"])
        except Exception as e:
            return jsonify({"error": "Invalid manifest JSON: " + str(e)}), 400

        ensure_dirs()
        folder_name = (
            manifest.get("clip_folder_name")
            or manifest.get("match_id")
            or "match"
        )
        # Keep folder names filesystem-safe
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in str(folder_name))[:120]
        target_folder = CLIPS_DIR / (safe or "match")
        target_folder.mkdir(parents=True, exist_ok=True)

        source_video_path = None
        temp_video_path = None
        if "video" in request.files:
            video_file = request.files["video"]
            name = video_file.filename or "upload.mp4"
            temp_video_path = AI_LIBRARY / f"temp_{os.getpid()}_{name}"
            video_file.save(str(temp_video_path))
            source_video_path = temp_video_path

        if not source_video_path or not source_video_path.exists():
            return jsonify({
                "error": "Source video file required to cut clips "
                         "(YouTube-only matches are not supported by this server yet)."
            }), 400

        clips_written = 0
        written_paths = []
        events = manifest.get("events") or []

        with open(JSONL_FILE, "a", encoding="utf-8") as jsonl_f:
            for i, ev in enumerate(events):
                if not isinstance(ev, dict):
                    continue
                start = ev.get("clip_start_sec")
                end = ev.get("clip_end_sec")
                if start is None:
                    continue
                start = float(start)
                end = float(end if end is not None else start + 5.5)
                duration = max(0.5, end - start)
                event_id = ev.get("event_id") or f"clip_{i:03d}"
                safe_id = "".join(c if c.isalnum() or c in "-_." else "_" for c in str(event_id))[:80]
                clip_filename = f"{safe_id}.mp4"
                clip_path = target_folder / clip_filename

                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start),
                    "-i", str(source_video_path),
                    "-t", str(duration),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-c:a", "aac",
                    str(clip_path),
                ]
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if res.returncode == 0 and clip_path.exists():
                    clips_written += 1
                    rel = f"Clips/{target_folder.name}/{clip_filename}"
                    written_paths.append(rel)
                    label_data = {
                        "move": ev.get("move"),
                        "category": ev.get("category"),
                        "direction": ev.get("direction"),
                        "actor": ev.get("actor"),
                        "outcome": ev.get("outcome"),
                        "points": ev.get("points"),
                        "detail": ev.get("detail", ""),
                        "tie": ev.get("tie", ""),
                        "period": ev.get("period", ""),
                    }
                    entry = {
                        "videos": [rel],
                        "messages": [
                            {
                                "role": "user",
                                "content": [{
                                    "type": "text",
                                    "text": "Identify the wrestling move in this sequence of frames, "
                                            "whether it succeeded, and any points scored. "
                                            "Respond with a single JSON object.",
                                }],
                            },
                            {
                                "role": "assistant",
                                "content": [{"type": "text", "text": json.dumps(label_data)}],
                            },
                        ],
                    }
                    jsonl_f.write(json.dumps(entry) + "\n")

        if temp_video_path and temp_video_path.exists():
            try:
                os.remove(temp_video_path)
            except OSError:
                pass

        # Human-readable per-match dump
        try:
            meta_path = LABELS_DIR / f"{safe or 'match'}.json"
            meta_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        except OSError:
            pass

        return jsonify({
            "status": "success",
            "clips_written": clips_written,
            "clips": written_paths,
            "clips_dir": str(target_folder),
        }), 200

    @app.route("/clip/file", methods=["GET"])
    def clip_file():
        """Serve a clip file for SW to mirror to Google Drive. Query: rel=Clips/.../file.mp4"""
        from flask import send_file, abort
        rel = (request.args.get("rel") or "").replace("\\", "/").lstrip("/")
        if not rel or ".." in rel.split("/"):
            return jsonify({"error": "invalid rel"}), 400
        # Allow Clips/ or labels/ under AI Library
        path = (AI_LIBRARY / rel).resolve()
        try:
            path.relative_to(AI_LIBRARY.resolve())
        except ValueError:
            return jsonify({"error": "path outside AI Library"}), 403
        if not path.is_file():
            return jsonify({"error": "not found", "path": str(path)}), 404
        return send_file(path, mimetype="video/mp4" if path.suffix.lower() == ".mp4" else None, as_attachment=False)

    @app.route("/clips/<path:match_id>", methods=["DELETE"])
    def delete_clips(match_id):
        ensure_dirs()
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in str(match_id))[:120]
        # Best-effort: remove folder if present under Clips
        removed = 0
        for folder in CLIPS_DIR.glob("*"):
            if not folder.is_dir():
                continue
            if safe in folder.name or folder.name == safe:
                for f in folder.glob("*.mp4"):
                    try:
                        f.unlink()
                        removed += 1
                    except OSError:
                        pass
                try:
                    folder.rmdir()
                except OSError:
                    pass
        return jsonify({"status": "ok", "removed": removed}), 200

    @app.route("/clip/delete", methods=["POST"])
    def clip_delete():
        data = request.get_json(silent=True) or {}
        mid = data.get("match_id") or data.get("id") or ""
        if not mid:
            return jsonify({"error": "match_id required"}), 400
        return delete_clips(mid)

    return app


def run_server_blocking() -> None:
    ensure_dirs()
    app = create_app()
    app.run(host="127.0.0.1", port=CLIP_PORT, debug=False, use_reloader=False)


def start_background() -> tuple[bool, str]:
    """Start Flask on 5057 in a daemon thread. Returns (ok, message)."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return True, f"Clip server already running on port {CLIP_PORT}"
    try:
        ensure_dirs()
        app = create_app()
    except ImportError as e:
        return False, str(e)
    except Exception as e:
        return False, "Clip server failed to initialize: " + str(e)

    def _run():
        try:
            # use_reloader=False required in a thread
            app.run(host="127.0.0.1", port=CLIP_PORT, debug=False, use_reloader=False, threaded=True)
        except OSError as e:
            print(f"  Clip server could not bind port {CLIP_PORT}: {e}", flush=True)
        except Exception as e:
            print(f"  Clip server error: {e}", flush=True)

    _thread = threading.Thread(target=_run, name="sw-clip-server", daemon=True)
    _thread.start()
    return True, (
        f"Clip server starting on http://127.0.0.1:{CLIP_PORT}  "
        f"(clips → {CLIPS_DIR})"
    )


if __name__ == "__main__":
    print(f"Strategic Wrestler clip server")
    print(f"  AI Library: {AI_LIBRARY}")
    print(f"  Clips:      {CLIPS_DIR}")
    print(f"  URL:        http://127.0.0.1:{CLIP_PORT}/health")
    run_server_blocking()
