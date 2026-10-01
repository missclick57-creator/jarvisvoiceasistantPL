"""
Moduł odpowiedzialny za weryfikację mówcy (Speaker Verification),
aby upewnić się, że asystent reaguje tylko na głos właściciela.
"""

import os
import numpy as np
import librosa
import sounddevice as sd
from scipy.spatial.distance import cosine
import config

class SpeakerVerifier:
    """Klasa do weryfikacji tożsamości mówcy na podstawie cech MFCC."""
    
    def __init__(self):
        # Profil mówcy zostaje załadowany jeśli istnieje
        self.profile = None
        if self.is_enrolled():
            try:
                self.profile = np.load(config.SPEAKER_PROFILE_FILE)
                # Jeśli to stary profil (26 cech z energią), usuwamy go, aby wymusić nową dokładną rejestrację
                if self.profile.shape == (26,):
                    print("[Speaker] Wykryto stary profil (26 cech). Usuwam w celu uaktualnienia.")
                    try:
                        os.remove(config.SPEAKER_PROFILE_FILE)
                    except OSError:
                        pass
                    self.profile = None
            except Exception as e:
                print(f"Błąd podczas ładowania profilu mówcy: {e}")

    def is_enrolled(self) -> bool:
        """Sprawdza, czy istnieje zapisany profil mówcy."""
        return os.path.exists(config.SPEAKER_PROFILE_FILE)

    def _extract_features(self, audio: np.ndarray) -> np.ndarray:
        """
        Ekstrahuje współczynniki MFCC (z pominięciem 0-go współczynnika energii)
        oraz ich delty. Skaluje wiersze ich własnym odchyleniem standardowym w czasie
        dla zbalansowania wag cech. Zwraca uśredniony wektor (24 wymiary).
        """
        try:
            # Obliczenie MFCC (13 współczynników)
            mfcc = librosa.feature.mfcc(y=audio, sr=config.SAMPLE_RATE, n_mfcc=13)
            # Usuwamy pierwszy współczynnik energii (indeks 0)
            mfcc_clean = mfcc[1:]
            
            # Normalizacja wariancji wierszy MFCC
            mfcc_std = np.std(mfcc_clean, axis=1, keepdims=True)
            mfcc_scaled = mfcc_clean / (mfcc_std + 1e-8)
            
            # Obliczenie delt z znormalizowanego MFCC
            delta_mfcc = librosa.feature.delta(mfcc_scaled)
            delta_std = np.std(delta_mfcc, axis=1, keepdims=True)
            delta_scaled = delta_mfcc / (delta_std + 1e-8)
            
            # Łączenie cech (24, liczba_ramek)
            combined = np.vstack([mfcc_scaled, delta_scaled])
            # Uśrednienie w czasie (daje 24 cechy)
            mean_features = np.mean(combined, axis=1)
            return mean_features
        except Exception as e:
            print(f"Błąd podczas ekstrakcji cech: {e}")
            return np.zeros(24)

    def _record_sample(self, duration: int) -> np.ndarray:
        """Nagrywa próbkę audio z mikrofonu przez zadany czas."""
        try:
            print(f"Nagrywanie przez {duration} sekund...")
            # sounddevice zwraca tablicę (frames, channels)
            recording = sd.rec(int(duration * config.SAMPLE_RATE), 
                               samplerate=config.SAMPLE_RATE, 
                               channels=1, 
                               dtype='float32')
            sd.wait()
            # Spłaszczenie do (frames,)
            return recording.flatten()
        except Exception as e:
            print(f"Błąd podczas nagrywania próbki: {e}")
            return np.array([])

    def enroll(self, voice_feedback=None):
        """
        Przewodnik po rejestracji (enrollment): nagrywa próbki, 
        oblicza średni wektor i zapisuje do pliku.
        Zwraca True jeśli rejestracja się powiodła, False w przeciwnym razie.
        """
        import time
        print("=== REJESTRACJA PROFILU GŁOSOWEGO ===")
        print(f"Będziemy nagrywać {config.ENROLLMENT_SAMPLES} próbek.")
        
        all_features = []
        try:
            for i in range(config.ENROLLMENT_SAMPLES):
                prompt_msg = (
                    f"Próbka {i+1} z {config.ENROLLMENT_SAMPLES}. "
                    f"Powiedz wyraźnie słowo Jarvis."
                )
                print(f"\n[ENROLLMENT] {prompt_msg}")
                if voice_feedback:
                    voice_feedback.speak(prompt_msg)
                
                time.sleep(0.5)  # Krótka pauza przed nagrywaniem
                audio_data = self._record_sample(duration=config.ENROLLMENT_SAMPLE_DURATION)
                
                if len(audio_data) > 0:
                    features = self._extract_features(audio_data)
                    all_features.append(features)
                    print(f"[ENROLLMENT] Próbka {i+1} przetworzona pomyślnie.")
                    if voice_feedback:
                        voice_feedback.speak("Zapisano.")
                else:
                    print(f"[ENROLLMENT] Puste nagranie dla próbki {i+1}.")
                    if voice_feedback:
                        voice_feedback.speak("Nie wykryłem dźwięku. Kontynuuję.")
            
            if len(all_features) >= 3:  # Minimum 3 dobre próbki
                # Uśrednienie ze wszystkich próbek dla uodpornienia na wahania głosu
                final_profile = np.mean(all_features, axis=0)
                np.save(config.SPEAKER_PROFILE_FILE, final_profile)
                self.profile = final_profile
                print("[ENROLLMENT] Profil głosowy został pomyślnie zapisany!")
                return True
            else:
                print("[ENROLLMENT] Za mało prawidłowych próbek do rejestracji.")
                return False
        except Exception as e:
            print(f"[ENROLLMENT] Błąd podczas procesu rejestracji: {e}")
            return False

    def verify(self, audio_data: np.ndarray) -> bool:
        """
        Porównuje nową próbkę audio z zapisanym profilem mówcy.
        Zwraca True, jeśli podobieństwo osiąga SIMILARITY_THRESHOLD.
        """
        if self.profile is None:
            print("Brak zapisanego profilu mówcy. Proszę wykonać rejestrację (enroll).")
            return False
            
        if len(audio_data) == 0:
            print("Puste dane audio podane do weryfikacji.")
            return False

        try:
            current_features = self._extract_features(audio_data)
            
            # cosine z scipy oblicza dystans (distance), podobieństwo to 1 - distance
            dist = cosine(self.profile, current_features)
            similarity = 1 - dist
            
            print(f"[Debug] Podobieństwo głosowe: {similarity:.4f} (próg: {config.SIMILARITY_THRESHOLD})")
            
            return similarity >= config.SIMILARITY_THRESHOLD
        except Exception as e:
            print(f"Błąd podczas weryfikacji mówcy: {e}")
            return False

if __name__ == '__main__':
    try:
        verifier = SpeakerVerifier()
        if not verifier.is_enrolled():
            print("Profil nie istnieje. Rozpoczynamy rejestrację.")
            verifier.enroll()
        else:
            print("Profil istnieje. Spróbujmy przeprowadzić weryfikację.")
            print("Powiedz coś przez 3 sekundy (np. 'jarvis, włącz światło').")
            test_audio = verifier._record_sample(duration=3)
            result = verifier.verify(test_audio)
            if result:
                print("Tożsamość potwierdzona! Zrozumiałem komendę.")
            else:
                print("Odrzucenie tożsamości! Zły mówca.")
    except Exception as e:
        print(f"Błąd testowania: {e}")
