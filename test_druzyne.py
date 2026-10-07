"""
test_druzyne.py — testy logiki drużyn BEZ połączenia z bazą.

Sprawdza:
  1. uprawnienia trenera (kto jakie drużyny widzi),
  2. klucze cache (dwie drużyny NIE dzielą danych),
  3. generowanie filtru team_code dla PostgREST,
  4. przypisanie gracza do drużyny (bez przenoszenia),
  5. regułę "team_code IS NULL = wpis wspólny" (migracja niczego nie ukrywa),
  6. blokadę przełączania na drużynę bez dostępu.
"""
import sys, os, threading, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import teams
import cache_manager

# --- atrapa Supabase -------------------------------------------------------
TEAMS_DB = [
    {"code": "I",   "name": "Drużyna I — Seniorzy", "short_name": "I",
     "color": "#3b8ed0", "sort_order": 1, "is_active": True},
    {"code": "II",  "name": "Drużyna II — Rezerwa", "short_name": "II",
     "color": "#2ecc71", "sort_order": 2, "is_active": True},
    {"code": "AKD", "name": "Akademia",             "short_name": "AKD",
     "color": "#e67e22", "sort_order": 3, "is_active": True},
    {"code": "OLD", "name": "Stara drużyna",        "short_name": "OLD",
     "color": "#888888", "sort_order": 9, "is_active": False},
]

PLAYERS = [
    {"id": "p1", "full_name": "Kowalski", "club_name": "Chełmianka Gdańsk"},
    {"id": "p2", "full_name": "Nowak",    "club_name": "Chełmianka Gdańsk"},
    {"id": "p3", "full_name": "Junior",   "club_name": "Chełmianka Gdańsk"},
    {"id": "p4", "full_name": "Obcokraj", "club_name": "Inny Klub"},
]
TERMS = [
    {"id": "t1", "player_id": "p1", "team_code": "I",   "is_primary": True,
     "left_on": None, "status": "active"},
    {"id": "t2", "player_id": "p1", "team_code": "AKD", "is_primary": False,
     "left_on": None, "status": "active"},      # senior W AKADEMII
    {"id": "t3", "player_id": "p2", "team_code": "II",  "is_primary": True,
     "left_on": None, "status": "active"},
    {"id": "t4", "player_id": "p3", "team_code": "AKD", "is_primary": True,
     "left_on": None, "status": "active"},
]
FITNESS = [
    {"id": "f1", "player_id": "p1", "team_code": "I",  "test_date": "2026-01-15", "beep_level": 8},
    {"id": "f2", "player_id": "p1", "team_code": "I",  "test_date": "2026-02-15", "beep_level": 9},
    {"id": "f3", "player_id": "p1", "team_code": "I",  "test_date": "2026-03-15", "beep_level": 11},
    {"id": "f4", "player_id": "p2", "team_code": "I",  "test_date": "2026-01-10", "beep_level": 7},
    {"id": "f5", "player_id": "p3", "team_code": "AKD", "test_date": "2026-01-11", "beep_level": 6},
]
QUERIES = []          # (tabela, filtry) - do liczenia zapytań w testach
INSERTS = []
PERMS = [
    {"email": "bartek@klub.pl", "role_name": "ADMIN", "team_codes": ["*"]},
    {"email": "trener@klub.pl", "role_name": "COACH",
     "team_codes": ["I", "II"]},
]


class FakeQuery:
    def __init__(self, table):
        self.t = table
        self.filters = {}

    def select(self, *a, **k): return self
    def eq(self, col, val):
        self.filters[col] = val; return self
    def in_(self, col, vals):
        self.filters[col] = vals; return self
    def is_(self, col, val):
        self.filters[col] = val; return self
    def order(self, *a, **k): return self
    def limit(self, n): self.lim = n; return self
    def delete(self): self._delete = True; return self
    def or_(self, cond):
        self.filters["or"] = cond; return self
    def update(self, data):
        self._update = data; return self
    def insert(self, data):
        self._insert = data; return self

    def execute(self):
        QUERIES.append((self.t, dict(self.filters)))
        # ZAPIS ma pierwszeństwo przed odczytem (atrapa)
        if getattr(self, "_insert", None) is not None:
            INSERTS.append((self.t, self._insert))
            if self.t == "player_team_terms":
                # KAŻDY nowy termin musi dostać WŁASNE id - przy stałym
                # 'new' zamykanie jednego terminu zamykało kilka naraz
                rec = dict(self._insert)
                rec.setdefault("id", f"t{len(TERMS) + 1}")
                # ATRAPA EGZEKWUJE INDEKSY UNIKALNE Z BAZY - bez tego
                # testy przejmując błąd uniq_primary_term z produkcji.
                for t in TERMS:
                    same_player = t.get("player_id") == rec.get("player_id")
                    open_term  = not t.get("left_on") and not rec.get("left_on")
                    if same_player and open_term:
                        if (t.get("is_primary") and rec.get("is_primary")):
                            raise Exception("23505 duplicate key value violates "
                                            "unique constraint uniq_primary_term")
                        if t.get("team_code") == rec.get("team_code"):
                            raise Exception("23505 duplicate key value violates "
                                            "unique constraint uniq_active_term")
                TERMS.append(rec)
            if self.t == "user_permissions":
                PERMS.append(dict(self._insert))
            return type("R", (), {"data": [self._insert]})()
        if getattr(self, "_delete", None) is not None:
            if self.t == "teams":
                code = self.filters.get("code")
                TEAMS_DB[:] = [x for x in TEAMS_DB if x.get("code") != code]
            return type("R", (), {"data": []})()
        if getattr(self, "_update", None) is not None:
            if self.t == "player_team_terms":
                tid  = self.filters.get("id")
                pid  = self.filters.get("player_id")
                code = self.filters.get("team_code")
                for t in TERMS:
                    if tid is not None and t.get("id") != tid: continue
                    if pid is not None and t.get("player_id") != pid: continue
                    if code is not None and t.get("team_code") != code: continue
                    t.update(self._update)
            elif self.t == "players":
                pid = self.filters.get("id")
                for pl in PLAYERS:
                    if pid is None or pl.get("id") == pid:
                        pl.update(self._update)
            return type("R", (), {"data": []})()
        if self.t == "rpc":
            # tt_terms_exist() - odpowiada WLASCICIELOWI, wiec atrapa
            # zwraca stan tabeli niezaleznie od uprawnien (tak jak
            # SECURITY DEFINER w bazie).
            return type("R", (), {"data": bool(TERMS)})()
        if self.t == "teams":
            return type("R", (), {"data": list(TEAMS_DB)})()
        if self.t == "player_team_terms":
            if getattr(self, "lim", None):
                return type("R", (), {"data": TERMS[:self.lim]})()
            key = self.filters.get("player_id")
            if key is not None:
                return type("R", (), {"data": [t for t in TERMS
                                               if t["player_id"] == key]})()
            code = self.filters.get("team_code")
            rows = [t for t in TERMS if t["team_code"] == code]
            if self.filters.get("left_on") == "null":
                rows = [t for t in rows if not t.get("left_on")]
            return type("R", (), {"data": rows})()
        if self.t == "fitness_tests":
            rows = [dict(r) for r in FITNESS]
            code = self.filters.get("team_code")
            if code is not None:
                rows = [r for r in rows if r.get("team_code") == code]
            # team_filter() dokłada or_("team_code.is.null,team_code.eq.X")
            cond = self.filters.get("or")
            if isinstance(cond, str) and ".eq." in cond:
                wanted = cond.split(".eq.")[-1]
                rows = [r for r in rows
                        if r.get("team_code") is None
                        or r.get("team_code") == wanted]
            return type("R", (), {"data": rows})()
        if self.t == "user_permissions":
            return type("R", (), {"data": [dict(p) for p in PERMS]})()
        if self.t == "players":
            ids = self.filters.get("id")
            rows = PLAYERS
            if ids:
                rows = [p for p in rows if p["id"] in ids]
            club = self.filters.get("club_name")
            if club:
                rows = [p for p in rows if p["club_name"] == club]
            return type("R", (), {"data": rows})()
        return type("R", (), {"data": []})()


class FakeSupabase:
    def table(self, name): return FakeQuery(name)
    def rpc(self, *a, **k): return FakeQuery("rpc")


teams._supabase = lambda: FakeSupabase()
cache_manager.get_supabase = lambda: FakeSupabase()
cache_manager.get_database = lambda: type("DB", (), {
    "CURRENT_CLUB": "Chełmianka Gdańsk"})()

ok, fail = 0, 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        print(f"  ✅ {name}"); ok += 1
    else:
        print(f"  ❌ {name} {extra}"); fail += 1


print("\n=== 1. Uprawnienia trenera ===")
teams.set_allowed_teams(["AKD"])
check("widoczna tylko akademia",
      [t["code"] for t in teams.visible_teams(include_all=False)] == ["AKD"])
check("nie widzi drużyny I", not teams.can_see_team("I"))
check("przełącznik na 'brak dostępu' jest ODRZUCANY",
      teams.set_current_team("I") is False)
check("może przejść na AKD", teams.set_current_team("AKD") is True)

teams.set_allowed_teams(["*"])
codes = [t["code"] for t in teams.visible_teams()]
check("kierownik widzi 'Wszystkie drużyny' + 3 aktywne",
      codes == ["*", "I", "II", "AKD"], f"(jest {codes}) - archiwum 'OLD' jest ukryte")
check("może wejść na I", teams.set_current_team("I") is True)

print("\n=== 2. Klucze cache per drużyna ===")
teams.set_current_team("I")
scope_I = cache_manager.cache._scope()
teams.set_current_team("II")
scope_II = cache_manager.cache._scope()
check("dwie drużyny = dwa różne klucze", scope_I != scope_II,
      f"({scope_I} vs {scope_II})")
check("klucz zawiera kod drużyny", scope_I.endswith("|I"))

print("\n=== 3. Kadra drużyny ===")
teams.set_current_team("I")
cache_manager.cache.invalidate_all(reason="test")
kadra_I = cache_manager.cache.get_players(force_refresh=True)
check("drużyna I = 1 zawodnik (Kowalski)",
      [p["full_name"] for p in kadra_I] == ["Kowalski"],
      f"({[p['full_name'] for p in kadra_I]})")

teams.set_current_team("AKD")
kadra_AKD = cache_manager.cache.get_players(force_refresh=True)
names = sorted(p["full_name"] for p in kadra_AKD)
check("akademia = Kowalski + Junior (senior wciąż w kadrze!)",
      names == ["Junior", "Kowalski"], f"({names})")

teams.set_current_team(teams.ALL_TEAMS)
wszyscy = cache_manager.cache.get_players(force_refresh=True)
check("tryb 'wszystkie' = 3 zawodnicy klubu (obcokrajnik wykluczony)",
      sorted(p["full_name"] for p in wszyscy) == ["Junior", "Kowalski", "Nowak"],
      f"({sorted(p['full_name'] for p in wszyscy)})")

print("\n=== 4. Filtr team_code dla PostgREST ===")
q = FakeQuery("events")
teams.set_current_team("I")
filtered = teams.team_filter(q, "events")
check("dla drużyny I generuje warunek 'club is null albo = I'",
      filtered.filters.get("or") == "team_code.is.null,team_code.eq.I",
      f"({filtered.filters.get('or')})")
teams.set_current_team(teams.ALL_TEAMS)
q2 = teams.team_filter(FakeQuery("events"), "events")
check("w trybie 'wszystkie' brak filtra", "or" not in q2.filters)

print("\n=== 5. Reguła wpisów wspólnych (team_code NULL) ===")
wspolny = {"team_code": None}
akademia = {"team_code": "AKD"}
teams.set_current_team("I")
check("wpis NULL (stare dane) widoczny w każdej drużynie",
      teams.row_matches_team(wspolny))
check("wpis z AKD NIE widoczny w drużynie I",
      not teams.row_matches_team(akademia))

print("\n=== 6. Przypisanie gracza (bez przenoszenia) ===")
before = len(TERMS)
ok1, msg1 = teams.assign_player("p2", "AKD")
check("Nowak trafił też do akademii", ok1, f"({msg1})")
check("w bazie jest teraz 5 terminów", len(TERMS) == before + 1)
check("termin ma is_primary=False (nie ma drugiej drużyny głównej)",
      TERMS[-1]["is_primary"] is False, f"({TERMS[-1]})")

ok2, msg2 = teams.assign_player("p2", "AKD")
check("powtórne przypisanie nie duplikuje", ok2 and len(TERMS) == before + 1,
      f"({msg2})")

print("\n=== 7. Drużyna główna i uprawnienia ===")
check("primary_team_of(Kowalski) = I", teams.primary_team_of("p1") == "I")
check("player_team_names(Kowalski) = 2 drużyny",
      len(teams.player_team_names("p1")) == 2,
      f"({teams.player_team_names('p1')})")

print("\n=== 8. Usuwanie z kadry (gracz zostaje w klubie) ===")
ok_r, msg_r = teams.remove_player_from_team("p3", "AKD")
check("nie można zostawić gracza bez żadnej drużyny", ok_r is False, f"({msg_r})")
check("komunikat tłumaczy dlaczego", "jednej drużynie" in msg_r, f"({msg_r})")

ok_r, msg_r = teams.remove_player_from_team("p2", "AKD")
check("Nowak wypisany z akademii", ok_r, f"({msg_r})")
closed = [t for t in TERMS
          if t["player_id"] == "p2" and t["team_code"] == "AKD"]
check("termin zamknięty (left_on), nie skasowany",
      closed and closed[0].get("left_on") and closed[0]["status"] == "inactive",
      f"({closed})")
check("gracz nadal ma drużynę II",
      teams.primary_team_of("p2") == "II",
      f"({teams.primary_team_of('p2')})")

print("\n=== 9. Ustawianie drużyn (dodaj / usuń / główna) ===")
ok_s, msg_s = teams.set_player_memberships("p2", ["I", "II"], "I")
check("Nowak dodany do I i zostaje w II", ok_s, f"({msg_s})")
mine = sorted(t["team_code"] for t in teams.get_active_terms("p2"))
check("aktywne drużyny = I + II", mine == ["I", "II"], f"(jest {mine})")
check("drużyna główna przeniesiona na I",
      teams.primary_team_of("p2") == "I")
check("termin w I ma is_primary=True",
      any(t["team_code"] == "I" and t["is_primary"]
          for t in teams.get_active_terms("p2")))

ok_s, msg_s = teams.set_player_memberships("p2", ["II"], "II")
check("usunięcie z I działa jednym wywołaniem", ok_s, f"({msg_s})")
mine = sorted(t["team_code"] for t in teams.get_active_terms("p2"))
check("aktywne drużyny = tylko II", mine == ["II"], f"(jest {mine})")
closed_i = [t for t in TERMS
            if t["player_id"] == "p2" and t["team_code"] == "I"
            and t.get("left_on")]
check("termin w I zamknięty z datą", bool(closed_i))
check("w historii jest wpis o przeniesieniu",
      any(tbl == "player_transfers" for tbl, _ in INSERTS))

ok_s, msg_s = teams.set_player_memberships("p2", [], None)
check("pusta lista jest odrzucana", ok_s is False, f"({msg_s})")

ok_s, msg_s = teams.set_player_memberships("p2", ["OLD"], "OLD")
check("drużyna archiwalna jest odrzucana", ok_s is False, f"({msg_s})")

ok_s, msg_s = teams.set_player_memberships("p2", ["II"], "II")
check("powtórny zapis bez zmian nie psuje kadry", ok_s, f"({msg_s})")
check("nadal tylko II",
      [t["team_code"] for t in teams.get_active_terms("p2")] == ["II"])

print("\n=== 10. Gracz w dwóch drużynach naraz ===")
ok_a, msg_a = teams.set_player_memberships("p1", ["I", "AKD"], "I")
check("senior zostaje seniorem i akademikiem", ok_a, f"({msg_a})")
check("dwie aktywne drużyny",
      sorted(t["team_code"] for t in teams.get_active_terms("p1")) == ["AKD", "I"])
check("kadra I nadal go widzi", "p1" in teams.get_team_player_ids("I", True))
check("kadra AKD też go widzi", "p1" in teams.get_team_player_ids("AKD", True))

print("\n=== 11. Pusta drużyna NIE pokazuje całego klubu ===")
check("w bazie są terminy kadry", teams.has_any_terms() is True)
teams.set_current_team("II")
ids_ii = teams.get_team_player_ids("II", force_refresh=True)
check("drużyna II ma tylko Nowaka", ids_ii == {"p2"}, f"(jest {ids_ii})")
teams.set_current_team("AKD")
check("akademia ma Kowalskiego i Juniora",
      teams.get_team_player_ids("AKD", True) == {"p1", "p3"},
      f'(jest {teams.get_team_player_ids("AKD", True)})')
teams.set_current_team("I")
check("drużyna I ma tylko Kowalskiego",
      teams.get_team_player_ids("I", True) == {"p1"},
      f'(jest {teams.get_team_player_ids("I", True)})')
check("Junior NIE jest nagle w drużynie I", "p3" not in
      teams.get_team_player_ids("I", True))

print("\n=== 12. Usuwanie drużyny ===")
ok_d, msg_d = teams.delete_team("AKD")
check("akademia usunięta", ok_d, f"({msg_d})")
check("nie ma jej już na liście",
      [t["code"] for t in teams.get_teams()] == ["I", "II", "OLD"],
      f"({[t['code'] for t in teams.get_teams()]})")
check("termin Juniora zamknięty",
      all(t.get("left_on") for t in TERMS if t["team_code"] == "AKD"))
check("Junior został przypisany do drużyny I",
      teams.primary_team_of("p3") == "I",
      f"({teams.primary_team_of('p3')})")
check("Junior dostał aktywny termin w zapasowej drużynie",
      [t["team_code"] for t in teams.get_active_terms("p3")] == ["I"],
      f'({[t["team_code"] for t in teams.get_active_terms("p3")]})')
check("kadra drużyny I widzi teraz Juniora",
      "p3" in teams.get_team_player_ids("I", True))

ok_d, msg_d = teams.delete_team("NIEISTNIEJACA")
check("usuwanie nieistniejącej drużyny jest błędem", ok_d is False)

for t in list(TEAMS_DB):
    if t["code"] != "I":
        TEAMS_DB.remove(t)
ok_d, msg_d = teams.delete_team("I")
check("ostatniej drużyny nie można usunąć", ok_d is False, f"({msg_d})")

print("\n=== 13. Jedna drużyna główna (uniq_primary_term) ===")
# test 12 usunął AKD - tutaj zakładamy ją z powrotem
TEAMS_DB[:] = [t for t in TEAMS_DB if t.get("code") != "AKD"]
TEAMS_DB.append({"code": "AKD", "name": "Akademia", "short_name": "AKD",
                 "color": "#e67e22", "sort_order": 3, "is_active": True})
TEAMS_DB[:] = [t for t in TEAMS_DB if t.get("code") != "II"]
TEAMS_DB.append({"code": "II", "name": "Drużyna II — Rezerwa",
                 "short_name": "II", "color": "#2ecc71", "sort_order": 2,
                 "is_active": True})
teams.get_teams(force_refresh=True)
teams.set_player_memberships("p1", ["I"], "I")
check("Kowalski tylko w I", teams.primary_team_of("p1") == "I")

ok_x, msg_x = teams.set_player_memberships("p1", ["I", "AKD"], "AKD")
check("dodanie AKD jako głównej NIE wywala się o uniq_primary_term",
      ok_x, f"({msg_x})")
act = [t for t in teams.get_active_terms("p1")]
prim = [t["team_code"] for t in act if t.get("is_primary")]
check("dokładnie jedna drużyna główna", prim == ["AKD"], f"(jest {prim})")
check("w players też AKD",
      [p for p in PLAYERS if p["id"] == "p1"][0].get("primary_team_code")
      == "AKD")

ok_y, msg_y = teams.remove_player_from_team("p1", "AKD")
check("usunięcie drużyny głównej nie zostawia gracza bez głównej",
      ok_y, f"({msg_y})")
act = [t for t in teams.get_active_terms("p1")]
prim = [t["team_code"] for t in act if t.get("is_primary")]
check("I przejęła rolę głównej", prim == ["I"], f"(jest {prim})")

ok_z, msg_z = teams.set_player_memberships("p1", ["I", "AKD", "II"], "II")
check("trzy drużyny, jedna główna", ok_z, f"({msg_z})")
prim = [t["team_code"] for t in teams.get_active_terms("p1")
        if t.get("is_primary")]
check("główna = II", prim == ["II"], f"(jest {prim})")
check("trzy aktywne terminy",
      len(teams.get_active_terms("p1")) == 3)

ok_w, msg_w = teams.set_player_memberships("p1", ["II"], "II")
check("została jedna drużyna", ok_w, f"({msg_w})")
_got=[(t["team_code"], t.get("is_primary")) for t in teams.get_active_terms("p1")]
check("nadal jedna główna",
      [t["team_code"] for t in teams.get_active_terms("p1")
       if t.get("is_primary")] == ["II"], f"({_got})")
check("zamknięte terminy zachowane w historii",
      len([t for t in TERMS if t["player_id"] == "p1" and t.get("left_on")]) >= 2)

print("\n=== 14. Etykiety drużyn (skrót, nie kod i nie pełna nazwa) ===")
check("skrót drużyny I", teams.team_label("I") == "I", f'({teams.team_label("I")})')
check("skrót drużyny II", teams.team_label("II") == "II", f'({teams.team_label("II")})')
check("w sidebarze skrót + nazwa",
      teams.team_label("I", with_name=True) == "I — Drużyna I — Seniorzy",
      f'({teams.team_label("I", with_name=True)})')

# drużyna o krótszym skrócie (A1 / AI) i bez skrótu
TEAMS_DB[:] = [t for t in TEAMS_DB if t.get("code") not in ("AKD", "II")]
TEAMS_DB.append({"code": "AKD", "name": "Akademia", "short_name": "A1",
                 "color": "#e67e22", "sort_order": 3, "is_active": True})
TEAMS_DB.append({"code": "OLD", "name": "Stara drużyna", "short_name": "AI",
                 "color": "#888888", "sort_order": 9, "is_active": False})
TEAMS_DB.append({"code": "BEZS", "name": "Bez skrótu", "short_name": "",
                 "color": "#888888", "sort_order": 10, "is_active": True})
teams.get_teams(force_refresh=True)
check("skrót A1 ma pierwszeństwo przed nazwą",
      teams.team_label("AKD") == "A1", f'({teams.team_label("AKD")})')
check("skrót AI (drużyna archiwalna)",
      teams.team_label("OLD") == "AI", f'({teams.team_label("OLD")})')
check("gdy brak skrótu, pokazuje nazwę",
      teams.team_label("BEZS") == "Bez skrótu",
      f'({teams.team_label("BEZS")})')
check("nieznany kod wraca sam do siebie",
      teams.team_label("XYZ") == "XYZ")
check("brak skrótu nie wywala get_team_label",
      teams.team_short("BEZS") == "Bez skrótu")

print("\n=== 15. Dostęp do drużyn per użytkownik ===")
TEAMS_DB[:] = [t for t in TEAMS_DB if t.get("code") in ("I", "OLD", "BEZS")]
TEAMS_DB.append({"code": "II", "name": "Drużyna II — Rezerwa",
                 "short_name": "II", "color": "#2ecc71", "sort_order": 2,
                 "is_active": True})
TEAMS_DB.append({"code": "III", "name": "Drużyna III", "short_name": "III",
                 "color": "#e74c3c", "sort_order": 4, "is_active": True})
teams.get_teams(force_refresh=True)

teams.set_allowed_teams(["II"])
check("widzi tylko drużynę II",
      [t["code"] for t in teams.visible_teams(include_all=False)] == ["II"],
      f'({[t["code"] for t in teams.visible_teams(include_all=False)]})')
check("nie widzi drużyny I", not teams.can_see_team("I"))
check("nie widzi drużyny III", not teams.can_see_team("III"))
check("przełącznik na I odrzucony", teams.set_current_team("I") is False)
check("przełącznik na III odrzucony", teams.set_current_team("III") is False)
check("przełącznik na II przyjęty", teams.set_current_team("II") is True)

teams.set_allowed_teams([])
check("pusta lista = brak dostępu (nie wszystkie!)",
      teams.visible_teams(include_all=False) == [],
      f'({teams.visible_teams(include_all=False)})')
check("nie widzi żadnej drużyny", not teams.can_see_team("I"))
check("nawet '*' nie przechodzi", not teams.can_see_team("*"))

teams.set_allowed_teams(None)
check("None = jeszcze nie wiadomo -> wszystkie",
      teams.get_allowed_teams() == ["*"],
      f'({teams.get_allowed_teams()})')
teams.set_allowed_teams(["I", "III"])
check("dostęp do dwóch z trzech",
      [t["code"] for t in teams.visible_teams(include_all=False)]
      == ["I", "III"])
check("archiwum niewidoczne mimo dostępu",
      "OLD" not in [t["code"] for t in teams.visible_teams(include_all=False)])
teams.set_allowed_teams(["*"])

print("\n=== 16. Jedno zapytanie zamiast N (Centrum Rozwoju) ===")
teams.set_allowed_teams(["*"])
teams.set_current_team("I")

QUERIES.clear()
hist = cache_manager.cache.get_fitness_history_all(force_refresh=True)
n_first = len([q for q in QUERIES if q[0] == "fitness_tests"])
check("historia pobrana JEDNYM zapytaniem", n_first == 1, f"(było {n_first})")
check("gracz ma swoje testy", len(hist.get("p1", [])) == 3, f'({hist.get("p1")})')
check("testy innej drużyny NIE trafiają do słownika", "p3" not in hist)
check("historia posortowana rosnąco (dla porównania z poprzednim)",
      [t["test_date"] for t in hist.get("p1", [])] ==
      sorted(t["test_date"] for t in hist.get("p1", [])))
check("powiązanie poprzedni/obecny działa na słowniku",
      hist["p1"][-2]["beep_level"] == 9 and hist["p1"][-1]["beep_level"] == 11)

QUERIES.clear()
cache_manager.cache.get_fitness_history_all()
check("drugie wywołanie z cache - ZERO zapytań",
      len([q for q in QUERIES if q[0] == "fitness_tests"]) == 0)

QUERIES.clear()
for _ in range(10):
    teams.has_any_terms()
terms_q = len([q for q in QUERIES
               if q[0] == "player_team_terms" and "limit" in q[1]])
check("has_any_terms: 10 wywołań = max 1 zapytanie (cache 60 s)",
      terms_q <= 1, f"({terms_q} zapytań)")

print("\n=== 17. Nowy trener ląduje na SWOJEJ drużynie ===")
# BUG Z KONSOLI: jan@klub.pl ma team_codes={'1'} i nie ma zapamiętanej
# preferencji -> set_current_team(None) nic nie ustawiał i trener zostawał
# na drużynie poprzedniego użytkownika, do której nie ma dostępu.
teams.set_allowed_teams(["*"])
teams.set_current_team("II")          # zostawiamy cudzą drużynę
teams.set_allowed_teams(["III"])       # ...i logujemy trenera z drużyny III
check("po zalogowaniu aktywna drużyna jest WIDOCZNA dla trenera",
      teams.can_see_team(teams.get_current_team()),
      f'(jest "{teams.get_current_team()}")')
check("to nie jest drużyna poprzedniego użytkownika",
      teams.get_current_team() != "II", f'(jest "{teams.get_current_team()}")')

teams.set_allowed_teams(["I"])
teams.reset_current_team()
check("reset_current_team() wybiera pierwszą dozwoloną",
      teams.get_current_team() == "I", f'(jest "{teams.get_current_team()}")')

teams.set_allowed_teams(["*"])
teams.set_current_team("II")
teams.set_allowed_teams(["II", "I"])
teams.reset_current_team()
check("reset_current_team() nie wybiera niedozwolonej",
      teams.can_see_team(teams.get_current_team()))

teams.set_allowed_teams(["*"])
teams.set_current_team("I")

print("\n=== 18. Ochrona cudzej kadry (jan@klub.pl = tylko drużyna III) ===")
# UWAGA: NIE nazywaj tu zmiennej 'ok' - to globalny licznik testów.
teams.set_allowed_teams(["*"])
teams.set_current_team("I")

# Symulacja jan@klub.pl: team_codes={'III'}
teams.set_allowed_teams(["III"])
teams.reset_current_team()
check("Jan jest na drużynie III",
      teams.get_current_team() == "III", f'(jest "{teams.get_current_team()}")')

res, msg = teams.assign_player("p1", "I")
check("NIE MOŻE dodać gracza do drużyny I", res is False)
check("komunikat mówi o braku dostępu", "dostęp" in msg.lower(), f'("{msg}")')
check("termin w drużynie I NIE powstał",
      not any(t["team_code"] == "I" for t in TERMS
              if t["player_id"] == "p1" and not t.get("left_on")))

res, msg = teams.move_player("p2", "I")
check("NIE MOŻE przenieść gracza do drużyny I", res is False)

res, msg = teams.set_player_memberships("p1", ["I", "III"], primary="I")
check("NIE MOŻE zapisać kadry z cudzą drużyną I", res is False)

res, msg = teams.remove_player_from_team("p3", "I")
check("NIE MOŻE wyrzucić gracza z drużyny I", res is False)

res, msg = teams.delete_team("I")
check("NIE MOŻE usunąć drużyny I", res is False)

# Gracz będący jednocześnie w I i III - zapis nie może zamknąć mu I
TERMS.append({"id": "tX", "player_id": "p4", "team_code": "I",
              "is_primary": True, "left_on": None, "status": "active"})
res, msg = teams.set_player_memberships("p4", ["III"], primary="III")
check("nie zamyka członkostwa w cudzej drużynie (nawet przy 'zostaw tylko III')",
      res is False, f'({msg})')
check("termin w I nadal aktywny",
      any(t["team_code"] == "I" and not t.get("left_on")
          for t in TERMS if t["player_id"] == "p4"))

# To, co JAN MOŻE, nadal działa (gracz, którego NIE ma w cudzej drużynie)
res, msg = teams.assign_player("p9", "III")
check("w swojej drużynie III dodawać MOŻE", res is True, f'({msg})')
res, msg = teams.set_player_memberships("p9", ["III"], primary="III")
check("kadrę w swojej drużynie zapisać MOŻE", res is True, f'({msg})')
res, msg = teams.move_player("p9", "III")
check("przeniesienie wewnątrz swojej drużyny zgłasza 'już jest' (nie błąd)",
      res is False and "już" in msg.lower(), f'({msg})')

# ...a gracz współdzielony z cudzą drużyną pozostaje nietknięty dla Jana
res, msg = teams.remove_player_from_team("p3", "I")
check("nie wyrzucił gracza z cudzej drużyny I (p3 jest też w I)", res is False)

teams.set_allowed_teams(["*"])
teams.set_current_team("I")
check("kierownik z '*' wciąż ma pełne uprawnienia",
      teams.can_edit_team("I") and teams.can_edit_team("II")
      and teams.can_edit_team("III"))

print("\n=== 12. TRENER BEZ 'players' NIE WIDZI CAŁEGO KLUBU (regresja) ===")
# ZGLOSZENIE: na Finansach po przełączeniu drużyny widać było wszystkich
# graczy z drużyny I. Przyczyna: zapytanie kadry wracało puste (RLS nie
# pokazuje terminów trenerowi bez zakładki 'players'), a aplikacja
# traktowała to jako "brak migracji" i pokazywała CAŁY KLUB.
# Naprawa: RPC tt_terms_exist() odpowiada z poziomu właściciela.
import types as _types

_zapytane = []

class _Q:
    def __init__(s, t): s.t = t
    def select(s, *a, **k): return s
    def eq(s, c, v): return s
    def in_(s, c, v): return s
    def is_(s, c, v): return s
    def limit(s, n): return s
    def execute(s):
        _zapytane.append(s.t)
        if s.t == "rpc":
            # terminy ISTNIEJA w bazie, ale ten uzytkownik ich nie widzi
            return _types.SimpleNamespace(data=True)
        if s.t == "player_team_terms":
            return _types.SimpleNamespace(data=[])      # RLS ukrywa
        if s.t == "players":
            return _types.SimpleNamespace(data=[{"id": "x", "name": "OBCY"}])
        return _types.SimpleNamespace(data=[])

class _C:
    def table(s, n): return _Q(n)
    def rpc(s, n): return _Q("rpc")

_stary_supabase = teams._supabase
_stary_run = cache_manager.cache._run_query
_stary_terms_at = teams._state["terms_checked_at"]
try:
    teams._supabase = lambda: _C()
    cache_manager.cache._run_query = lambda fn, label="": fn()
    teams._state["terms_checked_at"] = 0          # wymuś świeże sprawdzenie
    teams.set_allowed_teams(["*"])
    teams.set_current_team("II")
    cache_manager.cache.invalidate_players()
    _wynik = cache_manager.cache.get_players(force_refresh=True)
    check("pusta/obcięta kadra = pusta lista, nie cały klub", _wynik == [])
    check("nie odpytuje w ogóle tabeli players", "players" not in _zapytane)
finally:
    teams._supabase = _stary_supabase
    cache_manager.cache._run_query = _stary_run
    teams._state["terms_checked_at"] = _stary_terms_at
    cache_manager.cache.invalidate_players()

print(f"\n{'='*50}\nWYNIK: {ok} OK, {fail} błędów\n{'='*50}")
sys.exit(1 if fail else 0)