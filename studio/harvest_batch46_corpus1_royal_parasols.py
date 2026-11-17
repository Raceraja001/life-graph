#!/usr/bin/env python3
"""
Harvester: Batch 46 - Ancient Tamil Ceremonial Parasols, Palmyra & Silk Umbrella Craft & Venkotrakkudai Regalia
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
        "slug": "text-sangam-and-silappadikaram-on-venkotrakkudai-royal-parasol-and-muthukkudai",
        "category": "text",
        "file": "text-sangam-and-silappadikaram-on-venkotrakkudai-royal-parasol-and-muthukkudai.md",
        "name_en": "Purananuru, Tirukkural & Silappadikaram on Venkotrakkudai & Muthukkudai Regalia",
        "name_ta": "புறநானூறு, திருக்குறள் மற்றும் சிலப்பதிகாரத்தில் வெண்கொற்றக்குடை மற்றும் முத்துக்குடை மரபு",
        "era": "Sangam to Post-Sangam Era",
        "year_start": -300,
        "year_end": 600,
        "thinai": "marutham",
        "summary_en": "Classical Tamil literary attestations in Purananuru, Kalithogai, Tirukkural, and Silappadikaram (Indira Vizha and Kalkot Kathai) celebrating the monarch's spotless white parasol (Venkotrakkudai) and the pearl-fringed ceremonial canopy (Muthukkudai) carried during royal and sacred processions.",
        "summary_ta": "புறநானூறு, கலித்தொகை, திருக்குறள் மற்றும் சிலப்பதிகாரத்தில் விவரிக்கப்படும் மன்னனின் வெண்கொற்றக்குடை, முத்துத் தாழ்வடங்கள் தொங்கும் முத்துக்குடை மற்றும் குடைநாட்கோள் சடங்கு.",
        "sources": [
            "Purananuru (Verses 35, 60, 198)",
            "Silappadikaram (Indira Vizha Oor Edutha Kathai & Kalkot Kathai)",
            "Tirukkural (Kural 389)",
            "Tolkappiyam Purathinaiyiyal (Kudai Natkol)"
        ],
        "content": "# Sangam & Silappadikaram Accounts of Venkotrakkudai & Muthukkudai\n\nClassical Tamil literature treats the royal white parasol (*Venkotrakkudai*) and the pearl-strung canopy (*Muthukkudai*) as the highest visible emblems of sovereign protection and ritual honour:\n\n**Key Literary Attestations:**\n- **Purananuru & Kalithogai**: Poets clarify that the king's *Venkotrakkudai* is not raised merely to shield the monarch's own head from the fierce tropical sun, but to cast a cool, protective shade of compassion (*arul-nizhal*) over the distressed subjects of the realm.\n- **Tolkappiyam *Kudai Natkol***: In ancient military protocol (*Vanchi* and *Thumbai* warfare), the auspicious ceremonial dispatch of the king's white parasol (*Kudai Natkol*) on a chosen astrological day preceded the march of the royal army, paralleling the dispatch of the royal sword (*Val Natkol*).\n- **Silappadikaram Processions**: In *Indira Vizha Oor Edutha Kathai* and *Arangerrukathai*, Ilango Adigal describes the solemn state procession of the *Muthukkudai* (pearl-fringed canopy with garlands of Gulf of Mannar pearls) shading the *Thalaikkol* staff and the Chera monarch Senguttuvan's northward expedition."
    },
    {
        "slug": "concept-venkotrakkudai-protective-shade-arul-sovereignty-and-senkol-cosmology",
        "category": "concept",
        "file": "concept-venkotrakkudai-protective-shade-arul-sovereignty-and-senkol-cosmology.md",
        "name_en": "Venkotrakkudai Cosmology: Protective Shade (Arul), Full-Moon Symbolism & Senkol Pairing",
        "name_ta": "வெண்கொற்றக்குடை தத்துவம்: அருள் நிழல், முழுநிலவு உருவகம் மற்றும் செங்கோல் இணை",
        "era": "Sangam to Chola Imperial Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "marutham",
        "summary_en": "Political theology and cosmological symbolism of the Tamil royal parasol (Venkotrakkudai): pairing the cooling lunar umbrella of mercy (arul) with the upright sceptre of justice (senkol), where tyrannical rule causes the white parasol to droop and lose its protective shade.",
        "summary_ta": "தமிழ் அரசியல் தத்துவத்தில் வெண்கொற்றக்குடையின் குறியீடு: நீதியின் சின்னமான செங்கோலுடன் அருளின் சின்னமான வெண்கொற்றக்குடை இணைந்து முழுநிலவு போல் குடிமக்களுக்குத் தண்ணளி வழங்குதல்.",
        "sources": [
            "Purananuru Verse 60",
            "Silappadikaram Vanchikandam",
            "Kamba Ramayanam",
            "Manimekalai"
        ],
        "content": "# Venkotrakkudai Cosmology: Righteous Shade (Arul) & Senkol Pairing\n\nIn classical Tamil political philosophy, sovereignty rests on the complementary polarity of two regalia objects: the upright sceptre (*Senkol*) and the single white parasol (*Venkotrakkudai*):\n\n**Cosmological & Ethical Principles:**\n- **Senkol (Justice) & Venkotrakkudai (Grace)**: While the straight *Senkol* embodies unbending impartial law (*aram*), the *Venkotrakkudai* arching overhead embodies maternal mercy (*arul*) and cool refuge (*thannali*) shielding all living beings from suffering.\n- **Full-Moon & Axis Mundi Iconography**: The circular white silk dome represents the cooling full moon (*ven-thingal*) poised atop a central bamboo or gilded timber shaft symbolizing the cosmic axis (*meru*).\n- **Moral Barometer of Rule**: In *Silappadikaram*, when the Pandya king's *Senkol* bends through a miscarriage of justice, the poet laments that the cooling shade of the *Venkotrakkudai* turns to scorching heat—signifying that moral legitimacy alone sustains the royal canopy."
    },
    {
        "slug": "concept-collapsible-radial-bamboo-rib-kinematics-and-runner-hub-tension",
        "category": "concept",
        "file": "concept-collapsible-radial-bamboo-rib-kinematics-and-runner-hub-tension.md",
        "name_en": "Collapsible Radial Bamboo Rib Kinematics, Sliding Runner Hub & Dome Tension Mechanics",
        "name_ta": "மடக்குக் குடையின் மூங்கில் கம்பி இயக்கவியல், நகரும் குமிழ் மற்றும் விதான இழுவிசைப் பொறியியல்",
        "era": "Sangam to Nayak Era",
        "year_start": -200,
        "year_end": 1750,
        "thinai": "marutham",
        "summary_en": "Structural mechanics of traditional Tamil collapsible and fixed parasols: radial bamboo or cane ribs (kudai-kambi) hinged to a turned hardwood top notch, braced by secondary stretcher struts linked to a sliding cylindrical runner hub locked by a spring-pin or cord.",
        "summary_ta": "பாரம்பரியக் குடைகளின் பொறியியல் அமைப்பு: மேல் மரக் குமிழில் இணைக்கப்பட்ட மூங்கில் கம்பிகள், கீழே நகரும் வளையக் குமிழ் மற்றும் துணி விதானத்தின் வில் வளைவு இழுவிசை.",
        "sources": [
            "Chola Bronze and Mural Iconography of Processional Umbrellas",
            "South Indian Traditional Wood and Bamboo Craft Surveys",
            "Adiyarkkunallar Silappadikaram Commentary"
        ],
        "content": "# Collapsible Radial Rib Kinematics & Runner Hub Tension Mechanics\n\nTraditional Tamil ceremonial and travel umbrellas engineered a high strength-to-weight canopy capable of resisting gusting monsoon winds and processional sway:\n\n**Mechanical Architecture:**\n- **Radial Rib Flexure (*Kudai-Kambi*)**: Seasoned culms of thick-walled thorny bamboo (*Moongil*) or rattan cane (*pirambu*) were split radially into 16, 24, or 32 slender ribs. Retaining the dense outer silica rind (*purathol*) on the upper surface gave each rib elastic bow-spring recovery.\n- **Top Hub & Sliding Runner**: The inner tips of the main ribs were seated in radial kerf slots around a fixed upper wooden crown (*mel-kumizh*) and bound with twisted brass wire or rawhide cord. Diagonal bamboo stretcher struts (*thangi-kambi*) connected the mid-span of each main rib to a sliding lower collar (*izhuppu-kumizh*) that glided up the central staff (*kambu*) and locked over a bamboo peg or cord loop.\n- **Dome Pre-Stress**: When pushed open, the taut cotton or silk cover pulled the bamboo ribs into a parabolic arch, putting the fabric in biaxial tension and the bamboo ribs in elastic compression."
    },
    {
        "slug": "technology-kudai-kambi-bamboo-spindle-splitting-hub-mortising-and-silk-stretching",
        "category": "technology",
        "file": "technology-kudai-kambi-bamboo-spindle-splitting-hub-mortising-and-silk-stretching.md",
        "name_en": "Kudai-Kambi Bamboo Rib Splitting, Lathe-Turned Hub Mortising & Gore Silk Stretching",
        "name_ta": "குடைக்கம்பி மூங்கில் பிளப்பு, கடைசல் மரக்குமிழ் துளையிடல் மற்றும் பட்டுத் துணி போர்த்தும் தொழில்நுட்பம்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 1950,
        "thinai": "marutham",
        "summary_en": "Workshop fabrication process of ceremonial silk and cotton parasols: heat-straightening bamboo shaft poles, splitting and gauge-scraping radial bamboo ribs, lathe-turning slotted neem or teak hubs, and stitching triangular fabric gores under uniform tension.",
        "summary_ta": "பட்டு மற்றும் பருத்திக் குடைகள் செய்யும் பட்டறைத் தொழில்நுட்பம்: மூங்கில் தண்டு நிமிர்த்துதல், கம்பிகளைச் சீவுதல், மரக்குமிழ் கடைதல் மற்றும் முக்கோணத் துணிப் பட்டைகளை இழுத்துத் தைத்தல்.",
        "sources": [
            "Thanjavur and Kumbakonam Temple Craft Traditions",
            "Artisans of South India Ethnographic Records",
            "Chola Epigraphy on Temple Regalia Artisans"
        ],
        "content": "# Kudai-Kambi Rib Splitting, Hub Mortising & Silk Gore Stretching\n\nCrafting a ceremonial *Venkotrakkudai* or processional temple umbrella required coordinated woodworking, bamboo splitting, and precision tailoring:\n\n**Fabrication Sequence:**\n1. **Shaft Curing & Lacquering**: Long poles of mature male bamboo (*kattu-moongil*) or turned *vengai* wood were straightened over charcoal embers, rubbed with sesame oil, and coated with vermilion or black lac (*arakku*) or sheathed in embossed silver/brass sleeves.\n2. **Gauge-Scraping Ribs**: Artisans split seasoned bamboo internodes into matched strips, drawing each strip through an iron thickness gauge (*kambi-achu*) and drilling needle-fine eye holes at the tip and mid-joint with a bow-drill (*thurappan*).\n3. **Hub Lathe-Turning**: Hardwood blocks of teak or *kumizh* were turned on a two-point bow lathe (*kadaisal*), grooved around the circumference, and radially saw-slotted to receive the rib heels.\n4. **Triangular Gore Tailoring**: Heavy bleached cotton (*thugil*) or Kumbakonam degummed mulberry silk was cut into wedge-shaped gores, French-seamed together, stretched over the open rib frame, and tacked to each rib tip before adding the hanging valance (*thombai*)."
    },
    {
        "slug": "technology-olai-kudai-palmyra-leaf-braiding-and-monsoon-field-umbrella-weft",
        "category": "technology",
        "file": "technology-olai-kudai-palmyra-leaf-braiding-and-monsoon-field-umbrella-weft.md",
        "name_en": "Olai-Kudai Palmyra Leaf Thatching, Rattan Rim Binding & Monsoon Agrarian Umbrella Craft",
        "name_ta": "ஓலைக்குடை பனையோலைப் பின்னல், பிரம்பு விளிம்புக் கட்டு மற்றும் உழவர் மழைக்குடைத் தொழில்நுட்பம்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1950,
        "thinai": "marutham",
        "summary_en": "Vernacular technology of weaving waterproof palmyra palm-leaf umbrellas (olai-kudai) andhands-free conical rain hats (kambur / thazhankudai) using sun-cured Borassus flabellifer fronds, split bamboo radiating armatures, and twisted palmyra petiole fiber lashing.",
        "summary_ta": "பனையோலை மற்றும் தாழையோலை கொண்டு உழவர்களுக்கான மழைக்குடைகள் (ஓலைக்குடை, கம்பூர் தொப்பிக்குடை) பின்னும் நாட்டுப்புறத் தொழில்நுட்பம் மற்றும் பிரம்புக் கட்டு முறை.",
        "sources": [
            "Perumpanarruppadai Agrarian Descriptions",
            "Tala Vilasam (Arunachala Kavirayar)",
            "Ethnobotany of Borassus flabellifer in Tamil Nadu"
        ],
        "content": "# Olai-Kudai Palmyra Leaf Braiding & Agrarian Rain-Umbrella Craft\n\nAlongside courtly silk parasols, agrarian workers, herdsmen (*Idaiyar*), and paddy transplanters across Tamil Nadu relied on rigid, storm-proof palm-leaf umbrellas (*Olai-Kudai*):\n\n**Vernacular Construction:**\n1. **Frond Selection & Curing**: Unblemished crown leaves (*kuru-olai*) of the palmyra palm (*Borassus flabellifer*) or screw-pine (*thazhai* / *Pandanus*) were harvested, briefly steamed or morning-sun wilted for pliability, and flattened under weights.\n2. **Double-Layer Shingle Layup**: An inner spider-frame of split bamboo spokes radiated from a hollow bamboo handle. Fan-segments of palmyra leaf were overlapped concentrically like roof tiles and stitched down with rot-resistant palmyra petiole fibre (*manji* / *naar*) so rainwater cascaded off without seeping through stitch holes.\n3. **Rattan Rim & Hands-Free *Kambur***: The circular perimeter was clamped between twin hoops of split rattan cane (*pirambu*) bound in herringbone knots. For bent-over paddy weeding in torrential rain, artisans wove a stemless dome (*kambur* or *thoppi-kudai*) worn directly on the head with an inner woven crown ring."
    },
    {
        "slug": "artifact-muthukkudai-pearl-fringed-parasol-irattai-kudai-and-kalasam-finials",
        "category": "artifact",
        "file": "artifact-muthukkudai-pearl-fringed-parasol-irattai-kudai-and-kalasam-finials.md",
        "name_en": "Muthukkudai Pearl Parasols, Irattai-Kudai Processional Twins & Brass Kalasam Finials",
        "name_ta": "முத்துக்குடை, கோயில் திருவிழா இரட்டைக்குடை மற்றும் செப்புக் கலச உச்சி அணிகள்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Sacred and royal ceremonial parasol artifacts: the pearl-tasseled Muthukkudai, the matched pair of giant temple festival umbrellas (Irattai-Kudai) flanking bronze utsava deities, pleated cloth valances (thombai), and gilded copper/brass finial pots (kalasam).",
        "summary_ta": "கோயில் உற்சவங்கள் மற்றும் அரச ஊர்வலங்களில் பயன்படுத்தப்படும் முத்துக்குடை, சுவாமி புறப்பாட்டின் போது இருபுறமும் ஏந்தப்படும் இரட்டைக்குடை, தொம்பைத் தொங்கல்கள் மற்றும் தங்க முலாம் பூசிய கலசம்.",
        "sources": [
            "Silappadikaram Arangerrukathai",
            "Srirangam Koyil Olugu",
            "Thanjavur Brihadisvara Temple Inscriptions (Rajaraja I Regalia Gifts)"
        ],
        "content": "# Muthukkudai, Irattai-Kudai Processional Twins & Kalasam Finials\n\nIn Tamil temple liturgy (*utsavam*) and royal pageantry, ceremonial parasols form a codified hierarchy of sacred artifacts:\n\n**Artifact Typology & Anatomy:**\n- **Muthukkudai (Pearl-Fringed Canopy)**: Constructed over a white silk dome draped with concentric festoons (*maalai*) and hanging tassels of drilled natural pearls from Korkai and fake-seed glass beads in later eras, shimmering as bearers rotated the shaft during the *Muthukkudai Sevai* festival.\n- **Irattai-Kudai (Twin Processional Umbrellas)**: Whenever a bronze *utsava* deity mounts the street palanquin or *vahanam*, two bearers flank the deity holding matched six-foot diameter umbrellas—one pure white (*ven-kudai*) and one richly appliqued in crimson, emerald, and gold zari—tilted forward to shield the icon from glare and dust.\n- **Kalasam Finial & Thombai Valance**: The apex of the umbrella shaft pierces the dome to terminate in a lathe-spun brass or gilded copper water-pot finial (*kalasam*) sometimes topped with a sacred *rishabham* (bull) or *garuda* crest, while the perimeter hangs with a pleated border (*thombai*) and metallic *jhallari* fringes."
    },
    {
        "slug": "artifact-olai-kudai-agrarian-rain-shield-and-vithanam-temple-cloth-canopies",
        "category": "artifact",
        "file": "artifact-olai-kudai-agrarian-rain-shield-and-vithanam-temple-cloth-canopies.md",
        "name_en": "Olai-Kudai Agrarian Rain Shields, Thombai Hanging Cylinders & Vithanam Cloth Canopies",
        "name_ta": "உழவர் ஓலைக்குடை, தோரணத் தொம்பை உருளைகள் மற்றும் கோயில் மண்டப விதானத் துணிப் பந்தல்கள்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Comparative material artifacts of Tamil shade architecture: vernacular braided palmyra rain umbrellas (olai-kudai), cylindrical fabric processional streamers (thombai), and expansive rectangular appliqued cloth ceiling canopies (vithanam / ullurai) suspended in temple mandapas.",
        "summary_ta": "தமிழர் நிழல் சார்ந்த பொருட்களின் வகைப்பாடு: பனையோலை மழைக்குடைகள், திருவிழா ஊர்வலத் தொம்பை உருளைகள் மற்றும் கோயில் மண்டபக் கூரைகளில் கட்டப்படும் வண்ணத் துணி விதானங்கள்.",
        "sources": [
            "Perumpanarruppadai",
            "South Indian Temple Textile Catalogues",
            "Kumbakonam Applique Canopy Traditions"
        ],
        "content": "# Olai-Kudai Rain Shields, Thombai Cylinders & Vithanam Canopies\n\nTamil shade-making craft spans portable rain protection for the paddy field and monumental suspended textile architecture inside stone temples:\n\n**Functional & Ritual Forms:**\n- **Vernacular *Olai-Kudai* & *Idaiyar-Kudai***: Sangam idylls (*Perumpanarruppadai*) depict pastoralists (*Idaiyar*) carrying a stout palmyra-leaf umbrella alongside a fire-drill and leather sandals; its rigid dome doubled as a windbreak for kindling campfires in monsoon pastures.\n- **Thombai Cylindrical Hangings**: Suspended beneath umbrella rims or carried on twin poles ahead of processions, *thombai* are tiered cylindrical drums of stiffened starched cotton decorated with cut-cloth applique lotus petals and mango motifs (*maanga*).\n- **Vithanam (Suspended Ceiling Canopies)**: Stretched horizontally by corner ropes beneath the stone ceilings of temple *mandapas* and chariot (*ther*) superstructures, the *vithanam* converts a stark granite hall into a vibrant textile cosmos above the ritual arena."
    },
    {
        "slug": "concept-ullurai-and-vithanam-appliqued-ceiling-canopy-iconography-and-geometry",
        "category": "concept",
        "file": "concept-ullurai-and-vithanam-appliqued-ceiling-canopy-iconography-and-geometry.md",
        "name_en": "Ullurai & Vithanam Canopy Iconography: Ashtadikpalakas, Lotus Mandala & Acoustic Damping",
        "name_ta": "உள்ளுறை மற்றும் விதானக் குடை ஓவிய இலக்கணம்: அஷ்டதிக் பாலகர்கள், தாமரை மண்டலம் மற்றும் ஒலித் தடுப்பு",
        "era": "Chola to Nayak Era",
        "year_start": 900,
        "year_end": 1850,
        "thinai": "marutham",
        "summary_en": "Iconographic program and architectural function of the underside lining of royal parasols (ullurai) and suspended temple canopies (vithanam): concentric lotus mandalas, directional guardians (Ashtadikpalakas), zodiacal signs (Rasi), and reverberation damping in stone halls.",
        "summary_ta": "குடையின் உட்புறம் (உள்ளுறை) மற்றும் கோயில் விதானத் துணிப் பந்தல்களில் அமைக்கப்படும் தாமரை மண்டலம், அஷ்டதிக் பாலகர்கள், ராசிச் சக்கரம் மற்றும் கற்கோயில் எதிரொலித் தடுப்பு அறிவியல்.",
        "sources": [
            "Silappadikaram Commentary on Ullurai",
            "Agamic Utsava Vidhi Manuals",
            "Thanjavur and Kumbakonam Applique Textile Studies"
        ],
        "content": "# Ullurai & Vithanam Canopy Iconography and Acoustic Geometry\n\nBecause the monarch or deity looks upward into the belly of the parasol (*ullurai*) or suspended *vithanam* canopy, Tamil textile artisans concentrated the richest cosmological geometry on the underside lining:\n\n**Iconographic & Architectural Design:**\n- **Concentric Cosmogram (*Ullurai*)**: The central hub represents the hundred-petalled lotus (*Sahasrara* / *Thamarai*), surrounded by concentric registers depicting dancing *Ganas*, sacred geese (*Hamsa*), the twelve solar mansions (*Rasi*), and the eight directional guardians (*Ashtadikpalakas*) riding their mounts along the outer border.\n- **High-Contrast Color Coding**: Artisans appliqued cut shapes of vibrant red, green, yellow, and black cotton (*kalamkari* or dyed *kora* cloth) outlined with white chain-stitching so figures remained legible when viewed from twenty feet below by oil-lamp light (*theevatti*).\n- **Acoustic & Thermal Buffering**: Stretching a heavy multi-layered cotton *vithanam* beneath high granite *mandapa* ceilings absorbed harsh high-frequency slap echo from *Nadaswaram* and *Thavil* ensembles while trapping rising soot from camphor and ghee torches."
    },
    {
        "slug": "institution-kudai-katti-umbrella-artisans-and-temple-applique-needlework-guilds",
        "category": "institution",
        "file": "institution-kudai-katti-umbrella-artisans-and-temple-applique-needlework-guilds.md",
        "name_en": "Kudai-Katti Umbrella Makers, Thombai Tailors & Temple Regalia Endowments",
        "name_ta": "குடைகட்டி வினைஞர் குழாம், தொம்பைத் தையல் கலைஞர்கள் மற்றும் கோயில் குடை மானிய முறை",
        "era": "Chola to Modern Era",
        "year_start": 900,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Hereditary artisan guilds specializing in ceremonial umbrella construction (Kudai-Katti), temple applique canopy tailoring (Thombai / Vithanam), and the temple service tenures (Kudai-Manyam) funding annual renewal of festival parasols and chariot hangings.",
        "summary_ta": "கோயில் மற்றும் அரச குடைகளை உருவாக்கும் குடைகட்டி கலைஞர்கள், விதானம் மற்றும் தொம்பை தைக்கும் தையல் வினைஞர் குழுக்கள் மற்றும் அவர்களுக்கான கோயில் குடை மானிய உரிமைகள்.",
        "sources": [
            "South Indian Inscriptions (Chola & Pandya Temple Service Grants)",
            "Thanjavur District Manual",
            "Kumbakonam Temple Textile Artisan Oral Histories"
        ],
        "content": "# Kudai-Katti Umbrella Artisans & Temple Applique Needlework Guilds\n\nThe production and ceremonial bearing of royal and temple parasols were organized through specialized hereditary guilds attached to major *brahmadeya* and temple towns:\n\n**Guild Structure & Ritual Patronage:**\n- **Kudai-Katti & Tailoring Lineages**: Master craftsmen (*Kudai-Katti* and *Thையற்காரர்* / *Panar* needleworkers) maintained family pattern books of paper and palm-leaf stencils (*achu*) for cutting symmetrical lotus, *yazhi*, and deity figures for *Irattai-Kudai* and *Vithanam* canopies.\n- **Kudai-Manyam & Service Tenures**: Chola, Pandya, and Nayak stone inscriptions record tax-free land endowments (*Kudai-Manyam* or *Thirukkudai-Puram*) granted both to the artisans who refurbished the deity's umbrellas before each annual *Brahmotsavam* and to the hereditary umbrella-bearers (*Kudai-Pidippor*) who marched in the scorching sun during street processions.\n- **Seasonal Chariot Dressing**: The same guilds dressed the towering wooden temple cars (*ther*) with hundreds of yards of appliqued *thombai* skirts and corner parasols prior to the chariot pull."
    },
    {
        "slug": "place-thirunageswaram-ancient-chola-royal-parasol-and-silk-canopy-haven",
        "category": "place",
        "file": "place-thirunageswaram-ancient-chola-royal-parasol-and-silk-canopy-haven.md",
        "name_en": "Thirunageswaram: Ancient Chola Royal Parasol, Silk Weaving & Temple Canopy Haven",
        "name_ta": "திருநாகேஸ்வரம் - சோழர் கால வெண்கொற்றக்குடை, பட்டு நெசவு மற்றும் கோயில் விதானக் கலைத் தளம்",
        "era": "Chola to Modern Era",
        "year_start": 850,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Historic Chola temple town near Kumbakonam in the Kaveri delta (10.9630° N, 79.4290° E), renowned as a premier center for high-density mulberry silk weaving, temple applique canopy (vithanam) and thombai tailoring, and ceremonial festival parasols (irattai-kudai).",
        "summary_ta": "கும்பகோணம் அருகே காவிரி மருத நிலத்தில் அமைந்துள்ள திருநாகேஸ்வரம் (10.9630° N, 79.4290° E): சோழர் காலப் பட்டு நெசவு, கோயில் திருவிழா இரட்டைக்குடை, தொம்பை மற்றும் வண்ண விதானப் பந்தல்கள் உருவாக்கும் வரலாற்றுக் கலைத் தளம்.",
        "sources": [
            "Thirunageswaram Naganathaswamy Temple Chola Inscriptions",
            "Thanjavur Gazetteer on Kumbakonam-Thirunageswaram Silk & Temple Crafts",
            "Craft Map of Tamil Nadu"
        ],
        "content": "# Thirunageswaram: Ancient Chola Royal Parasol & Silk Canopy Haven\n\nLocated in the fertile *marutham* alluvial plain of the Kaveri delta just east of Kumbakonam (10.9630° N, 79.4290° E), Thirunageswaram (ancient *Thirunageswaram* / *Chenakipuram*) is a living hub of Chola temple ritual, silk weaving, and ceremonial umbrella craft:\n\n**Geographic & Craft Significance:**\n- **Chola Imperial Patronage**: Centered around the 10th-century Naganathaswamy (Rahu Stalam) temple rebuilt by Aditya Chola I, Parantaka I, and Sekkizhar's patron Kulottunga Chola II, the town lay at the heart of the Pazhayarai–Kumbakonam royal corridor where imperial *Venkotrakkudai* and *Muthukkudai* regalia were commissioned.\n- **Silk Canopy & Applique Cluster**: Generations of weavers and temple tailors across the Thirunageswaram–Kumbakonam–Sikkil belt weave dense degummed silk and stitch vibrant cut-cloth applique *Irattai-Kudai* parasols, *Vithanam* ceiling canopies, and *Thombai* chariot hangings supplied to temples across the Kaveri basin."
    }
]

EDGES = [
    [
        "text-sangam-and-silappadikaram-on-venkotrakkudai-royal-parasol-and-muthukkudai",
        "describes",
        "concept-venkotrakkudai-protective-shade-arul-sovereignty-and-senkol-cosmology",
        "material_culture",
        "Sangam to Post-Sangam Era",
        "Sangam poems and Silappadikaram articulate the political theology of the Venkotrakkudai as the protective shade of royal grace paired with the Senkol sceptre.",
        "Purananuru & Silappadikaram"
    ],
    [
        "text-sangam-and-silappadikaram-on-venkotrakkudai-royal-parasol-and-muthukkudai",
        "documents",
        "artifact-muthukkudai-pearl-fringed-parasol-irattai-kudai-and-kalasam-finials",
        "material_culture",
        "Sangam to Post-Sangam Era",
        "Silappadikaram documents the ceremonial procession of the pearl-fringed Muthukkudai shading the sacred Thalaikkol and sovereigns.",
        "Silappadikaram Arangerrukathai"
    ],
    [
        "concept-collapsible-radial-bamboo-rib-kinematics-and-runner-hub-tension",
        "underpins",
        "technology-kudai-kambi-bamboo-spindle-splitting-hub-mortising-and-silk-stretching",
        "material_culture",
        "Sangam to Nayak Era",
        "Radial bamboo rib flexure and sliding runner hub kinematics govern the workshop fabrication of collapsible silk parasols.",
        "Traditional Craft Surveys"
    ],
    [
        "technology-kudai-kambi-bamboo-spindle-splitting-hub-mortising-and-silk-stretching",
        "constructs",
        "artifact-muthukkudai-pearl-fringed-parasol-irattai-kudai-and-kalasam-finials",
        "material_culture",
        "Sangam to Modern Era",
        "Splitting bamboo ribs, turning wooden hubs, and stretching silk gores produce the Muthukkudai and twin Irattai-Kudai parasols.",
        "Temple Craft Traditions"
    ],
    [
        "technology-olai-kudai-palmyra-leaf-braiding-and-monsoon-field-umbrella-weft",
        "produces",
        "artifact-olai-kudai-agrarian-rain-shield-and-vithanam-temple-cloth-canopies",
        "material_culture",
        "Iron Age to Modern Era",
        "Concentric braiding of cured palmyra fronds over bamboo spokes and rattan rims produces waterproof Olai-Kudai agrarian rain shields.",
        "Perumpanarruppadai & Tala Vilasam"
    ],
    [
        "concept-ullurai-and-vithanam-appliqued-ceiling-canopy-iconography-and-geometry",
        "shapes",
        "artifact-olai-kudai-agrarian-rain-shield-and-vithanam-temple-cloth-canopies",
        "material_culture",
        "Chola to Nayak Era",
        "Concentric lotus mandalas and Ashtadikpalaka directional iconography structure the appliqued underside of Vithanam ceiling canopies.",
        "Agamic Utsava Vidhi"
    ],
    [
        "institution-kudai-katti-umbrella-artisans-and-temple-applique-needlework-guilds",
        "fabricates",
        "artifact-muthukkudai-pearl-fringed-parasol-irattai-kudai-and-kalasam-finials",
        "material_culture",
        "Chola to Modern Era",
        "Hereditary Kudai-Katti artisans and temple needlework guilds fabricate and maintain festival Irattai-Kudai and Muthukkudai parasols.",
        "South Indian Inscriptions"
    ],
    [
        "institution-kudai-katti-umbrella-artisans-and-temple-applique-needlework-guilds",
        "tailors",
        "artifact-olai-kudai-agrarian-rain-shield-and-vithanam-temple-cloth-canopies",
        "material_culture",
        "Chola to Modern Era",
        "Temple tailoring guilds cut and stitch appliqued Vithanam ceiling canopies and cylindrical Thombai hangings for mandapas and chariots.",
        "Kumbakonam Craft Records"
    ],
    [
        "institution-kudai-katti-umbrella-artisans-and-temple-applique-needlework-guilds",
        "operates_in",
        "place-thirunageswaram-ancient-chola-royal-parasol-and-silk-canopy-haven",
        "material_culture",
        "Chola to Modern Era",
        "Silk weavers and temple parasol applique artisans have operated across the Thirunageswaram-Kumbakonam temple belt since Chola times.",
        "Thanjavur Gazetteer"
    ],
    [
        "concept-venkotrakkudai-protective-shade-arul-sovereignty-and-senkol-cosmology",
        "anchors",
        "place-thirunageswaram-ancient-chola-royal-parasol-and-silk-canopy-haven",
        "material_culture",
        "Chola to Modern Era",
        "Chola royal and temple parasol traditions around Pazhayarai and Thirunageswaram materialized the sovereign ideal of Venkotrakkudai shade.",
        "Thirunageswaram Inscriptions"
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
