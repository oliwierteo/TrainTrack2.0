import PyInstaller.__main__
import traceback
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
        # universal2 = jeden plik działa na starszych i nowszych Macach.
        # Na maszynie GitHuba bywa z tym problem, więc można to wyłączyć:
        # TT_NO_UNIVERSAL=1 python build.py
        if os.environ.get('TT_NO_UNIVERSAL') != '1':
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
    except BaseException as e:
        print("\n" + "="*50)
        print(f"❌ BŁĄD KRYTYCZNY: {e}")
        traceback.print_exc()
        print("="*50)
        # BEZ tego build.py kończył się kodem 0 i GitHub Actions uważał
        # krok za udany mimo że nic nie powstało. Następny krok wtedy
        # wywalał się na "nie ma TrainTrack.app" bez żadnej przyczyny.
        sys.exit(1)

    # 7. Weryfikacja, że plik FAKTYCZNIE powstał
    #    PyInstaller potrafi wypisać "SUKCES" i nie zostawić nic w dist/.
    if system_os == 'Darwin':
        oczekiwany = os.path.join('dist', 'TrainTrack.app')
    else:
        oczekiwany = os.path.join('dist', 'TrainTrack.exe')

    if not os.path.exists(oczekiwany):
        print("\n" + "="*50)
        print(f"❌ Kompilacja nie wyprodukowała pliku: {oczekiwany}")
        print("Co jest w dist/:")
        if os.path.isdir('dist'):
            for nazwa in sorted(os.listdir('dist')):
                print(f"   - {nazwa}")
        else:
            print("   (folder dist/ w ogóle nie istnieje)")
        print("="*50)
        sys.exit(1)

    print("\n" + "="*50)
    print("✅ SUKCES! Aplikacja zbudowana.")

    dist_path = os.path.abspath('dist')
    print(f"📁 Wynik znajduje się w: {dist_path}")
    print(f"ℹ️  Plik: {oczekiwany}")

    if system_os == 'Darwin':
        print("ℹ️  Na Macu: dist/TrainTrack.app")
    else:
        print("ℹ️  Na Windows: dist/TrainTrack.exe")

    print("="*50)


if __name__ == "__main__":
    try:
        build_app()
    except SystemExit:
        raise
    except BaseException:
        # Nigdy nie kończ się kodem 0 po błędzie - inaczej CI kłamie,
        # że build się udał.
        traceback.print_exc()
        sys.exit(1)