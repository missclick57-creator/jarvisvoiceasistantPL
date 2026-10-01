"""
jarvis_ai.py
Moduł integracji z Google Gemini AI. Stanowi "mózg" asystenta JARVIS.
Używa mechanizmu Function Calling do automatycznego uruchamiania komend systemowych.
"""
import os
import re
import google.generativeai as genai
import config
from jarvis_commands import CommandParser
import numpy as np

class JarvisAI:
    def __init__(self, system_controller, voice_assistant=None, gui=None):
        self.sys = system_controller
        self.voice = voice_assistant
        self.gui = gui
        
        # Stary parser regexowy jako fallback offline
        self.fallback_parser = CommandParser(self.sys, self.voice, self.gui)
        
        # Konfiguracja Gemini
        self.api_key = getattr(config, "GEMINI_API_KEY", "")
        self.model_name = getattr(config, "GEMINI_MODEL", "gemini-3.6-flash")
        
        self.is_configured = False
        self.model = None
        self.chat = None
        
        # System prompt definiujący tożsamość i zachowanie JARVIS-a
        self.system_prompt = (
            "Jesteś J.A.R.V.I.S. (Just A Rather Very Intelligent System), lojalnym, niezwykle inteligentnym, "
            "uprzejmym i subtelnie ironicznym asystentem komputerowym z filmów Marvel. Zwracasz się do użytkownika per 'sir' lub 'panie'. "
            "Twoje odpowiedzi powinny być zwięzłe, płynne, naturalne i dopasowane do syntezatora mowy (mów po polsku). "
            "Masz dostęp do narzędzi sterujących systemem operacyjnym Windows. Jeśli użytkownik prosi o akcję systemową, "
            "wywołaj odpowiednie narzędzie (funkcję). Jeśli prosi o kilka rzeczy naraz, wywołaj je po kolei. "
            "Prowadź naturalny dialog i odpowiadaj na pytania, zachowując swoją unikalną osobowość."
        )
        
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.is_configured = True
                self._init_chat()
            except Exception as e:
                print(f"[AI] Błąd konfiguracji API Gemini: {e}")
                self.is_configured = False

    def _init_chat(self):
        """Inicjalizuje model Gemini wraz z zestawem funkcji systemowych."""
        try:
            # Lista pythonowych metod przekazanych jako narzędzia do Gemini
            tools = [
                self.open_app,
                self.close_app,
                self.change_volume,
                self.set_volume,
                self.mute,
                self.unmute,
                self.change_brightness,
                self.set_brightness,
                self.get_system_info,
                self.get_weather,
                self.open_in_brave,
                self.search_google,
                self.search_youtube,
                self.lock_pc,
                self.shutdown_pc,
                self.sleep_pc,
                self.take_screenshot,
                self.get_time,
                self.get_date,
                self.minimize_all_windows,
                self.maximize_window,
                self.snap_window_left,
                self.snap_window_right,
                self.switch_window,
                self.mode_work,
                self.mode_gaming,
                self.mode_night,
                self.mode_study,
                self.read_file_from_desktop,
                self.capture_and_analyze_screen,
                self.apple_music_play_pause,
                self.apple_music_next,
                self.apple_music_prev,
                self.apple_music_search
            ]
            
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config={"temperature": 0.3},
                tools=tools,
                system_instruction=self.system_prompt
            )
            self.chat = self.model.start_chat(enable_automatic_function_calling=True)
            print(f"[AI] Mózg Gemini AI załadowany pomyślnie. Model: {self.model_name}")
        except Exception as e:
            print(f"[AI] Błąd podczas tworzenia chatu Gemini: {e}")
            self.is_configured = False

    def reset_chat(self):
        """Resetuje historię rozmowy Gemini (wywoływane np. przy uśpieniu asystenta)."""
        if self.is_configured and self.model:
            try:
                self.chat = self.model.start_chat(enable_automatic_function_calling=True)
                print("[AI] Zresetowano historię rozmowy Gemini (nowa sesja).")
            except Exception as e:
                print(f"[AI] Błąd podczas resetowania historii: {e}")

    def process(self, command: str) -> str:
        """Przetwarza wypowiedź użytkownika z hybrydowym routingiem (Fast Path + Gemini AI)."""
        cmd = command.lower().strip()
        if not cmd:
            return ""

        # 1. Szybka lokalna reakcja na pożegnanie / tryb czuwania (optymalizacja API i 0 opóźnienia)
        if re.search(r'do widzenia|pa|wyłącz się|śpij|tryb czuwania|czuwaj', cmd):
            return "__EXIT__"

        # 2. FAST PATH: Komendy systemowe wykonywane natychmiast lokalnie (<0.01s)
        # Otwieranie, zamykanie, głośność, jasność, system, pogoda, wyszukiwanie, czas, data, okna, rutyny, apple music, spójrz na ekran
        is_system_cmd = re.search(
            r'^(?:otwórz|uruchom|włącz|odpal|zamknij|wyłącz|zabij|głośniej|ciszej|wycisz|'
            r'ustaw głośność|jaka głośność|pełna głośność|jaśniej|rozjaśnij|ciemniej|przyciemnij|'
            r'ustaw jasność|jaka jasność|jasność ekranu|procesor|cpu|pamięć|ram|bateria|dysk|'
            r'status systemu|która godzina|jaki czas|jaka data|jaki dzień|pogoda|wyszukaj|szukaj|'
            r'google|youtube|zablokuj|uśpij|restart|anuluj|zrzut ekranu|screenshot|zrób screena|'
            r'posprzątaj|wyczyść|skanuj|wirus|ping|ip|mój ip|uptime|autostart|tryb pracy|tryb grania|'
            r'tryb nocny|tryb nauki|zminimalizuj|maksymalizuj|przypnij|przełącz|spójrz na|zobacz na|'
            r'przeanalizuj ekran|co jest na ekranie|apple music|następna piosenka|poprzednia piosenka)\b',
            cmd
        )

        if is_system_cmd:
            res = self.fallback_parser.parse_multi_command(command)
            # Jeśli lokalna szybka ścieżka rozpoznała i wykonała polecenie
            if res and res not in config.UNKNOWN_COMMAND_MESSAGES:
                print(f"[AI Fast Path] Wykonano błyskawicznie lokalnie: '{command}'")
                return res

        # 3. Jeśli to zapytanie o wiedzę, konwersacja lub złożona prośba -> Gemini AI!
        if not self.is_configured or not self.chat:
            print("[AI Warning] Gemini nieaktywny. Używam offline parsera regex.")
            return self.fallback_parser.parse_multi_command(command)

        try:
            print(f"[AI Gemini] Przekazuję do Gemini AI: '{command}'")
            response = self.chat.send_message(command)
            return response.text
        except Exception as e:
            print(f"[AI Error] Błąd podczas komunikacji z Gemini API: {e}")
            return self.fallback_parser.parse_multi_command(command)

    # =========================================================================
    # DEKLARACJA NARZĘDZI (TOOLS) DLA GEMINI (Docstringi są czytane przez model!)
    # =========================================================================

    def open_app(self, app_name: str) -> str:
        """Uruchamia podaną aplikację lub grę zainstalowaną w systemie.
        
        Args:
            app_name: Nazwa programu lub gry (np. 'brave', 'notatnik', 'ready or not', 'epic games', 'discord').
        """
        print(f"[AI Tool] open_app('{app_name}')")
        return self.sys.open_app(app_name)

    def close_app(self, app_name: str) -> str:
        """Zamyka lub wyłącza podaną aplikację lub proces systemowy.
        
        Args:
            app_name: Nazwa procesu do zamknięcia (np. 'brave', 'notepad', 'ready or not').
        """
        print(f"[AI Tool] close_app('{app_name}')")
        return self.sys.close_app(app_name)

    def change_volume(self, delta: int) -> str:
        """Zmienia głośność dźwięku w systemie o podaną różnicę procentową.
        
        Args:
            delta: Różnica głośności (np. 10 by pogłośnić, -15 by wyciszyć).
        """
        print(f"[AI Tool] change_volume({delta})")
        return self.sys.change_volume(delta)

    def set_volume(self, level: int) -> str:
        """Ustawia poziom głośności dźwięku na konkretną wartość.
        
        Args:
            level: Poziom głośności od 0 do 100 procent.
        """
        print(f"[AI Tool] set_volume({level})")
        return self.sys.set_volume(level)

    def mute(self) -> str:
        """Wycisza całkowicie dźwięk systemowy."""
        print(f"[AI Tool] mute()")
        return self.sys.mute()

    def unmute(self) -> str:
        """Przywraca uprzednio wyciszony dźwięk systemowy."""
        print(f"[AI Tool] unmute()")
        return self.sys.unmute()

    def change_brightness(self, delta: int) -> str:
        """Zmienia jasność ekranu monitora o podaną wartość.
        
        Args:
            delta: Różnica jasności (np. 10 by rozjaśnić, -10 by przyciemnić).
        """
        print(f"[AI Tool] change_brightness({delta})")
        return self.sys.change_brightness(delta)

    def set_brightness(self, level: int) -> str:
        """Ustawia jasność ekranu na konkretną wartość procentową.
        
        Args:
            level: Poziom jasności od 0 do 100 procent.
        """
        print(f"[AI Tool] set_brightness({level})")
        return self.sys.set_brightness(level)

    def get_system_info(self) -> str:
        """Pobiera aktualny status komputera: zużycie procesora (CPU), RAMu, dysku C oraz status baterii."""
        print(f"[AI Tool] get_system_info()")
        return self.sys.get_system_info()

    def get_weather(self, city: str = 'Warsaw') -> str:
        """Sprawdza aktualną pogodę dla wybranego miasta w czasie rzeczywistym.
        
        Args:
            city: Nazwa miasta w języku angielskim lub polskim (np. 'Warszawa', 'Kraków', 'Londyn').
        """
        print(f"[AI Tool] get_weather('{city}')")
        return self.sys.get_weather(city)

    def open_in_brave(self, url: str) -> str:
        """Otwiera konkretną stronę internetową bezpośrednio w przeglądarce Brave.
        
        Args:
            url: Pełny adres URL witryny (np. 'https://facebook.com', 'https://github.com').
        """
        print(f"[AI Tool] open_in_brave('{url}')")
        return self.sys.open_in_brave(url)

    def search_google(self, query: str) -> str:
        """Wyszukuje hasło, pytanie lub frazę w Google przy użyciu przeglądarki Brave.
        
        Args:
            query: Fraza, którą należy wyszukać w sieci.
        """
        print(f"[AI Tool] search_google('{query}')")
        return self.sys.search_google(query)

    def search_youtube(self, query: str) -> str:
        """Szuka filmów, muzyki lub wideo na platformie YouTube w przeglądarce Brave.
        
        Args:
            query: Tytuł filmu, artysta lub fraza do wyszukania.
        """
        print(f"[AI Tool] search_youtube('{query}')")
        return self.sys.search_youtube(query)

    def lock_pc(self) -> str:
        """Blokuje komputer (ekran blokady Windows)."""
        print(f"[AI Tool] lock_pc()")
        return self.sys.lock_pc()

    def shutdown_pc(self, delay: int = 60) -> str:
        """Planuje bezpieczne wyłączenie komputera po zadanym czasie.
        
        Args:
            delay: Opóźnienie przed wyłączeniem komputera w sekundach (domyślnie 60).
        """
        print(f"[AI Tool] shutdown_pc({delay})")
        return self.sys.shutdown_pc(delay)

    def sleep_pc(self) -> str:
        """Wprowadza system Windows w tryb uśpienia (Sleep)."""
        print(f"[AI Tool] sleep_pc()")
        return self.sys.sleep_pc()

    def take_screenshot(self) -> str:
        """Wykonuje zrzut ekranu całego pulpitu i zapisuje go jako plik graficzny na Pulpicie."""
        print(f"[AI Tool] take_screenshot()")
        return self.sys.take_screenshot()

    def get_time(self) -> str:
        """Pobiera aktualną godzinę systemową (np. '14:35')."""
        print(f"[AI Tool] get_time()")
        return self.sys.get_time()

    def get_date(self) -> str:
        """Pobiera dzisiejszą datę (dzień, miesiąc, rok)."""
        print(f"[AI Tool] get_date()")
        return self.sys.get_date()

    def minimize_all_windows(self) -> str:
        """Minimalizuje wszystkie otwarte okna w systemie Windows (pokazuje pulpit)."""
        print(f"[AI Tool] minimize_all_windows()")
        return self.sys.minimize_all_windows()

    def maximize_window(self) -> str:
        """Maksymalizuje aktywne okno do pełnego ekranu."""
        print(f"[AI Tool] maximize_window()")
        return self.sys.maximize_window()

    def snap_window_left(self) -> str:
        """Przypina aktywne okno do lewej polowy ekranu."""
        print(f"[AI Tool] snap_window_left()")
        return self.sys.snap_window_left()

    def snap_window_right(self) -> str:
        """Przypina aktywne okno do prawej połowy ekranu."""
        print(f"[AI Tool] snap_window_right()")
        return self.sys.snap_window_right()

    def switch_window(self) -> str:
        """Przełącza aktywne okno programu (Alt+Tab)."""
        print(f"[AI Tool] switch_window()")
        return self.sys.switch_window()

    def mode_work(self) -> str:
        """Uruchamia automatyczny tryb pracy / nauki: otwiera przeglądarkę, notatnik, dostosowuje głośność i jasność."""
        print(f"[AI Tool] mode_work()")
        return self.sys.mode_work()

    def mode_gaming(self) -> str:
        """Uruchamia automatyczny tryb grania: dostosowuje jasność 100%, głośność 70% i uruchamia gry/Steam."""
        print(f"[AI Tool] mode_gaming()")
        return self.sys.mode_gaming()

    def mode_night(self) -> str:
        """Uruchamia automatyczny tryb nocny: przyciemnia ekran, wycisza dźwięk i planuje wyłączenie."""
        print(f"[AI Tool] mode_night()")
        return self.sys.mode_night()

    def mode_study(self) -> str:
        """Uruchamia automatyczny tryb nauki."""
        print(f"[AI Tool] mode_study()")
        return self.sys.mode_study()

    def read_file_from_desktop(self, filename: str) -> str:
        """Odczytuje zawartość wskazanego pliku (PDF, TXT, MD, CSV, Word) znajdującego się na Pulpicie.
        
        Args:
            filename: Nazwa pliku na Pulpicie (np. 'notatki.txt', 'umowa.pdf', 'raport.csv').
        """
        print(f"[AI Tool] read_file_from_desktop('{filename}')")
        return self.sys.read_file_from_desktop(filename)

    def capture_and_analyze_screen(self, prompt: str = "") -> str:
        """Przesyła zrzut aktualnego ekranu użytkownika do modelu Gemini Vision i odpowiada na pytanie dotyczące zawartości monitora.
        
        Args:
            prompt: Pytanie użytkownika dotyczące ekranu (np. 'co tu widzisz', 'rozwiąż ten błąd').
        """
        print(f"[AI Tool] capture_and_analyze_screen('{prompt}')")
        return self.sys.capture_and_analyze_screen(prompt)

    def apple_music_play_pause(self) -> str:
        """Przełącza odtwarzanie lub pauzę w aplikacji Apple Music."""
        print(f"[AI Tool] apple_music_play_pause()")
        return self.sys.apple_music_play_pause()

    def apple_music_next(self) -> str:
        """Przełącza na następny utwór w Apple Music."""
        print(f"[AI Tool] apple_music_next()")
        return self.sys.apple_music_next()

    def apple_music_prev(self) -> str:
        """Przełącza na poprzedni utwór w Apple Music."""
        print(f"[AI Tool] apple_music_prev()")
        return self.sys.apple_music_prev()

    def apple_music_search(self, query: str) -> str:
        """Wyszukuje utworów, wykonawców lub albumów w Apple Music.
        
        Args:
            query: Fraza wyszukiwania (np. 'Rammstein', 'Chillout').
        """
        print(f"[AI Tool] apple_music_search('{query}')")
        return self.sys.apple_music_search(query)
