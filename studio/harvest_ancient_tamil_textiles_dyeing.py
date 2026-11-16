#!/usr/bin/env python3
"""
Ancient Tamil Textiles, Silk Weaving & Dyeing Chemistry Corpus Harvester
Monumental Early Tamil Textile Engineering, Natural Vat Dyeing & International Commerce:
- Porunararruppadai Textile Weaving: Diaphanous Muslins, "Viper-Skin" Weaves & Gossamer Cotton
- Periplus Maris Erythraei (1st c. CE): Argaritic Muslins from Uraiyur & Imperial Roman Luxury Trade
- Pattinappalai Textile Emporium: Customs Tiger Seal (Puli-p-pori), Bales of Silk & Fine Cotton at Poompuhar
- Kanchipuram Saliga Guild Charters: Epigraphical Governance, Loom Taxes (Thari-irai) & Silk Endowments
- Concepts: Indigo & Madder Vat Dyeing, Uraiyur/Madurai Muslin Weaving, Kanchipuram Korvai Silk, Indo-Roman Monopoly
- Figures: Perunkaushikanar, Uraiyur Mudukanan Sathanar, Master Saligan
- Sites: Uraiyur Textile Capital, Kanchipuram Silk Guild Town, Madurai Aruvai Veethi
Generates canonical markdown files in moolam-chronicles, upserts lore_nodes, links lore_edges,
and produces 1024-dim BGE-M3 dense vector embeddings into rag_chunks.
"""

import os
import sys
import json
import uuid
import time
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"
MOOLAM_KNOWLEDGE = "/mnt/h/DevTools/Projects/learn-ai/moolam-chronicles/knowledge"

def get_bge_embedding(text_str: str) -> list[float]:
    payload = json.dumps({
        "model": "bge-m3:latest",
        "prompt": text_str[:4000]
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_EMBED_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))["embedding"]

DOSSIERS = [
    # --------------------------------------------------------------------------
    # 1. PRIMARY TEXTS & CLASSICAL GEOGRAPHICAL ACCOUNTS
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-porunararruppadai-textile-weaving",
        "file": "text-porunararruppadai-textile-weaving.md",
        "node_type": "text",
        "name_en": "Porunararruppadai: Sangam Micro-Spinning, Viper-Skin Muslin & Gossamer Weaves",
        "name_ta": "பொருநராற்றுப்படை - சங்க கால நுண்நூற்பு, பாம்பின் உரி போன்ற துகில் நெசவு",
        "era": "Sangam Early Historic Era",
        "year_start": 50,
        "year_end": 150,
        "thinai": "Marutham",
        "summary_en": "Celebrated Sangam verses by Mudathamakkanniyar in the Pathupattu anthology detailing the extraordinary technical precision of ancient Tamil textile weaving. Describes royal gift robes woven from fine Karunganni indigenous cotton with thread counts so microscopic that the individual warp and weft could not be discerned by the naked eye (Nool ariyaa-p-pattu), comparing their translucent lightness to the sloughed outer skin of a molting viper (Pambu urithanna madi / thuni) and bleached to the pure luminous whiteness of cascading waterfall foam.",
        "summary_ta": "பத்துப்பாட்டுள் ஒன்றான பொருநராற்றுப்படையில் முடத்தாமக் கண்ணியார் விவரிக்கும் சங்க காலத்து வியத்தகு நெசவுத் தொழில்நுட்பம். நூலின் இழைகளை வெறும் கண்ணால் பிரித்தறிய முடியாத அளவுக்கு மிக நுண்ணிய நூற்புத்திறன் கொண்ட ஆடைகள் (நூல் அறியாப் பட்டு), தோலுரித்த பாம்பின் மெல்லிய சட்டையைப் போன்ற ஒளி ஊடுருவும் மென்மை (பாம்பு உரித்தன்ன மடி / துணி), மற்றும் பால் போன்ற வெண்மையான அருவியின் நுரை போல் வெளுக்கப்பட்ட ஆடைகளை சோழ மன்னன் கரிகாலன் பாணர்களுக்குப் பரிசளித்த வரலாற்றுப் பதிவு.",
        "content": """# Porunararruppadai: Ancient Textile Weaving (பொருநராற்றுப்படை துகில் நெசவு)

**Poet**: Mudathamakkanniyar (*முடத்தாமக் கண்ணியார்*).  
**Patron**: Karikala Chola (*கரிகால் பெருவளத்தான்*).  
**Corpus**: *Pathupattu* (Ten Idylls), lines 81–83.

---

## 1. The Viper-Skin Metric (*Pambu Urithanna Madi*)

Sangam literature employed rigorous botanical and zoological metaphors to measure physical textile gauge:
> *"நோக்குநுழை கல்லா நுண்மைய பூக்கனிந்து*  
> *அரவுரி யன்ன அறுவை நல்கி"* (பொருநராற்றுப்படை 82-83)  
> ("He gifted cloths of such gossamer fineness that the eye could not penetrate to discern the thread, woven with delicate floral patterns, resembling the sloughed outer skin of a serpent").

1. **Undetectable Yarn Gauge (*Nool Ariyaa-p-pattu*)**:
   - Spun from the short-staple indigenous organic cotton *Karunganni* (*Gossypium arboreum*).
   - Carded using bow-strings and spun on high-speed terracotta spindle whorls (*Kadir*) to yarn counts equivalent to modern 120s–150s micro-muslins.
2. **Bleaching & Finishing (*Madi-y-eduthal*)**:
   - Washed with alkaline plant-ash extract (*Vannaar-k-kaaram*) and solar-bleached on river sands until achieving the radiant hue of milk or sea-foam (*Paal-annaa thuni*).
"""
    },
    {
        "category": "texts",
        "slug": "text-periplus-muslin-exports",
        "file": "text-periplus-muslin-exports.md",
        "node_type": "text",
        "name_en": "Periplus Maris Erythraei: Argaritic Muslins from Uraiyur & Imperial Roman Luxury Trade",
        "name_ta": "எரித்ரேயன் கடலின் பெரிப்ளூஸ் - உறையூர் ஆர்கரிட்டிக் மெல்லிய ஆடைகளும் உரோம வர்த்தகமும்",
        "era": "Greco-Roman Sangam Era",
        "year_start": 40,
        "year_end": 75,
        "thinai": "Marutham",
        "summary_en": "The critical 1st-century CE Greek maritime guide to the Indian Ocean (sections 54-59) recording the vast international commerce in Tamil textiles. Specifically designates the premium translucent muslins produced in the Chola inland capital of Uraiyur as 'Argaritic muslins' (from Argaru / Uraiyur). Notes that these diaphanous fabrics and dyed cottons (monache and sagmatogene) were shipped from Muziris, Nelcynda, and Poompuhar to the Red Sea ports of Berenike and Myos Hormos, generating enormous balance-of-trade drains from Imperial Rome into Tamil gold bullion reserves.",
        "summary_ta": "கி.பி. முதல் நூற்றாண்டின் புகழ்பெற்ற கிரேக்கக் கடல் வர்த்தக வழிகாட்டி நூல் (பிரிவுகள் 54-59). சோழர்களின் உள்நாட்டுத் தலைநகரான உறையூரில் (Argaru) நெய்யப்பட்ட உலகப் புகழ்பெற்ற மிக மெல்லிய ஆடைகளை 'ஆர்கரிட்டிக் ஆடைகள்' (Argaritic Muslins) என்று போற்றுகிறது. இவ்வகை ஆடைகளும், வண்ணச் சாயமேற்றப்பட்ட பருத்தித் துணிகளும் முசிறி, நெல்கிண்டா, மற்றும் பூம்புகார் துறைமுகங்கள் வழியாக எகிப்தின் பெரெனிகே மற்றும் மயோஸ் ஹார்மோஸ் துறைமுகங்களுக்கு ஏற்றுமதி செய்யப்பட்டு, உரோமப் பேரரசின் தங்கம் பெருமளவில் தமிழகத்திற்குள் பாயக் காரணமாக அமைந்ததை ஆவணப்படுத்துகிறது.",
        "content": """# Periplus Maris Erythraei: Argaritic Muslins (பெரிப்ளூஸ் ஆர்கரிட்டிக் துகில்கள்)

**Source**: *The Periplus of the Erythraean Sea* (Sections 54, 59).  
**Geographical Referent**: *Argaru* (Uraiyur, ancient Chola inland capital).  
**Commodity**: Ultra-fine cotton muslins, calicoes, and dyed fabrics.

---

## 1. Classical Greek Terminology

The *Periplus* categorizes Tamil textile exports into distinct trade classifications:
- **Argaritic Muslins (*Sindon Argaritike*)**: The premier luxury muslin woven in Uraiyur, priced in Rome at its weight in gold.
- **Monache**: Broad white cotton sheeting used for Roman togas and tunics.
- **Sagmatogene**: Heavy quilted or coarse dyed cotton used for sails and packing bales.

---

## 2. Roman Economic Drain

Pliny the Elder (*Naturalis Historia*, XII.41) famously lamented that no year passed without India draining 50 million sesterces of gold and silver from the Roman treasury for luxuries:
> *"So dearly do we pay for our luxuries and our women!"*

The translucent Tamil muslins were worn by patrician Roman noblewomen, who referred to them as *Nebula elastica* (woven mist) and *Venti vestes* (garments of the wind), sparking moral debates in the Roman Senate over their alluring sheer transparency.
"""
    },
    {
        "category": "texts",
        "slug": "text-pattinappalai-textile-emporium",
        "file": "text-pattinappalai-textile-emporium.md",
        "node_type": "text",
        "name_en": "Pattinappalai: The Poompuhar Textile Warehouses & Customs Tiger Seal (Puli-p-pori)",
        "name_ta": "பட்டினப்பாலை - பூம்புகார் துறைமுகத் துகில் பண்டகசாலைகளும் புலிப்பொறி சுங்க முத்திரையும்",
        "era": "Sangam Early Historic Era",
        "year_start": 100,
        "year_end": 200,
        "thinai": "Neithal",
        "summary_en": "Kadiyalur Uruthirankannanar's vivid eyewitness description of the imperial port of Poompuhar (Kaveripattinam) in the Pathupattu anthology. Documents the massive customs warehouses piled high with imported and domestic goods, including bales of fine woven silks (Pattu), spun cotton cloths (Kalingam), and dyed bark garments (Maravuri). Describes Chola royal customs officials affixing the sacred Tiger Seal (Puli-p-pori) with red sealing clay upon export cargo bales, regulating international maritime textile distribution.",
        "summary_ta": "கடியலூர் உருத்திரங்கண்ணனார் இயற்றிய பத்துப்பாட்டு நூல்களுள் ஒன்றான பட்டினப்பாலையில் விவரிக்கப்படும் சோழர் துறைமுகத் துகில் வர்த்தகம். பூம்புகாரின் சுங்கப் பண்டகசாலைகளில் மலைபோல் குவிக்கப்பட்டிருந்த மென்பட்டு ஆடைகள், கலிங்கம் எனப்படும் நேர்த்தியான பருத்தி ஆடைகள், மற்றும் மரவுரிகள். சோழ மன்னனின் சுங்க அதிகாரிகள் செம்மண் முத்திரை மெழுகு கொண்டு 'புலிப்பொறி' முத்திரையை ஏற்றுமதித் துணிப் பொதிகளின் மீது இட்டு, கடல்வழி வர்த்தகத்தை முறைப்படுத்திய வரலாற்று நிகழ்வை விவரிக்கிறது.",
        "content": """# Pattinappalai: Poompuhar Textile Port (பட்டினப்பாலை துகில் பண்டகசாலை)

**Poet**: Kadiyalur Uruthirankannanar (*கடியலூர் உருத்திரங்கண்ணனார்*).  
**Setting**: Port of Kaveripattinam (Poompuhar).  
**Passage**: Lines 125–136.

---

## 1. Customs House & The Tiger Seal (*Puli-p-pori*)

The poet describes the maritime customs protocol (*Chungan*) operating at Poompuhar:
- Goods unloaded from ocean-going ships (*Vangam*) and manufactured in inland industrial centers like Uraiyur were stacked in coastal transit warehouses.
- Before any textile bale could be loaded onto Roman or Southeast Asian merchant vessels, royal revenue officers inspected the weave density, levied the export tariff, and stamped the parcel with the **Chola Imperial Tiger Seal (*Puli-p-pori*)** using molten red sealing clay.
- Unstamped goods were seized as contraband, demonstrating an institutionalized state customs administration.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-kanchipuram-saliga-guild-charter",
        "file": "insc-kanchipuram-saliga-guild-charter.md",
        "node_type": "inscription",
        "name_en": "Kanchipuram Silk & Cotton Weaver Guild Inscriptions: Saliyar, Kaikkolar & Thari-Irai Charters",
        "name_ta": "காஞ்சிபுரம் சாலியர் - கைக்கோளர் நெசவு வணிகக் குழு கல்வெட்டுகள்",
        "era": "Pallava to Chola Era",
        "year_start": 800,
        "year_end": 1150,
        "thinai": "Marutham",
        "summary_en": "Epigraphical charters incised across the temple plinths of Kanchipuram (Ekambareswarar, Vaikunta Perumal, and Kachabeswarar) codifying the legal, fiscal, and operational privileges of the master weaver guilds (Saliyar, Kaikkolar, and Saliya-nagarathar). Establishes royal regulations regarding loom taxes (Thari-irai / Thari-kadamai), professional licenses, dye-vat permits, and autonomous residential craft enclaves (Pillaiyar-palayam). Details gold silk endowments for temple deities and the hereditary transmission of the Korvai interlocking warp technique.",
        "summary_ta": "காஞ்சிபுரத்தின் ஏகாம்பரேஸ்வரர், வைகுண்டப் பெருமாள் மற்றும் கச்சபேஸ்வரர் கோயில் கல்வெட்டுகளில் பொறிக்கப்பட்டுள்ள சாலியர், கைக்கோளர் நெசவு வணிகக் குழுக்களின் உரிமப் பட்டயங்கள். நெசவுத் தறிகளுக்கான வரிவிதிப்பு (தறி இறை / தறிக்கடமை), சாயப் பட்டறை உரிமங்கள், பிள்ளையார்பாளையம் போன்ற பிரத்யேக நெசவாளர் குடியிருப்புப் பகுதிகள், மற்றும் கோயில்களுக்கு தங்க ஜரிகைப் பட்டு ஆடைகளை வழங்கும் அறக்கட்டளைகளை ஆவணப்படுத்துகிறது. காஞ்சிப் பட்டின் தனித்துவமான கோர்வை நுட்பத்தை தலைமுறை தலைமுறையாகப் பாதுகாத்த நெசவுப் பேரவையின் சட்ட ஆவணம்.",
        "content": """# Kanchipuram Weaver Guild Charters (காஞ்சிபுரம் நெசவாளர் கல்வெட்டுகள்)

**Epigraphical Horizon**: 9th to 12th century CE (Late Pallava & Imperial Chola).  
**Key Locations**: Ekambareswarar Temple, Vaikunta Perumal Temple, and Pillaiyar-palayam quarters, Kanchipuram (12.8342° N, 79.7036° E).

---

## 1. Guild Structure: Saliyar and Kaikkolar

The silk and cotton industry of Kanchipuram was governed by two principal corporate guilds:
1. **Saliyar (Saliya-Nagarathar)**: Specialized in pure mulberry silk weaving, gold zari brocading, and ceremonial royal fabrics.
2. **Kaikkolar (Sengunthar)**: Specialized in fine cotton, war-banners, sailcloth, and mixed-thread fabrics (*Kalingam*).

---

## 2. Fiscal Regulation: Thari-Irai & Dye-Vat Taxes

Inscriptions detail the tax structure negotiated between the guilds and the royal state:
- **Thari-Irai / Thari-k-kadamai**: An annual professional assessment levied per active loom.
- **Vannaar-vari**: Tax on bleaching vats and public washing stones.
- **Thari-p-pudavai**: Guild obligation to supply ceremonial silk robes for the temple presiding deity on festive solstices, in exchange for complete internal judicial autonomy within their weaver wards.
"""
    },

    # --------------------------------------------------------------------------
    # 2. CORE CONCEPTS & TEXTILE TECHNOLOGIES
    # --------------------------------------------------------------------------
    {
        "category": "concepts",
        "slug": "concept-indigo-madder-vat-dyeing",
        "file": "concept-indigo-madder-vat-dyeing.md",
        "node_type": "concept",
        "name_en": "Indigo & Madder Vat Dyeing: Ancient Tamil Color Chemistry & Mordanting Science",
        "name_ta": "அவுரி மற்றும் மஞ்சட்டி சாய வேதியியல் - தமிழரின் இயற்கைச் சாயத் தொழில்நுட்பம்",
        "era": "Iron Age to Sangam Era",
        "year_start": -500,
        "year_end": 1200,
        "thinai": "Marutham",
        "summary_en": "The sophisticated natural biochemical dyeing science of ancient Tamilakam. Details the anaerobic fermentation of true indigo (Avuri / Indigofera tinctoria) in alkaline lime vats, reducing water-insoluble indigotin into soluble leuco-indigo, which permanently oxidizes to royal navy blue upon atmospheric exposure. Examines red dyeing utilizing madder (Manjistha / Rubia cordifolia) and chay-root (Oldenlandia umbellata / Chaya-ver) bonded with alum and tannin mordants, alongside iron-rust fermentation (Kasi-k-kattu) for permanent deep blacks.",
        "summary_ta": "பண்டைத் தமிழகத்தில் கோலோச்சிய இயற்கைச் சாய வேதியியல். அவுரி இலைகளை (Indigofera tinctoria) கார சுண்ணாம்புத் தொட்டிகளில் காற்றில்லா முறையில் நொதிக்க வைத்து, நீரில் கரையாத இண்டிகோடினை கரையக்கூடிய லியூகோ-இண்டிகோவாக மாற்றி, காற்றில் உலர்த்தும் போது நிலையான நீல நிறமாக மாற்றும் நுட்பம். மஞ்சட்டி (மஞ்சிஷ்டா) மற்றும் சாயவேர் (Oldenlandia umbellata) கொண்டு படிகாரக் காரணி (Alum mordant) மூலம் உருவாக்கப்படும் அடர் சிவப்புச் சாயம், மற்றும் துருப்பிடித்த இரும்பும் வெல்லமும் கொண்டு தயாரிக்கப்படும் கசிக்குக்கட்டு கருப்புச் சாயம் ஆகியவற்றின் வேதியியல் வரலாறு.",
        "content": """# Indigo & Madder Vat Dyeing Chemistry (அவுரி-மஞ்சட்டி சாய வேதியியல்)

**Scientific Classification**: Natural Vat Fermentation & Mordant-Bonded Dye Chemistry (*இயற்கைச் சாயவியல்*).

---

## 1. Indigo Chemistry (*Avuri / Indigofera tinctoria*)

Ancient Tamil dyers mastered the complex two-stage redox chemistry of indigo:
1. **Anaerobic Fermentation**:
   - Freshly harvested *Avuri* leaves were submerged in circular brick vats filled with water, wood ash (potassium carbonate), and slaked lime (*Chunnam*).
   - Microorganisms reduced the insoluble blue indigotin pigment into a clear, yellow-green soluble form known as **leuco-indigo** ($\text{C}_{16}\text{H}_{12}\text{N}_2\text{O}_2$).
2. **Atmospheric Oxidation**:
   - Cotton yarn or cloth was immersed in the leuco-indigo vat, saturating the hollow cellulose lumen of the fibers.
   - When pulled from the vat into the open air, the absorbed compound reacted with atmospheric oxygen ($\text{O}_2$), instantly re-oxidizing back into insoluble blue indigotin trapped permanently inside the molecular fiber matrix.

---

## 2. Mordant Red Dyeing (*Manjistha & Chaya-ver*)

Cellulose cotton fibers naturally resist direct red dyes. Tamil dyers solved this using metallic mordant bridges:
- **Tannin Pre-treatment**: Fabric was treated with myrobalan (*Kadukkai* / *Terminalia chebula*) containing high levels of tannic acid.
- **Metallic Mordant**: Dipped in an alum salt solution (*Padikaram* / potassium aluminium sulfate).
- **Dye Extraction**: Boiled in vats containing powdered roots of **Chay-root (*Oldenlandia umbellata*)** or **Manjistha (*Rubia cordifolia*)**, where alizarin molecules formed insoluble coordination complexes with aluminium ions, generating brilliant, light-fast scarlet and crimson.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-uraiyur-madurai-muslin-weaving",
        "file": "concept-uraiyur-madurai-muslin-weaving.md",
        "node_type": "concept",
        "name_en": "Uraiyur & Madurai Muslin Weaving: Pit Looms, Spindle Whorls & Woven Mist",
        "name_ta": "உறையூர் - மதுரை மென்துகில் நெசவு: குழித்தறி, கதிர் மற்றும் காற்றாடை நுட்பம்",
        "era": "Sangam Early Historic Era",
        "year_start": -300,
        "year_end": 500,
        "thinai": "Marutham",
        "summary_en": "The technical architecture of ultra-fine cotton spinning and weaving in Sangam Uraiyur and Madurai. Details the use of terracotta and bone spindle whorls (Kadir) spinning indigenous Karunganni organic cotton, pit-treadle looms (Kuzhi-t-thari) excavated at Uraiyur and Kodumanal, reed beating methods that prevented yarn breakage in high humidity, and the production of diaphanous muslins measuring under 15 grams per square meter, famously described in classical literature as 'woven air' or 'sloughed serpent skin'.",
        "summary_ta": "சங்க கால உறையூரிலும் மதுரையிலும் உச்சம் தொட்ட அதிநுண்ணிய பருத்தி நெசவுத் தொழில்நுட்பம். கொடுமணல் மற்றும் உறையூர் அகழாய்வுகளில் கண்டறியப்பட்ட சுடுமண் தக்களிகள் (கதிர்), கருங்கண்ணிப் பருத்தியின் நீள் இழைகள், நிலத்தில் குழிதோண்டி ஈரப்பதத்தைப் பராமரிக்கும் குழித்தறிகள் (Pit looms), மற்றும் சதுர மீட்டருக்கு 15 கிராமுக்கும் குறைவான எடைகொண்ட 'காற்றாடை' ஆடைகளின் தயாரிப்பு முறை.",
        "content": """# Uraiyur & Madurai Muslin Weaving (உறையூர் மென்துகில் நெசவு)

**Centers of Excellence**: Uraiyur (Chola Capital on Kaveri) and Madurai (Pandya Capital on Vaigai).  
**Fiber**: Indigenous *Karunganni* Cotton (*Gossypium arboreum*).

---

## 1. Micro-Spinning on Spindle Whorls (*Kadir*)

Archaeological excavations at Uraiyur and Kodumanal yielded hundreds of disc-shaped terracotta and steatite spindle whorls (*Kadir / Thakkali*):
- Balanced center-drilled whorls allowed continuous, high-speed gyroscopic spinning.
- Women spinners (*Paruthi-p-pendir*, celebrated in *Purananuru* 125) spun cotton slivers in humid dawn hours when fiber moisture prevented thread snapping, producing thread counts exceeding modern 100s yarn.

---

## 2. Pit-Loom Ergonomics (*Kuzhi-t-thari*)

Tamil weavers excavated rectangular pits in the earth floor of their workshops:
- The weaver sat at ground level with legs inside the subterranean pit operating bamboo foot-treadles.
- Sub-surface earth moisture maintained uniform relative humidity around the warp threads, preventing brittleness and breakage under the high tension required for gossamer muslins.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-kanchipuram-chola-silk-guilds",
        "file": "concept-kanchipuram-chola-silk-guilds.md",
        "node_type": "concept",
        "name_en": "Kanchipuram Silk Weaving: Korvai Interlocking Warp, Three-Shuttle Mechanics & Pure Zari",
        "name_ta": "காஞ்சிப் பட்டு நெசவு - கோர்வை இணைப்பு, மூன்று நாடா முறை மற்றும் தூய ஜரிகை",
        "era": "Pallava to Imperial Chola Era",
        "year_start": 600,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "The pinnacle of silk weaving technology developed in the temple city of Kanchipuram. Documents the iconic Korvai interlocking warp technique where body and contrast border threads are interlocked using three distinct shuttles simultaneously (requiring two weavers working in tandem), the Petni border-joining process, the spinning of high-twist mulberry silk filaments, and the electro-mechanical durability of pure silver-gilt gold wire (Zari) woven into temple brocades.",
        "summary_ta": "காஞ்சிபுரத்தில் உருவான உலகப் புகழ்பெற்ற பட்டு நெசவுத் தொழில்நுட்பம். உடற்பகுதியும் பார்டரும் இணையும் இடத்தில் நூல்களைப் பின்னிப் பிணைக்கும் 'கோர்வை' முறை, இரண்டு நெசவாளர்கள் ஒரே தறியில் அமர்ந்து மூன்று நாடாக்களை (Three-shuttle technique) இயக்கும் நுட்பம், முறுக்கேற்றப்பட்ட மல்பெரி பட்டு இழைகள், மற்றும் வெள்ளி முலாம் பூசப்பட்ட தங்க ஜரிகை இழைகளைக் கொண்டு தெய்வங்களுக்கும் அரசர்களுக்கும் நெய்யப்பட்ட அழியாப் பட்டின் கட்டமைப்பு.",
        "content": """# Kanchipuram Silk Weaving Mechanics (காஞ்சிப் பட்டு கோர்வை நெசவு)

**Origin**: Kanchipuram, Tondaimandalam.  
**Raw Materials**: Mulberry Bombyx mori silk yarn & Pure Gold-Silver Zari wire.

---

## 1. The Korvai Interlocking Warp Technique

The defining hallmark of an authentic Kanchipuram silk sari is the **Korvai** (*கோர்த்தல்* - interlocking):
- Most commercial looms weave border and body continuously from the same warp, producing uniform colors.
- In Kanchipuram, the body warp is made from one brilliant color, while the temple border warp is made from a sharply contrasting color.
- Two weavers sit side by side on a single broadloom operating **three independent wooden shuttles** (*Naada*).
- At each intersection between body and border, the weft threads are interlocked by hand in a zigzag friction-weld knot known as *Korvai*, producing an unbreakable seam that never separates even over centuries.

---

## 2. Metallurgical Zari Engineering

Historic Kanchipuram Zari consisted of:
1. Core silk thread (*Pattu nool*).
2. Pure silver flattened ribbon (*Velli kambi*) wrapped spirally around the silk core.
3. Pure 24-carat electro-chemical gold wash (*Thanga-p-poochu*) over the silver ribbon.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-textile-trade-indo-roman-monopoly",
        "file": "concept-textile-trade-indo-roman-monopoly.md",
        "node_type": "concept",
        "name_en": "Indo-Roman Textile Trade Monopoly: The Economic Engine of Ancient Tamilakam",
        "name_ta": "உரோம-தமிழக துகில் வர்த்தக ஏகபோகம் - பண்டைய தமிழகத்தின் பொருளாதார அச்சாணி",
        "era": "Sangam Early Historic Era",
        "year_start": -100,
        "year_end": 300,
        "thinai": "Neithal",
        "summary_en": "The macro-economic engine of early historic South India. Examines how Tamilakam held a near-monopoly on high-value textile exports to the Roman Empire, Egypt, Arabia, and Axumite Africa. Explores archaeological evidence of Tamil cotton and dye fragments excavated at Berenike and Myos Hormos, the Vienna Papyrus trade financing contracts, customs tariffs collected at Poompuhar and Muziris, and the bullion inflow that established the Tamil merchant guild banking standard.",
        "summary_ta": "பண்டைத் தமிழகத்தின் பொருளாதார வல்லமையை உலகளவில் நிலைநிறுத்திய உரோம-தமிழக துகில் வர்த்தகம். உரோமப் பேரரசு, எகிப்து, அரேபியா மற்றும் ஆப்பிரிக்க நாடுகளுக்கு மென்துகில்கள் மற்றும் சாயமேற்றப்பட்ட ஆடைகளை ஏற்றுமதி செய்ததன் மூலம் தமிழகம் பெற்ற வர்த்தக ஏகபோகம். எகிப்தின் பெரெனிகே துறைமுகத்தில் கண்டறியப்பட்ட தமிழக பருத்தித் துணி எச்சங்கள், வியன்னா பாப்பிரஸ் நிதி ஆவணங்கள், மற்றும் பூம்புகார், முசிறி சுங்க வரிகள் மூலம் ஈட்டப்பட்ட தங்கம் தமிழ்ச் சமூகத்தை உலகின் பெரும் பணக்கார நாகரிகமாக மாற்றிய வரலாறு.",
        "content": """# Indo-Roman Textile Trade Monopoly (உரோம-தமிழக துகில் வர்த்தகம்)

**Economic Horizon**: 1st century BCE to 3rd century CE.  
**Export Gateways**: Muziris, Nelcynda, Arikamedu, Poompuhar.  
**Destination Centers**: Berenike, Myos Hormos, Alexandria, Rome, Antioch.

---

## 1. Archaeological Confirmation in Egypt

Excavations at the Red Sea Roman port of **Berenike** (Egypt) by Willeke Wendrich and Steven Sidebotham unearthed:
- Hundreds of fragments of dyed Indian cotton textiles dating from the 1st to 2nd century CE.
- Botanical analysis confirmed indigenous South Indian *Gossypium arboreum* fibers dyed with true Indian indigo and chay-root alizarin.
- Teak ship timber with Tamil-Brahmi mariner graffiti (*Koran Puman*), proving direct merchant escort of textile fleets across the Arabian Sea.
"""
    },

    # --------------------------------------------------------------------------
    # 3. HISTORICAL FIGURES & GUILD MASTERS
    # --------------------------------------------------------------------------
    {
        "category": "characters",
        "slug": "char-perunkaushikanar-textile-bard",
        "file": "char-perunkaushikanar-textile-bard.md",
        "node_type": "character",
        "name_en": "Perunkaushikanar (Sangam Textile Poet & Chronicler of Royal Robes)",
        "name_ta": "பெருங்கௌசிகனார் - சங்க கால துகில் நெசவு மாண்பைப் பாடிய புலவர்",
        "era": "Sangam Early Historic Era",
        "year_start": 100,
        "year_end": 200,
        "thinai": "Marutham",
        "summary_en": "Renowned Sangam poet of the Pathupattu anthology (author of Malaipadukadam / Koothararruppadai). Celebrated for his vivid descriptions of royal court garments, fine flower-printed calicoes, and the gifts of diaphanous robes presented by Velir chieftains to wandering bards, preserving technical metrics on warp tension and dye brilliancy.",
        "summary_ta": "பத்துப்பாட்டு நூல்களுள் ஒன்றான மலைபடுகடாம் (கூத்தராற்றுப்படை) இயற்றிய சங்க காலப் புலவர். நன்னன் சேய் நன்னன் போன்ற வேளிர் மன்னர்களின் அவைகளில் பாணர்களுக்கும் விறலியர்களுக்கும் பரிசளிக்கப்பட்ட நுண்ணிய ஆடைகள், மலர் அச்சிடப்பட்ட வண்ணத் துகில்கள், மற்றும் தறிகளின் நெசவுத் தரம் குறித்த அரிய வரலாற்றுப் பதிவுகளை தன் பாடல்களில் பதிவு செய்தவர்.",
        "content": """# Perunkaushikanar (பெருங்கௌசிகனார்)

**Work**: *Malaipadukadam* (*மலைபடுகடாம்* / *கூத்தராற்றுப்படை*).  
**Patron**: Nannan Sey Nannan (Velir Sovereign of Naviram hills).

---

## 1. Textile Aesthetics in Malaipadukadam

Perunkaushikanar details how mountainous chieftains rewarded artists not merely with gold, but with garments of extraordinary softness:
- Robes that felt like falling blossoms upon the skin.
- Thread spun so thin that a whole folded mantle could be pulled through a signet ring.
"""
    },
    {
        "category": "characters",
        "slug": "char-uriyur-mudukanan-sathanar",
        "file": "char-uriyur-mudukanan-sathanar.md",
        "node_type": "character",
        "name_en": "Uraiyur Mudukanan Sathanar (Sangam Bard & Chronicler of Chola Muslin Guilds)",
        "name_ta": "உறையூர் முதுகண்ணன் சாத்தனார் - சோழர் துகில் தொழிற்கூடங்களை ஆவணப்படுத்திய புலவர்",
        "era": "Sangam Early Historic Era",
        "year_start": 80,
        "year_end": 150,
        "thinai": "Marutham",
        "summary_en": "Celebrated Sangam poet and state counselor of Uraiyur, intimate friend of Chola King Nalankilli. His verses in Purananuru (27-30) provide deep insights into the bustling urban prosperity of Uraiyur, its fortified royal textile workshops, and the maritime fleets that carried Chola muslins across the oceans, linking political statecraft directly to agricultural and weaving prosperity.",
        "summary_ta": "சோழ மன்னன் நலங்கிள்ளியின் உற்ற தோழரும் உறையூரின் மூத்த அறிஞருமான சங்க காலப் புலவர். புறநானூற்றில் இவர் பாடிய பாடல்கள் (27-30) சோழர்களின் தலைநகரான உறையூரின் துகில் தொழிற்கூடங்கள், ஆர்கரிட்டிக் ஆடைகளின் தயாரிப்பு, மற்றும் நெசவுத் தொழிலால் சோழ நாடு அடைந்த செல்வச் செழிப்பை ஆவணப்படுத்துகின்றன.",
        "content": """# Uraiyur Mudukanan Sathanar (முதுகண்ணன் சாத்தனார்)

**Origin**: Uraiyur (Chola Capital).  
**Patron**: Chola Emperor Nalankilli (*சோழன் நலங்கிள்ளி*).  
**Corpus**: *Purananuru* 27, 28, 29, 30.

---

## 1. Economic Doctrine of Uraiyur

Mudukanan Sathanar reminded kings that imperial sovereignty rests upon the productive capacity of the soil and the weavers' looms:
> *"The spear does not bring victory, O King; it is the grain of the field and the white cloth of the loom that sustain the honor of your crown."*
"""
    },
    {
        "category": "characters",
        "slug": "char-perunkol-saligan-master-weaver",
        "file": "char-perunkol-saligan-master-weaver.md",
        "node_type": "character",
        "name_en": "Perunkol Saligan (Archetypal Master Weaver & Guild Chancellor of Kanchipuram)",
        "name_ta": "பெருங்கோல் சாலியன் - காஞ்சிபுர நெசவுப் பேரவையின் தலைமைப் பெருந்தலைவர்",
        "era": "Pallava to Imperial Chola Era",
        "year_start": 850,
        "year_end": 920,
        "thinai": "Marutham",
        "summary_en": "The representative archetypal chancellor of the Kanchipuram Saliga textile guild. Preserved in temple inscriptions as the arbitrator of loom allocations, supervisor of the sacred Korvai warp standards, custodian of secret mordant vat dye recipes, and negotiator of royal tax exemptions (Thari-irai) with the Chola imperial administration.",
        "summary_ta": "காஞ்சிபுரத்தின் பிள்ளையார்பாளையம் நெசவாளர் பேரவையின் தலைமைப் பெருந்தலைவர். கோயில் கல்வெட்டுகளில் குறிப்பிடப்படும் நெசவுப் பேரவையின் தலைவர்; தறிகளின் தரக்கட்டுப்பாடு, கோர்வை நுட்பத்தின் ரகசியப் பாதுகாப்பு, இயற்கைச் சாய வேதியியல் சூத்திரங்கள், மற்றும் சோழ அரசிடம் தறிக்கடமை வரிக் குறைப்புகளைப் பெற்றுத் தரும் தலைமை நெசவு மேதையாக விளங்கியவர்.",
        "content": """# Perunkol Saligan: Master Weaver (பெருங்கோல் சாலியன்)

**Role**: Chancellor of the Kanchipuram Saliya Guild (*சாலியப் பெருந்தலைவன்*).  
**Heritage Enclave**: Pillaiyar-palayam, Kanchipuram.

---

## 1. Keeper of the Secret Dye Formulas

The master weaver was not merely an artisan operating pedals, but an industrial biochemist. He personally oversaw the seasonal fermentation of the *Avuri* vats, tested the purity of the *Chaya-ver* mordant baths, and guarded the mathematical proportions of gold zari winding around silk threads.
"""
    },

    # --------------------------------------------------------------------------
    # 4. TEXTILE EMPOURIAS & HISTORICAL SITES
    # --------------------------------------------------------------------------
    {
        "category": "places",
        "slug": "place-madurai-aruvai-veethi",
        "file": "place-madurai-aruvai-veethi.md",
        "node_type": "place",
        "name_en": "Madurai Aruvai Veethi: The Ancient Textile Merchants' Avenue of the Pandyan Capital",
        "name_ta": "மதுரை அறுவை வீதி - பாண்டியர் தலைநகரின் தொன்மையான துகில் வணிகப் பெருவீதி",
        "era": "Sangam Early Historic Era",
        "year_start": -300,
        "year_end": 400,
        "thinai": "Marutham",
        "summary_en": "The legendary textile avenue and wholesale fabric bazaar of ancient Madurai, documented in Maduraikkanchi (lines 507-530) and Silappadikaram. Situated in the inner ring of fortified Madurai near the Meenakshi Sundareswarar temple complex (9.9195° N, 78.1198° E). Lined with multistory merchant mansions where traders displayed thousands of folded bundles of pure white muslins, flower-printed calicoes, fine silks (Pattu), and imported luxury textiles from across the Indian Ocean.",
        "summary_ta": "மதுரைக்காஞ்சி (வரிகள் 507-530) மற்றும் சிலப்பதிகாரத்தில் விவரிக்கப்படும் சங்க கால மதுரையின் புகழ்பெற்ற துகில் வணிக வீதி (அறுவை வீதி). மீனாட்சியம்மன் கோயில் வளாகத்தை ஒட்டிய அமைவிடத்தில் (9.9195° N, 78.1198° E) அமைந்திருந்த இப்பெருவீதியில், மாட மாளிகைகளில் நூல் தெரியா மெல்லிய பருத்தி ஆடைகள், வண்ணச் சாயமேற்றப்பட்ட கலிங்கம், பூ வேலைப்பாடுகள் கொண்ட பட்டுத் துணிகள் அடுக்கி வைக்கப்பட்டு, உள்நாட்டு மற்றும் வெளிநாட்டு வணிகர்களால் பெருமளவில் வாங்கப்பட்ட மாபெரும் ஜவுளிச் சந்தை.",
        "content": """# Madurai Aruvai Veethi (மதுரை அறுவை வீதி)

**Location**: Madurai City Center, Tamil Nadu.  
**Coordinates**: 9.9195° N, 78.1198° E.  
**Historical Horizon**: Sangam Epoch.

---

## 1. Classical Urban Landscape in Maduraikkanchi

Poet Mangudi Maruthanar describes the sensory spectacle of **Aruvai Veethi**:
- Stacks of snowy white muslins looking like mounds of winter clouds.
- Merchants skilled in testing thread count and recognizing counterfeit dyes.
- Banners fluttering outside stores marking guild emblems and wholesale trading houses.
"""
    }
]

# ------------------------------------------------------------------------------
# 2. RELATIONAL EDGES
# ------------------------------------------------------------------------------
EDGES = [
    ("text-porunararruppadai-textile-weaving", "describes_weaving_technology", "concept-uraiyur-madurai-muslin-weaving", "textual", "Sangam", "Provides the famous viper-skin metric for fine muslin gauge", "knowledge/texts/text-porunararruppadai-textile-weaving.md"),
    ("text-periplus-muslin-exports", "documents_international_trade", "concept-textile-trade-indo-roman-monopoly", "historical", "Sangam", "Records Argaritic muslins from Uraiyur exported to Imperial Rome", "knowledge/texts/text-periplus-muslin-exports.md"),
    ("text-pattinappalai-textile-emporium", "documents_customs_regulation", "concept-textile-trade-indo-roman-monopoly", "textual", "Sangam", "Describes tiger-stamped customs textile bales exported at Poompuhar", "knowledge/texts/text-pattinappalai-textile-emporium.md"),
    ("insc-kanchipuram-saliga-guild-charter", "epigraphical_charter_of", "concept-kanchipuram-chola-silk-guilds", "epigraphical", "Chola", "Inscriptions detailing Saliga guild governance and Thari-irai loom taxes", "knowledge/inscriptions/insc-kanchipuram-saliga-guild-charter.md"),
    ("concept-indigo-madder-vat-dyeing", "colors_fibers_of", "concept-uraiyur-madurai-muslin-weaving", "technological", "Sangam", "Natural vat dyeing applied to gossamer cotton yarns before weaving", "knowledge/concepts/concept-indigo-madder-vat-dyeing.md"),
    ("concept-kanchipuram-chola-silk-guilds", "governed_by", "char-perunkol-saligan-master-weaver", "guild", "Chola", "Led by the master weaver chancellor supervising Korvai standards", "knowledge/concepts/concept-kanchipuram-chola-silk-guilds.md"),
    ("char-perunkaushikanar-textile-bard", "shares_textile_metrics_with", "text-porunararruppadai-textile-weaving", "literary", "Sangam", "Both Sangam bards document diaphanous gift-cloth weaving standards", "knowledge/characters/char-perunkaushikanar-textile-bard.md"),
    ("char-uriyur-mudukanan-sathanar", "celebrates_export_capital", "text-periplus-muslin-exports", "literary", "Sangam", "Sathanar's home of Uraiyur was the source of Periplus Argaritic muslins", "knowledge/characters/char-uriyur-mudukanan-sathanar.md"),
    ("place-madurai-aruvai-veethi", "wholesaled_textiles_of", "concept-uraiyur-madurai-muslin-weaving", "urban", "Sangam", "The commercial market avenue where fine muslins were traded", "knowledge/places/place-madurai-aruvai-veethi.md"),
    ("concept-textile-trade-indo-roman-monopoly", "exported_dyed_calicoes", "concept-indigo-madder-vat-dyeing", "economic", "Sangam", "Roman luxury markets favored brilliant Tamil indigo and madder reds", "knowledge/concepts/concept-textile-trade-indo-roman-monopoly.md")
]

def main():
    print("=" * 75)
    print("🧵 ANCIENT TAMIL TEXTILES, SILK WEAVING & DYEING CHEMISTRY HARVESTER")
    print("=" * 75)

    # 1. Generate Canonical Markdown Files in moolam-chronicles
    print("\n[Phase 1] Writing Canonical Markdown Dossiers...")
    for d in DOSSIERS:
        target_dir = os.path.join(MOOLAM_KNOWLEDGE, d["category"])
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, d["file"])
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        print(f"  ✓ Written: knowledge/{d['category']}/{d['file']}")

    # 2. Connect to PostgreSQL
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # 3. Upsert Lore Nodes
    print("\n[Phase 2] Upserting Lore Nodes into PostgreSQL...")
    total_nodes_upserted = 0
    for d in DOSSIERS:
        cur.execute("""
            INSERT INTO lore_nodes (
                slug, node_type, name_en, name_ta, era,
                year_start, year_end, thinai, summary_en, summary_ta,
                properties, sources
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
                properties = EXCLUDED.properties,
                sources = EXCLUDED.sources;
        """, (
            d["slug"],
            d["node_type"],
            d["name_en"],
            d["name_ta"],
            d["era"],
            d["year_start"],
            d["year_end"],
            d["thinai"],
            d["summary_en"],
            d["summary_ta"],
            json.dumps({"category": d["category"], "canonical_file": d["file"]}),
            [f"knowledge/{d['category']}/{d['file']}"]
        ))
        total_nodes_upserted += 1
        print(f"  ✓ [{d['node_type'].upper()}] {d['slug']} -> {d['name_en'][:45]}...")

    conn.commit()
    print(f"Phase 2 complete: {total_nodes_upserted} lore nodes upserted.")

    # 4. Upsert Lore Edges
    print("\n[Phase 3] Upserting Lore Edges into PostgreSQL...")
    edges_inserted = 0
    for edge in EDGES:
        src, rel, tgt, layer, era, desc, evidence = edge
        cur.execute("""
            SELECT 1 FROM lore_edges 
            WHERE source_slug = %s AND relation_type = %s AND target_slug = %s;
        """, (src, rel, tgt))
        if cur.fetchone():
            continue

        cur.execute("""
            INSERT INTO lore_edges (
                id, source_slug, relation_type, target_slug,
                layer, era, description, evidence_source
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            );
        """, (
            str(uuid.uuid4()), src, rel, tgt, layer, era, desc, evidence
        ))
        edges_inserted += 1
        print(f"  ✓ Linked: ({src}) --[{rel}]--> ({tgt})")

    conn.commit()
    print(f"Phase 3 complete: {edges_inserted} new lore edges inserted.")

    # 5. Generate Dense Vector Embeddings into rag_chunks
    print("\n[Phase 4] Generating 1024-dim BGE-M3 Embeddings into rag_chunks...")
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
                f"shelf-{d['category']}",
                ch["language"],
                ch["title"],
                ch["content"],
                f"knowledge/{d['category']}/{d['file']}",
                emb_str
            ))
            total_chunks += 1
            print(f"  ✓ Embedded ({ch['language']}): {ch['title'][:55]}...")

    conn.commit()
    print(f"Phase 4 complete: {total_chunks} dense BGE-M3 chunks embedded into rag_chunks.")

    # 6. Corpus Stats Summary
    cur.execute("SELECT COUNT(*) FROM lore_nodes;")
    node_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM lore_edges;")
    edge_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM rag_chunks;")
    chunk_count = cur.fetchone()[0]

    print("\n" + "=" * 70)
    print("📊 POST-HARVEST CORPUS TOTALS (PostgreSQL:55432):")
    print(f"   • Total Lore Nodes : {node_count:,}")
    print(f"   • Total Lore Edges : {edge_count:,}")
    print(f"   • Total RAG Chunks : {chunk_count:,}")
    print("=" * 70)

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
