# ══════════════════════════════════════════════════════════════════════════════
# action_executor.py — Ejecutor de acciones del sistema
# Contiene todas las funciones que interactúan con el sistema operativo:
# volumen, brillo, scroll, medios, capturas, ventanas y atajos.
# Cada función corresponde a una acción que puede asignarse a un gesto.
# ══════════════════════════════════════════════════════════════════════════════

import pyautogui    # Control de teclado, ratón y capturas de pantalla
import webbrowser   # Abrir URLs en el navegador predeterminado
import subprocess   # Ejecutar comandos del sistema
import os
from config_manager import load_config

# ── Intentar importar pycaw (control de volumen de Windows) ──────────────────
# pycaw accede directamente a la API de audio de Windows para control preciso.
# Si no está disponible, se usa pyautogui como fallback (teclas de volumen).
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    import ctypes
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False

# ── Intentar importar screen_brightness_control (control de brillo) ──────────
# Controla el brillo de la pantalla via WMI en Windows.
# Si no está disponible, las funciones de brillo no hacen nada.
try:
    import screen_brightness_control as sbc
    SBC_AVAILABLE = True
except ImportError:
    SBC_AVAILABLE = False

# Desactivar el failsafe de pyautogui (mover el ratón a la esquina no detiene el programa)
pyautogui.FAILSAFE = False

def _get_volume_interface():
    """
    Obtiene la interfaz COM de Windows para controlar el volumen del sistema.
    Retorna None si pycaw no está disponible.
    """
    if not PYCAW_AVAILABLE:
        return None
    devices = AudioUtilities.GetSpeakers()  # Obtener dispositivo de audio activo
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))

def volume_up():
    """Sube el volumen del sistema según el paso configurado en settings."""
    config = load_config()
    step = config["settings"]["volume_step"] / 100.0  # Convertir % a escala 0-1
    try:
        vol = _get_volume_interface()
        if vol:
            current = vol.GetMasterVolumeLevelScalar()  # Volumen actual (0.0 a 1.0)
            vol.SetMasterVolumeLevelScalar(min(1.0, current + step), None)  # No pasar de 1.0
    except Exception:
        pyautogui.press("volumeup")  # Fallback: simular tecla de volumen

def volume_down():
    """Baja el volumen del sistema según el paso configurado en settings."""
    config = load_config()
    step = config["settings"]["volume_step"] / 100.0
    try:
        vol = _get_volume_interface()
        if vol:
            current = vol.GetMasterVolumeLevelScalar()
            vol.SetMasterVolumeLevelScalar(max(0.0, current - step), None)  # No bajar de 0.0
    except Exception:
        pyautogui.press("volumedown")

def volume_mute():
    """Alterna el silencio del sistema (mute/unmute)."""
    try:
        vol = _get_volume_interface()
        if vol:
            vol.SetMute(not vol.GetMute(None), None)  # Invertir estado actual
    except Exception:
        pyautogui.press("volumemute")

def brightness_up():
    """Sube el brillo de la pantalla según el paso configurado."""
    if not SBC_AVAILABLE:
        return
    config = load_config()
    step = config["settings"]["brightness_step"]
    try:
        current = sbc.get_brightness(display=0)[0]  # Brillo actual del monitor 0
        sbc.set_brightness(min(100, current + step), display=0)  # Máximo 100%
    except Exception:
        pass

def brightness_down():
    """Baja el brillo de la pantalla según el paso configurado."""
    if not SBC_AVAILABLE:
        return
    config = load_config()
    step = config["settings"]["brightness_step"]
    try:
        current = sbc.get_brightness(display=0)[0]
        sbc.set_brightness(max(0, current - step), display=0)  # Mínimo 0%
    except Exception:
        pass

def scroll_up():
    """Hace scroll hacia arriba en la ventana activa."""
    amount = load_config()["settings"]["scroll_amount"]
    pyautogui.scroll(amount)  # Positivo = arriba

def scroll_down():
    """Hace scroll hacia abajo en la ventana activa."""
    amount = load_config()["settings"]["scroll_amount"]
    pyautogui.scroll(-amount)  # Negativo = abajo

def media_play_pause():
    """Envía la tecla Play/Pausa al reproductor de medios activo."""
    pyautogui.press("playpause")

def media_next():
    """Salta a la siguiente pista en el reproductor de medios."""
    pyautogui.press("nexttrack")

def media_prev():
    """Vuelve a la pista anterior en el reproductor de medios."""
    pyautogui.press("prevtrack")

def screenshot():
    """
    Toma una captura de pantalla completa y la guarda en el Escritorio.
    Soporta escritorio en español (Escritorio) e inglés (Desktop).
    """
    img = pyautogui.screenshot()
    home = os.path.expanduser("~")
    desktop = next(
        (os.path.join(home, n) for n in ["Desktop", "Escritorio"]
         if os.path.exists(os.path.join(home, n))),
        home  # Fallback: carpeta del usuario
    )
    img.save(os.path.join(desktop, "gesture_screenshot.png"))

def next_window():
    """Cambia a la siguiente ventana abierta (Alt+Tab)."""
    pyautogui.hotkey("alt", "tab")

def prev_window():
    """Cambia a la ventana anterior (Alt+Shift+Tab)."""
    pyautogui.hotkey("alt", "shift", "tab")

def open_browser():
    url = load_config()["custom_actions"].get("open_browser", "https://www.google.com")
    webbrowser.open(url)

def custom_shortcut():
    shortcut = load_config()["custom_actions"].get("custom_shortcut", "")
    if shortcut:
        pyautogui.hotkey(*shortcut.split("+"))

# ── Acciones de sistema ────────────────────────────────────────────────────────
def close_active_window():
    pyautogui.hotkey("alt", "f4")

def minimize_window():
    pyautogui.hotkey("win", "down")

def maximize_window():
    pyautogui.hotkey("win", "up")

def show_desktop():
    pyautogui.hotkey("win", "d")

def task_manager():
    pyautogui.hotkey("ctrl", "shift", "esc")

def lock_screen():
    pyautogui.hotkey("win", "l")

def virtual_desktop_next():
    pyautogui.hotkey("ctrl", "win", "right")

def virtual_desktop_prev():
    pyautogui.hotkey("ctrl", "win", "left")

def zoom_in():
    pyautogui.hotkey("ctrl", "+")

def zoom_out():
    pyautogui.hotkey("ctrl", "-")

def zoom_reset():
    pyautogui.hotkey("ctrl", "0")

def copy():
    pyautogui.hotkey("ctrl", "c")

def paste():
    pyautogui.hotkey("ctrl", "v")

def undo():
    pyautogui.hotkey("ctrl", "z")

def redo():
    pyautogui.hotkey("ctrl", "y")

def select_all():
    pyautogui.hotkey("ctrl", "a")

def find():
    pyautogui.hotkey("ctrl", "f")

def new_tab():
    pyautogui.hotkey("ctrl", "t")

def close_tab():
    pyautogui.hotkey("ctrl", "w")

def reopen_tab():
    pyautogui.hotkey("ctrl", "shift", "t")

def refresh():
    pyautogui.press("f5")

def go_back():
    pyautogui.hotkey("alt", "left")

def go_forward():
    pyautogui.hotkey("alt", "right")

def open_explorer():
    subprocess.Popen("explorer.exe")

def open_calculator():
    subprocess.Popen("calc.exe")

def open_notepad():
    subprocess.Popen("notepad.exe")

def sleep_display():
    subprocess.Popen(["powershell", "-Command",
        "(Add-Type -MemberDefinition '[DllImport(\"user32.dll\")]public static extern int SendMessage(int hWnd,int hMsg,int wParam,int lParam);' "
        "-Name 'Win32SendMessage' -Namespace Win32Functions -PassThru)::SendMessage(-1,0x0112,0xF170,2)"])

# ── Links personalizados 1-10 ──────────────────────────────────────────────────
def _open_link(n):
    url = load_config().get("custom_links", {}).get(f"link_{n}", "")
    if url:
        webbrowser.open(url)

def open_link_1():  _open_link(1)
def open_link_2():  _open_link(2)
def open_link_3():  _open_link(3)
def open_link_4():  _open_link(4)
def open_link_5():  _open_link(5)
def open_link_6():  _open_link(6)
def open_link_7():  _open_link(7)
def open_link_8():  _open_link(8)
def open_link_9():  _open_link(9)
def open_link_10(): _open_link(10)

# ── Comandos personalizados 1-10 ───────────────────────────────────────────────
def _run_command(n):
    cmd = load_config().get("custom_commands", {}).get(f"cmd_{n}", "")
    if cmd:
        subprocess.Popen(cmd, shell=True)

def run_command_1():  _run_command(1)
def run_command_2():  _run_command(2)
def run_command_3():  _run_command(3)
def run_command_4():  _run_command(4)
def run_command_5():  _run_command(5)
def run_command_6():  _run_command(6)
def run_command_7():  _run_command(7)
def run_command_8():  _run_command(8)
def run_command_9():  _run_command(9)
def run_command_10(): _run_command(10)

# ── Mapa de nombre → función ──────────────────────────────────────────────────
# Permite ejecutar cualquier acción por su nombre en string.
# Se usa en execute_action() para despachar la función correcta.
ACTIONS = {
    "volume_up":             volume_up,
    "volume_down":           volume_down,
    "volume_mute":           volume_mute,
    "brightness_up":         brightness_up,
    "brightness_down":       brightness_down,
    "scroll_up":             scroll_up,
    "scroll_down":           scroll_down,
    "media_play_pause":      media_play_pause,
    "media_next":            media_next,
    "media_prev":            media_prev,
    "screenshot":            screenshot,
    "next_window":           next_window,
    "prev_window":           prev_window,
    "close_active_window":   close_active_window,
    "minimize_window":       minimize_window,
    "maximize_window":       maximize_window,
    "show_desktop":          show_desktop,
    "task_manager":          task_manager,
    "lock_screen":           lock_screen,
    "virtual_desktop_next":  virtual_desktop_next,
    "virtual_desktop_prev":  virtual_desktop_prev,
    "zoom_in":               zoom_in,
    "zoom_out":              zoom_out,
    "zoom_reset":            zoom_reset,
    "copy":                  copy,
    "paste":                 paste,
    "undo":                  undo,
    "redo":                  redo,
    "select_all":            select_all,
    "find":                  find,
    "new_tab":               new_tab,
    "close_tab":             close_tab,
    "reopen_tab":            reopen_tab,
    "refresh":               refresh,
    "go_back":               go_back,
    "go_forward":            go_forward,
    "open_explorer":         open_explorer,
    "open_calculator":       open_calculator,
    "open_notepad":          open_notepad,
    "sleep_display":         sleep_display,
    "open_browser":          open_browser,
    "custom_shortcut":       custom_shortcut,
    **{f"open_link_{i}": globals()[f"open_link_{i}"] for i in range(1, 11)},
    **{f"run_command_{i}": globals()[f"run_command_{i}"] for i in range(1, 11)},
    "none": lambda: None,
}

def execute_action(action_name):
    """
    Ejecuta la acción correspondiente al nombre dado.
    Si la acción no existe en el mapa, no hace nada.
    Los errores se capturan para no interrumpir el loop de la cámara.
    """
    action = ACTIONS.get(action_name)
    if action:
        try:
            action()
        except Exception as e:
            print(f"Error ejecutando acción '{action_name}': {e}")
