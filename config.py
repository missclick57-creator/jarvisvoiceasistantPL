"""
JARVIS Configuration
Centralna konfiguracja asystenta głosowego.
"""
import os

# === Ścieżki ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VOICE_PROFILE_DIR = os.path.join(BASE_DIR, "voice_profile")
os.makedirs(VOICE_PROFILE_DIR, exist_ok=True)

# === Ustawienia głosu JARVIS (TTS) ===
JARVIS_VOICE_RATE = 175       # Szybkość mowy (słowa/min)
JARVIS_VOICE_VOLUME = 1.0     # Głośność (0.0 - 1.0)
JARVIS_NAME = "Jarvis"

# === Rozpoznawanie mowy (STT) ===
STT_LANGUAGE = "pl-PL"        # Język komend (polski)
WAKE_WORD = "jarvis"          # Słowo budzące
LISTEN_TIMEOUT = 5            # Timeout nasłuchiwania (sekundy)
PHRASE_TIMEOUT = 10           # Max czas frazy (sekundy)
AMBIENT_DURATION = 1          # Czas kalibracji szumu (sekundy)

# === Speaker Verification (Weryfikacja mówcy) ===
ENROLLMENT_SAMPLES = 5                # Liczba próbek do rejestracji głosu
SIMILARITY_THRESHOLD = 0.55           # Optymalny próg podobieństwa (0.0 - 1.0)
SPEAKER_PROFILE_FILE = os.path.join(VOICE_PROFILE_DIR, "speaker_profile.npy")
ENROLLMENT_SAMPLE_DURATION = 2.5      # Czas nagrywania jednej próbki (sekundy)
SAMPLE_RATE = 16000                   # Częstotliwość próbkowania audio

# === Mapa aplikacji (komenda -> proces/ścieżka) ===
APPS = {
    # Przeglądarki
    "chrome": "chrome.exe",
    "przeglądarka": "chrome.exe",
    "google": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "brave": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    "apple music": r"ms-windows-store://pdp/?productid=9PF4KZ2VN4BU",
    "applemusic": r"ms-windows-store://pdp/?productid=9PF4KZ2VN4BU",
    # Narzędzia systemowe
    "notatnik": "notepad.exe",
    "notepad": "notepad.exe",
    "kalkulator": "calc.exe",
    "calculator": "calc.exe",
    "eksplorator": "explorer.exe",
    "explorer": "explorer.exe",
    "terminal": "wt.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "menedżer zadań": "taskmgr.exe",
    "task manager": "taskmgr.exe",
    "ustawienia": "ms-settings:",
    "settings": "ms-settings:",
    "panel sterowania": "control.exe",
    # Multimedia
    "spotify": "spotify.exe",
    # Komunikacja
    "discord": "discord.exe",
    "teams": "teams.exe",
    # Gaming
    "steam": "steam.exe",
    # Office
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    # Grafika
    "paint": "mspaint.exe",
    "photos": "ms-photos:",
    "zdjęcia": "ms-photos:",
}

# === Komendy głośności ===
VOLUME_STEP = 10  # Krok zmiany głośności (%)

# === Powitania ===
GREETING_MESSAGES = [
    "Tak jest, sir.",
    "Co mogę zrobić, sir?",
    "Tak jest. Czekam na polecenie.",
    "Słucham, sir.",
    "Do usług, sir.",
]

FAREWELL_MESSAGES = [
    "Do widzenia, sir. Będę czekał.",
    "Rozumiem. Przechodzę w tryb nasłuchiwania.",
    "Oczywiście, sir. Do usłyszenia.",
]

UNKNOWN_COMMAND_MESSAGES = [
    "Przepraszam, sir. Nie rozumiem tego polecenia.",
    "Nie jestem pewien co mam zrobić, sir.",
    "Nie rozpoznaję tej komendy, sir. Proszę powtórzyć.",
]

UNAUTHORIZED_MESSAGES = [
    "Nie rozpoznaję tego głosu. Odmawiam dostępu.",
    "Głos niezidentyfikowany. Nie mogę wykonać polecenia.",
    "Przepraszam, ale nie jesteś autoryzowanym użytkownikiem.",
]

# === Konfiguracja Gemini AI ===
GEMINI_API_KEY = "AQ.Ab8RN6LogK6XdIR0YahR5DX9Fxplt5V94An7fL7NNeUn0rYv9Q"
GEMINI_MODEL = "gemini-3.6-flash"

