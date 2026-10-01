"""
JARVIS GUI — Interfejs Arc Reactor (pywebview) z System Tray
============================================================
Most łączący silnik głosowy JARVIS-a z graficznym
interfejsem Arc Reactor oraz zasobnikiem systemowym (System Tray).
"""
import os
import sys
import json
import time
import threading
import webview
import psutil

# Dodaj główny katalog do ścieżki
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

# Ścieżka do katalogu GUI
GUI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gui')


class JarvisAPI:
    """
    API dostępne z JavaScript (pywebview js_api).
    Umożliwia GUI odpytywanie backendu o stan systemu.
    """

    def __init__(self):
        self._state = 'idle'
        self._stats = {}
        self._logs = []

    def get_state(self):
        return self._state

    def get_stats(self):
        return self._stats

    def get_logs(self):
        return self._logs[-20:]


class JarvisGUI:
    """
    Klasa zarządzająca oknem GUI z interfejsem Arc Reactor.
    Uruchamia pywebview, ikonę zasobnika systemowego (System Tray)
    oraz integruje asystenta z systemem Windows w tle.
    """

    def __init__(self):
        self.api = JarvisAPI()
        self.window = None
        self.tray_icon = None
        self._stats_thread = None
        self._running = False
        self._visible = True

    def start(self, jarvis_callback=None):
        """Uruchamia okno GUI oraz zasobnik systemowy."""
        self._running = True

        # 1. Tworzenie okna interfejsu
        self.window = webview.create_window(
            'J.A.R.V.I.S.',
            os.path.join(GUI_DIR, 'index.html'),
            js_api=self.api,
            fullscreen=True,
            background_color='#020308',
            text_select=False,
        )

        def on_loaded():
            """Wywoływane po załadowaniu strony HTML."""
            # Uruchom wątek aktualizacji statystyk
            self._stats_thread = threading.Thread(
                target=self._stats_loop, daemon=True
            )
            self._stats_thread.start()

            # Uruchom zasobnik systemowy w osobnym wątku
            threading.Thread(target=self._setup_tray, daemon=True).start()

            # Uruchom logikę JARVIS-a w tle
            if jarvis_callback:
                threading.Thread(
                    target=jarvis_callback, args=(self,), daemon=True
                ).start()

        self.window.events.loaded += on_loaded

        # Blokujące — uruchamia pętlę zdarzeń okna
        webview.start(debug=False)
        self._running = False

    # ============================================================
    # SYSTEM TRAY (Zasobnik systemowy)
    # ============================================================

    def _create_tray_image(self):
        """Generuje ikonę reaktora Arc w locie przy użyciu Pillow."""
        try:
            from PIL import Image, ImageDraw
            width = 64
            height = 64
            image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            dc = ImageDraw.Draw(image)

            # Rysuj rdzeń reaktora Arc
            dc.ellipse([4, 4, 60, 60], outline=(0, 229, 255, 255), width=5)
            dc.ellipse([18, 18, 46, 46], fill=(0, 229, 255, 255))
            dc.ellipse([24, 24, 40, 40], fill=(255, 255, 255, 255))
            return image
        except Exception as e:
            print(f"[GUI] Błąd generowania ikony tray: {e}")
            return None

    def _setup_tray(self):
        """Inicjalizuje pystray dla ikony w zasobniku systemowym."""
        try:
            import pystray
            from pystray import MenuItem as item

            image = self._create_tray_image()
            if not image:
                return

            # Sprawdź stan autostartu przy budowaniu menu
            from jarvis_system import SystemController
            sys_ctrl = SystemController()

            def toggle_window_action():
                if self._visible:
                    self.hide()
                else:
                    self.show()

            def toggle_autostart_action(icon, item):
                if sys_ctrl.is_autostart_enabled():
                    sys_ctrl.disable_autostart()
                    self.add_log("Autostart disabled via System Tray", "warning")
                else:
                    sys_ctrl.enable_autostart()
                    self.add_log("Autostart enabled via System Tray", "success")

            # Definiujemy menu
            menu = (
                item('Pokaż / Ukryj interfejs', toggle_window_action, default=True),
                item('Autostart z systemem', toggle_autostart_action,
                     checked=lambda item: sys_ctrl.is_autostart_enabled()),
                item('Wyjście (Exit)', self.quit)
            )

            self.tray_icon = pystray.Icon("JARVIS", image, "J.A.R.V.I.S.", menu)
            self.tray_icon.run()
        except Exception as e:
            print(f"[GUI] Błąd inicjalizacji zasobnika: {e}")

    # ============================================================
    # KONTROLA WIDOCZNOŚCI OKNA
    # ============================================================

    def show(self):
        """Pokazuje okno interfejsu."""
        if self.window and not self._visible:
            try:
                self.window.show()
                self._visible = True
                self.add_log("Interfejs graficzny aktywowany", "success")
            except Exception:
                pass

    def hide(self):
        """Ukrywa okno interfejsu (JARVIS działa w tle)."""
        if self.window and self._visible:
            try:
                self.window.hide()
                self._visible = False
                print("[GUI] Okno schowane. JARVIS działa w tle (zasobnik systemowy).")
            except Exception:
                pass

    def quit(self):
        """Zamyka aplikację i sprząta zasoby."""
        self._running = False
        if self.tray_icon:
            self.tray_icon.stop()
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass
        os._exit(0)

    # ============================================================
    # STEROWANIE STANEM / LOGAMI
    # ============================================================

    def set_state(self, state):
        """Ustawia stan GUI: 'idle', 'listening', 'speaking'."""
        self.api._state = state
        if self.window and self._visible:
            try:
                self.window.evaluate_js(f"setState('{state}')")
            except Exception:
                pass

    def set_audio_level(self, level: float):
        """Wysyła poziom głośności audio (0.0–1.0) do GUI w czasie rzeczywistym."""
        if self.window and self._visible:
            try:
                self.window.evaluate_js(f"setAudioLevel({level:.3f})")
            except Exception:
                pass

    def set_spoken_text(self, text: str):
        """Wysyła aktualnie wypowiadane zdanie do GUI."""
        if self.window and self._visible:
            try:
                escaped = text.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"').replace('\n', ' ')
                self.window.evaluate_js(f"setSpokenText('{escaped}')")
            except Exception:
                pass

    def add_log(self, message, log_type='info'):
        """Dodaje wpis do logu komend w GUI."""
        entry = {
            'text': message,
            'type': log_type,
            'time': time.strftime('%H:%M:%S')
        }
        self.api._logs.append(entry)
        if len(self.api._logs) > 50:
            self.api._logs = self.api._logs[-50:]

        if self.window and self._visible:
            try:
                escaped = message.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"').replace('\n', ' ')
                self.window.evaluate_js(f"addLog('{escaped}', '{log_type}')")
            except Exception:
                pass

    # ============================================================
    # PĘTLA STATYSTYK
    # ============================================================

    def _stats_loop(self):
        """Pętla aktualizująca statystyki systemowe co 3 sekundy."""
        while self._running:
            if self._visible:  # Aktualizuj tylko jeśli okno jest widoczne
                try:
                    stats = self._collect_stats()
                    self.api._stats = stats
                    if self.window:
                        stats_json = json.dumps(stats, ensure_ascii=False)
                        self.window.evaluate_js(f"updateStats({stats_json})")
                except Exception as e:
                    print(f"[GUI] Błąd aktualizacji statystyk: {e}")
            time.sleep(3)

    def _collect_stats(self):
        """Zbiera statystyki systemowe do wyświetlenia w GUI."""
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('C:\\')
        battery = psutil.sensors_battery()

        boot_time = psutil.boot_time()
        uptime_sec = time.time() - boot_time
        hours = int(uptime_sec // 3600)
        minutes = int((uptime_sec % 3600) // 60)
        uptime_str = f"{hours}h {minutes}m"

        system_stats = {
            'cpu': round(cpu, 1),
            'ram_used': round(mem.used / (1024**3), 1),
            'ram_total': round(mem.total / (1024**3), 1),
            'ram_percent': mem.percent,
            'disk_free': round(disk.free / (1024**3), 1),
            'battery': battery.percent if battery else None,
            'charging': battery.power_plugged if battery else False,
            'uptime': uptime_str,
        }

        import socket
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
        except Exception:
            local_ip = 'N/A'

        net_io = psutil.net_io_counters()
        network_stats = {
            'local_ip': local_ip,
            'public_ip': getattr(self, '_cached_public_ip', '...'),
            'sent': round(net_io.bytes_sent / (1024**2)),
            'recv': round(net_io.bytes_recv / (1024**2)),
        }

        # Cache public IP
        if not hasattr(self, '_public_ip_last_check') or \
           time.time() - self._public_ip_last_check > 120:
            try:
                import requests
                self._cached_public_ip = requests.get(
                    'https://api.ipify.org', timeout=3
                ).text
                self._public_ip_last_check = time.time()
                network_stats['public_ip'] = self._cached_public_ip
            except Exception:
                if not hasattr(self, '_cached_public_ip'):
                    self._cached_public_ip = 'N/A'

        # Top processes
        procs = []
        for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_percent']):
            try:
                info = proc.info
                if info['cpu_percent'] and info['cpu_percent'] > 0.5:
                    procs.append({
                        'name': info['name'][:20],
                        'cpu': round(info['cpu_percent'], 1),
                        'ram': round(info['memory_percent'], 1),
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        procs.sort(key=lambda x: x['cpu'], reverse=True)
        top_procs = procs[:6]

        return {
            'system': system_stats,
            'network': network_stats,
            'processes': top_procs,
        }


if __name__ == '__main__':
    from main import main
    main()
