"""User-facing strings in English (en), Romi Konkani (kok), Hindi (hi) and
Marathi (mr).

Konkani uses the Romi (Latin) script — the script most used on WhatsApp by
the Catholic fishing communities of Salcete/Mormugao. Translations were
drafted for the pilot and are flagged for native-speaker review before the
WhatsApp template submission to Meta (execution plan §10: template approval).

Every entry falls back to English if a language key is missing, so partial
translations never crash message composition.
"""

from app.enums import Language

STRINGS: dict[str, dict[str, str]] = {
    # --- Onboarding -----------------------------------------------------------
    "welcome_language_menu": {
        "en": (
            "🌊 Welcome to Fisherman OS!\n"
            "Your daily sea forecast, fish prices & SOS — on WhatsApp.\n\n"
            "Choose your language / Tuji bhas vench / अपनी भाषा चुनें / तुमची भाषा निवडा:\n\n"
            "1️⃣ English\n"
            "2️⃣ Konkani (Romi)\n"
            "3️⃣ हिंदी\n"
            "4️⃣ मराठी\n\n"
            "Reply with 1, 2, 3 or 4"
        ),
    },
    "invalid_language": {
        "en": "Please reply with 1 (English), 2 (Konkani), 3 (हिंदी) or 4 (मराठी).",
    },
    "ask_name": {
        "en": "Great! 👋 What is your name?",
        "kok": "Borem! 👋 Tujem nanv kitem?",
        "hi": "बहुत अच्छा! 👋 आपका नाम क्या है?",
        "mr": "छान! 👋 तुमचे नाव काय आहे?",
    },
    "ask_village": {
        "en": (
            "Thanks {name}! 🏝️ Which village do you fish from?\n"
            "(e.g. Betul, Velim, Cavelossim, Palolem...)"
        ),
        "kok": (
            "Dev borem korum {name}! 🏝️ Tum khoinchea ganvant nustemari kortai?\n"
            "(dekhik: Betul, Velim, Cavelossim, Palolem...)"
        ),
        "hi": (
            "धन्यवाद {name}! 🏝️ आप किस गाँव से मछली पकड़ने जाते हैं?\n"
            "(जैसे: Betul, Velim, Cavelossim, Palolem...)"
        ),
        "mr": (
            "धन्यवाद {name}! 🏝️ तुम्ही कोणत्या गावातून मासेमारी करता?\n"
            "(उदा: Betul, Velim, Cavelossim, Palolem...)"
        ),
    },
    "village_not_found": {
        "en": (
            "I couldn't find that village, so I've set your village to {fallback} for now.\n"
            "Reply VILLAGE <name> anytime to change it."
        ),
        "kok": (
            "To ganv mhaka mellonk na, dekhun atam tuzo ganv {fallback} kelo.\n"
            "Bodlunk kednay VILLAGE <nanv> boroi."
        ),
        "hi": (
            "वह गाँव नहीं मिला, इसलिए अभी आपका गाँव {fallback} रखा है।\n"
            "बदलने के लिए कभी भी VILLAGE <नाम> भेजें।"
        ),
        "mr": (
            "ते गाव सापडले नाही, म्हणून सध्या तुमचे गाव {fallback} ठेवले आहे.\n"
            "बदलण्यासाठी कधीही VILLAGE <नाव> पाठवा."
        ),
    },
    "ask_boat_type": {
        "en": (
            "Almost done! ⛵ What type of boat do you use?\n\n"
            "1️⃣ Canoe (no motor)\n"
            "2️⃣ Motorized canoe / outboard\n"
            "3️⃣ Rampon (shore seine)\n"
            "4️⃣ Trawler\n"
            "5️⃣ Other\n\n"
            "Reply with 1-5"
        ),
        "kok": (
            "Zalem mhunn! ⛵ Tum khoinchem hodem vaportai?\n\n"
            "1️⃣ Vodem (motor naslelem)\n"
            "2️⃣ Motor aslelem vodem / outboard\n"
            "3️⃣ Rampon\n"
            "4️⃣ Trawler\n"
            "5️⃣ Her\n\n"
            "1-5 boroi"
        ),
        "hi": (
            "लगभग हो गया! ⛵ आप किस तरह की नाव चलाते हैं?\n\n"
            "1️⃣ डोंगी (बिना मोटर)\n"
            "2️⃣ मोटर वाली डोंगी / आउटबोर्ड\n"
            "3️⃣ रामपोन (किनारे का जाल)\n"
            "4️⃣ ट्रॉलर\n"
            "5️⃣ अन्य\n\n"
            "1-5 भेजें"
        ),
        "mr": (
            "जवळपास झाले! ⛵ तुम्ही कोणत्या प्रकारची होडी वापरता?\n\n"
            "1️⃣ होडी (मोटार नसलेली)\n"
            "2️⃣ मोटार असलेली होडी / आउटबोर्ड\n"
            "3️⃣ रामपण (रापण)\n"
            "4️⃣ ट्रॉलर\n"
            "5️⃣ इतर\n\n"
            "1-5 पाठवा"
        ),
    },
    "invalid_boat_type": {
        "en": "Please reply with a number from 1 to 5.",
        "kok": "1 thavn 5 modlo ankddo boroi.",
        "hi": "कृपया 1 से 5 तक का अंक भेजें।",
        "mr": "कृपया 1 ते 5 पैकी एक अंक पाठवा.",
    },
    "registered": {
        "en": (
            "✅ You're registered, {name}!\n"
            "📍 Village: {village}\n\n"
            "Every morning at 3:30 AM you'll get your sea forecast — before you leave shore.\n"
            "Here's today's forecast: 👇"
        ),
        "kok": (
            "✅ Tujem registration zalem, {name}!\n"
            "📍 Ganv: {village}\n\n"
            "Dor sokallim 3:30 vorancher tuka doryachi khobor melltoli — doryant vochche adim.\n"
            "Hi aichi khobor: 👇"
        ),
        "hi": (
            "✅ आपका पंजीकरण हो गया, {name}!\n"
            "📍 गाँव: {village}\n\n"
            "हर सुबह 3:30 बजे समुद्र का पूर्वानुमान मिलेगा — किनारा छोड़ने से पहले।\n"
            "आज का पूर्वानुमान: 👇"
        ),
        "mr": (
            "✅ तुमची नोंदणी झाली, {name}!\n"
            "📍 गाव: {village}\n\n"
            "दररोज पहाटे 3:30 वाजता समुद्राचा अंदाज मिळेल — किनारा सोडण्यापूर्वी.\n"
            "आजचा अंदाज: 👇"
        ),
    },
    # --- Forecast --------------------------------------------------------------
    "todays_sea": {
        "en": "Today's Sea", "kok": "Aizcho Dorya", "hi": "आज का समुद्र", "mr": "आजचा समुद्र",
    },
    "safety_safe": {
        "en": "SAFE TO GO", "kok": "VOCHUNK SUROKXIT", "hi": "जाना सुरक्षित है", "mr": "जाणे सुरक्षित",
    },
    "safety_caution": {
        "en": "CAUTION", "kok": "CHOTRAI", "hi": "सावधानी रखें", "mr": "सावधगिरी बाळगा",
    },
    "safety_danger": {
        "en": "DO NOT GO", "kok": "DORYANT VOCHUM NAKA", "hi": "समुद्र में न जाएं", "mr": "समुद्रात जाऊ नका",
    },
    "wind": {"en": "Wind", "kok": "Varem", "hi": "हवा", "mr": "वारा"},
    "waves": {"en": "Waves", "kok": "Lhara", "hi": "लहरें", "mr": "लाटा"},
    "rain": {"en": "Rain", "kok": "Paus", "hi": "बारिश", "mr": "पाऊस"},
    "rain_chance": {"en": "{pct}% chance", "kok": "{pct}% sombhov", "hi": "{pct}% संभावना", "mr": "{pct}% शक्यता"},
    "sea_temp": {"en": "Sea temp", "kok": "Doryachem tapman", "hi": "समुद्र का तापमान", "mr": "समुद्राचे तापमान"},
    "next_6_hours": {"en": "Next 6 hours", "kok": "Fuddlim 6 voram", "hi": "अगले 6 घंटे", "mr": "पुढील 6 तास"},
    "waves_calm": {"en": "calm", "kok": "xant", "hi": "शांत", "mr": "शांत"},
    "waves_moderate": {"en": "moderate", "kok": "modem", "hi": "मध्यम", "mr": "मध्यम"},
    "waves_rough": {"en": "rough", "kok": "khor", "hi": "उग्र", "mr": "खवळलेल्या"},
    "waves_very_rough": {"en": "very rough", "kok": "bhov khor", "hi": "बहुत उग्र", "mr": "खूप खवळलेल्या"},
    "menu_footer": {
        "en": 'Type "1" for detailed forecast\nType "2" for market prices\nType "SOS" for emergency',
        "kok": 'Sovistar khobrek "1" boroi\nBazarachea molank "2" boroi\nApotkalak "SOS" boroi',
        "hi": 'विस्तृत पूर्वानुमान के लिए "1" भेजें\nमछली के दाम के लिए "2" भेजें\nआपातकाल के लिए "SOS" भेजें',
        "mr": 'सविस्तर अंदाजासाठी "1" पाठवा\nमाशांच्या दरांसाठी "2" पाठवा\nआपत्कालासाठी "SOS" पाठवा',
    },
    "detailed_forecast_title": {
        "en": "Detailed Forecast", "kok": "Sovistar Khobor", "hi": "विस्तृत पूर्वानुमान", "mr": "सविस्तर अंदाज",
    },
    "forecast_source": {"en": "Source", "kok": "Mull", "hi": "स्रोत", "mr": "स्रोत"},
    "issued_at": {"en": "Issued", "kok": "Dilem", "hi": "जारी", "mr": "जारी"},
    "forecast_unavailable": {
        "en": "Sorry, today's forecast is not available right now. Please try again in a few minutes.",
        "kok": "Maf kor, aichi khobor atam mellona. Thodea vellan porot proitn kor.",
        "hi": "क्षमा करें, अभी पूर्वानुमान उपलब्ध नहीं है। कुछ मिनटों में फिर प्रयास करें।",
        "mr": "क्षमस्व, सध्या अंदाज उपलब्ध नाही. काही मिनिटांनी पुन्हा प्रयत्न करा.",
    },
    # --- Prices ------------------------------------------------------------------
    "price_header": {
        "en": "🐟 Today's Fish Prices ({day} closing)",
        "kok": "🐟 Aiz Nusteachem Mol ({day} bond zatana)",
        "hi": "🐟 आज मछली के दाम ({day} बंद भाव)",
        "mr": "🐟 आज माशांचे दर ({day} बंद भाव)",
    },
    "price_tip": {
        "en": "💡 TIP: {best_center} paying {pct}% more for {species} today",
        "kok": "💡 TIP: {best_center}-ant aiz {species}-k {pct}% chodd mol melltta",
        "hi": "💡 सुझाव: {best_center} आज {species} के लिए {pct}% अधिक दे रहा है",
        "mr": "💡 टीप: {best_center} आज {species} साठी {pct}% जास्त देत आहे",
    },
    "price_footer": {
        "en": 'Type "PRICES" anytime for latest',
        "kok": 'Kednay “PRICES” boroi ani novem mol ghe',
        "hi": 'ताज़ा दाम के लिए कभी भी "PRICES" भेजें',
        "mr": 'ताजे दर मिळवण्यासाठी कधीही "PRICES" पाठवा',
    },
    "no_prices": {
        "en": "No market prices reported yet today. Our field agent updates prices by 5 AM — check back soon!",
        "kok": "Aiz ajun bazarachem mol ailem na. Amcho agent 5 voram poilem mol dhaddta — thodea vellan polle!",
        "hi": "आज अभी तक दाम नहीं आए हैं। हमारा एजेंट सुबह 5 बजे तक दाम भेजता है — थोड़ी देर में देखें!",
        "mr": "आज अजून दर आलेले नाहीत. आमचा एजंट पहाटे 5 पर्यंत दर पाठवतो — थोड्या वेळाने पहा!",
    },
    # --- SOS -----------------------------------------------------------------------
    "sos_activated": {
        "en": (
            "🚨 EMERGENCY ACTIVATED\n"
            "{location_line}"
            "📞 Coast Guard: {coast_guard} — CALL NOW if you can\n"
            "👥 Emergency contacts notified: {contacts}\n"
            "🔄 Location sharing: ON — share your WhatsApp location every 5 min\n\n"
            "Stay calm. Help is being coordinated.\n"
            "Reply CANCEL to deactivate.\n\n"
            "⚠️ This service supports but does NOT replace calling Coast Guard {coast_guard}."
        ),
        "kok": (
            "🚨 APOTKAL SURU ZALO\n"
            "{location_line}"
            "📞 Coast Guard: {coast_guard} — zata zalear ATAM phone kor\n"
            "👥 Tujea gharcheank khobor dili: {contacts}\n"
            "🔄 Location dhaddop: ON — dor 5 minutanim WhatsApp location dhadd\n\n"
            "Xant rav. Mozot ieta.\n"
            "Bond korunk CANCEL boroi.\n\n"
            "⚠️ Hi seva Coast Guard {coast_guard}-ak phone korpachi zago ghenam."
        ),
        "hi": (
            "🚨 आपातकाल सक्रिय\n"
            "{location_line}"
            "📞 कोस्ट गार्ड: {coast_guard} — हो सके तो अभी कॉल करें\n"
            "👥 आपातकालीन संपर्कों को सूचित किया: {contacts}\n"
            "🔄 लोकेशन शेयरिंग: चालू — हर 5 मिनट में WhatsApp लोकेशन भेजें\n\n"
            "शांत रहें। मदद भेजी जा रही है।\n"
            "रद्द करने के लिए CANCEL भेजें।\n\n"
            "⚠️ यह सेवा कोस्ट गार्ड {coast_guard} को कॉल करने का विकल्प नहीं है।"
        ),
        "mr": (
            "🚨 आपत्काल सुरू\n"
            "{location_line}"
            "📞 कोस्ट गार्ड: {coast_guard} — शक्य असल्यास आत्ताच कॉल करा\n"
            "👥 आपत्कालीन संपर्कांना कळवले: {contacts}\n"
            "🔄 लोकेशन शेअरिंग: चालू — दर 5 मिनिटांनी WhatsApp लोकेशन पाठवा\n\n"
            "शांत राहा. मदत पाठवली जात आहे.\n"
            "रद्द करण्यासाठी CANCEL पाठवा.\n\n"
            "⚠️ ही सेवा कोस्ट गार्ड {coast_guard} ला कॉल करण्याची जागा घेत नाही."
        ),
    },
    "sos_location_line": {
        "en": "📍 Your location: {link}\n",
        "kok": "📍 Tuji suvat: {link}\n",
        "hi": "📍 आपकी लोकेशन: {link}\n",
        "mr": "📍 तुमचे स्थान: {link}\n",
    },
    "sos_no_location_line": {
        "en": "📍 Location unknown — SHARE YOUR LOCATION NOW (attach 📎 → Location)\n",
        "kok": "📍 Suvat khobor na — ATAM LOCATION DHADD (📎 → Location)\n",
        "hi": "📍 लोकेशन अज्ञात — अभी लोकेशन भेजें (📎 → Location)\n",
        "mr": "📍 स्थान अज्ञात — आत्ताच लोकेशन पाठवा (📎 → Location)\n",
    },
    "sos_location_received": {
        "en": "📍 Location received ({link}). Contacts updated. Keep sharing every 5 min.",
        "kok": "📍 Suvat pavli ({link}). Gharcheank kolloilem. Dor 5 minutanim dhaddit rav.",
        "hi": "📍 लोकेशन मिल गई ({link})। संपर्कों को बताया गया। हर 5 मिनट में भेजते रहें।",
        "mr": "📍 स्थान मिळाले ({link}). संपर्कांना कळवले. दर 5 मिनिटांनी पाठवत राहा.",
    },
    "sos_reminder": {
        "en": "🔄 SOS still active. Please share your current WhatsApp location (📎 → Location). Reply CANCEL if you are safe.",
        "kok": "🔄 SOS ajun chalu asa. Tuji atachi location dhadd (📎 → Location). Tum surokxit zalear CANCEL boroi.",
        "hi": "🔄 SOS अभी सक्रिय है। अपनी वर्तमान लोकेशन भेजें (📎 → Location)। सुरक्षित हों तो CANCEL भेजें।",
        "mr": "🔄 SOS अजून सुरू आहे. तुमचे सध्याचे स्थान पाठवा (📎 → Location). सुरक्षित असाल तर CANCEL पाठवा.",
    },
    "sos_cancelled": {
        "en": "✅ SOS deactivated. Glad you're safe! Your emergency contacts have been informed.",
        "kok": "✅ SOS bond kelo. Tum surokxit mhunn khuxi zali! Tujea gharcheank kolloilem.",
        "hi": "✅ SOS रद्द हो गया। खुशी है कि आप सुरक्षित हैं! आपके संपर्कों को बता दिया गया है।",
        "mr": "✅ SOS रद्द झाले. तुम्ही सुरक्षित आहात याचा आनंद! तुमच्या संपर्कांना कळवले आहे.",
    },
    "sos_none_active": {
        "en": "No active SOS found. Send SOS to activate an emergency alert.",
        "kok": "SOS chalu na. Apotkal suru korunk SOS boroi.",
        "hi": "कोई सक्रिय SOS नहीं है। आपातकाल के लिए SOS भेजें।",
        "mr": "कोणतेही सक्रिय SOS नाही. आपत्कालासाठी SOS पाठवा.",
    },
    "sos_contact_alert": {
        "en": (
            "🚨 EMERGENCY: {name} ({phone}) has activated SOS at sea via Fisherman OS.\n"
            "{location_line}"
            "📞 Call Indian Coast Guard: {coast_guard}\n"
            "We will send location updates as they arrive."
        ),
    },
    "sos_contact_location_update": {
        "en": "📍 SOS update — {name}'s latest location: {link} ({time})",
    },
    "sos_contact_stand_down": {
        "en": "✅ {name} has cancelled their SOS and reports being safe.",
    },
    # --- Commands / misc --------------------------------------------------------
    "help": {
        "en": (
            "🌊 Fisherman OS — Commands\n\n"
            "1 — Detailed forecast\n"
            "2 or PRICES — Market prices\n"
            "SOS — Emergency alert\n"
            "CANCEL — Stop SOS\n"
            "CONTACT <name> <phone> — Add emergency contact\n"
            "VILLAGE <name> — Change your village\n"
            "LANG — Change language\n"
            "STOP / START — Pause / resume daily messages\n"
            "HELP — This menu"
        ),
        "kok": (
            "🌊 Fisherman OS — Adnia\n\n"
            "1 — Sovistar khobor\n"
            "2 vo PRICES — Bazarachem mol\n"
            "SOS — Apotkal\n"
            "CANCEL — SOS bond kor\n"
            "CONTACT <nanv> <phone> — Apotkal sompork ghal\n"
            "VILLAGE <nanv> — Ganv bodol\n"
            "LANG — Bhas bodol\n"
            "STOP / START — Sodachim messages bond / suru kor\n"
            "HELP — Hi suchi"
        ),
        "hi": (
            "🌊 Fisherman OS — कमांड\n\n"
            "1 — विस्तृत पूर्वानुमान\n"
            "2 या PRICES — मछली के दाम\n"
            "SOS — आपातकालीन अलर्ट\n"
            "CANCEL — SOS बंद करें\n"
            "CONTACT <नाम> <फोन> — आपातकालीन संपर्क जोड़ें\n"
            "VILLAGE <नाम> — गाँव बदलें\n"
            "LANG — भाषा बदलें\n"
            "STOP / START — दैनिक संदेश बंद / चालू करें\n"
            "HELP — यह मेनू"
        ),
        "mr": (
            "🌊 Fisherman OS — आदेश\n\n"
            "1 — सविस्तर अंदाज\n"
            "2 किंवा PRICES — माशांचे दर\n"
            "SOS — आपत्कालीन इशारा\n"
            "CANCEL — SOS बंद करा\n"
            "CONTACT <नाव> <फोन> — आपत्कालीन संपर्क जोडा\n"
            "VILLAGE <नाव> — गाव बदला\n"
            "LANG — भाषा बदला\n"
            "STOP / START — दैनिक संदेश बंद / सुरू करा\n"
            "HELP — हा मेनू"
        ),
    },
    "unknown_command": {
        "en": "Sorry, I didn't understand that. Type HELP to see what I can do.",
        "kok": "Maf kor, mhaka samzonk na. HELP boroi ani polle hanv kitem korunk xoktam.",
        "hi": "क्षमा करें, समझ नहीं आया। HELP भेजकर देखें मैं क्या कर सकता हूँ।",
        "mr": "क्षमस्व, समजले नाही. HELP पाठवून पहा मी काय करू शकतो.",
    },
    "stopped": {
        "en": "🔕 Daily messages paused. Send START anytime to resume. SOS stays active 24/7.",
        "kok": "🔕 Sodachim messages bond kelim. Porot suru korunk START boroi. SOS 24/7 chalu urta.",
        "hi": "🔕 दैनिक संदेश रोक दिए गए। फिर शुरू करने के लिए START भेजें। SOS 24/7 सक्रिय रहेगा।",
        "mr": "🔕 दैनिक संदेश थांबवले. पुन्हा सुरू करण्यासाठी START पाठवा. SOS 24/7 सुरू राहील.",
    },
    "started": {
        "en": "🔔 Daily messages resumed. See you at 3:30 AM!",
        "kok": "🔔 Sodachim messages porot suru. Sokallim 3:30 vorancher melltat!",
        "hi": "🔔 दैनिक संदेश फिर शुरू। सुबह 3:30 बजे मिलते हैं!",
        "mr": "🔔 दैनिक संदेश पुन्हा सुरू. पहाटे 3:30 वाजता भेटू!",
    },
    "language_menu": {
        "en": (
            "Choose your language / Tuji bhas vench / अपनी भाषा चुनें / तुमची भाषा निवडा:\n\n"
            "1️⃣ English\n2️⃣ Konkani (Romi)\n3️⃣ हिंदी\n4️⃣ मराठी\n\nReply with 1, 2, 3 or 4"
        ),
    },
    "language_set": {
        "en": "✅ Language set to English.",
        "kok": "✅ Bhas Konkani keli.",
        "hi": "✅ भाषा हिंदी सेट हो गई।",
        "mr": "✅ भाषा मराठी सेट झाली.",
    },
    "village_changed": {
        "en": "✅ Village updated to {village}. Your forecasts will now be for {village}.",
        "kok": "✅ Ganv {village} kelo. Atam tuka {village}-chi khobor melltoli.",
        "hi": "✅ गाँव {village} हो गया। अब आपको {village} का पूर्वानुमान मिलेगा।",
        "mr": "✅ गाव {village} झाले. आता तुम्हाला {village} चा अंदाज मिळेल.",
    },
    "contact_added": {
        "en": "✅ Emergency contact added: {name} ({phone}). They'll be alerted if you send SOS.",
        "kok": "✅ Apotkal sompork ghatlo: {name} ({phone}). Tum SOS dhaddlear tankam khobor melltoli.",
        "hi": "✅ आपातकालीन संपर्क जुड़ गया: {name} ({phone})। SOS भेजने पर उन्हें सूचना मिलेगी।",
        "mr": "✅ आपत्कालीन संपर्क जोडला: {name} ({phone}). SOS पाठवल्यास त्यांना कळवले जाईल.",
    },
    "contact_usage": {
        "en": "To add an emergency contact, send: CONTACT <name> <phone>\nExample: CONTACT Maria 9822012345",
        "kok": "Apotkal sompork ghalunk boroi: CONTACT <nanv> <phone>\nDekhik: CONTACT Maria 9822012345",
        "hi": "आपातकालीन संपर्क जोड़ने के लिए भेजें: CONTACT <नाम> <फोन>\nउदाहरण: CONTACT Maria 9822012345",
        "mr": "आपत्कालीन संपर्क जोडण्यासाठी पाठवा: CONTACT <नाव> <फोन>\nउदा: CONTACT Maria 9822012345",
    },
    "price_recorded": {
        "en": "✅ Price recorded: {species} ₹{price}/kg at {center} ({day}).",
    },
    "price_usage": {
        "en": (
            "Price entry format: PRICE <center> <species> <₹/kg>\n"
            "Example: PRICE Betul mackerel 85\n"
            "Centers: Betul, Cutbona, Margao, Vasco, Colva"
        ),
    },
    "price_not_agent": {
        "en": "Price entry is only available to registered field agents.",
    },
}


def t(key: str, language: Language | str = Language.ENGLISH, **kwargs) -> str:
    """Translate `key` into `language`, falling back to English, and format."""
    lang = language.value if isinstance(language, Language) else language
    entry = STRINGS.get(key)
    if entry is None:
        raise KeyError(f"Unknown string key: {key}")
    template = entry.get(lang) or entry["en"]
    return template.format(**kwargs) if kwargs else template
