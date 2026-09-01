"""
reference_phrases.py

Self-written, hand-curated reference phrases for the four digital-arrest-scam
escalation stages, calibrated against the *pattern* described in publicly
documented advisories (RBI cybercrime advisories, I4C / cybercrime.gov.in
advisories, and reported news coverage of digital-arrest cases).

IMPORTANT:
  - No real victim-call transcripts or recordings are used anywhere in this
    dataset. Every phrase below was written for this project.
  - Phrases are grouped by stage and tagged by language for transparency and
    for the offline "lite" matching backend (see embeddings.py). The
    multilingual embedding backend (LaBSE) does NOT need the language tag —
    it matches on meaning across languages/scripts directly.

Stages, in the order they typically escalate:
  1. AUTHORITY        - caller claims to be police/CBI/customs/bank/govt
  2. ISOLATION         - caller tries to cut the victim off from help
  3. THREAT_URGENCY     - caller threatens arrest / legal action, creates urgency
  4. FINANCIAL_DEMAND   - caller asks for money / OTP / bank details
"""

STAGES = ["AUTHORITY", "ISOLATION", "THREAT_URGENCY", "FINANCIAL_DEMAND"]

# Base weight contributed by each stage when it first fires during a call.
# These match the weights shown on the "Risk Scoring Logic" slide.
STAGE_WEIGHTS = {
    "AUTHORITY": 20,
    "ISOLATION": 25,
    "THREAT_URGENCY": 25,
    "FINANCIAL_DEMAND": 30,
}

# Bonus added if all four stages fire in the classic textbook order
# (Authority -> Isolation -> Threat -> Financial Demand). Not required for a
# HIGH/CRITICAL classification -- purely an additional signal.
ORDER_BONUS = 10

# Risk-tier cutoffs, out of a 0-110 possible score (100 base + 10 order bonus).
# Documented here once so the PPT, the README and the code always agree.
RISK_TIERS = [
    ("LOW", 0, 24),
    ("MEDIUM", 25, 49),
    ("HIGH", 50, 79),
    ("CRITICAL", 80, 110),
]

REFERENCE_PHRASES = {
    "AUTHORITY": [
        ("en", "I am calling from the CBI regarding a case against you."),
        ("en", "This is the cyber crime cell, we need to verify your identity."),
        ("en", "Your Aadhaar card is linked to an illegal parcel seizure."),
        ("en", "We are from the customs department and your package contains banned items."),
        ("en", "I am an officer with the Reserve Bank of India investigating your account."),
        ("hi", "Main CBI officer bol raha hoon aapke case ke silsile mein."),
        ("hi", "Yeh cyber crime branch se call hai, aapki pehchaan verify karni hai."),
        ("hi", "Aapka Aadhaar ek illegal parcel case mein link hua hai."),
        ("hi", "Hum customs department se bol rahe hain, aapke parcel mein banned items mile hain."),
        ("hinglish", "Sir aapke naam par ek FIR register hui hai Mumbai police station mein."),
        ("hinglish", "Aapka mobile number ek money laundering case se juda hai."),
        ("hi", "Main CBI se bol raha hoon, aapke khilaaf money laundering ka gambhir maamla hai."),
        ("hi", "नमस्ते, मैं CBI से बोल रहा हूँ। आपके खिलाफ money laundering का एक गंभीर मामला है।"),
    ],
    "ISOLATION": [
        ("en", "Do not disconnect this call under any circumstances."),
        ("en", "You must not tell any family member about this investigation."),
        ("en", "This is a confidential matter, do not discuss it with anyone."),
        ("en", "Stay on this video call until the verification is complete."),
        ("hi", "Phone mat kaatna, yeh case abhi chal raha hai."),
        ("hi", "Kisi ko is baare mein mat batana, yeh gopniya maamla hai."),
        ("hi", "Aap is call ko chhod kar kahin nahi ja sakte."),
        ("hinglish", "Family ko is baare mein batane ki zaroorat nahi hai abhi."),
        ("hinglish", "Aap camera on rakhiye aur kisi se contact mat kijiye."),
        ("hi", "Phone bilkul mat kaatiyega, is gopniya jaanch ke baare mein kisi family member ko mat batana."),
        ("hi", "कृपया phone बिल्कुल भी मत काटिएगा।"),
        ("hi", "इस गोपनीय जांच के बारे में अपने परिवार के किसी भी सदस्य को बिल्कुल भी जानकारी नहीं देनी है।"),
        ("hinglish", "Private room mein jaiye aur kisi ko is confidential investigation ke baare mein mat batana."),
    ],
    "THREAT_URGENCY": [
        ("en", "You will be arrested within the next few hours if you do not cooperate."),
        ("en", "A non-bailable warrant has already been issued in your name."),
        ("en", "If you disconnect, the local police team will reach your house immediately."),
        ("en", "You have only ten minutes to respond before legal action is taken."),
        ("hi", "Aapko das minute mein arrest kar liya jaayega agar aap cooperate nahi karte."),
        ("hi", "Aapke naam ek non-bailable warrant jaari ho chuka hai."),
        ("hi", "Agar aap call kaatte hain to police aapke ghar pahunch jaayegi."),
        ("hinglish", "Yeh matter bahut urgent hai, aapke paas sirf thoda time hai."),
        ("hi", "Agar aapne sahyog nahi kiya to arrest warrant jaari kar diya jaayega aur police team aapke pate par bhej di jaayegi."),
        ("hinglish", "Cooperate nahi kiya to arrest warrant issue hoga aur police ki team aapke address par bheji jaayegi."),
        ("hi", "यदि आपने हमारे साथ सहयोग नहीं किया, तो arrest warrant जारी कर दिया जाएगा और police की एक team आपके पते पर भेज दी जाएगी।"),
    ],
    "FINANCIAL_DEMAND": [
        ("en", "You need to transfer the verification amount to this account immediately."),
        ("en", "Please share the OTP that you just received to confirm your identity."),
        ("en", "Send fifty thousand rupees as a refundable security deposit."),
        ("en", "Provide your bank account and card details for the investigation record."),
        ("hi", "Aapko turant verification ke liye paise transfer karne honge."),
        ("hi", "Jo OTP aaya hai woh humein bataiye apni pehchaan confirm karne ke liye."),
        ("hi", "Pachaas hazaar rupaye is account mein bhejiye, yeh refundable hai."),
        ("hinglish", "Please apna bank detail aur card number share kijiye."),
        ("hi", "Temporary security deposit ke taur par pachaas hazaar rupaye turant transfer kijiye."),
        ("hinglish", "Case ko rafa-dafa karne ke liye fifty thousand rupees security deposit ke taur par transfer kijiye."),
        ("hi", "इस case को रफा-दफा करने के लिए आपको temporary security deposit के तौर पर तुरंत 50,000 रुपये transfer करने होंगे।"),
    ],
}

# A small set of BENIGN / non-scam control lines, used only for measuring the
# false-positive behaviour of the pipeline (see tests/run_evaluation.py).
# These deliberately share surface words with scam phrases (police, account,
# transfer, OTP) without the underlying manipulation pattern, so a keyword
# matcher would over-trigger on them while a pattern-aware engine should not.
BENIGN_CONTROL_LINES = [
    ("en", "Hi, this is your bank calling to confirm your new debit card has been dispatched."),
    ("en", "Just checking if you received the OTP for your food delivery order."),
    ("en", "The police station near your society is organising a road-safety awareness camp."),
    ("hi", "Aapka parcel kal tak deliver ho jaayega, tracking number bhej diya hai."),
    ("hi", "Bank se call hai, aapka new debit card dispatch ho gaya hai."),
    ("hinglish", "Sir aapka Swiggy order ka OTP share kar dijiye delivery partner ko."),
]
