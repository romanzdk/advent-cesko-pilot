"""Credential-free JSON-only receiver. Run with: python3 -m backend.receiver --help."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import socket
import sqlite3
import threading
import time

from .errors import APIError
from .store import Store
from .validation import invalid, load_catalogue, validate, valid_uuid


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            invalid()
        result[key] = value
    return result


def make_server(*, state_dir, catalogue, host="127.0.0.1", port=8789,
                origins=None, clock=time.time, minute_limit=10, day_limit=100,
                max_body=16384, max_concurrency=8, read_timeout=5, request_timeout=10):
    origins = frozenset(origins if origins is not None else {"https://kamnaadvent.cz"})
    if host != "127.0.0.1" or not origins or "*" in origins or min(max_body, max_concurrency, read_timeout, request_timeout) <= 0:
        raise ValueError("loopback and explicit origins/bounds required")
    store = Store(state_dir, clock=clock, minute_limit=minute_limit, day_limit=day_limit)
    slots = threading.BoundedSemaphore(max_concurrency)

    class Server(ThreadingHTTPServer):
        daemon_threads = True
        block_on_close = True
        request_queue_size = 16

        def process_request(self, request, client_address):
            if not slots.acquire(blocking=False):
                try:
                    request.settimeout(0.2)
                    body = b'{"error":"unavailable","message":"Zkuste to pozdeji."}'
                    request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nContent-Type: application/json\r\nCache-Control: no-store\r\nConnection: close\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
                except OSError:
                    pass
                finally:
                    self.shutdown_request(request)
                return
            try:
                super().process_request(request, client_address)
            except BaseException:
                slots.release()
                raise

        def process_request_thread(self, request, client_address):
            try:
                super().process_request_thread(request, client_address)
            finally:
                slots.release()

        def handle_error(self, request, client_address):
            pass  # No traceback containing public request data.

    class Handler(BaseHTTPRequestHandler):
        server_version = "Feedback"
        sys_version = ""
        protocol_version = "HTTP/1.0"  # One request per bounded connection.

        def setup(self):
            super().setup()
            self.connection.settimeout(read_timeout)
            self.deadline = threading.Timer(request_timeout, self.expire)
            self.deadline.daemon = True
            self.deadline.start()

        def expire(self):
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

        def finish(self):
            self.deadline.cancel()
            try:
                super().finish()
            except OSError:
                pass

        def log_message(self, format, *args):
            pass  # Never log paths, challenges, request bodies or source URLs.

        def send_error(self, code, message=None, explain=None):
            self.reply(code, {"error": "validation", "message": "Neplatný HTTP požadavek."})

        def reply(self, code, body, *, preflight=False):
            data = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "close")
            self.send_header("Vary", "Origin")
            if getattr(self, "headers", {}).get("Origin") in origins:
                self.send_header("Access-Control-Allow-Origin", self.headers["Origin"])
                if preflight:
                    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                    self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(data)
            self.close_connection = True

        def dispatch(self):
            try:
                origin_headers = self.headers.get_all("Origin", [])
                if len(origin_headers) > 1 or (origin_headers and origin_headers[0] not in origins):
                    raise APIError(403, "origin", "Tento původ není povolen.")
                if self.command in {"POST", "OPTIONS"} and not origin_headers:
                    raise APIError(403, "origin", "Tento původ není povolen.")
                status_id = self.path.removeprefix("/api/submissions/") if self.path.startswith("/api/submissions/") else ""
                route = self.path in {"/health", "/api/challenge", "/api/submissions"} or valid_uuid(status_id)
                if not route:
                    raise APIError(404, "not_found", "Nenalezeno.")
                if self.command == "OPTIONS":
                    method = self.headers.get("Access-Control-Request-Method", "")
                    requested = {x.strip().lower() for x in self.headers.get("Access-Control-Request-Headers", "").split(",") if x.strip()}
                    if method not in {"GET", "POST"} or requested - {"content-type"}:
                        raise APIError(403, "origin", "Požadavek není povolen.")
                    self.reply(200, {"ok": True}, preflight=True)
                elif self.command == "GET" and self.path == "/health":
                    self.reply(200, {"ok": True})
                elif self.command == "GET" and self.path == "/api/challenge":
                    self.reply(200, {"challenge": store.challenge()})
                elif self.command == "GET" and valid_uuid(status_id):
                    self.reply(200, store.status(status_id))
                elif self.command == "POST" and self.path == "/api/submissions":
                    self.submit()
                else:
                    raise APIError(405, "method", "Metoda není povolena.")
            except APIError as exc:
                self.reply(exc.code, exc.body())
            except (sqlite3.Error, OSError):
                try:
                    self.reply(503, {"error": "unavailable", "message": "Podání nyní nelze potvrdit. Zkuste stejné podání později."})
                except OSError:
                    pass

        def submit(self):
            lengths = self.headers.get_all("Content-Length", [])
            if self.headers.get("Transfer-Encoding") or len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,9}", lengths[0]):
                invalid("Požadavek nemá platnou délku.")
            length = int(lengths[0])
            if length > max_body:
                raise APIError(413, "too_large", "Podání je příliš dlouhé.")
            if (len(self.headers.get_all("Content-Type", [])) != 1
                    or self.headers.get("Content-Type", "").lower().replace(" ", "") not in {"application/json", "application/json;charset=utf-8"}
                    or self.headers.get("Content-Encoding")):
                raise APIError(415, "content_type", "Použijte JSON bez komprese.")
            raw = self.rfile.read(length)
            if len(raw) != length:
                invalid()
            try:
                payload = json.loads(raw.decode("utf-8"), object_pairs_hook=strict_object,
                                     parse_constant=lambda _: invalid())
            except (ValueError, UnicodeError, RecursionError):
                return invalid("Podání není platný JSON.")
            if (not isinstance(payload, dict) or not valid_uuid(payload.get("requestId"))
                    or payload.get("website", "") != ""):
                invalid()
            if "challenge" not in payload:
                raise APIError(400, "challenge", "Obnovte ověření formuláře.")
            replay = store.retry(payload["requestId"], payload)
            if replay is not None:
                self.reply(*replay)
                return
            try:
                events = load_catalogue(catalogue)
            except (OSError, ValueError, TypeError, KeyError):
                raise APIError(503, "unavailable", "Katalog nyní není dostupný. Zkuste stejné podání později.") from None
            canonical = validate(payload, events)
            code, result = store.accept(payload["requestId"], canonical, payload["challenge"])
            self.reply(code, result)

        do_GET = do_POST = do_OPTIONS = do_DELETE = do_PUT = do_PATCH = do_HEAD = dispatch

    return Server((host, port), Handler)


def main(argv=None):
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Credential-free loopback anonymous feedback receiver")
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--catalogue", required=True, help="Fixed local site/events.json")
    parser.add_argument("--port", default=8789, type=int)
    parser.add_argument("--origin", action="append", help="Exact allowed origin (repeatable)")
    args = parser.parse_args(argv)
    try:
        with make_server(state_dir=args.state_dir, catalogue=args.catalogue, port=args.port, origins=args.origin) as server:
            print(json.dumps({"listening": "127.0.0.1", "port": server.server_address[1]}), flush=True)
            server.serve_forever()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        print("Receiver unavailable.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
