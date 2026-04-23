from flask_login import current_user
from app.models import SiteSetting, StoreInfo, Customer


def inject_globals():
    settings = {s.key: s.value for s in SiteSetting.query.all()}
    store = StoreInfo.current()
    return {
        'site_name': settings.get('site_name', 'Smart Island Hub｜智慧島嶼中心'),
        'site_short': settings.get('site_short', 'Smart Island'),
        'site_tagline': settings.get('site_tagline', ''),
        'theme_color': settings.get('theme_color', '#1f6f8b'),
        'background_color': settings.get('background_color', '#eef6f8'),
        'pwa_icon_version': settings.get('pwa_icon_version', '1'),
        'settings': settings,
        'store': store,
        'is_customer': isinstance(current_user._get_current_object() if hasattr(current_user, '_get_current_object') else current_user, Customer),
    }
