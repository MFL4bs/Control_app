import sys
sys.stdout.reconfigure(line_buffering=True)
from PIL import Image

img = Image.open("MF LABS logo.png").convert("RGBA")
img.resize((180, 180), Image.LANCZOS).save("logo_sidebar.png")

sizes = [(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
icons = [img.resize(s, Image.LANCZOS) for s in sizes]
icons[0].save("logo.ico", format="ICO", sizes=sizes, append_images=icons[1:])

print("logo_sidebar.png OK", flush=True)
print("logo.ico OK", flush=True)
