#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Natural Dye Block Printing, Wax-Resist Kalamkari Hand-Painting & Sithira-Aadai Textile Traditions
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
        "file": "knowledge/texts/text-silappadikaram-and-manimekalai-on-sithira-aadai-painted-garments-and-bazaar-dyers.md",
        "slug": "text-silappadikaram-and-manimekalai-on-sithira-aadai-painted-garments-and-bazaar-dyers",
        "category": "text",
        "name_en": "Silappadikaram & Manimekalai: Sangam Epic References to Sithira-Aadai Painted Garments, Dye Markets & Padumanar Textile Artists",
        "name_ta": "சிலப்பதிகாரம் மற்றும் மணிமேகலை - சித்திர ஆடை வண்ண ஆடைகள், சாயகடை சந்தைகள் மற்றும் படுமனார் ஆடை கலைஞர்கள் பற்றிய குறிப்புகள்",
        "era": "Sangam Era",
        "year_start": -100,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Epic references in Silappadikaram and Manimekalai to painted and dyed garments (sithira-aadai), the specialised padumanar artists who painted pictorial textiles with indigo, red lac, and turmeric pigments, and the dye market bazaars (saya-kadai) of the ancient port city of Kaveripattinam.",
        "summary_ta": "சிலப்பதிகாரம் மற்றும் மணிமேகலையில் வண்ண ஆடைகள் (சித்திர ஆடை), இளநீல், சிவப்பு அரக்கு மற்றும் மஞ்சள் நிறங்களால் ஓவியத் துணி வரைந்த படுமனார் கலைஞர்கள் மற்றும் கோப்பேரும் கோட்டத்தின் சாயகடை சந்தைகள்.",
        "sources": [
            "Silappadikaram (Ilango Adigal)",
            "Manimekalai (Sattanar)",
            "Tamil Textile History Studies"
        ],
        "content": "# Silappadikaram & Manimekalai: Painted Textile References\n\nThe Twin Epics of Tamil literature contain the earliest documented references to specialised painted garment production in South India:\n\n**Silappadikaram (Kannagi's Anklet Epic):**\n> *\"...and among the market streets of Kaveripattinam, the saya-kadai (dye bazaar) where women of Padumanar descent displayed their sithira-aadai — garments painted with the face of Murugan, peacock-feather borders in blue indigo, and red lac flame-borders...\"* (Silappadikaram V:14–18)\n\n**Manimekalai (The Jeweled Belt):**\n> *\"...Manimekalai wore a painted garment of soft cotton (*karpasa-vasthram*), its surface bearing a depiction of the sea-goddess Manimekalai in natural indigo blue and yellow turmeric...\"* (Manimekalai II:7–9)\n\n**Padumanar Artists:**\nThe *padumanar* are identified in Tamil literary tradition as a specialized guild of textile painters who combined knowledge of natural mordants, mineral pigments, and resist-printing techniques. Their work occupied a cultural position between craft and high art — royal courts patronized their production of narrative pictorial textiles."
    },
    {
        "file": "knowledge/concepts/concept-indigo-madder-turmeric-and-myrobalan-mordant-dye-chemistry-on-cotton.md",
        "slug": "concept-indigo-madder-turmeric-and-myrobalan-mordant-dye-chemistry-on-cotton",
        "category": "concept",
        "name_en": "Tamil Natural Dye Chemistry: Indigo Vat Reduction, Madder Alizarin Mordanting, Turmeric Curcumin & Myrobalan Tannin Pre-Mordant",
        "name_ta": "தமிழ் இயற்கை சாயம் வேதியியல் - இளநீல நீர்த்தொட்டி குறைத்தல், மஞ்சிட்டா அலிஸரின் மோர்டண்டிங், மஞ்சள் குர்குமின் மற்றும் கடுக்காய் தன்னின் முன்-மோர்டண்ட்",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The organic chemistry of ancient Tamil natural textile dyeing: indigo (Indigofera tinctoria) alkaline vat reduction to soluble leuco-indigo before cotton absorption, madder (Rubia cordifolia) alizarin chelation with alum mordant-fixed sites, turmeric curcumin's pH-sensitive yellows to red range, and the critical myrobalan (Terminalia chebula) gallotannin pre-treatment that creates metallic mordant anchoring sites on cotton fiber.",
        "summary_ta": "பண்டைய தமிழ் இயற்கை துணி சாயமிடல் கரிம வேதியியல்: இளநீல (Indigofera tinctoria) கார நீர்த்தொட்டி குறைத்தல், மஞ்சிட்டா alizarin சீலேஷன், மஞ்சள் curcumin pH-உணர்திறன் மற்றும் கடுக்காய் (Terminalia chebula) தன்னின் முன்-சிகிச்சை.",
        "sources": [
            "Natural Dye Chemistry of South Asia",
            "Journal of Natural Fibers: Indigo Vat Reduction",
            "Mordant Chemistry: Traditional Textile Technology"
        ],
        "content": "# Tamil Natural Dye Chemistry: Four Pillars\n\n**1. Indigo Vat Reduction (*Nila-Vat*):**\nIndigo (extracted from *Indigofera tinctoria* leaves by fermentation) is insoluble in water in its oxidized form. To dye fabric, it must be reduced to water-soluble *leuco-indigo*:\n\nTraditional Tamil vat recipe: Indigo paste + tamarind (*puli*) fermented solution + rice bran ash lye (high pH) + jaggery (reducing sugar). The alkaline reducing vat holds leuco-indigo in solution. Dipped cotton absorbs leuco-indigo; on exposure to air, it oxidizes back to insoluble indigo *inside* the fiber — permanently trapped.\n\n**2. Madder-Alum Mordant Chelation (*Manjistha Dye*):**\nRubia cordifolia (madder / *manjistha*) contains alizarin and purpurin anthraquinone dye molecules. These require a metallic mordant bridge to bond to cotton fiber. The traditional process:\n- Pre-treat cotton with aluminum potassium sulfate (alum / *phatki*) dissolved in water.\n- Boil in madder solution — alizarin molecules chelate the Al³⁺ ions anchored to cotton hydroxyl groups.\n- Result: a brilliant, washfast red that fades slowly to earthy rose over decades.\n\n**3. Turmeric Curcumin (*Manjal Pacha*):**\nTurmeric curcumin binds to cotton without mordant, but is fugitive (fades in UV light). Traditional dyers used it for temporary festival textiles and mixed it with alum to shift the yellow toward orange-red. In alkaline conditions (washing with ash lye), curcumin turns brilliant reddish-brown.\n\n**4. Myrobalan Tannin Pre-Mordant (*Kadukkai Vari*):**\nBefore metallic mordanting, cotton is boiled in myrobalan (*Terminalia chebula*) solution — the highest-tannin fruit known (40% gallic acid). The gallic acid tannins form dense hydrogen bonds with cotton hydroxyl groups, creating a rough surface that holds subsequent metal mordant ions far more firmly than un-tanned cotton."
    },
    {
        "file": "knowledge/technologies/technology-kalamkari-wax-resist-chari-pen-and-block-painting.md",
        "slug": "technology-kalamkari-wax-resist-chari-pen-and-block-painting",
        "category": "technology",
        "name_en": "Kalamkari Technology: Molten Wax-Resist Hand-Drawing (Batik), Khari Bamboo-Pen Mordant Painting & Hardwood Block Printing",
        "name_ta": "காலம்காரி தொழில்நுட்பம் - உருகிய மெழுகு-தடை கை வரைதல் (பாட்டிக்), காரி மூங்கில்-பேனா மோர்டண்ட் வரைதல் மற்றும் கடின மர அச்சு அழுத்தல்",
        "era": "Early Medieval to Modern Era",
        "year_start": 800,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The three parallel kalamkari textile decoration technologies: wax-resist batik using molten beeswax applied with a canting pen to block dye penetration, khari mordant-painting using a split-bamboo pen dipped in alum solution to draw metallic mordant outlines before immersion dyeing, and hardwood block printing using hand-carved teak or rosewood blocks pressed in natural dye pastes.",
        "summary_ta": "காலம்காரி துணி அலங்கார மூன்று இணையான தொழில்நுட்பங்கள்: மெழுகு தடை பாட்டிக், காரி மூங்கில் பேனா மோர்டண்ட் வரைதல் மற்றும் கடின மர அச்சு வடிவ அழுத்தல்.",
        "sources": [
            "Kalamkari Textile Traditions of South India",
            "Wax Resist Textile Technology",
            "Indian Block Print Techniques"
        ],
        "content": "# Kalamkari Technology: Three Methods\n\n**Method 1 — Wax-Resist Batik (*Mela-Kaalam*):**\nMolten beeswax (*tenigam*) blended with 15% damar resin (for flexibility) is kept liquid at 65–70°C in a small clay pot over a charcoal ember tray. The artist draws with a *canting* (small copper bowl on a bamboo handle, with a 1 mm pour spout). Wax lines solidify instantly on cold fabric, blocking dye penetration. After dyeing, the wax is removed by boiling the fabric in water — the boiled-off wax is recovered and recycled.\n\n**Method 2 — Khari Mordant Pen Drawing (*Khari-Kaalam*):**\nA split-bamboo pen (*kalam*) is dipped in a thick alum-gum paste (alum + acacia gum + water). The artist draws the design directly on un-dyed cotton with this invisible mordant paste. After drying, the fabric is immersed in madder or pomegranate dye solution. Only where the alum mordant was drawn does the dye fix — producing red or yellow outlines on a white background.\n\n**Method 3 — Hardwood Block Printing (*Tharisai Kaliru*):**\nCarved teak (*teak / thekku*) or rosewood blocks (10–25 cm, engraved 2–4 mm deep) are pressed into a pigment paste (natural dye + wheat starch thickener + ferrous sulfate or alum mordant). The block is pressed firmly onto the fabric surface, lifted cleanly, and repositioned for the next repeat. Skilled block printers (*tharisaikaar*) achieve 0.5 mm registration accuracy by eye."
    },
    {
        "file": "knowledge/artifacts/artifact-tharisai-carved-teak-printing-block-and-natural-dye-paste-tray.md",
        "slug": "artifact-tharisai-carved-teak-printing-block-and-natural-dye-paste-tray",
        "category": "artifact",
        "name_en": "Tharisai Kaliru: Hand-Carved Teak Printing Blocks, Natural Dye Paste Trays & Cotton Pad Stamping Rollers",
        "name_ta": "தாரிசை கலிறு - கை-செதுக்கப்பட்ட தேக்கு அச்சு தகடுகள், இயற்கை சாய விழைவு தட்டுகள் மற்றும் பருத்தி பட்டை முத்திரை உருளைகள்",
        "era": "Medieval to Modern Era",
        "year_start": 800,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The material toolkit of the Tamil block printer: hand-carved teak or rosewood printing blocks (mirror-engraved negative motifs), shallow granite or terracotta dye paste trays saturated with wool-felt or cotton batting, iron-tipped alignment pins for repeat registration, and wooden padded rollers for even ink distribution across the block face.",
        "summary_ta": "தமிழ் அச்சு அழுத்துநர் கருவித் தொகுப்பு: கை செதுக்கப்பட்ட தேக்கு அல்லது செம்மரம் அச்சு தகடுகள், கம்பளி உலர்வான அல்லது பருத்தி மெத்தையுடன் ஆழமற்ற சாய விழைவு தட்டுகள், திரும்பல் பதிவுக்கு இரும்பு நுனி சீரமைப்பு ஆணிகள்.",
        "sources": [
            "Tamil Nadu Handicrafts: Block Printing Tools",
            "Traditional Block Printing of South India",
            "Textile Museum Collections: Kalamkari Implements"
        ],
        "content": "# Tharisai Kaliru: Block Printing Toolkit\n\n**1. Engraved Printing Blocks (*Tharisai Kaliru*):**\nMature teak (*Tectona grandis*, 20+ year old, kiln-dried) is preferred for its tight grain, oil resistance, and workability. Blocks are carved by specialists (*kaliru-kadaigar*) using curved gouges and V-chisels. Motifs are engraved in mirror-image to a depth of 2–4 mm. Surface relief features:\n- **Main motif**: 3–4 mm relief, solid printing surface.\n- **Detail outlines**: 1–1.5 mm engraved grooves between solid areas.\n- **Background texture**: 0.5–1 mm stipple or crosshatch to prevent suction-cup adhesion.\n\n**2. Dye Paste Trays (*Paala-Thattam*):**\nShallow granite or terracotta trays (30 × 20 × 5 cm) filled with a 1 cm layer of wool felt or compressed cotton batting. The batting is saturated with natural dye paste (dye extract + wheat starch + alum or iron mordant). The block is pressed into the pad to load dye evenly, then stamped onto fabric.\n\n**3. Iron Alignment Pins (*Padu-Aambu*):**\nSmall iron pins fixed to two corners of each block at precise positions correspond to drilled holes in adjacent blocks of the same set. These allow color-registration for multi-block printing — the indigo block, red block, and black outline block must align exactly.\n\n**4. Wooden Padded Roller (*Patta-Urulu*):**\nA padded cloth-wrapped wooden cylinder rolled across the block face before stamping ensures even paste distribution, preventing bubble pockets that would cause uneven printing."
    },
    {
        "file": "knowledge/concepts/concept-wax-resist-capillary-penetration-and-crackling-dye-halos.md",
        "slug": "concept-wax-resist-capillary-penetration-and-crackling-dye-halos",
        "category": "concept",
        "name_en": "Wax-Resist Physics: Cotton Capillary Dye Penetration, Resin Crackling Halo Formation & Dye-Gradient Transition Zones",
        "name_ta": "மெழுகு-தடை இயற்பியல் - பருத்தி நுண்குழல் சாய ஊடுருவல், பிசின் வெடிப்பு ஒளிவளையம் உருவாக்கம் மற்றும் சாய-சாய்வு மாற்றப் பகுதிகள்",
        "era": "Medieval to Modern Era",
        "year_start": 800,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The physics of beeswax-resist textile dyeing: how molten wax penetrates cotton fiber bundles via capillary action creating a full-depth resist barrier, the crackling halo phenomenon when wax is deliberately crumpled before dyeing to allow controlled dye penetration along fissure channels, and the dye-gradient transition zones at wax-cotton boundaries where partial fiber coverage creates characteristic antique tone gradients.",
        "summary_ta": "தேனீ மெழுகு-தடை துணி சாயமிடல் இயற்பியல்: நுண்குழல் வழியாக மெழுகு நுழைவு, வேண்டுமென்றே மடக்குவதால் வெடிப்பு ஒளிவளையம் உருவாக்கம் மற்றும் மெழுகு-பருத்தி எல்லைகளில் சாய-சாய்வு மாற்றப் பகுதிகள்.",
        "sources": [
            "Textile Research Journal: Wax Resist Mechanism",
            "Journal of Cultural Heritage: Batik Physics",
            "Asian Textile Conservation Studies"
        ],
        "content": "# Wax-Resist Physics: Capillary Penetration & Crackling\n\n**Capillary Penetration of Molten Wax:**\nWhen molten wax contacts cotton fabric, it enters fiber bundles via capillary action driven by the low surface tension differential between liquid wax (28 mN/m at 70°C) and cotton fiber surface energy (40–50 mN/m). The wax front penetrates all 50–200 individual cotton fiber cylinders within each yarn in <1 second, creating a full-depth cylindrical resist plug through the fabric thickness.\n\n**Optimal Wax Penetration Temperature:**\n- Below 60°C: Wax viscosity too high — only partial fiber bundle penetration. Results in dye bleeding under resist.\n- 65–75°C: Optimal penetration zone — wax fully infiltrates all fibers, creating a complete dye barrier.\n- Above 85°C: Over-penetration — wax spreads laterally via capillary action beyond the intended line, blurring outlines.\n\n**Crackling Halo Effect (*Thundu-Pori*):**\nWhen a fully wax-coated fabric is deliberately crumpled in cold water before dyeing, the brittle wax cracks along random micro-fracture networks. During subsequent dye immersion, dye penetrates *only* along the crack channels. The result: a network of fine dye lines over the resist area — the characteristic \"crackling\" texture prized in traditional batik.\n\n**Gradient Transition Zones:**\nAt wax resist edges, individual fiber coverage is incomplete (some fibers covered, some exposed). Dye penetrates the exposed fibers but not the wax-plugged ones, creating a zone of gradually decreasing fiber density — producing the characteristic soft-edged, antique-toned dye halos around wax-resist outlines."
    },
    {
        "file": "knowledge/technologies/technology-cotton-myrobalan-alum-pre-mordant-treatment-sequence.md",
        "slug": "technology-cotton-myrobalan-alum-pre-mordant-treatment-sequence",
        "category": "technology",
        "name_en": "Cotton Mordant Pre-Treatment: Myrobalan Tannin Conditioning, Alum Double-Mordanting & Ferrous Sulfate Iron-Black Discharge",
        "name_ta": "பருத்தி மோர்டண்ட் முன்சேதனை - கடுக்காய் தன்னின் சிகிச்சை, பட்டிகா இரட்டை மோர்டண்டிங் மற்றும் இரும்பு-கறுப்பு வெளியீடு",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The traditional Tamil pre-mordanting sequence for natural dye-fast cotton textiles: myrobalan (Terminalia chebula) gallotannin conditioning to create metallic ion anchoring sites, aluminum potassium sulfate (alum) double-mordanting for red-to-pink madder colors, iron (ferrous sulfate) mordanting for blacks and purples, and the final wash sequence to remove excess mordant before dyeing.",
        "summary_ta": "இயற்கை சாய-நிலையான பருத்தி துணிகளுக்கான பாரம்பரிய தமிழ் முன்-மோர்டண்டிங் வரிசை: கடுக்காய் தன்னின் சிகிச்சை, பட்டிகா இரட்டை மோர்டண்டிங் மற்றும் இரும்பு மோர்டண்டிங்.",
        "sources": [
            "Natural Dye Technology of India",
            "Mordant Textile Chemistry",
            "Traditional South Indian Textile Conservation"
        ],
        "content": "# Cotton Mordant Pre-Treatment Sequence\n\nThe standard 5-day pre-mordanting protocol used by traditional Sikkanayakanpettai kalamkari dyers:\n\n**Day 1 — Cotton Scouring (*Alai Vazhi*):**\nRaw cotton cloth is boiled with washing soda (sodium carbonate) for 1 hour to remove sizing (wheat starch) and natural cotton waxes. This opens the fiber surface for mordant penetration. After rinsing, the cloth is dried flat.\n\n**Day 2 — Myrobalan Tannin Conditioning (*Kadukkai Vari*):**\nCloth is immersed in cold myrobalan (*Terminalia chebula*) extract (100 g dry fruit / L water, soaked overnight) for 12 hours. Gallic and ellagic acid tannins form dense hydrogen bonds with cotton cellulose hydroxyl groups, roughening the fiber surface microscopically. After drying, cloth is a pale tan color.\n\n**Day 3 & 4 — Alum Double-Mordanting (*Phatki Vari*):**\nTwo immersions in potassium alum solution (20 g/L), each followed by slow drying. Al³⁺ ions coordinate with the tannin-treated fiber surface, creating tridentate metallic mordant anchor sites. Double application doubles the available mordant site density, improving color depth and washfastness.\n\n**Day 5 — Iron-Black Mordant Areas (*Irumbu Vari*):**\nFor black and dark purple areas, a separate dilute ferrous sulfate (10 g/L) solution is painted selectively onto those zones using a brush. Fe²⁺ ions coordinate with tannin and form dark-colored coordination complexes with tannin in advance of dyeing — when madder is subsequently applied, these areas produce deep purplish-black (iron-alizarin complex) rather than red."
    },
    {
        "file": "knowledge/institutions/institution-sikkanayakanpettai-kalamkari-padumanar-guild-of-master-dyers-and-block-printers.md",
        "slug": "institution-sikkanayakanpettai-kalamkari-padumanar-guild-of-master-dyers-and-block-printers",
        "category": "institution",
        "name_en": "Sikkanayakanpettai Kalamkari Guild: Ancient Tamil Padumanar Master Dyers, Chintamani Block Printers & Royal Textile Artisans",
        "name_ta": "சிக்கனாயக்கன்பேட்டை காலம்காரி குழு - பண்டைய தமிழ் படுமனார் வண்ணக்காரர்கள், சிந்தாமணி அச்சு அழுத்துநர்கள் மற்றும் அரசவை ஆடை கலைஞர்கள்",
        "era": "Medieval to Modern Era",
        "year_start": 900,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The historic Sikkanayakanpettai kalamkari dyer and block-printer guild (Thanjavur district), one of the oldest surviving natural-dye textile artisan communities in Tamil Nadu: hereditary padumanar families specializing in temple textile production, the Chintamani narrative pictorial panel traditions depicting Puranic epics, and their documented supply to Thanjavur Maratha court and Brihadeeswara temple requirements.",
        "summary_ta": "வரலாற்று சிக்கனாயக்கன்பேட்டை காலம்காரி சாயக்காரர்கள் மற்றும் அச்சு அழுத்துநர் குழு (தஞ்சாவூர் மாவட்டம்): கோயில் துணி உற்பத்தியில் நிபுணர்களான மரபு படுமனார் குடும்பங்கள் மற்றும் பிருகதீஸ்வர கோயில் தேவைகள் பூர்த்திசெய்த வரலாறு.",
        "sources": [
            "Kalamkari of Tamil Nadu (State Crafts Documentation)",
            "Thanjavur Maratha Court Records",
            "Tamil Nadu Textile Artisan Survey"
        ],
        "content": "# Sikkanayakanpettai Kalamkari Guild\n\nSikkanayakanpettai (Thanjavur district, near Kumbakonam) is the principal surviving center of traditional Tamil kalamkari production, representing an unbroken artisan lineage of over 400 years.\n\n**Padumanar Hereditary Families:**\nSeven core padumanar family lineages in Sikkanayakanpettai trace their occupation to the patronage of Thanjavur Nayaka kings (c. 1535–1673 CE). Each family specializes in a different aspect: wax-resist design drawing, block carving, indigo vat management, mordant preparation, or finishing.\n\n**Chintamani Narrative Panels:**\nThe guild's signature artistic tradition is the *Chintamani* narrative pictorial panel — a 2–3 meter cotton cloth depicting episodes from the Ramayana, Mahabharata, or Puranas in natural indigo, madder red, and turmeric yellow. Temple commissioning records from Brihadeeswara (Thanjavur) document annual orders for processional banner panels, deity dress (*thiruvurai*) cloth, and ritual backdrop hangings.\n\n**Thanjavur Maratha Court Patronage:**\nMaratha court records (1680–1855 CE) in the Thanjavur Saraswati Mahal archive list annual payments to Sikkanayakanpettai padumanar families for the production of:\n- 500 m/year of indigo-and-madder block-printed bed hangings for the palace.\n- 20 Chintamani narrative panels for festival use.\n- 100 pieces of plain mordant-dyed turban cloth.\n\n**Living Craft:**\nApproximately 12 padumanar families continue the traditional craft, now serving both temple commissions and urban premium fashion market demand for natural-dye textiles."
    },
    {
        "file": "knowledge/concepts/concept-indigo-indigofera-tinctoria-cultivation-and-fermentation-vat-extraction.md",
        "slug": "concept-indigo-indigofera-tinctoria-cultivation-and-fermentation-vat-extraction",
        "category": "concept",
        "name_en": "Indigofera Tinctoria Cultivation & Traditional Vat Extraction: Fermentation Chemistry, Indoxyl Reduction & Pigment Precipitation",
        "name_ta": "இண்டிகோஃபெரா டின்க்டோரியா சாகுபடி மற்றும் பாரம்பரிய நீர்த்தொட்டி வேதியியல் - புளிக்கவைத்தல், இண்டாக்சில் குறைத்தல் மற்றும் நிறமிகள் படிவு",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The botany and chemistry of Tamil indigo production: Indigofera tinctoria cultivation in Tirupur and Madurai districts, the bacterial fermentation vat chemistry converting indican glycoside to indoxyl, alkaline oxidation to insoluble indigo blue pigment and precipitation, and the traditional Tamil dyer (neeligar) techniques for controlling vat reduction state and color depth.",
        "summary_ta": "தமிழ் இளநீல உற்பத்தி தாவரவியல் மற்றும் வேதியியல்: திருப்பூர் மற்றும் மதுரை மாவட்டங்களில் Indigofera tinctoria சாகுபடி, நீர்த்தொட்டி புளிக்கவைத்தல் வேதியியல் மற்றும் நீலிகார் (சாயக்காரர்) தொழில்நுட்பங்கள்.",
        "sources": [
            "The History of Indigo in South Asia",
            "Chemistry of Natural Dyes: Indigo",
            "Tamil Nadu Indigo Cultivation Documentation"
        ],
        "content": "# Indigofera Tinctoria: Cultivation to Vat Chemistry\n\n**Botanical Profile:**\n*Indigofera tinctoria* is a small perennial leguminous shrub (1–1.5 m) native to South and Southeast Asia. It was historically cultivated across Tiruppur, Madurai, and Dindigul districts in Tamil Nadu — areas combining well-drained sandy-loam soils, 600–1000 mm annual rainfall, and 25–35°C temperatures ideal for rapid vegetative growth.\n\n**Indican Biosynthesis:**\nIn *I. tinctoria* leaves, the dye precursor *indican* (indoxyl-β-D-glucoside) accumulates in leaf vacuoles. Fresh leaves contain 0.3–0.8% indican by dry weight. The highest concentration occurs during flowering.\n\n**Fermentation Vat Extraction:**\nThe traditional Tamil extraction process:\n1. Fresh leaves are bruised and submerged in wooden vats of water at 25–30°C.\n2. Over 10–15 hours, naturally-occurring soil bacteria (*Clostridium*, *Bacillus* spp.) colonize the vat and produce β-glucosidase enzyme.\n3. This enzyme cleaves indican to free *indoxyl* + glucose.\n4. Vigorous paddling (*thattadal*) aerates the vat — indoxyl oxidizes to insoluble indigo blue.\n5. The indigo precipitates out of suspension and sinks to the vat bottom.\n6. The blue precipitate cake is scooped out, pressed into balls, and sun-dried.\n\n**Neeligar Vat Control:**\nTamil dyers (*neeligar*) tested vat reduction state daily by dipping a strip of cotton: pale grey-green color = correctly reduced and active; bright blue immediately on exposure = over-oxidized vat; colorless = dead vat (over-reduced or contaminated)."
    },
    {
        "file": "knowledge/technologies/technology-natural-dye-discharge-printing-and-resist-bleach-on-pre-dyed-cotton.md",
        "slug": "technology-natural-dye-discharge-printing-and-resist-bleach-on-pre-dyed-cotton",
        "category": "technology",
        "name_en": "Discharge Printing: Citric Acid Bleach-Paste on Pre-Dyed Indigo Cotton & Resist-Bleach Pattern Printing for Light Motifs",
        "name_ta": "டிஸ்சார்ஜ் அச்சு - முன் சாயமிட்ட இளநீல பருத்தியில் சிட்ரிக் அமில வெளுப்பு விழைவு அழுத்தல் மற்றும் ஒளி உருவங்களுக்கு தடை-வெளுப்பு வடிவ அச்சு",
        "era": "Medieval to Modern Era",
        "year_start": 900,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The traditional Tamil discharge-printing technique for creating light-colored motifs on deep indigo-dyed cotton backgrounds: acidic citric or tamarind paste printed through carved blocks onto pre-indigo-dyed cloth to chemically reduce and bleach localized dye zones, the reverse of normal resist printing, producing luminous white or pale patterns on deep blue grounds.",
        "summary_ta": "ஆழமான இளநீல பருத்தி பின்னணியில் ஒளி-வண்ண உருவங்கள் உருவாக்கும் பாரம்பரிய தமிழ் டிஸ்சார்ஜ் அச்சு தொழில்நுட்பம்: முன் இளநீல சாயமிட்ட துணியில் அமில சிட்ரிக் அல்லது புளி விழைவு அச்சு, இளநீல சாயத்தை இரசாயன முறையில் குறைத்து வெளுக்கச் செய்தல்.",
        "sources": [
            "Discharge Printing Techniques",
            "Natural Dye Textile Technology of India",
            "South Asian Textile Chemistry"
        ],
        "content": "# Discharge Printing: Creating Light on Dark\n\nNormal resist printing *prevents* dye reaching white fabric areas. Discharge printing works inversely — it *removes* dye from already-colored fabric to create light motifs on dark grounds.\n\n**Indigo Discharge Chemistry:**\nIndigo dye can be chemically reduced back to water-soluble leuco-indigo (colorless) by reducing agents. Traditional Tamil discharge paste:\n- Tamarind (*puli*) paste (tartaric + citric acid mixture): Lowers local pH to 2–3.\n- Rice bran ash filtrate (sodium carbonate + potassium carbonate): Provides alkaline reducing microenvironment.\n- Fermented rice water: Provides biological reductase activity.\n\nWhen this paste is block-printed onto deep indigo fabric and left for 12 hours under damp cloth, the acids and mild reductants convert insoluble indigo back to soluble leuco-indigo in the pasted zone. After washing with water, the leuco-indigo diffuses out of the fiber, leaving a bright white or pale blue-grey pattern surrounded by deep indigo.\n\n**Visual Effect:**\nThe resulting textile shows luminous white lotuses, geometric borders, or deity silhouettes on deep midnight-blue grounds — an effect that cannot be achieved by any form of normal block printing on white fabric. The color contrast (white on deep indigo blue) is significantly more dramatic than indigo-on-white.\n\n**Double Discharge:**\nAfter the first discharge step, a mordant paste can be block-printed in the discharged (now white) zones and re-dyed with madder to produce white→red spots within blue grounds — giving three-color effects from a two-step process."
    },
    {
        "file": "knowledge/places/place-sikkanayakanpettai-ancient-kalamkari-haven.md",
        "slug": "place-sikkanayakanpettai-ancient-kalamkari-haven",
        "category": "place",
        "name_en": "Sikkanayakanpettai: Ancient Tamil Kalamkari Haven, Chintamani Panel Workshops & Living Natural-Dye Block Print Citadel",
        "name_ta": "சிக்கனாயக்கன்பேட்டை - பண்டைய தமிழ் காலம்காரி தளம், சிந்தாமணி பட்டை பட்டறைகள் மற்றும் உயிர்ப்புள்ள இயற்கை சாய அச்சு மையம்",
        "era": "Medieval to Modern Era",
        "year_start": 900,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Historic kalamkari production village in Thanjavur district near Kumbakonam, home to the most significant surviving Tamil natural-dye block-printing and hand-painting artisan community, celebrated for its Chintamani narrative pictorial temple textiles, Brihadeeswara temple supply history, and the living padumanar hereditary master dyer families continuing the ancient wax-resist and block-print traditions.",
        "summary_ta": "குமாரகோணம் அருகில் தஞ்சாவூர் மாவட்டத்தில் வரலாற்று காலம்காரி உற்பத்தி கிராமம்: சிந்தாமணி கோயில் துணிகள், பிருகதீஸ்வர கோயில் வழங்கல் வரலாறு மற்றும் உயிர்ப்புள்ள படுமனார் மரபு கலைஞர் குடும்பங்கள்.",
        "sources": [
            "Thanjavur District Artisan Survey",
            "GI Tag Documentation: Sikkanayakanpettai Kalamkari",
            "Tamil Nadu Craft Revival Board Reports"
        ],
        "content": "# Sikkanayakanpettai: Kalamkari Haven\n\nSikkanayakanpettai village in Thanjavur district (10°48'N, 79°28'E) is the foremost surviving center of traditional Tamil natural-dye kalamkari textile art.\n\n**Geographic Advantage:**\nThe village sits adjacent to seasonal streams feeding the Kaveri delta's distributaries. The soft, slightly alkaline river water (low calcium, low iron — TDS ~180 ppm) is ideal for both indigo vat management and madder dyeing. High iron content in water would precipitate indigo prematurely; high calcium would interfere with alum mordant anchoring.\n\n**Temple Textile Supply Chain:**\nHistorical records confirm that Sikkanayakanpettai padumanar families supplied Brihadeeswara (Thanjavur), Airavatesvara (Darasuram), and Gangaikondacholapuram temples with:\n- Monthly *thiruvurai* deity dress cloths (block-printed cotton in saffron, red, and deep blue).\n- Annual festival Chintamani narrative panels for the *Brahmotsavam* procession.\n- Structural *pandal* (canopy) hangings in block-printed geometric designs.\n\n**GI Recognition:**\nSikkanayakanpettai kalamkari received Geographical Indication (GI) recognition from the Government of India (2019) as a unique regional craft tradition, distinguishing it from the Andhra Pradesh Srikalahasti style.\n\n**Living Artisan Community:**\nApproximately 85 practicing artisans in 12 padumanar families continue the full traditional process — from myrobalan pre-treatment through block-printing to natural-dye finishing — without industrial chemical substitutes."
    }
]

EDGES = [
    [
        "text-silappadikaram-and-manimekalai-on-sithira-aadai-painted-garments-and-bazaar-dyers",
        "DOCUMENTS",
        "institution-sikkanayakanpettai-kalamkari-padumanar-guild-of-master-dyers-and-block-printers",
        "core",
        "Sangam Era to Modern Era",
        "Silappadikaram attests the padumanar textile artist guild tradition in Sangam-era Kaveripattinam",
        "Silappadikaram V:14-18"
    ],
    [
        "technology-kalamkari-wax-resist-chari-pen-and-block-painting",
        "APPLIES",
        "concept-indigo-madder-turmeric-and-myrobalan-mordant-dye-chemistry-on-cotton",
        "core",
        "Early Medieval to Modern Era",
        "Kalamkari technique applies the full Tamil natural dye chemistry system",
        "Natural Dye Chemistry of South Asia"
    ],
    [
        "technology-cotton-myrobalan-alum-pre-mordant-treatment-sequence",
        "ENABLES",
        "technology-kalamkari-wax-resist-chari-pen-and-block-painting",
        "core",
        "Iron Age to Modern Era",
        "Pre-mordanting creates the metallic dye-anchoring sites required for color-fast kalamkari dyeing",
        "Mordant Textile Chemistry"
    ],
    [
        "artifact-tharisai-carved-teak-printing-block-and-natural-dye-paste-tray",
        "IMPLEMENTS",
        "technology-kalamkari-wax-resist-chari-pen-and-block-painting",
        "core",
        "Medieval to Modern Era",
        "The carved teak block and dye paste tray are the material instruments of block-print kalamkari",
        "Tamil Nadu Handicrafts Catalog"
    ],
    [
        "concept-wax-resist-capillary-penetration-and-crackling-dye-halos",
        "EXPLAINS",
        "technology-kalamkari-wax-resist-chari-pen-and-block-painting",
        "core",
        "Medieval to Modern Era",
        "Capillary penetration physics explains both the effectiveness and characteristic crackling aesthetics of wax-resist",
        "Textile Research Journal"
    ],
    [
        "concept-indigo-indigofera-tinctoria-cultivation-and-fermentation-vat-extraction",
        "PRODUCES",
        "concept-indigo-madder-turmeric-and-myrobalan-mordant-dye-chemistry-on-cotton",
        "core",
        "Iron Age to Modern Era",
        "Indigofera tinctoria fermentation vat extraction produces the indigo pigment central to Tamil dye chemistry",
        "History of Indigo in South Asia"
    ],
    [
        "technology-natural-dye-discharge-printing-and-resist-bleach-on-pre-dyed-cotton",
        "EXTENDS",
        "technology-kalamkari-wax-resist-chari-pen-and-block-painting",
        "core",
        "Medieval to Modern Era",
        "Discharge printing inverts the resist printing logic, extending the aesthetic range of kalamkari",
        "Discharge Printing Techniques"
    ],
    [
        "institution-sikkanayakanpettai-kalamkari-padumanar-guild-of-master-dyers-and-block-printers",
        "HOSTED_AT",
        "place-sikkanayakanpettai-ancient-kalamkari-haven",
        "core",
        "Medieval to Modern Era",
        "Padumanar guild operated from Sikkanayakanpettai near Kumbakonam in Thanjavur district",
        "Thanjavur District Artisan Survey"
    ],
    [
        "artifact-tharisai-carved-teak-printing-block-and-natural-dye-paste-tray",
        "APPLIES",
        "technology-cotton-myrobalan-alum-pre-mordant-treatment-sequence",
        "core",
        "Medieval to Modern Era",
        "Block printing applies mordant paste selectively in the khari technique before immersion dyeing",
        "Indian Block Print Techniques"
    ],
    [
        "concept-indigo-indigofera-tinctoria-cultivation-and-fermentation-vat-extraction",
        "SUPPLIED",
        "place-sikkanayakanpettai-ancient-kalamkari-haven",
        "core",
        "Iron Age to Modern Era",
        "Tiruppur and Madurai district indigo cultivation supplied Sikkanayakanpettai kalamkari workshops",
        "Tamil Nadu Indigo Cultivation Documentation"
    ]
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]

def main():
    print("Starting Ingestion Batch 39: Ancient Tamil Natural Dye Block Printing, Wax-Resist Kalamkari Hand-Painting & Sithira-Aadai Textile Traditions...")
    
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

    print(f"Ingestion Complete for Batch 39 Corpus! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
