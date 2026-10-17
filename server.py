"""Browser transport: local by default, with explicitly enabled LAN play."""
import argparse
import hmac
import json
import re
import secrets
import threading
import time
import ipaddress
import socket
from http.cookies import SimpleCookie
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


def make_server(game, port=8765, host='127.0.0.1'):
    token = secrets.token_urlsafe(32)
    owner_key = secrets.token_urlsafe(24)
    multiplayer = getattr(game, 'multiplayer', False)
    sessions = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def allowed_host(self):
            value = self.headers.get('Host', '')
            if value in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}:
                return True
            if host != '0.0.0.0' or not multiplayer:
                return False
            try:
                parsed = urlparse('//'+value)
                if parsed.port != self.server.server_port or parsed.username or parsed.password:
                    return False
                if parsed.hostname == socket.gethostname().lower():
                    return True
                address = ipaddress.ip_address(parsed.hostname or '')
                return address.version == 4 and (address.is_private or address.is_loopback)
            except ValueError:
                return False

        def session(self):
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get('Cookie', ''))
                ident = cookie.get(f'relic_session_{self.server.server_port}')
                session = sessions.get(ident.value if ident else '')
            except Exception:
                return None
            if session and session['expires'] > time.time():
                return session
            if ident:
                sessions.pop(ident.value, None)
            return None

        def select_character(self, ident, owner=False):
            if ident:
                game.resume_character(ident)
            key = secrets.token_urlsafe(32)
            previous = self.session()
            # Prune expired sessions instead of accumulating them indefinitely.
            for old, session in list(sessions.items()):
                if session['expires'] <= time.time() or session is previous:
                    sessions.pop(old, None)
            # Picking the owner's character does not grant world-editor access.
            sessions[key] = dict(player_id=ident, owner=owner, expires=time.time()+86400)
            if previous and not any(s['player_id'] == previous['player_id'] for s in sessions.values()):
                game._presence.pop(previous['player_id'], None)
            self.session_cookie = f'relic_session_{self.server.server_port}={key}; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400'
            return sessions[key]

        def player_state(self, session):
            ident = session['player_id'] if session else None
            game.touch(ident)
            with game.as_player(ident):
                result = game.snapshot()
            result['session'] = dict(owner=bool(session and session['owner']))
            if not ident:
                result['characters'] = game.character_choices()
            return dict(result, token=token)

        def require_owner(self):
            if multiplayer and not (self.session() or {}).get('owner'):
                self.reply(403, {'error': 'Open the host link from the game launcher to use the owner editor.'})
                return False
            return True

        def quit_reply(self, session, stopped):
            return dict(title=game.w['title'], time=game.clock(), player=None, log=[],
                        multiplayer=multiplayer, session=dict(owner=bool(session and session['owner'])),
                        token=token, ui_action='quit', quit=dict(server_stopped=stopped))

        def quit_game(self, session):
            ident = session['player_id'] if session else None
            if multiplayer:
                if not session:
                    return self.reply(401, {'error': 'Choose a character first.'})
                if ident:
                    with game.as_player(ident):
                        result = game.command('quit')
                    if result.get('ui_action') != 'quit':
                        result['session'] = dict(owner=session['owner'])
                        return self.reply(200, result)
                    game.leave_character(ident)
                else:
                    game.save()
                # Clear every view of this character, including other browser tabs.
                for value in sessions.values():
                    if value['player_id'] == ident:
                        value['player_id'] = None
                with game.as_player(None):
                    others = game.social_players()
                stopped = session['owner'] and not others
            else:
                result = game.command('quit')
                if result.get('ui_action') != 'quit':
                    return self.reply(200, result)
                stopped = True
            if stopped:
                self.server.stop_requested.set()
            self.reply(200, self.quit_reply(session, stopped))
            if stopped:
                # shutdown() must run outside serve_forever's thread, after the reply.
                threading.Thread(target=self.server.shutdown, daemon=True).start()

        def reply(self, status, body, content_type='application/json; charset=utf-8', cache='no-store'):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', cache)
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'same-origin')
            if getattr(self, 'session_cookie', None):
                self.send_header('Set-Cookie', self.session_cookie)
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
                with game.lock:
                    if self.server.stop_requested.is_set():
                        return self.reply(200, self.quit_reply(self.session(), True))
                    if multiplayer:
                        return self.reply(200, self.player_state(self.session()))
                    return self.reply(200, dict(game.snapshot(), token=token))
            if route == '/api/world':
                if not self.require_owner(): return
                with game.lock:
                    return self.reply(200, game.w)
            if route == '/api/editor-schema':
                if not self.require_owner(): return
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
            if origin and origin != 'http://'+self.headers.get('Host', ''):
                return self.reply(403, {'error': 'Local access only.'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 1000000:
                    return self.reply(413, {'error': 'Request is too large or empty.'})
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError('Expected an object.')
                route = urlparse(self.path).path
                with game.lock:
                    if self.server.stop_requested.is_set():
                        return self.reply(503, {'error': 'The game has been saved and stopped. Reopen the launcher to play.'})
                    raw = ' '.join(str(data.get('command', '')).split())
                    if route == '/api/quit' or route == '/api/command' and raw.casefold() in ('quit', 'logout', 'exit'):
                        return self.quit_game(self.session() if multiplayer else None)
                    if multiplayer:
                        return self.multiplayer_post(route, data)
                if route == '/api/create':
                    return self.reply(200, game.create(data.get('name', ''), data.get('race', 'human'), data.get('class', 'warrior'), gender=data.get('gender', 'male')))
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

        def multiplayer_post(self, route, data):
            session = self.session()
            ident = session['player_id'] if session else None
            if route == '/api/host':
                code = data.get('code', '')
                if not isinstance(code, str) or not hmac.compare_digest(code, owner_key):
                    raise ValueError('Reopen the host link from the game launcher.')
                session = self.select_character(game.owner_id, owner=True)
                return self.reply(200, self.player_state(session))
            if route in ('/api/join', '/api/create', '/api/leave'):
                owner = bool(session and session['owner'])
                if route == '/api/join':
                    ident = data.get('player_id')
                    if not isinstance(ident, str) or ident not in game.state['players']:
                        raise ValueError('Choose a character from the list.')
                elif route == '/api/create':
                    if ident:
                        raise ValueError('Choose Switch character before creating another character.')
                    ident = game.create_character(data.get('name', ''), data.get('race', 'human'), data.get('class', 'warrior'), owner=owner, gender=data.get('gender', 'male'))
                else:
                    ident = None
                session = self.select_character(ident, owner=owner)
                return self.reply(200, self.player_state(session))
            if route == '/api/world':
                if not self.require_owner(): return
                with game.as_player(ident):
                    game.update_world(data)
                return self.reply(200, {'ok': True})
            if route == '/api/command':
                if not ident:
                    return self.reply(401, {'error': 'Choose a character first.'})
                game.touch(ident)
                with game.as_player(ident):
                    result = game.command(data.get('command', ''))
                result['session'] = dict(owner=session['owner'])
                return self.reply(200, result)
            return self.reply(404, {'error': 'Not found.'})

    server = ThreadingHTTPServer((host, port), Handler)
    server.owner_key = owner_key
    server.stop_requested = threading.Event()
    return server


def main():
    parser = argparse.ArgumentParser(description='Run Relic Frontier locally.')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--host', choices=['127.0.0.1', '0.0.0.0'], default='127.0.0.1', help='Use 0.0.0.0 to allow players on your local network.')
    args = parser.parse_args()
    (ROOT / 'saves').mkdir(exist_ok=True)
    database_path = ROOT / 'saves' / 'game.sqlite3'
    try:
        from multiplayer import MultiplayerGame
        game = MultiplayerGame(ROOT / 'content' / 'world.json', database_path)
        server = make_server(game, args.port, args.host)
    except (OSError, ValueError) as error:
        print(f'Could not start the game: {error}')
        print('If another copy is running, use its browser window. Otherwise try: python server.py --port 8766')
        return 1
    stop = server.stop_requested
    failed = threading.Event()

    def ticker():
        while not stop.wait(.1):
            try:
                with game.lock:
                    if not stop.is_set():
                        game.tick()
            except Exception:
                import traceback
                traceback.print_exc()
                print('Game clock stopped after an error. Restart the launcher after checking the error above.')
                failed.set()
                stop.set()
                server.shutdown()

    thread = threading.Thread(target=ticker, daemon=True); thread.start()
    address = f'http://127.0.0.1:{server.server_port}'
    print(f'\nRELIC FRONTIER v0.9.1\nFolder: {ROOT}\n\nPlay:  {address}\nHost link (includes owner editor): {address}/?owner={server.owner_key}\n\nChoose a character to play. Passwords are not enabled during multiplayer testing.\nKeep this window open while playing.\nType QUIT in the game to save and leave. If the host is alone, the server stops too.\nClosing the browser without QUIT leaves combat running. Ctrl+C is a fallback to stop and save.\n', flush=True)
    if args.host == '0.0.0.0':
        print(f'LAN play enabled. Other players can open http://{socket.gethostname()}:{server.server_port} on this network. Share the play address; keep the host link for yourself.', flush=True)
        try:
            addresses = sorted({row[4][0] for row in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET) if not ipaddress.ip_address(row[4][0]).is_loopback})
            for network_address in addresses:
                print(f'Network play address: http://{network_address}:{server.server_port}', flush=True)
        except OSError:
            pass
    print(f'Save file: {database_path}', flush=True)
    if game.p:
        print(f'Loaded character: {game.p["name"]} | Level {game.p["level"]} | XP {game.p["xp"]} | Location: {game.w["rooms"][game.p["room"]]["name"]}\n', flush=True)
    else:
        print('This copy has no saved character.\n', flush=True)
    if not args.no_browser:
        webbrowser.open(address+'/?owner='+server.owner_key)
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set(); thread.join(timeout=2); server.server_close()
        with game.lock:
            game.save(); game.db.close()
        print('Progress saved. See you at the fountain.')
    return 1 if failed.is_set() else 0


if __name__ == '__main__':
    raise SystemExit(main())
