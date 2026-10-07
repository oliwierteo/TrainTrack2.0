# views/login_view.py - MODERN LOGIN v2.0

import logging
import threading
import customtkinter as ctk
from PIL import Image
import os
import sys
import tkinter.messagebox as msgbox

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

logger = logging.getLogger(__name__)

SYSTEM_FONT = {
    "darwin": "SF Pro Text",
    "win32":  "Segoe UI",
    "linux":  "Ubuntu",
}.get(sys.platform, "Arial")


class LoginView(ctk.CTkFrame):
    def __init__(self, master, on_login_success):
        super().__init__(master, fg_color="#0f0f0f")
        self.on_login_success = on_login_success

        from database import AuthManager
        self.auth = AuthManager()

        # ── Tło z subtelnymi elementami ──
        # Lewa strona — branding
        left_panel = ctk.CTkFrame(self, fg_color="#0a0a0a", corner_radius=0)
        left_panel.place(relx=0, rely=0, relwidth=0.45, relheight=1)

        left_content = ctk.CTkFrame(left_panel, fg_color="transparent")
        left_content.place(relx=0.5, rely=0.5, anchor="center")

        # Logo duże
        logo_path = resource_path("assets/logo.png")
        if os.path.exists(logo_path):
            try:
                logo_img = ctk.CTkImage(
                    light_image=Image.open(logo_path),
                    dark_image=Image.open(logo_path),
                    size=(160, 160),
                )
                ctk.CTkLabel(left_content, image=logo_img, text="").pack(pady=(0, 20))
            except Exception:
                ctk.CTkLabel(left_content, text="⚽",
                             font=(SYSTEM_FONT, 80)).pack(pady=(0, 20))

        ctk.CTkLabel(
            left_content, text="TrainTrack",
            font=(SYSTEM_FONT, 42, "bold"),
            text_color="#3b8ed0",
        ).pack()

        ctk.CTkLabel(
            left_content, text="System Zarządzania Drużyną",
            font=(SYSTEM_FONT, 14),
            text_color="#555555",
        ).pack(pady=(5, 0))

        # Separator pionowy
        ctk.CTkFrame(
            self, width=1, fg_color="#1a1a1a", corner_radius=0,
        ).place(relx=0.45, rely=0.1, relheight=0.8)

        # ── Prawa strona — formularz ──
        right_panel = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        right_panel.place(relx=0.45, rely=0, relwidth=0.55, relheight=1)

        # Box logowania
        self.login_box = ctk.CTkFrame(
            right_panel, width=380, height=420,
            corner_radius=16, fg_color="#161616",
            border_width=1, border_color="#222222",
        )
        self.login_box.place(relx=0.5, rely=0.5, anchor="center")
        self.login_box.pack_propagate(False)

        # Nagłówek
        ctk.CTkLabel(
            self.login_box, text="Zaloguj się",
            font=(SYSTEM_FONT, 26, "bold"),
            text_color="#e8e8e8",
        ).pack(pady=(40, 5))

        ctk.CTkLabel(
            self.login_box, text="Wprowadź dane konta trenera",
            font=(SYSTEM_FONT, 12),
            text_color="#666666",
        ).pack(pady=(0, 30))

        # Email
        input_frame = ctk.CTkFrame(self.login_box, fg_color="transparent")
        input_frame.pack(fill="x", padx=40)

        ctk.CTkLabel(
            input_frame, text="EMAIL",
            font=(SYSTEM_FONT, 10, "bold"),
            text_color="#555555",
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self.email_entry = ctk.CTkEntry(
            input_frame, height=44, corner_radius=10,
            placeholder_text="trener@klub.pl",
            fg_color="#1e1e1e", border_color="#2a2a2a",
            font=(SYSTEM_FONT, 13),
        )
        self.email_entry.pack(fill="x")

        # Hasło
        ctk.CTkLabel(
            input_frame, text="HASŁO",
            font=(SYSTEM_FONT, 10, "bold"),
            text_color="#555555",
            anchor="w",
        ).pack(fill="x", pady=(15, 4))

        self.pass_entry = ctk.CTkEntry(
            input_frame, height=44, corner_radius=10,
            placeholder_text="••••••••", show="•",
            fg_color="#1e1e1e", border_color="#2a2a2a",
            font=(SYSTEM_FONT, 13),
        )
        self.pass_entry.pack(fill="x")

        # Błąd
        self.error_lbl = ctk.CTkLabel(
            input_frame, text="",
            text_color="#e74c3c",
            font=(SYSTEM_FONT, 11),
            height=20,
        )
        self.error_lbl.pack(fill="x", pady=(8, 0))

        # Przycisk logowania
        self.login_btn = ctk.CTkButton(
            self.login_box, text="ZALOGUJ SIĘ",
            width=300, height=48, corner_radius=10,
            font=(SYSTEM_FONT, 14, "bold"),
            fg_color="#1f6aa5", hover_color="#175a8e",
            command=self.perform_login,
        )
        self.login_btn.pack(pady=(25, 0))

        # Wyczyść dane
        ctk.CTkButton(
            self.login_box, text="Wyczyść dane lokalne",
            fg_color="transparent", text_color="#444444",
            hover_color="#1e1e1e", width=150, height=30,
            font=(SYSTEM_FONT, 11),
            command=self.clear_local_data,
        ).pack(pady=(15, 0))

        # ── Wersja na dole ──
        ctk.CTkLabel(
            right_panel, text="v1.0.0  ·  Tcube",
            font=(SYSTEM_FONT, 10),
            text_color="#333333",
        ).place(relx=0.5, rely=0.95, anchor="center")

        # Enter = login
        self.email_entry.bind("<Return>", lambda e: self.pass_entry.focus())
        self.pass_entry.bind("<Return>", lambda e: self.perform_login())

    def clear_local_data(self):
        if msgbox.askyesno("Czyszczenie",
                           "Usunąć zapisane dane na tym komputerze?"):
            from cache_manager import cache
            cache.hard_reset()
            msgbox.showinfo("Gotowe",
                            "Dane wyczyszczone. Możesz się zalogować.")

    def perform_login(self):
        """
        FIX: logowanie leci w wątku - aplikacja nie zamraża się na czas
        połączenia z serwerem. Przy okazji pokazujemy REALNY komunikat
        błędu (wcześniej każdy błąd wyglądał jak 'złe hasło').
        """
        email    = self.email_entry.get().strip()
        password = self.pass_entry.get()

        if not email or not password:
            self.error_lbl.configure(text="⚠ Wprowadź email i hasło")
            return

        self.error_lbl.configure(text="")
        self.login_btn.configure(state="disabled", text="Logowanie...")
        self.update_idletasks()

        def _login():
            try:
                success, message = self.auth.login(email, password)
            except Exception as e:
                success, message = False, str(e)
            # Wróć na wątek główny Tkintera (z zabezpieczeniem przed
            # zniszczonym ekranem - patrz _alive())
            try:
                self.after(0, lambda: self._finish_login(success, message))
            except Exception:
                pass

        threading.Thread(target=_login, daemon=True).start()

    def _alive(self):
        """
        Czy ten ekran logowania wciąż istnieje w drzewie widgetów?

        Logowanie leci w wątku i wraca przez after(0). Jeśli w międzyczasie
        ekran zostanie zniszczony (wylogowanie, wygaśnięcie sesji, ponowne
        show_login), configure() na martwym przycisku wywala aplikację:
            _tkinter.TclError: invalid command name ".!ctkbutton.!label"
        """
        try:
            return bool(self.winfo_exists()) and bool(self.login_btn.winfo_exists())
        except Exception:
            return False

    def _finish_login(self, success, message):
        """Obsługa wyniku logowania (ZAWSZE na wątku głównym)."""
        if not self._alive():
            # Ekran zniknął (wylogowanie / wygaśnięcie sesji), ale samo
            # logowanie jest bezpieczne - dokończ przejść w main.py,
            # inaczej użytkownik siedziałby na logowaniu mimo sukcesu.
            if success:
                try:
                    self.on_login_success()
                except Exception as e:
                    logger.error(f"Logowanie zakończone, ekran zniknął: {e}")
            return
        self.login_btn.configure(state="normal", text="ZALOGUJ SIĘ")

        if success:
            # BUG BYŁ: tu ustawiano database.CURRENT_USER (zmienna, której
            # nikt nie czyta) zamiast CURRENT_USER_EMAIL ustawianej w login().
            self.on_login_success()
        else:
            text = str(message or "Błąd logowania")
            self.error_lbl.configure(text=f"✕ {text}")
            self.login_btn.configure(state="normal", text="ZALOGUJ SIĘ")