#!/usr/bin/env python3
"""
Harvester: Batch 47 - Ancient Tamil Ceremonial Fans, Palmyra Folding Visiri, Vetiver Evaporative Cooling & Temple Alavattam Regalia
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
        "slug": "text-silappadikaram-and-chola-inscriptions-on-ven-chamarai-alavattam-and-visiri",
        "category": "text",
        "file": "text-silappadikaram-and-chola-inscriptions-on-ven-chamarai-alavattam-and-visiri.md",
        "name_en": "Silappadikaram, Perumpanarruppadai & Chola Epigraphy on Ven-Chamarai, Alavattam & Visiri",
        "name_ta": "சிலப்பதிகாரம், பெரும்பாணாற்றுப்படை மற்றும் சோழர் கல்வெட்டுகளில் வெண்சாமரை, ஆலவட்டம், விசிறி",
        "era": "Sangam to Imperial Chola Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "marutham",
        "summary_en": "Classical Tamil literary and epigraphical records in Silappadikaram, Perumpanarruppadai, Manimekalai, and Thanjavur Chola inscriptions documenting royal yak-tail fly-whisks (ven-chamarai), circular sun-disc ceremonial fans (alavattam / talavrinta), and woven palmyra and fragrant root hand-fans (visiri).",
        "summary_ta": "சிலப்பதிகாரம், பெரும்பாணாற்றுப்படை, மணிமேகலை மற்றும் தஞ்சைப் பெரியகோவில் சோழர் கல்வெட்டுகளில் பதிவு செய்யப்பட்டுள்ள வெண்சாமரை, ஆலவட்டம் மற்றும் பனையோலை, வெட்டிவேர் விசிறி பற்றிய சான்றுகள்.",
        "sources": [
            "Silappadikaram Indiravizhavureduthakathai",
            "Perumpanarruppadai",
            "South Indian Inscriptions Vol II (Thanjavur Rajarajesvaram)",
            "Manimekalai"
        ],
        "content": "# Classical Tamil Literature & Epigraphy on Ceremonial Fans\n\nSangam poetry, post-Sangam epics, and Imperial Chola temple inscriptions provide detailed accounts of both domestic cooling hand-fans (*visiri*) and sovereign ceremonial fans (*chamaram* and *alavattam*):\n\n**Literary & Epigraphical Attestations:**\n- **Silappadikaram & Perumpanarruppadai**: *Silappadikaram* describes royal processions in Puhar and Madurai where white yak-tail whisks (*ven-chamarai*) and circular standards (*alavattam*) flanked the pearl canopy (*muthu-pandal*), while court attendants fanned sleeping chambers with fragrant sandal- and *vettiver*-moistened fans.\n- **Thanjavur Chola Inscriptions**: Rajaraja Chola I's inscriptions at the Brihadisvara temple (recorded in *South Indian Inscriptions*) itemize gold- and silver-mounted fly-whisks (*பொற்காம்பு வெண்சாமரை*) and jewel-fringed *alavattam* sun-fans gifted to the *Utsava* deities."
    },
    {
        "slug": "concept-vetiver-root-evaporative-thermodynamics-and-sesquiterpene-volatiles",
        "category": "concept",
        "file": "concept-vetiver-root-evaporative-thermodynamics-and-sesquiterpene-volatiles.md",
        "name_en": "Vetiver Root Evaporative Psychrometrics, Latent Heat Cooling & Sesquiterpene Aromatics",
        "name_ta": "வெட்டிவேர் விசிறியின் ஆவியாதல் வெப்ப இயக்கவியலும் செஸ்குவிடெர்பீன் நறுமண வேதியியலும்",
        "era": "Ancient to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Thermodynamic and phytochemical principles of water-sprinkled Chrysopogon zizanioides (vettiver / khus root) fans: spongy root-cortex capillary water retention, psychrometric wet-bulb cooling of forced air via latent heat of vaporization, and aerosolized release of sedative sesquiterpene alcohols (khusimol, alpha- and beta-vetivone).",
        "summary_ta": "நீர் தெளித்த வெட்டிவேர் விசிறியின் நுண்புழை நீர் உறிஞ்சும் தன்மை, ஆவியாதல் மறைவெப்பத்தால் காற்றைக் குளிர்விக்கும் இயற்பியல் மற்றும் குசிமோல், வெட்டிவோன் நறுமணக் கூட்டுப்பொருட்களின் மருத்துவக் குணம்.",
        "sources": [
            "Phytochemistry of Chrysopogon zizanioides Essential Oils",
            "Psychrometric Evaporative Cooling in Traditional Indian Architecture",
            "Siddha Materia Medica (Gunapadam Mooligai Vaguppu)"
        ],
        "content": "# Vetiver Root Evaporative Thermodynamics & Sesquiterpene Volatiles\n\nWhen a woven *vettiver* (*Chrysopogon zizanioides*, Tamil *Vettiver* or *Vilamichai*) fan is dipped or sprinkled with cool water prior to waving, it acts as a miniature hand-powered evaporative air conditioner:\n\n**Thermodynamic & Phytochemical Mechanisms:**\n- **Adiabatic Latent-Heat Absorption**: The fibrous root cortex contains a high-surface-area network oferenchyma channels that hold up to $2.5\\times$ their dry weight in water without dripping. Waving the fan forces ambient dry summer air ($38-42^\\circ\\text{C}$) across the wet root lattice; water evaporation absorbs $\\approx 2400\\text{ kJ/kg}$ of latent heat, dropping the local airstream temperature by $5-8^\\circ\\text{C}$ toward the wet-bulb temperature.\n- **Sesquiterpene Volatilization**: Hydration swells the oil cells in the root pericycle, releasing high-boiling oxygenated sesquiterpenes—principally *khusimol*, *$\\alpha$-vetivone*, and *$\\beta$-vetivone*—known in Siddha medicine to reduce heat stress (*pitha-choodu*) and heart rate."
    },
    {
        "slug": "concept-borassus-flabellifer-petiole-hinge-mechanics-and-accordion-pleat-stiffness",
        "category": "concept",
        "file": "concept-borassus-flabellifer-petiole-hinge-mechanics-and-accordion-pleat-stiffness.md",
        "name_en": "Palmyra Leaf (Borassus flabellifer) Accordion-Pleat Stiffness & Petiole Hinge Mechanics",
        "name_ta": "பனையோலை விசிறியின் மடிப்பு விறைப்புத்தன்மை மற்றும் மட்டைக் காம்பு சுழல் பொறியியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "palai",
        "summary_en": "Structural biomechanics of the palmyra palm frond (Borassus flabellifer, panai-olai) in fixed and collapsible Tamil fans: corrugated V-pleat geometry multiplying flexural rigidity (second moment of area) while keeping mass minimal, and natural lignified vascular bundle convergence at the petiole hastula acting as an integral torsion hinge.",
        "summary_ta": "பனையோலையின் இயற்கையான விசிறி மடிப்பு அமைப்பு (Corrugated pleats) குறைந்த எடையில் அதிகக் காற்றைத் தள்ளும் விறைப்புத்தன்மையை அளிப்பதும், மட்டைக் காம்பின் நார் முடிச்சு சுழல் அச்சாகச் செயல்படுவதும்.",
        "sources": [
            "Biomechanics of Fan-Leaved Palms (Borassus flabellifer)",
            "Blatter Palms of British India",
            "Traditional Palmyra Craft Engineering of Tamil Nadu"
        ],
        "content": "# Palmyra Leaf Accordion-Pleat Stiffness & Petiole Mechanics\n\nThe palmyra palm (*Borassus flabellifer*, the state tree of Tamil Nadu) possesses a costapalmate leaf blade whose natural botanical architecture is pre-engineered for aerodynamic fan construction:\n\n**Biomechanical Principles:**\n- **Corrugated Pleat Moment of Inertia**: A flat leaf lamina of $0.4\\text{ mm}$ thickness would flutter uselessly under aerodynamic drag. The natural zig-zag accordion folding of the *panai-olai* segments increases the effective structural depth $h$ to $15-25\\text{ mm}$, raising the second moment of area ($I \\propto h^3$) by over two orders of magnitude so each stroke displaces a coherent vortex ring of air.\n- **Hastula & Petiole Integration**: All radial leaf ribs converge into the woody, silica-reinforced petiole stalk (*mattai-kambu*), allowing craftsmen to carve a single monolithic fan where handle and blade share continuous longitudinal sclerenchyma fibers."
    },
    {
        "slug": "concept-shodasa-upachara-ritual-aeration-and-royal-ashta-mangala-insignia",
        "category": "concept",
        "file": "concept-shodasa-upachara-ritual-aeration-and-royal-ashta-mangala-insignia.md",
        "name_en": "Shodasa-Upachara Ritual Aeration (Chamara-Vyajana Seva) & Ashta-Mangala Sovereign Regalia",
        "name_ta": "சோடச உபசார சாமர-வியஜன சேவையும் அஷ்டமங்கல அரச-ஆலய விருது மரபும்",
        "era": "Pallava to Modern Era",
        "year_start": 600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Agamic liturgical theory and royal political theology of ceremonial fans in Tamil Nadu: Vyajana-upachara (fanning with palmyra/alavattam) and Chamara-upachara (whisking with white yak tails) within the sixteen sacred honours (Shodasa-Upachara), and their inclusion among the eight auspicious emblems (Ashta-Mangala) signifying universal sovereignty.",
        "summary_ta": "ஆகம வழிபாட்டின் பதினாறு உபசாரங்களில் (சோடச உபசாரம்) இறைவனுக்குச் செய்யப்படும் சாமர மற்றும் ஆலவட்ட விசிறிச் சேவைகளும், அஷ்டமங்கலப் பொருட்களில் ஒன்றாகப் போற்றப்படும் அரச மரியாதை மரபும்.",
        "sources": [
            "Kamikagama & Karanagama Upachara Vidhi",
            "T.A. Gopinatha Rao Elements of Hindu Iconography",
            "Chola & Pandya Royal Insignia Studies"
        ],
        "content": "# Shodasa-Upachara Ritual Aeration & Ashta-Mangala Regalia\n\nIn South Indian Shaiva (*Kamikagama*) and Vaishnava (*Pancharatra*) temple liturgy, the consecrated deity in the sanctum (*moolavar*) and processional chariot (*utsavar*) is accorded the exact ceremonial honours of an earthly emperor (*Chakravartin*):\n\n**Liturgical & Sovereign Symbolism:**\n- **Vyajana & Chamara Upacharas**: Following the anointing (*abhishekam*), dressing (*alankaram*), and camphor lamp waving (*deeparadhana*), priests perform *Vyajana-upachara* (waving the circular *alavattam* or *vettiver* fan to soothe the heat of camphor flames) and *Chamara-upachara* (waving twin silver-handled white yak-tail whisks).\n- **Ashta-Mangala & Sun-Moon Cosmology**: The pair of circular *alavattam* discs held flanking the deity represent *Surya* (Sun) and *Chandra* (Moon), while the white *ven-chamarai* ranks among the eight auspicious *Ashta-Mangala* emblems symbolizing spotless fame and protective grace."
    },
    {
        "slug": "technology-panai-olai-steaming-radial-slitting-and-surul-visiri-pivot-weaving",
        "category": "technology",
        "file": "technology-panai-olai-steaming-radial-slitting-and-surul-visiri-pivot-weaving.md",
        "name_en": "Panai-Olai Steaming, Petiole Bending & Collapsible Surul-Visiri Pivot-Fan Fabrication",
        "name_ta": "பனையோலை வேகவைப்பு, மட்டை வளைப்பு மற்றும் சுருள் விசிறி (மடக்கு விசிறி) செய்யும் தொழில்நுட்பம்",
        "era": "Ancient to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Artisanal manufacturing process for Tamil palmyra hand-fans (panai-olai visiri) and 360-degree collapsible folding fans (surul-visiri / madakku-visiri): harvesting unopened ivory-white crown fronds (kurutholai), boiling with turmeric, crimping tight accordion pleats, binding rims with split bamboo and dyed strip borders, and fitting wire/wood pivot spindles.",
        "summary_ta": "இளம் பனைக் குருத்தோலையை நறுக்கி, மஞ்சள் நீரில் வேகவைத்து, நிழலில் உலர்த்தி, மூங்கில் சிம்பு மற்றும் வண்ண ஓலைக் கரைகள் கட்டி நிலையான விசிறி மற்றும் மடங்கும் சுருள் விசிறி செய்யும் நுட்பம்.",
        "sources": [
            "Handicrafts of Tamil Nadu: Palmyra Leaf Products",
            "Census of India 1961 Handicraft Survey: Palm Leaf Craft",
            "Thanjavur & Tirunelveli Palmyra Artisans Ethnography"
        ],
        "content": "# Panai-Olai Steaming & Collapsible Surul-Visiri Fabrication\n\nTamil palmyra weavers (*Olai-Varaipavar*) manufacture two distinct classes of palm-leaf fans—the rigid kidney- or wheel-shaped domestic fan (*Sadha-Visiri*) and the ingenious telescoping pocket fan (*Surul-Visiri* or *Madakku-Visiri*):\n\n**Fabrication Workflow:**\n- **Kurutholai Curing & Pleat Crimping**: Unopened pale-yellow heart fronds (*kurutholai*) are cut before chlorophyll toughens the epidermis, momentarily dipped in boiling turmeric water to prevent fungal spotting, shade-dried for three days, and compressed inside a wooden pleating clamp (*achchu*) to set razor-sharp accordion folds.\n- **Surul-Visiri Pivot Mechanism**: In the collapsible *surul-visiri*, a long pleated ribbon of palmyra leaf is gathered at its inner radius around a turned wooden handle spindle while its outer rim is stitched to a split-bamboo guide rod; rotating the rod $360^\\circ$ unfurls a full circular rosette that furls back into a compact tube."
    },
    {
        "slug": "technology-vettiver-root-mat-braiding-and-thanjavur-appliqued-alavattam-embroidery",
        "category": "technology",
        "file": "technology-vettiver-root-mat-braiding-and-thanjavur-appliqued-alavattam-embroidery.md",
        "name_en": "Vettiver Root Twined-Weaving & Thanjavur Appliqué (amalai) Temple Alavattam Craft",
        "name_ta": "வெட்டிவேர் விசிறி பின்னல் கலையும் தஞ்சாவூர் தையல்காரர் ஆலவட்டத் துணி வேலைப்பாட்டு நுட்பமும்",
        "era": "Medieval Chola to Modern Era",
        "year_start": 900,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Dual specialist fan-making technologies of the Kaveri delta: twined weaving of cleaned riverine vetiver roots with dyed cotton warp threads and fragrant screw-pine (thazhampoo) strips into crescent hand-fans, and the Thanjavur Thayyal-Kaarar textile craft of stretching woollen broadcloth (banath) and velvet appliqué over cane hoops to make temple alavattam standards.",
        "summary_ta": "காவேரிப் படுகையின் வெட்டிவேர் மற்றும் தாழம்பூ நார்களை வண்ண நூல்களால் பின்னும் கலையும், தஞ்சாவூர் தையல் கலைஞர்கள் பானாத்து மற்றும் வெல்வெட் துணிகளில் ஜரிகை வைத்துத் தைக்கும் ஆலவட்ட உருவாக்க நுட்பமும்.",
        "sources": [
            "Thanjavur Temple Appliqué Craft Documentation (GI Registry)",
            "Craft Traditions of India: Jaya Jaitly",
            "Madras Presidency Industrial Arts Survey"
        ],
        "content": "# Vettiver Root Braiding & Thanjavur Appliqué Alavattam Craft\n\nThe Kaveri delta around Thanjavur and Kumbakonam sustains two highly specialized ceremonial fan-making guilds:\n\n**Artisanal Techniques:**\n- **Twined Vettiver & Thazhampoo Weaving**: Harvested aromatic *vettiver* roots are washed, combed straight, graded by thickness, and compressed into a dense radiating pad. Artisans use double-strand cotton twining (*irattai-nool kattu*) to lock the roots into a crescent or lotus outline, edging the perimeter with dyed palmyra strips and fragrant dried *thazhampoo* (*Pandanus odorifer*) bracts.\n- **Thanjavur Appliqué (*Alavattam* Tailoring)**: Hereditary *Thayyal-Kaarar* tailors bend seasoned *pirambu* (rattan cane) into twin circular hoops ($60-90\\text{ cm}$ diameter), stretch crimson and emerald woollen felt (*banath*) across both faces, and stitch cut-cloth appliqué iconography (*Mayil*, *Rishabha*, *Ganda-Bherunda*), metallic *zari* lace, and pleated silk frills (*koyyagam*) around the rim."
    },
    {
        "slug": "artifact-ven-chamarai-silver-mounted-yak-tail-whisks-and-twin-alavattam-standards",
        "category": "artifact",
        "file": "artifact-ven-chamarai-silver-mounted-yak-tail-whisks-and-twin-alavattam-standards.md",
        "name_en": "Ven-Chamarai Silver-Mounted Yak-Tail Fly-Whisks & Twin Irattai-Alavattam Processional Discs",
        "name_ta": "வெள்ளிப் பூண் கட்டிய வெண்சாமரை கவரிமான் விசிறிகளும் இரட்டை ஆலவட்ட ஊர்வல விருதுகளும்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Sacred processional fan regalia of Tamil temples: the Ven-Chamarai (white Bos grunniens yak-tail plume set into a repoussé silver or goldsocket handle carved with makara and lotus motifs) and the Irattai-Alavattam (pair of long-poled circular cloth-appliqued sun-and-moon fans carried beside the deity on street processions).",
        "summary_ta": "ஆலய வீதி உலாக்களில் இறைவன் திருமேனிக்கு இருபுறமும் வீசப்படும் வெள்ளி மற்றும் தங்கக் கைப்பிடி கொண்ட வெண்சாமரை (கவரி) விசிறிகளும், நீண்ட தண்டு கொண்ட இரட்டை ஆலவட்டக் கொடிகளும்.",
        "sources": [
            "Thanjavur Palace & Brihadisvara Temple Treasury Inventories",
            "Madurai Meenakshi Temple Vahana & Regalia Records",
            "George Michell Temple Architecture and Art of Southern India"
        ],
        "content": "# Ven-Chamarai Yak-Tail Whisks & Irattai-Alavattam Discs\n\nDuring daily *Deeparadhana* and grand street processions (*ther* and *vahana-purappadu*), two distinct classes of ceremonial fans accompany the presiding deity:\n\n**Regalia Specifications:**\n- **Ven-Chamarai (*Kavari-Visiri*)**: Composed of a dense, silky white tail plume of the Himalayan yak (*Bos grunniens*, classically called *kavari-maan* in Tamil poetry) crimped into a flaring bell-shaped ferrule of chased silver or gold plate (*kazhuthu-poon*) mounted on a turned ivory, sandalwood, or silver shaft ($40-50\\text{ cm}$ long). Two attendants wave them in synchronized upward figure-eight arcs.\n- **Irattai-Alavattam (Twin Disc Standards)**: Mounted on $2.5\\text{-meter}$ lacquered bamboo or brass-sheathed poles with a perpendicular neck bracket, these twin circular fans are rotated edgewise to catch the breeze and pivoted flat to shield and cool the deity."
    },
    {
        "slug": "artifact-mayil-peeli-visiri-peacock-feather-fans-and-medicinal-vettiver-hand-fans",
        "category": "artifact",
        "file": "artifact-mayil-peeli-visiri-peacock-feather-fans-and-medicinal-vettiver-hand-fans.md",
        "name_en": "Mayil-Peeli Peacock-Feather Ritual Fans & Medicinal Vettiver-Thazhampoo Hand-Fans",
        "name_ta": "மயில்பீலி சடங்கு விசிறிகளும் மருத்துவக் குணமுடைய வெட்டிவேர்-தாழம்பூ கைவிசிறிகளும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Specialized organic fans in Tamil ritual and Siddha healthcare: concentric peacock tail-feather fans (mayil-peeli visiri / kundalam) bound with split cane quills for Murugan worship, Siddha therapeutic sweeping, and royal court regalia, paired with aromatic vettiver and screw-pine (thazhampoo) hand-fans prized in Carnatic music sabhas and bridal trousseaus.",
        "summary_ta": "முருகப்பெருமான் வழிபாட்டிலும் சித்த மருத்துவத்திலும் பயன்படும் மயில்பீலி விசிறிகளும், திருமணச் சீர்வரிசை மற்றும் இசை அரங்குகளில் போற்றப்படும் வெட்டிவேர்-தாழம்பூ நறுமணக் கைவிசிறிகளும்.",
        "sources": [
            "Palani & Tiruchendur Murugan Temple Ritual Inventories",
            "Siddha Vaidya Tirattu (Therapeutic Fanning Practices)",
            "DakshinaChitra Heritage Fan Collection"
        ],
        "content": "# Mayil-Peeli Peacock-Feather Fans & Medicinal Vettiver Hand-Fans\n\nBeyond palmyra leaf and cloth *alavattam*, Tamil artisans craft specialized ceremonial and therapeutic fans from shed peacock plumes and medicinal roots:\n\n**Artifact Typology:**\n- **Mayil-Peeli Visiri (Peacock-Feather Fans)**: Constructed from $100$ to $300$ naturally molted iridescent ocellus (\"eye\") tail feathers of the Indian peafowl (*Pavo cristatus*). The white hollow keratin quills (*iragu-thandu*) are split, woven into a concentric geometric lattice at the base with dyed thread, and fitted into a wooden or silver handle. Essential in Lord Murugan (*Kumara*) sanctums, *Kavadi* processions, and Siddha healing rituals (*mantra-veesuthal*).\n- **Bridal & Sabha Vettiver Hand-Fans**: Finely braided *vettiver* fans edged with *thazhampoo* petals and silk tassels are traditionally presented in Tamil wedding *seer-varisai* trays and carried to summer *kutcheri* music pavilions."
    },
    {
        "slug": "institution-temple-alavattam-chamaram-service-tenures-and-thanneer-pandal-visiri-dharmam",
        "category": "institution",
        "file": "institution-temple-alavattam-chamaram-service-tenures-and-thanneer-pandal-visiri-dharmam.md",
        "name_en": "Temple Alavattam-Kaani Service Tenures & Summer Thanneer-Pandal Visiri-Dharmam Charities",
        "name_ta": "ஆலய ஆலவட்டக் காணி ஊழிய முறையும் கோடைக்காலத் தண்ணீர்ப்பந்தல் விசிறி தர்ம அறக்கட்டளைகளும்",
        "era": "Chola to Colonial Era",
        "year_start": 900,
        "year_end": 1950,
        "thinai": "marutham",
        "summary_en": "Institutional frameworks governing ceremonial and charitable cooling in Tamil society: hereditary temple service grants (alavattam-kaani and chamaram-manyam) endowing attendants and tailors to maintain and wave sacred fans during pujas and processions, and summer highway charities (thanneer-pandal visiri-dharmam) distributing free palmyra fans and spiced buttermilk to travellers.",
        "summary_ta": "கோவில்களில் ஆலவட்டம் மற்றும் சாமரம் வீசும் பணியாளர்களுக்கு வழங்கப்பட்ட மானிய நில உரிமைகளும் (ஆலவட்டக் காணி), சித்திரை-வைகாசி கோடையில் வழிப்போக்கர்களுக்கு நீர்மோருடன் பனையோலை விசிறி வழங்கும் தர்ம சத்திர மரபும்.",
        "sources": [
            "South Indian Inscriptions (Temple Paricharakar & Alavattam Endowments)",
            "Thanjavur Maratha Modi Records on Chathiram Charities",
            "Colonial District Gazetteers of Tanjore & Madura"
        ],
        "content": "# Temple Alavattam Service Tenures & Summer Visiri-Dharmam Charities\n\nThe production and deployment of fans in historical Tamil Nadu were anchored by two enduring civic and religious institutions:\n\n**Endowments & Public Charities:**\n- **Temple Alavattam-Kaani & Chamaram-Manyam**: Chola, Pandya, Vijayanagara, and Nayak stone inscriptions record tax-free wet-land endowments (*manyam*) granted to hereditary temple attendants (*Alavattakkarar* and *Chamaram-Paricharakar*) and temple tailors (*Thayyal-Kaani*) responsible for renewing appliqued *alavattam* covers before annual *Brahmotsavam* car festivals and fanning the deity during every *kala-puja*.\n- **Summer Thanneer-Pandal & Visiri-Dharmam**: During the blazing *Agni-Nakshatram* (*Kallaththiri*) summer peak across *Chithirai* and *Vaikasi*, merchant guilds and Maratha/Nayak *chathiram* foundations erected thatched wayside *thanneer-pandal* booths offering free spiced buttermilk (*neer-mor*), jaggery *panakam*, and thousands of newly woven palmyra hand-fans (*visiri-dhaanam*) to pilgrims and scholars."
    },
    {
        "slug": "place-vallam-ancient-thanjavur-palmyra-visiri-and-vetiver-fan-haven",
        "category": "place",
        "file": "place-vallam-ancient-thanjavur-palmyra-visiri-and-vetiver-fan-haven.md",
        "name_en": "Vallam–Thanjavur: Ancient Palmyra Surul-Visiri, Vetiver Root & Temple Alavattam Haven",
        "name_ta": "வல்லம்–தஞ்சாவூர் - பண்டைய பனையோலைச் சுருள் விசிறி, வெட்டிவேர் மற்றும் ஆலவட்டக் கலைத் தளம்",
        "era": "Chola to Modern Era",
        "year_start": 850,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Historic craft corridor linking the Vallam tableland and Thanjavur (lat 10.7180, lng 79.0600, thinai: marutham) on the Kaveri delta border, celebrated for over a millennium as the premier artisanal hub uniting upland palmyra leaf folding fans (surul-visiri), sandy riverbank vetiver root fans, and royal/temple appliqued alavattam regalia.",
        "summary_ta": "தஞ்சாவூர்–வல்லம் பகுதியில் (அட்சரேகை 10.7180, தீர்க்கரேகை 79.0600) மருத நில ஆற்றுப் படுகையும் வல்லம் மேட்டுநிலப் பனை வளமும் இணைந்து உருவாக்கிய சுருள் விசிறி, வெட்டிவேர் விசிறி மற்றும் ஆலவட்டத் தயாரிப்புத் தளம்.",
        "sources": [
            "Tanjore District Gazetteer (Hemingway 1906)",
            "Geographical Indications Registry: Thanjavur Netti & Appliqué Works",
            "Craft Survey of Vallam & Thanjavur Taluk"
        ],
        "content": "# Vallam–Thanjavur: Palmyra Visiri, Vetiver & Alavattam Haven\n\nLocated at latitude $10.7180^\\circ\\text{ N}$, longitude $79.0600^\\circ\\text{ E}$ where the lateritic upland plateau of Vallam meets the fertile *marutham* alluvial delta of Thanjavur, this ecological ecotone has served since early Chola times as Tamil Nadu's foremost center of fan craftsmanship:\n\n**Ecological & Artisanal Convergence:**\n- **Upland Palmyra & Delta Vetiver**: The dry red-gravel tableland around Vallam fort supports dense groves of *Borassus flabellifer* yielding superior, pliable *kurutholai* fronds for weaving *surul-visiri* folding fans and dyed *panai-olai* hand-fans, while the nearby sandy floodplains of the Vennar and Kudamurutti channels cultivate long, aromatic *vettiver* roots.\n- **Thanjavur Temple Workshops**: Along the streets surrounding the Brihadisvara temple and palace, hereditary *Thayyal* and brazier families assemble silver-mounted *ven-chamarai* whisks and richly embroidered *irattai-alavattam* discs supplied to temples across South India."
    }
]

EDGES = [
    [
        "text-silappadikaram-and-chola-inscriptions-on-ven-chamarai-alavattam-and-visiri",
        "documents",
        "artifact-ven-chamarai-silver-mounted-yak-tail-whisks-and-twin-alavattam-standards",
        "material_culture",
        "Sangam to Imperial Chola Era",
        "Silappadikaram and Thanjavur Chola inscriptions document silver- and gold-mounted ven-chamarai yak-tail whisks and twin alavattam discs.",
        "South Indian Inscriptions Vol II"
    ],
    [
        "concept-vetiver-root-evaporative-thermodynamics-and-sesquiterpene-volatiles",
        "governs",
        "technology-vettiver-root-mat-braiding-and-thanjavur-appliqued-alavattam-embroidery",
        "material_culture",
        "Ancient to Modern Era",
        "Evaporative latent-heat cooling and sesquiterpene volatile release govern the dense twined root structure of vettiver fans.",
        "Siddha Gunapadam & Psychrometrics"
    ],
    [
        "concept-borassus-flabellifer-petiole-hinge-mechanics-and-accordion-pleat-stiffness",
        "enables",
        "technology-panai-olai-steaming-radial-slitting-and-surul-visiri-pivot-weaving",
        "material_culture",
        "Iron Age to Modern Era",
        "Corrugated accordion-pleat stiffness and woody petiole fiber continuity enable monolithic and 360-degree collapsible palmyra fans.",
        "Palms of British India"
    ],
    [
        "concept-shodasa-upachara-ritual-aeration-and-royal-ashta-mangala-insignia",
        "prescribes",
        "artifact-ven-chamarai-silver-mounted-yak-tail-whisks-and-twin-alavattam-standards",
        "material_culture",
        "Pallava to Modern Era",
        "Agamic Shodasa-Upachara liturgy prescribes waving twin alavattam sun-moon standards and white yak-tail chamaram whisks before the deity.",
        "Kamikagama Upachara Vidhi"
    ],
    [
        "technology-vettiver-root-mat-braiding-and-thanjavur-appliqued-alavattam-embroidery",
        "fabricates",
        "artifact-ven-chamarai-silver-mounted-yak-tail-whisks-and-twin-alavattam-standards",
        "material_culture",
        "Medieval Chola to Modern Era",
        "Thanjavur Thayyal-Kaarar artisans stretch woollen banath and velvet appliqué over rattan hoops to fabricate twin temple alavattam fans.",
        "Thanjavur Appliqué GI Dossier"
    ],
    [
        "technology-vettiver-root-mat-braiding-and-thanjavur-appliqued-alavattam-embroidery",
        "produces",
        "artifact-mayil-peeli-visiri-peacock-feather-fans-and-medicinal-vettiver-hand-fans",
        "material_culture",
        "Ancient to Modern Era",
        "Twined root-and-quill braiding techniques produce fragrant vettiver-thazhampoo hand-fans and concentric peacock-feather ritual fans.",
        "Handicrafts of Tamil Nadu"
    ],
    [
        "technology-panai-olai-steaming-radial-slitting-and-surul-visiri-pivot-weaving",
        "supplies",
        "institution-temple-alavattam-chamaram-service-tenures-and-thanneer-pandal-visiri-dharmam",
        "material_culture",
        "Chola to Colonial Era",
        "Palmyra fan weavers supply thousands of panai-olai and surul-visiri hand-fans distributed free at summer thanneer-pandal charities.",
        "Thanjavur Maratha Chathiram Records"
    ],
    [
        "institution-temple-alavattam-chamaram-service-tenures-and-thanneer-pandal-visiri-dharmam",
        "maintains",
        "concept-shodasa-upachara-ritual-aeration-and-royal-ashta-mangala-insignia",
        "material_culture",
        "Chola to Colonial Era",
        "Hereditary alavattam-kaani and chamaram-manyam temple tenures maintain uninterrupted daily ritual aeration and festival processional regalia.",
        "South Indian Inscriptions"
    ],
    [
        "place-vallam-ancient-thanjavur-palmyra-visiri-and-vetiver-fan-haven",
        "hosts",
        "technology-panai-olai-steaming-radial-slitting-and-surul-visiri-pivot-weaving",
        "material_culture",
        "Chola to Modern Era",
        "The Vallam-Thanjavur ecotone hosts the premier artisanal clusters weaving palmyra surul-visiri, vettiver fans, and temple alavattam discs.",
        "Tanjore District Gazetteer"
    ],
    [
        "text-silappadikaram-and-chola-inscriptions-on-ven-chamarai-alavattam-and-visiri",
        "celebrates",
        "place-vallam-ancient-thanjavur-palmyra-visiri-and-vetiver-fan-haven",
        "material_culture",
        "Sangam to Imperial Chola Era",
        "Chola royal inscriptions at Thanjavur celebrate the ceremonial fans and regalia crafted in the surrounding Thanjavur-Vallam region.",
        "Brihadisvara Epigraphy"
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
