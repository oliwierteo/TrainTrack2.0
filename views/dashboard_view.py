# views/dashboard_view.py - MODERN DASHBOARD v4.4 - FAST LOAD

import customtkinter as ctk
from datetime import datetime, timedelta
import database
import teams
from collections import Counter
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from logger import logger

COLORS = {
    "bg_dark":   "#121212",
    "card_bg":   "#1e1e1e",
    "accent":    "#3b8ed0",
    "success":   "#2ecc71",
    "warning":   "#f39c12",
    "danger":    "#e74c3c",
    "text_gray": "#aaaaaa",
    "white":     "#ffffff",
    "gold":      "#FFD700",
    "purple":    "#9b59b6",
}

SCROLL_THRESHOLD_H = 900


class DashboardView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg_dark"])

        self._loading    = False
        self.data        = {}
        self._scale      = 1.0
        self._last_size  = (0, 0)
        self._use_scroll = False
        self._executor   = ThreadPoolExecutor(max_workers=6)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._create_header()
        self._create_content()

        # Natychmiast zacznij ładować
        self.after(10, self.refresh_data_async)
        self.after(200, self._on_resize_check)

    def destroy(self):
        """Cleanup executor przy zamykaniu"""
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass
        super().destroy()

    # ════════════════════════════════════════════
    # SKALOWANIE
    # ════════════════════════════════════════════
    def _compute_scale(self):
        try:
            w = self.winfo_width()
            if w < 100:
                return 1.0
            return max(0.72, min(w / 1440, 1.60))
        except Exception:
            return 1.0

    def _should_scroll(self):
        try:
            return self.winfo_height() < SCROLL_THRESHOLD_H
        except Exception:
            return False

    def _on_resize_check(self):
        # FIX: self.after() po zniszczeniu widgetu rzuca TclError, a petla
        # rezerwowała się dalej poza try/except - błąd w logach co 500 ms.
        try:
            if not self.winfo_exists():
                return
            w, h = self.winfo_width(), self.winfo_height()
            if (w, h) != self._last_size and w > 100:
                old_scroll       = self._use_scroll
                self._last_size  = (w, h)
                self._scale      = self._compute_scale()
                self._use_scroll = self._should_scroll()
                if old_scroll != self._use_scroll:
                    self._rebuild_content()
            self.after(500, self._on_resize_check)
        except Exception:
            return

    def _fs(self, base: int) -> int:
        return max(8, int(base * self._scale))

    def _sz(self, base: int) -> int:
        return max(1, int(base * self._scale))

    def _rebuild_content(self):
        if hasattr(self, 'content_wrapper') and self.content_wrapper.winfo_exists():
            self.content_wrapper.destroy()
        self._create_content()
        if self.data:
            self._render_all()

    # ════════════════════════════════════════════
    # HEADER
    # ════════════════════════════════════════════
    def _create_header(self):
        hour     = datetime.now().hour
        greeting = "Dzień dobry" if 5 <= hour < 18 else "Dobry wieczór"

        try:
            user_name = (
                database.CURRENT_USER_EMAIL.split('@')[0].capitalize()
                if hasattr(database, 'CURRENT_USER_EMAIL') and database.CURRENT_USER_EMAIL
                else "Trenerze"
            )
        except Exception:
            user_name = "Trenerze"

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew",
                    padx=self._sz(30), pady=(self._sz(20), self._sz(5)))

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left")

        ctk.CTkLabel(
            left, text=f"{greeting}, {user_name}!",
            font=("Segoe UI", self._fs(28), "bold"),
            text_color=COLORS["white"],
        ).pack(anchor="w")

        today_str = datetime.now().strftime("%A, %d %B %Y")
        ctk.CTkLabel(
            left,
            text=f"📅 {today_str}  |  ⚽ {teams.scope_label()}"
                 f"  |  Sezon {database.CURRENT_SEASON}",
            font=("Segoe UI", self._fs(12)),
            text_color=COLORS["text_gray"],
        ).pack(anchor="w", pady=(2, 0))

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side="right")

        ctk.CTkButton(
            right, text="🔄 Odśwież",
            width=self._sz(110), height=self._sz(32),
            fg_color="#333", hover_color="#444",
            font=("Segoe UI", self._fs(12)),
            command=self.force_refresh,
        ).pack(side="right")

        ctk.CTkLabel(
            right, text=f"⚽ {database.CURRENT_CLUB}",
            font=("Segoe UI", self._fs(12), "bold"),
            text_color=COLORS["accent"],
        ).pack(side="right", padx=self._sz(15))

    # ════════════════════════════════════════════
    # CONTENT
    # ════════════════════════════════════════════
    def _create_content(self):
        if self._use_scroll:
            wrapper = ctk.CTkScrollableFrame(self, fg_color="transparent")
            wrapper.grid(row=1, column=0, sticky="nsew",
                         padx=self._sz(20), pady=(self._sz(5), self._sz(10)))
            self.content_wrapper = wrapper
            self._build_inner(wrapper, stretch=False)
        else:
            wrapper = ctk.CTkFrame(self, fg_color="transparent")
            wrapper.grid(row=1, column=0, sticky="nsew",
                         padx=self._sz(20), pady=(self._sz(5), self._sz(10)))
            wrapper.grid_columnconfigure(0, weight=1)
            wrapper.grid_rowconfigure(0, weight=0)
            wrapper.grid_rowconfigure(1, weight=3)
            wrapper.grid_rowconfigure(2, weight=3)
            wrapper.grid_rowconfigure(3, weight=4)
            self.content_wrapper = wrapper
            self._build_inner(wrapper, stretch=True)

        self.content = wrapper

    def _build_inner(self, parent, stretch: bool):
        pad = self._sz(6)

        # ROW 0: Stats
        self.stats_frame = ctk.CTkFrame(parent, fg_color="transparent")
        if stretch:
            self.stats_frame.grid(row=0, column=0, sticky="ew", pady=(0, pad))
        else:
            self.stats_frame.pack(fill="x", pady=(0, pad))
        self.stats_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        self.stat_cards = {}
        for i, (key, icon, label, default, color) in enumerate([
            ("players",    "👥", "Kadra",       "0", COLORS["accent"]),
            ("healthy",    "💪", "Zdrowi",      "0", COLORS["success"]),
            ("injured",    "🏥", "Kontuzje",    "0", COLORS["danger"]),
            ("next_event", "📅", "Nast. event", "—", COLORS["warning"]),
            ("scouting",   "🔍", "Scouting",    "0", COLORS["purple"]),
        ]):
            card = self._create_stat_card(self.stats_frame, icon, default, label, color)
            card.grid(row=0, column=i, padx=pad, pady=pad, sticky="nsew")
            self.stat_cards[key] = card

        # ROW 1
        row2 = ctk.CTkFrame(parent, fg_color="transparent")
        if stretch:
            row2.grid(row=1, column=0, sticky="nsew", pady=(0, pad))
        else:
            row2.pack(fill="x", pady=(0, pad))
        row2.grid_columnconfigure(0, weight=3)
        row2.grid_columnconfigure(1, weight=2)
        if stretch:
            row2.grid_rowconfigure(0, weight=1)

        self.training_card = self._create_section_card(row2, "📅 NAJBLIŻSZE WYDARZENIE")
        self.training_card.grid(row=0, column=0, padx=(0, pad), sticky="nsew")
        self.health_card = self._create_section_card(row2, "🏥 RAPORT MEDYCZNY")
        self.health_card.grid(row=0, column=1, padx=(pad, 0), sticky="nsew")

        # ROW 2
        row3 = ctk.CTkFrame(parent, fg_color="transparent")
        if stretch:
            row3.grid(row=2, column=0, sticky="nsew", pady=(0, pad))
        else:
            row3.pack(fill="x", pady=(0, pad))
        row3.grid_columnconfigure((0, 1), weight=1)
        if stretch:
            row3.grid_rowconfigure(0, weight=1)

        self.attendance_card = self._create_section_card(row3, "📊 FREKWENCJA (30 DNI)")
        self.attendance_card.grid(row=0, column=0, padx=(0, pad), sticky="nsew")
        self.scouting_card = self._create_section_card(row3, "🔍 TOP TALENTY SCOUTINGOWE")
        self.scouting_card.grid(row=0, column=1, padx=(pad, 0), sticky="nsew")

        # ROW 3
        row4 = ctk.CTkFrame(parent, fg_color="transparent")
        if stretch:
            row4.grid(row=3, column=0, sticky="nsew")
        else:
            row4.pack(fill="x")
        row4.grid_columnconfigure((0, 1), weight=1)
        if stretch:
            row4.grid_rowconfigure(0, weight=1)

        self.top5_card = self._create_section_card(row4, "🏆 TOP 5 — NAJWYŻSZE OCENY")
        self.top5_card.grid(row=0, column=0, padx=(0, pad), sticky="nsew")
        self.log_card_wrapper = self._create_section_card(row4, "🔔 OSTATNIA AKTYWNOŚĆ SZTABU")
        self.log_card_wrapper.grid(row=0, column=1, padx=(pad, 0), sticky="nsew")

    # ════════════════════════════════════════════
    # CARD BUILDERS
    # ════════════════════════════════════════════
    def _create_stat_card(self, parent, icon, value, label, color):
        card = ctk.CTkFrame(parent, fg_color=COLORS["card_bg"],
                            corner_radius=self._sz(12), height=self._sz(95))
        card.pack_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(expand=True)

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack()

        ctk.CTkLabel(top, text=icon,
                     font=("Segoe UI", self._fs(18))
                     ).pack(side="left", padx=(0, self._sz(4)))

        val_label = ctk.CTkLabel(top, text=value,
                                 font=("Segoe UI", self._fs(26), "bold"),
                                 text_color=color)
        val_label.pack(side="left")

        ctk.CTkLabel(inner, text=label,
                     font=("Segoe UI", self._fs(10)),
                     text_color=COLORS["text_gray"]).pack()

        card._val_label = val_label
        return card

    def _create_section_card(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color=COLORS["card_bg"],
                            corner_radius=self._sz(14))
        card.grid_rowconfigure(1, weight=1)
        card.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew",
                 padx=self._sz(16), pady=(self._sz(12), self._sz(6)))
        ctk.CTkLabel(hdr, text=title,
                     font=("Segoe UI", self._fs(13), "bold"),
                     text_color=COLORS["accent"]).pack(side="left")

        content_area = ctk.CTkFrame(card, fg_color="transparent")
        content_area.grid(row=1, column=0, sticky="nsew",
                          padx=self._sz(16), pady=(0, self._sz(12)))

        ctk.CTkLabel(content_area, text="⏳ Ładowanie...",
                     text_color=COLORS["text_gray"],
                     font=("Segoe UI", self._fs(12))).pack(pady=self._sz(12))

        card._content = content_area
        return card

    # ════════════════════════════════════════════
    # ⚡ PARALLEL ASYNC DATA — KLUCZ DO SZYBKOŚCI
    # ════════════════════════════════════════════
    def refresh_data_async(self):
        if self._loading:
            return
        self._loading = True

        def fetch_all():
            try:
                if not self.winfo_exists():
                    return

                from cache_manager import cache

                # ── FAZA 1: Równoległe pobieranie wszystkich danych ──
                results = {}

                def _fetch_players():
                    return cache.get_players(force_refresh=False)

                def _fetch_events():
                    return cache.get_upcoming_events(limit=5, force_refresh=False)

                def _fetch_scouting():
                    return cache.get_scouting_targets(force_refresh=False)

                def _fetch_logs():
                    return cache.get_activity_log(limit=5, force_refresh=False)

                def _fetch_past_events():
                    today_dt = datetime.now().date()
                    d30 = (today_dt - timedelta(days=30)).isoformat()
                    return cache.get_events(
                        start_date=d30,
                        end_date=today_dt.isoformat(),
                        force_refresh=False
                    )

                # Wszystkie zapytania lecą RÓWNOLEGLE
                futures = {
                    self._executor.submit(_fetch_players):     'players',
                    self._executor.submit(_fetch_events):      'events',
                    self._executor.submit(_fetch_scouting):    'scouting',
                    self._executor.submit(_fetch_logs):        'logs',
                    self._executor.submit(_fetch_past_events): 'past_events',
                }

                for future in as_completed(futures, timeout=10):
                    key = futures[future]
                    try:
                        results[key] = future.result()
                    except Exception as e:
                        logger.error(f"Fetch {key}: {e}")
                        results[key] = [] if key != 'events' else None

                if not self.winfo_exists():
                    return

                # ── FAZA 2: Przetwarzanie wyników ──
                all_players = results.get('players', [])
                upcoming    = results.get('events')
                targets_raw = results.get('scouting', [])
                logs        = results.get('logs', [])
                past_events = results.get('past_events', [])

                self.data = {
                    'training':   upcoming[0] if upcoming else None,
                    'health':     [p for p in all_players
                                   if p.get('health_status') != 'zdrowy'],
                    'scouting':   sorted(targets_raw,
                                         key=lambda x: x.get('rating', 0),
                                         reverse=True)[:3],
                    'attendance': None,
                    'logs':       logs,
                    'players':    all_players,
                    'top5':       [],
                }

                # ── FAZA 3: Frekwencja + TOP5 (jeśli są eventy) ──
                if past_events:
                    try:
                        eids = [e['id'] for e in past_events]
                        att = cache.get_attendance(
                            event_ids=eids, force_refresh=False
                        )
                        self.data['attendance'] = att

                        # TOP5 — równolegle pobierz oceny
                        self._calculate_top5_parallel(
                            all_players, att, past_events, cache
                        )
                    except Exception as e:
                        logger.error(f"Attendance/TOP5: {e}")

                # ── FAZA 4: Renderuj NATYCHMIAST ──
                if self.winfo_exists():
                    self.after(0, self._render_all)

            except Exception as e:
                logger.error(f"Dashboard fetch: {e}")
            finally:
                self._loading = False

        threading.Thread(target=fetch_all, daemon=True).start()

    def _calculate_top5_parallel(self, players, attendance, events, cache):
        """Pobiera oceny RÓWNOLEGLE dla wszystkich zawodników"""
        try:
            event_map = {e['id']: e for e in events}

            def _get_player_score(p):
                pid     = p['id']
                ratings = cache.get_ratings(player_id=pid, force_refresh=False)
                if not ratings:
                    return None

                scores = []
                for r in ratings:
                    ev = event_map.get(r.get('event_id'), {})
                    et = ev.get('event_types', [])
                    if isinstance(et, str):
                        et = [et]
                    is_match = any("Mecz" in t for t in et)

                    criteria = (
                        ['r_offense', 'r_defense', 'r_tactics', 'r_technique']
                        if is_match else
                        ['r_engagement', 'r_consistency', 'r_tactics',
                         'r_technique', 'r_motor']
                    )
                    vals = [r.get(k) for k in criteria if r.get(k) is not None]
                    if vals:
                        scores.append(sum(vals) / len(vals))

                if scores and len(scores) >= 2:
                    return {
                        'avg':      sum(scores) / len(scores),
                        'count':    len(scores),
                        'name':     p.get('full_name', '?'),
                        'position': p.get('primary_position', '?'),
                        'number':   p.get('jersey_number') or '-',
                    }
                return None

            # Równoległe pobieranie ocen
            futures = {
                self._executor.submit(_get_player_score, p): p['id']
                for p in players
            }

            all_scores = []
            for future in as_completed(futures, timeout=8):
                try:
                    result = future.result()
                    if result:
                        all_scores.append(result)
                except Exception:
                    pass

            self.data['top5'] = sorted(
                all_scores,
                key=lambda x: x['avg'],
                reverse=True
            )[:5]

        except Exception as e:
            logger.error(f"TOP5 parallel: {e}")
            self.data['top5'] = []

    # ════════════════════════════════════════════
    # RENDERING — BEZ OPÓŹNIEŃ after()
    # ════════════════════════════════════════════
    def _render_all(self):
        if not self.winfo_exists():
            return

        self._render_stats()
        self._render_training()
        self._render_health()
        self._render_attendance()
        self._render_scouting()
        self._render_top5()
        self._render_logs()

    def _render_stats(self):
        players = self.data.get('players', [])
        healthy = [p for p in players if p.get('health_status') == 'zdrowy']
        injured = self.data.get('health', [])
        scout   = self.data.get('scouting', []) or []
        ev      = self.data.get('training')

        self.stat_cards['players']._val_label.configure(text=str(len(players)))
        self.stat_cards['healthy']._val_label.configure(text=str(len(healthy)))

        inj_count = len(injured)
        self.stat_cards['injured']._val_label.configure(
            text=str(inj_count),
            text_color=COLORS["danger"] if inj_count > 0 else COLORS["success"])

        if ev:
            try:
                dt   = datetime.strptime(ev['event_date'], "%Y-%m-%d")
                diff = (dt.date() - datetime.now().date()).days
                ev_txt = ("DZIŚ" if diff == 0 else
                          "JUTRO" if diff == 1 else f"za {diff}d")
            except Exception:
                ev_txt = "—"
            self.stat_cards['next_event']._val_label.configure(text=ev_txt)
        else:
            self.stat_cards['next_event']._val_label.configure(text="—")

        self.stat_cards['scouting']._val_label.configure(text=str(len(scout)))

    def _render_training(self):
        if not self.winfo_exists():
            return
        cnt = self.training_card._content
        for w in cnt.winfo_children():
            w.destroy()

        ev = self.data.get('training')
        if not ev:
            ctk.CTkLabel(cnt, text="Brak nadchodzących wydarzeń",
                         text_color=COLORS["text_gray"],
                         font=("Segoe UI", self._fs(13))).pack(pady=self._sz(20))
            return

        ev_date = ev.get('event_date', '')
        today   = datetime.now().date().isoformat()

        if ev_date == today:
            badge_text, badge_color = "DZISIAJ", COLORS["success"]
        elif ev_date > today:
            try:
                dt   = datetime.strptime(ev_date, "%Y-%m-%d")
                diff = (dt.date() - datetime.now().date()).days
                badge_text = f"ZA {diff} DNI" if diff > 1 else "JUTRO"
            except Exception:
                badge_text = "NADCHODZĄCY"
            badge_color = COLORS["accent"]
        else:
            badge_text, badge_color = "MINIONY", COLORS["text_gray"]

        top = ctk.CTkFrame(cnt, fg_color="transparent")
        top.pack(fill="x")

        badge = ctk.CTkFrame(top, fg_color=badge_color, corner_radius=self._sz(6))
        badge.pack(side="left")
        ctk.CTkLabel(badge, text=f" {badge_text} ",
                     font=("Segoe UI", self._fs(11), "bold"),
                     text_color="white").pack(padx=self._sz(8), pady=self._sz(3))

        types     = ev.get('event_types', [])
        types_str = ', '.join(types) if isinstance(types, list) else str(types)
        type_badge = ctk.CTkFrame(top, fg_color="#2a2a3a", corner_radius=self._sz(6))
        type_badge.pack(side="left", padx=self._sz(8))
        ctk.CTkLabel(type_badge, text=f" {types_str} ",
                     font=("Segoe UI", self._fs(11)),
                     text_color=COLORS["warning"]).pack(padx=self._sz(6), pady=self._sz(3))

        try:
            date_display = datetime.strptime(ev_date, "%Y-%m-%d").strftime("%d.%m.%Y (%A)")
        except Exception:
            date_display = ev_date

        ctk.CTkLabel(cnt, text=date_display,
                     font=("Segoe UI", self._fs(22), "bold")
                     ).pack(pady=(self._sz(10), self._sz(2)))

        time_txt = ev.get('start_time', '')
        end_time = ev.get('end_time', '')
        time_display = (f"🕐 {time_txt} – {end_time}" if time_txt and end_time
                        else f"🕐 {time_txt}" if time_txt else "")
        if time_display:
            ctk.CTkLabel(cnt, text=time_display,
                         font=("Segoe UI", self._fs(14)),
                         text_color=COLORS["text_gray"]).pack()

        loc = ev.get('location', '')
        if loc:
            ctk.CTkLabel(cnt, text=f"📍 {loc}",
                         font=("Segoe UI", self._fs(11)),
                         text_color="#666").pack(pady=(self._sz(4), 0))

    def _render_health(self):
        if not self.winfo_exists():
            return
        cnt = self.health_card._content
        for w in cnt.winfo_children():
            w.destroy()

        health_list = self.data.get('health', [])
        count       = len(health_list)
        clr         = COLORS["danger"] if count > 0 else COLORS["success"]

        top = ctk.CTkFrame(cnt, fg_color="transparent")
        top.pack(fill="x")

        ctk.CTkLabel(top, text=str(count),
                     font=("Segoe UI", self._fs(40), "bold"),
                     text_color=clr).pack(side="left")

        ctk.CTkLabel(top, text="OSÓB POZA KADRĄ" if count > 0 else "WSZYSCY ZDROWI ✓",
                     font=("Segoe UI", self._fs(12)),
                     text_color=clr).pack(side="left", padx=self._sz(12),
                                          pady=(self._sz(10), 0))

        for p in health_list[:5]:
            row = ctk.CTkFrame(cnt, fg_color="#252525",
                               corner_radius=self._sz(8), height=self._sz(34))
            row.pack(fill="x", pady=self._sz(2))
            row.pack_propagate(False)

            health = p.get('health_status', '?')
            h_icon = "🏥" if health == 'kontuzja' else "⚠️"
            h_clr  = COLORS["danger"] if health == 'kontuzja' else COLORS["warning"]

            ctk.CTkLabel(row, text=f"{h_icon} {p.get('full_name', '?')}",
                         font=("Segoe UI", self._fs(11)), anchor="w"
                         ).pack(side="left", padx=self._sz(10), pady=self._sz(3))

            ctk.CTkLabel(row, text=health.upper(),
                         font=("Segoe UI", self._fs(9), "bold"),
                         text_color=h_clr).pack(side="right", padx=self._sz(10))

            ret = p.get('return_date')
            if ret:
                ctk.CTkLabel(row, text=f"↩ {str(ret)[:10]}",
                             font=("Segoe UI", self._fs(9)),
                             text_color="#666").pack(side="right", padx=self._sz(5))

    def _render_attendance(self):
        if not self.winfo_exists():
            return
        cnt = self.attendance_card._content
        for w in cnt.winfo_children():
            w.destroy()

        att_data = self.data.get('attendance')
        players  = self.data.get('players', [])

        if not att_data or not players:
            ctk.CTkLabel(cnt, text="Brak danych o frekwencji",
                         text_color=COLORS["text_gray"],
                         font=("Segoe UI", self._fs(13))).pack(pady=self._sz(20))
            return

        player_names = {p['id']: p.get('full_name', '?') for p in players}

        pres  = len([a for a in att_data if a.get('status') in ['obecny', 'spóźniony']])
        total = len(att_data)
        perc  = int((pres / total) * 100) if total > 0 else 0

        top = ctk.CTkFrame(cnt, fg_color="transparent")
        top.pack(fill="x")

        perc_clr = (COLORS["success"] if perc >= 80 else
                    COLORS["warning"] if perc >= 60 else COLORS["danger"])

        ctk.CTkLabel(top, text=f"{perc}%",
                     font=("Segoe UI", self._fs(34), "bold"),
                     text_color=perc_clr).pack(side="left")
        ctk.CTkLabel(top, text="ŚREDNIA\nOBECNOŚCI",
                     font=("Segoe UI", self._fs(10)),
                     text_color=COLORS["text_gray"],
                     justify="left").pack(side="left", padx=self._sz(10),
                                          pady=(self._sz(6), 0))

        bar_bg = ctk.CTkFrame(cnt, fg_color="#252525",
                              height=self._sz(8), corner_radius=self._sz(4))
        bar_bg.pack(fill="x", pady=(self._sz(4), self._sz(8)))
        bar_bg.pack_propagate(False)

        fill_w = max(int(perc * 2.5 * self._scale), 0)
        if fill_w > 0:
            ctk.CTkFrame(bar_bg, fg_color=perc_clr, height=self._sz(8),
                         width=fill_w, corner_radius=self._sz(4)).pack(side="left")

        presence_counts = Counter()
        absence_counts  = Counter()
        for a in att_data:
            pid, st = a.get('player_id'), a.get('status', '')
            if st in ['obecny', 'spóźniony']:
                presence_counts[pid] += 1
            elif st == 'nieobecny':
                absence_counts[pid] += 1

        grid = ctk.CTkFrame(cnt, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure((0, 1), weight=1)
        grid.grid_rowconfigure(0, weight=1)

        # LIDERZY — 5
        lead_frame = ctk.CTkFrame(grid, fg_color="#1a2a1a",
                                  corner_radius=self._sz(10))
        lead_frame.grid(row=0, column=0, padx=(0, self._sz(4)),
                        pady=self._sz(2), sticky="nsew")

        ctk.CTkLabel(lead_frame, text="🏆 LIDERZY",
                     font=("Segoe UI", self._fs(11), "bold"),
                     text_color=COLORS["success"]
                     ).pack(anchor="w", padx=self._sz(10),
                            pady=(self._sz(8), self._sz(3)))

        for pid, count in presence_counts.most_common(5):
            name = player_names.get(pid, '?')[:18]
            ctk.CTkLabel(lead_frame, text=f"  {name} ({count})",
                         font=("Segoe UI", self._fs(10)),
                         text_color="#aaa", anchor="w"
                         ).pack(anchor="w", padx=self._sz(10), pady=0)

        # DO POPRAWY — 5
        warn_frame = ctk.CTkFrame(grid, fg_color="#2a1a1a",
                                  corner_radius=self._sz(10))
        warn_frame.grid(row=0, column=1, padx=(self._sz(4), 0),
                        pady=self._sz(2), sticky="nsew")

        ctk.CTkLabel(warn_frame, text="⚠️ DO POPRAWY",
                     font=("Segoe UI", self._fs(11), "bold"),
                     text_color=COLORS["danger"]
                     ).pack(anchor="w", padx=self._sz(10),
                            pady=(self._sz(8), self._sz(3)))

        worst = absence_counts.most_common(5)
        if worst:
            for pid, count in worst:
                name = player_names.get(pid, '?')[:18]
                ctk.CTkLabel(warn_frame, text=f"  {name} ({count})",
                             font=("Segoe UI", self._fs(10)),
                             text_color="#aaa", anchor="w"
                             ).pack(anchor="w", padx=self._sz(10), pady=0)
        else:
            ctk.CTkLabel(warn_frame, text="  Wszyscy obecni! 🎉",
                         font=("Segoe UI", self._fs(10)),
                         text_color=COLORS["success"]
                         ).pack(anchor="w", padx=self._sz(10), pady=self._sz(4))

    def _render_scouting(self):
        if not self.winfo_exists():
            return
        cnt = self.scouting_card._content
        for w in cnt.winfo_children():
            w.destroy()

        targets = self.data.get('scouting')
        if not targets:
            ctk.CTkLabel(cnt, text="Brak celów scoutingowych",
                         text_color=COLORS["text_gray"],
                         font=("Segoe UI", self._fs(12))).pack(pady=self._sz(20))
            return

        for i, item in enumerate(targets[:3]):
            row = ctk.CTkFrame(cnt,
                               fg_color="#252525" if i % 2 == 0 else "#2b2b2b",
                               corner_radius=self._sz(8), height=self._sz(38))
            row.pack(fill="x", pady=self._sz(2))
            row.pack_propagate(False)

            ctk.CTkLabel(row, text=item.get('position', '?'), width=self._sz(36),
                         font=("Segoe UI", self._fs(10), "bold"),
                         text_color=COLORS["accent"]
                         ).pack(side="left", padx=self._sz(10), pady=self._sz(3))

            ctk.CTkLabel(row, text=(item.get('full_name') or '?')[:22],
                         font=("Segoe UI", self._fs(11), "bold"), anchor="w"
                         ).pack(side="left", fill="x", expand=True)

            club = (item.get('current_club') or '')[:15]
            if club:
                ctk.CTkLabel(row, text=club,
                             font=("Segoe UI", self._fs(9)),
                             text_color="#666").pack(side="left", padx=self._sz(5))

            rating = item.get('rating', 0) or 0
            ctk.CTkLabel(row, text="⭐" * rating,
                         font=("Segoe UI", self._fs(10))
                         ).pack(side="right", padx=self._sz(10))

    def _render_top5(self):
        if not self.winfo_exists():
            return
        cnt = self.top5_card._content
        for w in cnt.winfo_children():
            w.destroy()

        top5 = self.data.get('top5', [])
        if not top5:
            ctk.CTkLabel(cnt,
                         text="Za mało danych — oceń zawodników\nna treningach i meczach",
                         text_color=COLORS["text_gray"],
                         font=("Segoe UI", self._fs(12)),
                         justify="center").pack(pady=self._sz(20))
            return

        medals    = ["🥇", "🥈", "🥉", "4.", "5."]
        medal_clr = [COLORS["gold"], "#C0C0C0", "#CD7F32",
                     COLORS["text_gray"], COLORS["text_gray"]]

        for i, p in enumerate(top5):
            row = ctk.CTkFrame(cnt,
                               fg_color="#252525" if i % 2 == 0 else "#2b2b2b",
                               corner_radius=self._sz(10), height=self._sz(46))
            row.pack(fill="x", pady=self._sz(2))
            row.pack_propagate(False)

            ctk.CTkLabel(row, text=medals[i] if i < 5 else f"{i+1}.",
                         width=self._sz(36),
                         font=("Segoe UI", self._fs(16), "bold"),
                         text_color=medal_clr[i] if i < 5 else COLORS["text_gray"]
                         ).pack(side="left", padx=self._sz(8))

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="both", expand=True, pady=self._sz(4))

            ctk.CTkLabel(info, text=f"#{p['number']} {p['name']}",
                         font=("Segoe UI", self._fs(12), "bold"), anchor="w"
                         ).pack(anchor="w")
            ctk.CTkLabel(info, text=f"📍 {p['position']}  |  {p['count']} ocen",
                         font=("Segoe UI", self._fs(9)),
                         text_color=COLORS["text_gray"], anchor="w"
                         ).pack(anchor="w")

            avg     = p['avg']
            avg_clr = (COLORS["success"] if avg >= 8 else
                       COLORS["accent"]  if avg >= 6 else
                       COLORS["warning"] if avg >= 4.5 else COLORS["danger"])

            sf = ctk.CTkFrame(row, fg_color=avg_clr, corner_radius=self._sz(8),
                              width=self._sz(50), height=self._sz(30))
            sf.pack(side="right", padx=self._sz(12))
            sf.pack_propagate(False)
            ctk.CTkLabel(sf, text=f"{avg:.1f}",
                         font=("Segoe UI", self._fs(13), "bold"),
                         text_color="white").pack(expand=True)

    def _render_logs(self):
        if not self.winfo_exists():
            return
        cnt = self.log_card_wrapper._content
        for w in cnt.winfo_children():
            w.destroy()

        logs = self.data.get('logs')
        if not logs:
            ctk.CTkLabel(cnt, text="Brak aktywności",
                         text_color=COLORS["text_gray"],
                         font=("Segoe UI", self._fs(12))).pack(pady=self._sz(15))
            return

        for log in logs[:5]:
            try:
                created = datetime.fromisoformat(
                    log['created_at'].replace('Z', '+00:00'))
                diff = datetime.now(created.tzinfo) - created
                if diff.total_seconds() < 60:
                    t_str = "teraz"
                elif diff.seconds < 3600:
                    t_str = f"{diff.seconds // 60} min temu"
                elif diff.days == 0:
                    t_str = f"{diff.seconds // 3600}h temu"
                elif diff.days == 1:
                    t_str = "wczoraj"
                else:
                    t_str = f"{diff.days}d temu"
            except Exception:
                t_str = "?"

            row = ctk.CTkFrame(cnt, fg_color="#252525",
                               corner_radius=self._sz(8), height=self._sz(46))
            row.pack(fill="x", pady=self._sz(2))
            row.pack_propagate(False)

            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", padx=self._sz(10), pady=self._sz(4))

            ctk.CTkLabel(left, text=f"👤 {log.get('coach_name', '?')}",
                         font=("Segoe UI", self._fs(11), "bold"),
                         text_color=COLORS["accent"]).pack(anchor="w")
            ctk.CTkLabel(left, text=(log.get('action') or '')[:50],
                         font=("Segoe UI", self._fs(10)),
                         text_color="#aaa").pack(anchor="w")

            ctk.CTkLabel(row, text=t_str,
                         font=("Segoe UI", self._fs(9)),
                         text_color="#666").pack(side="right", padx=self._sz(10))

    # ════════════════════════════════════════════
    # FORCE REFRESH
    # ════════════════════════════════════════════
    def force_refresh(self):
        from cache_manager import cache

        def _invalidate_and_fetch():
            try:
                # Invaliduj cache
                cache.invalidate_dashboard()
                cache.invalidate_events()
                cache.invalidate_players()
                cache.invalidate_scouting()
                cache.invalidate("ratings")

                # Pre-fetch równolegle
                futs = [
                    self._executor.submit(cache.get_players, True),
                    self._executor.submit(cache.get_upcoming_events, 5, True),
                    self._executor.submit(cache.get_scouting_targets, True),
                    self._executor.submit(cache.get_activity_log, 5, True),
                ]
                for f in as_completed(futs, timeout=10):
                    try:
                        f.result()
                    except Exception:
                        pass

                if self.winfo_exists():
                    self.after(0, self._show_toast)
                    self._loading = False
                    self.after(50, self.refresh_data_async)
            except Exception as e:
                logger.error(f"Force refresh: {e}")
                self._loading = False

        self._loading = False
        threading.Thread(target=_invalidate_and_fetch, daemon=True).start()

    def _show_toast(self):
        toast = ctk.CTkFrame(self, fg_color=COLORS["success"],
                             corner_radius=self._sz(8), height=self._sz(36))
        toast.place(relx=0.5, rely=0.95, anchor="center")
        toast.pack_propagate(False)
        ctk.CTkLabel(toast, text="✅ Dane odświeżone",
                     font=("Segoe UI", self._fs(12), "bold"),
                     text_color="white").pack(expand=True, padx=self._sz(20))
        self.after(2000, toast.destroy)