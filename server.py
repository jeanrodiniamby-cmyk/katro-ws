# server.py
import asyncio, json, secrets, os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
import uvicorn

app = FastAPI()
rooms = {}  # code -> {"a": ws1 or None, "b": ws2 or None}

@app.get("/")
def health(): return PlainTextResponse("ok")

def new_code():
    return secrets.token_hex(2).upper()  # ex: 'A3F1' (4 hex)

async def send(ws, type_, **data):
    await ws.send_text(json.dumps({"type": type_, **data}))

async def broadcast(code, msg):
    for k in ("a", "b"):
        ws = rooms[code].get(k)
        if ws:
            try: await ws.send_text(msg)
            except: pass
 
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    role = None; code = None
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)

            t = msg.get("type")
            if t == "create_room":
                # créer room
                code = new_code()
                while code in rooms:
                    code = new_code()
                rooms[code] = {"a": ws, "b": None}
                role = "a"
                await send(ws, "room_created", code=code, role=role)

            elif t == "join_room":
                code = msg.get("code", "").upper()
                if code not in rooms or (rooms[code]["a"] and rooms[code]["b"]):
                    await send(ws, "error", reason="room_unavailable")
                    continue
                spot = "a" if rooms[code]["a"] is None else "b"
                rooms[code][spot] = ws
                role = spot
                await send(ws, "room_joined", code=code, role=role)
                # prévenir l'autre
                await broadcast(code, json.dumps({"type": "peer_joined"}))
                
                # server.py (dans join_room, juste avant le broadcast start)
                if rooms[code]["a"] and rooms[code]["b"]:
                    print(f"[SERVER] start -> room {code}")   # <--- log debug
                    await broadcast(code, json.dumps({"type": "start"}))
                
                # start quand 2 présents
                if rooms[code]["a"] and rooms[code]["b"]:
                    await broadcast(code, json.dumps({"type":"start"}))

            elif t in ("move", "chat", "ping"):
                if not code: continue
                await broadcast(code, raw)

            elif t == "leave":
                break
    except WebSocketDisconnect:
        pass
    finally:
        # nettoyage
        if code and code in rooms:
            for k in ("a","b"):
                if rooms[code].get(k) is ws:
                    rooms[code][k] = None
            if not rooms[code]["a"] and not rooms[code]["b"]:
                rooms.pop(code, None)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8765"))
    uvicorn.run(app, host="0.0.0.0", port=8765)
