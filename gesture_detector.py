import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision import HandLandmarkerOptions, HandLandmarker
import time
import subprocess
import json
import os
import sys
from config_manager import get_settings

def _model_path():
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, 'hand_landmarker.task')

_VIDEO_KEYWORDS = ["cam", "video", "droid", "webcam", "capture", "usb", "virtual"]

def _get_camera_names_from_system():
    names = []
    try:
        cmd = [
            "powershell", "-Command",
            "Get-PnpDevice | Where-Object {$_.Status -eq 'OK' -and "
            "($_.Class -eq 'Camera' -or ($_.Class -eq 'MEDIA' -and "
            "($_.FriendlyName -like '*cam*' -or $_.FriendlyName -like '*video*' -or "
            "$_.FriendlyName -like '*droid*' -or $_.FriendlyName -like '*capture*')))} "
            "| Select-Object FriendlyName | ConvertTo-Json"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        if result.stdout.strip():
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                data = [data]
            seen = set()
            for d in data:
                name = d.get("FriendlyName", "")
                if name and "audio" not in name.lower() and name not in seen:
                    seen.add(name)
                    names.append(name)
    except Exception:
        pass
    return names

def scan_cameras(max_test=6):
    system_names = _get_camera_names_from_system()
    available = []
    name_idx = 0
    for i in range(max_test):
        cap = None
        for backend in [cv2.CAP_DSHOW, cv2.CAP_MSMF]:
            try:
                c = cv2.VideoCapture(i, backend)
                if c.isOpened():
                    ret, _ = c.read()
                    c.release()
                    if ret:
                        cap = backend
                        break
                else:
                    c.release()
            except Exception:
                pass
        if cap is not None:
            name = system_names[name_idx] if name_idx < len(system_names) else f"Camara {i}"
            name_idx += 1
            available.append({"index": i, "name": name})
    return available


class GestureDetector:
    def __init__(self):
        settings = get_settings()
        options = HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=_model_path()),
            running_mode=mp_vision.RunningMode.IMAGE,
            num_hands=1,
            min_hand_detection_confidence=settings["detection_confidence"],
            min_tracking_confidence=0.5,
        )
        self.detector = HandLandmarker.create_from_options(options)
        self.last_gesture_time = 0
        self.last_gesture = None

    def _finger_states(self, lm, handedness="Right"):
        thumb = lm[4].x < lm[3].x if handedness == "Right" else lm[4].x > lm[3].x
        fingers = [lm[tip].y < lm[tip - 2].y for tip in [8, 12, 16, 20]]
        return [thumb] + fingers

    def _classify(self, lm, handedness="Right"):
        f = self._finger_states(lm, handedness)
        thumb, index, middle, ring, pinky = f

        # Pellizco: pulgar e indice muy cerca
        pinch = abs(lm[4].x - lm[8].x) + abs(lm[4].y - lm[8].y)
        if pinch < 0.06:
            return "pinch"

        # Puno: ningun dedo extendido
        if not any(f):
            return "fist"

        # Mano abierta: los 4 dedos extendidos (pulgar opcional)
        if index and middle and ring and pinky:
            return "open_hand"

        # Solo indice
        if index and not middle and not ring and not pinky and not thumb:
            return "pointing_up" if lm[8].y < lm[5].y - 0.05 else "pointing_down"

        # Solo pulgar
        if thumb and not index and not middle and not ring and not pinky:
            return "thumbs_up" if lm[4].y < lm[0].y else "thumbs_down"

        # Indice + medio (V/paz)
        if index and middle and not ring and not pinky and not thumb:
            return "peace"

        # Indice + medio + anular (3 dedos) o Spock si separados
        if index and middle and ring and not pinky and not thumb:
            if abs(lm[12].x - lm[16].x) > 0.06:
                return "spock"
            return "three_fingers"

        # 4 dedos sin pulgar — solo si la mano esta claramente cerrada en pulgar
        # (se elimina para evitar conflicto con open_hand)
        # four_fingers queda reservado para asignacion manual

        # Llamame: pulgar + menique
        if thumb and not index and not middle and not ring and pinky:
            return "call_me"

        # Rock: indice + menique sin pulgar
        if index and not middle and not ring and pinky and not thumb:
            return "rock"

        # Gun: pulgar + indice
        if thumb and index and not middle and not ring and not pinky:
            return "gun"

        # OK: pulgar + medio
        if thumb and not index and middle and not ring and not pinky:
            return "ok"

        # Indice + anular (saltar dedo medio)
        if index and not middle and ring and not pinky and not thumb:
            return "crossed"

        # Menique solo
        if not thumb and not index and not middle and not ring and pinky:
            return "pinky_up"

        return None

    _HAND_CONNECTIONS = [
        (0,1),(1,2),(2,3),(3,4),
        (0,5),(5,6),(6,7),(7,8),
        (5,9),(9,10),(10,11),(11,12),
        (9,13),(13,14),(14,15),(15,16),
        (13,17),(17,18),(18,19),(19,20),(0,17)
    ]

    # Color por dedo: pulgar, indice, medio, anular, menique, palma
    _FINGER_COLORS = [
        (0,  180, 255),  # pulgar    - naranja
        (0,  255, 120),  # indice    - verde lima
        (255, 200,  0),  # medio     - amarillo
        (255,  80,180),  # anular    - rosa
        (180,  80,255),  # menique   - violeta
    ]
    _PALM_COLOR   = (200, 200, 200)  # palma - gris claro
    _JOINT_COLOR  = (255, 255, 255)  # articulaciones - blanco

    # Segmentos por dedo (indices en _HAND_CONNECTIONS)
    _FINGER_SEGMENTS = [
        [(0,1),(1,2),(2,3),(3,4)],           # pulgar
        [(0,5),(5,6),(6,7),(7,8)],           # indice
        [(5,9),(9,10),(10,11),(11,12)],      # medio
        [(9,13),(13,14),(14,15),(15,16)],    # anular
        [(13,17),(17,18),(18,19),(19,20)],   # menique
    ]
    _PALM_SEGMENTS = [(0,17),(0,5),(5,9),(9,13),(13,17)]

    def process_frame(self, frame, show_landmarks=True):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self.detector.detect(mp_image)
        gesture = None

        if result.hand_landmarks:
            lm = result.hand_landmarks[0]
            handedness = "Right"
            if result.handedness:
                handedness = result.handedness[0][0].category_name

            if show_landmarks:
                h, w = frame.shape[:2]
                pts = [(int(p.x * w), int(p.y * h)) for p in lm]

                # Dibujar palma
                for a, b in self._PALM_SEGMENTS:
                    cv2.line(frame, pts[a], pts[b], self._PALM_COLOR, 2)

                # Dibujar cada dedo con su color
                for segs, color in zip(self._FINGER_SEGMENTS, self._FINGER_COLORS):
                    for a, b in segs:
                        cv2.line(frame, pts[a], pts[b], color, 3)

                # Dibujar articulaciones
                for i, (x, y) in enumerate(pts):
                    # Punta de cada dedo mas grande
                    r = 6 if i in (4, 8, 12, 16, 20) else 4
                    # Color segun dedo
                    if   i in (1,2,3,4):   c = self._FINGER_COLORS[0]
                    elif i in (5,6,7,8):   c = self._FINGER_COLORS[1]
                    elif i in (9,10,11,12):c = self._FINGER_COLORS[2]
                    elif i in (13,14,15,16):c= self._FINGER_COLORS[3]
                    elif i in (17,18,19,20):c= self._FINGER_COLORS[4]
                    else:                  c = self._PALM_COLOR
                    cv2.circle(frame, (x, y), r, c, -1)
                    cv2.circle(frame, (x, y), r, self._JOINT_COLOR, 1)

            gesture = self._classify(lm, handedness)

        return frame, gesture

    def should_trigger(self, gesture):
        settings = get_settings()
        cooldown = settings["gesture_cooldown"]
        now = time.time()
        if gesture and gesture != self.last_gesture:
            if now - self.last_gesture_time >= cooldown:
                self.last_gesture = gesture
                self.last_gesture_time = now
                return True
        if now - self.last_gesture_time >= cooldown:
            self.last_gesture = None
        return False

    def release(self):
        self.detector.close()
