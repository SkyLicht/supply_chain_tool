from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_MO_FILENAME = r"C:\Users\jorgeortiza\Downloads\R_MO_BASE_T_result.json"
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "resources"


def _load_mo_json(data_dir: Path, filename: str) -> Any:
    mo_path = data_dir / filename
    with mo_path.open("r", encoding="utf-8") as file:
        return json.load(file)


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path != "/api/v1/get_mo":
            self.send_error(HTTPStatus.NOT_FOUND, "Route not found.")
            return

        data_dir = Path(os.getenv("MO_DATA_DIR", str(DEFAULT_DATA_DIR)))
        filename = os.getenv("MO_JSON_FILE", DEFAULT_MO_FILENAME)

        try:
            payload = _load_mo_json(data_dir, filename)
        except FileNotFoundError:
            self.send_error(
                HTTPStatus.NOT_FOUND,
                f"JSON file not found: {data_dir / filename}",
            )
            return
        except json.JSONDecodeError:
            self.send_error(
                HTTPStatus.BAD_REQUEST,
                f"Invalid JSON in file: {data_dir / filename}",
            )
            return

        body = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    server = ThreadingHTTPServer((host, port), RequestHandler)
    print(f"Serving on http://{host}:{port}")
    server.serve_forever()


# if __name__ == "__main__":

# $env:MO_DATA_DIR="C:\path\to\dir"
# $env:MO_JSON_FILE="your_file.json"
# python cmd/baisc_api_to_mo.py