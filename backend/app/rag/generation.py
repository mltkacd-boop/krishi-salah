"""
Phase 6 — grounded, extractive answer assembly (English + Hindi).

WHY EXTRACTIVE
--------------
Every agricultural statement in the output is a field copied from a validated
knowledge-base record (`description`, `active_ingredient_and_formulation`,
`dosage`, pest names, PHI/REI/PPE status/values). The generator only adds fixed
scaffolding: headings, connective phrases, and the safety framing. That is what
makes "never invent a pesticide approval or a safety value" true by
construction — there is no step in which a model could produce a number.

Language policy
---------------
The scaffolding is bilingual (EN / HI). **Quoted source text stays in the
language it was transcribed in and is labelled as a quotation.** Translating a
quotation would create a new claim that no source makes, so it is not done; a
Hindi reader therefore sees Hindi framing and the source's own wording.

The Hindi is deliberately simple and formulaic (short sentences, no idiom),
because an agriculture extension message must stay unambiguous.
"""
from __future__ import annotations

from typing import Optional, Sequence

from app.knowledge_base.models import ApprovedUse, Crop, Source

CONTROL_TYPE_LABELS = {
    "en": {
        "chemical": "Chemical measures",
        "biological": "Biological measures",
        "cultural": "Cultural measures",
        "mechanical": "Mechanical measures",
    },
    "hi": {
        "chemical": "रासायनिक उपाय",
        "biological": "जैविक उपाय",
        "cultural": "फसल प्रबंधन उपाय",
        "mechanical": "यांत्रिक उपाय",
    },
}

TEXT = {
    "en": {
        "answer": "Recorded measures for {pest} in {crop}, as described by {authority}.",
        "pest_heading": "Crop and pest",
        "measures_heading": "Measures recorded in the source",
        "safety_heading": "Safety information in this record",
        "limits_heading": "What this answer does not establish",
        "pest_line": "Pest: {pest}",
        "scientific_line": "Scientific name: {name}",
        "threshold_line": "Economic threshold stated by the source: {threshold}",
        "ingredient_line": "Active ingredient / formulation: {value}",
        "dosage_line": "Dose printed in the source: {value}",
        "dosage_caveat": "This is the source's wording, not a recommendation from this assistant.",
        "phi": "Pre-harvest interval (PHI)",
        "rei": "Re-entry interval (REI)",
        "ppe": "Protective equipment (PPE)",
        "not_published": "Not published in the source",
        "published": "Published in the source",
        "limit_1": "This record is source-verified only. It has NOT been checked against the "
                   "CIB&RC product registry, so it is not evidence of a current product registration.",
        "limit_2": "Because PHI, REI and PPE are not published for this record, it is "
                   "EDUCATIONAL_ONLY: it must not be presented as a safe, ready-to-apply dose.",
        "limit_2_ok": "This record has a complete safety profile and may be used as an "
                      "evidence-backed recommendation.",
        "limit_3": "Always read the product label and confirm local restrictions before any use.",
        "educational": "Educational information only. Not a pesticide recommendation or a "
                       "regulatory approval.",
        "quoted_note": "Quoted from the source in its original language.",
        "safety_followup": "For a specific product, dose or waiting period, consult your local "
                           "agricultural extension officer.",
    },
    "hi": {
        "answer": "{crop} में {pest} के लिए स्रोत में दर्ज उपाय, {authority} के अनुसार।",
        "pest_heading": "फसल और कीट",
        "measures_heading": "स्रोत में दर्ज उपाय",
        "safety_heading": "इस रिकॉर्ड में सुरक्षा जानकारी",
        "limits_heading": "यह उत्तर क्या सिद्ध नहीं करता",
        "pest_line": "कीट: {pest}",
        "scientific_line": "वैज्ञानिक नाम: {name}",
        "threshold_line": "स्रोत में दिया गया आर्थिक क्षति स्तर: {threshold}",
        "ingredient_line": "सक्रिय तत्व / फॉर्मूलेशन: {value}",
        "dosage_line": "स्रोत में छपी मात्रा: {value}",
        "dosage_caveat": "यह स्रोत के शब्द हैं, यह सहायक की सिफ़ारिश नहीं है।",
        "phi": "फसल कटाई से पहले की प्रतीक्षा अवधि (PHI)",
        "rei": "फिर से खेत में जाने का अंतराल (REI)",
        "ppe": "सुरक्षा उपकरण (PPE)",
        "not_published": "स्रोत में नहीं दिया गया",
        "published": "स्रोत में दिया गया",
        "limit_1": "यह रिकॉर्ड केवल स्रोत से सत्यापित है। इसे CIB&RC उत्पाद रजिस्ट्री से नहीं "
                   "मिलाया गया है, इसलिए यह वर्तमान पंजीकरण का प्रमाण नहीं है।",
        "limit_2": "इस रिकॉर्ड में PHI, REI और PPE स्रोत में नहीं दिए गए हैं, इसलिए यह "
                   "EDUCATIONAL_ONLY है: इसे सुरक्षित, तुरंत लागू करने योग्य मात्रा के रूप में "
                   "नहीं दिखाया जाना चाहिए।",
        "limit_2_ok": "इस रिकॉर्ड में पूरी सुरक्षा जानकारी है और इसे प्रमाण-आधारित सिफ़ारिश "
                      "के रूप में उपयोग किया जा सकता है।",
        "limit_3": "किसी भी उपयोग से पहले उत्पाद का लेबल पढ़ें और स्थानीय नियमों की पुष्टि करें।",
        "educational": "यह केवल शैक्षिक जानकारी है। यह कीटनाशक सिफ़ारिश या नियामक अनुमोदन नहीं है।",
        "quoted_note": "स्रोत से उसी भाषा में उद्धृत।",
        "safety_followup": "किसी विशेष उत्पाद, मात्रा या प्रतीक्षा अवधि के लिए अपने स्थानीय "
                           "कृषि विस्तार अधिकारी से सलाह लें।",
    },
}

OUTCOME_MESSAGES = {
    "needs_clarification": {
        "en": "I need one more detail before I can look this up in the knowledge base.",
        "hi": "जानकारी खोजने से पहले मुझे एक और विवरण चाहिए।",
    },
    "out_of_scope": {
        "en": "This question is outside what this assistant covers. It only answers crop "
              "protection questions for rice, wheat, maize, cotton and tomato.",
        "hi": "यह प्रश्न इस सहायक के दायरे से बाहर है। यह केवल धान, गेहूँ, मक्का, कपास और "
              "टमाटर की फसल सुरक्षा से जुड़े प्रश्नों का उत्तर देता है।",
    },
    "unsupported_crop": {
        "en": "This assistant currently covers only rice, wheat, maize, cotton and tomato. "
              "I have no verified source for that crop, so I will not guess.",
        "hi": "यह सहायक अभी केवल धान, गेहूँ, मक्का, कपास और टमाटर के लिए है। उस फसल के लिए "
              "मेरे पास सत्यापित स्रोत नहीं है, इसलिए मैं अनुमान नहीं लगाऊँगा।",
    },
    "insufficient_evidence": {
        "en": "I found no knowledge-base record that supports an answer to this question. "
              "Rather than compose an answer from general knowledge, I am stopping here. "
              "Please rephrase with the crop and the pest, or ask your local extension officer.",
        "hi": "मुझे इस प्रश्न का उत्तर देने योग्य कोई ज्ञान-आधार रिकॉर्ड नहीं मिला। सामान्य जानकारी "
              "से उत्तर बनाने के बजाय मैं यहीं रुक रहा हूँ। कृपया फसल और कीट के साथ प्रश्न दोहराएँ, "
              "या अपने स्थानीय कृषि विस्तार अधिकारी से पूछें।",
    },
    "safety_value_not_published": {
        "en": "No source in this knowledge base publishes a PHI, REI or PPE value for this "
              "record, so I cannot give one. I will not estimate a waiting period or a "
              "protective-equipment requirement. Use the product label and confirm with your "
              "extension officer before spraying.",
        "hi": "इस ज्ञान-आधार के किसी स्रोत में इस रिकॉर्ड के लिए PHI, REI या PPE मान नहीं दिया "
              "गया है, इसलिए मैं यह नहीं बता सकता। मैं प्रतीक्षा अवधि या सुरक्षा उपकरण का अनुमान "
              "नहीं लगाऊँगा। छिड़काव से पहले उत्पाद का लेबल देखें और विस्तार अधिकारी से पुष्टि करें।",
    },
    "safety_contradiction": {
        "en": "The sources available to me disagree on a safety-critical value for this crop and "
              "target. I will not choose between them or average them. Please confirm with your "
              "local agricultural extension officer or the product label.",
        "hi": "इस फसल और लक्ष्य के लिए उपलब्ध स्रोत एक सुरक्षा-संबंधी मान पर सहमत नहीं हैं। मैं "
              "उनमें से कोई चुनूँगा या औसत नहीं निकालूँगा। कृपया अपने स्थानीय कृषि विस्तार "
              "अधिकारी या उत्पाद के लेबल से पुष्टि करें।",
    },
    "no_regulatory_verification": {
        "en": "This knowledge base records what named public sources recommend. It has never "
              "been cross-checked against the CIB&RC product registry, so I cannot confirm or "
              "deny that a product is registered or approved for a crop. Check the CIB&RC "
              "registration directly.",
        "hi": "यह ज्ञान-आधार केवल यह दर्ज करता है कि नामित सार्वजनिक स्रोत क्या सुझाते हैं। इसे "
              "CIB&RC उत्पाद रजिस्ट्री से कभी नहीं मिलाया गया, इसलिए मैं किसी उत्पाद के पंजीकरण "
              "या अनुमोदन की पुष्टि या खंडन नहीं कर सकता। कृपया CIB&RC पंजीकरण स्वयं जाँचें।",
    },
}


def outcome_message(code: str, language: str) -> str:
    table = OUTCOME_MESSAGES.get(code, {})
    return table.get(language) or table.get("en") or ""


def _t(language: str, key: str, **kwargs) -> str:
    template = TEXT[language][key]
    return template.format(**kwargs) if kwargs else template


def _has_latin_letters(text: str) -> bool:
    return any(ch.isascii() and ch.isalpha() for ch in text)


def _safety_section(records: Sequence[ApprovedUse], language: str) -> tuple[list[dict], list[dict], bool]:
    """Build the safety section, the disclosure objects, and an all-published flag."""
    items: list[dict] = []
    disclosures: list[dict] = []
    all_published = True

    for record in records:
        for field_name in ("phi", "rei", "ppe"):
            field = getattr(record.safety_restrictions, field_name)
            disclosures.append({
                "field": field_name,
                "status": field.status,
                "value": field.value,
                "note": field.note,
            })
            label = _t(language, field_name)
            if field.status == "PUBLISHED" and field.value:
                items.append(f"{label}: {field.value}")
            else:
                all_published = False
                note = f" — {field.note}" if field.note else ""
                if field.note and language != "en" and _has_latin_letters(field.note):
                    # The note is verbatim source text in English. In a Hindi
                    # answer it is labelled as a quotation instead of being
                    # spliced in as if it were translated prose.
                    note = f" ({_t(language, 'quoted_note')} \"{field.note}\")"
                items.append(f"{label}: {_t(language, 'not_published')}{note}")

    return items, disclosures, all_published


def build_answer(
    *,
    records: Sequence[ApprovedUse],
    crops: dict[str, Crop],
    sources: dict[str, Source],
    language: str,
) -> tuple[str, list[dict], list[dict], bool]:
    """
    Compose the grounded answer.

    Returns (answer, sections, safety_disclosures, all_safety_published).
    `records` must already be the crop-matched, evidence-backed subset.
    """
    primary = records[0]
    crop = crops.get(primary.crop_id)
    source = sources.get(primary.source_id)
    crop_name = crop_display_name(primary.crop_id, crop.crop_name if crop else primary.crop_id, language)
    authority = source.authority if source else primary.source_id

    answer = _t(language, "answer",
                pest=primary.target_pest_common_name, crop=crop_name, authority=authority)

    # --- crop and pest -----------------------------------------------------
    pest_items = [_t(language, "pest_line", pest=primary.target_pest_common_name)]
    if primary.target_pest_scientific_name:
        pest_items.append(_t(language, "scientific_line",
                            name=primary.target_pest_scientific_name))
    if primary.economic_threshold_level:
        pest_items.append(_t(language, "threshold_line",
                            threshold=primary.economic_threshold_level))

    sections = [{"heading": _t(language, "pest_heading"), "items": pest_items}]

    # --- measures ----------------------------------------------------------
    grouped: dict[str, list[str]] = {}
    for record in records:
        for intervention in record.interventions:
            parts = [intervention.description]
            if intervention.active_ingredient_and_formulation:
                parts.append(_t(language, "ingredient_line",
                                value=intervention.active_ingredient_and_formulation))
            if intervention.dosage:
                parts.append(_t(language, "dosage_line", value=intervention.dosage))
                parts.append(_t(language, "dosage_caveat"))
            grouped.setdefault(intervention.control_type, []).append(" ".join(parts))

    labels = CONTROL_TYPE_LABELS[language]
    measure_items: list[str] = []
    for control_type in ("chemical", "biological", "cultural", "mechanical"):
        for text in grouped.get(control_type, []):
            measure_items.append(f"{labels[control_type]}: {text}")
    if measure_items:
        sections.append({"heading": _t(language, "measures_heading"), "items": measure_items})

    # --- safety ------------------------------------------------------------
    safety_items, disclosures, all_published = _safety_section(records, language)
    sections.append({"heading": _t(language, "safety_heading"), "items": safety_items})

    # --- limits ------------------------------------------------------------
    limits = [
        _t(language, "limit_1"),
        _t(language, "limit_2_ok" if all_published else "limit_2"),
        _t(language, "limit_3"),
        _t(language, "educational"),
    ]
    sections.append({"heading": _t(language, "limits_heading"), "items": limits})

    return answer, sections, disclosures, all_published


def quoted_note(language: str) -> str:
    return _t(language, "quoted_note")


# Hindi crop names used only when composing Hindi scaffolding around an English
# crop_name field. Interface vocabulary, not an agronomic claim.
CROP_NAMES_HI = {
    "rice": "धान",
    "wheat": "गेहूँ",
    "maize": "मक्का",
    "cotton": "कपास",
    "tomato": "टमाटर",
}


def crop_display_name(crop_id: str, crop_name: str, language: str) -> str:
    if language == "hi":
        return CROP_NAMES_HI.get(crop_id, crop_name)
    return crop_name


CROP_LEVEL = {
    "en": {
        "answer": "I could not match a specific pest name in your question, so here are all "
                  "{count} records this knowledge base holds for {crop}. Please tell me which "
                  "pest you mean, or read the matching record below.",
        "heading": "Pests covered for this crop",
        "item": "{pest}: {count} measure(s) recorded from {authority}.",
    },
    "hi": {
        "answer": "मैं आपके प्रश्न में कीट का नाम ठीक से नहीं मिला पाया, इसलिए {crop} के लिए इस "
                  "ज्ञान-आधार में दर्ज सभी {count} रिकॉर्ड नीचे दिए गए हैं। कृपया बताएं कि आप "
                  "किस कीट की बात कर रहे हैं।",
        "heading": "इस फसल के लिए दर्ज कीट",
        "item": "{pest}: स्रोत {authority} से दर्ज {count} उपाय।",
    },
}


def build_crop_answer(
    *,
    records: Sequence[ApprovedUse],
    crops: dict[str, Crop],
    sources: dict[str, Source],
    language: str,
) -> tuple[str, list[dict], list[dict], bool]:
    """
    Crop-level answer: every record for the crop, explicitly framed as a list.

    Used when a pest name cannot be matched. It must not pick a "best" record,
    because doing so silently answers a different pest's question.
    """
    table = CROP_LEVEL[language]
    crop = crops.get(records[0].crop_id) if records else None
    crop_id = records[0].crop_id if records else ""
    crop_name = crop_display_name(crop_id, crop.crop_name if crop else crop_id, language)

    answer = table["answer"].format(count=len(records), crop=crop_name)

    items: list[str] = []
    for record in records:
        source = sources.get(record.source_id)
        authority = source.authority if source else record.source_id
        items.append(table["item"].format(
            pest=record.target_pest_common_name,
            count=len(record.interventions),
            authority=authority,
        ))

    sections = [{"heading": table["heading"], "items": items}]

    safety_items, disclosures, all_published = _safety_section(records, language)
    sections.append({"heading": _t(language, "safety_heading"), "items": safety_items})

    limits = [
        _t(language, "limit_1"),
        _t(language, "limit_2_ok" if all_published else "limit_2"),
        _t(language, "limit_3"),
        _t(language, "educational"),
    ]
    sections.append({"heading": _t(language, "limits_heading"), "items": limits})

    return answer, sections, disclosures, all_published
