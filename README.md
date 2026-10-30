# Single-Server Key-Value Store

A Python server that stores, reads, and deletes key-value pairs. It supports concurrent requests, saves data to disk, and logs operations with timestamps.

## Files

- `server.py`: the server.
- `kv_bench.py`: tests writes and reads and measures performance.
- `Dockerfile`: builds the Docker image and starts the server.
- `.dockerignore`: excludes local files from the Docker build context.
- `.gitignore`: excludes local files from GitHub.

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

## Run with Docker

Install and open Docker Desktop. Run these commands in the project folder.

Build the image:

```
docker build -t kv-store .
```

Start the container:

```
docker run -d --name kv-server -p 8000:8000 kv-store
```

The Dockerfile uses `python:3.12-alpine`, copies `server.py` into `/app`, exposes port 8000, and starts the server automatically. The server must listen on `0.0.0.0` inside the container. On your Mac, connect using `http://127.0.0.1:8000`.

Check the container and startup logs:

```
docker ps
docker logs kv-server
```

Stop the container:

```
docker stop kv-server
```

Start the same container again:

```
docker start kv-server
```

Because the container runs in the background with `-d`, Control+C in your terminal does not stop it.

After changing the server or Dockerfile, rebuild and replace the container:

```
docker stop kv-server
docker rm kv-server
docker build -t kv-store .
docker run -d --name kv-server -p 8000:8000 kv-store
```

Removing the container deletes data stored only inside it. Stopping and starting the same container keeps its files. To keep data when replacing a container, use a named volume when creating it:

```
docker run -d --name kv-server -p 8000:8000 -v kv-data:/app/data kv-store
```

Use this command instead of the normal run command, after removing any existing container named `kv-server`.

## Start the server without Docker

```
.venv/bin/python server.py --port 8000
```

Leave this terminal running. Connect at `http://127.0.0.1:8000`. Press Control+C to stop it. Run either the local server or the Docker server on port 8000, one at a time.

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

The benchmark uses 3 threads to write 300 keys, then reads all 300 keys and checks their values. Make sure `kv_bench.py` uses this base URL, because the server requires `/kv/` before each key:

```python
BASE_URL = "http://127.0.0.1:8000/kv"
```

The benchmark runs on your Mac and can test either the Docker server or the local server. Changing the benchmark does not require rebuilding the Docker image.

A successful run shows:

- SET: `ok=300 mismatch=0 error=0`
- GET: `ok=300 mismatch=0 error=0`
- TOTAL: 600 successful operations

It also reports throughput, average latency, and p99 latency. Performance numbers depend on your computer. The benchmark does not test deletion or conflicting writes to the same key.

One successful Docker test with 3 threads produced:

| Operation | Successful | Mismatches | Errors | Throughput |
|---|---:|---:|---:|---:|
| SET | 300 | 0 | 0 | 570.9 ops/s |
| GET | 300 | 0 | 0 | 1070.2 ops/s |

Total: 600 successful operations in 0.81 seconds. These results test writes and reads, not deletion or persistence.

## Check saved data after a restart

With the server running, write the keys:

```
.venv/bin/python kv_bench.py set
```

For the local server, stop it with Control+C, then restart it from the same folder:

```
.venv/bin/python server.py --port 8000
```

For Docker, restart the same container instead:

```
docker stop kv-server
docker start kv-server
```

Then read and check the saved keys:

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

For Docker, view the operation logs inside the container:

```
docker exec kv-server tail -n 30 /app/logs/operations.log
```

Without a volume, Docker data and logs are stored inside the container, separate from the folders on your Mac.

## Files to push to GitHub

Push `server.py`, `kv_bench.py`, `Dockerfile`, `.dockerignore`, `.gitignore`, and `README.md`.

Add these patterns to both `.gitignore` and `.dockerignore`:

```
.venv/
__pycache__/
*.pyc
.git/
.DS_Store
data/
logs/
```