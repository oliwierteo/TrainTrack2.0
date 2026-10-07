# views/analysis_view.py - PROFIL ZAWODNIKA v3.1 + FILTR SEZONU

import customtkinter as ctk
from database import supabase
import database
import teams
import tkinter.messagebox as msgbox
import threading
from datetime import datetime, date, timedelta

COLORS = {
    "bg_dark":   "#121212",
    "panel_bg":  "#1e1e1e",
    "accent":    "#3b8ed0",
    "success":   "#2fa572",
    "warning":   "#f39c12",
    "danger":    "#e74c3c",
    "text_gray": "#aaaaaa",
    "gold":      "#FFD700",
}

POS_ORDER = {
    'BR': 1, 'GK': 1, 'LO': 2, 'LB': 2, 'ŚO': 3, 'CB': 3, 'PO': 4, 'RB': 4,
    'DP': 5, 'DM': 5, 'ŚP': 6, 'CM': 6, 'ŚPO': 7, 'CAM': 7,
    'LS': 8, 'LW': 8, 'PS': 9, 'RW': 9, 'N': 10, 'ST': 10
}

POS_GROUPS = {
    "🧤 Bramkarze":  ["BR", "GK"],
    "🛡 Obrońcy":    ["LO", "LB", "ŚO", "CB", "PO", "RB"],
    "🎯 Pomocnicy":  ["DP", "DM", "ŚP", "CM", "ŚPO", "CAM", "LP", "PP"],
    "⚡ Napastnicy":  ["LS", "LW", "PS", "RW", "N", "ST", "CF", "OP"],
}


class AnalysisView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg_dark"])

        self.grid_columnconfigure(0, weight=0, minsize=280)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.current_pid    = None
        self.current_name   = None
        self.current_player = None
        self.players_data   = []

        # Cache surowych danych (WSZYSTKO, bez filtra sezonu)
        self._notes_cache   = {}
        self._ratings_cache = {}
        self._events_cache  = {}
        self._attend_cache  = {}
        self._fitness_cache = {}
        self._loading       = False

        # Aktualny filtr sezonu
        self._season_filter = "Cały okres"

        self._build_left_panel()
        self._build_right_panel()

        self.after(50, self.load_players)

    # ════════════════════════════════════════════
    # HELPER: FILTR SEZONU
    # ════════════════════════════════════════════
    def _get_season_date_range(self):
        """Zwraca (start_date, end_date) dla wybranego sezonu lub None dla 'Cały okres'"""
        if self._season_filter == "Cały okres":
            return None, None
        try:
            return database.get_season_range(self._season_filter)
        except Exception:
            return None, None

    def _date_in_season(self, date_str):
        """Sprawdza czy data mieści się w wybranym sezonie"""
        if self._season_filter == "Cały okres":
            return True
        start, end = self._get_season_date_range()
        if not start or not end:
            return True
        try:
            d = str(date_str)[:10]
            return start <= d <= end
        except Exception:
            return True

    def _filter_ratings_by_season(self, ratings):
        """Filtruje oceny po sezonie (przez datę eventu)"""
        if self._season_filter == "Cały okres":
            return ratings or []
        filtered = []
        for r in (ratings or []):
            ev = self._events_cache.get(r.get('event_id'), {})
            dt = ev.get('event_date', '')
            if self._date_in_season(dt):
                filtered.append(r)
        return filtered

    def _filter_attendance_by_season(self, attend):
        """Filtruje frekwencję po sezonie"""
        if self._season_filter == "Cały okres":
            return attend or []
        filtered = []
        for a in (attend or []):
            eid = a.get('event_id')
            ev  = self._events_cache.get(eid, {})
            dt  = ev.get('event_date', '')
            if dt:
                if self._date_in_season(dt):
                    filtered.append(a)
            else:
                # Jeśli brak eventu w cache, spróbuj po dacie w attendance
                filtered.append(a)
        return filtered

    def _filter_fitness_by_season(self, fitness):
        """Filtruje testy fizyczne po sezonie"""
        if self._season_filter == "Cały okres":
            return fitness or []
        return [f for f in (fitness or [])
                if self._date_in_season(f.get('test_date', ''))]

    def _on_season_changed(self, new_season):
        """Callback gdy zmieni się sezon"""
        self._season_filter = new_season
        # Przerenderuj wszystko z nowym filtrem (dane już w cache)
        if self.current_pid:
            pid     = self.current_pid
            note    = self._notes_cache.get(pid, '')
            ratings = self._ratings_cache.get(pid, [])
            attend  = self._attend_cache.get(pid, [])
            fitness = self._fitness_cache.get(pid, [])
            self._render_all(note, ratings, attend, fitness)

    # ════════════════════════════════════════════
    # LEWY PANEL
    # ════════════════════════════════════════════
    def _build_left_panel(self):
        self.left = ctk.CTkFrame(self, width=280, corner_radius=0,
                                 fg_color=COLORS["panel_bg"])
        self.left.grid(row=0, column=0, sticky="nsew")
        self.left.grid_propagate(False)

        hf = ctk.CTkFrame(self.left, fg_color="transparent")
        hf.pack(fill="x", padx=10, pady=(15, 5))

        ctk.CTkLabel(hf, text="📊 ANALIZA",
                     font=("Segoe UI", 20, "bold"),
                     text_color=COLORS["accent"]).pack(side="left")

        ctk.CTkButton(hf, text="⟳", width=35, fg_color="#444",
                      command=self.force_refresh).pack(side="right")

        self.search_entry = ctk.CTkEntry(self.left,
                                         placeholder_text="🔍 Szukaj...",
                                         width=250)
        self.search_entry.pack(padx=10, pady=5)
        self.search_entry.bind("<KeyRelease>", self._on_search)

        self.pos_filter = ctk.CTkOptionMenu(
            self.left,
            values=["Wszystkie pozycje"] + list(POS_GROUPS.keys()),
            width=250,
            command=lambda _: self._filter_players())
        self.pos_filter.pack(padx=10, pady=(0, 5))

        self.p_scroll = ctk.CTkScrollableFrame(self.left, fg_color="transparent")
        self.p_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(self.p_scroll, text="⏳ Ładowanie...",
                     text_color="gray").pack(pady=20)

    # ════════════════════════════════════════════
    # PRAWY PANEL
    # ════════════════════════════════════════════
    def _build_right_panel(self):
        self.right = ctk.CTkFrame(self, fg_color="transparent")
        self.right.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        self.placeholder = ctk.CTkFrame(self.right, fg_color=COLORS["panel_bg"],
                                         corner_radius=15)
        self.placeholder.pack(fill="both", expand=True)

        ctk.CTkLabel(self.placeholder, text="📊",
                     font=("Segoe UI", 64)).pack(pady=(80, 10))
        ctk.CTkLabel(self.placeholder, text="Wybierz zawodnika z listy",
                     font=("Segoe UI", 18, "bold"),
                     text_color="gray").pack()
        ctk.CTkLabel(self.placeholder,
                     text="Pełny profil analityczny:\n"
                          "oceny, frekwencja, forma, testy fizyczne, notatki",
                     text_color="#666", font=("Segoe UI", 12)).pack(pady=10)

    # ════════════════════════════════════════════
    # ŁADOWANIE ZAWODNIKÓW
    # ════════════════════════════════════════════
    def load_players(self):
        def fetch():
            from cache_manager import cache
            self.players_data = cache.get_players() or []
            self.after(0, self._filter_players)
        threading.Thread(target=fetch, daemon=True).start()

    def _on_search(self, event=None):
        if hasattr(self, '_search_timer'):
            self.after_cancel(self._search_timer)
        self._search_timer = self.after(300, self._filter_players)

    def _filter_players(self):
        for w in self.p_scroll.winfo_children():
            w.destroy()

        query   = self.search_entry.get().lower().strip()
        pos_f   = self.pos_filter.get()
        players = list(self.players_data)

        if pos_f != "Wszystkie pozycje":
            allowed = POS_GROUPS.get(pos_f, [])
            players = [p for p in players
                       if (p.get('primary_position') or '').upper() in allowed]

        if query:
            players = [p for p in players
                       if query in (p.get('full_name') or '').lower()
                       or query in str(p.get('jersey_number') or '')]

        try:
            players = sorted(players, key=lambda x: (
                POS_ORDER.get((x.get('primary_position') or '').upper(), 99),
                x.get('jersey_number') or 999))
        except Exception:
            pass

        if not players:
            ctk.CTkLabel(self.p_scroll, text="Brak wyników",
                         text_color="gray").pack(pady=20)
            return

        for p in players:
            self._create_player_btn(p)

    def _create_player_btn(self, p):
        pid  = p['id']
        nr   = p.get('jersey_number') or '-'
        name = (p.get('full_name') or '?')
        pos  = p.get('primary_position') or '?'

        bg = "#1f4a6e" if pid == self.current_pid else "#2b2b2b"

        btn_frame = ctk.CTkFrame(self.p_scroll, fg_color=bg,
                                  corner_radius=8, height=38)
        btn_frame.pack(fill="x", pady=2, padx=3)
        btn_frame.pack_propagate(False)

        inner = ctk.CTkFrame(btn_frame, fg_color="transparent", cursor="hand2")
        inner.pack(fill="both", expand=True, padx=8, pady=4)

        ctk.CTkLabel(inner, text=f"#{nr}", width=35,
                     text_color=COLORS["accent"],
                     font=("Arial", 11, "bold")).pack(side="left")

        ctk.CTkLabel(inner, text=name[:20], anchor="w",
                     font=("Segoe UI", 11)).pack(side="left", fill="x",
                                                  expand=True)

        ctk.CTkLabel(inner, text=pos, width=30, text_color="#666",
                     font=("Segoe UI", 10)).pack(side="right")

        for widget in [btn_frame, inner] + inner.winfo_children():
            widget.bind("<Button-1>",
                        lambda e, pid2=pid, nm=name, pl=p:
                        self.show_player(pid2, nm, pl))

    # ════════════════════════════════════════════
    # PROFIL ZAWODNIKA
    # ════════════════════════════════════════════
    def show_player(self, pid, name, player=None):
        if self._loading:
            return

        self.current_pid    = pid
        self.current_name   = name
        self.current_player = player

        self._filter_players()
        self.placeholder.pack_forget()
        self._build_profile_ui()
        self._load_player_data_async()

    def _build_profile_ui(self):
        if hasattr(self, 'profile_scroll'):
            self.profile_scroll.pack_forget()
            self.profile_scroll.destroy()

        self.profile_scroll = ctk.CTkScrollableFrame(self.right,
                                                      fg_color="transparent")
        self.profile_scroll.pack(fill="both", expand=True)

        ps = self.profile_scroll
        p  = self.current_player or {}

        # ── HEADER ──
        header = ctk.CTkFrame(ps, fg_color=COLORS["panel_bg"], corner_radius=15)
        header.pack(fill="x", pady=(0, 5))

        hdr_top = ctk.CTkFrame(header, fg_color="transparent")
        hdr_top.pack(fill="x", padx=20, pady=(15, 5))

        nr = p.get('jersey_number') or '-'
        ctk.CTkLabel(hdr_top, text=f"#{nr}",
                     font=("Segoe UI", 36, "bold"),
                     text_color=COLORS["accent"]).pack(side="left")

        info_frame = ctk.CTkFrame(hdr_top, fg_color="transparent")
        info_frame.pack(side="left", padx=15)

        ctk.CTkLabel(info_frame, text=self.current_name,
                     font=("Segoe UI", 22, "bold")).pack(anchor="w")

        details = []
        if p.get('primary_position'):
            details.append(f"📍 {p['primary_position']}")
        if p.get('age'):
            details.append(f"🎂 {p['age']} lat")
        if p.get('key_ability'):
            details.append(f"🎯 {p['key_ability']}")

        if details:
            ctk.CTkLabel(info_frame, text="  |  ".join(details),
                         text_color="#888",
                         font=("Segoe UI", 12)).pack(anchor="w")

        # Mini-stats w headerze
        self.header_stats = ctk.CTkFrame(hdr_top, fg_color="transparent")
        self.header_stats.pack(side="right")

        for lbl, val in [("Średnia", "—"), ("Frekwencja", "—"), ("Forma", "—")]:
            sf = ctk.CTkFrame(self.header_stats, fg_color="#2b2b2b",
                              corner_radius=8, width=90, height=55)
            sf.pack(side="left", padx=4)
            sf.pack_propagate(False)
            ctk.CTkLabel(sf, text=val, font=("Segoe UI", 16, "bold"),
                         text_color="gray").pack(pady=(8, 0))
            ctk.CTkLabel(sf, text=lbl, font=("Segoe UI", 9),
                         text_color="#666").pack()

        # ══ SELEKTOR SEZONU ══
        season_bar = ctk.CTkFrame(header, fg_color="#252525", corner_radius=8)
        season_bar.pack(fill="x", padx=20, pady=(5, 15))

        ctk.CTkLabel(season_bar, text="📅 Zakres danych:",
                     font=("Segoe UI", 11, "bold"),
                     text_color="#aaa").pack(side="left", padx=10, pady=8)

        seasons = ["Cały okres"] + database.get_available_seasons()

        self.season_selector = ctk.CTkSegmentedButton(
            season_bar,
            values=seasons,
            command=self._on_season_changed,
            font=("Segoe UI", 11),
            selected_color=COLORS["accent"],
            selected_hover_color="#2a6fa0",
            unselected_color="#333",
            unselected_hover_color="#444",
        )
        self.season_selector.pack(side="left", padx=10, pady=8)
        self.season_selector.set(self._season_filter)

        # Info o wybranym zakresie
        self.season_info_label = ctk.CTkLabel(season_bar, text="",
                                               font=("Segoe UI", 10),
                                               text_color="#666")
        self.season_info_label.pack(side="right", padx=10)
        self._update_season_info()

        # ── STATYSTYKI ──
        self.quick_stats_frame = ctk.CTkFrame(ps, fg_color=COLORS["panel_bg"],
                                               corner_radius=15)
        self.quick_stats_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(self.quick_stats_frame,
                     text="⏳ Ładowanie statystyk...",
                     text_color="gray").pack(pady=20)

        # ── WYKRES FORMY ──
        self.form_section = ctk.CTkFrame(ps, fg_color=COLORS["panel_bg"],
                                          corner_radius=15)
        self.form_section.pack(fill="x", pady=5)
        self._section_hdr(self.form_section, "📈 WYKRES FORMY")
        self.form_chart = ctk.CTkFrame(self.form_section, fg_color="transparent")
        self.form_chart.pack(fill="x", padx=15, pady=(0, 15))
        ctk.CTkLabel(self.form_chart, text="⏳",
                     text_color="gray").pack(pady=15)

        # ── FREKWENCJA ──
        self.attend_section = ctk.CTkFrame(ps, fg_color=COLORS["panel_bg"],
                                            corner_radius=15)
        self.attend_section.pack(fill="x", pady=5)
        self._section_hdr(self.attend_section, "📅 FREKWENCJA")
        self.attend_content = ctk.CTkFrame(self.attend_section,
                                            fg_color="transparent")
        self.attend_content.pack(fill="x", padx=15, pady=(0, 15))
        ctk.CTkLabel(self.attend_content, text="⏳",
                     text_color="gray").pack(pady=10)

        # ── TESTY FIZYCZNE ──
        self.fitness_section = ctk.CTkFrame(ps, fg_color=COLORS["panel_bg"],
                                             corner_radius=15)
        self.fitness_section.pack(fill="x", pady=5)
        self._section_hdr(self.fitness_section, "🏃 TESTY FIZYCZNE")
        self.fitness_content = ctk.CTkFrame(self.fitness_section,
                                             fg_color="transparent")
        self.fitness_content.pack(fill="x", padx=15, pady=(0, 15))
        ctk.CTkLabel(self.fitness_content, text="⏳",
                     text_color="gray").pack(pady=10)

        # ── HISTORIA OCEN ──
        self.history_section = ctk.CTkFrame(ps, fg_color=COLORS["panel_bg"],
                                             corner_radius=15)
        self.history_section.pack(fill="x", pady=5)

        hdr_hist = ctk.CTkFrame(self.history_section, fg_color="transparent")
        hdr_hist.pack(fill="x", padx=15, pady=(15, 5))

        ctk.CTkLabel(hdr_hist, text="📋 HISTORIA OCEN",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["accent"]).pack(side="left")

        self.filter_var = ctk.StringVar(value="Wszystkie")
        for txt, val in [("Wszystkie", "Wszystkie"), ("Mecze", "Mecz"),
                         ("Treningi", "Trening")]:
            ctk.CTkRadioButton(hdr_hist, text=txt,
                               variable=self.filter_var, value=val,
                               command=self._render_history,
                               font=("Segoe UI", 10)).pack(side="right", padx=5)

        self.history_frame = ctk.CTkFrame(self.history_section,
                                           fg_color="transparent")
        self.history_frame.pack(fill="x", padx=10, pady=(0, 15))
        ctk.CTkLabel(self.history_frame, text="⏳",
                     text_color="gray").pack(pady=15)

        # ── NOTATKA ──
        self.note_section = ctk.CTkFrame(ps, fg_color=COLORS["panel_bg"],
                                          corner_radius=15)
        self.note_section.pack(fill="x", pady=5)
        self._section_hdr(self.note_section, "📝 NOTATKA TRENERSKA")

        self.note_box = ctk.CTkTextbox(self.note_section, height=100,
                                        font=("Segoe UI", 12))
        self.note_box.pack(fill="x", padx=15, pady=(0, 5))
        self.note_box.insert("0.0", "Ładowanie...")
        self.note_box.configure(state="disabled")

        nb = ctk.CTkFrame(self.note_section, fg_color="transparent")
        nb.pack(fill="x", padx=15, pady=(0, 15))
        self.save_note_btn = ctk.CTkButton(nb, text="💾 Zapisz notatkę",
                                            width=150, fg_color=COLORS["success"],
                                            state="disabled",
                                            command=self._save_note)
        self.save_note_btn.pack(side="right")

    def _section_hdr(self, parent, text):
        ctk.CTkLabel(parent, text=text,
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["accent"]).pack(anchor="w",
                                                        padx=15, pady=(15, 5))

    def _update_season_info(self):
        """Aktualizuje tekst informacyjny o wybranym zakresie"""
        if not hasattr(self, 'season_info_label'):
            return
        if self._season_filter == "Cały okres":
            self.season_info_label.configure(text="Wyświetla całą historię zawodnika")
        else:
            start, end = self._get_season_date_range()
            if start and end:
                try:
                    s = datetime.strptime(start, "%Y-%m-%d").strftime("%d.%m.%Y")
                    e = datetime.strptime(end, "%Y-%m-%d").strftime("%d.%m.%Y")
                    self.season_info_label.configure(text=f"{s} → {e}")
                except Exception:
                    self.season_info_label.configure(text=f"Sezon {self._season_filter}")

    # ════════════════════════════════════════════
    # ŁADOWANIE DANYCH
    # ════════════════════════════════════════════
    def _load_player_data_async(self):
        self._loading = True
        pid = self.current_pid

        def fetch():
            try:
                from cache_manager import cache

                # Notatka
                note = self._notes_cache.get(pid)
                if note is None:
                    note = self._fetch_note(pid)
                    self._notes_cache[pid] = note

                # Oceny (WSZYSTKIE)
                ratings = cache.get_ratings(player_id=pid)
                self._ratings_cache[pid] = ratings

                # Eventy
                if ratings:
                    event_ids   = list(set(r['event_id'] for r in ratings))
                    missing_ids = [eid for eid in event_ids
                                   if eid not in self._events_cache]
                    if missing_ids:
                        for i in range(0, len(missing_ids), 20):
                            batch = missing_ids[i:i + 20]
                            evs   = teams.team_filter(
                                supabase.table('events')
                                .select("id,event_date,event_types")
                                .in_('id', batch)
                            ).execute().data
                            for e in evs:
                                self._events_cache[e['id']] = e

                # Frekwencja (WSZYSTKA)
                attend = self._attend_cache.get(pid)
                if attend is None:
                    attend = self._fetch_attendance(pid)
                    self._attend_cache[pid] = attend

                # Testy fizyczne (WSZYSTKIE)
                fitness = self._fitness_cache.get(pid)
                if fitness is None:
                    fitness = database.get_player_fitness_history(pid)
                    self._fitness_cache[pid] = fitness

                # Pobierz eventy z frekwencji (dla filtra sezonu)
                if attend:
                    att_event_ids = list(set(a.get('event_id') for a in attend
                                            if a.get('event_id')))
                    missing_att   = [eid for eid in att_event_ids
                                     if eid not in self._events_cache]
                    if missing_att:
                        for i in range(0, len(missing_att), 20):
                            batch = missing_att[i:i + 20]
                            evs   = teams.team_filter(
                                supabase.table('events')
                                .select("id,event_date,event_types")
                                .in_('id', batch)
                            ).execute().data
                            for e in evs:
                                self._events_cache[e['id']] = e

                self.after(0, lambda: self._render_all(note, ratings,
                                                        attend, fitness))
            except Exception as e:
                print(f"❌ Profil error: {e}")
                self.after(0, lambda: self._show_error(str(e)))
            finally:
                self._loading = False

        threading.Thread(target=fetch, daemon=True).start()

    def _fetch_note(self, player_id):
        try:
            r = supabase.table('analysis_notes').select("note") \
                .eq("player_id", player_id).execute()
            return r.data[0].get('note', '') if r.data else ''
        except Exception:
            return ''

    def _fetch_attendance(self, player_id):
        try:
            q = (supabase.table('attendance').select("status,event_id")
                 .eq('player_id', player_id))
            att = teams.team_filter(q, 'attendance').execute().data
            return att or []
        except Exception:
            return []

    # ════════════════════════════════════════════
    # RENDEROWANIE (z filtrem sezonu)
    # ════════════════════════════════════════════
    def _render_all(self, note, ratings, attend, fitness):
        if not self.winfo_exists():
            return

        self._update_season_info()

        # Filtruj dane przez sezon
        f_ratings = self._filter_ratings_by_season(ratings)
        f_attend  = self._filter_attendance_by_season(attend)
        f_fitness = self._filter_fitness_by_season(fitness)

        self._render_header_stats(f_ratings, f_attend)
        self._render_quick_stats(f_ratings, f_attend, f_fitness)
        self._render_form_chart(f_ratings)
        self._render_attendance(f_attend)
        self._render_fitness(f_fitness)
        self._render_history()
        self._render_note(note)

    # ── HEADER STATS ──
    def _render_header_stats(self, ratings, attend):
        for w in self.header_stats.winfo_children():
            w.destroy()

        avg      = self._calc_overall_avg(ratings)
        avg_text = f"{avg:.1f}" if avg else "—"
        avg_clr  = self._score_color(avg) if avg else "gray"

        if attend:
            present = sum(1 for a in attend
                          if a.get('status') in ['obecny', 'spóźniony'])
            total   = len(attend)
            freq    = (present / total * 100) if total > 0 else 0
            freq_txt = f"{freq:.0f}%"
            freq_clr = "#2ecc71" if freq >= 80 else "#f39c12" if freq >= 60 else "#e74c3c"
        else:
            freq_txt, freq_clr = "—", "gray"

        recent = self._get_recent_scores(ratings, 5)
        if len(recent) >= 2:
            trend    = recent[-1] - recent[0]
            form_txt = "📈" if trend > 0.3 else "📉" if trend < -0.3 else "➡️"
            form_clr = "#2ecc71" if trend > 0.3 else "#e74c3c" if trend < -0.3 else "#f39c12"
        else:
            form_txt, form_clr = "—", "gray"

        for val, lbl, clr in [(avg_text, "Średnia", avg_clr),
                               (freq_txt, "Frekwencja", freq_clr),
                               (form_txt, "Forma", form_clr)]:
            sf = ctk.CTkFrame(self.header_stats, fg_color="#2b2b2b",
                              corner_radius=8, width=90, height=55)
            sf.pack(side="left", padx=4)
            sf.pack_propagate(False)
            ctk.CTkLabel(sf, text=val, font=("Segoe UI", 16, "bold"),
                         text_color=clr).pack(pady=(8, 0))
            ctk.CTkLabel(sf, text=lbl, font=("Segoe UI", 9),
                         text_color="#666").pack()

    # ── STATYSTYKI SZYBKIE ──
    def _render_quick_stats(self, ratings, attend, fitness):
        for w in self.quick_stats_frame.winfo_children():
            w.destroy()

        # Season label
        if self._season_filter != "Cały okres":
            ctk.CTkLabel(self.quick_stats_frame,
                         text=f"📅 Sezon: {self._season_filter}",
                         font=("Segoe UI", 11, "bold"),
                         text_color=COLORS["warning"]).pack(anchor="w",
                                                             padx=15, pady=(10, 0))

        grid = ctk.CTkFrame(self.quick_stats_frame, fg_color="transparent")
        grid.pack(fill="x", padx=15, pady=(5, 15))
        grid.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

        match_count = 0
        train_count = 0
        for r in (ratings or []):
            ev = self._events_cache.get(r.get('event_id'), {})
            et = ev.get('event_types', [])
            if isinstance(et, str):
                et = [et]
            if any("Mecz" in t for t in et):
                match_count += 1
            else:
                train_count += 1

        scores  = self._get_all_scores(ratings)
        best    = f"{max(scores):.1f}" if scores else "—"
        present = sum(1 for a in (attend or [])
                      if a.get('status') in ['obecny', 'spóźniony'])
        absent  = sum(1 for a in (attend or [])
                      if a.get('status') == 'nieobecny')
        tests   = len(fitness or [])

        stats = [
            ("⚽", f"{match_count}", "Oceny\nmeczowe", COLORS["warning"]),
            ("🏋️", f"{train_count}", "Oceny\ntreningowe", COLORS["accent"]),
            ("✅", f"{present}", "Obecności", COLORS["success"]),
            ("❌", f"{absent}", "Nieobecności", COLORS["danger"]),
            ("🏆", best, "Najlepsza\nocena", COLORS["gold"]),
            ("🧪", f"{tests}", "Testów\nfizycznych", "#9b59b6"),
        ]

        for i, (icon, val, lbl, clr) in enumerate(stats):
            sf = ctk.CTkFrame(grid, fg_color="#252525", corner_radius=10)
            sf.grid(row=0, column=i, padx=4, pady=4, sticky="nsew")
            ctk.CTkLabel(sf, text=icon,
                         font=("Segoe UI", 18)).pack(pady=(10, 2))
            ctk.CTkLabel(sf, text=val,
                         font=("Segoe UI", 20, "bold"),
                         text_color=clr).pack()
            ctk.CTkLabel(sf, text=lbl, font=("Segoe UI", 9),
                         text_color="#666", justify="center").pack(pady=(0, 10))

    # ── WYKRES FORMY ──
    def _render_form_chart(self, ratings):
        for w in self.form_chart.winfo_children():
            w.destroy()

        scores_by_date = self._get_scores_by_date(ratings)

        if not scores_by_date:
            ctk.CTkLabel(self.form_chart, text="Brak danych do wykresu",
                         text_color="gray").pack(pady=15)
            return

        recent = scores_by_date[-20:]

        for dt_str, score, is_match in recent:
            row = ctk.CTkFrame(self.form_chart, fg_color="transparent")
            row.pack(fill="x", pady=2)

            try:
                dt_obj  = datetime.strptime(dt_str, "%Y-%m-%d")
                display = dt_obj.strftime("%d.%m")
            except Exception:
                display = dt_str[:5]

            ctk.CTkLabel(row, text=display, width=50, anchor="w",
                         text_color="gray",
                         font=("Segoe UI", 10)).pack(side="left")

            type_txt = "⚽" if is_match else "🏋️"
            ctk.CTkLabel(row, text=type_txt, width=25,
                         font=("Segoe UI", 11)).pack(side="left")

            clr   = self._score_color(score)
            bar_bg = ctk.CTkFrame(row, fg_color="#1a1a1a", height=16,
                                  corner_radius=4)
            bar_bg.pack(side="left", fill="x", expand=True, padx=5)
            bar_bg.pack_propagate(False)

            bar_w = int((score / 10) * 300)
            if bar_w > 0:
                bar = ctk.CTkFrame(bar_bg, fg_color=clr, height=16,
                                   width=bar_w, corner_radius=4)
                bar.pack(side="left")
                bar.pack_propagate(False)

            ctk.CTkLabel(row, text=f"{score:.1f}", width=40,
                         font=("Segoe UI", 11, "bold"),
                         text_color=clr).pack(side="left")

    # ── FREKWENCJA ──
    def _render_attendance(self, attend):
        for w in self.attend_content.winfo_children():
            w.destroy()

        if not attend:
            ctk.CTkLabel(self.attend_content, text="Brak danych frekwencji",
                         text_color="gray").pack(pady=10)
            return

        present = sum(1 for a in attend
                      if a.get('status') in ['obecny', 'spóźniony'])
        late    = sum(1 for a in attend if a.get('status') == 'spóźniony')
        absent  = sum(1 for a in attend if a.get('status') == 'nieobecny')
        total   = len(attend)
        freq    = (present / total * 100) if total > 0 else 0

        freq_clr = "#2ecc71" if freq >= 80 else "#f39c12" if freq >= 60 else "#e74c3c"

        bar_frame = ctk.CTkFrame(self.attend_content, fg_color="transparent")
        bar_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(bar_frame, text=f"{freq:.0f}%",
                     font=("Segoe UI", 24, "bold"),
                     text_color=freq_clr).pack(side="left", padx=10)

        bar_bg = ctk.CTkFrame(bar_frame, fg_color="#1a1a1a", height=20,
                              corner_radius=6)
        bar_bg.pack(side="left", fill="x", expand=True, padx=10)
        bar_bg.pack_propagate(False)

        fill_w = max(int(freq * 3), 0)
        bar_fill = ctk.CTkFrame(bar_bg, fg_color=freq_clr, height=20,
                                width=fill_w, corner_radius=6)
        bar_fill.pack(side="left")
        bar_fill.pack_propagate(False)

        det = ctk.CTkFrame(self.attend_content, fg_color="transparent")
        det.pack(fill="x", padx=10, pady=5)

        for txt, val, clr in [("✅ Obecny", present, "#2ecc71"),
                               ("⏰ Spóźniony", late, "#f39c12"),
                               ("❌ Nieobecny", absent, "#e74c3c"),
                               ("📊 Łącznie", total, "#aaa")]:
            ctk.CTkLabel(det, text=f"{txt}: {val}",
                         font=("Segoe UI", 11), text_color=clr).pack(
                side="left", padx=15)

    # ── TESTY FIZYCZNE ──
    def _render_fitness(self, fitness):
        for w in self.fitness_content.winfo_children():
            w.destroy()

        if not fitness:
            ctk.CTkLabel(self.fitness_content,
                         text="Brak testów fizycznych w wybranym okresie",
                         text_color="gray").pack(pady=10)
            return

        last = fitness[-1]
        prev = fitness[-2] if len(fitness) >= 2 else None

        grid = ctk.CTkFrame(self.fitness_content, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure((0, 1, 2), weight=1)

        bl   = last.get('beep_level', 0) or 0
        bs   = last.get('beep_shuttle', 0) or 0
        s150 = last.get('shuttle_150m_seconds', 0) or 0

        items = [
            ("🏃 Beep Test", f"L{bl} / S{bs}", self._beep_color(bl), 0),
            ("⏱ 150m", f"{s150:.1f}s" if s150 > 0 else "—",
             self._shuttle_color(s150), 1),
            ("📅 Data", str(last.get('test_date', ''))[:10], "#aaa", 2),
        ]

        for txt, val, clr, col in items:
            sf = ctk.CTkFrame(grid, fg_color="#252525", corner_radius=10)
            sf.grid(row=0, column=col, padx=5, pady=5, sticky="nsew")
            ctk.CTkLabel(sf, text=txt, font=("Segoe UI", 10),
                         text_color="#888").pack(pady=(10, 2))
            ctk.CTkLabel(sf, text=val, font=("Segoe UI", 16, "bold"),
                         text_color=clr).pack(pady=(0, 10))

        if prev:
            trend_frame = ctk.CTkFrame(self.fitness_content,
                                        fg_color="#1a1a1a", corner_radius=8)
            trend_frame.pack(fill="x", pady=5)

            bc   = bl + bs / 20.0
            bp   = (prev.get('beep_level', 0) or 0) + \
                   (prev.get('beep_shuttle', 0) or 0) / 20.0
            diff = bc - bp

            icon = "📈" if diff > 0 else "📉" if diff < 0 else "➡️"
            clr  = "#2ecc71" if diff > 0 else "#e74c3c" if diff < 0 else "#f39c12"
            ctk.CTkLabel(trend_frame,
                         text=f"{icon} Beep: {diff:+.1f} vs poprzedni",
                         text_color=clr,
                         font=("Segoe UI", 11)).pack(side="left",
                                                      padx=15, pady=8)

            p150 = prev.get('shuttle_150m_seconds', 0) or 0
            if s150 > 0 and p150 > 0:
                sd = p150 - s150
                si = "📈" if sd > 0 else "📉" if sd < 0 else "➡️"
                sc = "#2ecc71" if sd > 0 else "#e74c3c" if sd < 0 else "#f39c12"
                ctk.CTkLabel(trend_frame, text=f"{si} 150m: {sd:+.1f}s",
                             text_color=sc,
                             font=("Segoe UI", 11)).pack(side="left", padx=15)

        ctk.CTkLabel(self.fitness_content,
                     text=f"Testów w okresie: {len(fitness)}",
                     text_color="#666", font=("Segoe UI", 10)).pack(
            anchor="e", padx=10, pady=(5, 0))

    # ── HISTORIA OCEN ──
    def _render_history(self):
        if not hasattr(self, 'history_frame') or \
           not self.history_frame.winfo_exists():
            return

        for w in self.history_frame.winfo_children():
            w.destroy()

        pid          = self.current_pid
        all_ratings  = self._ratings_cache.get(pid, [])
        ratings      = self._filter_ratings_by_season(all_ratings)

        if not ratings:
            txt = "Brak ocen"
            if self._season_filter != "Cały okres":
                txt += f" w sezonie {self._season_filter}"
            ctk.CTkLabel(self.history_frame, text=txt,
                         text_color="gray").pack(pady=15)
            return

        events = {}
        for r in ratings:
            eid = r['event_id']
            events.setdefault(eid, []).append(r)

        def get_date(item):
            return self._events_cache.get(item[0], {}).get(
                'event_date', '0000-00-00')

        sorted_events = sorted(events.items(), key=get_date, reverse=True)
        filter_val    = self.filter_var.get()
        count         = 0

        for eid, r_list in sorted_events:
            ev = self._events_cache.get(eid)
            if not ev:
                continue

            e_types = ev.get('event_types', [])
            if isinstance(e_types, str):
                e_types = [e_types]
            is_match = any("Mecz" in t for t in e_types)

            if filter_val == "Mecz" and not is_match:
                continue
            if filter_val == "Trening" and is_match:
                continue

            self._create_history_row(eid, r_list, ev, is_match)
            count += 1

        if count == 0:
            ctk.CTkLabel(self.history_frame,
                         text="Brak wyników dla filtra",
                         text_color="gray").pack(pady=15)

    def _create_history_row(self, eid, r_list, ev, is_match):
        row = ctk.CTkFrame(self.history_frame, fg_color="#252525",
                           corner_radius=8, height=38)
        row.pack(fill="x", pady=2, padx=5)
        row.pack_propagate(False)

        try:
            dt  = datetime.strptime(ev['event_date'], "%Y-%m-%d")
            dtf = dt.strftime("%d.%m.%Y")
        except Exception:
            dtf = ev.get('event_date', '?')

        ctk.CTkLabel(row, text=dtf, width=80, anchor="w",
                     font=("Segoe UI", 10),
                     text_color="#aaa").pack(side="left", padx=8)

        type_txt = "⚽ MECZ" if is_match else "🏋️ TRENING"
        type_clr = "#e67e22" if is_match else "#3b8ed0"
        ctk.CTkLabel(row, text=type_txt, width=85,
                     font=("Segoe UI", 10, "bold"),
                     text_color=type_clr).pack(side="left", padx=3)

        criteria = (['r_offense', 'r_defense', 'r_tactics', 'r_technique']
                     if is_match else
                     ['r_engagement', 'r_consistency', 'r_tactics',
                      'r_technique', 'r_motor'])

        all_avgs = []
        for r in r_list:
            vals = [r.get(k) for k in criteria if r.get(k) is not None]
            if vals:
                all_avgs.append(sum(vals) / len(vals))

        score = sum(all_avgs) / len(all_avgs) if all_avgs else 0
        clr   = self._score_color(score)

        bar = ctk.CTkProgressBar(row, height=12,
                                  progress_color=clr, width=180)
        bar.set(score / 10)
        bar.pack(side="left", padx=8)

        ctk.CTkLabel(row, text=f"{score:.1f}", width=40,
                     font=("Segoe UI", 12, "bold"),
                     text_color=clr).pack(side="left", padx=3)

        ctk.CTkLabel(row, text=f"({len(r_list)})",
                     font=("Segoe UI", 9),
                     text_color="#666").pack(side="left", padx=3)

        ctk.CTkButton(row, text="🗑", width=28, height=26,
                      fg_color="transparent", hover_color="#c0392b",
                      text_color="#666",
                      command=lambda e_id=eid:
                      self.delete_event_ratings(e_id)).pack(side="right",
                                                             padx=5)

    # ── NOTATKA ──
    def _render_note(self, note):
        if not self.note_box or not self.note_box.winfo_exists():
            return
        self.note_box.configure(state="normal")
        self.note_box.delete("0.0", "end")
        if note:
            self.note_box.insert("0.0", note)
        self.save_note_btn.configure(state="normal")

    def _save_note(self):
        if not self.note_box or not self.current_pid:
            return
        txt = self.note_box.get("0.0", "end").strip()
        pid = self.current_pid
        self._notes_cache[pid] = txt

        def save():
            try:
                # team_code: notatka należy do kadry, w której powstała.
                # Bez tego analiza drużyny II mieszała się z I.
                code = teams.get_current_team()
                supabase.table('analysis_notes').upsert(
                    {"player_id": pid, "note": txt,
                     "team_code": None if code == teams.ALL_TEAMS else code},
                    on_conflict="player_id").execute()
                self.after(0, lambda: self._notify("✅ Notatka zapisana!"))
            except Exception as e:
                self.after(0, lambda: msgbox.showerror("Błąd", str(e)))

        threading.Thread(target=save, daemon=True).start()

    # ════════════════════════════════════════════
    # HELPERS
    # ════════════════════════════════════════════
    def _score_color(self, score):
        if not score:
            return "gray"
        if score >= 8.0:
            return "#2ecc71"
        if score >= 6.0:
            return "#3498db"
        if score >= 4.5:
            return "#f39c12"
        return "#e74c3c"

    def _beep_color(self, level):
        if level >= 11:
            return "#FFD700"
        if level >= 9:
            return "#2ecc71"
        if level >= 7:
            return "#3498db"
        if level >= 5:
            return "#f39c12"
        return "#e74c3c"

    def _shuttle_color(self, seconds):
        if seconds <= 0:
            return "gray"
        if seconds <= 28:
            return "#FFD700"
        if seconds <= 30:
            return "#2ecc71"
        if seconds <= 33:
            return "#3498db"
        if seconds <= 36:
            return "#f39c12"
        return "#e74c3c"

    def _calc_overall_avg(self, ratings):
        scores = self._get_all_scores(ratings)
        return sum(scores) / len(scores) if scores else None

    def _get_all_scores(self, ratings):
        results = []
        for r in (ratings or []):
            ev = self._events_cache.get(r.get('event_id'), {})
            et = ev.get('event_types', [])
            if isinstance(et, str):
                et = [et]
            is_match = any("Mecz" in t for t in et)

            criteria = (['r_offense', 'r_defense', 'r_tactics', 'r_technique']
                         if is_match else
                         ['r_engagement', 'r_consistency', 'r_tactics',
                          'r_technique', 'r_motor'])

            vals = [r.get(k) for k in criteria if r.get(k) is not None]
            if vals:
                results.append(sum(vals) / len(vals))
        return results

    def _get_recent_scores(self, ratings, n=5):
        by_date = self._get_scores_by_date(ratings)
        return [s for _, s, _ in by_date[-n:]]

    def _get_scores_by_date(self, ratings):
        events = {}
        for r in (ratings or []):
            eid = r['event_id']
            events.setdefault(eid, []).append(r)

        result = []
        for eid, r_list in events.items():
            ev = self._events_cache.get(eid)
            if not ev:
                continue
            dt      = ev.get('event_date', '0000-00-00')
            e_types = ev.get('event_types', [])
            if isinstance(e_types, str):
                e_types = [e_types]
            is_match = any("Mecz" in t for t in e_types)

            criteria = (['r_offense', 'r_defense', 'r_tactics', 'r_technique']
                         if is_match else
                         ['r_engagement', 'r_consistency', 'r_tactics',
                          'r_technique', 'r_motor'])

            all_avgs = []
            for r in r_list:
                vals = [r.get(k) for k in criteria if r.get(k) is not None]
                if vals:
                    all_avgs.append(sum(vals) / len(vals))

            if all_avgs:
                result.append((dt, sum(all_avgs) / len(all_avgs), is_match))

        result.sort(key=lambda x: x[0])
        return result

    # ════════════════════════════════════════════
    # AKCJE
    # ════════════════════════════════════════════
    def delete_event_ratings(self, event_id):
        if not msgbox.askyesno("Usuń", "Usunąć oceny z tego dnia?"):
            return
        pid = self.current_pid

        def delete():
            try:
                supabase.table('ratings').delete() \
                    .eq('event_id', event_id) \
                    .eq('player_id', pid).execute()
                from cache_manager import cache
                cache.invalidate_ratings()
                if pid in self._ratings_cache:
                    del self._ratings_cache[pid]
                self.after(0, self._load_player_data_async)
            except Exception as e:
                self.after(0, lambda: msgbox.showerror("Błąd", str(e)))

        threading.Thread(target=delete, daemon=True).start()

    def force_refresh(self):
        self._notes_cache.clear()
        self._ratings_cache.clear()
        self._events_cache.clear()
        self._attend_cache.clear()
        self._fitness_cache.clear()
        from cache_manager import cache
        cache.invalidate("players")
        cache.invalidate("ratings")
        self.load_players()
        if self.current_pid:
            self._load_player_data_async()

    def refresh_content(self):
        if self.current_pid:
            self._load_player_data_async()

    def _notify(self, msg):
        n = ctk.CTkFrame(self, fg_color="#2ecc71", corner_radius=8, height=40)
        n.pack(side="bottom", fill="x", padx=20, pady=5)
        n.pack_propagate(False)
        ctk.CTkLabel(n, text=msg, font=("Segoe UI", 12, "bold"),
                     text_color="white").pack(expand=True)
        n.lift()
        self.after(2000, lambda: (n.pack_forget(), n.destroy()))

    def _show_error(self, message):
        if hasattr(self, 'quick_stats_frame') and \
           self.quick_stats_frame.winfo_exists():
            for w in self.quick_stats_frame.winfo_children():
                w.destroy()
            ctk.CTkLabel(self.quick_stats_frame,
                         text=f"❌ {message}", text_color="red").pack(pady=20)