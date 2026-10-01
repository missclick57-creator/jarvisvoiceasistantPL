"""
Moduł odpowiedzialny za przetwarzanie mowy (Text-to-Speech oraz Speech-to-Text).
Wykorzystuje edge-tts (Microsoft Neural TTS) dla naturalnego, męskiego głosu
oraz speech_recognition dla rozpoznawania mowy.
"""

import os
import asyncio
import tempfile
import time

import speech_recognition as sr
import numpy as np
import edge_tts
import pygame

import config


class JarvisVoice:
    """
    Klasa odpowiedzialna za zamianę tekstu na mowę (TTS).
    Używa edge-tts z neuralnym głosem Microsoft dla naturalnej mowy.
    """

    # Dostępne głosy męskie (neural)
    VOICES = {
        'pl_marek': 'pl-PL-MarekNeural',       # Polski męski — naturalny
        'en_ryan':  'en-GB-RyanNeural',         # Brytyjski męski — najbardziej JARVIS-owy
        'en_guy':   'en-US-GuyNeural',          # Amerykański męski
        'en_andrew':'en-US-AndrewNeural',       # Amerykański męski (spokojny)
        'de_conrad':'de-DE-ConradNeural',       # Niemiecki męski
    }

    def __init__(self, voice_key='pl_marek', rate='-5%', pitch='-2Hz'):
        """
        Inicjalizacja silnika TTS.

        Args:
            voice_key: klucz głosu z VOICES (domyślnie polski Marek)
            rate: szybkość mowy (np. '-5%', '+10%', '+0%')
            pitch: wysokość głosu (np. '-2Hz', '+5Hz')
        """
        self.on_speak_start = None  # callback wywoływany przed mówieniem
        self.on_speak_end = None    # callback wywoływany po skończeniu mówienia
        self.gui = None             # referencja do GUI (ustawiana z main.py)

        # Konfiguracja głosu
        self.voice_name = self.VOICES.get(voice_key, self.VOICES['pl_marek'])
        self.rate = rate
        self.pitch = pitch

        # Inicjalizacja pygame mixer do odtwarzania audio
        try:
            pygame.mixer.init(frequency=24000, size=-16, channels=1, buffer=2048)
            print(f"[TTS] Silnik głosowy: edge-tts ({self.voice_name})")
            print(f"[TTS] Rate: {self.rate}, Pitch: {self.pitch}")
        except Exception as e:
            print(f"[TTS] Błąd inicjalizacji pygame mixer: {e}")

        # Katalog na pliki tymczasowe audio
        self._temp_dir = os.path.join(config.BASE_DIR, '.audio_cache')
        os.makedirs(self._temp_dir, exist_ok=True)

    def _run_async(self, coro):
        """Uruchamia korutynę async bezpiecznie z dowolnego wątku."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    async def _generate_speech(self, text, output_file):
        """Generuje mowę z tekstu i zapisuje do pliku MP3."""
        communicate = edge_tts.Communicate(
            text,
            self.voice_name,
            rate=self.rate,
            pitch=self.pitch
        )
        await communicate.save(output_file)

    def _monitor_audio_level(self, audio_path):
        """
        Wątek monitorujący amplitudę audio w czasie rzeczywistym.
        Analizuje plik WAV i wysyła poziom głośności do GUI synchronicznie
        z odtwarzaniem pygame.
        """
        import wave
        import struct
        import threading

        if not self.gui:
            return

        try:
            # Konwertuj MP3 do WAV do analizy amplitudy
            wav_path = audio_path.replace('.mp3', '.wav')
            sound = pygame.mixer.Sound(audio_path)
            # Pobierz surowe dane audio z pygame Sound
            raw = pygame.sndarray.array(sound)

            # Oblicz ramki amplitudy (co ~30ms = ~720 samples przy 24kHz)
            chunk_size = 720
            amplitudes = []
            for i in range(0, len(raw), chunk_size):
                chunk = raw[i:i + chunk_size]
                if len(chunk) == 0:
                    continue
                # RMS amplitude
                rms = np.sqrt(np.mean(chunk.astype(np.float64) ** 2))
                amplitudes.append(rms)

            if not amplitudes:
                return

            # Normalizuj do zakresu 0-1
            max_amp = max(amplitudes) if max(amplitudes) > 0 else 1
            amplitudes = [min(1.0, (a / max_amp) * 1.2) for a in amplitudes]

            def send_levels():
                """Wysyła poziomy audio zsynchronizowane z odtwarzaniem."""
                start_time = time.time()
                frame_duration = chunk_size / 24000.0  # ~30ms

                for i, level in enumerate(amplitudes):
                    if not pygame.mixer.music.get_busy():
                        break

                    self.gui.set_audio_level(level)

                    # Poczekaj do następnej ramki
                    target_time = start_time + (i + 1) * frame_duration
                    sleep_time = target_time - time.time()
                    if sleep_time > 0:
                        time.sleep(sleep_time)

                # Wygaś poziom audio na końcu
                self.gui.set_audio_level(0.0)

            threading.Thread(target=send_levels, daemon=True).start()

        except Exception as e:
            print(f"[TTS] Audio monitor error: {e}")

    def speak(self, text: str):
        """Wypowiada podany tekst naturalnym głosem neuralnym z szybkimi odpowiedziami z bufora."""
        if not text or not text.strip():
            return

        try:
            print(f"JARVIS: {text}")

            # Powiadom GUI że zaczynamy mówić i przekaż tekst zdania
            if self.gui:
                self.gui.set_spoken_text(text)
            if self.on_speak_start:
                self.on_speak_start()

            # Hash z tekstu dla szybkiego buforowania (audio cache)
            import hashlib
            text_hash = hashlib.md5(text.strip().encode('utf-8')).hexdigest()
            # Uwzględniamy nazwę głosu w nazwie pliku cache, by zmiana głosu automatycznie go unieważniała
            cache_path = os.path.join(self._temp_dir, f"cache_{self.voice_name}_{text_hash}.mp3")

            # Jeśli nie ma w buforze, wygeneruj mowę z edge-tts
            if not os.path.exists(cache_path) or os.path.getsize(cache_path) == 0:
                self._run_async(self._generate_speech(text, cache_path))

            # Odtwórz audio przez pygame (błyskawicznie z bufora)
            if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
                # Uruchom monitor poziomu audio PRZED odtwarzaniem
                self._monitor_audio_level(cache_path)

                pygame.mixer.music.load(cache_path)
                pygame.mixer.music.play()

                # Czekaj aż audio się skończy
                while pygame.mixer.music.get_busy():
                    pygame.time.wait(30)

                # Zwolnij plik
                pygame.mixer.music.unload()

            # Powiadom GUI że skończyliśmy mówić
            if self.gui:
                self.gui.set_spoken_text("")
            if self.on_speak_end:
                self.on_speak_end()

        except Exception as e:
            print(f"[TTS] Błąd podczas mówienia: {e}")
            # Fallback: spróbuj pyttsx3 (offline)
            self._speak_fallback(text)
            if self.on_speak_end:
                self.on_speak_end()

    def _speak_fallback(self, text: str):
        """Fallback na systemowy SAPI5 jeśli edge-tts nie działa."""
        try:
            import pyttsx3
            engine = pyttsx3.init('sapi5')
            engine.setProperty('rate', config.JARVIS_VOICE_RATE)
            engine.setProperty('volume', config.JARVIS_VOICE_VOLUME)
            engine.say(text)
            engine.runAndWait()
            print("[TTS] Użyto głosu zapasowego (SAPI5)")
        except Exception as e2:
            print(f"[TTS] Fallback SAPI5 również zawiódł: {e2}")

    def set_voice(self, voice_key: str):
        """Zmienia głos JARVIS-a na inny z listy VOICES."""
        if voice_key in self.VOICES:
            self.voice_name = self.VOICES[voice_key]
            print(f"[TTS] Zmieniono głos na: {self.voice_name}")
        else:
            print(f"[TTS] Nieznany głos: {voice_key}. Dostępne: {list(self.VOICES.keys())}")

    def list_voices(self) -> dict:
        """Zwraca listę dostępnych głosów."""
        return self.VOICES.copy()


class JarvisEar:
    """Klasa odpowiedzialna za nasłuchiwanie i rozpoznawanie mowy (STT)."""

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self._calibrated = False
        # Ustawienia recognizera — mniej wrażliwy na szum
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 1.5
        self.recognizer.non_speaking_duration = 0.8

    def calibrate(self, source: sr.Microphone):
        """Jednorazowa kalibracja mikrofonu do szumów otoczenia."""
        if self._calibrated:
            return
        try:
            print("[MIC] Kalibracja mikrofonu...")
            self.recognizer.adjust_for_ambient_noise(
                source, duration=config.AMBIENT_DURATION
            )
            self._calibrated = True
            print("[MIC] Kalibracja zakończona.")
        except Exception as e:
            print(f"[MIC] Błąd kalibracji: {e}")

    def get_audio_data(self, audio: sr.AudioData) -> np.ndarray:
        """Konwertuje obiekt AudioData do tablicy numpy dla weryfikacji mówcy."""
        try:
            raw_data = np.frombuffer(audio.frame_data, dtype=np.int16)
            float_data = raw_data.astype(np.float32) / 32768.0
            return float_data
        except Exception as e:
            print(f"[MIC] Błąd konwersji audio: {e}")
            return None

    def listen_for_wake_word(self) -> tuple:
        """
        Nasłuchuje wake word 'jarvis'. Nie loguje niczego
        jeśli nie wykryje mowy — cicho czeka.
        Zwraca: (True/False, np.ndarray audio lub None)
        """
        try:
            with sr.Microphone(sample_rate=config.SAMPLE_RATE) as source:
                self.calibrate(source)

                # Cicho nasłuchuj — bez logowania timeoutów
                audio = self.recognizer.listen(
                    source,
                    timeout=config.LISTEN_TIMEOUT,
                    phrase_time_limit=config.PHRASE_TIMEOUT
                )
                text = self.recognizer.recognize_google(
                    audio, language=config.STT_LANGUAGE
                ).lower()

                # Loguj tylko jeśli coś usłyszał
                if config.WAKE_WORD in text:
                    return True, self.get_audio_data(audio)
                else:
                    return False, None

        except sr.WaitTimeoutError:
            # Timeout — cisza, to normalne. Nie loguj.
            return False, None
        except sr.UnknownValueError:
            # Szum/niezrozumiała mowa — normalne. Nie loguj.
            return False, None
        except Exception as e:
            # Tylko prawdziwe błędy loguj
            print(f"[STT] Błąd: {e}")
            return False, None

    def listen_for_command(self) -> str:
        """
        Nasłuchuje komendy po wybudzeniu.
        Zwraca tekst komendy lub pusty string.
        """
        try:
            with sr.Microphone(sample_rate=config.SAMPLE_RATE) as source:
                audio = self.recognizer.listen(
                    source,
                    timeout=config.LISTEN_TIMEOUT,
                    phrase_time_limit=config.PHRASE_TIMEOUT
                )
                text = self.recognizer.recognize_google(
                    audio, language=config.STT_LANGUAGE
                ).lower()
                return text
        except sr.WaitTimeoutError:
            return ""
        except sr.UnknownValueError:
            return ""
        except Exception as e:
            print(f"[STT] Błąd rozpoznawania: {e}")
            return ""


if __name__ == '__main__':
    # Test głosu
    print("=== Test silnika głosowego JARVIS ===")
    voice = JarvisVoice(voice_key='pl_marek')
    voice.speak("Witaj, sir. Silnik głosowy JARVIS aktywny. Wszystkie systemy operacyjne.")
    print("\nDostępne głosy:", voice.list_voices())

    # Test nasłuchiwania
    print("\n=== Test nasłuchiwania ===")
    ear = JarvisEar()
    print("Powiedz 'Jarvis'...")
    detected, audio_data = ear.listen_for_wake_word()
    if detected:
        print("Wykryto wake word!")
        cmd = ear.listen_for_command()
        print(f"Komenda: {cmd}")
