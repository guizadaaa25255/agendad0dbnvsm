from PIL import Image
from pathlib import Path

dir_path = Path(r"C:\Users\Administrator\.gemini\antigravity\scratch\telegram-story-scheduler\app\static\img\fonts\pinkcandyy")
for p in sorted(dir_path.glob("*.png")):
    im = Image.open(p).convert("RGBA").resize((30, 30))
    print(f"=== {p.name} ===")
    for y in range(30):
        line = ""
        for x in range(30):
            r, g, b, a = im.getpixel((x, y))
            line += "#" if a > 128 else " "
        print(line)
