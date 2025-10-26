# KATRO — 4×8 — moteur + rendu + sons (version sobre et online-safe)
# Compatible Kivy 2.3.0 / KivyMD 1.2.0

import os
from kivy.metrics import dp
from kivy.properties import (
    ListProperty, NumericProperty, StringProperty,
    BooleanProperty, ObjectProperty
)
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.graphics import (
    Color, Rectangle, Ellipse, RoundedRectangle,
    PushMatrix, PopMatrix, Translate, Scale
)
from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.core.image import Image as CoreImage
from kivy.core.audio import SoundLoader
from kivymd.app import MDApp
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton
from kivy.uix.boxlayout import BoxLayout

# (petits toasts cross-version)
try:
    from kivymd.uix.snackbar import MDSnackbar as _SBNew  # KivyMD 2.x
except Exception:
    _SBNew = None
try:
    from kivymd.uix.snackbar import Snackbar as _SBOld  # KivyMD 1.2.0
    from kivymd.uix.label import MDLabel as _SBLabel
except Exception:
    _SBOld, _SBLabel = None, None
try:
    from kivymd.uix.dialog import MDDialog as _SBDialog
except Exception:
    _SBDialog = None

ASSETS = {
    "board": "board_wood.png",
    "pit_shadow": "pit_shadow1.png",
    "seed": "seed.png",
    "hand": {"j1": "hand1.png", "j2": "hand2.png"},
    # bannières fin de partie
    "end_win": "win.png",
    "end_lose": "lose.png",
}

SOUNDS = {
    "ui": "ui_click.wav",
    "error": "error.wav",
    "sow": "sow.wav",
    "capture": "capture.wav",
    "stop": "stop.wav",
    "ai": "ai.wav",
    "win": "win.wav",
    "lose": "lose.wav",
}

class _SoundBank:
    def __init__(self, mapping, master=0.8, enabled=True):
        self.map = mapping
        self.cache = {}
        self.enabled = enabled
        self.master = float(master)

    def load(self, key):
        if key in self.cache:
            return self.cache[key]
        path = self.map.get(key)
        if not path:
            return None
        try:
            s = SoundLoader.load(path)
            if s:
                s.volume = self.master
                self.cache[key] = s
            return s
        except Exception:
            return None

    def set_master(self, v):
        self.master = max(0.0, min(1.0, float(v)))
        for s in self.cache.values():
            try:
                s.volume = self.master
            except Exception:
                pass

    def play(self, key):
        if not self.enabled:
            return
        s = self.load(key)
        try:
            if s:
                s.stop()
                s.volume = self.master
                s.play()
        except Exception:
            pass

# =================== Plateau ===================
ROWS = 4
COLS = 8
SEEDS_PER_PIT = 3

J1_ROWS = [2, 3]  # joueur 1 (bas)
J2_ROWS = [1, 0]  # joueur 2 (haut)

# couleurs fallback si pas d’images
C_BG, C_BOARD, C_FRAME = (0.07, 0.06, 0.05, 1), (0.22, 0.16, 0.11, 1), (0.28, 0.20, 0.14, 1)
C_RING, C_MID, C_DEEP, C_SEED = (0.30, 0.21, 0.15, 1), (0.18, 0.13, 0.09, 1), (0.12, 0.09, 0.06, 1), (0.86, 0.86, 0.85, 1)

# -------------------- Sprites --------------------
class PitSprite(Widget):
    count = NumericProperty(0)
    pit_index = NumericProperty(-1)
    seed_img = ObjectProperty(None, allownone=True)
    pit_img = ObjectProperty(None, allownone=True)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(pos=self._redraw, size=self._redraw, count=self._redraw)

    def load_assets(self):
        try:
            if ASSETS.get("pit_shadow") and os.path.exists(ASSETS["pit_shadow"]):
                self.pit_img = CoreImage(ASSETS["pit_shadow"]).texture
        except Exception:
            self.pit_img = None
        try:
            if ASSETS.get("seed") and os.path.exists(ASSETS["seed"]):
                self.seed_img = CoreImage(ASSETS["seed"]).texture
        except Exception:
            self.seed_img = None

    def _redraw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            # cupule
            if self.pit_img is not None:
                oversize = max(4.0, self.width * 0.12)
                Rectangle(texture=self.pit_img,
                          pos=(self.x - oversize/2, self.y - oversize/2),
                          size=(self.width + oversize, self.height + oversize))
            else:
                Color(*C_RING); Ellipse(pos=self.pos, size=self.size)
                inset1 = max(6.0, self.width * 0.10)
                Color(*C_MID); Ellipse(pos=(self.x+inset1, self.y+inset1),
                                       size=(self.width-2*inset1, self.height-2*inset1))
                inset2 = max(12.0, self.width * 0.20)
                Color(*C_DEEP); Ellipse(pos=(self.x+inset2, self.y+inset2),
                                        size=(self.width-2*inset2, self.height-2*inset2))

            # graines
            n = int(self.count)
            if n <= 0:
                return
            cx, cy = self.center
            R = min(self.width, self.height) * 0.26

            def base_positions(m):
                center = [(cx, cy)]
                two = [(cx - R*0.35, cy), (cx + R*0.35, cy)]
                ring6 = [(cx, cy+R),(cx+0.866*R, cy+0.5*R),(cx+0.866*R, cy-0.5*R),
                         (cx, cy-R),(cx-0.866*R, cy-0.5*R),(cx-0.866*R, cy+0.5*R)]
                if m == 1: return center
                if m == 2: return two
                if m == 3: return center + [ring6[0], ring6[3]]
                if m == 4: return [two[0], two[1], ring6[1], ring6[5]]
                if m == 5: return [two[0], two[1], ring6[0], ring6[3], center[0]]
                if m == 6: return ring6
                return ring6 + [center[0]]

            base = base_positions(min(n, 7))
            base_count = len(base)
            seed_sz_base = max(14.0, self.width * 0.26)

            for i in range(n):
                bx, by = base[i % base_count]
                layer = i // base_count
                lift = layer * (seed_sz_base * 0.12)
                scale = max(0.80, 1.0 - layer * 0.06)
                seed = seed_sz_base * scale
                px, py = bx - seed/2, by - seed/2 + lift
                if self.seed_img is not None:
                    Color(1, 1, 1, 1); Rectangle(texture=self.seed_img, pos=(px, py), size=(seed, seed))
                else:
                    Color(*C_SEED); Ellipse(pos=(px, py), size=(seed*0.95, seed*0.95))

class HandSprite(Image):
    """Sprite de la main, avec miroirs H/V (permet 180° via -1,-1)."""
    mirror_h = BooleanProperty(False)  # miroir horizontal
    mirror_v = BooleanProperty(False)  # miroir vertical

    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            PushMatrix()
            self._t1 = Translate(0, 0, 0)   # translation au centre
            self._s  = Scale(1, 1, 1)       # mise à l’échelle (miroirs)
            self._t2 = Translate(0, 0, 0)   # translation retour
        with self.canvas.after:
            PopMatrix()
        # Met à jour la transform dès que la main bouge/change
        self.bind(
            pos=self._update_transform,
            size=self._update_transform,
            mirror_h=self._update_transform,
            mirror_v=self._update_transform,
        )
class HandSprite(Image):
    mirror_h = BooleanProperty(False)
    mirror_v = BooleanProperty(False)

    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            PushMatrix()
            self._t1 = Translate(0, 0, 0)
            self._s  = Scale(1, 1, 1)
            self._t2 = Translate(0, 0, 0)
        with self.canvas.after:
            PopMatrix()
        self.bind(pos=self._update_transform,
                  size=self._update_transform,
                  mirror_h=self._update_transform,
                  mirror_v=self._update_transform)

    def _update_transform(self, *_):
        cx, cy = self.center
        sx = -1 if self.mirror_h else 1
        sy = -1 if self.mirror_v else 1
        self._t1.xy = (cx, cy)
        self._s.xyz = (sx, sy, 1)
        self._t2.xy = (-cx, -cy)



HAND_SPEED_MULT = 2.0

# -------------------- Board --------------------
class KatroBoard(Widget):
    pits = ListProperty([SEEDS_PER_PIT] * (ROWS * COLS))
    player = NumericProperty(1)
    running_anim = BooleanProperty(False)
    vs_ai = BooleanProperty(False)
    ai_player = NumericProperty(2)
        # vue locale :true = les rangées sont retournées verticalement
    view_flip_v = BooleanProperty(False)  # flip vertical (haut/bas)
    view_flip_h = BooleanProperty(False)  # flip horizontal (gauche/droite)


    # paramètres layout
    cell = NumericProperty(80.0)
    gap = NumericProperty(14.0)
    margin = NumericProperty(22.0)

    # totaux
    j1_total = NumericProperty(0)
    j2_total = NumericProperty(0)

    # sens de déplacement
    direction_mode = StringProperty("fixed")  # "fixed" | "free"
    _pending_start_idx = NumericProperty(-1)
    _await_dir_choice = BooleanProperty(False)
    _current_step = NumericProperty(1)

    # audio (exposé et piloté depuis main.py)
    sound_enabled = BooleanProperty(True)
    volume_master = NumericProperty(0.8)

    # rôle local pour l'online ("a"->J1 / "b"->J2)
    local_role = StringProperty("a") # "a" pour l’hôte (J1 local), "b" pour l’invité (J2 local)
    device_flip_180 = BooleanProperty(False)  # vrai si on veut retourner TOUTE la vue de la main à 180°


    def _sync_hand_flip(self, *_):
        if self.hand:
            self.hand.mirror_h = bool(self.view_flip_h)


    def set_sound(self, enabled=None, volume=None):
        if enabled is not None:
            self.sound_enabled = bool(enabled)
            self._sbank.enabled = self.sound_enabled
        if volume is not None:
            self.volume_master = max(0.0, min(1.0, float(volume)))
            self._sbank.set_master(self.volume_master)

    # utilitaires côté
    def side_rows(self, p): return J1_ROWS if p == 1 else J2_ROWS
    def _sum_side(self, p):
        rows = self.side_rows(p)
        return sum(self.pits[r*COLS + c] for r in rows for c in range(COLS))

    def __init__(self, **kw):
        super().__init__(**kw)
        self.pit_widgets = []
        self.hand = None
        self.board_tex = None
        self.initialized = False
        self.bind(size=self._layout, pos=self._layout)
        # sons
        self._sbank = _SoundBank(SOUNDS, master=self.volume_master, enabled=self.sound_enabled)
        self._last_sow_tick = 0

        # === Online (flags/état) ===
        self.online_mode = False
        self.on_send_move = None
        self._is_replaying_remote = False
        self._last_local_nonce = None
        self.local_role = "a"  # déjà défini comme StringProperty plus haut

        # Quand le rôle ou le mode changent -> maj flip
        self.fbind("local_role", self._update_view_flip)
        self.fbind("online_mode", self._update_view_flip)
        self.fbind("view_flip_h", self._sync_hand_flip)

        Clock.schedule_once(self._init_graphics, 0)
    
    def _update_view_flip(self, *_):
        # Si on est en ligne et qu'on est le joueur "b", on inverse l'affichage
        enabled = bool(self.online_mode and (getattr(self, "local_role", "a") == "b"))
        self.view_flip_v = enabled
        self.view_flip_h = enabled
        self._layout()



    # ---------- métriques & géométrie ----------
    def _compute_metrics(self):
        W, H = self.width, self.height
        self.margin = max(12.0, min(W, H) * 0.025)
        self.gap = max(6.0, min(W, H) * 0.015)
        cell_w = (W - 2*self.margin - (COLS-1)*self.gap) / COLS
        cell_h = (H - 2*self.margin - (ROWS-1)*self.gap) / ROWS
        self.cell = max(22.0, min(cell_w, cell_h))

    def _grid_pos(self, r, c):
        # Applique les flips d'AFFICHAGE uniquement (les indices logiques restent identiques).
        vr = (ROWS - 1 - r) if self.view_flip_v else r
        vc = (COLS - 1 - c) if self.view_flip_h else c

        plate_w = COLS*self.cell + (COLS-1)*self.gap + 2*self.margin
        plate_h = ROWS*self.cell + (ROWS-1)*self.gap + 2*self.margin
        x0 = self.center_x - plate_w/2 + self.margin
        y0 = self.center_y - plate_h/2 + self.margin

        x = x0 + vc*(self.cell + self.gap)
        y = y0 + (ROWS-1 - vr)*(self.cell + self.gap)
        return x, y



    def _plate_bounds(self):
        plate_w = COLS*self.cell + (COLS-1)*self.gap + 2*self.margin
        plate_h = ROWS*self.cell + (ROWS-1)*self.gap + 2*self.margin
        return (self.center_x - plate_w/2, self.center_y - plate_h/2, plate_w, plate_h)

    # ---------- assets main ----------
    def _hand_asset_for(self, player: int):
        """Retourne l'image de main selon le joueur (J1 ou J2)."""
        h = ASSETS.get("hand") or {}
        path = h.get("j1") if player == 1 else h.get("j2")  # ✅ J1 → hand1.png / J2 → hand2.png
        return path if path and os.path.exists(path) else None


    def _apply_hand_asset(self, player: int):
        """Affiche la bonne image de main (selon le joueur actif),
        et la retourne éventuellement à 180° selon le RÔLE LOCAL (appareil)."""
        if not self.hand:
            return

        # 1) Image selon le joueur dont c'est le tour
        path = self._hand_asset_for(player)  # j1 -> hand1.png, j2 -> hand2.png
        if path:
            self.hand.source = path
            self.hand.opacity = 1
        else:
            self.hand.opacity = 0

        # 2) Orientation selon le RÔLE LOCAL (appareil)
        #    - Hôte ("a") : vue normale
        #    - Invité ("b") : vue retournée (miroir H + V) => 180°
        flip = bool(self.device_flip_180) or (self.online_mode and self.local_role == "b")
        self.hand.mirror_h = flip
        self.hand.mirror_v = flip   




    # ---------- init / layout ----------
    def _init_graphics(self, *_):
        self._compute_metrics()
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*C_BG); self.bg_rect = Rectangle(pos=self.pos, size=self.size)

        if ASSETS.get("board") and os.path.exists(ASSETS["board"]):
            try: self.board_tex = CoreImage(ASSETS["board"]).texture
            except Exception: self.board_tex = None

        with self.canvas:
            bx, by, bw, bh = self._plate_bounds()
            if self.board_tex:
                Color(1, 1, 1, 1); self.board_rect = Rectangle(texture=self.board_tex, pos=(bx, by), size=(bw, bh))
            else:
                rr = dp(16)
                Color(*C_FRAME); self.board_rect = RoundedRectangle(pos=(bx, by), size=(bw, bh), radius=[(rr, rr)]*4)
                Color(*C_BOARD); RoundedRectangle(pos=(bx+dp(6), by+dp(6)), size=(bw-dp(12), bh-dp(12)), radius=[(rr-4, rr-4)]*4)

        self.pit_widgets.clear()
        for r in range(ROWS):
            for c in range(COLS):
                p = PitSprite(count=SEEDS_PER_PIT)
                p.pit_index = r*COLS + c
                p.size = (self.cell, self.cell)
                p.pos = self._grid_pos(r, c)
                p.load_assets()
                self.add_widget(p)
                self.pit_widgets.append(p)

        self.hand = HandSprite()
        self.hand.size = (max(80.0, self.cell*1.2), max(80.0, self.cell*1.2))
        self.add_widget(self.hand)
        self._apply_hand_asset(1)

        self.initialized = True
        self.update_counts()

    def _layout(self, *_):
        self._compute_metrics()
        if getattr(self, "bg_rect", None):
            self.bg_rect.pos, self.bg_rect.size = self.pos, self.size
        if getattr(self, "board_rect", None):
            bx, by, bw, bh = self._plate_bounds()
            self.board_rect.pos, self.board_rect.size = (bx, by), (bw, bh)
        if not self.initialized: return
        for i, w in enumerate(self.pit_widgets):
            r, c = divmod(i, COLS)
            w.size = (self.cell, self.cell)
            w.pos = self._grid_pos(r, c)
        if self.hand is not None:
            s = max(80.0, self.cell*1.2)
            self.hand.size = (s, s)

    # ---------- helpers ----------
    def _pit_center(self, idx):
        r, c = divmod(idx, COLS)
        x, y = self._grid_pos(r, c)
        return x + self.cell/2, y + self.cell/2

    def _move_hand_to(self, idx, after=None, duration=None):
        if not self.hand:
            if after: after(self, None)
            return
        cx, cy = self._pit_center(idx)
        target = (cx - self.hand.width/2, cy - self.hand.height/2)
        base = max(0.08, min(0.18, 0.12 * (80.0 / max(1.0, self.cell))))
        d = (duration if duration is not None else base) * HAND_SPEED_MULT
        anim = Animation(pos=target, d=d, t="out_quad")
        if after: anim.bind(on_complete=after)
        anim.start(self.hand)

    def _animate_capture(self, from_idx, opp_idx, captured, then_continue):
        def _go_back(*_): self._move_hand_to(from_idx, after=lambda *_: then_continue())
        self._move_hand_to(opp_idx, after=_go_back, duration=0.10)

    def _toast(self, msg):
        try:
            if _SBNew is not None:
                _SBNew(text=msg, duration=1).open(); return
            if _SBOld is not None and _SBLabel is not None:
                sb = _SBOld(duration=1); sb.add_widget(_SBLabel(text=msg, halign="center")); sb.open(); return
            if _SBDialog is not None:
                _SBDialog(title="Info", text=msg).open(); return
        except Exception:
            pass
        print(msg)

    def is_own_pit(self, idx):
        return (idx // COLS) in self.side_rows(self.player)

    def boustro_path(self, player):
        rows = self.side_rows(player)
        return [rows[0]*COLS + c for c in range(COLS)] + [rows[1]*COLS + c for c in reversed(range(COLS))]

    def update_counts(self):
        for i, p in enumerate(self.pit_widgets):
            p.count = self.pits[i]
        self.j1_total = self._sum_side(1)
        self.j2_total = self._sum_side(2)

    # ---------- interaction ----------
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        # bloque si IA
        if self.vs_ai and self.player == self.ai_player:
            self._toast("Tour de l'ordinateur…")
            self._sbank.play("error")
            return True
        if self.running_anim:
            return True

        # bloque si pas ton tour en mode online
        if self.online_mode:
            my_player = 1 if (self.local_role or "a") == "a" else 2
            if self.player != my_player:
                self._toast("Tour de l'adversaire…")
                self._sbank.play("error")
                return True

        # Choix du sens (2e clic en mode "free")
        if self.direction_mode == "free" and self._await_dir_choice and self._pending_start_idx >= 0:
            path = self.boustro_path(self.player)
            pos0 = path.index(self._pending_start_idx)
            next_idx = path[(pos0 + 1) % len(path)]
            prev_idx = path[(pos0 - 1) % len(path)]
            for p in self.pit_widgets:
                if p.collide_point(*touch.pos):
                    if p.pit_index == next_idx:
                        step = +1
                    elif p.pit_index == prev_idx:
                        step = -1
                    else:
                        self._toast("Clique la case voisine (gauche/droite) pour choisir le sens.")
                        self._sbank.play("error")
                        return True
                    self._await_dir_choice = False
                    start = self._pending_start_idx
                    self._pending_start_idx = -1
                    self._sbank.play("ui")
                    # ⚠️ jouer via start_move (publication réseau + jeu local)
                    self.start_move(start, step=step)
                    return True
            return True

        # 1er clic : choisir la case de départ
        for p in self.pit_widgets:
            if p.collide_point(*touch.pos):
                if not self.is_own_pit(p.pit_index):
                    self._toast("Choisis une case de TES rangées.")
                    self._sbank.play("error")
                    return True
                if self.pits[p.pit_index] == 0:
                    self._toast("Case vide.")
                    self._sbank.play("error")
                    return True

                if self.direction_mode == "free":
                    self._pending_start_idx = p.pit_index
                    self._await_dir_choice = True
                    self._toast("Choisis le SENS : clique la case voisine (gauche/droite).")
                    self._sbank.play("ui")
                    return True
                else:
                    self._sbank.play("ui")
                    # ⚠️ jouer via start_move
                    self.start_move(p.pit_index, step=+1)
                    return True

        return super().on_touch_down(touch)

    # ---------- moteur ----------
    def start_move(self, start_idx: int, step: int):
        """Coup local : publie au réseau (si online) puis joue."""
        if self.online_mode and not self._is_replaying_remote and self.on_send_move:
            import time
            self._last_local_nonce = str(time.time_ns())
            try:
                self.on_send_move({
                    "idx": int(start_idx),
                    "step": 1 if step >= 0 else -1,
                    "player": int(self.player),
                    "nonce": self._last_local_nonce,
                })
            except Exception:
                pass
        # Surtout PAS d'appel récursif à start_move !
        self.play_move(start_idx, step)

    def apply_remote_move(self, idx: int, step: int):
        """Coup reçu du serveur : on l'exécute sans le réémettre."""
        self._is_replaying_remote = True
        try:
            self.play_move(idx, step)
        finally:
            self._is_replaying_remote = False

    def play_move(self, start_idx, step=+1):
        # sens
        self._current_step = 1 if step >= 0 else -1

        # main / z-order
        self._apply_hand_asset(self.player)
        if self.hand:
            self.remove_widget(self.hand)
            self.add_widget(self.hand)

        # on soulève tout du trou de départ
        seeds = self.pits[start_idx]
        self.pits[start_idx] = 0
        self.update_counts()

        # position "courante" = sur la case de départ (main part de là)
        path = self.boustro_path(self.player)
        pos = path.index(start_idx)

        # on place visuellement la main sur la case de départ
        self.running_anim = True
        self._move_hand_to(start_idx, after=lambda *_: self._sow_loop(path, pos, seeds))

    def _sow_loop(self, path, pos, seeds_left):
        if seeds_left <= 0:
            last_idx = path[pos]
            self._after_sow_rules(last_idx)
            return

        next_pos = (pos + self._current_step) % len(path)
        next_idx = path[next_pos]

        def _arrived(*_):
            self.pits[next_idx] += 1
            self.update_counts()
            self._sbank.play("sow")

            if seeds_left - 1 <= 0:
                self._after_sow_rules(next_idx)
            else:
                self._sow_loop(path, next_pos, seeds_left - 1)

        self._move_hand_to(next_idx, after=_arrived)


    def _is_local_winner(self, winner: int) -> bool:
        """
        Retourne True si, du point de vue de cet appareil, c'est une victoire.
        - En ligne: on compare `winner` avec le joueur local (J1 si role "a", sinon J2).
        - Hors ligne vs IA: victoire locale = winner != ai_player.
        - 2 joueurs hors-ligne sur le même appareil: on considère J1 comme "local" par défaut.
        """
        if self.online_mode:
            local_player = 1 if getattr(self, "local_role", "a") == "a" else 2
            return winner == local_player
        if self.vs_ai:
            return winner != self.ai_player
        # local 2P sur un seul appareil : on affiche "victoire" côté J1
        return winner == 1
        

    def _after_sow_rules(self, last_idx: int):
        """Règles officielles : CAPTURE > RELAIS > STOP."""
        opponent = 2 if self.player == 1 else 1

        # fin si un camp est vide
        def _no_seeds_side(p):
            rows = self.side_rows(p)
            return sum(self.pits[r*COLS + c] for r in rows for c in range(COLS)) == 0

        if _no_seeds_side(1) or _no_seeds_side(2):
            winner = 2 if _no_seeds_side(1) else 1

            # Son selon résultat LOCAL (pas absolu)
            if self._is_local_winner(winner):
                self._sbank.play("win")
            else:
                self._sbank.play("lose")

            self.running_anim = False
            self._show_end_dialog(winner)
            return


        r, c = divmod(last_idx, COLS)
        seeds_here = self.pits[last_idx]

        def front_row_of(p): return 2 if p == 1 else 1
        def back_row_of(p):  return 3 if p == 1 else 0
        def effective_front_row_of(p):
            fr = front_row_of(p)
            if all(self.pits[fr*COLS + i] == 0 for i in range(COLS)):
                return back_row_of(p)
            return fr

        # 1) CAPTURE si sur ta 1re rangée et en face > 0 (rangée 'effective')
        if r == front_row_of(self.player):
            opp_front_eff = effective_front_row_of(opponent)
            opp_idx = opp_front_eff * COLS + c
            if self.pits[opp_idx] > 0:
                captured = self.pits[opp_idx] + self.pits[last_idx]
                self.pits[opp_idx] = 0
                self.pits[last_idx] = 0
                self.update_counts()
                self._sbank.play("capture")
                path = self.boustro_path(self.player)
                pos = path.index(last_idx)
                return self._animate_capture(
                    last_idx, opp_idx, captured,
                    then_continue=lambda: self._sow_loop(path, pos, captured)
                )

        # 2) RELAIS si la case n’était pas vide (>1)
        if seeds_here > 1:
            pickup = seeds_here
            self.pits[last_idx] = 0
            self.update_counts()
            path = self.boustro_path(self.player)
            pos = path.index(last_idx)
            return self._sow_loop(path, pos, pickup)

        # 3) STOP
        self.player = opponent
        self._apply_hand_asset(self.player)
        if self.hand:
            self.remove_widget(self.hand); self.add_widget(self.hand)
        self.running_anim = False
        self._sbank.play("stop")

        # NE JAMAIS déclencher l’IA en ligne
        if not self.online_mode:
            self._maybe_ai_turn()
        return

    # ---------- IA (très simple) ----------
    def _ai_choose_start(self):
        import random
        rows = self.side_rows(self.ai_player)
        choices = [
            r * COLS + c
            for r in rows
            for c in range(COLS)
            if self.pits[r * COLS + c] > 0
        ]
        return random.choice(choices) if choices else None

    def _ai_play(self, *_):
        if not (self.vs_ai and self.player == self.ai_player) or self.running_anim:
            return
        self._apply_hand_asset(self.player)
        idx = self._ai_choose_start()
        if idx is None:
            self.player = 1 if self.ai_player == 2 else 2
            self.running_anim = False
            return
        self.play_move(idx, step=+1)

    def _maybe_ai_turn(self): 
        if self.vs_ai and self.player == self.ai_player:
            self._sbank.play("ai")
            Clock.schedule_once(self._ai_play, 0.2)

    def _show_end_dialog(self, winner: int):
        """Fenêtre de fin avec bannière image + boutons Rejouer / Menu."""
        app = None
        try:
            app = MDApp.get_running_app()
        except Exception:
            pass

        local_win = self._is_local_winner(winner)

        if local_win:
            title = "FANDRESENA!"
            subtitle = "Belle victoire !" if self.vs_ai else "Félicitations !"
            banner_path = ASSETS.get("end_win", "")
        else:
            title = "RESY ALOHA!"
            subtitle = "Dommage, retente ta chance."
            banner_path = ASSETS.get("end_lose", "")


        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=(0, dp(4), 0, 0), size_hint_y=None)
        content.bind(minimum_height=lambda *_: setattr(content, "height", content.minimum_height))

        if banner_path and os.path.exists(banner_path):
            content.add_widget(Image(source=banner_path, allow_stretch=True, keep_ratio=True,
                                    size_hint_y=None, height=dp(140)))

        def _replay(*_):
            if getattr(self, "_end_dialog", None):
                self._end_dialog.dismiss()
            if app and hasattr(app, "replay_current_game"):
                app.replay_current_game()

        def _menu(*_):
            if getattr(self, "_end_dialog", None):
                self._end_dialog.dismiss()
            if app and hasattr(app, "go_home"):
                app.go_home()

        btn_menu = MDFlatButton(text="MENU", on_release=_menu)
        btn_replay = MDFlatButton(text="REJOUER", on_release=_replay)

        try:
            self._end_dialog = MDDialog(
                title=title,
                text=subtitle,
                type="custom",
                content_cls=content,
                buttons=[btn_menu, btn_replay],
            )
            self._end_dialog.open()
        except Exception:
            print(f"{title} - {subtitle}")
