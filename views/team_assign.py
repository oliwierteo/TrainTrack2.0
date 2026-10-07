"""
views/team_assign.py - szybkie przypisywanie zawodnika do drużyn.

Jeden gracz może być w kilku drużynach naraz ("tu i tu"), a w każdej ma
własny termin kadry. Ten modal obsługuje wszystkie ruchy:
  * dodanie do kolejnej drużynyy bez ruszania poprzednich,
  * przeniesienie (zamyka stary termin, zapisuje historię),
  * wyprowadzenie z kadry (zostaje w klubie, znika tylko z drużyny),
  * wskazanie drużyny głównej (ta, która wgrywa się wszędzie).
"""
import customtkinter as ctk
import tkinter.messagebox as msgbox

import teams
from logger import logger

BG = "#1a1a1a"
CARD = "#1e1e1e"
FIELD = "#252525"


class TeamAssignDialog(ctk.CTkToplevel):
    """Modal: 'w jakich drużynach jest ten zawodnik'."""

    def __init__(self, master, player, on_changed=None):
        super().__init__(master)
        self.player = player or {}
        self.player_id = self.player.get("id")
        self.on_changed = on_changed
        self.rows = {}          # kod -> {'var': BooleanVar, 'cb': widget}
        self._primary = None
        self._busy = False
        self._buttons = []

        self.title("⚽ Drużyny zawodnika")
        self.geometry("560x640")
        self.configure(fg_color=BG)
        self.transient(master)
        try:
            self.grab_set()
        except Exception:
            pass

        self.update_idletasks()
        x = max((self.winfo_screenwidth() - 560) // 2, 0)
        y = max((self.winfo_screenheight() - 640) // 2, 0)
        self.geometry(f"+{x}+{y}")

        self._build()
        self._load_state()

    # ------------------------------------------------------------------
    def _build(self):
        name = self.player.get("full_name", "?")
        ctk.CTkLabel(self, text=f"⚽  Drużyny: {name}",
                     font=("Segoe UI", 20, "bold"),
                     text_color="#3b8ed0").pack(anchor="w", padx=22,
                                                pady=(20, 2))
        self.summary = ctk.CTkLabel(self, text="", font=("Segoe UI", 12),
                                    text_color="#888888", justify="left",
                                    anchor="w", wraplength=510)
        self.summary.pack(fill="x", padx=22, pady=(0, 12))

        # --- szybkie akcje dla aktywnej drużyny ---
        quick = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        quick.pack(fill="x", padx=22, pady=(0, 12))

        ctk.CTkLabel(quick, text="Aktywna drużyna (z przełącznika):",
                     font=("Segoe UI", 11, "bold"),
                     text_color="#888888").pack(anchor="w", padx=14,
                                                 pady=(12, 6))

        self.quick_label = ctk.CTkLabel(quick, text="—", font=("Segoe UI", 14,
                                        "bold"), text_color="#2ecc71")
        self.quick_label.pack(anchor="w", padx=14)

        btn_row = ctk.CTkFrame(quick, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(8, 14))

        self.btn_add = ctk.CTkButton(
            btn_row, text="➕ Dodaj tu", width=150, height=36,
            fg_color="#2ecc71", hover_color="#27ae60",
            font=("Segoe UI", 12, "bold"), command=self._quick_add)
        self.btn_add.pack(side="left", padx=(0, 8))

        self.btn_move = ctk.CTkButton(
            btn_row, text="➡️ Przenieś tu", width=150, height=36,
            fg_color="#e67e22", hover_color="#d35400",
            font=("Segoe UI", 12, "bold"), command=self._quick_move)
        self.btn_move.pack(side="left", padx=(0, 8))

        self.btn_remove = ctk.CTkButton(
            btn_row, text="➖ Usuń z tu", width=150, height=36,
            fg_color="#e74c3c", hover_color="#c0392b",
            font=("Segoe UI", 12, "bold"), command=self._quick_remove)
        self.btn_remove.pack(side="left")

        # --- lista drużyn ---
        ctk.CTkLabel(self, text="Zaznacz wszystkie drużyny, w których "
                                "gracz ma grać:", font=("Segoe UI", 12,
                                "bold"), text_color="#cccccc",
                     anchor="w").pack(anchor="w", padx=22, pady=(0, 6))

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=FIELD,
                                                 corner_radius=10, height=200)
        self.list_frame.pack(fill="both", expand=True, padx=22)

        # --- przyciski ---
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=22, pady=18)

        self.btn_cancel = ctk.CTkButton(
            footer, text="Anuluj", width=120, height=42,
            fg_color="#555", hover_color="#444",
            command=self.destroy)
        self.btn_cancel.pack(side="left")

        self.btn_save = ctk.CTkButton(
            footer, text="💾 ZAPISZ ZMIANY", width=220, height=42,
            fg_color="#3b8ed0", hover_color="#2a6ea6",
            font=("Segoe UI", 13, "bold"), command=self._save)
        self.btn_save.pack(side="right")
        self._buttons = [self.btn_cancel, self.btn_save,
                         self.btn_add, self.btn_move, self.btn_remove]

    # ------------------------------------------------------------------
    def _load_state(self):
        """Wczytuje aktualne drużyny gracza i rysuje listę."""
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.rows = {}

        # Tylko drużyny, do których ten trener ma dostęp (fail-closed).
        active = teams.visible_teams(include_all=False)
        if not active:
            ctk.CTkLabel(self.list_frame, text="Brak aktywnych drużyn.",
                         text_color="#888888").pack(pady=20)
            return

        terms = teams.get_active_terms(self.player_id)
        mine = {t["team_code"]: t for t in terms}
        prim = teams.primary_team_of(self.player_id)
        self._primary = prim

        for t in sorted(active, key=lambda x: x.get("sort_order", 999)):
            code = t["code"]
            var = ctk.BooleanVar(value=code in mine)
            row = ctk.CTkFrame(self.list_frame, fg_color=CARD,
                               corner_radius=8)
            row.pack(fill="x", pady=3, padx=4)

            ctk.CTkLabel(row, text="●", width=22,
                         font=("Segoe UI", 16, "bold"),
                         text_color=t.get("color", "#3b8ed0")).pack(side="left",
                                                                    padx=(10, 2))

            cb = ctk.CTkCheckBox(
                row, text=teams.team_label(code, with_name=True),
                variable=var, font=("Segoe UI", 13),
                checkbox_width=22, checkbox_height=22,
                text_color="#dddddd", fg_color="#3b8ed0",
                hover_color="#2a6ea6",
                command=lambda c=code, v=var: self._on_toggle(c, v))
            cb.pack(side="left", pady=8)

            star = ctk.CTkButton(
                row, text="⭐ główna", width=110, height=26,
                fg_color="transparent", border_width=1,
                border_color="#3a3a3a", text_color="#555555",
                font=("Segoe UI", 10),
                command=lambda c=code, v=var: self._set_primary(c, v))
            star.pack(side="right", padx=8)
            self.rows[code] = {"var": var, "cb": cb, "star": star}

        self._refresh_summary()
        current = teams.get_current_team()
        if current == teams.ALL_TEAMS:
            self.quick_label.configure(text="Wszystkie drużyny (★)",
                                       text_color="#e67e22")
            for b in (self.btn_add, self.btn_move, self.btn_remove):
                b.configure(state="disabled")
        else:
            t = teams.get_team(current)
            self.quick_label.configure(text=teams.team_label(current))
            self.btn_move.configure(state="normal")
            self.btn_remove.configure(state="normal")
            self.btn_add.configure(
                state="disabled" if current in mine else "normal")

    # ------------------------------------------------------------------
    def _selected(self):
        return [c for c, r in self.rows.items() if r["var"].get()]

    def _refresh_summary(self):
        sel = self._selected()
        if not sel:
            self.summary.configure(text="⚠️  Zaznacz co najmniej jedną "
                                       "drużynę — inaczej gracz zniknie "
                                       "z całej kadry.")
            return
        names = " + ".join(teams.team_label(c) for c in sel)
        prim = teams.team_label(self._primary) if self._primary else "—"
        self.summary.configure(
            text=f"Po zapisie: {names}\nDrużyna główna: {prim}")

    def _on_toggle(self, code, var):
        # odznaczamy drużynę główną, jeśli właśnie ją włączono/wyłączono
        if self._primary == code and not var.get():
            self._primary = None
        if self._primary is None and var.get():
            self._set_primary(code, var)
            return
        self._refresh_summary()

    def _set_primary(self, code, var):
        if not var.get():
            var.set(True)          # drużyna główna musi być zaznaczona
        self._primary = code
        for c, r in self.rows.items():
            on = (c == code)
            r["star"].configure(
                text_color="#f1c40f" if on else "#555555",
                border_color="#f1c40f" if on else "#3a3a3a",
                font=("Segoe UI", 10, "bold") if on else ("Segoe UI", 10))
        self._refresh_summary()

    # ------------------------------------------------------------------
    def _run(self, fn, *args):
        # Zabezpieczenie: dwa szybkie kliknięcia = dwa zapisy naraz,
        # a druga próba dostaje 409 (uniq_primary_term).
        if getattr(self, "_busy", False):
            return
        self._busy = True
        self._set_buttons("disabled")
        try:
            ok, msg = fn(*args)
        except Exception as e:
            logger.error(f"Błąd zmiany drużyny: {e}")
            ok, msg = False, str(e)
        self._busy = False
        self._set_buttons("normal")
        if not ok:
            msgbox.showerror("Nie udało się", msg, parent=self)
            return
        self._load_state()
        if self.on_changed:
            try:
                self.on_changed()
            except Exception as e:
                logger.warning(f"Callback drużyn: {e}")

    def _set_buttons(self, state):
        for b in getattr(self, "_buttons", []):
            try:
                b.configure(state=state)
            except Exception:
                pass

    def _quick_add(self):
        code = teams.get_current_team()
        if code == teams.ALL_TEAMS:
            return
        var = self.rows.get(code, {}).get("var")
        if var is not None:
            var.set(True)
        self._run(teams.assign_player, self.player_id, code)

    def _quick_move(self):
        code = teams.get_current_team()
        if code == teams.ALL_TEAMS:
            return
        self._run(teams.move_player, self.player_id, code,
                  "szybkie przeniesienie")

    def _quick_remove(self):
        code = teams.get_current_team()
        if code == teams.ALL_TEAMS:
            return
        self._run(teams.remove_player_from_team, self.player_id, code)

    def _save(self):
        sel = self._selected()
        if not sel:
            msgbox.showwarning("Brak drużyny",
                               "Zaznacz co najmniej jedną drużynę.",
                               parent=self)
            return
        primary = self._primary if self._primary in sel else sel[0]
        self._run(teams.set_player_memberships, self.player_id, sel, primary)