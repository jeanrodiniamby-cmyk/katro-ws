# server.py
import asyncio, json, secrets, os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
import uvicorn

app = FastAPI()

# --------- Parties classiques (rooms) ----------
rooms = {}  # code -> {"a": ws1 or None, "b": ws2 or None, "names": {"a": str|None, "b": str|None}}

# --------- Lobby (joueurs en ligne) -----------
# clé = WebSocket, valeur = {"id": str, "name": str, "status": str}
lobby_users = {}


@app.get("/")
def health():
    return PlainTextResponse("ok")


def new_code():
    # ex: 'A3F1' (4 hex)
    return secrets.token_hex(2).upper()


async def send(ws: WebSocket, type_, **data):
    """Helper pour envoyer un message typé à un client."""
    await ws.send_text(json.dumps({"type": type_, **data}))


async def broadcast(code: str, msg: str):
    """Broadcast dans une salle (partie à 2)."""
    for k in ("a", "b"):
        ws = rooms[code].get(k)
        if ws:
            try:
                await ws.send_text(msg)
            except Exception:
                pass


async def lobby_broadcast(payload: dict, exclude: WebSocket | None = None):
    """
    Broadcast d'un message de lobby (presence_delta, etc.)
    à tous les joueurs du lobby, sauf éventuellement `exclude`.
    """
    raw = json.dumps(payload)
    for ws in list(lobby_users.keys()):
        if exclude is not None and ws is exclude:
            continue
        try:
            await ws.send_text(raw)
        except Exception:
            # on ignore les erreurs réseau ponctuelles
            pass


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    role = None
    code = None

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            t = msg.get("type")

            # ---------- LOBBY : joueurs en ligne ----------
            if t == "lobby_hello":
                # Un client s'annonce dans le lobby
                name = (msg.get("name") or "Joueur")[:20]

                # Si ce websocket est déjà dans le lobby, on garde le même id
                if ws in lobby_users:
                    uid = lobby_users[ws]["id"]
                else:
                    uid = secrets.token_hex(4)

                user = {
                    "id": uid,
                    "name": name,
                    "status": "dispo",  # tu pourras affiner plus tard
                }
                lobby_users[ws] = user

                # 1) envoyer au client un snapshot complet
                snapshot = {
                    "type": "presence_snapshot",
                    "users": list(lobby_users.values()),
                }
                await ws.send_text(json.dumps(snapshot))

                # 2) prévenir les autres joueurs du lobby de l'arrivée
                delta = {
                    "type": "presence_delta",
                    "added": [user],
                    "removed": [],
                    "updated": [],
                }
                await lobby_broadcast(delta, exclude=ws)

            elif t == "lobby_goodbye":
                # Le client quitte volontairement le lobby
                user = lobby_users.pop(ws, None)
                if user:
                    delta = {
                        "type": "presence_delta",
                        "added": [],
                        "removed": [user],
                        "updated": [],
                    }
                    await lobby_broadcast(delta, exclude=ws)

            # (plus tard tu pourras ajouter lobby_invite / lobby_answer ici)

            # ---------- PARTIES CLASSIQUES ----------
            elif t == "create_room":
                code = new_code()
                while code in rooms:
                    code = new_code()
                # NEW: stocke le nom du créateur (optionnel)
                creator_name = (msg.get("name") or "J1")[:20]
                rooms[code] = {
                    "a": ws,
                    "b": None,
                    "names": {"a": creator_name, "b": None},
                }
                role = "a"
                await send(ws, "room_created", code=code, role=role)

            elif t == "join_room":
                code = (msg.get("code", "") or "").upper()
                if code not in rooms or (rooms[code]["a"] and rooms[code]["b"]):
                    await send(ws, "error", reason="room_unavailable")
                    continue

                spot = "a" if rooms[code]["a"] is None else "b"
                rooms[code][spot] = ws

                # NEW: stocke le nom du joueur qui rejoint
                joiner_name = (
                    msg.get("name") or ("J2" if spot == "b" else "J1")
                )[:20]
                rooms[code]["names"][spot] = joiner_name  # NEW

                role = spot
                await send(ws, "room_joined", code=code, role=role)

                # prévenir l'autre
                await broadcast(code, json.dumps({"type": "peer_joined"}))

                # start quand 2 présents: inclure les noms
                if rooms[code]["a"] and rooms[code]["b"]:
                    await broadcast(
                        code,
                        json.dumps(
                            {
                                "type": "start",
                                "names": rooms[code]["names"],  # NEW
                            }
                        ),
                    )

            elif t in ("move", "chat", "ping"):
                if not code:
                    continue
                await broadcast(code, raw)

            elif t == "leave":
                # côté client on ferme la partie
                break

    except WebSocketDisconnect:
        # déconnexion "normale"
        pass
    finally:
        # ---------- Nettoyage lobby ----------
        user = lobby_users.pop(ws, None)
        if user:
            delta = {
                "type": "presence_delta",
                "added": [],
                "removed": [user],
                "updated": [],
            }
            # on informe les autres qu'il a quitté le lobby
            await lobby_broadcast(delta, exclude=ws)

        # ---------- Nettoyage rooms ----------
        if code and code in rooms:
            for k in ("a", "b"):
                if rooms[code].get(k) is ws:
                    rooms[code][k] = None
            if not rooms[code]["a"] and not rooms[code]["b"]:
                rooms.pop(code, None)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8765"))
    uvicorn.run(app, host="0.0.0.0", port=port)
