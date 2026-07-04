import io
import tempfile
import wave
from pathlib import Path

import numpy as np

from ai.inference.scam import ScamDetectionPipeline
from ai.preprocessing.audio import validate_audio
from ai.utils.lazy_imports import optional_import


class VoiceAnalysisPipeline:
    @staticmethod
    def forensic_signals(content: bytes) -> dict:
        """Extract reproducible WAV signal indicators; this is not a certified deepfake verdict."""
        try:
            with wave.open(io.BytesIO(content), "rb") as source:
                sample_rate = source.getframerate()
                channels = source.getnchannels()
                width = source.getsampwidth()
                frames = source.readframes(min(source.getnframes(), sample_rate * 120))
            if width != 2 or not frames:
                raise ValueError("Only 16-bit PCM WAV supports local voice forensics")
            signal = np.frombuffer(frames, dtype="<i2").astype(np.float64)
            if channels > 1:
                signal = signal.reshape(-1, channels).mean(axis=1)
            signal /= 32768.0
            if signal.size < sample_rate:
                raise ValueError("At least one second of audio is required")
            rms = float(np.sqrt(np.mean(signal ** 2)))
            zcr = float(np.mean(np.abs(np.diff(np.signbit(signal)))))
            spectrum = np.abs(np.fft.rfft(signal[: min(signal.size, sample_rate * 20)])) + 1e-12
            frequencies = np.fft.rfftfreq(min(signal.size, sample_rate * 20), 1 / sample_rate)
            flatness = float(np.exp(np.mean(np.log(spectrum))) / np.mean(spectrum))
            centroid = float(np.sum(frequencies * spectrum) / np.sum(spectrum))
            frame_size = max(1, sample_rate // 20)
            frame_count = signal.size // frame_size
            energies = np.array([
                np.sqrt(np.mean(signal[i * frame_size:(i + 1) * frame_size] ** 2))
                for i in range(frame_count)
            ])
            energy_variation = float(np.std(energies) / (np.mean(energies) + 1e-9))
            score = 0
            reasons = []
            if flatness < 0.015:
                score += 22
                reasons.append("Unusually low spectral flatness")
            if energy_variation < 0.18:
                score += 24
                reasons.append("Unusually uniform frame energy")
            if zcr < 0.015 or zcr > 0.25:
                score += 16
                reasons.append("Atypical zero-crossing rate")
            if centroid < 450 or centroid > 5000:
                score += 14
                reasons.append("Atypical spectral centroid")
            if rms < 0.005:
                reasons.append("Audio level is too low for reliable analysis")
            score = min(score, 100)
            return {
                "available": True, "method": "pcm-signal-heuristics-v1",
                "synthetic_likelihood": score, "classification": (
                    "synthetic_suspected" if score >= 60 else "inconclusive" if score >= 30 else "no_strong_signal"
                ),
                "reasons": reasons, "metrics": {
                    "sample_rate": sample_rate, "duration_seconds": round(signal.size / sample_rate, 2),
                    "rms": round(rms, 5), "zero_crossing_rate": round(zcr, 5),
                    "spectral_flatness": round(flatness, 5),
                    "spectral_centroid_hz": round(centroid, 1),
                    "energy_variation": round(energy_variation, 4),
                },
                "limitation": "Heuristic screening only; forensic confirmation requires a validated voice model and original media.",
            }
        except (wave.Error, ValueError, EOFError) as exc:
            return {
                "available": False, "method": "pcm-signal-heuristics-v1",
                "synthetic_likelihood": 0, "classification": "not_assessed",
                "reasons": [str(exc)], "metrics": {},
                "limitation": "Provide a 16-bit PCM WAV recording for local signal analysis.",
            }

    async def analyze(self, filename: str, content: bytes, caller_number: str = "unknown", previous_reports: int = 0):
        suffix = validate_audio(filename, content)
        transcript = ""
        whisper = optional_import("whisper")
        model_version = "whisper-placeholder-v1.0"
        if whisper:
            with tempfile.NamedTemporaryFile(suffix=suffix) as target:
                target.write(content)
                target.flush()
                transcript = whisper.load_model("base").transcribe(target.name)["text"]
                model_version = "whisper-base-v1.0"
        if not transcript:
            transcript = "Audio transcription requires the optional Whisper model."
        result = await ScamDetectionPipeline().predict(caller_number, transcript, 0, False, previous_reports)
        result.details.update({
            "transcript": transcript, "speech_model": model_version,
            "voice_forensics": self.forensic_signals(content),
        })
        return result
