"""
test_bez_deadlocku.py

Dowód, że poprawka pul wątków w cache_manager działa.

BEFORE (bug): preload i zapytania do bazy dzieliły jeden ThreadPoolExecutor
z 4 workerami. Job preloadu sam wywoływał _run_query() -> submit() na tej
samej puli i czekał na wynik. Przy 4 równoległych preloadach wszystkie
workery czekały na zadania, które nie mogły się już wykonać -> deadlock.

AFTER (fix): osobna pula dla zapytań -> preload czeka na workera, który
zawsze jest wolny.

Test: odpala 4x preload_parallel + 4x preload_finances + 8 zapytań
i mierzy, czy wszystko kończy się w rozsądnym czasie (przed: wisiałoby
w nieskończoność).
"""
import sys, os, time, threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cache_manager
from cache_manager import cache

# --- Podmiana Supabase na wolną atrapę -------------------------------------
QUERY_TIME = 0.05
calls = {"n": 0}
lock = threading.Lock()


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, table):
        self.table = table

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def gte(self, *a, **k):
        return self

    def lte(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def execute(self):
        time.sleep(QUERY_TIME)          # symulacja latencji sieci
        with lock:
            calls["n"] += 1
        return FakeResponse([])


class FakeSupabase:
    def table(self, name):
        return FakeQuery(name)


def get_fake_supabase():
    return FakeSupabase()


cache_manager.get_supabase = get_fake_supabase
cache_manager.get_database = lambda: type("DB", (), {
    "CURRENT_CLUB": "Chełmianka Gdańsk"})()

# --- Scenariusz --------------------------------------------------------------
print("Test: 4x preload_parallel + 4x preload_finances + 8 zapytań")
started = time.time()

threads = []
for _ in range(4):
    t = threading.Thread(target=cache.preload_parallel, daemon=True)
    t.start(); threads.append(t)
for _ in range(4):
    t = threading.Thread(target=cache.preload_finances, daemon=True)
    t.start(); threads.append(t)
for _ in range(8):
    def one():
        cache.get_players(force_refresh=True)
        cache.get_finances(2026, 3, force_refresh=True)
    t = threading.Thread(target=one, daemon=True)
    t.start(); threads.append(t)

DEADLINE = 30.0
for t in threads:
    t.join(timeout=DEADLINE)

alive = [t for t in threads if t.is_alive()]
elapsed = time.time() - started

if alive:
    print(f"❌ DEADLOCK: {len(alive)} wątków wciąż żyje po {DEADLINE}s")
    sys.exit(1)

print(f"✅ Brak deadlocku - wszystko zakończone w {elapsed:.2f}s")
print(f"   Wykonanych zapytań (atrapa): {calls['n']}")
print(f"   Ostatni błąd zapisany w cache: {cache.get_last_error()}")

# --- Drugi test: timeout zapytania nie zostawia zawieszonego stanu ----------
print("\nTest: timeout zapytania")


class SlowQuery(FakeQuery):
    def execute(self):
        time.sleep(30)          # dłuższy niż _query_timeout
        return FakeResponse([])


def get_slow_supabase():
    class S:
        def table(self, name):
            return SlowQuery(name)
    return S()


cache_manager.get_supabase = get_slow_supabase
t0 = time.time()
result = cache.get_players(force_refresh=True)
dt = time.time() - t0
print(f"   get_players -> {result} po {dt:.1f}s (limit: {cache._query_timeout}s)")
err = cache.get_last_error()
print(f"   błąd zapisany: {err}")
if result == [] and err:
    print("✅ Timeout obsłużony poprawnie - widok dostanie [], a błąd jest widoczny")
else:
    print("❌ Timeout nieobsłużony")
    sys.exit(1)

cache.shutdown()
print("\nGotowe.")