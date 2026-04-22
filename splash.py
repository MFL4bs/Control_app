# ══════════════════════════════════════════════════════════════════════════════
# splash.py — Pantalla de carga animada (Splash Screen)
# Muestra el banner de MF LABS con una barra de progreso animada mientras
# la aplicación carga sus módulos en segundo plano.
# ══════════════════════════════════════════════════════════════════════════════

import tkinter as tk
import os
import sys
from PIL import Image, ImageTk

def resource_path(filename):
    """Resuelve rutas tanto en desarrollo como dentro del .exe de PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, filename)

# ── Colores del tema oscuro ────────────────────────────────────────────────────
BG     = "#0f0f1a"   # Fondo principal negro azulado
BLUE   = "#4cc9f0"   # Azul claro para la barra de progreso
GREEN  = "#06d6a0"   # Verde para indicar que terminó la carga
FG_DIM = "#888899"   # Gris para textos secundarios
FONT   = "Segoe UI"

# Textos que se muestran en cada paso de la carga
STEPS = [
    "Iniciando módulos...",    # Paso 0: inicio
    "Cargando MediaPipe...",   # Paso 1: carga del motor de detección de manos
    "Detectando cámaras...",   # Paso 2: escaneo de cámaras del sistema
    "Preparando interfaz...",  # Paso 3: construcción de la GUI
    "Listo ✓",                 # Paso 4: todo listo
]

class SplashScreen:
    def __init__(self, root):
        self.root = root

        # Sin bordes del sistema operativo (ventana limpia)
        self.root.overrideredirect(True)
        self.root.configure(bg=BG)

        # Siempre encima de otras ventanas durante la carga
        self.root.attributes("-topmost", True)

        # Centrar la ventana en la pantalla
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = 700, 420
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        self._build()       # Construir los widgets visuales
        self._step = 0      # Paso actual de la carga
        self._progress = 0.0  # Progreso actual de la barra (0.0 a 1.0)

    def _build(self):
        """Construye todos los elementos visuales del splash."""

        # ── Banner principal ───────────────────────────────────────────────────
        # Intenta cargar el banner.png. Si falla, muestra texto como fallback.
        try:
            img = Image.open(resource_path("banner.png"))
            img = img.resize((700, 340), Image.LANCZOS)  # Ajustar al ancho del splash
            self._banner = ImageTk.PhotoImage(img)
            tk.Label(self.root, image=self._banner, bg=BG, borderwidth=0).pack()
        except Exception:
            # Fallback si no se encuentra el banner
            tk.Label(self.root, text="Gesture Control", bg=BG,
                     fg=BLUE, font=(FONT, 28, "bold")).pack(expand=True)

        # ── Área inferior con barra de progreso ───────────────────────────────
        bottom = tk.Frame(self.root, bg=BG, height=80)
        bottom.pack(fill="x")
        bottom.pack_propagate(False)  # Mantener altura fija de 80px

        # Texto de estado que cambia en cada paso
        self.status_lbl = tk.Label(bottom, text="Iniciando...", bg=BG,
                                    fg=FG_DIM, font=(FONT, 9))
        self.status_lbl.pack(pady=(8, 4))

        # Contenedor gris de la barra de progreso (fondo)
        bar_bg = tk.Frame(bottom, bg="#1a1a2e", height=6, width=500, relief="flat")
        bar_bg.pack()
        bar_bg.pack_propagate(False)

        # Relleno azul que crece de izquierda a derecha
        self.bar_fill = tk.Frame(bar_bg, bg=BLUE, height=6, width=0)
        self.bar_fill.place(x=0, y=0, height=6)  # Posición absoluta dentro del contenedor

        self._bar_width = 500  # Ancho total de la barra en píxeles

        # Versión y marca en la parte inferior
        tk.Label(bottom, text="v2.0  |  MF LABS", bg=BG,
                 fg=FG_DIM, font=(FONT, 8)).pack(pady=(6, 0))

    def advance(self, step_index):
        """
        Avanza la barra de progreso al paso indicado.
        step_index: 0 a 4 (corresponde a los STEPS definidos arriba)
        """
        total = len(STEPS) - 1
        target = step_index / total  # Convertir paso a porcentaje (0.0 a 1.0)
        self.status_lbl.configure(text=STEPS[step_index])  # Actualizar texto
        self._animate_to(target)  # Animar suavemente hasta el nuevo porcentaje

    def _animate_to(self, target):
        """
        Animación fluida de la barra: avanza 2% cada 16ms (~60fps).
        Cuando llega al 100% cambia de azul a verde.
        """
        if self._progress < target:
            # Incrementar progreso en pequeños pasos para suavidad
            self._progress = min(self._progress + 0.02, target)
            w = int(self._progress * self._bar_width)
            self.bar_fill.place(x=0, y=0, height=6, width=w)

            # Cambiar a verde cuando llega al final
            color = GREEN if self._progress >= 0.99 else BLUE
            self.bar_fill.configure(bg=color)

            # Programar el siguiente frame de animación (16ms = ~60fps)
            self.root.after(16, lambda: self._animate_to(target))
        else:
            # Asegurar que llegue exactamente al target
            w = int(target * self._bar_width)
            self.bar_fill.place(x=0, y=0, height=6, width=w)

    def close(self):
        """Completa la barra al 100% y programa el cierre del splash."""
        self.advance(len(STEPS) - 1)  # Ir al último paso (Listo ✓)
        self.root.after(600, self.root.quit)  # Salir del mainloop después de 600ms
