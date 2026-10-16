"""Local tablet backend with a separate database and debugger disabled."""
import argparse
import getpass
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5003)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--create-user', metavar='USERNAME')
    parser.add_argument('--init-only', action='store_true')
    parser.add_argument('--offline', action='store_true', help='login/history only; no cloud model calls')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be 1..65535')
    runtime = ROOT / 'uploads' / 'harmony-dev'
    runtime.mkdir(parents=True, exist_ok=True)
    secret_path = runtime / 'session-secret.txt'
    try:
        with secret_path.open('x', encoding='utf-8') as f:
            f.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    # Set before importing app.config so .env cannot select the user's normal database.
    os.environ['DATABASE'] = str(runtime / 'tablet.db')
    os.environ['SECRET_KEY'] = secret_path.read_text(encoding='utf-8').strip()
    os.environ['DEBUG'] = 'false'
    if args.offline:
        os.environ['GLM_API_KEY'] = 'offline-development-placeholder'
        os.environ['GLM_BASE_URL'] = 'http://127.0.0.1:1/disabled'
        os.environ['GLM_REALTIME_ENABLED'] = 'false'
    from app import create_app
    from app.db import get_db, init_db
    from werkzeug.security import generate_password_hash
    app = create_app()
    from flask import jsonify, request

    @app.before_request
    def tablet_routes_only():
        # This launcher exposes only the first native milestone, never unrelated cloud jobs.
        if not request.path.startswith('/api/mobile/v1/'):
            return jsonify(error='Use the native tablet API on this development server'), 404

    if args.offline:
        from app.llm.client import LLMError

        class OfflineModel:
            def chat(self, *args, **kwargs):
                raise LLMError('Offline development: configure GLM_API_KEY and restart without --offline')

        app.extensions['llm'] = OfflineModel()
        print('Offline mode: login/history available; AI chat returns service unavailable.')
    with app.app_context():
        init_db()
        if args.create_user:
            name = args.create_user
            if not 0 < len(name) <= 128:
                parser.error('username must be 1..128 characters')
            db = get_db()
            if db.execute('SELECT 1 FROM users WHERE user_name=?', (name,)).fetchone():
                parser.error('user already exists; no password or data was changed')
            password = getpass.getpass('New development account password: ')
            if not 8 <= len(password) <= 1024:
                parser.error('password must be 8..1024 characters')
            if password != getpass.getpass('Repeat password: '):
                parser.error('passwords do not match')
            with db:
                db.execute('INSERT INTO users(user_name,pwd) VALUES (?,?)',
                           (name, generate_password_hash(password)))
            print('Development account created. No existing accounts were changed.')
            return 0
    print('Isolated tablet database:', runtime / 'tablet.db')
    if args.init_only:
        return 0
    print(f'Tablet: use this computer LAN IPv4 address, port {args.port}; do not use 127.0.0.1.')
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False, threaded=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
