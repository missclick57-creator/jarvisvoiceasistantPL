"""
jarvis_system.py
System controller module for JARVIS. Handles Windows system operations.
"""
import os
import subprocess
import psutil
import pyautogui
import datetime
import requests
import ctypes
import webbrowser
import re
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

try:
    import config
except ImportError:
    # Dummy config for testing if config doesn't exist yet
    class DummyConfig:
        APPS = {
            "notatnik": "notepad.exe",
            "kalkulator": "calc.exe",
            "przeglądarka": "msedge.exe",
        }
    config = DummyConfig()


class SystemController:
    """Klasa kontrolująca operacje systemowe Windows."""
    
    def __init__(self):
        self._installed_apps = {}
        import threading
        threading.Thread(target=self._scan_installed_apps, daemon=True).start()

    def _scan_installed_apps(self):
        """Skanuje system (Menu Start i Pulpity) w poszukiwaniu zainstalowanych aplikacji."""
        self._installed_apps = {}
        
        # Lokacje skrótów Menu Start i Pulpitu
        paths = [
            os.path.join(os.environ.get('ProgramData', r'C:\ProgramData'), r'Microsoft\Windows\Start Menu\Programs'),
            os.path.join(os.environ.get('APPDATA', ''), r'Microsoft\Windows\Start Menu\Programs'),
            os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop'),
            r'C:\Users\Public\Desktop'
        ]
        
        for base_path in paths:
            if not os.path.exists(base_path):
                continue
            for root, dirs, files in os.walk(base_path):
                for file in files:
                    if file.lower().endswith(('.lnk', '.url')):
                        name = os.path.splitext(file)[0].lower().strip()
                        full_path = os.path.join(root, file)
                        if name not in self._installed_apps:
                            self._installed_apps[name] = full_path

    def find_installed_app(self, name: str) -> str:
        """Przeszukuje zainstalowane aplikacje i zwraca ścieżkę do skrótu."""
        name = name.lower().strip()
        
        # 1. Dokładne dopasowanie
        if name in self._installed_apps:
            return self._installed_apps[name]
            
        # 2. Dopasowanie jako podciąg
        for app_name, path in self._installed_apps.items():
            if name in app_name or app_name in name:
                return path
                
        # 3. Znormalizowane dopasowanie (usuwanie spacji i znaków diakrytycznych)
        def clean_str(s):
            import unicodedata
            s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
            return ''.join(e for e in s if e.isalnum())
            
        clean_name = clean_str(name)
        for app_name, path in self._installed_apps.items():
            if clean_name in clean_str(app_name) or clean_str(app_name) in clean_name:
                return path
                
        return None

    # --- App Management ---
    def open_app(self, app_name: str) -> str:
        """Otwiera aplikację."""
        app_name = app_name.lower().strip()
        
        # 1. Sprawdź ręcznie zdefiniowaną mapę
        app_path = config.APPS.get(app_name)
        
        # 2. Jeśli nie ma w mapie, przeszukaj dynamicznie zainstalowane aplikacje
        if not app_path:
            app_path = self.find_installed_app(app_name)
            
        if not app_path:
            return f"Nie znam aplikacji {app_name}."
        
        try:
            def launch():
                try:
                    if app_path.endswith(('.lnk', '.url')) or app_path.startswith("ms-"):
                        os.startfile(app_path)
                    else:
                        if app_name == "brave":
                            paths = [
                                r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                                r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
                                os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe")
                            ]
                            for p in paths:
                                if os.path.exists(p):
                                    subprocess.Popen(p)
                                    return
                        subprocess.Popen(app_path)
                except Exception as ex:
                    print(f"[LAUNCH ERROR] {ex}")

            import threading
            threading.Thread(target=launch, daemon=True).start()
            return f"Otwieram {app_name}."
        except Exception as e:
            return f"Wystąpił błąd podczas otwierania {app_name}: {e}"

    def close_app(self, app_name: str) -> str:
        """Zamyka aplikację."""
        app_name = app_name.lower().strip()
        target_process = config.APPS.get(app_name, app_name)
        
        if target_process.endswith('.exe'):
            target_exe = target_process
        else:
            target_exe = f"{target_process}.exe"
            
        closed = False
        try:
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and proc.info['name'].lower() == target_exe.lower():
                    proc.kill()
                    closed = True
            if closed:
                return f"Zamknęłam {app_name}."
            return f"Aplikacja {app_name} nie była uruchomiona."
        except Exception as e:
            return f"Nie udało się zamknąć {app_name}: {e}"

    def list_running_apps(self) -> str:
        """Zwraca listę ważniejszych uruchomionych aplikacji."""
        notable = ['chrome.exe', 'msedge.exe', 'firefox.exe', 'notepad.exe', 'code.exe', 'spotify.exe']
        running = set()
        for proc in psutil.process_iter(['name']):
            try:
                name = proc.info['name']
                if name and name.lower() in notable:
                    running.add(name.replace('.exe', ''))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if running:
            return f"Obecnie uruchomione to między innymi: {', '.join(running)}."
        return "Nie widzę żadnych ważniejszych uruchomionych aplikacji."

    # --- Volume Control ---
    def _get_volume_interface(self):
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))

    def set_volume(self, level: int) -> str:
        """Ustawia głośność na podany procent (0-100)."""
        level = max(0, min(100, level))
        try:
            volume = self._get_volume_interface()
            volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            return f"Głośność ustawiona na {level} procent."
        except Exception as e:
            return f"Nie udało się zmienić głośności: {e}"

    def change_volume(self, delta: int) -> str:
        """Zmienia głośność o delta procent."""
        try:
            current = self.get_volume()
            return self.set_volume(current + delta)
        except Exception as e:
            return f"Błąd przy zmianie głośności: {e}"

    def mute(self) -> str:
        """Wycisza system."""
        try:
            volume = self._get_volume_interface()
            volume.SetMute(1, None)
            return "System został wyciszony."
        except Exception:
            return "Error muting system."

    def unmute(self) -> str:
        """Cofa wyciszenie systemu."""
        try:
            volume = self._get_volume_interface()
            volume.SetMute(0, None)
            return "Wyciszenie zostało cofnięte."
        except Exception:
            return "Error unmuting system."

    def toggle_mute(self) -> str:
        """Przełącza wyciszenie."""
        try:
            volume = self._get_volume_interface()
            is_muted = volume.GetMute()
            volume.SetMute(not is_muted, None)
            if is_muted:
                return "Dźwięk włączony."
            return "Dźwięk wyłączony."
        except Exception:
            return "Error toggling mute."

    def get_volume(self) -> int:
        """Zwraca obecny poziom głośności w procentach."""
        try:
            volume = self._get_volume_interface()
            scalar = volume.GetMasterVolumeLevelScalar()
            return int(round(scalar * 100))
        except Exception:
            return 0

    # --- System Info ---
    def get_cpu_usage(self) -> str:
        usage = psutil.cpu_percent(interval=0.5)
        return f"Użycie procesora wynosi {usage} procent."

    def get_memory_usage(self) -> str:
        mem = psutil.virtual_memory()
        return f"Zużycie pamięci RAM to {mem.percent} procent."

    def get_battery_status(self) -> str:
        battery = psutil.sensors_battery()
        if battery:
            plugged = "podłączony do ładowania" if battery.power_plugged else "działa na baterii"
            return f"Bateria ma {battery.percent} procent i komputer {plugged}."
        return "Brak informacji o baterii."

    def get_disk_usage(self) -> str:
        disk = psutil.disk_usage('C:\\')
        free_gb = disk.free / (1024 ** 3)
        return f"Wolne miejsce na dysku C to {free_gb:.1f} gigabajtów."

    def get_system_info(self) -> str:
        cpu = self.get_cpu_usage()
        mem = self.get_memory_usage()
        bat = self.get_battery_status()
        disk = self.get_disk_usage()
        return f"{cpu} {mem} {disk} {bat}"

    # --- System Actions ---
    def lock_pc(self) -> str:
        ctypes.windll.user32.LockWorkStation()
        return "Komputer zablokowany."

    def shutdown_pc(self, delay=60) -> str:
        os.system(f'shutdown /s /t {delay}')
        return f"Komputer zostanie wyłączony za {delay} sekund."

    def restart_pc(self, delay=60) -> str:
        os.system(f'shutdown /r /t {delay}')
        return f"Komputer zostanie uruchomiony ponownie za {delay} sekund."

    def cancel_shutdown(self) -> str:
        os.system('shutdown /a')
        return "Zamykanie systemu anulowane."

    def sleep_pc(self) -> str:
        os.system('rundll32.exe powrprof.dll,SetSuspendState 0,1,0')
        return "Usypiam komputer."

    def take_screenshot(self) -> str:
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        filename = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = os.path.join(desktop_path, filename)
        pyautogui.screenshot(filepath)
        return f"Zrzut ekranu zapisany na pulpicie jako {filename}."

    # --- Date/Time/Weather ---
    def get_time(self) -> str:
        now = datetime.datetime.now()
        return f"Jest godzina {now.strftime('%H:%M')}."

    def get_date(self) -> str:
        now = datetime.datetime.now()
        months = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]
        return f"Dzisiaj jest {now.day} {months[now.month-1]} {now.year} roku."

    def get_weather(self, city='Warsaw') -> str:
        try:
            response = requests.get(f'https://wttr.in/{city}?format=j1', timeout=5)
            data = response.json()
            temp = data['current_condition'][0]['temp_C']
            desc = data['current_condition'][0]['lang_pl'][0]['value'] if 'lang_pl' in data['current_condition'][0] else "brak opisu"
            return f"Temperatura w mieście {city} wynosi {temp} stopni Celsjusza. Warunki: {desc}."
        except Exception as e:
            return f"Failed to get weather: {e}"

    # --- Web Search ---
    def search_google(self, query: str) -> str:
        url = f"https://www.google.com/search?q={query}"
        self.open_in_brave(url)
        return f"Wyszukuję {query} w Google."

    def search_youtube(self, query: str) -> str:
        url = f"https://www.youtube.com/results?search_query={query}"
        self.open_in_brave(url)
        return f"Szukam {query} na YouTube."

    def open_website(self, url: str) -> str:
        if not url.startswith('http'):
            url = f"https://{url}"
        self.open_in_brave(url)
        return f"Otwieram stronę {url}."

    # ============================================================
    # BEZPIECZEŃSTWO — Windows Defender
    # ============================================================

    def defender_quick_scan(self) -> str:
        """Uruchamia szybkie skanowanie Windows Defender."""
        try:
            print("[DEFENDER] Uruchamiam szybkie skanowanie...")
            subprocess.Popen(
                ['powershell', '-Command',
                 'Start-MpScan -ScanType QuickScan'],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return ("Uruchomiłem szybkie skanowanie Windows Defender. "
                    "Skanowanie działa w tle, sir. Może potrwać kilka minut.")
        except Exception as e:
            return f"Nie udało się uruchomić skanowania: {e}"

    def defender_full_scan(self) -> str:
        """Uruchamia pełne skanowanie Windows Defender."""
        try:
            print("[DEFENDER] Uruchamiam pełne skanowanie...")
            subprocess.Popen(
                ['powershell', '-Command',
                 'Start-MpScan -ScanType FullScan'],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return ("Uruchomiłem pełne skanowanie systemu. "
                    "To może potrwać dłuższy czas, sir. Skanowanie działa w tle.")
        except Exception as e:
            return f"Nie udało się uruchomić skanowania: {e}"

    def defender_status(self) -> str:
        """Sprawdza status Windows Defender i ostatnie zagrożenia."""
        try:
            # Sprawdź status ochrony
            result = subprocess.run(
                ['powershell', '-Command',
                 'Get-MpComputerStatus | Select-Object AntivirusEnabled,'
                 'RealTimeProtectionEnabled,AntivirusSignatureLastUpdated,'
                 'QuickScanEndTime | Format-List'],
                capture_output=True, text=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            output = result.stdout.strip()

            # Parsuj wynik
            antivirus_on = "True" in output.split("AntivirusEnabled")[1].split("\n")[0] if "AntivirusEnabled" in output else False
            realtime_on = "True" in output.split("RealTimeProtectionEnabled")[1].split("\n")[0] if "RealTimeProtectionEnabled" in output else False

            status_parts = []
            if antivirus_on:
                status_parts.append("antywirus jest włączony")
            else:
                status_parts.append("UWAGA — antywirus jest wyłączony!")

            if realtime_on:
                status_parts.append("ochrona w czasie rzeczywistym działa")
            else:
                status_parts.append("UWAGA — ochrona w czasie rzeczywistym jest wyłączona!")

            # Sprawdź zagrożenia
            threats_result = subprocess.run(
                ['powershell', '-Command',
                 '(Get-MpThreatDetection | Measure-Object).Count'],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            threat_count = threats_result.stdout.strip()

            if threat_count and threat_count != "0":
                status_parts.append(f"{threat_count} zagrożeń w historii")
            else:
                status_parts.append("nie wykryto żadnych zagrożeń")

            return f"Status bezpieczeństwa, sir: {', '.join(status_parts)}."
        except Exception as e:
            return f"Failed to check Defender status: {e}"

    def defender_update(self) -> str:
        """Aktualizuje definicje wirusów Windows Defender."""
        try:
            subprocess.Popen(
                ['powershell', '-Command', 'Update-MpSignature'],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return "Aktualizuję definicje wirusów Windows Defender, sir."
        except Exception as e:
            return f"Error updating definitions: {e}"

    # ============================================================
    # DIAGNOSTYKA SIECI
    # ============================================================

    def get_ip_address(self) -> str:
        """Zwraca adres IP lokalny i publiczny."""
        try:
            import socket
            # IP lokalne
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)

            # IP publiczne
            try:
                public_ip = requests.get('https://api.ipify.org', timeout=5).text
            except Exception:
                public_ip = "unavailable"

            return f"Adres IP lokalny to {local_ip}, a publiczny to {public_ip}, sir."
        except Exception as e:
            return f"Failed to read IP address: {e}"

    def ping_test(self, host="google.com") -> str:
        """Wykonuje test ping do danego hosta."""
        try:
            result = subprocess.run(
                ['ping', '-n', '4', host],
                capture_output=True, text=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            output = result.stdout

            # Szukaj średniego czasu
            match = re.search(r'(Średni|Average).*?(\d+)\s*ms', output)
            if match:
                avg = match.group(2)
                return f"Ping do {host} zakończony. Średni czas opóźnienia to {avg} ms, sir."
            elif "Średni" in output or "Average" in output:
                lines = output.strip().split('\n')
                last_line = lines[-1] if lines else ""
                return f"Ping do {host} zakończony. {last_line.strip()}, sir."
            elif "100%" in output or "nieosiągalny" in output or "unreachable" in output:
                return f"Nie udało się połączyć z {host}. Sprawdź połączenie internetowe, sir."
            else:
                return f"Ping do {host} udany. Połączenie działa, sir."
        except subprocess.TimeoutExpired:
            return f"Ping test to {host} timed out."
        except Exception as e:
            return f"Ping test error: {e}"

    def get_network_info(self) -> str:
        """Zwraca informacje o połączeniu sieciowym."""
        try:
            net = psutil.net_if_stats()
            active_connections = []
            for iface, stats in net.items():
                if stats.isup and stats.speed > 0:
                    active_connections.append(f"{iface} ({stats.speed} Mbps)")

            net_io = psutil.net_io_counters()
            sent_mb = net_io.bytes_sent / (1024 ** 2)
            recv_mb = net_io.bytes_recv / (1024 ** 2)

            parts = []
            if active_connections:
                parts.append(f"Active interfaces: {', '.join(active_connections)}")
            parts.append(f"Sent {sent_mb:.0f} MB, received {recv_mb:.0f} MB since boot")

            return ". ".join(parts) + ", sir."
        except Exception as e:
            return f"Failed to get network info: {e}"

    # ============================================================
    # CZYSZCZENIE SYSTEMU
    # ============================================================

    def cleanup_temp_files(self) -> str:
        """Czyści pliki tymczasowe systemu."""
        import shutil
        import tempfile

        cleaned_count = 0
        freed_bytes = 0
        temp_dirs = [
            tempfile.gettempdir(),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Temp'),
        ]

        for temp_dir in temp_dirs:
            if not os.path.exists(temp_dir):
                continue
            try:
                for item in os.listdir(temp_dir):
                    item_path = os.path.join(temp_dir, item)
                    try:
                        if os.path.isfile(item_path):
                            size = os.path.getsize(item_path)
                            os.remove(item_path)
                            cleaned_count += 1
                            freed_bytes += size
                        elif os.path.isdir(item_path):
                            size = sum(
                                os.path.getsize(os.path.join(dp, f))
                                for dp, dn, filenames in os.walk(item_path)
                                for f in filenames
                            )
                            shutil.rmtree(item_path, ignore_errors=True)
                            cleaned_count += 1
                            freed_bytes += size
                    except (PermissionError, OSError):
                        continue  # Pomiń pliki w użyciu
            except Exception:
                continue

        freed_mb = freed_bytes / (1024 ** 2)
        return f"Czyszczenie zakończone, sir. Usunąłem {cleaned_count} elementów i zwolniłem {freed_mb:.1f} megabajtów."

    # ============================================================
    # ZARZĄDZANIE PROCESAMI
    # ============================================================

    def list_top_processes(self) -> str:
        """Zwraca listę procesów zużywających najwięcej CPU/RAM."""
        try:
            processes = []
            for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_percent']):
                try:
                    info = proc.info
                    if info['cpu_percent'] is not None and info['memory_percent'] is not None:
                        processes.append(info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Sortuj po CPU
            top_cpu = sorted(processes, key=lambda x: x['cpu_percent'] or 0, reverse=True)[:5]

            result_parts = ["Procesy zużywające najwięcej zasobów: "]
            for p in top_cpu:
                if p['cpu_percent'] > 0:
                    result_parts.append(
                        f"{p['name']} - CPU {p['cpu_percent']:.0f}%, "
                        f"RAM {p['memory_percent']:.1f}%"
                    )

            if len(result_parts) == 1:
                return "Żaden proces nie zużywa znacząco zasobów, sir."
            return ". ".join(result_parts) + "."
        except Exception as e:
            return f"Error reading processes: {e}"

    def kill_process(self, process_name: str) -> str:
        """Zabija proces po nazwie."""
        process_name = process_name.strip().lower()
        if not process_name.endswith('.exe'):
            process_name += '.exe'

        killed = 0
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() == process_name:
                        proc.kill()
                        killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if killed > 0:
                return f"Zakończyłem {killed} procesów {process_name}, sir."
            return f"Nie znalazłem procesu {process_name}."
        except Exception as e:
            return f"Error killing process: {e}"

    # ============================================================
    # AKTUALIZACJE WINDOWS
    # ============================================================

    def check_windows_updates(self) -> str:
        """Sprawdza dostępne aktualizacje Windows."""
        try:
            result = subprocess.run(
                ['powershell', '-Command',
                 'try { $updates = (New-Object -ComObject Microsoft.Update.Session).'
                 'CreateUpdateSearcher().Search("IsInstalled=0").Updates; '
                 '$updates.Count } catch { "error" }'],
                capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            count = result.stdout.strip()
            if count == "0":
                return "System jest aktualny, sir. Brak oczekujących aktualizacji."
            elif count == "error" or not count:
                return "Nie udało się sprawdzić aktualizacji. Spróbuj otworzyć Windows Update ręcznie."
            else:
                return f"Dostępnych jest {count} aktualizacji Windows, sir. Zalecam ich zainstalowanie."
        except Exception as e:
            return f"Error checking updates: {e}"

    def open_windows_update(self) -> str:
        """Otwiera ustawienia Windows Update."""
        try:
            os.startfile("ms-settings:windowsupdate")
            return "Otwieram Windows Update, sir."
        except Exception as e:
            return f"Failed to open Windows Update: {e}"

    # ============================================================
    # INFORMACJE O SYSTEMIE (rozszerzone)
    # ============================================================

    def get_uptime(self) -> str:
        """Zwraca czas działania systemu."""
        import time
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)

        if hours > 0:
            return f"System działa od {hours} godzin i {minutes} minut, sir."
        return f"System działa od {minutes} minut, sir."

    def get_startup_programs(self) -> str:
        """Zwraca listę programów uruchamianych przy starcie."""
        try:
            result = subprocess.run(
                ['powershell', '-Command',
                 'Get-CimInstance Win32_StartupCommand | '
                 'Select-Object -ExpandProperty Name'],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            programs = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
            if programs:
                prog_list = ", ".join(programs[:8])  # Max 8 żeby nie gadać za długo
                return f"Programy startowe to między innymi: {prog_list}."
            return "Nie znalazłem programów startowych."
        except Exception as e:
            return f"Error reading startup programs: {e}"

    # ============================================================
    # JASNOŚĆ EKRANU
    # ============================================================

    def set_brightness(self, level: int) -> str:
        """Ustawia jasność ekranu w procentach (0-100)."""
        level = max(0, min(100, level))
        try:
            import screen_brightness_control as sbc
            sbc.set_brightness(level)
            return f"Jasność ekranu ustawiona na {level} procent, sir."
        except Exception as e:
            return f"Nie udało się zmienić jasności ekranu: {e}"

    def change_brightness(self, delta: int) -> str:
        """Zmienia jasność ekranu o delta procent."""
        try:
            import screen_brightness_control as sbc
            current = sbc.get_brightness()
            if isinstance(current, list):
                current = current[0]
            elif isinstance(current, int) or isinstance(current, float):
                pass
            else:
                current = 50
            return self.set_brightness(current + delta)
        except Exception as e:
            return f"Błąd podczas zmiany jasności: {e}"

    def get_brightness(self) -> int:
        """Zwraca aktualną jasność ekranu."""
        try:
            import screen_brightness_control as sbc
            val = sbc.get_brightness()
            if isinstance(val, list):
                val = val[0]
            return val
        except Exception:
            return 50

    # ============================================================
    # AUTOSTART WINDOWS
    # ============================================================

    def _get_startup_shortcut_path(self) -> str:
        startup_dir = os.path.join(os.environ['APPDATA'], r"Microsoft\Windows\Start Menu\Programs\Startup")
        return os.path.join(startup_dir, "JARVIS.lnk")

    def is_autostart_enabled(self) -> bool:
        """Sprawdza, czy skrót autostartu istnieje."""
        return os.path.exists(self._get_startup_shortcut_path())

    def enable_autostart(self) -> str:
        """Tworzy skrót w folderze Autostartu użytkownika."""
        shortcut_path = self._get_startup_shortcut_path()
        target_path = os.path.join(config.BASE_DIR, "START_JARVIS.bat")
        working_dir = config.BASE_DIR

        if not os.path.exists(target_path):
            return "Nie odnaleziono pliku startowego START_JARVIS.bat, sir."

        try:
            # Tworzenie skrótu przy użyciu skryptu PowerShell
            # Escapujemy cudzysłowy w ścieżce
            shortcut_path_esc = shortcut_path.replace('"', '`"')
            target_path_esc = target_path.replace('"', '`"')
            working_dir_esc = working_dir.replace('"', '`"')

            ps_command = (
                f'$WshShell = New-Object -ComObject WScript.Shell; '
                f'$Shortcut = $WshShell.CreateShortcut(\"{shortcut_path_esc}\"); '
                f'$Shortcut.TargetPath = \"{target_path_esc}\"; '
                f'$Shortcut.WorkingDirectory = \"{working_dir_esc}\"; '
                f'$Shortcut.Save()'
            )
            subprocess.run(
                ['powershell', '-Command', ps_command],
                capture_output=True, check=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return "Autostart systemu został pomyślnie włączony, sir."
        except Exception as e:
            return f"Błąd włączania autostartu: {e}"

    def disable_autostart(self) -> str:
        """Usuwa skrót z folderu Autostartu."""
        shortcut_path = self._get_startup_shortcut_path()
        try:
            if os.path.exists(shortcut_path):
                os.remove(shortcut_path)
                return "Autostart systemu został wyłączony, sir."
            return "Autostart nie był włączony, sir."
        except Exception as e:
            return f"Nie udało się wyłączyć autostartu: {e}"

    def open_in_brave(self, url: str) -> str:
        """Otwiera podany adres URL bezpośrednio w przeglądarce Brave."""
        paths = [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe")
        ]
        
        brave_path = None
        for p in paths:
            if os.path.exists(p):
                brave_path = p
                break
                
        try:
            if brave_path:
                subprocess.Popen([brave_path, url])
                return "Otwieram w przeglądarce Brave, sir."
            else:
                # Fallback do domyślnej przeglądarki
                import webbrowser
                webbrowser.open(url)
                return "Nie odnalazłem przeglądarki Brave. Otwieram w domyślnej przeglądarce, sir."
        except Exception as e:
            return f"Błąd otwierania w Brave: {e}"

    # ============================================================
    # STEROWANIE OKNAMI (MENEDŻER OKIEN)
    # ============================================================

    def minimize_all_windows(self) -> str:
        """Minimalizuje wszystkie okna (pokazuje pulpit)."""
        try:
            pyautogui.hotkey('win', 'd')
            return "Wszystkie okna zminimalizowane, sir."
        except Exception as e:
            return f"Błąd minimalizacji okien: {e}"

    def maximize_window(self) -> str:
        """Maksymalizuje aktywne okno."""
        try:
            pyautogui.hotkey('win', 'up')
            return "Okno zaktualizowane do pełnego ekranu, sir."
        except Exception as e:
            return f"Błąd maksymalizacji okna: {e}"

    def snap_window_left(self) -> str:
        """Przypina aktywne okno do lewej połowy ekranu."""
        try:
            pyautogui.hotkey('win', 'left')
            return "Przypiąłem okno do lewej strony, sir."
        except Exception as e:
            return f"Błąd przypinania okna: {e}"

    def snap_window_right(self) -> str:
        """Przypina aktywne okno do prawej połowy ekranu."""
        try:
            pyautogui.hotkey('win', 'right')
            return "Przypiąłem okno do prawej strony, sir."
        except Exception as e:
            return f"Błąd przypinania okna: {e}"

    def switch_window(self) -> str:
        """Przełącza aktywne okno (Alt+Tab)."""
        try:
            pyautogui.hotkey('alt', 'tab')
            return "Przełączyłem okno, sir."
        except Exception as e:
            return f"Błąd przełączania okna: {e}"

    # ============================================================
    # SCENARIUSZE I RUTYNY (MAKRA)
    # ============================================================

    def mode_work(self) -> str:
        """Aktywuje tryb pracy: otwiera przeglądarkę, notatnik, ustawia głośność i jasność."""
        self.set_brightness(80)
        self.set_volume(35)
        self.open_app("brave")
        self.open_app("notatnik")
        return "Tryb pracy aktywowany, sir. Otworzyłem przeglądarkę i notatnik, jasność 80%, głośność 35%."

    def mode_gaming(self) -> str:
        """Aktywuje tryb grania: jasność 100%, głośność 70%, uruchamia Steam."""
        self.set_brightness(100)
        self.set_volume(70)
        self.close_app("notatnik")
        self.open_app("steam")
        return "Tryb grania gotowy, sir. Ekran rozjaśniony do 100%, głośność 70%, uruchamiam Steam."

    def mode_night(self) -> str:
        """Aktywuje tryb nocny: przyciemnia ekran, wycisza głośność i planuje wyłączenie."""
        self.set_brightness(15)
        self.set_volume(15)
        self.shutdown_pc(delay=1800)
        return "Tryb nocny włączony, sir. Przyciemniłem ekran do 15%, wyciszyłem dźwięk. Wyłączenie komputera za 30 minut."

    def mode_study(self) -> str:
        """Aktywuje tryb nauki."""
        self.set_brightness(75)
        self.set_volume(25)
        self.open_app("brave")
        self.open_app("notatnik")
        return "Tryb nauki włączony, sir. Przygotowałem notatnik i przeglądarkę."

    # ============================================================
    # ODCZYT I ANALIZA DOKUMENTÓW (PDF, TXT, WORD, MD)
    # ============================================================

    def read_file_from_desktop(self, filename: str) -> str:
        """
        Przeszukuje Pulpit w poszukiwaniu wskazanego pliku i odczytuje jego zawartość.
        Obsługuje pliki .txt, .pdf, .md, .csv, .json, .py.
        """
        filename_lower = filename.lower().strip()
        desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        
        target_path = None
        if os.path.isabs(filename) and os.path.exists(filename):
            target_path = filename
        else:
            # Szukaj na Pulpicie
            for f in os.listdir(desktop_dir):
                if filename_lower in f.lower():
                    target_path = os.path.join(desktop_dir, f)
                    break

        if not target_path or not os.path.exists(target_path):
            return f"Nie odnalazłem pliku {filename} na Pulpicie, sir."

        ext = os.path.splitext(target_path)[1].lower()
        print(f"[FILE READ] Odczytuję plik: {target_path} ({ext})")

        try:
            content = ""
            if ext == '.pdf':
                try:
                    import pypdf
                    reader = pypdf.PdfReader(target_path)
                    for page in reader.pages[:5]: # Max 5 stron
                        text = page.extract_text()
                        if text:
                            content += text + "\n"
                except Exception as ex:
                    return f"Błąd podczas odczytu PDF: {ex}"
            else:
                # Zwykły plik tekstowy
                encodings = ['utf-8', 'cp1250', 'latin-1']
                for enc in encodings:
                    try:
                        with open(target_path, 'r', encoding=enc) as f_in:
                            content = f_in.read(4000) # Max 4000 znaków
                        break
                    except UnicodeDecodeError:
                        continue

            if not content.strip():
                return f"Plik {os.path.basename(target_path)} jest pusty, sir."

            # Zwróć zawartość pliku z prefiksem dla AI
            return f"Oto zawartość pliku {os.path.basename(target_path)}:\n{content[:2500]}"
        except Exception as e:
            return f"Wystąpił błąd odczytu pliku: {e}"

    # ============================================================
    # VISION API (SPÓJRZ NA MÓJ EKRAN)
    # ============================================================

    def capture_and_analyze_screen(self, prompt: str = "") -> str:
        """
        Robi zrzut ekranu w tle, przesyła go do modelu Gemini Vision
        i odpowiada na pytanie użytkownika dotyczące tego, co jest widoczne na monitorze.
        """
        try:
            print("[VISION] Wykonuję zrzut ekranu do analizy...")
            screenshot = pyautogui.screenshot()
            
            # Zapis tymczasowy
            temp_path = os.path.join(config.BASE_DIR, '.audio_cache', 'temp_vision.png')
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            screenshot.save(temp_path)

            import google.generativeai as genai
            from PIL import Image

            api_key = getattr(config, "GEMINI_API_KEY", "")
            if api_key:
                genai.configure(api_key=api_key)

            img = Image.open(temp_path)
            model_name = getattr(config, "GEMINI_MODEL", "gemini-3.6-flash")
            model = genai.GenerativeModel(model_name)

            user_prompt = prompt.strip() if prompt.strip() else "Opisz zwięźle w 2-3 zdaniach po polsku co dokładnie widzisz na tym zrzucie ekranu i na czym skupia się użytkownik."
            full_prompt = (
                f"Jesteś JARVIS-em, zaawansowanym asystentem AI. "
                f"Przeanalizuj poniższy zrzut ekranu użytkownika i odpowiedz zwięźle po polsku. "
                f"Pytanie użytkownika: {user_prompt}"
            )

            print(f"[VISION] Wysyłam ekran do Gemini Vision... Pytanie: '{user_prompt}'")
            response = model.generate_content([full_prompt, img])
            text_response = response.text.strip() if response and response.text else "Nie mogłem odczytać obrazu."
            
            # Usunięcie pliku tymczasowego
            try:
                os.remove(temp_path)
            except OSError:
                pass

            return text_response
        except Exception as e:
            print(f"[VISION] Błąd analizy ekranu: {e}")
            return f"Przepraszam sir, wystąpił błąd podczas analizy ekranu: {e}"

    # ============================================================
    # INTEGRACJA Z APPLE MUSIC
    # ============================================================

    def apple_music_play_pause(self) -> str:
        """Przełącza odtwarzanie / pauzę w Apple Music."""
        try:
            pyautogui.press('playpause')
            return "Przełączyłem odtwarzanie w Apple Music, sir."
        except Exception as e:
            return f"Błąd sterowania Apple Music: {e}"

    def apple_music_next(self) -> str:
        """Przełącza na następny utwór w Apple Music."""
        try:
            pyautogui.press('nexttrack')
            return "Następny utwór w Apple Music, sir."
        except Exception as e:
            return f"Błąd przełączania utworu: {e}"

    def apple_music_prev(self) -> str:
        """Przełącza na poprzedni utwór w Apple Music."""
        try:
            pyautogui.press('prevtrack')
            return "Poprzedni utwór w Apple Music, sir."
        except Exception as e:
            return f"Błąd przełączania utworu: {e}"

    def apple_music_search(self, query: str) -> str:
        """Wyszukuje utwór, wykonawcę lub album w Apple Music z automatycznym czyszczeniem łączników mowy."""
        try:
            import urllib.parse
            # Czyszczenie słów łączących polskiej mowy i czasowników dla idealnego wyszukiwania w Apple Music
            clean_q = re.sub(
                r'\b(?:puść|zagraj|włącz|znajdź|szukaj|wyszukaj|piosenkę|piosenka|utwór|nagranie|zespołu|zespół|wykonawcy|wykonawca|artysty|artysta|od|w|w\s+apple\s+music|apple\s+music)\b',
                '',
                query,
                flags=re.IGNORECASE
            )
            clean_q = ' '.join(clean_q.split()).strip()
            search_term = clean_q if clean_q else query.strip()

            encoded = urllib.parse.quote(search_term)
            url = f"https://music.apple.com/us/search?term={encoded}"
            webbrowser.open(url)
            return f"Wyszukuję {search_term} w Apple Music, sir."
        except Exception as e:
            return f"Błąd wyszukiwania w Apple Music: {e}"

if __name__ == '__main__':
    sys_ctrl = SystemController()
    print(sys_ctrl.get_time())
    print(sys_ctrl.get_cpu_usage())
    print(sys_ctrl.get_volume())
    print(sys_ctrl.defender_status())
    print(sys_ctrl.get_ip_address())
    print(sys_ctrl.get_uptime())
