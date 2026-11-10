/**
 * Interface strings, English and Hindi.
 *
 * Scope: the whole product shell, the advisory workflow, the library and the
 * safety guide are bilingual, because a farmer reads a safety decision in their
 * own language. Record identifiers, source titles and dosages are never
 * translated: they are quoted from the source and translating them would invent
 * vocabulary the source does not use.
 *
 * Nothing here is a safety message. Decision text, refusal text and escalation
 * instructions for a specific answer come from the backend in the answer
 * language, so a translation in this file can never soften a refusal.
 */
export type Lang = 'en' | 'hi'

export const STRINGS = {
  en: {
    'brand.name': 'Krishi Salah',
    'brand.tagline': 'Safe pesticide decisions',

    'nav.home': 'Home',
    'nav.advisory': 'Ask assistant',
    'nav.knowledge': 'Knowledge library',
    'nav.library': 'Library',
    'nav.safety': 'Safety guide',
    'nav.project': 'About this project',
    'nav.skip': 'Skip to content',

    'home.eyebrow': 'Safe pesticide use · decision support',
    'home.title': 'Better crop decisions start with better information.',
    'home.body':
      'Ask about a pest, a crop or a safety rule. You get the answer we can support from published agricultural sources — and a clear next step when we cannot.',
    'home.ctaPrimary': 'Ask about your crop',
    'home.ctaSecondary': 'Explore the safety guide',
    'home.imageCaption': 'Cotton — illustrative photograph',

    'home.composerTitle': 'Ask about your crop',
    'home.composerHint': 'Describe the crop and the problem in your own words.',
    'home.helpTitle': 'What you get',
    'home.help1': 'The source behind every answer',
    'home.help2': 'PHI, REI and protective-equipment status',
    'home.help3': 'A clear refusal when information is missing',
    'home.help4': 'An expert referral when it is needed',

    'trust.source.title': 'Source-backed',
    'trust.source.body':
      'Every answer cites the agricultural authority and the page it was taken from.',
    'trust.rules.title': 'Rules before answers',
    'trust.rules.body': 'Five fixed safety rules run before anything is written.',
    'trust.escalate.title': 'A person when needed',
    'trust.escalate.body':
      'Questions outside the pilot are handed to an expert instead of guessed.',
    'trust.noGuess.title': 'Nothing invented',
    'trust.noGuess.body': 'Missing safety values are shown as missing, never filled in.',

    'home.coverageTitle': 'In this pilot',
    'home.coverageBody':
      'A small, hand-verified set of crops and pest records, transcribed from Indian agricultural sources and checked line by line.',
    'home.stepsTitle': 'How a question is answered',
    'home.step1': 'Write your question',
    'home.step1.body': 'A short description of the crop and the problem is enough.',
    'home.step2': 'We find the record',
    'home.step2.body':
      'The question is matched against the source records and re-ranked by crop and pest.',
    'home.step3': 'The rules decide',
    'home.step3.body':
      'Safety rules decide whether the answer is educational, refused, or needs a person.',
    'home.step4': 'The answer, with sources',
    'home.step4.body': 'You see the decision, the evidence and what to do next.',

    'home.safetyTitle': 'Why nothing here is a dose',
    'home.safetyBody':
      'An actionable recommendation needs a published PHI, REI and PPE profile for the product, plus a CIB&RC registration check. No current record has all four, so every answer stays educational.',
    'home.safetyLink': 'How safety is decided',

    'status.live': 'Live',
    'status.checking': 'Checking services…',
    'status.unreachable': 'Service unreachable',
    'status.records': 'records',
    'status.passages': 'indexed passages',
    'status.pilotCrops': 'pilot crops',
    'status.sources': 'sources',
    'status.retry': 'Check again',

    'advisory.title': 'Ask the assistant',
    'advisory.subtitle':
      'Describe the crop and the problem in English or Hindi. You will get an answer with its sources, or a clear reason why the system will not answer.',
    'advisory.language': 'Answer language',
    'advisory.language.auto': 'Match my question',
    'advisory.language.en': 'English',
    'advisory.language.hi': 'हिंदी',
    'advisory.question': 'Your question',
    'advisory.placeholder':
      'Describe the problem in your crop — e.g. pink bollworm in cotton',
    'advisory.submit': 'Get guidance',
    'advisory.submitting': 'Searching the knowledge base…',
    'advisory.examples': 'Try an example',
    'advisory.example1': 'Cotton: pink bollworm',
    'advisory.example2': 'Rice: stem borer damage',
    'advisory.example3': 'Wheat: aphids on the crop',
    'advisory.example4': 'Maize: fall armyworm',
    'advisory.example5': 'Cotton: how long before harvest?',
    'advisory.empty.title': 'No question yet',
    'advisory.empty.body':
      'Ask about a pest, a crop, or a safety requirement. Answers cite the source page they came from.',
    'advisory.error.title': 'The advisory service did not respond',
    'advisory.error.retry': 'Try again',
    'advisory.error.unavailable':
      'The knowledge base or search service is unavailable. Nothing has been guessed in its place — please retry shortly.',
    'advisory.error.offline':
      'The assistant cannot reach its server right now. Check the connection and try again.',

    'result.decision': 'Decision',
    'result.confidence': 'Confidence',
    'result.answer': 'Answer',
    'result.response': 'Response',
    'result.scope.record': 'Matched to a single pest record',
    'result.scope.crop': 'Crop-level answer — no single record matched',
    'result.why': 'Why this decision',
    'result.gateWhy':
      'The question was stopped before any knowledge-base record was selected, so no safety rule had to run. This is a retrieval-stage decision, not a rule decision.',
    'result.gateReason': 'Gate reason',
    'result.imageCaption': 'Cotton — illustrative photograph',
    'result.missing': 'Missing information',
    'result.missingBody':
      'Without these, nothing in this answer may be treated as an actionable instruction.',
    'result.safety': 'Safety data for this record',
    'result.citations': 'Sources',
    'result.evidence': 'Retrieved passages',
    'result.escalation': 'The answer from the assistant',
    'result.technical': 'Technical details (for evaluation)',
    'result.technicalNote':
      'Machine-readable fields returned by the backend, kept for project evaluation. None of it is needed to act on the answer above.',
    'result.techDecision': 'Decision fields',
    'result.techConfidence': 'Confidence inputs',
    'result.techRules': 'Rule trace',
    'result.techPassages': 'Retrieved passages',
    'result.techCitations': 'Citation metadata',
    'result.techClassification': 'Classifier output',
    'result.techModel': 'Model versions and usage policy',
    'result.published': 'Published in source',
    'result.notPublished': 'Not published in source',
    'result.note': 'Note',
    'result.authority': 'Authority',
    'result.retrieved': 'Retrieved',
    'result.tier': 'Reliability',
    'result.verification': 'Verification',
    'result.digest': 'Document digest',
    'result.openSource': 'Open source',
    'result.chunks': 'passages',
    'result.records': 'records',
    'result.noCitations': 'No citations — this response did not use a record.',
    'result.score': 'Similarity',
    'result.answerLanguage': 'Answer language',
    'result.policy':
      'Educational information only. This is not a pesticide recommendation, not a regulatory approval, and not a substitute for the product label.',
    'result.usagePolicy': 'Usage policy',
    'result.sourceCount': 'sources',
    'result.next.title': 'What to do next',
    'result.next.clarify':
      'Add the crop and the pest or symptom, then ask again. A specific question is easier to match.',
    'result.next.refusal':
      'Do not spray on the basis of this answer. Check the product label, or ask your local agricultural extension officer.',
    'result.next.educational':
      'Treat this as learning material, not a dose. Before spraying anything, confirm the waiting period, re-entry time and protective equipment on the product label.',
    'result.next.escalate':
      'This question is outside the pilot. Take it to your local agricultural extension officer or a licensed agronomist.',
    'result.next.unsupported':
      'The pilot covers rice, wheat, maize, cotton and tomato. Ask about one of these crops for a supported answer.',
    'result.next.registry':
      'Before buying or spraying any product, confirm its CIB&RC registration and read the label.',

    'decision.ACTIONABLE_RECOMMENDATION': 'Verified recommendation',
    'decision.EDUCATIONAL_INFORMATION': 'Educational information only',
    'decision.SAFETY_REFUSAL': 'Cannot provide a safe recommendation',
    'decision.REGULATORY_VERIFICATION_REQUIRED': 'Product approval needs verification',
    'decision.ESCALATION_REQUIRED': 'Consult an agricultural expert',
    'decision.CLARIFICATION_REQUIRED': 'More information needed',
    'decision.unknown': 'Unclassified response',

    'decision.ACTIONABLE_RECOMMENDATION.desc':
      'Every safety value for this record is published and a registration check is recorded.',
    'decision.EDUCATIONAL_INFORMATION.desc':
      'Shown for learning. At least one safety value is not published, so this is not a dose you should act on.',
    'decision.SAFETY_REFUSAL.desc':
      'The answer needs a value the system cannot supply safely, so it declined.',
    'decision.REGULATORY_VERIFICATION_REQUIRED.desc':
      'Advice copied from a source is not a CIB&RC registration. Check the product label first.',
    'decision.ESCALATION_REQUIRED.desc':
      'No record covers this question, so it goes to a person instead of a guess.',
    'decision.CLARIFICATION_REQUIRED.desc':
      'The question was not clear enough to look up.',

    'field.phi': 'Pre-harvest interval (PHI)',
    'field.rei': 'Re-entry interval (REI)',
    'field.ppe': 'Protective equipment (PPE)',
    'field.dosage': 'Dosage',
    'field.regulatory_approval': 'Regulatory approval',
    'field.source_verification': 'Source verification',

    'kb.title': 'Knowledge library',
    'kb.subtitle':
      'Every record the assistant can use, with the source it came from and its safety status.',
    'kb.searchPlaceholder': 'Search crop, pest or ingredient',
    'kb.searchLabel': 'Search records',
    'kb.allCrops': 'All crops',
    'kb.records': 'records',
    'kb.noResults': 'No record matches that search.',
    'kb.noResultsBody': 'Try a crop name, a pest, or part of an ingredient name.',
    'kb.clear': 'Clear search',
    'kb.loading': 'Loading records…',
    'kb.error': 'Could not load the library',
    'kb.retry': 'Try again',
    'kb.verificationTitle': 'Source-checked, not regulator-approved',
    'kb.verificationBody':
      'Each record was checked against the exact text of its cited source — a state agricultural university or a national IPM package. None has been cross-checked against the live CIB&RC registration database, so none is a confirmed regulatory approval.',
    'kb.interventions': 'What the source recommends',
    'kb.safety': 'Safety data',
    'kb.source': 'Source',
    'kb.educational': 'Learning only',
    'kb.actionable': 'Actionable, with evidence',
    'kb.etl': 'Economic threshold',
    'kb.details': 'Record details',
    'kb.verifiedBy': 'Verified by',
    'kb.datasetNote':
      'Pilot dataset: 9 records across 5 crops, from 8 authoritative Indian sources. A hand-verified pilot set, not a product-registration database.',

    'safety.title': 'How safety is decided',
    'safety.subtitle':
      'Five deterministic rules run before any answer is written. No question, confidence score or language choice can override them.',
    'safety.termsTitle': 'Five things that decide safe use',
    'safety.phi.title': 'Pre-harvest interval (PHI)',
    'safety.phi.body':
      'The waiting period between spraying and harvesting. Food is only safe to take if this period has passed.',
    'safety.rei.title': 'Re-entry interval (REI)',
    'safety.rei.body':
      'The waiting period before anyone goes back into a treated field, usually without protective equipment.',
    'safety.ppe.title': 'Protective equipment (PPE)',
    'safety.ppe.body':
      'What the person spraying must wear: gloves, mask, long sleeves, boots — as the label states.',
    'safety.label.title': 'The product label',
    'safety.label.body':
      'The label is the legal instruction for that product. If a label and this app disagree, the label wins.',
    'safety.registry.title': 'Regulatory approval (CIB&RC)',
    'safety.registry.body':
      'A product must be registered with the Central Insecticides Board & Registration Committee for that crop and pest. Source-checked advice is not the same thing.',
    'safety.gateTitle': 'Why missing data stops a recommendation',
    'safety.gateBody':
      'A dose is only safe together with its PHI, REI and PPE. If any of them is unpublished, the system will not combine a dose with a guess — it keeps the answer educational and says what is missing.',
    'safety.rulesTitle': 'Rule registry',
    'safety.precedenceTitle': 'Blocking precedence',
    'safety.precedenceBody':
      'Several rules can fire at once. Exactly one reason is shown, chosen in this order, so the same question always gets the same explanation.',
    'safety.thresholdsTitle': 'Thresholds in force',
    'safety.involvement': 'generation involvement',
    'safety.headline': 'records are actionable',
    'safety.backendReason': 'Reason, as reported by the backend',
    'safety.loading': 'Loading rule registry…',
    'safety.error': 'Could not load the rule engine status',
    'safety.severity.block': 'Refuses the answer',
    'safety.severity.restrict': 'Educational information only',
    'safety.severity.warn': 'Important caution',

    'about.eyebrow': 'About',
    'about.title': 'About Krishi Salah',
    'about.subtitle': 'A source-backed assistant for safer pesticide decisions.',
    'about.whatTitle': 'What Krishi Salah does',
    'about.whatBody':
      'Krishi Salah answers questions about a pest, a crop or a pesticide safety rule. Every answer is assembled from published Indian agricultural sources and checked against fixed safety rules before it is shown. When the information a safe answer depends on is missing, the assistant says what is missing instead of guessing.',
    'about.coverageTitle': 'What it covers today',
    'about.coverageBody':
      'A small pilot set of crops, transcribed from published state and national agricultural sources and checked line by line. This is not a product catalogue.',
    'about.cropsLabel': 'Crops in the pilot',
    'about.languageTitle': 'Languages',
    'about.languageBody':
      'The interface and the safety explanations are written in English and Hindi, and a question can be asked in either. Retrieval compares words rather than meaning, so a Hindi question is matched against the English source text: common phrasings work, unusual ones can be missed.',
    'about.processTitle': 'How an answer is built',
    'about.showTitle': 'What every answer shows',
    'about.showBody':
      'The source it came from, the status of the pre-harvest interval, re-entry interval and protective equipment, and a clear next step — including when the assistant cannot answer.',
    'about.limitsTitle': 'Limits of this pilot',
    'about.limit1':
      'No record in the pilot publishes a pre-harvest interval, a re-entry interval and a protective-equipment requirement together, so every chemical answer stays educational rather than actionable.',
    'about.limit2':
      'No product has been checked against the CIB&RC pesticide registration database, and the assistant never queries it.',
    'about.limit3':
      'The knowledge base holds a handful of records. Questions about other crops or pests are passed to an agricultural expert instead of answered.',
    'about.limit4':
      'It does not replace the product label, a registration check, or advice from a licensed agronomist.',
    'about.titleLine':
      'Academic pilot · Safe Pesticide Use Knowledge and Advisory Assistant for Decision Support',

    'eval.title': 'Evaluation details',
    'eval.subtitle':
      'Technical diagnostics for project evaluation. Nothing on this page changes what the assistant decides.',
    'eval.note':
      'Values are reported exactly as the services return them. No credentials, keys or connection strings are shown.',
    'eval.loading': 'Loading diagnostics…',
    'eval.error': 'Could not load diagnostics',
    'eval.retrieval': 'Retrieval index',
    'eval.rules': 'Safety rule engine',
    'eval.classifier': 'Question classifier',
    'eval.kb': 'Knowledge base',
    'eval.academic': 'Project record',
    'eval.records': 'Records',
    'eval.indexedPassages': 'Indexed passages',
    'eval.actionable': 'Actionable records',
    'eval.reason': 'Reason reported by the engine',
    'eval.unavailable': 'Not reported',

    'footer.disclaimer':
      'Educational pilot. Not a pesticide recommendation, not a regulatory approval. Always read the product label and confirm with your local agricultural extension officer.',
    'footer.safetyLink': 'Safety guide',
    'footer.libraryLink': 'Knowledge library',
    // Submission metadata (student, section, course, project type) appears
    // nowhere in the product, on /evaluation or off it. The footer carries the
    // technical project title only.
    'footer.built': 'Safe Pesticide Use Knowledge and Advisory Assistant',
    'footer.evaluation': 'Evaluation details',
  },
  hi: {
    'brand.name': 'कृषि सलाह',
    'brand.tagline': 'कीटनाशक के सुरक्षित उपयोग के निर्णय',

    'nav.home': 'होम',
    'nav.advisory': 'सलाह पूछें',
    'nav.knowledge': 'ज्ञान पुस्तकालय',
    'nav.library': 'पुस्तकालय',
    'nav.safety': 'सुरक्षा',
    'nav.project': 'परियोजना के बारे में',
    'nav.skip': 'मुख्य सामग्री पर जाएँ',

    'home.eyebrow': 'कीटनाशक का सुरक्षित उपयोग · निर्णय सहायता',
    'home.title': 'बेहतर फसल निर्णय बेहतर जानकारी से शुरू होते हैं।',
    'home.body':
      'कीट, फसल या सुरक्षा नियम के बारे में पूछें। उत्तर केवल प्रकाशित कृषि स्रोतों से दिया जाता है — और जब उत्तर संभव न हो, तो अगला सही कदम बताया जाता है।',
    'home.ctaPrimary': 'अपनी फसल के बारे में पूछें',
    'home.ctaSecondary': 'सुरक्षा मार्गदर्शन देखें',
    'home.imageCaption': 'कपास — उदाहरण चित्र',

    'home.composerTitle': 'अपनी फसल के बारे में पूछें',
    'home.composerHint': 'फसल और समस्या अपने शब्दों में लिखें।',
    'home.helpTitle': 'आपको क्या मिलेगा',
    'home.help1': 'हर उत्तर के पीछे का स्रोत',
    'home.help2': 'PHI, REI और सुरक्षा उपकरण की स्थिति',
    'home.help3': 'जानकारी न होने पर स्पष्ट मना',
    'home.help4': 'ज़रूरत पड़ने पर विशेषज्ञ के पास भेजना',

    'trust.source.title': 'स्रोत से प्रमाणित',
    'trust.source.body':
      'हर उत्तर उस कृषि संस्था और पृष्ठ का हवाला देता है जहाँ से वह लिया गया है।',
    'trust.rules.title': 'उत्तर से पहले नियम',
    'trust.rules.body': 'कुछ भी लिखे जाने से पहले पाँच तय सुरक्षा नियम चलते हैं।',
    'trust.escalate.title': 'ज़रूरत पर व्यक्ति',
    'trust.escalate.body':
      'पायलट से बाहर के प्रश्न अनुमान लगाने के बजाय विशेषज्ञ को भेजे जाते हैं।',
    'trust.noGuess.title': 'कुछ भी बनाया नहीं जाता',
    'trust.noGuess.body': 'अनुपलब्ध सुरक्षा मान अनुपलब्ध ही दिखते हैं, भरे नहीं जाते।',

    'home.coverageTitle': 'इस पायलट में',
    'home.coverageBody':
      'फसलों और कीट रिकॉर्ड का छोटा, हाथ से जाँचा गया समूह — भारतीय कृषि स्रोतों से शब्दशः लिया गया।',
    'home.stepsTitle': 'प्रश्न का उत्तर कैसे बनता है',
    'home.step1': 'अपना प्रश्न लिखें',
    'home.step1.body': 'फसल और समस्या का छोटा विवरण पर्याप्त है।',
    'home.step2': 'हम रिकॉर्ड खोजते हैं',
    'home.step2.body':
      'प्रश्न को स्रोत रिकॉर्ड से मिलाया जाता है और फसल तथा कीट के नाम से क्रमित किया जाता है।',
    'home.step3': 'नियम निर्णय करते हैं',
    'home.step3.body':
      'सुरक्षा नियम तय करते हैं कि उत्तर शैक्षिक होगा, अस्वीकार होगा, या किसी व्यक्ति की ज़रूरत है।',
    'home.step4': 'स्रोतों के साथ उत्तर',
    'home.step4.body': 'आपको निर्णय, प्रमाण और अगला कदम दिखाई देता है।',

    'home.safetyTitle': 'यहाँ कोई मात्रा क्यों नहीं दी जाती',
    'home.safetyBody':
      'क्रियान्वयन योग्य सिफ़ारिश के लिए उत्पाद का PHI, REI और PPE प्रकाशित होना चाहिए, साथ में CIB&RC पंजीकरण की जाँच। वर्तमान में किसी रिकॉर्ड में ये चारों नहीं हैं, इसलिए हर उत्तर शैक्षिक ही रहता है।',
    'home.safetyLink': 'सुरक्षा का निर्णय कैसे होता है',

    'status.live': 'लाइव',
    'status.checking': 'सेवाएँ जाँची जा रही हैं…',
    'status.unreachable': 'सेवा उपलब्ध नहीं',
    'status.records': 'रिकॉर्ड',
    'status.passages': 'अनुक्रमित अंश',
    'status.pilotCrops': 'पायलट फसलें',
    'status.sources': 'स्रोत',
    'status.retry': 'फिर जाँचें',

    'advisory.title': 'सहायक से पूछें',
    'advisory.subtitle':
      'फसल और समस्या अंग्रेज़ी या हिंदी में लिखें। आपको स्रोतों के साथ उत्तर मिलेगा, या स्पष्ट कारण कि प्रणाली उत्तर क्यों नहीं दे रही।',
    'advisory.language': 'उत्तर की भाषा',
    'advisory.language.auto': 'मेरे प्रश्न जैसी',
    'advisory.language.en': 'English',
    'advisory.language.hi': 'हिंदी',
    'advisory.question': 'आपका प्रश्न',
    'advisory.placeholder':
      'अपनी फसल की समस्या लिखें — जैसे कपास में गुलाबी सुंडी',
    'advisory.submit': 'सलाह लें',
    'advisory.submitting': 'ज्ञान-आधार में खोजा जा रहा है…',
    'advisory.examples': 'एक उदाहरण आज़माएँ',
    'advisory.example1': 'कपास: गुलाबी सुंडी',
    'advisory.example2': 'धान: तना छेदक',
    'advisory.example3': 'गेहूँ: माहू (एफिड)',
    'advisory.example4': 'मक्का: फॉल आर्मीवर्म',
    'advisory.example5': 'कपास: कटाई से पहले कितना समय?',
    'advisory.empty.title': 'अभी कोई प्रश्न नहीं',
    'advisory.empty.body':
      'कीट, फसल या सुरक्षा आवश्यकता के बारे में पूछें। उत्तर के साथ उसका स्रोत पृष्ठ दिखाया जाता है।',
    'advisory.error.title': 'सलाह सेवा ने उत्तर नहीं दिया',
    'advisory.error.retry': 'फिर से कोशिश करें',
    'advisory.error.unavailable':
      'ज्ञान-आधार या खोज सेवा उपलब्ध नहीं है। इसकी जगह कोई अनुमान नहीं लगाया गया — कृपया थोड़ी देर बाद पुनः प्रयास करें।',
    'advisory.error.offline':
      'सहायक अभी अपने सर्वर तक नहीं पहुँच रहा। कनेक्शन जाँचें और फिर कोशिश करें।',

    'result.decision': 'निर्णय',
    'result.confidence': 'विश्वास',
    'result.answer': 'उत्तर',
    'result.response': 'प्रतिक्रिया',
    'result.scope.record': 'एक कीट रिकॉर्ड से मिलान',
    'result.scope.crop': 'फसल-स्तरीय उत्तर — कोई एकल रिकॉर्ड नहीं मिला',
    'result.why': 'यह निर्णय क्यों',
    'result.gateWhy':
      'प्रश्न को ज्ञान-आधार का कोई रिकॉर्ड चुनने से पहले ही रोक दिया गया, इसलिए कोई सुरक्षा नियम चलाने की आवश्यकता नहीं पड़ी। यह खोज-चरण का निर्णय है, नियम का निर्णय नहीं।',
    'result.gateReason': 'रोक का कारण',
    'result.imageCaption': 'कपास — उदाहरण चित्र',
    'result.missing': 'अनुपलब्ध जानकारी',
    'result.missingBody':
      'इनके बिना इस उत्तर की कोई भी बात क्रियान्वयन योग्य निर्देश नहीं मानी जाती।',
    'result.safety': 'इस रिकॉर्ड का सुरक्षा विवरण',
    'result.citations': 'स्रोत',
    'result.evidence': 'प्राप्त अंश',
    'result.escalation': 'सहायक का उत्तर',
    'result.technical': 'तकनीकी विवरण (मूल्यांकन के लिए)',
    'result.technicalNote':
      'बैकएंड से मिले मशीन-पठनीय मान, परियोजना मूल्यांकन के लिए रखे गए हैं। ऊपर दिए उत्तर पर काम करने के लिए इनमें से कुछ भी ज़रूरी नहीं है।',
    'result.techDecision': 'निर्णय के मान',
    'result.techConfidence': 'विश्वास के इनपुट',
    'result.techRules': 'नियम लॉग',
    'result.techPassages': 'प्राप्त अंश',
    'result.techCitations': 'स्रोत का मेटाडेटा',
    'result.techClassification': 'वर्गीकरण मॉडल का आउटपुट',
    'result.techModel': 'मॉडल संस्करण और उपयोग नीति',
    'result.published': 'स्रोत में प्रकाशित',
    'result.notPublished': 'स्रोत में प्रकाशित नहीं',
    'result.note': 'टिप्पणी',
    'result.authority': 'प्राधिकरण',
    'result.retrieved': 'प्राप्ति',
    'result.tier': 'विश्वसनीयता',
    'result.verification': 'सत्यापन',
    'result.digest': 'दस्तावेज़ डाइजेस्ट',
    'result.openSource': 'स्रोत खोलें',
    'result.chunks': 'अंश',
    'result.records': 'रिकॉर्ड',
    'result.noCitations': 'कोई स्रोत नहीं — इस उत्तर में किसी रिकॉर्ड का उपयोग नहीं हुआ।',
    'result.score': 'समानता',
    'result.answerLanguage': 'उत्तर की भाषा',
    'result.policy':
      'केवल शैक्षिक जानकारी। यह कीटनाशक सिफ़ारिश नहीं, नियामक अनुमोदन नहीं, और उत्पाद लेबल का विकल्प नहीं है।',
    'result.usagePolicy': 'उपयोग नीति',
    'result.sourceCount': 'स्रोत',
    'result.next.title': 'आगे क्या करें',
    'result.next.clarify':
      'फसल और कीट या लक्षण जोड़कर फिर पूछें। स्पष्ट प्रश्न का मिलान आसान होता है।',
    'result.next.refusal':
      'इस उत्तर के आधार पर छिड़काव न करें। उत्पाद लेबल देखें, या अपने स्थानीय कृषि विस्तार अधिकारी से पूछें।',
    'result.next.educational':
      'इसे सीखने की सामग्री मानें, मात्रा नहीं। कुछ भी छिड़कने से पहले उत्पाद लेबल पर प्रतीक्षा अवधि, खेत में लौटने का समय और सुरक्षा उपकरण जाँच लें।',
    'result.next.escalate':
      'यह प्रश्न पायलट के बाहर है। इसे अपने स्थानीय कृषि विस्तार अधिकारी या लाइसेंस प्राप्त कृषि विशेषज्ञ के पास ले जाएँ।',
    'result.next.unsupported':
      'पायलट में धान, गेहूँ, मक्का, कपास और टमाटर शामिल हैं। समर्थित उत्तर के लिए इन्हीं फसलों में से पूछें।',
    'result.next.registry':
      'कोई भी उत्पाद खरीदने या छिड़कने से पहले उसका CIB&RC पंजीकरण जाँचें और लेबल पढ़ें।',

    'decision.ACTIONABLE_RECOMMENDATION': 'सत्यापित सिफ़ारिश',
    'decision.EDUCATIONAL_INFORMATION': 'केवल शैक्षिक जानकारी',
    'decision.SAFETY_REFUSAL': 'सुरक्षित सिफ़ारिश संभव नहीं',
    'decision.REGULATORY_VERIFICATION_REQUIRED': 'उत्पाद अनुमोदन की पुष्टि आवश्यक',
    'decision.ESCALATION_REQUIRED': 'कृषि विशेषज्ञ से सलाह लें',
    'decision.CLARIFICATION_REQUIRED': 'अधिक जानकारी चाहिए',
    'decision.unknown': 'अवर्गीकृत उत्तर',

    'decision.ACTIONABLE_RECOMMENDATION.desc':
      'इस रिकॉर्ड के सभी सुरक्षा मान प्रकाशित हैं और पंजीकरण जाँच दर्ज है।',
    'decision.EDUCATIONAL_INFORMATION.desc':
      'सीखने के लिए दिखाया गया। कम से कम एक सुरक्षा मान प्रकाशित नहीं है, इसलिए इसे मात्रा के रूप में न लें।',
    'decision.SAFETY_REFUSAL.desc':
      'उत्तर के लिए ऐसा मान चाहिए जो प्रणाली सुरक्षित रूप से नहीं दे सकती, इसलिए मना किया गया।',
    'decision.REGULATORY_VERIFICATION_REQUIRED.desc':
      'स्रोत से ली गई सलाह CIB&RC पंजीकरण नहीं है। पहले उत्पाद लेबल जाँचें।',
    'decision.ESCALATION_REQUIRED.desc':
      'इस प्रश्न के लिए कोई रिकॉर्ड नहीं है, इसलिए अनुमान के बजाय किसी व्यक्ति के पास भेजा गया।',
    'decision.CLARIFICATION_REQUIRED.desc': 'प्रश्न इतना स्पष्ट नहीं था कि उसे खोजा जा सके।',

    'field.phi': 'कटाई से पहले की अवधि (PHI)',
    'field.rei': 'पुनः-प्रवेश अवधि (REI)',
    'field.ppe': 'सुरक्षा उपकरण (PPE)',
    'field.dosage': 'मात्रा',
    'field.regulatory_approval': 'नियामक अनुमोदन',
    'field.source_verification': 'स्रोत सत्यापन',

    'kb.title': 'ज्ञान पुस्तकालय',
    'kb.subtitle':
      'सहायक जिन रिकॉर्डों का उपयोग कर सकता है, उनका स्रोत और सुरक्षा स्थिति।',
    'kb.searchPlaceholder': 'फसल, कीट या घटक खोजें',
    'kb.searchLabel': 'रिकॉर्ड खोजें',
    'kb.allCrops': 'सभी फसलें',
    'kb.records': 'रिकॉर्ड',
    'kb.noResults': 'इस खोज से कोई रिकॉर्ड नहीं मिला।',
    'kb.noResultsBody': 'फसल का नाम, कीट, या घटक के नाम का कोई हिस्सा आज़माएँ।',
    'kb.clear': 'खोज हटाएँ',
    'kb.loading': 'रिकॉर्ड लोड हो रहे हैं…',
    'kb.error': 'पुस्तकालय लोड नहीं हो सका',
    'kb.retry': 'फिर कोशिश करें',
    'kb.verificationTitle': 'स्रोत से जाँचा, नियामक से स्वीकृत नहीं',
    'kb.verificationBody':
      'हर रिकॉर्ड अपने उद्धृत स्रोत के ठीक उसी पाठ से जाँचा गया है — किसी राज्य कृषि विश्वविद्यालय या राष्ट्रीय IPM पैकेज से। किसी को भी CIB&RC के जीवित पंजीकरण डेटाबेस से नहीं मिलाया गया, इसलिए कोई भी पुष्ट नियामक अनुमोदन नहीं है।',
    'kb.interventions': 'स्रोत क्या बताता है',
    'kb.safety': 'सुरक्षा जानकारी',
    'kb.source': 'स्रोत',
    'kb.educational': 'केवल शिक्षा',
    'kb.actionable': 'प्रमाण के साथ क्रियान्वयन योग्य',
    'kb.etl': 'आर्थिक सीमा',
    'kb.details': 'रिकॉर्ड का विवरण',
    'kb.verifiedBy': 'सत्यापित करने वाला',
    'kb.datasetNote':
      'पायलट डेटा: 5 फसलों के 9 रिकॉर्ड, 8 प्रामाणिक भारतीय स्रोतों से। यह हाथ से सत्यापित पायलट सेट है, उत्पाद-पंजीकरण डेटाबेस नहीं।',

    'safety.title': 'सुरक्षा का निर्णय कैसे होता है',
    'safety.subtitle':
      'कोई भी उत्तर लिखे जाने से पहले पाँच निश्चित नियम चलते हैं। इन्हें प्रश्न, विश्वास-स्तर या भाषा के चयन से बदला नहीं जा सकता।',
    'safety.termsTitle': 'सुरक्षित उपयोग तय करने वाली पाँच बातें',
    'safety.phi.title': 'कटाई से पहले की अवधि (PHI)',
    'safety.phi.body':
      'छिड़काव और कटाई के बीच की प्रतीक्षा अवधि। इस अवधि के बाद ही फसल खाने योग्य मानी जाती है।',
    'safety.rei.title': 'पुनः-प्रवेश अवधि (REI)',
    'safety.rei.body':
      'छिड़काव के बाद खेत में लौटने से पहले की प्रतीक्षा अवधि, आमतौर पर बिना सुरक्षा उपकरण के।',
    'safety.ppe.title': 'सुरक्षा उपकरण (PPE)',
    'safety.ppe.body':
      'छिड़काव करने वाले को क्या पहनना चाहिए: दस्ताने, मास्क, पूरी आस्तीन, जूते — जैसा लेबल कहता है।',
    'safety.label.title': 'उत्पाद का लेबल',
    'safety.label.body':
      'लेबल उस उत्पाद का कानूनी निर्देश है। यदि लेबल और यह ऐप अलग कहें, तो लेबल मान्य है।',
    'safety.registry.title': 'नियामक अनुमोदन (CIB&RC)',
    'safety.registry.body':
      'किसी उत्पाद का उस फसल और कीट के लिए केंद्रीय कीटनाशक बोर्ड एवं पंजीकरण समिति में पंजीकृत होना आवश्यक है। स्रोत से जाँची सलाह इसके बराबर नहीं है।',
    'safety.gateTitle': 'जानकारी न हो तो सिफ़ारिश क्यों रुकती है',
    'safety.gateBody':
      'मात्रा तभी सुरक्षित है जब उसका PHI, REI और PPE साथ हों। इनमें से कोई प्रकाशित न हो तो प्रणाली मात्रा के साथ अनुमान नहीं जोड़ती — उत्तर शैक्षिक रहता है और बताता है कि क्या अनुपलब्ध है।',
    'safety.rulesTitle': 'नियम सूची',
    'safety.precedenceTitle': 'रोकने का क्रम',
    'safety.precedenceBody':
      'एक साथ कई नियम लागू हो सकते हैं। इसी क्रम में चुनकर केवल एक कारण दिखाया जाता है, ताकि एक ही प्रश्न पर हमेशा एक ही स्पष्टीकरण मिले।',
    'safety.thresholdsTitle': 'लागू सीमाएँ',
    'safety.involvement': 'निर्माण में भूमिका',
    'safety.headline': 'रिकॉर्ड क्रियान्वयन योग्य हैं',
    'safety.backendReason': 'कारण, जैसा बैकएंड ने बताया',
    'safety.loading': 'नियम सूची लोड हो रही है…',
    'safety.error': 'नियम इंजन की स्थिति लोड नहीं हो सकी',
    'safety.severity.block': 'उत्तर रोकता है',
    'safety.severity.restrict': 'केवल शैक्षिक जानकारी',
    'safety.severity.warn': 'महत्वपूर्ण सावधानी',

    'about.eyebrow': 'परिचय',
    'about.title': 'कृषि सलाह के बारे में',
    'about.subtitle': 'कीटनाशक के सुरक्षित उपयोग के लिए स्रोत-आधारित सहायक।',
    'about.whatTitle': 'कृषि सलाह क्या करती है',
    'about.whatBody':
      'कृषि सलाह कीट, फसल या कीटनाशक सुरक्षा नियम से जुड़े प्रश्नों का उत्तर देती है। हर उत्तर प्रकाशित भारतीय कृषि स्रोतों से बनाया जाता है और दिखाने से पहले तय सुरक्षा नियमों से जाँचा जाता है। जब सुरक्षित उत्तर के लिए ज़रूरी जानकारी नहीं होती, तो सहायक अनुमान लगाने के बजाय बताता है कि क्या कम है।',
    'about.coverageTitle': 'अभी क्या शामिल है',
    'about.coverageBody':
      'फसलों का एक छोटा पायलट समूह — राज्य और राष्ट्रीय कृषि स्रोतों से शब्दशः लिया गया और पंक्ति-दर-पंक्ति जाँचा गया। यह उत्पादों की सूची नहीं है।',
    'about.cropsLabel': 'पायलट की फसलें',
    'about.languageTitle': 'भाषाएँ',
    'about.languageBody':
      'इंटरफ़ेस और सुरक्षा की जानकारी अंग्रेज़ी और हिंदी में है, और प्रश्न किसी भी भाषा में पूछा जा सकता है। खोज शब्दों की तुलना करती है, अर्थ की नहीं, इसलिए हिंदी प्रश्न अंग्रेज़ी स्रोत पाठ से मिलाया जाता है: सामान्य वाक्य चल जाते हैं, असामान्य छूट सकते हैं।',
    'about.processTitle': 'उत्तर कैसे बनता है',
    'about.showTitle': 'हर उत्तर में क्या दिखता है',
    'about.showBody':
      'स्रोत का नाम, PHI, REI और सुरक्षा उपकरण की स्थिति, और अगला स्पष्ट कदम — यह भी कि सहायक उत्तर क्यों नहीं दे सका।',
    'about.limitsTitle': 'इस पायलट की सीमाएँ',
    'about.limit1':
      'पायलट के किसी रिकॉर्ड में एक साथ PHI, REI और सुरक्षा उपकरण प्रकाशित नहीं हैं, इसलिए हर रासायनिक उत्तर शैक्षिक रहता है, क्रियान्वयन योग्य नहीं।',
    'about.limit2':
      'किसी उत्पाद की CIB&RC कीटनाशक पंजीकरण सूची से जाँच नहीं हुई है, और सहायक उसे कभी नहीं पूछता।',
    'about.limit3':
      'ज्ञान आधार में गिने-चुने रिकॉर्ड हैं। दूसरी फसलों या कीटों के प्रश्न उत्तर देने के बजाय कृषि विशेषज्ञ के पास भेजे जाते हैं।',
    'about.limit4':
      'यह उत्पाद लेबल, पंजीकरण जाँच या लाइसेंस प्राप्त कृषि विशेषज्ञ की सलाह का विकल्प नहीं है।',
    'about.titleLine':
      'शैक्षिक पायलट · कीटनाशक सुरक्षित उपयोग ज्ञान और सलाह सहायक (निर्णय समर्थन)',

    'eval.title': 'मूल्यांकन विवरण',
    'eval.subtitle':
      'परियोजना मूल्यांकन के लिए तकनीकी जानकारी। यह पृष्ठ सहायक के किसी निर्णय को नहीं बदलता।',
    'eval.note':
      'सभी मान सेवाओं से जैसे मिलते हैं वैसे ही दिखाए गए हैं। कोई क्रेडेंशियल, कुंजी या कनेक्शन स्ट्रिंग नहीं दिखाई जाती।',
    'eval.loading': 'जानकारी लोड हो रही है…',
    'eval.error': 'तकनीकी जानकारी लोड नहीं हो सकी',
    'eval.retrieval': 'खोज सूचकांक',
    'eval.rules': 'सुरक्षा नियम इंजन',
    'eval.classifier': 'प्रश्न वर्गीकरण मॉडल',
    'eval.kb': 'ज्ञान आधार',
    'eval.academic': 'परियोजना विवरण',
    'eval.records': 'रिकॉर्ड',
    'eval.indexedPassages': 'अनुक्रमित अंश',
    'eval.actionable': 'क्रियान्वयन योग्य रिकॉर्ड',
    'eval.reason': 'इंजन द्वारा बताया गया कारण',
    'eval.unavailable': 'उपलब्ध नहीं',

    'footer.disclaimer':
      'शैक्षिक पायलट। यह कीटनाशक सिफ़ारिश नहीं, नियामक अनुमोदन नहीं। हमेशा उत्पाद लेबल पढ़ें और अपने स्थानीय कृषि विस्तार अधिकारी से पुष्टि करें।',
    'footer.safetyLink': 'सुरक्षा मार्गदर्शन',
    'footer.libraryLink': 'ज्ञान पुस्तकालय',
    'footer.built': 'कीटनाशक सुरक्षित उपयोग ज्ञान और सलाह सहायक',
    'footer.evaluation': 'मूल्यांकन विवरण',
  },
} as const

export type StringKey = keyof typeof STRINGS.en










