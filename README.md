# Single-Server Key-Value Store

A Python server that stores, reads, and deletes key-value pairs. It supports concurrent requests, saves data to disk, and logs operations with timestamps.

## Files

- `server.py`: the server.
- `kv_bench.py`: tests writes and reads and measures performance.

Use these filenames when saving the downloaded Python files.

## Setup (macOS)

Open Terminal in the project folder. Python 3.9 or newer is required.

Create a virtual environment once:

```
python3 -m venv .venv
```

Install the benchmark's required package:

```
.venv/bin/python -m pip install requests
```

You do not need to activate the environment when using `.venv/bin/python` directly. The server itself needs no extra packages.

## Start the server

```
.venv/bin/python server.py --port 8000
```

Leave this terminal running. The server listens at `http://127.0.0.1:8000`. Press Control+C to stop it.

## Try the operations

Open a second terminal in the same project folder.

Store or update a value (PUT):

```
curl -i -X PUT http://127.0.0.1:8000/kv/name -H 'Content-Type: application/json' -d '{"value":"Apple"}'
```

Read the value (GET):

```
curl -i http://127.0.0.1:8000/kv/name
```

Delete the key (DEL, using HTTP DELETE):

```
curl -i -X DELETE http://127.0.0.1:8000/kv/name
```

Successful operations return 200. Reading or deleting a missing key returns 404. Invalid input returns 400. Keys must be nonempty strings, and values must be strings.

## Run the benchmark

Keep the server running. In the second terminal, run:

```
.venv/bin/python kv_bench.py
```

The benchmark uses 3 threads to write 300 keys, then reads all 300 keys and checks their values. It is already set to use port 8000 and the correct URL.

A successful run shows:

- SET: `ok=300 mismatch=0 error=0`
- GET: `ok=300 mismatch=0 error=0`
- TOTAL: 600 successful operations

It also reports throughput, average latency, and p99 latency. Performance numbers depend on your computer. The benchmark does not test deletion or conflicting writes to the same key.

## Check saved data after a restart

With the server running, write the keys:

```
.venv/bin/python kv_bench.py set
```

Stop the server with Control+C, then restart it from the same folder:

```
.venv/bin/python server.py --port 8000
```

In the second terminal, read and check the saved keys:

```
.venv/bin/python kv_bench.py get
```

It should show 300 successful reads with zero errors and zero mismatches.

## Data and logs

- Data is saved to `data/store.json` after every successful PUT or DEL and loaded when the server restarts.
- Logs are saved to `logs/operations.log` with UTC timestamps, operation names, keys, and status codes.
- These folders are created automatically.
- A shared lock protects the data so requests do not change it at the same time. Use only one server process per data file.

View the logs:

```
cat logs/operations.log
```

Keep `.venv/`, `data/`, and `logs/` out of GitHub. Each user can create their own environment using the setup commands above.
