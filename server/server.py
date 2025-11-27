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
rooms: dict[str, dict] = {}

# NOUVEAU : mapping websocket -> code de salle
ws_to_room_code: dict[WebSocket, str] = {}

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
    if code not in rooms:
        return
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


def get_ws_by_user_id(user_id: str) -> Optional[WebSocket]:
    """Retrouve le WebSocket correspondant à un user_id du lobby."""
    for ws, uid in ws_to_user_id.items():
        if uid == user_id:
            return ws
    return None


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    role = None
    code: Optional[str] = None

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

            # ---------- INVITATIONS (lobby_invite / lobby_answer) ----------
            elif t == "invite":
                # Le client (ws) invite un autre joueur à jouer
                from_id = ws_to_user_id.get(ws)
                if not from_id:
                    continue
                to_id = str(msg.get("to_id") or "")
                if not to_id:
                    continue

                print(f"[SERVER] invite from {from_id} to {to_id}")

                target_ws = get_ws_by_user_id(to_id)
                if not target_ws:
                    continue  # joueur plus là

                from_user = lobby_users.get(from_id, {"name": "Joueur"})
                payload = {
                    "type": "invite_incoming",
                    "from_id": from_id,
                    "from_name": from_user.get("name") or "Joueur",
                    "avatar": from_user.get("avatar") or "avatar_01",
                }
                await target_ws.send_text(json.dumps(payload))

            elif t == "invite_reply":
                # Un joueur accepte / refuse une invitation
                from_id = ws_to_user_id.get(ws)
                if not from_id:
                    continue
                to_id = str(msg.get("to_id") or "")
                if not to_id:
                    continue
                accepted = bool(msg.get("accepted"))

                print(f"[SERVER] invite_reply from {from_id} to {to_id}, accepted={accepted}")

                inviter_ws = get_ws_by_user_id(to_id)
                if not inviter_ws:
                    continue  # l'autre n'est plus connecté

                from_user = lobby_users.get(from_id, {"name": "Joueur"})
                inviter_user = lobby_users.get(to_id, {"name": "Joueur"})

                if not accepted:
                    # Simple refus
                    payload = {
                        "type": "invite_declined",
                        "from_id": from_id,
                        "from_name": from_user.get("name") or "Joueur",
                    }
                    await inviter_ws.send_text(json.dumps(payload))
                    continue

                # Invitation acceptée -> création d'une salle et match_start pour les 2
                code = new_code()
                while code in rooms:
                    code = new_code()

                rooms[code] = {
                    "a": inviter_ws,
                    "b": ws,
                    "names": {
                        "a": inviter_user.get("name") or "J1",
                        "b": from_user.get("name") or "J2",
                    },
                }
                ws_to_room_code[inviter_ws] = code
                ws_to_room_code[ws] = code

                names = rooms[code]["names"]

                # message match_start pour les 2 joueurs
                await inviter_ws.send_text(
                    json.dumps(
                        {
                            "type": "match_start",
                            "code": code,
                            "role": "a",
                            "names": names,
                        }
                    )
                )
                await ws.send_text(
                    json.dumps(
                        {
                            "type": "match_start",
                            "code": code,
                            "role": "b",
                            "names": names,
                        }
                    )
                )

            # ---------- PARTIES CLASSIQUES (création/join par code) ----------
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
                ws_to_room_code[ws] = code
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
                ws_to_room_code[ws] = code
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
                # on retrouve le code de salle via le mapping global
                room_code = ws_to_room_code.get(ws)
                if not room_code:
                    continue
                await broadcast(room_code, raw)

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
                await lobby_broadcast(delta, exclude=ws)

        # ---------- Nettoyage rooms ----------
        room_code = ws_to_room_code.pop(ws, None)
        if room_code and room_code in rooms:
            for k in ("a", "b"):
                if rooms[room_code].get(k) is ws:
                    rooms[room_code][k] = None
            if not rooms[room_code]["a"] and not rooms[room_code]["b"]:
                rooms.pop(room_code, None)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8765"))
    uvicorn.run(app, host="0.0.0.0", port=port)
