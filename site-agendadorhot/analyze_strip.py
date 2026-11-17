from PIL import Image

# strip.png has width 279, height 45
strip = Image.open(r"C:\Users\Administrator\AppData\Local\Programs\antigravity\strip.png")

# Let's inspect the bounding boxes of pink pixels in strip.png
# to identify the exact coordinates of each letter!
w, h = strip.size
column_has_pink = []
for x in range(w):
    has_pink = False
    for y in range(h):
        r, g, b, a = strip.getpixel((x, y))
        # pink has high r and b, lower g
        if r > 180 and b > 100 and g < 150:
            has_pink = True
            break
    column_has_pink.append(has_pink)

# Group contiguous pink columns into letter bounding boxes
letters = []
in_letter = False
start_x = 0
for x, hp in enumerate(column_has_pink):
    if hp and not in_letter:
        in_letter = True
        start_x = x
    elif not hp and in_letter:
        in_letter = False
        letters.append((start_x, x))
if in_letter:
    letters.append((start_x, w))

print("Detected letters count:", len(letters))
for idx, (sx, ex) in enumerate(letters):
    print(f"Letter {idx}: x from {sx} to {ex} (width {ex - sx})")
    im = strip.crop((sx - 2, 0, ex + 2, h))
    im.resize((30, 30)).save(f"letter_{idx}.png")
    
    # Print ASCII
    print(f"--- Letter {idx} ASCII ---")
    im_small = im.resize((20, 20))
    for y in range(20):
        line = ""
        for x in range(20):
            r, g, b, a = im_small.getpixel((x, y))
            line += "#" if (r > 180 and b > 100 and g < 150) else " "
        print(line)
