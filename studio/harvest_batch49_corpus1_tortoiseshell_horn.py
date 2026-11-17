#!/usr/bin/env python3
"""
Harvester: Batch 49 - Ancient Tamil Tortoiseshell, Horn & Mother-of-Pearl Inlay Craft, Comb Sawing & Coastal Lapidary
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

# The knowledge tree uses real English plurals ("technologies", not "technologys").
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
        "slug": "text-periplus-and-sangam-corpus-on-aamai-odu-tortoiseshell-and-seeppu-combs",
        "category": "text",
        "file": "text-periplus-and-sangam-corpus-on-aamai-odu-tortoiseshell-and-seeppu-combs.md",
        "name_en": "Periplus Maris Erythraei & Sangam Corpus on Aamai-Odu Tortoiseshell & Seeppu Combs",
        "name_ta": "பெரிப்ளஸ் மற்றும் சங்க இலக்கியங்களில் ஆமையோடு, மாட்டுக் கொம்பு மற்றும் ஈர்வலிச் சீப்பு",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "neithal",
        "summary_en": "Classical attestations in the Periplus Maris Erythraei and Sangam poems (Akananuru, Kalittokai, Porunararruppadai) documenting the export of mottled Gulf of Mannar tortoiseshell (chelone / aamai-odu), buffalo horn (kombu), and finely sawn grooming combs (eervali / seeppu).",
        "summary_ta": "பெரிப்ளஸ் கடற்பயண நூல் மற்றும் அகநானூறு, கலித்தொகை, பொருநராற்றுப்படை ஆகிய சங்க இலக்கியங்களில் மன்னார் வளைகுடா ஆமையோடு, எருமைக் கொம்பு மற்றும் ஈர்வலிச் சீப்புகள் பற்றிய குறிப்புகள்.",
        "sources": [
            "Periplus Maris Erythraei",
            "Akananuru",
            "Kalittokai",
            "Porunararruppadai"
        ],
        "content": "# Periplus & Sangam Corpus on Aamai-Odu Tortoiseshell & Seeppu Combs\n\nBoth Graeco-Roman maritime manuals and classical Tamil *Sangam* poetry highlight the Gulf of Mannar and Palk Strait as a premier source of translucent tortoiseshell (*aamai-odu* / *chelone*), polished horn (*kombu*), and mother-of-pearl (*muthu-chippi*):\n\n**Literary & Historical Attestations:**\n- **Periplus Maris Erythraei**: The 1st-century CE Alexandrian merchant guide explicitly notes that the finest mottled tortoiseshell (*chelone*) in the Indian Ocean was harvested in the waters between the Pandya coast (Colchi/Korkai and the Argalu/Rameswaram–Kilakarai reef chain) and Taprobane (Sri Lanka), shipped westward to Roman Egypt for luxury furniture veneer and hairpins.\n- **Akananuru, Kalittokai & Porunararruppadai**: Sangam verses describe the convex carapace of the turtle (*aamai-odu*), the glossy black curvature of water-buffalo horns (*erumai-kombu*), and women parting their fragrant oiled tresses with fine-toothed combs (*eervali* and *seeppu*)."
    },
    {
        "slug": "concept-thermoplastic-keratin-polymer-softening-and-autogenous-thermal-scute-welding",
        "category": "concept",
        "file": "concept-thermoplastic-keratin-polymer-softening-and-autogenous-thermal-scute-welding.md",
        "name_en": "Thermoplastic Keratin Polymer Physics & Autogenous Thermal Scute Welding (110°C–130°C)",
        "name_ta": "கொம்பு மற்றும் ஆமையோட்டின் கெரட்டின் வெப்ப நெகிழ்வு இயற்பியலும் பசையற்ற வெப்பப் பிணைப்பும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Materials science of natural keratin polymers in water-buffalo horn (kombu) and historical marine scutes: softening cross-linked disulfide and hydrogen bonds in boiling brine or oil at 110°C–130°C to flatten curved cylinders and autogenously weld overlapping plates under pressure without glue.",
        "summary_ta": "எருமைக் கொம்பு மற்றும் ஆமையோட்டில் உள்ள கெரட்டின் புரத இழைகளை 110°C–130°C வெப்ப நீராவி அல்லது எண்ணெயில் இளக்கித் தட்டையாக்குவது மற்றும் பசையின்றி அழுத்தி ஒட்டும் பொருள் அறிவியல்.",
        "sources": [
            "Materials Science of Natural Keratin Composites",
            "Traditional Horn and Shell Craft of Madras Presidency",
            "Indian Museum Art-Manufactures Compendia"
        ],
        "content": "# Thermoplastic Keratin Physics & Autogenous Thermal Welding\n\nUnlike bone or ivory (which are rigid mineralized calcium phosphate matrices that char or crack when bent), horn (*kombu*) and carapace scutes are **natural thermoplastic alpha- and beta-keratin polymers**:\n\n**Polymer & Thermal Principles:**\n- **Glass Transition & Disulfide Mobility (110°C–130°C)**: When immersed in boiling salted water, steam, or heated sesame/coconut oil between $110^\\circ\\text{C}$ and $130^\\circ\\text{C}$, water molecules plasticize the amorphous keratin matrix and temporarily relax inter-chain hydrogen and cysteine disulfide bonds. A hollow conical horn or arched scute becomes leathery and malleable.\n- **Autogenous Thermal Fusion (Glue-Free Welding)**: When two freshly scraped, bevel-edged keratin plates are heated to ~125°C and squeezed tightly between hot iron tongs or wooden screw-blocks dipped in boiling water, the softened keratin chains inter-diffuse across the interface. Upon cooling under pressure, the two pieces fuse into a single seamless, optically continuous sheet of arbitrary thickness—a property impossible in bone or wood."
    },
    {
        "slug": "concept-anti-static-keratin-hair-tribology-and-eervali-fine-tooth-comb-biomechanics",
        "category": "concept",
        "file": "concept-anti-static-keratin-hair-tribology-and-eervali-fine-tooth-comb-biomechanics.md",
        "name_en": "Anti-Static Keratin Hair Tribology & Eervali Double-Edged Lice-Comb Biomechanics",
        "name_ta": "நிலைமின்சாரம் தவிர்க்கும் கெரட்டின் சீப்பு உராய்வியலும் ஈர்வலி இருபக்கச் சீப்பின் நுண் பொறியியலும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Tribological and hygienic principles of buffalo-horn combs (maattu-kombu seeppu / eervali): identical keratin triboelectric potential preventing hair static and cuticle stripping, natural micro-porosity distributing herbal scalp oils, and sub-millimetre tooth pitch trapping nits.",
        "summary_ta": "மாட்டுக் கொம்புச் சீப்பு மற்றும் ஈர்வலியின் அறிவியல்: தலைமுடியும் கொம்பும் ஒரே கெரட்டின் புரதத்தால் ஆனதால் நிலைமின்சாரம் (Static Electricity) ஏற்படாமல் தடுத்தல், மூலிகை எண்ணெயைச் சமமாகப் பரப்புதல் மற்றும் ஈர்-பேன் நீக்குதல்.",
        "sources": [
            "Siddha Hygiene and Dinacharya Manuals",
            "Tribology of Keratin Fibers",
            "Ethnography of Tamil Personal Grooming Implements"
        ],
        "content": "# Anti-Static Keratin Tribology & Eervali Comb Biomechanics\n\nTraditional Tamil households and Siddha physicians strongly preferred carved water-buffalo horn combs (*maattu-kombu seeppu* and *eervali*) over metal or synthetic combs for daily hair care:\n\n**Tribological & Hygienic Advantages:**\n- **Zero Triboelectric Static**: Because human hair shafts and buffalo horn share the exact same **keratin protein composition**, drawing a horn comb through dry hair lies at zero differential on the triboelectric series—generating no static charge, frizz, or cuticle scale lifting.\n- **Sebum & Herbal Oil Conditioning**: Polished horn possesses microscopic fibrous channels that absorb excess scalp sebum and evenly distribute medicated coconut or gingelly oil (*thaali-ennai*) from root to tip without scraping the scalp skin.\n- **Eervali Sub-Millimetre Nit Geometry**: The double-sided *eervali* comb features 35 to 45 ultra-fine, bevel-tapered teeth per inch; the inter-tooth gap (0.2–0.3 mm) lets individual hair shafts pass while mechanically stripping lice (*pean*) and cemented nit eggs (*eer*)."
    },
    {
        "slug": "technology-horn-and-scute-steam-flattening-iron-clamp-pressing-and-thermal-lamination",
        "category": "technology",
        "file": "technology-horn-and-scute-steam-flattening-iron-clamp-pressing-and-thermal-lamination.md",
        "name_en": "Horn Slitting, Oil-Bath Roasting, Wedge-Press Flattening & Rottenstone Mirror Polishing",
        "name_ta": "கொம்பு அறுப்பு, எண்ணெய் வெப்பமூட்டல், ஆப்பு அச்சுத் தட்டையாக்கல் மற்றும் பளபளப்பூட்டும் தொழில்நுட்பம்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Workshop sequence of transforming hollow curved buffalo horns into flat translucent sheets: sawing off solid tips for lathe turning, spiral-slitting the hollow cylinder, roasting over charcoal and sesame oil, flattening in wooden wedge-presses, and buffing with charcoal and leaf ash.",
        "summary_ta": "வளைந்த எருமைக் கொம்பை நீளவாக்கில் பிளந்து, நல்லெண்ணெய் தடவிக் கனலில் வாட்டி, மர ஆப்பு அச்சில் வைத்துத் தட்டையாக்கி, கரித்தூள் மற்றும் தேங்காய் எண்ணெய் கொண்டு கண்ணாடி போல் பளபளப்பாக்கும் பட்டறை நுட்பம்.",
        "sources": [
            "Artisans of South India Horn-Work Surveys",
            "Kilakarai and Madurai Horn-Comb Makers Oral Histories",
            "Traditional Indian Handicrafts Technical Manuals"
        ],
        "content": "# Horn Slitting, Oil-Bath Roasting & Wedge-Press Flattening\n\nConverting a rugged, curved water-buffalo horn (*erumai-kombu*) into a crystal-clear golden or jet-black flat blank (*palagai*) requires four precise thermal and mechanical stages:\n\n**Workshop Fabrication Sequence:**\n1. **Core Removal & Longitudinal Slitting**: Seasoned hollow horns are boiled to loosen the inner bony core (*ul-elumbu*). The solid pointed tip is sawn off for lathe-turning into finials or snuff-jars, while the hollow barrel is slit lengthwise along its inner concave curve with a frame saw.\n2. **Sesame-Oil & Ember Plastification**: The split cylinder is brushed with gingelly (sesame) oil and held over smokeless tamarind-charcoal embers (`~120°C`), while the artisan pries the curling walls open with twin iron pincers (*kuradu*).\n3. **Hardwood Wedge-Press (*Maram-Achu*)**: The hot, opened sheet is sandwiched between two oiled iron plates inside a heavy hardwood beam press tightened by driving hardwood wedges (*aappu*) with a mallet, cooling overnight into a perfectly flat plate.\n4. **Scraping & Leaf-Ash Polishing**: The rough outer rind is scraped translucent with a curved steel scraper (*seevu-uli*), sanded with rough *pirai* leaves (*Streblus asper*), and buffed to a mirror gloss with fine wood-ash, brick dust, and coconut oil on a chamois or cotton pad."
    },
    {
        "slug": "technology-eervali-double-edged-comb-tooth-sawing-and-muthu-chippi-fretwork-inlay",
        "category": "technology",
        "file": "technology-eervali-double-edged-comb-tooth-sawing-and-muthu-chippi-fretwork-inlay.md",
        "name_en": "Stiff-Backed Karukku-Vaal Comb Tooth Sawing, Bevel Filing & Mother-of-Pearl Fretwork Inlay",
        "name_ta": "கருக்குவாள் சீப்புப் பல் அறுப்பு, முப்பட்டை அரத் தேய்ப்பு மற்றும் முத்துச்சிப்பிப் பதிப்புத் தொழில்நுட்பம்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Precision hand-cutting of comb teeth and shell inlay: clamping horn blanks in a foot-vice (kudirai), sawing 40 teeth per inch by eye with a paper-thin stiff-backed steel saw (karukku-vaal), rounding tooth tips with a triangular file, and inlaying engraved mother-of-pearl (muthu-chippi).",
        "summary_ta": "மரக் குதிரையில் கொம்புத் தகட்டைப் பொருத்தி, மெல்லிய கருக்குவாள் ரம்பத்தால் ஒரு அங்குலத்திற்கு 40 பற்கள் வீதம் அறுத்து, முப்பட்டை அரத்தால் முனை மழுக்கி, முத்துச்சிப்பி பதிக்கும் நுட்பம்.",
        "sources": [
            "Traditional Comb-Makers of Tamil Nadu",
            "Thanjavur and Kilakarai Musical Instrument & Casket Inlay Craft",
            "South Indian Decorative Arts Monographs"
        ],
        "content": "# Karukku-Vaal Comb Tooth Sawing & Muthu-Chippi Fretwork Inlay\n\nCutting scores of hair-thin, parallel teeth into a horn plate without snapping a single tooth is a tour de force of manual tool control:\n\n**Precision Cutting & Inlay Techniques:**\n1. **The *Kudirai* Foot-Vice**: The artisan sits cross-legged on the floor, gripping the polished horn blank tightly between the jaws of a sloped wooden clamp (*kudirai*) held firm by foot tension.\n2. ** Twin-Blade & *Karukku-Vaal* Sawing**: Using a thin, stiff-backed steel pull-saw (*karukku-vaal*) lubricated with a drop of oil—sometimes fitted with a secondary gauge blade that scores the next kerf line as the primary blade cuts the current tooth—the craftsman saws coarse teeth (*pallari*) on one edge and microscopic nit teeth (*eervali*) on the opposite edge, stopping precisely at the central spine (*nadupattai*).\n3. **Tooth-Tip Taper Filing**: Each tooth is beveled on both sides with a knife-edge file (*vaazhai-aram*) so no sharp burr can scratch the scalp.\n4. **Muthu-Chippi Nacre Inlay**: Flat inner plates of *Pinctada* pearl-oyster shells are fret-sawn into lotus petals and birds, recessed into dark horn or rosewood surfaces with hot lac (*arakku*) and lime-resin putty, and engraved with black lac-filled line details."
    },
    {
        "slug": "artifact-eervali-pallari-keratin-grooming-combs-podimattai-snuff-boxes-and-mai-kudam",
        "category": "artifact",
        "file": "artifact-eervali-pallari-keratin-grooming-combs-podimattai-snuff-boxes-and-mai-kudam.md",
        "name_en": "Eervali & Pallari Keratin Combs, Podimattai Horn Snuff-Boxes & Mai-Kudam Collyrium Vials",
        "name_ta": "ஈர்வலி மற்றும் பல்லரி கொம்புச் சீப்புகள், பொடிமட்டை மூக்குப்பொடிச் சிமிழ்கள் மற்றும் மைக்குடம்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Personal grooming and apothecary artifacts crafted from polished horn and shell: double-sided eervali lice combs, single-row handled pallari combs, lathe-turned airtight horn snuff-boxes (podimattai), kohl/collyrium jars (mai-kudam), and Siddha medicine spoons.",
        "summary_ta": "பதப்படுத்திய கொம்பு மற்றும் சிப்பியால் செய்யப்பட்ட அன்றாடப் பயன்பாட்டுப் பொருட்கள்: இருபக்க ஈர்வலிச் சீப்பு, பல்லரிச் சீப்பு, காற்றுப்புகாத மூக்குப்பொடிச் சிமிழ் (பொடிமட்டை), கண்மைச் சிமிழ் (மைக்குடம்) மற்றும் மருந்துக் கரண்டிகள்.",
        "sources": [
            "Porunararruppadai",
            "Government Museum Chennai Ethnographic Collection",
            "Siddha Apothecary Vessel Traditions"
        ],
        "content": "# Eervali Combs, Podimattai Snuff-Boxes & Mai-Kudam Collyrium Vials\n\nBecause horn and tortoiseshell are chemically inert, non-corrosive, waterproof, and shatter-resistant, Tamil artisans fashioned them into essential personal and medical containers:\n\n**Artifact Typology:**\n- **Eervali & Pallari Combs**:\n  - *Eervali*: Rectangular double-edged comb with a central spine often pierced with geometric latticework or inlaid with bone/mother-of-pearl circles.\n  - *Pallari / Konde-Seeppu*: Wide-toothed detangling comb and curved ornamental chignon comb worn tucked into a woman's hair bun (*kondai*).\n- **Podimattai (Airtight Horn Snuff & Chooranam Caskets)**: Turned on a bow-lathe from the solid tip of a buffalo horn or welded from flat horn plates with a friction-fitted horn lid and tiny bone scoop; the natural oiliness and tight keratin seal kept herbal snuff (*mookkupodi*) and Siddha *chooranams* dry through coastal monsoons.\n- **Mai-Kudam (Collyrium / Kan-Mai Pots)**: Small, vase-shaped horn vials with an integrated applicator wand used to store sacred herbal lampblack eye salve (*kan-mai*)."
    },
    {
        "slug": "artifact-muthu-chippi-nacre-and-horn-inlaid-netti-petti-caskets-and-instrument-bridges",
        "category": "artifact",
        "file": "artifact-muthu-chippi-nacre-and-horn-inlaid-netti-petti-caskets-and-instrument-bridges.md",
        "name_en": "Muthu-Chippi Nacre & Horn Inlaid Jewel Caskets (Netti-Petti), Veena Bridges &Konikkol Plectrums",
        "name_ta": "முத்துச்சிப்பி மற்றும் கொம்பு பதித்த ஆபரணப் பெட்டிகள், வீணைக் குதிரை முகப்பு மற்றும் கோணிக்கோல்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Luxury decorative and acoustic artifacts combining horn, deer antler, and Gulf of Mannar mother-of-pearl (muthu-chippi): bridal jewel chests, Thanjavur Veena resonator borders and horn/stag-horn tonal bridges, and polished horn plectrums (konikkol).",
        "summary_ta": "முத்துச்சிப்பி, மான் கொம்பு மற்றும் எருமைக் கொம்பு பதித்த கலைப்பொருட்கள்: மணமகள் ஆபரணப் பெட்டிகள், தஞ்சாவூர் வீணையின் விளிம்பு வேலைப்பாடுகள், குதிரை முகப்பு மற்றும் யாழ்/வீணை சுண்டும் கோணிக்கோல்.",
        "sources": [
            "Thanjavur Palace & Saraswathi Mahal Craft Inventories",
            "Ramnad Setupati Court Decorative Arts",
            "South Indian Musical Instrument Organology"
        ],
        "content": "# Muthu-Chippi & Horn Inlaid Caskets and Musical Instrument Fittings\n\nIn the royal courts of Madurai, Ramnad (Ramanathapuram), and Thanjavur, coastal shell-and-horn lapidaries collaborated with cabinetmakers and luthiers to produce high-status regalia:\n\n**Courtly & Acoustic Artifacts:**\n- **Inlaid Bridal & Betel Caskets (*Netti-Petti* / *Chellam*)**: Teak and rosewood caskets veneered with translucent amber-mottled horn plates fixed over gold leaf (*thanga-rekku*) or inlaid with iridescent *muthu-chippi* (mother-of-pearl) floral arabesques and brass corner mounts.\n- **Veena & Yazh Acoustic Fittings**: Luthiers used dense, cured stag-horn (*maan-kombu*), buffalo horn, and mother-of-pearl dots along the curved rim of the *kudam* resonator and neck of the Thanjavur *Veena*, as well as polished horn plectrums (*konikkol*) whose elastic keratin flex plucked strings with warm attack free of metallic scratch."
    },
    {
        "slug": "concept-pinctada-nacre-aragonite-iridescence-and-ethical-buffalo-horn-substitution",
        "category": "concept",
        "file": "concept-pinctada-nacre-aragonite-iridescence-and-ethical-buffalo-horn-substitution.md",
        "name_en": "Pinctada Nacre Aragonite Iridescence & Ethical Buffalo-Horn / Coconut-Shell Craft Substitution",
        "name_ta": "முத்துச்சிப்பி அரகோனைட் ஒளிச்சிதறல் இயற்பியலும் ஆமையோட்டிற்குப் பதிலான அறவழி எருமைக் கொம்பு மாற்றும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "neithal",
        "summary_en": "Optical physics of Pinctada fucata mother-of-pearl brick-and-mortar aragonite platelets and the ecological transition of Gulf of Mannar artisans from protected marine hawksbill turtle scutes (Eretmochelys imbricata) to mottled water-buffalo horn and polished coconut shell.",
        "summary_ta": "பின்க்டாடா முத்துச்சிப்பியின் அரகோனைட் படிக அடுக்குகள் உருவாக்கும் வானவில் ஒளிச்சிதறலும், கடல் ஆமைகள் பாதுகாப்பிற்காக ஆமையோட்டிற்குப் பதிலாகப் புள்ளிகளுடைய எருமைக் கொம்பு மற்றும் கொட்டாங்குச்சியைப் பயன்படுத்தும் சூழலியல் மாற்றமும்.",
        "sources": [
            "Gulf of Mannar Marine Biosphere Reserve Conservation Reports",
            "Biomineralization of Pinctada Nacre",
            "Sustainable Craft Revival in Ramanathapuram District"
        ],
        "content": "# Pinctada Nacre Iridescence & Ethical Buffalo-Horn Substitution\n\nThe coastal lapidary tradition of the Gulf of Mannar combines the optical physics of biomineralized shell nacre with an exemplary modern transition toward sustainable materials:\n\n**Optical & Ecological Principles:**\n- **Aragonite Thin-Film Interference (*Muthu-Chippi*)**: The inner nacreous lining of the Gulf of Mannar pearl oyster (*Pinctada fucata*) and turban snail (*Turbo marmoratus*) consists of hexagonal aragonite $\\text{CaCO}_3$ platelets (~500 nm thick, matching the wavelength of visible light) mortared with elastic conchiolin protein. Constructive interference across these nano-layers produces structural rainbow iridescence that never fades.\n- **Ethical Substitution for Marine Turtle Scutes**: Historically, artisans worked the overlapping carapace scutes of the hawksbill sea turtle (*Eretmochelys imbricata*, *alungu-aamai*). With the strict protection of marine turtles under the Indian Wildlife Protection Act (1972) and Gulf of Mannar Biosphere conservation, traditional *Kilakarai* and *Rameswaram* craftsmen transferred their thermal-pressing, mottling, and *eervali* comb-sawing techniques entirely to **by-product water-buffalo horn (*kombu*)** and high-density polished **coconut shell (*kottanguchi*)**, preserving the ancient craft without harming marine life."
    },
    {
        "slug": "institution-gulf-of-mannar-shell-and-horn-lapidary-guilds-and-marakkayar-export-networks",
        "category": "institution",
        "file": "institution-gulf-of-mannar-shell-and-horn-lapidary-guilds-and-marakkayar-export-networks.md",
        "name_en": "Gulf of Mannar Shell & Horn Lapidary Workshops, Paravar Divers & Marakkayar Trade Networks",
        "name_ta": "மன்னார் வளைகுடா சிப்பி மற்றும் கொம்புச் சிற்பப் பட்டறைகள், பரதவர் மூழ்குநர் மற்றும் மரைக்காயர் வணிக வலைப்பின்னல்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Social and commercial organization of coastal keratin and shell craft in Ramanathapuram and Tirunelveli: Paravar and Kadaiyar reef divers supplying pearl-oyster shells, hereditary horn-comb and inlay artisans, and Marakkayar maritime merchants trading across the Indian Ocean.",
        "summary_ta": "இராமநாதபுரம் மற்றும் திருநெல்வேலி கடற்கரைக் கொம்பு மற்றும் சிப்பித் தொழில் அமைப்பு: முத்துச்சிப்பி சேகரிக்கும் பரதவர் மூழ்குநர்கள், சீப்பு மற்றும் சிப்பிப் பதிப்புக் கலைஞர்கள் மற்றும் மரைக்காயர் கடல் வணிகர்கள்.",
        "sources": [
            "Madura and Ramnad District Manuals",
            "Gulf of Mannar Pearl and Chank Fishery Records",
            "Maritime Trade History of Kilakarai and Kayalpattinam"
        ],
        "content": "# Gulf of Mannar Shell & Horn Lapidary Guilds & Maritime Networks\n\nAlong the *Neithal* littoral of the Ramanathapuram (Sethupathi) and Tirunelveli coast, horn and shell working flourished through a three-part division of labour:\n\n**Artisan & Mercantile Ecosystem:**\n- **Reef Divers & Shell Sorters**: During pearl and chank fishery seasons (*muthu-kulippu*) on the *paars* (rocky pearl banks) off Kilakarai, Tuticorin, and Korkai, *Paravar* and Muslim skin-divers brought up millions of *Pinctada* oysters. Even shells lacking free pearls yielded prized thick mother-of-pearl valves (*muthu-chippi*) and opercula (*nagana-mooku* used in incense).\n- **Hereditary Comb & Lapidary Artisans**: Specialized cottage workshops in Kilakarai, Rameswaram, Paramakudi, and Madurai procured rural cattle horns and coastal shells, training apprentices in *karukku-vaal* comb sawing, thermal horn pressing, and nacre fretwork.\n- **Setupati Court & Marakkayar Export Patronage**: The Setupati rulers of Ramnad commissioned mother-of-pearl and horn-inlaid palanquins, sword hilts, and presentation caskets, while *Marakkayar* shipowners exported horn combs (*eervali*) and shell-inlaid boxes to Penang, Singapore, Colombo, and the Malabar coast."
    },
    {
        "slug": "place-kilakarai-ancient-gulf-of-mannar-tortoiseshell-and-horn-craft-haven",
        "category": "place",
        "file": "place-kilakarai-ancient-gulf-of-mannar-tortoiseshell-and-horn-craft-haven.md",
        "name_en": "Kilakarai: Ancient Gulf of Mannar Port, Mother-of-Pearl Lapidary & Horn-Comb Craft Haven",
        "name_ta": "கீழக்கரை - பண்டைய மன்னார் வளைகுடாத் துறைமுகம், முத்துச்சிப்பி மற்றும் கொம்புச் சீப்புக் கலைத் தளம்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Historic Gulf of Mannar port town in Ramanathapuram district (9.2320° N, 78.7840° E), sheltered by a natural chain of 21 coral islands (Appa Tivu, Nallathanni Tivu) and celebrated since classical antiquity for pearl diving, chank cutting, mother-of-pearl inlay, and horn comb craft.",
        "summary_ta": "இராமநாதபுரம் மாவட்டத்தில் மன்னார் வளைகுடாவின் பவளப்பாறைத் தீவுகளால் சூழப்பட்ட கீழக்கரைத் துறைமுகம் (9.2320° N, 78.7840° E): சங்க காலம் தொட்டு முத்துக்குளிப்பு, முத்துச்சிப்பி வேலைப்பாடு மற்றும் கொம்புச் சீப்புக் கலைக்குப் புகழ்பெற்ற வரலாற்றுத் தளம்.",
        "sources": [
            "Periplus Maris Erythraei",
            "Ramnad Manual (Kilakarai Port & Pearl Banks)",
            "Archaeological Survey Reports on Coastal Ramanathapuram"
        ],
        "content": "# Kilakarai: Ancient Gulf of Mannar Shell & Horn Craft Haven\n\nLocated on the Ramanathapuram coast overlooking the coral-fringed lagoon of the Gulf of Mannar (9.2320° N, 78.7840° E), **Kilakarai** (historically linked with classical *Korkai–Argalu* and medieval *Ninra-Seer-Nedumaran-Pattinam* / *Lebbai-Pattinam*) is one of Tamil Nadu's oldest continuous maritime craft centers:\n\n**Geographic & Material-Culture Significance:**\n- **Coral-Barrier Lagoon Anchorage**: Protected from open-ocean monsoon swells by a natural chain of fringing coral islands (*Kurisadi, Shingle, Appa, and Nallathanni Tivu*), Kilakarai's shallow seagrass and coral waters formed the biological heart of the Gulf of Mannar shell, pearl-oyster (*Pinctada*), and ancient *chelone* trade described in the *Periplus*.\n- **Living Lapidary & Keratin Craft Cluster**: Across Kilakarai, Rameswaram, and neighboring Ramnad towns, master artisans perfected thermal buffalo-horn pressing, *eervali* fine-comb sawing, coconut-shell carving, and iridescent *muthu-chippi* inlay for domestic grooming, Siddha apothecaries, and maritime trade."
    }
]

EDGES = [
    [
        "text-periplus-and-sangam-corpus-on-aamai-odu-tortoiseshell-and-seeppu-combs",
        "documents",
        "place-kilakarai-ancient-gulf-of-mannar-tortoiseshell-and-horn-craft-haven",
        "material_culture",
        "Sangam Era",
        "The Periplus Maris Erythraei and Sangam poems attest to the Gulf of Mannar reef channel around Kilakarai as the premier source of tortoiseshell, nacre, and horn craft.",
        "Periplus & Akananuru"
    ],
    [
        "concept-thermoplastic-keratin-polymer-softening-and-autogenous-thermal-scute-welding",
        "underpins",
        "technology-horn-and-scute-steam-flattening-iron-clamp-pressing-and-thermal-lamination",
        "material_culture",
        "Sangam to Modern Era",
        "Disulfide and hydrogen bond relaxation in keratin at 110°C-130°C enables split buffalo horns to be flattened in wedge-presses and welded without glue.",
        "Keratin Materials Science"
    ],
    [
        "technology-horn-and-scute-steam-flattening-iron-clamp-pressing-and-thermal-lamination",
        "feeds",
        "technology-eervali-double-edged-comb-tooth-sawing-and-muthu-chippi-fretwork-inlay",
        "material_culture",
        "Sangam to Modern Era",
        "Wedge-pressed and leaf-ash polished flat horn blanks are clamped in the foot-vice for karukku-vaal comb tooth sawing and nacre inlay.",
        "South Indian Craft Surveys"
    ],
    [
        "technology-eervali-double-edged-comb-tooth-sawing-and-muthu-chippi-fretwork-inlay",
        "produces",
        "artifact-eervali-pallari-keratin-grooming-combs-podimattai-snuff-boxes-and-mai-kudam",
        "material_culture",
        "Sangam to Modern Era",
        "Precision karukku-vaal sawing and bow-lathe turning produce double-sided eervali lice combs, pallari combs, and airtight podimattai snuff caskets.",
        "Madras Museum Catalogues"
    ],
    [
        "concept-anti-static-keratin-hair-tribology-and-eervali-fine-tooth-comb-biomechanics",
        "explains",
        "artifact-eervali-pallari-keratin-grooming-combs-podimattai-snuff-boxes-and-mai-kudam",
        "material_culture",
        "Sangam to Modern Era",
        "Matching keratin triboelectric potential and sub-millimetre tooth geometry explain why eervali horn combs eliminate hair static and trap nits.",
        "Siddha Dinacharya Manuals"
    ],
    [
        "technology-eervali-double-edged-comb-tooth-sawing-and-muthu-chippi-fretwork-inlay",
        "fashions",
        "artifact-muthu-chippi-nacre-and-horn-inlaid-netti-petti-caskets-and-instrument-bridges",
        "material_culture",
        "Sangam to Modern Era",
        "Fret-sawn Pinctada mother-of-pearl and translucent horn plates are inlaid into bridal jewel caskets and Thanjavur Veena resonator borders.",
        "Thanjavur Craft Inventories"
    ],
    [
        "concept-pinctada-nacre-aragonite-iridescence-and-ethical-buffalo-horn-substitution",
        "guides",
        "artifact-muthu-chippi-nacre-and-horn-inlaid-netti-petti-caskets-and-instrument-bridges",
        "material_culture",
        "Sangam to Modern Era",
        "Thin-film aragonite interference in Pinctada nacre and ethical buffalo-horn substitution guide decorative casket and musical instrument inlay.",
        "Gulf of Mannar Conservation Reports"
    ],
    [
        "institution-gulf-of-mannar-shell-and-horn-lapidary-guilds-and-marakkayar-export-networks",
        "fabricates",
        "artifact-eervali-pallari-keratin-grooming-combs-podimattai-snuff-boxes-and-mai-kudam",
        "material_culture",
        "Sangam to Modern Era",
        "Hereditary coastal comb-makers and horn-turners fabricate eervali combs, podimattai snuff-boxes, and mai-kudam vials for domestic and overseas markets.",
        "Ramnad District Manual"
    ],
    [
        "institution-gulf-of-mannar-shell-and-horn-lapidary-guilds-and-marakkayar-export-networks",
        "operates_in",
        "place-kilakarai-ancient-gulf-of-mannar-tortoiseshell-and-horn-craft-haven",
        "material_culture",
        "Sangam to Modern Era",
        "Paravar shell divers, horn-and-nacre lapidaries, and Marakkayar merchants operated out of the coral-sheltered port of Kilakarai.",
        "Kilakarai Maritime History"
    ],
    [
        "text-periplus-and-sangam-corpus-on-aamai-odu-tortoiseshell-and-seeppu-combs",
        "describes",
        "artifact-eervali-pallari-keratin-grooming-combs-podimattai-snuff-boxes-and-mai-kudam",
        "material_culture",
        "Sangam Era",
        "Sangam poems Akananuru, Kalittokai, and Porunararruppadai describe tortoise carapaces, buffalo horns, and fine-toothed eervali grooming combs.",
        "Porunararruppadai & Kalittokai"
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
