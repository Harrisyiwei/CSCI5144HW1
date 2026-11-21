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

## Coding Assignment 3

The router listens on port 8000 and forwards requests to the backend that owns each key. It uses SHA-256 and a consistent hash ring with 128 virtual nodes per backend. Each backend runs its own copy of `server.py` with a separate JSON snapshot and log.

### Run the system

From the project folder, install the benchmark dependency:

```sh
python -m pip install requests
```

Free port 8000 by stopping any earlier local server or Docker container using it. Start each backend command in its own terminal:

```sh
python server.py --host 127.0.0.1 --port 8001 --data data/hw3-3/store1.json --log logs/hw3-3/store1.log
python server.py --host 127.0.0.1 --port 8002 --data data/hw3-3/store2.json --log logs/hw3-3/store2.log
python server.py --host 127.0.0.1 --port 8003 --data data/hw3-3/store3.json --log logs/hw3-3/store3.log
```

Once the backends are listening, start the router in a separate terminal:

```sh
python router.py --backends 8001 8002 8003
```

### Benchmark one, two, and three backends

Start only the backend ports listed for each run. In both paths in each server command, replace `hw3-3` with the directory for that run. Use fresh snapshot files for each configuration.

| Backends | Server ports | Run directory | Router command |
|---:|---|---|---|
| 1 | 8001 | `hw3-1` | `python router.py --backends 8001` |
| 2 | 8001, 8002 | `hw3-2` | `python router.py --backends 8001 8002` |
| 3 | 8001, 8002, 8003 | `hw3-3` | `python router.py --backends 8001 8002 8003` |

With the router and backends running, run `python kv_bench.py` in a separate terminal. It uses three client threads to write 300 keys and verify all 300 values. Both phases should report `ok=300 mismatch=0 error=0`. Stop the router and backends with Ctrl+C before switching configurations.

| Backends | PUT (ops/s) | GET (ops/s) | Overall (ops/s) |
|---:|---:|---:|---:|
| 1 | 97.2 | 217.2 | 134.3 |
| 2 | 119.9 | 229.2 | 157.4 |
| 3 | 147.3 | 271.0 | 190.9 |

In the three-backend run, ports 8001, 8002, and 8003 stored 104, 90, and 106 keys, respectively.

### Test a planned change from two backends to three

1. Run the two-backend configuration with `data/hw3-2/store1.json` and `data/hw3-2/store2.json`. Run `python kv_bench.py set` to write the keys.
2. Start a third backend with a fresh snapshot path:

   ```sh
   python server.py --host 127.0.0.1 --port 8003 --data data/hw3-migration/store3.json --log logs/hw3-migration/store3.log
   ```

3. Stop the router and keep the three backends running. Pause any direct writes to the backends, then run:

   ```sh
   python rebalance.py --old 8001 8002 --new 8001 8002 8003 --snapshot 8001=data/hw3-2/store1.json 8002=data/hw3-2/store2.json 8003=data/hw3-migration/store3.json
   ```

4. After `Rebalance complete` appears, restart the router with `python router.py --backends 8001 8002 8003`.
5. Run `python kv_bench.py get`. Expect `GET: ok=300 mismatch=0 error=0`. This checks the values written before the change.

The router is briefly unavailable during planned migration. Recovering values after an unexpected backend failure would require a replica or backup.



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
