"""PWA：manifest.json 與 service worker，沿用 Daykeep / Dayshop 規格。"""
import os
from flask import Blueprint, jsonify, current_app, Response, url_for
from app.models import SiteSetting

pwa_bp = Blueprint('pwa', __name__)


def _icon_url(name, version):
    return url_for('static', filename=f'uploads/pwa/{name}') + f'?v={version}'


@pwa_bp.route('/manifest.json')
def manifest():
    version = SiteSetting.get('pwa_icon_version', '1')
    theme = SiteSetting.get('theme_color', '#1f6f8b')
    bg = SiteSetting.get('background_color', '#eef6f8')
    name = SiteSetting.get('site_name', 'Smart Island Hub｜智慧島嶼中心')
    short = SiteSetting.get('site_short', 'Smart Island')

    pwa_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'pwa')
    has_custom = os.path.exists(os.path.join(pwa_dir, 'icon-source.png'))

    if has_custom:
        icons = [
            {'src': _icon_url('icon-192.png', version), 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any maskable'},
            {'src': _icon_url('icon-512.png', version), 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'},
        ]
    else:
        icons = [
            {'src': url_for('pwa.placeholder_icon', size=192), 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any maskable'},
            {'src': url_for('pwa.placeholder_icon', size=512), 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'},
        ]

    return jsonify({
        'name': name,
        'short_name': short,
        'description': SiteSetting.get('site_tagline', ''),
        'start_url': '/',
        'scope': '/',
        'display': 'standalone',
        'orientation': 'any',
        'background_color': bg,
        'theme_color': theme,
        'icons': icons,
    })


@pwa_bp.route('/sw.js')
def service_worker():
    version = SiteSetting.get('pwa_icon_version', '1')
    sw = f"""
const CACHE = 'smartisland-v{version}';
const PRECACHE = ['/', '/manifest.json'];

self.addEventListener('install', (e) => {{
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(PRECACHE)).catch(()=>{{}}));
  self.skipWaiting();
}});

self.addEventListener('activate', (e) => {{
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
}});

self.addEventListener('fetch', (e) => {{
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  if (url.pathname.startsWith('/admin') ||
      url.pathname.startsWith('/api') ||
      url.pathname.startsWith('/orders') ||
      url.pathname.startsWith('/auth')) return;
  e.respondWith(
    fetch(e.request).then((resp) => {{
      const copy = resp.clone();
      if (resp.ok) caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(()=>{{}});
      return resp;
    }}).catch(() => caches.match(e.request))
  );
}});
""".strip()
    return Response(sw, mimetype='application/javascript')


@pwa_bp.route('/_placeholder_icon/<int:size>.png')
def placeholder_icon(size):
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFont
    size = max(32, min(1024, size))
    img = Image.new('RGB', (size, size), '#1f6f8b')
    draw = ImageDraw.Draw(img)
    text = 'S'
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2, (size - th) / 2 - size * 0.05), text, fill='#eef6f8', font=font)
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return Response(buf.getvalue(), mimetype='image/png')
