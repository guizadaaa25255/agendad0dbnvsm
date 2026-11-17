from PIL import Image
from pathlib import Path

p = Path(r"C:\Users\Administrator\.gemini\antigravity\scratch\telegram-story-scheduler\app\static\img\fonts\pinkcandyy_sample.png")
im = Image.open(p).convert("RGBA").resize((68, 20))
for y in range(20):
    line = ""
    for x in range(68):
        r, g, b, a = im.getpixel((x, y))
        line += "#" if a > 128 else " "
    print(line)
