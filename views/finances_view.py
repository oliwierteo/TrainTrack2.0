# finances_view.py - COMPLETE OPTIMIZED v5.0 (FIXED)
import sys 
import customtkinter as ctk
import tkinter.messagebox as msgbox
from database import supabase
import database
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import json
import os
import platform
import threading
from concurrent.futures import ThreadPoolExecutor
from logger import logger
from ui_async import run_async
import teams

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Teraz import zadziała
try:
    from pdf_generator import PDFGenerator
except ImportError:
    # Fallback dla PyInstaller (gdy wszystko jest spakowane)
    import pdf_generator
    PDFGenerator = pdf_generator.PDFGenerator

# =============================================
# HELPERS
# =============================================
def safe_float(value, default=0.0):
    try:
        if value is None or value == '':
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_int(value, default=0):
    try:
        if value is None or value == '':
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default

# =============================================
# KOLORY
# =============================================
COLORS = {
    "bg_dark": "#121212",
    "card_bg": "#1e1e1e",
    "card_lighter": "#252525",
    "accent": "#3b8ed0",
    "paid": "#2fa572",
    "unpaid": "#cf352e",
    "partial": "#e67e22",
    "money": "#f1c40f",
    "text_gray": "#aaaaaa",
    "exempt": "#9b59b6",
    "danger": "#e74c3c"
}

MONTHS_PL = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", 
             "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]


class FinancesView(ctk.CTkFrame):
    """System zarządzania składkami v5.0 - FIXED"""
    
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg_dark"])
        
        # Stan
        self.current_year = datetime.now().year
        self.selected_month = datetime.now().month
        self.players_data = []
        self.finances_data = []
        self.all_finances_data = []
        self.club_settings = {}
        self.fee_history = []
        
        # Kontrola wątków
        self.search_timer = None
        self._loading = False
        # FIX: zmiana filtra (rok/miesiąc/sezon) w trakcie ładowania nie może
        # zostać PO DRODZE ZGUBIONA - jest zapamiętywana i wykonywana po fakcie.
        self._reload_pending = False
        self._executor = ThreadPoolExecutor(max_workers=2)
        
        # Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        self._create_header()
        self._create_filters()
        self._create_player_list()
        self._create_stats_panel()
        
        # Preload w tle + ładowanie UI
        self._initial_load()
    
    def _initial_load(self):
        """
        Wejście do zakładki = JEDEN load (load_data czyta cache, bez refreshu).

        Dawniej tu było drugie, równoległe ładowanie obok refresh_data() z
        after(50, ...) - przez to finances/fee_history leciały 2x przy
        każdym wejściu. Teraz obie ścieżki idą przez load_data(),
        a strażnik self._loading odcina wyścig.
        """
        self.load_data()
    
    def _show_loading(self):
        for w in self.scroll_frame.winfo_children(): w.destroy()
        ctk.CTkLabel(self.scroll_frame, text="⏳ Ładowanie...", font=("Segoe UI", 16), text_color="gray").pack(pady=50)
    
    def _show_error(self, message):
        for w in self.scroll_frame.winfo_children(): w.destroy()
        ctk.CTkLabel(self.scroll_frame, text=f"❌ Błąd: {message}", text_color="red", font=("Segoe UI", 14)).pack(pady=50)
        ctk.CTkButton(self.scroll_frame, text="🔄 Spróbuj ponownie", command=self._force_refresh).pack(pady=10)
    
    # =============================================
    # UI CREATION
    # =============================================
    
    def _create_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 10))
        
        ctk.CTkLabel(header, text=f"💰 FINANSE — {teams.scope_label().upper()}",
                     font=("Segoe UI", 24, "bold"),
                     text_color=COLORS["accent"]).pack(side="left")
        
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right")
        
        ctk.CTkButton(btn_frame, text="⚙️ Ustawienia", width=110, height=32, fg_color=COLORS["card_bg"], hover_color="#333", command=self._show_settings_modal).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="📄 Export PDF", width=110, height=32, fg_color=COLORS["card_bg"], hover_color="#333", command=self._show_export_modal).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="⟳", width=40, height=32, fg_color=COLORS["card_bg"], hover_color="#333", command=self._force_refresh).pack(side="left", padx=5)
    
    def _create_filters(self):
        filters = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=12)
        filters.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        
        inner = ctk.CTkFrame(filters, fg_color="transparent")
        inner.pack(fill="x", padx=15, pady=10)
        
        date_frame = ctk.CTkFrame(inner, fg_color="transparent")
        date_frame.pack(side="left")
        
        ctk.CTkLabel(date_frame, text="Okres:", font=("Segoe UI", 12)).pack(side="left", padx=(0, 10))
        self.month_menu = ctk.CTkOptionMenu(date_frame, values=MONTHS_PL, command=self._on_date_change, width=130)
        self.month_menu.set(MONTHS_PL[self.selected_month - 1])
        self.month_menu.pack(side="left", padx=5)
        
        years = [str(y) for y in range(2024, datetime.now().year + 2)]
        self.year_menu = ctk.CTkOptionMenu(date_frame, values=years, command=self._on_date_change, width=80)
        self.year_menu.set(str(self.current_year))
        self.year_menu.pack(side="left", padx=5)
        
        self.search_var = ctk.StringVar()
        ctk.CTkEntry(inner, textvariable=self.search_var, placeholder_text="🔍 Szukaj...", width=180).pack(side="left", padx=30)
        self.search_var.trace("w", self._on_search)
        
        filter_frame = ctk.CTkFrame(inner, fg_color="transparent")
        filter_frame.pack(side="right")
        self.filter_var = ctk.StringVar(value="all")
        
        for text, value in [("Wszyscy", "all"), ("Zaległości", "unpaid"), ("Opłaceni", "paid")]:
            ctk.CTkRadioButton(filter_frame, text=text, variable=self.filter_var, value=value, command=self._display_players, radiobutton_width=18, radiobutton_height=18).pack(side="left", padx=8)
    
    def _create_player_list(self):
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color=COLORS["card_bg"], corner_radius=15)
        self.scroll_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=5)
    
    def _create_stats_panel(self):
        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.grid(row=3, column=0, sticky="ew", padx=20, pady=(10, 20))
        stats.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        
        self.stat_monthly = self._create_stat_card(stats, 0, "WPŁYWY (MIESIĄC)", COLORS["paid"])
        self.stat_yearly = self._create_stat_card(stats, 1, "WPŁYWY (ROK)", COLORS["money"])
        self.stat_pending = self._create_stat_card(stats, 2, "ZALEGŁOŚCI (MIESIĄC)", COLORS["unpaid"])
        self.stat_balance = self._create_stat_card(stats, 3, "SALDO NADPŁAT", COLORS["accent"])
        # HYBRYDA: wpływy tej drużyny vs całego klubu w danym miesiącu
        self.stat_club = self._create_stat_card(stats, 4, "KLUB ŁĄCZNIE (MIES.)", COLORS["money"])
    
    def _create_stat_card(self, parent, col, title, color):
        card = ctk.CTkFrame(parent, fg_color=COLORS["card_bg"], corner_radius=12)
        card.grid(row=0, column=col, padx=8, pady=5, sticky="nsew")
        ctk.CTkLabel(card, text=title, font=("Segoe UI", 10, "bold"), text_color=COLORS["text_gray"]).pack(pady=(10, 0))
        label = ctk.CTkLabel(card, text="0 PLN", font=("Segoe UI", 22, "bold"), text_color=color)
        label.pack(pady=(0, 10))
        return label
    
    # =============================================
    # DATA LOADING
    # =============================================
    
    def load_data(self):
        if self._loading:
            self._reload_pending = True
            return
        self._loading = True
        self._show_loading()
        
        def fetch():
            try:
                from cache_manager import cache
                self.players_data = cache.get_players(force_refresh=False)
                self.finances_data = cache.get_finances(year=self.current_year, force_refresh=False)
                # KLUBOWE: składka jest jedna na gracza niezależnie od drużyny
                self.all_finances_data = cache.get_all_finances_club(force_refresh=False)
                self.club_settings = cache.get_club_settings(force_refresh=False)
                self.fee_history = cache.get_fee_history(force_refresh=False)
                self.after(0, self._display_players)
                # Odświeżenie w tle - RAZ na wejście, poza pierwszym ładowaniem
                self.after(0, self._background_refresh)
            except Exception as e:
                logger.error(f"Finanse - błąd: {e}")
                self.after(0, lambda: self._show_error(str(e)))
            finally:
                self._loading = False
                if self._reload_pending:
                    self._reload_pending = False
                    self.after(0, self.load_data)
        
        self._executor.submit(fetch)
    
    def _background_refresh(self):
        """Odświeżenie danych w tle - nie blokuje UI i nie duplikuje zapytań."""
        try:
            from cache_manager import cache
            cache.preload_finances()
        except Exception as e:
            logger.debug(f"Finanse - preload w tle: {e}")

    def _force_refresh(self):
        if self._loading:
            self._reload_pending = True
            return
        self._loading = True
        self._show_loading()
        
        def refresh():
            try:
                from cache_manager import cache
                cache.invalidate_finances()
                cache.invalidate_players()
                self.players_data = cache.get_players(force_refresh=True)
                self.finances_data = cache.get_finances(year=self.current_year, force_refresh=True)
                self.all_finances_data = cache.get_all_finances_club(force_refresh=True)
                self.club_settings = cache.get_club_settings(force_refresh=True)
                self.fee_history = cache.get_fee_history(force_refresh=True)
                self.after(0, self._display_players)
            except Exception as e:
                logger.error(f"Finanse - błąd refresh: {e}")
                self.after(0, lambda: self._show_error(str(e)))
            finally:
                self._loading = False
                if self._reload_pending:
                    self._reload_pending = False
                    self.after(0, self.load_data)
        self._executor.submit(refresh)
    
    # =============================================
    # DISPLAY (LAZY LOADING)
    # =============================================
    
    def _display_players(self):
        """Wyświetla listę - STABILNA WERSJA (bez skakania)"""
        self._loading = False
        
        # Mapa finansów
        month_finances = {
            f['player_id']: f
            for f in self.finances_data
            if f.get('month') == self.selected_month
        }
        
        # Filtruj i sortuj
        players = self._filter_players(self.players_data, month_finances)
        players.sort(key=lambda x: x.get('full_name', '').lower())
        
        # Wyczyść WSZYSTKO (eliminuje skakanie)
        for w in self.scroll_frame.winfo_children():
            w.destroy()
        
        if not players:
            ctk.CTkLabel(self.scroll_frame, text="Brak wyników", text_color="gray").pack(pady=50)
            self._update_stats(0, 0, 0, 0)
            return
        
        # Nagłówek
        self.header_row = self._create_list_header()
        
        # Renderuj wiersze batch po batch (płynnie)
        self._players_to_render = players
        self._month_finances = month_finances
        self._render_index = 0
        self._render_finance_batch()

    def _render_finance_batch(self):
        """Renderuje 5 graczy co 10ms - płynne bez skakania"""
        if not self.winfo_exists():
            return
        
        batch_size = 5
        end = min(self._render_index + batch_size, len(self._players_to_render))
        
        for i in range(self._render_index, end):
            player = self._players_to_render[i]
            status = self._calculate_player_status(player, self._month_finances)
            
            row = ctk.CTkFrame(self.scroll_frame, fg_color=COLORS["card_lighter"], corner_radius=10)
            row.pack(fill="x", padx=5, pady=3)
            self._fill_player_row(row, player, status)
        
        self._render_index = end
        
        if self._render_index < len(self._players_to_render):
            self.after(10, self._render_finance_batch)
        else:
            # Przelicz statystyki po zakończeniu renderowania
            self._recalc_stats(self._players_to_render, self._month_finances)

    def _fill_player_row(self, row, player, status):
        """Wypełnia wiersz widgetami"""
        ctk.CTkLabel(row, text=str(player.get('jersey_number', '-')), width=50, font=("Segoe UI", 13, "bold"), text_color=COLORS["accent"]).pack(side="left", padx=5, pady=10)
        ctk.CTkLabel(row, text=player.get('full_name', '?'), width=180, anchor="w", font=("Segoe UI", 13)).pack(side="left", padx=5)
        ctk.CTkLabel(row, text=f"{safe_int(status['fee'])} zł", width=80, font=("Segoe UI", 12), text_color=COLORS["money"]).pack(side="left", padx=5)
        
        if status['is_exempt']: st_text, st_color = "⛱️ WOLNY", COLORS["exempt"]
        elif status['is_paid']: st_text, st_color = "✅ OPŁACONY", COLORS["paid"]
        elif not status['should_pay']: st_text, st_color = "➖ N/D", COLORS["text_gray"]
        else: st_text, st_color = "❌ BRAK", COLORS["unpaid"]
        
        ctk.CTkLabel(row, text=st_text, width=120, font=("Segoe UI", 12, "bold"), text_color=st_color).pack(side="left", padx=5)
        
        arr = status['arrears_months']
        if arr > 0: arr_text, arr_color = f"-{arr} ({safe_int(status['arrears_amount'])} zł)", COLORS["unpaid"]
        else: arr_text, arr_color = "OK", COLORS["paid"]
        
        ctk.CTkLabel(row, text=arr_text, width=120, font=("Segoe UI", 12, "bold"), text_color=arr_color).pack(side="left", padx=5)
        
        bal = status['balance']
        bal_text = f"+{safe_int(bal)} zł" if bal > 0 else "0 zł"
        bal_color = COLORS["accent"] if bal > 0 else COLORS["text_gray"]
        ctk.CTkLabel(row, text=bal_text, width=80, font=("Segoe UI", 12), text_color=bal_color).pack(side="left", padx=5)
        
        btn_frame = ctk.CTkFrame(row, fg_color="transparent")
        btn_frame.pack(side="right", padx=10)
        ctk.CTkButton(btn_frame, text="💰", width=35, height=30, fg_color=COLORS["paid"], hover_color="#248a5e", command=lambda p=player: self._show_payment_modal(p)).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="🗑️", width=35, height=30, fg_color=COLORS["danger"], hover_color="#c0392b", command=lambda p=player: self._show_delete_modal(p)).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="⚙️", width=35, height=30, fg_color="#444", hover_color="#555", command=lambda p=player: self._show_player_settings(p)).pack(side="left", padx=2)

    def _show_empty_state(self, message):
        for w in self.scroll_frame.winfo_children(): w.destroy()
        ctk.CTkLabel(self.scroll_frame, text=message, text_color="gray").pack(pady=50)
        self._update_stats(0, 0, 0, 0)
    
    def _update_stats(self, monthly, yearly, pending, balance, club_monthly=None):
        self.stat_monthly.configure(text=f"{safe_int(monthly)} PLN")
        self.stat_yearly.configure(text=f"{safe_int(yearly)} PLN")
        self.stat_pending.configure(text=f"{safe_int(pending)} PLN")
        self.stat_balance.configure(text=f"{safe_int(balance)} PLN")
        if hasattr(self, 'stat_club'):
            if club_monthly is None:
                club_monthly = 0
            self.stat_club.configure(text=f"{safe_int(club_monthly)} PLN")
    
    def _filter_players(self, players, month_finances):
        result = players.copy()
        query = self.search_var.get().lower().strip()
        if query: result = [p for p in result if query in p.get('full_name', '').lower()]
        
        filter_type = self.filter_var.get()
        if filter_type != "all":
            filtered = []
            for p in result:
                status = self._calculate_player_status(p, month_finances)
                if filter_type == "paid" and status['is_paid']: filtered.append(p)
                elif filter_type == "unpaid" and status['should_pay'] and not status['is_paid'] and not status['is_exempt']: filtered.append(p)
            result = filtered
        return result
    
    def _recalc_stats(self, players, month_finances):
        """Przelicza statystyki po załadowaniu listy"""
        total_monthly = 0
        total_pending_month = 0
        total_balance = 0
        
        for player in players:
            status = self._calculate_player_status(player, month_finances)
            if status['is_paid']: total_monthly += status['amount_paid']
            elif status['should_pay'] and not status['is_exempt']: total_pending_month += status['fee']
            total_balance += safe_float(player.get('balance'), 0)
        
        total_yearly = sum([safe_float(f.get('amount'), 0) for f in self.finances_data if f.get('is_paid')])

        # HYBRYDA: ile zarobiŁ CAŁY KLUB w tym miesiącu (dane klubowe,
        # niezależnie od drużyny), żeby kierownik widział pełny obraz.
        club_monthly = sum([
            safe_float(f.get('amount'), 0)
            for f in self.all_finances_data
            if f.get('is_paid')
            and f.get('year') == self.current_year
            and f.get('month') == self.selected_month])

        self._update_stats(total_monthly, total_yearly, total_pending_month,
                           total_balance, club_monthly)

    # =============================================
    # HELPER METHODS (zoptymalizowane)
    # =============================================
    
    def _get_default_fee(self):
        return safe_float(self.club_settings.get('default_fee'), 100.0)
    
    def _get_player_fee(self, player, for_date=None):
        individual = player.get('monthly_fee')
        if individual is not None:
            val = safe_float(individual, 0)
            if val > 0: return val
        
        if for_date and self.fee_history:
            for record in self.fee_history:
                eff_from = self._parse_date(record.get('effective_from', '2000-01-01'))
                eff_to = record.get('effective_to')
                if eff_to:
                    eff_to = self._parse_date(eff_to)
                    if eff_from <= for_date <= eff_to: return safe_float(record.get('fee_amount'), 100)
                else:
                    if for_date >= eff_from: return safe_float(record.get('fee_amount'), 100)
        return self._get_default_fee()
    
    def _get_fee_start_date(self, player):
        if player.get('fee_start_date'): return self._parse_date(player['fee_start_date'])
        join = player.get('join_date') or player.get('created_at')
        if join:
            join_date = self._parse_date(join)
            return join_date.replace(day=1) + relativedelta(months=1)
        return date(2024, 9, 1)
    
    def _parse_date(self, date_str):
        if isinstance(date_str, date): return date_str
        if isinstance(date_str, datetime): return date_str.date()
        if isinstance(date_str, str):
            try: return datetime.strptime(date_str[:10], '%Y-%m-%d').date()
            except: pass
        return date.today()
    
    def _get_exempt_months(self, player):
        exempt_str = player.get('exempt_months', '') or ''
        if not exempt_str: return []
        try: return [int(m.strip()) for m in str(exempt_str).split(',') if m.strip()]
        except: return []
    
    def _setup_modal_geometry(self, modal, width, height):
        """Dynamicznie oblicza rozmiar i wyśrodkowuje okno"""
        modal.update_idletasks()
        screen_w = modal.winfo_screenwidth()
        screen_h = modal.winfo_screenheight()
        
        # Max wysokość to 90% ekranu
        final_h = min(height, int(screen_h * 0.9))
        
        # Oblicz środek
        x = (screen_w - width) // 2
        y = (screen_h - final_h) // 2
        
        modal.geometry(f"{width}x{final_h}+{x}+{y}")
    
    def _should_pay_for_month(self, player, year, month):
        check_date = date(year, month, 1)
        
        # 1. Sprawdź start (przed dołączeniem nie płaci)
        fee_start = self._get_fee_start_date(player)
        if check_date < fee_start.replace(day=1): return False
        
        # 2. Sprawdź koniec (po odejściu nie płaci)
        fee_end = player.get('fee_end_date')
        if fee_end:
            if check_date > self._parse_date(fee_end): return False
        
        # 3. Sprawdź miesiące wolne cykliczne (np. lipiec co roku)
        exempt_str = str(player.get('exempt_months', '') or '')
        exempt_list = exempt_str.split(',')
        if str(month) in exempt_list: return False
        
        # 4. Sprawdź zwolnienie czasowe (NOWOŚĆ)
        ex_from = player.get('exempt_from')
        ex_until = player.get('exempt_until')
        
        if ex_from and ex_until:
            d_from = self._parse_date(ex_from).replace(day=1)
            d_until = self._parse_date(ex_until)
            # Jeśli data mieści się w przedziale
            if d_from <= check_date <= d_until:
                return False
        
        return True
    
    def _calculate_player_status(self, player, month_finances):
        player_id = player['id']
        check_date = date(self.current_year, self.selected_month, 1)
        fee = self._get_player_fee(player, for_date=check_date)
        finance_record = month_finances.get(player_id, {})
        
        should_pay = self._should_pay_for_month(player, self.current_year, self.selected_month)
        is_paid = finance_record.get('is_paid', False)
        is_exempt = finance_record.get('is_exempt', False) or (self.selected_month in self._get_exempt_months(player))
        amount_paid = safe_float(finance_record.get('amount'), 0) if is_paid else 0
        
        # --- FIX: Definiuj amount_due PRZED return ---
        amount_due = fee if (should_pay and not is_paid and not is_exempt) else 0
        
        arrears_months, arrears_amount = self._calculate_arrears_cached(player)
        
        return {
            'should_pay': should_pay, 'is_paid': is_paid, 'is_exempt': is_exempt,
            'amount_paid': amount_paid, 'fee': fee,
            'amount_due': amount_due,
            'arrears_months': arrears_months, 'arrears_amount': arrears_amount,
            'balance': safe_float(player.get('balance'), 0)
        }
    
    def _calculate_arrears_cached(self, player):
        fee_start = self._get_fee_start_date(player)
        until_date = date(self.current_year, self.selected_month, 1)
        if until_date < fee_start.replace(day=1): return 0, 0
        
        paid_set = set()
        for f in self.all_finances_data:
            if f.get('player_id') == player['id'] and f.get('is_paid'):
                paid_set.add((f.get('year'), f.get('month')))
        
        arrears_count = 0
        arrears_total = 0.0
        check_date = fee_start.replace(day=1)
        while check_date <= until_date:
            year, month = check_date.year, check_date.month
            if self._should_pay_for_month(player, year, month):
                if (year, month) not in paid_set:
                    month_fee = self._get_player_fee(player, for_date=check_date)
                    arrears_count += 1
                    arrears_total += month_fee
            check_date += relativedelta(months=1)
        return arrears_count, arrears_total
    
    def _create_list_header(self):
        header = ctk.CTkFrame(self.scroll_frame, fg_color=COLORS["card_lighter"], corner_radius=8)
        header.pack(fill="x", padx=5, pady=(5, 10))
        for text, width in [("Nr", 50), ("Zawodnik", 180), ("Składka", 80), ("Status", 120), ("Zaległości", 120), ("Saldo", 80), ("Akcje", 140)]:
            ctk.CTkLabel(header, text=text, width=width, font=("Segoe UI", 11, "bold"), text_color=COLORS["text_gray"]).pack(side="left", padx=5, pady=8)
        return header

    # =============================================
    # EVENT HANDLERS
    # =============================================
    
    def _on_date_change(self, _=None):
        self.selected_month = MONTHS_PL.index(self.month_menu.get()) + 1
        self.current_year = int(self.year_menu.get())
        self.load_data()
    
    def refresh_data(self):
        """
        Wywoływane przez MainApp przy ponownym wejściu na zakładkę
        (i przy przełączaniu drużyny). Bez tego widok wracał z danymi
        sprzed godziny, bo Finanse nie miały refresh_data() - main.py
        szuka w kolejności refresh_data / refresh_data_async.
        """
        self.load_data()

    def on_team_changed(self):
        """Wywoływane przez MainApp po zmianie drużyny w sidebarze."""
        self.load_data()

    def on_season_changed(self, season):
        """
        Wywoływane przez MainApp po zmianie sezonu w pasku bocznym.

        FIX: widok trzymał własny rok/miesiąc ustawiony w __init__, więc
        zmiana sezonu w sidebarze NIE zmieniała danych finansów - zostawały
        dane roku kalendarzowego z momentu uruchomienia aplikacji.
        """
        import database as db
        year, month = db.get_season_anchor(season)
        self.current_year = year
        self.selected_month = month
        try:
            years = [str(y) for y in range(2024, datetime.now().year + 2)]
            if str(year) not in years:
                years.append(str(year))
                years.sort()
            self.year_menu.configure(values=years)
            self.year_menu.set(str(year))
            self.month_menu.set(MONTHS_PL[month - 1])
        except Exception as e:
            logger.error(f"Finanse - nie udało się ustawić okresu: {e}")
        self._reload_pending = False
        self.load_data()

    def _on_search(self, *args):
        if self.search_timer: self.after_cancel(self.search_timer)
        self.search_timer = self.after(300, self._display_players)
    
    # =============================================
    # MODALS & EXPORT
    # =============================================
    
    def _show_delete_modal(self, player):
        modal = ctk.CTkToplevel(self)
        modal.title(f"🗑️ Usuń składki")
        modal.attributes("-topmost", True)
        self._setup_modal_geometry(modal, 450, 480) # <--- To wystarczy
        modal.transient(self)
        modal.grab_set()
        
        
        content = ctk.CTkFrame(modal, fg_color="transparent")
        content.grid(row=0, column=0, sticky="nsew", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(content, text="🗑️ Usuń składki", font=("Segoe UI", 20, "bold"), text_color=COLORS["danger"]).pack(anchor="w")
        ctk.CTkLabel(content, text=f"Zawodnik: {player.get('full_name', 'Nieznany')}", font=("Segoe UI", 14)).pack(anchor="w", pady=(0, 20))
        
        delete_var = ctk.StringVar(value="current")
        ctk.CTkLabel(content, text="Co chcesz usunąć?", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(10, 10))
        ctk.CTkRadioButton(content, text=f"Tylko {MONTHS_PL[self.selected_month-1]} {self.current_year}", variable=delete_var, value="current").pack(anchor="w", pady=5)
        
        range_frame = ctk.CTkFrame(content, fg_color="transparent")
        range_frame.pack(anchor="w", pady=5, fill="x")
        ctk.CTkRadioButton(range_frame, text="Wybrany miesiąc:", variable=delete_var, value="specific").pack(side="left")
        specific_month = ctk.CTkOptionMenu(range_frame, values=MONTHS_PL, width=120); specific_month.pack(side="left", padx=10)
        specific_year = ctk.CTkOptionMenu(range_frame, values=[str(y) for y in range(2024, datetime.now().year + 2)], width=80); specific_year.pack(side="left", padx=5)
        
        ctk.CTkRadioButton(content, text=f"Cały rok {self.current_year}", variable=delete_var, value="year").pack(anchor="w", pady=5)
        ctk.CTkRadioButton(content, text="🚨 WSZYSTKIE składki", variable=delete_var, value="all", text_color=COLORS["danger"]).pack(anchor="w", pady=5)
        
        btn_frame = ctk.CTkFrame(modal, fg_color="transparent")
        btn_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(10, 20))
        
        def confirm_delete():
            # FIX: usuwanie składek to operacja sieciowa - wątek GUI
            choice = delete_var.get()
            if not msgbox.askyesno("Potwierdzenie", "Czy na pewno chcesz usunąć wybrane składki?\nTej operacji nie można cofnąć."): return

            def _work():
                query = supabase.table('finances').delete().eq('player_id', player['id'])
                if choice == "current": query = query.eq('year', self.current_year).eq('month', self.selected_month)
                elif choice == "specific": query = query.eq('year', int(specific_year.get())).eq('month', MONTHS_PL.index(specific_month.get())+1)
                elif choice == "year": query = query.eq('year', self.current_year)
                query.execute()

            def _ok(_result=None):
                from cache_manager import cache
                cache.invalidate_finances()
                try: modal.destroy()
                except Exception: pass
                msgbox.showinfo("Sukces", "Usunięto składki.")
                self._force_refresh()

            run_async(self, _work, on_success=_ok,
                      on_error=lambda e: msgbox.showerror("Błąd", str(e)))
        
        ctk.CTkButton(btn_frame, text="Anuluj", width=140, height=45, fg_color="#444", command=modal.destroy).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="🗑️ Potwierdź usunięcie", width=200, height=45, fg_color=COLORS["danger"], hover_color="#c0392b", command=confirm_delete).pack(side="right", padx=10)

    def _show_payment_modal(self, player):
        modal = ctk.CTkToplevel(self)
        modal.title(f"💰 Wpłata")
        modal.attributes("-topmost", True)
        self._setup_modal_geometry(modal, 500, 700) # <--- To wystarczy
        modal.transient(self)
        modal.grab_set()
        
        
        
        content = ctk.CTkScrollableFrame(modal, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        # NAGŁÓWEK ZAWODNIKA
        header_frame = ctk.CTkFrame(content, fg_color=COLORS["card_bg"], corner_radius=10)
        header_frame.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(
            header_frame, 
            text=f"👤 {player.get('full_name', 'Zawodnik')}", 
            font=("Segoe UI", 20, "bold"),
            text_color=COLORS["accent"]
        ).pack(anchor="w", padx=15, pady=(15, 5))
        
        # Informacje o stanie konta
        fee = self._get_player_fee(player, for_date=date(self.current_year, self.selected_month, 1))
        arrears, arr_amt = self._calculate_arrears_cached(player)
        balance = safe_float(player.get('balance'), 0)
        
        info_grid = ctk.CTkFrame(header_frame, fg_color="transparent")
        info_grid.pack(fill="x", padx=15, pady=(0, 15))
        
        # Kolumny info
        def add_info(parent, title, val, color):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.pack(side="left", expand=True)
            ctk.CTkLabel(f, text=title, font=("Segoe UI", 10), text_color=COLORS["text_gray"]).pack()
            ctk.CTkLabel(f, text=val, font=("Segoe UI", 14, "bold"), text_color=color).pack()

        add_info(info_grid, "SKŁADKA", f"{safe_int(fee)} zł", COLORS["money"])
        add_info(info_grid, "ZALEGŁOŚCI", f"{arrears} ({safe_int(arr_amt)} zł)", COLORS["unpaid"])
        add_info(info_grid, "SALDO", f"{safe_int(balance)} zł", COLORS["accent"])
        
        # --- OPCJA 1: KWOTA ---
        ctk.CTkLabel(content, text="OPCJA 1: WPISZ KWOTĘ", font=("Segoe UI", 12, "bold"), text_color=COLORS["text_gray"]).pack(anchor="w", pady=(10, 5))
        
        amount_frame = ctk.CTkFrame(content, fg_color=COLORS["card_bg"], corner_radius=10)
        amount_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(amount_frame, text="Kwota:", font=("Segoe UI", 12)).pack(side="left", padx=15, pady=15)
        amount_entry = ctk.CTkEntry(amount_frame, width=120, placeholder_text="np. 500", font=("Segoe UI", 14))
        amount_entry.pack(side="left", padx=5)
        ctk.CTkLabel(amount_frame, text="PLN", font=("Segoe UI", 12, "bold")).pack(side="left", padx=5)
        
        # Podgląd
        preview_frame = ctk.CTkFrame(content, fg_color="#252525", corner_radius=8)
        preview_frame.pack(fill="x", pady=10)
        
        preview_label = ctk.CTkLabel(
            preview_frame,
            text="Wprowadź kwotę, aby zobaczyć podgląd...",
            font=("Segoe UI", 11),
            text_color=COLORS["text_gray"],
            justify="left",
            wraplength=400
        )
        preview_label.pack(padx=15, pady=15, anchor="w", fill="x")
        
        def update_preview(*args):
            try:
                amt = safe_float(amount_entry.get(), 0)
                if amt <= 0:
                    preview_label.configure(text="Wprowadź kwotę, aby zobaczyć podgląd...")
                    return
                
                res = self._calculate_payment_distribution(player, amt)
                
                txt = "📊 PLAN ROZLICZENIA:\n\n"
                for m in res['months'][:6]:
                    txt += f"✅ {MONTHS_PL[m['month']-1]} {m['year']} - {safe_int(m['amount'])} zł\n"
                
                if len(res['months']) > 6:
                    txt += f"... i {len(res['months'])-6} więcej\n"
                
                if res['remaining_balance'] > 0:
                    txt += f"\n💰 Saldo końcowe: +{safe_int(res['remaining_balance'])} zł"
                
                txt += f"\n\nSUMA: {safe_int(amt)} zł ({len(res['months'])} mies.)"
                preview_label.configure(text=txt)
            except: pass
            
        amount_entry.bind("<KeyRelease>", update_preview)
        
        # SEPARATOR
        ctk.CTkFrame(content, height=2, fg_color="#333").pack(fill="x", pady=20)
        
        # --- OPCJA 2: MIESIĄCE ---
        ctk.CTkLabel(content, text="OPCJA 2: LICZBA MIESIĘCY", font=("Segoe UI", 12, "bold"), text_color=COLORS["text_gray"]).pack(anchor="w", pady=(0, 5))
        
        mon_frame = ctk.CTkFrame(content, fg_color=COLORS["card_bg"], corner_radius=10)
        mon_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(mon_frame, text="Ile miesięcy:", font=("Segoe UI", 12)).pack(side="left", padx=15, pady=15)
        mon_entry = ctk.CTkEntry(mon_frame, width=60, placeholder_text="3", font=("Segoe UI", 14))
        mon_entry.pack(side="left", padx=5)
        
        mon_lbl = ctk.CTkLabel(mon_frame, text="= ? zł", font=("Segoe UI", 14, "bold"), text_color=COLORS["money"])
        mon_lbl.pack(side="left", padx=15)
        
        def upd_mon(*args):
            try:
                mon_val = safe_int(mon_entry.get())
                mon_lbl.configure(text=f"= {safe_int(mon_val * fee)} zł")
            except: pass
        mon_entry.bind("<KeyRelease>", upd_mon)
        
        # NOTATKA
        ctk.CTkLabel(content, text="Notatka (opcjonalnie):", font=("Segoe UI", 12)).pack(anchor="w", pady=(20, 5))
        note_entry = ctk.CTkEntry(content, placeholder_text="np. Przelew z dnia 15.01.2025", height=35)
        note_entry.pack(fill="x", pady=5)
        
        # PRZYCISKI
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x", pady=30)
        
        def save():
            amt = safe_float(amount_entry.get(), 0)
            mons = safe_int(mon_entry.get(), 0)
            
            if amt <= 0 and mons <= 0:
                msgbox.showwarning("Uwaga", "Podaj kwotę lub liczbę miesięcy!")
                return
            
            if mons > 0 and amt <= 0:
                amt = mons * fee
            
            res = self._process_payment(player, amt, note_entry.get())
            if res['success']:
                modal.destroy()
                msgbox.showinfo("Sukces", f"✅ Zapisano wpłatę {safe_int(amt)} zł")
                self._force_refresh()
            else:
                msgbox.showerror("Błąd", res['error'])
        
        ctk.CTkButton(
            btn_frame, text="Anuluj", width=120, height=45, 
            fg_color="#444", hover_color="#555",
            command=modal.destroy
        ).pack(side="left")
        
        ctk.CTkButton(
            btn_frame, text="✓ Zapisz wpłatę", width=200, height=45, 
            fg_color=COLORS["paid"], hover_color="#248a5e", 
            font=("Segoe UI", 14, "bold"),
            command=save
        ).pack(side="right")

    def _calculate_payment_distribution(self, player, amount):
        fee_start = self._get_fee_start_date(player)
        balance = safe_float(player.get('balance'), 0)
        total_amount = amount + balance
        months_to_pay = []
        current_date = fee_start.replace(day=1)
        end_date = date.today() + relativedelta(months=36)
        
        while current_date <= end_date and total_amount > 0:
            year, month = current_date.year, current_date.month
            if self._should_pay_for_month(player, year, month):
                is_paid = any(f.get('player_id')==player['id'] and f.get('year')==year and f.get('month')==month and f.get('is_paid') for f in self.all_finances_data)
                if not is_paid:
                    month_fee = self._get_player_fee(player, for_date=current_date)
                    if total_amount >= month_fee:
                        months_to_pay.append({'year': year, 'month': month, 'amount': month_fee, 'paid': True})
                        total_amount -= month_fee
                    else: break
            current_date += relativedelta(months=1)
        return {'months': months_to_pay, 'remaining_balance': max(0, total_amount)}

    def _process_payment(self, player, amount, note=""):
        try:
            dist = self._calculate_payment_distribution(player, amount)
            for item in dist['months']:
                # HYBRYDA: jedna składka, ale wpłata przypisana do drużyny,
                # w której gracz wtedy grał -> raport per drużyna działa,
                # a gracz nie płaci dwa razy.
                data = {'player_id': player['id'], 'year': item['year'], 'month': item['month'], 'is_paid': True, 'amount': safe_int(item['amount']), 'paid_date': date.today().isoformat(), 'payment_note': note, 'club_name': database.CURRENT_CLUB, 'team_code': teams.get_current_team()}
                supabase.table('finances').upsert(data, on_conflict="player_id,year,month").execute()
            
            supabase.table('players').update({'balance': safe_int(dist['remaining_balance'])}).eq('id', player['id']).execute()
            from cache_manager import cache
            cache.invalidate_finances()
            return {'success': True}
        except Exception as e: return {'success': False, 'error': str(e)}

    def _show_player_settings(self, player):
        modal = ctk.CTkToplevel(self)
        modal.title(f"⚙️ Ustawienia - {player.get('full_name', 'Zawodnik')}")
        modal.attributes("-topmost", True)
        # ZAMIEŃ STARE GEOMETRY NA TO:
        self._setup_modal_geometry(modal, 500, 800)
        modal.transient(self)
        modal.grab_set()
        
        
        
        content = ctk.CTkScrollableFrame(modal, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(content, text=f"👤 {player.get('full_name', 'Zawodnik')}", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(0, 20))
        
        # --- 1. SKŁADKA INDYWIDUALNA ---
        # ... (kod bez zmian) ...
        card1 = ctk.CTkFrame(content, fg_color=COLORS["card_bg"], corner_radius=10)
        card1.pack(fill="x", pady=5)
        ctk.CTkLabel(card1, text="Indywidualna składka:", font=("Segoe UI", 12)).pack(anchor="w", padx=15, pady=(15, 5))
        fee_entry = ctk.CTkEntry(card1, width=120, placeholder_text=f"Domyślnie: {safe_int(self._get_default_fee())}")
        fee_entry.pack(anchor="w", padx=15, pady=(0, 15))
        if player.get('monthly_fee'): fee_entry.insert(0, str(safe_int(player['monthly_fee'])))

        # --- 2. DATA STARTU SKŁADEK ---
        # ... (kod bez zmian) ...
        card_date = ctk.CTkFrame(content, fg_color=COLORS["card_bg"], corner_radius=10)
        card_date.pack(fill="x", pady=10)
        ctk.CTkLabel(card_date, text="Naliczaj składki od:", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        date_inner = ctk.CTkFrame(card_date, fg_color="transparent")
        date_inner.pack(fill="x", padx=10, pady=(0, 15))
        current_start = self._get_fee_start_date(player)
        start_month_menu = ctk.CTkOptionMenu(date_inner, values=MONTHS_PL, width=110)
        start_month_menu.set(MONTHS_PL[current_start.month - 1]); start_month_menu.pack(side="left", padx=5)
        start_year_menu = ctk.CTkOptionMenu(date_inner, values=[str(y) for y in range(2023, datetime.now().year + 3)], width=80)
        start_year_menu.set(str(current_start.year)); start_year_menu.pack(side="left", padx=5)

        # --- 3. MIESIĄCE WOLNE (CYKLICZNE) ---
        # ... (kod bez zmian) ...
        card2 = ctk.CTkFrame(content, fg_color=COLORS["card_bg"], corner_radius=10)
        card2.pack(fill="x", pady=5)
        ctk.CTkLabel(card2, text="Miesiące wolne (Cykliczne, np. wakacje):", font=("Segoe UI", 12)).pack(anchor="w", padx=15, pady=(15, 5))
        grid_frame = ctk.CTkFrame(card2, fg_color="transparent")
        grid_frame.pack(fill="x", padx=10, pady=(0, 15))
        exempt_vars = {}
        current_exempt_str = str(player.get('exempt_months', '') or '')
        current_exempt_list = current_exempt_str.split(',')
        for i, m in enumerate(MONTHS_PL):
            var = ctk.BooleanVar(value=str(i+1) in current_exempt_list)
            exempt_vars[i+1] = var
            row, col = i // 3, i % 3
            ctk.CTkCheckBox(grid_frame, text=m[:3], variable=var, width=60).grid(row=row, column=col, padx=5, pady=5, sticky="w")

        # --- 4. ZWOLNIENIE CZASOWE (NOWOŚĆ) ---
        card_temp = ctk.CTkFrame(content, fg_color=COLORS["card_bg"], corner_radius=10)
        card_temp.pack(fill="x", pady=10)
        
        ctk.CTkLabel(card_temp, text="Zwolnienie czasowe (np. kontuzja/trudna sytuacja):", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        
        # Checkbox "Aktywne zwolnienie"
        has_exemption = bool(player.get('exempt_from'))
        is_exempt_var = ctk.BooleanVar(value=has_exemption)
        
        def toggle_exempt_dates():
            state = "normal" if is_exempt_var.get() else "disabled"
            ex_from_m.configure(state=state)
            ex_from_y.configure(state=state)
            ex_until_m.configure(state=state)
            ex_until_y.configure(state=state)
            
        ctk.CTkCheckBox(card_temp, text="Włącz zwolnienie w okresie:", variable=is_exempt_var, command=toggle_exempt_dates).pack(anchor="w", padx=15, pady=5)
        
        # Data OD
        f_from = ctk.CTkFrame(card_temp, fg_color="transparent")
        f_from.pack(fill="x", padx=10)
        ctk.CTkLabel(f_from, text="Od:", width=30).pack(side="left")
        ex_from_m = ctk.CTkOptionMenu(f_from, values=MONTHS_PL, width=110); ex_from_m.pack(side="left", padx=5)
        ex_from_y = ctk.CTkOptionMenu(f_from, values=[str(y) for y in range(2024, 2030)], width=80); ex_from_y.pack(side="left", padx=5)
        
        # Data DO
        f_until = ctk.CTkFrame(card_temp, fg_color="transparent")
        f_until.pack(fill="x", padx=10, pady=(5, 15))
        ctk.CTkLabel(f_until, text="Do:", width=30).pack(side="left")
        ex_until_m = ctk.CTkOptionMenu(f_until, values=MONTHS_PL, width=110); ex_until_m.pack(side="left", padx=5)
        ex_until_y = ctk.CTkOptionMenu(f_until, values=[str(y) for y in range(2024, 2030)], width=80); ex_until_y.pack(side="left", padx=5)
        
        # Ustawienie wartości początkowych
        if has_exemption:
            d_from = self._parse_date(player['exempt_from'])
            d_until = self._parse_date(player['exempt_until'])
            ex_from_m.set(MONTHS_PL[d_from.month-1]); ex_from_y.set(str(d_from.year))
            ex_until_m.set(MONTHS_PL[d_until.month-1]); ex_until_y.set(str(d_until.year))
        else:
            toggle_exempt_dates() # Wyłącz na start

        # --- 5. SALDO ---
        # ... (kod bez zmian) ...
        card3 = ctk.CTkFrame(content, fg_color=COLORS["card_bg"], corner_radius=10)
        card3.pack(fill="x", pady=5)
        ctk.CTkLabel(card3, text="Korekta salda (nadpłata):", font=("Segoe UI", 12)).pack(anchor="w", padx=15, pady=(15, 5))
        balance_entry = ctk.CTkEntry(card3, width=120)
        balance_entry.pack(anchor="w", padx=15, pady=(0, 15))
        balance_entry.insert(0, str(safe_int(player.get('balance', 0))))
        
        # Przyciski
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x", pady=30)
        
        def save():
            try:
                new_fee = safe_int(fee_entry.get()) if fee_entry.get() else None
                new_bal = safe_int(balance_entry.get())
                
                # Cykliczne
                exempt_list = [str(k) for k,v in exempt_vars.items() if v.get()]
                exempt = ",".join(exempt_list)
                
                # Start
                s_month = MONTHS_PL.index(start_month_menu.get()) + 1
                s_year = int(start_year_menu.get())
                new_start_date = date(s_year, s_month, 1).isoformat()
                
                # Czasowe zwolnienie
                ex_from = None
                ex_until = None
                
                if is_exempt_var.get():
                    fm = MONTHS_PL.index(ex_from_m.get()) + 1
                    fy = int(ex_from_y.get())
                    tm = MONTHS_PL.index(ex_until_m.get()) + 1
                    ty = int(ex_until_y.get())
                    
                    ex_from = date(fy, fm, 1).isoformat()
                    # Do końca miesiąca
                    ex_until = (date(ty, tm, 1) + relativedelta(months=1) - relativedelta(days=1)).isoformat()
                
                update_data = {
                    'monthly_fee': new_fee,
                    'fee_start_date': new_start_date,
                    'exempt_months': exempt,
                    'exempt_from': ex_from,
                    'exempt_until': ex_until,
                    'balance': new_bal
                }
                
                supabase.table('players').update(update_data).eq('id', player['id']).execute()
                
                from cache_manager import cache
                cache.invalidate_players()
                cache.invalidate_finances()
                
                modal.destroy()
                msgbox.showinfo("Sukces", "Zapisano ustawienia!")
                self._force_refresh()
                
            except Exception as e:
                msgbox.showerror("Błąd", str(e))
            
        ctk.CTkButton(btn_frame, text="Anuluj", width=100, height=40, fg_color="#444", command=modal.destroy).pack(side="left")
        ctk.CTkButton(btn_frame, text="💾 Zapisz", width=150, height=40, fg_color=COLORS["paid"], font=("Segoe UI", 12, "bold"), command=save).pack(side="right")

    def _show_settings_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("⚙️ Ustawienia Finansów Klubu")
        modal.attributes("-topmost", True)
        self._setup_modal_geometry(modal, 500, 700) # <--- To wystarczy
        modal.transient(self)
        modal.grab_set()

        
        
        # =========================================================================
        # 1. PRZYCISKI (Tworzone i pakowane NAJPIERW na dół - gwarancja widoczności)
        # =========================================================================
        btn_frame = ctk.CTkFrame(modal, fg_color="transparent", height=80)
        btn_frame.pack(side="bottom", fill="x", padx=20, pady=20)
        
        # Definicja save (musi być dostępna dla przycisku)
        def save():
            try:
                # Pobieranie danych
                new_fee = safe_int(fee_entry.get())
                d = safe_int(day_entry.get(), 1)
                
                # Bezpieczne pobieranie daty
                try:
                    m = MONTHS_PL.index(eff_month_menu.get()) + 1
                    y = int(eff_year_menu.get())
                    eff_date = date(y, m, d)
                except:
                    eff_date = date(datetime.now().year, datetime.now().month, 1)
                
                # Dane do zapisu
                data = {
                    'club_name': database.CURRENT_CLUB,
                    'default_fee': new_fee,
                    'fee_effective_date': eff_date.isoformat(),
                    'bank_account': str(acc_entry.get()).strip(),
                    'bank_name': str(bank_entry.get()).strip(),
                    'updated_at': datetime.now().isoformat()
                }
                
                # Zapis do bazy
                supabase.table('club_settings').upsert(data, on_conflict="club_name").execute()
                
                # Historia (opcjonalnie)
                try:
                    supabase.table('fee_history').insert({
                        'club_name': database.CURRENT_CLUB,
                        'fee_amount': new_fee,
                        'effective_from': eff_date.isoformat()
                    }).execute()
                except: pass
                
                # Odświeżenie
                self.club_settings = data
                from cache_manager import cache
                cache.invalidate_finances()
                
                modal.destroy()
                msgbox.showinfo("Sukces", "Zapisano ustawienia!")
                self._force_refresh()
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                msgbox.showerror("Błąd", f"Nie udało się zapisać: {str(e)}")

        # Przyciski
        ctk.CTkButton(
            btn_frame, text="Anuluj", width=100, height=45, 
            fg_color="#444", hover_color="#555",
            command=modal.destroy
        ).pack(side="left")
        
        ctk.CTkButton(
            btn_frame, text="💾 Zapisz Zmiany", width=200, height=45, 
            fg_color=COLORS["paid"], hover_color="#248a5e", 
            font=("Segoe UI", 13, "bold"),
            command=save
        ).pack(side="right")

        # =========================================================================
        # 2. TREŚĆ (Pakowana na górę - zajmuje resztę miejsca)
        # =========================================================================
        content = ctk.CTkScrollableFrame(modal, fg_color="transparent")
        content.pack(side="top", fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(content, text="⚙️ Konfiguracja Klubu", font=("Segoe UI", 20, "bold")).pack(anchor="w", pady=(0, 20))
        
        # --- SEKCJA SKŁADKI ---
        card1 = ctk.CTkFrame(content, fg_color=COLORS["card_bg"], corner_radius=10)
        card1.pack(fill="x", pady=10)
        
        ctk.CTkLabel(card1, text="Domyślna składka miesięczna:", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        
        fee_box = ctk.CTkFrame(card1, fg_color="transparent")
        fee_box.pack(fill="x", padx=15, pady=(0, 15))
        
        fee_entry = ctk.CTkEntry(fee_box, width=100)
        fee_entry.pack(side="left")
        fee_entry.insert(0, str(safe_int(self._get_default_fee())))
        ctk.CTkLabel(fee_box, text="PLN").pack(side="left", padx=10)
        
        # Data obowiązywania
        ctk.CTkLabel(card1, text="Nowa kwota obowiązuje od:", font=("Segoe UI", 12)).pack(anchor="w", padx=15, pady=(5, 5))
        date_box = ctk.CTkFrame(card1, fg_color="transparent")
        date_box.pack(fill="x", padx=15, pady=(0, 15))
        
        day_entry = ctk.CTkEntry(date_box, width=40, placeholder_text="01")
        day_entry.insert(0, "01"); day_entry.pack(side="left")
        
        eff_month_menu = ctk.CTkOptionMenu(date_box, values=MONTHS_PL, width=110)
        eff_month_menu.pack(side="left", padx=5)
        
        eff_year_menu = ctk.CTkOptionMenu(date_box, values=[str(y) for y in range(2024, datetime.now().year + 2)], width=80)
        eff_year_menu.pack(side="left", padx=5)
        
        # Ustaw obecną datę (z zabezpieczeniem)
        curr_eff = self.club_settings.get('fee_effective_date')
        if curr_eff:
            try:
                d = self._parse_date(curr_eff)
                day_entry.delete(0, 'end'); day_entry.insert(0, str(d.day).zfill(2))
                eff_month_menu.set(MONTHS_PL[d.month-1])
                eff_year_menu.set(str(d.year))
            except: pass
        else:
            eff_month_menu.set(MONTHS_PL[datetime.now().month-1])
            eff_year_menu.set(str(datetime.now().year))

        # --- SEKCJA DANE BANKOWE (Z FIXEM TCL ERROR) ---
        card2 = ctk.CTkFrame(content, fg_color=COLORS["card_bg"], corner_radius=10)
        card2.pack(fill="x", pady=10)
        
        ctk.CTkLabel(card2, text="Dane do przelewu (do raportów PDF):", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=15, pady=(15, 10))
        
        # Nazwa Banku
        ctk.CTkLabel(card2, text="Nazwa Banku:", font=("Segoe UI", 11)).pack(anchor="w", padx=15)
        bank_entry = ctk.CTkEntry(card2, placeholder_text="np. PKO BP")
        bank_entry.pack(fill="x", padx=15, pady=(5, 10))
        
        # FIX: Bezpieczne wstawianie (zamiana None na "")
        bank_val = self.club_settings.get('bank_name')
        if bank_val is None: bank_val = ""
        bank_entry.insert(0, str(bank_val))
        
        # Numer Rachunku
        ctk.CTkLabel(card2, text="Numer Rachunku:", font=("Segoe UI", 11)).pack(anchor="w", padx=15)
        acc_entry = ctk.CTkEntry(card2, placeholder_text="XX XXXX ...")
        acc_entry.pack(fill="x", padx=15, pady=(5, 15))
        
        # FIX: Bezpieczne wstawianie
        acc_val = self.club_settings.get('bank_account')
        if acc_val is None: acc_val = ""
        acc_entry.insert(0, str(acc_val))

    def _show_export_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("📄 Export PDF")
        modal.attributes("-topmost", True)
        self._setup_modal_geometry(modal, 450, 500) # <--- To wystarczy
        modal.transient(self)
        modal.grab_set()
        
        
        content = ctk.CTkFrame(modal, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(content, text="📄 Generowanie Raportu", font=("Segoe UI", 18, "bold")).pack(pady=(0, 20))
        
        type_var = ctk.StringVar(value="monthly")
        
        ctk.CTkLabel(content, text="Wybierz typ raportu:", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        
        # Opcja 1
        ctk.CTkRadioButton(content, text="📅 Raport Miesięczny (Wszyscy)", variable=type_var, value="monthly").pack(anchor="w", pady=5)
        # Opcja 2 (NOWA)
        ctk.CTkRadioButton(content, text="📉 Zestawienie Całkowite (Dłużnicy)", variable=type_var, value="debt").pack(anchor="w", pady=5)
        # Opcja 3
        ctk.CTkRadioButton(content, text="👤 Karta Zawodnika (Historia)", variable=type_var, value="player").pack(anchor="w", pady=5)
        
        # --- OPCJE DLA MIESIĘCZNEGO ---
        month_frame = ctk.CTkFrame(content, fg_color="transparent")
        ctk.CTkLabel(month_frame, text="Miesiąc:").pack(side="left")
        month_menu = ctk.CTkOptionMenu(month_frame, values=MONTHS_PL, width=120)
        month_menu.set(MONTHS_PL[self.selected_month-1])
        month_menu.pack(side="left", padx=5)
        year_menu = ctk.CTkOptionMenu(month_frame, values=[str(y) for y in range(2024, datetime.now().year + 2)], width=80)
        year_menu.set(str(self.current_year))
        year_menu.pack(side="left", padx=5)
        
        # --- OPCJE DLA ZAWODNIKA ---
        player_frame = ctk.CTkFrame(content, fg_color="transparent")
        ctk.CTkLabel(player_frame, text="Zawodnik:").pack(side="left")
        player_names = sorted([p['full_name'] for p in self.players_data])
        player_menu = ctk.CTkOptionMenu(player_frame, values=player_names, width=200)
        if player_names: player_menu.set(player_names[0])
        player_menu.pack(side="left", padx=5)
        
        # Logika ukrywania
        def update_options():
            choice = type_var.get()
            month_frame.pack_forget()
            player_frame.pack_forget()
            
            if choice == "monthly":
                month_frame.pack(fill="x", pady=10)
            elif choice == "player":
                player_frame.pack(fill="x", pady=10)
            # dla "debt" nie ma dodatkowych opcji (bierze stan na dziś)
        
        type_var.trace("w", lambda *args: update_options())
        update_options()
        
        def generate():
            # FIX: generowanie PDF blokowało całe okno - leci w wątku.
            btn_pdf.configure(state="disabled", text="⏳ Generowanie...")
            run_async(modal, _generate_worker,
                      on_success=_generate_done,
                      on_error=_generate_error)

        def _generate_error(e):
            btn_pdf.configure(state="normal", text="🖨️ Generuj PDF")
            msgbox.showerror("Błąd PDF", str(e))

        def _generate_done(fn):
            btn_pdf.configure(state="normal", text="🖨️ Generuj PDF")
            try:
                modal.destroy()
                if platform.system() == "Windows":
                    os.startfile(fn)
                elif platform.system() == "Darwin":
                    os.system(f"open '{fn}'")
                msgbox.showinfo("Sukces", f"Wygenerowano:\n{fn}")
            except Exception as e:
                msgbox.showerror("Błąd", str(e))

        def _generate_worker():
            if True:
                acc = self.club_settings.get('bank_account', '')
                bank = self.club_settings.get('bank_name', '')
                
                if PDFGenerator is None:
                    # wątek roboczy - nie otwieramy okienek, rzucamy wyjątek
                    raise RuntimeError("Nie znaleziono modułu PDF!")

                generator = PDFGenerator(database.CURRENT_CLUB, acc, bank)
                desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                
                choice = type_var.get()
                
                if choice == "monthly":
                    m = MONTHS_PL.index(month_menu.get()) + 1
                    y = int(year_menu.get())
                    fn = os.path.join(desktop, f"Raport_{y}_{m}.pdf")
                    
                    # Logika pobierania danych (uproszczona)
                    fin_data = {f['player_id']: f for f in self.finances_data if f.get('month') == m and f.get('year') == y}
                    generator.generate_monthly_report(y, m, self.players_data, fin_data, fn)
                    
                elif choice == "debt":
                    # --- GENEROWANIE RAPORTU ZADŁUŻENIA ---
                    fn = os.path.join(desktop, f"Raport_Zaleglosci_{datetime.now().strftime('%Y_%m_%d')}.pdf")
                    
                    debt_data = []
                    # Oblicz zaległości dla każdego gracza
                    for p in self.players_data:
                        # Używamy existing logic
                        arrears_count, arrears_amount = self._calculate_arrears_cached(p)
                        fee = self._get_player_fee(p)
                        
                        debt_data.append({
                            'number': p.get('jersey_number', '-'),
                            'name': p['full_name'],
                            'fee': fee,
                            'arrears_months': arrears_count,
                            'total_debt': arrears_amount,
                            'balance': safe_float(p.get('balance', 0))
                        })
                    
                    generator.generate_total_debt_report(debt_data, fn)
                    
                elif choice == "player":
                    p_name = player_menu.get()
                    player = next((p for p in self.players_data if p['full_name'] == p_name), None)
                    if not player: return
                    
                    fn = os.path.join(desktop, f"Karta_{p_name}.pdf")
                    p_fin = [f for f in self.all_finances_data if f['player_id'] == player['id']]
                    generator.generate_player_card(player, p_fin, fn)
                
                return fn
        
        btn_pdf = ctk.CTkButton(content, text="🖨️ Generuj PDF", fg_color=COLORS["accent"], height=40, command=generate)
        btn_pdf.pack(side="bottom", fill="x", pady=20)