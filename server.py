import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.data = json.loads(self.path.read_text('utf-8')) if self.path.exists() else {}
        if not isinstance(self.data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in self.data.items()):
            raise ValueError('Snapshot must be a JSON object mapping strings to strings')

    def save(self, data):
        # Same-directory temporary file makes replacement atomic on local filesystems.
        fd, name = tempfile.mkstemp(dir=self.path.parent, prefix='.snapshot-')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def execute(self, method, key, value=None):
        with self.lock:
            if method == 'GET':
                result = (200, {'key': key, 'value': self.data[key]}) if key in self.data else (404, {'error': 'Key not found'})
            elif method == 'PUT':
                updated = self.data.copy()
                updated[key] = value
                self.save(updated)
                self.data = updated
                result = (200, {'key': key, 'value': value})
            else:
                if key not in self.data:
                    result = (404, {'error': 'Key not found'})
                else:
                    updated = self.data.copy()
                    del updated[key]
                    self.save(updated)
                    self.data = updated
                    result = (200, {'key': key, 'deleted': True})
            return result


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *_):
        pass  # Structured application log below replaces default access logging.

    def process(self):
        key = None
        operation = 'DEL' if self.command == 'DELETE' else self.command
        status, payload = 500, {'error': 'Internal server error'}
        try:
            path = urlsplit(self.path).path
            if not path.startswith('/kv/') or not path[4:]:
                status, payload = 400, {'error': 'Use /kv/<nonempty-key>'}
            else:
                key = unquote(path[4:], errors='strict')
                if len(key.encode('utf-8')) > 1024:
                    raise ValueError('Key exceeds 1024 bytes')
                value = None
                if self.command == 'PUT':
                    if self.headers.get('Transfer-Encoding'):
                        raise ValueError('Transfer-Encoding is unsupported; use Content-Length')
                    length = int(self.headers.get('Content-Length', '-1'))
                    if not 0 <= length <= 1048576:
                        raise ValueError('Content-Length must be between 0 and 1048576')
                    raw = self.rfile.read(length)
                    if len(raw) != length:
                        raise ValueError('Incomplete request body')
                    body = json.loads(raw)
                    if not isinstance(body, dict) or not isinstance(body.get('value'), str):
                        raise ValueError('PUT requires JSON: {"value": "a string"}')
                    value = body['value']
                status, payload = self.server.store.execute(operation, key, value)
        except (ValueError, UnicodeError) as exc:
            status, payload = 400, {'error': str(exc)}
        except (TimeoutError, ConnectionError):
            status, payload = 408, {'error': 'Request timed out or disconnected'}
        except OSError:
            logging.exception('Storage or socket failure')
            status, payload = 500, {'error': 'Storage unavailable; operation not acknowledged'}
        finally:
            logging.info(json.dumps({'operation': operation, 'key': key, 'status': status}, ensure_ascii=True))
        encoded = json.dumps(payload, ensure_ascii=True).encode()
        try:
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(encoded)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(encoded)
        except (OSError, TimeoutError):
            pass  # Client disconnection does not crash the server.

    do_GET = process
    do_PUT = process
    do_DELETE = process
    do_DEL = process  # Also accept the assignment's literal DEL method.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--data', default='data/store.json')
    parser.add_argument('--log', default='logs/operations.log')
    args = parser.parse_args()
    Path(args.log).parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(args.log, maxBytes=5_000_000, backupCount=3)
    formatter = logging.Formatter('%(asctime)sZ %(levelname)s %(message)s', '%Y-%m-%dT%H:%M:%S')
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    try:
        store = Store(args.data)
        with ThreadingHTTPServer((args.host, args.port), Handler) as server:
            server.store = store
            print(f'Listening on http://{args.host}:{args.port}; Ctrl+C to stop', flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Cannot start server: {exc}\n')


if __name__ == '__main__':
    main()
