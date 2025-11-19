import asyncio
import json
import secrets
import os
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
import uvicorn

app = FastAPI()

# ========= Parties classiques (rooms de jeu 1v1) ========= #

# code -> {
#   "a": ws ou None,
#   "b": ws ou None,
#   "names": {"a": str|None, "b": str|None}
# }
rooms = {}

# ========= Lobby (joueurs en ligne) ========= #

# Joueurs connectés au lobby.
#   lobby_users[user_id] = {
#       "id": user_id,
#       "name": str,
#       "status": str,
#       "avatar": str,   # ex: "avatar_01"
#   }
lobby_users: dict[str, dict] = {}

# Mapping websocket -> user_id
ws_to_user_id: dict[WebSocket, str] = {}


@app.get("/")
def health():
    return PlainTextResponse("ok")


def new_code() -> str:
    """Génère un code de salle, ex: 'A3F1' (4 hex)."""
    return secrets.token_hex(2).upper()


async def send(ws: WebSocket, type_, **data):
    """Helper pour envoyer un message typé à un client de partie."""
    await ws.send_text(json.dumps({"type": type_, **data}))


async def broadcast(code: str, msg: str):
    """Broadcast dans une salle de jeu (partie à 2)."""
    for k in ("a", "b"):
        ws = rooms[code].get(k)
        if ws:
            try:
                await ws.send_text(msg)
            except Exception:
                pass


async def lobby_broadcast(payload: dict, exclude: Optional[WebSocket] = None):
    """
    Broadcast d'un message de lobby (presence_delta, etc.)
    à tous les joueurs du lobby, sauf éventuellement `exclude`.
    """
    raw = json.dumps(payload)
    for ws in list(ws_to_user_id.keys()):
        if exclude is not None and ws is exclude:
            continue
        try:
            await ws.send_text(raw)
        except Exception:
            # on ignore les erreurs réseau ponctuelles
            pass


async def send_presence_snapshot_to(ws: WebSocket):
    """
    Envoie à un websocket le snapshot complet des autres joueurs du lobby.
    On exclut le joueur lui-même de la liste et on lui donne son your_id.
    """
    user_id = ws_to_user_id.get(ws)
    if not user_id:
        # pas encore enregistré, rien à envoyer
        return

    others = [u for uid, u in lobby_users.items() if uid != user_id]
    snapshot = {
        "type": "presence_snapshot",
        "your_id": user_id,  # permet au client de savoir qui il est
        "users": others,
    }
    await ws.send_text(json.dumps(snapshot))


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
                avatar = msg.get("avatar") or "avatar_01"

                existing_id = ws_to_user_id.get(ws)
                is_new = existing_id is None
                user_id = existing_id or secrets.token_hex(4)

                # Enregistrer / mettre à jour l'utilisateur
                user = {
                    "id": user_id,
                    "name": name,
                    "status": "dispo",  # tu pourras gérer AFK, occupé, etc. plus tard
                    "avatar": avatar,
                }
                lobby_users[user_id] = user
                ws_to_user_id[ws] = user_id

                # 1) envoyer au client un snapshot des AUTRES
                await send_presence_snapshot_to(ws)

                # 2) prévenir les autres joueurs du lobby de l'arrivée / mise à jour
                delta = {
                    "type": "presence_delta",
                    "added": [user] if is_new else [],
                    "removed": [],
                    "updated": [] if is_new else [user],
                }
                await lobby_broadcast(delta, exclude=ws)

            elif t == "lobby_goodbye":
                # Le client quitte volontairement le lobby
                user_id = ws_to_user_id.pop(ws, None)
                if user_id:
                    user = lobby_users.pop(user_id, None)
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

                joiner_name = (
                    msg.get("name") or ("J2" if spot == "b" else "J1")
                )[:20]
                rooms[code]["names"][spot] = joiner_name

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
                                "names": rooms[code]["names"],
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
        # déconnexion "normale" / réseau
        pass
    finally:
        # ---------- Nettoyage lobby ----------
        user_id = ws_to_user_id.pop(ws, None)
        if user_id:
            user = lobby_users.pop(user_id, None)
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
