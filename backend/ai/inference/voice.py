import tempfile
from pathlib import Path

from ai.inference.scam import ScamDetectionPipeline
from ai.preprocessing.audio import validate_audio
from ai.utils.lazy_imports import optional_import


class VoiceAnalysisPipeline:
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
        result.details.update({"transcript": transcript, "speech_model": model_version})
        return result
