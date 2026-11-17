#!/usr/bin/env python3
"""
Harvester: Batch 44 - Ancient Tamil Bull-Taming Sports, Native Cattle Breeds & Mullai Pastoral Heritage
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
        "slug": "text-mullaikkali-bridal-bull-contest-convention-and-ayar-cowherd-idiom",
        "category": "text",
        "file": "text-mullaikkali-bridal-bull-contest-convention-and-ayar-cowherd-idiom.md",
        "name_en": "Mullaikkali Poetics: The Bull-Embracing Bridal Contest as Literary Convention & Ayar Cowherd Idiom",
        "name_ta": "முல்லைக்கலியின் கவிதை மரபு: ஏறுதழுவுதல் மணக்கோலச் சிறப்பும் ஆயர் இடைச்சொல் வழக்கும்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "A poetics-level reading of how the Kalittokai Mullaikkali section turns bull-embracing into a formal marriage-eligibility convention, voiced through cowherd speakers, and of the herding vocabulary (aanirai, kovalar, patti, thimil) that the Mullai tract's poems share with Mullaippattu and the Aycciyar Kuravai.",
        "summary_ta": "கலித்தொகையின் முல்லைக்கலிப் பகுதி ஏறுதழுவுதலை ஒரு மணமுறைச் சடங்காக வகைப்படுத்தும் விதத்தையும், ஆநிரை, கோவலர், பட்டி, திமில் எனும் இடையர் சொல்வழக்கு முல்லைப்பாட்டு மற்றும் ஆய்ச்சியர் குரவையுடன் பொதுவாக இருப்பதையும் ஆராயும் இலக்கிய மரபு ஆய்வு.",
        "sources": [
            "Kalittokai (Mullaikkali)",
            "Mullaippattu",
            "Silappadikaram (Aycciyar Kuravai)",
            "Tolkappiyam (Porulathikaram)"
        ],
        "content": r"""# Mullaikkali Poetics: Bull-Embracing as a Bridal Convention

The *Mullaikkali* division of **Kalittokai** is the densest classical witness to
**eru thazhuvuthal** ("bull-embracing"), but its interest is literary as much as
documentary: the sport appears there as a *convention* (marapu), not a report.

**How the convention works in the poems**
- The speakers are pastoral types — the cowherd youth, the *aycciyar* (herdswomen),
  the companion — not a narrating poet. Boasting, teasing and refusal are staged as
  dialogue in the *kali* metre, whose long rhythmic lines suit a crowd scene.
- Marriage is made conditional on the bull: the herd-girl's hand is won by the youth
  who closes with the stud bull, and the man who shrinks back is mocked. This makes
  the arena a **qualifying rite** for adulthood and alliance inside the Mullai tract's
  own value system.
- The bull is described admiringly, not as an enemy — its **thimil** (dorsal hump),
  horn spread and dust-cloud charge are the poem's ornament.

**Shared pastoral idiom**

The same lexicon recurs across the Mullai corpus: *aanirai* (cattle herd), *kovalar*
and *ayar* (cowherds), *patti* (the night pen or herd camp), *kaanam* (the dry
pasture woodland), *kuzhal* (the herder's flute). **Mullaippattu** supplies the
landscape, and the *Aycciyar Kuravai* of **Silappadikaram** the herdswomen's round
dance, so the bull contest sits inside a wider poetic economy of cattle, waiting and
return rather than standing alone. Verse numbering is deliberately omitted here:
editions differ, and the convention — not any single line — is what is attested.
"""
    },
    {
        "slug": "concept-indus-seal-and-rock-art-bull-taming-scholarly-parallels",
        "category": "concept",
        "file": "concept-indus-seal-and-rock-art-bull-taming-scholarly-parallels.md",
        "name_en": "Indus Seal & Rock-Art Bull-Taming Parallels: A Cautious Scholarly Comparison",
        "name_ta": "சிந்து முத்திரைகளும் பாறை ஓவியங்களும்: காளை அடக்குதல் ஒப்பீட்டு ஆய்வின் எச்சரிக்கை",
        "era": "Bronze Age to Iron Age",
        "year_start": -2600,
        "year_end": -300,
        "thinai": "mullai",
        "summary_en": "A survey of the comparison scholars have drawn between Indus-valley seals and sealings showing men grappling or being tossed by bulls, Minoan bull-leaping, South Indian rock paintings of cattle and herders, and historic Tamil bull-embracing — together with the reasons that comparison cannot be read as demonstrated continuity.",
        "summary_ta": "சிந்துவெளி முத்திரைகளில் காணப்படும் காளையுடன் மோதும் மனித உருவங்கள், மினோவன் காளைத் தாண்டல், தென்னிந்திய பாறை ஓவியங்களின் கால்நடைக் காட்சிகள், தமிழ் ஏறுதழுவுதல் ஆகியவற்றை அறிஞர்கள் ஒப்பிட்ட விதமும், அதை தொடர்ச்சியாகக் கொள்ள முடியாத காரணங்களும்.",
        "sources": [
            "Marshall, Mohenjo-daro and the Indus Civilization",
            "Archaeological Survey of India reports on Indus seals",
            "Rock art surveys of the Nilgiris and northern Tamil Nadu",
            "Journal of the Royal Asiatic Society"
        ],
        "content": r"""# Indus Seals, Rock Art & Bull-Taming: What the Comparison Can and Cannot Carry

**The comparison as usually stated**

A small number of Indus-civilisation seals and sealings show human figures in violent
contact with a horned bovine — men apparently vaulting, grappling, or being tossed on
the horns, sometimes with several figures around one animal. Writers on the Indus
corpus have repeatedly noted the resemblance to **Minoan bull-leaping**
(*taurokathapsia*) from Crete and, in Indian discussion, to living Tamil
**eru thazhuvuthal / manju-virattu**. Zebu bulls with high humps and long horns are
also among the most carefully rendered animals on Indus seals, which makes bovine
prestige in that culture hard to doubt even where the scenes are ambiguous.

Rock paintings and petroglyph groups in the Nilgiri hills and northern Tamil Nadu add
humped cattle, herds and figures with sticks, and are regularly cited in the same
breath.

**Why caution is required**
- The seal scenes are tiny, worn and few; whether they show sport, hunting, myth or a
  ritual killing is **not settled**, and several readings have been proposed.
- Rock-art panels in South India are rarely securely dated; most cattle scenes are
  more plausibly herding or raiding imagery than arena sport.
- Between the Indus material and the Sangam-era Tamil evidence lie many centuries with
  no connecting documentation.

The honest formulation: bull-centred ritual and display are **widely attested across
Bronze Age and later agro-pastoral societies**, and Tamil bull-embracing is one
historically documented member of that family — not a proven descendant of any
specific earlier practice.
"""
    },
    {
        "slug": "concept-umblachery-and-bargur-native-breed-morphology-and-draught-aptitude",
        "category": "concept",
        "file": "concept-umblachery-and-bargur-native-breed-morphology-and-draught-aptitude.md",
        "name_en": "Umblachery & Bargur Breed Morphology: Delta Ploughing Cattle and Hill-Forest Trotters",
        "name_ta": "உம்பளச்சேரி, பர்கூர் இனக் கால்நடைகளின் உடலமைப்பு: டெல்டா உழவு மாடுகளும் மலைக்காட்டு ஓட்ட மாடுகளும்",
        "era": "Medieval to Modern Era",
        "year_start": 900,
        "year_end": 2025,
        "thinai": "mullai",
        "summary_en": "Comparative description of two lesser-known Tamil Bos indicus breeds: the Umblachery or 'mottai madu' of the Cauvery delta, dehorned and short-legged for puddled paddy ploughing, and the brown-and-white Bargur of the Erode hill forests, bred by hill herders for speed, trotting endurance and sure footing.",
        "summary_ta": "தமிழ்நாட்டின் இரு சிறிய நாட்டு இனங்கள்: காவிரி டெல்டாவின் சேற்று வயல் உழவுக்கேற்ற, கொம்பு நறுக்கப்பட்ட 'மொட்டை மாடு' எனும் உம்பளச்சேரி; ஈரோடு மலைக்காடுகளில் வேகத்திற்கும் தாங்கும் ஓட்டத்திற்கும் வளர்க்கப்படும் பர்கூர் பழுப்பு-வெள்ளை மாடு.",
        "sources": [
            "ICAR National Bureau of Animal Genetic Resources breed descriptors",
            "Tamil Nadu Veterinary and Animal Sciences University breed surveys",
            "Madras District Gazetteers (Tanjore; Coimbatore)",
            "Indian Journal of Animal Sciences"
        ],
        "content": r"""# Umblachery & Bargur: Two Working Breeds, Two Terrains

Both are small-to-medium **Bos indicus** (zebu) draught breeds, and in both cases the
morphology is legible as an answer to the ground the animal must work.

**Umblachery (Cauvery delta — Nagapattinam, Thiruvarur, Thanjavur)**
- Calves are commonly born a reddish-brown coat that greys out with age; adults are
  grey to dark grey in bulls, lighter in cows, with characteristic **white markings on
  the face, the lower legs ("socks") and the tail switch**.
- Short-legged and compact with a moderate hump — a low centre of gravity that suits
  **puddled, waterlogged paddy fields**, where tall cattle bog down.
- Herders traditionally **trim or remove the horns of working males** while young; the
  local name *mottai madu* ("hornless beast") records the practice, which is kept up
  to make delta plough-bulls easier to yoke and handle.

**Bargur (Bargur hills, Anthiyur region, Erode district)**
- Distinctively **brown with white patches**; compact, tight-muscled, with horns set
  close together and inclined backwards.
- Reared by hill herding families who graze the animals in **forest tracts rather than
  on stall feed**, producing hard hooves and alert temperament.
- Valued for **speed and trotting endurance** — historically for fast cart work and
  racing-type contests, and for moving loads on broken hill paths.

Against these, the Kangayam of the Kongu plains is heavier-boned with a wide outward
horn sweep for sustained draught, and the small, agile Pulikulam of the Madurai–
Sivaganga dry tract is kept in large migratory herds and favoured in the arena.
Breed-society and department descriptors agree on these traits; coat and horn detail
varies between individual herds.
"""
    },
    {
        "slug": "concept-korangadu-kaaval-grazing-commons-and-silvopasture-tenure",
        "category": "concept",
        "file": "concept-korangadu-kaaval-grazing-commons-and-silvopasture-tenure.md",
        "name_en": "Korangadu Silvopasture & Kaaval Grazing Tenure of the Kangayam Tract",
        "name_ta": "கொறங்காடு மேய்ச்சல் நிலமும் காவல் உரிமை முறையும்: காங்கேயம் பகுதி",
        "era": "Medieval to Modern Era",
        "year_start": 1000,
        "year_end": 2025,
        "thinai": "mullai",
        "summary_en": "The korangadu grazing system of the dry Kangayam tract: enclosed private pasture plots combining a perennial grass sward, scattered Acacia leucophloea shade trees and a living thorn fence, grazed in rotation and let out seasonally to migratory herds under customary kaaval watch-and-penning arrangements.",
        "summary_ta": "காங்கேயம் வறண்ட பகுதியின் கொறங்காடு முறை: பல்லாண்டு புல், வெள்வேல் மரங்கள், உயிர் வேலி ஆகியவை இணைந்த தனியார் மேய்ச்சல் நிலங்கள்; சுழற்சி முறையில் மேய்த்து, பருவத்திற்கேற்ப இடம்பெயர் மாட்டுக் கூட்டங்களுக்கு காவல் ஒப்பந்தத்தின் கீழ் வாடகைக்கு விடப்படும்.",
        "sources": [
            "Madras District Gazetteer (Coimbatore)",
            "Indian Grassland and Fodder Research Institute surveys",
            "Range Management and Agroforestry",
            "Tamil Nadu Agricultural University dry-farming bulletins"
        ],
        "content": r"""# Korangadu: Enclosed Dry Pasture as Engineered Commons

The **korangadu** of the Kangayam tract (Tiruppur–Erode–Karur, roughly 600–700 mm of
erratic annual rain) is not waste ground but a deliberately maintained
**silvopasture** — the pastoral counterpart of a tank-irrigated field.

**The three-layer design**
1. **Sward layer** — a perennial bunch grass, chiefly *kolukattai pul*
   (*Cenchrus ciliaris*), which cures standing into a palatable dry hay and regrows
   from the crown after rain, so the plot carries stock through the dry months.
2. **Tree layer** — scattered **velvel / *Acacia leucophloea***, giving shade, pods
   as supplementary fodder, leaf litter and lopped fuel without closing the canopy
   over the grass.
3. **Fence layer** — a living thorn hedge, typically ***Dichrostachys cinerea***
   (*vedathalai*), which excludes stray stock and makes the plot defensible without
   purchased fencing.

**Tenure and the kaaval relation**

Plots are privately held but pastorally shared: owners **let grazing by the season**
to herders moving Kangayam and Pulikulam herds, the arrangement often settled in
fodder, cash, or the manure and urine the penned herd leaves overnight — dung being
the real currency in a tract with no canal. *Kaaval* (watch) names both the duty of
guarding a herd on another's land and the customary right to graze it, and disputes
over boundaries, watering turns and stray cattle were traditionally handled by village
assemblies rather than courts. Rotation is the discipline that keeps the system
standing: plots are rested so the grass can seed, and overstocking is what degrades a
korangadu, not drought.
"""
    },
    {
        "slug": "technology-vadivasal-arena-chute-and-kalam-enclosure-layout",
        "category": "technology",
        "file": "technology-vadivasal-arena-chute-and-kalam-enclosure-layout.md",
        "name_en": "Vadivasal Release Chute & Kalam Arena Layout: Crowd and Animal Flow Engineering",
        "name_ta": "வாடிவாசல் விடுதலைப் பாதையும் களத்தின் அமைப்பும்: கூட்டமும் மாடும் நகரும் வழிமுறை",
        "era": "Medieval to Modern Era",
        "year_start": 1200,
        "year_end": 2025,
        "thinai": "mullai",
        "summary_en": "The built geometry of the bull-embracing ground: a holding pen feeding a narrow masonry vadivasal gateway that releases one bull at a time into the open kalam, with a marked run beyond the gate, flanking barricades that separate tamers from spectators, and exit lanes that return the animal to its owner.",
        "summary_ta": "ஏறுதழுவுதல் களத்தின் கட்டமைப்பு: மாடுகள் காத்திருக்கும் தொழுவத்திலிருந்து ஒவ்வொரு காளையையும் தனித்தனியே வெளியேற்றும் குறுகிய வாடிவாசல் வாயில், அதற்கு அப்பால் அளவு குறிக்கப்பட்ட களம், தடுப்பு வேலிகள், காளை திரும்பிச் செல்லும் வெளியேறு வழி.",
        "sources": [
            "Tamil Nadu district collectorate jallikattu conduct notifications",
            "Madras District Gazetteer (Madura)",
            "Tamil Nadu Regulation of Jallikattu Act, 2009",
            "Field descriptions of Madurai-district arenas"
        ],
        "content": r"""# Vadivasal & Kalam: The Arena as a Flow-Control Device

Every element of a bull-embracing ground exists to solve one problem: let a powerful
animal run freely while keeping the number of humans in contact with it at any moment
down to one or a few.

**The chute**

The **vadivasal** is the narrow gateway — in older village grounds a masonry arch with
thick flanking walls, elsewhere a timber or steel-framed equivalent — through which
bulls enter the arena. Behind it sits a **holding pen / thozhuvam** where animals wait
with their owners. The chute is deliberately **just wide enough for one bull**: it
serialises the release, denies the animal a running start into a crowd, and gives
officials a single controllable choke point. A bull that balks is not forced through
at speed.

**The ground**

Beyond the gate lies the **kalam**, a cleared, loosened-earth stretch. Modern
district-notified layouts mark a **defined zone immediately past the vadivasal within
which a tamer may attempt the hump**, with waiting participants restrained behind a
line until the bull clears the gate; the exact marked distances, galleries and
barricade counts are set by each year's collectorate notification rather than by any
single fixed standard.

- **Double barricading** separates the active ground from spectators, with a gap so a
  bull colliding with the inner rail cannot reach the crowd.
- **Exit lanes** at the far end funnel the bull out to its owner, so animals are never
  turned back through the arriving traffic.
- Raised spectator ground, veterinary inspection bays and ambulance access complete the
  modern plan.

Older accounts describe far simpler versions: a village street mouth, a temple
forecourt, or a threshing floor pressed into service.
"""
    },
    {
        "slug": "technology-kaalai-conditioning-regimen-tank-swimming-and-horn-dressing",
        "category": "technology",
        "file": "technology-kaalai-conditioning-regimen-tank-swimming-and-horn-dressing.md",
        "name_en": "Kaalai Conditioning: Tank Swimming, Sand Runs, Feed Regimens & Horn Dressing",
        "name_ta": "காளைப் பயிற்சி முறை: குளத்தில் நீந்தல், மணல் ஓட்டம், தீனி முறை, கொம்பு பரிமாற்றம்",
        "era": "Medieval to Modern Era",
        "year_start": 1200,
        "year_end": 2025,
        "thinai": "mullai",
        "summary_en": "The husbandry craft that produces an arena- or draught-fit bull: graded swimming in village tanks for low-impact stamina, running on loosened sand, a concentrate ration built on cottonseed and horse gram, oil massage, hoof paring, and the filing, oiling and capping of horns.",
        "summary_ta": "களத்திற்கும் உழவுக்கும் தகுந்த காளையை உருவாக்கும் பராமரிப்புக் கலை: ஊர்க்குளத்தில் படிப்படியாக நீந்தச் செய்தல், தளர்ந்த மணலில் ஓட்டப் பயிற்சி, பருத்திக்கொட்டை-கொள்ளு தீனி, எண்ணெய் தேய்த்தல், குளம்பு சீர்செய்தல், கொம்பு அராவி எண்ணெய் தடவுதல்.",
        "sources": [
            "Ethnographic accounts of jallikattu bull rearing, Madurai region",
            "Tamil Nadu Veterinary and Animal Sciences University extension notes",
            "Madras District Gazetteer (Madura)",
            "Indian Journal of Traditional Knowledge"
        ],
        "content": r"""# Conditioning a Kaalai: Stamina Without Pounding

Rearing a stud bull for display or heavy draught is a slow craft, and the practices
below are recorded mainly **ethnographically — from herding families and extension
surveys — rather than from excavation**, so they describe living custom of the last
century or two with older roots implied, not proven.

**Work and movement**
- **Tank swimming** is the signature method: the bull is walked into a village tank or
  irrigation channel and made to swim short, repeated stretches. Water loads the
  shoulder and hump musculature while sparing joints — low-impact conditioning for an
  animal too heavy for sustained road running.
- **Sand running** over loosened earth builds propulsion and strengthens the hoof and
  pastern.
- Daily walking with a handler keeps the animal accustomed to noise and crowds.

**Feeding**

Grazing on dry pasture is topped up with a concentrate mix drawn from what the tract
grows: **paruthi kottai (cottonseed) and cottonseed cake, kollu (horse gram) — often
soaked or boiled — green gram, sesame or groundnut cake, millet gruel, coconut, and
jaggery or ghee as a finisher**. Mineral licks and salt are offered; proportions vary
by household and are not standardised.

**Body and horn care**
- **Oil massage** of the neck, hump and limbs after work, often with sesame oil.
- **Hoof paring** to keep the wall even, important for animals on hard ground.
- **Horn dressing**: horns are scraped and filed smooth, oiled or polished, sometimes
  painted, and the tips fitted with **brass or metal caps** — cosmetic, but also
  blunting the point. Horn sharpening, and any use of irritants, liquor or goads on an
  animal, are prohibited under current regulated conduct rules.
"""
    },
    {
        "slug": "artifact-kayiru-halters-bell-metal-mani-collars-and-horn-brass-caps",
        "category": "artifact",
        "file": "artifact-kayiru-halters-bell-metal-mani-collars-and-horn-brass-caps.md",
        "name_en": "Cattle Gear: Fibre Kayiru Halters, Bell-Metal Mani Collars, Horn Brass Caps & Cattle-Raid Nadukal",
        "name_ta": "மாட்டுச் சாமான்கள்: நார்க் கயிறு தலைக்கட்டு, வெண்கல மணிப் பட்டை, கொம்புப் பித்தளை உறை, ஆநிரைக் கல்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "mullai",
        "summary_en": "The material kit of Tamil cattle keeping: coir, agave and palmyra-fibre ropes for nose lines, halters and tethers; cast bell-metal neck bells on fibre or leather collars; brass horn caps and ornamental tassels; and the hero-stones and memorial slabs on which cattle, herders and raid scenes appear.",
        "summary_ta": "தமிழ் மாடு வளர்ப்பின் பொருள் தொகுப்பு: தென்னை நார், கற்றாழை நார், பனைநார் கயிறுகள் — மூக்கணாங்கயிறு, தலைக்கட்டு, கட்டுக்கயிறு; வெண்கலத்தில் வார்த்த கழுத்து மணிகள்; பித்தளைக் கொம்பு உறைகள்; ஆநிரை காட்சிகள் பொறித்த நடுகற்கள்.",
        "sources": [
            "Madras District Gazetteers",
            "Government Museum Chennai, metalware and hero-stone collections",
            "Archaeological Survey of India hero-stone surveys, northern Tamil Nadu",
            "Journal of Ethnobiology"
        ],
        "content": r"""# Ropes, Bells, Horn Caps & Memorial Stones

**Kayiru — the ropes**

Cattle work is rope work. Herders twist cordage from whatever fibre the tract yields:
**coir** from coconut husk in the deltas and coast, **agave / sisal** and **palmyra
leaf-base fibre** inland. Distinct forms do distinct jobs — the thin *mookkanaan
kayiru* (nose line) through the nasal septum for a worked bullock, a braided head
halter, a heavier tether run to a ground peg at the night pen, and the soft neck lead
by which a show bull is walked. Ropes are smoked, oiled or soaked to keep them supple
and resist rot.

**Mani — the bells**

Neck bells are cast in **bell metal (a high-tin copper–tin bronze)** or worked in
brass and iron sheet, hung on a fibre or leather collar. The point is acoustic
tracking: a herd dispersed in thorn pasture is located by ear, and experienced
herders claim to know individual animals by the pitch of their bell. Larger
deep-toned bells typically go to lead animals and temple bulls.

**Ornament**

Brass or metal **horn caps** protect and blunt the tips; coloured cord, tassels,
bead strings, and cowrie or metal-disc neck bands are added for Mattu Pongal and
festival processions.

**Stones**

Among the **nadukal** (hero-stones) and memorial slabs of northern and western Tamil
Nadu, a subset carries cattle, herders, and armed figures in what are generally read
as **cattle-raid and herd-defence scenes**; tiger and bull motifs recur on memorial
and boundary stones. The association with cattle conflict is standard in the
epigraphic literature, but individual panels are often worn and their readings
remain interpretive.
"""
    },
    {
        "slug": "institution-kovil-kaalai-temple-bull-endowment-and-idaiyar-herder-assembly",
        "category": "institution",
        "file": "institution-kovil-kaalai-temple-bull-endowment-and-idaiyar-herder-assembly.md",
        "name_en": "Kovil Kaalai Temple-Bull Endowments & the Idaiyar Herder Assembly",
        "name_ta": "கோயில் காளை அறக்கட்டளையும் இடையர் ஊர்க்கூட்ட அமைப்பும்",
        "era": "Medieval to Modern Era",
        "year_start": 850,
        "year_end": 2025,
        "thinai": "mullai",
        "summary_en": "The twin institutions that reproduced native cattle: the temple bull (kovil kaalai), dedicated to a shrine, exempt from plough and sale and serving as the village's free-ranging breeding sire under endowed maintenance; and the Idaiyar / Ayar herding community's own assembly, which allotted grazing, timed migrations and arbitrated cattle disputes.",
        "summary_ta": "நாட்டு மாட்டினத்தைக் காத்த இரு நிறுவனங்கள்: கோயிலுக்கு நேர்ந்து, உழவுக்கும் விற்பனைக்கும் விலக்கப்பட்டு, ஊரின் இனவிருத்திக் காளையாகத் திரிந்த கோயில் காளை; மேய்ச்சல் பகிர்வு, இடப்பெயர்வு காலம், மாட்டுத் தகராறு தீர்வு ஆகியவற்றை நிர்வகித்த இடையர் ஊர்க்கூட்டம்.",
        "sources": [
            "South Indian Inscriptions volumes on temple endowments",
            "Madras District Gazetteers",
            "Epigraphia Indica",
            "Studies in medieval South Indian temple economy"
        ],
        "content": r"""# Kovil Kaalai & the Herder Assembly: Who Kept the Breed

Native cattle did not persist by accident. Two institutions, one religious and one
communal, together carried the genetics and the grazing.

**The temple bull**

A **kovil kaalai** is a bull dedicated to a temple — often fulfilling a vow, or given
with an endowment for its upkeep. Once dedicated it is withdrawn from ordinary
economy: **not yoked, not sold, not slaughtered**. It roams the village and its
pastures freely and serves as the **common breeding sire**, so a single carefully
chosen animal shapes a locality's calves for years. Temple endowment records from the
medieval South routinely provide land, grain or cash for maintaining animals and
attendants attached to a shrine, which is the mechanism by which such a bull is fed
when no owner profits from it. Nandi worship and the Saiva association of the bull
give the custom its sanction; selection for the role rewarded conformation and
temperament, not milk.

**The Idaiyar / Ayar assembly**

The pastoral community — **Ayar** in Sangam usage, **Idaiyar / Konar** in later
Tamil — organised itself around the herd rather than the field. Its collective
functions were practical:
- allotting and rotating **grazing** on common and leased land, and fixing watering
  turns at tanks;
- timing **seasonal migration** of herds between home pasture and distant stubble or
  forest grazing, and negotiating overnight **penning-for-manure** agreements with
  cultivators;
- adjudicating **strays, cattle theft, stud fees and festival precedence**, including
  which animals went to the arena.

Where kings issued charters over pasture, these assemblies were the bodies that
actually enforced them on the ground.
"""
    },
    {
        "slug": "concept-regulated-manju-virattu-rulebook-and-animal-welfare-contestation",
        "category": "concept",
        "file": "concept-regulated-manju-virattu-rulebook-and-animal-welfare-contestation.md",
        "name_en": "The Regulated Rulebook: Modern Conduct Codes for Bull-Embracing & Its Welfare Litigation",
        "name_ta": "ஒழுங்குபடுத்தப்பட்ட விதிமுறைகள்: நவீன ஏறுதழுவுதல் நடத்தை நெறியும் விலங்கு நலன் வழக்குகளும்",
        "era": "Modern Era",
        "year_start": 1900,
        "year_end": 2025,
        "thinai": "mullai",
        "summary_en": "How the sport is governed today: compulsory veterinary fitness checks and registration, release of one bull at a time, a single tamer attempting the hump within a marked zone, bans on tail-pulling, horn sharpening, goads and intoxicants — set against the animal-welfare litigation that produced a national ban, a Tamil Nadu amendment, and a later constitutional ruling.",
        "summary_ta": "இன்றைய ஒழுங்குமுறை: கட்டாய கால்நடை மருத்துவப் பரிசோதனை, பதிவு, ஒரு நேரத்தில் ஒரு காளை, குறித்த எல்லைக்குள் ஒருவர் மட்டுமே திமிலைப் பிடித்தல், வால் இழுத்தல்-கொம்பு கூர்மைப்படுத்தல்-போதை ஊட்டம் தடை; இதனுடன் தேசிய தடை, தமிழ்நாடு திருத்தச் சட்டம், பின்னர் வந்த அரசியலமைப்பு அமர்வு தீர்ப்பு.",
        "sources": [
            "Tamil Nadu Regulation of Jallikattu Act, 2009",
            "Animal Welfare Board of India v. A. Nagaraja (Supreme Court of India, 2014)",
            "Prevention of Cruelty to Animals (Tamil Nadu Amendment) Act, 2017",
            "District collectorate conduct notifications"
        ],
        "content": r"""# The Regulated Form and Its Contestation

**What the conduct rules require**

Modern events run under state legislation plus a district collectorate notification
issued for each occasion. Recurring requirements include:

- **Registration and veterinary fitness screening** of every bull before entry, with
  animals rejected on injury, illness or signs of drugging; registration and fitness
  checks on tamers.
- **One bull released at a time** through the vadivasal, and an attempt made by a
  single tamer within a marked zone — not a group pile-on.
- The hold must be on the **thimil (hump)** only, until the animal clears the marked
  distance. **Tail-twisting or pulling, holding horns or legs, mounting and striking
  are offences**, as are **horn sharpening, goads, irritants in the eyes or nose, and
  alcohol or stimulants**.
- The animal is **not to be killed, maimed or restrained to be overpowered** — it must
  be free to run and exit; owners reclaim their bull at the far end.
- Double barricades, medical cover, spectator exclusion zones and observer teams.

**The legal and welfare argument — both sides**

Animal-welfare petitioners argue that fear-driven flight through a crowd, injuries to
bulls and humans, and pre-event handling abuses make the event inherently cruel; the
**Supreme Court accepted that case in 2014** and the practice was barred nationally.
Tamil Nadu's position — pressed by very large public protests in January 2017 — was
that the event is integral to the region's culture and is the economic reason native
stud bulls are kept at all, and the state **amended the Prevention of Cruelty to
Animals Act in 2017** to permit it under regulation. A **Constitution Bench upheld that
amendment in 2023**. The welfare objection has not been withdrawn, and compliance
varies by venue; this dossier records the dispute rather than settling it.
"""
    },
    {
        "slug": "place-alanganallur-ancient-vaigai-eru-thazhuvuthal-haven",
        "category": "place",
        "file": "place-alanganallur-ancient-vaigai-eru-thazhuvuthal-haven.md",
        "name_en": "Alanganallur: Vaigai-Basin Eru-Thazhuvuthal Haven of the Madurai Pastoral Belt",
        "name_ta": "அலங்காநல்லூர்: வைகைச் சமவெளியின் ஏறுதழுவுதல் தலம்",
        "era": "Medieval to Modern Era",
        "year_start": 1200,
        "year_end": 2025,
        "thinai": "mullai-marutham",
        "summary_en": "Village on the Vaigai plain north of Madurai (approx. 10.0460 N, 78.0970 E) whose Mattu Pongal bull-embracing event is the best known in Tamil Nadu, sitting at the junction of marutham wet cultivation along the Vaigai and the mullai dry pasture that supplies its Pulikulam and Kangayam bulls.",
        "summary_ta": "மதுரைக்கு வடக்கே வைகைச் சமவெளியில் அமைந்த ஊர் (ஏறத்தாழ 10.0460 வ., 78.0970 கி.). மாட்டுப்பொங்கல் ஏறுதழுவுதலால் தமிழ்நாட்டில் மிகவும் பெயர்பெற்றது; வைகையின் மருத நிலத்திற்கும் புலிக்குளம்-காங்கேயம் காளைகளை அளிக்கும் முல்லை மேய்ச்சல் நிலத்திற்கும் இடையே உள்ளது.",
        "sources": [
            "Madras District Gazetteer (Madura)",
            "Tamil Nadu district collectorate jallikattu notifications, Madurai",
            "Census of India village directories, Madurai district",
            "Regional ethnographic accounts of Mattu Pongal observance"
        ],
        "content": r"""# Alanganallur: Where the Vaigai Pasture Meets the Arena

**Setting**

Alanganallur lies on the **Vaigai plain a short distance north of Madurai**
(approximately **10.0460 N, 78.0970 E**). Its landscape is a genuine seam between two
*thinai*: **marutham** — irrigated paddy and garden land along the Vaigai and its
channels and tanks — and **mullai**, the dry thorn pasture and tank-fed grazing of the
surrounding uplands. That pairing matters, because an arena needs both the grain and
fodder surplus of wet country and the pasture that can carry uncultivated stud bulls.

**Why this village**

Alanganallur's **Mattu Pongal** bull-embracing event is the most widely known in Tamil
Nadu, drawing bulls and tamers from across the southern districts and, in recent
decades, national and international press. In Madurai district it anchors a **short
circuit of events held on successive days around Pongal**, alongside Avaniyapuram and
Palamedu — a sequence that lets the same animals, owners and crowds move between
grounds in one festival week.

**What the village supplies**
- Herds of **Pulikulam** stock from the Madurai–Sivaganga dry tract, with **Kangayam**
  and other native bulls brought in by owners.
- A permanent **vadivasal** and prepared ground, plus the lanes and temple forecourt
  the event uses.
- Households whose standing as bull-keepers is itself the prize — the reputation of an
  animal that is never caught travels further than any purse.

The village's fame is modern in reach but local in root: the practice here is reported
as long-standing custom tied to the temple and the Pongal calendar, and claims to any
precise founding date should be treated as tradition rather than record.
"""
    }
]

EDGES = [
    [
        "text-mullaikkali-bridal-bull-contest-convention-and-ayar-cowherd-idiom",
        "attests",
        "place-alanganallur-ancient-vaigai-eru-thazhuvuthal-haven",
        "material_culture",
        "Sangam to Modern Era",
        "Mullaikkali poetics supply the classical convention that the Vaigai-basin arena villages still enact at Mattu Pongal.",
        "Kalittokai (Mullaikkali)"
    ],
    [
        "concept-indus-seal-and-rock-art-bull-taming-scholarly-parallels",
        "contextualizes",
        "text-mullaikkali-bridal-bull-contest-convention-and-ayar-cowherd-idiom",
        "material_culture",
        "Bronze Age to Sangam Era",
        "Scholarly comparison with Indus seals and rock art frames the Sangam bull-embracing convention within a wider agro-pastoral family, without demonstrating descent.",
        "Archaeological Survey of India reports on Indus seals"
    ],
    [
        "concept-korangadu-kaaval-grazing-commons-and-silvopasture-tenure",
        "sustains",
        "concept-umblachery-and-bargur-native-breed-morphology-and-draught-aptitude",
        "material_culture",
        "Medieval to Modern Era",
        "Enclosed dry pasture and seasonal kaaval grazing tenure are what make keeping unirrigated native draught herds viable.",
        "Madras District Gazetteer (Coimbatore)"
    ],
    [
        "institution-kovil-kaalai-temple-bull-endowment-and-idaiyar-herder-assembly",
        "governs",
        "concept-korangadu-kaaval-grazing-commons-and-silvopasture-tenure",
        "material_culture",
        "Medieval to Modern Era",
        "Herder assemblies allotted grazing turns, migration timing and penning agreements across korangadu pasture plots.",
        "South Indian Inscriptions volumes on temple endowments"
    ],
    [
        "institution-kovil-kaalai-temple-bull-endowment-and-idaiyar-herder-assembly",
        "reproduces",
        "concept-umblachery-and-bargur-native-breed-morphology-and-draught-aptitude",
        "material_culture",
        "Medieval to Modern Era",
        "Free-ranging endowed temple bulls acted as common breeding sires, fixing breed conformation within a locality.",
        "Epigraphia Indica"
    ],
    [
        "technology-kaalai-conditioning-regimen-tank-swimming-and-horn-dressing",
        "prepares",
        "concept-umblachery-and-bargur-native-breed-morphology-and-draught-aptitude",
        "material_culture",
        "Medieval to Modern Era",
        "Swimming, sand work, concentrate feeding and horn dressing convert breed potential into working or arena fitness.",
        "Tamil Nadu Veterinary and Animal Sciences University extension notes"
    ],
    [
        "artifact-kayiru-halters-bell-metal-mani-collars-and-horn-brass-caps",
        "equips",
        "technology-kaalai-conditioning-regimen-tank-swimming-and-horn-dressing",
        "material_culture",
        "Sangam to Modern Era",
        "Fibre nose lines, halters, tethers, bell collars and brass horn caps are the physical kit through which conditioning and handling are carried out.",
        "Government Museum Chennai, metalware and hero-stone collections"
    ],
    [
        "technology-vadivasal-arena-chute-and-kalam-enclosure-layout",
        "enables",
        "concept-regulated-manju-virattu-rulebook-and-animal-welfare-contestation",
        "material_culture",
        "Modern Era",
        "Serialised release through a single-bull chute and a marked run are the built preconditions the regulated conduct rules assume.",
        "Tamil Nadu Regulation of Jallikattu Act, 2009"
    ],
    [
        "place-alanganallur-ancient-vaigai-eru-thazhuvuthal-haven",
        "hosts",
        "technology-vadivasal-arena-chute-and-kalam-enclosure-layout",
        "material_culture",
        "Medieval to Modern Era",
        "The village maintains a permanent vadivasal and prepared kalam for its Mattu Pongal event.",
        "Tamil Nadu district collectorate jallikattu notifications, Madurai"
    ],
    [
        "concept-regulated-manju-virattu-rulebook-and-animal-welfare-contestation",
        "constrains",
        "artifact-kayiru-halters-bell-metal-mani-collars-and-horn-brass-caps",
        "material_culture",
        "Modern Era",
        "Conduct rules prohibit sharpened horns, goads and tail-holding, restricting which gear and handling practices are permitted at an event.",
        "Prevention of Cruelty to Animals (Tamil Nadu Amendment) Act, 2017"
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
