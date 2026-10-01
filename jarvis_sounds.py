"""
jarvis_sounds.py
Moduł odpowiedzialny za generowanie i odtwarzanie futurystycznych
efektów dźwiękowych Iron Mana (aktywacja reaktora, czuwanie, zatwierdzenie akcji).
"""
import os
import wave
import struct
import math
import pygame
import config

class SoundEffects:
    def __init__(self):
        self.sound_dir = os.path.join(config.BASE_DIR, '.sound_effects')
        os.makedirs(self.sound_dir, exist_ok=True)
        
        self.wake_file = os.path.join(self.sound_dir, 'wake.wav')
        self.standby_file = os.path.join(self.sound_dir, 'standby.wav')
        self.action_file = os.path.join(self.sound_dir, 'action.wav')
        
        self._ensure_sounds_exist()
        self._load_sounds()

    def _generate_wav(self, filepath, generator_func, duration=0.4, sample_rate=22050):
        """Generuje syntetyczny plik WAV na podstawie funkcji f(t)."""
        num_samples = int(duration * sample_rate)
        with wave.open(filepath, 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            
            raw_bytes = bytearray()
            for i in range(num_samples):
                t = i / sample_rate
                val = generator_func(t, duration)
                # Kamping [-1.0, 1.0]
                val = max(-1.0, min(1.0, val))
                sample_int = int(val * 32767)
                raw_bytes.extend(struct.pack('<h', sample_int))
            wav_file.writeframes(raw_bytes)

    def _ensure_sounds_exist(self):
        """Generuje 3 efekty dźwiękowe sci-fi o wysoce mechanicznym, metalicznym brzmieniu."""
        import random
        
        if not os.path.exists(self.wake_file):
            # Wybudzenie / Aktywacja: Mechaniczny zgrzyt serwa + metaliczne ryglowanie + narastający impuls mocy
            def wake_mech(t, dur):
                # 1. Metaliczny styk / klik na samym początku (t < 0.05s)
                click = math.sin(2 * math.pi * 2400 * t) * math.exp(-60 * t) if t < 0.08 else 0
                # 2. Szum przeskakującej zębatki / hydrauliki
                mech_noise = (math.sin(1700 * t) * math.cos(3100 * t)) * (0.3 * math.exp(-15 * t))
                # 3. Narastający kwadratowy ton serwomechanizmu z akcentem reaktora
                freq = 150 + 650 * (t / dur)**2
                servo = 0.5 * math.sin(2 * math.pi * freq * t) + 0.25 * math.sin(2 * math.pi * freq * 2 * t)
                # Obwiednia narastająca i opadająca
                env = math.sin(math.pi * (t / dur))
                return (click * 0.5 + mech_noise + servo * 0.5) * env * 0.45

            self._generate_wav(self.wake_file, wake_mech, duration=0.38)

        if not os.path.exists(self.standby_file):
            # Czuwanie / Wyłączenie: Zawór hydrauliczny + opadające przekładnie + metaliczne stuknięcie
            def standby_mech(t, dur):
                # 1. Stuknięcie przekaźnika (t < 0.06s)
                clack = math.sin(2 * math.pi * 1500 * t) * math.exp(-50 * t) if t < 0.06 else 0
                # 2. Opadający ton zaworu i prądu
                freq = max(60, 500 - 400 * (t / dur)**0.8)
                sub = 0.6 * math.sin(2 * math.pi * freq * t) + 0.3 * math.sin(2 * math.pi * (freq * 1.5) * t)
                # 3. Szum opadającego ciśnienia hydraulicznego
                hiss = (math.sin(2300 * t) * math.sin(4100 * t)) * (0.2 * math.exp(-3 * t))
                env = math.exp(-3.5 * (t / dur))
                return (clack * 0.4 + sub + hiss) * env * 0.4

            self._generate_wav(self.standby_file, standby_mech, duration=0.42)

        if not os.path.exists(self.action_file):
            # Zatwierdzenie akcji: Ostre, mechaniczne kliknięcie przekaźnika z podwójnym rezonansem
            def action_mech(t, dur):
                # Podwójne mechaniczne kliknięcie (20ms i 70ms)
                c1 = math.sin(2 * math.pi * 2800 * t) * math.exp(-70 * t)
                t2 = t - 0.05
                c2 = (math.sin(2 * math.pi * 3600 * t2) * math.exp(-80 * t2)) if t2 > 0 else 0
                # Metaliczny ton rezonansowy
                ring = 0.3 * math.sin(2 * math.pi * 1400 * t) * math.exp(-20 * t)
                return (c1 * 0.45 + c2 * 0.45 + ring) * 0.4

            self._generate_wav(self.action_file, action_mech, duration=0.16)

    def _load_sounds(self):
        """Ładuje efekty dźwiękowe do Pygame Mixer."""
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=1024)
            self.snd_wake = pygame.mixer.Sound(self.wake_file)
            self.snd_standby = pygame.mixer.Sound(self.standby_file)
            self.snd_action = pygame.mixer.Sound(self.action_file)
        except Exception as e:
            print(f"[SOUNDS] Błąd ładowania dźwięków: {e}")
            self.snd_wake = None
            self.snd_standby = None
            self.snd_action = None

    def play_wake(self):
        """Odtwarza dźwięk aktywacji przy wykryciu wake word."""
        if self.snd_wake:
            try:
                self.snd_wake.play()
            except Exception:
                pass

    def play_standby(self):
        """Odtwarza dźwięk przejścia w tryb czuwania."""
        if self.snd_standby:
            try:
                self.snd_standby.play()
            except Exception:
                pass

    def play_action(self):
        """Odtwarza dźwięk wykonania komendy."""
        if self.snd_action:
            try:
                self.snd_action.play()
            except Exception:
                pass
