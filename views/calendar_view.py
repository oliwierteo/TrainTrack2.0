# calendar_view.py - v3.1 (fix: border_color transparent)
import customtkinter as ctk
import calendar
import datetime
import uuid
import platform
from database import supabase
import database
import teams
from tkinter import messagebox

# Czcionka kompatybilna z Windows i Mac
FONT = "Segoe UI" if platform.system() == "Windows" else "Helvetica Neue"

TYPE_COLORS = {
    "Techniczny":        "#c92c2c",
    "Motoryczny":        "#2cc985",
    "Taktyczny":         "#3b8ed0",
    "Mieszany":          "#e67e22",
    "Mecz":              "#8e44ad",
    "Spotkanie Klubowe": "#7f8c8d",
    "Inny":              "#34495e"
}

TRAINING_TYPES = {"Techniczny", "Motoryczny", "Taktyczny", "Mieszany", "Inny"}
MATCH_TYPES    = {"Mecz"}
MEETING_TYPES  = {"Spotkanie Klubowe"}

STATUSES = [
    ("obecny",           "✅", "#2cc985"),
    ("spóźniony",        "⏰", "#f39c12"),
    ("nieobecny",        "❌", "#e74c3c"),
    ("usprawiedliwiony", "📋", "#3b8ed0"),
    ("chory",            "🤒", "#e67e22"),
    ("kontuzja",         "🩹", "#8e44ad"),
]

# Kolor "nieaktywnego" przycisku — nigdy "transparent"
BTN_INACTIVE = "#2a2a2a"
BTN_INACTIVE_BORDER = "#444444"


class AttendanceWindow(ctk.CTkToplevel):
    """Szybkie okno obecności — kliknij status, zapisz batch"""

    def __init__(self, master, event, on_save_callback=None):
        super().__init__(master)
        self.event   = event
        self.on_save = on_save_callback
        self._vars   = {}   # player_id → StringVar
        self._btns   = {}   # player_id → {status: CTkButton}
        self._dirty  = False

        ev_date  = datetime.datetime.strptime(event['event_date'], "%Y-%m-%d")
        ev_types = ", ".join(event.get('event_types', []))
        self.title(f"Obecność — {ev_date.strftime('%d.%m.%Y')}  [{ev_types}]")

        types_set = set(event.get('event_types', []))
        if types_set & MATCH_TYPES:
            self._cat_color = "#8e44ad"
            self._cat_label = "MECZ"
        elif types_set & MEETING_TYPES:
            self._cat_color = "#7f8c8d"
            self._cat_label = "SPOTKANIE"
        else:
            self._cat_color = "#3b8ed0"
            self._cat_label = "TRENING"

        self._build_ui()
        self._load_data()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.attributes("-topmost", True)

        self.update_idletasks()
        w, h = 700, 720
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        # Nagłówek
        hdr = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=0)
        hdr.pack(fill="x")

        inner = ctk.CTkFrame(hdr, fg_color="transparent")
        inner.pack(fill="x", padx=15, pady=10)

        ev_date = datetime.datetime.strptime(
            self.event['event_date'], "%Y-%m-%d").strftime("%d.%m.%Y")

        ctk.CTkLabel(
            inner,
            text=f"{self._cat_label}  •  {ev_date}  •  "
                 f"{self.event.get('start_time','')[:5]}–"
                 f"{self.event.get('end_time','')[:5]}",
            font=("Segoe UI", 16, "bold"),
            text_color=self._cat_color
        ).pack(side="left")

        self._saved_lbl = ctk.CTkLabel(
            inner, text="", font=("Segoe UI", 12), text_color="#2cc985")
        self._saved_lbl.pack(side="right")

        # Legenda
        leg = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=0)
        leg.pack(fill="x")
        leg_inner = ctk.CTkFrame(leg, fg_color="transparent")
        leg_inner.pack(pady=5)
        for status, icon, color in STATUSES:
            ctk.CTkLabel(
                leg_inner,
                text=f"{icon} {status}",
                font=("Segoe UI", 10),
                text_color=color
            ).pack(side="left", padx=8)

        # Pasek szybkiego zaznaczania
        quick = ctk.CTkFrame(self, fg_color="#252525", corner_radius=0)
        quick.pack(fill="x")
        q_inner = ctk.CTkFrame(quick, fg_color="transparent")
        q_inner.pack(pady=6, padx=15)

        ctk.CTkLabel(
            q_inner, text="Wszyscy →",
            font=("Segoe UI", 11), text_color="#777"
        ).pack(side="left", padx=(0, 8))

        for status, icon, color in STATUSES:
            ctk.CTkButton(
                q_inner,
                text=f"{icon}",
                width=42, height=28,
                fg_color=color,
                hover_color=color,
                border_width=0,
                font=("Segoe UI", 13),
                command=lambda s=status: self._set_all(s)
            ).pack(side="left", padx=2)

        # Scroll z zawodnikami
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=8, pady=8)

        # Licznik
        self._counter_lbl = ctk.CTkLabel(
            self, text="", font=("Segoe UI", 11), text_color="#777")
        self._counter_lbl.pack(pady=(0, 4))

        # Zapis
        ctk.CTkButton(
            self,
            text="💾  ZAPISZ LISTĘ OBECNOŚCI",
            height=50,
            fg_color="#2cc985",
            hover_color="#239a65",
            font=("Segoe UI", 14, "bold"),
            command=self._save
        ).pack(fill="x", padx=20, pady=(0, 15))

    def _load_data(self):
        import threading

        for w in self._scroll.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self._scroll, text="⏳ Ładowanie...", text_color="gray"
        ).pack(pady=30)

        def fetch():
            from cache_manager import cache
            players = cache.get_players()

            event_date = self.event['event_date']  # YYYY-MM-DD

            def is_active_for_event(player):
                join_date = player.get('join_date')
                created_at = player.get('created_at')

                if join_date:
                    player_start = str(join_date)[:10]
                elif created_at:
                    player_start = str(created_at)[:10]
                else:
                    player_start = "1900-01-01"

                return player_start <= event_date

            # filtr po dacie dołączenia
            players = [p for p in players if is_active_for_event(p)]

            # sortowanie alfabetyczne
            players.sort(key=lambda p: str(p.get('full_name') or '').strip().lower())

            existing = supabase.table('attendance') \
                .select("player_id, status") \
                .eq('event_id', self.event['id']) \
                .execute().data

            att_map = {a['player_id']: a['status'] for a in existing}

            self.after(0, lambda: self._render_players(players, att_map))

        threading.Thread(target=fetch, daemon=True).start()

    def _render_players(self, players, att_map):
        for w in self._scroll.winfo_children():
            w.destroy()

        self._players = players

        for p in players:
            pid     = p['id']
            current = att_map.get(pid, "")

            var = ctk.StringVar(value=current)
            self._vars[pid] = var
            self._btns[pid] = {}
            self._create_player_row(p, var)

        self._update_counter()

    def _create_player_row(self, player, var):
        pid = player['id']

        row = ctk.CTkFrame(
            self._scroll, fg_color="#2a2a2a",
            corner_radius=8, height=54)
        row.pack(fill="x", pady=3)
        row.pack_propagate(False)

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=8, pady=7)

        # Numer koszulki
        nr = str(player.get('jersey_number') or '–')
        ctk.CTkLabel(
            inner, text=nr, width=32, height=32,
            fg_color="#1f6aa5", corner_radius=16,
            font=("Arial", 11, "bold")
        ).pack(side="left")

        # Imię
        name = player.get('full_name', '?')
        if len(name) > 20:
            name = name[:18] + "…"
        ctk.CTkLabel(
            inner, text=name,
            font=("Segoe UI", 13, "bold"),
            width=170, anchor="w"
        ).pack(side="left", padx=(8, 0))

        # Przyciski statusów
        btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
        btn_frame.pack(side="right")

        current = var.get()
        for status, icon, color in STATUSES:
            is_active = (current == status)
            btn = ctk.CTkButton(
                btn_frame,
                text=icon,
                width=40, height=36,
                corner_radius=6,
                fg_color=color if is_active else BTN_INACTIVE,
                hover_color=color,
                border_width=2 if is_active else 1,
                border_color="white" if is_active else BTN_INACTIVE_BORDER,
                font=("Segoe UI", 14),
                command=lambda s=status, p_id=pid: self._toggle(p_id, s)
            )
            btn.pack(side="left", padx=2)
            self._btns[pid][status] = btn

    def _toggle(self, pid, status):
        current = self._vars[pid].get()
        new_val = "" if current == status else status
        self._vars[pid].set(new_val)
        self._dirty = True

        for s, icon, color in STATUSES:
            btn = self._btns[pid].get(s)
            if btn and btn.winfo_exists():
                active = (new_val == s)
                btn.configure(
                    fg_color=color if active else BTN_INACTIVE,
                    border_width=2 if active else 1,
                    border_color="white" if active else BTN_INACTIVE_BORDER
                )

        self._update_counter()

    def _set_all(self, status):
        for pid, var in self._vars.items():
            var.set(status)
            for s, icon, color in STATUSES:
                btn = self._btns[pid].get(s)
                if btn and btn.winfo_exists():
                    active = (s == status)
                    btn.configure(
                        fg_color=color if active else BTN_INACTIVE,
                        border_width=2 if active else 1,
                        border_color="white" if active else BTN_INACTIVE_BORDER
                    )
        self._dirty = True
        self._update_counter()

    def _update_counter(self):
        counts    = {}
        no_status = 0

        # ✅ POPRAWKA: .values() nie .items()
        for var in self._vars.values():
            v = var.get()
            if v:
                counts[v] = counts.get(v, 0) + 1
            else:
                no_status += 1

        parts = []
        for status, icon, _ in STATUSES:
            if counts.get(status, 0) > 0:
                parts.append(f"{icon} {counts[status]}")

        if no_status > 0:
            parts.append(f"⬜ {no_status} → będzie nieobecny")

        self._counter_lbl.configure(text="   ".join(parts))

    def _save(self):
        batch = []
        for pid, var in self._vars.items():
            status = var.get()
            
            # Jeśli brak statusu → automatycznie "nieobecny"
            if not status:
                status = "nieobecny"
            
            batch.append({
                "event_id":  self.event['id'],
                "player_id": pid,
                "status":    status,
                # drużyna wydarzenia (nie drużyna widoku!) - inaczej
                # wpis z drużyny I trafiłby do statystyk akademii
                "team_code": (self.event.get('team_code')
                              or teams.get_current_team()),
            })

        if not batch:
            messagebox.showwarning(
                "Uwaga",
                "Brak zawodników do zapisania.")
            return

        try:
            # Usuń stare wpisy
            supabase.table('attendance') \
                .delete() \
                .eq('event_id', self.event['id']) \
                .execute()

            # Wstaw nowe (batch po 50)
            for i in range(0, len(batch), 50):
                supabase.table('attendance') \
                    .insert(batch[i:i+50]) \
                    .execute()

            from cache_manager import cache
            cache.invalidate("att")
            cache.invalidate("events")

            ev_date = datetime.datetime.strptime(
                self.event['event_date'], "%Y-%m-%d").strftime("%d.%m")
            database.log_activity(
                f"uzupełnił listę obecności ({len(batch)} osób) z dnia {ev_date}")

            self._saved_lbl.configure(text=f"✓ Zapisano {len(batch)} wpisów")
            self._dirty = False

            if self.on_save:
                self.on_save()

            self.after(1500, self.destroy)

        except Exception as e:
            messagebox.showerror("Błąd zapisu", str(e))

    def _on_close(self):
        if self._dirty:
            if messagebox.askyesno(
                    "Niezapisane zmiany",
                    "Masz niezapisane zmiany. Zamknąć?"):
                self.destroy()
        else:
            self.destroy()


class CalendarView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        import database as db
        start_str, end_str = db.get_season_range()
        try:
            season_start = datetime.datetime.strptime(start_str, "%Y-%m-%d").date()
            season_end   = datetime.datetime.strptime(end_str,   "%Y-%m-%d").date()
            today        = datetime.date.today()
            self.current_date = today \
                if season_start <= today <= season_end else season_start
        except:
            self.current_date = datetime.date.today()

        self.year  = self.current_date.year
        self.month = self.current_date.month

        self._build_ui()
        self.refresh_calendar()

    def _build_ui(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", pady=(0, 10))

        nav = ctk.CTkFrame(top, fg_color="transparent")
        nav.pack(side="left")

        ctk.CTkButton(
            nav, text="<", width=40,
            font=("Arial", 16, "bold"),
            command=self.prev_month
        ).pack(side="left", padx=5)

        self.month_label = ctk.CTkLabel(
            nav, text="", font=("Segoe UI", 22, "bold"))
        self.month_label.pack(side="left", padx=15)

        ctk.CTkButton(
            nav, text=">", width=40,
            font=("Arial", 16, "bold"),
            command=self.next_month
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            top, text="⟳ Odśwież", width=90,
            fg_color="#444",
            command=self.force_refresh
        ).pack(side="right", padx=10)

        ctk.CTkButton(
            top,
            text="+ Zaplanuj Trening / Cykl",
            fg_color="#2cc985", hover_color="#239a65",
            font=("Segoe UI", 13, "bold"), height=40,
            command=self.open_add_event_dialog
        ).pack(side="right")

        self.grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_frame.pack(fill="both", expand=True)

        for i in range(7):
            self.grid_frame.grid_columnconfigure(i, weight=1, uniform="col")
        self.grid_frame.grid_rowconfigure(0, weight=0)
        for i in range(1, 7):
            self.grid_frame.grid_rowconfigure(i, weight=1, uniform="row")

    def refresh_calendar(self):
        import database as db
        start_str, end_str = db.get_season_range()
        try:
            s     = datetime.datetime.strptime(start_str, "%Y-%m-%d").date()
            e     = datetime.datetime.strptime(end_str,   "%Y-%m-%d").date()
            today = datetime.date.today()
            view  = datetime.date(self.year, self.month, 1)

            if not (s <= view <= e):
                if s <= today <= e:
                    self.year, self.month = today.year, today.month
                else:
                    self.year, self.month = s.year, s.month
        except:
            pass

        MONTHS = ["","Styczeń","Luty","Marzec","Kwiecień","Maj","Czerwiec",
                  "Lipiec","Sierpień","Wrzesień","Październik","Listopad","Grudzień"]
        self.month_label.configure(
            text=f"{MONTHS[self.month]} {self.year}")

        for w in self.grid_frame.winfo_children():
            if int(w.grid_info()["row"]) > 0:
                w.destroy()

        days = ["PONIEDZIAŁEK","WTOREK","ŚRODA","CZWARTEK",
                "PIĄTEK","SOBOTA","NIEDZIELA"]
        for i, d in enumerate(days):
            ctk.CTkLabel(
                self.grid_frame, text=d,
                font=("Segoe UI", 10, "bold"),
                text_color="gray"
            ).grid(row=0, column=i, pady=(0, 5))

        start_db = f"{self.year}-{self.month:02d}-01"
        from cache_manager import cache
        raw = cache.get_events(start_date=start_db)
        month_events = [
            ev for ev in raw
            if ev['event_date'].startswith(f"{self.year}-{self.month:02d}")
        ]

        today = datetime.date.today()
        cal   = calendar.monthcalendar(self.year, self.month)

        for row_i, week in enumerate(cal):
            for col_i, day in enumerate(week):
                if day == 0:
                    continue

                cell = ctk.CTkFrame(
                    self.grid_frame,
                    fg_color="#2b2b2b",
                    border_width=1,
                    border_color="#3a3a3a",
                    corner_radius=0)
                cell.grid(row=row_i + 1, column=col_i,
                          sticky="nsew", padx=1, pady=1)

                is_today = (
                    day == today.day and
                    self.month == today.month and
                    self.year == today.year)

                ctk.CTkLabel(
                    cell, text=str(day),
                    font=("Segoe UI", 13, "bold"),
                    text_color="#3b8ed0" if is_today else "white"
                ).pack(anchor="nw", padx=5, pady=2)

                d_str = f"{self.year}-{self.month:02d}-{day:02d}"
                for ev in [e for e in month_events
                           if e['event_date'] == d_str]:
                    types   = ev['event_types']
                    main    = types[0]
                    bg      = TYPE_COLORS.get(main, "#1f6aa5") \
                              if len(types) == 1 else "#555"
                    txt     = f"{ev['start_time'][:5]} " \
                              f"{'MIX' if len(types) > 1 else main[:3].upper()}"

                    ctk.CTkButton(
                        cell, text=txt,
                        height=22,
                        font=("Segoe UI", 10, "bold"),
                        fg_color=bg,
                        corner_radius=4,
                        command=lambda e=ev: self.show_event_details(e)
                    ).pack(fill="x", padx=4, pady=1)

    def prev_month(self):
        self.month -= 1
        if self.month == 0:
            self.month = 12; self.year -= 1
        self.refresh_calendar()

    def next_month(self):
        self.month += 1
        if self.month == 13:
            self.month = 1; self.year += 1
        self.refresh_calendar()

    def force_refresh(self):
        from cache_manager import cache
        cache.invalidate("events")
        cache.invalidate("att")
        self.refresh_calendar()

    def show_event_details(self, event):
        info = ctk.CTkToplevel(self)
        info.title("Wydarzenie")
        info.attributes("-topmost", True)
        info.resizable(False, False)

        w, h = 400, 380
        info.update_idletasks()
        x = (info.winfo_screenwidth()  - w) // 2
        y = (info.winfo_screenheight() - h) // 2
        info.geometry(f"{w}x{h}+{x}+{y}")

        dt        = datetime.datetime.strptime(event['event_date'], "%Y-%m-%d")
        types_set = set(event.get('event_types', []))

        hdr_color = (
            "#8e44ad" if types_set & MATCH_TYPES else
            "#7f8c8d" if types_set & MEETING_TYPES else
            "#3b8ed0"
        )

        ctk.CTkLabel(
            info, text=dt.strftime("%d.%m.%Y"),
            font=("Segoe UI", 24, "bold"),
            text_color=hdr_color
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            info,
            text=f"⌚ {event['start_time'][:5]} – {event['end_time'][:5]}",
            font=("Segoe UI", 15)
        ).pack()

        ctk.CTkLabel(
            info,
            text=f"📌 {', '.join(event['event_types'])}",
            font=("Segoe UI", 12),
            text_color="gray"
        ).pack(pady=4)

        if event.get('description'):
            ctk.CTkLabel(
                info,
                text=f"📝 {event['description']}",
                font=("Segoe UI", 13, "italic"),
                text_color="white"
            ).pack(pady=4)

        ctk.CTkButton(
            info, text="👥 LISTA OBECNOŚCI",
            height=48, fg_color="#1f6aa5",
            font=("Segoe UI", 14, "bold"),
            command=lambda: [
                info.destroy(),
                AttendanceWindow(
                    self, event,
                    on_save_callback=self.refresh_calendar)
            ]
        ).pack(pady=(20, 8), padx=40, fill="x")

        ctk.CTkButton(
            info, text="⭐ OCEŃ ZAWODNIKÓW",
            height=42, fg_color="#8e44ad",
            font=("Segoe UI", 12, "bold"),
            command=lambda: [info.destroy(), self._open_ratings(event)]
        ).pack(pady=(0, 12), padx=40, fill="x")

        del_frame = ctk.CTkFrame(info, fg_color="transparent")
        del_frame.pack(fill="x", padx=40)

        ctk.CTkButton(
            del_frame, text="Usuń ten trening",
            fg_color="#c92c2c", hover_color="#a82525",
            command=lambda: self._delete_event(event, 'one', info)
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))

        if event.get('cycle_id'):
            ctk.CTkButton(
                del_frame, text="Usuń cały cykl",
                fg_color="#3a2a00",
                border_width=1, border_color="orange",
                text_color="orange",
                command=lambda: self._delete_event(event, 'cycle', info)
            ).pack(side="left", expand=True, fill="x", padx=(4, 0))

    def _open_ratings(self, event):
        from views.ratings_view import RatingsView
        RatingsView(self, event)

    def _delete_event(self, event, mode, parent):
        if mode == 'one':
            pytanie = "Usunąć ten trening?"
        else:
            pytanie = "Usunąć CAŁY cykl treningowy?\nNie można tego cofnąć!"

        # Unieś parent na wierzch przed pytaniem
        parent.lift()
        parent.focus_force()

        odpowiedz = messagebox.askyesno(
            "Potwierdź usunięcie",
            pytanie,
            parent=parent          # ← KLUCZOWE: dialog jest przywiązany do parent
        )

        if not odpowiedz:
            return

        try:
            if mode == 'one':
                supabase.table('events').delete() \
                    .eq('id', event['id']).execute()
                database.log_activity(
                    f"usunął trening z dnia {event['event_date']}")
            else:
                supabase.table('events').delete() \
                    .eq('cycle_id', event['cycle_id']).execute()
                database.log_activity("usunął cały cykl treningowy")

            from cache_manager import cache
            cache.invalidate("events")
            cache.invalidate("att")
            parent.destroy()
            self.refresh_calendar()

        except Exception as e:
            messagebox.showerror("Błąd", str(e), parent=parent)

    def open_add_event_dialog(self):
        d = ctk.CTkToplevel(self)
        d.title("Planowanie")
        d.resizable(False, False)
        d.attributes("-topmost", True)

        w, h = 460, 600
        d.update_idletasks()
        x = (d.winfo_screenwidth()  - w) // 2
        y = (d.winfo_screenheight() - h) // 2
        d.geometry(f"{w}x{h}+{x}+{y}")

        ctk.CTkLabel(
            d, text="📅 Nowe Wydarzenie",
            font=("Segoe UI", 20, "bold"),
            text_color="#2cc985"
        ).pack(pady=(20, 15))

        tf = ctk.CTkFrame(d, fg_color="transparent")
        tf.pack(fill="x", padx=30)

        type_vars = {}
        for i, (t, col) in enumerate(TYPE_COLORS.items()):
            v  = ctk.StringVar(value="off")
            cb = ctk.CTkCheckBox(
                tf, text=t, variable=v,
                onvalue=t, offvalue="off",
                text_color=col,
                font=("Segoe UI", 11), width=180)
            cb.grid(row=i // 2, column=i % 2,
                    sticky="w", pady=2, padx=5)
            type_vars[t] = v

        tf2 = ctk.CTkFrame(d, fg_color="transparent")
        tf2.pack(pady=(15, 10))
        ctk.CTkLabel(tf2, text="🕐",
                     font=("Segoe UI", 14)).pack(side="left", padx=(0, 5))
        e_s = ctk.CTkEntry(tf2, width=70, justify="center")
        e_s.insert(0, "17:00"); e_s.pack(side="left", padx=3)
        ctk.CTkLabel(tf2, text="—",
                     font=("Segoe UI", 14)).pack(side="left", padx=5)
        e_e = ctk.CTkEntry(tf2, width=70, justify="center")
        e_e.insert(0, "18:30"); e_e.pack(side="left", padx=3)

        df = ctk.CTkFrame(d, fg_color="transparent")
        df.pack(fill="x", padx=30, pady=(5, 10))
        ctk.CTkLabel(df, text="📝 Opis / Przeciwnik:",
                     font=("Segoe UI", 11),
                     text_color="#888").pack(anchor="w")
        desc = ctk.CTkEntry(
            df, placeholder_text="np. sparing z Bałtykiem")
        desc.pack(fill="x", pady=(3, 0))

        tabs = ctk.CTkTabview(d, height=200)
        tabs.pack(fill="x", padx=20, pady=5)
        t1 = tabs.add("📌 Pojedynczy")
        t2 = tabs.add("🔄 Cykl")

        ctk.CTkLabel(t1, text="Data:",
                     font=("Segoe UI", 12)).pack(pady=(15, 5))
        d_e = ctk.CTkEntry(t1, placeholder_text="DD-MM-RRRR",
                            width=180, justify="center")
        d_e.insert(0, datetime.date.today().strftime("%d-%m-%Y"))
        d_e.pack()

        ct = ctk.CTkFrame(t2, fg_color="transparent")
        ct.pack(pady=(10, 5))
        ctk.CTkLabel(ct, text="Od:",
                     font=("Segoe UI", 11)).pack(side="left", padx=(0, 5))
        c_s = ctk.CTkEntry(ct, width=110, justify="center")
        c_s.insert(0, datetime.date.today().strftime("%d-%m-%Y"))
        c_s.pack(side="left", padx=3)
        ctk.CTkLabel(ct, text="Do:",
                     font=("Segoe UI", 11)).pack(side="left", padx=(10, 5))
        c_e = ctk.CTkEntry(ct, width=110, justify="center")
        c_e.pack(side="left", padx=3)

        ctk.CTkLabel(t2, text="Dni tygodnia:",
                     font=("Segoe UI", 10),
                     text_color="#888").pack(pady=(8, 3))
        df2 = ctk.CTkFrame(t2, fg_color="transparent")
        df2.pack()
        self._cyc_vars = {}
        for i, nm in enumerate(["Pn","Wt","Śr","Cz","Pt","Sb","Nd"]):
            v = ctk.IntVar()
            ctk.CTkCheckBox(
                df2, text=nm, variable=v,
                width=42, font=("Segoe UI", 10)
            ).grid(row=0, column=i, padx=1)
            self._cyc_vars[i] = v

        bf = ctk.CTkFrame(d, fg_color="transparent")
        bf.pack(fill="x", padx=20, pady=20)

        ctk.CTkButton(
            bf, text="Anuluj", width=90, height=42,
            fg_color="#444",
            command=d.destroy
        ).pack(side="left")

        def save():
            sel = [t for t, v in type_vars.items() if v.get() != "off"]
            if not sel:
                return messagebox.showerror("Błąd", "Wybierz typ!", parent=d)
            try:
                base = {
                    "start_time":  e_s.get(),
                    "end_time":    e_e.get(),
                    "event_types": sel,
                    "club_name":   database.CURRENT_CLUB,
                    "description": desc.get() or None,
                    "team_code":   teams.get_current_team(),
                }
                if tabs.get() == "📌 Pojedynczy":
                    db_date = datetime.datetime.strptime(
                        d_e.get(), "%d-%m-%Y").strftime("%Y-%m-%d")
                    supabase.table('events') \
                        .insert({**base, "event_date": db_date}) \
                        .execute()
                    database.log_activity(
                        f"zaplanował wydarzenie ({db_date})")
                else:
                    sd = datetime.datetime.strptime(
                        c_s.get(), "%d-%m-%Y").date()
                    ed = datetime.datetime.strptime(
                        c_e.get(), "%d-%m-%Y").date()
                    sel_days = [i for i, v in self._cyc_vars.items()
                                if v.get()]
                    if not sel_days:
                        return messagebox.showerror("Błąd", "Wybierz dni!", parent=d)

                    cid   = str(uuid.uuid4())
                    batch = []
                    cur   = sd
                    while cur <= ed:
                        if cur.weekday() in sel_days:
                            batch.append({
                                **base,
                                "event_date": str(cur),
                                "cycle_id":   cid
                            })
                        cur += datetime.timedelta(days=1)

                    if not batch:
                        return messagebox.showerror("Błąd", "Brak dat!", parent=d)

                    for i in range(0, len(batch), 50):
                        supabase.table('events') \
                            .insert(batch[i:i+50]) \
                            .execute()
                    database.log_activity(
                        f"zaplanował cykl ({len(batch)} jednostek)")

                from cache_manager import cache
                cache.invalidate("events")
                d.destroy()
                self.refresh_calendar()

            except ValueError:
                messagebox.showerror(
                    "Błąd", "Zły format daty (DD-MM-RRRR)")
            except Exception as ex:
                messagebox.showerror("Błąd", str(ex))

        ctk.CTkButton(
            bf, text="✓ DODAJ",
            height=42, fg_color="#2cc985",
            hover_color="#239a65",
            font=("Segoe UI", 13, "bold"),
            command=save
        ).pack(side="right", fill="x", expand=True, padx=(10, 0))