"""Copy existing values to their new owners during a planned backend change.

Pause the router and any clients that write directly to backends before running
this command. Keep all old and new backends running on their configured ports.
Pass the snapshot path used when starting each backend.
"""

import argparse
from http.client import HTTPConnection, HTTPException
import json
from pathlib import Path
from urllib.parse import quote

from router import HashRing


def snapshot_argument(text):
    port, separator, filename = text.partition("=")
    if not separator or not port.isdecimal() or not filename:
        raise argparse.ArgumentTypeError("Use PORT=FILE for each snapshot")
    return int(port), Path(filename)


def read_snapshot(path, allow_missing):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if allow_missing:
            return {}
        raise
    if not isinstance(data, dict) or not all(
        isinstance(value, str) for value in data.values()
    ):
        raise ValueError(f"{path} must contain a JSON object of string values")
    return data


def write_to_backend(port, method, key, value=None):
    path = "/kv/" + quote(key, safe="")
    body = None
    headers = {}
    if method == "PUT":
        body = json.dumps({"value": value}).encode("utf-8")
        headers["Content-Type"] = "application/json"

    connection = HTTPConnection("127.0.0.1", port, timeout=12)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        response.read()
        if response.status != 200 and not (method == "DELETE" and response.status == 404):
            raise RuntimeError(f"{method} {path} on port {port} returned {response.status}")
    except (OSError, HTTPException) as error:
        raise RuntimeError(f"{method} {path} failed on port {port}: {error}") from error
    finally:
        connection.close()


def rebalance(old_ports, new_ports, paths):
    old_ring = HashRing(old_ports)
    new_ring = HashRing(new_ports)
    snapshots = {
        port: read_snapshot(path, allow_missing=port not in old_ports)
        for port, path in paths.items()
    }

    # A backend can still hold copies from a previous configuration.
    # The old ring tells us which copy represents the current value.
    values = {
        key: value
        for port in old_ports
        for key, value in snapshots[port].items()
        if old_ring.owner(key) == port
    }

    moved = 0
    copied = 0
    for key, value in values.items():
        target = new_ring.owner(key)
        if target != old_ring.owner(key):
            moved += 1
        if snapshots[target].get(key) != value:
            write_to_backend(target, "PUT", key, value)
            copied += 1

    # Prevent a deleted key from reappearing when a stale copy gets a new owner.
    # Every key still visible through the old ring stays available for rollback.
    for port in new_ports:
        for key in snapshots[port]:
            if key not in values and new_ring.owner(key) == port:
                write_to_backend(port, "DELETE", key)

    print(f"Rebalance complete. {len(values)} keys, {moved} changed owners, {copied} copied.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", type=int, nargs="+", required=True)
    parser.add_argument("--new", type=int, nargs="+", required=True)
    parser.add_argument("--snapshot", type=snapshot_argument, nargs="+", required=True)
    args = parser.parse_args()

    old_ports = set(args.old)
    new_ports = set(args.new)
    paths = dict(args.snapshot)
    if any(not 1 <= port <= 65535 for port in old_ports | new_ports):
        parser.error("Ports must be between 1 and 65535")
    if len(paths) != len(args.snapshot) or paths.keys() != old_ports | new_ports:
        parser.error("Provide one snapshot path per old or new port")
    if len({path.resolve() for path in paths.values()}) != len(paths):
        parser.error("Each backend must use a separate snapshot file")

    try:
        rebalance(old_ports, new_ports, paths)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"Rebalance stopped. Keep the old backend list and retry. {error}\n")


if __name__ == "__main__":
    main()
