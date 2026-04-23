"""PWA icon 生成與驗證（沿用 Daykeep / Dayshop 規格）。

後台上傳一張至少 512x512 的正方形 PNG，本模組會：
  - 驗證格式 / 尺寸 / 長寬比
  - 儲存原圖為 icon-source.png
  - 產出 icon-192.png、icon-512.png、apple-touch-icon-180.png、favicon-32.png
  - 由路由 bump pwa_icon_version，前端透過 ?v= 破快取
"""
import os
from PIL import Image


PWA_DIR_NAME = 'pwa'
SOURCE_NAME = 'icon-source.png'
TARGETS = [
    ('icon-192.png', 192),
    ('icon-512.png', 512),
    ('apple-touch-icon-180.png', 180),
    ('favicon-32.png', 32),
]


class IconError(ValueError):
    pass


def validate_and_save(file_storage, upload_root):
    if not file_storage or not file_storage.filename:
        raise IconError('請選擇檔案')

    filename = file_storage.filename.lower()
    if not filename.endswith('.png'):
        raise IconError('圖示格式必須是 PNG')

    try:
        img = Image.open(file_storage.stream)
        img.load()
    except Exception:
        raise IconError('無法讀取圖片，請確認檔案未損毀')

    if img.format != 'PNG':
        raise IconError('圖示格式必須是 PNG')

    w, h = img.size
    if w != h:
        raise IconError(f'圖片必須是正方形，目前尺寸 {w}x{h}')
    if w < 512:
        raise IconError(f'圖片解析度至少 512x512，目前 {w}x{h}')

    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGBA')

    pwa_dir = os.path.join(upload_root, PWA_DIR_NAME)
    os.makedirs(pwa_dir, exist_ok=True)

    source_path = os.path.join(pwa_dir, SOURCE_NAME)
    img.save(source_path, format='PNG', optimize=True)

    generated = []
    for name, size in TARGETS:
        target_path = os.path.join(pwa_dir, name)
        resized = img.resize((size, size), Image.LANCZOS)
        resized.save(target_path, format='PNG', optimize=True)
        generated.append(name)

    return source_path, generated


def has_custom_icon(upload_root):
    return os.path.exists(os.path.join(upload_root, PWA_DIR_NAME, SOURCE_NAME))
