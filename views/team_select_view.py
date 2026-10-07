"""
views/team_select_view.py - ekran wyboru drużyny.

Pokazywany:
  * po zalogowaniu, gdy trener ma więcej niż jedną drużynę,
  * po kliknięciu "🔄 Zmień drużynę" w sidebarze.

Nie wylogowuje - zmiana drużyny to zmiana kontekstu, nie sesji.
Widoczne są TYLKO drużyny, do których trener ma dostęp
(user_permissions.team_codes), więc nowy użytkownik z dostępem do jednej
drużyny z trzech w ogóle nie zobaczy pozostałych.
"""
import customtkinter as ctk

import teams
from logger import logger


class TeamSelectView(ctk.CTkFrame):
    """Kafelki drużyn do wyboru."""

    def __init__(self, master, on_choose, on_cancel=None,
                 heading="Wybierz drużynę",
                 subtitle="Na której chcesz dziś pracować?"):
        super().__init__(master, fg_color="transparent")
        self.on_choose = on_choose
        self.on_cancel = on_cancel
        self._cards = []

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=40, pady=(50, 6))

        ctk.CTkLabel(top, text=f"⚽  {heading}",
                     font=("Segoe UI", 30, "bold"),
                     text_color="#3b8ed0").pack(anchor="w")

        ctk.CTkLabel(top, text=subtitle, font=("Segoe UI", 14),
                     text_color="#888888").pack(anchor="w", pady=(4, 0))

        self.grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_frame.pack(fill="both", expand=True, padx=40, pady=(20, 10))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=40, pady=(0, 40))
        if on_cancel:
            ctk.CTkButton(footer, text="↩ Wróć bez zmian", width=200,
                          height=42, fg_color="#3a3a3a", hover_color="#2a2a2a",
                          command=on_cancel).pack(side="left")

        self._render()

    # ------------------------------------------------------------------
    def _render(self):
        visible = [t for t in teams.visible_teams(include_all=False)
                   if t.get("is_active", True)]

        if not visible:
            ctk.CTkLabel(
                self.grid_frame,
                text="⚠️  Twoje konto nie ma przydzielonej drużyny.\n\n"
                     "Poproś administratora o wpisanie Twojego adresu "
                     "w tabeli user_permissions (kolumna team_codes).",
                font=("Segoe UI", 14), text_color="#e67e22",
                justify="left").pack(pady=40)
            return

        cols = 3 if len(visible) > 2 else len(visible)
        for i, t in enumerate(visible):
            self.grid_frame.grid_columnconfigure(i % cols, weight=1)
            card = self._make_card(t)
            card.grid(row=i // cols, column=i % cols, padx=12, pady=12,
                      sticky="nsew")
            self._cards.append(card)

    # ------------------------------------------------------------------
    def _make_card(self, team):
        code = team["code"]
        current = (code == teams.get_current_team())
        count = len(teams.get_team_player_ids(code, force_refresh=False))

        card = ctk.CTkFrame(self.grid_frame, fg_color="#1e1e1e",
                            corner_radius=14,
                            border_width=3 if current else 1,
                            border_color=team.get("color", "#3b8ed0")
                            if current else "#2a2a2a")
        card.configure(cursor="hand2")

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(18, 0))

        ctk.CTkLabel(top, text=teams.team_short(code),
                     font=("Segoe UI", 30, "bold"),
                     text_color=team.get("color", "#3b8ed0")).pack(side="left")

        if current:
            ctk.CTkLabel(top, text="TWOJA DRUŻYNA", font=("Segoe UI", 10,
                         "bold"), text_color="#2ecc71").pack(side="right")

        ctk.CTkLabel(card, text=team.get("name", code), font=("Segoe UI", 14),
                     text_color="#dddddd", wraplength=220,
                     justify="left").pack(anchor="w", padx=18, pady=(6, 0))

        ctk.CTkLabel(card,
                     text=f"{count} zawodników w kadrze"
                          if count else "kadra pusta",
                     font=("Segoe UI", 11), text_color="#777777"
                     ).pack(anchor="w", padx=18)

        ctk.CTkButton(card, text="WBIERZ", height=38,
                      font=("Segoe UI", 13, "bold"),
                      fg_color="#3b8ed0" if current else "#2a5f8a",
                      hover_color="#2a6ea6",
                      command=lambda c=code: self._choose(c)
                      ).pack(fill="x", padx=18, pady=(16, 18))

        for w in (card, top):
            w.bind("<Button-1>", lambda _e, c=code: self._choose(c))
        return card

    # ------------------------------------------------------------------
    def _choose(self, code):
        try:
            self.on_choose(code)
        except Exception as e:
            logger.error(f"Wybór drużyny nie powiódł się: {e}")