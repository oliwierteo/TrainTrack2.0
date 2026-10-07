"""test_deadlock_dowod_stara_architektura.py

Dowód, że BUG BYŁ REALNY: w STAREJ architekturze (jedna pula wątków)
cztery jednoczesne preloady potrafiły zawiesić aplikację na stałe.
Test ma celowo pokazać awarię - po uruchomieniu zwróci 0/4 i wyjdzie.

Uruchomienie:  python3 test_deadlock_dowod_stara_architektura.py
Poprawna wersja: python3 test_bez_deadlocku.py  (0,16 s, bez zawieszeń)
"""
import threading, time
from concurrent.futures import ThreadPoolExecutor

done = {"n": 0}
guard = threading.Lock()
pool = ThreadPoolExecutor(max_workers=4)   # STARA architektura
gate = threading.Barrier(4, timeout=20)   # wymusza równoczesne wejście 4 preloadów

def query():
    time.sleep(0.05)
    return []

def preload():
    gate.wait()                          # wszyscy 4 workerzy są teraz ZAJĘCI
    fut = pool.submit(query)             # a ich zapytania czekają w kolejce
    fut.result(timeout=15)               # do tej samej puli -> nigdy nie wykonają się
    with guard:
        done["n"] += 1

ts = [threading.Thread(target=lambda: pool.submit(preload), daemon=True) for _ in range(4)]
for t in ts: t.start()
time.sleep(10)
print(f"Po 10s: ukończonych preloadów {done['n']}/4")
print("❌ DEADLOCK POTWIERDZONY - aplikacja by wisiała w nieskończoność"
      if done["n"] == 0 else "brak deadlocku")
