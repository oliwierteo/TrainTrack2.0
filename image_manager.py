# image_manager.py
import os
import sys
import requests
from PIL import Image, ImageOps, ImageDraw
import customtkinter as ctk
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from logger import logger
import threading

class ImageManager:
    """
    ZOPTYMALIZOWANY MANAGER ZDJĘĆ v2.0
    - Pula wątków (max 3 jednocześnie)
    - Cache RAM + Dysk
    - Obsługa WebP/PNG/JPG
    - Thread-safe
    - Mac + Windows compatible
    """
    
    def __init__(self):
        # Folder cache zależny od systemu
        if sys.platform == "darwin":
            # macOS: ~/Library/Caches/TrainTrack/images
            self.img_dir = os.path.expanduser("~/Library/Caches/TrainTrack/images")
        else:
            # Windows: %APPDATA%/TrainTrack/cache/images
            self.img_dir = os.path.join(
                os.environ.get('APPDATA', os.path.expanduser('~')), 
                'TrainTrack', 'cache', 'images'
            )
        
        # Utwórz folder jeśli nie istnieje
        try:
            os.makedirs(self.img_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Błąd tworzenia folderu zdjęć: {e}")
            # Fallback - temp folder
            import tempfile
            self.img_dir = os.path.join(tempfile.gettempdir(), 'TrainTrack_images')
            os.makedirs(self.img_dir, exist_ok=True)
        
        # Cache w pamięci RAM (szybki dostęp)
        self.memory_cache = {}
        self._cache_lock = threading.RLock()
        
        # Placeholder (domyślny awatar)
        self.placeholder = None
        self._placeholder_cache = {}  # Różne rozmiary
        
        # Pula wątków do pobierania (max 3 jednocześnie)
        self._executor = ThreadPoolExecutor(
            max_workers=3, 
            thread_name_prefix="ImageLoader"
        )
        
        logger.info(f"📸 ImageManager - folder: {self.img_dir}")

    def get_circular_image(self, player_id, photo_url, size=(50, 50), callback=None):
        """
        Pobiera okrągłe zdjęcie zawodnika (z cache lub internetu)
        
        Args:
            player_id: UUID gracza
            photo_url: URL zdjęcia z Supabase (lub None)
            size: tuple (width, height) - rozmiar docelowy
            callback: funkcja wywoływana po załadowaniu (opcjonalna)
        
        Returns:
            CTkImage - placeholder na start, potem aktualizowany przez callback
        """
        if not player_id:
            return self._get_placeholder(size)
        
        cache_key = f"{player_id}_{size[0]}x{size[1]}"
        
        # 1. Sprawdź cache RAM (najszybsze)
        with self._cache_lock:
            if cache_key in self.memory_cache:
                img = self.memory_cache[cache_key]
                if callback:
                    try:
                        callback(img)
                    except Exception as e:
                        logger.error(f"Błąd callback RAM: {e}")
                return img
        
        # 2. Zwróć placeholder na start
        placeholder = self._get_placeholder(size)
        
        # 3. Załaduj rzeczywiste zdjęcie w tle (przez pulę wątków)
        def load_task():
            try:
                ext = self._detect_extension(photo_url)
                local_path = os.path.join(self.img_dir, f"{player_id}{ext}")
                
                img_data = None
                
                if os.path.exists(local_path):
                    try:
                        if os.path.getsize(local_path) > 0:
                            img_data = Image.open(local_path)
                            img_data.load()
                    except Exception:
                        try:
                            os.remove(local_path)
                        except Exception:
                            pass
                
                if not img_data and photo_url:
                    img_data = self._download_image(photo_url, local_path)
                
                if img_data:
                    self._process_and_cache(img_data, size, cache_key, callback)
                else:
                    if callback:
                        try:
                            callback(placeholder)
                        except Exception:
                            pass
                            
            except Exception:
                if callback:
                    try:
                        callback(placeholder)
                    except Exception:
                        pass
        
        # Submit do puli wątków (nie tworzy nowego wątku za każdym razem)
        self._executor.submit(load_task)
        
        return placeholder

    def _detect_extension(self, url):
        """Wykrywa rozszerzenie pliku z URL"""
        if not url:
            return ".webp"  # Domyślne
        
        url_lower = url.lower()
        if ".png" in url_lower:
            return ".png"
        elif ".jpg" in url_lower or ".jpeg" in url_lower:
            return ".jpg"
        else:
            return ".webp"

    def _download_image(self, url, save_path):
        """
        Pobiera zdjęcie z internetu i zapisuje lokalnie
        
        Returns:
            PIL.Image lub None
        """
        try:
            response = requests.get(url, timeout=8, stream=True)
            
            if response.status_code == 200:
                # Wczytaj do pamięci
                img_bytes = BytesIO(response.content)
                img = Image.open(img_bytes)
                img.load()  # Wymusza pełne wczytanie
                
                # Zapisz na dysk (cache offline)
                try:
                    with open(save_path, 'wb') as f:
                        f.write(response.content)
                except Exception as e:
                    logger.error(f"Błąd zapisu pliku {save_path}: {e}")
                
                return img
            else:
                logger.error(f"HTTP {response.status_code} dla {url}")
                return None
                
        except requests.Timeout:
            logger.error(f"Timeout pobierania: {url}")
            return None
        except Exception as e:
            logger.error(f"Błąd pobierania {url}: {e}")
            return None

    def _process_and_cache(self, img, size, cache_key, callback):
        """
        Przetwarza obraz na okrąg i zapisuje w cache RAM
        """
        try:
            # 1. Smart crop (środek góra)
            img_cropped = ImageOps.fit(img, size, centering=(0.5, 0.3))
            
            # 2. Konwersja na RGBA (dla przezroczystości)
            if img_cropped.mode != 'RGBA':
                img_cropped = img_cropped.convert('RGBA')
            
            # 3. Maska okręgu
            mask = Image.new('L', size, 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0) + size, fill=255)
            
            # 4. Aplikuj maskę
            img_cropped.putalpha(mask)
            
            # 5. Konwersja na CTkImage
            ctk_img = ctk.CTkImage(
                light_image=img_cropped, 
                dark_image=img_cropped, 
                size=size
            )
            
            # 6. Zapisz w cache RAM
            with self._cache_lock:
                self.memory_cache[cache_key] = ctk_img
            
            # 7. Wywołaj callback (aktualizuj UI)
            if callback:
                try:
                    callback(ctk_img)
                except Exception:
                    pass
                    
        except Exception as e:
            logger.error(f"Błąd przetwarzania obrazu: {e}")

    def _get_placeholder(self, size):
        """
        Generuje szare kółko jako placeholder
        
        Cache'uje różne rozmiary żeby nie tworzyć za każdym razem
        """
        size_key = f"{size[0]}x{size[1]}"
        
        # Sprawdź cache placeholderów
        if size_key in self._placeholder_cache:
            return self._placeholder_cache[size_key]
        
        try:
            # Utwórz szare tło
            img = Image.new('RGBA', size, (50, 50, 50, 255))
            
            # Maska okręgu
            mask = Image.new('L', size, 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0) + size, fill=255)
            
            # Aplikuj
            output = ImageOps.fit(img, size, centering=(0.5, 0.5))
            output.putalpha(mask)
            
            # Opcjonalnie: Dodaj ikonę użytkownika (Unicode)
            try:
                from PIL import ImageFont
                # Emoji użytkownika
                draw_text = ImageDraw.Draw(output)
                font_size = int(size[0] * 0.5)
                # Fallback font - systemowy
                try:
                    if sys.platform == "darwin":
                        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
                    else:
                        font = ImageFont.truetype("arial.ttf", font_size)
                except:
                    font = ImageFont.load_default()
                
                text = "👤"
                
                # Wyśrodkuj tekst
                bbox = draw_text.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                position = ((size[0] - text_width) // 2, (size[1] - text_height) // 2 - font_size // 4)
                
                draw_text.text(position, text, fill=(150, 150, 150, 255), font=font)
            except:
                pass  # Jeśli nie uda się dodać ikony - zwykłe szare kółko
            
            # Konwersja na CTkImage
            ctk_img = ctk.CTkImage(
                light_image=output, 
                dark_image=output, 
                size=size
            )
            
            # Cache
            self._placeholder_cache[size_key] = ctk_img
            
            return ctk_img
            
        except Exception as e:
            logger.error(f"Błąd tworzenia placeholder: {e}")
            # Absolute fallback - puste CTkImage
            empty = Image.new('RGBA', size, (40, 40, 40, 255))
            return ctk.CTkImage(light_image=empty, dark_image=empty, size=size)

    def clear_memory_cache(self):
        """Czyści cache RAM (zdjęcia zostają na dysku)"""
        with self._cache_lock:
            cleared = len(self.memory_cache)
            self.memory_cache.clear()
            self._placeholder_cache.clear()
        logger.info(f"🗑️ Wyczyszczono {cleared} zdjęć z RAM")

    def clear_disk_cache(self):
        """Czyści zdjęcia z dysku (UWAGA: wymaga ponownego pobierania)"""
        try:
            import shutil
            if os.path.exists(self.img_dir):
                shutil.rmtree(self.img_dir)
                os.makedirs(self.img_dir, exist_ok=True)
                logger.info(f"🗑️ Wyczyszczono folder: {self.img_dir}")
            
            # Wyczyść też RAM
            self.clear_memory_cache()
            
        except Exception as e:
            logger.error(f"Błąd czyszczenia dysku: {e}")

    def get_cache_size(self):
        """Zwraca rozmiar cache na dysku (w MB)"""
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(self.img_dir):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
            
            return round(total_size / (1024 * 1024), 2)  # MB
        except:
            return 0

    def preload_images(self, player_ids, photo_urls, size=(50, 50)):
        """
        Preload wielu zdjęć w tle (przydatne przy starcie widoku)
        
        Args:
            player_ids: lista UUID graczy
            photo_urls: lista URL (ta sama kolejność)
            size: rozmiar docelowy
        """
        def preload_task():
            for pid, url in zip(player_ids, photo_urls):
                if pid:
                    self.get_circular_image(pid, url, size, callback=None)
        
        self._executor.submit(preload_task)

    def shutdown(self):
        """Bezpieczne zamknięcie (wywołaj przy zamykaniu aplikacji)"""
        try:
            self._executor.shutdown(wait=False)
            logger.info("📸 ImageManager zamknięty")
        except:
            pass

# =============================================
# GLOBALNA INSTANCJA
# =============================================
img_manager = ImageManager()

# Opcjonalnie: Cleanup przy zamknięciu Pythona
import atexit
atexit.register(img_manager.shutdown)