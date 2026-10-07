"""teams.py — warstwa drużyn (Drużyna I / Rezerwa / Akademia).

Jeden klub, wiele drużyn, jeden system:
  * każdy trener widzi TYLKO swoje drużyny (user_permissions.team_codes),
  * przełącznik drużyny w sidebarze zmienia kontekst całej aplikacji,
  * zawodnik może być jednocześnie w kilku drużynach (player_team_terms),
  * przeniesienie gracza to zamknięcie terminu + otwarcie nowego
    (funkcja move_player_to_team w bazie), a nie kasowanie i zakładanie od nowa.

Konwencja: drużyna to TEKSTOWY KOD ('I', 'II', 'AKD'), tak jak dziś
club_name. Kod '*' = wszystkie drużyny.
"""
import threading
import time

from logger import logger

ALL_TEAMS = "*"

# Zapasowa lista - gdy baza nie odpowiada albo przed pierwszą synchronizacją
FALLBACK_TEAMS = [
    {"code": "I",   "name": "Drużyna I — Seniorzy", "short_name": "I",
     "color": "#3b8ed0", "sort_order": 1, "is_active": True},
    {"code": "II",  "name": "Drużyna II — Rezerwa", "short_name": "II",
     "color": "#2ecc71", "sort_order": 2, "is_active": True},
    {"code": "AKD", "name": "Akademia",             "short_name": "AKD",
     "color": "#e67e22", "sort_order": 3, "is_active": True},
]

TTL = 300  # 5 minut

_lock = threading.RLock()
_state = {
    "teams": list(FALLBACK_TEAMS),
    "loaded": False,
    "loaded_at": 0.0,
    "current": "I",
    "allowed": None,   # None = jeszcze nie wiadomo; ['*'] = wszystkie
    "has_terms": True,
    "terms_checked_at": 0.0,
}


# =====================================================================
# DOSTĘP DO BAZY (leniwy import - unikamy cyklu z database.py)
# =====================================================================
def _supabase():
    from database import supabase
    return supabase


def _club():
    try:
        import database
        return database.CURRENT_CLUB
    except Exception:
        return ""


# =====================================================================
# LISTA DRUŻYN
# =====================================================================
def get_teams(force_refresh=False):
    """Lista drużyn z bazy (z cache w pamięci). Fallback przy awarii."""
    with _lock:
        fresh = (time.time() - _state["loaded_at"]) < TTL
        if _state["loaded"] and fresh and not force_refresh:
            return list(_state["teams"])
        cached = list(_state["teams"])

    try:
        res = _supabase().table("teams").select("*") \
            .order("sort_order").execute()
        rows = res.data or []
        if rows:
            with _lock:
                _state["teams"] = rows
                _state["loaded"] = True
                _state["loaded_at"] = time.time()
            return list(rows)
        logger.info("Tabela teams jest pusta - używam listy zapasowej")
    except Exception as e:
        logger.warning(f"Nie udało się pobrać drużyn ({e}) - lista zapasowa")
        with _lock:
            _state["teams"] = cached
            _state["loaded"] = True
            _state["loaded_at"] = time.time()
    return list(cached)


def get_team(code):
    """Dane jednej drużyny (dict) albo None."""
    if not code or code == ALL_TEAMS:
        return None
    for t in get_teams():
        if t.get("code") == code:
            return t
    return None


def team_name(code):
    t = get_team(code)
    return t["name"] if t else (code or "?")


def team_short(code):
    """Skrót drużyny ('A1', 'AI', 'II'). Nigdy nie wywala się na brak danych."""
    t = get_team(code)
    if t is None:
        return code or "?"
    return (t.get("short_name") or "").strip() or (t.get("name") or "").strip() \
        or code or "?"


def team_label(code, with_name=False):
    """
    Jedna etykieta drużyny dla całego interfejsu.

    Kolejność: SKRÓT -> nazwa -> kod. Interfejs ma pokazywać skrót
    ('A1', 'AI', 'II'), a nie surowy kod z bazy i nie pełną nazwę.
    with_name=True dokłada pełną nazwę tam, gdzie to pomaga
    (przełącznik w sidebarze, lista drużyn).
    """
    label = team_short(code)
    if with_name:
        t = get_team(code)
        name = (t or {}).get("name") or ""
        if name and name != label:
            return f"{label} — {name}"
    return label


# =====================================================================
# UPRAWNIENIA TRENERA
# =====================================================================
def set_allowed_teams(codes):
    """
    Ustawia listę kodów drużyn widocznych dla zalogowanego trenera.

    None  = jeszcze nie wiadomo (traktowane jak '*', zanim nastąpi logowanie)
    []    = ŚWIADOME ograniczenie: trener NIE ma dostępu do żadnej drużyny.
            Nie zamieniamy tego na '*' - inaczej nowy użytkownik
            z pustą listą dostałby dostęp do wszystkich drużyn.
    """
    if codes is None:
        codes = [ALL_TEAMS]
    with _lock:
        _state["allowed"] = [c for c in codes if c]
        current = _state["current"]
    logger.info(f"Trener widzi drużyny: "
                f"{', '.join(_state['allowed']) or 'BRAK DOSTĘPU'}")

    # KRYTYCZNE: po zalogowaniu aktywna drużyna musi BYĆ widoczna.
    # Bez tego nowy trener (brak zapisanej preferencji) zostawał na
    # drużynie poprzedniego użytkownika, do której nie ma dostępu -
    # wszystkie zapytania leciały z filtrem cudzej drużyny.
    if not can_see_team(current):
        visible = visible_teams(include_all=False)
        fallback = visible[0]["code"] if visible else (
            ALL_TEAMS if ALL_TEAMS in get_allowed_teams() else current)
        set_current_team(fallback)


def get_allowed_teams():
    with _lock:
        allowed = _state["allowed"]
    if allowed is None:
        return [ALL_TEAMS]
    return list(allowed)


def can_see_team(code):
    allowed = get_allowed_teams()
    return (ALL_TEAMS in allowed) or (code in allowed)


def can_edit_team(code):
    """
    Czy zalogowany trener MOŻE ZMIENIAĆ kadrę tej drużyny.

    Dziś = to samo co widzenie (can_see_team). Osobna nazwa, bo 'widzieć'
    i 'móc zmieniać' to dwa różne przywileje - i to tutaj się rozjeżdżają:
    trener z dostępem tylko do jednej drużyny nie może przenieść gracza
    z innej drużyny ani wpisać go do cudzej kadry.
    """
    if not code:
        return False
    return can_see_team(code)


def guard_teams(codes, action="zmienić kadry"):
    """
    Fail-closed: zwraca (ok, komunikat). Blokuje WSZYSTKO poza drużynami,
    do których zalogowany trener ma dostęp - również gdy kod przyszedł
    z dialogu, z listy wyboru albo z przypadku (np. zapis drużyny głównej).
    """
    bad = [c for c in (codes or []) if not can_edit_team(c)]
    if not bad:
        return True, ""
    bad_names = ", ".join(team_short(c) or c for c in bad)
    mine = [team_short(t.get("code")) or t.get("code")
            for t in visible_teams(include_all=False)]
    return False, (f"Brak dostępu do drużyny: {bad_names}. "
                   f"Masz dostęp tylko do: {', '.join(mine) or 'braku drużyn'}.")


def visible_teams(include_all=True):
    """Lista drużyn widocznych dla trenera (do przełącznika)."""
    allowed = get_allowed_teams()
    teams = [t for t in get_teams() if t.get("is_active", True)]
    if ALL_TEAMS in allowed:
        out = list(teams)
        if include_all:
            out.insert(0, {"code": ALL_TEAMS, "name": "Wszystkie drużyny",
                           "short_name": "★", "color": "#888888",
                           "sort_order": 0, "is_active": True})
        return out
    return [t for t in teams if t.get("code") in allowed]


# =====================================================================
# AKTYWNA DRUŻYNA
# =====================================================================
def set_current_team(code):
    """
    Ustawia aktywną drużynę. Zwraca True, gdy ustawiono (lub już była).
    Nieznany/zabroniony kod -> zostaje poprzednia drużyna.
    """
    if code == ALL_TEAMS:
        code = ALL_TEAMS
    elif not code:
        # None/'' = brak zapamiętanej drużyny (nowy trener) - to nie błąd
        return False
    elif not can_see_team(code):
        logger.warning(f"Brak dostępu do drużyny {code}")
        return False
    with _lock:
        _state["current"] = code
    return True


def resolve_team_for_player(player_id):
    """
    Kod drużiny, do której należy zapisać wiersz tego gracza.

    'get_current_team()' w trybie "wszystkie drużyny" zwraca '*' - a to
    NIE jest kod drużyny i nie wolno go zapisywać w kolumnie team_code
    (taki wiersz zniknąłby potem z widoku właściciela drużyny).
    """
    cur = get_current_team()
    if cur and cur != ALL_TEAMS and get_team(cur) is not None:
        return cur
    prim = primary_team_of(player_id)
    if prim:
        return prim
    terms = get_active_terms(player_id)
    if terms:
        return terms[0].get("team_code")
    return cur


def reset_current_team():
    """
    Ustaw aktywną drużynę na pierwszą WIDOCZNĄ dla zalogowanego trenera
    (albo '*' gdy może widzieć wszystkie). Używane po zalogowaniu,
    gdy nie ma zapamiętanej preferencji.
    """
    visible = visible_teams(include_all=False)
    if visible:
        return set_current_team(visible[0]["code"])
    if ALL_TEAMS in get_allowed_teams():
        return set_current_team(ALL_TEAMS)
    return False


def get_current_team():
    """Kod aktywnej drużyny ('*' = wszystkie)."""
    with _lock:
        cur = _state["current"]
    if cur != ALL_TEAMS and not can_see_team(cur):
        # np. po zalogowaniu innym trenerem - wracamy do bezpiecznej wartości
        return ALL_TEAMS if ALL_TEAMS in get_allowed_teams() else cur
    return cur


def current_team_dict():
    return get_team(get_current_team())


def is_all_teams():
    return get_current_team() == ALL_TEAMS


def scope_label(short_only=False):
    """
    Napisy do paska stanu i nagłówków.
    short_only=True zwraca sam SKRÓT drużyny (np. 'A1') - używane tam,
    gdzie nazwa jest już widoczna obok i tylko zaciemnia.
    """
    if is_all_teams():
        return "Wszystkie drużyny"
    return team_label(get_current_team(), with_name=not short_only)


# =====================================================================
# FILTROWANIE (wspólne dla cache i widoków)
# =====================================================================
def team_filter(query, table="events", column="team_code"):
    """
    Dokłada warunek drużyny do zapytania PostgREST.

    Zasada: team_code IS NULL = wpis wspólny (stare dane przed migracją)
    -> widoczny w każdej drużynie. team_code = 'I' -> tylko w drużynie I.
    """
    code = get_current_team()
    if code == ALL_TEAMS:
        return query
    return query.or_(f"{column}.is.null,{column}.eq.{code}")


def row_matches_team(row, column="team_code"):
    """Filtr po stronie Pythona (gdy dane są już w pamięci)."""
    code = get_current_team()
    if code == ALL_TEAMS:
        return True
    value = row.get(column) if isinstance(row, dict) else None
    return value is None or value == code


def filter_rows(rows, column="team_code"):
    """Zwraca tylko wiersze pasujące do aktywnej drużyny."""
    if is_all_teams():
        return list(rows)
    return [r for r in rows if row_matches_team(r, column)]


def scope_keys(club, code=None):
    """Klucz cache: 'Klub|KOD' - dwa różne kluby/drużyny nie mieszają się."""
    return f"{club}|{code if code is not None else get_current_team()}"


# =====================================================================
# SKŁAD I CZŁONKOSTWA
# =====================================================================
def get_team_player_ids(code=None, force_refresh=False):
    """Zbiór ID zawodników aktywnie przypisanych do drużyny."""
    code = code if code is not None else get_current_team()
    key = f"roster::{_club()}::{code}"
    if code == ALL_TEAMS:
        key = f"roster::{_club()}::*"

    from cache_manager import cache
    cached = cache._get_cached(key)
    if cached is not None and not force_refresh:
        return set(cached)

    try:
        if code == ALL_TEAMS:
            res = _supabase().table("players").select("id").eq(
                "club_name", _club()).execute()
        else:
            res = _supabase().table("player_team_terms").select("player_id") \
                .eq("team_code", code).is_("left_on", "null").execute()
        ids = [r["player_id"] if "player_id" in r else r["id"]
               for r in (res.data or [])]
    except Exception as e:
        logger.error(f"Nie udało się pobrać kadry drużyny {code}: {e}")
        ids = []

    cache._set(key, ids)
    return set(ids)


def has_any_terms(force_refresh=False):
    """
    Czy w bazie istnieje JAKIKOLWIEK termin kadry.

    Jedyny przypadek, w którym kadra drużyny może spaść do całego klubu:
    migracja nie została wykonana i tabela player_team_terms jest pusta.

    Odpowiedź trzymamy w pamięci na 60 s - to pytanie powtarzało się
    przy KAŻDYM pobraniu kadry, a z sieci idzie ~90 ms.

    WAŻNE: odpowiedź musi być niezależna od RLS, inaczej użytkownik bez
    zakładki 'players' dostanie fałszywe "nie ma terminów" i zobaczy całą
    kadrę klubu zamiast swojej drużyny. Dlatego pytamy funkcję RPC
    tt_terms_exist() (SECURITY DEFINER), a nie wprost tabelę.
    """
    with _lock:
        fresh = (time.time() - _state["terms_checked_at"]) < 60
        if fresh and not force_refresh:
            return _state["has_terms"]

    value = None
    # 1) Zapytanie z SECURITY DEFINER - widzi tabelę TYLKO wtedy, gdy
    #    naprawdę jest pusta, a nie gdy RLS ukrył ją przed tym
    #    użytkownikiem. Bez tego trener bez zakładki 'players' (np. Milosz,
    #    sam Finanse) dostawał "brak terminów" i kadra spadała do CAŁEGO
    #    klubu - czyli widział wszystkich zawodników zamiast swojej drużyny.
    try:
        res = _supabase().rpc("tt_terms_exist").execute()
        if res.data is not None:
            value = bool(res.data)
    except Exception:
        value = None      # funkcji jeszcze nie ma - próbujemy starej drogi

    if value is None:
        try:
            res = _supabase().table("player_team_terms").select("id") \
                .limit(1).execute()
            value = bool(res.data)
        except Exception as e:
            logger.error(f"Nie udało się sprawdzić terminów kadry: {e}")
            value = True  # nie ufamy 'nie ma kadry' - bezpieczniej pokaż mniej

    with _lock:
        _state["has_terms"] = value
        _state["terms_checked_at"] = time.time()
    return value


def get_roster(code=None, force_refresh=False):
    """Lista słowników graczy aktywnej drużyny (pełne rekordy z players)."""
    code = code if code is not None else get_current_team()
    ids = get_team_player_ids(code, force_refresh)
    if not ids:
        return []
    try:
        res = _supabase().table("players").select("*").in_("id", list(ids)) \
            .execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Błąd pobierania kadry {code}: {e}")
        return []


def get_player_terms(player_id):
    """Historia przynależności gracza do drużyn (nowsze najpierw)."""
    try:
        res = _supabase().table("player_team_terms").select("*") \
            .eq("player_id", player_id) \
            .order("joined_on", desc=True).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Błąd pobierania członkostw gracza: {e}")
        return []


def get_active_terms(player_id):
    return [t for t in get_player_terms(player_id) if not t.get("left_on")]


def player_team_names(player_id):
    """['Drużyna I — Seniorzy', 'Akademia'] - do profilu gracza."""
    return [team_name(t["team_code"]) for t in get_active_terms(player_id)]


def primary_team_of(player_id):
    """Kod drużyny głównej gracza albo None."""
    terms = get_active_terms(player_id)
    primary = [t for t in terms if t.get("is_primary")]
    if primary:
        return primary[0]["team_code"]
    return terms[0]["team_code"] if terms else None


def assign_player(player_id, team_code, is_primary=None):
    """
    Przypisuje gracza do drużyny BEZ przenoszenia (może być w kilku naraz,
    np. zawodnik pierwszej drużyny wciąż widoczny w akademii).

    Używane przy: dodaniu nowego zawodnika, włączeniu juniora do kadry.
    """
    if not team_code or team_code == ALL_TEAMS:
        return False, "Brak drużyny docelowej."
    ok, msg = guard_teams([team_code], "dodać zawodnika")
    if not ok:
        return False, msg
    try:
        terms = get_active_terms(player_id)
        if any(t["team_code"] == team_code for t in terms):
            return True, "Gracz już jest w tej drużynie."

        if is_primary is None:
            is_primary = not any(t.get("is_primary") for t in terms)

        _supabase().table("player_team_terms").insert({
            "player_id": player_id,
            "team_code": team_code,
            "is_primary": bool(is_primary),
            "status": "active",
            # joined_on pomijamy celowo - wtedy baza wstawia current_date
        }).execute()

        if is_primary:
            try:
                _supabase().table("players").update(
                    {"primary_team_code": team_code}) \
                    .eq("id", player_id).execute()
            except Exception as e:
                logger.warning(f"Nie udało się zapisać primary_team_code: {e}")

        from cache_manager import cache
        cache.invalidate("roster")
        cache.invalidate("players")
        return True, f"Gracz przypisany do {team_name(team_code)}."
    except Exception as e:
        logger.error(f"Błąd przypisania gracza do drużyny: {e}")
        return False, str(e)


def _invalidate_roster():
    """Po zmianie kadry: kasujemy klucze zależne od listy zawodników."""
    try:
        from cache_manager import cache
        cache.invalidate("roster")
        cache.invalidate("players")
        cache.invalidate("all_players")
        cache.invalidate("finances")
    except Exception as e:
        logger.warning(f"Nie udało się wyczyścić cache kadry: {e}")


def _set_primary_flag(player_id, code):
    """
    Ustawia dokładnie jeden aktywny termin główny.

    NAJPIERW zdejmuje flagę ze wszystkich, POTEM zakłada ją na wskazany.
    Odwrotna kolejność wywala się o uniq_primary_term (jeden gracz =
    jedna drużyna główna).
    """
    if not code:
        return
    _supabase().table("player_team_terms").update({"is_primary": False}) \
        .eq("player_id", player_id).is_("left_on", "null").execute()
    _supabase().table("player_team_terms").update({"is_primary": True}) \
        .eq("player_id", player_id).eq("team_code", code) \
        .is_("left_on", "null").execute()


def _sync_primary(player_id):
    """Upewnia się, że gracz ma dokładnie jedną aktywną drużynę główną."""
    try:
        terms = get_active_terms(player_id)
        if not terms:
            _supabase().table("players").update(
                {"primary_team_code": None}).eq("id", player_id).execute()
            return
        primaries = [t for t in terms if t.get("is_primary")]
        # więcej niż jedna główna? zostaje pierwsza, reszta przestaje nią być
        for extra in primaries[1:]:
            _supabase().table("player_team_terms").update(
                {"is_primary": False}).eq("id", extra["id"]).execute()
        if primaries:
            keep = primaries[0]
        else:
            # żadna nie jest główna (np. zamknęliśmy dawną) -> wybieramy
            keep = terms[0]
            _supabase().table("player_team_terms").update(
                {"is_primary": True}).eq("id", keep["id"]).execute()
        _supabase().table("players").update(
            {"primary_team_code": keep["team_code"]}) \
            .eq("id", player_id).execute()
    except Exception as e:
        logger.warning(f"Nie udało się ustalić drużyny głównej: {e}")


def remove_player_from_team(player_id, team_code, note=None):
    """
    Wyprowadza gracza z kadry drużyny (termin jest ZAMYKANY, nie kasowany -
    zostaje historia). Sam zawodnik zostaje w klubie.
    """
    if not team_code or team_code == ALL_TEAMS:
        return False, "Nie można usunąć z 'wszystkich drużyn'."
    ok, msg = guard_teams([team_code], "usunąć zawodnika")
    if not ok:
        return False, msg
    terms = [t for t in get_active_terms(player_id)
             if t.get("team_code") == team_code]
    if not terms:
        return False, f"Gracz nie jest w drużynie {team_name(team_code)}."
    if len(get_active_terms(player_id)) <= len(terms):
        return False, "Gracz musi zostać w co najmniej jednej drużynie."

    try:
        for t in terms:
            _supabase().table("player_team_terms").update({
                "left_on": str(time.strftime("%Y-%m-%d")),
                "status": "inactive",
                "is_primary": False,
                "note": note or "usunięty z kadry",
            }).eq("id", t["id"]).execute()
        _sync_primary(player_id)
        _invalidate_roster()
        return True, f"Usunięto z kadry: {team_name(team_code)}."
    except Exception as e:
        logger.error(f"Błąd usuwania gracza z drużyny: {e}")
        return False, str(e)


def set_player_memberships(player_id, codes, primary=None, note=None):
    """
    Ustawia dokładnie te drużyny, w których gracz ma być (lista = stan docelowy).

    Różnica między 'dodaj do' i 'usuń z' robi się sama: to, co zaznaczone,
    zostaje, reszta jest zamykana. Gracz może być w kilku drużynach naraz.
    """
    wanted = []
    for c in (codes or []):
        c = (c or "").strip()
        if c and c != ALL_TEAMS and c not in wanted:
            wanted.append(c)
    if not wanted:
        return False, "Gracz musi należeć do co najmniej jednej drużyny."

    known = {t.get("code") for t in get_teams(force_refresh=True)
             if t.get("is_active", True)}
    unknown = [c for c in wanted if c not in known]
    if unknown:
        return False, "Nieznane drużyny: " + ", ".join(unknown)

    ok, msg = guard_teams(wanted, "zapisać kadrę")
    if not ok:
        return False, msg

    current = {t["team_code"]: t for t in get_active_terms(player_id)}

    # NIE wolno ruszać gracza, który jest też w innej drużynie - inaczej
    # zapis 'zostaw tylko AK1' po cichu zamknąłby mu członkostwo w
    # drużynie, na którą trener nawet nie ma prawa patrzeć.
    foreign = [c for c in current if not can_edit_team(c)]
    if foreign:
        names = ", ".join(team_short(c) or c for c in foreign)
        return False, (f"Gracz jest też w drużynie {names}, do której nie "
                       f"masz dostępu - nie możesz zmieniać jego kadry. "
                       f"Poproś kierownika drużyny {names}.")
    to_add    = [c for c in wanted if c not in current]
    to_remove = [c for c in current if c not in wanted]
    if primary and primary not in wanted:
        primary = None

    try:
        # KOLEJNOŚĆ MA ZNACZENIE:
        #   1) zamykamy zbędne terminy (is_primary=False),
        #   2) wstawiamy nowe ZAWSZE bez flagi głównej,
        #   3) dopiero na końcu ustawiamy drużynę główną.
        # Wstawienie nowego terminu jako 'głównego' przed zdjęciem tej
        # flagi ze starego wywala się o uniq_primary_term (HTTP 409).

        for code in to_remove:
            t = current[code]
            _supabase().table("player_team_terms").update({
                "left_on": str(time.strftime("%Y-%m-%d")),
                "status": "inactive",
                "is_primary": False,
                "note": note or "zmiana kadry",
            }).eq("id", t["id"]).execute()
            _supabase().table("player_transfers").insert({
                "player_id": player_id, "from_team": code,
                "to_team": (wanted[0] if wanted else "-"),
                "note": note or "zmiana kadry",
            }).execute()

        for code in to_add:
            _supabase().table("player_team_terms").insert({
                "player_id": player_id,
                "team_code": code,
                "is_primary": False,
                "status": "active",
            }).execute()

        if not primary and wanted:
            primary = wanted[0]
        _set_primary_flag(player_id, primary)
        _sync_primary(player_id)
        _invalidate_roster()

        parts = []
        if to_add:
            parts.append("dodano do: " + ", ".join(team_name(c) for c in to_add))
        if to_remove:
            parts.append("usunięto z: " + ", ".join(
                team_name(c) for c in to_remove))
        if not parts:
            parts.append("bez zmian")
        return True, "; ".join(parts).capitalize() + "."
    except Exception as e:
        logger.error(f"Błąd zapisu członkostw: {e}")
        return False, str(e)


def move_player(player_id, to_team, note=None, moved_by=None):
    """
    Przenosi zawodnika do innej drużyny (RPC w bazie zapisuje historię).
    Zwraca (ok, komunikat).
    """
    if not to_team or to_team == ALL_TEAMS:
        return False, "Nie można przenieść do 'wszystkich drużyn'."
    if get_team(to_team) is None:
        return False, f"Nieznana drużyna: {to_team}"
    ok, msg = guard_teams([to_team], "przenieść zawodnika")
    if not ok:
        return False, msg

    current = primary_team_of(player_id)
    if current == to_team:
        return False, "Gracz jest już w tej drużynie."

    try:
        import database
        if moved_by is None:
            moved_by = database.CURRENT_USER_EMAIL or "system"
        _supabase().rpc("move_player_to_team", {
            "p_player": player_id,
            "p_to_team": to_team,
            "p_note": note,
            "p_moved_by": moved_by,
        }).execute()
    except Exception as e:
        logger.error(f"Nie udało się przenieść gracza: {e}")
        return False, str(e)

    from cache_manager import cache
    cache.invalidate("roster")
    cache.invalidate("players")
    cache.invalidate("all_players")
    cache.invalidate("finances")
    return True, f"Przeniesiono z {team_name(current) if current else '—'} " \
                 f"do {team_name(to_team)}."


def delete_team(code, note=None):
    """
    Kasuje drużynę z bazy.

    Nie rzuca niczego w SQL: najpierw zamykamy kadry tej drużyny (terminy
    dostają left_on i status 'inactive', więc historia zostaje), potem
    kasujemy sam wiersz teams. Gracze zostają w klubie i trafiają do
    pierwszej aktywnej drużyny.
    """
    team = get_team(code)
    if team is None:
        return False, f"Nie ma drużyny o kodzie '{code}'."
    ok, msg = guard_teams([code], "usunąć drużynę")
    if not ok:
        return False, msg

    others = [t for t in get_teams(force_refresh=True)
              if t.get("is_active", True) and t.get("code") != code]
    if not others:
        return False, ("To jest ostatnia aktywna drużyna — nie można jej "
                       "usunąć. Najpierw dodaj kolejną.")
    fallback = others[0]["code"]

    try:
        # 1. zamknij terminy kadry tej drużyny
        for t in [t for t in _all_terms(code) if not t.get("left_on")]:
            _supabase().table("player_team_terms").update({
                "left_on": str(time.strftime("%Y-%m-%d")),
                "status": "inactive",
                "note": note or "drużyna usunięta",
            }).eq("id", t["id"]).execute()

            # 2. gracz bez innej drużyny -> dostaje termin w zapasowej,
            #    bo inaczej zniknąłby ze wszystkich kad naraz
            rest = [x for x in get_active_terms(t["player_id"])
                    if x.get("team_code") != code]
            if not rest:
                _supabase().table("player_team_terms").insert({
                    "player_id": t["player_id"],
                    "team_code": fallback,
                    "is_primary": True,
                    "status": "active",
                    "note": note or "przeniesiony po usunięciu drużyny",
                }).execute()
                _supabase().table("players").update(
                    {"primary_team_code": fallback}) \
                    .eq("id", t["player_id"]).execute()
            else:
                _supabase().table("players").update(
                    {"primary_team_code": rest[0]["team_code"]}) \
                    .eq("id", t["player_id"]).execute()

        # 3. wiersz drużyny
        _supabase().table("teams").delete().eq("code", code).execute()

        # 4. uprawnienia trenerów: nikt nie może trzymać usuniętego kodu
        try:
            rows = _supabase().table("user_permissions") \
                .select("email, team_codes").execute().data or []
            for r in rows:
                codes = r.get("team_codes") or []
                if "*" in codes or code not in codes:
                    continue
                left = [c for c in codes if c != code] or ["*"]
                _supabase().table("user_permissions").update(
                    {"team_codes": left}).eq("email", r["email"]).execute()
        except Exception as e:
            logger.warning(f"Nie udało się posprzątać uprawnień: {e}")

        # 5. jeśli właśnie tu był przełącznik -> przenieś kontekst
        if get_current_team() == code:
            set_current_team(fallback)

        get_teams(force_refresh=True)
        _invalidate_roster()
        logger.info(f"Usunięto drużynę {code} ({team.get('name')})")
        return True, (f"Usunięto drużynę: {team.get('name')}. "
                      f"Gracze, którzy tylko w niej byli, przeszli do "
                      f"{team_name(fallback)}.")
    except Exception as e:
        logger.error(f"Błąd usuwania drużyny: {e}")
        return False, str(e)


def _all_terms(code):
    """Wszystkie terminy kadry drużyny (również zamknięte)."""
    try:
        res = _supabase().table("player_team_terms").select("*") \
            .eq("team_code", code).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Nie udało się pobrać terminów drużyny {code}: {e}")
        return []


def get_transfers(player_id=None, limit=50):
    """Historia przeniesień (widok w profilu gracza)."""
    try:
        q = _supabase().table("player_transfers").select("*") \
            .order("created_at", desc=True).limit(limit)
        if player_id:
            q = q.eq("player_id", player_id)
        return (q.execute().data) or []
    except Exception as e:
        logger.error(f"Błąd historii transferów: {e}")
        return []