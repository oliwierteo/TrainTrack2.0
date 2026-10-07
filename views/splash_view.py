# views/splash_view.py - MODERN SPLASH v2.0

import customtkinter as ctk
from PIL import Image
import os
import sys
import threading

SYSTEM_FONT = {
    "darwin": "SF Pro Text",
    "win32":  "Segoe UI",
    "linux":  "Ubuntu",
}.get(sys.platform, "Arial")


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class SplashFrame(ctk.CTkFrame):
    """Ekran ładowania — minimalny, szybki"""

    def __init__(self, parent, on_complete, title="TrainTrack",
                 subtitle="System zarządzania drużyną",
                 steps=None, preload_function=None):
        super().__init__(parent, fg_color="#0a0a0a")
        self.on_complete      = on_complete
        self.preload_function = preload_function
        self.preload_done     = False
        self.animation_done   = False

        if steps is None:
            steps = [
                "Uruchamianie...",
                "Łączenie z bazą danych...",
                "Pobieranie konfiguracji...",
                "Przygotowywanie interfejsu...",
                "Prawie gotowe...",
            ]
        self.loading_steps = steps
        self.progress_value = 0

        self.pack(fill="both", expand=True)

        # ── Zawartość ──
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.place(relx=0.5, rely=0.48, anchor="center")

        # Logo
        logo_path = resource_path("assets/logo.png")
        if os.path.exists(logo_path):
            try:
                logo_img = ctk.CTkImage(
                    light_image=Image.open(logo_path),
                    dark_image=Image.open(logo_path),
                    size=(100, 100),
                )
                ctk.CTkLabel(center, image=logo_img, text="").pack(pady=(0, 18))
            except Exception:
                ctk.CTkLabel(center, text="⚽",
                             font=("Arial", 60)).pack(pady=(0, 18))

        ctk.CTkLabel(
            center, text=title,
            font=(SYSTEM_FONT, 34, "bold"),
            text_color="#3b8ed0",
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            center, text=subtitle,
            font=(SYSTEM_FONT, 13),
            text_color="#555555",
        ).pack(pady=(0, 35))

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            center, width=320, height=6,
            progress_color="#3b8ed0",
            fg_color="#1a1a1a",
            corner_radius=3,
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=(0, 12))

        # Tekst statusu
        self.loading_label = ctk.CTkLabel(
            center, text=steps[0],
            font=(SYSTEM_FONT, 11),
            text_color="#555555",
        )
        self.loading_label.pack()

        # Wersja
        ctk.CTkLabel(
            self, text="v1.0.0  ·  Developed by Tcube",
            font=(SYSTEM_FONT, 10),
            text_color="#2a2a2a",
        ).pack(side="bottom", pady=20)

        # ── Start ──
        if self.preload_function:
            threading.Thread(target=self._run_preload, daemon=True).start()
        else:
            self.preload_done = True

        self.after(50, self._animate)

    def _run_preload(self):
        try:
            self.preload_function()
        except Exception as e:
            print(f"Preload error: {e}")
        finally:
            self.preload_done = True

    def _animate(self):
        if not self.winfo_exists():
            return

        if self.progress_value < 100:
            # Zatrzymaj na 75% jeśli preload trwa
            if self.progress_value >= 75 and not self.preload_done:
                self.loading_label.configure(
                    text="Pobieranie danych z serwera..."
                )
                self.after(80, self._animate)
                return

            # Szybciej na początku, wolniej pod koniec
            if self.progress_value < 40:
                step = 3
            elif self.progress_value < 70:
                step = 2
            else:
                step = 1

            self.progress_value += step
            self.progress_bar.set(self.progress_value / 100)

            idx = min(
                self.progress_value // (100 // len(self.loading_steps)),
                len(self.loading_steps) - 1,
            )
            self.loading_label.configure(text=self.loading_steps[idx])

            self.after(20, self._animate)
        else:
            self.animation_done = True
            self._check_finish()

    def _check_finish(self):
        if not self.winfo_exists():
            return
        if self.animation_done and self.preload_done:
            self.after(80, self._finish)
        else:
            self.after(50, self._check_finish)

    def _finish(self):
        if not self.winfo_exists():
            return
        self.destroy()
        self.on_complete()


class LoadingOverlay(ctk.CTkFrame):
    """Nakładka ładowania — minimalna"""

    def __init__(self, parent, message="Ładowanie danych..."):
        super().__init__(parent, fg_color="#0f0f0f")

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")

        # Animowany wskaźnik
        self._dots_label = ctk.CTkLabel(
            center, text="●",
            font=(SYSTEM_FONT, 24),
            text_color="#3b8ed0",
        )
        self._dots_label.pack(pady=(0, 12))

        self.message_label = ctk.CTkLabel(
            center, text=message,
            font=(SYSTEM_FONT, 13),
            text_color="#666666",
        )
        self.message_label.pack()

        self._dot_frame = 0
        self._dot_patterns = ["●  ○  ○", "○  ●  ○", "○  ○  ●"]
        self._animate()

    def _animate(self):
        try:
            if not self.winfo_exists():
                return
            self._dot_frame = (self._dot_frame + 1) % len(self._dot_patterns)
            self._dots_label.configure(text=self._dot_patterns[self._dot_frame])
            self.after(300, self._animate)
        except Exception:
            pass

    def alive(self):
        """
        Czy nakładka jeszcze istnieje w drzewie Tk.

        Kontener bywa przebudowywany (show_dashboard kasuje dzieci), a
        referencja zostaje - wtedy configure() wywala TclError
        'invalid command name'. Każde wywołanie musi to sprawdzić.
        """
        try:
            return bool(self.winfo_exists()) and \
                   bool(self.message_label.winfo_exists())
        except Exception:
            return False

    def set_message(self, message):
        """Aktualizuje tekst bezpiecznie (nic nie robi na martwej nakładce)."""
        try:
            if not self.alive():
                return
            self.message_label.configure(text=message)
        except Exception:
            pass

    def show(self):
        try:
            if not self.winfo_exists():
                return
            self.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.lift()
        except Exception:
            pass

    def hide(self):
        try:
            if not self.winfo_exists():
                return
            self.place_forget()
        except Exception:
            pass