from flask import Flask, request, jsonify
import time

app = Flask(__name__)

# ============================================================
#  CONFIG
# ============================================================
API_SECRET = "blox_secret_2026"  # <-- đổi thành chuỗi bí mật của bạn
DATA_TTL   = 300  # giây

VALID_EVENTS = [
    "darkbeard", "dough-king", "cursed-captain", "rip-indra",
    "soul-reaper", "mirage", "cake-prince", "raid-castle",
    "cake-queen", "tyrant-of-the-skies", "full-moon",
    "sword", "haki", "berry",
]

# ============================================================
#  STORAGE
# ============================================================
store: dict[str, dict] = {k: {} for k in VALID_EVENTS}

def now_ts():
    return time.time()

def purge_expired():
    ts = now_ts()
    for key in store:
        expired = [jid for jid, v in store[key].items() if v["expires_at"] < ts]
        for jid in expired:
            del store[key][jid]

def get_live(event_key: str):
    purge_expired()
    return list(store.get(event_key, {}).values())

def fmt(e: dict):
    return {
        "Players": e["players"],
        "jobid":   e["jobid"],
        "name":    e["name"],
    }

# ============================================================
#  POST /push  — tool gửi data lên đây
# ============================================================
@app.route("/push", methods=["POST"])
def push():
    if request.headers.get("X-Secret") != API_SECRET:
        return jsonify({"error": "Unauthorized"}), 401

    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Invalid JSON"}), 400

    event   = body.get("event", "").strip().lower()
    jobid   = body.get("jobid", "").strip()
    players = int(body.get("players", 0))
    name    = body.get("name", event).strip()

    if event not in VALID_EVENTS:
        return jsonify({"error": f"Unknown event: {event}"}), 400
    if not jobid:
        return jsonify({"error": "Missing jobid"}), 400

    is_new = jobid not in store[event]
    store[event][jobid] = {
        "jobid":      jobid,
        "players":    players,
        "name":       name,
        "expires_at": now_ts() + DATA_TTL,
    }

    return jsonify({"ok": True, "new": is_new, "event": event}), 200

# ============================================================
#  GET endpoints
# ============================================================
@app.route("/")
def root():
    purge_expired()
    return jsonify({
        "source":  "BloxMonitor",
        "success": True,
        "events":  VALID_EVENTS,
        "live_counts": {k: len(v) for k, v in store.items() if v},
    })

@app.route("/<path:event>")
def get_event(event):
    event = event.lower()
    if event not in VALID_EVENTS:
        return jsonify({"error": "Not found"}), 404
    data = get_live(event)
    return jsonify({
        "source":  "BloxMonitor",
        "success": True,
        "total":   len(data),
        "count":   len(data),
        "data":    [fmt(e) for e in data],
    })

if __name__ == "__main__":
    app.run(debug=False)