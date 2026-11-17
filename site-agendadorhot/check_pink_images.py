from PIL import Image
from pathlib import Path

dir_path = Path(r"C:\Users\Administrator\.gemini\antigravity\scratch\telegram-story-scheduler\app\static\img\fonts\pinkcandyy")
for p in dir_path.glob("*.png"):
    im = Image.open(p)
    print(p.name, im.size, im.mode)
