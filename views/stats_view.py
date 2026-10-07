# stats_view.py - v4.0 (Nowa Logika Procentów + Fix Wyświetlania)
import customtkinter as ctk
import datetime
from datetime import timedelta
from tkinter import messagebox as msgbox
import threading

TRAINING_TYPES = {"Techniczny", "Motoryczny", "Taktyczny", "Mieszany", "Inny"}
MATCH_TYPES    = {"Mecz"}
MEETING_TYPES  = {"Spotkanie Klubowe"}

FRAME_INACTIVE_BG     = "#1e1e1e"
FRAME_INACTIVE_BORDER = "#1e1e1e"

def _event_category(event):
    types = set(event.get('event_types', []))
    if types & MATCH_TYPES:   return 'match'
    if types & MEETING_TYPES: return 'meeting'
    return 'training'

def _get_effective_join(player, season_start_s):
    raw = (player.get('join_date') or player.get('created_at') or season_start_s)
    join_s = str(raw)[:10]
    return join_s if join_s > season_start_s else season_start_s

class StatsView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self._loading    = False
        self._first_load = True
        self._cache      = {}
        self._current_key = None

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", pady=(0, 10), padx=20)
        ctk.CTkLabel(top, text="Regularność", font=("Segoe UI", 24, "bold")).pack(side="left")
        ctk.CTkButton(top, text="⟳ Odśwież", width=100, fg_color="#2b2b2b",
                      border_width=1, border_color="gray", command=self.refresh_data).pack(side="right")

        cat_bar = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=10)
        cat_bar.pack(fill="x", padx=20, pady=(0, 8))
        cat_inner = ctk.CTkFrame(cat_bar, fg_color="transparent")
        cat_inner.pack(side="left", padx=15, pady=8)
        ctk.CTkLabel(cat_inner, text="Pokaż:", font=("Segoe UI", 12)).pack(side="left", padx=(0, 10))

        self._cat_var = ctk.StringVar(value="training")
        for label, val in [("🏃 Treningi", "training"), ("⚽ Mecze", "match"),
                           ("🤝 Spotkania", "meeting"), ("📊 Wszystko", "all")]:
            ctk.CTkRadioButton(cat_inner, text=label, variable=self._cat_var, value=val,
                               command=self._on_cat_change).pack(side="left", padx=8)

        ctrl = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=10)
        ctrl.pack(fill="x", padx=20, pady=(0, 15))
        bf = ctk.CTkFrame(ctrl, fg_color="transparent")
        bf.pack(side="left", padx=15, pady=10)

        self._btn7  = self._mk_btn(bf, "7 dni",  7)
        self._btn30 = self._mk_btn(bf, "30 dni", 30)
        self._btnSz = self._mk_btn(bf, "Sezon",  0)

        ctk.CTkFrame(ctrl, width=2, height=30, fg_color="gray").pack(side="left", padx=10)
        ctk.CTkLabel(ctrl, text="Od:", font=("Segoe UI", 11)).pack(side="left", padx=(5, 2))
        self._e_start = ctk.CTkEntry(ctrl, placeholder_text="DD-MM-RRRR", width=95)
        self._e_start.pack(side="left", padx=2)
        ctk.CTkLabel(ctrl, text="Do:", font=("Segoe UI", 11)).pack(side="left", padx=(5, 2))
        self._e_end = ctk.CTkEntry(ctrl, placeholder_text="DD-MM-RRRR", width=95)
        self._e_end.pack(side="left", padx=2)
        ctk.CTkButton(ctrl, text="Szukaj", width=70, fg_color="#1f6aa5",
                      command=self._load_custom).pack(side="left", padx=10)

        self._range_lbl = ctk.CTkLabel(ctrl, text="", font=("Segoe UI", 13, "bold"), text_color="#3b8ed0")
        self._range_lbl.pack(side="right", padx=20)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self._show_loading_screen()
        self._highlight(self._btnSz)
        self.after(60, self._load_season)

    def _mk_btn(self, parent, text, days):
        btn = ctk.CTkButton(parent, text=text, width=80, height=32, fg_color="#2b2b2b",
                            border_width=1, border_color="gray", command=lambda d=days: self._switch(d))
        btn.pack(side="left", padx=4)
        return btn

    def _highlight(self, active):
        for b in [self._btn7, self._btn30, self._btnSz]:
            b.configure(fg_color="#2b2b2b", border_color="gray")
        active.configure(fg_color="#1f6aa5", border_color="#1f6aa5")

    def _switch(self, days):
        if self._loading: return
        if days == 7:   self._highlight(self._btn7)
        elif days == 30: self._highlight(self._btn30)
        else:            self._highlight(self._btnSz)

        if days == 0: self._load_season()
        else:
            end = datetime.date.today()
            start = end - timedelta(days=days)
            self._start_calc(start, end)

    def _on_cat_change(self):
        if self._loading: return
        if self._current_key and self._current_key in self._cache:
            results, summary = self._cache[self._current_key]
            self._render(results, summary)

    def _load_season(self):
        import database
        s, e = database.get_season_range()
        try:
            start = datetime.datetime.strptime(s, "%Y-%m-%d").date()
            end   = datetime.datetime.strptime(e, "%Y-%m-%d").date()
            self._e_start.delete(0, 'end'); self._e_start.insert(0, start.strftime("%d-%m-%Y"))
            self._e_end.delete(0, 'end'); self._e_end.insert(0, end.strftime("%d-%m-%Y"))
            self._start_calc(start, end)
        except Exception as ex:
            end = datetime.date.today()
            start = end - timedelta(days=30)
            self._start_calc(start, end)

    def _load_custom(self):
        if self._loading: return
        try:
            start = datetime.datetime.strptime(self._e_start.get(), "%d-%m-%Y").date()
            end_s = self._e_end.get()
            end   = datetime.datetime.strptime(end_s, "%d-%m-%Y").date() if end_s else datetime.date.today()
            if start > end: msgbox.showerror("Błąd", "Data od > do"); return
            self._start_calc(start, end)
        except ValueError:
            msgbox.showerror("Błąd", "Format: DD-MM-RRRR")

    def refresh_data(self):
        if self._loading: return
        self._cache.clear()
        try:
            from cache_manager import cache
            cache.invalidate("att")
            cache.invalidate("events")
        except: pass
        self._load_season()

    def _start_calc(self, start: datetime.date, end: datetime.date):
        if self._loading: return
        today = datetime.date.today()
        if end > today: end = today

        key = f"{start}_{end}"
        self._current_key = key
        self._range_lbl.configure(text=f"{start.strftime('%d.%m.%Y')} — {end.strftime('%d.%m.%Y')}")

        if key in self._cache:
            results, summary = self._cache[key]
            self._render(results, summary)
            return

        self._loading = True
        if not self._first_load: self._show_loading_screen()
        self._first_load = False

        start_s, end_s, today_s = str(start), str(end), str(today)

        def fetch():
            try:
                from cache_manager import cache
                players = cache.get_players()
                all_ev  = cache.get_events(start_date=start_s, end_date=end_s)
                events  = [e for e in all_ev if e.get('event_date', '9999') <= today_s]

                att = []
                if events:
                    att = cache.get_attendance(event_ids=[e['id'] for e in events])

                results, summary = self._compute(players, events, att, start_s, today_s)
                self._cache[key] = (results, summary)
                self.after(0, lambda: self._finish(results, summary))
            except Exception as ex:
                self.after(0, lambda: self._show_error(str(ex)))

        threading.Thread(target=fetch, daemon=True).start()

    def _compute(self, players, events, attendance, season_start_s, today_s):
        if not events:
            return [], {"training": 0, "match": 0, "meeting": 0, "all": 0,
                        "training_cnt": 0, "match_cnt": 0, "meeting_cnt": 0}

        ev_info = {e['id']: (e['event_date'], _event_category(e)) for e in events}
        total = {"training": 0, "match": 0, "meeting": 0}
        for _, (_, ecat) in ev_info.items(): total[ecat] += 1

        player_stats = {}
        for p in players:
            pid = p.get('id')
            if not pid: continue
            eff_join = _get_effective_join(p, season_start_s)
            player_stats[pid] = {
                "id": pid, "name": p.get('full_name', '?'),
                "goal": p.get('development_goal') or "—", "photo_url": p.get('photo_url'),
                "join_str": eff_join,
                "present":  {"training": 0, "match": 0, "meeting": 0},
                "late":     {"training": 0, "match": 0, "meeting": 0},
                "absent":   {"training": 0, "match": 0, "meeting": 0},
                "excused":  {"training": 0, "match": 0, "meeting": 0},
                "sick":     {"training": 0, "match": 0, "meeting": 0},
                "injured":  {"training": 0, "match": 0, "meeting": 0},
                "avail":    {"training": 0, "match": 0, "meeting": 0},
            }

        # Dostępne
        for pid, pdata in player_stats.items():
            join = pdata['join_str']
            for _, (edate, ecat) in ev_info.items():
                if join <= edate <= today_s:
                    pdata['avail'][ecat] += 1

        # Odczyt statusów
        STATUS_MAP = {
            'obecny': ('present', True), 'spóźniony': ('late', True),
            'nieobecny': ('absent', False), 'usprawiedliwiony': ('excused', False),
            'chory': ('sick', False), 'kontuzja': ('injured', False),
        }

        for att in attendance:
            pid, eid, status = att.get('player_id'), att.get('event_id'), att.get('status', '')
            if pid not in player_stats or eid not in ev_info: continue
            edate, ecat = ev_info[eid]
            if not (player_stats[pid]['join_str'] <= edate <= today_s): continue

            field, _ = STATUS_MAP.get(status, ('absent', False))
            player_stats[pid][field][ecat] += 1

        results = []
        for pid, d in player_stats.items():
            pct = {}
            for cat in ('training', 'match', 'meeting', 'all'):
                if cat == 'all':
                    pres = sum(d['present'].values()) + (sum(d['late'].values()) * 0.9)
                    excl = (sum(d['excused'].values()) + sum(d['sick'].values()) +
                            sum(d['injured'].values()))
                    av = sum(d['avail'].values())
                else:
                    pres = d['present'][cat] + (d['late'][cat] * 0.9)
                    excl = (d['excused'][cat] + d['sick'][cat] +
                            d['injured'][cat])
                    av = d['avail'][cat]

                eff = av - excl
                pct[cat] = round(min(pres / eff * 100, 100.0), 1) if eff > 0 else None

            results.append({**d, "pct": pct, "total": total})

        summary = {}
        for cat in ('training', 'match', 'meeting', 'all'):
            vals = [r['pct'][cat] for r in results if r['pct'].get(cat) is not None]
            summary[cat] = round(sum(vals) / len(vals), 1) if vals else 0

        summary['training_cnt'] = total['training']
        summary['match_cnt'] = total['match']
        summary['meeting_cnt'] = total['meeting']

        return results, summary

    def _show_loading_screen(self):
        for w in self.scroll.winfo_children(): w.destroy()
        f = ctk.CTkFrame(self.scroll, fg_color="transparent")
        f.pack(expand=True, fill="both")
        c = ctk.CTkFrame(f, fg_color="transparent")
        c.place(relx=0.5, rely=0.4, anchor="center")
        ctk.CTkLabel(c, text="⏳", font=("Segoe UI", 52)).pack()
        ctk.CTkLabel(c, text="Obliczanie frekwencji...", font=("Segoe UI", 20), text_color="#aaa").pack(pady=(15, 5))

    def _finish(self, results, summary):
        self._loading = False
        self._render(results, summary)

    def _show_error(self, msg):
        self._loading = False
        for w in self.scroll.winfo_children(): w.destroy()
        ctk.CTkLabel(self.scroll, text=f"❌ {msg}", text_color="red", font=("Segoe UI", 14)).pack(pady=50)

    def _render(self, results, summary):
        cat = self._cat_var.get()
        for w in self.scroll.winfo_children(): w.destroy()
        if not results:
            ctk.CTkLabel(self.scroll, text="Brak danych w wybranym okresie.", text_color="gray", font=("Segoe UI", 16)).pack(pady=50)
            return

        self._render_summary(summary, cat)
        self._render_legend()

        valid = [r for r in results if r['pct'].get(cat) is not None]
        no_data = [r for r in results if r['pct'].get(cat) is None]
        valid.sort(key=lambda x: x['pct'][cat], reverse=True)

        cat_lbls = {"training": "treningów", "match": "meczy", "meeting": "spotkań", "all": "wydarzeń"}
        t_cnt = sum([summary[k] for k in ('training_cnt','match_cnt','meeting_cnt')]) if cat == 'all' else summary.get(f'{cat}_cnt', 0)

        ctk.CTkLabel(self.scroll, text=f"📋 Szczegóły zawodników ({t_cnt} {cat_lbls.get(cat, 'wydarzeń')})",
                     font=("Segoe UI", 17, "bold"), text_color="#888").pack(pady=(15, 5), anchor="w")

        self._cards = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self._cards.pack(fill="both", expand=True)

        self._to_render = valid + no_data
        self._team_avg = summary.get(cat, 0)
        self._render_cat = cat
        self._render_idx = 0
        self.after(10, self._render_batch)

        if no_data:
            ctk.CTkLabel(self.scroll, text=f"⚪ {len(no_data)} zawodnik(ów) bez danych",
                         font=("Segoe UI", 11), text_color="#555").pack(pady=5, anchor="w")

    def _render_summary(self, summary, active_cat):
        s = ctk.CTkFrame(self.scroll, fg_color="#242424", corner_radius=12)
        s.pack(fill="x", pady=8)
        inner = ctk.CTkFrame(s, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=15)

        cats_info = [("🏃 Treningi", "training", "#3b8ed0", summary['training_cnt']),
                     ("⚽ Mecze", "match", "#8e44ad", summary['match_cnt']),
                     ("🤝 Spotkania", "meeting", "#7f8c8d", summary['meeting_cnt'])]

        for label, key, color, cnt in cats_info:
            is_active = (key == active_cat)
            box = ctk.CTkFrame(inner, fg_color="#1a1a1a" if is_active else FRAME_INACTIVE_BG,
                               corner_radius=8, border_width=2 if is_active else 0,
                               border_color=color if is_active else FRAME_INACTIVE_BORDER)
            box.pack(side="left", expand=True, fill="both", padx=6)
            avg = summary.get(key, 0)
            ctk.CTkLabel(box, text=label, font=("Segoe UI", 11), text_color=color).pack(pady=(10, 2))
            ctk.CTkLabel(box, text=f"{avg}%" if avg > 0 else "—", font=("Segoe UI", 26, "bold"), text_color=color).pack()
            ctk.CTkLabel(box, text=f"{cnt} wydarzeń", font=("Segoe UI", 10), text_color="#666").pack(pady=(2, 10))

    def _render_legend(self):
        leg = ctk.CTkFrame(self.scroll, fg_color="#2b2b2b", corner_radius=8)
        leg.pack(fill="x", pady=(0, 8))
        inner = ctk.CTkFrame(leg, fg_color="transparent")
        inner.pack(pady=8)
        for color, text in [("#2cc985", "90%+"), ("#1f6aa5", "80–89%"), ("#e67e22", "70–79%"), ("#c92c2c", "<70%")]:
            ctk.CTkLabel(inner, text="●", font=("Arial", 14), text_color=color).pack(side="left", padx=2)
            ctk.CTkLabel(inner, text=text, font=("Segoe UI", 11)).pack(side="left", padx=(0, 15))

    def _render_batch(self):
        if not self.winfo_exists() or not hasattr(self, '_cards') or not self._cards.winfo_exists(): return
        bs = 8 if self._render_idx == 0 else 3
        end = min(self._render_idx + bs, len(self._to_render))
        for i in range(self._render_idx, end):
            try: self._create_card(self._to_render[i], self._team_avg, self._render_cat)
            except: pass
        self._render_idx = end
        if self._render_idx < len(self._to_render): self.after(16, self._render_batch)

    def _create_card(self, data, team_avg, cat):
        pct = data['pct'].get(cat)

        card = ctk.CTkFrame(self._cards, fg_color="#2b2b2b", corner_radius=10, height=100)
        card.pack(fill="x", pady=4, padx=5)

        card.grid_columnconfigure(0, weight=0, minsize=320)
        card.grid_columnconfigure(1, weight=1)
        card.grid_columnconfigure(2, weight=0, minsize=130)
        card.grid_rowconfigure(0, weight=1)

        # --- LEWA ---
        left = ctk.CTkFrame(card, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)

        try:
            from image_manager import img_manager
            lbl_p = ctk.CTkLabel(left, text="", width=50, height=50)
            lbl_p.pack(side="left", padx=(0, 12))
            img = img_manager.get_circular_image(
                data['id'], data.get('photo_url'), (50, 50),
                lambda i, l=lbl_p: l.configure(image=i) if l.winfo_exists() else None)
            lbl_p.configure(image=img)
        except:
            pass

        tf = ctk.CTkFrame(left, fg_color="transparent")
        tf.pack(side="left", fill="y", pady=5)

        name = data['name'][:20] + "…" if len(data['name']) > 22 else data['name']
        ctk.CTkLabel(tf, text=name, font=("Segoe UI", 15, "bold"), anchor="w").pack(anchor="w")

        # Mini frekwencja wszystkich kategorii
        mini = []
        for c, icon in [("training", "🏃"), ("match", "⚽"), ("meeting", "🤝")]:
            v = data['pct'].get(c)
            if v is not None:
                mini.append(f"{icon}{v}%")
        if mini:
            ctk.CTkLabel(tf, text="  ".join(mini), font=("Segoe UI", 10),
                        text_color="#666", anchor="w").pack(anchor="w")

        # Liczba branych pod uwagę
        if cat == 'all':
            av   = sum(data['avail'].values())
            excl = (sum(data['excused'].values()) + sum(data['sick'].values()) +
                    sum(data['injured'].values()))
        else:
            av   = data['avail'].get(cat, 0)
            excl = (data['excused'].get(cat, 0) + data['sick'].get(cat, 0) +
                    data['injured'].get(cat, 0))
        eff = av - excl

        ctk.CTkLabel(tf, text=f"📅 {eff} branych pod uwagę",
                    font=("Segoe UI", 10), text_color="#555", anchor="w").pack(anchor="w")

        # --- ŚRODEK ---
        mid = ctk.CTkFrame(card, fg_color="transparent")
        mid.grid(row=0, column=1, sticky="nsew", padx=8, pady=10)

        # ✅ POPRAWKA — osobne bloki if/else, żadnych średników inline
        if cat == 'all':
            pres = sum(data['present'].values())
            late = sum(data['late'].values())
            abs_ = sum(data['absent'].values())
            exc  = sum(data['excused'].values())
            sick = sum(data['sick'].values())
            inj  = sum(data['injured'].values())
        else:
            pres = data['present'].get(cat, 0)
            late = data['late'].get(cat, 0)
            abs_ = data['absent'].get(cat, 0)
            exc  = data['excused'].get(cat, 0)
            sick = data['sick'].get(cat, 0)
            inj  = data['injured'].get(cat, 0)

        ctk.CTkLabel(mid,
                    text=f"✅ {pres}   ⏰ {late}   ❌ {abs_}",
                    font=("Segoe UI", 13, "bold"),
                    text_color="#ccc").pack(anchor="w")

        ctk.CTkLabel(mid,
                    text=f"📋 {exc}   🤒 {sick}   🩹 {inj}",
                    font=("Segoe UI", 11),
                    text_color="#888").pack(anchor="w", pady=(2, 0))

        # ✅ POPRAWKA — color musi być zdefiniowany PRZED użyciem w obu gałęziach
        if pct is not None:
            color = ("#2cc985" if pct >= 90 else
                    "#1f6aa5" if pct >= 80 else
                    "#e67e22" if pct >= 70 else
                    "#c92c2c")
            bar = ctk.CTkProgressBar(mid, height=8, progress_color=color)
            bar.set(pct / 100)
            bar.pack(fill="x", pady=(6, 0))
        else:
            color = "#555"
            ctk.CTkLabel(mid, text="Brak danych",
                        font=("Segoe UI", 11),
                        text_color="#444").pack(anchor="w", pady=(8, 0))

        # --- PRAWA ---
        right = ctk.CTkFrame(card, fg_color="transparent")
        right.grid(row=0, column=2, sticky="nsew", padx=12, pady=10)

        ctk.CTkLabel(right,
                    text=f"{pct}%" if pct is not None else "—",
                    font=("Segoe UI", 24, "bold"),
                    text_color=color).pack(anchor="e")

        if pct is not None and team_avg > 0:
            diff     = pct - team_avg
            diff_col = "#2cc985" if diff >= 0 else "#c92c2c"
            ctk.CTkLabel(right,
                        text=f"{diff:+.1f}% vs śr.",
                        font=("Segoe UI", 11, "bold"),
                        text_color=diff_col).pack(anchor="e")