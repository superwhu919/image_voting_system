import os
from PIL import Image

INPUT_DIR = "all_images"
OUTPUT_DIR = "all_images_small"
TARGET_SIZE = 100 * 1024  # 100KB

os.makedirs(OUTPUT_DIR, exist_ok=True)


def compress_image(input_path, output_path):
    img = Image.open(input_path).convert("RGB")

    # 初始参数
    quality = 85
    scale = 1.0

    while True:
        # 缩放
        if scale < 1.0:
            w, h = img.size
            img_resized = img.resize(
                (int(w * scale), int(h * scale)),
                Image.LANCZOS
            )
        else:
            img_resized = img

        # 保存为 JPEG（体积最可控）
        img_resized.save(
            output_path,
            format="JPEG",
            quality=quality,
            optimize=True
        )

        size = os.path.getsize(output_path)

        if size <= TARGET_SIZE:
            break

        # 先降质量，再缩尺寸
        if quality > 30:
            quality -= 10
        else:
            scale *= 0.9

        # 防止无限循环
        if scale < 0.3:
            break


for filename in os.listdir(INPUT_DIR):
    if not filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        continue

    input_path = os.path.join(INPUT_DIR, filename)
    output_filename = os.path.splitext(filename)[0] + ".jpg"
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    compress_image(input_path, output_path)
    final_size = os.path.getsize(output_path)

    print(f"{filename} -> {output_filename}, {final_size / 1024:.1f} KB")

