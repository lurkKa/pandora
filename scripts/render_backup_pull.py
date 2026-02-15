#!/usr/bin/env python3
"""
Pulls an authenticated SQLite backup from a deployed PANDORA instance and stores it as .db.gz.
"""

from __future__ import annotations

import argparse
import gzip
import json
import pathlib
import sys
import urllib.error
import urllib.request


def _request_json(url: str, method: str, payload: dict | None = None, headers: dict | None = None, timeout: int = 60):
    body = None
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, data=body, headers=req_headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        text = raw.decode("utf-8", errors="replace")
        return json.loads(text or "{}")


def _request_bytes(url: str, method: str, headers: dict | None = None, timeout: int = 180) -> bytes:
    req = urllib.request.Request(url=url, data=None, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def main() -> int:
    parser = argparse.ArgumentParser(description="Download SQLite backup from PANDORA server")
    parser.add_argument("--base-url", required=True, help="Base URL, e.g. https://pandora-academy.onrender.com")
    parser.add_argument("--username", required=True, help="Admin username")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--output", required=True, help="Output .db.gz path")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    output_path = pathlib.Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        login_data = _request_json(
            f"{base_url}/api/auth/login",
            method="POST",
            payload={"username": args.username, "password": args.password},
            timeout=60,
        )
        token = (login_data or {}).get("token")
        if not token:
            raise RuntimeError("Login succeeded without token")

        backup_raw = _request_bytes(
            f"{base_url}/api/admin/backup/sqlite",
            method="GET",
            headers={"Authorization": f"Bearer {token}"},
            timeout=180,
        )
        if not backup_raw:
            raise RuntimeError("Backup endpoint returned empty response")

        with gzip.open(output_path, "wb", compresslevel=9) as gz:
            gz.write(backup_raw)

        print(f"Backup saved: {output_path} ({len(backup_raw)} bytes raw)")
        return 0
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        print(f"HTTP error: {e.code} {e.reason}\n{body}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"Backup failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
