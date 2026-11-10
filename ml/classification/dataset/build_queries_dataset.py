"""
Build the Phase 4 labeled query dataset (Module B training data).

This script is the *authoring tool* for `queries.csv`. It exists so the exact
label assignment for every example is readable, diffable and reviewable in one
place; the generated `queries.csv` is the authoritative dataset the training
and evaluation scripts consume.

IMPORTANT — dataset honesty rules (see LABELING_GUIDE.md):
1. These are *user queries*, i.e. text a farmer or advisor might type. No row
   asserts a pesticide dosage, PHI, REI, PPE requirement or registration status
   as a fact. Product names appear only as the subject of a question ("what is
   the dose of X"), never as a stated recommendation. Therefore this training
   data cannot leak an invented pesticide fact into the system.
2. Every row was written by hand for this project. No row is copied from the
   Phase 3 knowledge base, so classification training data cannot leak into the
   retrieval corpus and vice versa.
3. Hindi rows use Devanagari script. `hi-latn` rows are romanised Hindi
   (Hinglish), which is how many users actually type on mobile keyboards.
4. Rows whose `notes` start with "ambiguous" are deliberately under-specified.
   They exist so the model can be tested for *low-confidence, request
   clarification* behaviour rather than forced into a confident label.

Run:  python ml/classification/dataset/build_queries_dataset.py
"""
from __future__ import annotations

import csv
from pathlib import Path

HEADER = ["id", "text", "language", "crop", "task", "safety_topic", "notes"]

# (text, language, crop, task, safety_topic, notes)
ROWS: list[tuple[str, str, str, str, str, str]] = [
    # ------------------------------------------------------------------ RICE
    ("My paddy field has yellowing leaves in patches, what is causing this?", "en", "rice", "disease_management", "no_safety_topic", ""),
    ("How do I identify yellow stem borer damage in rice?", "en", "rice", "pest_identification", "no_safety_topic", ""),
    ("Dead heart and white ear symptoms in paddy, which pest is it?", "en", "rice", "pest_identification", "no_safety_topic", ""),
    ("What is the economic threshold level for yellow stem borer in rice?", "en", "rice", "pest_management", "no_safety_topic", ""),
    ("Recommend a spray schedule for rice leaf folder", "en", "rice", "pest_management", "no_safety_topic", ""),
    ("How much chlorantraniliprole should I use per acre in paddy?", "en", "rice", "product_information", "dosage", ""),
    ("What is the dose of fipronil for rice stem borer", "en", "rice", "product_information", "dosage", ""),
    ("After spraying insecticide in paddy, how many days before harvest is it safe?", "en", "rice", "general_guidance", "phi", ""),
    ("Pre harvest interval for chlorpyrifos in rice", "en", "rice", "product_information", "phi", ""),
    ("How soon can I enter the paddy field after spraying?", "en", "rice", "general_guidance", "rei", ""),
    ("Re-entry interval after insecticide spray in rice field", "en", "rice", "general_guidance", "rei", ""),
    ("What protective clothing should I wear while spraying rice pesticides?", "en", "rice", "general_guidance", "ppe", ""),
    ("Is cartap hydrochloride poisonous to humans?", "en", "no_crop", "product_information", "toxicity", ""),
    ("Is monocrotophos still allowed on paddy in India?", "en", "rice", "product_information", "regulatory_approval", ""),
    ("Is chlorantraniliprole registered for rice in India?", "en", "rice", "product_information", "regulatory_approval", ""),
    ("Safe handling of pesticide bottles in rice cultivation", "en", "rice", "general_guidance", "general_safety", ""),
    ("What is the mandi price of rice today?", "en", "rice", "out_of_scope", "no_safety_topic", ""),
    ("धान में पीली पत्तियां हो रही हैं, क्या कारण है", "hi", "rice", "disease_management", "no_safety_topic", ""),
    ("धान के तने में कीड़ा लगा है, कौन सा कीट है", "hi", "rice", "pest_identification", "no_safety_topic", ""),
    ("धान में तना छेदक के लिए कौन सा कीटनाशक डालें", "hi", "rice", "pest_management", "no_safety_topic", ""),
    ("धान में कीटनाशक की मात्रा प्रति एकड़ कितनी होनी चाहिए", "hi", "rice", "product_information", "dosage", ""),
    ("धान में छिड़काव के बाद कटाई से कितने दिन पहले रुकना चाहिए", "hi", "rice", "general_guidance", "phi", ""),
    ("धान में दवा छिड़कने के बाद खेत में कब जा सकते हैं", "hi", "rice", "general_guidance", "rei", ""),
    ("धान में छिड़काव करते समय कौन से सुरक्षा कपड़े पहनें", "hi", "rice", "general_guidance", "ppe", ""),
    ("dhan me keede lag gaye hain, kya spray karun", "hi-latn", "rice", "pest_management", "no_safety_topic", ""),
    ("dhan me dawa ki matra kitni hai", "hi-latn", "rice", "product_information", "dosage", ""),
    ("paddy me spray ke baad kitne din baad khet me jana chahiye", "hi-latn", "rice", "general_guidance", "rei", ""),

    # ----------------------------------------------------------------- WHEAT
    ("Aphids are clustering on wheat ears, how do I control them?", "en", "wheat", "pest_management", "no_safety_topic", ""),
    ("Small green insects on wheat leaves, what pest is this?", "en", "wheat", "pest_identification", "no_safety_topic", ""),
    ("Termite damage in wheat field, plants drying in patches", "en", "wheat", "pest_identification", "no_safety_topic", ""),
    ("How to manage termites in wheat before sowing", "en", "wheat", "pest_management", "no_safety_topic", ""),
    ("Orange powder on wheat leaves, is it rust?", "en", "wheat", "disease_management", "no_safety_topic", ""),
    ("Yellow stripe on wheat leaves, disease identification", "en", "wheat", "disease_management", "no_safety_topic", ""),
    ("What is the dose of thiamethoxam for wheat seed treatment?", "en", "wheat", "product_information", "dosage", ""),
    ("Quinalphos quantity per acre for wheat aphid", "en", "wheat", "product_information", "dosage", ""),
    ("Waiting period for chlorpyrifos on wheat before harvest", "en", "wheat", "product_information", "phi", ""),
    ("How many days after spraying wheat can we harvest?", "en", "wheat", "general_guidance", "phi", ""),
    ("Time to wait before re-entering wheat field after spray", "en", "wheat", "general_guidance", "rei", ""),
    ("Should I wear gloves while treating wheat seed with insecticide?", "en", "wheat", "general_guidance", "ppe", ""),
    ("Is thiamethoxam harmful to bees?", "en", "no_crop", "product_information", "toxicity", ""),
    ("Is chlorpyrifos banned for wheat in India?", "en", "wheat", "product_information", "regulatory_approval", ""),
    ("General safety rules for storing pesticides on the farm", "en", "no_crop", "general_guidance", "general_safety", ""),
    ("गेहूं में माहू कीट लगा है, कैसे नियंत्रण करें", "hi", "wheat", "pest_management", "no_safety_topic", ""),
    ("गेहूं की पत्तियों पर छोटे हरे कीड़े हैं, यह कौन सा कीट है", "hi", "wheat", "pest_identification", "no_safety_topic", ""),
    ("गेहूं में दीमक लगी है, क्या करें", "hi", "wheat", "pest_management", "no_safety_topic", ""),
    ("गेहूं में पीला रतुआ रोग के लक्षण क्या हैं", "hi", "wheat", "disease_management", "no_safety_topic", ""),
    ("गेहूं के बीजोपचार में दवा की मात्रा कितनी डालें", "hi", "wheat", "product_information", "dosage", ""),
    ("गेहूं पर छिड़काव के बाद कटाई में कितने दिन का अंतराल", "hi", "wheat", "general_guidance", "phi", ""),
    ("गेहूं में कीटनाशक छिड़काव के बाद खेत में प्रवेश कब करें", "hi", "wheat", "general_guidance", "rei", ""),
    ("कौन सा कीटनाशक ज्यादा जहरीला होता है", "hi", "no_crop", "product_information", "toxicity", ""),
    ("gehu me maahu lag gaya hai, kya karein", "hi-latn", "wheat", "pest_management", "no_safety_topic", ""),
    ("gehu me deemak ke liye dawa ki matra batao", "hi-latn", "wheat", "product_information", "dosage", ""),
    ("gehu par spray ke baad kitne din tak khet me na jayein", "hi-latn", "wheat", "general_guidance", "rei", ""),

    # ----------------------------------------------------------------- MAIZE
    ("Fall armyworm larvae in maize whorl, how to identify", "en", "maize", "pest_identification", "no_safety_topic", ""),
    ("Maize leaves have ragged holes and wet sawdust like frass", "en", "maize", "pest_identification", "no_safety_topic", ""),
    ("How to control fall armyworm in maize", "en", "maize", "pest_management", "no_safety_topic", ""),
    ("Integrated management of fall armyworm in maize at early stage", "en", "maize", "pest_management", "no_safety_topic", ""),
    ("Maize plants wilting and stem rotting at the base", "en", "maize", "disease_management", "no_safety_topic", ""),
    ("Maize leaf blight disease symptoms and control", "en", "maize", "disease_management", "no_safety_topic", ""),
    ("Dose of azadirachtin for maize fall armyworm", "en", "maize", "product_information", "dosage", ""),
    ("How much emamectin benzoate per hectare in maize", "en", "maize", "product_information", "dosage", ""),
    ("Pre harvest interval for emamectin benzoate in maize", "en", "maize", "product_information", "phi", ""),
    ("Days to wait before harvesting maize after insecticide", "en", "maize", "general_guidance", "phi", ""),
    ("How long before I can go back into maize field after spraying", "en", "maize", "general_guidance", "rei", ""),
    ("Protective equipment for spraying maize", "en", "maize", "general_guidance", "ppe", ""),
    ("Is emamectin benzoate toxic to humans?", "en", "no_crop", "product_information", "toxicity", ""),
    ("Is chlorantraniliprole approved for maize in India?", "en", "maize", "product_information", "regulatory_approval", ""),
    ("First aid if pesticide gets on skin while spraying maize", "en", "maize", "general_guidance", "general_safety", ""),
    ("मक्का में फॉल आर्मीवर्म कीट की पहचान कैसे करें", "hi", "maize", "pest_identification", "no_safety_topic", ""),
    ("मक्का में सुंडी लग गई है, नियंत्रण कैसे करें", "hi", "maize", "pest_management", "no_safety_topic", ""),
    ("मक्का के पत्तों पर धब्बे और सूखा रोग", "hi", "maize", "disease_management", "no_safety_topic", ""),
    ("मक्का में कीटनाशक की मात्रा प्रति हेक्टेयर", "hi", "maize", "product_information", "dosage", ""),
    ("मक्का में छिड़काव के बाद कटाई से पहले कितने दिन रुकें", "hi", "maize", "general_guidance", "phi", ""),
    ("मक्का में दवा छिड़कने के बाद कब खेत में जाएं", "hi", "maize", "general_guidance", "rei", ""),
    ("मक्का में छिड़काव के समय मास्क और दस्ताने जरूरी हैं क्या", "hi", "maize", "general_guidance", "ppe", ""),
    ("makka me sundi lag gayi hai, kya dawa daalein", "hi-latn", "maize", "pest_management", "no_safety_topic", ""),
    ("makka me spray ke baad kitna samay rukna hai", "hi-latn", "maize", "general_guidance", "rei", ""),
    ("makka me dawa kitni matra me daalein", "hi-latn", "maize", "product_information", "dosage", ""),
    ("maize me kitnashak ka istemal surakshit tarike se kaise karein", "hi-latn", "maize", "general_guidance", "general_safety", ""),

    # ---------------------------------------------------------------- COTTON
    ("How to identify pink bollworm damage in cotton bolls?", "en", "cotton", "pest_identification", "no_safety_topic", ""),
    ("Cotton squares shedding and holes in bolls, which pest", "en", "cotton", "pest_identification", "no_safety_topic", ""),
    ("American bollworm control in cotton", "en", "cotton", "pest_management", "no_safety_topic", ""),
    ("Management of spotted bollworm in cotton", "en", "cotton", "pest_management", "no_safety_topic", ""),
    ("Pheromone trap number per acre for pink bollworm in cotton", "en", "cotton", "pest_management", "no_safety_topic", ""),
    ("Cotton leaf curl virus symptoms", "en", "cotton", "disease_management", "no_safety_topic", ""),
    ("Cotton seedlings dying after emergence, is it damping off?", "en", "cotton", "disease_management", "no_safety_topic", ""),
    ("Dosage of spinosad for cotton bollworm", "en", "cotton", "product_information", "dosage", ""),
    ("How many ml of chlorantraniliprole per acre in cotton", "en", "cotton", "product_information", "dosage", ""),
    ("PHI of spinosad in cotton", "en", "cotton", "product_information", "phi", ""),
    ("How many days before picking cotton after spray", "en", "cotton", "general_guidance", "phi", ""),
    ("Re entry time after spraying cotton", "en", "cotton", "general_guidance", "rei", ""),
    ("What PPE is needed for cotton pesticide spraying", "en", "cotton", "general_guidance", "ppe", ""),
    ("Is indoxacarb poisonous?", "en", "no_crop", "product_information", "toxicity", ""),
    ("Is flubendiamide registered for cotton in India?", "en", "cotton", "product_information", "regulatory_approval", ""),
    ("How to dispose of empty pesticide containers after cotton spray", "en", "cotton", "general_guidance", "general_safety", ""),
    ("कपास में गुलाबी सुंडी की पहचान कैसे करें", "hi", "cotton", "pest_identification", "no_safety_topic", ""),
    ("कपास में टिंडे गिर रहे हैं, कौन सा कीट है", "hi", "cotton", "pest_identification", "no_safety_topic", ""),
    ("कपास में अमेरिकन सुंडी का नियंत्रण कैसे करें", "hi", "cotton", "pest_management", "no_safety_topic", ""),
    ("कपास में पत्ती मरोड़ रोग के लक्षण", "hi", "cotton", "disease_management", "no_safety_topic", ""),
    ("कपास में कीटनाशक की मात्रा प्रति एकड़", "hi", "cotton", "product_information", "dosage", ""),
    ("कपास में छिड़काव के बाद कटाई से पहले कितने दिन", "hi", "cotton", "general_guidance", "phi", ""),
    ("कपास में दवा छिड़कने के बाद खेत में कब जाएं", "hi", "cotton", "general_guidance", "rei", ""),
    ("कपास का भाव क्या है", "hi", "cotton", "out_of_scope", "no_safety_topic", ""),
    ("kapas me sundi lag gayi, kaun si dawa daalein", "hi-latn", "cotton", "pest_management", "no_safety_topic", ""),
    ("kapas me dawa ki matra kitni hai", "hi-latn", "cotton", "product_information", "dosage", ""),
    ("kapas chhidkav ke baad kitne din baad todaai karein", "hi-latn", "cotton", "general_guidance", "phi", ""),

    # ---------------------------------------------------------------- TOMATO
    ("Small white flies on tomato leaves, what pest is this?", "en", "tomato", "pest_identification", "no_safety_topic", ""),
    ("Tomato fruit borer holes identification", "en", "tomato", "pest_identification", "no_safety_topic", ""),
    ("How to control fruit borer in tomato", "en", "tomato", "pest_management", "no_safety_topic", ""),
    ("Leaf miner management in tomato nursery", "en", "tomato", "pest_management", "no_safety_topic", ""),
    ("Tomato leaves curling and yellowing, is it a virus?", "en", "tomato", "disease_management", "no_safety_topic", ""),
    ("Early blight on tomato, symptoms and management", "en", "tomato", "disease_management", "no_safety_topic", ""),
    ("Dose of indoxacarb for tomato fruit borer", "en", "tomato", "product_information", "dosage", ""),
    ("Cyantraniliprole quantity in tomato per acre", "en", "tomato", "product_information", "dosage", ""),
    ("Pre harvest interval for tomato insecticide", "en", "tomato", "product_information", "phi", ""),
    ("How many days before picking tomatoes after spraying?", "en", "tomato", "general_guidance", "phi", ""),
    ("When is it safe to re-enter the tomato field after spray", "en", "tomato", "general_guidance", "rei", ""),
    ("What safety gear do I need for spraying tomato", "en", "tomato", "general_guidance", "ppe", ""),
    ("Is profenofos toxic to humans?", "en", "no_crop", "product_information", "toxicity", ""),
    ("Is cyantraniliprole approved for tomato in India?", "en", "tomato", "product_information", "regulatory_approval", ""),
    ("Safe storage of pesticides near a tomato field", "en", "tomato", "general_guidance", "general_safety", ""),
    ("टमाटर के फल में छेद है, कौन सा कीट है", "hi", "tomato", "pest_identification", "no_safety_topic", ""),
    ("टमाटर में सफेद मक्खी का नियंत्रण कैसे करें", "hi", "tomato", "pest_management", "no_safety_topic", ""),
    ("टमाटर के पत्ते मुड़ रहे हैं, कौन सा रोग है", "hi", "tomato", "disease_management", "no_safety_topic", ""),
    ("टमाटर में अगेती झुलसा रोग के लक्षण", "hi", "tomato", "disease_management", "no_safety_topic", ""),
    ("टमाटर में कीटनाशक की मात्रा कितनी होती है", "hi", "tomato", "product_information", "dosage", ""),
    ("टमाटर तोड़ने से पहले छिड़काव के बाद कितने दिन रुकें", "hi", "tomato", "general_guidance", "phi", ""),
    ("टमाटर में दवा छिड़कने के बाद कब खेत में जाएं", "hi", "tomato", "general_guidance", "rei", ""),
    ("टमाटर में छिड़काव के समय सुरक्षा के क्या उपाय हैं", "hi", "tomato", "general_guidance", "ppe", ""),
    ("tamatar me keeda lag gaya hai, kya karein", "hi-latn", "tomato", "pest_management", "no_safety_topic", ""),
    ("tamatar me dawa ki matra batao", "hi-latn", "tomato", "product_information", "dosage", ""),
    ("tamatar todne se pehle kitne din rukna chahiye", "hi-latn", "tomato", "general_guidance", "phi", ""),

    # ---------------------------------------------------- UNSUPPORTED CROPS
    ("Sugarcane pygmy borer control measures", "en", "unsupported_crop", "pest_management", "no_safety_topic", "crop outside the 5-crop pilot scope"),
    ("Red rot disease in sugarcane management", "en", "unsupported_crop", "disease_management", "no_safety_topic", "crop outside the 5-crop pilot scope"),
    ("Potato late blight spray schedule", "en", "unsupported_crop", "disease_management", "no_safety_topic", "crop outside the 5-crop pilot scope"),
    ("Onion thrips control dose", "en", "unsupported_crop", "pest_management", "dosage", "crop outside the 5-crop pilot scope"),
    ("Chilli leaf curl management", "en", "unsupported_crop", "disease_management", "no_safety_topic", "crop outside the 5-crop pilot scope"),
    ("Soybean girdle beetle control", "en", "unsupported_crop", "pest_management", "no_safety_topic", "crop outside the 5-crop pilot scope"),
    ("Mustard aphid control measures", "en", "unsupported_crop", "pest_management", "no_safety_topic", "crop outside the 5-crop pilot scope"),
    ("Groundnut leaf miner management", "en", "unsupported_crop", "pest_management", "no_safety_topic", "crop outside the 5-crop pilot scope"),
    ("Banana bunchy top virus control", "en", "unsupported_crop", "disease_management", "no_safety_topic", "crop outside the 5-crop pilot scope"),
    ("Tea mosquito bug management dose", "en", "unsupported_crop", "pest_management", "dosage", "crop outside the 5-crop pilot scope"),
    ("Coffee berry borer control", "en", "unsupported_crop", "pest_management", "no_safety_topic", "crop outside the 5-crop pilot scope"),
    ("Mango hopper control per tree", "en", "unsupported_crop", "pest_management", "no_safety_topic", "crop outside the 5-crop pilot scope"),
    ("Grape mealybug management", "en", "unsupported_crop", "pest_management", "no_safety_topic", "crop outside the 5-crop pilot scope"),
    ("गन्ना में कीट लगा है, क्या करें", "hi", "unsupported_crop", "pest_management", "no_safety_topic", "crop outside the 5-crop pilot scope"),
    ("आलू में झुलसा रोग का इलाज", "hi", "unsupported_crop", "disease_management", "no_safety_topic", "crop outside the 5-crop pilot scope"),
    ("प्याज में थ्रिप्स का नियंत्रण", "hi", "unsupported_crop", "pest_management", "no_safety_topic", "crop outside the 5-crop pilot scope"),
    ("सरसों में माहू लगी है", "hi", "unsupported_crop", "pest_management", "no_safety_topic", "crop outside the 5-crop pilot scope"),
    ("केला में पत्ती रोग", "hi", "unsupported_crop", "disease_management", "no_safety_topic", "crop outside the 5-crop pilot scope"),
    ("मिर्च में मरोड़िया रोग", "hi", "unsupported_crop", "disease_management", "no_safety_topic", "crop outside the 5-crop pilot scope"),
    ("ganna me keeda lag gaya hai", "hi-latn", "unsupported_crop", "pest_management", "no_safety_topic", "crop outside the 5-crop pilot scope"),
    ("aalu me jhulsa rog ka dawa", "hi-latn", "unsupported_crop", "disease_management", "no_safety_topic", "crop outside the 5-crop pilot scope"),
    ("pyaz me dawa ki matra kitni hai", "hi-latn", "unsupported_crop", "product_information", "dosage", "crop outside the 5-crop pilot scope"),

    # ------------------------------------- NO CROP NAMED / GENERIC / SCOPE
    ("What is the weather forecast for tomorrow?", "en", "no_crop", "out_of_scope", "no_safety_topic", ""),
    ("How do I apply for a farm loan subsidy?", "en", "no_crop", "out_of_scope", "no_safety_topic", ""),
    ("Who are you and what can you do?", "en", "no_crop", "out_of_scope", "no_safety_topic", ""),
    ("Hello", "en", "no_crop", "out_of_scope", "no_safety_topic", ""),
    ("Best tractor brand for a small farm", "en", "no_crop", "out_of_scope", "no_safety_topic", ""),
    ("How much urea should I add to my field?", "en", "no_crop", "general_guidance", "no_safety_topic", "ambiguous: fertiliser question, no crop stated"),
    ("Benefits of drip irrigation", "en", "no_crop", "general_guidance", "no_safety_topic", ""),
    ("Which crop is best to sow in June?", "en", "no_crop", "general_guidance", "no_safety_topic", ""),
    ("How to improve soil organic matter", "en", "no_crop", "general_guidance", "no_safety_topic", ""),
    ("Pesticide poisoning symptoms in humans", "en", "no_crop", "general_guidance", "toxicity", ""),
    ("What are the general safety precautions while handling pesticides?", "en", "no_crop", "general_guidance", "general_safety", ""),
    ("How should I store pesticide bottles at home?", "en", "no_crop", "general_guidance", "general_safety", ""),
    ("Which pesticides are banned in India?", "en", "no_crop", "general_guidance", "regulatory_approval", ""),
    ("What is the meaning of integrated pest management", "en", "no_crop", "general_guidance", "no_safety_topic", ""),
    ("कीटनाशक छिड़कते समय क्या सावधानी रखें", "hi", "no_crop", "general_guidance", "general_safety", ""),
    ("खेत में यूरिया कितना डालें", "hi", "no_crop", "general_guidance", "no_safety_topic", "ambiguous: fertiliser question, no crop stated"),
    ("मौसम का पूर्वानुमान बताइए", "hi", "no_crop", "out_of_scope", "no_safety_topic", ""),
    ("कीटनाशक के जहरीलेपन के लक्षण क्या हैं", "hi", "no_crop", "general_guidance", "toxicity", ""),
    ("एकीकृत कीट प्रबंधन क्या है", "hi", "no_crop", "general_guidance", "no_safety_topic", ""),
    ("kitnashak chhidkate samay kya savdhani rakhein", "hi-latn", "no_crop", "general_guidance", "general_safety", ""),
    ("khet me khad kitna daalein", "hi-latn", "no_crop", "general_guidance", "no_safety_topic", "ambiguous: fertiliser question, no crop stated"),
    ("kisi bhi fasal me spray ke baad kitne din rukna chahiye", "hi-latn", "no_crop", "general_guidance", "rei", ""),

    # --------------------- ADDITIONAL COVERAGE FOR RARE CLASSES (task/safety)
    ("What is the minimum support price of wheat this season?", "en", "wheat", "out_of_scope", "no_safety_topic", ""),
    ("How do I get crop insurance claim for cotton?", "en", "cotton", "out_of_scope", "no_safety_topic", ""),
    ("Show me the maize export news", "en", "maize", "out_of_scope", "no_safety_topic", ""),
    ("टमाटर का भाव आज क्या है", "hi", "tomato", "out_of_scope", "no_safety_topic", ""),
    ("Do I need a respirator when spraying inside a polyhouse?", "en", "no_crop", "general_guidance", "ppe", ""),
    ("Which mask and goggles are recommended for pesticide mixing", "en", "no_crop", "general_guidance", "ppe", ""),
    ("टमाटर में छिड़काव के बाद नहाना चाहिए क्या", "hi", "tomato", "general_guidance", "ppe", ""),
    ("Is quinalphos classified as highly hazardous?", "en", "no_crop", "product_information", "toxicity", ""),
    ("मक्का में इस्तेमाल होने वाली दवा जहरीली है क्या", "hi", "maize", "product_information", "toxicity", ""),
    ("Is spinosad registered and approved for tomato in India?", "en", "tomato", "product_information", "regulatory_approval", ""),
    ("कपास में यह कीटनाशक सरकार से पंजीकृत है क्या", "hi", "cotton", "product_information", "regulatory_approval", ""),
    ("Is fipronil permitted for rice cultivation in India", "en", "rice", "product_information", "regulatory_approval", ""),

    # --------- STRENGTHENING THIN SAFETY CLASSES (rei / ppe) AND out_of_scope
    # Added after the first evaluation showed `rei` (15 rows) and `ppe` (11 rows)
    # were the weakest safety classes. These are new phrasings written from the
    # labeling guide; the specific sentences used in the test suite were NOT
    # added, so the added rows cannot vouch for the tests they are meant to fix.
    ("How soon after spraying can workers return to the cotton field?", "en", "cotton", "general_guidance", "rei", ""),
    ("Is there a waiting time before entering the sprayed maize plot?", "en", "maize", "general_guidance", "rei", ""),
    ("How long should the family stay out of the paddy field after spraying?", "en", "rice", "general_guidance", "rei", ""),
    ("दवा छिड़कने के बाद खेत में जाने से पहले कितना समय रुकें", "hi", "no_crop", "general_guidance", "rei", ""),
    ("छिड़काव के बाद मजदूर कब गेहूं के खेत में काम कर सकते हैं", "hi", "wheat", "general_guidance", "rei", ""),
    ("spray ke baad kitni der baad khet me ghus sakte hain", "hi-latn", "no_crop", "general_guidance", "rei", ""),
    ("Which protective clothing is needed while handling concentrated pesticide?", "en", "no_crop", "general_guidance", "ppe", ""),
    ("Are rubber gloves and boots necessary for spraying tomato?", "en", "tomato", "general_guidance", "ppe", ""),
    ("What should I wear to avoid pesticide contact while mixing the solution for cotton?", "en", "cotton", "general_guidance", "ppe", ""),
    ("कीटनाशक मिलाते समय कौन से कपड़े और दस्ताने पहनें", "hi", "no_crop", "general_guidance", "ppe", ""),
    ("मक्का में छिड़काव में आंखों की सुरक्षा के लिए क्या पहनें", "hi", "maize", "general_guidance", "ppe", ""),
    ("spray karte waqt mask aur dastane pehnna zaroori hai kya", "hi-latn", "no_crop", "general_guidance", "ppe", ""),
    ("Tell me the government subsidy scheme for tractor purchase", "en", "no_crop", "out_of_scope", "no_safety_topic", ""),
    ("गेहूं का सरकारी खरीद भाव क्या है", "hi", "wheat", "out_of_scope", "no_safety_topic", ""),
    ("crop insurance kaise le sakte hain", "hi-latn", "no_crop", "out_of_scope", "no_safety_topic", ""),

    # ------------------------------------------------ DELIBERATELY AMBIGUOUS
    ("Problem in my crop", "en", "no_crop", "general_guidance", "no_safety_topic", "ambiguous: no crop, no symptom, no topic"),
    ("Cotton", "en", "cotton", "general_guidance", "no_safety_topic", "ambiguous: crop named only, no intent"),
    ("Need help with spraying", "en", "no_crop", "general_guidance", "general_safety", "ambiguous: no crop, no product, no specific safety question"),
    ("Is it safe?", "en", "no_crop", "general_guidance", "general_safety", "ambiguous: no referent for 'it'"),
    ("फसल में समस्या है", "hi", "no_crop", "general_guidance", "no_safety_topic", "ambiguous: no crop, no symptom, no topic"),
    ("dawa ke bare me jankari chahiye", "hi-latn", "no_crop", "product_information", "no_safety_topic", "ambiguous: no crop, no product named"),
    ("What should I do now", "en", "no_crop", "general_guidance", "no_safety_topic", "ambiguous: no crop, no context"),
    ("टमाटर", "hi", "tomato", "general_guidance", "no_safety_topic", "ambiguous: crop named only, no intent"),
]


def main() -> None:
    out = Path(__file__).resolve().parent / "queries.csv"
    seen: dict[str, str] = {}
    for idx, row in enumerate(ROWS, start=1):
        text = row[0]
        key = "".join(ch for ch in text.lower() if ch.isalnum())
        if key in seen:
            raise SystemExit(f"Duplicate query text at row {idx}: {text!r} (first seen in {seen[key]})")
        seen[key] = f"row {idx}"
        if len(row) != 6:
            raise SystemExit(f"Row {idx} has {len(row)} fields, expected 6")

    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(HEADER)
        for idx, (text, language, crop, task, safety, notes) in enumerate(ROWS, start=1):
            writer.writerow([f"Q{idx:03d}", text, language, crop, task, safety, notes])

    print(f"Wrote {len(ROWS)} rows to {out}")


if __name__ == "__main__":
    main()
