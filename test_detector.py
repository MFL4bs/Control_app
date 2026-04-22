import sys
sys.stdout.reconfigure(line_buffering=True)

print("paso 1", flush=True)

from gesture_detector import scan_cameras, GestureDetector
print("paso 2 - import OK", flush=True)

cams = scan_cameras()
print("paso 3 - camaras:", cams, flush=True)

det = GestureDetector()
print("paso 4 - detector OK", flush=True)

det.release()
print("paso 5 - TODO OK", flush=True)
