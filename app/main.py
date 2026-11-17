import asyncio
import math
import time

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

app = FastAPI(title="PCRMS Demo App")

REQUESTS = Counter("app_requests_total", "Total HTTP requests", ["endpoint", "status"])
LATENCY = Histogram("app_request_latency_seconds", "Request latency in seconds", ["endpoint"])


@app.middleware("http")
async def track_metrics(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    endpoint = route.path if route else "unmatched"
    LATENCY.labels(endpoint).observe(time.perf_counter() - start)
    REQUESTS.labels(endpoint, str(response.status_code)).inc()
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/cpu")
def cpu(iterations: int = 200000):
    iterations = min(max(iterations, 1), 5_000_000)
    total = 0.0
    for i in range(1, iterations + 1):
        total += math.sqrt(i)
    return {"iterations": iterations, "result": round(total, 2)}


@app.get("/memory")
def memory(mb: int = 10, hold_ms: int = 100):
    mb = min(max(mb, 1), 200)
    hold_ms = min(max(hold_ms, 0), 2000)
    block = bytearray(mb * 1024 * 1024)
    for i in range(0, len(block), 4096):
        block[i] = 1
    time.sleep(hold_ms / 1000)
    return {"allocated_mb": mb, "held_ms": hold_ms}


@app.get("/io")
async def io(delay_ms: int = 50):
    delay_ms = min(max(delay_ms, 0), 2000)
    await asyncio.sleep(delay_ms / 1000)
    return {"delay_ms": delay_ms}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
