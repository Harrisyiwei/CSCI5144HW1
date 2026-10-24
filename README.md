# Single-Server Key-Value Store

A Python HTTP key-value store with concurrent client handling, disk persistence, error handling, and timestamped logging.

## Files

- `server.py`: runs the key-value store server.
- `kv_bench.py`: writes keys, reads them back, verifies values, and measures performance.

## Requirements

Python 3.9 or newer. Both files use only Python's standard library. No additional packages or compilation are required.

## Run the server

Open Terminal in the folder containing the two Python files and run:

```
python3 server.py --port 8000
```

The server listens at `http://127.0.0.1:8000`. Leave this terminal running and open a second terminal for the commands below. Press Control+C to stop the server.

## Basic operations

PUT creates or updates a key:

```
curl -i -X PUT http://127.0.0.1:8000/kv/name -H 'Content-Type: application/json' -d '{"value":"Apple"}'
```

GET retrieves its value:

```
curl -i http://127.0.0.1:8000/kv/name
```

DEL removes the key using HTTP DELETE:

```
curl -i -X DELETE http://127.0.0.1:8000/kv/name
```

The literal HTTP method `DEL` is also supported. Reading the deleted key returns `404` with `{"error": "Key not found"}`.

| Status | Meaning |
| --- | --- |
| 200 | Operation succeeded |
| 400 | Invalid path, key, or PUT body |
| 404 | Key does not exist |
| 408 | Request timed out or disconnected, when a response can be sent |
| 500 | Storage or socket failure |

Keys must be nonempty and no longer than 1024 UTF-8 bytes. URL-encode special characters in keys. PUT requires a JSON object with a string `value`; the request body is limited to 1 MiB. Empty string values are allowed.

## Run the benchmark

In a second terminal, open the same project folder and run:

```
python3 kv_bench.py
```

The benchmark is already configured for `http://127.0.0.1:8000/kv`. It uses 3 worker threads to write 300 keys, then read and verify all 300 values. The phase named `set` sends HTTP PUT requests.

A successful full run reports:

- SET: 300 successful operations, zero mismatches, zero errors.
- GET: 300 successful operations, zero mismatches, zero errors.
- TOTAL: 600 successful operations.

The output includes elapsed time, successful operations per second, average latency, and p99 latency. Latency statistics include successful requests only. Actual performance depends on the machine and disk. Requests use a 30-second timeout. The benchmark uses distinct keys and does not test deletion or conflicting writes to the same key.

To change the workload, edit `NUM_THREADS` or `OPS_PER_THREAD` in `kv_bench.py`. If changing the server's port, update `BASE_URL` in the benchmark as well.

## Test persistence across a restart

With the server running, write the benchmark keys:

```
python3 kv_bench.py set
```

Stop the server with Control+C, then restart it from the same project folder:

```
python3 server.py --port 8000
```

Read and verify the saved keys:

```
python3 kv_bench.py get
```

The GET phase should report 300 successful operations, zero mismatches, and zero errors. Keep the benchmark settings unchanged between these phases.

## Implementation

The server uses `ThreadingHTTPServer` to handle connections in separate threads. One shared lock protects dictionary reads, updates, deletions, and snapshot saving. Operations execute one at a time inside this lock, including operations on different keys. Conflicting writes take effect in lock-acquisition order.

Every successful PUT or DEL saves the complete dictionary to `data/store.json` before returning success. The server writes and flushes a temporary file, calls `fsync`, and atomically replaces the previous snapshot. It loads this snapshot on startup. This supports process restarts; full power-loss durability is not guaranteed because the parent directory is not fsynced. Use only one server process per data file.

GET, PUT, and DEL attempts are logged with UTC timestamps, keys, and status codes. Values are omitted. Logs rotate at approximately 5 MB, keeping up to three backups.

View the current log from the project folder:

```
cat logs/operations.log
```

The server creates `data/` and `logs/` automatically; these generated files are not needed to start a fresh store. Each response closes its connection, so benchmark timings include connection setup. Saving a full snapshot for each mutation favors simplicity over write throughput.

## Optional server settings

| Option | Default |
| --- | --- |
| `--host` | `127.0.0.1` |
| `--port` | `8000` |
| `--data` | `data/store.json` |
| `--log` | `logs/operations.log` |

Relative data and log paths are resolved from the terminal's current working folder.
