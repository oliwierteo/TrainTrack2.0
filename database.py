from supabase import create_client, Client
import os
from logger import logger
import teams

# --- KONFIGURACJA POŁĄCZENIA ---
url: str = "https://jbnqmrsaqklbrhyyivdc.supabase.co/"
key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpibnFtcnNhcWtsYnJoeXlpdmRjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk3MTkwMTksImV4cCI6MjA4NTI5NTAxOX0.MDsaMWRqE4nR1e_n4zEeNaZd-U33N_lzuVBB2DeCWwo"

supabase: Client = create_client(url, key)

# --- ZMIENNE GLOBALNE (Dostępne w całej aplikacji) ---
CURRENT_CLUB = "Chełmianka Gdańsk"
CURRENT_USER_EMAIL = ""
ALLOWED_TABS = []
ALLOWED_TEAMS = []          # kody drużyn danego trenera


def current_team():
    """Kod aktywnej drużyny (patrz teams.py - jedno źródło prawdy)."""
    return teams.get_current_team()


def current_team_label():
    return teams.scope_label()

class AuthManager:
    """Klasa odpowiedzialna za logowanie i zarządzanie sesją"""
    
    def login(self, email, password):
        global CURRENT_USER_EMAIL, ALLOWED_TABS
        try:
            # 1. Próba logowania w Supabase Auth
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            
            if response.user:
                CURRENT_USER_EMAIL = email
                
                # 2. Pobranie uprawnień (zakładek) dla tego adresu e-mail
                res = (supabase.table('user_permissions')
                       .select("allowed_tabs, team_codes")
                       .eq('email', email).execute())

                if res.data:
                    ALLOWED_TABS = res.data[0]['allowed_tabs']
                    # team_codes nie istniało przed migracją drużyn.
                    # WAŻNE: pusta lista to BRAK dostępu, nie wszystko -
                    # inaczej nowy trener z team_codes = '{}' dostałby
                    # dostęp do wszystkich drużyn. '*' zakładamy tylko tam,
                    # gdzie kolumny jeszcze nie ma (stare bazy).
                    raw = res.data[0].get('team_codes', None)
                    if raw is None:
                        team_codes = ['*']
                    else:
                        team_codes = [c for c in raw if c]
                else:
                    # Konto bez wiersza w user_permissions: sam dashboard
                    ALLOWED_TABS = ['dashboard']
                    team_codes = []

                # Które drużyny ten trener widzi (wpływa na przełącznik
                # i na to, co kadrę/zdarzenia da się odpytać)
                global ALLOWED_TEAMS
                ALLOWED_TEAMS = list(team_codes)
                teams.set_allowed_teams(team_codes)

                # Ustaw aktywną drużynę: preferencja trenera, inaczej
                # pierwsza drużyna, do której ma dostęp
                saved = load_preferred_team(email)
                if saved and not teams.set_current_team(saved):
                    logger.info(f"Zapisana drużyna {saved} niedostępna "
                                f"- wybieram domyślną")
                    teams.reset_current_team()
                elif not saved:
                    # Nowy trener (np. jan@klub.pl): brak preferencji ->
                    # pierwsza drużyna, do której ma dostęp.
                    teams.reset_current_team()
                logger.info(f"Aktywna drużyna: {teams.get_current_team()}")

                # 3. AUTOMATYCZNE CZYSZCZENIE LOGÓW (Retention Policy: 7 dni)
                # Wywołujemy funkcję SQL zdefiniowaną w bazie
                try:
                    supabase.rpc('clean_old_activity_logs').execute()
                except Exception as e:
                    logger.info(f"Brak funkcji czyszczącej lub błąd rpc: {e}")

                return True, response.user
            
            return False, "Nieznany błąd logowania."
            
        except Exception as e:
            # Obsługa błędnych danych logowania
            error_msg = str(e)
            if "Invalid login credentials" in error_msg:
                return False, "Błędny e-mail lub hasło."
            return False, error_msg

def log_activity(action_text):
    """
    Zapisuje działanie trenera do tabeli activity_log.
    Używaj w widokach jako: database.log_activity("dodał zawodnika")
    """
    global CURRENT_USER_EMAIL, CURRENT_CLUB
    try:
        # Formatowanie nazwy trenera na podstawie maila (np. bartek@klub.pl -> Bartek)
        if CURRENT_USER_EMAIL:
            coach_display_name = CURRENT_USER_EMAIL.split('@')[0].capitalize()
        else:
            coach_display_name = "System"

        data = {
            "coach_name": coach_display_name,
            "action": action_text,
            "club_name": CURRENT_CLUB,
            # kolumna team_code powstaje w migracja_druzyne.sql; przy
            # starym schemacie zapis i tak przejdzie (błąd jest logowany).
            # '*' nie jest kodem drużyny - przy logowaniu z widoku
            # "wszystkie drużyny" wpisujemy kod aktywnej drużyny.
            "team_code": (teams.get_current_team()
                          if teams.get_current_team() != teams.ALL_TEAMS
                          else None)
        }
        
        supabase.table('activity_log').insert(data).execute()
    except Exception as e:
        logger.error(f"Błąd podczas logowania aktywności: {e}")

# --- DODATKOWE FUNKCJE POMOCNICZE (Opcjonalne) ---
def _prefs_path():
    import os as _os
    import json as _json
    import tempfile
    base = _os.path.join(_os.path.expanduser("~"), ".traintrack")
    try:
        _os.makedirs(base, exist_ok=True)
    except Exception:
        base = _os.path.join(tempfile.gettempdir(), "traintrack")
    return _os.path.join(base, "prefs.json")


def load_preferred_team(email):
    """Drużyna zapamiętana z ostatniej sesji tego trenera."""
    import json
    try:
        with open(_prefs_path(), "r", encoding="utf-8") as f:
            return (json.load(f).get("team_by_user") or {}).get(email)
    except Exception:
        return None


def save_preferred_team(email, code):
    """Zapamiętaj drużynę trenera (żeby wrócił do niej po restarcie)."""
    import json
    try:
        path = _prefs_path()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        data.setdefault("team_by_user", {})[email] = code
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Nie udało się zapamiętać drużyny: {e}")


def get_current_user_short():
    """Zwraca sformatowane imię zalogowanego trenera"""
    if CURRENT_USER_EMAIL:
        return CURRENT_USER_EMAIL.split('@')[0].capitalize()
    return "Trener"

def safe_int(value, default=0):
    """Bezpieczna zamiana na liczbę całkowitą (np. wiek, numer)"""
    try:
        if value is None: return default
        # Czyścimy spacje i zamieniamy pusty string na default
        s = str(value).strip()
        if not s: return default
        # Najpierw na float (żeby obsłużyć "20.0"), potem int
        return int(float(s))
    except (ValueError, TypeError):
        return default

def safe_float(value, default=0.0):
    """Bezpieczna zamiana na liczbę zmiennoprzecinkową (np. kwota)"""
    try:
        if value is None: return default
        # Zamieniamy przecinek na kropkę (dla polskiego formatu)
        s = str(value).strip().replace(',', '.')
        if not s: return default
        return float(s)
    except (ValueError, TypeError):
        return default

# NOWE - automatyczne wykrywanie sezonu:
def _get_current_season():
    """
    Automatycznie wykrywa aktualny sezon.
    Sezon piłkarski: lipiec - czerwiec
    np. lipiec 2026 = sezon 26/27
    """
    from datetime import date
    today = date.today()
    year  = today.year

    # Jeśli miesiąc >= lipiec (7) -> nowy sezon się zaczął
    if today.month >= 7:
        start = year % 100        # np. 2026 -> 26
        end   = (year + 1) % 100  # np. 2027 -> 27
    else:
        start = (year - 1) % 100  # np. 2026 -> 25
        end   = year % 100        # np. 2026 -> 26

    return f"{start}/{end}"

CURRENT_SEASON = _get_current_season()

# Sprawdź przy starcie
logger.info(f"🗓 Wykryty sezon: {CURRENT_SEASON}")


def set_season(season_str):
    """Ustawia aktywny sezon (bez błędów na złym formacie)."""
    global CURRENT_SEASON
    try:
        start, end = season_str.split('/')
        season_str = f"{int(start):02d}/{int(end):02d}"
    except (ValueError, AttributeError):
        return CURRENT_SEASON
    CURRENT_SEASON = season_str
    return CURRENT_SEASON


def get_season_start_date(season_str=None):
    """Pierwszy dzień sezonu jako datetime.date."""
    from datetime import date
    start_str, _ = get_season_range(season_str)
    try:
        return date(*map(int, start_str.split("-")))
    except (ValueError, TypeError):
        return date.today()


def get_season_anchor(season_str=None):
    """
    Zwraca (rok, miesiąc) na który wskakuje dany sezon:
    - jeśli 'dzisiaj' mieści się w sezonie -> dziś
    - w przeciwnym razie -> pierwszy miesiąc sezonu (lipiec)
    """
    from datetime import date
    start_str, end_str = get_season_range(season_str)
    today = date.today()
    try:
        s = date(*map(int, start_str.split("-")))
        e = date(*map(int, end_str.split("-")))
    except (ValueError, TypeError):
        return today.year, today.month
    if s <= today <= e:
        return today.year, today.month
    return s.year, s.month

def get_season_range(season_str=None):
    """
    Konwertuje format '26/27' na daty (YYYY-07-01, YYYY-06-30)
    """
    if season_str is None:
        season_str = CURRENT_SEASON
    
    try:
        parts = season_str.split('/')
        start_yr_short = int(parts[0])
        end_yr_short = int(parts[1])
        
        start_date = f"20{start_yr_short}-07-01"
        end_date = f"20{end_yr_short}-06-30"
        return start_date, end_date
    except Exception:
        # Fallback - aktualny sezon z CURRENT_SEASON
        from datetime import date
        y = date.today().year
        if date.today().month >= 7:
            return f"{y}-07-01", f"{y+1}-06-30"
        else:
            return f"{y-1}-07-01", f"{y}-06-30"

def get_available_seasons():
    """Lista sezonów - dynamiczna, zawsze aktualna"""
    from datetime import date
    today = date.today()
    
    # Ustal bazowy rok sezonu
    base = today.year if today.month >= 7 else today.year - 1
    
    seasons = []
    for i in range(-1, 3):  # 1 wstecz + aktualny + 2 w przód
        s = (base + i) % 100
        e = (base + i + 1) % 100
        seasons.append(f"{s:02d}/{e:02d}")
    
    return seasons  # Dziś: ["25/26", "26/27", "27/28", "28/29"]

def create_fitness_tests_table():
    """Przy Supabase - tabela tworzona przez SQL Editor, ta funkcja nic nie robi"""
    pass  # Tabela już istnieje w Supabase

def add_fitness_test(player_id, test_date, beep_level, beep_shuttle, shuttle_150m, notes=""):
    """Dodaje wynik testu fizycznego"""
    try:
        supabase.table("fitness_tests").insert({
            "player_id": player_id,
            # '*' (wszystkie drużyny) NIE jest kodem drużyny - bierzemy
            # realną drużynę gracza, inaczej wiersz znika z jego widoku.
            "team_code": teams.resolve_team_for_player(player_id),
            "test_date": str(test_date),
            "beep_level": int(beep_level),
            "beep_shuttle": int(beep_shuttle),
            "shuttle_150m_seconds": float(shuttle_150m),
            "notes": notes
        }).execute()
    except Exception as e:
        logger.error(f"❌ Błąd dodawania testu: {e}")

def get_fitness_tests(player_id=None):
    """Pobiera testy - opcjonalnie filtruje po zawodniku"""
    try:
        query = supabase.table("fitness_tests")\
            .select("*, players(full_name, jersey_number, key_ability, primary_position)")\
            .order("test_date", desc=True)

        if player_id:
            query = query.eq("player_id", player_id)
        if player_id is None:
            query = teams.team_filter(query, "fitness_tests")

        response = query.execute()
        
        # Spłaszcz dane (Supabase zwraca nested dict)
        result = []
        for row in response.data:
            flat = {**row}
            if row.get("players"):
                flat["full_name"] = row["players"].get("full_name")
                flat["jersey_number"] = row["players"].get("jersey_number")
                flat["key_ability"] = row["players"].get("key_ability")
                flat["primary_position"] = row["players"].get("primary_position")
            del flat["players"]
            result.append(flat)
        
        return result
    except Exception as e:
        logger.error(f"❌ Błąd pobierania testów: {e}")
        return []

def get_latest_fitness_tests():
    """Pobiera najnowszy test dla każdego zawodnika AKTYWNEJ DRUŻYNY"""
    try:
        # Pobierz testy z danymi graczy
        query = (supabase.table("fitness_tests")
                 .select("*, players(full_name, jersey_number, key_ability, "
                         "primary_position)")
                 .order("test_date", desc=True))
        # BEZ tego Centrum Rozwoju pokazywałoby wyniki innych drużyn
        try:
            query = teams.team_filter(query, "fitness_tests")
        except Exception as e:
            logger.warning(f"Filtr drużyny (fitness_tests) pominięty: {e}")
        response = query.execute()
        
        # Zostaw tylko najnowszy dla każdego
        seen_players = set()
        result = []
        
        for row in response.data:
            pid = row["player_id"]
            if pid not in seen_players:
                seen_players.add(pid)
                flat = {**row}
                if row.get("players"):
                    flat["full_name"] = row["players"].get("full_name")
                    flat["jersey_number"] = row["players"].get("jersey_number")
                    flat["key_ability"] = row["players"].get("key_ability")
                    flat["primary_position"] = row["players"].get("primary_position")
                del flat["players"]
                result.append(flat)
        
        return result
    except Exception as e:
        logger.error(f"❌ Błąd pobierania najnowszych testów: {e}")
        return []

def get_player_fitness_history(player_id):
    """Historia testów jednego zawodnika - od najstarszego"""
    try:
        response = supabase.table("fitness_tests")\
            .select("*")\
            .eq("player_id", player_id)\
            .order("test_date", desc=False)\
            .execute()
        return response.data
    except Exception as e:
        logger.error(f"❌ Błąd pobierania historii: {e}")
        return []

def delete_fitness_test(test_id):
    """Usuwa test"""
    try:
        supabase.table("fitness_tests")\
            .delete()\
            .eq("id", test_id)\
            .execute()
    except Exception as e:
        logger.error(f"❌ Błąd usuwania testu: {e}")

def update_fitness_test(test_id, beep_level, beep_shuttle, shuttle_150m, notes=""):
    """Aktualizuje test"""
    try:
        supabase.table("fitness_tests")\
            .update({
                "beep_level": int(beep_level),
                "beep_shuttle": int(beep_shuttle),
                "shuttle_150m_seconds": float(shuttle_150m),
                "notes": notes
            })\
            .eq("id", test_id)\
            .execute()
    except Exception as e:
        logger.error(f"❌ Błąd aktualizacji testu: {e}")