import asyncio
import aiohttp
import time
from datetime import datetime, timezone
from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn

# ============================================================
#  CẤU HÌNH
# ============================================================
DISCORD_TOKEN = "MTExNTYzOTAzNjA5NTI1NDYwMA.Gxsxjt.WLzNTI7_2QH6wnb7nahbBJmAqNGQHyW9PWo3wU"

WEBHOOKS = {
    "boss":        "https://discord.com/api/webhooks/1520778925503021076/cIPa6rjOlNCAok29IPzoULQu7huFom_pAirhFT3X-jDzlazfJreXs_4RryiDtG2V_t_S",
    "sword":       "https://discord.com/api/webhooks/1520778964006604870/lS1ASgoNrRBZRUHmRlmRCehpgmvhWskw6iLXAgMkacBMOD6iPWdc4HbYANVXY2W4obko",
    "full-moon":   "https://discord.com/api/webhooks/1520779034680885389/YurQiOT8qOkVyj_zX9ySQkxKT5MNIkY8NqTyr4bXpr0gq9SodWV6tDkXWVmngZUydaU4",
    "mirage":      "https://discord.com/api/webhooks/1520779062799241257/Kj93On6FhjdP7MAU62lwwBFNSrkGPXcH7kdMFrdx9_kGtHN_J_x7J1oaQWZbI-JvAtoe",
    "haki":        "https://discord.com/api/webhooks/1520779085469716651/ie_xZ3YK74V3uuuqZaFUnDa6ccie2HOasTwzPkDE8XSoi1oNGfbT1-F4fOOGWut4KAE8",
    "raid-castle": "https://discord.com/api/webhooks/1520779120475377734/PkMfJrdim5KiNjpgYas77dkRPO0yDiGHUI4Ka3lRh_ja0BjEWoy5aEef7uIFv1OmV40y",
}

DATA_TTL = 300  # giây

ROBLOX_HEADERS = {
    "User-Agent": "Roblox/WinInet",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate",
}

DISCORD_HEADERS = {
    "Authorization": DISCORD_TOKEN,
    "Content-Type": "application/json",
}

# --- Banana-hub APIs ---
BOSS_APIS = {
    "darkbeard":      "https://raw.banana-hub.xyz/api/data/recent?name=Darkbeard&limit=100",
    "dough-king":     "https://raw.banana-hub.xyz/api/data/recent?name=Dough%20King&limit=100",
    "cursed-captain": "https://raw.banana-hub.xyz/api/data/recent?name=Cursed%20Captain&limit=100",
    "rip-indra":      "https://raw.banana-hub.xyz/api/data/recent?name=Rip%20Indra&limit=100",
    "soul-reaper":    "https://raw.banana-hub.xyz/api/data/recent?name=Soul%20Reaper&limit=100",
    "mirage":         "https://raw.banana-hub.xyz/api/data/recent?name=Mirage&limit=100",
    "cake-prince":    "https://raw.banana-hub.xyz/api/data/recent?name=Cake%20Prince&limit=100",
    "raid-castle":    "https://raw.banana-hub.xyz/api/data/recent?name=Raid%20Castle&limit=100",
    "cake-queen":     "https://raw.banana-hub.xyz/api/data/recent?name=Cake%20Queen&limit=100",
    "full-moon":      "https://raw.banana-hub.xyz/api/data/recent?name=FullMoon&limit=100",
}

# Discord channels theo nhóm
DISCORD_CHANNELS = {
    "boss":      ["1483394002567827521", "1197504846459310161"],
    "mirage":    ["1085601317717811200", "1483394041231183903"],
    "sword":     ["1483396203180851401", "1144623714663682138"],
    "full-moon": ["1085601598555832400", "1483394231392272467"],
    "haki":      ["1088023824555053097", "1520220748805964058"],
    "berry":     ["1520220511823466686"],
}

# Map tên embed -> event_key
EMBED_NAME_MAP = {
    "darkbeard":            "darkbeard",
    "dough king":           "dough-king",
    "cursed captain":       "cursed-captain",
    "rip_indra":            "rip-indra",
    "rip indra":            "rip-indra",
    "soul reaper":          "soul-reaper",
    "mysticisland":         "mirage",
    "mirage":               "mirage",
    "tyrant of the skies":  "cake-prince",   # Cake Prince alias
    "cake prince":          "cake-prince",
    "cake queen":           "cake-queen",
    "shizu":                "sword",
    "oroshi":               "sword",
    "saishi":               "sword",
    "full moon":            "full-moon",
    "fullmoon":             "full-moon",
}

BOSS_GROUP = ["darkbeard", "dough-king", "rip-indra", "soul-reaper",
              "cake-prince", "cake-queen", "cursed-captain"]

def get_webhook_group(event_key: str) -> str:
    if event_key in BOSS_GROUP:
        return "boss"
    return event_key  # mirage, full-moon, raid-castle, sword, haki, berry

def resolve_event_key(name: str, group_key: str) -> str:
    """Dùng EMBED_NAME_MAP để xác định event_key chính xác từ tên embed."""
    nl = name.lower().strip()
    for keyword, key in EMBED_NAME_MAP.items():
        if keyword in nl:
            return key
    return group_key  # fallback về nhóm

# ============================================================
#  STORAGE
# ============================================================
ALL_KEYS = list(BOSS_APIS.keys()) + list(DISCORD_CHANNELS.keys())
store: dict[str, dict] = {key: {} for key in ALL_KEYS}

def now_ts():
    return time.time()

def add_entry(event_key: str, jobid: str, players: int, name: str, source: str):
    if event_key not in store:
        store[event_key] = {}
    store[event_key][jobid] = {
        "jobid":      jobid,
        "players":    players,
        "name":       name,
        "source":     source,
        "expires_at": now_ts() + DATA_TTL,
    }

def purge_expired():
    ts = now_ts()
    for key in store:
        expired = [jid for jid, v in store[key].items() if v["expires_at"] < ts]
        for jid in expired:
            del store[key][jid]

def get_live(event_key: str):
    purge_expired()
    return list(store.get(event_key, {}).values())

# ============================================================
#  COLORS
# ============================================================
COLORS = {
    "darkbeard":      0x2C2F33,
    "dough-king":     0xFF69B4,
    "cursed-captain": 0x1ABC9C,
    "rip-indra":      0xE74C3C,
    "soul-reaper":    0x9B59B6,
    "mirage":         0x3498DB,
    "cake-prince":    0xF9A8D4,
    "raid-castle":    0xF4A81D,
    "cake-queen":     0xFF1493,
    "full-moon":      0xF1C40F,
    "sword":          0x95A5A6,
    "haki":           0xD4AC0D,
    "berry":          0x2ECC71,
}

# ============================================================
#  SEND WEBHOOK
# ============================================================
async def send_webhook(session: aiohttp.ClientSession, event_key: str, jobid: str, players: int, name: str):
    group  = get_webhook_group(event_key)
    wh_url = WEBHOOKS.get(group)
    if not wh_url:
        return

    now   = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    color = COLORS.get(event_key, 0x5865F2)
    payload = {
        "embeds": [{
            "title":  f"🆕 {name}",
            "color":  color,
            "fields": [
                {"name": "👥 Players", "value": str(players), "inline": True},
                {"name": "📂 Event",   "value": event_key,    "inline": True},
                {"name": "🆔 Job ID",  "value": f"```{jobid}```", "inline": False},
            ],
            "footer":    {"text": "Blox Monitor"},
            "timestamp": now,
        }]
    }
    try:
        async with session.post(wh_url, json=payload) as r:
            if r.status not in (200, 204):
                print(f"[Webhook] ❌ Lỗi {r.status} | group={group} event={event_key}")
    except Exception as e:
        print(f"[Webhook] ❌ Exception: {e}")

# ============================================================
#  DISCORD LOGIN CHECK
# ============================================================
async def check_discord_login(session: aiohttp.ClientSession) -> bool:
    try:
        async with session.get("https://discord.com/api/v10/users/@me", headers=DISCORD_HEADERS) as r:
            if r.status == 200:
                data = await r.json()
                username = data.get("username", "unknown")
                uid      = data.get("id", "?")
                print(f"[Discord] ✅ Đăng nhập thành công! Username: {username} | ID: {uid}")
                return True
            else:
                print(f"[Discord] ❌ Đăng nhập thất bại! Status: {r.status}")
                return False
    except Exception as e:
        print(f"[Discord] ❌ Lỗi kết nối khi login: {e}")
        return False

# ============================================================
#  MONITOR BANANA-HUB
# ============================================================
async def monitor_banana(session: aiohttp.ClientSession):
    seen: dict[str, set] = {k: set() for k in BOSS_APIS}

    for key, url in BOSS_APIS.items():
        try:
            async with session.get(url, headers=ROBLOX_HEADERS) as r:
                if r.status == 200:
                    resp = await r.json(content_type=None)
                    data = resp.get("data", []) if isinstance(resp, dict) else resp
                    seen[key] = {s["jobid"] for s in data}
        except:
            pass
    print(f"[Banana] ✅ Preload xong {len(BOSS_APIS)} events")

    while True:
        await asyncio.sleep(5)
        for key, url in BOSS_APIS.items():
            try:
                async with session.get(url, headers=ROBLOX_HEADERS) as r:
                    if r.status != 200:
                        continue
                    resp = await r.json(content_type=None)
                    data = resp.get("data", []) if isinstance(resp, dict) else resp
                    for s in data:
                        jid = s["jobid"]
                        if jid not in seen[key]:
                            seen[key].add(jid)
                            players = s.get("Players", 0)
                            name    = s.get("name", key)
                            add_entry(key, jid, players, name, "banana-hub")
                            print(f"[Banana] 🆕 {key} | {players}p | {jid[:25]}...")
                            await send_webhook(session, key, jid, players, name)
            except Exception as e:
                print(f"[Banana] ❌ Lỗi {key}: {e}")

# ============================================================
#  PARSE EMBED
# ============================================================
def parse_embed(embed: dict, group_key: str) -> tuple | None:
    jobid, players, name = None, 0, group_key

    if embed.get("title"):
        name = embed["title"]

    for field in embed.get("fields", []):
        fname = field.get("name", "").lower()
        fval  = field.get("value", "").strip().strip("`").strip()
        if any(k in fname for k in ["job", "jobid", "id"]):
            jobid = fval
        elif any(k in fname for k in ["player", "count", "online"]):
            try:
                players = int("".join(filter(str.isdigit, fval)))
            except:
                pass
        elif any(k in fname for k in ["name", "event", "boss"]):
            name = fval

    if not jobid and embed.get("description"):
        for line in embed["description"].split("\n"):
            ll = line.lower()
            if "jobid" in ll or "job id" in ll:
                parts = line.split(":")
                if len(parts) > 1:
                    jobid = parts[1].strip().strip("`")
            elif "player" in ll:
                try:
                    players = int("".join(filter(str.isdigit, line)))
                except:
                    pass

    return (jobid, players, name) if jobid else None

# ============================================================
#  MONITOR DISCORD CHANNELS
# ============================================================
async def poll_channel(session: aiohttp.ClientSession, channel_id: str, group_key: str, seen_msgs: set):
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=50"
    try:
        async with session.get(url, headers=DISCORD_HEADERS) as r:
            if r.status == 401:
                print(f"[Discord] ❌ Unauthorized channel {channel_id} - token không hợp lệ")
                return
            if r.status == 403:
                print(f"[Discord] ❌ Không có quyền đọc channel {channel_id}")
                return
            if r.status != 200:
                print(f"[Discord] ❌ Lỗi channel {channel_id}: HTTP {r.status}")
                return
            messages = await r.json()
            for msg in messages:
                mid = msg["id"]
                if mid in seen_msgs:
                    continue
                seen_msgs.add(mid)
                for embed in msg.get("embeds", []):
                    result = parse_embed(embed, group_key)
                    if not result:
                        continue
                    jobid, players, name = result
                    event_key = resolve_event_key(name, group_key)
                    add_entry(event_key, jobid, players, name, f"discord:{channel_id}")
                    print(f"[Discord] 🆕 {event_key} | {players}p | {name} | {jobid[:25]}...")
                    await send_webhook(session, event_key, jobid, players, name)
    except Exception as e:
        print(f"[Discord] ❌ Exception ch={channel_id}: {e}")

async def monitor_discord(session: aiohttp.ClientSession):
    # Kiểm tra login trước
    logged_in = await check_discord_login(session)
    if not logged_in:
        print("[Discord] ⚠️  Bỏ qua monitor Discord do không đăng nhập được")
        return

    seen_msgs: dict[str, set] = {
        cid: set()
        for channels in DISCORD_CHANNELS.values()
        for cid in channels
    }

    # Preload message IDs
    preload_count = 0
    for group_key, channels in DISCORD_CHANNELS.items():
        for cid in channels:
            url = f"https://discord.com/api/v10/channels/{cid}/messages?limit=50"
            try:
                async with session.get(url, headers=DISCORD_HEADERS) as r:
                    if r.status == 200:
                        msgs = await r.json()
                        for m in msgs:
                            seen_msgs[cid].add(m["id"])
                        preload_count += 1
                        print(f"[Discord] 📥 Preload channel {cid} ({group_key}): {len(msgs)} tin nhắn")
                    else:
                        print(f"[Discord] ⚠️  Không preload được channel {cid}: HTTP {r.status}")
            except Exception as e:
                print(f"[Discord] ⚠️  Lỗi preload channel {cid}: {e}")

    print(f"[Discord] ✅ Preload xong {preload_count}/{sum(len(v) for v in DISCORD_CHANNELS.values())} channels")

    while True:
        await asyncio.sleep(8)
        for group_key, channels in DISCORD_CHANNELS.items():
            for cid in channels:
                await poll_channel(session, cid, group_key, seen_msgs[cid])

# ============================================================
#  FASTAPI
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    connector = aiohttp.TCPConnector(limit=20)
    session   = aiohttp.ClientSession(connector=connector)
    print("=" * 50)
    print("🚀 Blox Monitor đang khởi động...")
    print("=" * 50)
    asyncio.create_task(monitor_banana(session))
    asyncio.create_task(monitor_discord(session))
    yield
    await session.close()

app = FastAPI(title="Blox Monitor API", lifespan=lifespan)

def fmt(e: dict):
    return {
        "jobid":      e["jobid"],
        "players":    e["players"],
        "name":       e["name"],
        "source":     e["source"],
        "expires_in": max(0, int(e["expires_at"] - now_ts())),
    }

@app.get("/darkbeard")
async def ep_darkbeard():
    return {"event": "darkbeard", "servers": [fmt(e) for e in get_live("darkbeard")]}

@app.get("/dough-king")
async def ep_dough_king():
    return {"event": "dough-king", "servers": [fmt(e) for e in get_live("dough-king")]}

@app.get("/cursed-captain")
async def ep_cursed_captain():
    return {"event": "cursed-captain", "servers": [fmt(e) for e in get_live("cursed-captain")]}

@app.get("/rip-indra")
async def ep_rip_indra():
    return {"event": "rip-indra", "servers": [fmt(e) for e in get_live("rip-indra")]}

@app.get("/soul-reaper")
async def ep_soul_reaper():
    return {"event": "soul-reaper", "servers": [fmt(e) for e in get_live("soul-reaper")]}

@app.get("/mirage")
async def ep_mirage():
    return {"event": "mirage", "servers": [fmt(e) for e in get_live("mirage")]}

@app.get("/cake-prince")
async def ep_cake_prince():
    return {"event": "cake-prince", "servers": [fmt(e) for e in get_live("cake-prince")]}

@app.get("/raid-castle")
async def ep_raid_castle():
    return {"event": "raid-castle", "servers": [fmt(e) for e in get_live("raid-castle")]}

@app.get("/cake-queen")
async def ep_cake_queen():
    return {"event": "cake-queen", "servers": [fmt(e) for e in get_live("cake-queen")]}

@app.get("/full-moon")
async def ep_full_moon():
    return {"event": "full-moon", "servers": [fmt(e) for e in get_live("full-moon")]}

@app.get("/sword")
async def ep_sword():
    return {"event": "sword", "servers": [fmt(e) for e in get_live("sword")]}

@app.get("/haki")
async def ep_haki():
    return {"event": "haki", "servers": [fmt(e) for e in get_live("haki")]}

@app.get("/berry")
async def ep_berry():
    return {"event": "berry", "servers": [fmt(e) for e in get_live("berry")]}

@app.get("/")
async def root():
    purge_expired()
    return {
        "status": "online",
        "endpoints": [
            "/darkbeard", "/dough-king", "/cursed-captain", "/rip-indra",
            "/soul-reaper", "/mirage", "/cake-prince", "/raid-castle",
            "/cake-queen", "/full-moon", "/sword", "/haki", "/berry",
        ],
        "live_counts": {k: len(v) for k, v in store.items() if v},
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
