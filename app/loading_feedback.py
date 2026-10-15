"""Install shared loading UI on rendered pages, including standalone templates."""
import re

from flask import request, url_for


def install(app):
    @app.after_request
    def loading_assets(response):
        if (response.mimetype != 'text/html' or response.is_streamed
                or response.direct_passthrough or request.endpoint == 'static'
                or request.method == 'HEAD'):
            return response
        html = response.get_data(as_text=True)
        if 'data-pait-loading-assets' in html or not re.search(r'<head\b[^>]*>', html, re.I):
            return response
        version = app.config.get('APP_VERSION', '1')
        css = url_for('static', filename='css/glass-loading.css', v=version)
        js = url_for('static', filename='js/glass-loading.js', v=version)
        assets = (f'<link data-pait-loading-assets rel="stylesheet" href="{css}">'
                  f'<script src="{js}"></script>')
        response.set_data(re.sub(r'(<head\b[^>]*>)', lambda m: m[0] + assets,
                                 html, count=1, flags=re.I))
        return response
