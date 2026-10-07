# development_center_view.py

import customtkinter as ctk
import database
from database import supabase
import threading
from datetime import datetime, date

COLORS = {
    "bg_dark": "#121212",
    "card_bg": "#1e1e1e",
    "accent": "#3b8ed0",
    "success": "#2ecc71",
    "warning": "#f39c12",
    "danger": "#e74c3c",
    "info": "#3498db",
}

ABILITY_COLORS = {
    "strzelec": "#e74c3c",
    "drybler": "#9b59b6",
    "kreator": "#3498db",
    "wojownik": "#e67e22",
    "bramkarz": "#2ecc71",
}

# ════════════════════════════════════════════════════════════
# NORMY DLA DOROSŁYCH 18+ (profesjonalne i amatorskie)
# ════════════════════════════════════════════════════════════
BEEP_TEST_NORMS = {
    "pro_elite":   {"min_level": 13, "min_shuttle": 1,  "label": "⭐ Pro: Elita",       "color": "#FFD700", "desc": "Zawodowcy top-liga (Premier League, La Liga)"},
    "pro_good":    {"min_level": 11, "min_shuttle": 1,  "label": "🏆 Pro: Dobry",        "color": "#2ecc71", "desc": "Zawodowcy niższe ligi, dobrzy amatorzy"},
    "pro_average": {"min_level": 9,  "min_shuttle": 1,  "label": "✅ Pro: Przeciętny",   "color": "#3498db", "desc": "Minimalny poziom półzawodowy"},
    "am_good":     {"min_level": 7,  "min_shuttle": 6,  "label": "🟢 Amateur: Dobry",    "color": "#27ae60", "desc": "Dobra forma, regularny trening"},
    "am_average":  {"min_level": 6,  "min_shuttle": 1,  "label": "📊 Amateur: Średni",   "color": "#f39c12", "desc": "Przeciętna sprawność dorosłego aktywnego"},
    "am_below":    {"min_level": 4,  "min_shuttle": 6,  "label": "⚠️ Amateur: Słaby",    "color": "#e67e22", "desc": "Poniżej przeciętnej, wymaga pracy"},
    "poor":        {"min_level": 0,  "min_shuttle": 0,  "label": "🔴 Niewystarczający",  "color": "#e74c3c", "desc": "Bardzo słaba kondycja, konieczna poprawa"},
}

SHUTTLE_150M_NORMS = {
    "pro_elite":   {"max_seconds": 26.0, "label": "⭐ Pro: Elita",       "color": "#FFD700", "desc": "Zawodowcy top-liga"},
    "pro_good":    {"max_seconds": 28.0, "label": "🏆 Pro: Dobry",        "color": "#2ecc71", "desc": "Zawodowcy / świetni amatorzy"},
    "pro_average": {"max_seconds": 30.0, "label": "✅ Pro: Przeciętny",   "color": "#3498db", "desc": "Poziom półzawodowy"},
    "am_good":     {"max_seconds": 32.5, "label": "🟢 Amateur: Dobry",    "color": "#27ae60", "desc": "Dobra sprawność, regularny sport"},
    "am_average":  {"max_seconds": 35.0, "label": "📊 Amateur: Średni",   "color": "#f39c12", "desc": "Przeciętna sprawność dorosłego"},
    "am_below":    {"max_seconds": 38.0, "label": "⚠️ Amateur: Słaby",    "color": "#e67e22", "desc": "Poniżej przeciętnej"},
    "poor":        {"max_seconds": 99.0, "label": "🔴 Niewystarczający",  "color": "#e74c3c", "desc": "Bardzo słaba forma"},
}


def get_beep_rating(level, shuttle):
    if level == 0 and shuttle == 0:
        return {"label": "—", "color": "#555", "desc": ""}
    score = level + (shuttle / 20.0)
    for key in ["pro_elite", "pro_good", "pro_average", "am_good", "am_average", "am_below", "poor"]:
        norm = BEEP_TEST_NORMS[key]
        norm_score = norm["min_level"] + (norm["min_shuttle"] / 20.0)
        if score >= norm_score:
            return norm
    return BEEP_TEST_NORMS["poor"]


def get_shuttle_rating(seconds):
    if seconds <= 0:
        return {"label": "—", "color": "#555", "desc": ""}
    for key in ["pro_elite", "pro_good", "pro_average", "am_good", "am_average", "am_below", "poor"]:
        norm = SHUTTLE_150M_NORMS[key]
        if seconds <= norm["max_seconds"]:
            return norm
    return SHUTTLE_150M_NORMS["poor"]


def get_trend_icon(current, previous, higher_is_better=True):
    if previous is None or current is None:
        return "➖", "gray", "Brak danych"
    diff = current - previous
    if abs(diff) < 0.01:
        return "➡️", "#f39c12", "Bez zmian"
    if higher_is_better:
        return ("📈", "#2ecc71", f"+{diff:.1f} ↑") if diff > 0 else ("📉", "#e74c3c", f"{diff:.1f} ↓")
    else:
        return ("📈", "#2ecc71", f"{diff:.1f}s ↑") if diff < 0 else ("📉", "#e74c3c", f"+{diff:.1f}s ↓")


# ════════════════════════════════════════════════════════════
# GŁÓWNY WIDOK
# ════════════════════════════════════════════════════════════
class DevelopmentCenterView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg_dark"])

        # Nagłówek
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(
            header, text="🎯 CENTRUM ROZWOJU",
            font=("Segoe UI", 26, "bold"), text_color=COLORS["accent"]
        ).pack(side="left")

        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right")

        ctk.CTkButton(
            btn_frame, text="📊 Dodaj Testy", width=130,
            fg_color="#2ecc71", hover_color="#27ae60",
            command=self.open_add_tests_dialog
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_frame, text="📋 Legenda", width=100,
            fg_color="#9b59b6", hover_color="#8e44ad",
            command=self.show_legend
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_frame, text="🔄", width=40,
            command=self.load_data
        ).pack(side="left", padx=4)

        # Tabs
        self.tabview = ctk.CTkTabview(self, fg_color=COLORS["bg_dark"])
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.tab_groups  = self.tabview.add("👥 Grupy Zdolności")
        self.tab_fitness = self.tabview.add("🏃 Testy Fizyczne")
        self.tab_ranking = self.tabview.add("🏆 Ranking")

        self.scroll_groups  = ctk.CTkScrollableFrame(self.tab_groups,  fg_color="transparent")
        self.scroll_groups.pack(fill="both", expand=True)

        self.scroll_fitness = ctk.CTkScrollableFrame(self.tab_fitness, fg_color="transparent")
        self.scroll_fitness.pack(fill="both", expand=True)

        self.scroll_ranking = ctk.CTkScrollableFrame(self.tab_ranking, fg_color="transparent")
        self.scroll_ranking.pack(fill="both", expand=True)

        self.players      = []
        self.fitness_tests = []
        self._history_by_player = {}

        self.load_data()

    # ────────────────────────────────────────────────────────
    # ŁADOWANIE DANYCH
    # ────────────────────────────────────────────────────────
    def _player_history(self, player_id):
        """Historia gracza ze słownika (bez zapytania do bazy)."""
        if not player_id:
            return []
        return self._history_by_player.get(player_id, [])

    def load_data(self):
        for scroll in [self.scroll_groups, self.scroll_fitness, self.scroll_ranking]:
            for w in scroll.winfo_children():
                w.destroy()
            ctk.CTkLabel(scroll, text="⏳ Ładowanie...", text_color="gray").pack(pady=50)

        def fetch():
            try:
                from cache_manager import cache
                self.players       = cache.get_players(force_refresh=True) or []
                self.fitness_tests = database.get_latest_fitness_tests()   or []
                # JEDNO zapytanie zamiast jednego na gracza (było ich ~33)
                self._history_by_player = cache.get_fitness_history_all() or {}
                print(f"✅ Zawodników: {len(self.players)} | "
                      f"Testów (ostatnie): {len(self.fitness_tests)} | "
                      f"Historia: {sum(len(v) for v in self._history_by_player.values())}")
                self.after(0, self.display_all)
            except Exception as e:
                print(f"❌ load_data: {e}")
                self.after(0, self.display_all)

        threading.Thread(target=fetch, daemon=True).start()

    def display_all(self):
        self.display_groups()
        self.display_fitness()
        self.display_ranking()

    # ════════════════════════════════════════════════════════
    # TAB 1 – GRUPY ZDOLNOŚCI
    # ════════════════════════════════════════════════════════
    def display_groups(self):
        for w in self.scroll_groups.winfo_children():
            w.destroy()

        if not self.players:
            ctk.CTkLabel(self.scroll_groups, text="Brak zawodników",
                         text_color="gray", font=("Segoe UI", 14)).pack(pady=50)
            return

        grid = ctk.CTkFrame(self.scroll_groups, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=5)
        grid.grid_columnconfigure((0, 1, 2), weight=1)

        abilities = ["strzelec", "drybler", "kreator", "wojownik", "bramkarz"]
        positions = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1)]

        no_ability = [p for p in self.players
                      if not p.get('key_ability') or
                      str(p.get('key_ability')).lower().strip() not in abilities]

        for ability, (row, col) in zip(abilities, positions):
            group = [p for p in self.players
                     if p.get('key_ability') and
                     str(p.get('key_ability')).lower().strip() == ability]
            self.create_group_card(grid, ability, group, row, col)

        if no_ability:
            self.create_group_card(grid, "bez zdolności", no_ability, 1, 2, color="#7f8c8d")

    def create_group_card(self, parent, ability, players, row, col, color=None):
        if color is None:
            color = ABILITY_COLORS.get(ability, COLORS["accent"])

        card = ctk.CTkFrame(parent, fg_color=COLORS["card_bg"], corner_radius=15)
        card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

        hdr = ctk.CTkFrame(card, fg_color=color, corner_radius=10)
        hdr.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(hdr, text=f"🎯 {ability.upper()}",
                     font=("Segoe UI", 15, "bold"), text_color="white").pack(side="left", padx=12, pady=8)
        ctk.CTkLabel(hdr, text=str(len(players)),
                     font=("Segoe UI", 14, "bold"), text_color="white").pack(side="right", padx=12)

        list_frame = ctk.CTkFrame(card, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        if not players:
            ctk.CTkLabel(list_frame, text="Brak zawodników", text_color="gray").pack(pady=15)
            return

        for p in sorted(players, key=lambda x: x.get('jersey_number') or 999):
            rf = ctk.CTkFrame(list_frame, fg_color="#2b2b2b", height=32, corner_radius=6)
            rf.pack(fill="x", pady=2)
            rf.pack_propagate(False)

            ctk.CTkLabel(rf, text=f"#{p.get('jersey_number') or '-'}",
                         width=32, text_color=color, font=("Arial", 11, "bold")).pack(side="left", padx=8)

            name = (p.get('full_name') or '?')[:18]
            nl = ctk.CTkLabel(rf, text=name, anchor="w", cursor="hand2", font=("Segoe UI", 11))
            nl.pack(side="left", fill="x", expand=True)
            nl.bind("<Button-1>", lambda e, pl=p: self.show_player_history(pl.get('id')))

            test = self._get_player_latest_test(p.get('id'))
            if test and test.get('beep_level', 0) > 0:
                rating = get_beep_rating(test['beep_level'], test['beep_shuttle'])
                ctk.CTkLabel(rf, text=f"L{test['beep_level']}",
                             width=30, text_color=rating['color'],
                             font=("Arial", 10, "bold")).pack(side="right", padx=5)

            ctk.CTkLabel(rf, text=p.get('primary_position') or '?',
                         width=30, text_color="gray", font=("Segoe UI", 10)).pack(side="right", padx=3)

    def _get_player_latest_test(self, player_id):
        if not player_id:
            return None
        for t in self.fitness_tests:
            if t.get('player_id') == player_id:
                return t
        return None

    # ════════════════════════════════════════════════════════
    # TAB 2 – TESTY FIZYCZNE
    # ════════════════════════════════════════════════════════
    def display_fitness(self):
        for w in self.scroll_fitness.winfo_children():
            w.destroy()

        if not self.players:
            ctk.CTkLabel(self.scroll_fitness, text="Brak zawodników",
                         text_color="gray").pack(pady=50)
            return

        self._create_fitness_summary()
        self._create_fitness_table()

    def _create_fitness_summary(self):
        summary = ctk.CTkFrame(self.scroll_fitness, fg_color=COLORS["card_bg"], corner_radius=15)
        summary.pack(fill="x", padx=5, pady=10)

        ctk.CTkLabel(summary, text="📊 PODSUMOWANIE",
                     font=("Segoe UI", 16, "bold"), text_color=COLORS["accent"]).pack(padx=20, pady=(15, 10))

        sf = ctk.CTkFrame(summary, fg_color="transparent")
        sf.pack(fill="x", padx=20, pady=(0, 15))
        sf.grid_columnconfigure((0, 1, 2, 3), weight=1)

        tests = [t for t in self.fitness_tests if t.get('beep_level', 0) > 0]
        total  = len(self.players)
        tested = len(tests)
        pct    = (tested / total * 100) if total > 0 else 0

        beep_levels   = [t['beep_level']           for t in tests if t.get('beep_level', 0) > 0]
        shuttle_times = [t['shuttle_150m_seconds']  for t in tests if t.get('shuttle_150m_seconds', 0) > 0]

        stats = [
            ("👥 Przetestowani",    f"{tested}/{total}",                                          COLORS["info"]),
            ("📊 Przetestowani %",  f"{pct:.0f}%",                                               "#9b59b6"),
            ("🏃 Śr. Beep Level",  f"{sum(beep_levels)/len(beep_levels):.1f}" if beep_levels else "—",   "#2ecc71"),
            ("⏱ Śr. 150m",         f"{sum(shuttle_times)/len(shuttle_times):.1f}s" if shuttle_times else "—", "#f39c12"),
        ]

        for i, (label, value, clr) in enumerate(stats):
            sc = ctk.CTkFrame(sf, fg_color="#2b2b2b", corner_radius=10)
            sc.grid(row=0, column=i, padx=5, pady=5, sticky="nsew")
            ctk.CTkLabel(sc, text=value,  font=("Segoe UI", 20, "bold"), text_color=clr).pack(pady=(10, 2))
            ctk.CTkLabel(sc, text=label,  font=("Segoe UI", 10),         text_color="gray").pack(pady=(0, 10))

    def _create_fitness_table(self):
        tc = ctk.CTkFrame(self.scroll_fitness, fg_color=COLORS["card_bg"], corner_radius=15)
        tc.pack(fill="x", padx=5, pady=10)

        ctk.CTkLabel(tc, text="📋 WYNIKI WSZYSTKICH ZAWODNIKÓW",
                     font=("Segoe UI", 16, "bold"), text_color=COLORS["accent"]).pack(padx=20, pady=(15, 5))

        hdr = ctk.CTkFrame(tc, fg_color="#2b2b2b", corner_radius=8)
        hdr.pack(fill="x", padx=15, pady=(10, 5))

        for text, width in [("Zawodnik", 200), ("Beep Test", 95), ("Ocena Beep", 130),
                            ("150m (s)", 75), ("Ocena 150m", 130), ("Trend", 55), ("Data", 85), ("", 90)]:
            ctk.CTkLabel(hdr, text=text, width=width,
                         font=("Segoe UI", 10, "bold"), text_color="#888").pack(side="left", padx=3, pady=8)

        for player in sorted(self.players, key=lambda p: p.get('jersey_number') or 999):
            self._create_fitness_row(tc, player)

    def _create_fitness_row(self, parent, player):
        pid  = player.get('id')
        test = self._get_player_latest_test(pid)

        row = ctk.CTkFrame(parent, fg_color="#252525", corner_radius=8, height=42)
        row.pack(fill="x", padx=15, pady=2)
        row.pack_propagate(False)

        nr   = player.get('jersey_number') or '-'
        name = (player.get('full_name') or '?')
        nl   = ctk.CTkLabel(row, text=f"#{nr} {name[:17]}",
                            width=200, anchor="w", cursor="hand2",
                            font=("Segoe UI", 11, "bold"))
        nl.pack(side="left", padx=8)
        nl.bind("<Button-1>", lambda e: self.show_player_history(pid))

        if not test:
            ctk.CTkLabel(row, text="Brak testów", width=420,
                         text_color="#555", font=("Segoe UI", 10, "italic"),
                         anchor="w").pack(side="left", padx=5)

            ctk.CTkButton(row, text="➕ Dodaj", width=80, height=26,
                          fg_color="#2ecc71", hover_color="#27ae60",
                          font=("Segoe UI", 10),
                          command=lambda p=player: self.open_add_single_test(p)).pack(side="right", padx=8)
            return

        history   = self._player_history(pid)
        prev_test = history[-2] if len(history) >= 2 else None

        # Beep
        bl = test.get('beep_level', 0) or 0
        bs = test.get('beep_shuttle', 0) or 0
        ctk.CTkLabel(row, text=f"L{bl}/S{bs}", width=95,
                     font=("Segoe UI", 11, "bold"), text_color="white").pack(side="left", padx=3)

        br = get_beep_rating(bl, bs)
        ctk.CTkLabel(row, text=br['label'], width=130,
                     font=("Segoe UI", 10, "bold"), text_color=br['color']).pack(side="left", padx=3)

        # Shuttle
        s150 = test.get('shuttle_150m_seconds', 0) or 0
        ctk.CTkLabel(row, text=f"{s150:.1f}s" if s150 > 0 else "—",
                     width=75, font=("Segoe UI", 11, "bold"), text_color="white").pack(side="left", padx=3)

        sr = get_shuttle_rating(s150)
        ctk.CTkLabel(row, text=sr['label'] if s150 > 0 else "—",
                     width=130, font=("Segoe UI", 10, "bold"),
                     text_color=sr['color'] if s150 > 0 else "#555").pack(side="left", padx=3)

        # Trend
        if prev_test:
            bc   = bl + bs / 20.0
            bp   = (prev_test.get('beep_level', 0) or 0) + (prev_test.get('beep_shuttle', 0) or 0) / 20.0
            icon, clr, _ = get_trend_icon(bc, bp, True)
            ctk.CTkLabel(row, text=icon, width=55,
                         font=("Segoe UI", 14), text_color=clr).pack(side="left", padx=3)
        else:
            ctk.CTkLabel(row, text="🆕", width=55, text_color="gray").pack(side="left", padx=3)

        # Data
        ctk.CTkLabel(row, text=str(test.get('test_date', ''))[:10],
                     width=85, text_color="gray",
                     font=("Segoe UI", 10)).pack(side="left", padx=3)

        # Przyciski Edytuj / Historia
        btn_box = ctk.CTkFrame(row, fg_color="transparent")
        btn_box.pack(side="right", padx=5)

        ctk.CTkButton(btn_box, text="✏️", width=32, height=26,
                      fg_color="#e67e22", hover_color="#ca6f1e",
                      command=lambda t=test, p=player: self.open_edit_test_dialog(t, p)).pack(side="left", padx=2)

        ctk.CTkButton(btn_box, text="📈", width=32, height=26,
                      fg_color="#3498db", hover_color="#2980b9",
                      command=lambda: self.show_player_history(pid)).pack(side="left", padx=2)

    # ════════════════════════════════════════════════════════
    # TAB 3 – RANKING
    # ════════════════════════════════════════════════════════
    def display_ranking(self):
        for w in self.scroll_ranking.winfo_children():
            w.destroy()

        beep_tests    = [t for t in self.fitness_tests if t.get('beep_level', 0) > 0]
        shuttle_tests = [t for t in self.fitness_tests if t.get('shuttle_150m_seconds', 0) > 0]

        if not beep_tests and not shuttle_tests:
            ec = ctk.CTkFrame(self.scroll_ranking, fg_color=COLORS["card_bg"], corner_radius=15)
            ec.pack(fill="x", padx=5, pady=20)
            ctk.CTkLabel(ec, text="🏆", font=("Segoe UI", 48)).pack(pady=(20, 5))
            ctk.CTkLabel(ec, text="Brak wyników do rankingu",
                         font=("Segoe UI", 14, "bold"), text_color="gray").pack(pady=(0, 20))
            return

        if beep_tests:
            self._create_ranking_section(
                "🏃 RANKING BEEP TEST",
                sorted(beep_tests, key=lambda t: (t.get('beep_level', 0), t.get('beep_shuttle', 0)), reverse=True),
                "beep"
            )
        if shuttle_tests:
            self._create_ranking_section(
                "⏱ RANKING BIEG WAHADŁOWY 150m",
                sorted(shuttle_tests, key=lambda t: t.get('shuttle_150m_seconds', 999)),
                "shuttle"
            )

        self._create_progress_ranking()

    def _create_ranking_section(self, title, sorted_tests, test_type):
        card = ctk.CTkFrame(self.scroll_ranking, fg_color=COLORS["card_bg"], corner_radius=15)
        card.pack(fill="x", padx=5, pady=10)

        ctk.CTkLabel(card, text=title, font=("Segoe UI", 16, "bold"),
                     text_color=COLORS["accent"]).pack(padx=20, pady=(15, 10))

        medals = ["🥇", "🥈", "🥉"]

        for i, test in enumerate(sorted_tests):
            row = ctk.CTkFrame(card, fg_color="#252525" if i % 2 == 0 else "#2b2b2b",
                               corner_radius=8, height=40)
            row.pack(fill="x", padx=15, pady=1)
            row.pack_propagate(False)

            pos_color = "#FFD700" if i == 0 else "#C0C0C0" if i == 1 else "#CD7F32" if i == 2 else "gray"
            ctk.CTkLabel(row, text=medals[i] if i < 3 else f" {i+1}.",
                         width=40, font=("Segoe UI", 14, "bold"),
                         text_color=pos_color).pack(side="left", padx=10)

            nr   = test.get('jersey_number') or '-'
            name = (test.get('full_name') or '?')[:20]
            ctk.CTkLabel(row, text=f"#{nr} {name}", width=210, anchor="w",
                         font=("Segoe UI", 12, "bold" if i < 3 else "normal")).pack(side="left", padx=5)

            if test_type == "beep":
                value_text = f"Level {test['beep_level']} / Shuttle {test['beep_shuttle']}"
                rating     = get_beep_rating(test['beep_level'], test['beep_shuttle'])
            else:
                value_text = f"{test['shuttle_150m_seconds']:.1f} sekund"
                rating     = get_shuttle_rating(test['shuttle_150m_seconds'])

            ctk.CTkLabel(row, text=value_text, width=180,
                         font=("Segoe UI", 12), text_color=rating['color']).pack(side="left", padx=10)
            ctk.CTkLabel(row, text=rating['label'], width=140,
                         font=("Segoe UI", 10), text_color=rating['color']).pack(side="left", padx=5)

    def _create_progress_ranking(self):
        progress_data = []

        for test in self.fitness_tests:
            pid = test.get('player_id')
            if not pid:
                continue
            history = self._player_history(pid)
            if len(history) >= 2:
                prev = history[-2]
                curr = history[-1]
                beep_diff    = ((curr.get('beep_level', 0) or 0) + (curr.get('beep_shuttle', 0) or 0) / 20.0) - \
                               ((prev.get('beep_level', 0) or 0) + (prev.get('beep_shuttle', 0) or 0) / 20.0)
                shuttle_diff = 0
                if (prev.get('shuttle_150m_seconds') or 0) > 0 and (curr.get('shuttle_150m_seconds') or 0) > 0:
                    shuttle_diff = prev['shuttle_150m_seconds'] - curr['shuttle_150m_seconds']
                progress_data.append({
                    **test,
                    'beep_diff': beep_diff,
                    'shuttle_diff': shuttle_diff,
                    'total_progress': beep_diff + shuttle_diff * 0.5
                })

        if not progress_data:
            return

        progress_data.sort(key=lambda x: x['total_progress'], reverse=True)

        card = ctk.CTkFrame(self.scroll_ranking, fg_color=COLORS["card_bg"], corner_radius=15)
        card.pack(fill="x", padx=5, pady=10)

        ctk.CTkLabel(card, text="📈 RANKING PROGRESU",
                     font=("Segoe UI", 16, "bold"), text_color="#2ecc71").pack(padx=20, pady=(15, 2))
        ctk.CTkLabel(card, text="(poprzedni test → obecny test)",
                     font=("Segoe UI", 10), text_color="gray").pack(pady=(0, 10))

        medals = ["🥇", "🥈", "🥉"]

        for i, data in enumerate(progress_data):
            row = ctk.CTkFrame(card, fg_color="#252525" if i % 2 == 0 else "#2b2b2b",
                               corner_radius=8, height=42)
            row.pack(fill="x", padx=15, pady=1)
            row.pack_propagate(False)

            ctk.CTkLabel(row, text=medals[i] if i < 3 else f" {i+1}.",
                         width=40, font=("Segoe UI", 14, "bold")).pack(side="left", padx=10)

            nr   = data.get('jersey_number') or '-'
            name = (data.get('full_name') or '?')[:20]
            ctk.CTkLabel(row, text=f"#{nr} {name}", width=210, anchor="w",
                         font=("Segoe UI", 12, "bold" if i < 3 else "normal")).pack(side="left", padx=5)

            bd    = data['beep_diff']
            bclr  = "#2ecc71" if bd > 0 else "#e74c3c" if bd < 0 else "gray"
            ctk.CTkLabel(row, text=f"Beep: {bd:+.1f}", width=100,
                         text_color=bclr, font=("Segoe UI", 11)).pack(side="left", padx=5)

            if data['shuttle_diff'] != 0:
                sd   = data['shuttle_diff']
                sclr = "#2ecc71" if sd > 0 else "#e74c3c"
                ctk.CTkLabel(row, text=f"150m: {sd:+.1f}s", width=100,
                             text_color=sclr, font=("Segoe UI", 11)).pack(side="left", padx=5)

            tp    = data['total_progress']
            picon = "📈" if tp > 0 else "📉" if tp < 0 else "➡️"
            pclr  = "#2ecc71" if tp > 0 else "#e74c3c" if tp < 0 else "gray"
            ctk.CTkLabel(row, text=f"{picon} {tp:+.1f}", width=80,
                         text_color=pclr, font=("Segoe UI", 12, "bold")).pack(side="right", padx=15)

    # ════════════════════════════════════════════════════════
    # DIALOG – DODAJ TESTY (MASOWO)
    # ════════════════════════════════════════════════════════
    def open_add_tests_dialog(self):
        if not self.players:
            self._notify("❌ Brak zawodników!", error=True)
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("📊 Dodaj Wyniki Testów")
        dialog.geometry("820x700")
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()
        dialog.attributes("-topmost", True)

        ctk.CTkLabel(dialog, text="📊 NOWE WYNIKI TESTÓW",
                     font=("Segoe UI", 20, "bold"), text_color=COLORS["accent"]).pack(pady=(20, 5))
        ctk.CTkLabel(dialog, text="Wypełnij tylko testowanych zawodników — reszta zostanie pominięta",
                     text_color="gray").pack(pady=(0, 10))

        df = ctk.CTkFrame(dialog, fg_color=COLORS["card_bg"], corner_radius=10)
        df.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(df, text="📅 Data testu:", font=("Segoe UI", 13, "bold")).pack(side="left", padx=15, pady=10)
        date_entry = ctk.CTkEntry(df, width=150, placeholder_text="YYYY-MM-DD")
        date_entry.pack(side="left", padx=10)
        date_entry.insert(0, date.today().isoformat())

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent", height=450)
        scroll.pack(fill="both", expand=True, padx=20, pady=10)

        hdr = ctk.CTkFrame(scroll, fg_color="#2b2b2b", corner_radius=8)
        hdr.pack(fill="x", pady=(0, 5))
        for text, width in [("Zawodnik", 220), ("Beep Lvl", 75), ("Beep Sh", 75), ("150m (s)", 90), ("Notatki", 160)]:
            ctk.CTkLabel(hdr, text=text, width=width,
                         font=("Segoe UI", 11, "bold"), text_color="#888").pack(side="left", padx=3, pady=8)

        player_entries = []
        for p in sorted(self.players, key=lambda x: x.get('jersey_number') or 999):
            row = ctk.CTkFrame(scroll, fg_color="#1a1a1a", corner_radius=8, height=40)
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)

            nr   = p.get('jersey_number') or '-'
            name = (p.get('full_name') or '?')[:20]
            ctk.CTkLabel(row, text=f"#{nr} {name}", width=220, anchor="w",
                         font=("Segoe UI", 11)).pack(side="left", padx=8, pady=5)

            e_bl = ctk.CTkEntry(row, width=75,  placeholder_text="0")
            e_bl.pack(side="left", padx=3)
            e_bs = ctk.CTkEntry(row, width=75,  placeholder_text="0")
            e_bs.pack(side="left", padx=3)
            e_s  = ctk.CTkEntry(row, width=90,  placeholder_text="0.0")
            e_s.pack(side="left", padx=3)
            e_n  = ctk.CTkEntry(row, width=160, placeholder_text="Opcjonalne")
            e_n.pack(side="left", padx=3)

            player_entries.append({'player': p, 'bl': e_bl, 'bs': e_bs, 'sh': e_s, 'no': e_n})

        bf = ctk.CTkFrame(dialog, fg_color="transparent")
        bf.pack(fill="x", padx=20, pady=15)

        def save_all():
            td = date_entry.get().strip()
            if not td:
                self._notify("❌ Podaj datę!", error=True)
                return
            count = 0
            for e in player_entries:
                vbl = e['bl'].get().strip()
                vbs = e['bs'].get().strip()
                vsh = e['sh'].get().strip()
                vno = e['no'].get().strip()
                if vbl or vbs or vsh:
                    try:
                        database.add_fitness_test(
                            player_id   = e['player']['id'],
                            test_date   = td,
                            beep_level  = int(vbl)                         if vbl else 0,
                            beep_shuttle= int(vbs)                         if vbs else 0,
                            shuttle_150m= float(vsh.replace(',', '.'))     if vsh else 0.0,
                            notes       = vno
                        )
                        count += 1
                    except ValueError as ex:
                        print(f"Błąd konwersji {e['player'].get('full_name')}: {ex}")
            dialog.destroy()
            if count:
                self._notify(f"✅ Zapisano {count} wyników!")
                self.load_data()
            else:
                self._notify("⚠️ Nic nie zapisano")

        ctk.CTkButton(bf, text="💾 Zapisz wszystkie", width=200,
                      fg_color="#2ecc71", hover_color="#27ae60",
                      font=("Segoe UI", 14, "bold"), command=save_all).pack(side="right", padx=10)
        ctk.CTkButton(bf, text="Anuluj", width=100,
                      fg_color="#555", command=dialog.destroy).pack(side="right", padx=5)

    # ════════════════════════════════════════════════════════
    # DIALOG – DODAJ TEST (POJEDYNCZY)
    # ════════════════════════════════════════════════════════
    def open_add_single_test(self, player):
        self._open_test_form(player, existing_test=None)

    # ════════════════════════════════════════════════════════
    # DIALOG – EDYTUJ TEST
    # ════════════════════════════════════════════════════════
    def open_edit_test_dialog(self, test, player):
        self._open_test_form(player, existing_test=test)

    # ────────────────────────────────────────────────────────
    # WSPÓLNY FORMULARZ (dodawanie + edycja)
    # ────────────────────────────────────────────────────────
    def _open_test_form(self, player, existing_test=None):
        is_edit = existing_test is not None
        title   = f"✏️ Edytuj test — {player.get('full_name','?')}" if is_edit else f"➕ Nowy test — {player.get('full_name','?')}"

        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("480x440")
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()
        dialog.attributes("-topmost", True)

        header_color = "#e67e22" if is_edit else "#2ecc71"
        ctk.CTkLabel(dialog, text=title, font=("Segoe UI", 16, "bold"),
                     text_color=header_color).pack(pady=(20, 15))

        form = ctk.CTkFrame(dialog, fg_color=COLORS["card_bg"], corner_radius=15)
        form.pack(fill="x", padx=30, pady=10)

        fields = {}

        def add_field(label, key, default="", placeholder=""):
            row = ctk.CTkFrame(form, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=7)
            ctk.CTkLabel(row, text=label, width=160, anchor="w").pack(side="left")
            e = ctk.CTkEntry(row, width=220, placeholder_text=placeholder)
            e.pack(side="left", padx=10)
            if default:
                e.insert(0, str(default))
            fields[key] = e

        if is_edit:
            td = str(existing_test.get('test_date', ''))[:10]
        else:
            td = date.today().isoformat()

        add_field("📅 Data testu:",     "date",     td,
                  "YYYY-MM-DD")
        add_field("🏃 Beep Level:",     "bl",
                  existing_test.get('beep_level', '')   if is_edit else "",  "np. 9")
        add_field("🏃 Beep Shuttle:",   "bs",
                  existing_test.get('beep_shuttle', '')  if is_edit else "",  "np. 5")
        add_field("⏱ 150m (sekundy):", "sh",
                  existing_test.get('shuttle_150m_seconds', '') if is_edit else "", "np. 30.5")
        add_field("📝 Notatki:",        "no",
                  existing_test.get('notes', '')         if is_edit else "",  "Opcjonalne")

        # Podgląd oceny na żywo
        preview_lbl = ctk.CTkLabel(form, text="", font=("Segoe UI", 11), text_color="gray")
        preview_lbl.pack(pady=(5, 10))

        def update_preview(*_):
            try:
                bl = int(fields['bl'].get() or 0)
                bs = int(fields['bs'].get() or 0)
                sh = float((fields['sh'].get() or "0").replace(',', '.'))
                br = get_beep_rating(bl, bs)
                sr = get_shuttle_rating(sh)
                preview_lbl.configure(
                    text=f"Beep: {br['label']}  |  150m: {sr['label']}",
                    text_color=br['color']
                )
            except:
                preview_lbl.configure(text="")

        for f in fields.values():
            f.bind("<KeyRelease>", update_preview)
        update_preview()

        # Przyciski
        bf = ctk.CTkFrame(dialog, fg_color="transparent")
        bf.pack(fill="x", padx=30, pady=15)

        def save():
            try:
                bl = fields['bl'].get().strip()
                bs = fields['bs'].get().strip()
                sh = fields['sh'].get().strip().replace(',', '.')
                no = fields['no'].get().strip()
                td = fields['date'].get().strip()

                if is_edit:
                    database.update_fitness_test(
                        test_id      = existing_test['id'],
                        beep_level   = int(bl)    if bl else 0,
                        beep_shuttle = int(bs)    if bs else 0,
                        shuttle_150m = float(sh)  if sh else 0.0,
                        notes        = no
                    )
                    # Aktualizuj też datę jeśli potrzeba
                    supabase.table("fitness_tests")\
                        .update({"test_date": td})\
                        .eq("id", existing_test['id'])\
                        .execute()
                    self._notify("✅ Test zaktualizowany!")
                else:
                    database.add_fitness_test(
                        player_id    = player['id'],
                        test_date    = td,
                        beep_level   = int(bl)    if bl else 0,
                        beep_shuttle = int(bs)    if bs else 0,
                        shuttle_150m = float(sh)  if sh else 0.0,
                        notes        = no
                    )
                    self._notify("✅ Test zapisany!")

                dialog.destroy()
                self.load_data()
            except ValueError:
                self._notify("❌ Błędne dane (sprawdź liczby)", error=True)

        ctk.CTkButton(bf, text="Anuluj", width=100, fg_color="#555",
                      command=dialog.destroy).pack(side="left")

        btn_label = "💾 Zapisz zmiany" if is_edit else "💾 Zapisz test"
        btn_color = "#e67e22"          if is_edit else "#2ecc71"
        btn_hover = "#ca6f1e"          if is_edit else "#27ae60"

        ctk.CTkButton(bf, text=btn_label, width=200,
                      fg_color=btn_color, hover_color=btn_hover,
                      font=("Segoe UI", 13, "bold"), command=save).pack(side="right")

    # ════════════════════════════════════════════════════════
    # HISTORIA ZAWODNIKA
    # ════════════════════════════════════════════════════════
    def show_player_history(self, player_id):
        if not player_id:
            return

        history = database.get_player_fitness_history(player_id)
        player  = next((p for p in self.players if p.get('id') == player_id), None)
        if not player:
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"📈 Historia — {player.get('full_name','?')}")
        dialog.geometry("860x680")
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()
        dialog.attributes("-topmost", True)

        # Header
        hdr = ctk.CTkFrame(dialog, fg_color=COLORS["card_bg"], corner_radius=15)
        hdr.pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(hdr, text=f"#{player.get('jersey_number','-')} {player.get('full_name','?')}",
                     font=("Segoe UI", 22, "bold"), text_color="white").pack(side="left", padx=20, pady=15)

        # Przycisk dodaj nowy test w headerze
        ctk.CTkButton(hdr, text="➕ Dodaj nowy test", width=150, height=32,
                      fg_color="#2ecc71", hover_color="#27ae60",
                      command=lambda: (dialog.destroy(), self.open_add_single_test(player))
                      ).pack(side="right", padx=20, pady=15)

        if player.get('key_ability'):
            ab    = str(player['key_ability']).lower().strip()
            abclr = ABILITY_COLORS.get(ab, COLORS["accent"])
            ctk.CTkLabel(hdr, text=f"🎯 {player['key_ability'].upper()}",
                         font=("Segoe UI", 14, "bold"), text_color=abclr).pack(side="right", padx=10)

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        if not history:
            ef = ctk.CTkFrame(scroll, fg_color=COLORS["card_bg"], corner_radius=15)
            ef.pack(fill="x", pady=20)
            ctk.CTkLabel(ef, text="📭", font=("Segoe UI", 48)).pack(pady=(20, 5))
            ctk.CTkLabel(ef, text="Brak wyników testów",
                         font=("Segoe UI", 16, "bold"), text_color="gray").pack()
            ctk.CTkButton(ef, text="📊 Dodaj Pierwszy Test",
                          fg_color="#2ecc71", hover_color="#27ae60",
                          command=lambda: (dialog.destroy(), self.open_add_single_test(player))
                          ).pack(pady=20)
            return

        # ── Wykres Beep ──
        self._render_beep_chart(scroll, history)

        # ── Wykres 150m ──
        sh_data = [h for h in history if (h.get('shuttle_150m_seconds') or 0) > 0]
        if sh_data:
            self._render_shuttle_chart(scroll, sh_data)

        # ── Szczegóły wszystkich testów (z edycją i usunięciem) ──
        self._render_history_details(scroll, history, dialog, player_id, player)

        # ── Podsumowanie ──
        if len(history) >= 2:
            self._render_summary(scroll, history)

    # ────────────────────────────────────────────────────────
    def _render_beep_chart(self, parent, history):
        card = ctk.CTkFrame(parent, fg_color=COLORS["card_bg"], corner_radius=15)
        card.pack(fill="x", pady=10)

        ctk.CTkLabel(card, text="📊 PROGRESJA BEEP TESTU",
                     font=("Segoe UI", 14, "bold"), text_color=COLORS["accent"]).pack(padx=15, pady=(15, 5))

        max_lvl = max((h.get('beep_level') or 0 for h in history), default=1) or 1

        for h in history:
            bf = ctk.CTkFrame(card, fg_color="transparent")
            bf.pack(fill="x", padx=15, pady=3)

            ctk.CTkLabel(bf, text=str(h.get('test_date', ''))[:10],
                         width=90, anchor="w", text_color="gray",
                         font=("Segoe UI", 10)).pack(side="left")

            bl = h.get('beep_level', 0) or 0
            bs = h.get('beep_shuttle', 0) or 0
            w  = int((bl / max_lvl) * 300) + 30
            r  = get_beep_rating(bl, bs)

            bar = ctk.CTkFrame(bf, fg_color=r['color'], corner_radius=5, height=22, width=w)
            bar.pack(side="left", padx=5, pady=2)
            bar.pack_propagate(False)
            ctk.CTkLabel(bar, text=f"L{bl}/S{bs}",
                         font=("Segoe UI", 9, "bold"), text_color="white").pack(expand=True)

            ctk.CTkLabel(bf, text=r['label'], text_color=r['color'],
                         font=("Segoe UI", 9)).pack(side="left", padx=10)

        ctk.CTkLabel(card, text="", height=5).pack()

    # ────────────────────────────────────────────────────────
    def _render_shuttle_chart(self, parent, sh_data):
        card = ctk.CTkFrame(parent, fg_color=COLORS["card_bg"], corner_radius=15)
        card.pack(fill="x", pady=10)

        ctk.CTkLabel(card, text="⏱ PROGRESJA BIEG WAHADŁOWY 150m",
                     font=("Segoe UI", 14, "bold"), text_color="#f39c12").pack(padx=15, pady=(15, 5))

        max_t = max(h['shuttle_150m_seconds'] for h in sh_data)

        for h in sh_data:
            bf = ctk.CTkFrame(card, fg_color="transparent")
            bf.pack(fill="x", padx=15, pady=3)

            ctk.CTkLabel(bf, text=str(h.get('test_date', ''))[:10],
                         width=90, anchor="w", text_color="gray",
                         font=("Segoe UI", 10)).pack(side="left")

            s150 = h['shuttle_150m_seconds']
            w    = int(((max_t - s150 + 20) / (max_t + 20)) * 300) + 50
            r    = get_shuttle_rating(s150)

            bar = ctk.CTkFrame(bf, fg_color=r['color'], corner_radius=5, height=22, width=w)
            bar.pack(side="left", padx=5, pady=2)
            bar.pack_propagate(False)
            ctk.CTkLabel(bar, text=f"{s150:.1f}s",
                         font=("Segoe UI", 9, "bold"), text_color="white").pack(expand=True)

            ctk.CTkLabel(bf, text=r['label'], text_color=r['color'],
                         font=("Segoe UI", 9)).pack(side="left", padx=10)

        ctk.CTkLabel(card, text="", height=5).pack()

    # ────────────────────────────────────────────────────────
    def _render_history_details(self, parent, history, dialog, player_id, player):
        card = ctk.CTkFrame(parent, fg_color=COLORS["card_bg"], corner_radius=15)
        card.pack(fill="x", pady=10)

        ctk.CTkLabel(card, text="📋 WSZYSTKIE TESTY (od najnowszego)",
                     font=("Segoe UI", 14, "bold"), text_color=COLORS["accent"]).pack(padx=15, pady=(15, 5))

        for i, h in enumerate(reversed(history)):
            tf = ctk.CTkFrame(card, fg_color="#252525", corner_radius=10)
            tf.pack(fill="x", padx=15, pady=5)

            # ── Top row: numer testu + data + przyciski akcji ──
            top = ctk.CTkFrame(tf, fg_color="transparent")
            top.pack(fill="x", padx=15, pady=(10, 5))

            test_num = len(history) - i
            ctk.CTkLabel(top, text=f"Test #{test_num}",
                         font=("Segoe UI", 13, "bold"), text_color=COLORS["accent"]).pack(side="left")

            date_str = str(h.get('test_date', ''))[:10]
            ctk.CTkLabel(top, text=f"📅 {date_str}", text_color="gray").pack(side="left", padx=15)

            # Przycisk Usuń
            ctk.CTkButton(top, text="🗑 Usuń", width=75, height=26,
                          fg_color="#e74c3c", hover_color="#c0392b",
                          font=("Segoe UI", 10),
                          command=lambda tid=h['id']: self._delete_test(tid, dialog, player_id)
                          ).pack(side="right", padx=3)

            # Przycisk Edytuj
            ctk.CTkButton(top, text="✏️ Edytuj", width=80, height=26,
                          fg_color="#e67e22", hover_color="#ca6f1e",
                          font=("Segoe UI", 10),
                          command=lambda hh=h: (dialog.destroy(), self._open_test_form(player, existing_test=hh))
                          ).pack(side="right", padx=3)

            # ── Wyniki ──
            res = ctk.CTkFrame(tf, fg_color="transparent")
            res.pack(fill="x", padx=15, pady=(0, 5))

            bl = h.get('beep_level', 0) or 0
            bs = h.get('beep_shuttle', 0) or 0
            br = get_beep_rating(bl, bs)

            ctk.CTkLabel(res, text=f"🏃 Beep: L{bl} / S{bs}",
                         font=("Segoe UI", 12)).pack(side="left", padx=5)
            ctk.CTkLabel(res, text=br['label'],
                         text_color=br['color'], font=("Segoe UI", 11, "bold")).pack(side="left", padx=8)

            s150 = h.get('shuttle_150m_seconds', 0) or 0
            if s150 > 0:
                sr = get_shuttle_rating(s150)
                ctk.CTkLabel(res, text=f"⏱ 150m: {s150:.1f}s",
                             font=("Segoe UI", 12)).pack(side="left", padx=15)
                ctk.CTkLabel(res, text=sr['label'],
                             text_color=sr['color'], font=("Segoe UI", 11, "bold")).pack(side="left", padx=5)

            # ── Trend vs poprzedni ──
            idx = len(history) - 1 - i
            if idx > 0:
                prev = history[idx - 1]
                comp = ctk.CTkFrame(tf, fg_color="#1a1a1a", corner_radius=8)
                comp.pack(fill="x", padx=15, pady=(0, 5))

                bc = bl + bs / 20.0
                bp = (prev.get('beep_level', 0) or 0) + (prev.get('beep_shuttle', 0) or 0) / 20.0
                bi, bc2, bt = get_trend_icon(bc, bp, True)
                ctk.CTkLabel(comp, text=f"{bi} Beep: {bt}",
                             text_color=bc2, font=("Segoe UI", 10)).pack(side="left", padx=15, pady=5)

                ps150 = prev.get('shuttle_150m_seconds', 0) or 0
                if s150 > 0 and ps150 > 0:
                    si, sc, st = get_trend_icon(s150, ps150, False)
                    ctk.CTkLabel(comp, text=f"{si} 150m: {st}",
                                 text_color=sc, font=("Segoe UI", 10)).pack(side="left", padx=15)

            # ── Notatki ──
            if h.get('notes') and str(h['notes']).strip():
                ctk.CTkLabel(tf, text=f"📝 {h['notes']}",
                             text_color="#888", font=("Segoe UI", 10),
                             anchor="w").pack(fill="x", padx=20, pady=(0, 8))

    # ────────────────────────────────────────────────────────
    def _render_summary(self, parent, history):
        sf = ctk.CTkFrame(parent, fg_color="#1a3a2a", corner_radius=15)
        sf.pack(fill="x", pady=10)

        first = history[0]
        last  = history[-1]

        tb = ((last.get('beep_level', 0) or 0) + (last.get('beep_shuttle', 0) or 0) / 20.0) - \
             ((first.get('beep_level', 0) or 0) + (first.get('beep_shuttle', 0) or 0) / 20.0)

        ctk.CTkLabel(sf, text="📊 PODSUMOWANIE CAŁKOWITE",
                     font=("Segoe UI", 14, "bold"), text_color="#2ecc71").pack(padx=15, pady=(15, 5))

        pc  = "#2ecc71" if tb > 0 else "#e74c3c" if tb < 0 else "gray"
        pi  = "📈" if tb > 0 else "📉" if tb < 0 else "➡️"
        ctk.CTkLabel(
            sf,
            text=f"{pi} Beep: L{first.get('beep_level',0)}/S{first.get('beep_shuttle',0)} "
                 f"→ L{last.get('beep_level',0)}/S{last.get('beep_shuttle',0)} ({tb:+.1f})",
            font=("Segoe UI", 13), text_color=pc
        ).pack(padx=20, pady=5)

        f150 = first.get('shuttle_150m_seconds', 0) or 0
        l150 = last.get('shuttle_150m_seconds', 0)  or 0
        if f150 > 0 and l150 > 0:
            ts  = f150 - l150
            sc  = "#2ecc71" if ts > 0 else "#e74c3c" if ts < 0 else "gray"
            si  = "📈" if ts > 0 else "📉" if ts < 0 else "➡️"
            ctk.CTkLabel(sf, text=f"{si} 150m: {f150:.1f}s → {l150:.1f}s ({ts:+.1f}s)",
                         font=("Segoe UI", 13), text_color=sc).pack(padx=20, pady=5)

        ctk.CTkLabel(
            sf,
            text=f"📅 {str(first.get('test_date',''))[:10]} → {str(last.get('test_date',''))[:10]} | Testów: {len(history)}",
            text_color="gray", font=("Segoe UI", 10)
        ).pack(padx=20, pady=(5, 15))

    # ════════════════════════════════════════════════════════
    # USUWANIE TESTU
    # ════════════════════════════════════════════════════════
    def _delete_test(self, test_id, dialog, player_id):
        confirm = ctk.CTkToplevel(dialog)
        confirm.title("Potwierdzenie")
        confirm.geometry("360x160")
        confirm.configure(fg_color=COLORS["bg_dark"])
        confirm.transient(dialog)
        confirm.grab_set()
        confirm.attributes("-topmost", True)

        ctk.CTkLabel(confirm, text="🗑 Usunąć ten wynik testu?",
                     font=("Segoe UI", 14, "bold")).pack(pady=25)

        bf = ctk.CTkFrame(confirm, fg_color="transparent")
        bf.pack(pady=5)

        def do_delete():
            database.delete_fitness_test(test_id)
            confirm.destroy()
            dialog.destroy()
            self.load_data()

        ctk.CTkButton(bf, text="✅ Tak, usuń", fg_color="#e74c3c", hover_color="#c0392b",
                      command=do_delete).pack(side="left", padx=10)
        ctk.CTkButton(bf, text="Anuluj", fg_color="#555",
                      command=confirm.destroy).pack(side="left", padx=10)

    # ════════════════════════════════════════════════════════
    # LEGENDA – DOROŚLI 18+ (pro + amator)
    # ════════════════════════════════════════════════════════
    def show_legend(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("📋 Legenda Testów — Dorośli 18+")
        dialog.geometry("720x820")
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()
        dialog.attributes("-topmost", True)

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=20)

        # ── Podział poziomów ──
        intro = ctk.CTkFrame(scroll, fg_color="#1a2a3a", corner_radius=15)
        intro.pack(fill="x", pady=10)
        ctk.CTkLabel(intro, text="🎯 PODZIAŁ POZIOMÓW — DOROŚLI 18+",
                     font=("Segoe UI", 16, "bold"), text_color=COLORS["accent"]).pack(padx=20, pady=(15, 5))

        for icon, label, desc, clr in [
            ("⭐", "Pro: Elita",      "Zawodowi piłkarze top-lig (Premier League, La Liga, Bundesliga)", "#FFD700"),
            ("🏆", "Pro: Dobry",      "Zawodowcy niższych lig, bardzo dobrzy amatorzy trenujący 5+ razy/tyg", "#2ecc71"),
            ("✅", "Pro: Przeciętny", "Minimalny poziom półzawodowy, amatorzy z wieloletnią praktyką", "#3498db"),
            ("🟢", "Amateur: Dobry",  "Regularne treningi 3-4×/tydzień, dobra ogólna sprawność", "#27ae60"),
            ("📊", "Amateur: Średni", "Aktywna zdrowa osoba, sport rekreacyjny", "#f39c12"),
            ("⚠️", "Amateur: Słaby",  "Poniżej przeciętnej zdrowej dorosłej osoby", "#e67e22"),
            ("🔴", "Niewystarczający","Bardzo słaba kondycja — konieczna intensywna praca", "#e74c3c"),
        ]:
            row = ctk.CTkFrame(intro, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=3)
            ctk.CTkLabel(row, text=icon, width=30, font=("Segoe UI", 14)).pack(side="left")
            ctk.CTkLabel(row, text=label, width=160, anchor="w",
                         text_color=clr, font=("Segoe UI", 12, "bold")).pack(side="left")
            ctk.CTkLabel(row, text=desc, text_color="#aaa",
                         font=("Segoe UI", 10), anchor="w", wraplength=360).pack(side="left", padx=5)
        ctk.CTkLabel(intro, text="", height=10).pack()

        # ── Beep Test ──
        bc = ctk.CTkFrame(scroll, fg_color=COLORS["card_bg"], corner_radius=15)
        bc.pack(fill="x", pady=10)
        ctk.CTkLabel(bc, text="🏃 BEEP TEST — NORMY 18+ (dorosły mężczyzna)",
                     font=("Segoe UI", 16, "bold"), text_color=COLORS["accent"]).pack(padx=20, pady=(15, 5))
        ctk.CTkLabel(bc,
                     text="20 metrów tam i z powrotem w tempie sygnałów dźwiękowych.\n"
                          "Każdy poziom (Level) jest trudniejszy — tempo rośnie.\n"
                          "Wynik = Level + Shuttle (odcinek w danym poziomie).",
                     text_color="#aaa", font=("Segoe UI", 11), justify="left").pack(padx=20, pady=5)

        hdr = ctk.CTkFrame(bc, fg_color="#2b2b2b", corner_radius=8)
        hdr.pack(fill="x", padx=20, pady=(8, 4))
        for txt, w in [("Poziom", 150), ("Min. wynik", 130), ("Kontekst", 300)]:
            ctk.CTkLabel(hdr, text=txt, width=w, font=("Segoe UI", 10, "bold"),
                         text_color="#888").pack(side="left", padx=5, pady=6)

        for key, norm in BEEP_TEST_NORMS.items():
            row = ctk.CTkFrame(bc, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=2)
            ind = ctk.CTkFrame(row, fg_color=norm['color'], width=6, height=24, corner_radius=3)
            ind.pack(side="left", padx=(0, 8))
            ind.pack_propagate(False)
            ctk.CTkLabel(row, text=norm['label'], width=148, anchor="w",
                         text_color=norm['color'], font=("Segoe UI", 11, "bold")).pack(side="left")
            ctk.CTkLabel(row, text=f"≥ L{norm['min_level']} / S{norm['min_shuttle']}",
                         width=128, anchor="w", text_color="#aaa").pack(side="left")
            ctk.CTkLabel(row, text=norm.get('desc', ''), width=300, anchor="w",
                         text_color="#666", font=("Segoe UI", 10)).pack(side="left", padx=5)
        ctk.CTkLabel(bc, text="", height=10).pack()

        # ── 150m ──
        sc = ctk.CTkFrame(scroll, fg_color=COLORS["card_bg"], corner_radius=15)
        sc.pack(fill="x", pady=10)
        ctk.CTkLabel(sc, text="⏱ BIEG WAHADŁOWY 150m — NORMY 18+",
                     font=("Segoe UI", 16, "bold"), text_color="#f39c12").pack(padx=20, pady=(15, 5))
        ctk.CTkLabel(sc,
                     text="Np. 5×30m lub 3×50m z nawrotami — mierzy szybkość + zmianę kierunku.\n"
                          "Czas mierzony stoperem — im mniej sekund, tym lepiej.",
                     text_color="#aaa", font=("Segoe UI", 11), justify="left").pack(padx=20, pady=5)

        hdr2 = ctk.CTkFrame(sc, fg_color="#2b2b2b", corner_radius=8)
        hdr2.pack(fill="x", padx=20, pady=(8, 4))
        for txt, w in [("Poziom", 150), ("Maks. czas", 130), ("Kontekst", 300)]:
            ctk.CTkLabel(hdr2, text=txt, width=w, font=("Segoe UI", 10, "bold"),
                         text_color="#888").pack(side="left", padx=5, pady=6)

        for key, norm in SHUTTLE_150M_NORMS.items():
            row = ctk.CTkFrame(sc, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=2)
            ind = ctk.CTkFrame(row, fg_color=norm['color'], width=6, height=24, corner_radius=3)
            ind.pack(side="left", padx=(0, 8))
            ind.pack_propagate(False)
            ctk.CTkLabel(row, text=norm['label'], width=148, anchor="w",
                         text_color=norm['color'], font=("Segoe UI", 11, "bold")).pack(side="left")
            ctk.CTkLabel(row, text=f"≤ {norm['max_seconds']:.1f}s",
                         width=128, anchor="w", text_color="#aaa").pack(side="left")
            ctk.CTkLabel(row, text=norm.get('desc', ''), width=300, anchor="w",
                         text_color="#666", font=("Segoe UI", 10)).pack(side="left", padx=5)
        ctk.CTkLabel(sc, text="", height=10).pack()

        # ── Trendy ──
        tc = ctk.CTkFrame(scroll, fg_color=COLORS["card_bg"], corner_radius=15)
        tc.pack(fill="x", pady=10)
        ctk.CTkLabel(tc, text="📊 OZNACZENIA TRENDÓW",
                     font=("Segoe UI", 16, "bold"), text_color="#2ecc71").pack(padx=20, pady=(15, 8))
        for icon, desc in [
            ("📈", "Poprawa wyników vs. poprzedni test"),
            ("📉", "Spadek formy — wymaga reakcji trenera"),
            ("➡️", "Wynik stabilny (bez zmian)"),
            ("🆕", "Pierwszy test — brak punktu odniesienia"),
        ]:
            row = ctk.CTkFrame(tc, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=3)
            ctk.CTkLabel(row, text=icon, width=40, font=("Segoe UI", 16)).pack(side="left")
            ctk.CTkLabel(row, text=desc, text_color="#aaa", anchor="w").pack(side="left", padx=10)
        ctk.CTkLabel(tc, text="", height=10).pack()

        # ── Harmonogram ──
        hc = ctk.CTkFrame(scroll, fg_color=COLORS["card_bg"], corner_radius=15)
        hc.pack(fill="x", pady=10)
        ctk.CTkLabel(hc, text="📅 ZALECANY HARMONOGRAM",
                     font=("Segoe UI", 16, "bold"), text_color="#9b59b6").pack(padx=20, pady=(15, 5))
        ctk.CTkLabel(hc,
                     text="✅ Testy co pół roku (styczeń/luty i lipiec/sierpień)\n"
                          "✅ Rozgrzewka minimum 15 minut przed testem\n"
                          "✅ Sucha, płaska nawierzchnia | temperatura 15–25°C\n"
                          "✅ Zawodnik zdrowy, wypoczęty (brak treningu dzień wcześniej)\n"
                          "✅ Standardowe obuwie piłkarskie lub sportowe",
                     text_color="#aaa", font=("Segoe UI", 11), justify="left").pack(padx=20, pady=(5, 15))

        ctk.CTkButton(scroll, text="Zamknij", width=160,
                      fg_color="#555", hover_color="#666",
                      command=dialog.destroy).pack(pady=15)

    # ════════════════════════════════════════════════════════
    # UTILITY
    # ════════════════════════════════════════════════════════
    def _notify(self, message, error=False):
        clr   = "#e74c3c" if error else "#2ecc71"
        notif = ctk.CTkFrame(self, fg_color=clr, corner_radius=8, height=45)
        notif.pack(side="top", fill="x", padx=20, pady=(5, 0))
        notif.pack_propagate(False)
        ctk.CTkLabel(notif, text=message,
                     font=("Segoe UI", 13, "bold"), text_color="white").pack(expand=True)
        notif.lift()
        self.after(2500, lambda: (notif.pack_forget(), notif.destroy()))