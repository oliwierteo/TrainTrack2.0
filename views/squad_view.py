import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk
import os
import sys
import tkinter.messagebox as msgbox
from datetime import datetime
from formations import FORMATIONS
from ui_async import run_async
from logger import logger
import teams

# Importy PDF
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors

from database import supabase
import database

# --- POMOCNIK ŚCIEŻEK (Dla PyInstallera) ---
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- KALIBRACJA POD MONITOR ---
GLOBAL_X_SHIFT = 30
BASE_WIDTH = 1000 

POSITIONS_COORDS = {
    # Bramkarz
    "BR": (0.5, 0.90),
    
    # Obrona
    "LO": (0.15, 0.75), 
    "LŚO": (0.35, 0.75), "ŚO": (0.5, 0.75), "PŚO": (0.65, 0.75), 
    "PO": (0.85, 0.75),
    
    # Pomoc Defensywna
    "LDP": (0.4, 0.60), "DP": (0.5, 0.60), "PDP": (0.6, 0.60),
    
    # Pomoc Środkowa/Boczna
    "LP": (0.15, 0.45), 
    "LŚP": (0.35, 0.45), "ŚP": (0.5, 0.45), "PŚP": (0.65, 0.45), 
    "PP": (0.85, 0.45),
    
    # Pomoc Ofensywna
    "LOP": (0.35, 0.30), "OP": (0.5, 0.30), "POP": (0.65, 0.30),
    
    # Atak
    "LS": (0.15, 0.20), # Lewy Skrzydłowy
    "LN": (0.35, 0.15), "N": (0.5, 0.15), "PN": (0.65, 0.15),
    "PS": (0.85, 0.20), # Prawy Skrzydłowy
    
    "ŁAW": (0.0, 0.0)
}

COLORS = {
    "bg_dark": "#121212", "panel_bg": "#1e1e1e", "accent": "#3b8ed0",
    "success": "#2fa572", "danger": "#cf352e", "token_outline": "#1f6aa5", "bench_bg": "#252525"
}

class SquadView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg_dark"])
        
        self.grid_columnconfigure(0, weight=0, minsize=340)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.pitch_players = {} 
        self.bench_players = []
        self.drag_data = {"x": 0, "y": 0, "tag": None}
        self.current_scale = 1.0
        self.resize_timer = None

        # LEWY PANEL
        self.left = ctk.CTkFrame(self, width=340, corner_radius=0, fg_color=COLORS["panel_bg"])
        self.left.grid(row=0, column=0, sticky="nsew")
        self.left.grid_propagate(False)
        ctk.CTkLabel(self.left, text="KADRA", font=("Segoe UI", 20, "bold"), text_color=COLORS["accent"]).pack(pady=(20, 5))
        self.p_scroll = ctk.CTkScrollableFrame(self.left, fg_color="transparent")
        self.p_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        # PRAWY PANEL
        self.right = ctk.CTkFrame(self, fg_color="transparent")
        self.right.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        # Toolbar
        tool = ctk.CTkFrame(self.right, fg_color=COLORS["panel_bg"], height=50)
        tool.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(tool, text="Odśwież", fg_color="#444", width=80, command=self.refresh_players).pack(side="right", padx=10)
        
        # 1. Wyczyść
        ctk.CTkButton(tool, text="Wyczyść", fg_color=COLORS["danger"], width=80, command=self.clear_all).pack(side="left", padx=10)
        
        # 2. Formacje
        from formations import FORMATIONS
        formation_names = sorted(list(FORMATIONS.keys()))
        self.formation_var = ctk.StringVar(value="4-3-3")
        ctk.CTkOptionMenu(tool, variable=self.formation_var, values=formation_names,
                          width=150, command=self.change_formation).pack(side="left", padx=10)
        
        # 3. Zapisz
        ctk.CTkButton(tool, text="💾 Zapisz", fg_color="#2fa572", width=100, command=self.save_squad_batch).pack(side="left", padx=10)
        
        # 4. PDF (Pewnie tego brakuje)
        ctk.CTkButton(tool, text="🖨️ PDF", fg_color="#e67e22", width=80, command=self.export_pdf).pack(side="right", padx=10)


        # Canvas
        self.c_frame = ctk.CTkFrame(self.right, fg_color="#2b2b2b")
        self.c_frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(self.c_frame, bg="#369c56", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=2, pady=2)
        
        self.bg_img = None
        self.bg_tk = None
        self.load_pitch_image()
        self.canvas.bind("<Configure>", self.on_resize)

        # Ławka
        bench_frame = ctk.CTkFrame(self.right, height=120, fg_color=COLORS["bench_bg"])
        bench_frame.pack(fill="x", pady=(10, 0))
        bench_frame.pack_propagate(False)
        ctk.CTkLabel(bench_frame, text="ŁAWKA REZERWOWYCH", font=("Arial", 11, "bold"), text_color="gray").pack(anchor="w", padx=10, pady=5)
        self.bench_scroll = ctk.CTkScrollableFrame(bench_frame, orientation="horizontal", fg_color="transparent", height=80)
        self.bench_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        self.load_players_list()

    def load_pitch_image(self):
        path = resource_path("assets/pitch.png")
        if os.path.exists(path): 
            self.bg_img = Image.open(path)
        else: 
            self.bg_img = Image.new('RGB', (800, 600), color="#2e7d32")

    def refresh_players(self):
        """Wymusza odświeżenie listy zawodników z bazy"""
        from cache_manager import cache
        cache.invalidate("players")
        self.load_players_list()

    # --- LISTA ---
    def load_players_list(self):
        for w in self.p_scroll.winfo_children(): w.destroy()
        
        # Placeholder ładowania
        loading = ctk.CTkLabel(self.p_scroll, text="⏳ Ładowanie...", text_color="gray")
        loading.pack(pady=20)
        
        def fetch():
            from cache_manager import cache
            self.players = cache.get_players()
            self.after(0, self.display_players_list)
        
        import threading
        threading.Thread(target=fetch, daemon=True).start()

    def save_squad_batch(self):
        """Zapisuje cały skład do bazy jednym zapytaniem (poza wątkiem GUI)"""
        if not self.pitch_players:
            msgbox.showwarning("Uwaga", "Brak zawodników na boisku")
            return

        # FIX: dwie operacje sieciowe blokowały okno - wątek roboczy.
        run_async(self, self._save_squad_worker,
                  on_success=self._save_squad_done,
                  on_error=lambda e: msgbox.showerror(
                      "Błąd", f"Nie udało się zapisać składu: {e}"))

    def _save_squad_done(self, current_date):
        database.log_activity(
            f"zapisał skład meczowy "
            f"({len(self.pitch_players) + len(self.bench_players)} zawodników)")
        msgbox.showinfo(
            "Sukces",
            f"Zapisano skład na dzień {current_date}:\n"
            f"• {len(self.pitch_players)} na boisku\n"
            f"• {len(self.bench_players)} na ławce"
        )

    def _save_squad_worker(self):
        if True:
            # Data dzisiejsza
            current_date = datetime.now().date().isoformat()
            
            # Przygotuj dane
            squad_data = []
            
            # Zawodnicy na boisku
            for tag, data in self.pitch_players.items():
                squad_data.append({
                    "club_name": database.CURRENT_CLUB,
                    "team_code": teams.get_current_team(),
                    "player_id": data['player']['id'],
                    "position": data['position'],
                    "is_starting": True,
                    "formation": "custom",
                    "match_date": current_date
                })
            
            # Zawodnicy na ławce
            for item in self.bench_players:
                squad_data.append({
                    "club_name": database.CURRENT_CLUB,
                    "team_code": teams.get_current_team(),
                    "player_id": item['player']['id'],
                    "position": "BENCH",
                    "is_starting": False,
                    "formation": "custom",
                    "match_date": current_date
                })
            
            # BATCH SAVE
            # Najpierw usuń stary skład z dziś (opcjonalne, ale czystsze)
            # kasujemy TYLKO skład tej drużyny (nie całego klubu!)
            delete = supabase.table('squad_setup').delete()\
                .eq('club_name', database.CURRENT_CLUB)\
                .eq('match_date', current_date)
            code = teams.get_current_team()
            if code != teams.ALL_TEAMS:
                delete = delete.eq('team_code', code)
            delete.execute()
            
            # Zapisz nowy
            supabase.table('squad_setup').insert(squad_data).execute()
            return current_date
    
    def display_players_list(self):
        """Wyświetla załadowanych zawodników z sortowaniem po pozycji"""
        for w in self.p_scroll.winfo_children(): w.destroy()
        
        if not self.players:
            ctk.CTkLabel(self.p_scroll, text="Brak zawodników", text_color="gray").pack(pady=20)
            return
        
        # --- SORTOWANIE ---
        POSITION_ORDER = {
            'BR': 1, 'GK': 1,
            'LO': 2, 'LB': 2, 'LŚO': 3, 'ŚO': 3, 'CB': 3, 'PŚO': 3, 'PO': 4, 'RB': 4,
            'DP': 5, 'DM': 5, 'CDM': 5,
            'ŚP': 6, 'CM': 6,
            'ŚPO': 7, 'CAM': 7, 'OP': 7,
            'LS': 8, 'LW': 8, 'PS': 9, 'RW': 9,
            'N': 10, 'ST': 10, 'CF': 10, 'ŚN': 10
        }
        
        try:
            # Sortowanie w miejscu
            self.players.sort(key=lambda x: (
                POSITION_ORDER.get(str(x.get('primary_position', '')).upper(), 99),
                x.get('full_name', '')
            ))
        except Exception as e:
            print(f"Błąd sortowania: {e}")

        # Opcje do menu
        opts = ["BR", 
                "LO", "LŚO", "ŚO", "PŚO", "PO", 
                "DP", "LDP", "PDP",
                "LP", "LŚP", "ŚP", "PŚP", "PP", 
                "ŚPO",
                "LS", "LN", "N", "PN", "PS", 
                "ŁAW"]

        for p in self.players:
            # 1. Sprawdź czy wybrany
            is_picked = False
            for d in self.pitch_players.values():
                if d['player']['id'] == p['id']: is_picked = True
            for b in self.bench_players:
                if b['player']['id'] == p['id']: is_picked = True
            
            # 2. Stylizacja (Wybrany vs Niewybrany)
            bg_color = "#1a1a1a" if is_picked else "#2b2b2b"
            text_color = "#555555" if is_picked else "white"
            
            c = ctk.CTkFrame(self.p_scroll, fg_color=bg_color)
            c.pack(fill="x", pady=2)
            c.grid_columnconfigure(1, weight=1)
            
            # Numer
            ctk.CTkLabel(c, text=str(p['jersey_number']), width=25, 
                         fg_color="#333" if is_picked else COLORS["accent"], 
                         text_color="gray" if is_picked else "white",
                         corner_radius=5).grid(row=0, column=0, padx=5, pady=5)
            
            # Nazwisko
            name = p['full_name']
            if len(name) > 18: name = name[:16] + "..."
            if is_picked: name = f"✓ {name}"
            
            ctk.CTkLabel(c, text=name, anchor="w", text_color=text_color).grid(row=0, column=1, sticky="ew")
            
            # Mapowanie pozycji
            db_pos = p.get('primary_position', 'ŚP')
            nominal = 'ŚP'
            pos_map = {'GK': 'BR', 'LB': 'LO', 'CB': 'ŚO', 'RB': 'PO', 'CDM': 'DP', 
                       'CM': 'ŚP', 'CAM': 'ŚPO', 'LM': 'LP', 'RM': 'PP', 
                       'LW': 'LS', 'RW': 'PS', 'ST': 'N', 'CF': 'N'}
            
            if db_pos in pos_map: nominal = pos_map[db_pos]
            elif db_pos in opts: nominal = db_pos
            
            pv = ctk.StringVar(value=nominal)
            
            # Menu i Przycisk
            if not is_picked:
                ctk.CTkOptionMenu(c, variable=pv, values=opts, width=65, height=22, fg_color="#444").grid(row=0, column=2, padx=5)
                ctk.CTkButton(c, text="+", width=30, height=22, fg_color=COLORS["success"], 
                              command=lambda pl=p, v=pv: self.dispatch_add(pl, v.get())).grid(row=0, column=3, padx=5)
            else:
                ctk.CTkLabel(c, text="WYBRANY", font=("Arial", 9), text_color="gray").grid(row=0, column=2, columnspan=2)

    def dispatch_add(self, player, pos):
        # 1. Sprawdź duplikaty
        for d in self.pitch_players.values():
            if d['player']['id'] == player['id']: return msgbox.showinfo("Info", "Już na boisku")
        for b in self.bench_players:
            if b['player']['id'] == player['id']: return msgbox.showinfo("Info", "Już na ławce")
        
        if pos == "ŁAW":
            self.add_to_bench(player)
            return

        # 2. Auto-pozycjonowanie
        final_pos = pos
        taken_positions = [d['position'] for d in self.pitch_players.values()]
        
        # Definicja alternatyw
        alternatives = {
            "ŚO": ["LŚO", "PŚO"],
            "ŚP": ["LŚP", "PŚP"],
            "DP": ["LDP", "PDP"],
            "ŚPO": ["LOP", "POP"],
            "N":  ["LN", "PN"]
        }
        
        # Jeśli główna pozycja zajęta -> szukaj wolnej alternatywy
        if pos in taken_positions:
            if pos in alternatives:
                for alt in alternatives[pos]:
                    if alt not in taken_positions:
                        final_pos = alt
                        break
        
        # Dodaj na boisko
        self.add_to_pitch(player, final_pos)
    
    def change_formation(self, formation_name):
        """Zmienia formację i przesuwa zawodników"""
        from formations import FORMATIONS
        
        if formation_name in FORMATIONS:
            # 1. Pobierz nowe współrzędne
            new_coords = FORMATIONS[formation_name]
            
            # 2. Zaktualizuj globalny słownik (dla nowych dodań)
            POSITIONS_COORDS.update(new_coords)
            
            # 3. Zaktualizuj JUŻ DODANYCH zawodników
            for tag, data in self.pitch_players.items():
                pos_name = data['position']
                
                # Jeśli ta pozycja istnieje w nowej formacji -> przesuń gracza
                if pos_name in new_coords:
                    new_x, new_y = new_coords[pos_name]
                    data['rel_x'] = new_x
                    data['rel_y'] = new_y
            
            # 4. Przerysuj
            w = self.canvas.winfo_width()
            h = self.canvas.winfo_height()
            if w > 1: self.redraw_all(w, h)

    def add_to_bench(self, player):
        c = ctk.CTkFrame(self.bench_scroll, fg_color="#333", width=150)
        c.pack(side="left", padx=5, fill="y")
        ctk.CTkLabel(c, text=f"{player['jersey_number']}. {player['full_name'].split()[-1]}", font=("Arial", 12)).pack(side="left", padx=10)
        ctk.CTkButton(c, text="X", width=25, height=25, fg_color="transparent", text_color="red", 
                      command=lambda: self.remove_bench(player['id'])).pack(side="right", padx=5)
        self.bench_players.append({'player': player, 'widget': c})
        self.display_players_list()

    def remove_bench(self, pid):
        for i, item in enumerate(self.bench_players):
            if item['player']['id'] == pid:
                item['widget'].destroy()
                self.bench_players.pop(i)
                self.display_players_list()
                return

    # --- SKALOWANIE ---
    def on_resize(self, event):
        if self.resize_timer: self.after_cancel(self.resize_timer)
        self.resize_timer = self.after(50, lambda: self.perform_resize(event.width, event.height))

    def perform_resize(self, w, h):
        if w < 50: return
        self.current_scale = w / BASE_WIDTH
        if self.current_scale < 0.6: self.current_scale = 0.6
        if self.current_scale > 3.0: self.current_scale = 3.0

        if self.bg_img:
            resized = self.bg_img.resize((w, h), Image.Resampling.LANCZOS)
            self.bg_tk = ImageTk.PhotoImage(resized)
            self.canvas.delete("bg")
            self.canvas.create_image(0, 0, image=self.bg_tk, anchor="nw", tags="bg")
            self.canvas.tag_lower("bg")
        
        self.redraw_all(w, h)

    def redraw_all(self, w, h):
        for tag, data in self.pitch_players.items():
            self.canvas.delete(tag)
            px = w * data['rel_x']
            py = h * data['rel_y']
            self.draw_token(tag, px, py, data['player'], data['position'])

    def add_to_pitch(self, player, pos):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 50: w, h = 800, 600
        rx, ry = POSITIONS_COORDS.get(pos, (0.5, 0.5))
        tag = f"p_{player['id']}"
        self.pitch_players[tag] = {'player': player, 'position': pos, 'rel_x': rx, 'rel_y': ry}
        self.draw_token(tag, w*rx, h*ry, player, pos)
        self.display_players_list()

    def draw_token(self, tag, x, y, player, pos):
        print(f"🔍 {player.get('full_name')} - primary_position: '{player.get('primary_position')}' | menu: '{pos}'")
        s = self.current_scale
        visual_x = x + (GLOBAL_X_SHIFT * s)
        visual_y = y
        r = 18 * s
        f_n = int(11 * s)
        f_t = int(9 * s)
        
        # Wszystkie elementy zawodnika dostają tag (tag) ORAZ ogólny tag "drag"
        self.canvas.create_oval(visual_x-r+3, visual_y-r+3, visual_x+r+3, visual_y+r+3, fill="#1e502b", outline="", tags=(tag, "drag"))
        self.canvas.create_oval(visual_x-r, visual_y-r, visual_x+r, visual_y+r, fill="white", outline=COLORS["token_outline"], width=3*s, tags=(tag, "drag"))
        self.canvas.create_text(visual_x, visual_y, text=str(player['jersey_number']), font=("Arial", f_n, "bold"), fill="black", tags=(tag, "drag"))
        
        name = player['full_name'].split()[-1].upper()
        txt = self.canvas.create_text(visual_x, visual_y+(28*s), text=name, fill="white", font=("Arial", f_t, "bold"), tags=(tag, "drag"))
        bb = self.canvas.bbox(txt)
        if bb:
            bg = self.canvas.create_rectangle(bb[0]-4, bb[1]-2, bb[2]+4, bb[3]+2, fill="#1a1a1a", outline="", tags=(tag, "drag"))
            self.canvas.tag_lower(bg, txt)
        
        self.canvas.create_rectangle(visual_x+(12*s), visual_y-(22*s), visual_x+(32*s), visual_y-(8*s), fill="#f1c40f", outline="black", tags=(tag, "drag"))
        # Wyświetl pozycję NOMINALNĄ zamiast wybranej z menu
        nominal_pos = player.get('primary_position')
        if not nominal_pos or str(nominal_pos).strip() == "":
            nominal_pos = pos
        print(f"   ✅ Wyświetlam: {nominal_pos}")  # DEBUG
        self.canvas.create_text(visual_x+(22*s), visual_y-(15*s), text=nominal_pos, font=("Arial", int(7*s), "bold"), fill="black", tags=(tag, "drag"))
        self.canvas.tag_bind(tag, "<ButtonPress-1>", lambda e, t=tag: self.on_drag_start(e, t))
        self.canvas.tag_bind(tag, "<B1-Motion>", self.on_drag_motion)
        self.canvas.tag_bind(tag, "<Button-3>", lambda e, t=tag: self.remove_pitch(t)) # Windows/Myszka
        if sys.platform == "darwin":
            self.canvas.tag_bind(tag, "<Button-2>", lambda e, t=tag: self.remove_pitch(t)) # Mac Touchpad
            self.canvas.tag_bind(tag, "<Control-Button-1>", lambda e, t=tag: self.remove_pitch(t))
        self.canvas.tag_raise(tag)

    def on_drag_start(self, e, tag):
        self.drag_data["tag"] = tag
        self.drag_data["x"] = e.x
        self.drag_data["y"] = e.y
        self.canvas.tag_raise(tag)

    def on_drag_motion(self, e):
        tag = self.drag_data["tag"]
        if not tag: return
        dx = e.x - self.drag_data["x"]
        dy = e.y - self.drag_data["y"]
        self.canvas.move(tag, dx, dy)
        self.drag_data["x"] = e.x
        self.drag_data["y"] = e.y
        
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        bb = self.canvas.bbox(tag)
        if bb and w>0 and h>0:
            cx_vis, cy_vis = (bb[0]+bb[2])/2, (bb[1]+bb[3])/2
            shift_px = GLOBAL_X_SHIFT * self.current_scale
            pure_cx = cx_vis - shift_px
            if tag in self.pitch_players:
                self.pitch_players[tag]['rel_x'] = pure_cx / w
                self.pitch_players[tag]['rel_y'] = cy_vis / h

    def remove_pitch(self, tag):
        if msgbox.askyesno("Usuń", "Zdjąć zawodnika?"):
            self.canvas.delete(tag)
            del self.pitch_players[tag]
            self.display_players_list()

    # --- POPRAWIONA FUNKCJA CZYŚĆ ---
    def clear_all(self):
        if msgbox.askyesno("Potwierdź", "Wyczyścić wszystko?"):
            # Usuwamy tylko elementy z tagiem "drag" (zawodnicy), tło ("bg") zostaje!
            self.canvas.delete("drag")
            self.pitch_players = {}
            
            # Czyścimy ławkę
            for i in self.bench_players: 
                try: i['widget'].destroy()
                except: pass
            self.bench_players = []
            self.display_players_list()

    # --- PDF ---
    def export_pdf(self):
        """
        FIX: generowanie PDF (renderowanie + fonty) blokowało wątek główny
        Tkintera - okno zamrażało się na wiele sekund. Teraz leci w wątku.
        """
        if not self.pitch_players and not self.bench_players:
            return msgbox.showerror("Błąd", "Skład jest pusty - dodaj zawodników.")

        run_async(self, self._build_pdf,
                  on_success=self._pdf_done,
                  on_error=lambda e: msgbox.showerror("Błąd PDF", f"Szczegóły: {e}"))

    def _pdf_done(self, fn):
        """Pokazanie wyniku (wątek główny Tkintera)."""
        try:
            import platform
            msgbox.showinfo("Sukces", f"Wygenerowano profesjonalny raport:\n{fn}")
            if platform.system() == "Darwin":
                os.system(f'open "{fn}"')
            elif platform.system() == "Windows":
                os.startfile(fn)
            else:
                os.system(f'xdg-open "{fn}"')
        except Exception as e:
            logger.error(f"Nie udało się otworzyć PDF: {e}")

    def _build_pdf(self):
        """Właściwy render PDF - wywoływane w wątku roboczym, zwraca ścieżkę."""
        if True:
            # Importy lokalne dla pewności
            import platform
            from reportlab.pdfgen import canvas as pdf_canvas
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            import os
            import sys
            
            # --- HELPER: Ścieżka do zasobów ---
            def resource_path(relative_path):
                try: base_path = sys._MEIPASS
                except: base_path = os.path.abspath(".")
                return os.path.join(base_path, relative_path)

            # Ścieżka pulpitu
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            filename = f"Raport_Taktyczny_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            fn = os.path.join(desktop, filename)
            
            # --- CZCIONKI (POLSKIE ZNAKI) ---
            f_r, f_b = "Arial-Custom", "Arial-Bold-Custom"
            try:
                # Użyj funkcji resource_path z main.py (lub zdefiniuj lokalnie)
                def res_path(rel):
                    try: return os.path.join(sys._MEIPASS, rel)
                    except: return os.path.abspath(rel)

                font_file = res_path(os.path.join("assets", "arial.ttf"))
                if os.path.exists(font_file):
                    pdfmetrics.registerFont(TTFont(f_r, font_file))
                    # Jeśli nie masz osobnego pliku bold, użyj tego samego
                    pdfmetrics.registerFont(TTFont(f_b, font_file))
                else:
                    f_r, f_b = "Helvetica", "Helvetica-Bold"
            except:
                f_r, f_b = "Helvetica", "Helvetica-Bold"

            c = pdf_canvas.Canvas(fn, pagesize=landscape(A4))
            W, H = landscape(A4)
            steps = 60
            for i in range(steps):
                ratio = i / steps
                r = (234 + (179-234)*ratio)/255
                g = (242 + (202-242)*ratio)/255
                b = (251 + (228-251)*ratio)/255
                c.setFillColorRGB(r, g, b)
                c.rect(0, (H/steps)*i, W, H/steps, fill=1, stroke=0)
            
            # --- NAGŁÓWEK (BARWY KLUBOWE) ---
            header_h = 80
            # Tło nagłówka: CZARNE
            c.setFillColorRGB(0, 0, 0) 
            c.rect(0, H - header_h, W, header_h, fill=1, stroke=0)
            
            # Logo (jeśli istnieje)
            logo_path = resource_path("assets/logo.png")
            text_x_offset = 40
            if os.path.exists(logo_path):
                try:
                    c.drawImage(logo_path, 20, H - 70, width=60, height=60, mask='auto')
                    text_x_offset = 90
                except: pass

            c.setFillColorRGB(1,1,1)
            c.setFont(f_b, 26)
            club_name = database.CURRENT_CLUB.upper()
            c.drawString(text_x_offset, H - 50, club_name)
            
            c.setFont(f_r, 12)
            c.drawRightString(W - 40, H - 35, f"Data: {datetime.now().strftime('%d.%m.%Y')}")
            c.setFont(f_r, 10)
            c.drawRightString(W - 40, H - 50, "System TrainTrack PRO")
            
            # Linia oddzielająca: CZERWONA
            c.setStrokeColorRGB(0.8, 0, 0)
            c.setLineWidth(3)
            c.line(0, H - header_h, W, H - header_h)
            
            safe_padding = 15
            top_limit = H - header_h - safe_padding

            # --- BOISKO ---
            px, pw, ph = 50, 420, 420 
            py = top_limit - ph 

            c.setFillColorRGB(0.15, 0.4, 0.2) 
            c.rect(px, py, pw, ph, fill=1, stroke=0)

            c.setStrokeColorRGB(1, 1, 1)
            c.setLineWidth(2)
            c.rect(px, py, pw, ph, stroke=1, fill=0)
            mid_y = py + ph/2
            c.line(px, mid_y, px + pw, mid_y)
            c.circle(px + pw/2, mid_y, 45, stroke=1, fill=0)
            c.setFillColorRGB(1,1,1)
            c.circle(px + pw/2, mid_y, 2.5, fill=1, stroke=0)

            box_w, box_h = pw * 0.65, ph * 0.15
            sbox_w, sbox_h = pw * 0.25, ph * 0.05
            bx = px + (pw - box_w)/2
            sbx = px + (pw - sbox_w)/2
            c.rect(bx, py, box_w, box_h, stroke=1)
            c.rect(sbx, py, sbox_w, sbox_h, stroke=1)
            c.circle(px + pw/2, py + ph*0.1, 2, fill=1)
            c.arc(px+pw/2-40, py+box_h-30, px+pw/2+40, py+box_h+40, 0, 180)
            c.rect(bx, py + ph - box_h, box_w, box_h, stroke=1)
            c.rect(sbx, py + ph - sbox_h, sbox_w, sbox_h, stroke=1)
            c.circle(px + pw/2, py + ph - ph*0.1, 2, fill=1)
            c.arc(px+pw/2-40, py+ph-box_h-40, px+pw/2+40, py+ph-box_h+30, 180, 180)

            # --- ZAWODNICY NA BOISKU ---
            for tag, d in self.pitch_players.items():
                rel_x, rel_y = d['rel_x'], d['rel_y']
                pdf_x = px + (rel_x * pw)
                pdf_y = (py + ph) - (rel_y * ph)
                
                c.setFillColorRGB(0.1, 0.2, 0.1)
                c.circle(pdf_x+1.5, pdf_y-1.5, 14, fill=1, stroke=0)
                c.setStrokeColorRGB(0.1, 0.1, 0.1)
                c.setFillColorRGB(1,1,1)
                c.circle(pdf_x, pdf_y, 14, fill=1, stroke=1)
                c.setFillColorRGB(0,0,0)
                c.setFont(f_b, 11)
                c.drawCentredString(pdf_x, pdf_y-4, str(d['player'].get('jersey_number', '?')))
                
                nm = d['player']['full_name'].split()[-1].upper()
                c.setFont(f_b, 8)
                txt_w = c.stringWidth(nm, f_b, 8)
                c.setFillColorRGB(0.1, 0.1, 0.1)
                c.rect(pdf_x - txt_w/2 - 3, pdf_y - 28, txt_w + 6, 11, fill=1, stroke=0)
                c.setFillColorRGB(1,1,1)
                c.drawCentredString(pdf_x, pdf_y-25, nm)

            # --- TABELA SKŁADU ---
            tx = 530
            bottom_limit = 50
            box_height = top_limit - bottom_limit
            
            c.setFillColorRGB(0.97, 0.97, 0.98)
            c.setStrokeColorRGB(0.8, 0.8, 0.8)
            c.setLineWidth(1)
            c.rect(tx - 15, bottom_limit, 290, box_height, fill=1, stroke=1)

            ty = top_limit - 30 
            
            c.setFillColorRGB(0,0,0)
            c.setFont(f_b, 17)
            c.drawString(tx, ty, "SKŁAD WYJŚCIOWY")
            
            # Czerwona linia pod tytułem
            c.setStrokeColorRGB(0.8, 0, 0)
            c.setLineWidth(2)
            c.line(tx, ty - 8, tx + 260, ty - 8)
            
            ty -= 35 
            c.setFont(f_b, 10)
            c.setFillColorRGB(0.4, 0.4, 0.4)
            c.drawString(tx, ty, "POZ")
            c.drawString(tx+45, ty, "NR")
            c.drawString(tx+85, ty, "NAZWISKO")
            
            ty -= 20 
            po = ["BR","ŚO","ŚO P","ŚO L","LO","PO","DP","ŚP","LP","PP","OP","LN","N","PN"]
            srt = sorted(self.pitch_players.values(), key=lambda x: po.index(x['position']) if x['position'] in po else 99)
            
            for i, d in enumerate(srt):
                if i % 2 == 0:
                    c.setFillColorRGB(0.92, 0.93, 0.96)
                    c.rect(tx-5, ty-4, 275, 16, fill=1, stroke=0)
                
                c.setFillColorRGB(0,0,0)
                c.setFont(f_b, 10)
                c.drawString(tx, ty, d['position'])
                c.setFont(f_r, 10)
                c.drawString(tx+45, ty, str(d['player'].get('jersey_number', '?')))
                c.drawString(tx+85, ty, d['player']['full_name'].upper())
                ty -= 18

            # --- ŁAWKA REZERWOWYCH (MULTI-COLUMN) ---
            ty -= 25
            c.setFont(f_b, 16)
            c.setFillColorRGB(0,0,0)
            c.drawString(tx, ty, "ŁAWKA REZERWOWYCH")
            
            c.setStrokeColorRGB(0.8, 0, 0) # Czerwona linia
            c.line(tx, ty - 8, tx + 260, ty - 8)
            
            ty -= 30 
            c.setFont(f_r, 10)
            
            start_y = ty
            col_offset = 0
            
            for i, item in enumerate(self.bench_players):
                # Obsługa różnych struktur danych
                if 'player' in item:
                    p = item['player']
                    pos = item.get('position', '-')
                else:
                    p = item # Zakładamy że item to gracz
                    pos = p.get('primary_position', '-')

                text = f"{p.get('jersey_number','?')}. {p.get('full_name', 'Nieznany').upper()} ({pos})"
                
                c.drawString(tx + col_offset, ty, text)
                ty -= 15
                
                # Jeśli koniec strony w ramce -> nowa kolumna
                if ty < bottom_limit + 20:
                    ty = start_y
                    col_offset += 140 # Przesuń w prawo

            # --- STOPKA ---
            c.setStrokeColorRGB(0.7, 0.7, 0.7)
            c.setLineWidth(1)
            c.line(40, 35, W-40, 35)
            c.setFont(f_r, 8)
            c.setFillColorRGB(0.5, 0.5, 0.5)
            c.drawCentredString(W/2, 20, f"Wygenerowano w systemie TrainTrack PRO | Oficjalny Raport {club_name}")

            c.save()
            return fn