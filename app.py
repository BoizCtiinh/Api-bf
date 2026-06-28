from flask import Flask, request, jsonify
import time

app = Flask(__name__)

# ============================================================
#  CONFIG
# ============================================================
API_SECRET = "blox_secret_2026"  # <-- đổi thành chuỗi bí mật của bạn
DATA_TTL   = 300  # giây

# ============================================================
#  STORAGE
# ============================================================
VALID_EVENTS = [
    "darkbeard", "dough-king", "cursed-captain", "rip-indra",
    "soul-reaper", "mirage", "cake-prince", "raid-castle",
    "cake-queen", "full-moon", "sword", "haki", "berry",
]

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
        "jobid":      e["jobid"],
        "players":    e["players"],
        "name":       e["name"],
        "source":     e["source"],
        "expires_in": max(0, int(e["expires_at"] - now_ts())),
    }

# ============================================================
#  POST /push  — tool gửi data lên đây
# ============================================================
@app.route("/push", methods=["POST"])
def push():
    # Auth
    if request.headers.get("X-Secret") != API_SECRET:
        return jsonify({"error": "Unauthorized"}), 401

    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Invalid JSON"}), 400

    event = body.get("event", "").strip()
    jobid = body.get("jobid", "").strip()
    players = int(body.get("players", 0))
    name  = body.get("name", event).strip()
    source = body.get("source", "unknown").strip()

    if event not in VALID_EVENTS:
        return jsonify({"error": f"Unknown event: {event}"}), 400
    if not jobid:
        return jsonify({"error": "Missing jobid"}), 400

    is_new = jobid not in store[event]
    store[event][jobid] = {
        "jobid":      jobid,
        "players":    players,
        "name":       name,
        "source":     source,
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
        "status": "online",
        "endpoints": [f"/{e}" for e in VALID_EVENTS],
        "live_counts": {k: len(v) for k, v in store.items() if v},
    })

@app.route("/<event>")
def get_event(event):
    if event not in VALID_EVENTS:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "event":   event,
        "servers": [fmt(e) for e in get_live(event)],
    })

if __name__ == "__main__":
    app.run(debug=False)