import sys
sys.stdout.reconfigure(line_buffering=True)
import tkinter as tk
import cv2
import time
from PIL import Image, ImageTk

root = tk.Tk()
root.geometry("800x600")
root.configure(bg="#0f0f1a")

label = tk.Label(root, bg="#0a0a14", text="Esperando...")
label.pack(fill="both", expand=True, padx=10, pady=10)

cap = cv2.VideoCapture(4, cv2.CAP_DSHOW)
print(f"Camara abierta: {cap.isOpened()}", flush=True)

# Calentar camara
for _ in range(5):
    cap.read()

frame_count = [0]

def loop():
    ret, frame = cap.read()
    frame_count[0] += 1

    if ret:
        frame = cv2.flip(frame, 1)
        w = label.winfo_width()
        h = label.winfo_height()
        print(f"Frame {frame_count[0]}: ret={ret} widget={w}x{h}", flush=True)

        if w < 50 or h < 50:
            w, h = 640, 420

        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        img = img.resize((w, h), Image.LANCZOS)
        imgtk = ImageTk.PhotoImage(image=img)
        label.imgtk = imgtk
        label.configure(image=imgtk, text="")
    else:
        print(f"Frame {frame_count[0]}: ret=False", flush=True)

    if frame_count[0] < 5:
        root.after(30, loop)
    else:
        print("Test completado - si ves imagen en la ventana funciona OK", flush=True)

root.update_idletasks()
root.after(150, loop)
root.mainloop()
cap.release()
