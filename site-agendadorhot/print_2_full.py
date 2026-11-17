from PIL import Image

im = Image.open(r"C:\Users\Administrator\.gemini\antigravity\scratch\telegram-story-scheduler\app\static\img\fonts\pinkcandyy\2.png")
print("Size:", im.size)
# Print full 50x50 resolution grid
im_res = im.resize((50, 50))
for y in range(0, 50, 2):
    row = ""
    for x in range(0, 50):
        r, g, b, a = im_res.getpixel((x, y))
        row += "#" if a > 100 else " "
    print(row)
