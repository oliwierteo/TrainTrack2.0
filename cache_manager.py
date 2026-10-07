import json
import os
import sys
import time
import threading
import gzip
import hashlib
import platform
import shutil
import random
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from logger import logger
import teams

# Lazy imports wewnątrz funkcji, aby uniknąć circular dependencies
_supabase = None
_database = None

def get_supabase():
    global _supabase
    if _supabase is None:
        from database import supabase
        _supabase = supabase
    return _supabase

def get_database():
    global _database
    if _database is None:
        import database
        _database = database
    return _database


# teams.py nie importuje cache_manager na poziomie modułu (tylko wewnątrz
# funkcji), więc ten import jest bezpieczny.


# Sentinel: 'w cache nie ma świeżej wartości' (inne niż None/[]/{})
_MISS = object()


class CacheManager:
    """
    ULTRA CACHE MANAGER v5.0 (FINAL)
    - Thread-safe & Process-safe (Windows fix)
    - Obsługa wszystkich modułów aplikacji
    - Inteligentne odświeżanie
    """
    
    def __init__(self):
        self.cache = {}
        self.timestamps = {}
        self.ttl = 600  # 10 minut w pamięci
        
        # Zabezpieczenia wątków
        self._lock = threading.RLock()

        # FIX: DWIE OSOBNE PULE WĄTKÓW.
        # Wcześniej preload i zapytania do bazy dzieliły jeden executor, a job
        # preloadu sam wołał _run_query() -> submit() na tej samej puli.
        # Gdy 4 takie joby zajmą 4 workery, wszystkie czekają na zapytania,
        # które nigdy nie dostaną się do wykonania -> deadlock (apka wisi).
        self._executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="CachePreload")
        self._query_executor = ThreadPoolExecutor(
            max_workers=8, thread_name_prefix="CacheQuery")
        self._query_timeout = 15  # Sekundy

        # Ostatni błąd połączenia (pokazywany zamiast cichych pustych list)
        self.last_error = None
        self.last_error_time = 0.0
        
        # Mechanizm zapisu (Debounce)
        self._save_timer = None
        self._save_delay = 5.0  # Czekaj 2s przed zapisem na dysk
        
        # Ścieżki
        self.cache_dir = self._get_cache_dir()
        self.cache_file = os.path.join(self.cache_dir, "data_cache.json.gz")
        
        # Start
        self._load_from_disk_safe()

    def _get_cache_dir(self):
        """Uniwersalna ścieżka cache (Windows/macOS)"""
        try:
            if platform.system() == "Darwin":
                base = os.path.expanduser("~/Library/Caches/TrainTrack")
            elif platform.system() == "Windows":
                base = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'TrainTrack', 'cache')
            else:
                base = os.path.expanduser("~/.cache/TrainTrack")
            
            os.makedirs(base, exist_ok=True)
            return base
        except Exception as e:
            logger.error(f"❌ Błąd tworzenia folderu cache: {e}")
            import tempfile
            return tempfile.gettempdir()

    # =============================================
    # I/O DISK OPERATIONS (WINDOWS SAFE)
    # =============================================

    def _load_from_disk_safe(self):
        """Wczytuje cache przy starcie"""
        if not os.path.exists(self.cache_file):
            return

        try:
            # Ignoruj pliki starsze niż 24h
            if time.time() - os.path.getmtime(self.cache_file) > 86400:
                return

            with self._lock:
                with gzip.open(self.cache_file, 'rt', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cache = data.get('cache', {})
                    self.timestamps = data.get('timestamps', {})
            
            logger.info(f"💾 Cache załadowany: {len(self.cache)} elementów")
        except Exception as e:
            logger.error(f"⚠️ Błąd odczytu cache: {e}")
            self.cache = {}

    def _schedule_save(self):
        """Planuje zapis za 2 sekundy (resetuje timer jeśli nowa zmiana)"""
        if self._save_timer:
            self._save_timer.cancel()
        
        self._save_timer = threading.Timer(self._save_delay, self._do_save_disk)
        self._save_timer.start()

    def _do_save_disk(self):
        """Faktyczny zapis na dysk z obsługą błędów Windows"""
        try:
            with self._lock:
                data = {
                    'cache': self.cache.copy(),
                    'timestamps': self.timestamps.copy()
                }
            
            # Unikalna nazwa tymczasowa
            temp_file = f"{self.cache_file}.{os.getpid()}.{random.randint(1000,9999)}.tmp"
            
            # 1. Zapisz do tmp
            with gzip.open(temp_file, 'wt', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            
            # 2. Bezpieczna podmiana.
            # FIX: os.replace() jest ATOMOWY na Windowsie i POSIXie - nie ma
            # już okna, w którym plik cache nie istnieje (wcześniejsze
            # remove() + move() gubiło cache przy awarii w trakcie zapisu).
            max_retries = 3
            for i in range(max_retries):
                try:
                    os.replace(temp_file, self.cache_file)
                    break
                except (PermissionError, OSError) as e:
                    if i == max_retries - 1:
                        logger.error(
                            f"❌ Nie udało się zapisać cache (plik zablokowany): {e}")
                    else:
                        time.sleep(0.2 * (i + 1))
            
            # Sprzątanie w razie błędu
            if os.path.exists(temp_file):
                try: os.remove(temp_file)
                except: pass
                
        except Exception as e:
            logger.error(f"❌ Błąd zapisu cache: {e}")

    # =============================================
    # CORE LOGIC
    # =============================================

    def _is_valid(self, key):
        with self._lock:
            return key in self.cache and \
                   key in self.timestamps and \
                   (time.time() - self.timestamps[key]) < self.ttl

    def _read_cache(self, key, default=None):
        """
        Atomowy odczyt cache: sprawdza TTL i zwraca wartość w JEDNEJ operacji.

        FIX: wcześniej kod robił  _is_valid(key) -> self.cache[key]  w dwóch
        krokach. W międzyczasie inny wątek (monitor aktywności co 60 s albo
        zmiana sezonu) mógł zdjąć klucz przez invalidate() -> KeyError
        i crash widoku. Teraz operacja jest niepodzielna.
        """
        with self._lock:
            ts = self.timestamps.get(key)
            if key in self.cache and ts is not None and (time.time() - ts) < self.ttl:
                value = self.cache.get(key)
                if value is not None:
                    return value
            return _MISS

    def _get_cached(self, key, default=None):
        """Bezpieczny odczyt cache (bez wyjątku po równoległym invalidate)."""
        with self._lock:
            value = self.cache.get(key)
        return default if value is None else value

    def _record_error(self, message):
        with self._lock:
            self.last_error = str(message)
            self.last_error_time = time.time()

    def _record_success(self):
        with self._lock:
            self.last_error = None
            self.last_error_time = 0.0

    def get_last_error(self, max_age=180):
        """
        Ostatni błąd sieciowy (jeśli był niedawno). Dzięki temu widok może
        pokazać 'Brak połączenia' zamiast pustej listy.
        """
        with self._lock:
            if not self.last_error:
                return None
            if time.time() - self.last_error_time > max_age:
                self.last_error = None
                return None
            return self.last_error

    def _set(self, key, data):
        with self._lock:
            self.cache[key] = data
            self.timestamps[key] = time.time()
        self._schedule_save()

    def _get_club(self):
        try:
            return get_database().CURRENT_CLUB
        except Exception:
            return "default"

    def _scope(self, code=None):
        """
        Klucz cache = 'Klub|KodDrużyny'.

        BEZ tego przełącznik drużyny pokazywałby dane poprzedniej drużyny
        przez 10 minut (TTL) - błąd klasy 'cichych pustych list'.
        """
        try:
            return teams.scope_keys(self._get_club(), code)
        except Exception:
            return f"{self._get_club()}|*"

    def _team_filter(self, query, table="events", column="team_code"):
        """Dokłada warunek aktywnej drużyny do zapytania."""
        try:
            return teams.team_filter(query, table, column)
        except Exception:
            return query

    def _run_query(self, func, label="zapytanie"):
        """Uruchamia zapytanie w wątku z timeoutem (osobna pula!)."""
        try:
            future = self._query_executor.submit(func)
        except RuntimeError:
            return None  # Executor zamknięty (aplikacja się zamyka)
        try:
            result = future.result(timeout=self._query_timeout)
        except FuturesTimeout:
            self._record_error(f"Timeout serwera ({self._query_timeout}s) - {label}")
            logger.error(f"⏱️ Timeout zapytania do bazy: {label}")
            return None
        except Exception as e:
            self._record_error(e)
            logger.error(f"❌ Błąd SQL ({label}): {e}")
            return None
        self._record_success()
        return result

    # =============================================
    # POBIERANIE DANYCH (API)
    # =============================================

    # --- GRACZE ---
    def get_players(self, force_refresh=False, team=None):
        """
        Kadrę AKTYWNEJ DRUŻYNY (przez player_team_terms).
        Przy '*' - całą kadrę klubu.

        UWAGA: pusta drużyna = pusta lista. Wcześniej warunek 'nie ma
        nikogo' wywoływał powrót do CAŁEJ kadry klubu, więc drużyna II
        bez graczy pokazywała wszystkich zawodników drużyny I.
        Awaryjnie (cały klub) wracamy tylko wtedy, gdy w bazie nie ma
        W OGÓLE żadnego terminu kadry, czyli migracja nie została wykonana.
        """
        club = self._get_club()
        key = f"players_{self._scope(team)}"
        cached = self._read_cache(key)
        if not force_refresh and cached is not _MISS:
            return cached

        def q():
            code = team if team is not None else teams.get_current_team()
            if code != teams.ALL_TEAMS:
                ids = teams.get_team_player_ids(code, force_refresh=True)
                if ids:
                    return (get_supabase().table('players').select("*")
                            .in_('id', list(ids)).execute().data) or []
                if teams.has_any_terms(force_refresh=True):
                    return []          # drużyna jest pusta - i koniec
            if code == teams.ALL_TEAMS:
                return (get_supabase().table('players').select("*")
                        .eq('club_name', club).execute().data) or []
            # Awaria walidna TYLKO dla bazy bez migracji (brak terminów
            # w ogóle). Gdyby kiedyś wróciła dla pustej drużyny, pokazalibyśmy
            # CAŁY klub - dlatego zostawiamy ślad w logu.
            logger.warning(
                "Kadra: brak terminów w bazie, pokazuję CAŁY KLUB "
                "(team=%s). Jeśli widzisz tu zawodników spoza drużyny - "
                "zgłoś to.", code)
            return (get_supabase().table('players').select("*")
                    .eq('club_name', club).execute().data) or []

        data = self._run_query(q, label=key)
        if data is not None: self._set(key, data); return data
        return self._get_cached(key, [])
    def get_all_players(self, force_refresh=False): # Dla scoutingu (klub)
        key = "all_players"
        cached = self._read_cache(key)
        if not force_refresh and cached is not _MISS:
            return cached
        
        def q(): return get_supabase().table('players').select("*").execute().data
        data = self._run_query(q, label=key)
        if data is not None: self._set(key, data); return data
        return self._get_cached(key, [])
    # --- FINANSE ---
    def get_finances(self, year=None, month=None, force_refresh=False):
        club = self._get_club()
        key = f"finances_{self._scope()}_{year}_{month}"
        cached = self._read_cache(key)
        if not force_refresh and cached is not _MISS:
            return cached
        
        def q():
            query = get_supabase().table('finances').select("*").eq('club_name', club)
            if year: query = query.eq('year', year)
            if month: query = query.eq('month', month)
            # FINanse są HYBRYDOWE: wpłata należy do gracza (jedna składka),
            # ale jest PRZYPISANA do drużyny, w której wtedy grał.
            return self._team_filter(query, 'finances').execute().data
        
        data = self._run_query(q, label=key)
        if data is not None: self._set(key, data); return data
        return self._get_cached(key, [])
    def get_all_finances(self, force_refresh=False): # Dla historii zaległości
        club = self._get_club()
        key = f"all_finances_{self._scope()}"
        cached = self._read_cache(key)
        if not force_refresh and cached is not _MISS:
            return cached
        
        def q():
            query = get_supabase().table('finances').select("*").eq('club_name', club)
            return self._team_filter(query, 'finances').execute().data
        data = self._run_query(q, label=key)
        if data is not None: self._set(key, data); return data
        return self._get_cached(key, [])
    def get_all_finances_club(self, force_refresh=False):
        """
        WSZYSTKIE wpłaty w klubie - bez filtru drużyny.

        Potrzebne do logiki 'czy gracz zapłacił': składka jest JEDNA na
        gracza, więc wpłata zapisana w akademii musi zamykać miesiąc
        także w widoku drużyny I (hybryda).
        """
        club = self._get_club()
        key = f"all_finances_CLUB::{club}"
        cached = self._read_cache(key)
        if not force_refresh and cached is not _MISS:
            return cached

        def q():
            return (get_supabase().table('finances').select("*")
                    .eq('club_name', club).execute().data)

        data = self._run_query(q, label=key)
        if data is not None: self._set(key, data); return data
        return self._get_cached(key, [])

    def get_club_settings(self, force_refresh=False):
        club = self._get_club()
        key = f"settings_{club}"
        cached = self._read_cache(key)
        if not force_refresh and cached is not _MISS:
            return cached
        
        def q(): 
            res = get_supabase().table('club_settings').select("*").eq('club_name', club).execute().data
            return res[0] if res else {}
        
        data = self._run_query(q, label=key)
        if data is not None: self._set(key, data); return data
        return self._get_cached(key, {'default_fee': 100})
    def get_fee_history(self, force_refresh=False):
        club = self._get_club()
        key = f"fee_hist_{club}"
        cached = self._read_cache(key)
        if not force_refresh and cached is not _MISS:
            return cached
        
        def q(): 
            return (get_supabase().table('fee_history')
                    .select("*").eq('club_name', club)
                    .order('effective_from', desc=True).execute().data)
        
        data = self._run_query(q, label=key)
        if data is not None: self._set(key, data); return data
        return self._get_cached(key, [])
    # --- KALENDARZ / WYDARZENIA ---
    def get_events(self, start_date=None, end_date=None, force_refresh=False):
        club = self._get_club()
        key = f"events_{self._scope()}_{start_date}_{end_date}"
        cached = self._read_cache(key)
        if not force_refresh and cached is not _MISS:
            return cached
        
        def q():
            query = get_supabase().table('events').select("*").eq('club_name', club)
            if start_date: query = query.gte('event_date', str(start_date))
            if end_date: query = query.lte('event_date', str(end_date))
            query = self._team_filter(query, 'events')
            return query.order('event_date').execute().data
        
        data = self._run_query(q, label=key)
        if data is not None: self._set(key, data); return data
        return self._get_cached(key, [])
    def get_attendance(self, event_ids=None, force_refresh=False):
        if not event_ids: return []
        ids_hash = hashlib.md5(str(sorted(event_ids)).encode()).hexdigest()[:10]
        key = f"att_{self._scope()}_{ids_hash}"
        cached = self._read_cache(key)
        if not force_refresh and cached is not _MISS:
            return cached
        
        def q():
            all_data = []
            # BATCH: 30 wydarzeń ~1,2 kB URL - bezpiecznie dla limitu PostgREST,
            # a zamiast 8 zapytań na 120 wydarzeń robimy 4.
            for i in range(0, len(event_ids), 30):
                batch = event_ids[i:i+30]
                all_data.extend(get_supabase().table('attendance').select("*").in_('event_id', batch).execute().data or [])
            return all_data
        
        data = self._run_query(q, label=key)
        if data is not None: self._set(key, data); return data
        return self._get_cached(key, [])
    # --- DASHBOARD ---
    def get_upcoming_events(self, limit=5, force_refresh=False):
        club = self._get_club()
        today = datetime.now().date().isoformat()
        key = f"upcoming_{self._scope()}_{limit}"
        cached = self._read_cache(key)
        if not force_refresh and cached is not _MISS:
            return cached
        
        def q():
            query = (get_supabase().table('events').select("*")
                     .eq('club_name', club).gte('event_date', today))
            query = self._team_filter(query, 'events')
            return query.order('event_date').limit(limit).execute().data
        
        data = self._run_query(q, label=key)
        if data is not None: self._set(key, data); return data
        return self._get_cached(key, [])
    def get_activity_log(self, limit=5, force_refresh=False):
        club = self._get_club()
        key = f"logs_{self._scope()}_{limit}"
        cached = self._read_cache(key)
        if not force_refresh and cached is not _MISS:
            return cached
        
        def q():
            query = (get_supabase().table('activity_log').select("*")
                     .eq('club_name', club))
            query = self._team_filter(query, 'activity_log')
            return query.order('created_at', desc=True).limit(limit).execute().data
        
        data = self._run_query(q, label=key)
        if data is not None: self._set(key, data); return data
        return self._get_cached(key, [])
    # --- SCOUTING & INNE ---
    def get_scouting_targets(self, force_refresh=False):
        club = self._get_club()
        key = f"scouting_{club}"
        cached = self._read_cache(key)
        if not force_refresh and cached is not _MISS:
            return cached
        
        def q(): return get_supabase().table('scouting_targets').select("*").eq('club_name', club).order('created_at', desc=True).execute().data
        data = self._run_query(q, label=key)
        if data is not None: self._set(key, data); return data
        return self._get_cached(key, [])
    def get_ratings(self, player_id=None, force_refresh=False):
        club = self._get_club()
        key = f"ratings_{self._scope()}_{player_id}"
        cached = self._read_cache(key)
        if not force_refresh and cached is not _MISS:
            return cached
        
        def q():
            query = get_supabase().table('ratings').select("*")
            if player_id: query = query.eq('player_id', player_id)
            return self._team_filter(query, 'ratings').execute().data
        
        data = self._run_query(q, label=key)
        if data is not None: self._set(key, data); return data
        return self._get_cached(key, [])
    def get_fitness_history_all(self, force_refresh=False):
        """
        WSZYSTKIE testy fizyczne AKTYWNEJ DRUŻYNY w JEDNYM zapytaniu.

        Wcześniej widok Centrum Rozwoju pytał o historię osobno dla
        każdego gracza (33 zapytania x ~90 ms = ~5 sekund śnieżenia).
        Teraz: jedno zapytanie + słownik player_id -> [testy].
        """
        key = f"fitness_hist_{self._scope()}"
        cached = self._read_cache(key)
        if not force_refresh and cached is not _MISS:
            return cached

        def q():
            query = (get_supabase().table('fitness_tests').select("*")
                     .order("test_date", desc=False))
            query = self._team_filter(query, 'fitness_tests')
            return query.execute().data or []

        data = self._run_query(q, label=key)
        if data is None:
            data = self._get_cached(key, [])
        else:
            self._set(key, data)

        by_player = {}
        for t in data:
            by_player.setdefault(t.get('player_id'), []).append(t)
        return by_player

    def get_development_goals(self, player_id=None, force_refresh=False):
        club = self._get_club()
        key = f"dev_goals_{self._scope()}_{player_id}"
        cached = self._read_cache(key)
        if not force_refresh and cached is not _MISS:
            return cached
        
        def q():
            query = get_supabase().table('development_goals').select("*")
            if player_id: query = query.eq('player_id', player_id)
            return self._team_filter(query, 'development_goals').execute().data
        
        data = self._run_query(q, label=key)
        if data is not None: self._set(key, data); return data
        return self._get_cached(key, [])
    # --- DRUŻYNY / KADRY ---
    def get_teams(self, force_refresh=False):
        """Lista drużyn (teams.py trzyma własny cache w pamięci)."""
        key = f"teams::{self._get_club()}"
        cached = self._read_cache(key)
        if not force_refresh and cached is not _MISS:
            return cached
        # teams.py ma własny cache 5 min - force_refresh=True ominął go
        # i pchał GET /teams przy każdym otwarciu widoku
        data = teams.get_teams(force_refresh=force_refresh)
        self._set(key, data)
        return data

    def get_team_roster(self, team=None, force_refresh=False):
        """Kadra konkretnej drużyny (słowniki graczy)."""
        code = team if team is not None else teams.get_current_team()
        key = f"roster::{self._get_club()}::{code}"
        cached = self._read_cache(key)
        if not force_refresh and cached is not _MISS:
            return cached
        data = teams.get_roster(code, force_refresh=True)
        self._set(key, data)
        return data

    # =============================================
    # INVALIDATION
    # =============================================
    def invalidate(self, pattern):
        with self._lock:
            keys = [k for k in self.cache.keys() if pattern in k]
            for k in keys:
                self.cache.pop(k, None)
                self.timestamps.pop(k, None)
        self._schedule_save()
    
    def invalidate_all(self, reason=""):
        """Czyści cały cache (zmiana sezonu / drużyny / trenera)"""
        with self._lock:
            self.cache.clear()
            self.timestamps.clear()
        self._schedule_save()
        logger.info("🧹 Cały cache wyczyszczony (zmiana sezonu)")

    def invalidate_players(self): self.invalidate("players")
    def invalidate_finances(self): self.invalidate("finances"); self.invalidate("settings"); self.invalidate("fee_hist")
    def invalidate_events(self): self.invalidate("events"); self.invalidate("att"); self.invalidate("upcoming")
    def invalidate_scouting(self): self.invalidate("scouting")
    def invalidate_dashboard(self): self.invalidate("upcoming"); self.invalidate("logs")
    def invalidate_ratings(self):
        """Czyści cache ocen"""
        self.invalidate("ratings")
        logger.info("🗑️ Cache ocen wyczyszczony")
    def hard_reset(self):
        with self._lock: self.cache.clear(); self.timestamps.clear()
        try: os.remove(self.cache_file)
        except: pass

    # =============================================
    # PRELOAD
    # =============================================
    def preload_parallel(self):
        def _job():
            try:
                self.get_teams(True)
                self.get_players(True)
                self.get_club_settings(True)
                self.get_upcoming_events(5, True)
                
                # Reszta w tle
                yr = datetime.now().year
                self.get_finances(yr, None, True)
                self.get_all_finances(True)
                
                today = datetime.now().date()
                start = (today - timedelta(days=60)).isoformat()
                evs = self.get_events(start_date=start, force_refresh=True)
                if evs: 
                    self.get_attendance([e['id'] for e in evs], True)
                
                self.get_scouting_targets(True)
            except Exception as e:
                logger.error(f"Preload error: {e}")
        self._executor.submit(_job)

    def flush(self):
        """Wymusza zapis cache na dysk (wołane przy zamykaniu aplikacji)."""
        if self._save_timer:
            self._save_timer.cancel()
            self._save_timer = None
        self._do_save_disk()

    def shutdown(self):
        """Bezpieczne zamknięcie pul wątków (wołane przy zamykaniu aplikacji)."""
        try:
            self.flush()
        except Exception as e:
            logger.error(f"❌ Błąd finalnego zapisu cache: {e}")
        for pool in (self._executor, self._query_executor):
            try:
                pool.shutdown(wait=False)
            except Exception:
                pass

    def preload_finances(self):
        def _job():
            yr = datetime.now().year
            self.get_teams(True)
            self.get_players(True)
            self.get_finances(yr, None, True)
            self.get_all_finances(True)
            self.get_club_settings(True)
            self.get_fee_history(True)
        self._executor.submit(_job)

# Global Instance
cache = CacheManager()