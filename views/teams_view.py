"""views/teams_view.py - zarządzanie drużynami (kody, nazwy, kolory).

Okno dostępne z sidebara dla trenerów z uprawnieniem 'squad'.
Ustawia kolejność i kolor drużyny, dodaje nowe, archiwizuje stare.
"""
import customtkinter as ctk
import tkinter.messagebox as msgbox

import teams
from logger import logger

COLOR_PRESETS = ["#3b8ed0", "#2ecc71", "#e67e22", "#e74c3c",
                 "#9b59b6", "#1abc9c", "#f1c40f", "#888888"]


class TeamsManager(ctk.CTkToplevel):
    """Modal: lista drużyn + dodawanie/edycja."""

    def __init__(self, master, on_changed=None):
        super().__init__(master)
        self.title("⚙️ Drużyny klubu")
        self.geometry("860x720")
        self.attributes("-topmost", True)
        self.transient(master)
        try:
            self.grab_set()
        except Exception:
            pass
        self.on_changed = on_changed

        header = ctk.CTkLabel(
            self, text="⚙️  DRUŻYNY KLUBU",
            font=("Segoe UI", 22, "bold"), text_color="#3b8ed0")
        header.pack(anchor="w", padx=20, pady=(20, 2))

        ctk.CTkLabel(
            self,
            text="Kod drużyny (np. I, II, AKD) jest kluczem w bazie - "
                 "zmiana kodu rozspaja dotychczasowe powiązania.",
            font=("Segoe UI", 11), text_color="#888888", wraplength=680,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 12))

        # --- lista ---
        self.list_frame = ctk.CTkScrollableFrame(self, height=340)
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        # --- dodawanie ---
        add = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=12)
        add.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkLabel(add, text="Dodaj drużynę", font=("Segoe UI", 13, "bold")) \
            .pack(anchor="w", padx=15, pady=(12, 6))

        row = ctk.CTkFrame(add, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=(0, 12))

        self.code_entry = ctk.CTkEntry(row, width=90, placeholder_text="KOD")
        self.code_entry.pack(side="left", padx=(0, 8))

        self.name_entry = ctk.CTkEntry(row, width=240, placeholder_text="Pełna nazwa")
        self.name_entry.pack(side="left", padx=(0, 8))

        self.short_entry = ctk.CTkEntry(row, width=80, placeholder_text="Skrót")
        self.short_entry.pack(side="left", padx=(0, 8))

        self.color_var = ctk.StringVar(value=COLOR_PRESETS[0])
        ctk.CTkOptionMenu(row, variable=self.color_var,
                          values=COLOR_PRESETS, width=110).pack(side="left", padx=(0, 8))

        ctk.CTkButton(row, text="➕ Dodaj", width=110, height=36,
                      fg_color="#2ecc71", hover_color="#27ae60",
                      command=self._add).pack(side="left")

        self._render()

    # ------------------------------------------------------------------
    def _render(self):
        """Lista drużyn z EDYCJĄ W MIEJSCU (bez wyskakujących dialogów -
        wcześniej okno zmiany nazwy ginęło za oknem głównym)."""
        for w in self.list_frame.winfo_children():
            w.destroy()

        # Tylko drużyny, do których ten trener ma dostęp. Kierownik widzi
        # wszystkie; trener z jedną drużyną NIE może rename'ować, archiwizować
        # ani usuwać cudzych drużyn.
        data = teams.visible_teams(include_all=False)
        if not data:
            ctk.CTkLabel(self.list_frame, text="Brak drużyn w bazie.",
                         text_color="gray").pack(pady=30)
            return

        for t in sorted(data, key=lambda x: x.get('sort_order', 999)):
            self._render_row(t)

    # ------------------------------------------------------------------
    def _render_row(self, t):
        code = t.get('code')
        row = ctk.CTkFrame(self.list_frame, fg_color="#1e1e1e",
                           corner_radius=10)
        row.pack(fill="x", pady=4, padx=4)

        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True, padx=(12, 6), pady=8)

        head = ctk.CTkFrame(left, fg_color="transparent")
        head.pack(fill="x")

        ctk.CTkLabel(head, text="●", font=("Segoe UI", 18, "bold"),
                     text_color=t.get('color', '#3b8ed0'),
                     width=22).pack(side="left")

        ctk.CTkLabel(head, text="Kod:", font=("Segoe UI", 11),
                     text_color="#888888").pack(side="left", padx=(2, 4))
        ctk.CTkLabel(head, text=f"{code}", font=("Segoe UI", 12, "bold"),
                     text_color="#cccccc").pack(side="left")

        if not t.get('is_active', True):
            ctk.CTkLabel(head, text="  ARCHIWUM", font=("Segoe UI", 10,
                         "bold"), text_color="#e67e22").pack(side="left",
                                                            padx=8)

        # nazwa - edytowalna w miejscu
        name_var = ctk.StringVar(value=t.get('name', ''))
        ctk.CTkEntry(left, textvariable=name_var, height=32,
                     font=("Segoe UI", 13, "bold")).pack(fill="x", pady=(6, 0))

        row2 = ctk.CTkFrame(left, fg_color="transparent")
        row2.pack(fill="x", pady=(4, 0))

        ctk.CTkLabel(row2, text="Skrót:", font=("Segoe UI", 11),
                     text_color="#888888").pack(side="left")
        short_var = ctk.StringVar(value=t.get('short_name', ''))
        ctk.CTkEntry(row2, textvariable=short_var, width=80, height=28) \
            .pack(side="left", padx=6)

        color_var = ctk.StringVar(value=t.get('color', COLOR_PRESETS[0]))
        ctk.CTkOptionMenu(row2, variable=color_var, values=COLOR_PRESETS,
                          width=110, height=28).pack(side="left", padx=6)

        ctk.CTkButton(row2, text="💾 ZAPISZ", width=110, height=28,
                      fg_color="#2ecc71", hover_color="#27ae60",
                      font=("Segoe UI", 11, "bold"),
                      command=lambda tv=name_var, sv=short_var, cv=color_var,
                                     c=code: self._save_team(c, tv.get(),
                                                             sv.get(),
                                                             cv.get())
                      ).pack(side="left", padx=6)

        ctk.CTkButton(
            row, text="🗑 Usuń", width=100, height=34,
            fg_color="transparent", border_width=1,
            border_color="#e74c3c", text_color="#e74c3c",
            hover_color="#3a1512",
            command=lambda tt=t: self._delete(tt),
        ).pack(side="right", padx=(0, 6))

        if t.get('is_active', True):
            ctk.CTkButton(
                row, text="⏸ Archiwizuj", width=120, height=34,
                fg_color="transparent", border_width=1,
                border_color="#e67e22", text_color="#e67e22",
                command=lambda tt=t: self._toggle(tt, False),
            ).pack(side="right", padx=(0, 6))
        else:
            ctk.CTkButton(
                row, text="▶ Przywróć", width=120, height=34,
                fg_color="transparent", border_width=1,
                border_color="#2ecc71", text_color="#2ecc71",
                command=lambda tt=t: self._toggle(tt, True),
            ).pack(side="right", padx=(0, 6))

    # ------------------------------------------------------------------
    def _save_team(self, code, name, short, color):
        """Zapis nazwy/skrótu/koloru drużyny."""
        name = (name or "").strip()
        short = (short or "").strip().upper() or code
        if not name:
            msgbox.showerror("Błąd", "Nazwa drużyny nie może być pusta.",
                             parent=self)
            return
        ok, msg = teams.guard_teams([code], "edytować drużynę")
        if not ok:
            msgbox.showerror("Brak dostępu", msg, parent=self)
            return
        try:
            teams._supabase().table("teams").update({
                "name": name, "short_name": short, "color": color
            }).eq("code", code).execute()
            logger.info(f"Zapisano drużynę {code}: {name}")
            teams.get_teams(force_refresh=True)
            self._render()
            if self.on_changed:
                self.on_changed()
        except Exception as e:
            logger.error(f"Nie udało się zapisać drużyny: {e}")
            msgbox.showerror("Błąd", f"Nie udało się zapisać:\n{e}",
                             parent=self)

    def _add(self):
        # Tworzenie drużyn to przywilej kierownika - trener z dostępem
        # tylko do jednej drużyny nie zakłada nowych.
        if not teams.can_edit_team(teams.ALL_TEAMS):
            msgbox.showerror(
                "Brak dostępu",
                "Tylko kierownik może zakładać nowe drużyny.",
                parent=self)
            return
        code = self.code_entry.get().strip().upper()
        name = self.name_entry.get().strip()
        short = self.short_entry.get().strip().upper() or code

        if not code or not name:
            msgbox.showerror("Błąd", "Podaj kod i nazwę drużyny.", parent=self)
            return
        if teams.get_team(code) is not None:
            msgbox.showerror("Błąd", f"Drużyna o kodzie '{code}' już istnieje.",
                             parent=self)
            return

        try:
            teams._supabase().table("teams").insert({
                "code": code,
                "name": name,
                "short_name": short,
                "color": self.color_var.get(),
                "sort_order": len(teams.get_teams()) + 1,
                "is_active": True,
            }).execute()
            logger.info(f"Dodano drużynę {code} ({name})")
            teams.get_teams(force_refresh=True)
            self.code_entry.delete(0, "end")
            self.name_entry.delete(0, "end")
            self.short_entry.delete(0, "end")
            self._render()
            if self.on_changed:
                self.on_changed()
        except Exception as e:
            logger.error(f"Nie udało się dodać drużyny: {e}")
            msgbox.showerror("Błąd", f"Nie udało się dodać drużyny:\n{e}",
                             parent=self)

    def _rename(self, team):
        """Zapasowa ścieżka zmiany nazwy (gdyby ktoś chciał z kodu)."""
        new_name = team.get('name', '')
        try:
            new_name = ctk.CTkInputDialog(
                text="Nowa nazwa drużyny:", title="Zmiana nazwy",
                initialvalue=new_name).get_input()[0]
        except Exception:
            return
        if new_name:
            self._save_team(team['code'], new_name,
                            team.get('short_name'), team.get('color'))

    def _delete(self, team):
        """
        Usunięcie drużyny z potwierdzeniem. Pokazuje, ilu graczy zostanie
        odjętych, bo to jedyna operacja, która ich rusza.
        """
        code = team.get('code')
        name = team.get('name', code)

        ok, msg = teams.guard_teams([code], "usunąć drużynę")
        if not ok:
            msgbox.showerror("Brak dostępu", msg, parent=self)
            return

        others = [t for t in teams.get_teams()
                  if t.get('is_active', True) and t.get('code') != code]
        if not others:
            msgbox.showerror(
                "Nie można usunąć",
                "To jest ostatnia aktywna drużyna.\n"
                "Najpierw dodaj kolejną (np. Drużynę II), potem usuń tę.",
                parent=self)
            return

        members = []
        for t in teams._all_terms(code):
            if not t.get("left_on") and t.get("player_id") not in members:
                members.append(t.get("player_id"))
        n = len(members)

        if not msgbox.askyesno(
                "Potwierdź usunięcie",
                f"Usunąć drużynę:\n\n    {name}  (kod: {code})\n\n"
                + (f"• {n} graczy przestanie do niej należeć\n"
                   f"• przeniosą się do: {teams.team_label(others[0]['code'])}"
                   f" — {others[0]['name']}\n"
                   if n else "• nikt obecnie do niej nie należy\n")
                + "• historia terminów kadry zostanie zachowana\n"
                  "• terminarze, wpłaty i skład tej drużyny zostaną w bazie\n\n"
                  "Tej operacji nie da się cofnąć.",
                icon="warning", default="no", parent=self):
            return

        # drugie potwierdzenie: wpisz kod drużyny
        typed = ""
        try:
            typed = ctk.CTkInputDialog(
                text=f"Dla pewności wpisz kod drużyny ({code}):",
                title="Usuń drużynę").get_input()[0]
        except Exception:
            return
        if (typed or "").strip().upper() != str(code).upper():
            msgbox.showwarning("Anulowano",
                               "Kod się nie zgadza — drużyna została.",
                               parent=self)
            return

        ok, msg = teams.delete_team(code)
        if not ok:
            msgbox.showerror("Nie udało się", msg, parent=self)
            return
        self._render()
        if self.on_changed:
            self.on_changed()
        msgbox.showinfo("Gotowe", msg, parent=self)

    def _toggle(self, team, active):
        ok, msg = teams.guard_teams([team.get('code')],
                                    "archiwizować drużynę")
        if not ok:
            msgbox.showerror("Brak dostępu", msg, parent=self)
            return
        try:
            teams._supabase().table("teams").update({"is_active": active}) \
                .eq("code", team['code']).execute()
            teams.get_teams(force_refresh=True)
            self._render()
            if self.on_changed:
                self.on_changed()
        except Exception as e:
            msgbox.showerror("Błąd", str(e), parent=self)