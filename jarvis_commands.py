import re
import random
import threading

try:
    import config
except ImportError:
    class DummyConfig:
        RESPONSES_UNKNOWN = ["Nie rozumiem", "Proszę powtórzyć", "Nie wiem o co chodzi"]
    config = DummyConfig()

class CommandParser:
    """Klasa parsująca i wykonująca komendy głosowe."""
    
    def __init__(self, system_controller, voice_assistant=None, gui=None):
        self.sys = system_controller
        self.voice = voice_assistant
        self.gui = gui

    # Wzorce spójników rozdzielających komendy
    _SPLIT_PATTERN = re.compile(
        r'\s+(?:i\s+(?:też\s+)?|oraz\s+|a\s+(?:także\s+|potem\s+)?|dodatkowo\s+)'
        r'(?=(?:otwórz|uruchom|włącz|odpal|zamknij|wyłącz|zabij|wyszukaj|szukaj|google|youtube|'
        r'ustaw|zrób|pokaż|sprawdź|jaka|jaki|która|pogoda|zablokuj|uśpij|restart|wyczyść|ping|'
        r'głośniej|ciszej|wycisz|jaśniej|przyciemnij|rozjaśnij|screenshot|zrzut))',
        re.IGNORECASE
    )

    def parse_multi_command(self, command: str) -> str:
        """
        Rozdziela złożone polecenie na podkomendy i wykonuje je równolegle.
        Np. 'otwórz ready or not i wyszukaj mapę londynu' → 2 równoległe zadania.
        Zwraca połączone odpowiedzi.
        """
        cmd = command.strip()
        if not cmd:
            return ""

        # Podziel komendę na podkomendy za pomocą spójników
        sub_commands = self._SPLIT_PATTERN.split(cmd)
        sub_commands = [s.strip() for s in sub_commands if s.strip()]

        # Jeśli jest tylko jedna komenda, wykonaj normalnie
        if len(sub_commands) <= 1:
            return self.parse_and_execute(cmd)

        # Wykonaj wiele komend równolegle
        results = [None] * len(sub_commands)
        has_exit = False

        def execute_sub(index, sub_cmd):
            nonlocal has_exit
            result = self.parse_and_execute(sub_cmd)
            if result == "__EXIT__":
                has_exit = True
            results[index] = result

        threads = []
        for i, sub_cmd in enumerate(sub_commands):
            t = threading.Thread(target=execute_sub, args=(i, sub_cmd), daemon=True)
            threads.append(t)
            t.start()

        # Poczekaj na zakończenie wszystkich wątków (max 15 sek.)
        for t in threads:
            t.join(timeout=15)

        # Jeśli którakolwiek komenda to wyjście, zwróć __EXIT__
        if has_exit:
            return "__EXIT__"

        # Połącz odpowiedzi, pomijając puste
        responses = [r for r in results if r and r != "__EXIT__"]
        if not responses:
            return ""
        return " ".join(responses)

    def parse_and_execute(self, command: str) -> str:
        """Parsuje pojedynczą komendę w języku polskim i wykonuje odpowiednią akcję."""
        cmd = command.lower().strip()
        if not cmd:
            return ""

        # 0. Rutyny / Scenariusze (Makra)
        if re.search(r'tryb pracy', cmd):
            return self.sys.mode_work()
        elif re.search(r'tryb grania', cmd):
            return self.sys.mode_gaming()
        elif re.search(r'tryb nocny', cmd):
            return self.sys.mode_night()
        elif re.search(r'tryb nauki', cmd):
            return self.sys.mode_study()

        # 0.1 Sterowanie Oknami (Menedżer Okien)
        if re.search(r'zminimalizuj|pokaż pulpit', cmd):
            return self.sys.minimize_all_windows()
        elif re.search(r'maksymalizuj okno|pełny ekran okna', cmd):
            return self.sys.maximize_window()
        elif re.search(r'przypnij.*lewej', cmd):
            return self.sys.snap_window_left()
        elif re.search(r'przypnij.*prawej', cmd):
            return self.sys.snap_window_right()
        elif re.search(r'przełącz okno', cmd):
            return self.sys.switch_window()

        # 0.3 Analiza Ekranu (Vision AI)
        if re.search(r'spójrz na.*ekran|zobacz na.*ekran|co (?:jest|widzisz) na ekranie|przeanalizuj ekran', cmd):
            prompt = re.sub(r'.*?(?:ekran|ekranie)\s*', '', cmd).strip()
            return self.sys.capture_and_analyze_screen(prompt)

        # 0.4 Sterowanie Apple Music
        if re.search(r'apple music', cmd):
            if re.search(r'włącz|otwórz|uruchom', cmd) and not re.search(r'pauza|zatrzymaj|następny|poprzedni|szukaj', cmd):
                return self.sys.open_app("apple music")
            elif re.search(r'szukaj|wyszukaj|zagraj|puść', cmd):
                q = re.sub(r'.*?(?:szukaj|wyszukaj|zagraj|puść)\s+', '', cmd).replace('w apple music', '').strip()
                if q:
                    return self.sys.apple_music_search(q)

        if re.search(r'następn(?:a|y) (?:piosenka|utwór)', cmd):
            return self.sys.apple_music_next()
        elif re.search(r'poprzedn(?:a|y) (?:piosenka|utwór)', cmd):
            return self.sys.apple_music_prev()

        # 1. Otwieranie aplikacji
        match = re.search(r'(?:otwórz|uruchom|włącz|odpal)\s+(.+)', cmd)
        if match and "stronę" not in cmd:
            app = match.group(1).strip()
            return self.sys.open_app(app)

        # 2. Zamykanie aplikacji
        match = re.search(r'(?:zamknij|wyłącz|zabij)\s+(.+)', cmd)
        if match and "komputer" not in cmd and "się" not in cmd:
            app = match.group(1).strip()
            return self.sys.close_app(app)

        # 3. Głośność
        if re.search(r'głośniej', cmd):
            return self.sys.change_volume(10)
        elif re.search(r'ciszej', cmd):
            return self.sys.change_volume(-10)
        elif re.search(r'wycisz', cmd):
            return self.sys.mute()
        elif re.search(r'pełna głośność', cmd):
            return self.sys.set_volume(100)
        elif re.search(r'jaka\s+głośność', cmd) or (re.search(r'głośność', cmd) and 'ustaw' not in cmd):
            vol = self.sys.get_volume()
            return f"Głośność to {vol} procent."
        
        match = re.search(r'ustaw głośność na (\d+)', cmd)
        if match:
            vol = int(match.group(1))
            return self.sys.set_volume(vol)

        # 3.1 Jasność ekranu
        if re.search(r'jaśniej|rozjaśnij', cmd):
            return self.sys.change_brightness(10)
        elif re.search(r'ciemniej|przyciemnij', cmd):
            return self.sys.change_brightness(-10)
        elif re.search(r'jaka\s+jasność|jasność\s+ekranu', cmd) and 'ustaw' not in cmd:
            bright = self.sys.get_brightness()
            return f"Jasność ekranu wynosi {bright} procent, sir."
        
        match = re.search(r'ustaw jasność na (\d+)', cmd)
        if match:
            bright = int(match.group(1))
            return self.sys.set_brightness(bright)

        # 4. System info
        if re.search(r'status systemu', cmd):
            return self.sys.get_system_info()
        elif re.search(r'procesor|cpu', cmd):
            return self.sys.get_cpu_usage()
        elif re.search(r'pamięć|ram', cmd):
            return self.sys.get_memory_usage()
        elif re.search(r'bateria', cmd):
            return self.sys.get_battery_status()
        elif re.search(r'dysk', cmd):
            return self.sys.get_disk_usage()

        # 5. Czas/Data
        if re.search(r'która godzina|jaki czas', cmd):
            return self.sys.get_time()
        elif re.search(r'jaka data|jaki dzień', cmd):
            return self.sys.get_date()

        # 6. Pogoda
        match = re.search(r'pogoda w (\w+)', cmd)
        if match:
            city = match.group(1)
            return self.sys.get_weather(city)
        elif re.search(r'pogoda|jaka pogoda', cmd):
            return self.sys.get_weather()

        # 6.9 Wyszukiwanie w Brave (Brave search i Google Maps)
        match = re.search(r'(?:otwórz|szukaj|wyszukaj)\s+na\s+brave\s+(.+)', cmd)
        if match:
            query = match.group(1).strip()
            if re.search(r'map[aę]', query):
                map_query = re.sub(r'.*map[aę]\s*(?:i\s+|w\s+)?', '', query).strip()
                url = f"https://www.google.com/maps/search/{map_query}"
                return self.sys.open_in_brave(url)
            else:
                url = f"https://www.google.com/search?q={query}"
                return self.sys.open_in_brave(url)

        # 7. Wyszukiwanie
        match = re.search(r'(?:wyszukaj|szukaj|google)\s+(.+)', cmd)
        if match:
            query = match.group(1)
            return self.sys.search_google(query)
            
        match = re.search(r'youtube\s+(.+)', cmd)
        if match:
            query = match.group(1)
            return self.sys.search_youtube(query)

        # 8. Strony www
        match = re.search(r'otwórz stronę\s+(.+)', cmd)
        if match:
            url = match.group(1).replace(' ', '')
            return self.sys.open_website(url)

        # 9. System actions
        if re.search(r'zablokuj komputer', cmd):
            return self.sys.lock_pc()
        elif re.search(r'wyłącz komputer', cmd):
            return self.sys.shutdown_pc()
        elif re.search(r'restart', cmd):
            return self.sys.restart_pc()
        elif re.search(r'uśpij komputer', cmd):
            return self.sys.sleep_pc()
        elif re.search(r'anuluj wyłączanie', cmd):
            return self.sys.cancel_shutdown()

        # 9.1 Autostart systemu
        if re.search(r'włącz autostart|uruchamiaj ze startem', cmd):
            return self.sys.enable_autostart()
        elif re.search(r'wyłącz autostart|nie uruchamiaj ze startem', cmd):
            return self.sys.disable_autostart()

        # 9.2 Zarządzanie interfejsem graficznym
        if re.search(r'schowaj interfejs|ukryj interfejs|schowaj okno|ukryj okno|schowaj reaktor|ukryj reaktor', cmd):
            if self.gui:
                import threading
                threading.Thread(target=self._delayed_hide, daemon=True).start()
                return "Ukrywam interfejs graficzny, sir. Będę działał w tle."
            return "Interfejs graficzny nie jest podłączony, sir."
        elif re.search(r'pokaż interfejs|pokaż okno|włącz interfejs|pokaż reaktor', cmd):
            if self.gui:
                self.gui.show()
                return "Interfejs graficzny aktywowany, sir."
            return "Interfejs graficzny nie jest podłączony, sir."

        # 10. Screenshot
        if re.search(r'zrzut ekranu|screenshot|zrób screena', cmd):
            return self.sys.take_screenshot()

        # ============================================================
        # 11. Bezpieczeństwo — Windows Defender
        # ============================================================
        if re.search(r'skanuj.*wirus|skanowanie.*wirus|sprawdź.*wirus|szybkie skanowanie|przeskanuj.*system|czy mam wirusa|skanuj komputer', cmd):
            return self.sys.defender_quick_scan()
        if re.search(r'pełne skanowanie|dogłębne skanowanie|pełny skan', cmd):
            return self.sys.defender_full_scan()
        if re.search(r'status.*bezpieczeństwa|status.*defender|ochrona.*systemu|czy.*jestem.*bezpieczny|czy.*system.*bezpieczny', cmd):
            return self.sys.defender_status()
        if re.search(r'aktualizuj.*definicj|aktualizuj.*wirus|update.*defender', cmd):
            return self.sys.defender_update()

        # ============================================================
        # 12. Diagnostyka sieci
        # ============================================================
        if re.search(r'jaki.*ip|adres.*ip|mój.*ip|moje.*ip', cmd):
            return self.sys.get_ip_address()
        match = re.search(r'ping(?:\s+(.+))?', cmd)
        if match:
            host = match.group(1).strip() if match.group(1) else "google.com"
            return self.sys.ping_test(host)
        if re.search(r'stan.*sieci|info.*sieć|diagnostyka.*siec|połączenie.*internet', cmd):
            return self.sys.get_network_info()

        # ============================================================
        # 13. Czyszczenie systemu
        # ============================================================
        if re.search(r'wyczyść.*system|oczyść.*system|wyczyść.*temp|pliki tymczasowe|posprzątaj', cmd):
            return self.sys.cleanup_temp_files()

        # ============================================================
        # 14. Zarządzanie procesami
        # ============================================================
        if re.search(r'jakie.*procesy|top.*procesy|co.*żre.*zasoby|co.*zużywa|procesy', cmd):
            return self.sys.list_top_processes()
        match = re.search(r'zabij proces\s+(.+)', cmd)
        if match:
            return self.sys.kill_process(match.group(1).strip())

        # ============================================================
        # 15. Aktualizacje Windows
        # ============================================================
        if re.search(r'sprawdź.*aktualizacj|czy.*są.*aktualizacj|aktualizacje.*windows|update', cmd):
            return self.sys.check_windows_updates()
        if re.search(r'otwórz.*windows.*update|otwórz.*aktualizacj', cmd):
            return self.sys.open_windows_update()

        # ============================================================
        # 16. Informacje rozszerzone
        # ============================================================
        if re.search(r'jak długo.*działa|uptime|czas.*działania|od kiedy.*działa', cmd):
            return self.sys.get_uptime()
        if re.search(r'programy.*startow|autostart|co.*startuje', cmd):
            return self.sys.get_startup_programs()
        if re.search(r'jakie.*aplikacje.*działają|co.*jest.*uruchomion', cmd):
            return self.sys.list_running_apps()

        # ============================================================
        # 17. Pożegnanie
        # ============================================================
        if re.search(r'do widzenia|pa|wyłącz się|śpij|tryb czuwania|czuwaj', cmd):
            return "__EXIT__"

        # 18. Pomoc
        if re.search(r'co potrafisz|pomoc|help|jakie komendy', cmd):
            return (
                "Potrafię wiele rzeczy, sir. Otwierać i zamykać aplikacje, "
                "zmieniać głośność, podawać informacje o systemie, "
                "sprawdzić godzinę, datę i pogodę, "
                "wyszukiwać w Google i YouTube, "
                "skanować system na wirusy Windows Defenderem, "
                "sprawdzić status bezpieczeństwa i aktualizacje Windows, "
                "diagnostykę sieci i adres IP, "
                "wyczyścić pliki tymczasowe, "
                "zrobić zrzut ekranu, "
                "a także zablokować, uśpić lub wyłączyć komputer."
            )

        # Fallback — nieznana komenda
        return random.choice(config.UNKNOWN_COMMAND_MESSAGES)

    def _delayed_hide(self):
        """Pomocnicza metoda ukrywająca GUI z lekkim opóźnieniem."""
        import time
        time.sleep(2)
        if self.gui:
            self.gui.hide()

if __name__ == '__main__':
    from jarvis_system import SystemController
    parser = CommandParser(SystemController())
    print(parser.parse_and_execute("która godzina"))
    print(parser.parse_and_execute("czy mam wirusa"))
    print(parser.parse_and_execute("jaki mój ip"))
