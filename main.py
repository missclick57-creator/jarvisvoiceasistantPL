"""
JARVIS - Główna pętla asystenta głosowego z GUI Arc Reactor
=============================================================
Pełnowymiarowy asystent głosowy dla Windows inspirowany JARVIS-em z filmów Marvel.
Nasłuchuje wake word "Jarvis", weryfikuje tożsamość mówcy,
wykonuje zaawansowane komendy systemowe i wyświetla futurystyczny
interfejs Arc Reactor.

Autor: Paweł
"""
import sys
import os
import random
import signal
import time
import threading

# Dodaj katalog projektu do ścieżki
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from jarvis_voice import JarvisVoice, JarvisEar
from jarvis_speaker import SpeakerVerifier
from jarvis_system import SystemController
from jarvis_ai import JarvisAI
from jarvis_gui import JarvisGUI
from jarvis_sounds import SoundEffects


class Jarvis:
    """
    Główna klasa asystenta JARVIS.
    Łączy wszystkie moduły: głos, rozpoznawanie mowy,
    weryfikację mówcy, kontroler systemowy i GUI.
    """

    def __init__(self, gui: JarvisGUI = None):
        self.gui = gui

        print("=" * 60)
        print("  J.A.R.V.I.S. — Just A Rather Very Intelligent System")
        print("  Inicjalizacja systemu...")
        print("=" * 60)

        self._log("Ładowanie silnika głosowego...", "info")
        self.voice = JarvisVoice()
        # Dodaj callbacki do głosu, żeby GUI wiedział kiedy JARVIS mówi
        self.voice.on_speak_start = lambda: self._set_state('speaking')
        self.voice.on_speak_end = lambda: self._set_state('idle')

        self._log("Ładowanie modułu nasłuchiwania...", "info")
        self.ear = JarvisEar()

        self._log("Ładowanie weryfikacji mówcy...", "info")
        self.speaker = SpeakerVerifier()

        self._log("Ładowanie kontrolera systemowego...", "info")
        self.system = SystemController()

        self._log("Ładowanie sztucznej inteligencji (Gemini)...", "info")
        self.ai = JarvisAI(self.system, self.voice, self.gui)

        self._log("Ładowanie modułu efektów dźwiękowych...", "info")
        self.sounds = SoundEffects()

        # Flaga działania
        self.running = True

        self._log("Wszystkie moduły załadowane pomyślnie.", "success")

    def _log(self, message, log_type='info'):
        """Loguje wiadomość do konsoli i GUI."""
        prefix_map = {
            'info': '[INFO]',
            'success': '[OK]',
            'warning': '[WARN]',
            'cmd': '[CMD]',
        }
        prefix = prefix_map.get(log_type, '[INFO]')
        print(f"{prefix} {message}")

        if self.gui:
            self.gui.add_log(message, log_type)

    def _set_state(self, state):
        """Aktualizuje stan w GUI (idle/listening/speaking)."""
        if self.gui:
            self.gui.set_state(state)

    def _check_enrollment(self):
        """
        Sprawdza czy głos właściciela został zarejestrowany.
        Jeśli nie, uruchamia procedurę rejestracji.
        """
        if not self.speaker.is_enrolled():
            self._log("Profil głosowy nie znaleziony — rozpoczynam rejestrację", "warning")

            self.voice.speak(
                "Witaj, sir. Nie wykryłem profilu głosowego. "
                "Muszę zarejestrować twój głos, aby reagować wyłącznie na ciebie. "
                "Proszę, powiedz kilka zdań, gdy cię o to poproszę."
            )

            success = self.speaker.enroll(voice_feedback=self.voice)
            if success:
                self._log("Rejestracja głosu zakończona pomyślnie", "success")
                self.voice.speak(
                    "Rejestracja zakończona pomyślnie. "
                    "Od teraz będę reagować wyłącznie na twój głos, sir."
                )
            else:
                self._log("Rejestracja głosu nie powiodła się", "warning")
                self.voice.speak(
                    "Rejestracja nie powiodła się. "
                    "Spróbuj ponownie przy następnym uruchomieniu."
                )
                sys.exit(1)

    def _startup_greeting(self):
        """Powitanie przy uruchomieniu."""
        hour = time.localtime().tm_hour
        if 5 <= hour < 12:
            greeting = "Dzień dobry, sir."
        elif 12 <= hour < 18:
            greeting = "Dobre popołudnie, sir."
        elif 18 <= hour < 22:
            greeting = "Dobry wieczór, sir."
        else:
            greeting = "Witaj, sir. Późna pora."

        self.voice.speak(
            f"{greeting} JARVIS w pełni operacyjny. "
            "Wszystkie systemy działają prawidłowo. "
            "Czekam na twoje polecenia."
        )

    def run(self, gui_ref=None):
        """
        Główna pętla asystenta.
        Jeśli gui_ref jest podany (z JarvisGUI.start), użyj go.
        """
        if gui_ref:
            self.gui = gui_ref
            self.ai.gui = gui_ref
            self.voice.gui = gui_ref  # Przekaż GUI do modułu głosowego (audio level sync)

        # Sprawdź rejestrację głosu
        self._check_enrollment()

        # Powitanie
        self._startup_greeting()

        # Przejdź w tryb ducha (ukryty) po przywitaniu
        if self.gui:
            time.sleep(1.5)
            self.gui.hide()

        self._log(f"JARVIS aktywny — wake word: '{config.WAKE_WORD}'", "success")
        self._set_state('idle')

        while self.running:
            try:
                # --- Krok 1: Nasłuchuj wake word ---
                self._set_state('idle')
                wake_detected, audio_data = self.ear.listen_for_wake_word()

                if not wake_detected:
                    continue

                self._log("Wake word wykryty!", "success")

                # --- Krok 2: Weryfikuj tożsamość mówcy ---
                if audio_data is not None and self.speaker.is_enrolled():
                    is_authorized = self.speaker.verify(audio_data)
                    if not is_authorized:
                        unauthorized_msg = random.choice(config.UNAUTHORIZED_MESSAGES)
                        self._log(f"Nieautoryzowany głos!", "warning")
                        self.voice.speak(unauthorized_msg)
                        continue
                    self._log("Głos zweryfikowany — autoryzowany", "success")

                # --- Krok 3: Potwierdź nasłuchiwanie i zagraj dźwięk wybudzania ---
                self.sounds.play_wake()
                if self.gui:
                    self.gui.show()
                    time.sleep(0.2)
                greeting = random.choice(config.GREETING_MESSAGES)
                self.voice.speak(greeting)

                in_conversation = True
                consecutive_timeouts = 0

                # Pętla ciągłej konwersacji (brak potrzeby mówienia "Jarvis" co komendę)
                while in_conversation and self.running:
                    # --- Krok 4: Nasłuchuj komendy ---
                    self._set_state('listening')
                    self._log("Nasłuchuję komendy...", "info")
                    command = self.ear.listen_for_command()

                    if not command:
                        consecutive_timeouts += 1
                        # Po 2 z rzędu nieudanych próbach (brak mowy), wyjdź z konwersacji i schowaj interfejs
                        if consecutive_timeouts >= 2:
                            self._log("Brak aktywności — powrót do trybu oczekiwania na wake word", "info")
                            self.sounds.play_standby()
                            self.voice.speak("Przechodzę w tryb czuwania, sir.")
                            in_conversation = False
                            self.ai.reset_chat()  # Zresetuj historię przy wejściu w tryb czuwania
                            if self.gui:
                                self.gui.hide()
                        continue

                    # Wykryto komendę — resetuj timeouty
                    consecutive_timeouts = 0
                    self._log(f'Komenda: "{command}"', "cmd")

                    # --- Krok 5: Przetwarzaj komendę przez Gemini AI ---
                    self.sounds.play_action()
                    response = self.ai.process(command)

                    # --- Krok 6: Odpowiedz głosowo ---
                    if response:
                        if response == "__EXIT__":
                            self.sounds.play_standby()
                            farewell = random.choice(config.FAREWELL_MESSAGES)
                            self.voice.speak(farewell)
                            self._log("Koniec konwersacji na żądanie", "info")
                            in_conversation = False
                            self.ai.reset_chat()  # Zresetuj historię przy pożegnaniu
                            if self.gui:
                                self.gui.hide()
                            break

                        self._log(f"Odpowiedź: {response[:80]}...", "info") if len(response) > 80 else self._log(f"Odpowiedź: {response}", "info")
                        self.voice.speak(response)
                        self._set_state('idle')

            except KeyboardInterrupt:
                self._log("Zamykanie systemu...", "warning")
                self.running = False
                self.voice.speak("Zamykam systemy. Do widzenia, sir.")
                break
            except Exception as e:
                self._log(f"Błąd: {e}", "warning")
                time.sleep(1)
                continue

    def _auto_hide_gui(self, delay=5):
        """Automatycznie ukrywa interfejs po zadanym czasie bezczynności."""
        time.sleep(delay)
        # Ukryj tylko jeśli stan to wciąż idle (czyli nie zaczęliśmy nowego nasłuchu)
        if self.gui and self.gui.api.get_state() == 'idle':
            self.gui.hide()


def main():
    """Punkt wejścia programu."""
    print(r"""
       ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
       ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
       ██║███████║██████╔╝██║   ██║██║███████╗
  ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
  ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
   ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
    Just A Rather Very Intelligent System v1.0
    """)

    # Utwórz instancję JARVIS
    jarvis = Jarvis()

    # Utwórz i uruchom GUI z JARVIS-em w tle
    gui = JarvisGUI()

    def jarvis_thread(gui_ref):
        """Wątek głównej pętli JARVIS-a."""
        time.sleep(1)  # Poczekaj na załadowanie GUI
        jarvis.run(gui_ref)

    # Uruchom GUI (blokujące) — logika JARVIS-a w osobnym wątku
    gui.start(jarvis_callback=jarvis_thread)


if __name__ == "__main__":
    main()
