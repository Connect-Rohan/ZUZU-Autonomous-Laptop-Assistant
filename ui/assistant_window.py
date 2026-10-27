"""
ZUZU – Animated Tkinter Assistant Window
All GUI updates happen on the main thread via .after().
Background threads post work items via _event_queue.
"""

import tkinter as tk
from tkinter import font as tkfont
import math
import threading
import queue
import time
from config import (
    APP_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT,
    BG_COLOR, ACCENT_COLOR, ACCENT2_COLOR
)

# ── Colour palette ─────────────────────────────────────────────
CLR_BG          = BG_COLOR
CLR_PANEL       = "#13132b"
CLR_ACCENT      = ACCENT_COLOR
CLR_ACCENT2     = ACCENT2_COLOR
CLR_TEXT        = "#e8e8f0"
CLR_SUBTEXT     = "#9090b0"
CLR_IDLE        = "#4a4a72"
CLR_LISTEN      = "#7c5cfc"
CLR_PROCESS     = "#00d4ff"
CLR_SPEAK       = "#00e5a0"
CLR_ERROR       = "#ff4f6a"

# Pulsar ring radii (inner → outer)
RING_RADII      = [80, 105, 130, 158]
CORE_RADIUS     = 58


class AssistantWindow:
    """Main ZUZU application window."""

    def __init__(self, on_text_command=None, on_toggle_listen=None, on_quit=None):
        """
        Parameters
        ----------
        on_text_command   : callable(text) – called when user sends a typed command
        on_toggle_listen  : callable()     – called when listen/stop button clicked
        on_quit           : callable()     – called on window close / quit
        """
        self._on_text_command  = on_text_command or (lambda t: None)
        self._on_toggle_listen = on_toggle_listen or (lambda: None)
        self._on_quit          = on_quit or (lambda: None)

        self._event_queue: queue.Queue = queue.Queue()
        self._state  = "idle"   # idle | listening | processing | speaking | error
        self._anim_t = 0.0      # animation clock
        self._running = True

        self._ring_ids   = []
        self._core_id    = None
        self._glow_ids   = []
        self._particles  = []   # [(x,y,r,alpha,tag)]
        self._history    = []   # list of strings

        self._build_window()
        self._build_header()
        self._build_canvas()
        self._build_status()
        self._build_transcript()
        self._build_input_area()
        self._build_action_history()
        self._build_footer()
        self._animate()
        self._poll_events()

    # ── Window construction ────────────────────────────────────

    def _build_window(self):
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.configure(bg=CLR_BG)
        self.root.resizable(False, False)

        # Centre on screen
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x  = (sw - WINDOW_WIDTH)  // 2
        y  = (sh - WINDOW_HEIGHT) // 2
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")
        self.root.protocol("WM_DELETE_WINDOW", self._handle_quit)

        # Custom fonts
        self._font_title    = tkfont.Font(family="Segoe UI", size=22, weight="bold")
        self._font_subtitle = tkfont.Font(family="Segoe UI", size=9)
        self._font_status   = tkfont.Font(family="Segoe UI Semibold", size=12, weight="bold")
        self._font_body     = tkfont.Font(family="Segoe UI", size=10)
        self._font_small    = tkfont.Font(family="Segoe UI", size=9)
        self._font_mono     = tkfont.Font(family="Consolas", size=9)

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=CLR_BG)
        hdr.pack(fill="x", padx=20, pady=(18, 0))

        tk.Label(hdr, text="ZUZU", font=self._font_title,
                 fg=CLR_ACCENT, bg=CLR_BG).pack(side="left")
        tk.Label(hdr, text=" AI Assistant", font=self._font_subtitle,
                 fg=CLR_SUBTEXT, bg=CLR_BG).pack(side="left", padx=(2,0), pady=(8,0))

        # Mic indicator dot
        self._mic_dot = tk.Canvas(hdr, width=12, height=12, bg=CLR_BG,
                                   highlightthickness=0)
        self._mic_dot.pack(side="right", pady=(6,0))
        self._mic_circle = self._mic_dot.create_oval(1, 1, 11, 11, fill=CLR_IDLE,
                                                      outline="")
        sep = tk.Frame(self.root, bg=CLR_PANEL, height=1)
        sep.pack(fill="x", padx=20, pady=(8, 0))

    def _build_canvas(self):
        """Central animation canvas."""
        self._canvas_size = 330
        cv_frame = tk.Frame(self.root, bg=CLR_BG)
        cv_frame.pack(pady=(10, 0))
        self.canvas = tk.Canvas(cv_frame,
                                width=self._canvas_size,
                                height=self._canvas_size,
                                bg=CLR_BG, highlightthickness=0)
        self.canvas.pack()
        self._cx = self._canvas_size // 2
        self._cy = self._canvas_size // 2
        self._draw_static_rings()
        self._draw_core()

    def _draw_static_rings(self):
        """Draw the outermost decorative ring once."""
        r = RING_RADII[-1] + 22
        self.canvas.create_oval(self._cx - r, self._cy - r,
                                 self._cx + r, self._cy + r,
                                 outline=CLR_PANEL, width=1)

    def _draw_core(self):
        """Initial core circle."""
        r = CORE_RADIUS
        self._core_id = self.canvas.create_oval(
            self._cx - r, self._cy - r, self._cx + r, self._cy + r,
            fill=CLR_IDLE, outline="")

        # ZUZU label inside core
        self.canvas.create_text(self._cx, self._cy, text="Z",
                                 font=tkfont.Font(family="Segoe UI", size=28, weight="bold"),
                                 fill="#ffffff", tags="core_label")

    def _build_status(self):
        self._status_var = tk.StringVar(value="Initializing…")
        frm = tk.Frame(self.root, bg=CLR_BG)
        frm.pack(pady=(4, 0))
        self._status_lbl = tk.Label(frm, textvariable=self._status_var,
                                    font=self._font_status,
                                    fg=CLR_ACCENT, bg=CLR_BG)
        self._status_lbl.pack()

    def _build_transcript(self):
        frm = tk.Frame(self.root, bg=CLR_PANEL, bd=0, relief="flat")
        frm.pack(fill="x", padx=20, pady=(6, 0))
        tk.Label(frm, text="LAST HEARD", font=self._font_small,
                 fg=CLR_SUBTEXT, bg=CLR_PANEL).pack(anchor="w", padx=8, pady=(4, 0))
        self._transcript_var = tk.StringVar(value="—")
        tk.Label(frm, textvariable=self._transcript_var,
                 font=self._font_body, fg=CLR_TEXT, bg=CLR_PANEL,
                 wraplength=WINDOW_WIDTH - 60, justify="left").pack(
                     anchor="w", padx=8, pady=(0, 6))

    def _build_input_area(self):
        frm = tk.Frame(self.root, bg=CLR_BG)
        frm.pack(fill="x", padx=20, pady=(8, 0))
        tk.Label(frm, text="Type a command (text fallback):",
                 font=self._font_small, fg=CLR_SUBTEXT, bg=CLR_BG).pack(anchor="w")

        row = tk.Frame(frm, bg=CLR_BG)
        row.pack(fill="x", pady=(2, 0))

        self._cmd_var = tk.StringVar()
        entry = tk.Entry(row, textvariable=self._cmd_var,
                         font=self._font_body,
                         bg=CLR_PANEL, fg=CLR_TEXT,
                         insertbackground=CLR_ACCENT,
                         relief="flat", bd=4)
        entry.pack(side="left", fill="x", expand=True, ipady=4)
        entry.bind("<Return>", self._handle_send)

        self._send_btn = tk.Button(row, text="Send",
                                   font=self._font_small,
                                   bg=CLR_ACCENT, fg="#ffffff",
                                   activebackground=CLR_ACCENT2,
                                   relief="flat", bd=0, padx=12,
                                   cursor="hand2",
                                   command=self._handle_send)
        self._send_btn.pack(side="left", padx=(6, 0), ipady=4)

    def _build_action_history(self):
        frm = tk.Frame(self.root, bg=CLR_PANEL)
        frm.pack(fill="x", padx=20, pady=(8, 0))
        tk.Label(frm, text="RECENT ACTIONS", font=self._font_small,
                 fg=CLR_SUBTEXT, bg=CLR_PANEL).pack(anchor="w", padx=8, pady=(4, 0))
        self._history_text = tk.Text(frm, height=4,
                                     font=self._font_mono,
                                     bg=CLR_PANEL, fg=CLR_TEXT,
                                     relief="flat", bd=0,
                                     state="disabled",
                                     wrap="word")
        self._history_text.pack(fill="x", padx=8, pady=(0, 6))

    def _build_footer(self):
        frm = tk.Frame(self.root, bg=CLR_BG)
        frm.pack(pady=(10, 12))

        self._listen_btn = tk.Button(
            frm, text="⏹  Stop Listening",
            font=self._font_body,
            bg=CLR_PANEL, fg=CLR_TEXT,
            activebackground=CLR_IDLE,
            relief="flat", bd=0, padx=14, pady=6,
            cursor="hand2",
            command=self._handle_toggle_listen
        )
        self._listen_btn.pack(side="left", padx=6)

        quit_btn = tk.Button(
            frm, text="✕  Quit",
            font=self._font_body,
            bg=CLR_ERROR, fg="#ffffff",
            activebackground="#cc3350",
            relief="flat", bd=0, padx=14, pady=6,
            cursor="hand2",
            command=self._handle_quit
        )
        quit_btn.pack(side="left", padx=6)

    # ── Animation engine ───────────────────────────────────────

    def _state_colour(self):
        return {
            "idle":       CLR_IDLE,
            "listening":  CLR_LISTEN,
            "processing": CLR_PROCESS,
            "speaking":   CLR_SPEAK,
            "error":      CLR_ERROR,
        }.get(self._state, CLR_IDLE)

    def _animate(self):
        if not self._running:
            return
        self._anim_t += 0.04
        t = self._anim_t
        col = self._state_colour()

        # Clear previous dynamic elements
        self.canvas.delete("ring")
        self.canvas.delete("particle")

        if self._state == "listening":
            self._animate_listening(t, col)
        elif self._state == "processing":
            self._animate_processing(t, col)
        elif self._state == "speaking":
            self._animate_speaking(t, col)
        else:
            self._animate_idle(t, col)

        # Redraw core on top
        r = CORE_RADIUS + (3 * math.sin(t * 2))
        self.canvas.coords(self._core_id,
                           self._cx - r, self._cy - r,
                           self._cx + r, self._cy + r)
        self.canvas.itemconfig(self._core_id, fill=col)
        self.canvas.tag_raise("core_label")

        # Mic indicator pulse
        mic_col = col if self._state != "idle" else CLR_IDLE
        self._mic_dot.itemconfig(self._mic_circle, fill=mic_col)

        self.root.after(33, self._animate)   # ~30 fps

        
    def _animate_idle(self, t, col):
        """Slow single-ring breathe."""
        phase = 0.5 + 0.5 * math.sin(t)
        r = RING_RADII[0] + 8 * phase

        self.canvas.create_oval(
            self._cx - r, self._cy - r,
            self._cx + r, self._cy + r,
            outline=col, width=1, tags="ring"
        )


    def _animate_listening(self, t, col):
        """Expanding pulsing rings."""
        for i, base_r in enumerate(RING_RADII):
            phase = (t - i * 0.4) % (2 * math.pi)
            expand = 14 * math.sin(phase) if math.sin(phase) > 0 else 0
            r = base_r + expand
            alpha = max(0, int(180 * math.sin(phase))) if math.sin(phase) > 0 else 20
            self.canvas.create_oval(
                self._cx - r, self._cy - r, self._cx + r, self._cy + r,
                outline=self._hex_with_alpha(col, alpha),
                width=2 - i * 0.3, tags="ring")

    def _animate_processing(self, t, col):
        """Spinning arc."""
        for i in range(6):
            angle = t * 3 + i * (math.pi / 3)
            for frac, alpha in [(0.85, 200), (0.92, 120), (1.0, 50)]:
                r = RING_RADII[1] * frac
                x = self._cx + r * math.cos(angle)
                y = self._cy + r * math.sin(angle)
                pr = 4 - frac * 2
                self.canvas.create_oval(x - pr, y - pr, x + pr, y + pr,
                                        fill=self._hex_with_alpha(col, alpha),
                                        outline="", tags="particle")

    def _animate_speaking(self, t, col):
        """Radiating wave rings."""
        for i in range(3):
            wave = (t * 1.8 + i * 1.1) % (2 * math.pi)
            r = RING_RADII[0] + (RING_RADII[-1] - RING_RADII[0]) * (wave / (2 * math.pi))
            alpha = int(160 * (1 - wave / (2 * math.pi)))
            self.canvas.create_oval(
                self._cx - r, self._cy - r, self._cx + r, self._cy + r,
                outline=self._hex_with_alpha(col, alpha), width=2, tags="ring")

    # ── Colour helpers ─────────────────────────────────────────

    @staticmethod
    def _alpha_hex(a: int) -> str:
        """Tkinter doesn't support #RRGGBBAA, so we simulate via the colour string trick."""
        # Not actually used in create_oval outline; kept for reference.
        return format(min(255, max(0, a)), "02x")

    @staticmethod
    def _hex_with_alpha(base_hex: str, alpha: int) -> str:
        """
        Blend base_hex colour toward BG by alpha (0=invisible, 255=full).
        Returns a valid #RRGGBB Tkinter colour string.
        """
        # Parse base
        base_hex = base_hex.lstrip("#")
        if len(base_hex) == 3:
            base_hex = "".join(c * 2 for c in base_hex)
        r = int(base_hex[0:2], 16)
        g = int(base_hex[2:4], 16)
        b = int(base_hex[4:6], 16)
        # BG: #0d0d1a → (13,13,26)
        bg_r, bg_g, bg_b = 13, 13, 26
        a = alpha / 255
        rr = int(r * a + bg_r * (1 - a))
        gg = int(g * a + bg_g * (1 - a))
        bb = int(b * a + bg_b * (1 - a))
        return f"#{rr:02x}{gg:02x}{bb:02x}"

    # ── Event queue (thread-safe GUI updates) ──────────────────

    def _poll_events(self):
        """Drain the event queue on the main thread every 50 ms."""
        try:
            while True:
                fn = self._event_queue.get_nowait()
                fn()
        except queue.Empty:
            pass
        if self._running:
            self.root.after(50, self._poll_events)

    def post(self, fn):
        """Schedule a callable to run on the Tkinter main thread."""
        self._event_queue.put(fn)

    # ── Public state-update methods (call from any thread) ─────

    def set_state(self, state: str, status_text: str = ""):
        """Change the visual state.  Safe to call from background threads."""
        def _update():
            self._state = state
            if status_text:
                self._status_var.set(status_text)
            # Update listen button label
            if state == "listening":
                self._listen_btn.config(text="⏹  Stop Listening")
            elif state == "idle":
                self._listen_btn.config(text="▶  Start Listening")
        self.post(_update)

    def show_transcript(self, text: str):
        def _update():
            self._transcript_var.set(text or "—")
        self.post(_update)

    def add_history(self, entry: str):
        def _update():
            self._history.append(entry)
            if len(self._history) > 50:
                self._history = self._history[-50:]
            self._history_text.config(state="normal")
            self._history_text.delete("1.0", "end")
            display = self._history[-6:]   # show last 6
            self._history_text.insert("end", "\n".join(display))
            self._history_text.config(state="disabled")
            self._history_text.see("end")
        self.post(_update)

    def show_error(self, msg: str):
        def _update():
            self._state = "error"
            self._status_var.set(f"⚠ {msg}")
        self.post(_update)

    def update_status(self, text: str):
        self.post(lambda: self._status_var.set(text))

    # ── User-action handlers ───────────────────────────────────

    def _handle_send(self, event=None):
        text = self._cmd_var.get().strip()
        if text:
            self._cmd_var.set("")
            self.show_transcript(text)
            threading.Thread(target=self._on_text_command,
                             args=(text,), daemon=True).start()

    def _handle_toggle_listen(self):
        threading.Thread(target=self._on_toggle_listen, daemon=True).start()

    def _handle_quit(self):
        self._running = False
        threading.Thread(target=self._on_quit, daemon=True).start()
        # Give callbacks ~500 ms to clean up, then destroy
        self.root.after(500, self.root.destroy)

    # ── Main loop ──────────────────────────────────────────────

    def run(self):
        self.root.mainloop()

    def close(self):
        """Close from a background thread."""
        self.post(self.root.destroy)
