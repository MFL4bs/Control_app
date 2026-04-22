# ══════════════════════════════════════════════════════════════════════════════
# main.py — Punto de entrada de la aplicación
# Se encarga de mostrar el splash screen mientras carga los módulos pesados,
# y luego lanza la ventana principal con las cámaras ya detectadas.
# ══════════════════════════════════════════════════════════════════════════════

import sys
import os

# Cuando la app corre como .exe (PyInstaller), stdout puede ser None.
# Esto evita que crashee al intentar imprimir en consola.
if sys.stdout is not None:
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

def resource_path(filename):
    """
    Resuelve la ruta de un archivo tanto en desarrollo como dentro del .exe.
    - En desarrollo: usa la carpeta del script.
    - En .exe (PyInstaller): usa la carpeta temporal _MEIPASS donde se extraen los archivos.
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, filename)

import tkinter as tk
from splash import SplashScreen  # Pantalla de carga animada

def launch():
    # ── 1. Mostrar splash screen ───────────────────────────────────────────────
    # Se crea una ventana Tkinter temporal solo para el splash.
    # El splash se muestra ANTES de importar los módulos pesados (mediapipe, cv2)
    # para que el usuario vea algo mientras la app carga.
    splash_root = tk.Tk()
    splash = SplashScreen(splash_root)
    splash_root.update()  # Forzar que se dibuje la ventana inmediatamente

    # ── 2. Paso 1: módulos base listos ────────────────────────────────────────
    splash.advance(0)
    splash_root.update()

    # ── 3. Paso 2: importar gesture_detector (carga mediapipe, el más lento) ──
    # Se importa aquí (no al inicio del archivo) para que el splash ya esté
    # visible cuando mediapipe tarda en inicializarse.
    from gesture_detector import scan_cameras, GestureDetector
    splash.advance(1)
    splash_root.update()

    # ── 4. Paso 3: escanear cámaras disponibles en el sistema ─────────────────
    # Se hace aquí para pasar la lista ya lista a la GUI sin re-escanear.
    cameras = scan_cameras()
    splash.advance(2)
    splash_root.update()

    # ── 5. Paso 4: importar la GUI principal ──────────────────────────────────
    from gui import GestureControlApp
    splash.advance(3)
    splash_root.update()

    # ── 6. Paso 5: cerrar splash y arrancar la app ────────────────────────────
    splash_root.update()
    splash_root.after(700, splash_root.quit)  # Salir del mainloop sin destruir aún
    splash_root.mainloop()   # Mantiene el splash vivo hasta quit()
    splash_root.destroy()    # Destruir después de que mainloop retorne

    # ── 7. Ventana principal ──────────────────────────────────────────────────
    root = tk.Tk()
    app = GestureControlApp(root, preloaded_cameras=cameras)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()

if __name__ == "__main__":
    launch()
