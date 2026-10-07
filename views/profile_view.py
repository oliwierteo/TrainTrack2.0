import customtkinter as ctk
import tkinter.messagebox as msgbox
from database import supabase
from tkinter import filedialog
from image_manager import img_manager
from database import safe_int
import os
import threading
import time
import database
from logger import logger
from ui_async import run_async
import teams

PHOTO_BUCKET = "player-photos"


def storage_path_from_url(url, bucket=PHOTO_BUCKET):
    """
    Wyciąga ścieżkę obiektu z public URL Supabase Storage.
    '.../object/public/player-photos/abc.webp' -> 'abc.webp'
    """
    if not url:
        return None
    tail = str(url).split("?")[0].rstrip("/").split("/")
    if bucket in tail:
        idx = tail.index(bucket)
        parts = tail[idx + 1:]
        if parts:
            return "/".join(parts)
    return tail[-1] if tail else None


def delete_from_storage(url):
    """
    Usuwa plik ze storage. Nie wywala całej operacji, jeśli polityki
    (RLS/Storage) nie pozwalają - zwraca False i loguje ostrzeżenie.
    """
    path = storage_path_from_url(url)
    if not path:
        return False
    try:
        supabase.storage.from_(PHOTO_BUCKET).remove([path])
        logger.info(f"Usunięto plik ze storage: {path}")
        return True
    except Exception as e:
        logger.warning(
            f"Nie udało się usunąć pliku ze storage ({path}): {e}. "
            "Jeśli bucket jest prywatny lub RLS blokuje usuwanie - "
            "plik trzeba usunąć ręcznie w panelu Supabase.")
        return False

class ProfileView(ctk.CTkScrollableFrame):
    def __init__(self, master, player_data, on_back):
        super().__init__(master, fg_color="transparent")
        self.player_data = player_data
        self.on_back = on_back
        
        # Słowniki (jak wcześniej)
        self.GOAL_MAP = {"W trakcie": "w_trakcie", "Zrealizowany": "zrealizowany", "Brak celu": "brak_celu"}
        self.GOAL_MAP_REV = {v: k for k, v in self.GOAL_MAP.items()}
        self.HEALTH_MAP = {"Zdrowy": "zdrowy", "Lekki Uraz": "lekki_uraz", "Kontuzja": "kontuzja", "Chory": "chory", "Wykluczenie": "wykluczenie"}
        self.HEALTH_MAP_REV = {v: k for k, v in self.HEALTH_MAP.items()}

        # --- NAGŁÓWEK Z PRZYCISKAMI AKCJI (TERAZ NA GÓRZE) ---
        header_frame = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=15)
        header_frame.pack(fill="x", pady=(0, 20), padx=5)
        
        # Lewa strona nagłówka: Wróć i Tytuł
        left_head = ctk.CTkFrame(header_frame, fg_color="transparent")
        left_head.pack(side="left", padx=15, pady=15)
        
        ctk.CTkButton(left_head, text="< Wróć", width=70, fg_color="#333", command=on_back).pack(side="left")
        ctk.CTkLabel(left_head, text=f"  {player_data.get('full_name')}", font=("Segoe UI", 20, "bold")).pack(side="left")

        # Prawa strona nagłówka: ZAPISZ i USUŃ
        right_head = ctk.CTkFrame(header_frame, fg_color="transparent")
        right_head.pack(side="right", padx=15, pady=15)

        ctk.CTkButton(right_head, text="USUŃ 🗑️", width=80, fg_color="transparent", 
                      border_width=1, border_color="#cf352e", text_color="#cf352e", 
                      command=self.delete_player).pack(side="right", padx=5)
        
        ctk.CTkButton(right_head, text="ZAPISZ ZMIANY", width=150, fg_color="#2fa572", 
                      font=("Segoe UI", 13, "bold"), command=self.save_changes).pack(side="right", padx=5)

        # --- ZDJĘCIE PROFILOWE ---
        photo_frame = ctk.CTkFrame(self, fg_color="transparent")
        photo_frame.pack(fill="x", pady=10)
        
        self.profile_photo = ctk.CTkLabel(photo_frame, text="", width=120, height=120)
        self.profile_photo.pack(side="left", padx=20)
        
        self.btn_col = ctk.CTkFrame(photo_frame, fg_color="transparent")
        self.btn_col.pack(side="left", fill="y")

        self.btn_upload = ctk.CTkButton(self.btn_col, text="Zmień Zdjęcie 📸", width=140, command=self.upload_photo)
        self.btn_upload.pack(pady=5)

        self.btn_delete_photo = ctk.CTkButton(self.btn_col, text="Usuń Zdjęcie", width=140, 
                                            fg_color="transparent", border_width=1, border_color="#555", 
                                            command=self.delete_photo)
        self.btn_delete_photo.pack(pady=5)

        self.upload_progress = ctk.CTkProgressBar(self.btn_col, width=140, height=8)
        self.upload_progress.set(0)
        self.refresh_profile_image(self.player_data.get('photo_url'))

        # --- SEKCJA 1: DANE PODSTAWOWE ---
        self.create_section("Dane Podstawowe")
        self.name_entry = self.create_input("Imię i Nazwisko", player_data.get('full_name'))
        
        row1 = ctk.CTkFrame(self, fg_color="transparent")
        row1.pack(fill="x", pady=5)
        self.age_entry = self.create_input("Wiek", str(player_data.get('age') or ""), parent=row1, side="left")
        self.nr_entry = self.create_input("Nr na koszulce", str(player_data.get('jersey_number') or ""), parent=row1, side="right")

        row2 = ctk.CTkFrame(self, fg_color="transparent")
        row2.pack(fill="x", pady=5)
        self.pos_entry = self.create_input("Pozycja Główna", player_data.get('primary_position') or "", parent=row2, side="left")
        alt_pos_list = player_data.get('secondary_positions') or []
        self.alt_pos_entry = self.create_input("Pozycje Alt. (po przecinku)", ", ".join(alt_pos_list), parent=row2, side="right")

        self.club_entry = self.create_input("Klub", player_data.get('club_name') or "FC Szkółka")

        # --- DRUŻYNY (NOWE: jeden gracz może być w kilku drużynach) ---
        self.create_section("Drużyny")
        self.teams_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.teams_frame.pack(fill="x", pady=(5, 0))
        self._render_team_badges()
        ctk.CTkButton(
            self.teams_frame, text="⚽ Ustaw drużyny", width=180,
            fg_color="#2ecc71", hover_color="#27ae60",
            command=self.show_team_assign,
        ).pack(anchor="w", pady=(10, 0))
        ctk.CTkButton(
            self.teams_frame, text="🔀 Przenieś do innej drużyny", width=250,
            fg_color="#2a6a9e", hover_color="#1f6aa5",
            command=self.show_transfer_dialog,
        ).pack(anchor="w", pady=(6, 0))

        # --- SEKCJA 2: PROFIL SPORTOWY ---
        self.create_section("Profil Sportowy")
        ctk.CTkLabel(self, text="🎯 Zdolność kluczowa", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(10, 5))
        
        db_ability = player_data.get('key_ability')
        current_ability = db_ability.capitalize() if db_ability else "Brak"
        
        self.ability_var = ctk.StringVar(value=current_ability)
        self.ability_menu = ctk.CTkOptionMenu(
            self, variable=self.ability_var, 
            values=["Brak", "Strzelec", "Drybler", "Kreator", "Wojownik", "Bramkarz"],
            width=250
        )
        self.ability_menu.pack(anchor="w", pady=(0, 15))

        self.strengths = self.create_textbox("Mocne strony", player_data.get('strengths') or "")
        self.weaknesses = self.create_textbox("Słabe strony", player_data.get('weaknesses') or "")
        self.mental_strengths = self.create_textbox("🧠 Atuty mentalne", player_data.get('mental_strengths') or "")

        # Wiersz 3: Data dołączenia
        row3 = ctk.CTkFrame(self, fg_color="transparent")
        row3.pack(fill="x", pady=5)
        
        db_join = player_data.get('join_date') or datetime.date.today().isoformat()
        self.join_entry = self.create_input("Data dołączenia (RRRR-MM-DD)", db_join, parent=row3)

        # --- SEKCJA 3: CELE I ROZWÓJ ---
        self.create_section("Cele i Rozwój")
        self.goal_entry = self.create_input("Cel Główny", player_data.get('development_goal') or "")
        
        ctk.CTkLabel(self, text="Status Celu", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(10, 0))
        db_goal_status = player_data.get('goal_status') or "brak_celu"
        self.goal_status_var = ctk.StringVar(value=self.GOAL_MAP_REV.get(db_goal_status, "Brak celu"))
        ctk.CTkOptionMenu(self, variable=self.goal_status_var, values=list(self.GOAL_MAP.keys())).pack(anchor="w", pady=(5, 10))

        ctk.CTkLabel(self, text="Postęp Realizacji (%)", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(10, 0))
        self.prog_slider = ctk.CTkSlider(self, from_=0, to=100, number_of_steps=100)
        self.prog_slider.set(player_data.get('goal_progress') or 0)
        self.prog_slider.pack(fill="x", pady=5)
        
        # --- SEKCJA 4: ZDROWIE ---
        self.create_section("Zdrowie")
        ctk.CTkLabel(self, text="Status Zdrowotny", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(10, 0))
        db_health_status = player_data.get('health_status') or "zdrowy"
        self.health_var = ctk.StringVar(value=self.HEALTH_MAP_REV.get(db_health_status, "Zdrowy"))
        ctk.CTkOptionMenu(self, variable=self.health_var, values=list(self.HEALTH_MAP.keys()), fg_color="#c92c2c").pack(anchor="w", pady=(5, 10))
        self.injury_entry = self.create_input("Rodzaj urazu (opcjonalne)", player_data.get('injury_type') or "")


    # --- DRUŻYNY ---------------------------------------------------------
    def _render_team_badges(self):
        """Pokazuje, w jakich drużynach gracz aktualnie występuje."""
        for w in self.teams_frame.winfo_children():
            if isinstance(w, (ctk.CTkLabel, ctk.CTkFrame)):
                try:
                    w.destroy()
                except Exception:
                    pass

        try:
            terms = teams.get_active_terms(self.player_data['id'])
        except Exception as e:
            logger.error(f"Nie udało się pobrać drużyn gracza: {e}")
            terms = []

        if not terms:
            ctk.CTkLabel(
                self.teams_frame,
                text="⚠️  Gracz nie jest przypisany do żadnej drużyny",
                font=("Segoe UI", 12), text_color="#e67e22",
            ).pack(anchor="w")
            return

        for t in terms:
            team = teams.get_team(t['team_code']) or {}
            color = team.get('color', '#3b8ed0')
            row = ctk.CTkFrame(self.teams_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row, text="●", font=("Segoe UI", 16, "bold"),
                text_color=color,
            ).pack(side="left", padx=(0, 8))
            label = f"{team.get('name', t['team_code'])}"
            if t.get('is_primary'):
                label += "   (drużyna główna)"
            ctk.CTkLabel(
                row, text=label, font=("Segoe UI", 13, "bold"),
                anchor="w",
            ).pack(side="left")
            if t.get('joined_on'):
                ctk.CTkLabel(
                    row, text=f"od {t['joined_on']}",
                    font=("Segoe UI", 11), text_color="#888888",
                ).pack(side="left", padx=10)

    def show_team_assign(self):
        """Okno 'w jakich drużynach jest gracz' (dodaj / usuń / główna)."""
        try:
            from views.team_assign import TeamAssignDialog
            TeamAssignDialog(self, self.player_data,
                             on_changed=self._after_team_change)
        except Exception as e:
            logger.error(f"Nie udało się otworzyć okna drużyn: {e}")
            msgbox.showerror("Błąd", str(e))

    def _after_team_change(self):
        """Odśwież odznaki drużyn po zmianie z okna przypisań."""
        self._render_team_badges()
        try:
            import main as app
            root = self.winfo_toplevel()
            while root is not None and not hasattr(root, "refresh_team_list"):
                root = root.master
            if root is not None:
                root.refresh_team_list()
        except Exception:
            pass

    def show_transfer_dialog(self):
        """Przeniesienie gracza do innej drużyny (historia w bazie)."""
        visible = [t for t in teams.visible_teams(include_all=False)]
        if len(visible) < 2:
            msgbox.showinfo(
                "Drużyny",
                "Masz dostęp tylko do jednej drużyny - brak dokąd przenieść.")
            return

        modal = ctk.CTkToplevel(self)
        modal.title("🔀 Przenieś zawodnika")
        modal.attributes("-topmost", True)
        modal.transient(self)
        modal.grab_set()
        try:
            modal.geometry("520x300")
        except Exception:
            pass

        current = teams.primary_team_of(self.player_data['id'])
        ctk.CTkLabel(
            modal, text=f"Zawodnik: {self.player_data.get('full_name')}",
            font=("Segoe UI", 17, "bold"),
        ).pack(anchor="w", padx=25, pady=(22, 2))
        ctk.CTkLabel(
            modal, text=f"Obecnie: {teams.team_name(current) if current else 'brak'}",
            font=("Segoe UI", 12), text_color="#888888",
        ).pack(anchor="w", padx=25)

        ctk.CTkLabel(modal, text="Nowa drużyna:", font=("Segoe UI", 12, "bold")).pack(
            anchor="w", padx=25, pady=(16, 5))

        options = [t for t in visible if t['code'] != current]
        # skrót drużyny, a nie pełna nazwa (pełna jest w liście wyżej)
        labels = [teams.team_label(t['code']) for t in options]
        codes = [t['code'] for t in options]
        target = ctk.StringVar(value=labels[0] if labels else "")
        ctk.CTkOptionMenu(modal, variable=target, values=labels or ["—"],
                          width=420).pack(anchor="w", padx=25)

        def do_move():
            code = codes[labels.index(target.get())]
            modal.destroy()
            run_async(
                self,
                lambda: teams.move_player(self.player_data['id'], code,
                                          note="Przeniesiony z profilu gracza"),
                on_success=lambda res: self._after_transfer(res),
                on_error=lambda e: msgbox.showerror("Błąd", str(e)))

        ctk.CTkButton(modal, text="🔀 Przenieś", width=200, height=40,
                      fg_color="#2ecc71", hover_color="#27ae60",
                      command=do_move).pack(pady=25)

    def _after_transfer(self, result):
        ok, info = result
        if ok:
            msgbox.showinfo("Przeniesiono", info)
            self._render_team_badges()
        else:
            msgbox.showwarning("Nie przeniesiono", info)

    # --- FUNKCJE OBSŁUGI ZDJĘĆ ---

    def refresh_profile_image(self, url):
        img = img_manager.get_circular_image(
            self.player_data['id'], url, size=(120, 120),
            callback=lambda i: self.profile_photo.configure(image=i)
        )
        self.profile_photo.configure(image=img)

    def upload_photo(self):
        file_path = filedialog.askopenfilename(filetypes=[("Obrazy", "*.jpg *.jpeg *.png")])
        if not file_path: return
        
        self.btn_upload.configure(state="disabled")
        self.btn_delete_photo.pack_forget()
        self.upload_progress.pack(pady=10)
        self.upload_progress.set(0.1)

        def run_upload():
            try:
                from io import BytesIO
                from PIL import Image, ImageOps
                import time
                
                player_id = self.player_data['id']
                # ZMIANA: Rozszerzenie .webp
                filename = f"{player_id}_{int(time.time())}.webp"
                
                # Optymalizacja lokalna
                img = Image.open(file_path)
                
                # Konwersja kolorów (wymagane dla WebP)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGBA")
                else:
                    img = img.convert("RGB")

                # Smart crop (500x500)
                img_optimized = ImageOps.fit(img, (500, 500), centering=(0.5, 0.3))
                
                # Zapis do bufora jako WEBP
                buffer = BytesIO()
                # lossless=True zachowuje idealną jakość przy małym rozmiarze
                img_optimized.save(buffer, format="WEBP", quality=85, method=6)
                buffer.seek(0)
                
                self.after(0, lambda: self.upload_progress.set(0.4))

                # 1. Upload do Supabase
                supabase.storage.from_("player-photos").upload(
                    path=filename, 
                    file=buffer.getvalue(), 
                    file_options={"content-type": "image/webp"} # ZMIANA: image/webp
                )
                self.after(0, lambda: self.upload_progress.set(0.7))
                
                # 2. Pobierz URL
                old_url = self.player_data.get('photo_url')
                public_url = supabase.storage.from_(PHOTO_BUCKET).get_public_url(filename)

                # FIX: stary plik zostawał w bucketcie na zawsze - przy
                # każdym nowym zdjęciu powstawał kolejny plik, którego nikt
                # nie usuwał. Teraz czyścimy poprzedni (zdjęcia nieletnich).
                if old_url and old_url != public_url:
                    delete_from_storage(old_url)
                supabase.table('players').update({"photo_url": public_url}).eq('id', player_id).execute()
                
                # 3. CZYSZCZENIE CACHE
                keys_to_del = [k for k in img_manager.memory_cache.keys() if k.startswith(f"{player_id}_")]
                for k in keys_to_del: del img_manager.memory_cache[k]
                
                # Usuwamy stare pliki z dysku (zarówno .png jak i .webp, dla pewności)
                for ext in ["png", "webp"]:
                    local_path = os.path.join(img_manager.img_dir, f"{player_id}.{ext}")
                    if os.path.exists(local_path):
                        try: os.remove(local_path)
                        except: pass
                
                self.player_data['photo_url'] = public_url
                self.after(0, lambda: self.finish_upload(public_url))
                
            except Exception as e:
                err_txt = str(e)
                self.after(0, lambda: self.reset_upload_ui(f"Błąd: {err_txt}"))
                
        threading.Thread(target=run_upload, daemon=True).start()

    def finish_upload(self, new_url):
        """Aktualizuje zdjęcie w profilu po sukcesie"""
        self.upload_progress.set(1.0)
        # Dajemy 500ms przerwy, żeby cache na serwerach Supabase się odświeżył
        self.after(500, lambda: self.refresh_profile_image(new_url))
        # Resetujemy UI
        self.after(1000, lambda: self.reset_upload_ui("Zdjęcie zaktualizowane!"))
        # Ważne: Inwalidacja cache zawodników
        from cache_manager import cache
        cache.invalidate("players")

    def delete_photo(self):
        if not self.player_data.get('photo_url'): return
        
        if msgbox.askyesno("Usuń", "Czy na pewnie chcesz usunąć zdjęcie profilowe?"):
            # FIX: operacja sieciowa leci w wątku (wcześniej blokowała UI),
            # a sam plik jest USUWANY ze storage - samo wyczyszczenie bazy
            # zostawiało zdjęcie nadal publicznie dostępne pod linkiem.
            self.btn_upload.configure(state="disabled")
            old_url = self.player_data.get('photo_url')

            def _delete():
                try:
                    pid = self.player_data['id']
                    supabase.table('players').update({"photo_url": None}).eq('id', pid).execute()
                    delete_from_storage(old_url)
                    self.after(0, lambda: self._finish_delete_photo(pid))
                except Exception as e:
                    self.after(0, lambda: self._fail_delete_photo(str(e)))

            threading.Thread(target=_delete, daemon=True).start()

    def _fail_delete_photo(self, error):
        self.btn_upload.configure(state="normal")
        msgbox.showerror("Błąd", f"Nie udało się usunąć zdjęcia: {error}")

    def _finish_delete_photo(self, pid):
        """Sprzątanie po udanym usunięciu (wątek główny Tkintera)."""
        try:
            # 1. Cache RAM managera zdjęć
            with img_manager._cache_lock:
                keys_to_del = [k for k in img_manager.memory_cache.keys()
                               if k.startswith(f"{pid}_")]
                for k in keys_to_del:
                    del img_manager.memory_cache[k]

            # 2. Cache zdjęć na dysku (wszystkie formaty)
            for ext in [".png", ".webp", ".jpg"]:
                local_path = os.path.join(img_manager.img_dir, f"{pid}{ext}")
                if os.path.exists(local_path):
                    try:
                        os.remove(local_path)
                    except OSError as e:
                        logger.warning(f"Nie udało się usunąć {local_path}: {e}")

            # 3. Aktualizacja UI
            self.player_data['photo_url'] = None
            self.refresh_profile_image(None)   # wymuś placeholder
            self.btn_upload.configure(state="normal")

            # 4. Odśwież listę główną
            from cache_manager import cache
            cache.invalidate("players")
            cache.invalidate("all_players")

            msgbox.showinfo("Sukces", "Zdjęcie zostało usunięte.")
        except Exception as e:
            logger.error(f"Błąd finalizacji usunięcia zdjęcia: {e}")
            self.btn_upload.configure(state="normal")
            msgbox.showerror("Błąd", f"Nie udało się usunąć zdjęcia: {e}")

    def reset_upload_ui(self, message):
        self.btn_upload.configure(state="normal")
        self.upload_progress.pack_forget()
        self.btn_delete_photo.pack(pady=5)
        if "Błąd" in message: msgbox.showerror("Błąd", message)
        elif "zaktualizowane" in message: msgbox.showinfo("Sukces", message)

    # --- POMOCNIKI UI ---

    def create_section(self, text):
        ctk.CTkLabel(self, text=text.upper(), font=("Segoe UI", 14, "bold"), text_color="#3b8ed0").pack(anchor="w", pady=(20, 5))
        ctk.CTkFrame(self, height=2, fg_color="#3a3a3a").pack(fill="x", pady=(0, 10))

    def create_input(self, label, value, parent=None, side=None):
        target = parent if parent else self
        frame = ctk.CTkFrame(target, fg_color="transparent")
        frame.pack(side=side if side else "top", fill="x", expand=True, padx=5)
        ctk.CTkLabel(frame, text=label, font=("Segoe UI", 12)).pack(anchor="w")
        entry = ctk.CTkEntry(frame)
        entry.insert(0, str(value))
        entry.pack(fill="x")
        return entry

    def create_textbox(self, label, value):
        ctk.CTkLabel(self, text=label, font=("Segoe UI", 12)).pack(anchor="w", pady=(5,0))
        tb = ctk.CTkTextbox(self, height=80)
        tb.insert("0.0", value)
        tb.pack(fill="x", pady=5)
        return tb

    def save_changes(self):
        try:
            alt_pos_raw = self.alt_pos_entry.get()
            alt_pos_arr = [x.strip() for x in alt_pos_raw.split(",")] if alt_pos_raw else []

            update_data = {
                "full_name": self.name_entry.get(),
                "age": safe_int(self.age_entry.get(), default=None),
                "jersey_number": safe_int(self.nr_entry.get(), default=None),
                "primary_position": self.pos_entry.get(),
                "secondary_positions": alt_pos_arr,
                "club_name": self.club_entry.get(), 
                "key_ability": self.ability_var.get().lower() if self.ability_var.get() != "Brak" else None,
                "strengths": self.strengths.get("0.0", "end").strip(),
                "weaknesses": self.weaknesses.get("0.0", "end").strip(),
                "mental_strengths": self.mental_strengths.get("0.0", "end").strip(),
                "development_goal": self.goal_entry.get(),
                "goal_status": self.GOAL_MAP.get(self.goal_status_var.get(), "brak_celu"),
                "goal_progress": int(self.prog_slider.get()),
                "health_status": self.HEALTH_MAP.get(self.health_var.get(), "zdrowy"),
                "injury_type": self.injury_entry.get(),
                "join_date": self.join_entry.get(), # <-- DODAJ
            }
            

            player_id = self.player_data['id']
        except Exception as e:
            msgbox.showerror("Błąd", f"Nie udało się zapisać: {e}")
            return

        # FIX: UPDATE do bazy leci w wątku - okno nie zamraża się na czas sieci.
        def _work():
            supabase.table('players').update(update_data).eq('id', player_id).execute()

        def _ok(_result=None):
            from cache_manager import cache
            cache.invalidate("players")
            cache.invalidate("all_players")
            self.on_back()

        run_async(self, _work, on_success=_ok,
                  on_error=lambda e: msgbox.showerror(
                      "Błąd", f"Nie udało się zapisać: {e}"))

    def delete_player(self):
        player_id = self.player_data['id']
        name = self.player_data.get('full_name')

        # NIE usuwamy zawodnika będącego w innej drużynie niż Twoja:
        # kasowanie gracza z AK1 skasowałoby go też z drużyny I.
        # (ta sama zasada co przy zapisie kadry - patrz teams.guard_teams)
        mine = [t for t in teams.get_active_terms(player_id)
                if teams.can_edit_team(t.get("team_code"))]
        foreign = [t.get("team_code") for t in teams.get_active_terms(player_id)
                   if not teams.can_edit_team(t.get("team_code"))]
        if foreign:
            msgbox.showwarning(
                "Nie można usunąć",
                f"{name} jest też w drużynie "
                f"{', '.join(teams.team_short(c) or c for c in foreign)}, "
                f"do której nie masz dostępu.\n\nUsunięcie skasowałby go "
                f"stamtąd. Poproś o to kierownika tej drużyny.")
            return

        confirm = msgbox.askyesno(
            "Potwierdzenie",
            f"Czy na pewno chcesz usunąć zawodnika:\n{name}?\n\n"
            f"Usunięcie jest nieodwracalne - historia też zniknie.")
        if not confirm:
            return

        def _work():
            supabase.table('players').delete().eq('id', player_id).execute()

        # BUG Z KONSOLI: run_async woła on_success(WYNIK) - funkcja
        # bez argumentów wywalała TypeError PO udanym usunięciu
        # (zawodnik znikał, ale UI się nie odświeżało).
        def _ok(_result=None):
            from cache_manager import cache
            cache.invalidate("players")
            cache.invalidate("all_players")
            cache.invalidate("roster")
            self.on_back()

        run_async(self, _work, on_success=_ok,
                  on_error=lambda e: msgbox.showerror(
                      "Błąd", f"Nie udało się usunąć: {e}"))