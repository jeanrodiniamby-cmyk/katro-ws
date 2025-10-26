# main.py — Shell KATRO (écrans & UI)
# Compatible Kivy 2.3.0 / KivyMD 1.2.0
from dataclasses import dataclass
from kivy.lang import Builder
from kivy.utils import get_color_from_hex as hex
from kivy.properties import ObjectProperty, StringProperty, NumericProperty, ListProperty
from kivy.clock import Clock

from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.screen import MDScreen
from kivymd.uix.dialog import MDDialog

# (les 3 imports ci-dessous ne sont pas indispensables ici, mais gardés si tu veux t'en servir)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.metrics import dp

from online import OnlineClient   # ton fichier online.py
WS_URL = "ws://localhost:8765/ws"    # plus tard: wss://ton-domaine/ws

from KATRO import KatroBoard, ROWS, COLS, SEEDS_PER_PIT

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:import FitImage kivymd.uix.fitimage.FitImage

<HomeScreen>:
    name: "home"
    MDBoxLayout:
        orientation: "vertical"
        spacing: 0
        md_bg_color: app.c_bg

        MDTopAppBar:
            title: "KATRO _ Jeu traditionnel Malagasy"
            md_bg_color: app.c_appbar
            specific_text_color: 1, 1, 1, 1
            left_action_items: []
            right_action_items: [["help-circle", lambda *_: app.goto_info()], ["cog", lambda *_: app.goto_settings()]]

        FloatLayout:

            FitImage:
                source: "katro.png"
                size_hint: 1, 1
                pos_hint: {"x": 0, "y": 0}
                keep_ratio: True
                allow_stretch: True

            Widget:
                size_hint: 1, 1
                canvas.before:
                    Color:
                        rgba: 0, 0, 0, 0.22
                    Rectangle:
                        pos: self.pos
                        size: self.size

            AnchorLayout:
                anchor_x: "center"
                anchor_y: "center"

            # --- Menu centré ---
                MDBoxLayout:
                    id: menu_box
                    orientation: "vertical"
                    spacing: dp(16)
                    padding: dp(8)
                    size_hint: None, None
                    width: max(dp(260), min(self.parent.width * 0.60, dp(820)))
                    height: self.minimum_height

                    MDLabel:
                        text: "PLAY MODE"
                        halign: "center"
                        bold: True
                        font_style: "H5"
                        size_hint_y: None
                        height: self.texture_size[1] + dp(4)
                        theme_text_color: "Custom"
                        text_color: 1, 1, 1, 1

                    MDRaisedButton:
                        text: "CONTRE ORDINATEUR"
                        size_hint_x: 1
                        height: dp(48)
                        font_size: sp(max(14, min(18, int(root.width/50))))
                        md_bg_color: app.c_btn1
                        text_color: app.c_btn_txt
                        on_release: app.goto_ai()

                    MDRaisedButton:
                        text: "2 JOUEURS (HORS-LIGNE)"
                        size_hint_x: 1
                        height: dp(48)
                        font_size: sp(max(14, min(18, int(root.width/50))))
                        md_bg_color: app.c_btn2
                        text_color: app.c_btn_txt
                        on_release: app.goto_local_2p()

                    MDRaisedButton:
                        text: "AVEC UN AMI (EN LIGNE)"
                        size_hint_x: 1
                        height: dp(48)
                        font_size: sp(max(14, min(18, int(root.width/50))))
                        md_bg_color: app.c_btn3
                        text_color: app.c_btn_txt
                        on_release: app.goto_friend_online()

                    MDRaisedButton:
                        text: "CHERCHER UN ADVERSAIRE (EN LIGNE)"
                        size_hint_x: 1
                        height: dp(48)
                        font_size: sp(max(14, min(18, int(root.width/50))))
                        md_bg_color: app.c_btn4
                        text_color: app.c_btn_txt
                        on_release: app.goto_matchmaking()

                    MDLabel:
                        text: "Astuce : active le Wi-Fi pour jouer en ligne."
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: 1, 1, 1, .92
                        size_hint_y: None
                        text_size: self.width, None
                        height: self.texture_size[1] + dp(6)

# après (MDToolbar -> petite barre custom compatible 1.2.0)
<OnlineBoardScreen>:
    name: "online_board"
    MDBoxLayout:
        orientation: "vertical"

        MDTopAppBar:
            title: "KATRO — En ligne"
            left_action_items: [["arrow-left", lambda *_: app.leave_online()]]
            right_action_items: [["account", lambda *_: None]]

        # Barre d'état compatible KivyMD 1.2.0
        MDBoxLayout:
            id: online_statebar
            md_bg_color: app.c_appbar
            adaptive_height: True
            padding: dp(8), dp(6)
            MDLabel:
                text: app.turn_text
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 1
                halign: "center"

        FloatLayout:
            id: online_board_area
                      



<OnlineScreen@MDScreen>:
    name: "online"
    MDBoxLayout:
        orientation: "vertical"

        MDTopAppBar:
            title: "Jouer en ligne"
            left_action_items: [["arrow-left", lambda *_: app.go_home()]]

        MDBoxLayout:
            orientation: "vertical"
            padding: dp(16)
            spacing: dp(12)

            MDLabel:
                id: lbl_status
                text: "Créer une salle ou entrer un code pour rejoindre."
                halign: "center"
                size_hint_y: None
                height: self.texture_size[1] + dp(8)

            MDTextField:
                id: tf_code
                hint_text: "Code de salle (ex: A3F1)"
                helper_text: "Saisis le code de ton ami"
                size_hint_x: None
                width: min(dp(420), self.parent.width * 0.8)
                pos_hint: {"center_x": 0.5}

            MDBoxLayout:
                adaptive_height: True
                spacing: dp(10)
                pos_hint: {"center_x": 0.5}
                MDRaisedButton:
                    text: "CRÉER UNE SALLE"
                    on_release: app.online_create()
                MDRaisedButton:
                    text: "REJOINDRE"
                    on_release: app.online_join(root.ids.tf_code.text)

<Local2PScreen>:
    name: "local2p"
    MDBoxLayout:
        orientation: "vertical"

        MDTopAppBar:
            title: "KATRO — 2 Joueurs (hors-ligne)"
            md_bg_color: app.c_appbar
            specific_text_color: 1, 1, 1, 1
            left_action_items: [["arrow-left", lambda *_: app.go_home()]]
            right_action_items: [["cog", lambda *_: app.goto_settings()]]

        KatroBoard:
            id: board

<AIScreen>:
    name: "ai"
    MDBoxLayout:
        orientation: "vertical"

        MDTopAppBar:
            title: "KATRO — Contre ordinateur"
            md_bg_color: app.c_appbar
            specific_text_color: 1, 1, 1, 1
            left_action_items: [["arrow-left", lambda *_: app.go_home()]]
            right_action_items: [["cog", lambda *_: app.goto_settings()]]

        KatroBoard:
            id: board_ai

<InfoScreen>:
    name: "info"
    MDBoxLayout:
        orientation: "vertical"

        MDTopAppBar:
            title: "À propos • Règles"
            md_bg_color: app.c_appbar
            specific_text_color: 1, 1, 1, 1
            left_action_items: [["arrow-left", lambda *_: app.go_home()]]

        ScrollView:
            MDBoxLayout:
                orientation: "vertical"
                padding: dp(16)
                spacing: dp(12)
                size_hint_y: None
                height: self.minimum_height

                MDLabel:
                    text: "Introduction"
                    bold: True
                    font_style: "H6"
                    size_hint_y: None
                    height: self.texture_size[1]

                MDLabel:
                    text: app.info_intro
                    theme_text_color: "Primary"
                    size_hint_y: None
                    text_size: self.width, None
                    height: self.texture_size[1]

                MDSeparator:

                MDLabel:
                    text: "Règles du jeu"
                    bold: True
                    font_style: "H6"
                    size_hint_y: None
                    height: self.texture_size[1]

                MDLabel:
                    text: app.info_rules
                    theme_text_color: "Primary"
                    size_hint_y: None
                    text_size: self.width, None
                    height: self.texture_size[1]

                MDSeparator:

                MDLabel:
                    text: "Conclusion"
                    bold: True
                    font_style: "H6"
                    size_hint_y: None
                    height: self.texture_size[1]

                MDLabel:
                    text: app.info_outro
                    theme_text_color: "Primary"
                    size_hint_y: None
                    text_size: self.width, None
                    height: self.texture_size[1]

<SettingsScreen>:
    name: "settings"
    MDBoxLayout:
        orientation: "vertical"

        MDTopAppBar:
            title: "Paramètres"
            md_bg_color: app.c_appbar
            specific_text_color: 1, 1, 1, 1
            left_action_items: [["arrow-left", lambda *_: app.go_home()]]

        ScrollView:
            MDBoxLayout:
                orientation: "vertical"
                padding: dp(16)
                spacing: dp(16)
                size_hint_y: None
                height: self.minimum_height

                # --- Nombre de graines par trou ---
                MDLabel:
                    text: "Nombre de graines par trou"
                    font_style: "H6"
                    size_hint_y: None
                    height: self.texture_size[1]

                MDBoxLayout:
                    spacing: dp(10)
                    adaptive_height: True

                    MDCheckbox:
                        group: "seeds"
                        active: app.seeds_per_pit == 2
                        on_active: app.set_seeds(2) if self.active else None
                    MDLabel:
                        text: "2 graines"
                        halign: "left"

                    MDCheckbox:
                        group: "seeds"
                        active: app.seeds_per_pit == 3
                        on_active: app.set_seeds(3) if self.active else None
                    MDLabel:
                        text: "3 graines"
                        halign: "left"

                MDSeparator:

                # --- Sens de déplacement ---
                MDLabel:
                    text: "Sens de déplacement"
                    font_style: "H6"
                    size_hint_y: None
                    height: self.texture_size[1]

                MDBoxLayout:
                    spacing: dp(10)
                    adaptive_height: True

                    MDCheckbox:
                        group: "dir"
                        active: app.direction_mode == "fixed"
                        on_active: app.set_direction_mode("fixed") if self.active else None
                    MDLabel:
                        text: "Fixe (classique)"
                        halign: "left"

                    MDCheckbox:
                        group: "dir"
                        active: app.direction_mode == "free"
                        on_active: app.set_direction_mode("free") if self.active else None
                    MDLabel:
                        text: "Libre (choisir à chaque tour)"
                        halign: "left"

                MDSeparator:

                # --- Son ---
                MDLabel:
                    text: "Son"
                    font_style: "H6"
                    size_hint_y: None
                    height: self.texture_size[1]

                MDBoxLayout:
                    spacing: dp(10)
                    adaptive_height: True

                    MDLabel:
                        text: "Activer"
                        halign: "left"
                    MDSwitch:
                        active: bool(app.sound_enabled)
                        on_active: app.set_sound_enabled(self.active)

                MDBoxLayout:
                    spacing: dp(10)
                    adaptive_height: True

                    MDLabel:
                        text: "Volume"
                        halign: "left"
                        size_hint_x: .25
                    MDSlider:
                        min: 0
                        max: 100
                        value: app.sound_volume
                        step: 1
                        hint: True
                        on_value: app.set_sound_volume(self.value)
"""

class HomeScreen(MDScreen): ...
class Local2PScreen(MDScreen): ...
class AIScreen(MDScreen): ...
class InfoScreen(MDScreen): ...
class SettingsScreen(MDScreen): ...
class OnlineScreen(MDScreen): ...
class OnlineBoardScreen(MDScreen): ...

@dataclass
class GameConfig:
    mode: str = "local_2p"

class KatroAppShell(MDApp):
    # --- Palette (multi-tons) ---
    c_appbar  = ListProperty(hex("#2F4AC2"))   # Brown 600
    c_btn1    = ListProperty(hex("#EC9108"))   # Brown 600
    c_btn2    = ListProperty(hex("#5F7900"))   # Teal 700
    c_btn3    = ListProperty(hex("#3949AB"))   # Indigo 600
    c_btn4    = ListProperty(hex("#F4511E"))   # Deep Orange 600
    c_btn_txt = ListProperty([1, 1, 1, 1])     # texte blanc
    c_bg      = ListProperty(hex("#FAF7F2"))   # fond clair

    _seen_nonces = set()

    # Aide / textes
    info_intro = StringProperty(
        "KATRO est un jeu traditionnel malgache (4×8). "
        "Deux joueurs sèment des graines et capturent celles de l’adversaire."
    )
    info_rules = StringProperty(
        "• Choisis un trou dans tes 2 rangées et un sens de déplacement (si mode Libre).\n"
        "• RELAIS : si la case d’arrivée était non vide (>1), tu ramasses tout et continues.\n"
        "• CAPTURE (prioritaire) : si la dernière graine s’arrête sur TA 1ʳᵉ rangée et qu’en face (>0), "
        "tu prends ces graines + celles de ta case et tu continues. "
        "La 2ᵉ rangée adverse devient 1ʳᵉ si la 1ʳᵉ est vide.\n"
        "• STOP : si la case d’arrivée était vide (devient 1) et qu’aucune capture n’est possible, le tour passe.\n"
        "• Fin : si un camp n’a plus de graines, il perd."
    )
    info_outro = StringProperty(
        "Bonne partie ! Partage KATRO — un jeu simple et profond du patrimoine malagasy."
    )

    from kivy.properties import StringProperty
    from kivy.clock import Clock

    turn_text = StringProperty("")

    def _update_turn_banner(self, *_):
        b = self.board_online
        if not b:
            self.turn_text = ""
            return
        # rôle local
        role = getattr(b, "local_role", "")  # "a" ou "b"
        role_humain = "J1" if role == "a" else ("J2" if role == "b" else "?")
        # joueur courant
        who = "J1" if b.player == 1 else "J2"
        prefix = "À toi de jouer !" if ((role == "a" and b.player == 1) or (role == "b" and b.player == 2)) else "Tour de l'adversaire…"
        self.turn_text = f"{prefix}  |  Ton rôle: {role_humain}  |  Tour: {who}"

    
    # Paramètres gameplay
    seeds_per_pit = NumericProperty(SEEDS_PER_PIT)   # 2 ou 3
    direction_mode = StringProperty("fixed")         # "fixed" ou "free"

    # Audio global (lié aux widgets Paramètres)
    sound_enabled = NumericProperty(1)   # 1=ON / 0=OFF
    sound_volume = NumericProperty(80)   # 0..100

    def build(self):
        self.title = "KATRO"
        self.theme_cls.material_style = "M2"   # KivyMD 1.2.0
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Brown"

        # Online state
        self.online = None       # OnlineClient
        self.room_code = ""
        self.role = None         # "a" ou "b"
        self.board_online = None # plateau courant en ligne

        Builder.load_string(KV)

        self.sm = MDScreenManager()
        self.sm.add_widget(HomeScreen())
        self.sm.add_widget(Local2PScreen())
        self.sm.add_widget(AIScreen())
        self.sm.add_widget(InfoScreen())
        self.sm.add_widget(SettingsScreen())
        self.sm.add_widget(OnlineScreen())
        self.sm.add_widget(OnlineBoardScreen())

        Clock.schedule_once(lambda *_: self._post_build(), 0)
        return self.sm

    # --------- Hooks init des plateaux
    def _init_board_common(self, board: KatroBoard):
        board.pits = [self.seeds_per_pit] * (ROWS * COLS)
        board.update_counts()
        board.direction_mode = self.direction_mode
        # appliquer son
        board.set_sound(enabled=bool(self.sound_enabled), volume=float(self.sound_volume)/100.0)

    def _post_build(self, *_):
        # Local 2P
        scr2p = self.sm.get_screen("local2p")
        self.board = scr2p.ids.board
        self._init_board_common(self.board)

        # IA
        scrai = self.sm.get_screen("ai")
        self.board_ai = scrai.ids.board_ai
        self.board_ai.vs_ai = True
        self.board_ai.ai_player = 2
        self._init_board_common(self.board_ai)

    # --------- Navigation
    def go_home(self): self.sm.current = "home"
    def goto_local_2p(self):
        self._init_board_common(self.sm.get_screen("local2p").ids.board)
        self.sm.current = "local2p"
    def goto_ai(self):
        self._init_board_common(self.sm.get_screen("ai").ids.board_ai)
        self.sm.current = "ai"
    def goto_info(self): self.sm.current = "info"
    def goto_settings(self): self.sm.current = "settings"

    # --------- En ligne (UI)
    def goto_friend_online(self):
        self.sm.current = "online"
        # (ré)crée le client si nécessaire
        if not getattr(self, "online", None):
            self.online = OnlineClient(
                WS_URL,
                on_message=self._on_ws_message,
                on_open=lambda: self._set_status("Connecté au serveur"),
                on_close=lambda: self._set_status("Connexion fermée"),
                on_error=lambda e: self._set_status(f"Erreur: {e}")
            )
            self._set_status("Connexion…")
            self.online.connect()
        elif not self.online.connected:
            self._set_status("Connexion…")
            self.online.connect()
        else:
            self._set_status("Prêt. Crée une salle ou rejoins un code.")




    def goto_matchmaking(self):
        MDDialog(title="Bientôt", text="À implémenter.").open()

    # --------- Online client
    def online_connect(self):
        if self.online:
            return
        self.online = OnlineClient(WS_URL, self._on_ws_message)
        self.online.connect()

    def online_create(self):
        scr = self.sm.get_screen("online")
        scr.ids.lbl_status.text = "Connexion..."
        self._ensure_online()
        # grâce à la queue, on peut envoyer tout de suite :
        self.online.create_room()

    def online_join(self, code):
        scr = self.sm.get_screen("online")
        if not code:
            scr.ids.lbl_status.text = "Code manquant."
            return
        scr.ids.lbl_status.text = f"Connexion à la salle {code}…"
        self._ensure_online()
        self.online.join_room(code)


    from kivy.clock import Clock

    def _set_status(self, text):
        try:
            scr = self.sm.get_screen("online")
            lbl = scr.ids.get("lbl_status")
            if lbl: lbl.text = text
        except Exception:
            pass

    def _apply_remote_move(self, idx: int, step: int):
        if not self.board_online:
            print("remote move but board_online is None")
            return
        try:
            self.board_online.apply_remote_move(idx, step)
        except Exception as e:
            print("apply_remote_move error:", e)

    
    def _on_ws_message(self, msg: dict):
        print("[WS <=]", msg)
        t = msg.get("type")

        if t == "room_created":
            self.room_code = msg.get("code", "")
            self.role = msg.get("role", "a")
            self._set_status(f"Salle créée : {self.room_code} (rôle {self.role}).")

        elif t == "room_joined":
            self.room_code = msg.get("code", "")
            self.role = msg.get("role", "b")
            self._set_status(f"Rejoint la salle {self.room_code} (rôle {self.role}).")

        elif t == "peer_joined":
            self._set_status(f"Un ami a rejoint ({self.room_code}).")

        elif t == "start":
            # Ouvrir l’écran plateau en ligne
            try:
                self.start_online_match()
            except Exception as e:
                print("start_online_match error:", e)

        elif t == "move":
            # 1) Si c'est le coup que NOUS venons d'envoyer (même nonce), on ignore.
            nonce = msg.get("nonce")
            if self.board_online and nonce and getattr(self.board_online, "_last_local_nonce", None) == nonce:
                return

            # 2) Petit filet de sécurité anti-duplicates réseau (seen set)
            if not hasattr(self, "_seen_nonces"):
                self._seen_nonces = set()
            if nonce:
                if nonce in self._seen_nonces:
                    return
                if len(self._seen_nonces) > 2000:
                    self._seen_nonces.clear()
                self._seen_nonces.add(nonce)

            # 3) Appliquer le coup reçu
            if self.board_online:
                try:
                    idx = int(msg.get("idx", -1))
                    step = int(msg.get("step", 1))
                    self.board_online.apply_remote_move(idx, step)
                except Exception as e:
                    print("apply_remote_move error:", e)

            # 4) (optionnel) mettre à jour la bannière "à qui le tour"
            try:
                self._update_turn_banner()
            except Exception:
                pass


        elif t == "error":
            self._set_status(f"Erreur: {msg.get('reason', 'inconnue')}")





    def start_online_match(self):
        print("[APP] start_online_match()")
        board = KatroBoard(vs_ai=False)
        self._init_board_common(board)
        board.vs_ai = False
        board.online_mode = True

        board.local_role = self.role or "a"   # "a" -> J1, "b" -> J2
        board.player = 1                      # J1 commence au Katro

        board.on_send_move = lambda payload: (
            self.online and self.online.send_move(
                payload["idx"], payload["step"], payload["player"], payload["nonce"]
            )
        )


        # Monter le plateau dans l'écran
        self.board_online = board
        scr = self.sm.get_screen("online_board")
        area = scr.ids.online_board_area
        area.clear_widgets()
        area.add_widget(board)
        self.sm.current = "online_board"

        # --- Bannière de tour ---
        # Texte initial
        self._update_turn_banner()
        board.local_role = self.role                  # "a" ou "b" selon ce que t'a renvoyé le serveur
        board.device_flip_180 = (self.role == "b")    # J2 local -> retourne la main à 180°

        # Se mettre à jour à chaque changement de joueur
        board.fbind("player", lambda *_: self._update_turn_banner())
        # Egalement après 200 ms (mise en place écran)
        from kivy.clock import Clock
        Clock.schedule_once(lambda *_: self._update_turn_banner(), 0.2)





    
    def _ensure_online(self):
        if not getattr(self, "online", None):
            self.online = OnlineClient(
                WS_URL,
                on_message=self._on_ws_message,
                on_open=lambda: self._set_status("Connecté au serveur"),
                on_close=lambda: self._set_status("Connexion fermée"),
                on_error=lambda e: self._set_status(f"Erreur: {e}")
            )
            self._set_status("Connexion…")
            self.online.connect()
        elif not self.online.connected:
            self._set_status("Connexion…")
            self.online.connect()




    def leave_online(self):
        try:
            if self.online:
                self.online.leave()
                self.online.close()
        except Exception:
            pass
        self.online = None
        self.room_code = ""
        self.role = None
        self.board_online = None
        self.go_home()

    # --------- Paramètres (callbacks)
    def set_seeds(self, n:int):
        if n not in (2, 3): return
        self.seeds_per_pit = n
        for sid, wid in (("local2p", "board"), ("ai", "board_ai")):
            scr = self.sm.get_screen(sid)
            board = scr.ids.get(wid)
            if board:
                self._init_board_common(board)

    def set_direction_mode(self, mode:str):
        if mode not in ("fixed", "free"): return
        self.direction_mode = mode
        for sid, wid in (("local2p", "board"), ("ai", "board_ai")):
            scr = self.sm.get_screen(sid)
            board = scr.ids.get(wid)
            if board:
                board.direction_mode = mode

    def set_sound_enabled(self, value):
        self.sound_enabled = 1 if value else 0
        for sid, wid in (("local2p","board"), ("ai","board_ai")):
            scr = self.sm.get_screen(sid)
            b = scr.ids.get(wid)
            if b:
                b.set_sound(enabled=bool(self.sound_enabled))

    def set_sound_volume(self, value):
        try:
            self.sound_volume = int(value)
        except Exception:
            return
        vol = float(self.sound_volume) / 100.0
        for sid, wid in (("local2p","board"), ("ai","board_ai")):
            scr = self.sm.get_screen(sid)
            b = scr.ids.get(wid)
            if b:
                b.set_sound(volume=vol)

    def replay_current_game(self):
        """Réinitialise le plateau de l'écran courant et reste sur cet écran."""
        cur = self.sm.current
        if cur == "ai":
            if hasattr(self, "board_ai"):
                self._init_board_common(self.board_ai)
            self.sm.current = "ai"
        elif cur == "local2p":
            if hasattr(self, "board"):
                self._init_board_common(self.board)
            self.sm.current = "local2p"
        else:
            self.go_home()

    # --------- Snackbar helper (KivyMD 1.2.0)
    def snack(self, text):
        try:
            from kivymd.uix.snackbar import Snackbar
            Snackbar(text=text, duration=1.4).open()
        except Exception:
            print(text)

if __name__ == "__main__":
    KatroAppShell().run()
