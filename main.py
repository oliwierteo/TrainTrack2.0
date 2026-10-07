# main.py - TRAINTRACK PRO v2.0 — MODERN UI

import customtkinter as ctk
import sys
import os
import platform
from PIL import Image
import tkinter as tk
import time
import tkinter.messagebox as msgbox
import subprocess
from datetime import datetime
import threading
import database

database.create_fitness_tests_table()

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform.startswith("win")

SYSTEM_FONT = {
    "darwin": "SF Pro Text",
    "win32":  "Segoe UI",
    "linux":  "Ubuntu",
}.get(sys.platform, "Arial")

print(f"🖥️  Platform: {platform.system()}")
print(f"🔤 Using font: {SYSTEM_FONT}")

# ═══════════════════════════════════════════════
# KOLORY — SPÓJNY DESIGN SYSTEM
# ═══════════════════════════════════════════════
THEME = {
    "bg_main":      "#0a0a0a",
    "bg_sidebar":   "#111111",
    "bg_content":   "#121212",
    "sidebar_hover":"#1a2a3a",
    "sidebar_active":"#1f6aa5",
    "accent":       "#3b8ed0",
    "accent_dim":   "#2a6a9e",
    "text_primary": "#ffffff",
    "text_secondary":"#888888",
    "text_muted":   "#555555",
    "border":       "#1e1e1e",
    "border_light": "#2a2a2a",
    "success":      "#2ecc71",
    "danger":       "#c92c2c",
    "danger_hover": "#8a1c1c",
    "separator":    "#1a1a1a",
    "status_bg":    "#0d0d0d",
}


# ═══════════════════════════════════════════════
# PERFORMANCE TIMER (bez zmian)
# ═══════════════════════════════════════════════
class PerformanceTimer:
    def __init__(self, name=""):
        self.name = name
        self.start_time = None
        self.laps = []

    def start(self):
        self.start_time = time.perf_counter()
        return self

    def lap(self, label=""):
        if self.start_time:
            elapsed = (time.perf_counter() - self.start_time) * 1000
            self.laps.append((label, elapsed))
            return elapsed
        return 0

    def stop(self):
        return (time.perf_counter() - self.start_time) * 1000 if self.start_time else 0

    @staticmethod
    def format_time(ms):
        if ms < 100:
            return f"\033[92m{ms:.1f}ms\033[0m"
        elif ms < 500:
            return f"\033[93m{ms:.1f}ms\033[0m"
        return f"\033[91m{ms:.1f}ms\033[0m"


def log_perf(message, time_ms=None):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    if time_ms is not None:
        print(f"[{ts}] ⏱️  {message}: {PerformanceTimer.format_time(time_ms)}")
    else:
        print(f"[{ts}] 📌 {message}")


if IS_WINDOWS:
    os.system('')


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# Importy widoków
from database import supabase
from cache_manager import cache
from views.login_view import LoginView
from views.splash_view import SplashFrame, LoadingOverlay
from views.players_view import PlayersView
from views.profile_view import ProfileView
from views.calendar_view import CalendarView
from views.stats_view import StatsView
from views.analysis_view import AnalysisView
from views.squad_view import SquadView
from views.scouting_view import ScoutingView
from views.dashboard_view import DashboardView
from views.development_center_view import DevelopmentCenterView
from views.teams_view import TeamsManager
from logger import logger
import teams

try:
    from ctypes import windll
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        'traintrack.chelmianka.mgmt.1.0'
    )
except Exception:
    pass

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

if IS_MAC:
    ctk.set_widget_scaling(1.0)
    ctk.set_window_scaling(0.9)
else:
    ctk.set_widget_scaling(1.0)
    ctk.set_window_scaling(1.0)


# ═══════════════════════════════════════════════
# MODERN SIDEBAR BUTTON
# ═══════════════════════════════════════════════
class SidebarButton:
    """
    Przycisk sidebar oparty na CTkButton — ZERO selekcji tekstu.
    CTkButton nigdy nie pozwala na zaznaczanie tekstu.
    """

    def __init__(self, parent, text, icon, command, **kwargs):
        self._is_active = False
        self._text = text
        self._icon = icon
        self._command = command
        self._parent = parent

        # Główny kontener — CTkFrame tylko na indicator
        self._frame = ctk.CTkFrame(parent, fg_color="transparent",
                                   height=44, corner_radius=10)
        self._frame.pack_propagate(False)

        # Wskaźnik aktywności (pasek po lewej)
        self._indicator = ctk.CTkFrame(
            self._frame, width=3, height=22,
            fg_color="transparent", corner_radius=2,
        )
        self._indicator.pack(side="left", padx=(5, 0), pady=10)

        # JEDEN CTkButton — ikona + tekst razem
        # CTkButton NIGDY nie zaznacza tekstu
        self._button = ctk.CTkButton(
            self._frame,
            text=f"{icon}  {text}",
            font=(SYSTEM_FONT, 13),
            text_color=THEME["text_secondary"],
            fg_color="transparent",
            hover_color=THEME["sidebar_hover"],
            anchor="w",
            height=40,
            corner_radius=8,
            command=self._on_click,
            cursor="hand2",
        )
        self._button.pack(side="left", fill="both", expand=True, padx=(2, 4), pady=2)

    def _on_click(self):
        if self._command:
            self._command()

    def pack(self, **kwargs):
        self._frame.pack(**kwargs)

    def set_active(self, active: bool):
        self._is_active = active
        if active:
            self._frame.configure(fg_color=THEME["sidebar_active"])
            self._indicator.configure(fg_color=THEME["accent"])
            self._button.configure(
                text_color=THEME["text_primary"],
                fg_color="transparent",
                hover_color=THEME["sidebar_active"],
                font=(SYSTEM_FONT, 13, "bold"),
            )
        else:
            self._frame.configure(fg_color="transparent")
            self._indicator.configure(fg_color="transparent")
            self._button.configure(
                text_color=THEME["text_secondary"],
                fg_color="transparent",
                hover_color=THEME["sidebar_hover"],
                font=(SYSTEM_FONT, 13),
            )


# ═══════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════
class MainApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.withdraw()

        self._app_timer = PerformanceTimer("App Init")
        self._app_timer.start()
        log_perf("CTk.__init__", self._app_timer.lap("CTk"))

        self.title("TrainTrack v1.0 - Chełmianka Gdańsk")

        # Ikona
        if IS_WINDOWS:
            icon_p = resource_path("assets/icon.ico")
            if os.path.exists(icon_p):
                self.iconbitmap(icon_p)
        elif IS_MAC:
            try:
                icon_png = resource_path("assets/logo.png")
                if os.path.exists(icon_png):
                    img = tk.PhotoImage(file=icon_png)
                    self.iconphoto(True, img)
            except Exception:
                pass

        self.minsize(1200, 750)

        if IS_MAC:
            ctk.set_widget_scaling(1.0)
            ctk.set_window_scaling(1.0)

        # Główny kontener
        self.container = ctk.CTkFrame(self, fg_color=THEME["bg_main"])
        self.container.pack(fill="both", expand=True)

        self.loaded_views    = {}
        self.current_view    = None
        self.current_view_name = ""
        self.loading_overlay = None
        self._stale_views = []
        self._skip_overlay = False
        self._view_timers    = {}
        self._sidebar_btns   = {}

        if IS_MAC:
            try:
                self.after(100, self._set_macos_dark_title_bar)
            except Exception:
                pass

        self.last_activity_id = None
        self.is_monitoring    = False
        self.after(50, self.start_app)

    # ═══════════════════════════════════════════
    # STARTUP
    # ═══════════════════════════════════════════
    def start_app(self):
        logger.info("🚀 Aplikacja uruchomiona")
        self.deiconify()

        if IS_WINDOWS:
            self.state('zoomed')
        elif IS_MAC:
            try:
                self.state('zoomed')
            except Exception:
                w, h = self.winfo_screenwidth(), self.winfo_screenheight()
                self.geometry(f"{w}x{h}+0+0")

        # FIX: wcześniej socket.create_connection(8.8.8.8:53) blokował okno
        # startowe do 3 s i skutecznie odrzucał użytkowników sieci
        # firmowej/VPN. Teraz test leci w wątku i nie blokuje UI.
        self._startup_internet_check()

        self.show_startup_splash()

    def _startup_internet_check(self):
        """Sprawdza łączność w tle; aplikacja startuje niezależnie."""
        def _check():
            ok = self.check_internet()
            self.after(0, lambda: self._on_internet_result(ok))

        threading.Thread(target=_check, daemon=True).start()

    def _on_internet_result(self, ok):
        try:
            self._status_label = None  # status bar jeszcze nie istnieje
            if not ok:
                # Nie ubijamy aplikacji - widoki pokażą 'Brak połączenia'
                logger.warning("Brak łączności z internetem - działa w trybie offline")
        except Exception:
            pass

    def ensure_fullscreen(self):
        if IS_WINDOWS:
            self.state('zoomed')
        elif IS_MAC:
            try:
                self.state('zoomed')
            except Exception:
                w, h = self.winfo_screenwidth(), self.winfo_screenheight()
                self.geometry(f"{w}x{h}+0+0")

    def check_internet(self):
        """
        Sprawdzenie łączności. KROK 1: DNS hosta Supabase (działa też za
        firewallem, gdzie 8.8.8.8:53 bywa zablokowane).
        KROK 2: TCP na port 443 hosta Supabase.
        """
        import socket
        host = "jbnqmrsaqklbrhyyivdc.supabase.co"
        try:
            socket.getaddrinfo(host, 443)
        except OSError:
            return False
        try:
            with socket.create_connection((host, 443), timeout=3):
                return True
        except OSError:
            return False

    def show_startup_splash(self):
        self.ensure_fullscreen()
        SplashFrame(
            self.container,
            on_complete=self.show_login,
            title="TrainTrack",
            subtitle="System zarządzania drużyną",
            steps=[
                "Uruchamianie aplikacji...",
                "Łączenie z serwerem...",
                "Sprawdzanie połączenia...",
                "Ładowanie zasobów...",
                "Prawie gotowe...",
            ],
        )

    def show_login(self):
        logger.info("📋 Ekran logowania")
        # Monitor MUSI zostać zatrzymany. Bez tego co 60 s wykrywał brak
        # sesji i wołał show_login() ponownie - niszcząc ekran logowania
        # dokładnie w trakcie logowania (TclError na zniszczonym przycisku)
        # i kasując to, co użytkownik zdążył wpisać.
        self.is_monitoring = False
        # Fail-closed: po wylogowaniu nie zostawiamy uprawnień ani danych
        # poprzedniego trenera w pamięci aplikacji.
        try:
            teams.set_allowed_teams([])
        except Exception:
            pass
        database.CURRENT_USER_EMAIL = None
        for widget in self.container.winfo_children():
            widget.destroy()
        self.ensure_fullscreen()
        LoginView(
            self.container, on_login_success=self.on_login_success
        ).pack(fill="both", expand=True)

    def on_login_success(self):
        logger.info(f"✅ Zalogowano: {database.CURRENT_USER_EMAIL}")

        self._reset_layout()
        self.ensure_fullscreen()

        try:
            res = (supabase.table('activity_log')
                   .select("id")
                   .order('created_at', desc=True)
                   .limit(1).execute())
            if res.data:
                self.last_activity_id = res.data[0]['id']
        except Exception as e:
            logger.error(f"Nie udało się zainicjować monitora: {e}")

        if not self.is_monitoring:
            self.start_background_monitor()

        def preload_data():
            pt = PerformanceTimer("Preload")
            pt.start()
            log_perf("🔄 PRELOAD START")
            cache.preload_parallel()
            try:
                teams.get_teams(force_refresh=True)
                self.after(0, self.refresh_team_list)
            except Exception as e:
                logger.error(f"Nie udało się pobrać drużyn: {e}")
            log_perf("✅ PRELOAD DONE", pt.stop())
            print("-" * 60)

        SplashFrame(
            self.container,
            on_complete=self.show_dashboard,
            title="Witaj!",
            subtitle="Przygotowywanie panelu trenera",
            steps=[
                "Logowanie udane!",
                "Pobieranie danych klubu...",
                "Ładowanie zawodników...",
                "Przygotowywanie cache...",
                "Otwieranie dashboardu...",
            ],
            preload_function=preload_data,
        )

    # ═══════════════════════════════════════════
    # BACKGROUND MONITOR (bez zmian logiki)
    # ═══════════════════════════════════════════
    def start_background_monitor(self):
        if self.is_monitoring:
            return
        self.is_monitoring = True
        logger.info("📡 Monitor synchronizacji uruchomiony")
        self._monitor_loop()

    def _monitor_loop(self):
        if not self.is_monitoring:
            return

        def check_task():
            try:
                session = supabase.auth.get_session()
                if not session:
                    # Na ekranie logowania brak sesji jest NORMALNY -
                    # nie straszemy i nie przebudowujemy tego samego ekranu.
                    if not database.CURRENT_USER_EMAIL:
                        return
                    logger.warning("⚠️ Sesja wygasła!")
                    self.after(0, self.show_login)
                    return
            except Exception:
                pass

            try:
                res = (supabase.table('activity_log')
                       .select("id, coach_name, action")
                       .order('created_at', desc=True)
                       .limit(1).execute())
                if res.data:
                    current_id = res.data[0]['id']
                    if (self.last_activity_id
                            and current_id != self.last_activity_id):
                        coach  = res.data[0].get('coach_name', 'Inny trener')
                        action = res.data[0].get('action', 'zmienił dane')
                        logger.info(
                            f"🔄 Nowa aktywność: {coach} {action}. Odświeżam..."
                        )
                        cache.invalidate("players")
                        cache.invalidate("events")
                        cache.invalidate("ratings")
                        self.last_activity_id = current_id
                        self.after(0, self._auto_refresh_active_view)
                    else:
                        self.last_activity_id = current_id
            except Exception as e:
                logger.error(f"Monitor sync: {e}")

        threading.Thread(target=check_task, daemon=True).start()
        # Status połączenia odświeżany w tym samym cyklu
        self.after(0, self._update_status_text)
        self.after(60000, self._monitor_loop)

    def _auto_refresh_active_view(self):
        if self.current_view and hasattr(self.current_view, 'refresh_data'):
            logger.info(f"✨ Auto-refresh: {self.current_view_name}")
            self.current_view.refresh_data()

    # ═══════════════════════════════════════════
    # DASHBOARD SETUP
    # ═══════════════════════════════════════════
    def _reset_layout(self):
        """
        Kontener jest przebudowywany od zera, więc wszystkie jego dzieci
        (nakładka ładowania, załadowane widoki) znikają na zawsze.
        Bez wyczyszczenia referencji kolejne show_loading() i show_view()
        operują na zniszczonych widgetach (TclError).
        """
        self.loaded_views.clear()
        self.current_view = None
        self.current_view_name = None
        self.loading_overlay = None
        for widget in self.container.winfo_children():
            try:
                widget.destroy()
            except Exception:
                pass

    def show_dashboard(self):
        self._reset_layout()
        self.ensure_fullscreen()
        self.setup_sidebar()
        self.show_dashboard_view()

    # ═══════════════════════════════════════════
    # MODERN SIDEBAR
    # ═══════════════════════════════════════════
    def setup_sidebar(self):
        # ── Sidebar kontener ──
        self.sidebar = ctk.CTkFrame(
            self.container,
            width=260,
            corner_radius=0,
            fg_color=THEME["bg_sidebar"],
            border_width=0,
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # ── Logo + Brand ──
        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=15, pady=(25, 5))

        logo_path = resource_path("assets/logo.png")
        if os.path.exists(logo_path):
            try:
                logo_img = ctk.CTkImage(
                    light_image=Image.open(logo_path),
                    dark_image=Image.open(logo_path),
                    size=(70, 70),
                )
                ctk.CTkLabel(brand, image=logo_img, text="").pack(pady=(0, 8))
            except Exception:
                pass

        ctk.CTkLabel(
            brand, text="TrainTrack",
            font=(SYSTEM_FONT, 24, "bold"),
            text_color=THEME["accent"],
        ).pack()

        ctk.CTkLabel(
            brand, text="Chełmianka Gdańsk",
            font=(SYSTEM_FONT, 12),
            text_color=THEME["text_muted"],
        ).pack(pady=(2, 0))

        # ── Separator ──
        ctk.CTkFrame(
            self.sidebar, height=1,
            fg_color=THEME["border_light"],
        ).pack(fill="x", padx=20, pady=(15, 10))

        # ── Sezon ──
        season_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        season_frame.pack(fill="x", padx=20, pady=(5, 12))

        ctk.CTkLabel(
            season_frame, text="AKTYWNY SEZON",
            font=(SYSTEM_FONT, 9, "bold"),
            text_color=THEME["text_muted"],
        ).pack(anchor="w")

        self.season_menu = ctk.CTkOptionMenu(
            season_frame,
            values=database.get_available_seasons(),
            command=self._on_season_change,
            height=30,
            fg_color="#1a1a1a",
            button_color=THEME["border_light"],
            button_hover_color=THEME["accent_dim"],
            dropdown_fg_color="#1a1a1a",
            dropdown_hover_color=THEME["sidebar_hover"],
            font=(SYSTEM_FONT, 12),
            dropdown_font=(SYSTEM_FONT, 12),
            corner_radius=8,
        )
        self.season_menu.set(database.CURRENT_SEASON)
        self.season_menu.pack(fill="x", pady=(5, 0))

        # ── Drużyna (przełącznik rozwijany) ──
        team_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        team_frame.pack(fill="x", padx=20, pady=(5, 12))

        ctk.CTkLabel(
            team_frame, text="DRUŻYNA",
            font=(SYSTEM_FONT, 9, "bold"),
            text_color=THEME["text_muted"],
        ).pack(anchor="w")

        visible = teams.visible_teams()
        self._team_codes = [t["code"] for t in visible]
        self.team_menu = ctk.CTkOptionMenu(
            team_frame,
            values=[self._label_for(t["code"]) for t in visible] or ["—"],
            command=self._on_team_change_menu,
            height=34,
            fg_color="#1a1a1a",
            button_color=THEME["border_light"],
            button_hover_color=THEME["accent_dim"],
            dropdown_fg_color="#1a1a1a",
            dropdown_hover_color=THEME["sidebar_hover"],
            font=(SYSTEM_FONT, 11),
            dropdown_font=(SYSTEM_FONT, 11),
            corner_radius=8,
        )
        self.team_menu.set(self._label_for(teams.get_current_team()))
        self.team_menu.pack(fill="x", pady=(5, 0))

        # ── Separator ──
        ctk.CTkFrame(
            self.sidebar, height=1,
            fg_color=THEME["border_light"],
        ).pack(fill="x", padx=20, pady=(8, 12))

        # ── Sekcja: GŁÓWNE ──
        ctk.CTkLabel(
            self.sidebar, text="  MENU GŁÓWNE",
            font=(SYSTEM_FONT, 9, "bold"),
            text_color=THEME["text_muted"],
            anchor="w",
        ).pack(fill="x", padx=20, pady=(0, 4))

        # ── Menu buttons ──
        self._sidebar_btns = {}
        self.main_area = ctk.CTkFrame(
            self.container,
            fg_color=THEME["bg_content"],
            corner_radius=0,
        )
        self.main_area.pack(side="left", fill="both", expand=True)

        menu_items = [
            ("dashboard",   "🏠 Dashboard",       self.show_dashboard_view),
            ("players",     "👤 Zawodnicy",        self.show_players_list),
            ("calendar",    "📅 Kalendarz",        self.show_calendar),
            ("reports",     "📊 Regularność",      self.show_stats),
            ("analysis",    "📈 Analiza Formy",    self.show_analysis),
            ("squad",       "⚽ Skład / Taktyka",  self.show_squad),
            ("scouting",    "🔍 Scouting",         self.show_scouting),
            ("development", "🎯 Centrum Rozwoju",  self.show_development),
            ("finanse",     "💰 Finanse",          self.show_finanse),
        ]

        for key, label, cmd in menu_items:
            if key in database.ALLOWED_TABS:
                btn = ctk.CTkButton(
                    self.sidebar,
                    text=label,
                    height=42,
                    font=(SYSTEM_FONT, 14),
                    anchor="w",
                    corner_radius=8,
                    # Domyślny wygląd = nieaktywny
                    fg_color="transparent",
                    text_color="#888888",
                    hover_color="#1a2a3a",
                    command=cmd,
                )
                btn.pack(fill="x", padx=12, pady=3)
                self._sidebar_btns[key] = btn

        # ── Dolna sekcja (push to bottom) ──
        bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=15, pady=(0, 15))

        # Sygnatura
        sig = ctk.CTkFrame(bottom, fg_color="transparent")
        sig.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            sig, text="TrainTrack Engine v1.0.0",
            font=(SYSTEM_FONT, 9),
            text_color=THEME["text_muted"],
        ).pack()
        ctk.CTkLabel(
            sig, text="Developed by Tcube",
            font=(SYSTEM_FONT, 9, "bold"),
            text_color=THEME["accent_dim"],
        ).pack()

        # Drużyny (tylko dla trenerów z uprawnieniem 'squad')
        if "squad" in database.ALLOWED_TABS:
            ctk.CTkButton(
                bottom, text="⚙️ Drużyny",
                height=32,
                fg_color="transparent",
                border_width=1,
                border_color=THEME["border_light"],
                hover_color=THEME["sidebar_hover"],
                font=(SYSTEM_FONT, 11),
                text_color=THEME["text_secondary"],
                corner_radius=8,
                command=self.show_teams_manager,
            ).pack(fill="x", pady=(0, 8))

        # Repair
        ctk.CTkButton(
            bottom, text="🔧 Napraw / Czyść Cache",
            height=32,
            fg_color="transparent",
            border_width=1,
            border_color=THEME["border_light"],
            hover_color=THEME["sidebar_hover"],
            font=(SYSTEM_FONT, 11),
            text_color=THEME["text_secondary"],
            corner_radius=8,
            command=self.repair_app,
        ).pack(fill="x", pady=(0, 8))

        # Wyloguj
        ctk.CTkButton(
            bottom, text="WYLOGUJ",
            height=40,
            fg_color=THEME["danger"],
            hover_color=THEME["danger_hover"],
            font=(SYSTEM_FONT, 13, "bold"),
            corner_radius=8,
            command=self.show_login,
        ).pack(fill="x")

        # Status bar na dole main_area
        self._create_status_bar()

        # Ustaw aktywny widok
        if database.ALLOWED_TABS:
            self.current_view_name = database.ALLOWED_TABS[0]
        self.update_menu_active()

    def _create_status_bar(self):
        """Pasek statusu na dole ekranu — live info"""
        self.status_bar = ctk.CTkFrame(
            self.main_area,
            height=28,
            fg_color=THEME["status_bg"],
            corner_radius=0,
        )
        self.status_bar.pack(side="bottom", fill="x")
        self.status_bar.pack_propagate(False)

        # Lewa strona: status
        self._status_label = ctk.CTkLabel(
            self.status_bar,
            text=f"✅ Połączono  |  {database.CURRENT_CLUB}"
                 f"  |  {teams.scope_label()}"
                 f"  |  Sezon {database.CURRENT_SEASON}",
            font=(SYSTEM_FONT, 10),
            text_color=THEME["text_muted"],
        )
        self._status_label.pack(side="left", padx=15)

        # Prawa strona: czas
        self._clock_label = ctk.CTkLabel(
            self.status_bar,
            text="",
            font=(SYSTEM_FONT, 10),
            text_color=THEME["text_muted"],
        )
        self._clock_label.pack(side="right", padx=15)
        self._update_clock()

    def _update_clock(self):
        # FIX: po zniszczeniu okna self.after() rzuca TclError - cały
        # callback musi być w try/except, nie tylko konfiguracja labela.
        try:
            if not self.winfo_exists():
                return
            now = datetime.now().strftime("%H:%M:%S")
            self._clock_label.configure(text=f"🕐 {now}")
            self.after(1000, self._update_clock)
        except Exception:
            return

    def _update_status_text(self):
        """Aktualizuje tekst statusu (uwzględnia błędy połączenia)"""
        try:
            if not hasattr(self, "_status_label") or self._status_label is None:
                return
            err = cache.get_last_error()
            if err:
                icon = "⚠️  Brak połączenia"
            else:
                icon = "✅ Połączono"
            self._status_label.configure(
                text=f"{icon}  |  {database.CURRENT_CLUB}"
                     f"  |  {teams.scope_label()}"
                     f"  |  Sezon {database.CURRENT_SEASON}"
            )
        except Exception:
            pass

    # ═══════════════════════════════════════════
    # MENU STATE
    # ═══════════════════════════════════════════
    def update_menu_active(self):
        for key, btn in self._sidebar_btns.items():
            if key == self.current_view_name:
                btn.configure(
                    fg_color="#1f6aa5",
                    text_color="#ffffff",
                    hover_color="#1f6aa5",
                    font=(SYSTEM_FONT, 14, "bold"),
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color="#888888",
                    hover_color="#1a2a3a",
                    font=(SYSTEM_FONT, 14),
                )

    # ═══════════════════════════════════════════
    # SEASON CHANGE
    # ═══════════════════════════════════════════
    @staticmethod
    def _label_for(code):
        """Etykieta drużyny w przełączniku: SKRÓT + nazwa."""
        if code == teams.ALL_TEAMS:
            return "★  Wszystkie drużyny"
        return teams.team_label(code, with_name=True)

    def _on_team_change_menu(self, label):
        """Trener wybrał drużynę z listy w sidebarze."""
        try:
            values = list(self.team_menu.cget("values"))
            index = values.index(label)
            code = self._team_codes[index]
        except (ValueError, IndexError, AttributeError):
            logger.warning(f"Nieznana etykieta drużyny: {label}")
            return
        self.set_team(code)

    # Zakładka -> metoda otwierająca (do przebudowy po zmianie drużyny)
    _TAB_ROUTES = {
        "dashboard":   "show_dashboard_view",
        "players":     "show_players_list",
        "profile":     "show_players_list",   # profil -> lista zawodników
        "calendar":    "show_calendar",
        "reports":     "show_stats",
        "analysis":    "show_analysis",
        "squad":       "show_squad",
        "scouting":    "show_scouting",
        "finanse":     "show_finanse",
        "development": "show_development",
    }

    def set_team(self, code, reopen=True):
        """
        Zmiana aktywnej drużyny.

        KLUCZOWE: widoki trzymają dane konkretnej drużyny (kadra, terminarze,
        skład, finanse), a większość z nich nie ma on_team_changed() ani
        refresh_data(). Dlatego zamiast prosić widok o odświeżenie,
        BUDUJEMY zakładkę od nowa dla nowej drużyny.

        Płynność: stare widoki zostają pod nowym kadrem do momentu
        wyrysowania nowego, cache (klucze per drużyna) zostaje, a nakładka
        ładowania jest pomijana. Dane są już w poblięciu.
        """
        if not teams.set_current_team(code):
            logger.warning(f"Zmiana drużyny na {code} odrzucona (brak dostępu)")
            self.team_menu.set(self._label_for(teams.get_current_team()))
            self._update_status_text()
            return False

        logger.info(f"⚽ Zmieniono drużynę: {teams.scope_label()}")
        try:
            database.save_preferred_team(database.CURRENT_USER_EMAIL, code)
        except Exception as e:
            logger.error(f"Nie udało się zapamiętać drużyny: {e}")

        previous = self.current_view_name

        # Stare widoki NIE giną od razu - zostają pod nowym kadrem do
        # momentu, aż nowy zakładka się wyrysowała. Bez tego w oknie
        # zmiany drużyny pojawia się pusty ekran (migotanie).
        stale = [v for v in self.loaded_views.values() if v is not None]
        if self.current_view is not None and self.current_view not in stale:
            stale.append(self.current_view)
        # kolejne szybkie przełączenia nie mogą zgubić wcześniejszych
        self._stale_views = (getattr(self, "_stale_views", []) or []) + stale
        self.loaded_views.clear()
        self.current_view = None

        # Cache ZOSTAJE. Klucze są per drużyna (scope), więc dane nowej
        # drużyny są już gotowe albo pobiorą się same. invalidate_all()
        # kasował wszystko i zamieniał każdą zmianę drużyny w ładowanie
        # z sieci - stąd "ciężkie przełączanie".
        teams.get_teams()          # cache 5 min - nie pytamy na nowo
        self.refresh_team_list()
        self._update_status_text()

        try:
            route = self._TAB_ROUTES.get(previous if reopen else None,
                                         "show_dashboard_view")
            self._skip_overlay = True      # dane z cache - bez nakładki
            getattr(self, route)()
        except Exception as e:
            logger.error(f"Nie udało się otworzyć zakładki po zmianie "
                         f"drużyny: {e}")
            try:
                self.show_dashboard_view()
            except Exception:
                pass
        finally:
            self._skip_overlay = False
            self._purge_stale()
        return True

    def _purge_stale(self):
        """Dopiero po wyrysowaniu nowego widoku niszczymy stare."""
        for view in getattr(self, "_stale_views", []) or []:
            try:
                view.pack_forget()
                view.destroy()
            except Exception as e:
                logger.warning(f"Nie udało się zamknąć starego widoku: {e}")
        self._stale_views = []

    def _destroy_all_views(self):
        """Niszczy WSZYSTKIE widoki (trzymają dane starej drużyny)."""
        for name in list(self.loaded_views.keys()):
            self._destroy_view(name)
        self.loaded_views.clear()
        self.current_view = None

    def refresh_team_list(self):
        """
        Odświeża listę drużyn (po zalogowaniu lub zmianie uprawnień).

        UWAGA: preload kończy się asynchronicznie i potrafi dobiec tu
        PRZED zbudowaniem sidebara (brak team_menu) albo PO wylogowaniu,
        gdy stary sidebar już nie istnieje w drzewie widgetów - wtedy
        obiekt team_menu istnieje w Pythonie, ale jego komenda Tcl już nie.
        Dlatego sprawdzamy nie tylko atrybut, lecz czy widget NAPRAWDĘ żyje.
        """
        menu = getattr(self, "team_menu", None)
        if menu is None:
            return
        try:
            if not menu.winfo_exists():
                return
        except Exception:
            return          # zniszczony sidebar - nie ma czego odświeżać
        try:
            visible = teams.visible_teams()
            self._team_codes = [t["code"] for t in visible]
            labels = [self._label_for(c) for c in self._team_codes]
            current_code = teams.get_current_team()
            current = self._label_for(current_code)
            if current not in labels:
                # drużyna spoza listy dozwolonych - dopisujemy RAZEM
                # z kodem, żeby indeksy etykiety i kodu się zgadzały
                labels.append(current)
                self._team_codes.append(current_code)
            self.team_menu.configure(values=labels)
            self.team_menu.set(current)
        except Exception as e:
            logger.error(f"Nie udało się odświeżyć listy drużyn: {e}")

    def _destroy_view(self, view_name):
        """
        FIX: samo `del self.loaded_views[key]` zostawiało widgety w pamięci
        (i ich timery po self.after()) - wyciek przy każdej zmianie sezonu.
        """
        view = self.loaded_views.pop(view_name, None)
        if view is None:
            return
        try:
            view.pack_forget()
            view.destroy()
        except Exception as e:
            logger.error(f"Nie udało się zamknąć widoku {view_name}: {e}")

    def _on_season_change(self, new_season):
        if database.CURRENT_SEASON == new_season:
            return

        database.set_season(new_season)
        logger.info(f"❄️ Zmieniono sezon: {new_season}")

        cache.invalidate_all()

        # Widoki zależne od sezonu tworzymy od nowa
        for key in ["calendar", "reports"]:
            self._destroy_view(key)

        # Widoki, które trzymają własny stan (np. finances: rok/miesiąc),
        # muszą dostać informację o nowym sezonie
        if self.current_view:
            try:
                if hasattr(self.current_view, "on_season_changed"):
                    self.current_view.on_season_changed(database.CURRENT_SEASON)
            except Exception as e:
                logger.error(f"Błąd przy zmianie sezonu widoku: {e}")

        self._update_status_text()

        if self.current_view_name == "calendar":
            self.show_calendar()
        elif self.current_view_name == "reports":
            self.show_stats()
        elif self.current_view and hasattr(self.current_view, 'refresh_data'):
            self.show_loading(f"Ładowanie sezonu {new_season}...")
            self.current_view.refresh_data()
            self.after(500, self.hide_loading)

    # ═══════════════════════════════════════════
    # LOADING OVERLAY
    # ═══════════════════════════════════════════
    def show_loading(self, message="Ładowanie danych..."):
        """
        Nakładka musi być tworzona OD NOWA, jeśli poprzednia została
        zniszczona wraz z kontenerem (show_dashboard przebudowuje layout).
        Bez tego configure() konczy się TclError 'invalid command name'
        i zakładka w ogóle się nie otwiera.
        """
        try:
            if self.loading_overlay is None or not self.loading_overlay.alive():
                self.loading_overlay = LoadingOverlay(self.main_area, message)
            else:
                self.loading_overlay.set_message(message)
            self.loading_overlay.show()
        except Exception as e:
            logger.warning(f"Nakładka ładowania: {e}")

    def hide_loading(self):
        try:
            if self.loading_overlay and self.loading_overlay.alive():
                self.loading_overlay.hide()
        except Exception as e:
            logger.warning(f"Ukrycie nakładki: {e}")

    # ═══════════════════════════════════════════
    # VIEW SWITCHING (zoptymalizowane)
    # ═══════════════════════════════════════════
    def show_view(self, view_name, view_class, *args, **kwargs):
        timer = PerformanceTimer(view_name)
        timer.start()

        print()
        log_perf(f"🔄 → {view_name.upper()}")

        if self.current_view:
            self.current_view.pack_forget()
            log_perf("  └─ Ukryto poprzedni", timer.lap("hide"))

        cached_view = self.loaded_views.get(view_name)
        if cached_view is not None:
            try:
                cached_view.winfo_exists()
            except Exception:
                cached_view = None          # widget nie istnieje - odtwarzamy
        if view_name not in self.loaded_views or cached_view is None:
            heavy = ["players", "calendar", "scouting"]
            show_overlay = view_name in heavy and not self._skip_overlay
            if show_overlay:
                self.show_loading(f"Ładowanie {view_name}...")

            t0 = time.perf_counter()
            self.loaded_views[view_name] = view_class(
                self.main_area, *args, **kwargs
            )
            ct = (time.perf_counter() - t0) * 1000

            if show_overlay:
                self.hide_loading()

            log_perf("  └─ NOWY widok", ct)
        else:
            log_perf("  └─ Z CACHE", timer.lap("cache"))

        self.current_view      = self.loaded_views[view_name]
        self.current_view_name = view_name
        self.current_view.pack(fill="both", expand=True, padx=0, pady=0)
        log_perf("  └─ Wyświetlono", timer.lap("pack"))

        def refresh_async():
            if hasattr(self.current_view, 'refresh_data'):
                self.current_view.refresh_data()
            elif hasattr(self.current_view, 'refresh_data_async'):
                self.current_view.refresh_data_async()

        self.after(50, refresh_async)

        total = timer.stop()
        self._view_timers[view_name] = total
        log_perf(f"✅ {view_name.upper()} TOTAL", total)
        print("-" * 60)

        if IS_MAC:
            self.update_idletasks()

    def clear_main_area(self):
        import gc
        for widget in self.main_area.winfo_children():
            if widget != getattr(self, 'status_bar', None):
                widget.destroy()
        gc.collect()

    # ═══════════════════════════════════════════
    # VIEW METHODS
    # ═══════════════════════════════════════════
    def show_dashboard_view(self):
        self.current_view_name = "dashboard"
        self.update_menu_active()
        self.show_view("dashboard", DashboardView)

    def show_players_list(self):
        self.current_view_name = "players"
        self.update_menu_active()
        self.show_view("players", PlayersView,
                       on_open_profile=self.show_profile)

    def show_profile(self, player_data):
        # FIX: stary widok (np. poprzedni profil gracza) tylko się ukrywał,
        # ale nigdy nie był niszczony -> po 20 otwarciach 20 żywych widgetów.
        if self.current_view is not None:
            try:
                self.current_view.pack_forget()
                if self.current_view is not self.loaded_views.get(self.current_view_name):
                    self.current_view.destroy()
                    self.current_view = None
            except Exception as e:
                logger.error(f"Błąd przy zamykaniu poprzedniego widoku: {e}")
        view = ProfileView(
            self.main_area,
            player_data=player_data,
            on_back=self.show_players_list,
        )
        view.pack(fill="both", expand=True, padx=0, pady=0)
        self.current_view = view

    def show_calendar(self):
        self.current_view_name = "calendar"
        self.update_menu_active()
        self.show_view("calendar", CalendarView)

    def show_stats(self):
        self.current_view_name = "reports"
        self.update_menu_active()
        self.show_view("stats", StatsView)

    def show_analysis(self):
        self.current_view_name = "analysis"
        self.update_menu_active()
        self.show_view("analysis", AnalysisView)

    def show_squad(self):
        self.current_view_name = "squad"
        self.update_menu_active()
        self.show_view("squad", SquadView)

    def show_scouting(self):
        self.current_view_name = "scouting"
        self.update_menu_active()
        self.show_view("scouting", ScoutingView)

    def show_finanse(self):
        from views.finances_view import FinancesView
        self.current_view_name = "finanse"
        self.update_menu_active()
        self.show_view("finanse", FinancesView)

    def show_development(self):
        self.current_view_name = "development"
        self.update_menu_active()
        self.show_view("development", DevelopmentCenterView)

    # ═══════════════════════════════════════════
    # REPAIR / UTILS
    # ═══════════════════════════════════════════
    def repair_app(self):
        if msgbox.askyesno("Naprawa",
                           "Czy wyczyścić pamięć podręczną i zdjęcia?"):
            try:
                cache.hard_reset()
                msgbox.showinfo(
                    "Gotowe",
                    "Pamięć wyczyszczona.\n"
                    "Zamknij aplikację i uruchom ponownie.",
                )
                self.quit()
                self.destroy()
            except Exception as e:
                msgbox.showerror("Błąd", f"Nie udało się: {e}")

    def show_teams_manager(self):
        """Okno zarządzania drużynami (kody, nazwy, kolory)."""
        try:
            TeamsManager(self, on_changed=lambda: (
                self.refresh_team_list(), self._update_status_text()))
        except Exception as e:
            logger.error(f"Nie udało się otworzyć menedżera drużyn: {e}")
            msgbox.showerror("Błąd", str(e))

    def _set_macos_dark_title_bar(self):
        pass

    def print_performance_summary(self):
        print()
        print("=" * 60)
        print("📊 PODSUMOWANIE WYDAJNOŚCI ZAKŁADEK")
        print("=" * 60)

        if not self._view_timers:
            print("  Brak danych")
            return

        for name, ms in sorted(self._view_timers.items(),
                                key=lambda x: x[1], reverse=True):
            bar = "█" * int(min(ms / 20, 30))
            print(f"  {name:15} {bar:30} "
                  f"{PerformanceTimer.format_time(ms)}")

        if self._view_timers:
            avg = sum(self._view_timers.values()) / len(self._view_timers)
            print("-" * 60)
            print(f"  {'ŚREDNIA':15} {PerformanceTimer.format_time(avg)}")

        print("=" * 60)


# ═══════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════
if __name__ == "__main__":
    startup_timer = PerformanceTimer("Startup")
    startup_timer.start()

    print()
    print("=" * 60)
    print("🚀 TRAINTRACK PRO - STARTUP")
    print("=" * 60)
    log_perf(f"System: {platform.system()} {platform.release()}")
    log_perf(f"Python: {sys.version.split()[0]}")
    print("-" * 60)

    app = MainApp()

    log_perf("STARTUP TOTAL", startup_timer.stop())
    print("=" * 60)
    print()

    try:
        app.mainloop()
    finally:
        # FIX: bez tego cache zapisany z debounce'em (5 s) przepadał,
        # a pule wątków zostawały wiszące przy zamknięciu aplikacji.
        logger.info("Zamykanie - zapis cache i zatrzymanie wątków...")
        try:
            cache.shutdown()
        except Exception as e:
            logger.error(f"Błąd przy zamykaniu cache: {e}")
        try:
            from image_manager import img_manager
            img_manager.shutdown()
        except Exception as e:
            logger.error(f"Błąd przy zamykaniu image_manager: {e}")
        logger.info("TrainTrack zamknięty")
        app.print_performance_summary()