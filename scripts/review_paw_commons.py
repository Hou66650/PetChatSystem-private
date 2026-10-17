"""Loopback-only, allowlisted design review. Does not expose the repository."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = [ROOT / p for p in ('art/paw-commons-v2', 'static/models/paw-commons-v2', 'static/js/vendor')]


class ReviewHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        candidate = (ROOT / unquote(urlsplit(path).path).lstrip('/')).resolve()
        if any(candidate.is_relative_to(root.resolve()) for root in ALLOWED):
            return str(candidate)
        return str(ROOT / '__no_review_file__')

    def list_directory(self, path):
        self.send_error(403, 'Directory listing disabled')
        return None


if __name__ == '__main__':
    print('http://127.0.0.1:5089/art/paw-commons-v2/index.html', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 5089), ReviewHandler).serve_forever()
