# views/players_view.py - POPRAWKI v2

import customtkinter as ctk
from database import supabase
import database
import teams
from image_manager import img_manager
from logger import logger
import datetime
import tkinter.messagebox as tk_msgbox
import threading

COLORS = {
    "bg_dark":   "#121212",
    "card_bg":   "#1e1e1e",
    "card_hover":"#2a2a2a",
    "accent":    "#3b8ed0",
    "success":   "#2ecc71",
    "warning":   "#f39c12",
    "danger":    "#e74c3c",
    "text_dim":  "#888888",
    "border":    "#333333",
}

HEALTH_COLORS = {
    "zdrowy":      ("#2ecc71", "✅"),
    "kontuzja":    ("#e74c3c", "🏥"),
    "lekki_uraz":  ("#f39c12", "⚠️"),
}


class PlayerCard(ctk.CTkFrame):
    def __init__(self, master, player_data, on_click, on_team=None, **kwargs):
        super().__init__(master, **kwargs)
        self.player_data = player_data
        self._all_widgets = []

        self.configure(
            fg_color=COLORS["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"]
            
        )
        

        # Dane
        name        = str(player_data.get('full_name', 'Nieznany'))
        number      = str(player_data.get('jersey_number') or '-')
        age         = str(player_data.get('age') or '-')
        primary_pos = str(player_data.get('primary_position') or '-')
        alt_pos     = player_data.get('alternative_positions', [])
        strengths   = str(player_data.get('strengths') or '')
        weaknesses  = str(player_data.get('weaknesses') or '')
        health      = str(player_data.get('health_status', 'zdrowy'))
        goal_txt    = str(player_data.get('development_goal') or '')
        prog        = player_data.get('goal_progress')
        if not isinstance(prog, (int, float)):
            prog = 0
        key_ability = player_data.get('key_ability', '')

        # ══════ LAYOUT ══════
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=12, pady=8)
        self._all_widgets.append(main)

        # ── LEWA: Zdjęcie 70x70 + Numer ──
        left = ctk.CTkFrame(main, fg_color="transparent", width=85)
        left.pack(side="left", padx=(0, 12))
        left.pack_propagate(False)
        self._all_widgets.append(left)

        self.photo_label = ctk.CTkLabel(left, text="", width=70, height=70)
        self.photo_label.pack(pady=(0, 3))
        self._all_widgets.append(self.photo_label)

        img = img_manager.get_circular_image(
            player_id=player_data.get('id'),
            photo_url=player_data.get('photo_url'),
            size=(70, 70),
            callback=self.update_photo
        )
        self.photo_label.configure(image=img)

        nr_lbl = ctk.CTkLabel(left, text=f"#{number}",
                               font=("Arial", 13, "bold"),
                               text_color=COLORS["accent"])
        nr_lbl.pack()
        self._all_widgets.append(nr_lbl)

        # ── ŚRODEK ──
        center = ctk.CTkFrame(main, fg_color="transparent")
        center.pack(side="left", fill="both", expand=True)
        self._all_widgets.append(center)

        # Wiersz 1: Imię + Zdrowie
        row1 = ctk.CTkFrame(center, fg_color="transparent")
        row1.pack(fill="x")
        self._all_widgets.append(row1)

        w = ctk.CTkLabel(row1, text=name,
                         font=("Segoe UI", 17, "bold"), anchor="w")
        w.pack(side="left")
        self._all_widgets.append(w)

        h_color, h_icon = HEALTH_COLORS.get(health, ("#888", "●"))
        w = ctk.CTkLabel(row1, text=f" {h_icon} {health.upper()}",
                         font=("Segoe UI", 10, "bold"), text_color=h_color)
        w.pack(side="left", padx=8)
        self._all_widgets.append(w)

        # Wiersz 2: Pozycja + Wiek + Zdolność
        row2 = ctk.CTkFrame(center, fg_color="transparent")
        row2.pack(fill="x", pady=(2, 0))
        self._all_widgets.append(row2)

        pos_badge = ctk.CTkFrame(row2, fg_color="#2a4a6b", corner_radius=5)
        pos_badge.pack(side="left")
        self._all_widgets.append(pos_badge)

        w = ctk.CTkLabel(pos_badge, text=f" {primary_pos} ",
                         font=("Segoe UI", 11, "bold"), text_color="white")
        w.pack(padx=5, pady=1)
        self._all_widgets.append(w)

        if alt_pos and isinstance(alt_pos, list) and len(alt_pos) > 0:
            for ap in alt_pos[:3]:
                ab = ctk.CTkFrame(row2, fg_color="#1a3a2a", corner_radius=5)
                ab.pack(side="left", padx=2)
                self._all_widgets.append(ab)
                w = ctk.CTkLabel(ab, text=f" {ap} ",
                                 font=("Segoe UI", 10), text_color="#2ecc71")
                w.pack(padx=3, pady=1)
                self._all_widgets.append(w)

        w = ctk.CTkLabel(row2, text="│", text_color="#444",
                         font=("Segoe UI", 11))
        w.pack(side="left", padx=5)
        self._all_widgets.append(w)

        w = ctk.CTkLabel(row2, text=f"🎂 {age} lat",
                         font=("Segoe UI", 13), text_color=COLORS["text_dim"])
        w.pack(side="left")
        self._all_widgets.append(w)

        if key_ability:
            w = ctk.CTkLabel(row2, text="│", text_color="#444",
                             font=("Segoe UI", 11))
            w.pack(side="left", padx=5)
            self._all_widgets.append(w)

            w = ctk.CTkLabel(row2, text=f"🎯 {key_ability}",
                             font=("Segoe UI", 13, "bold"),
                             text_color="#9b59b6")
            w.pack(side="left")
            self._all_widgets.append(w)

        # Wiersz 3: Mocne / Słabe
        if strengths or weaknesses:
            row3 = ctk.CTkFrame(center, fg_color="transparent")
            row3.pack(fill="x", pady=(4, 0))
            self._all_widgets.append(row3)

            if strengths:
                s_txt = strengths[:35] + '..' if len(strengths) > 35 else strengths
                w = ctk.CTkLabel(row3, text=f"✅ {s_txt}",
                                 font=("Segoe UI", 12),
                                 text_color="#2ecc71")
                w.pack(side="left", padx=(0, 15))
                self._all_widgets.append(w)

            if weaknesses:
                w_txt = weaknesses[:35] + '..' if len(weaknesses) > 35 else weaknesses
                w = ctk.CTkLabel(row3, text=f"⚠️ {w_txt}",
                                 font=("Segoe UI", 12),
                                 text_color="#e74c3c")
                w.pack(side="left")
                self._all_widgets.append(w)

        # Wiersz 4: Atuty mentalne (jeśli są)
        mental = str(player_data.get('mental_strengths') or '')
        
        if mental:
            row_mental = ctk.CTkFrame(center, fg_color="transparent")
            row_mental.pack(fill="x", pady=(3, 0))
            self._all_widgets.append(row_mental)

            m_txt = mental[:50] + '..' if len(mental) > 50 else mental
            w = ctk.CTkLabel(row_mental, text=f"🧠 {m_txt}",
                             font=("Segoe UI", 12),
                             text_color="#9b59b6")
            w.pack(side="left")
            self._all_widgets.append(w)

        # Wiersz 5: Cel + Progress
        if goal_txt and goal_txt != 'Brak celu':
            row5 = ctk.CTkFrame(center, fg_color="transparent")
            row5.pack(fill="x", pady=(3, 0))
            self._all_widgets.append(row5)

            g_display = goal_txt[:35] + '..' if len(goal_txt) > 35 else goal_txt
            w = ctk.CTkLabel(row5, text=f"🎯 {g_display}",
                             font=("Segoe UI", 12),
                             text_color=COLORS["text_dim"])
            w.pack(side="left")
            self._all_widgets.append(w)

            w = ctk.CTkLabel(row5, text=f"{prog}%",
                             font=("Segoe UI", 12, "bold"),
                             text_color=COLORS["accent"])
            w.pack(side="right")
            self._all_widgets.append(w)

            bar_bg = ctk.CTkFrame(row5, fg_color="#2b2b2b",
                                   height=5, width=100, corner_radius=3)
            bar_bg.pack(side="right", padx=5)
            bar_bg.pack_propagate(False)
            self._all_widgets.append(bar_bg)

            fill_w = max(int((prog / 100) * 100), 0)
            bar_clr = "#2ecc71" if prog >= 75 else "#f39c12" if prog >= 40 else "#e74c3c"
            if fill_w > 0:
                bf = ctk.CTkFrame(bar_bg, fg_color=bar_clr,
                                  height=5, width=fill_w, corner_radius=3)
                bf.pack(side="left")
                self._all_widgets.append(bf)

        # ── PRAWA: Przycisk ──
        right = ctk.CTkFrame(main, fg_color="transparent", width=100)
        right.pack(side="right", padx=(8, 0))
        right.pack_propagate(False)
        self._all_widgets.append(right)

        # ── szybkie przypisanie do drużyn ──
        if on_team:
            team_btn = ctk.CTkButton(
                right, text="⚽", width=90, height=32,
                corner_radius=8,
                border_width=1,
                border_color="#3a3a3a",
                fg_color="transparent",
                hover_color="#1a3a2a",
                text_color="#2ecc71",
                font=("Segoe UI", 14, "bold"),
                command=lambda: on_team(self.player_data))
            team_btn.pack(fill="x", pady=(0, 4))
            self._all_widgets.append(team_btn)

        ctk.CTkButton(
            right, text="Profil ›",
            width=90, height=42,
            corner_radius=10,
            border_width=1,
            border_color=COLORS["accent"],
            fg_color="transparent",
            hover_color="#1a3a5a",
            text_color=COLORS["accent"],
            font=("Segoe UI", 13, "bold"),
            command=lambda: on_click(self.player_data)
        ).pack(expand=True)
        # ── HOVER: binduj na WSZYSTKIE widgety ──
        self._bind_hover_recursive(self)

    def _bind_hover_recursive(self, widget):
        """Binduje hover na widget i WSZYSTKIE jego dzieci"""
        try:
            widget.bind("<Enter>", self._on_enter, add="+")
            widget.bind("<Leave>", self._on_leave, add="+")
        except Exception:
            pass
        for child in widget.winfo_children():
            self._bind_hover_recursive(child)

    def _on_enter(self, event):
        self.configure(fg_color=COLORS["card_hover"],
                       border_color=COLORS["accent"])

    def _on_leave(self, event):
        # Sprawdź czy mysz faktycznie opuściła całą kartę
        try:
            x = self.winfo_pointerx() - self.winfo_rootx()
            y = self.winfo_pointery() - self.winfo_rooty()
            w = self.winfo_width()
            h = self.winfo_height()
            if 0 <= x <= w and 0 <= y <= h:
                return  # Mysz nadal jest na karcie
            self.configure(fg_color=COLORS["card_bg"],
                           border_color=COLORS["border"])
        except Exception:
            self.configure(fg_color=COLORS["card_bg"],
                           border_color=COLORS["border"])

    def update_photo(self, img):
        if self.photo_label.winfo_exists():
            self.photo_label.configure(image=img)


class PlayersView(ctk.CTkFrame):
    def __init__(self, master, on_open_profile):
        super().__init__(master, fg_color="transparent")
        self.on_open_profile = on_open_profile
        self.page = 0
        self.per_page = 10
        self.all_players_data = []

        # ── GÓRNY PASEK ──
        top_bar = ctk.CTkFrame(self, fg_color=COLORS["card_bg"],
                                corner_radius=12)
        top_bar.pack(fill="x", pady=(10, 15), padx=20)

        top_inner = ctk.CTkFrame(top_bar, fg_color="transparent")
        top_inner.pack(fill="x", padx=15, pady=12)

        self.title_label = ctk.CTkLabel(top_inner, text="👥 Kadra",
                                        font=("Segoe UI", 24, "bold"),
                                        text_color=COLORS["accent"])
        self.title_label.pack(side="left")
        self._update_title()

        btn_box = ctk.CTkFrame(top_inner, fg_color="transparent")
        btn_box.pack(side="right")

        ctk.CTkButton(btn_box, text="+ Dodaj Zawodnika",
                      fg_color="#2ecc71", hover_color="#27ae60",
                      height=38, font=("Segoe UI", 12, "bold"),
                      command=self.open_add_dialog).pack(side="left", padx=8)

        ctk.CTkButton(btn_box, text="🔄", width=38, height=38,
                      fg_color="#444", hover_color="#555",
                      command=self.refresh_data).pack(side="left")

        self.search_var = ctk.StringVar()
        search_frame = ctk.CTkFrame(top_inner, fg_color="#252525",
                                     corner_radius=8)
        search_frame.pack(side="left", padx=20)

        ctk.CTkLabel(search_frame, text="🔍", width=25,
                     font=("Segoe UI", 13)).pack(side="left", padx=(8, 0))

        search_entry = ctk.CTkEntry(search_frame,
                                     textvariable=self.search_var,
                                     placeholder_text="Szukaj zawodnika...",
                                     width=200, height=32,
                                     fg_color="transparent",
                                     border_width=0)
        search_entry.pack(side="left", padx=5)
        self.search_timer = None
        self.search_var.trace("w", self.on_search)

        self.count_label = ctk.CTkLabel(top_inner, text="",
                                         font=("Segoe UI", 11),
                                         text_color=COLORS["text_dim"])
        self.count_label.pack(side="left", padx=10)

        # ── SCROLL ──
        self.scroll_area = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_area.pack(fill="both", expand=True, padx=20, pady=(0, 5))

        # ── PAGINACJA ──
        pagination = ctk.CTkFrame(self, fg_color=COLORS["card_bg"],
                                   corner_radius=12, height=50)
        pagination.pack(fill="x", padx=20, pady=(5, 10))
        pagination.pack_propagate(False)

        pag_inner = ctk.CTkFrame(pagination, fg_color="transparent")
        pag_inner.pack(expand=True)

        self.prev_btn = ctk.CTkButton(pag_inner, text="‹ Poprzednie",
                                       width=110, height=32,
                                       fg_color="#333", hover_color="#444",
                                       command=self.prev_page)
        self.prev_btn.pack(side="left", padx=10)

        self.page_label = ctk.CTkLabel(pag_inner, text="Strona 1",
                                        font=("Segoe UI", 12, "bold"),
                                        width=100)
        self.page_label.pack(side="left")

        self.info_label = ctk.CTkLabel(pag_inner, text="",
                                        text_color="gray",
                                        font=("Segoe UI", 10))
        self.info_label.pack(side="left", padx=10)

        self.next_btn = ctk.CTkButton(pag_inner, text="Następne ›",
                                       width=110, height=32,
                                       fg_color="#333", hover_color="#444",
                                       command=self.next_page)
        self.next_btn.pack(side="left", padx=10)

        self.load_data()

    def load_data(self):
        for widget in self.scroll_area.winfo_children():
            widget.destroy()

        ctk.CTkLabel(self.scroll_area, text="⏳ Ładowanie...",
                     text_color="gray").pack(pady=20)

        def fetch():
            from cache_manager import cache
            # KADRA AKTYWNEJ DRUŻYNY (nie cały klub). Przy 'Wszystkie
            # drużyny' get_players() zwraca całą kadrę klubu.
            self.all_players_data = cache.get_players()
            self.after(0, self.display_players)

        threading.Thread(target=fetch, daemon=True).start()

    def display_players(self):
        for widget in self.scroll_area.winfo_children():
            widget.destroy()

        all_players = self.all_players_data
        if not all_players:
            self.count_label.configure(text="0 zawodników")
            return

        position_priority = {
            'BR': 1, 'GK': 1,
            'LO': 2, 'LB': 2, 'ŚO': 3, 'CB': 3, 'LŚO': 3, 'PŚO': 3,
            'PO': 4, 'RB': 4,
            'DP': 5, 'DM': 5, 'CDM': 5, 'LDP': 5, 'PDP': 5,
            'ŚP': 6, 'CM': 6, 'LŚP': 6, 'PŚP': 6,
            'OP': 7, 'CAM': 7, 'ŚPO': 7, 'LOP': 7, 'POP': 7,
            'LS': 8, 'LW': 8, 'LP': 8, 'LM': 8, 'LN': 8,
            'PS': 9, 'RW': 9, 'PP': 9, 'RM': 9, 'PN': 9,
            'N': 10, 'ST': 10, 'CF': 10, 'ŚN': 10
        }

        def get_sort_key(x):
            pos = str(x.get('primary_position') or '').strip().upper()
            if not pos or pos == 'NONE':
                return (99, x.get('full_name', ''))
            return (position_priority.get(pos, 99),
                    x.get('jersey_number') or 999)

        all_players.sort(key=get_sort_key)

        query = self.search_var.get().lower().strip()
        selected_club = str(database.CURRENT_CLUB).strip()

        filtered = []
        for p in all_players:
            if selected_club != "WSZYSCY" and \
               str(p.get('club_name', '')).strip() != selected_club:
                continue
            if query:
                full_search = (f"{p.get('full_name', '')} "
                               f"{p.get('primary_position', '')} "
                               f"{p.get('jersey_number', '')}").lower()
                if query not in full_search:
                    continue
            filtered.append(p)

        self.count_label.configure(text=f"{len(filtered)} zawodników")

        total = len(filtered)
        total_pages = max(1, (total + self.per_page - 1) // self.per_page)

        if self.page >= total_pages:
            self.page = total_pages - 1
        if self.page < 0:
            self.page = 0

        start_idx    = self.page * self.per_page
        end_idx      = start_idx + self.per_page
        page_players = filtered[start_idx:end_idx]

        # Renderuj WSZYSTKIE karty naraz (max 10 na stronę)
        try:
            from image_manager import img_manager
            ids  = [p.get('id') for p in page_players]
            urls = [p.get('photo_url') for p in page_players]
            img_manager.preload_images(ids, urls, size=(70, 70))
        except Exception:
            pass

        # Render batch - szybciej i większymi porcjami
        self.players_to_render = page_players
        self.render_index = 0
        self.after(1, self.render_batch)

        # Przewiń do góry
        try:
            self.scroll_area._parent_canvas.yview_moveto(0)
        except Exception:
            pass

        self.page_label.configure(
            text=f"Strona {self.page + 1} z {total_pages}")
        self.info_label.configure(
            text=f"{start_idx + 1}–{min(end_idx, total)} z {total}")

        self.prev_btn.configure(
            state="normal" if self.page > 0 else "disabled")
        self.next_btn.configure(
            state="normal" if self.page < total_pages - 1 else "disabled")
    
    def render_batch(self):
        if not self.winfo_exists():
            return

        batch_size = 5
        end_index = min(self.render_index + batch_size,
                        len(self.players_to_render))

        for i in range(self.render_index, end_index):
            p = self.players_to_render[i]
            try:
                PlayerCard(
                    self.scroll_area,
                    player_data=p,
                    on_click=self.on_open_profile,
                    on_team=self.open_team_dialog
                ).pack(fill="x", pady=4)
            except Exception:
                pass

        self.render_index = end_index

        if self.render_index < len(self.players_to_render):
            self.after(1, self.render_batch)


    def next_page(self):
        self.page += 1
        self.display_players()

    def prev_page(self):
        self.page -= 1
        self.display_players()

    def refresh_data(self):
        self.page = 0
        from cache_manager import cache
        cache.invalidate("players")
        cache.invalidate("all_players")
        self.load_data()

    # ------------------------------------------------------------------
    def _update_title(self):
        """Nagłówek zawsze pokazuje, czyjej kadry to jest lista."""
        try:
            self.title_label.configure(
                text=f"👥 Kadra — {teams.scope_label(short_only=True)}")
        except Exception:
            pass

    def on_team_changed(self):
        """Wołane z main.py po zmianie drużyny w przełączniku."""
        self._update_title()
        self.page = 0
        self.refresh_data()

    def open_team_dialog(self, player_data):
        """Szybkie przypisanie zawodnika do drużyn (⚽ na karcie)."""
        try:
            from views.team_assign import TeamAssignDialog
            TeamAssignDialog(self, player_data,
                             on_changed=lambda: self.refresh_data())
        except Exception as e:
            logger.error(f"Nie udało się otworzyć okna drużyn: {e}")
            tk_msgbox.showerror("Błąd", str(e))

    # ------------------------------------------------------------------
    def open_add_dialog(self):
        """
        Dodanie zawodnika. UWAGA: formularz jest przewijany, a przyciski
        ZAPISZ/Anuluj są przyklejone do dołu - wcześniej przycisk zapisywania
        wypadał poza okno i był niewidoczny.
        """
        dialog = ctk.CTkToplevel(self)
        dialog.title("Dodaj Zawodnika")
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()

        height = min(700, dialog.winfo_screenheight() - 80)
        dialog.geometry(f"480x{height}")
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 480) // 2
        y = (dialog.winfo_screenheight() - height) // 2
        dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(dialog, text="👤 Nowy Zawodnik",
                     font=("Segoe UI", 20, "bold"),
                     text_color=COLORS["accent"]).pack(pady=(18, 6))

        # --- przewijany formularz ---
        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20)

        form = ctk.CTkFrame(scroll, fg_color=COLORS["card_bg"],
                            corner_radius=15)
        form.pack(fill="both", expand=True)

        inner = ctk.CTkFrame(form, fg_color="transparent")
        inner.pack(fill="x", padx=25, pady=(16, 10))

        def add_field(label, placeholder):
            ctk.CTkLabel(inner, text=label, font=("Segoe UI", 11, "bold"),
                         text_color=COLORS["text_dim"]).pack(anchor="w",
                                                              pady=(8, 2))
            e = ctk.CTkEntry(inner, placeholder_text=placeholder, height=38)
            e.pack(fill="x")
            return e

        self.entry_name   = add_field("Imię i Nazwisko", "np. Jan Kowalski")
        self.entry_number = add_field("Numer koszulki", "np. 10")
        self.entry_age    = add_field("Wiek", "np. 22")

        ctk.CTkLabel(inner, text="Pozycja", font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w",
                                                          pady=(8, 2))
        positions = ['BR', 'LO', 'ŚO', 'PO', 'DP', 'ŚP', 'OP', 'LS', 'PS', 'N']
        self.option_pos = ctk.CTkOptionMenu(inner, values=positions, height=38)
        self.option_pos.pack(fill="x")
        self.option_pos.set("Wybierz pozycję")

        ctk.CTkLabel(inner, text="Klub", font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w",
                                                          pady=(8, 2))
        club_e = ctk.CTkEntry(inner, height=38)
        club_e.insert(0, database.CURRENT_CLUB)
        club_e.configure(state="disabled")
        club_e.pack(fill="x")

        # --- DRUŻYNY ---
        # TYLKO drużyny, do których zalogowany trener ma dostęp.
        # Kierownik widzi wszystkie; trener z jedną drużyną (np. jan@klub.pl)
        # NIE może w polubić nowego gracza do cudzej kadry.
        active_teams = teams.visible_teams(include_all=False)
        ctk.CTkLabel(inner, text="Drużyna główna",
                     font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w",
                                                          pady=(14, 2))

        codes = [t["code"] for t in active_teams]
        cur = teams.get_current_team()
        default = cur if cur in codes else (codes[0] if codes else None)
        # Interfejs pokazuje SKRÓT drużyny ('A1', 'AI', 'II'),
        # a NIE surowy kod z bazy ('1', '2', 'I').
        self._team_by_label = {teams.team_label(c): c for c in codes}

        self.team_choice = {}
        if codes:
            self.option_team = ctk.CTkOptionMenu(
                inner, values=list(self._team_by_label.keys()), height=38,
                command=lambda _=None: self._sync_extra_teams())
            self.option_team.pack(fill="x")
            self.option_team.set(teams.team_label(default))
            self.team_choice[default] = True

            ctk.CTkLabel(inner, text="Dodaj też do (opcjonalnie)",
                         font=("Segoe UI", 11, "bold"),
                         text_color=COLORS["text_dim"]).pack(anchor="w",
                                                              pady=(12, 2))
            extra_frame = ctk.CTkFrame(inner, fg_color="transparent")
            extra_frame.pack(fill="x")
            for i, t in enumerate(active_teams):
                var = ctk.BooleanVar(value=False)
                ctk.CTkCheckBox(
                    extra_frame,
                    text=f"{t['name']} ({t['code']})",
                    variable=var, font=("Segoe UI", 12),
                    text_color="#cccccc",
                    command=lambda c=t["code"], v=var:
                        self._toggle_extra_team(c, v),
                ).grid(row=i // 2, column=i % 2, sticky="w", padx=6, pady=3)
                self.team_choice[t["code"]] = var
        else:
            ctk.CTkLabel(inner, text="⚠️ W bazie nie ma żadnej drużyny — "
                                     "najpierw dodaj drużynę (⚙️ Drużyny).",
                         text_color=COLORS["danger"], wraplength=380,
                         justify="left").pack(anchor="w", pady=8)

        # --- STICKY FOOTER ---
        footer = ctk.CTkFrame(dialog, fg_color=COLORS["bg_dark"])
        footer.pack(fill="x", padx=20, pady=(8, 16), side="bottom")

        status = ctk.CTkLabel(footer, text="", font=("Segoe UI", 11),
                              text_color=COLORS["text_dim"], anchor="w")
        status.pack(fill="x", pady=(0, 6))

        btn_frame = ctk.CTkFrame(footer, fg_color="transparent")
        btn_frame.pack(fill="x")

        ctk.CTkButton(btn_frame, text="Anuluj", width=110, height=44,
                      fg_color="#555", hover_color="#444",
                      command=dialog.destroy).pack(side="left")

        save_btn = ctk.CTkButton(
            btn_frame, text="💾 ZAPISZ ZAWODNIKA", width=230, height=44,
            fg_color=COLORS["success"], hover_color="#27ae60",
            font=("Segoe UI", 14, "bold"), command=lambda: save())
        save_btn.pack(side="right")

        # Enter w dowolnym polu = zapis
        dialog.bind("<Return>", lambda _e: save())

        def chosen_teams():
            """Główna drużyna + zaznaczone dodatkowe (etykieta -> kod)."""
            label = self.option_team.get() if codes else None
            primary = self._team_by_label.get(label)
            out = [primary] if primary else []
            for code, var in self.team_choice.items():
                if code == primary:
                    continue
                if isinstance(var, ctk.BooleanVar):
                    if var.get():
                        out.append(code)
                elif var:
                    out.append(code)
            return out

        def _on_success():
            tk_msgbox.showinfo("Sukces", "Dodano zawodnika!")
            dialog.destroy()
            self.load_data()

        def _on_error(err_text):
            status.configure(text=f"❌ {err_text[:90]}",
                             text_color=COLORS["danger"])
            save_btn.configure(state="normal", text="💾 ZAPISZ ZAWODNIKA")

        def save():
            name = self.entry_name.get().strip()
            if not name:
                status.configure(text="❌ Podaj imię i nazwisko!",
                                 text_color=COLORS["danger"])
                return

            try:
                nr  = int(self.entry_number.get()) \
                    if self.entry_number.get().isdigit() else None
                age = int(self.entry_age.get()) \
                    if self.entry_age.get().isdigit() else None
                pos = self.option_pos.get()
                if pos == "Wybierz pozycję":
                    pos = None
            except Exception as e:
                status.configure(text=f"❌ Sprawdź dane: {e}",
                                 text_color=COLORS["danger"])
                return

            wanted = chosen_teams()
            primary = wanted[0] if wanted else None

            # Ostatnia linia obrony: wiersz do 'players' (z primary_team_code)
            # powstaje PRZED zapisem terminów, więc sprawdzamy dostęp
            # do każdej wybranej drużyny zanim cokolwiek zapiszemy.
            access_ok, access_msg = teams.guard_teams(wanted, "dodać zawodnika")
            if not access_ok:
                status.configure(text=access_msg, text_color=COLORS["danger"])
                save_btn.configure(state="normal", text="💾 ZAPISZ ZAWODNIKA")
                return
            new_data = {
                "full_name":        name,
                "jersey_number":    nr,
                "age":              age,
                "primary_position": pos,
                "club_name":        database.CURRENT_CLUB,
                "join_date":        datetime.date.today().isoformat(),
                "primary_team_code": primary,
            }

            save_btn.configure(state="disabled", text="⏳ Zapisuję...")
            status.configure(text="", text_color=COLORS["text_dim"])

            def save_thread():
                try:
                    res = supabase.table('players').insert(new_data).execute()
                    rows = res.data or []
                    pid = rows[0].get('id') if rows else None

                    if pid is None:      # fallback (gdy baza nie zwróci wiersza)
                        q = (supabase.table('players').select('id')
                             .eq('full_name', name)
                             .order('created_at', desc=True).limit(1)
                             .execute())
                        pid = q.data[0]['id'] if q.data else None

                    if pid and wanted:
                        teams.set_player_memberships(pid, wanted, primary)

                    database.log_activity(f"dodał zawodnika: {name}")
                    from cache_manager import cache
                    cache.invalidate_players()
                    dialog.after(0, _on_success)
                except Exception as e:
                    err = str(e)
                    logger.error(f"Nie udało się dodać zawodnika: {err}")
                    dialog.after(0, lambda: _on_error(err))

            threading.Thread(target=save_thread, daemon=True).start()

    # ------------------------------------------------------------------
    def _primary_code(self):
        """Kod drużyny wybranej jako główna (etykieta -> kod)."""
        if not hasattr(self, "option_team"):
            return None
        return self._team_by_label.get(self.option_team.get())

    def _toggle_extra_team(self, code, var):
        """Drużyny głównej nie da się odznaczyć - zostaje w kadrze."""
        primary = self._primary_code()
        if code == primary and not var.get():
            var.set(True)

    def _sync_extra_teams(self):
        """Zmiana drużyny głównej czyści jej checkbox 'dodaj też do'."""
        primary = self._primary_code()
        var = self.team_choice.get(primary)
        if isinstance(var, ctk.BooleanVar):
            var.set(False)

    def on_search(self, *args):
        if self.search_timer:
            self.after_cancel(self.search_timer)
        self.search_timer = self.after(300, self.display_players)

def update_photo(self, img):
        try:
            if self.winfo_exists() and self.photo_label.winfo_exists():
                self.photo_label.configure(image=img)
                self.photo_label.image = img  # trzymaj referencję
        except Exception:
            pass