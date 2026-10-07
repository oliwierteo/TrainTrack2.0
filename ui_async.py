"""ui_async.py - wykonywanie pracy blokującej poza wątkiem GUI.

Wzorzec ten sam, którego aplikacja używa od początku (threading.Thread +
self.after(0, ...)), tyle że w jednym miejscu i z obsługą wyjątków.
FIX: zapytania do Supabase i generowanie PDF wykonane na wątku głównym
Tkintera zamrażały całe okno (biały 'not responding') na czas sieci/renderu.
"""
import threading
import tkinter as tk
from logger import logger


def run_async(widget, work, on_success=None, on_error=None):
    """Uruchamia work() w wątku; callbacki ZAWSZE wracają na wątek GUI."""
    def _runner():
        try:
            result = work()
        except Exception as e:
            logger.error(f"run_async - blad zadania: {e}")
            if on_error:
                _marshal(widget, lambda: on_error(e))
            return
        if on_success:
            # BUG Z KONSOLI: "TypeError: _ok() takes 0 positional
            # arguments but 1 was given" - czynność (np. usunięcie
            # zawodnika) udawała się, ale UI nie odświeżało się wcale.
            # Wołamy zgodnie z sygnaturą callbacka, nie na ślepo.
            _marshal(widget, lambda: _call_flexible(on_success, result))

    threading.Thread(target=_runner, daemon=True).start()


def _call_flexible(fn, result):
    """Woła fn z wynikiem, a jeśli przyjmuje zero argumentów - bez niego."""
    try:
        return fn(result)
    except TypeError as e:
        if "positional argument" not in str(e) and "argument" not in str(e):
            raise
        return fn()


def _marshal(widget, fn):
    """Wraca na wątek główny Tkintera (bezpiecznie mimo zniszczonego okna)."""
    try:
        widget.after(0, fn)
    except Exception:
        try:
            fn()
        except Exception as e:
            logger.error(f"ui_async - callback nieudany: {e}")
