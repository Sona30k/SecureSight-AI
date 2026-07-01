from io import BytesIO

from ai.inference import CurrencyDetectionPipeline, OCRPipeline, VoiceAnalysisPipeline
from ai.preprocessing import detect_keywords, normalize_text
from app.ai import NLPAnalyzer, RiskScoringEngine, RiskSignals


class ChatService:
    """RAG-ready orchestrator. Replace retrieve() and generate() without changing the API."""

    def __init__(self):
        self.nlp = NLPAnalyzer()
        self.risk = RiskScoringEngine()

    async def chat(
        self, text: str, attachment_type: str | None = None,
        attachment: bytes | None = None, filename: str = "",
    ) -> dict:
        original_text = text.strip()
        normalized = normalize_text(original_text)
        attachment_context = ""
        attachment_score = 0
        if attachment and attachment_type == "image":
            if any(word in normalized for word in ("currency", "note", "counterfeit", "rupee")):
                prediction = await CurrencyDetectionPipeline().predict(attachment)
                attachment_score = prediction.risk_score
                attachment_context = (
                    f" Currency image assessment: {prediction.prediction} "
                    f"({prediction.confidence:.1f}% confidence). {'; '.join(prediction.explanation)}."
                )
            else:
                ocr = await OCRPipeline().extract(attachment)
                extracted = " ".join(ocr.get("text", []))
                if extracted:
                    text = f"{original_text}\nExtracted image text: {extracted}"
                attachment_context = (
                    f" I extracted visible text from the image with {ocr['confidence']:.1f}% OCR confidence."
                    " A QR image alone cannot establish that its destination is trustworthy."
                )
        elif attachment and attachment_type == "voice":
            prediction = await VoiceAnalysisPipeline().analyze(filename or "audio.wav", attachment)
            attachment_score = prediction.risk_score
            transcript = prediction.details.get("transcript", "")
            if transcript and "requires the optional Whisper model" not in transcript:
                text = f"{original_text}\nVoice transcript: {transcript}"
                attachment_context = f" Voice transcript analyzed: {transcript[:600]}"
            else:
                attachment_context = " Voice upload received, but local transcription requires the optional Whisper model."
        elif attachment and attachment_type == "pdf":
            from pypdf import PdfReader
            extracted = " ".join((page.extract_text() or "") for page in PdfReader(BytesIO(attachment)).pages[:20])
            attachment_context = f" I reviewed {min(len(extracted), 8000)} characters extracted from the document."
            text = f"{text}\n{extracted[:8000]}"

        normalized = normalize_text(text)
        informational = normalized.startswith(("explain ", "what is ", "how does ", "how do "))
        needs_context = (
            not attachment
            and len(original_text.split()) < 8
            and any(phrase in normalized for phrase in ("is this fake", "is this message fake", "check this", "verify this", "is this a scam"))
        )
        if needs_context:
            return {
                "response": (
                    "Please paste the full suspicious message, caller statement, UPI request, or link details. "
                    "You can also attach one image, audio file, or PDF. Remove passwords, OTPs, PINs, and account credentials first."
                ),
                "confidence": 0.99,
                "risk_level": "low",
                "recommendations": ["Provide the suspicious content", "Redact sensitive credentials", "Do not click or pay while checking"],
            }
        if informational and "digital arrest" in normalized:
            return {
                "response": (
                    "A “digital arrest” is a scam, not a lawful police procedure. Fraudsters impersonate police, CBI, customs, "
                    "courts, or banks; keep victims on video calls; demand secrecy; and request a “verification” transfer. "
                    "End the call, do not transfer money, independently contact the agency through an official number, preserve evidence, "
                    "and report immediate financial loss to your bank and the appropriate cybercrime channel."
                ),
                "confidence": 0.99,
                "risk_level": "high",
                "recommendations": ["End the call", "Never transfer verification funds", "Verify independently", "Preserve and report evidence"],
            }
        analysis = await self.nlp.analyze(text)
        score, _ = self.risk.score(RiskSignals(
            suspicious_keywords=len(analysis["keywords"]),
            coercion_detected=analysis["coercion_detected"],
            suspicious_transactions=1 if any(x in text.lower() for x in ("upi", "qr", "transfer", "otp")) else 0,
        ))
        score = max(score, attachment_score)
        if "digital arrest" in normalized:
            score = max(score, 78)
        if "share otp" in normalized or ("transfer immediately" in normalized and any(x in normalized for x in ("cbi", "police", "customs", "court"))):
            score = max(score, 82)
        level = "critical" if score >= 80 else "high" if score >= 60 else "medium" if score >= 30 else "low"
        keywords = detect_keywords(text)
        if score >= 60:
            response = (
                "This content has strong fraud indicators and should be treated as high risk. "
                "Stop engaging, do not click links or transfer funds, and never share an OTP, PIN, password, or screen." + attachment_context
            )
            recommendations = ["Stop engaging immediately", "Contact the institution through an official channel", "Preserve evidence and report it"]
        elif score >= 30:
            response = (
                "I found several suspicious signals. Pause before taking any action and independently verify the sender or payment request."
                + attachment_context
            )
            recommendations = ["Do not approve a payment request", "Verify the sender independently", "Report further pressure or threats"]
        elif any(term in normalized for term in ("upi", "qr", "payment", "bank account", "blocked")):
            response = (
                "I did not find enough evidence to confirm fraud, but payment and account-verification requests require extra caution. "
                "Check the payee name inside your official banking app and contact the bank through its published number." + attachment_context
            )
            recommendations = ["Verify the payee name", "Never enter a UPI PIN to receive money", "Avoid links from unsolicited messages"]
        else:
            response = "I did not find strong fraud indicators in the supplied content. That is not a guarantee of safety; verify the sender before taking financial action." + attachment_context
            recommendations = ["Check the official domain", "Never share OTP or PIN", "Report any request for urgent payment"]
        if keywords:
            response += f" Detected risk phrases: {', '.join(keywords)}."
        return {
            "response": response,
            "confidence": round(min(.62 + score / 180, .98), 2),
            "risk_level": level,
            "recommendations": recommendations,
        }
