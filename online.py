# online.py
import json, threading
from websocket import WebSocketApp
from kivy.clock import Clock

class OnlineClient:
    def __init__(self, url, on_message=None, on_open=None, on_close=None, on_error=None):
        self.url = url
        self.on_message = on_message
        self.on_open = on_open
        self.on_close = on_close
        self.on_error = on_error
        self.ws = None
        self._t = None
        self.connected = False

    def connect(self):
        def _ui(fn, *args):
            Clock.schedule_once(lambda dt: fn(*args), 0)

        def _on_open(ws):
            self.connected = True
            if self.on_open: _ui(self.on_open)

        def _on_close(ws, *a):
            self.connected = False
            if self.on_close: _ui(self.on_close)

        def _on_error(ws, e):
            if self.on_error: _ui(self.on_error, e)

        def _on_message(ws, txt):
            try:
                msg = json.loads(txt)
            except Exception:
                return
            if self.on_message: _ui(self.on_message, msg)

        self.ws = WebSocketApp(
            self.url, on_open=_on_open, on_close=_on_close,
            on_error=_on_error, on_message=_on_message
        )
        self._t = threading.Thread(target=self.ws.run_forever, daemon=True)
        self._t.start()

    def send_json(self, obj):
        try:
            if self.ws and self.connected:
                self.ws.send(json.dumps(obj))
        except Exception:
            pass

    # API
    def create_room(self): self.send_json({"type":"create_room"})
    def join_room(self, code): self.send_json({"type":"join_room","code":str(code).upper()})
    def send_move(self, idx, step, player, nonce):
        self.send_json({"type":"move","idx":idx,"step":step,"player":player,"nonce":nonce})
    def leave(self): self.send_json({"type":"leave"})
    def close(self):
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        self.connected = False

