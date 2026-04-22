import sys
sys.stdout.reconfigure(line_buffering=True)
import cv2

print("Probando camara 4 (DroidCam)...", flush=True)
cap = cv2.VideoCapture(4, cv2.CAP_DSHOW)
print(f"Abierta: {cap.isOpened()}", flush=True)

# Leer 10 frames de calentamiento
for i in range(10):
    ret, frame = cap.read()
    print(f"Frame {i}: ret={ret}, shape={frame.shape if frame is not None else None}", flush=True)

print("Mostrando video en ventana OpenCV (presiona Q para salir)...", flush=True)
while True:
    ret, frame = cap.read()
    if ret:
        cv2.imshow("TEST CAMARA", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("Listo", flush=True)
