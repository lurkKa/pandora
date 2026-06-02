#!/usr/bin/env python3
"""
PANDORA Load Test Suite
=======================
Simulates 5-8 concurrent users hitting the most common endpoints
to identify what causes health-check timeouts and crashes on Render (free tier).

Tests:
1. Health check (/ping) under load — should NEVER fail
2. /api/tasks — the 43MB JSON bomb
3. /api/auth/login — bcrypt blocking
4. /api/tasks/attempt — subprocess runner blocking
5. Mixed concurrent traffic — realistic 5-8 user simulation
6. Memory pressure from large JSON serialization

Usage:
    # Start server first: uvicorn main:app --host 0.0.0.0 --port 8765 --workers 1
    python scripts/load_test.py
"""

import asyncio
import time
import statistics
import sys
import os
import json
import traceback
from dataclasses import dataclass, field

# We use httpx (already in requirements.txt)
try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)


BASE_URL = os.getenv("PANDORA_TEST_URL", "http://127.0.0.1:8765")
# We'll create a test user during setup
TEST_USER = "loadtest_user"
TEST_PASS = "loadtest_pass_123"
TEST_DISPLAY = "Load Tester"
ADMIN_USER = os.getenv("PANDORA_TEST_ADMIN", "admin")
ADMIN_PASS = os.getenv("PANDORA_TEST_ADMIN_PASS", "admin123")

# Timeouts matching Render's health check
HEALTH_CHECK_TIMEOUT = 5.0  # Render kills instance if /ping > 5s
REQUEST_TIMEOUT = 30.0


@dataclass
class TestResult:
    name: str
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    timeouts: int = 0
    latencies_ms: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    response_sizes: list = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration_s(self):
        return self.end_time - self.start_time

    @property
    def rps(self):
        d = self.duration_s
        return self.total_requests / d if d > 0 else 0

    @property
    def p50(self):
        return statistics.median(self.latencies_ms) if self.latencies_ms else 0

    @property
    def p95(self):
        if not self.latencies_ms:
            return 0
        sorted_l = sorted(self.latencies_ms)
        idx = int(len(sorted_l) * 0.95)
        return sorted_l[min(idx, len(sorted_l) - 1)]

    @property
    def p99(self):
        if not self.latencies_ms:
            return 0
        sorted_l = sorted(self.latencies_ms)
        idx = int(len(sorted_l) * 0.99)
        return sorted_l[min(idx, len(sorted_l) - 1)]

    @property
    def max_ms(self):
        return max(self.latencies_ms) if self.latencies_ms else 0

    @property
    def avg_response_kb(self):
        return statistics.mean(self.response_sizes) / 1024 if self.response_sizes else 0

    def summary(self):
        lines = [
            f"\n{'='*60}",
            f"  TEST: {self.name}",
            f"{'='*60}",
            f"  Requests:    {self.total_requests} ({self.successful} ok, {self.failed} fail, {self.timeouts} timeout)",
            f"  Duration:    {self.duration_s:.2f}s  |  RPS: {self.rps:.1f}",
            f"  Latency:     p50={self.p50:.0f}ms  p95={self.p95:.0f}ms  p99={self.p99:.0f}ms  max={self.max_ms:.0f}ms",
        ]
        if self.response_sizes:
            lines.append(f"  Resp. size:  avg={self.avg_response_kb:.1f} KB")
        if self.timeouts > 0:
            lines.append(f"  ⚠️  TIMEOUTS: {self.timeouts} — this KILLS the Render instance!")
        if self.errors:
            unique_errors = list(set(self.errors[:5]))
            lines.append(f"  Errors:      {unique_errors}")
        # Verdict
        if self.p95 > 5000:
            lines.append(f"  🔴 CRITICAL: p95 > 5s — health checks WILL fail under this load")
        elif self.p95 > 2000:
            lines.append(f"  🟡 WARNING: p95 > 2s — health checks at risk under concurrent load")
        elif self.p95 > 500:
            lines.append(f"  🟠 SLOW: p95 > 500ms — noticeable user lag")
        else:
            lines.append(f"  🟢 OK: p95 < 500ms")
        return "\n".join(lines)


async def timed_request(client: httpx.AsyncClient, method: str, url: str,
                        result: TestResult, timeout: float = REQUEST_TIMEOUT, **kwargs):
    """Execute a single request and record metrics."""
    result.total_requests += 1
    t0 = time.monotonic()
    try:
        resp = await client.request(method, url, timeout=timeout, **kwargs)
        latency = (time.monotonic() - t0) * 1000
        result.latencies_ms.append(latency)
        result.response_sizes.append(len(resp.content))
        if resp.status_code < 400:
            result.successful += 1
        else:
            result.failed += 1
            result.errors.append(f"HTTP {resp.status_code}: {resp.text[:100]}")
        return resp
    except httpx.TimeoutException:
        latency = (time.monotonic() - t0) * 1000
        result.latencies_ms.append(latency)
        result.timeouts += 1
        result.errors.append(f"TIMEOUT after {latency:.0f}ms")
        return None
    except Exception as e:
        latency = (time.monotonic() - t0) * 1000
        result.latencies_ms.append(latency)
        result.failed += 1
        result.errors.append(f"{type(e).__name__}: {str(e)[:80]}")
        return None


# ─────────────────────────────────────────────────────────────
# TEST 1: Health check baseline — must respond < 100ms always
# ─────────────────────────────────────────────────────────────

async def test_health_check_baseline():
    """Ping 50 times sequentially — baseline latency."""
    result = TestResult("1. /ping baseline (sequential)")
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        result.start_time = time.monotonic()
        for _ in range(50):
            await timed_request(client, "GET", "/ping", result, timeout=HEALTH_CHECK_TIMEOUT)
        result.end_time = time.monotonic()
    return result


# ─────────────────────────────────────────────────────────────
# TEST 2: /api/tasks — the 43MB JSON monster
# ─────────────────────────────────────────────────────────────

async def test_tasks_endpoint():
    """Hit /api/tasks 5 times — each response is ~43MB JSON."""
    result = TestResult("2. /api/tasks (43MB JSON, 5 requests)")
    # Need auth token
    token = await get_test_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        result.start_time = time.monotonic()
        for _ in range(5):
            await timed_request(client, "GET", "/api/tasks", result,
                               timeout=60.0, headers=headers)
        result.end_time = time.monotonic()
    return result


# ─────────────────────────────────────────────────────────────
# TEST 3: /api/tasks concurrent — what happens when 5 users
#          all load the task list at the same time?
# ─────────────────────────────────────────────────────────────

async def test_tasks_concurrent():
    """5 concurrent /api/tasks requests — simulates 5 users opening the app."""
    result = TestResult("3. /api/tasks CONCURRENT (5 users loading simultaneously)")
    token = await get_test_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        result.start_time = time.monotonic()
        tasks = [
            timed_request(client, "GET", "/api/tasks", result,
                          timeout=60.0, headers=headers)
            for _ in range(5)
        ]
        await asyncio.gather(*tasks)
        result.end_time = time.monotonic()
    return result


# ─────────────────────────────────────────────────────────────
# TEST 4: /ping DURING heavy /api/tasks — the kill scenario
# ─────────────────────────────────────────────────────────────

async def test_ping_during_heavy_load():
    """
    Simulate the EXACT crash scenario:
    - 3 users loading /api/tasks concurrently
    - While Render's health check hits /ping
    - If /ping takes > 5s -> instance killed
    """
    result_ping = TestResult("4a. /ping DURING heavy load")
    result_tasks = TestResult("4b. /api/tasks (background load)")
    token = await get_test_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    async def heavy_task_load(client):
        for _ in range(3):
            await timed_request(client, "GET", "/api/tasks", result_tasks,
                                timeout=60.0, headers=headers)

    async def health_check_probe(client):
        # Wait a tiny bit for tasks to start loading, then hammer /ping
        await asyncio.sleep(0.1)
        for _ in range(20):
            await timed_request(client, "GET", "/ping", result_ping,
                                timeout=HEALTH_CHECK_TIMEOUT)
            await asyncio.sleep(0.2)

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        result_ping.start_time = time.monotonic()
        result_tasks.start_time = time.monotonic()
        await asyncio.gather(
            heavy_task_load(client),
            heavy_task_load(client),
            heavy_task_load(client),
            health_check_probe(client),
        )
        result_ping.end_time = time.monotonic()
        result_tasks.end_time = time.monotonic()

    return result_ping, result_tasks


# ─────────────────────────────────────────────────────────────
# TEST 5: Login storm — bcrypt is CPU-heavy, blocks event loop
# ─────────────────────────────────────────────────────────────

async def test_login_storm():
    """5 concurrent login attempts — bcrypt blocks the single worker."""
    result = TestResult("5. Login storm (5 concurrent bcrypt verifications)")
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        result.start_time = time.monotonic()
        tasks = []
        for i in range(5):
            tasks.append(
                timed_request(client, "POST", "/api/auth/login", result,
                              timeout=REQUEST_TIMEOUT,
                              json={"username": f"fake_user_{i}", "password": "wrong_pass"})
            )
        await asyncio.gather(*tasks)
        result.end_time = time.monotonic()
    return result


# ─────────────────────────────────────────────────────────────
# TEST 6: Mixed realistic traffic — 8 users doing different things
# ─────────────────────────────────────────────────────────────

async def test_mixed_traffic_8_users():
    """
    Simulate 8 concurrent users:
    - 3 loading /api/tasks (page open)
    - 2 hitting /api/auth/login
    - 2 hitting /api/status + /ping
    - 1 hitting / (index.html, 492KB)
    Plus periodic health checks from Render.
    """
    result = TestResult("6. Mixed traffic (8 users + health checks)")
    token = await get_test_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    async def user_load_tasks(client, n):
        for _ in range(n):
            await timed_request(client, "GET", "/api/tasks", result,
                                timeout=60.0, headers=headers)
            await asyncio.sleep(0.5)

    async def user_login(client, n):
        for i in range(n):
            await timed_request(client, "POST", "/api/auth/login", result,
                                timeout=REQUEST_TIMEOUT,
                                json={"username": f"user_{i}", "password": "test123"})
            await asyncio.sleep(0.3)

    async def user_browse(client, n):
        for _ in range(n):
            await timed_request(client, "GET", "/api/status", result, timeout=10.0)
            await asyncio.sleep(0.2)
            await timed_request(client, "GET", "/", result, timeout=10.0)
            await asyncio.sleep(0.5)

    async def render_health_check(client):
        for _ in range(15):
            await timed_request(client, "GET", "/ping", result,
                                timeout=HEALTH_CHECK_TIMEOUT)
            await asyncio.sleep(1.0)

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        result.start_time = time.monotonic()
        await asyncio.gather(
            user_load_tasks(client, 2),   # user 1
            user_load_tasks(client, 2),   # user 2
            user_load_tasks(client, 2),   # user 3
            user_login(client, 3),        # user 4
            user_login(client, 3),        # user 5
            user_browse(client, 3),       # user 6
            user_browse(client, 3),       # user 7
            user_browse(client, 3),       # user 8
            render_health_check(client),  # Render probe
        )
        result.end_time = time.monotonic()
    return result


# ─────────────────────────────────────────────────────────────
# TEST 7: Sustained /ping while 5 users hit /api/tasks in a loop
# ─────────────────────────────────────────────────────────────

async def test_sustained_health_under_load():
    """
    The exact Render failure mode:
    5 users continuously loading tasks for 15 seconds,
    while health checks run every second.
    Counts how many health checks fail the 5s threshold.
    """
    result_health = TestResult("7. SUSTAINED health check under 5-user task load (15s)")
    duration = 15  # seconds

    token = await get_test_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    stop_event = asyncio.Event()

    async def user_loop(client):
        while not stop_event.is_set():
            try:
                r = await client.get("/api/tasks", timeout=60.0, headers=headers)
            except Exception:
                pass
            await asyncio.sleep(0.1)

    async def health_loop(client):
        while not stop_event.is_set():
            t0 = time.monotonic()
            try:
                r = await client.get("/ping", timeout=HEALTH_CHECK_TIMEOUT)
                latency = (time.monotonic() - t0) * 1000
                result_health.total_requests += 1
                result_health.latencies_ms.append(latency)
                if r.status_code == 200:
                    result_health.successful += 1
                else:
                    result_health.failed += 1
            except httpx.TimeoutException:
                latency = (time.monotonic() - t0) * 1000
                result_health.total_requests += 1
                result_health.latencies_ms.append(latency)
                result_health.timeouts += 1
                result_health.errors.append(f"HEALTH CHECK TIMEOUT at {latency:.0f}ms — INSTANCE WOULD BE KILLED")
            except Exception as e:
                result_health.total_requests += 1
                result_health.failed += 1
                result_health.errors.append(str(e)[:80])
            await asyncio.sleep(1.0)

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        result_health.start_time = time.monotonic()

        user_tasks = [asyncio.create_task(user_loop(client)) for _ in range(5)]
        health_task = asyncio.create_task(health_loop(client))

        await asyncio.sleep(duration)
        stop_event.set()

        # Give tasks time to finish
        for t in user_tasks:
            t.cancel()
        health_task.cancel()
        await asyncio.sleep(0.5)

        result_health.end_time = time.monotonic()

    return result_health


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

_cached_token = None

async def get_test_token():
    """Get a valid auth token (try test user, fallback to admin)."""
    global _cached_token
    if _cached_token:
        return _cached_token

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        # Try registering test user
        try:
            resp = await client.post("/api/auth/register", json={
                "username": TEST_USER, "password": TEST_PASS, "display_name": TEST_DISPLAY
            })
            if resp.status_code == 200:
                data = resp.json()
                _cached_token = data.get("token")
                if _cached_token:
                    return _cached_token
        except Exception:
            pass

        # Try logging in as test user
        try:
            resp = await client.post("/api/auth/login", json={
                "username": TEST_USER, "password": TEST_PASS
            })
            if resp.status_code == 200:
                data = resp.json()
                _cached_token = data.get("token")
                if _cached_token:
                    return _cached_token
        except Exception:
            pass

        # Try admin
        try:
            resp = await client.post("/api/auth/login", json={
                "username": ADMIN_USER, "password": ADMIN_PASS
            })
            if resp.status_code == 200:
                data = resp.json()
                _cached_token = data.get("token")
                if _cached_token:
                    return _cached_token
        except Exception:
            pass

    print("  ⚠️  Could not get auth token — some tests may return 401")
    return None


async def check_server():
    """Verify server is running."""
    try:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
            r = await client.get("/ping")
            if r.status_code == 200:
                return True
    except Exception:
        pass
    return False


async def main():
    print("\n" + "█" * 60)
    print("  PANDORA LOAD TEST SUITE")
    print("  Target:", BASE_URL)
    print("█" * 60)

    if not await check_server():
        print(f"\n❌ Server not reachable at {BASE_URL}")
        print(f"   Start it first: uvicorn main:app --host 0.0.0.0 --port 8765 --workers 1")
        sys.exit(1)

    print("\n✅ Server is running. Starting tests...\n")

    all_results = []

    # Test 1: Health check baseline
    print("▶ Running Test 1: /ping baseline...")
    r = await test_health_check_baseline()
    print(r.summary())
    all_results.append(r)

    # Test 2: /api/tasks sequential
    print("\n▶ Running Test 2: /api/tasks sequential...")
    r = await test_tasks_endpoint()
    print(r.summary())
    all_results.append(r)

    # Test 3: /api/tasks concurrent
    print("\n▶ Running Test 3: /api/tasks concurrent...")
    r = await test_tasks_concurrent()
    print(r.summary())
    all_results.append(r)

    # Test 4: /ping during heavy load
    print("\n▶ Running Test 4: /ping DURING heavy /api/tasks load...")
    r_ping, r_tasks = await test_ping_during_heavy_load()
    print(r_ping.summary())
    print(r_tasks.summary())
    all_results.extend([r_ping, r_tasks])

    # Test 5: Login storm
    print("\n▶ Running Test 5: Login storm...")
    r = await test_login_storm()
    print(r.summary())
    all_results.append(r)

    # Test 6: Mixed traffic
    print("\n▶ Running Test 6: Mixed realistic traffic (8 users)...")
    r = await test_mixed_traffic_8_users()
    print(r.summary())
    all_results.append(r)

    # Test 7: Sustained health under load
    print("\n▶ Running Test 7: Sustained health check under 5-user load (15s)...")
    r = await test_sustained_health_under_load()
    print(r.summary())
    all_results.append(r)

    # ─── FINAL DIAGNOSIS ───
    print("\n\n" + "█" * 60)
    print("  DIAGNOSIS SUMMARY")
    print("█" * 60)

    critical = []
    warnings = []

    for r in all_results:
        if r.timeouts > 0:
            critical.append(f"❌ {r.name}: {r.timeouts} timeouts!")
        if r.p95 > 5000:
            critical.append(f"❌ {r.name}: p95={r.p95:.0f}ms (>5s health threshold)")
        elif r.p95 > 2000:
            warnings.append(f"⚠️  {r.name}: p95={r.p95:.0f}ms (risky)")
        if r.avg_response_kb > 10000:  # > 10MB
            critical.append(f"❌ {r.name}: avg response={r.avg_response_kb/1024:.1f}MB — memory bomb!")

    if critical:
        print("\n🔴 CRITICAL ISSUES (will crash on Render):")
        for c in critical:
            print(f"  {c}")

    if warnings:
        print("\n🟡 WARNINGS:")
        for w in warnings:
            print(f"  {w}")

    if not critical and not warnings:
        print("\n🟢 All tests passed within acceptable limits.")

    print("\n" + "─" * 60)
    print("  LIKELY ROOT CAUSES FOR RENDER CRASHES:")
    print("─" * 60)

    # Check specific findings
    tasks_results = [r for r in all_results if "/api/tasks" in r.name and r.avg_response_kb > 1000]
    if tasks_results:
        mb = tasks_results[0].avg_response_kb / 1024
        print(f"""
  1. 📦 /api/tasks returns {mb:.0f}MB per request
     → 5 users × {mb:.0f}MB = {5*mb:.0f}MB simultaneous memory
     → Render free tier has 512MB RAM → OOM kill
     → FIX: Paginate /api/tasks or return only IDs+titles first

  2. 🧵 Single uvicorn worker (--workers 1)
     → Serializing {mb:.0f}MB JSON blocks the entire event loop
     → While blocked, /ping cannot respond → health check fails
     → FIX: Use StreamingResponse or reduce payload size

  3. 🔐 bcrypt.checkpw() is synchronous CPU-bound (~100-300ms)
     → Blocks the event loop during login
     → 5 concurrent logins = 500-1500ms of event-loop stall
     → FIX: Run bcrypt in thread pool (run_in_executor)
""")

    print("═" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
