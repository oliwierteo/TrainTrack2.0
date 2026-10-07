# views/scouting_view.py v3.0 - SCOUT PRO

import customtkinter as ctk
import tkinter.messagebox as msgbox
from database import supabase
from database import safe_int
import database
import datetime
import threading
from ui_async import run_async
from logger import logger
import teams

COLORS = {
    "bg_dark":   "#121212",
    "panel_bg":  "#1e1e1e",
    "accent":    "#3b8ed0",
    "success":   "#2fa572",
    "warning":   "#f39c12",
    "danger":    "#cf352e",
    "transfer":  "#e67e22",
    "text_gray": "#aaaaaa",
    "gold":      "#FFD700",
    "purple":    "#9b59b6",
}

POSITION_LIST = ["BR", "LO", "ŚO", "PO", "DP", "ŚP", "LP", "PP", "OP", "N"]

PRIORITY_COLORS = {
    "Pilny":    "#e74c3c",
    "Wysoki":   "#f39c12",
    "Normalny": "#3498db",
    "Niski":    "#7f8c8d",
}

POS_ORDER = {
    'BR': 1, 'GK': 1,
    'LO': 2, 'LB': 2, 'ŚO': 3, 'CB': 3, 'PO': 4, 'RB': 4,
    'DP': 5, 'DM': 5, 'ŚP': 6, 'CM': 6, 'ŚPO': 7, 'CAM': 7,
    'LS': 8, 'LW': 8, 'PS': 9, 'RW': 9,
    'N': 10, 'ST': 10
}

STATUS_COLORS = {
    "Obserwowany": "#3498db",
    "Zaproszony":  "#2ecc71",
    "Odrzucony":   "#e74c3c",
    "Do kontaktu": "#f39c12",
}


def rating_bar(parent, label, value, max_val=10, color="#3b8ed0"):
    """Mini pasek oceny"""
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.pack(fill="x", padx=5, pady=1)
    ctk.CTkLabel(frame, text=label, width=100, anchor="w",
                 font=("Segoe UI", 10), text_color="#aaa").pack(side="left")
    bar_bg = ctk.CTkFrame(frame, fg_color="#2b2b2b", height=12,
                          width=150, corner_radius=6)
    bar_bg.pack(side="left", padx=5)
    bar_bg.pack_propagate(False)
    if value and value > 0:
        fill_w = int((value / max_val) * 150)
        fill = ctk.CTkFrame(bar_bg, fg_color=color, height=12,
                            width=fill_w, corner_radius=6)
        fill.pack(side="left")
        fill.pack_propagate(False)
    ctk.CTkLabel(frame, text=f"{value}/10" if value else "—",
                 width=40, font=("Segoe UI", 10, "bold"),
                 text_color=color).pack(side="left", padx=3)


class ScoutingView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg_dark"])

        self.search_timer      = None
        self.current_target_id = None
        self.current_data      = None
        self.targets_data      = []
        self._loading          = False

        self.grid_columnconfigure(0, weight=0, minsize=340)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._create_left_panel()
        self._create_right_panel()

        self.after(50, self._load_data_async)

    # ════════════════════════════════════════════
    # LEWY PANEL
    # ════════════════════════════════════════════
    def _create_left_panel(self):
        self.left_panel = ctk.CTkFrame(self, width=340, corner_radius=0,
                                       fg_color=COLORS["panel_bg"])
        self.left_panel.grid(row=0, column=0, sticky="nsew")
        self.left_panel.grid_propagate(False)

        # Header
        hf = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        hf.pack(pady=(20, 5), fill="x", padx=10)
        ctk.CTkLabel(hf, text="🔍 SCOUTING PRO",
                     font=("Segoe UI", 22, "bold"),
                     text_color=COLORS["accent"]).pack(side="left")
        ctk.CTkButton(hf, text="⟳", width=40, fg_color="#444",
                      command=self.force_refresh).pack(side="right")

        # Filtry
        filter_frame = ctk.CTkFrame(self.left_panel, fg_color="#252525",
                                    corner_radius=10)
        filter_frame.pack(fill="x", padx=10, pady=5)

        self.search_entry = ctk.CTkEntry(filter_frame,
                                         placeholder_text="🔍 Szukaj...",
                                         width=200)
        self.search_entry.pack(side="left", padx=10, pady=8)
        self.search_entry.bind("<KeyRelease>", self.filter_list)

        self.filter_pos = ctk.CTkOptionMenu(
            filter_frame, values=["Wszystkie"] + POSITION_LIST,
            width=100, command=lambda _: self.do_filter())
        self.filter_pos.pack(side="left", padx=5, pady=8)

        # Filtr priorytetu
        prio_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        prio_frame.pack(fill="x", padx=10, pady=(0, 5))

        self.filter_priority = ctk.CTkOptionMenu(
            prio_frame,
            values=["Wszystkie priorytety", "Pilny", "Wysoki", "Normalny", "Niski"],
            width=160, command=lambda _: self.do_filter())
        self.filter_priority.pack(side="left", padx=2)

        self.filter_status = ctk.CTkOptionMenu(
            prio_frame,
            values=["Wszystkie statusy", "Obserwowany", "Zaproszony",
                    "Odrzucony", "Do kontaktu"],
            width=160, command=lambda _: self.do_filter())
        self.filter_status.pack(side="left", padx=2)

        # Statystyki
        self.stats_frame = ctk.CTkFrame(self.left_panel, fg_color="#1a1a1a",
                                         corner_radius=8)
        self.stats_frame.pack(fill="x", padx=10, pady=5)
        self.stats_label = ctk.CTkLabel(self.stats_frame,
                                         text="Ładowanie...", text_color="gray",
                                         font=("Segoe UI", 10))
        self.stats_label.pack(pady=5)

        # Lista
        self.scroll_list = ctk.CTkScrollableFrame(self.left_panel,
                                                   fg_color="transparent")
        self.scroll_list.pack(fill="both", expand=True, padx=5, pady=5)

        self.loading_label = ctk.CTkLabel(self.scroll_list,
                                           text="⏳ Ładowanie...",
                                           text_color="gray")
        self.loading_label.pack(pady=20)

    # ════════════════════════════════════════════
    # PRAWY PANEL - FORMULARZ
    # ════════════════════════════════════════════
    def _create_right_panel(self):
        self.right_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        self.form_scroll = ctk.CTkScrollableFrame(self.right_panel,
                                                   fg_color=COLORS["panel_bg"],
                                                   corner_radius=10)
        self.form_scroll.pack(fill="both", expand=True)

        self._build_form()

    def _build_form(self):
        fs = self.form_scroll

        # ── Header ──
        hbar = ctk.CTkFrame(fs, fg_color="transparent")
        hbar.pack(fill="x", padx=20, pady=15)
        self.lbl_mode = ctk.CTkLabel(hbar, text="KARTA OBSERWACJI",
                                      font=("Segoe UI", 20, "bold"))
        self.lbl_mode.pack(side="left")
        ctk.CTkButton(hbar, text="+ NOWY", fg_color="#444", width=80,
                      command=self.clear_form).pack(side="right")

        # ── SEKCJA 1: Dane osobowe ──
        self._section_header(fs, "👤 DANE OSOBOWE")

        g1 = self._grid(fs)

        self._lbl(g1, "Imię i Nazwisko:", 0, 0)
        self.ent_name = self._ent(g1, "np. Jan Kowalski", 1, 0, colspan=2)

        self._lbl(g1, "Obecny Klub:", 2, 0)
        self.ent_club = self._ent(g1, "np. Wisła Kraków", 3, 0)

        self._lbl(g1, "Narodowość:", 2, 1)
        self.ent_nationality = self._ent(g1, "np. Polska", 3, 1)

        self._lbl(g1, "Wiek:", 4, 0)
        self.ent_age = self._ent(g1, "lat", 5, 0)

        self._lbl(g1, "Wzrost (cm):", 4, 1)
        self.ent_height = self._ent(g1, "cm", 5, 1)

        self._lbl(g1, "Waga (kg):", 4, 2)
        self.ent_weight = self._ent(g1, "kg", 5, 2)

        # ── SEKCJA 2: Dane sportowe ──
        self._section_header(fs, "⚽ DANE SPORTOWE")

        g2 = self._grid(fs)

        self._lbl(g2, "Pozycja:", 0, 0)
        self.cmb_pos = ctk.CTkOptionMenu(g2, values=POSITION_LIST, width=160)
        self.cmb_pos.grid(row=1, column=0, padx=5, pady=(0, 15), sticky="w")

        self._lbl(g2, "Lepsza noga:", 0, 1)
        self.cmb_foot = ctk.CTkOptionMenu(g2,
                                          values=["Prawa", "Lewa", "Obunożny"],
                                          width=160)
        self.cmb_foot.grid(row=1, column=1, padx=5, pady=(0, 15), sticky="w")

        self._lbl(g2, "Kontrakt do:", 0, 2)
        self.ent_contract = self._ent(g2, "YYYY-MM", 1, 2)

        # ── SEKCJA 3: Ocena scauta ──
        self._section_header(fs, "📊 OCENA SCAUTA")

        g3 = self._grid(fs)

        self._lbl(g3, "Potencjał (1-5⭐):", 0, 0)
        self.cmb_rating = ctk.CTkOptionMenu(g3,
                                            values=["1", "2", "3", "4", "5"],
                                            width=120)
        self.cmb_rating.grid(row=1, column=0, padx=5, pady=(0, 15), sticky="w")
        self.cmb_rating.set("3")

        self._lbl(g3, "Priorytet:", 0, 1)
        self.cmb_priority = ctk.CTkOptionMenu(g3,
                                              values=["Pilny", "Wysoki",
                                                      "Normalny", "Niski"],
                                              width=140,
                                              fg_color=COLORS["accent"])
        self.cmb_priority.grid(row=1, column=1, padx=5, pady=(0, 15), sticky="w")
        self.cmb_priority.set("Normalny")

        self._lbl(g3, "Status:", 0, 2)
        self.cmb_status = ctk.CTkOptionMenu(g3,
                                            values=["Obserwowany", "Zaproszony",
                                                    "Odrzucony", "Do kontaktu"],
                                            fg_color=COLORS["accent"], width=140)
        self.cmb_status.grid(row=1, column=2, padx=5, pady=(0, 15), sticky="w")

        # Oceny techniczne (suwaki 1-10)
        self._section_header(fs, "🎯 OCENY SZCZEGÓŁOWE (1-10)")

        sliders_frame = ctk.CTkFrame(fs, fg_color="#1a1a1a", corner_radius=10)
        sliders_frame.pack(fill="x", padx=20, pady=(0, 10))

        sliders_grid = ctk.CTkFrame(sliders_frame, fg_color="transparent")
        sliders_grid.pack(fill="x", padx=15, pady=10)
        sliders_grid.grid_columnconfigure((0, 1), weight=1)

        self.sliders = {}
        slider_defs = [
            ("Technika",     "technical",    "#3498db",  0, 0),
            ("Fizyczność",   "physical",     "#e74c3c",  0, 1),
            ("Mentalność",   "mental",       "#9b59b6",  1, 0),
            ("Szybkość",     "speed_rating", "#f39c12",  1, 1),
        ]

        for label, key, color, row, col in slider_defs:
            sf = ctk.CTkFrame(sliders_grid, fg_color="transparent")
            sf.grid(row=row, column=col, padx=10, pady=5, sticky="ew")

            hf2 = ctk.CTkFrame(sf, fg_color="transparent")
            hf2.pack(fill="x")
            ctk.CTkLabel(hf2, text=label, font=("Segoe UI", 11, "bold"),
                         text_color=color).pack(side="left")
            val_lbl = ctk.CTkLabel(hf2, text="5", font=("Segoe UI", 12, "bold"),
                                   text_color=color, width=30)
            val_lbl.pack(side="right")

            sl = ctk.CTkSlider(sf, from_=1, to=10, number_of_steps=9,
                               progress_color=color, button_color=color,
                               height=14)
            sl.set(5)
            sl.pack(fill="x", pady=3)

            def make_updater(lbl):
                return lambda v: lbl.configure(text=str(int(v)))

            sl.configure(command=make_updater(val_lbl))
            self.sliders[key] = sl

        # Ogólna ocena (na żywo)
        self.overall_frame = ctk.CTkFrame(sliders_frame, fg_color="#252525",
                                           corner_radius=8)
        self.overall_frame.pack(fill="x", padx=15, pady=(0, 10))
        self.overall_label = ctk.CTkLabel(self.overall_frame,
                                           text="Śr. ocena: —",
                                           font=("Segoe UI", 13, "bold"),
                                           text_color=COLORS["gold"])
        self.overall_label.pack(pady=8)

        for sl in self.sliders.values():
            sl.configure(command=self._make_slider_cmd(sl,
                         list(self.sliders.values())))

        # ── SEKCJA 4: Finanse / Transfer ──
        self._section_header(fs, "💰 FINANSE & TRANSFER")

        g4 = self._grid(fs)

        self._lbl(g4, "Szac. wartość rynkowa:", 0, 0)
        self.ent_market_val = self._ent(g4, "np. 50 000 PLN", 1, 0)

        self._lbl(g4, "Koszt pozyskania:", 0, 1)
        self.ent_val = self._ent(g4, "np. 5000 PLN", 1, 1)

        self._lbl(g4, "Meczów obserwowanych:", 0, 2)
        self.ent_games = self._ent(g4, "0", 1, 2)

        self._lbl(g4, "Ostatnia obserwacja:", 2, 0)
        self.ent_last_obs = self._ent(g4, "YYYY-MM-DD", 3, 0)

        self._lbl(g4, "Kontakt (Agent/Rodzic):", 2, 1)
        self.ent_contact = self._ent(g4, "Telefon / Email", 3, 1, colspan=2)

        # ── SEKCJA 5: Analiza ──
        self._section_header(fs, "💪 MOCNE STRONY")
        self.txt_strengths = ctk.CTkTextbox(fs, height=80,
                                            font=("Consolas", 11))
        self.txt_strengths.pack(fill="x", padx=20, pady=(0, 10))

        self._section_header(fs, "⚠️ SŁABE STRONY")
        self.txt_weaknesses = ctk.CTkTextbox(fs, height=80,
                                             font=("Consolas", 11))
        self.txt_weaknesses.pack(fill="x", padx=20, pady=(0, 10))

        self._section_header(fs, "📋 SZCZEGÓŁOWY RAPORT SCAUTA")
        self.txt_notes = ctk.CTkTextbox(fs, height=150,
                                        font=("Consolas", 11))
        self.txt_notes.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # ── PRZYCISKI ──
        action_bar = ctk.CTkFrame(fs, fg_color="transparent")
        action_bar.pack(fill="x", padx=20, pady=15)

        self.btn_transfer = ctk.CTkButton(
            action_bar, text="✍️ PODPISZ KONTRAKT",
            fg_color=COLORS["transfer"], height=45,
            font=("Segoe UI", 12, "bold"),
            command=self.transfer_to_squad)

        self.btn_delete = ctk.CTkButton(
            action_bar, text="🗑 USUŃ", height=45, width=90,
            fg_color="transparent", border_width=1,
            border_color=COLORS["danger"], text_color=COLORS["danger"],
            command=self.delete_target)

        self.btn_save = ctk.CTkButton(
            action_bar, text="💾 ZAPISZ ZMIANY",
            fg_color=COLORS["success"], height=45, width=200,
            font=("Segoe UI", 14, "bold"), command=self.save_target)
        self.btn_save.pack(side="right", padx=5)

    # ════════════════════════════════════════════
    # HELPERS
    # ════════════════════════════════════════════
    def _section_header(self, parent, text):
        f = ctk.CTkFrame(parent, fg_color="#2b2b2b", corner_radius=8, height=32)
        f.pack(fill="x", padx=20, pady=(12, 4))
        f.pack_propagate(False)
        ctk.CTkLabel(f, text=text, font=("Segoe UI", 12, "bold"),
                     text_color=COLORS["accent"]).pack(side="left", padx=12, pady=4)

    def _grid(self, parent):
        g = ctk.CTkFrame(parent, fg_color="transparent")
        g.pack(fill="x", padx=20)
        g.grid_columnconfigure((0, 1, 2), weight=1)
        return g

    def _lbl(self, parent, text, r, c):
        ctk.CTkLabel(parent, text=text,
                     font=("Segoe UI", 11, "bold")).grid(
            row=r, column=c, sticky="w", padx=5, pady=(8, 2))

    def _ent(self, parent, placeholder, r, c, colspan=1):
        e = ctk.CTkEntry(parent, placeholder_text=placeholder)
        e.grid(row=r, column=c, columnspan=colspan,
               sticky="ew", padx=5, pady=(0, 10))
        return e

    def _make_slider_cmd(self, _slider, all_sliders):
        def cmd(v):
            # Aktualizuj etykietę powiązaną (już ustawiona wcześniej)
            try:
                vals = [int(sl.get()) for sl in all_sliders]
                avg  = sum(vals) / len(vals)
                clr  = "#2ecc71" if avg >= 7 else "#f39c12" if avg >= 5 else "#e74c3c"
                self.overall_label.configure(
                    text=f"Śr. ocena: {avg:.1f}/10", text_color=clr)
            except Exception:
                pass
        return cmd

    # ════════════════════════════════════════════
    # ŁADOWANIE DANYCH
    # ════════════════════════════════════════════
    def _load_data_async(self):
        if self._loading:
            return
        self._loading = True

        def fetch():
            try:
                from cache_manager import cache
                data = cache.get_scouting_targets(force_refresh=False)
                sorted_data = self._sort_targets(data)
                self.after(0, lambda: self._update_list_ui(sorted_data))
            except Exception as e:
                print(f"Scouting error: {e}")
                self.after(0, lambda: self._show_error(str(e)))
            finally:
                self._loading = False

        threading.Thread(target=fetch, daemon=True).start()

    def _sort_targets(self, data):
        try:
            return sorted(data, key=lambda x: (
                {"Pilny": 0, "Wysoki": 1, "Normalny": 2, "Niski": 3}.get(
                    x.get('scout_priority', 'Normalny'), 2),
                POS_ORDER.get(str(x.get('position', '')).upper(), 99),
                -int(x.get('rating', 0) or 0)
            ))
        except Exception as e:
            print(f"Sort error: {e}")
            return data

    def _update_list_ui(self, data):
        self.targets_data = data

        if self.loading_label and self.loading_label.winfo_exists():
            self.loading_label.destroy()

        self._update_stats(data)
        self.refresh_list(data)

    def _update_stats(self, data):
        """Aktualizuje ministatystyki na górze listy"""
        total      = len(data)
        pilne      = sum(1 for x in data if x.get('scout_priority') == 'Pilny')
        zaproszone = sum(1 for x in data if x.get('status') == 'Zaproszony')

        self.stats_label.configure(
            text=f"👥 Łącznie: {total}  |  🔴 Pilne: {pilne}  |  ✉️ Zaproszeni: {zaproszone}",
            text_color="#aaa"
        )

    def _show_error(self, message):
        if self.loading_label and self.loading_label.winfo_exists():
            self.loading_label.configure(text=f"❌ Błąd: {message}",
                                         text_color="red")

    # ════════════════════════════════════════════
    # LISTA
    # ════════════════════════════════════════════
    def refresh_list(self, data):
        for w in self.scroll_list.winfo_children():
            w.destroy()

        if not data:
            ctk.CTkLabel(self.scroll_list,
                         text="Brak wyników", text_color="gray").pack(pady=20)
            return

        for item in data:
            self._create_target_card(item)

    def _create_target_card(self, item):
        r_val      = int(item.get('rating', 3) or 3)
        priority   = item.get('scout_priority', 'Normalny')
        status     = item.get('status', 'Obserwowany')
        prio_color = PRIORITY_COLORS.get(priority, "#7f8c8d")
        stat_color = STATUS_COLORS.get(status, "#3498db")

        card = ctk.CTkFrame(self.scroll_list, fg_color="#2b2b2b",
                            corner_radius=8)
        card.pack(fill="x", pady=3, padx=5)

        # Pasek priorytetu
        ctk.CTkFrame(card, width=5, height=70,
                     fg_color=prio_color, corner_radius=3).pack(
            side="left", fill="y", padx=(0, 5))

        # Info
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(side="left", padx=5, pady=6, fill="both", expand=True)

        # Linia 1: Nazwa
        name = item.get('full_name', '?')
        display_name = name[:24] if len(name) > 24 else name
        ctk.CTkLabel(info, text=display_name,
                     font=("Segoe UI", 12, "bold")).pack(anchor="w")

        # Linia 2: Pozycja + Klub
        club = item.get('current_club', '') or ''
        ctk.CTkLabel(info,
                     text=f"📍 {item.get('position','?')}  |  🏟 {club[:20]}",
                     font=("Segoe UI", 10), text_color="gray").pack(anchor="w")

        # Linia 3: Status + Priorytet + Ocena
        row3 = ctk.CTkFrame(info, fg_color="transparent")
        row3.pack(anchor="w", fill="x")

        ctk.CTkLabel(row3, text=f"● {status}",
                     font=("Segoe UI", 10, "bold"),
                     text_color=stat_color).pack(side="left")

        ctk.CTkLabel(row3, text=f"  {priority}",
                     font=("Segoe UI", 10),
                     text_color=prio_color).pack(side="left")

        stars = "⭐" * r_val + "☆" * (5 - r_val)
        ctk.CTkLabel(row3, text=f"  {stars}",
                     font=("Segoe UI", 9)).pack(side="left")

        # Waga/Wzrost jeśli są
        extras = []
        if item.get('height'):
            extras.append(f"📏 {item['height']}cm")
        if item.get('weight'):
            extras.append(f"⚖️ {item['weight']}kg")
        if item.get('age'):
            extras.append(f"🎂 {item['age']}l")
        if extras:
            ctk.CTkLabel(info, text="  ".join(extras),
                         font=("Segoe UI", 9), text_color="#666").pack(anchor="w")

        # Przycisk
        ctk.CTkButton(card, text="›", width=28, height=50,
                      fg_color="transparent", hover_color="#3b3b3b",
                      font=("Segoe UI", 18, "bold"),
                      command=lambda i=item: self.select_target(i)
                      ).pack(side="right", padx=5)

    # ════════════════════════════════════════════
    # WYBÓR CELU
    # ════════════════════════════════════════════
    def select_target(self, item):
        self.current_target_id = item['id']
        self.current_data      = item
        self.lbl_mode.configure(text=f"PROFIL: {item['full_name']}")

        def _set(ent, val):
            ent.delete(0, "end")
            ent.insert(0, str(val) if val else "")

        _set(self.ent_name,        item.get('full_name', ''))
        _set(self.ent_club,        item.get('current_club', ''))
        _set(self.ent_nationality, item.get('nationality', ''))
        _set(self.ent_age,         item.get('age', ''))
        _set(self.ent_height,      item.get('height', ''))
        _set(self.ent_weight,      item.get('weight', ''))
        _set(self.ent_contract,    item.get('contract_until', ''))
        _set(self.ent_val,         item.get('estimated_value', ''))
        _set(self.ent_market_val,  item.get('market_value', ''))
        _set(self.ent_games,       item.get('observed_games', ''))
        _set(self.ent_last_obs,    item.get('last_observed', ''))
        _set(self.ent_contact,     item.get('contact_info', ''))

        self.cmb_pos.set(item.get('position', 'N'))
        self.cmb_foot.set(item.get('foot', 'Prawa'))
        self.cmb_status.set(item.get('status', 'Obserwowany'))
        self.cmb_rating.set(str(item.get('rating', 3) or 3))
        self.cmb_priority.set(item.get('scout_priority', 'Normalny'))

        # Suwaki
        for key, sl in self.sliders.items():
            v = item.get(key, 5) or 5
            sl.set(int(v))

        # Aktualizuj średnią
        try:
            vals = [int(sl.get()) for sl in self.sliders.values()]
            avg  = sum(vals) / len(vals)
            clr  = "#2ecc71" if avg >= 7 else "#f39c12" if avg >= 5 else "#e74c3c"
            self.overall_label.configure(
                text=f"Śr. ocena: {avg:.1f}/10", text_color=clr)
        except Exception:
            pass

        # Teksty
        self.txt_strengths.delete("1.0", "end")
        self.txt_strengths.insert("1.0", item.get('strengths', '') or '')

        self.txt_weaknesses.delete("1.0", "end")
        self.txt_weaknesses.insert("1.0", item.get('weaknesses', '') or '')

        self.txt_notes.delete("1.0", "end")
        self.txt_notes.insert("1.0", item.get('notes', '') or '')

        # Pokaż przyciski
        self.btn_delete.pack(side="left", padx=5)
        self.btn_transfer.pack(side="left", padx=5)

        # Przewiń do góry formularza
        try:
            self.form_scroll._parent_canvas.yview_moveto(0)
        except Exception:
            pass

    def clear_form(self):
        self.current_target_id = None
        self.current_data      = None
        self.lbl_mode.configure(text="KARTA OBSERWACJI")

        for ent in [self.ent_name, self.ent_club, self.ent_nationality,
                    self.ent_age, self.ent_height, self.ent_weight,
                    self.ent_contract, self.ent_val, self.ent_market_val,
                    self.ent_games, self.ent_last_obs, self.ent_contact]:
            ent.delete(0, "end")

        for sl in self.sliders.values():
            sl.set(5)
        self.overall_label.configure(text="Śr. ocena: 5.0/10",
                                     text_color=COLORS["accent"])

        for tb in [self.txt_strengths, self.txt_weaknesses, self.txt_notes]:
            tb.delete("1.0", "end")

        self.cmb_priority.set("Normalny")
        self.cmb_status.set("Obserwowany")
        self.cmb_rating.set("3")

        self.btn_delete.pack_forget()
        self.btn_transfer.pack_forget()

    # ════════════════════════════════════════════
    # CRUD
    # ════════════════════════════════════════════
    def save_target(self):
        name = self.ent_name.get().strip()
        if not name:
            return msgbox.showwarning("Błąd", "Imię i nazwisko wymagane!")

        data = {
            "club_name":      database.CURRENT_CLUB,
            "full_name":      name,
            "current_club":   self.ent_club.get().strip(),
            "nationality":    self.ent_nationality.get().strip(),
            "age":            safe_int(self.ent_age.get(), default=None),
            "height":         safe_int(self.ent_height.get(), default=None),
            "weight":         safe_int(self.ent_weight.get(), default=None),
            "contract_until": self.ent_contract.get().strip(),
            "position":       self.cmb_pos.get(),
            "foot":           self.cmb_foot.get(),
            "status":         self.cmb_status.get(),
            "scout_priority": self.cmb_priority.get(),
            "rating":         int(self.cmb_rating.get()),
            "estimated_value":self.ent_val.get().strip(),
            "market_value":   self.ent_market_val.get().strip(),
            "observed_games": safe_int(self.ent_games.get(), default=0),
            "last_observed":  self.ent_last_obs.get().strip() or None,
            "contact_info":   self.ent_contact.get().strip(),
            "strengths":      self.txt_strengths.get("1.0", "end").strip(),
            "weaknesses":     self.txt_weaknesses.get("1.0", "end").strip(),
            "notes":          self.txt_notes.get("1.0", "end").strip(),
            "technical":      int(self.sliders['technical'].get()),
            "physical":       int(self.sliders['physical'].get()),
            "mental":         int(self.sliders['mental'].get()),
            "speed_rating":   int(self.sliders['speed_rating'].get()),
        }

        # FIX: zapis do bazy leci w wątku (okno nie zamraża się na czas sieci)
        target_id = self.current_target_id

        def _work():
            if target_id:
                supabase.table('scouting_targets').update(data)\
                    .eq('id', target_id).execute()
                database.log_activity(f"zaktualizował raport: {name}")
            else:
                supabase.table('scouting_targets').insert(data).execute()
                database.log_activity(f"dodał do scoutingu: {name}")

        def _ok(_result=None):
            msgbox.showinfo("Sukces", "Karta zapisana pomyślnie.")
            from cache_manager import cache
            cache.invalidate_scouting()
            self._load_data_async()
            self.clear_form()

        run_async(self, _work, on_success=_ok,
                  on_error=lambda e: msgbox.showerror("Błąd", str(e)))

    def delete_target(self):
        if not self.current_target_id:
            return
        if not msgbox.askyesno("Usuń", "Usunąć zawodnika z bazy scoutingu?"):
            return
        # FIX: DELETE w wątku roboczym
        name = self.ent_name.get()
        target_id = self.current_target_id

        def _work():
            supabase.table('scouting_targets').delete()\
                .eq('id', target_id).execute()
            database.log_activity(f"usunął raport: {name}")

        def _ok(_result=None):
            from cache_manager import cache
            cache.invalidate_scouting()
            self._load_data_async()
            self.clear_form()

        run_async(self, _work, on_success=_ok,
                  on_error=lambda e: msgbox.showerror("Błąd", str(e)))

    def transfer_to_squad(self):
        if not self.current_data:
            return
        name = self.current_data['full_name']
        if not msgbox.askyesno("KONTRAKT",
                               f"Podpisać kontrakt z {name}?\n"
                               "Zawodnik trafi do głównej kadry."):
            return
        # FIX: transfer = 2 zapisy do bazy - wątek roboczy, UI czeka żywe
        new_player = {
            "full_name":        name,
            "age":              self.current_data.get('age'),
            "primary_position": self.current_data.get('position', 'N'),
            "club_name":        database.CURRENT_CLUB,
            "strengths":        self.current_data.get('strengths', ''),
            "weaknesses":       self.current_data.get('weaknesses', ''),
            "join_date":        datetime.date.today().isoformat(),
            "jersey_number":    0,
        }
        target_id = self.current_target_id

        def _work():
            res = supabase.table('players').insert(new_player).execute()
            # od razu przypisujemy do AKTYWNEJ drużyny, inaczej nie pojawi się
            # w kadrze (kadrę filtrujemy po player_team_terms)
            new_id = None
            try:
                if getattr(res, "data", None):
                    new_id = res.data[0]['id']
            except Exception:
                new_id = None
            if new_id:
                ok, info = teams.assign_player(new_id, teams.get_current_team())
                if not ok:
                    logger.error(f"Nie udało się przypisać gracza: {info}")

            supabase.table('scouting_targets').delete()\
                .eq('id', target_id).execute()
            database.log_activity(
                f"podpisał kontrakt z: {name} ({teams.scope_label()})")

        def _ok(_result=None):
            msgbox.showinfo("GRATULACJE!",
                            f"{name} nowym graczem {database.CURRENT_CLUB}!")
            from cache_manager import cache
            cache.invalidate_scouting()
            cache.invalidate_players()
            self._load_data_async()
            self.clear_form()

        run_async(self, _work, on_success=_ok,
                  on_error=lambda e: msgbox.showerror("Błąd transferu", str(e)))

    # ════════════════════════════════════════════
    # WYSZUKIWANIE / FILTROWANIE
    # ════════════════════════════════════════════
    def filter_list(self, event=None):
        if self.search_timer:
            self.after_cancel(self.search_timer)
        self.search_timer = self.after(300, self.do_filter)

    def do_filter(self):
        query    = self.search_entry.get().lower().strip()
        pos_f    = self.filter_pos.get()
        prio_f   = self.filter_priority.get()
        status_f = self.filter_status.get()

        result = self.targets_data

        if query:
            result = [x for x in result
                      if query in x.get('full_name', '').lower()
                      or query in (x.get('current_club') or '').lower()
                      or query in (x.get('nationality') or '').lower()]

        if pos_f != "Wszystkie":
            result = [x for x in result if x.get('position') == pos_f]

        if prio_f != "Wszystkie priorytety":
            result = [x for x in result
                      if x.get('scout_priority') == prio_f]

        if status_f != "Wszystkie statusy":
            result = [x for x in result if x.get('status') == status_f]

        self.refresh_list(result)

    def force_refresh(self):
        from cache_manager import cache
        cache.invalidate_scouting()
        self._load_data_async()

    def load_targets(self):
        self._load_data_async()