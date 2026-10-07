import customtkinter as ctk
import tkinter.messagebox as msgbox
from database import supabase
import database
import teams
from datetime import datetime
from image_manager import img_manager

class RatingsView(ctk.CTkToplevel):
    def __init__(self, master, event):
        super().__init__(master)
        self.title(f"Ocenianie: {event['event_date']}")
        self.geometry("700x600")
        self.minsize(600, 400)
        self.event = event
        self.attributes("-topmost", True)
        
        # WYKRYWANIE TYPU WYDARZENIA
        event_types = event.get('event_types', [])
        if isinstance(event_types, str): event_types = [event_types]
        
        self.is_match = any("Mecz" in t for t in event_types)
        
        # KONFIGURACJA KRYTERIÓW
        if self.is_match:
            self.MODE_LABEL = "MECZ"
            self.MODE_COLOR = "#e67e22" # Pomarańczowy dla meczu
            self.CRITERIA = [
                ("⚔️ Ofensywa", "r_offense"),
                ("🧱 Defensywa", "r_defense"), # Zmiana emotki na węższą (cegła/mur)
                ("🧠 Taktyka", "r_tactics"),
                ("⚽ Technika", "r_technique")
            ]
        else:
            self.MODE_LABEL = "TRENING"
            self.MODE_COLOR = "#3b8ed0" # Niebieski dla treningu
            self.CRITERIA = [
                ("🔥 Zaangażowanie", "r_engagement"),
                ("📊 Powtarzalność", "r_consistency"),
                ("🧠 Taktyka", "r_tactics"),
                ("⚽ Technika", "r_technique"),
                ("🏃 Motoryka", "r_motor")
            ]

        self.all_ratings = []
        self.players = []

        # Pasek górny
        top = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=0)
        top.pack(fill="x")
        
        top_inner = ctk.CTkFrame(top, fg_color="transparent")
        top_inner.pack(fill="x", padx=15, pady=12)
        
        dt_obj = datetime.strptime(event['event_date'], "%Y-%m-%d")
        dt_display = dt_obj.strftime("%d.%m.%Y")
        
        ctk.CTkLabel(top_inner, text=f"📋 {self.MODE_LABEL} - {dt_display}", 
                     font=("Segoe UI", 18, "bold"), text_color=self.MODE_COLOR).pack(side="left")
        
        ctk.CTkButton(top_inner, text="ℹ️", width=32, height=32, fg_color="#333", 
                      corner_radius=16, command=self.show_legend).pack(side="right")
        
        self.progress_label = ctk.CTkLabel(top_inner, text="", font=("Segoe UI", 11), text_color="#888")
        self.progress_label.pack(side="right", padx=15)

        # Nagłówki kolumn
        header = ctk.CTkFrame(self, fg_color="#242424", height=30)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        header_inner = ctk.CTkFrame(header, fg_color="transparent")
        header_inner.pack(fill="both", expand=True, padx=15)
        
        ctk.CTkLabel(header_inner, text="ZAWODNIK", font=("Segoe UI", 10, "bold"), text_color="#666").pack(side="left", pady=5)
        
        ctk.CTkLabel(header_inner, text="MOJA", font=("Segoe UI", 10, "bold"), text_color="#666", width=50).pack(side="right", padx=5)
        ctk.CTkLabel(header_inner, text="SZTAB", font=("Segoe UI", 10, "bold"), text_color="#666", width=50).pack(side="right", padx=5)
        ctk.CTkLabel(header_inner, text="", width=70).pack(side="right")  # Spacer dla przycisku

        # Lista zawodników
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=10, pady=10)

        self.load_data()

    def load_data(self):
        for w in self.scroll.winfo_children(): w.destroy()
        
        try:
            # Pobierz obecnych
            att = supabase.table('attendance').select("player_id, status").eq('event_id', self.event['id']).execute()
            present_ids = [a['player_id'] for a in att.data if a['status'] in ['obecny', 'spóźniony']]
            
            if not present_ids:
                ctk.CTkLabel(self.scroll, text="Brak obecnych zawodników do ocenienia.", 
                             font=("Segoe UI", 14), text_color="gray").pack(pady=50)
                return

            # Pobierz graczy
            self.players = supabase.table('players').select("*").in_('id', present_ids).execute().data
            
            # Sortowanie po pozycji
            POS_ORDER = {
                'BR': 1, 'GK': 1, 
                'LO': 2, 'LB': 2, 
                'ŚO': 3, 'CB': 3, 
                'PO': 4, 'RB': 4,
                'DP': 5, 'DM': 5, 
                'ŚP': 6, 'CM': 6, 
                'ŚPO': 7, 'CAM': 7,
                'LS': 8, 'LW': 8, 
                'PS': 9, 'RW': 9, 
                'N': 10, 'ST': 10, 
                'CF': 10
            }
            
            self.players.sort(key=lambda x: (
                POS_ORDER.get(str(x.get('primary_position') or '').upper(), 99),
                x.get('jersey_number') or 99
            ))
            
            # Pobierz oceny
            self.all_ratings = supabase.table('ratings').select("*").eq('event_id', self.event['id']).execute().data
            
            self.update_progress()
            
            for p in self.players:
                self.create_row(p)
                
        except Exception as e: 
            ctk.CTkLabel(self.scroll, text=f"Błąd: {e}", text_color="red").pack(pady=20)

    def update_progress(self):
        coach_id = database.CURRENT_USER_EMAIL if hasattr(database, 'CURRENT_USER_EMAIL') else "System"
        rated = sum(1 for p in self.players if any(
            r['player_id'] == p['id'] and r['coach_name'] == coach_id for r in self.all_ratings
        ))
        self.progress_label.configure(text=f"✓ {rated}/{len(self.players)}")

    def get_color(self, val):
        if val is None: return "#555"
        if val <= 3: return "#e74c3c"
        if val <= 6: return "#f39c12"
        if val <= 8: return "#3498db"
        return "#2ecc71"

    def calculate_average(self, rating_entry):
        """Oblicza średnią na podstawie aktywnych kryteriów"""
        if not rating_entry: return None
        
        # Pobieramy klucze z bazy danych dla aktualnego trybu
        keys = [c[1] for c in self.CRITERIA]
        
        # Pobierz wartości, pomijając None
        values = [rating_entry.get(k) for k in keys if rating_entry.get(k) is not None]
        
        if not values: return None
        return sum(values) / len(values)

    def create_row(self, player):
        pid = player.get('id')
        coach_id = database.CURRENT_USER_EMAIL if hasattr(database, 'CURRENT_USER_EMAIL') else "System"
        
        # Główny wiersz - kompaktowy
        row = ctk.CTkFrame(self.scroll, fg_color="#2a2a2a", corner_radius=8, height=52)
        row.pack(fill="x", pady=2)
        row.pack_propagate(False)
        
        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=10, pady=6)

        # Zdjęcie (małe)
        photo_lbl = ctk.CTkLabel(inner, text="", width=38, height=38)
        photo_lbl.pack(side="left")
        
        img = img_manager.get_circular_image(
            player['id'], player.get('photo_url'), (38, 38),
            lambda i, lbl=photo_lbl: lbl.configure(image=i)
        )
        photo_lbl.configure(image=img)

        # Numer (mały)
        nr = player.get('jersey_number') or '-'
        ctk.CTkLabel(inner, text=str(nr), width=28, height=28, fg_color="#1f6aa5", 
                     corner_radius=14, font=("Arial", 11, "bold")).pack(side="left", padx=8)

        # Imię + Pozycja
        name_frame = ctk.CTkFrame(inner, fg_color="transparent")
        name_frame.pack(side="left", fill="y")
        
        name_text = player.get('full_name', '')
        pos_text = player.get('primary_position') or ''
        
        ctk.CTkLabel(name_frame, text=name_text, font=("Segoe UI", 12, "bold"), 
                     anchor="w").pack(side="left")
        
        # === PRAWA STRONA ===
        
        # Moja ocena
        my_rating = next((r for r in self.all_ratings if r['player_id'] == pid and r['coach_name'] == coach_id), None)
        my_avg = self.calculate_average(my_rating)
        
        my_text = f"{my_avg:.1f}" if my_avg is not None else "—"
        my_color = self.get_color(my_avg)

        # Średnia sztabu
        all_p_ratings = [r for r in self.all_ratings if r['player_id'] == pid]
        staff_avgs = [self.calculate_average(r) for r in all_p_ratings]
        # Filtruj None
        staff_avgs = [a for a in staff_avgs if a is not None]
        
        if staff_avgs:
            staff_final = sum(staff_avgs) / len(staff_avgs)
            staff_text = f"{staff_final:.1f}"
            staff_color = self.get_color(staff_final)
        else:
            staff_text = "—"
            staff_color = "#444"

        # Label: Moja ocena
        ctk.CTkLabel(inner, text=my_text, font=("Arial", 13, "bold"), 
                     text_color=my_color, width=45).pack(side="right", padx=2)

        # Label: Średnia sztabu
        ctk.CTkLabel(inner, text=staff_text, font=("Arial", 13, "bold"), 
                     text_color=staff_color, width=45).pack(side="right", padx=2)

        # Przycisk
        btn_text = "✏️" if my_rating else "⭐"
        btn_fg = "#444" if my_rating else "#8e44ad"
        
        btn = ctk.CTkButton(inner, text=btn_text, width=36, height=28, fg_color=btn_fg, 
                            corner_radius=6, font=("Arial", 12),
                            command=lambda p=player: self.open_rating_dialog(p))
        btn.pack(side="right", padx=(0, 8))

    def open_rating_dialog(self, player):
        pid = player.get('id')
        name = player.get('full_name', 'Zawodnik')
        
        coach_id = database.CURRENT_USER_EMAIL if hasattr(database, 'CURRENT_USER_EMAIL') else "System"
        existing = next((r for r in self.all_ratings if r['player_id'] == pid and r['coach_name'] == coach_id), None)
        
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Ocena ({self.MODE_LABEL})")
        
        # Wysokość okna zależna od liczby suwaków
        height = 420 if self.is_match else 480
        dialog.geometry(f"380x{height}")
        
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.attributes("-topmost", True)
        
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 380) // 2
        y = (dialog.winfo_screenheight() - height) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # Nagłówek
        header = ctk.CTkFrame(dialog, fg_color="#1a1a1a", corner_radius=0)
        header.pack(fill="x")
        
        ctk.CTkLabel(header, text=f"#{player.get('jersey_number') or '-'}  {name}", 
                     font=("Segoe UI", 16, "bold"), text_color="#3b8ed0").pack(pady=(15, 5))
        
        ctk.CTkLabel(header, text=f"TRYB: {self.MODE_LABEL}", 
                     font=("Arial", 10, "bold"), text_color=self.MODE_COLOR).pack(pady=(0, 10))

        # Suwaki
        sliders_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        sliders_frame.pack(fill="x", padx=20, pady=10)
        
        sliders = {}
        
        for label_text, db_key in self.CRITERIA:
            frame = ctk.CTkFrame(sliders_frame, fg_color="transparent")
            frame.pack(fill="x", pady=6)
            
            # --- POPRAWIONE WYRÓWNANIE (EMOTKA OSOBNO) ---
            
            # Rozdzielamy emotkę od tekstu
            parts = label_text.split(" ", 1)
            emoji = parts[0] if len(parts) > 0 else ""
            text = parts[1] if len(parts) > 1 else label_text

            # 1. Emotka (stała szerokość 30px, wyśrodkowana)
            ctk.CTkLabel(frame, text=emoji, width=30, font=("Segoe UI", 12)).pack(side="left")
            
            # 2. Tekst (stała szerokość 100px, wyrównany do lewej)
            ctk.CTkLabel(frame, text=text, width=100, anchor="w", font=("Segoe UI", 12)).pack(side="left")
            
            # Wartość startowa
            start_val = (existing.get(db_key) or 5) if existing else 5
            
            # 4. Wartość liczbowa (po prawej)
            val_lbl = ctk.CTkLabel(frame, text=str(int(start_val)), width=30, 
                                   font=("Arial", 14, "bold"), text_color=self.get_color(start_val))
            val_lbl.pack(side="right")

            # 3. Suwak (wypełnia środek)
            slider = ctk.CTkSlider(frame, from_=1, to=10, number_of_steps=9, width=150,
                                   progress_color=self.MODE_COLOR, button_color="#3b8ed0", height=16)
            slider.set(start_val)
            slider.pack(side="right", padx=10)
            
            def update_label(v, lbl=val_lbl):
                lbl.configure(text=str(int(v)), text_color=self.get_color(int(v)))
            
            slider.configure(command=update_label)
            sliders[db_key] = slider

        # Przyciski
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkButton(btn_frame, text="Anuluj", width=100, height=40, fg_color="#333",
                      command=dialog.destroy).pack(side="left")
        
        def save():
            try:
                data = {
                    "event_id": self.event['id'],
                    "player_id": pid,
                    "coach_name": coach_id,
                }
                
                for _, db_key in self.CRITERIA:
                    data[db_key] = int(sliders[db_key].get())
                
                data['team_code'] = self.event.get('team_code') or teams.get_current_team()
                supabase.table('ratings').upsert(data, on_conflict="event_id,player_id,coach_name").execute()
                
                dt_formatted = datetime.strptime(self.event['event_date'], "%Y-%m-%d").strftime("%d.%m.%Y")
                database.log_activity(f"ocenił {name} ({dt_formatted}) - {self.MODE_LABEL}")
                
                if existing:
                    existing.update(data)
                else:
                    self.all_ratings.append(data)
                
                try:
                    from cache_manager import cache
                    cache.invalidate("ratings")
                except: pass
                
                dialog.destroy()
                
                # ✅ NAJPIERW odśwież dane
                self.load_data()
                
                # ✅ POTEM pokaż powiadomienie (żeby było nad odświeżoną listą)
                self._show_success_notification("✓ Ocena zapisana pomyślnie!")
                
            except Exception as e:
                msgbox.showerror("Błąd", str(e))
        
        ctk.CTkButton(btn_frame, text="💾 Zapisz", width=140, height=40, fg_color="#2ecc71",
                      font=("Segoe UI", 13, "bold"), command=save).pack(side="right")

    def show_legend(self):
        leg = ctk.CTkToplevel(self)
        leg.title("Legenda")
        leg.geometry("300x220")
        leg.attributes("-topmost", True)
        leg.resizable(False, False)
        
        ctk.CTkLabel(leg, text="Skala ocen", font=("Segoe UI", 14, "bold")).pack(pady=15)
        
        items = [("1-3", "Słabo", "#e74c3c"), ("4-6", "Przeciętnie", "#f39c12"),
                 ("7-8", "Dobrze", "#3498db"), ("9-10", "Wzorowo", "#2ecc71")]
        
        for s, t, c in items:
            f = ctk.CTkFrame(leg, fg_color="transparent")
            f.pack(fill="x", padx=25, pady=4)
            ctk.CTkLabel(f, text=s, font=("Arial", 13, "bold"), text_color=c, width=50).pack(side="left")
            ctk.CTkLabel(f, text=t, font=("Segoe UI", 12)).pack(side="left", padx=8)
    
    def _show_success_notification(self, message):
        """Wyświetla powiadomienie na górze okna (kompatybilne Win/Mac)"""
        # Tworzymy overlay który pakujemy NA GÓRĘ hierarchii
        notif = ctk.CTkFrame(self, fg_color="#2ecc71", corner_radius=8, height=50)
        notif.pack(side="top", fill="x", padx=20, pady=(10, 0))
        notif.pack_propagate(False)  # Wymuszamy stałą wysokość
        
        ctk.CTkLabel(
            notif, 
            text=message, 
            font=("Segoe UI", 14, "bold"),
            text_color="white"
        ).pack(expand=True)
        
        # Podniesienie do góry hierarchii wizualnej
        notif.lift()
        
        # Auto-ukrycie po 2 sekundach
        def hide():
            notif.pack_forget()
            notif.destroy()
        
        self.after(2000, hide)