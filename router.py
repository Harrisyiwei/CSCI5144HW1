"""Route the team's /kv/<key> requests to local KV servers."""

import argparse
from bisect import bisect_left
from hashlib import sha256
from http.client import HTTPConnection, HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import unquote, urlsplit


def hash_position(text):
    return int.from_bytes(sha256(text.encode("utf-8")).digest(), "big")


class HashRing:
    def __init__(self, ports):
        # Multiple positions per backend help spread keys more evenly.
        entries = sorted(
            (hash_position(f"127.0.0.1:{port}#{replica}"), port)
            for port in set(ports)
            for replica in range(128)
        )
        self.positions = [position for position, _ in entries]
        self.ports = [port for _, port in entries]

    def owner(self, key):
        index = bisect_left(self.positions, hash_position(key))
        # Wrap around when the key falls beyond the last position.
        return self.ports[index % len(self.ports)]


class Router(ThreadingHTTPServer):
    def __init__(self, port, backends):
        self.ring = HashRing(backends)
        super().__init__(("127.0.0.1", port), RouterHandler)


class RouterHandler(BaseHTTPRequestHandler):
    timeout = 10

    def reply(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def reply_error(self, status, message):
        self.reply(status, "application/json", json.dumps({"error": message}).encode())

    def forward(self):
        path = urlsplit(self.path).path
        prefix, separator, key = path.partition("/kv/")
        if prefix or not separator or not key:
            self.reply_error(404, "Use /kv/<key>")
            return

        body = None
        headers = {}
        if self.command == "PUT":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or "Transfer-Encoding" in self.headers:
                    raise ValueError
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValueError
            except ValueError:
                self.reply_error(400, "Invalid request body length")
                return
            except TimeoutError:
                self.reply_error(408, "Timed out reading request body")
                return
            if "Content-Type" in self.headers:
                headers["Content-Type"] = self.headers["Content-Type"]

        backend = self.server.ring.owner(unquote(key))
        connection = HTTPConnection("127.0.0.1", backend, timeout=12)
        try:
            connection.request(self.command, path, body=body, headers=headers)
            response = connection.getresponse()
            status = response.status
            content_type = response.getheader("Content-Type", "application/json")
            payload = response.read()
        except (OSError, HTTPException):
            self.reply_error(503, f"Backend on port {backend} is unavailable")
            return
        finally:
            connection.close()
        self.reply(status, content_type, payload)

    do_GET = forward
    do_PUT = forward
    do_DELETE = forward


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--backends", type=int, nargs="+", required=True)
    args = parser.parse_args()
    if any(not 1 <= port <= 65535 for port in [args.port, *args.backends]):
        parser.error("Ports must be between 1 and 65535")
    if args.port in args.backends:
        parser.error("The router port must be different from the backend ports")

    with Router(args.port, args.backends) as router:
        print(f"Router listening on http://127.0.0.1:{args.port}", flush=True)
        print(f"Backend ports: {', '.join(map(str, args.backends))}", flush=True)
        try:
            router.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
