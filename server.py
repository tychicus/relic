"""Local-only browser transport. Keep this server bound to loopback."""
import argparse
import hmac
import json
import re
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from engine import Game

ROOT = Path(__file__).resolve().parent
# Built by `npm run build` in ui/. Players only need these files, not Node.
STATIC = ROOT / 'static'
PAGES = {'/': 'index.html', '/admin': 'admin.html'}
ASSET_TYPES = {'.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.woff2': 'font/woff2', '.svg': 'image/svg+xml', '.png': 'image/png'}
ASSET_NAME = re.compile(r'[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+)*')


def make_server(game, port=8765):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def allowed_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def reply(self, status, body, content_type='application/json; charset=utf-8', cache='no-store'):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', cache)
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            # Inline styles are allowed for the UI library's dialog scroll lock; scripts stay same-origin only.
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            if not self.allowed_host():
                return self.reply(403, {'error': 'Local access only.'})
            route = urlparse(self.path).path
            if route == '/api/state':
                return self.reply(200, dict(game.snapshot(), token=token))
            if route == '/api/world':
                with game.lock:
                    return self.reply(200, game.w)
            if route == '/api/editor-schema':
                from revision_rules import SCHEMA
                return self.reply(200, SCHEMA)
            if route in PAGES:
                page = STATIC / PAGES[route]
                if not page.is_file():
                    return self.reply(500, b'The game interface is missing. Run "npm run build" in the ui folder.', 'text/plain; charset=utf-8')
                return self.reply(200, page.read_bytes(), 'text/html; charset=utf-8')
            if route.startswith('/assets/'):
                # Only plain file names directly inside static/assets; built names are content-hashed.
                name = route[len('/assets/'):]
                asset = STATIC / 'assets' / name
                if ASSET_NAME.fullmatch(name) and asset.suffix in ASSET_TYPES and asset.is_file():
                    return self.reply(200, asset.read_bytes(), ASSET_TYPES[asset.suffix], 'public, max-age=31536000, immutable')
            return self.reply(404, {'error': 'Not found.'})

        def do_POST(self):
            if not self.allowed_host() or not hmac.compare_digest(self.headers.get('X-Game-Token', ''), token):
                return self.reply(403, {'error': 'Reload the game page to reconnect.'})
            origin = self.headers.get('Origin')
            if origin and origin not in {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}:
                return self.reply(403, {'error': 'Local access only.'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 1000000:
                    return self.reply(413, {'error': 'Request is too large or empty.'})
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError('Expected an object.')
                route = urlparse(self.path).path
                if route == '/api/create':
                    return self.reply(200, game.create(data.get('name', ''), data.get('race', 'human'), data.get('class', 'warrior')))
                if route == '/api/command':
                    return self.reply(200, game.command(data.get('command', '')))
                if route == '/api/world':
                    game.update_world(data)
                    return self.reply(200, {'ok': True})
                return self.reply(404, {'error': 'Not found.'})
            except (ValueError, TypeError, KeyError) as error:
                return self.reply(400, {'error': str(error)})
            except Exception:
                import traceback
                traceback.print_exc()
                return self.reply(500, {'error': 'The server hit an error. Check the launcher window.'})

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description='Run Relic Frontier locally.')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    (ROOT / 'saves').mkdir(exist_ok=True)
    database_path = ROOT / 'saves' / 'game.sqlite3'
    try:
        game = Game(ROOT / 'content' / 'world.json', database_path)
        server = make_server(game, args.port)
    except (OSError, ValueError) as error:
        print(f'Could not start the game: {error}')
        print('If another copy is running, use its browser window. Otherwise try: python server.py --port 8766')
        return 1
    stop = threading.Event()

    def ticker():
        while not stop.wait(.1):
            try:
                game.tick()
            except Exception:
                import traceback
                traceback.print_exc()
                print('Game clock stopped after an error. Restart the launcher after checking the error above.')
                stop.set()
                server.shutdown()

    thread = threading.Thread(target=ticker, daemon=True); thread.start()
    address = f'http://127.0.0.1:{server.server_port}'
    print(f'\nRELIC FRONTIER v0.9.1\nFolder: {ROOT}\n\nPlay:  {address}\nOwner: {address}/admin\n\nKeep this window open while playing.\nReturn to safety before closing your browser: combat keeps running.\nPress Ctrl+C here to stop the server and save.\n', flush=True)
    print(f'Save file: {database_path}', flush=True)
    if game.p:
        print(f'Loaded character: {game.p["name"]} | Level {game.p["level"]} | XP {game.p["xp"]} | Location: {game.w["rooms"][game.p["room"]]["name"]}\n', flush=True)
    else:
        print('This copy has no saved character.\n', flush=True)
    if not args.no_browser:
        webbrowser.open(address)
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set(); thread.join(timeout=2); server.server_close()
        with game.lock:
            game.save(); game.db.close()
        print('Progress saved. See you at the fountain.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
