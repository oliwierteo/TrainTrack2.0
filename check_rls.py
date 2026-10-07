"""
check_rls.py — walidator PL/pgSQL, którego NIE robi parser SQL.

Parser (pglast) akceptuje napis, którego Postgres potem nie skompiluje.
Najczęstszy błąd z tej klasy:

    raise warning 'tekst (%). tekst: %', sqlerrm;
    --  dwa znaczniki %, JEDEN argument -> ERROR 42601
       "too few parameters specified for RAISE"

Ten skrypt liczy znaczniki % i argumenty w KAŻDEJ instrukcji RAISE
we wszystkich plikach SQL i zgłasza rozjazd.

Użycie:  python3 check_rls.py [plik.sql ...]
"""
import re
import sys
import pathlib

LEVELS = ("debug", "log", "info", "notice", "warning", "exception")

# 'tekst %s' 'więcej %s'  ->  jeden literał po konkatenacji
STR = re.compile(r"'(?:[^']|'')*'", re.S)


def _split_args(tail: str):
    """Rozbija listę argumentów RAISE po przecinkach (głębokość nawiasów)."""
    args, depth, cur, i = [], 0, "", 0
    while i < len(tail):
        ch = tail[i]
        if ch in "([": depth += 1
        elif ch in ")]": depth -= 1
        if ch == "," and depth == 0:
            args.append(cur.strip()); cur = ""
        else:
            cur += ch
        i += 1
    if cur.strip():
        args.append(cur.strip())
    return [a for a in args if a]


def check_format(sql: str, label: str):
    """
    format('tekst %I %L', a, b) - tyle samo placeholderów co argumentów.
    Niezgodność to błąd w TRAKCIE wykonania (nie kompilacji), więc parser
    SQL jej nie zauważy, a w bazie wywala w połowie skryptu.
    """
    problems = []
    sql = re.sub(r"--[^\n]*", "", sql)
    for m in re.finditer(r"\bformat\s*\(", sql, re.I):
        i = m.end(); depth = 1; out = ""
        while i < len(sql) and depth > 0:
            ch = sql[i]
            if ch == "'":
                sm = STR.match(sql, i)
                if sm:
                    out += sm.group(0); i += len(sm.group(0)); continue
            if ch == "(": depth += 1
            elif ch == ")": depth -= 1
            if depth > 0: out += ch
            i += 1
        stmt = out.strip().rstrip(",")
        if not stmt.startswith("'"):
            continue                      # format z samą zmienną - pomijamy
        lits, pos, last_end = [], 0, None
        for sm in STR.finditer(stmt):
            if stmt[last_end:sm.start()].strip():
                break                     # coś nie-literalnego przed spójnikiem
            lits.append(sm.group(0)); last_end = sm.end()
        if not lits:
            continue
        text = "".join(lits)
        text_plain = "".join(STR.findall(text))
        args = _split_args(stmt[last_end:].lstrip().lstrip(","))
        n_ph = len(re.findall(r"%(?!%)", text_plain))
        n_ph = n_ph if n_ph else None
        # format domyślnie nie wymaga kompletności, ale nadmiar argumentów
        # i tak jest błędem logicznym - zgłaszamy tylko wyraźne rozjazdy
        if n_ph is not None and n_ph != len(args):
            line = sql[:m.start()].count("\n") + 1
            problems.append(
                f"{label}:{line}  format(): {n_ph} placeholder(ów) "
                f"vs {len(args)} argument(ów)\n    {stmt.strip()[:100]}")
    return problems


def check_text(sql: str, label: str):
    problems = []
    # Usuwamy komentarze liniowe, żeby '-- % coś' nie psuł liczenia
    sql = re.sub(r"--[^\n]*", "", sql)
    for m in re.finditer(r"\braise\b\s+(" + "|".join(LEVELS) + r")\b",
                         sql, re.I):
        level = m.group(1)
        # Koniec instrukcji: ';' na poziomie 0 nawiasów (poza $$ i cudzysłowami)
        i = m.end()
        depth, out = 0, ""
        while i < len(sql):
            ch = sql[i]
            if ch == "'":
                sm = STR.match(sql, i)
                out += sm.group(0) if sm else ch
                i = i + len(sm.group(0)) if sm else i + 1
                continue
            if ch in "([": depth += 1
            elif ch in ")]": depth -= 1
            out += ch
            i += 1
            if ch == ";" and depth <= 0:
                break
        stmt = out[:-1] if out.endswith(";") else out

        # Rozdziel literał od argumentów
        parts, pos, lits = [], 0, []
        for sm in STR.finditer(stmt):
            parts.append(("lit", sm.group(0), sm.start(), sm.end()))
        # tekst przed pierwszym literałem musi być pusty
        first = parts[0][2] if parts else None
        if first is None:
            continue
        if stmt[:first].strip():
            continue   # RAISE bez tekstu (np. RAISE NOTICE;) — pomijamy

        # Scalamy sąsiednie literały (konkatenacja w Postgresie)
        i = 0
        while i < len(parts):
            j = i
            joined = parts[i][1]
            end = parts[i][3]
            while (j + 1 < len(parts)
                   and stmt[end:parts[j + 1][2]].strip() == ""):
                joined += parts[j + 1][1]
                end = parts[j + 1][3]
                j += 1
            lits.append((joined, parts[i][2], end))
            i = j + 1
        text, tstart, tend = lits[0]
        text_plain = "".join(STR.findall(text))   # bez cudzysłowów
        placeholders = len(re.findall(r"%(?!%)", text_plain))
        tail = stmt[tend:].lstrip()
        if tail.startswith(","):
            tail = tail[1:]
        args = _split_args(tail)
        if placeholders != len(args):
            line = sql[:m.start()].count("\n") + 1
            # policz numer linię na surowym pliku (bez komentarzy)
            line += 0
            problems.append(
                f"{label}:{line}  RAISE {level.upper()}: "
                f"{placeholders} znacznik(ów) % vs {len(args)} argument(ów)\n"
                f"    {stmt.strip()[:110]}")
    return problems


def check_transakcyjnosc(raw, label):
    """set_config(..., true) żyje TYLKO do końca transakcji.

    Dwa realne błędy, które przeszły przez pglast (składnia jest poprawna):
      1. commit PRZED zapytaniem wynikowym -> current_setting() zwraca NULL
         i wszystkie komórki raportu są puste.
      2. set_config zapisany, a nigdzie nieprzeczytany albo odczytany
         spoza zakresu, w którym został ustawiony.
    """
    problems = []
    sql = re.sub(r"--[^\n]*", "", raw)
    # pozycja commitu (bez komentarzy)
    commit_pos = -1
    for m in re.finditer(r"\bcommit\s*;", sql, re.I):
        commit_pos = m.start()
        break
    if commit_pos != -1:
        for m in re.finditer(r"current_setting\('tt\.", sql, re.I):
            if m.start() > commit_pos:
                line = raw[:m.start()].count("\n") + 1
                problems.append(
                    f"{label}:{line}  current_setting() PO commit "
                    f"- set_config(..., true) nie przetrwa COMMIT, "
                    f"komórka będzie pusta\n"
                    f"    {sql[m.start():m.start() + 70].splitlines()[0]}")
                break
    # FOREACH po polu rekordu, którego nigdy nie przypisano
    for m in re.finditer(r"foreach\s+([a-z_]\w*)\.(\w+)\s+in\s+array", sql, re.I):
        line = raw[:m.start()].count("\n") + 1
        problems.append(
            f"{label}:{line}  FOREACH po polu '{m.group(1)}.{m.group(2)}' "
            f"- pole rekordu nigdy nie przypisane, wywala się "
            f"'record \"{m.group(1)}\" is not assigned yet'; "
            f"użyj zwykłej zmiennej tekstowej\n"
            f"    {sql[m.start():m.start() + 60].splitlines()[0]}")
    return problems


def _kolumny(fragment: str):
    """Liczba kolumn na najwyższym poziomie nawiasów (poza napisami)."""
    depth, n, i = 0, 1, 0
    while i < len(fragment):
        ch = fragment[i]
        if ch == "'":
            m = re.match(r"'(?:[^']|'')*'", fragment[i:], re.S)
            if m:
                i += len(m.group(0)); continue
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "," and depth == 0:
            n += 1
        i += 1
    return n


def check_union(raw, label):
    """UNION ALL z gałęziami o różnej liczbie kolumn.

    Postgres: ERROR 42601 "each UNION query must have the same number of
    columns". pglast tego NIE łapie - sprawdza składnię, nie kolumny.
    """
    problems = []
    sql = re.sub(r"--[^\n]*", "", raw)
    for m in re.finditer(r"\bunion\s+all\b", sql, re.I):
        # gałąź przed: od ostatniego SELECT po poprzedni UNION/;/koniec
        start = max(sql.rfind(";", 0, m.start()),
                    sql.rfind("union all", 0, m.start()),
                    sql.rfind("union", 0, m.start()))
        if start == -1:
            start = 0          # pierwsze UNION w pliku - nie ma cofnięcia
        prev = sql[start:m.start()]
        ps = prev.rfind("select")
        if ps == -1:
            continue
        # gałąź po: do następnego UNION albo średnika na tym poziomie
        rest = sql[m.end():]
        depth, cut = 0, len(rest)
        i = 0
        while i < len(rest):
            ch = rest[i]
            if ch == "'":
                mm = re.match(r"'(?:[^']|'')*'", rest[i:], re.S)
                if mm:
                    i += len(mm.group(0)); continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif depth == 0 and ch == ";":
                cut = i; break
            elif depth == 0 and re.match(r"union\b", rest[i:], re.I):
                cut = i; break
            i += 1
        nxt = rest[:cut]
        ns = nxt.find("select")
        if ns == -1:
            continue
        a, b = _kolumny(prev[ps:]), _kolumny(nxt[ns:])
        if a != b:
            line = raw[:m.start()].count("\n") + 1
            problems.append(
                f"{label}:{line}  UNION ALL: gałąź ma {a} kolumn(y), "
                f"następna {b} -> ERROR 42601 "
                f"'each UNION query must have the same number of columns'")
    return problems


def main():
    files = sys.argv[1:] or sorted(str(p) for p in
                                   pathlib.Path(__file__).parent.glob("*.sql"))
    all_problems = []
    for f in files:
        raw = pathlib.Path(f).read_text(encoding="utf-8")
        p = check_text(raw, f) + check_format(raw, f) + check_transakcyjnosc(raw, f) + check_union(raw, f)
        all_problems += p
        print(f"{'❌' if p else '✅'} {f}" + (f" — {len(p)} błędów" if p else ""))
    if all_problems:
        print("\n" + "=" * 60)
        print("\n".join(all_problems))
        print("=" * 60)
        return 1
    print("\n✅ RAISE, format(), UNION i transakcyjność set_config są poprawne.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
