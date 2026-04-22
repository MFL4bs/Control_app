# ══════════════════════════════════════════════════════════════════════════════
# config_manager.py — Gestión de configuración
# Todas las funciones que leen y escriben en config.json.
# Es el único módulo que toca el archivo de configuración directamente,
# el resto de módulos lo usan a través de estas funciones.
# ══════════════════════════════════════════════════════════════════════════════

import json
import os
import sys

def _get_config_path():
    """
    Resuelve la ruta de config.json de forma correcta tanto en desarrollo como en .exe.
    - En desarrollo: usa la carpeta del script.
    - En .exe: usa la carpeta donde está el .exe (no _MEIPASS que es temporal y de solo lectura).
    Si el config.json no existe junto al .exe, lo copia desde _MEIPASS como plantilla inicial.
    """
    if getattr(sys, 'frozen', False):
        # Corriendo como .exe — guardar junto al ejecutable
        exe_dir = os.path.dirname(sys.executable)
    else:
        # Corriendo como script Python normal
        exe_dir = os.path.dirname(os.path.abspath(__file__))

    config_path = os.path.join(exe_dir, "config.json")

    # Si no existe junto al exe, copiar la plantilla desde _MEIPASS
    if not os.path.exists(config_path) and getattr(sys, '_MEIPASS', None):
        import shutil
        template = os.path.join(sys._MEIPASS, "config.json")
        if os.path.exists(template):
            shutil.copy(template, config_path)

    return config_path

CONFIG_PATH = _get_config_path()

def load_config():
    """Lee y retorna todo el contenido de config.json como diccionario."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    """Guarda el diccionario completo en config.json con formato legible."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def get_gesture_action(gesture_name):
    """
    Retorna la acción asignada a un gesto específico.
    Ejemplo: get_gesture_action("fist") → "media_play_pause"
    Retorna None si el gesto no existe.
    """
    config = load_config()
    gesture = config["gestures"].get(gesture_name)
    return gesture["action"] if gesture else None

def get_settings():
    """Retorna solo la sección 'settings' del config (sensibilidad, cooldown, etc.)."""
    return load_config()["settings"]

def update_gesture(gesture_name, action):
    """
    Cambia la acción asignada a un gesto existente y guarda.
    Retorna True si el gesto existía, False si no.
    """
    config = load_config()
    if gesture_name in config["gestures"]:
        config["gestures"][gesture_name]["action"] = action
        save_config(config)
        return True
    return False

def add_gesture(key, name, description, action):
    """
    Agrega un nuevo gesto personalizado al config.
    - key: identificador único sin espacios (ej: "my_gesture")
    - name: nombre legible (ej: "Mi Gesto")
    - description: descripción de cómo hacer el gesto
    - action: acción a ejecutar (ej: "volume_up")
    """
    config = load_config()
    config["gestures"][key] = {"name": name, "description": description, "action": action}
    save_config(config)

def delete_gesture(key):
    """
    Elimina un gesto del config por su clave.
    Retorna True si existía y fue eliminado, False si no existía.
    """
    config = load_config()
    if key in config["gestures"]:
        del config["gestures"][key]
        save_config(config)
        return True
    return False

def update_setting(key, value):
    """Actualiza un valor específico en la sección 'settings' y guarda."""
    config = load_config()
    config["settings"][key] = value
    save_config(config)

def get_all_gestures():
    """Retorna el diccionario completo de gestos configurados."""
    return load_config()["gestures"]

def get_available_actions():
    """
    Retorna la lista de todas las acciones disponibles para asignar a gestos.
    Esta lista se usa para poblar los dropdowns en la interfaz.
    """
    return [
        # Volumen
        "volume_up", "volume_down", "volume_mute",
        # Brillo
        "brightness_up", "brightness_down",
        # Scroll
        "scroll_up", "scroll_down",
        # Medios
        "media_play_pause", "media_next", "media_prev",
        # Ventanas
        "next_window", "prev_window", "close_active_window",
        "minimize_window", "maximize_window", "show_desktop",
        "virtual_desktop_next", "virtual_desktop_prev",
        # Sistema
        "screenshot", "task_manager", "lock_screen", "sleep_display",
        "open_explorer", "open_calculator", "open_notepad",
        # Zoom
        "zoom_in", "zoom_out", "zoom_reset",
        # Edicion
        "copy", "paste", "undo", "redo", "select_all", "find",
        # Navegador
        "new_tab", "close_tab", "reopen_tab", "refresh", "go_back", "go_forward",
        # Personalizados
        "open_browser", "custom_shortcut",
        *[f"open_link_{i}" for i in range(1, 11)],
        *[f"run_command_{i}" for i in range(1, 11)],
        "none"
    ]
