import PyInstaller.__main__
import os
import shutil
import platform
import sys

def build_app():
    system_os = platform.system()
    print(f"🚀 Rozpoczynam budowanie TrainTrack PRO na {system_os}...")

    # 1. Czyszczenie starych plików
    print("🧹 Czyszczenie folderów build/ i dist/...")
    if os.path.exists('build'): shutil.rmtree('build')
    if os.path.exists('dist'): shutil.rmtree('dist')
    
    # Usuń stare pliki spec (żeby wygenerować świeże)
    for f in os.listdir('.'):
        if f.endswith('.spec'):
            try:
                os.remove(f)
            except: pass

    # 2. Separator ścieżek
    sep = ';' if system_os == 'Windows' else ':'

    # 3. Lista ukrytych importów (bezpieczna lista)
    hidden_imports = [
        # Twoje moduły
        'pdf_generator',
        'cache_manager',
        'image_manager',
        'database',
        'logger',
        'formations',
        'teams',
        'ui_async',
        
        # Widoki
        'views',
        'views.login_view',
        'views.splash_view',
        'views.dashboard_view',
        'views.players_view',
        'views.profile_view',
        'views.calendar_view',
        'views.stats_view',
        'views.analysis_view',
        'views.ratings_view',
        'views.squad_view',
        'views.scouting_view',
        'views.finances_view',
        'views.development_center_view',
        'views.teams_view',
        
        # Biblioteki zewnętrzne
        'customtkinter',
        'PIL',
        'PIL._tkinter_finder',
        'supabase',
        'postgrest',
        'gotrue',
        'realtime',
        'storage3',
        'dateutil',
        'requests',
        'reportlab',
        'reportlab.pdfbase',
        'reportlab.pdfbase.ttfonts',
        'reportlab.standardfonts'
    ]

    # Dodaj flagę hidden-import dla każdego modułu
    hidden_imports_args = []
    for mod in hidden_imports:
        hidden_imports_args.append(f'--hidden-import={mod}')

    # 4. Podstawowa konfiguracja PyInstallera
    opts = [
        'main.py',                       # Główny plik
        '--name=TrainTrack',             # Nazwa pliku wynikowego
        '--noconsole',                   # Ukryj konsolę
        '--clean',                       # Wyczyść cache
        f'--add-data=assets{sep}assets', # Dołącz folder assets
        '--collect-all=customtkinter',   # Zbierz wszystko z CTk (motywy)
        '--collect-all=reportlab',       # Zbierz fonty z reportlab
    ] + hidden_imports_args

    # 5. Konfiguracja specyficzna dla systemu
    if system_os == 'Windows':
        print("🪟 Konfiguracja Windows...")
        opts.append('--onefile')  # Na Windows wolisz jeden plik .exe
        
        if os.path.exists('assets/icon.ico'):
            opts.append('--icon=assets/icon.ico')
            print("✅ Dodano ikonę .ico")
            
    elif system_os == 'Darwin':  # macOS
        print("🍎 Konfiguracja macOS...")
        opts.append('--onedir')  # Na Macu lepiej budować folder .app
        opts.append('--windowed')
        opts.append('--target-arch=universal2')
        
        if os.path.exists('assets/icon.icns'):
            opts.append('--icon=assets/icon.icns')
            print("✅ Dodano ikonę .icns")
            
        # Dodaj bundle identifier dla macOS
        opts.append('--osx-bundle-identifier=com.chelmianka.traintrack')

    # 6. Uruchomienie
    print("🔨 Kompilacja w toku... (może potrwać kilka minut)")
    try:
        PyInstaller.__main__.run(opts)
        
        print("\n" + "="*50)
        print("✅ SUKCES! Aplikacja zbudowana.")
        
        dist_path = os.path.abspath('dist')
        print(f"📁 Wynik znajduje się w: {dist_path}")
        
        if system_os == 'Darwin':
            print("ℹ️  Na Macu: dist/TrainTrack.app")
        else:
            print("ℹ️  Na Windows: dist/TrainTrack.exe")
            
        print("="*50)
        
    except Exception as e:
        print(f"\n❌ BŁĄD KRYTYCZNY: {e}")

if __name__ == "__main__":
    build_app()