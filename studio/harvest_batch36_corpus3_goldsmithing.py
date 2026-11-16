#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Goldsmithing, Granulation & Filigree Regalia
import os
import sys
import json
import uuid
import psycopg2
import requests

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
MOOLAM_KNOWLEDGE = "/mnt/h/DevTools/Projects/learn-ai/moolam-chronicles"

DOSSIERS = [
    {
        "file": "knowledge/texts/text-silappadikaram-14-verses-on-madurai-jewellers-street-and-gold-refining.md",
        "slug": "text-silappadikaram-14-verses-on-madurai-jewellers-street-and-gold-refining",
        "category": "text",
        "name_en": "Silappadikaram 14: Epic Verses on Madurai Goldsmiths Quarter, Pon-Sei-Seri & Refining Hearth",
        "name_ta": "சிலப்பதிகாரம் ஊர்காண் காதை - மதுரைப் பொன் செய் சேரி, தட்டார் உலை மற்றும் பொன் உருக்கு இலக்கியப் பாடல்",
        "era": "Post-Sangam Era",
        "year_start": 200,
        "year_end": 500,
        "thinai": "marutham",
        "summary_en": "Ilango Adigal's vivid poetic portrayal in Ur-Kaan Kathai detailing the opulent goldsmith street (pon-sei-seri) in Madurai, where royal jewellers melted, alloyed, and assayed gold regalia.",
        "summary_ta": "இளங்கோவடிகள் இயற்றிய சிலப்பதிகாரத்தில், மதுரை நகரின் பொற்கொல்லர் தெருவில் அணிகலன்களை உருக்கி, உரைகல்லில் உரைத்து, நுணுக்கமான நகைகளைச் செய்யும் தட்டாரின் காட்சிகளை விவரிக்கும் பாடல்.",
        "sources": [
            "Silappadikaram 14:180-215",
            "Pattinappalai 190",
            "Maduraikkanchi 510-530"
        ],
        "content": "# Silappadikaram 14: Madurai Goldsmiths Quarter & Refining\n\nIn *Silappadikaram* (Canto 14, *Ur-Kaan Kathai*), Ilango Adigal describes Kovalan entering the magnificent capital of the Pandyan kings:\n\n> \"Entering the vibrant street of the master goldsmiths (*pon-sei-seri*), he beheld skilled artisans working before roaring crucible hearths... With clay blowpipes (*oothu-kuzhal*) directing slender flames, they purified native gold, testing streaks against smooth black touchstones (*uravuk-kallu*), and hammering delicate ornaments studded with rubies and lustrous Korkai pearls...\"\n\nThis epic passage provides unparalleled historical documentation of the urban concentration, pyrotechnic skill, and commercial sophistication of the royal goldsmith guilds of Madurai."
    },
    {
        "file": "knowledge/concepts/concept-kundrumani-abrus-precatorius-standard-seed-gravimetric-metrology.md",
        "slug": "concept-kundrumani-abrus-precatorius-standard-seed-gravimetric-metrology",
        "category": "concept",
        "name_en": "Kundrumani: Abrus Precatorius Seed Metrology, Manjadi Calibration & Gold Weight Standards",
        "name_ta": "குன்றிமணி - குன்றிமணி எடை அளவு, மஞ்சாடி அளவீடு மற்றும் பண்டைய பொன் எடைத் தரம்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Standardized gravimetric weight system anchored on the remarkably uniform scarlet seeds of Abrus precatorius (kundrumani ~ 105 mg) and Adenanthera pavonina (manjadi ~ 240 mg) for precision bullion trade.",
        "summary_ta": "இயற்கையிலேயே சீரான எடை கொண்ட குன்றிமணி மற்றும் மஞ்சாடி விதைகளை அடிப்படையாகக் கொண்டு, துல்லியமான தராசுகளில் பொன்னின் எடையைக் கணித்த தமிழரின் எடையியல் முறை.",
        "sources": [
            "Tholkappiyam Marapiyal on Weights",
            "South Indian Inscriptions Vol. II",
            "Archaeometrological Studies of Ancient Indian Weights"
        ],
        "content": "# Kundrumani: Precision Gold Metrology & Seed Standards\n\nLong before the adoption of standardized metallic metric weights, ancient Tamil jewellers utilized botanical seeds of astonishingly uniform mass:\n\n- **The Kundrumani Base Unit**: The brilliant scarlet seed with a black eye from *Abrus precatorius* (*kundrumani*) possesses a natural dry weight variance of less than 3%, averaging approximately 105–110 milligrams.\n- **The Manjadi Scale**: Two *kundrumani* equalled one *manjadi* (~210–240 mg), the seed of *Adenanthera pavonina*.\n- **The Royal Kalanju System**: Epigraphs from the Pandyan and Chola reigns established the sovereign bullion benchmark: 20 *manjadi* constituted one *kalanju* (~4.8 to 5.0 grams of high-purity gold).\n- **Balance Precision**: Goldsmiths operated sensitive ivory and brass balances (*thula-kole*) enclosed inside glass-faced or cloth lanterns to shield the pans from stray drafts, detecting variances as subtle as half a *kundrumani*."
    },
    {
        "file": "knowledge/technologies/technology-thattar-kodu-and-oothu-kuzhal-blowpipe-cupellation-and-gold-assaying.md",
        "slug": "technology-thattar-kodu-and-oothu-kuzhal-blowpipe-cupellation-and-gold-assaying",
        "category": "technology",
        "name_en": "Thattar-Kodu & Oothu-Kuzhal: Crucible Cupellation, Blowpipe Pyrotechnics & Gold Refining",
        "name_ta": "தட்டார் உலை மற்றும் ஊதுகுழல் - புடமிடுதல், ஊதுகுழல் நுட்பம் மற்றும் தங்கம் சுத்திகரிப்பு முறை",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Pyrotechnic assaying using charcoal hearths, clay blowpipes, and bone-ash cupels (kodu) to oxidize base metals (lead, copper, silver) and isolate unblemished 24-karat gold.",
        "summary_ta": "எலும்புச் சாம்பல் கிண்ணங்கள் மற்றும் களிமண் ஊதுகுழல்களைக் கொண்டு, உயர் வெப்பத்தில் தங்கத்திலுள்ள செம்பு, காரீயக் கலவைகளை நீக்கித் தூய பொன்னாக்கும் புட முறை.",
        "sources": [
            "Arthashastra Section on Suvarnadhyaksha",
            "Tamil Lexicon on Thattar-Kalai",
            "Archaeological Metallurgy at Kodumanal"
        ],
        "content": "# Thattar-Kodu: Blowpipe Cupellation & Gold Refining\n\nTransforming raw placer or vein gold into regal jewelry required meticulous pyrochemical purification (*pudam-poduthal*):\n\n- **The Blowpipe Hearth (*Oothu-Kuzhal*)**: Jewellers sat before small pit hearths filled with dense acacia charcoal. Using curved brass or clay blowpipes, they directed a pinpoint oxidizing flame reaching temperatures exceeding 1064°C (the melting point of pure gold).\n- **Cupellation in Bone-Ash Vessels (*Kodu*)**: Impure gold scrap containing copper, iron, and lead was placed into a porous crucible made of compacted bone ash and washed clay. Under high oxidizing heat, base metals oxidized and were absorbed into the porous cupel walls, leaving a luminous button of noble gold.\n- **Flux Formulations**: Borax (*venkaram*) and ground saltpetre were added to dissolve oxides and promote clean separation of dross."
    },
    {
        "file": "knowledge/artifacts/artifact-makara-kundalam-gold-filigree-earrings-and-granulated-pendants.md",
        "slug": "artifact-makara-kundalam-gold-filigree-earrings-and-granulated-pendants",
        "category": "artifact",
        "name_en": "Makara-Kundalam: Royal Mythical Sea-Monster Earrings, Micro-Filigree & Pendant Regalia",
        "name_ta": "மகர குண்டலம் - புராணக் கடல் விலங்கு வடிவ தங்கக் காதணி, மெல்லிய கம்பி வேலை மற்றும் தொங்கல் அணிகலன்",
        "era": "Iron Age to Medieval Era",
        "year_start": -300,
        "year_end": 1400,
        "thinai": "marutham",
        "summary_en": "Iconic royal gold ear ornaments depicting the mythical composite marine creature (makara), fabricated from micro-soldered gold wires, repoussé sheet metal, and hanging granulated clusters.",
        "summary_ta": "மகர மீன் உருவத்தில், மிக நுண்ணிய தங்கக் கம்பிகள் மற்றும் உருண்டை மணிகளால் இழைக்கப்பட்ட அரச குடும்பத்தினரின் பிரம்மாண்ட காதணி.",
        "sources": [
            "Purananuru 378",
            "Silappadikaram 6:85-110",
            "Madurai Pandyan Royal Treasure Excavations"
        ],
        "content": "# Makara-Kundalam: Gold Filigree & Royal Pendants\n\nThe *Makara-Kundalam* stood as the ultimate badge of sovereignty and aristocratic refinement across South Indian courts:\n\n- **Mythological Iconography**: The ornament represented the *makara*, a primordial composite sea monster possessing the trunk of an elephant, jaws of a crocodile, and tail of a fish—symbolizing oceanic dominion and cosmic vitality.\n- **Micro-Filigree Lamination**: Goldsmiths drew pure gold through pierced iron draw-plates (*kambi-vaai*) into threads as fine as human hair. These wires were twisted, coiled, and soldered into lace-like filigree patterns forming the scales, fins, and open jaws of the creature.\n- **Hanging Drops**: Beneath the central body hung clusters of granulated gold pendants (*thookku-kadal-mani*) that chimed softly with the wearer's movements."
    },
    {
        "file": "knowledge/concepts/concept-pon-akkam-gold-mercury-fire-gilding-and-surface-enrichment.md",
        "slug": "concept-pon-akkam-gold-mercury-fire-gilding-and-surface-enrichment",
        "category": "concept",
        "name_en": "Pon-Akkam: Mercury Fire-Gilding, Chemical Depletion Gilding & Surface Enrichment",
        "name_ta": "பொன் ஆக்கம் - பாதரசத் தங்கப் பூச்சு, வேதியியல் நிறமேற்றம் மற்றும் மேலடுக்குத் தங்கம் பிரித்தல்",
        "era": "Classical Antiquity to Medieval Era",
        "year_start": -300,
        "year_end": 1500,
        "thinai": "marutham",
        "summary_en": "Ancient electrochemical and pyrochemical surface treatment involving gold-mercury amalgams and organic acid baths to deposit lustrous 24-karat pure gold surfaces on copper and bronze temple regalia.",
        "summary_ta": "பாதரசத்தில் தங்கத்தைக் கரைத்துப் பூசி, சூடாக்கிப் பாதரசத்தை ஆவியாக்கும் தீ-பூச்சு முறை மற்றும் சிட்ரிக் அமிலக் கரைசலால் தங்கத்தை ஒளிரச் செய்யும் வேதியியல் கலை.",
        "sources": [
            "Mayamata Chapter on Metal Finishing",
            "Silappadikaram Adaikkalakkathai",
            "Conservation of South Indian Bronzes (Government Museum Chennai)"
        ],
        "content": "# Pon-Akkam: Fire-Gilding & Surface Enrichment\n\nTo adorn monumental temple statues, copperplate charters, and royal crowns without consuming solid bullion, ancient artisans perfected fire-gilding (*pon-akkam*):\n\n- **Mercury Amalgamation**: Gold foil was shredded and dissolved in heated liquid mercury (*rasam*), forming a silvery, butter-like amalgam paste.\n- **Paste Application & Thermal Volatilization**: The amalgam was brushed evenly onto a meticulously cleaned copper or bronze surface. The object was then heated over a smokeless charcoal hearth, vaporizing the toxic mercury while permanently fusing the gold layer into the substrate metal.\n- **Depletion Acid Polishing**: The gilded surface was boiled in an astringent herbal bath of tamarind water, fermented rice liquor, and rock salt, dissolving any surface base metal oxides and revealing an intense, brilliant 24-karat golden sheen."
    },
    {
        "file": "knowledge/institutions/institution-akkar-and-thattar-corporation-of-royal-goldsmiths-and-mint-masters.md",
        "slug": "institution-akkar-and-thattar-corporation-of-royal-goldsmiths-and-mint-masters",
        "category": "institution",
        "name_en": "Akkar & Pon-Thattar: Royal Mint Masters, Jewellers Guild & Hallmarking Corporation",
        "name_ta": "அக்கசாலை மற்றும் பொன் தட்டார் - அரச நாணயச் சாலை, பொற்கொல்லர் சங்கம் மற்றும் தரக்கட்டுப்பாட்டு வாரியம்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "State-authorized corporation of crown goldsmiths and mint masters operating royal workshops (Akka-Saalai), issuing hallmarked gold coinage, and certifying bullion purity.",
        "summary_ta": "அரசரின் நாணயங்களை அச்சிடுதல், தங்கத்தின் தரத்தை உறுதி செய்து முத்திரையிடுதல் மற்றும் அரச பொக்கிஷத்தை நிர்வகித்த அதிகாரப்பூர்வ பொற்கொல்லர் அவை.",
        "sources": [
            "Kalyanaraman: Coins of the Pandyas",
            "South Indian Inscriptions Vol. III",
            "Chola Mint Inscriptions at Uttiramerur"
        ],
        "content": "# Akkar & Pon-Thattar: Royal Mint Masters & Guilds\n\nThe royal treasury and monetary stability of ancient Tamil dynasties rested upon the integrity of the *Akka-Saalai* (royal mint and assay office):\n\n- **Imperial Guild Hierarchy**: Led by the *Perun-Thattar* (chief royal architect-goldsmith), the guild maintained strict hereditary apprenticeships, code of ethics, and guild secrets regarding metallurgy and lost-wax alloying.\n- **Punch-Marked & Die-Struck Minting**: Operating under royal charter, mint masters melted standardized bullion ingots, poured uniform blanks, and struck them with state emblems—the double carp of the Pandyas, the tiger of the Cholas, or the bow of the Cheras.\n- **Hallmarking & Bullion Certification**: The guild possessed the legal authority to seize adulterated gold, penalize deceptive merchants, and affix certification stamps (*ilaichinai*) on certified bullion bars destined for temple endowments."
    },
    {
        "file": "knowledge/technologies/technology-kadal-mani-and-pon-granulation-micro-droplet-gold-soldering.md",
        "slug": "technology-kadal-mani-and-pon-granulation-micro-droplet-gold-soldering",
        "category": "technology",
        "name_en": "Kadal-Mani Granulation: Surface Tension Spheroidization & Colloidal Hard Soldering",
        "name_ta": "கடல் மணி பொன் மணிகள் - பரப்பு இழுவிசை தங்க உருண்டையாக்கல் மற்றும் கூழ்மப் பற்றவைப்பு நுட்பம்",
        "era": "Iron Age to Medieval Era",
        "year_start": -400,
        "year_end": 1400,
        "thinai": "marutham",
        "summary_en": "Sophisticated pyrotechnic micro-granulation technique using surface tension of molten gold dust to form microscopic spheres (0.2–0.5 mm) fused onto sheets with organic copper glue without melting the base plate.",
        "summary_ta": "தங்கத் தூள்களை உலைக்களத்தில் உருக்கி மிக நுண்ணிய கோள வடிவ மணிகளாக்கி, செப்புக் கூழ்மப் பசை கொண்டு தாள் தகட்டில் பற்றவைக்கும் நுட்பமான மணிவேலை.",
        "sources": [
            "Archaeological Studies in South Indian Jewellery",
            "Maryon: Metalwork and Enamelling",
            "Kodumanal Excavation Reports"
        ],
        "content": "# Kadal-Mani Granulation: Micro-Droplet Gold Soldering\n\nGranulation was one of the most demanding pyrotechnic feats accomplished by ancient Tamil jewellers:\n\n- **Surface Tension Spheroidization**: Microscopic snippets of gold wire were layered inside charcoal powder in a sealed crucible and heated past their melting point. Liquid surface tension instantly pulled each molten droplet into a perfect sphere (*kadal-mani*).\n- **Colloidal Copper Gluing**: The spheres were positioned onto the jewelry substrate using a sticky adhesive made of plant gum mixed with copper salts (malachite or copper sulfate).\n- **Eutectic Diffusion Bonding**: The assembly was subjected to a gentle reducing flame. At 890°C, the copper salts reduced to metallic copper, forming a localized eutectic alloy with the gold touching points. The granules welded seamlessly to the base plate with zero visible solder overflow."
    },
    {
        "file": "knowledge/artifacts/artifact-kasu-malai-and-kural-gold-coin-necklaces-and-repousse-amulets.md",
        "slug": "artifact-kasu-malai-and-kural-gold-coin-necklaces-and-repousse-amulets",
        "category": "artifact",
        "name_en": "Kasu-Malai: Roman Aurei Coin Necklaces, Repoussé Tiger-Claw Amulets & Gold Chokers",
        "name_ta": "காசு மாலை - உரோம பொற்காசு மாலை, புலிப்பல் தாயத்து மற்றும் பொன் கழுத்தணி",
        "era": "Iron Age to Modern Era",
        "year_start": -300,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Prestigious heirloom necklaces composed of pierced gold coins—including Roman imperial aurei and Sangam dynastic coinage—flanked by repoussé gold-sheathed tiger claw talismans.",
        "summary_ta": "உரோமப் பேரரசின் தங்க நாணயங்கள் மற்றும் சங்க கால பாண்டிய மன்னர்களின் பொற்காசுகளைக் கோர்த்து, புலிப்பல் வடிவில் செய்யப்பட்ட பிரம்மாண்ட காசு மாலை.",
        "sources": [
            "Purananuru 218",
            "Akananuru 269",
            "Roman Coin Hoards in Tamil Nadu (Madras Museum)"
        ],
        "content": "# Kasu-Malai: Coin Necklaces & Tiger-Claw Talismans\n\nThe *Kasu-Malai* represented both wearable wealth and a sacred talismanic ornament across ancient Tamil society:\n\n- **Monetary Adornment**: Massive hoards of Roman gold *aurei* from Augustus, Tiberius, and Nero entering Tamil ports via the spice trade were not melted into ingots; instead, jewellers soldered delicate gold suspension loops (*kannikal*) to the rims, stringing them into dazzling multi-tiered coin collars.\n- **Tiger-Claw Amulets (*Puli-Pal Thali*)**: Sangam warriors and princes wore pendants fashioned from real royal Bengal tiger claws or hollow repoussé gold replicas filled with lac, chased with floral scrolls symbolizing martial invincibility.\n- **Repoussé & Chasing**: Thin sheets of 22k gold were bedded in warm pitch and beaten from the back (*repoussé*) and detailed from the front (*chasing*), creating volumetric deities, lotuses, and elephants with minimal gold consumption."
    },
    {
        "file": "knowledge/concepts/concept-uravuk-kallu-touchstone-streak-colorimetry-and-karat-purity-grading.md",
        "slug": "concept-uravuk-kallu-touchstone-streak-colorimetry-and-karat-purity-grading",
        "category": "concept",
        "name_en": "Uravuk-Kallu: Basanite Touchstone Streak Testing, Needle Colorimetry & Karat Grading",
        "name_ta": "உரைகல் - கருங்கற்கள் மீது தங்க உரைப்புத் தடம், நிற ஒப்பீடு மற்றும் மாற்றுத் தரம் அறிதல்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Non-destructive assaying methodology utilizing fine-grained siliceous basanite touchstones (uravuk-kallu) and calibrated gold-alloy touch-needles to determine karat purity (maattru).",
        "summary_ta": "நுணுக்கமான கருங்கல் பலகையில் தங்கத்தை உரசி, அமிலமிட்டு, வண்ண மாற்றங்களை ஆய்வு செய்து தங்கத்தின் மாற்றுத் தரத்தைத் துல்லியமாகக் கணிக்கும் தொன்மை முறை.",
        "sources": [
            "Thirukkural 505 Commentaries",
            "Silappadikaram 14",
            "Goldsmith Assay Traditions of South India"
        ],
        "content": "# Uravuk-Kallu: Touchstone Assaying & Colorimetry\n\nThe touchstone (*uravuk-kallu*) was the sacred, indispensable instrument of every honest Tamil goldsmith:\n\n- **The Basanite Substrate**: The stone consisted of a fine-grained, velvet-black radiolarite or siliceous basanite slate possessing just enough micro-abrasive tooth to draw a thin metal streak without gouging the artifact.\n- **Streak Colorimetry**: The unknown gold specimen was rubbed across the stone to produce a streak 1 cm wide. Parallel to it, the goldsmith drew streaks using calibrated reference needles (*thattu-kambi*) of known fineness ranging from 12 to 24 karats (*maattru*).\n- **Acid Reaction Verification**: A feather-drop of nitric acid (*vedippu-neer*) and salt solution was brushed across the streaks. Base metal constituents dissolved immediately, leaving behind the insoluble gold residue whose golden tone precisely indicated purity."
    },
    {
        "file": "knowledge/places/place-madurai-ancient-pandya-jewellers-guild-haven.md",
        "slug": "place-madurai-ancient-pandya-jewellers-guild-haven",
        "category": "place",
        "name_en": "Madurai: Ancient Vaigai Royal Goldsmiths Quarter, Akka-Saalai & Pandyan Jewellery Haven",
        "name_ta": "மதுரை - பண்டைய வைகை அரச பொற்கொல்லர் சேரி, அக்கசாலை மற்றும் பாண்டியர் தங்கக் கலைத் தளம்",
        "era": "Sangam Era to Modern Era",
        "year_start": -600,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "The storied Pandyan capital on the Vaigai River, renowned throughout antiquity for its sprawling goldsmiths quarter (pon-sei-seri), royal mints, and pearl-inlaid royal regalia.",
        "summary_ta": "வைகை நதிக்கரையில் அமைந்துள்ள பாண்டியர்களின் தலைநகரம், சிலப்பதிகாரம் பாடும் பொன் செய் சேரி மற்றும் உலகப் புகழ்பெற்ற அக்கசாலை பொற்கலைத் தளம்.",
        "sources": [
            "Silappadikaram Ur-Kaan Kathai",
            "Maduraikkanchi 490-530",
            "Keezhadi Archaeological Excavation Reports"
        ],
        "content": "# Madurai: Ancient Pandyan Jewellery Haven\n\nFamed throughout the ancient world as the cultural heart of Tamil civilization, Madurai was the prime metropolitan sanctuary for master jewellers and royal metallurgists:\n\n- **The Pon-Sei-Seri of Madurai**: Excavations at nearby Keezhadi and Sangam epigraphy confirm that the southern royal capital supported an entire dedicated artisan quarter (*pon-sei-seri*) bustling with hundreds of crucible furnaces, lapidary workshops, and ivory carvers.\n- **The Royal Mint (*Akka-Saalai*)**: Established along the northern banks of the sacred Vaigai, the royal mint melted incoming Roman gold coin hordes and Korkai pearl hauls, striking royal Pandyan coin series stamped with the dynastic twin fish.\n- **Enduring Living Heritage**: To this day, the inner streets surrounding the Meenakshi Sundareswarar temple—notably *Thattar Theru* and *Avani Moola Veethi*—continue an unbroken 2,500-year hereditary lineage of precision temple jewellery manufacturing."
    }
]

EDGES = [
    [
        "text-silappadikaram-14-verses-on-madurai-jewellers-street-and-gold-refining",
        "DESCRIBES",
        "place-madurai-ancient-pandya-jewellers-guild-haven",
        "core",
        "Post-Sangam Era",
        "Silappadikaram verses describe the goldsmiths street and refining hearths of Madurai.",
        "Silappadikaram 14:180-215"
    ],
    [
        "technology-thattar-kodu-and-oothu-kuzhal-blowpipe-cupellation-and-gold-assaying",
        "PURIFIES",
        "concept-kundrumani-abrus-precatorius-standard-seed-gravimetric-metrology",
        "core",
        "Iron Age to Modern Era",
        "Purified gold was weighed in calibrated balances against standard kundrumani seeds.",
        "Tholkappiyam Marapiyal on Weights"
    ],
    [
        "technology-thattar-kodu-and-oothu-kuzhal-blowpipe-cupellation-and-gold-assaying",
        "FABRICATES",
        "artifact-makara-kundalam-gold-filigree-earrings-and-granulated-pendants",
        "core",
        "Iron Age to Medieval Era",
        "Crucible-melted gold was drawn into fine wires to form royal makara earrings.",
        "Silappadikaram 6:85-110"
    ],
    [
        "technology-kadal-mani-and-pon-granulation-micro-droplet-gold-soldering",
        "ADORES",
        "artifact-makara-kundalam-gold-filigree-earrings-and-granulated-pendants",
        "core",
        "Iron Age to Medieval Era",
        "Micro-granulation droplets decorated the borders and drops of makara kundalam.",
        "Maryon: Metalwork and Enamelling"
    ],
    [
        "concept-pon-akkam-gold-mercury-fire-gilding-and-surface-enrichment",
        "APPLIED_TO",
        "artifact-kasu-malai-and-kural-gold-coin-necklaces-and-repousse-amulets",
        "core",
        "Classical Antiquity to Modern Era",
        "Fire-gilding and surface enrichment adorned repousse amulets and coin necklaces.",
        "Purananuru 218"
    ],
    [
        "concept-uravuk-kallu-touchstone-streak-colorimetry-and-karat-purity-grading",
        "REGULATED_BY",
        "institution-akkar-and-thattar-corporation-of-royal-goldsmiths-and-mint-masters",
        "core",
        "Iron Age to Modern Era",
        "Touchstone streak testing was regulated by royal mint masters and guild inspectors.",
        "Thirukkural 505 Commentaries"
    ],
    [
        "institution-akkar-and-thattar-corporation-of-royal-goldsmiths-and-mint-masters",
        "OPERATED_AT",
        "place-madurai-ancient-pandya-jewellers-guild-haven",
        "core",
        "Sangam Era to Modern Era",
        "The Pandyan Akka-Saalai royal mint and jewellers guild operated in Madurai.",
        "Maduraikkanchi 490-530"
    ],
    [
        "artifact-kasu-malai-and-kural-gold-coin-necklaces-and-repousse-amulets",
        "PRESERVED_AT",
        "place-madurai-ancient-pandya-jewellers-guild-haven",
        "core",
        "Sangam Era to Modern Era",
        "Pandyan royal treasuries and temple vaults in Madurai preserved masterwork kasu-malai.",
        "Roman Coin Hoards in Tamil Nadu"
    ],
    [
        "technology-thattar-kodu-and-oothu-kuzhal-blowpipe-cupellation-and-gold-assaying",
        "GOVERNED_BY",
        "institution-akkar-and-thattar-corporation-of-royal-goldsmiths-and-mint-masters",
        "core",
        "Iron Age to Modern Era",
        "State assayers supervised blowpipe cupellation and hallmarking inside the mint.",
        "South Indian Inscriptions Vol. III"
    ],
    [
        "concept-uravuk-kallu-touchstone-streak-colorimetry-and-karat-purity-grading",
        "TESTS",
        "concept-kundrumani-abrus-precatorius-standard-seed-gravimetric-metrology",
        "core",
        "Iron Age to Modern Era",
        "Touchstone colorimetry and kundrumani balances formed the twin pillars of gold appraisal.",
        "Silappadikaram 14"
    ]
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]

def main():
    print("Starting Ingestion Batch 36: Ancient Tamil Goldsmithing, Granulation & Filigree Regalia...")
    
    # Phase 1: Write Dossiers
    print("Phase 1: Writing Markdown Dossiers...")
    for d in DOSSIERS:
        fpath = os.path.join(MOOLAM_KNOWLEDGE, d["file"])
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        print(f"  ✓ Written: {d['file']}")

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Phase 2: Upsert Lore Nodes
    print("Phase 2: Upserting Lore Nodes...")
    nodes_upserted = 0
    for d in DOSSIERS:
        slug = d["slug"]
        props = json.dumps({"category": d["category"], "canonical_file": d["file"]})
        cur.execute("""
            INSERT INTO lore_nodes (
                id, slug, node_type, name_en, name_ta, era, year_start, year_end,
                thinai, summary_en, summary_ta, sources, layer, properties, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, NOW()
            )
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
            str(uuid.uuid4()), slug, d["category"], d["name_en"], d["name_ta"],
            d["era"], d["year_start"], d["year_end"], d.get("thinai"),
            d["summary_en"], d["summary_ta"], d["sources"], "core", props
        ))
        nodes_upserted += 1
        print(f"  ✓ Upserted node: {slug}")
    conn.commit()

    # Phase 3: Insert Lore Edges
    print("Phase 3: Inserting Lore Edges...")
    edges_inserted = 0
    for edge in EDGES:
        src, rel, tgt, layer, era, desc, evidence = edge
        cur.execute("""
            DELETE FROM lore_edges
            WHERE source_slug = %s AND relation_type = %s AND target_slug = %s;
        """, (src, rel, tgt))
        cur.execute("""
            INSERT INTO lore_edges (
                id, source_slug, relation_type, target_slug, layer, era,
                description, evidence_source
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            );
        """, (
            str(uuid.uuid4()), src, rel, tgt, layer, era, desc, evidence
        ))
        edges_inserted += 1
        print(f"  ✓ Linked: ({src}) --[{rel}]-> ({tgt})")
    conn.commit()

    # Phase 4: Embed & Insert RAG Chunks
    print("Phase 4: Embedding RAG Chunks with bge-m3:latest...")
    total_chunks = 0
    for d in DOSSIERS:
        slug = d["slug"]
        cur.execute("DELETE FROM rag_chunks WHERE node_slug = %s;", (slug,))
        chunks = [
            {
                "language": "en",
                "title": d["name_en"],
                "content": f"{d['name_en']}\n\nSummary:\n{d['summary_en']}\n\nKey Concepts:\n{d['content'][:1500]}"
            },
            {
                "language": "ta",
                "title": d["name_ta"],
                "content": f"{d['name_ta']}\n\nசுருக்கம்:\n{d['summary_ta']}\n\nமுக்கிய நுட்பங்கள்:\n{d['content'][:1500]}"
            }
        ]
        for ch in chunks:
            emb = get_bge_embedding(ch["content"])
            emb_str = "[" + ",".join(str(x) for x in emb) + "]"
            cur.execute("""
                INSERT INTO rag_chunks (
                    id, node_slug, shelf, language, title, content,
                    source_ref, embedding, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                );
            """, (
                str(uuid.uuid4()),
                slug,
                f"shelf-{d['category']}s",
                ch["language"],
                ch["title"],
                ch["content"],
                d["file"],
                emb_str
            ))
            total_chunks += 1
        print(f"  ✓ Embedded 2 chunks for: {slug}")
    conn.commit()
    cur.close()
    conn.close()

    print(f"Ingestion Complete for Batch 36 Corpus! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
