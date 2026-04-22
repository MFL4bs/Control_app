import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import cv2
import time
import os
import sys
from PIL import Image, ImageTk
from gesture_detector import scan_cameras, GestureDetector
from action_executor import execute_action
from config_manager import (
    get_all_gestures, get_available_actions, update_gesture,
    get_settings, update_setting, load_config, save_config,
    add_gesture, delete_gesture
)

def _res(filename):
    """
    Resuelve rutas de archivos de recursos (logos, iconos).
    - En .exe: busca primero junto al ejecutable, luego en _MEIPASS.
    - En desarrollo: usa la carpeta del script.
    """
    if getattr(sys, 'frozen', False):
        # Primero buscar junto al .exe (permite reemplazar recursos)
        p = os.path.join(os.path.dirname(sys.executable), filename)
        if os.path.exists(p):
            return p
        # Fallback a _MEIPASS (recursos empaquetados)
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

# ── Paleta de colores ──────────────────────────────────────────────────────────
BG       = "#0d1117"   # GitHub dark — casi negro azulado
PANEL    = "#161b22"   # sidebar oscuro
CARD     = "#1c2333"   # cards con profundidad
ACCENT   = "#1f3a5f"   # azul marino selección
BLUE     = "#2f81f7"   # azul brillante
PURPLE   = "#a371f7"   # violeta vivo
GREEN    = "#2ea043"   # verde saturado
RED      = "#da3633"   # rojo profundo
YELLOW   = "#e3b341"   # ámbar dorado
TEAL     = "#1f6feb"   # azul acento secundario
FG       = "#e6edf3"   # blanco suave
FG_DIM   = "#7d8590"   # gris medio
BORDER   = "#30363d"   # borde sutil
FONT     = "Segoe UI"

def _lighten(hex_color, amount=30):
    r, g, b = int(hex_color[1:3],16), int(hex_color[3:5],16), int(hex_color[5:7],16)
    r, g, b = min(255,r+amount), min(255,g+amount), min(255,b+amount)
    return f"#{r:02x}{g:02x}{b:02x}"

def _darken(hex_color, amount=20):
    r, g, b = int(hex_color[1:3],16), int(hex_color[3:5],16), int(hex_color[5:7],16)
    r, g, b = max(0,r-amount), max(0,g-amount), max(0,b-amount)
    return f"#{r:02x}{g:02x}{b:02x}"

class RoundedButton(tk.Button):
    """Botón estilizado con padding generoso para apariencia redondeada."""
    def __init__(self, parent, text, command, color=BLUE, fg="#ffffff",
                 radius=8, padx=22, pady=10, font_size=10, **kw):
        self._color = color
        self._fg    = fg
        super().__init__(parent, text=text, command=command,
                         bg=color, fg=fg, font=(FONT, font_size, "bold"),
                         relief="flat", cursor="hand2", bd=0,
                         activebackground=_lighten(color, 20),
                         activeforeground=fg,
                         padx=padx, pady=pady, **kw)
        self.bind("<Enter>", lambda e: super(RoundedButton, self).config(bg=_lighten(color, 20)))
        self.bind("<Leave>", lambda e: super(RoundedButton, self).config(bg=color))

    def config(self, **kw):
        if "state" in kw and kw["state"] == "disabled":
            kw.setdefault("bg", _darken(self._color, 40))
            kw.setdefault("fg", FG_DIM)
            kw.setdefault("cursor", "")
        elif "state" in kw and kw["state"] == "normal":
            kw.setdefault("bg", self._color)
            kw.setdefault("fg", self._fg)
            kw.setdefault("cursor", "hand2")
        super().config(**kw)

def styled_btn(parent, text, command, color=BLUE, fg=BG, **kw):
    return RoundedButton(parent, text, command, color=color, fg=fg, **kw)

def card_frame(parent, **kw):
    f = tk.Frame(parent, bg=CARD, relief="flat",
                 highlightbackground=BORDER, highlightthickness=1, **kw)
    return f

class GestureControlApp:
    def __init__(self, root, preloaded_cameras=None):
        self.root = root
        self.root.title("Gesture Control - MF LABS")
        self.root.geometry("1100x700")
        self.root.configure(bg=BG)
        self.root.minsize(900, 600)
        try:
            self.root.iconbitmap(_res("logo.ico"))
            icon_img = Image.open(_res("logo_sidebar.png"))
            icon_img = icon_img.resize((64, 64), Image.LANCZOS)
            self._taskbar_icon = ImageTk.PhotoImage(icon_img)
            self.root.wm_iconphoto(True, self._taskbar_icon)
        except Exception:
            pass

        self.running   = False
        self.cap       = None
        self.detector  = None
        self.cam_thread= None
        self._frame_queue = queue.Queue(maxsize=2)
        self.last_action_text = ""
        self.pulse_after = None
        self.overlay   = None
        self._overlay_drag = {}
        self._available_cams = preloaded_cameras or []

        self._build_ui()
        if preloaded_cameras:
            self._populate_cameras(preloaded_cameras)
            if preloaded_cameras:
                threading.Thread(target=self._auto_start, daemon=True).start()
        else:
            self._scan_cameras_async(auto_start=True)

    def _auto_start(self):
        """Prueba todas las cámaras disponibles en orden hasta encontrar una con señal."""
        for i, cam in enumerate(self._available_cams):
            cap = self._open_camera(cam["index"])
            if cap:
                self.cap = cap
                # Seleccionar en el combo la cámara que funcionó
                self.root.after(0, lambda i=i: [
                    self.cam_combo.current(i),
                    self.cam_var.set(self.cam_combo["values"][i]),
                ])
                self.root.after(0, self._start_capture)
                return
        self.root.after(0, lambda: self.cam_label.configure(
            image="", text="⚠️ No se detectó señal en ninguna cámara\nUsa ▶ Iniciar o ⚡ Forzar"))

    # ── UI principal ──────────────────────────────────────────────────────────
    def _build_ui(self):
        # Sidebar con borde derecho sutil
        sidebar = tk.Frame(self.root, bg=PANEL, width=210)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        # Borde derecho
        tk.Frame(self.root, bg=BORDER, width=1).pack(side="left", fill="y")

        # Logo MF LABS
        try:
            logo_img = Image.open(_res("logo_sidebar.png"))
            logo_img = logo_img.resize((120, 120), Image.LANCZOS)
            self._logo_imgtk = ImageTk.PhotoImage(logo_img)
            tk.Label(sidebar, image=self._logo_imgtk, bg=PANEL).pack(pady=(20, 4))
        except Exception:
            tk.Label(sidebar, text="✋", bg=PANEL, fg=BLUE, font=(FONT, 32)).pack(pady=(30, 4))
        tk.Label(sidebar, text="Gesture\nControl", bg=PANEL, fg=FG,
                 font=(FONT, 14, "bold"), justify="center").pack()
        tk.Label(sidebar, text="v2.0  |  MF LABS", bg=PANEL, fg=FG_DIM,
                 font=(FONT, 8)).pack(pady=(0, 20))
        tk.Frame(sidebar, bg=BORDER, height=1).pack(fill="x", padx=12, pady=(0,8))

        self.nav_btns = {}
        pages = [("📷  Cámara", "camera"), ("🤚  Gestos", "gestures"),
                 ("⚙️  Ajustes", "settings")]
        for label, key in pages:
            btn = tk.Button(sidebar, text=label, bg=PANEL, fg=FG_DIM,
                            font=(FONT, 10), relief="flat", anchor="w",
                            padx=20, pady=11, cursor="hand2",
                            activebackground=ACCENT, activeforeground=BLUE,
                            borderwidth=0,
                            command=lambda k=key: self._show_page(k))
            btn.pack(fill="x", padx=8, pady=1)
            self.nav_btns[key] = btn

        tk.Frame(sidebar, bg=BORDER, height=1).pack(fill="x", padx=12, pady=10)

        # Botón mini overlay
        RoundedButton(sidebar, "⧉  Mini Overlay", self._toggle_overlay,
                      color=PURPLE, fg=FG, radius=8).pack(padx=12, pady=2)

        # Status dot
        self.status_dot = tk.Label(sidebar, text="⬤  Inactivo", bg=PANEL,
                                    fg=FG_DIM, font=(FONT, 9))
        self.status_dot.pack(side="bottom", pady=16)
        tk.Frame(sidebar, bg=BORDER, height=1).pack(side="bottom", fill="x", padx=12)

        # Contenedor de páginas
        self.content = tk.Frame(self.root, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)

        self.pages = {}
        self._build_camera_page()
        self._build_gestures_page()
        self._build_settings_page()
        self._show_page("camera")

    def _show_page(self, name):
        for k, f in self.pages.items():
            f.pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        for k, b in self.nav_btns.items():
            active = k == name
            b.config(bg=ACCENT if active else PANEL,
                     fg=BLUE  if active else FG_DIM,
                     font=(FONT, 10, "bold") if active else (FONT, 10))

    # ── Página Cámara ─────────────────────────────────────────────────────────
    def _build_camera_page(self):
        page = tk.Frame(self.content, bg=BG)
        self.pages["camera"] = page

        # Header con título + info bar + controles
        hdr = tk.Frame(page, bg=BG)
        hdr.pack(fill="x", padx=20, pady=(14,6))

        # Título
        tk.Label(hdr, text="Monitor de Cámara", bg=BG, fg=FG,
                 font=(FONT, 15, "bold")).pack(side="left")

        # Info: GESTO / ACCIÓN / FPS — pegados al título
        self.gesture_card = card_frame(hdr, padx=10, pady=6)
        self.gesture_card.pack(side="left", padx=(16,4), pady=4)
        tk.Label(self.gesture_card, text="GESTO", bg=CARD, fg=FG_DIM, font=(FONT, 7)).pack()
        self.gesture_val = tk.Label(self.gesture_card, text="---", bg=CARD,
                                     fg=BLUE, font=(FONT, 12, "bold"))
        self.gesture_val.pack()

        self.action_card = card_frame(hdr, padx=10, pady=6)
        self.action_card.pack(side="left", padx=4, pady=4)
        tk.Label(self.action_card, text="ACCIÓN", bg=CARD, fg=FG_DIM, font=(FONT, 7)).pack()
        self.action_val = tk.Label(self.action_card, text="---", bg=CARD,
                                    fg=GREEN, font=(FONT, 12, "bold"))
        self.action_val.pack()

        self.fps_card = card_frame(hdr, padx=10, pady=6)
        self.fps_card.pack(side="left", padx=4, pady=4)
        tk.Label(self.fps_card, text="FPS", bg=CARD, fg=FG_DIM, font=(FONT, 7)).pack()
        self.fps_val = tk.Label(self.fps_card, text="0", bg=CARD,
                                 fg=YELLOW, font=(FONT, 12, "bold"))
        self.fps_val.pack()

        # Controles de cámara — lado derecho
        cam_frame = card_frame(hdr)
        cam_frame.pack(side="right", padx=(0,4))
        tk.Label(cam_frame, text="Cam:", bg=CARD, fg=FG_DIM,
                 font=(FONT, 9)).pack(side="left", padx=(10,4), pady=8)
        self.cam_var = tk.StringVar(value="Buscando...")
        self.cam_combo = ttk.Combobox(cam_frame, textvariable=self.cam_var,
                                       width=13, state="readonly",
                                       font=(FONT, 9))
        self.cam_combo.pack(side="left", padx=4, pady=8)
        styled_btn(cam_frame, "🔄", self._scan_cameras_async,
                   color=ACCENT, fg=BLUE, padx=10, pady=8).pack(side="left", padx=(0,3), pady=6)
        styled_btn(cam_frame, "⚡ Forzar", self._force_reconnect,
                   color="#92400e", fg="#fbbf24", padx=12, pady=8).pack(side="left", padx=(0,3), pady=6)
        self.start_btn = styled_btn(cam_frame, "▶ Iniciar", self.start_camera,
                                    color="#166534", fg="#4ade80", padx=12, pady=8)
        self.start_btn.pack(side="left", padx=(0,3), pady=6)
        self.stop_btn = styled_btn(cam_frame, "⏹ Detener", self.stop_camera,
                                   color="#7f1d1d", fg="#f87171", padx=12, pady=8)
        self.stop_btn.pack(side="left", padx=(0,8), pady=6)
        self.stop_btn.config(state="disabled")

        # Video — ocupa todo el espacio restante
        video_card = card_frame(page)
        video_card.pack(fill="both", expand=True, padx=20, pady=(0,14))

        self.cam_label = tk.Label(video_card, bg="#0a0a14",
                                   text="⏳ Conectando cámara...",
                                   fg=FG_DIM, font=(FONT, 13))
        self.cam_label.pack(fill="both", expand=True, padx=3, pady=3)

        # Fila vacía para mantener padding inferior
        tk.Frame(page, bg=BG, height=4).pack()

    # ── Página Gestos ─────────────────────────────────────────────────────────
    def _build_gestures_page(self):
        page = tk.Frame(self.content, bg=BG)
        self.pages["gestures"] = page

        hdr = tk.Frame(page, bg=BG)
        hdr.pack(fill="x", padx=20, pady=(20,10))
        tk.Label(hdr, text="Gestos Configurados", bg=BG, fg=FG,
                 font=(FONT, 16, "bold")).pack(side="left")
        styled_btn(hdr, "+ Nuevo Gesto", self._open_add_gesture_dialog,
                   color=GREEN, fg=BG).pack(side="right")

        # Tabla con scroll
        table_card = card_frame(page)
        table_card.pack(fill="both", expand=True, padx=20, pady=(0,20))

        cols = ("Clave", "Nombre", "Descripción", "Acción")
        self.tree = ttk.Treeview(table_card, columns=cols, show="headings",
                                  selectmode="browse")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=CARD, foreground=FG,
                         fieldbackground=CARD, rowheight=36,
                         font=(FONT, 10), borderwidth=0)
        style.configure("Treeview.Heading", background=ACCENT, foreground=BLUE,
                         font=(FONT, 10, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", ACCENT)],
                  foreground=[("selected", BLUE)])

        widths = [120, 160, 240, 160]
        for col, w in zip(cols, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="center")

        vsb = ttk.Scrollbar(table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        # Botones de acción sobre fila
        row_btns = tk.Frame(page, bg=BG)
        row_btns.pack(pady=(0,16))
        styled_btn(row_btns, "✏️  Editar acción", self._edit_selected_gesture,
                   color=BLUE, fg=BG).pack(side="left", padx=6)
        styled_btn(row_btns, "🗑️  Eliminar", self._delete_selected_gesture,
                   color=RED, fg=FG).pack(side="left", padx=6)

        self._refresh_gesture_table()

    def _refresh_gesture_table(self):
        self.tree.delete(*self.tree.get_children())
        for key, data in get_all_gestures().items():
            self.tree.insert("", "end", iid=key,
                             values=(key, data["name"], data["description"], data["action"]))

    def _open_add_gesture_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Nuevo Gesto")
        dlg.geometry("420x340")
        dlg.configure(bg=BG)
        dlg.grab_set()

        fields = [("Clave (sin espacios)", "key"), ("Nombre", "name"),
                  ("Descripción", "description")]
        vars_ = {}
        for i, (label, key) in enumerate(fields):
            tk.Label(dlg, text=label, bg=BG, fg=FG_DIM,
                     font=(FONT, 10)).grid(row=i, column=0, padx=20, pady=10, sticky="w")
            v = tk.StringVar()
            vars_[key] = v
            tk.Entry(dlg, textvariable=v, bg=CARD, fg=FG, insertbackground=FG,
                     font=(FONT, 11), relief="flat",
                     width=28).grid(row=i, column=1, padx=10, pady=10)

        tk.Label(dlg, text="Acción", bg=BG, fg=FG_DIM,
                 font=(FONT, 10)).grid(row=3, column=0, padx=20, pady=10, sticky="w")
        action_var = tk.StringVar(value="none")
        ttk.Combobox(dlg, textvariable=action_var,
                     values=get_available_actions(),
                     state="readonly", width=26,
                     font=(FONT, 11)).grid(row=3, column=1, padx=10, pady=10)

        def save():
            k = vars_["key"].get().strip().replace(" ", "_")
            n = vars_["name"].get().strip()
            d = vars_["description"].get().strip()
            a = action_var.get()
            if not k or not n:
                messagebox.showerror("Error", "Clave y nombre son obligatorios", parent=dlg)
                return
            add_gesture(k, n, d, a)
            self._refresh_gesture_table()
            dlg.destroy()

        styled_btn(dlg, "💾  Guardar", save, GREEN, BG).grid(
            row=4, column=0, columnspan=2, pady=20)

    def _edit_selected_gesture(self):
        sel = self.tree.focus()
        if not sel:
            messagebox.showwarning("Aviso", "Selecciona un gesto primero")
            return
        data = get_all_gestures()[sel]

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Editar: {data['name']}")
        dlg.geometry("380x180")
        dlg.configure(bg=BG)
        dlg.grab_set()

        tk.Label(dlg, text=f"Gesto: {data['name']}", bg=BG, fg=FG,
                 font=(FONT, 12, "bold")).pack(pady=(20,10))
        tk.Label(dlg, text="Nueva acción:", bg=BG, fg=FG_DIM,
                 font=(FONT, 10)).pack()
        action_var = tk.StringVar(value=data["action"])
        ttk.Combobox(dlg, textvariable=action_var,
                     values=get_available_actions(),
                     state="readonly", width=28,
                     font=(FONT, 11)).pack(pady=8)

        def save():
            update_gesture(sel, action_var.get())
            self._refresh_gesture_table()
            dlg.destroy()

        styled_btn(dlg, "💾  Guardar", save, GREEN, BG).pack(pady=10)

    def _delete_selected_gesture(self):
        sel = self.tree.focus()
        if not sel:
            messagebox.showwarning("Aviso", "Selecciona un gesto primero")
            return
        if messagebox.askyesno("Confirmar", f"¿Eliminar el gesto '{sel}'?"):
            delete_gesture(sel)
            self._refresh_gesture_table()

    # ── Página Ajustes ────────────────────────────────────────────────────────
    def _build_settings_page(self):
        page = tk.Frame(self.content, bg=BG)
        self.pages["settings"] = page

        # Scroll container
        canvas = tk.Canvas(page, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(page, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=BG)
        scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        tk.Label(scroll_frame, text="Configuración", bg=BG, fg=FG,
                 font=(FONT, 16, "bold")).pack(anchor="w", padx=20, pady=(20,10))

        # ─ Ajustes generales
        self._settings_section(scroll_frame, "⚙️  Ajustes Generales")
        card = card_frame(scroll_frame, padx=20, pady=16)
        card.pack(fill="x", padx=20, pady=(0,16))
        settings = get_settings()
        fields = [
            ("Confianza de detección (0-1)", "detection_confidence", "float"),
            ("Cooldown entre gestos (seg)",   "gesture_cooldown",     "float"),
            ("Paso de volumen (%)",            "volume_step",          "int"),
            ("Paso de brillo (%)",             "brightness_step",      "int"),
            ("Cantidad de scroll",             "scroll_amount",        "int"),
        ]
        self.setting_vars = {}
        for i, (label, key, dtype) in enumerate(fields):
            tk.Label(card, text=label, bg=CARD, fg=FG_DIM,
                     font=(FONT, 10)).grid(row=i, column=0, sticky="w", pady=6)
            v = tk.StringVar(value=str(settings.get(key, "")))
            self.setting_vars[key] = (v, dtype)
            tk.Entry(card, textvariable=v, bg=ACCENT, fg=FG, insertbackground=FG,
                     font=(FONT, 10), relief="flat", width=14).grid(row=i, column=1, padx=16, pady=6)

        # ─ Acciones rápidas
        self._settings_section(scroll_frame, "⚡  Acciones Rápidas")
        card2 = card_frame(scroll_frame, padx=20, pady=16)
        card2.pack(fill="x", padx=20, pady=(0,16))
        config = load_config()
        tk.Label(card2, text="URL navegador", bg=CARD, fg=FG_DIM,
                 font=(FONT, 10)).grid(row=0, column=0, sticky="w", pady=6)
        self.browser_var = tk.StringVar(value=config["custom_actions"].get("open_browser", ""))
        tk.Entry(card2, textvariable=self.browser_var, bg=ACCENT, fg=FG,
                 insertbackground=FG, font=(FONT, 10), relief="flat",
                 width=40).grid(row=0, column=1, padx=16, pady=6)
        tk.Label(card2, text="Atajo personalizado", bg=CARD, fg=FG_DIM,
                 font=(FONT, 10)).grid(row=1, column=0, sticky="w", pady=6)
        self.shortcut_var = tk.StringVar(value=config["custom_actions"].get("custom_shortcut", ""))
        tk.Entry(card2, textvariable=self.shortcut_var, bg=ACCENT, fg=FG,
                 insertbackground=FG, font=(FONT, 10), relief="flat",
                 width=40).grid(row=1, column=1, padx=16, pady=6)

        # ─ Links personalizados
        self._settings_section(scroll_frame, "🔗  Links Personalizados (open_link_1 — open_link_10)")
        links_card = card_frame(scroll_frame, padx=20, pady=16)
        links_card.pack(fill="x", padx=20, pady=(0,16))
        self.link_vars = {}
        links = config.get("custom_links", {})
        for i in range(1, 11):
            key = f"link_{i}"
            tk.Label(links_card, text=f"Link {i}", bg=CARD, fg=FG_DIM,
                     font=(FONT, 10)).grid(row=i-1, column=0, sticky="w", pady=5, padx=(0,8))
            v = tk.StringVar(value=links.get(key, ""))
            self.link_vars[key] = v
            tk.Entry(links_card, textvariable=v, bg=ACCENT, fg=FG,
                     insertbackground=FG, font=(FONT, 10), relief="flat",
                     width=50).grid(row=i-1, column=1, pady=5)

        # ─ Comandos personalizados
        self._settings_section(scroll_frame, "🖥️  Comandos Personalizados (run_command_1 — run_command_10)")
        cmds_card = card_frame(scroll_frame, padx=20, pady=16)
        cmds_card.pack(fill="x", padx=20, pady=(0,24))
        self.cmd_vars = {}
        cmds = config.get("custom_commands", {})
        for i in range(1, 11):
            key = f"cmd_{i}"
            tk.Label(cmds_card, text=f"Cmd {i}", bg=CARD, fg=FG_DIM,
                     font=(FONT, 10)).grid(row=i-1, column=0, sticky="w", pady=5, padx=(0,8))
            v = tk.StringVar(value=cmds.get(key, ""))
            self.cmd_vars[key] = v
            tk.Entry(cmds_card, textvariable=v, bg=ACCENT, fg=FG,
                     insertbackground=FG, font=(FONT, 10), relief="flat",
                     width=50).grid(row=i-1, column=1, pady=5)

        styled_btn(scroll_frame, "💾  Guardar configuración", self._save_settings,
                   GREEN, "#ffffff").pack(pady=(0, 30))

    def _settings_section(self, parent, title):
        tk.Label(parent, text=title, bg=BG, fg=BLUE,
                 font=(FONT, 11, "bold")).pack(anchor="w", padx=20, pady=(10, 4))

    def _save_settings(self):
        for key, (var, dtype) in self.setting_vars.items():
            try:
                value = int(var.get()) if dtype == "int" else float(var.get())
                update_setting(key, value)
            except ValueError:
                messagebox.showerror("Error", f"Valor inválido para '{key}'")
                return
        config = load_config()
        config["custom_actions"]["open_browser"]    = self.browser_var.get()
        config["custom_actions"]["custom_shortcut"] = self.shortcut_var.get()
        if "custom_links" not in config:    config["custom_links"] = {}
        if "custom_commands" not in config: config["custom_commands"] = {}
        for key, var in self.link_vars.items():
            config["custom_links"][key] = var.get().strip()
        for key, var in self.cmd_vars.items():
            config["custom_commands"][key] = var.get().strip()
        save_config(config)
        messagebox.showinfo("✅ Guardado", "Configuración guardada correctamente")

    # ── Cámara ────────────────────────────────────────────────────────────────
    def _populate_cameras(self, cams):
        self._available_cams = cams
        if cams:
            options = [f"{c['name']} (idx {c['index']})" for c in cams]
            self.cam_combo["values"] = options
            self.cam_combo.config(state="readonly")
            self.cam_var.set(options[0])
        else:
            self.cam_combo["values"] = ["Sin cámaras detectadas"]
            self.cam_combo.config(state="disabled")
            self.cam_var.set("Sin cámaras detectadas")

    def _scan_cameras_async(self, auto_start=False):
        self.cam_var.set("Buscando...")
        self.cam_combo.config(state="disabled")
        def _scan():
            cams = scan_cameras()
            self._available_cams = cams
            if cams:
                options = [f"{c['name']} (idx {c['index']})" for c in cams]
                self.root.after(0, lambda: [
                    self.cam_combo.config(values=options, state="readonly"),
                    self.cam_var.set(options[0]),
                ])
                if auto_start:
                    self._auto_start()
            else:
                self.root.after(0, lambda: [
                    self.cam_combo.config(values=["Sin cámaras detectadas"], state="disabled"),
                    self.cam_var.set("Sin cámaras detectadas"),
                    self.cam_label.configure(image="", text="⚠️ No se encontraron cámaras"),
                ])
        threading.Thread(target=_scan, daemon=True).start()

    def _get_selected_cam_index(self):
        try:
            idx = self.cam_combo.current()
            return self._available_cams[idx]["index"]
        except Exception:
            return 0

    def _open_camera(self, cam_idx):
        for backend in [cv2.CAP_DSHOW, cv2.CAP_MSMF, 0]:
            try:
                cap = cv2.VideoCapture(cam_idx, backend) if backend != 0 else cv2.VideoCapture(cam_idx)
                if not cap.isOpened():
                    cap.release()
                    continue
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 30)
                ret, _ = cap.read()
                if not ret:
                    cap.release()
                    continue
                return cap
            except Exception:
                continue
        return None

    def _force_reconnect(self):
        self.running = False
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        self.status_dot.config(text="⬤  Reconectando...", fg=YELLOW)
        self.cam_label.configure(image="", text="⚡ Forzando conexión...")
        threading.Thread(target=self._do_force_start, daemon=True).start()

    def _do_force_start(self):
        # Esperar que el hilo anterior termine (fuera del hilo de Tkinter)
        if self.cam_thread and self.cam_thread.is_alive():
            self.cam_thread.join(timeout=3.0)
        if self.cap:
            self.cap.release()
            self.cap = None
        if self.detector:
            self.detector.release()
            self.detector = None
        cam_idx = self._get_selected_cam_index()
        cap = self._open_camera(cam_idx)
        if not cap:
            self.root.after(0, lambda: [
                self.cam_label.configure(image="", text="❌ No se pudo conectar"),
                self.status_dot.config(text="⬤  Inactivo", fg=FG_DIM),
                self.start_btn.config(state="normal"),
            ])
            return
        self.cap = cap
        self.root.after(0, self._start_capture)

    def start_camera(self):
        self.start_btn.config(state="disabled")
        self.cam_label.configure(image="", text="⏳ Conectando cámara...")
        threading.Thread(target=self._do_start_camera, daemon=True).start()

    def _do_start_camera(self):
        cam_idx = self._get_selected_cam_index()
        cap = self._open_camera(cam_idx)
        if not cap:
            self.root.after(0, lambda: [
                messagebox.showerror("Error", f"No se pudo abrir la cámara {cam_idx}\n\nVerifica que no esté en uso."),
                self.start_btn.config(state="normal"),
                self.cam_label.configure(image="", text="Sin señal de cámara"),
            ])
            return
        self.cap = cap
        self.root.after(0, self._start_capture)

    def _start_capture(self):
        self.detector = GestureDetector()
        self.running  = True
        # Vaciar cola de frames anteriores
        while not self._frame_queue.empty():
            try: self._frame_queue.get_nowait()
            except queue.Empty: break
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_dot.config(text="⬤  Activo", fg=GREEN)
        self.cam_thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.cam_thread.start()
        self.root.after(30, self._poll_frame)

    def _capture_worker(self):
        """Hilo dedicado: lee frames y los procesa, sin tocar Tkinter."""
        from config_manager import get_gesture_action
        prev_time = time.time()
        fail_count = 0

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                fail_count += 1
                try: self._frame_queue.put_nowait((None, fail_count, None))
                except queue.Full: pass
                if fail_count >= 10:
                    fail_count = 0
                    cam_idx = self._get_selected_cam_index()
                    if self.cap:
                        self.cap.release()
                    # Esperar 2s para que la cámara se estabilice antes de reconectar
                    time.sleep(2.0)
                    self.cap = self._open_camera(cam_idx)
                    if not self.cap:
                        try: self._frame_queue.put_nowait((None, None, None))
                        except queue.Full: pass
                        self.running = False
                        break
                time.sleep(0.05)
                continue

            fail_count = 0
            frame = cv2.flip(frame, 1)
            settings = get_settings()
            frame, gesture = self.detector.process_frame(frame, settings["show_landmarks"])

            if gesture:
                action = get_gesture_action(gesture)
                if action and self.detector.should_trigger(gesture):
                    threading.Thread(target=execute_action, args=(action,), daemon=True).start()

            now = time.time()
            fps = max(1, int(1 / (now - prev_time + 1e-9)))
            prev_time = now

            try: self._frame_queue.put_nowait((frame, gesture, fps))
            except queue.Full: pass

    def _poll_frame(self):
        """Corre en el hilo de Tkinter: consume la cola y actualiza la UI."""
        try:
            frame, gesture, fps = self._frame_queue.get_nowait()
        except queue.Empty:
            if self.running:
                self.root.after(30, self._poll_frame)
            return

        if frame is None:
            if fps is None:  # error fatal — no se pudo reconectar
                self.stop_camera()
                self.cam_label.configure(image="", text="❌ No se pudo reconectar")
                return
            self.cam_label.configure(image="", text=f"⚡ Sin señal ({gesture})")
            self.root.after(30, self._poll_frame)
            return

        # Actualizar acción en UI
        if gesture:
            from config_manager import get_gesture_action
            new_action = get_gesture_action(gesture)
            if new_action and new_action != self.action_val.cget("text"):
                self.action_val.configure(text=new_action)
                self._pulse_action()

        w = self.cam_label.winfo_width()
        h = self.cam_label.winfo_height()
        if w < 50 or h < 50:
            w, h = 640, 420
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        img = img.resize((w, h), Image.LANCZOS)
        imgtk = ImageTk.PhotoImage(image=img)
        self.cam_label.imgtk = imgtk
        self.cam_label.configure(image=imgtk, text="")
        self.gesture_val.configure(text=gesture or "---")
        self.fps_val.configure(text=str(fps))

        if self.overlay and self.overlay.winfo_exists():
            ow = self.ov_label.winfo_width()
            oh = self.ov_label.winfo_height()
            if ow < 50 or oh < 50:
                ow, oh = 300, 200
            ov_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            ov_img = ov_img.resize((ow, oh), Image.LANCZOS)
            # Dibujar indicadores sobre el frame del overlay
            ov_arr = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            ov_arr = cv2.resize(ov_arr, (ow, oh))
            g_text = gesture or "---"
            a_text = self.action_val.cget("text")
            f_text = f"FPS:{fps}"
            # Sombra + texto para legibilidad
            for text, x, y, color in [
                (g_text,  8,  oh-36, (80, 220, 100)),
                (a_text,  8,  oh-14, (100, 180, 255)),
                (f_text,  ow-60, oh-14, (220, 180, 60)),
            ]:
                cv2.putText(ov_arr, text, (x+1, y+1), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 2)
                cv2.putText(ov_arr, text, (x,   y),   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color,   1)
            ov_imgtk = ImageTk.PhotoImage(image=Image.fromarray(ov_arr))
            self.ov_label.ov_imgtk = ov_imgtk
            self.ov_label.configure(image=ov_imgtk, text="")

        self.root.after(30, self._poll_frame)

    def _pulse_action(self):
        if self.pulse_after:
            self.root.after_cancel(self.pulse_after)
        self.action_card.config(bg=GREEN)
        self.action_val.config(bg=GREEN, fg=BG)
        def reset():
            self.action_card.config(bg=CARD)
            self.action_val.config(bg=CARD, fg=GREEN)
        self.pulse_after = self.root.after(600, reset)

    def stop_camera(self):
        self.running = False
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        self.cam_label.configure(image="", text="Sin señal de cámara")
        self.gesture_val.configure(text="---")
        self.action_val.configure(text="---")
        self.fps_val.configure(text="0")
        self.status_dot.config(text="⬤  Inactivo", fg=FG_DIM)
        def _cleanup():
            if self.cam_thread and self.cam_thread.is_alive():
                self.cam_thread.join(timeout=3.0)
            if self.cap:
                self.cap.release()
                self.cap = None
            if self.detector:
                self.detector.release()
                self.detector = None
            self.root.after(0, lambda: self.start_btn.config(state="normal"))
        threading.Thread(target=_cleanup, daemon=True).start()

    # ── Mini Overlay flotante ─────────────────────────────────────────────────
    def _toggle_overlay(self):
        if self.overlay and self.overlay.winfo_exists():
            self.overlay.destroy()
            self.overlay = None
        else:
            self._open_overlay()

    def _open_overlay(self):
        ov = tk.Toplevel(self.root)
        ov.title("")
        ov.geometry("320x240+20+20")
        ov.overrideredirect(True)       # sin bordes del SO
        ov.attributes("-topmost", True) # siempre encima
        ov.attributes("-alpha", 0.92)
        ov.configure(bg="#0a0a14")
        self.overlay = ov

        # Barra de título personalizada
        bar = tk.Frame(ov, bg=PANEL, height=28)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        try:
            logo_small = Image.open(_res("logo_sidebar.png"))
            logo_small = logo_small.resize((22, 22), Image.LANCZOS)
            self._ov_logo = ImageTk.PhotoImage(logo_small)
            tk.Label(bar, image=self._ov_logo, bg=PANEL).pack(side="left", padx=4)
        except Exception:
            pass

        tk.Label(bar, text="Gesture Control", bg=PANEL, fg=FG,
                 font=(FONT, 9, "bold")).pack(side="left", padx=4)

        # Controles de la barra
        tk.Button(bar, text="✕", bg=PANEL, fg=RED, font=(FONT, 10, "bold"),
                  relief="flat", cursor="hand2", padx=6,
                  command=lambda: [ov.destroy(), setattr(self, "overlay", None)]
                  ).pack(side="right")

        # Slider de opacidad
        self._ov_alpha = tk.DoubleVar(value=0.92)
        def _set_alpha(v):
            ov.attributes("-alpha", float(v))
        tk.Scale(bar, from_=0.3, to=1.0, resolution=0.05, orient="horizontal",
                 variable=self._ov_alpha, command=_set_alpha,
                 bg=PANEL, fg=FG_DIM, troughcolor=ACCENT,
                 highlightthickness=0, length=80, showvalue=False
                 ).pack(side="right", padx=4)
        tk.Label(bar, text="👁", bg=PANEL, fg=FG_DIM,
                 font=(FONT, 9)).pack(side="right")

        # Area de video
        self.ov_label = tk.Label(ov, bg="#0a0a14", text="Sin senal",
                                  fg=FG_DIM, font=(FONT, 10))
        self.ov_label.pack(fill="both", expand=True)

        # Indicadores van dibujados sobre el frame con OpenCV
        self.ov_gesture = None
        self.ov_action  = None
        self.ov_fps     = None

        # Arrastre con el mouse
        bar.bind("<ButtonPress-1>",   self._ov_drag_start)
        bar.bind("<B1-Motion>",       self._ov_drag_move)
        for child in bar.winfo_children():
            child.bind("<ButtonPress-1>", self._ov_drag_start)
            child.bind("<B1-Motion>",     self._ov_drag_move)

        # Resize con esquina
        grip = tk.Label(ov, text="◢", bg="#0a0a14", fg=FG_DIM,
                        cursor="size_nw_se", font=(FONT, 10))
        grip.place(relx=1.0, rely=1.0, anchor="se")
        grip.bind("<ButtonPress-1>",  self._ov_resize_start)
        grip.bind("<B1-Motion>",      self._ov_resize_move)

    def _ov_drag_start(self, e):
        self._overlay_drag = {"x": e.x_root - self.overlay.winfo_x(),
                               "y": e.y_root - self.overlay.winfo_y()}

    def _ov_drag_move(self, e):
        if self.overlay and self._overlay_drag:
            x = e.x_root - self._overlay_drag["x"]
            y = e.y_root - self._overlay_drag["y"]
            self.overlay.geometry(f"+{x}+{y}")

    def _ov_resize_start(self, e):
        self._overlay_drag = {"x": e.x_root, "y": e.y_root,
                               "w": self.overlay.winfo_width(),
                               "h": self.overlay.winfo_height()}

    def _ov_resize_move(self, e):
        if self.overlay and self._overlay_drag:
            dw = e.x_root - self._overlay_drag["x"]
            dh = e.y_root - self._overlay_drag["y"]
            nw = max(200, self._overlay_drag["w"] + dw)
            nh = max(160, self._overlay_drag["h"] + dh)
            self.overlay.geometry(f"{nw}x{nh}")

    def on_close(self):
        self.running = False
        def _cleanup():
            if self.cam_thread and self.cam_thread.is_alive():
                self.cam_thread.join(timeout=3.0)
            if self.cap:
                self.cap.release()
            if self.detector:
                self.detector.release()
            self.root.after(0, self.root.destroy)
        threading.Thread(target=_cleanup, daemon=True).start()
