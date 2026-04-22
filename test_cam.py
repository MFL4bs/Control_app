import sys
sys.stdout.reconfigure(line_buffering=True)
import cv2

cameras = [2, 4]
backends = [("DSHOW", cv2.CAP_DSHOW), ("MSMF", cv2.CAP_MSMF), ("AUTO", 0)]

for cam_idx in cameras:
    print(f"\n=== Camara {cam_idx} ===", flush=True)
    for name, backend in backends:
        try:
            if backend == 0:
                cap = cv2.VideoCapture(cam_idx)
            else:
                cap = cv2.VideoCapture(cam_idx, backend)
            opened = cap.isOpened()
            print(f"  {name}: opened={opened}", flush=True)
            if opened:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                ret, frame = cap.read()
                print(f"  {name}: ret={ret}, frame={'OK '+str(frame.shape) if frame is not None else 'None'}", flush=True)
                cap.release()
                if ret:
                    print(f"  {name}: >>> FUNCIONA <<<", flush=True)
                    break
            else:
                cap.release()
        except Exception as e:
            print(f"  {name}: ERROR {e}", flush=True)

print("\nDone", flush=True)
