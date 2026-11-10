"""
Phase 7 — fixed escalation text.

Blueprint §12 requires the escalation mechanism to be a fixed, template-based
message (never LLM-generated) that directs the user to a human, and §13 requires
that text to be pre-translated so a translation step cannot garble or alter it.
Both requirements are met by holding the strings here as data.

None of these messages contains a dose, a PHI/REI value in days, or a
protective-equipment specification. That is checked by a test rather than left
to review: a refusal that quotes the number it refuses to give would defeat
itself.
"""
from __future__ import annotations

from typing import Optional

from app.rules.schemas import EscalationAction

ESCALATION_MESSAGES: dict[str, dict[str, str]] = {
    "ESCALATE_MISSING_INFO": {
        "en": "I stopped before giving advice because information this system requires is not "
              "published in the source. Check the product label and confirm the dose, waiting "
              "period and protective equipment with your local agricultural extension officer "
              "before spraying.",
        "hi": "सलाह देने से पहले मैं रुक गया, क्योंकि इस प्रणाली के लिए ज़रूरी जानकारी स्रोत में "
              "प्रकाशित नहीं है। छिड़काव से पहले उत्पाद का लेबल देखें और मात्रा, प्रतीक्षा अवधि "
              "और सुरक्षा उपकरण की पुष्टि अपने स्थानीय कृषि विस्तार अधिकारी से करें।",
    },
    "ESCALATE_CONTRADICTION": {
        "en": "The sources available to me disagree on a safety-critical value for this crop and "
              "target. I will not choose between them or average them. Please confirm with your "
              "local agricultural extension officer or the product label.",
        "hi": "इस फसल और लक्ष्य के लिए उपलब्ध स्रोत एक सुरक्षा-संबंधी मान पर सहमत नहीं हैं। मैं "
              "उनमें से कोई चुनूँगा या औसत नहीं निकालूँगा। कृपया अपने स्थानीय कृषि विस्तार "
              "अधिकारी या उत्पाद के लेबल से पुष्टि करें।",
    },
    "ESCALATE_LOW_CONFIDENCE": {
        "en": "I could not establish what is being asked with enough confidence to look it up. "
              "Please name the crop and the pest, or ask your local agricultural extension "
              "officer.",
        "hi": "जो पूछा गया है वह मैं पर्याप्त विश्वास के साथ समझ नहीं सका। कृपया फसल और कीट का नाम "
              "बताएँ, या अपने स्थानीय कृषि विस्तार अधिकारी से पूछें।",
    },
}


def escalation_message(action: Optional[EscalationAction], language: str) -> str:
    """Localised fixed text for a blocking action. Empty string if not blocking."""
    if action is None:
        return ""
    table = ESCALATION_MESSAGES.get(action)
    if not table:
        return ""
    return table.get(language) or table.get("en") or ""
