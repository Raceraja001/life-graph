#!/usr/bin/env python3
"""
Harvester: Batch 56 - Ancient Tamil Black Pepper (Milagu) & Indo-Roman Spice Confederations
Generated automatically.
"""

import os
import json
import psycopg2
import requests

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "bge-m3:latest"
DOSSIER_DIR = "/mnt/h/DevTools/Projects/learn-ai/moolam-chronicles/knowledge"

CATEGORY_DIRS = {
    "technology": "technologies",
    "archaeology": "archaeology",
    "history": "history",
    "science": "science",
}

def category_dir(category: str) -> str:
    return CATEGORY_DIRS.get(category, category + "s")

DOSSIERS = [
  {
    "slug": "technology-milagu-pepper-vine-standards-harvesting-hot-water-scalding-and-sun-curing-technology",
    "file": "technology-milagu-pepper-vine-standards-harvesting-hot-water-scalding-and-sun-curing-technology.md",
    "category": "technology",
    "name_en": "Milagu Pepper-Vine Standards, Harvesting, Hot-Water Scalding & Sun-Curing Technology",
    "name_ta": "மிளகுக் கொடி ஆதார மரம், அறுவடை, வெந்நீர் அமிழ்த்தல் மற்றும் வெயில் உலர்த்தும் தொழில்நுட்பம்",
    "era": "Sangam Era to Modern Era",
    "year_start": -300,
    "year_end": 2026,
    "thinai": "kurinji",
    "summary_en": "Traditional cultivation and curing of Piper nigrum in the Western Ghats and Kolli Hills: training perennial vines on live tree standards (Murikku, Jackfruit), climbing bamboo ladders (enip-padikkal) to hand-strip mature green-orange spikes, quick hot-water immersion (scalding at 80°C) to rupture cellular membranes and activate polyphenol oxidase enzymes, followed by open-air sun curing on palm mats until berries turn into wrinkly, pitch-black drupes.",
    "summary_ta": "கொல்லிமலை மற்றும் மேற்குத் தொடர்ச்சி மலைப் பகுதிகளில் மிளகு சாகுபடி: முருக்கு மற்றும் பலா மரங்களில் கொடி ஏற்றுதல், மூங்கில் ஏணி கொண்டு பழக்கொத்துகளைப் பறித்தல், 80 பாகை வெந்நீரில் நொதி தூண்ட அமிழ்த்தி எடுத்துப் பனைப் பாய்களில் வெயிலில் உலர்த்திச் சுருங்கிய கருமிளகாக மாற்றும் தொழில்நுட்பம்.",
    "sources": [
      "Akananuru 2",
      "Kurunthogai 288",
      "Spices Board Black Pepper Production Guide"
    ],
    "content": "---\nslug: technology-milagu-pepper-vine-standards-harvesting-hot-water-scalding-and-sun-curing-technology\ncategory: technology\nname_en: Milagu Pepper-Vine Standards, Harvesting, Hot-Water Scalding & Sun-Curing Technology\nname_ta: மிளகுக் கொடி ஆதார மரம், அறுவடை, வெந்நீர் அமிழ்த்தல் மற்றும் வெயில் உலர்த்தும் தொழில்நுட்பம்\nera: Sangam Era to Modern Era\nyear_start: -300\nyear_end: 2026\nthinai: kurinji\nsummary_en: Traditional cultivation and curing of Piper nigrum in the Western Ghats and Kolli Hills: training perennial vines on live tree standards (Murikku, Jackfruit), climbing bamboo ladders (enip-padikkal) to hand-strip mature green-orange spikes, quick hot-water immersion (scalding at 80°C) to rupture cellular membranes and activate polyphenol oxidase enzymes, followed by open-air sun curing on palm mats until berries turn into wrinkly, pitch-black drupes.\nsummary_ta: கொல்லிமலை மற்றும் மேற்குத் தொடர்ச்சி மலைப் பகுதிகளில் மிளகு சாகுபடி: முருக்கு மற்றும் பலா மரங்களில் கொடி ஏற்றுதல், மூங்கில் ஏணி கொண்டு பழக்கொத்துகளைப் பறித்தல், 80 பாகை வெந்நீரில் நொதி தூண்ட அமிழ்த்தி எடுத்துப் பனைப் பாய்களில் வெயிலில் உலர்த்திச் சுருங்கிய கருமிளகாக மாற்றும் தொழில்நுட்பம்.\nsources:\n  - Akananuru 2\n  - Kurunthogai 288\n  - Spices Board Black Pepper Production Guide\n---\n\n# Milagu Pepper-Vine Standards, Harvesting, Hot-Water Scalding & Sun-Curing Technology\n\nBlack pepper (**Piper nigrum**, Tamil: **மிளகு / Milagu**, historically termed **கறி / Kari** in Sangam literature) is the quintessential indigenous spice of peninsular South India.\n\n### 1. Live Support Standards & Vine Canopy\n- Pepper is a woody perennial climbing vine that requires sturdy living host trees (*aadhaara marangal*).\n- In the rainforests and montane valleys of Kolli Hills and the Chera Western Ghats, cultivators trained vines onto *Erythrina indica* (Kalyana Murukku), *Artocarpus heterophyllus* (Jackfruit / Palaa), and wild figs.\n- The standard trees were pruned annually before the monsoon to provide 40 to 50 percent sunlight penetration, preventing fungal foot-rot (*Phytophthora*) during torrential mountain rains.\n\n### 2. Harvest Timing & Bamboo Ladder Stripping\n- Spikes (*milagu kothu*) bear 50 to 70 drupes. Harvesting begins when 1 or 2 drupes in the spike turn from yellowish-green to bright orange-red.\n- Harvesters climbed tall single-pole notched bamboo ladders (*kazhi eni*) to hand-pick clusters into woven palm-leaf shoulder bags (*kudai*).\n\n### 3. Hot-Water Scalding (*கொதிநீர் அமிழ்த்தல்*)\n- To produce uniform pitch-black drupes, traditional processors developed the hot-water dip:\n  - Whole spikes or threshed berries are placed inside perforated wicker baskets and lowered into boiling water (80-90°C) for 60 to 90 seconds.\n  - Heat shock ruptures the hypodermal cell walls, bringing endogenous **polyphenol oxidase** (o-diphenol oxidase) enzymes into direct contact with phenolic substrates, catalyzing rapid enzymatic browning into dark melanin pigments.\n  - Scalding also cleans fungal spores, accelerates drying speed by half, and produces a glossy, uniform, wrinkly black finish.\n\n### 4. Sun-Curing on Palm Mats (*பாயில் வெயில் உலர்த்தல்*)\n- Scalded berries are immediately spread across clean woven screwpine or palmyra mats elevated on wooden racks.\n- Over 4 to 6 days under bright tropical sunshine, berry moisture plunges from 70 percent to 10-12 percent. The berry shrivels tightly around the hard endocarp seed, forming the classic corrugated surface characteristic of black pepper (*karumilagu*).\n"
  },
  {
    "slug": "technology-milagu-kashayam-decoction-thirikadugu-blending-and-milagu-rasam-pharmacology-technology",
    "file": "technology-milagu-kashayam-decoction-thirikadugu-blending-and-milagu-rasam-pharmacology-technology.md",
    "category": "technology",
    "name_en": "Milagu Kashayam Decoction, Thirikadugu Blending & Milagu Rasam Pharmacology Technology",
    "name_ta": "மிளகுக் கஷாயம், திரிகடுகு கூட்டு மற்றும் மிளகு ரச மருந்தியல் தொழில்நுட்பம்",
    "era": "Sangam Era to Modern Era",
    "year_start": -300,
    "year_end": 2026,
    "thinai": "marutham",
    "summary_en": "The pharmaceutical and culinary preparation of Piper nigrum in Tamil heritage: coarse crushing of black peppercorns to release piperine without volatilizing pinene terpenes, boiling with cumin, garlic, and tamarind water for medicinal Milagu Rasam, and compounding into Thirikadugu (three-pungent triad) to enhance digestive agni and bioabsorption.",
    "summary_ta": "தமிழர் பாரம்பரியத்தில் மிளகின் மருந்தியல் மற்றும் சமையல் தயாரிப்பு முறை: பைப்பரின் வீரியம் வெளிப்படக் கொறகொறப்பாக அரைத்தல், சீரகம், பூண்டு மற்றும் புளித்தண்ணீருடன் கொதிக்கவைத்து மிளகு ரசம் தயாரித்தல் மற்றும் செரிமானத் தீயைத் தூண்டி ஊட்டச்சத்து உறிஞ்சுதலை உயர்த்தும் திரிகடுகுக் கூட்டுத் தொழில்நுட்பம்.",
    "sources": [
      "Agathiyar Vaidya Rathina Churukkam",
      "Siddha Gunapadam: Mooligai Vaguppu",
      "Biochemical Pharmacology of Piperine"
    ],
    "content": "---\nslug: technology-milagu-kashayam-decoction-thirikadugu-blending-and-milagu-rasam-pharmacology-technology\ncategory: technology\nname_en: Milagu Kashayam Decoction, Thirikadugu Blending & Milagu Rasam Pharmacology Technology\nname_ta: மிளகுக் கஷாயம், திரிகடுகு கூட்டு மற்றும் மிளகு ரச மருந்தியல் தொழில்நுட்பம்\nera: Sangam Era to Modern Era\nyear_start: -300\nyear_end: 2026\nthinai: marutham\nsummary_en: The pharmaceutical and culinary preparation of Piper nigrum in Tamil heritage: coarse crushing of black peppercorns to release piperine without volatilizing pinene terpenes, boiling with cumin, garlic, and tamarind water for medicinal Milagu Rasam, and compounding into Thirikadugu (three-pungent triad) to enhance digestive agni and bioabsorption.\nsummary_ta: தமிழர் பாரம்பரியத்தில் மிளகின் மருந்தியல் மற்றும் சமையல் தயாரிப்பு முறை: பைப்பரின் வீரியம் வெளிப்படக் கொறகொறப்பாக அரைத்தல், சீரகம், பூண்டு மற்றும் புளித்தண்ணீருடன் கொதிக்கவைத்து மிளகு ரசம் தயாரித்தல் மற்றும் செரிமானத் தீயைத் தூண்டி ஊட்டச்சத்து உறிஞ்சுதலை உயர்த்தும் திரிகடுகுக் கூட்டுத் தொழில்நுட்பம்.\nsources:\n  - Agathiyar Vaidya Rathina Churukkam\n  - Siddha Gunapadam: Mooligai Vaguppu\n  - Biochemical Pharmacology of Piperine\n---\n\n# Milagu Kashayam Decoction, Thirikadugu Blending & Milagu Rasam Pharmacology Technology\n\nPeppercorn processing for therapy and daily gastronomy exemplifies how Tamil civilizational science married preventative pharmacology with culinary art.\n\n### 1. Coarse Crushing vs Fine Grinding (*கொறகொறப்பு இடிப்பு*)\n- Peppercorns are never pulverized into powdery dust for daily boiling. Rapid pulverization generates frictional heat that volatilizes essential terpenes (phellandrene, caryophyllene, and pinene).\n- Traditional cooks and Siddha practitioners use a heavy granite hand-pestle (*ammikkal* or *kallural*) to fracture peppercorns into coarse splits (*nodukku* / நொடுக்கு). This exposes the crystalline piperine alkaloid while trapping volatile aroma compounds within the lipid core.\n\n### 2. Decoction Thermodynamics of Milagu Rasam (*மிளகு ரசக் காய்ச்சிவடித்தல்*)\n- *Milagu Rasam* (anciently *Milagu-Thanni*, the phonetic ancestor of Anglo-Indian *Mulligatawny*) is a precision medicinal bouillon:\n  - Coarsely crushed pepper is tempered in hot ghee or sesame oil with cumin (*seeragam*), mustard seeds, and crushed raw garlic cloves.\n  - Dilute tamarind extract (*puli-thanni*) or crushed country tomatoes provide an acidic aqueous medium (pH 3.5 to 4.0).\n  - Simmering at sub-boiling temperatures (85-92°C) solubilizes hydrophobic piperine into lipid micellar vesicles, optimizing bioavailability across intestinal enterocytes.\n  - Fresh curry leaves (*karuveppilai*) add antioxidant flavonoids, preventing thermal peroxidation.\n\n### 3. Thirikadugu Synergy (*திரிகடுகுக் கூட்டு*)\n- Formulated as an equal-ratio tripartite dry powder:\n  - Dry Ginger (*Sukku*, 1 part)\n  - Black Pepper (*Milagu*, 1 part)\n  - Long Pepper (*Thippili*, 1 part)\n- In Siddha pharmacology, this triad is the ultimate bio-enhancer (*marundhu yoga-vaahi*). Piperine acts as an intestinal efflux inhibitor, dramatically increasing blood plasma absorption of companion botanical remedies.\n"
  },
  {
    "slug": "artifact-shriveled-black-pepper-drupes-terracotta-steeping-pots-and-granite-ammikal-grinding-stones",
    "file": "artifact-shriveled-black-pepper-drupes-terracotta-steeping-pots-and-granite-ammikal-grinding-stones.md",
    "category": "artifact",
    "name_en": "Shriveled Black Pepper Drupes, Terracotta Steeping Pots & Granite Ammikal Grinding Stones",
    "name_ta": "சுருங்கிய கருமிளகு மணிகள், மண்பாண்ட வெந்நீர்க் கலங்கள் மற்றும் கருங்கல் அம்மிக் குழவிகள்",
    "era": "Sangam Era to Modern Era",
    "year_start": -300,
    "year_end": 2026,
    "thinai": "kurinji",
    "summary_en": "The traditional processing and grinding implements of Tamil pepper culture: spherical shriveled black peppercorn drupes with dense endocarp seeds, large porous terracotta blanching pots used over open hearths, and flat volcanic granite grinding stones (ammikkal) paired with cylindrical rolling mullers.",
    "summary_ta": "தமிழ் மிளகுப் பண்பாட்டின் கருவிகள்: சுருக்கங்கள் நிறைந்த உருண்டைக் கருமிளகு மணிகள், வெந்நீரில் அமிழ்த்தப் பயன்படும் தடித்த சுடுமண் கலங்கள் மற்றும் மிளகு நசுக்கப் பயன்படும் கருங்கல் அம்மி மற்றும் குழவிகள்.",
    "sources": [
      "Pattina-p-palai 185-190",
      "Adichanallur & Kodumanal Excavation Reports",
      "Traditional Tamil Culinary Implements Survey"
    ],
    "content": "---\nslug: artifact-shriveled-black-pepper-drupes-terracotta-steeping-pots-and-granite-ammikal-grinding-stones\ncategory: artifact\nname_en: Shriveled Black Pepper Drupes, Terracotta Steeping Pots & Granite Ammikal Grinding Stones\nname_ta: சுருங்கிய கருமிளகு மணிகள், மண்பாண்ட வெந்நீர்க் கலங்கள் மற்றும் கருங்கல் அம்மிக் குழவிகள்\nera: Sangam Era to Modern Era\nyear_start: -300\nyear_end: 2026\nthinai: kurinji\nsummary_en: The traditional processing and grinding implements of Tamil pepper culture: spherical shriveled black peppercorn drupes with dense endocarp seeds, large porous terracotta blanching pots used over open hearths, and flat volcanic granite grinding stones (ammikkal) paired with cylindrical rolling mullers.\nsummary_ta: தமிழ் மிளகுப் பண்பாட்டின் கருவிகள்: சுருக்கங்கள் நிறைந்த உருண்டைக் கருமிளகு மணிகள், வெந்நீரில் அமிழ்த்தப் பயன்படும் தடித்த சுடுமண் கலங்கள் மற்றும் மிளகு நசுக்கப் பயன்படும் கருங்கல் அம்மி மற்றும் குழவிகள்.\nsources:\n  - Pattina-p-palai 185-190\n  - Adichanallur & Kodumanal Excavation Reports\n  - Traditional Tamil Culinary Implements Survey\n---\n\n# Shriveled Black Pepper Drupes, Terracotta Steeping Pots & Granite Ammikal Grinding Stones\n\nThe material identity of Tamil black pepper spans agricultural harvesting vessels, kitchen grinding stones, and archaeological botanical remains.\n\n### 1. Shriveled Black Pepper Drupes (*சுருங்கிய கருமிளகு மணிகள்*)\n- Physically, the cured drupe measures 4 to 6 mm in diameter with a characteristic rough reticulated black outer pericarp surrounding a hard greyish-white seed kernel containing starch and piperine crystals.\n- Carbonized peppercorns excavated at ancient Red Sea ports (Berenike, Quseir al-Qadim) match Indian *Piper nigrum*, sealed inside Indian coarse earthenware storage jars (*matka*).\n\n### 2. Large Terracotta Blanching Cauldrons (*மிளகு அமிழ்த்தும் பானை*)\n- Hill villages utilized wide-rimmed, heavy earthenware pots set on three-stone mud hearths (*aduppu*) to heat blanching water.\n- Perforated woven cane scoops were lowered into the cauldron, holding 5 to 10 kg of freshly picked green pepper spikes, then lifted and drained before sun-drying.\n\n### 3. Granite Ammikkal and Kuzhavi (*அம்மியும் குழவியும்*)\n- The granite grinding stone (*ammikkal*) is the signature culinary implement of the Tamil home.\n- Carved from dense crystalline Charnockite granite, its flat textured bed allows the cylindrical roller stone (*kuzhavi*) to execute a dual crushing-shearing motion.\n- When dry pepper is rolled across the *ammikkal* with cumin seeds, the abrasive granite grit shears the pericarp without overheating, creating coarse aromatic fragments ideal for temple broths and curries.\n"
  },
  {
    "slug": "artifact-roman-gold-aurei-hoards-burlap-spice-bales-and-musiris-dockyard-steelyard-balances",
    "file": "artifact-roman-gold-aurei-hoards-burlap-spice-bales-and-musiris-dockyard-steelyard-balances.md",
    "category": "artifact",
    "name_en": "Roman Gold Aurei Hoards, Burlap Spice Bales & Musiris Dockyard Steelyard Balances",
    "name_ta": "ரோமானிய பொற்காசுக் குவியல்கள், சணல் மிளகு மூட்டைகள் மற்றும் முசிறித் துறைமுக எடைத் தராசுகள்",
    "era": "Early Historic to Roman Trade Era",
    "year_start": -100,
    "year_end": 400,
    "thinai": "neithal",
    "summary_en": "Archaeological artifacts of the global pepper emporium: vast hoards of Roman imperial gold aurei and denarii (Augustus, Tiberius, Nero) unearthed across Coimbatore and Kerala pass routes, double-stitched coir and jute spice bales, and massive bronze steelyard balances used to weigh black gold at Musiris wharves.",
    "summary_ta": "உலகளாவிய மிளகுப் பேரங்காடியின் தொல்பொருட்கள்: கோவை மற்றும் சேர மலைப்பாதைகளில் கண்டெடுக்கப்பட்ட அகஸ்டஸ்-நீரோ மன்னர்களின் ரோமானிய தங்க நாணயக் குவியல்கள், கயிறு-சணல் மிளகு மூட்டைகள் மற்றும் முசிறித் துறைமுகத்தில் மிளகு எடையிட்ட வெண்கலத் தராசுகள்.",
    "sources": [
      "Muziris Papyrus (SB XVIII 13167, Vienna)",
      "Pliny the Elder: Naturalis Historia Book XII",
      "Coimbatore District Roman Coin Hoards Catalogues"
    ],
    "content": "---\nslug: artifact-roman-gold-aurei-hoards-burlap-spice-bales-and-musiris-dockyard-steelyard-balances\ncategory: artifact\nname_en: Roman Gold Aurei Hoards, Burlap Spice Bales & Musiris Dockyard Steelyard Balances\nname_ta: ரோமானிய பொற்காசுக் குவியல்கள், சணல் மிளகு மூட்டைகள் மற்றும் முசிறித் துறைமுக எடைத் தராசுகள்\nera: Early Historic to Roman Trade Era\nyear_start: -100\nyear_end: 400\nthinai: neithal\nsummary_en: Archaeological artifacts of the global pepper emporium: vast hoards of Roman imperial gold aurei and denarii (Augustus, Tiberius, Nero) unearthed across Coimbatore and Kerala pass routes, double-stitched coir and jute spice bales, and massive bronze steelyard balances used to weigh black gold at Musiris wharves.\nsummary_ta: உலகளாவிய மிளகுப் பேரங்காடியின் தொல்பொருட்கள்: கோவை மற்றும் சேர மலைப்பாதைகளில் கண்டெடுக்கப்பட்ட அகஸ்டஸ்-நீரோ மன்னர்களின் ரோமானிய தங்க நாணயக் குவியல்கள், கயிறு-சணல் மிளகு மூட்டைகள் மற்றும் முசிறித் துறைமுகத்தில் மிளகு எடையிட்ட வெண்கலத் தராசுகள்.\nsources:\n  - Muziris Papyrus (SB XVIII 13167, Vienna)\n  - Pliny the Elder: Naturalis Historia Book XII\n  - Coimbatore District Roman Coin Hoards Catalogues\n---\n\n# Roman Gold Aurei Hoards, Burlap Spice Bales & Musiris Dockyard Steelyard Balances\n\nThe maritime exchange of Indian black pepper generated one of the greatest transfers of metallic bullion in antiquity, leaving tangible numismatic and metrological remains.\n\n### 1. Roman Imperial Gold Aurei Hoards (*ரோமானிய பொற்காசுகள்*)\n- Thousands of Roman gold coins (*aurei*) and silver coins (*denarii*) spanning the Julio-Claudian emperors (Augustus, Tiberius, Caligula, Claudius, Nero) have been excavated across Tamil Nadu and Kerala.\n- Major hoard concentrations at Pollachi, Vellalur, Karur, and Nedumkandam trace the ancient trans-peninsular transit corridor along the Palghat Gap connecting Musiris to Poompuhar.\n- Tamil merchants accepted gold coins primarily by bullion weight, often counter-marking or slashing them to test metallurgical purity.\n\n### 2. Export Spice Bales & Coir Netting (*சணல் மூட்டைகள்*)\n- Black pepper for oceanic export was packed in heavy woven jute or palmyra leaf sacks (*gunny bags* / *gonip-pai*), wrapped in coir rope netting to withstand rough bilge waters during 90-day monsoon sea voyages.\n- The 2nd-century CE **Muziris Papyrus** (preserved in the Vienna National Library) explicitly records maritime consignments of black pepper loaded aboard the Roman ship *Hermapollon*, calculating freight values exceeding millions of sesterces.\n\n### 3. Steelyard Balances & Stone Standards (*முசிறித் துறைமுகத் தராசுகள்*)\n- At port quays, customs officials (*kavalar*) and merchant guilds weighed massive spice sacks using heavy bronze and iron steelyard balances (*thulaa-kole*).\n- Stone standards engraved with guild insignias guaranteed honest measurement before goods were transferred onto river lighters and ocean-going merchantmen (*yavana-kappal*).\n"
  },
  {
    "slug": "concept-piperine-alkaloid-thermo-pungency-vanilloid-receptor-activation-and-bioavailability-enhancement",
    "file": "concept-piperine-alkaloid-thermo-pungency-vanilloid-receptor-activation-and-bioavailability-enhancement.md",
    "category": "concept",
    "name_en": "Piperine Alkaloid Thermo-Pungency, Vanilloid Receptor Activation & Bioavailability Enhancement",
    "name_ta": "பைப்பரின் கார வேதியியல், வெப்ப உணர்வு நரம்புத் தூண்டல் மற்றும் ஊட்டச்சத்து உறிஞ்சுதல் உயர்வு",
    "era": "Sangam Era to Modern Era",
    "year_start": -300,
    "year_end": 2026,
    "thinai": "kurinji",
    "summary_en": "The molecular pharmacology of black pepper: the alkaloid piperine (1-peperoylpiperidine), its activation of TRPV1 vanilloid thermo-receptors eliciting systemic heat sensations and diaphoresis, hepatic glucuronidation inhibition (via CYP3A4 and P-glycoprotein modulation), and the scientific rationale behind Siddha bio-enhancer formulations.",
    "summary_ta": "மிளகின் மூலக்கூறு மருந்தியல்: பைப்பரின் ஆல்கலாய்டு, TRPV1 வெப்ப நரம்பு உணர்வேற்பிகளைத் தூண்டி வியர்வையும் செரிமானச் சூடும் உண்டாக்குதல், கல்லீரல் நொதிகளை மட்டுப்படுத்தி பிற மருந்துகளின் உறிஞ்சுதலை 2000 விழுக்காடு வரை உயர்த்தும் உயிரி-வினை மேம்பாட்டுத் தத்துவம்.",
    "sources": [
      "Planta Medica: Piperine Bioavailability Studies",
      "Critical Reviews in Food Science and Nutrition: Black Pepper",
      "Journal of Ethnopharmacology: Siddha Bioenhancers"
    ],
    "content": "---\nslug: concept-piperine-alkaloid-thermo-pungency-vanilloid-receptor-activation-and-bioavailability-enhancement\ncategory: concept\nname_en: Piperine Alkaloid Thermo-Pungency, Vanilloid Receptor Activation & Bioavailability Enhancement\nname_ta: பைப்பரின் கார வேதியியல், வெப்ப உணர்வு நரம்புத் தூண்டல் மற்றும் ஊட்டச்சத்து உறிஞ்சுதல் உயர்வு\nera: Sangam Era to Modern Era\nyear_start: -300\nyear_end: 2026\nthinai: kurinji\nsummary_en: The molecular pharmacology of black pepper: the alkaloid piperine (1-peperoylpiperidine), its activation of TRPV1 vanilloid thermo-receptors eliciting systemic heat sensations and diaphoresis, hepatic glucuronidation inhibition (via CYP3A4 and P-glycoprotein modulation), and the scientific rationale behind Siddha bio-enhancer formulations.\nsummary_ta: மிளகின் மூலக்கூறு மருந்தியல்: பைப்பரின் ஆல்கலாய்டு, TRPV1 வெப்ப நரம்பு உணர்வேற்பிகளைத் தூண்டி வியர்வையும் செரிமானச் சூடும் உண்டாக்குதல், கல்லீரல் நொதிகளை மட்டுப்படுத்தி பிற மருந்துகளின் உறிஞ்சுதலை 2000 விழுக்காடு வரை உயர்த்தும் உயிரி-வினை மேம்பாட்டுத் தத்துவம்.\nsources:\n  - Planta Medica: Piperine Bioavailability Studies\n  - Critical Reviews in Food Science and Nutrition: Black Pepper\n  - Journal of Ethnopharmacology: Siddha Bioenhancers\n---\n\n# Piperine Alkaloid Thermo-Pungency, Vanilloid Receptor Activation & Bioavailability Enhancement\n\nThe sharp, biting pungency and profound medicinal power of black pepper reside in **Piperine** (trans-trans isomer of 1-piperoylpiperidine), present at 4 to 9 percent concentration in dried berries.\n\n### 1. Neurosensory Thermo-Pungency (TRPV1 Activation)\n- Piperine binds directly to the **transient receptor potential cation channel subfamily V member 1 (TRPV1)** on sensory nerve endings in the tongue, mouth, and stomach.\n- TRPV1 is the identical receptor activated by noxious heat (>43°C). Binding induces calcium influx, signalling intense warmth and stinging pungency without physical tissue burns.\n- This sensory cascade triggers hypothalamic thermoregulation: increased peripheral vasodilation, perspiration (*diaphoresis* / வியர்வை பெருக்குதல்), salivary and gastric secretion, and bronchial mucociliary clearance.\n\n### 2. Hepatic Enzyme Inhibition & Bioenhancement (*மருந்து வீரியப் பெருக்கம்*)\n- In modern pharmacology, piperine is celebrated as the world's premier natural bio-enhancer (*bioavailability enhancer*).\n- Mechanistically, piperine acts upon two crucial biochemical pathways:\n  1. Inhibits **hepatic and intestinal glucuronidation** by suppressing UDP-glucuronosyltransferase.\n  2. Moderates **cytochrome P450 (CYP3A4)** enzymes and inhibits **P-glycoprotein (P-gp)** drug efflux pumps.\n- This prevents first-pass metabolic destruction of co-administered drugs and polyphenols. For example, co-administering piperine with curcumin (turmeric) enhances curcumin bioavailability in human serum by 2,000 percent.\n\n### 3. Ancient Siddha Formulation Genius\n- Long before molecular pharmacology identified CYP3A4 inhibition, Tamil Siddha physicians codified the principle that complex herbal remedies must incorporate *Milagu* or *Thirikadugu* as the carrier (*anupanam* / yoga-vaahi) to \"carry the medicine through the seven bodily tissues\" (*sapta dhatus*).\n"
  },
  {
    "slug": "concept-indo-roman-maritime-black-pepper-yavana-trade-and-gold-bullion-drain-economics",
    "file": "concept-indo-roman-maritime-black-pepper-yavana-trade-and-gold-bullion-drain-economics.md",
    "category": "concept",
    "name_en": "Indo-Roman Maritime Black Pepper Yavana Trade & Gold Bullion Drain Economics",
    "name_ta": "ரோமானிய-இந்தியக் கடல்வழி மிளகு வர்த்தகம் மற்றும் ரோமப் பேரரசின் பொன் வடிகால் பொருளாதாரம்",
    "era": "Early Historic Era",
    "year_start": -100,
    "year_end": 300,
    "thinai": "neithal",
    "summary_en": "The macro-economics of the ancient spice trade: how Roman appetite for black pepper (piper) as a culinary luxury and meat preservative sparked massive seasonal maritime expeditions using Hippalus monsoon winds, culminating in Pliny the Elder's famous lamentation over Rome's hundred million sesterces annual trade deficit to India.",
    "summary_ta": "பண்டைய உலகளாவிய மிளகு வர்த்தகப் பொருளாதாரம்: ரோமானியர்களின் மிளகு மோகமும் இறைச்சிப் பதனிடல் தேவையும், பருவக்காற்று வழிவந்த யவனக் கப்பல்கள் மற்றும் ஆண்டுதோறும் பல கோடி பொற்காசுகள் ரோம் நாட்டிலிருந்து தமிழகத்திற்கு வடிந்தோடியதாக பிளினி எழுதிய வரலாற்றுப் பதிவு.",
    "sources": [
      "Pliny the Elder: Natural History XII.84",
      "Periplus of the Erythraean Sea 56",
      "Roman Imperial Economy & Indian Trade by E.H. Warmington"
    ],
    "content": "---\nslug: concept-indo-roman-maritime-black-pepper-yavana-trade-and-gold-bullion-drain-economics\ncategory: concept\nname_en: Indo-Roman Maritime Black Pepper Yavana Trade & Gold Bullion Drain Economics\nname_ta: ரோமானிய-இந்தியக் கடல்வழி மிளகு வர்த்தகம் மற்றும் ரோமப் பேரரசின் பொன் வடிகால் பொருளாதாரம்\nera: Early Historic Era\nyear_start: -100\nyear_end: 300\nthinai: neithal\nsummary_en: The macro-economics of the ancient spice trade: how Roman appetite for black pepper (piper) as a culinary luxury and meat preservative sparked massive seasonal maritime expeditions using Hippalus monsoon winds, culminating in Pliny the Elder's famous lamentation over Rome's hundred million sesterces annual trade deficit to India.\nsummary_ta: பண்டைய உலகளாவிய மிளகு வர்த்தகப் பொருளாதாரம்: ரோமானியர்களின் மிளகு மோகமும் இறைச்சிப் பதனிடல் தேவையும், பருவக்காற்று வழிவந்த யவனக் கப்பல்கள் மற்றும் ஆண்டுதோறும் பல கோடி பொற்காசுகள் ரோம் நாட்டிலிருந்து தமிழகத்திற்கு வடிந்தோடியதாக பிளினி எழுதிய வரலாற்றுப் பதிவு.\nsources:\n  - Pliny the Elder: Natural History XII.84\n  - Periplus of the Erythraean Sea 56\n  - Roman Imperial Economy & Indian Trade by E.H. Warmington\n---\n\n# Indo-Roman Maritime Black Pepper Yavana Trade & Gold Bullion Drain Economics\n\nDuring the 1st century BCE to the 3rd century CE, black pepper was not merely a seasoning—it was a global currency and geostrategic asset that altered the fiscal solvency of the Roman Empire.\n\n### 1. Roman Culinary Passion & Preservation\n- In Apicius's classical Roman cookbook *De Re Coquinaria*, black pepper appears in more than 70 percent of recipes. Pepper was indispensable for seasoning game, masking salted meats, creating spiced wine (*conditum paradoxum*), and compounding pharmaceutical antidotes (*theriac*).\n- When Alaric the Visigoth besieged Rome in 408 CE, his ransom demand to spare the imperial city included 5,000 pounds of gold, 30,000 pounds of silver, and **3,000 pounds of pepper**.\n\n### 2. Hippalus Monsoon Navigation & Direct Crossing\n- The discovery of direct oceanic sailing utilizing the southwest monsoon winds (*Hippalus*) transformed the spice route from slow coastal hugging to a 40-day deep-sea sprint from the Red Sea ports (Berenike and Myos Hormos) directly to Musiris and Nelcynda in Tamilakam.\n- Fleets of up to 120 massive grain-and-spice freighters set sail annually in July, arriving in southern India by September, loading pepper through winter, and returning on northeast winds in December.\n\n### 3. Pliny's Bullion Drain Lamentation\n- In *Naturalis Historia* (Book VI & XII), Roman naturalist Pliny the Elder decried the relentless fiscal bleed:\n  > *\"By the lowest reckoning, India, Seres and the Arabian peninsula drain from our Empire one hundred million sesterces every year... so dearly do we pay for our luxury and our women!\"*\n- Because Rome produced few manufactured commodities desired in prosperous Tamil ports, Roman merchants settled accounts with solid gold aurei and silver denarii, transforming the Kongu and Chera realms into the largest repository of Roman coinage outside the Mediterranean basin.\n"
  },
  {
    "slug": "concept-siddha-milaguthaali-respiratory-kapha-dispersion-and-antimicrobial-meat-curing-biochemistry",
    "file": "concept-siddha-milaguthaali-respiratory-kapha-dispersion-and-antimicrobial-meat-curing-biochemistry.md",
    "category": "concept",
    "name_en": "Siddha Milaguthaali Respiratory Kapha Dispersion & Antimicrobial Meat Curing Biochemistry",
    "name_ta": "சித்த மிளகுத்தாளி கபக்கரைப்பு, சுவாசப் பாதை மீட்பு மற்றும் இறைச்சி பதனிடல் நுண்ணுயிரியல்",
    "era": "Sangam Era to Modern Era",
    "year_start": -300,
    "year_end": 2026,
    "thinai": "mullai",
    "summary_en": "Siddha medical and culinary chemistry of black pepper: its hot potency (ushna veeryam) liquefying viscous respiratory mucus (kapha), bronchospasm relief, and the food-safety biochemistry of ancient Tamil hunters and cooks rubbing pepper and salt on venison and wild game to inhibit bacterial decay (spoilage bacteria and lipid oxidation).",
    "summary_ta": "சித்த மருத்துவத்தில் மிளகின் வெப்ப வீரியத்தால் நுரையீரல் சளி (ஐயம்/கபம்) கரைதல், சுவாசக் குழாய் விரிவு மற்றும் சங்க கால வேட்டுவர் மிளகையும் உப்பையும் இறைச்சியில் தடவி பாக்டீரியா அழுகலைத் தடுத்துப் பதப்படுத்திய வேதியியல் தத்துவம்.",
    "sources": [
      "Porunararruppadai 100-115",
      "Therayar Thaila Varkka Churukkam",
      "Food Microbiology: Spices as Antimicrobial Agents"
    ],
    "content": "---\nslug: concept-siddha-milaguthaali-respiratory-kapha-dispersion-and-antimicrobial-meat-curing-biochemistry\ncategory: concept\nname_en: Siddha Milaguthaali Respiratory Kapha Dispersion & Antimicrobial Meat Curing Biochemistry\nname_ta: சித்த மிளகுத்தாளி கபக்கரைப்பு, சுவாசப் பாதை மீட்பு மற்றும் இறைச்சி பதனிடல் நுண்ணுயிரியல்\nera: Sangam Era to Modern Era\nyear_start: -300\nyear_end: 2026\nthinai: mullai\nsummary_en: Siddha medical and culinary chemistry of black pepper: its hot potency (ushna veeryam) liquefying viscous respiratory mucus (kapha), bronchospasm relief, and the food-safety biochemistry of ancient Tamil hunters and cooks rubbing pepper and salt on venison and wild game to inhibit bacterial decay (spoilage bacteria and lipid oxidation).\nsummary_ta: சித்த மருத்துவத்தில் மிளகின் வெப்ப வீரியத்தால் நுரையீரல் சளி (ஐயம்/கபம்) கரைதல், சுவாசக் குழாய் விரிவு மற்றும் சங்க கால வேட்டுவர் மிளகையும் உப்பையும் இறைச்சியில் தடவி பாக்டீரியா அழுகலைத் தடுத்துப் பதப்படுத்திய வேதியியல் தத்துவம்.\nsources:\n  - Porunararruppadai 100-115\n  - Therayar Thaila Varkka Churukkam\n  - Food Microbiology: Spices as Antimicrobial Agents\n---\n\n# Siddha Milaguthaali Respiratory Kapha Dispersion & Antimicrobial Meat Curing Biochemistry\n\nBlack pepper exemplifies the integration of therapeutic respiration relief and food preservation chemistry in ancient Tamil pastoral (*Mullai*) and hill (*Kurinji*) cultures.\n\n### 1. Respiratory Kapha Dispersion (*கபக் கரைப்பு*)\n- In Siddha nosology, chronic cough (*irumal*), bronchial asthma (*eezhai*), and chest congestion are caused by vitiated **Kapha** (sluggish, cold, unctuous humor).\n- Peppercorns possess intense heating potency (*ushna veeryam*) and pungent post-digestive taste (*katu vipaka*).\n- Inhaling the fumes of crushed pepper placed on burning cow-dung coals (*milagu pukai*) or drinking *Milaguthaali* (pepper infused in goat-milk whey or honey) stimulates respiratory cilia and liquefies hardened phlegm, allowing rapid expectoration.\n\n### 2. Antimicrobial Meat Curing (*இறைச்சிப் பதனிடல்*)\n- Sangam literature (*Porunararruppadai* and *Perumpanarruppadai*) vividly describes hunters roasting fat skewered venison and wild boar (*aan-thadi*) seasoned heavily with crushed black pepper (*karimilagu*) and sea salt.\n- In tropical heat without refrigeration, raw meat spoils within hours due to bacterial proliferation (*Pseudomonas*, *Enterobacteriaceae*) and oxidative rancidity of lipids.\n- Piperine combined with pepper essential oils (beta-caryophyllene, limonene) exerts potent bactericidal activity against food-borne pathogens by disrupting microbial cell membranes, while natural polyphenols prevent lipid peroxidation, extending meat edibility for days during long forest journeys.\n"
  },
  {
    "slug": "institution-ayyavole-500-and-manigramam-merchant-guilds-in-western-ghats-pepper-trade",
    "file": "institution-ayyavole-500-and-manigramam-merchant-guilds-in-western-ghats-pepper-trade.md",
    "category": "institution",
    "name_en": "Ayyavole 500 & Manigramam Merchant Guilds in Western Ghats Pepper Trade",
    "name_ta": "ஐந்நூற்றுவர் மற்றும் மணிக்கிராம வணிகக் கூட்டமைப்புகளின் மேற்குத் தொடர்ச்சி மலை மிளகு வர்த்தகம்",
    "era": "Medieval Chola & Pandya Era",
    "year_start": 850,
    "year_end": 1300,
    "thinai": "mullai",
    "summary_en": "The corporate merchant guilds of medieval South India: the Ainnurruvar (Ayyavole 500, Disai-Aayirathu-Ainnurruvar) and Manigramam trade corporations controlling the collection of black pepper along Western Ghats mountain passes, protecting pack-bullion caravans with armed mercenary regiments (Velaikkarar), and negotiating pepper tax charters with Chola imperial administrators.",
    "summary_ta": "இடைக்காலத் தென்னிந்தியாவின் திசை ஆயிரத்து ஐந்நூற்றுவர் மற்றும் மணிக்கிராம வணிகக் கூட்டமைப்புகள்: மேற்குத் தொடர்ச்சி மலைப்பாதைகளில் மிளகு சேகரித்தல், வேளைக்காரப் படைகளுடன் வணிகக் கூட்டுகளைப் பாதுகாத்தல் மற்றும் சோழ-பாண்டிய அரசர்களுடன் சுங்க வரி ஒப்பந்தங்கள் செய்தல்.",
    "sources": [
      "Tiruvalangadu Copperplates of Rajendra Chola",
      "Barus Tamil Inscription (North Sumatra, 1088 CE)",
      "Epigraphia Carnatica & South Indian Inscriptions"
    ],
    "content": "---\nslug: institution-ayyavole-500-and-manigramam-merchant-guilds-in-western-ghats-pepper-trade\ncategory: institution\nname_en: Ayyavole 500 & Manigramam Merchant Guilds in Western Ghats Pepper Trade\nname_ta: ஐந்நூற்றுவர் மற்றும் மணிக்கிராம வணிகக் கூட்டமைப்புகளின் மேற்குத் தொடர்ச்சி மலை மிளகு வர்த்தகம்\nera: Medieval Chola & Pandya Era\nyear_start: 850\nyear_end: 1300\nthinai: mullai\nsummary_en: The corporate merchant guilds of medieval South India: the Ainnurruvar (Ayyavole 500, Disai-Aayirathu-Ainnurruvar) and Manigramam trade corporations controlling the collection of black pepper along Western Ghats mountain passes, protecting pack-bullion caravans with armed mercenary regiments (Velaikkarar), and negotiating pepper tax charters with Chola imperial administrators.\nsummary_ta: இடைக்காலத் தென்னிந்தியாவின் திசை ஆயிரத்து ஐந்நூற்றுவர் மற்றும் மணிக்கிராம வணிகக் கூட்டமைப்புகள்: மேற்குத் தொடர்ச்சி மலைப்பாதைகளில் மிளகு சேகரித்தல், வேளைக்காரப் படைகளுடன் வணிகக் கூட்டுகளைப் பாதுகாத்தல் மற்றும் சோழ-பாண்டிய அரசர்களுடன் சுங்க வரி ஒப்பந்தங்கள் செய்தல்.\nsources:\n  - Tiruvalangadu Copperplates of Rajendra Chola\n  - Barus Tamil Inscription (North Sumatra, 1088 CE)\n  - Epigraphia Carnatica & South Indian Inscriptions\n---\n\n# Ayyavole 500 & Manigramam Merchant Guilds in Western Ghats Pepper Trade\n\nDuring the imperial Chola and Pandya epochs, the procurement and transcontinental distribution of black pepper were organized by sophisticated supra-regional commercial corporations.\n\n### 1. Guild Structure: Ainnurruvar & Manigramam\n- The **Ainnurruvar** (*Disai-Aayirathu-Ainnurruvar* / Five Hundred of the Thousand Directions) and the **Manigramam** were autonomous chartered merchant confederations.\n- Guild members hailed from multiple regional communities (Chettis, Pillais, and Vanigars) and maintained permanent lodges (*eri-veera-pattinam*) along vital spice crossroads.\n\n### 2. Armed Caravans & Pass Defenses\n- Crossing the rugged forested passes of the Western Ghats (Anamalai, Palghat Gap, and Kolli slopes) exposed cargo to banditry.\n- The guilds maintained their own sworn private mercenary forces (*Velaikkarar* and *Bhoomi-puthrar*) equipped with swords, composite bows, and wardrums.\n- Caravans consisted of hundreds of pack bullocks (*pothi-maadu*) bearing branded jute bales of black pepper, travelling under the blue-and-gold double-serpent guild banner.\n\n### 3. Trans-Oceanic Guild Franchises\n- The guilds did not stop at Indian shores. Their maritime fleets carried pepper across the Bay of Bengal to Sri Vijaya (Sumatra), Malacca, and southern China (Guangzhou / Quanzhou).\n- The famous **Barus Tamil Inscription of 1088 CE** discovered in western Sumatra records the commercial presence of the *Five Hundred of the Thousand Directions* settling accounts in local gold and pepper marts.\n"
  },
  {
    "slug": "place-kolli-hills-ancient-milagu-black-pepper-and-spicery-haven",
    "file": "place-kolli-hills-ancient-milagu-black-pepper-and-spicery-haven.md",
    "category": "place",
    "name_en": "Kolli Hills: Ancient Milagu Black Pepper & Spicery Haven",
    "name_ta": "கொல்லிமலை: பழங்காலக் கருமிளகு மற்றும் நறுமணச் சரக்குப் பெருநிலம்",
    "era": "Sangam Era to Modern Era",
    "year_start": -300,
    "year_end": 2026,
    "thinai": "kurinji",
    "summary_en": "The rugged montane massif of Kolli Hills (Kolli Malai, Namakkal district, Tamil Nadu): ancient stronghold of King Valvil Ori, famed for high-piperine indigenous black pepper cultivars thriving on steep misty slopes at 1,000 to 1,300 metres elevation.",
    "summary_ta": "வல்வில் ஓரியின் ஆட்சிக்குட்பட்ட கொல்லிமலை (நாமக்கல் மாவட்டம்): 1,000 முதல் 1,300 மீட்டர் உயரத்தில் அடர்ந்த பனி படர்ந்த மலைச்சரிவுகளில் விளையும் அதியுயர் பைப்பரின் கொண்ட பாரம்பரியக் கருமிளகின் புகழ்பெற்ற மலைத்தளம்.",
    "sources": [
      "Purananuru 158 (Vanparanar on Valvil Ori)",
      "Sirupanarruppadai 110",
      "Namakkal District Archaeological Gazettes"
    ],
    "content": "---\nslug: place-kolli-hills-ancient-milagu-black-pepper-and-spicery-haven\ncategory: place\nname_en: Kolli Hills: Ancient Milagu Black Pepper & Spicery Haven\nname_ta: கொல்லிமலை: பழங்காலக் கருமிளகு மற்றும் நறுமணச் சரக்குப் பெருநிலம்\nera: Sangam Era to Modern Era\nyear_start: -300\nyear_end: 2026\nthinai: kurinji\nsummary_en: The rugged montane massif of Kolli Hills (Kolli Malai, Namakkal district, Tamil Nadu): ancient stronghold of King Valvil Ori, famed for high-piperine indigenous black pepper cultivars thriving on steep misty slopes at 1,000 to 1,300 metres elevation.\nsummary_ta: வல்வில் ஓரியின் ஆட்சிக்குட்பட்ட கொல்லிமலை (நாமக்கல் மாவட்டம்): 1,000 முதல் 1,300 மீட்டர் உயரத்தில் அடர்ந்த பனி படர்ந்த மலைச்சரிவுகளில் விளையும் அதியுயர் பைப்பரின் கொண்ட பாரம்பரியக் கருமிளகின் புகழ்பெற்ற மலைத்தளம்.\nsources:\n  - Purananuru 158 (Vanparanar on Valvil Ori)\n  - Sirupanarruppadai 110\n  - Namakkal District Archaeological Gazettes\n---\n\n# Kolli Hills: Ancient Milagu Black Pepper & Spicery Haven\n\n**Coordinates:** `11.2485° N, 78.3389° E`  \n**Elevation:** 1,000 to 1,300 metres above MSL  \n**Landscape Ecosystem:** Montane evergreen and deciduous forests (*Kurinji thinai*)  \n**Modern District:** Namakkal District, Tamil Nadu  \n\n### 1. Sacred Geography & Sangam Lineage\n- Kolli Hills (*Kolli Malai*) is immortalized in Sangam poetry as the realm of **Valvil Ori** (வல்வில் ஓரி), one of the Seven Great Patrons (*Kadai Ezhu Vallalgal*), famed for shooting an arrow that pierced through an elephant, tiger, deer, and boar.\n- Classical bards lauded the hills for their perennial mountain cascades (such as Agaya Gangai), deep gorges, and cloud-capped forests rich in wild pepper vines (*அடுக்கத்து விளைந்த மிளகு*).\n\n### 2. High-Piperine Montane Agroforestry\n- Kolli Hills pepper is recognized for its intense intrinsic heat, boasting piperine concentrations reaching 5 to 7 percent due to rich lateritic soils, high solar UV radiation at elevation, and abundant subtropical rainfall.\n- Indigenous Malayali tribal farmers have cultivated heirloom varieties for generations, intercropping pepper with coffee, silver oak, and jackfruit trees.\n\n### 3. Spice Convergence & Heritage\n- Kolli Hills commands pass routes linking the Cauvery river plains with the Salem-Kongu upland corridors.\n- Ancient spice trails radiated down from the 70 hairpin bends toward the inland exchange marts of Karur and Musiri on the Cauvery, feeding the trans-peninsular spice flow to the Coromandel coast.\n"
  },
  {
    "slug": "text-sangam-akanannuru-and-periplus-maris-erythraei-records-on-pepper-fleets-and-tribute",
    "file": "text-sangam-akanannuru-and-periplus-maris-erythraei-records-on-pepper-fleets-and-tribute.md",
    "category": "text",
    "name_en": "Sangam Akananuru & Periplus Maris Erythraei Records on Pepper Fleets and Tribute",
    "name_ta": "அகநானூறு மற்றும் பெரிப்ளூஸ் காட்டும் யவனக் கப்பல்கள் மற்றும் மிளகு வணிக ஆவணங்கள்",
    "era": "Early Historic Era",
    "year_start": -100,
    "year_end": 200,
    "thinai": "neithal",
    "summary_en": "Comparative literary and documentary texts illustrating the magnitude of early historic black pepper trade: Akananuru 149 portraying swift Yavana ships churning white foam to exchange gold for sacks of black pepper at Musiris, synchronized with Greek navigational directives in the Periplus of the Erythraean Sea.",
    "summary_ta": "பண்டைய மிளகு வர்த்தகத்தின் பிரம்மாண்டத்தை விளக்கும் அகநானூறு 149-ஆம் பாடல் (யவனர் தந்த வினைமாண் நன்கலம் பொன்னொடு வந்து கறியொடு பெயரும்) மற்றும் கிரேக்க மாலுமியின் பெரிப்ளூஸ் கடற்பயண வழிகாட்டி ஆவணங்களின் வரலாற்றுப் பதிவு.",
    "sources": [
      "Akananuru 149 (Erukkatoor Thayan Kannanar)",
      "Periplus Maris Erythraei Sections 54-57",
      "Muziris Papyrus Contract Clauses"
    ],
    "content": "---\nslug: text-sangam-akanannuru-and-periplus-maris-erythraei-records-on-pepper-fleets-and-tribute\ncategory: text\nname_en: Sangam Akananuru & Periplus Maris Erythraei Records on Pepper Fleets and Tribute\nname_ta: அகநானூறு மற்றும் பெரிப்ளூஸ் காட்டும் யவனக் கப்பல்கள் மற்றும் மிளகு வணிக ஆவணங்கள்\nera: Early Historic Era\nyear_start: -100\nyear_end: 200\nthinai: neithal\nsummary_en: Comparative literary and documentary texts illustrating the magnitude of early historic black pepper trade: Akananuru 149 portraying swift Yavana ships churning white foam to exchange gold for sacks of black pepper at Musiris, synchronized with Greek navigational directives in the Periplus of the Erythraean Sea.\nsummary_ta: பண்டைய மிளகு வர்த்தகத்தின் பிரம்மாண்டத்தை விளக்கும் அகநானூறு 149-ஆம் பாடல் (யவனர் தந்த வினைமாண் நன்கலம் பொன்னொடு வந்து கறியொடு பெயரும்) மற்றும் கிரேக்க மாலுமியின் பெரிப்ளூஸ் கடற்பயண வழிகாட்டி ஆவணங்களின் வரலாற்றுப் பதிவு.\nsources:\n  - Akananuru 149 (Erukkatoor Thayan Kannanar)\n  - Periplus Maris Erythraei Sections 54-57\n  - Muziris Papyrus Contract Clauses\n---\n\n# Sangam Akananuru & Periplus Maris Erythraei Records on Pepper Fleets and Tribute\n\nThe global prestige of Indian black pepper is validated by an extraordinary concordance between indigenous Tamil Sangam poetry and Greco-Roman maritime manuals.\n\n### 1. Akananuru 149: The Golden Exchange\n- In *Akananuru* 149, the classical poet Erukkatoor Thayan Kannanar describes the bustling port of Musiris under the Chera sovereigns:\n  > *\"யவனர் தந்த வினைமாண் நன்கலம்  \n  பொன்னொடு வந்து கறியொடு பெயரும்  \n  வளங்கெழு முசிறி...\"*  \n  *(Musiris of surging wealth, where the masterfully crafted ships of the Yavanas arrive laden with glittering gold and depart bearing heavy cargoes of pungent black pepper).*\n- Here, black pepper is designated by its Sangam name **கறி (Kari)**, the root term for curried and spiced preparations.\n\n### 2. Periplus Maris Erythraei (c. 50-70 CE)\n- The anonymous Alexandrian navigator's logbook provides specific logistical intelligence for merchant captains:\n  > *\"Musiris and Nelcynda, which are of leading importance... they send large ships there on account of the great quantity and bulk of pepper (*piper*) and malabathrum.\"*\n- Section 56 details how pepper was brought down from the mountains (*Cottonara* / Kotta-nadu district) to river estuaries in country canoes (*dugouts*) before being transferred onto ocean freighters anchored in deep roadsteads.\n\n### 3. The Muziris Papyrus (Vienna Papyrus)\n- Discovered in Egypt, this mid-2nd century CE legal document contains a maritime loan contract and cargo inventory for the ship *Hermapollon*.\n- The manifest records **nearly 1,000 sacks of black pepper** valued at 130 talents of silver, alongside Gangetic spikenard and elephant ivory, demonstrating the colossal capital deployed in the pepper trade.\n"
  }
]

EDGES = [
  [
    "technology-milagu-pepper-vine-standards-harvesting-hot-water-scalding-and-sun-curing-technology",
    "located_in",
    "place-kolli-hills-ancient-milagu-black-pepper-and-spicery-haven",
    "material_culture",
    "Sangam Era to Modern Era",
    "Kolli Hills is the ancient highland haven for pepper vine standards and sun curing",
    "Purananuru 158"
  ],
  [
    "technology-milagu-pepper-vine-standards-harvesting-hot-water-scalding-and-sun-curing-technology",
    "utilizes_artifact",
    "artifact-shriveled-black-pepper-drupes-terracotta-steeping-pots-and-granite-ammikal-grinding-stones",
    "material_culture",
    "Sangam Era to Modern Era",
    "Hot water blanching pots and sun-drying mats create shriveled black pepper drupes",
    "Spices Board Manuals"
  ],
  [
    "technology-milagu-kashayam-decoction-thirikadugu-blending-and-milagu-rasam-pharmacology-technology",
    "applies_concept",
    "concept-piperine-alkaloid-thermo-pungency-vanilloid-receptor-activation-and-bioavailability-enhancement",
    "material_culture",
    "Sangam Era to Modern Era",
    "Milagu decoction and rasam release piperine to activate TRPV1 and enhance bioavailability",
    "Siddha Gunapadam"
  ],
  [
    "technology-milagu-kashayam-decoction-thirikadugu-blending-and-milagu-rasam-pharmacology-technology",
    "utilizes_artifact",
    "artifact-shriveled-black-pepper-drupes-terracotta-steeping-pots-and-granite-ammikal-grinding-stones",
    "material_culture",
    "Sangam Era to Modern Era",
    "Granite ammikkal grinding stones crush peppercorns for medicinal kashayam and rasam",
    "Traditional Tamil Kitchen Survey"
  ],
  [
    "concept-piperine-alkaloid-thermo-pungency-vanilloid-receptor-activation-and-bioavailability-enhancement",
    "embodies_concept",
    "concept-siddha-milaguthaali-respiratory-kapha-dispersion-and-antimicrobial-meat-curing-biochemistry",
    "material_culture",
    "Sangam Era to Modern Era",
    "Piperine thermo-pungency directly drives respiratory kapha liquefaction and meat curing",
    "Food Microbiology"
  ],
  [
    "concept-indo-roman-maritime-black-pepper-yavana-trade-and-gold-bullion-drain-economics",
    "documented_in",
    "text-sangam-akanannuru-and-periplus-maris-erythraei-records-on-pepper-fleets-and-tribute",
    "material_culture",
    "Early Historic Era",
    "Akananuru 149 and Periplus document the Roman gold bullion drain for black pepper",
    "Akananuru 149"
  ],
  [
    "concept-indo-roman-maritime-black-pepper-yavana-trade-and-gold-bullion-drain-economics",
    "utilizes_artifact",
    "artifact-roman-gold-aurei-hoards-burlap-spice-bales-and-musiris-dockyard-steelyard-balances",
    "material_culture",
    "Early Historic Era",
    "Yavana spice trade deposited vast hoards of Roman gold aurei in exchange for pepper bales",
    "Muziris Papyrus"
  ],
  [
    "institution-ayyavole-500-and-manigramam-merchant-guilds-in-western-ghats-pepper-trade",
    "governs_place",
    "place-kolli-hills-ancient-milagu-black-pepper-and-spicery-haven",
    "material_culture",
    "Medieval Era",
    "Medieval merchant guilds operated caravan trade outposts across Kolli Hills passes",
    "South Indian Inscriptions"
  ],
  [
    "institution-ayyavole-500-and-manigramam-merchant-guilds-in-western-ghats-pepper-trade",
    "organizes_practice",
    "technology-milagu-pepper-vine-standards-harvesting-hot-water-scalding-and-sun-curing-technology",
    "material_culture",
    "Medieval Era",
    "Merchant guilds standardized weights and quality control for cured black pepper",
    "Tiruvalangadu Plates"
  ],
  [
    "concept-siddha-milaguthaali-respiratory-kapha-dispersion-and-antimicrobial-meat-curing-biochemistry",
    "documented_in",
    "text-sangam-akanannuru-and-periplus-maris-erythraei-records-on-pepper-fleets-and-tribute",
    "material_culture",
    "Sangam Era",
    "Porunararruppadai and Sangam poems record pepper meat rubs and respiratory cures",
    "Porunararruppadai"
  ]
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=== Phase 1: Markdown Dossiers ===")
    for d in DOSSIERS:
        cat_dir = os.path.join(DOSSIER_DIR, category_dir(d["category"]))
        os.makedirs(cat_dir, exist_ok=True)
        filepath = os.path.join(cat_dir, d["file"])
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        print(f"Wrote dossier: {filepath}")

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("=== Phase 2: Lore Nodes Upsert ===")
    for d in DOSSIERS:
        props = json.dumps({"category": d["category"], "canonical_file": d["file"]})
        cur.execute("""
            INSERT INTO lore_nodes (slug, node_type, name_en, name_ta, era, year_start, year_end, thinai, summary_en, summary_ta, sources, layer, properties)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (slug) DO UPDATE SET
                node_type = EXCLUDED.node_type,
                name_en = EXCLUDED.name_en,
                name_ta = EXCLUDED.name_ta,
                era = EXCLUDED.era,
                year_start = EXCLUDED.year_start,
                year_end = EXCLUDED.year_end,
                thinai = EXCLUDED.thinai,
                summary_en = EXCLUDED.summary_en,
                summary_ta = EXCLUDED.summary_ta,
                sources = EXCLUDED.sources,
                layer = EXCLUDED.layer,
                properties = EXCLUDED.properties;
        """, (
            d["slug"], d["category"], d["name_en"], d["name_ta"], d["era"],
            d["year_start"], d["year_end"], d["thinai"], d["summary_en"],
            d["summary_ta"], d["sources"], "material_culture", props
        ))
        print(f"Upserted node: {d['slug']}")
    conn.commit()

    print("=== Phase 3: Lore Edges Insert ===")
    for edge in EDGES:
        src, rel, tgt, layer, era, desc, ev = edge
        cur.execute("""
            SELECT 1 FROM lore_edges
            WHERE source_slug = %s AND relation_type = %s AND target_slug = %s
        """, (src, rel, tgt))
        if cur.fetchone() is None:
            cur.execute("""
                INSERT INTO lore_edges (source_slug, relation_type, target_slug, layer, era, description, evidence_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (src, rel, tgt, layer, era, desc, ev))
            print(f"Inserted edge: {src} -> {tgt} ({rel})")
        else:
            print(f"Edge exists: {src} -> {tgt} ({rel})")
    conn.commit()

    print("=== Phase 4: RAG Chunks Embedding ===")
    for d in DOSSIERS:
        title = d["name_en"]
        slug = d["slug"]
        cur.execute("DELETE FROM rag_chunks WHERE node_slug = %s", (slug,))

        text_en = d["summary_en"] + " " + d["content"][:800]
        emb_en = get_embedding(text_en)
        cur.execute("""
            INSERT INTO rag_chunks (node_slug, shelf, language, title, content, source_ref, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (slug, d["category"], "en", title + " (Overview)", text_en, d["sources"][0] if d["sources"] else "Oral Tradition", emb_en))

        text_ta = d["summary_ta"] + " " + d["name_ta"]
        emb_ta = get_embedding(text_ta)
        cur.execute("""
            INSERT INTO rag_chunks (node_slug, shelf, language, title, content, source_ref, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (slug, d["category"], "ta", d["name_ta"] + " (கண்ணோட்டம்)", text_ta, d["sources"][0] if d["sources"] else "Oral Tradition", emb_ta))
        print(f"Embedded 2 chunks for: {slug}")
    conn.commit()

    cur.close()
    conn.close()
    print("=== Harvester Complete! ===")

if __name__ == "__main__":
    main()
