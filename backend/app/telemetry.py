from __future__ import annotations

from collections import deque
from datetime import datetime
from threading import Lock
from time import perf_counter, time

import psutil
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class RequestTelemetry:
    def __init__(self):
        self._lock = Lock()
        self._started = deque(maxlen=6000)
        self._latencies = deque(maxlen=6000)
        self._active = 0
        self._peak_concurrent = 0
        self._process = psutil.Process()

    def request_started(self):
        now = time()
        with self._lock:
            self._active += 1
            self._peak_concurrent = max(self._peak_concurrent, self._active)
            self._started.append(now)

    def request_finished(self, latency_ms: float):
        with self._lock:
            self._active = max(0, self._active - 1)
            self._latencies.append(latency_ms)

    def snapshot(self):
        now = time()
        with self._lock:
            starts = [stamp for stamp in self._started if now - stamp <= 60]
            latencies = sorted(self._latencies)
            active = self._active
            peak = self._peak_concurrent

        p95_index = max(0, int(len(latencies) * 0.95) - 1)
        memory = self._process.memory_info()
        return {
            "sampled_at": datetime.utcnow().isoformat(),
            "process_rss_mb": round(memory.rss / (1024 * 1024), 2),
            "process_vms_mb": round(memory.vms / (1024 * 1024), 2),
            "process_cpu_percent": self._process.cpu_percent(interval=None),
            "system_memory_percent": psutil.virtual_memory().percent,
            "active_requests": active,
            "peak_concurrent_requests": peak,
            "requests_last_minute": len(starts),
            "average_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
            "p95_latency_ms": round(latencies[p95_index], 2) if latencies else 0,
            "process_threads": self._process.num_threads(),
        }


request_telemetry = RequestTelemetry()


class RequestTelemetryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_telemetry.request_started()
        started = perf_counter()
        try:
            return await call_next(request)
        finally:
            request_telemetry.request_finished((perf_counter() - started) * 1000)
