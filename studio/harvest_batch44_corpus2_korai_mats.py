#!/usr/bin/env python3
"""
Harvester: Batch 44 - Tamil Korai Sedge Mat Weaving, Pattamadai Silk-Grass Mats and Riverine Reed Craft
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
        "slug": "text-sangam-paai-and-nanal-reed-mat-bedding-references",
        "category": "text",
        "file": "text-sangam-paai-and-nanal-reed-mat-bedding-references.md",
        "name_en": "Sangam Poetic References to Woven Floor Mats (Paai) and Reed Bedding (Nanal)",
        "name_ta": "சங்கப் பாடல்களில் பாய் மற்றும் நாணல் படுக்கை பற்றிய குறிப்புகள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Classical Tamil poems repeatedly name the woven floor mat (paai, paay) and reed or grass bedding (nanal) as ordinary household furniture of herders, farmers and bards, offered to guests for sleeping and sitting; the verses describe use and texture but never identify a botanical species, so the link to korai sedge is inferential rather than proven.",
        "summary_ta": "பாய், நாணல் படுக்கை ஆகியவை ஆயர், உழவர், பாணர் குடிகளின் அன்றாட வீட்டுப் பொருளாகச் சங்கப் பாடல்களில் பலமுறை இடம்பெறுகின்றன; விருந்தினருக்கு விரித்துத் தரும் பாயின் மென்மையைப் பாடல்கள் சொல்கின்றன, ஆனால் எந்தப் புல் வகை என்பதை வரையறுக்கவில்லை.",
        "sources": [
            "Perumpanarruppadai",
            "Porunararruppadai",
            "Nedunalvadai",
            "Purananuru",
            "Tamil Lexicon (University of Madras)"
        ],
        "content": r"""# Sangam References to Woven Mats (Paai) and Reed Bedding (Nanal)

**What the corpus actually says.** The *arruppadai* ("guide-poems") that send a bard from one patron
to the next dwell on hospitality, and bedding is part of that inventory. In *Perumpanarruppadai* and
*Porunararruppadai* the traveller is given food, oil, and a mat or soft grass bedding spread on the
floor; *Nedunalvadai* uses bedding imagery for the sleepless heroine in the cold northern wind.
*Purananuru* uses the mat as a marker of plain living in contrast to courtly cushioning.

**Vocabulary.** Three words carry the sense: **paai / paay** (பாய்) — a plaited or woven mat;
**nanal** (நாணல்) — reed, the tall hollow riverside grasses; and **thazhai / thaimbu**-type words for
leaf and grass bedding. The *Tamil Lexicon* records *paai* for mats of palmyra leaf, screw-pine
(*thaazhai*), and sedge alike. The verb used is "to spread" (*viri*), which fits a pliable rolled mat
rather than a rigid screen.

**Honest limits.** No Sangam poem names *korai* sedge, gives a strand count, or locates a mat
workshop. Claims that the Pattamadai fine-mat tradition is two thousand years old rest on the general
antiquity of mat-making in the region, not on any verse. What the poems do establish is that woven
floor mats were commonplace, portable, and socially neutral in the early Tamil country.
"""
    },
    {
        "slug": "concept-cyperus-pangorei-korai-sedge-ecology-on-thamirabarani-banks",
        "category": "concept",
        "file": "concept-cyperus-pangorei-korai-sedge-ecology-on-thamirabarani-banks.md",
        "name_en": "Korai Sedge Ecology: Cyperus pangorei Beds on the Thamirabarani Floodplain",
        "name_ta": "தாமிரபரணிக் கரையோரக் கோரைப் புல் சூழலியல்",
        "era": "Ancient to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Korai is a marsh sedge with a three-angled (trigonous) stem, grown in waterlogged river-margin plots and old channel backwaters of the Thamirabarani; the plant is a perennial that regrows from rhizomes after cutting, is harvested as whole stalks several times a year, and yields longer, finer, more flexible culms when standing water is kept shallow and constant.",
        "summary_ta": "கோரை என்பது முக்கோண வடிவத் தண்டுடைய சதுப்பு நிலப் புல்; தாமிரபரணியின் கரையோர நீர் தேங்கும் நிலங்களிலும் பழைய ஆற்றுப் படுகைகளிலும் வளர்க்கப்படுகிறது. வேர்த்தண்டிலிருந்து மீண்டும் முளைக்கும் இது ஆண்டுக்குப் பல முறை அறுவடை செய்யப்படுகிறது; ஆழமற்ற நிலைத்த நீர் இருந்தால் நீண்ட, நுண்ணிய, நெகிழ்வான தண்டுகள் கிடைக்கும்.",
        "sources": [
            "Flora of the Presidency of Madras (Gamble)",
            "Madras District Gazetteer, Tinnevelly",
            "Journal of Ethnobiology",
            "Tamil Nadu Agricultural University extension bulletins"
        ],
        "content": r"""# Korai Sedge Ecology on the Thamirabarani Floodplain

**The plant.** *Korai* (கோரை) is not a grass but a sedge of the genus *Cyperus* — the mat species of
the southern Tamil country is usually cited as *Cyperus pangorei* Rottb. (listed in older floras under
*C. corymbosus*; the closely related *C. tegetum* is the mat sedge of eastern India). Sedges are told
from grasses by the stem: a *Cyperus* culm is solid and **three-angled in cross-section**, with no
swollen nodes. That triangular section is the whole basis of the craft — split along its angles, one
stalk yields two or three long ribbons of even width.

**How it is grown.** Korai is a cultivated wetland crop, not a gathered weed. Rhizome clumps are
planted into puddled, bunded plots on the river margin and kept under a few centimetres of standing
water; the Thamirabarani's perennial flow makes this possible in a district that is otherwise dry.
Being perennial, a planted bed is cut repeatedly over several years and regrows from the rhizome
rather than from seed.

**Quality factors.** Weavers judge a standing crop by stalk length, straightness and slenderness.
Deep or stagnant water gives coarse, pithy stalks; shallow, moving water gives the long thin culms
that split finest. Stalks are cut near the base, the flowering head discarded, and bundles graded by
length before splitting — the longest reserved for the finest mats.
"""
    },
    {
        "slug": "concept-korai-stalk-splitting-boiling-and-natural-dye-absorption",
        "category": "concept",
        "file": "concept-korai-stalk-splitting-boiling-and-natural-dye-absorption.md",
        "name_en": "Splitting, Boiling and Dyeing Korai Stalks: Softening and Colour Absorption",
        "name_ta": "கோரைத் தண்டு பிளத்தல், அவித்தல், சாயம் ஏற்றுதல்",
        "era": "Medieval to Modern Era",
        "year_start": 1000,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Cut korai stalks are split lengthwise by hand or knife-point into fine ribbons, boiled in water to soften the pith and open the fibre, then soaked in river water for several days before dyeing; the softened strands take colour readily, traditionally from indigo, turmeric and root reds, with alum-type mordants, though synthetic dyes replaced most natural recipes in the twentieth century.",
        "summary_ta": "அறுவடை செய்த கோரைத் தண்டுகள் நீளவாக்கில் கைகளாலோ கத்தி முனையாலோ நுண்ணிய இழைகளாகப் பிளக்கப்படுகின்றன; பின்பு நீரில் அவித்து உள்சோற்றை மென்மையாக்கி, ஆற்று நீரில் பல நாட்கள் ஊறவைத்த பின் சாயம் ஏற்றப்படுகிறது. பாரம்பரியமாக அவுரி, மஞ்சள், வேர்ச் சாயங்கள் பயன்பட்டன; இருபதாம் நூற்றாண்டில் பெரும்பாலும் செயற்கைச் சாயங்களே இடம்பெற்றன.",
        "sources": [
            "Madras District Gazetteer, Tinnevelly",
            "Census of India handicrafts monographs",
            "Journal of Ethnobiology",
            "All India Handicrafts Board survey reports"
        ],
        "content": r"""# Splitting, Boiling and Dyeing Korai

**Splitting.** Freshly cut stalks are split while still green and pliant. The worker nicks the base
with a small blade and then runs the stalk apart along its natural angles with thumb and finger; a
coarse household mat uses halves, while superfine work subdivides a single culm into very thin
ribbons — fineness is limited by hand skill, not by tooling. Split ribbons are dried in shade, since
direct sun makes them brittle and bleaches them unevenly.

**Boiling and soaking.** The dried ribbons are boiled in water, which softens the inner pith and
leaches soluble matter, and are then steeped in river water for several days and beaten or rubbed by
hand. Craft accounts from Pattamadai attribute the final suppleness specifically to soaking in
Thamirabarani water — a traditional claim about local water quality, not a measured result. The
practical effect is real enough: a boiled and soaked strand can be bent double without cracking,
which is what allows a finished mat to be folded instead of rolled.

**Colour.** Softened, de-waxed strands absorb dye far better than raw ones. Traditional palettes drew
on **indigo** (அவுரி) for blue-black, **turmeric** for yellow, and red from dye roots and barks, with
alum-type mordants to fix them. Aniline and later synthetic dyes displaced most of these recipes
during the colonial and post-independence periods; the classic Pattamadai border colours of red,
green and black are today usually chemical.
"""
    },
    {
        "slug": "concept-hygroscopic-sedge-aerenchyma-and-thermal-comfort-of-floor-mats",
        "category": "concept",
        "file": "concept-hygroscopic-sedge-aerenchyma-and-thermal-comfort-of-floor-mats.md",
        "name_en": "Why a Sedge Mat Sleeps Cool: Aerenchyma, Moisture Wicking and Thermal Comfort",
        "name_ta": "கோரைப் பாயின் காற்றுத் திசு, ஈரம் உறிஞ்சும் தன்மை, குளிர்ச்சி",
        "era": "Ancient to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "A sedge mat feels cool in humid heat for three linked reasons: the stem's air-filled aerenchyma tissue makes it a poor conductor yet a light, breathable layer; cellulose-rich strands are hygroscopic and wick sweat away from skin, where it evaporates; and the woven lattice holds the sleeper a few millimetres clear of the floor so air can move beneath.",
        "summary_ta": "ஈரப்பதமான வெப்பத்தில் கோரைப் பாய் குளிர்ச்சியாக உணரப்படுவதற்கு மூன்று காரணங்கள்: தண்டின் உள்ளே உள்ள காற்று நிரம்பிய திசு வெப்பத்தைக் கடத்தாது; செல்லுலோஸ் இழைகள் வியர்வையை உறிஞ்சி ஆவியாக வெளியேற்றுகின்றன; நெய்யப்பட்ட கட்டம் உடலை தரையிலிருந்து சற்று உயர்த்தி, அடியில் காற்று நகர வழிவிடுகிறது.",
        "sources": [
            "Flora of the Presidency of Madras (Gamble)",
            "Journal of Ethnobiology",
            "Textile Research Journal",
            "Indian Council of Agricultural Research fibre crop bulletins"
        ],
        "content": r"""# Thermal Comfort and Hygroscopy of a Korai Mat

**Air inside the stem.** Wetland sedges carry **aerenchyma** — spongy, air-filled parenchyma that
ferries oxygen down to roots sitting in anaerobic mud. Split korai keeps much of that void structure,
so each strand is partly still air. Still air is one of the poorest conductors available in a natural
material, which is why a mat neither drains body heat like a stone floor nor stores and returns it
like a thick cotton quilt.

**Water in the wall.** Sedge strand is largely cellulose with some lignin and silica. Cellulose is
**hygroscopic**: it adsorbs water vapour into its amorphous regions and releases it as the surrounding
air dries. In practice a mat takes up sweat at the contact patch and passes it outward to evaporate,
so the skin stays comparatively dry — the dominant comfort factor in a humid climate, where
evaporation, not conduction, limits cooling.

**Geometry.** The plain-weave lattice of cotton warp over korai weft creates a corrugated surface with
a few millimetres of relief and thousands of small interstices. Contact area with the body is reduced,
and air can move laterally under the sleeper.

**Trade-offs.** The same hygroscopy makes mats vulnerable: stored damp they mildew, and swelling and
shrinking cycles embrittle the strands. Households therefore sun and re-roll mats periodically, and
the silica content that stiffens the strand also abrades thread, which is why warp cotton wears out
before the sedge does.
"""
    },
    {
        "slug": "technology-cotton-warp-korai-weft-frame-loom-paai-weaving",
        "category": "technology",
        "file": "technology-cotton-warp-korai-weft-frame-loom-paai-weaving.md",
        "name_en": "Frame-Loom Mat Weaving: Cotton Warp (Paavu), Korai Weft (Oodai) and the Hand Beater",
        "name_ta": "பருத்தி நூல் பாவும் கோரை ஊடையும் கொண்ட மரச்சட்ட தறியில் பாய் நெய்தல்",
        "era": "Medieval to Modern Era",
        "year_start": 1000,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Fine mats are woven on a low wooden frame loom set near the ground: cotton thread is stretched as the lengthwise warp (paavu) under even tension, single wet korai strands are laid in by hand as the crosswise weft (oodai), and each pick is driven home with a flat wooden beater; two people usually work the loom, one inserting strands and one beating and dressing the selvedge.",
        "summary_ta": "நுண்ணிய பாய்கள் தரைக்கு அருகில் அமைக்கப்படும் தாழ்வான மரச்சட்ட தறியில் நெய்யப்படுகின்றன: பருத்தி நூல் சமமான இறுக்கத்தில் நீளவாக்கில் பாவாக விரிக்கப்படுகிறது, ஈரமான கோரை இழைகள் ஒவ்வொன்றாகக் கையால் ஊடையாக நுழைக்கப்படுகின்றன, ஒவ்வொரு இழையும் தட்டையான மரத் தட்டையால் இறுக்கித் தள்ளப்படுகிறது. பொதுவாக இருவர் சேர்ந்து நெய்வர்.",
        "sources": [
            "Census of India handicrafts monographs",
            "All India Handicrafts Board survey reports",
            "Madras District Gazetteer, Tinnevelly",
            "Development Commissioner (Handicrafts) craft documentation"
        ],
        "content": r"""# Cotton Warp, Korai Weft: the Mat Loom

**The loom.** Unlike a coarse mat plaited without any loom, the fine korai mat is a true woven cloth
with two different materials. The loom is a simple rectangular hardwood frame, pegged or lashed, laid
low over the ground or over a shallow pit so the weavers sit at floor level with legs extended. There
is no fly shuttle and no treadle; warp openings are made with lease rods or by hand.

**Warp and weft.** The lengthwise **paavu** (பாவு) is cotton thread, counted out and stretched across
the frame at a uniform spacing that fixes the mat's width and its grade. The crosswise **oodai**
(ஊடை) is korai: strands are kept damp in a cloth or water trough and inserted one at a time, alternate
strands entering from opposite sides so that the butt ends alternate and the mat stays even in
thickness.

**Beating.** After each pick the weaver drives the strand against the previous one with a flat wooden
beater, then tucks the projecting end back around the edge warp to form the selvedge. Density depends
almost entirely on this beating: the same warp can yield a loose kitchen mat or a dense sleeping mat.

**Pace.** Because every weft strand is placed by hand, output is measured in weeks per mat for fine
grades rather than metres per day — the central economic fact of the craft.
"""
    },
    {
        "slug": "technology-pattamadai-pattu-paai-superfine-strand-count-grading",
        "category": "technology",
        "file": "technology-pattamadai-pattu-paai-superfine-strand-count-grading.md",
        "name_en": "Pattamadai Pattu Paai: Superfine Strand-Count Grading of Silk-Like Mats",
        "name_ta": "பட்டமடை பட்டுப் பாய் — நுண்ணிய இழை எண்ணிக்கை தரப்படுத்தல்",
        "era": "Colonial to Modern Era",
        "year_start": 1800,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Pattamadai's reputation rests on grading by fineness: mats are sorted by how thinly the korai was split and how many strands are packed per unit of length, from coarse household grades up to the superfine 'pattu paai' (silk mat) that is pliable enough to fold like cloth and carries a Geographical Indication registration in India today.",
        "summary_ta": "பட்டமடையின் புகழ் நுண்மையைத் தரப்படுத்துவதில் உள்ளது: கோரை எவ்வளவு மெல்லியதாகப் பிளக்கப்பட்டது, ஒரு அங்குலத்தில் எத்தனை இழைகள் அடைக்கப்பட்டன என்பதன் அடிப்படையில் பாய்கள் வகைப்படுத்தப்படுகின்றன. சாதாரண வீட்டுப் பாயிலிருந்து துணிபோல மடிக்கக்கூடிய 'பட்டுப் பாய்' வரை தரங்கள் உண்டு; இன்று இதற்குப் புவிசார் குறியீட்டு அங்கீகாரம் உள்ளது.",
        "sources": [
            "Geographical Indications Registry, India",
            "Development Commissioner (Handicrafts) craft documentation",
            "Census of India handicrafts monographs",
            "Madras District Gazetteer, Tinnevelly"
        ],
        "content": r"""# Grading the Pattamadai Silk Mat

**What "pattu paai" means.** *Pattu* is silk; *paai* is mat. The name is a claim about handle, not
material — there is no silk in the mat. A superfine Pattamadai mat is soft and drapey enough to be
folded into a small bundle and posted, and it is this foldability that trade buyers test first.

**The grade is a count.** Fineness is set upstream, at splitting: the thinner each korai ribbon, the
more strands fit into a given length of mat, and the smoother and more cloth-like the surface. Weavers
and cooperative graders therefore classify mats by strand density per unit length, expressed as a
count, together with warp thread spacing. Coarse grades are quick, utilitarian and thick; the
superfine grades take a single weaver-pair weeks of work and are correspondingly expensive. Published
figures for these counts vary between sources and are not quoted here.

**Recognition.** The craft's fame grew through colonial and post-independence exhibition circuits, and
craft accounts record a presentation mat woven at Pattamadai for Queen Elizabeth II around her 1953
coronation — the anecdote most often repeated about the village. The mat is today registered as a
Geographical Indication in India, which ties the name to the Pattamadai locality and its process.

**Why fineness is fragile.** Superfine work needs long slender stalks, skilled splitters and patient
beating; when any of the three is short, grades slip downward, and the economics of the craft have
pushed much production toward the coarser end.
"""
    },
    {
        "slug": "artifact-pattamadai-pattu-paai-bridal-mat-and-storage-rolls",
        "category": "artifact",
        "file": "artifact-pattamadai-pattu-paai-bridal-mat-and-storage-rolls.md",
        "name_en": "The Bridal Pattu Paai: Woven Monograms, Coloured Borders and Storage Rolls",
        "name_ta": "பட்டமடை மணப் பட்டுப் பாய்: பெயர் நெய்தல், வண்ணக் கரை, சுருள் பேணல்",
        "era": "Colonial to Modern Era",
        "year_start": 1800,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The best-known korai object is the dowry or wedding-gift mat: a superfine mat with dyed borders and often the couple's names or initials woven into the field in coloured strands, presented folded or rolled, wrapped in cloth, and kept for decades in a household chest with neem leaves or pepper against insects.",
        "summary_ta": "கோரைப் பொருட்களில் மிகப் பிரபலமானது மணமக்களுக்கு அன்பளிப்பாகத் தரப்படும் பாய்: வண்ணக் கரையுடன், சில சமயம் மணமக்களின் பெயர்களை வண்ண இழைகளில் நெய்து, மடித்தோ சுருட்டியோ துணியில் சுற்றித் தரப்படுகிறது. பூச்சி அணுகாமல் வேப்பிலை அல்லது மிளகுடன் பெட்டியில் பல ஆண்டுகள் பாதுகாக்கப்படுகிறது.",
        "sources": [
            "Development Commissioner (Handicrafts) craft documentation",
            "Census of India handicrafts monographs",
            "Madras District Gazetteer, Tinnevelly",
            "Journal of Ethnobiology"
        ],
        "content": r"""# The Bridal Mat as Object

**Form.** A gift-grade mat is rectangular, sized for one or two sleepers, with a plain or lightly
patterned field framed by dyed borders — red, green and black are the familiar Pattamadai
combination. Lettering is produced in the weave itself: the weaver substitutes pre-dyed korai strands
for undyed ones at counted positions, so a name, a year, or a pair of initials appears as a woven
block motif rather than as printing or embroidery. Mistakes cannot be unpicked cheaply, so the
lettering is planned on the warp before weaving begins.

**Social use.** The mat belongs to the ordinary gift economy of Tamil households rather than to ritual:
it is given at weddings and housewarmings, carried to a daughter's new home, and brought out for
guests. The silk-grade mat's portability — folded flat into a cloth bundle — is part of why it travels
as a present.

**Keeping it.** Storage is a craft of its own. Mats are rolled around a core or folded along existing
creases, wrapped in old cotton cloth, and stored dry; neem leaves, dried pepper or camphor are added
against silverfish and borers. Periodic sunning drives off the moisture that sedge readily takes up.
Warp cotton is the usual point of failure, and a well-kept bridal mat is often repaired at the
selvedge and kept in a family for a generation or more.
"""
    },
    {
        "slug": "artifact-korai-splitting-knife-hardwood-beater-and-mat-loom-frame",
        "category": "artifact",
        "file": "artifact-korai-splitting-knife-hardwood-beater-and-mat-loom-frame.md",
        "name_en": "Mat-Weaver's Kit: Splitting Blade, Hardwood Beater, Lease Rods and Loom Frame",
        "name_ta": "கோரை நெசவாளரின் கருவிகள்: பிளக்கும் கத்தி, மரத் தட்டை, பாய் தறிச் சட்டம்",
        "era": "Medieval to Modern Era",
        "year_start": 1000,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The whole craft runs on a handful of cheap tools: a short iron blade for nicking and splitting stalks, a flat hardwood or bamboo beater for driving each weft strand home, smooth lease rods for opening the warp, wooden pegs and a pegged frame for warp tension, and a water trough and cloth for keeping strands damp.",
        "summary_ta": "இந்தக் கைவினை முழுவதும் சில எளிய கருவிகளிலேயே இயங்குகிறது: தண்டை நுனி கீறிப் பிளக்கும் சிறிய இரும்புக் கத்தி, ஒவ்வொரு ஊடையையும் இறுக்கித் தள்ளும் தட்டையான மரத் தட்டை, பாவைப் பிரிக்கும் மெழுகிய மரக் கோல்கள், இறுக்கத்திற்கான மரக் குமிழ்களும் சட்டமும், இழைகளை ஈரமாக வைக்கும் நீர்த் தொட்டியும் துணியும்.",
        "sources": [
            "Census of India handicrafts monographs",
            "All India Handicrafts Board survey reports",
            "Development Commissioner (Handicrafts) craft documentation"
        ],
        "content": r"""# The Mat-Weaver's Tool Kit

**Splitting blade.** A short, thin iron knife, often a reworked kitchen blade, used only to start the
split at the butt of a stalk; the rest of the split is pulled by hand along the stalk's three angles.
A splitter's skill, not the blade, sets the fineness of the ribbon.

**Beater.** A flat, smooth bat of hardwood — bamboo and tamarind-type dense woods are both reported —
with a rounded working edge. Each inserted korai strand is struck along its length to pack it against
the preceding pick. A worn beater with a nicked edge snags wet strands, so the edge is dressed with
sand or a file.

**Lease rods and pegs.** Smooth rods laid through the cotton warp hold the shed open and preserve
thread order. The loom frame itself is a pegged rectangle of beams; wedges at the ends take up slack
as weaving advances. Tension is judged by thumb-pluck, not measured.

**Wet storage.** A shallow trough or a damp cloth bundle keeps split strands pliable at the loom —
dried-out strands crack when beaten. Finished mats are wound on a wooden roller for transport.

**Nothing precious.** Every item here is village-made and replaceable, which is one reason the craft
leaves so little archaeological trace: the tools are perishable wood and the product is cellulose,
while the only durable component, the iron blade, is indistinguishable from any household knife.
"""
    },
    {
        "slug": "institution-pattamadai-hereditary-korai-weaver-cooperative-society",
        "category": "institution",
        "file": "institution-pattamadai-hereditary-korai-weaver-cooperative-society.md",
        "name_en": "Pattamadai's Hereditary Weaver Households and Their Cooperative Society",
        "name_ta": "பட்டமடை பரம்பரைக் கோரை நெசவாளர் குடிகளும் கூட்டுறவுச் சங்கமும்",
        "era": "Colonial to Modern Era",
        "year_start": 1800,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Fine mat weaving at Pattamadai is concentrated in hereditary households of the Tamil-speaking Labbai Muslim community, with women doing much of the splitting and weaving; since the twentieth century a weavers' cooperative society and state handicrafts agencies have handled raw korai supply, grading, credit and marketing, and today also administer the Geographical Indication.",
        "summary_ta": "பட்டமடையின் நுண்பாய் நெசவு தமிழ் பேசும் லப்பை முஸ்லிம் சமூகத்தின் பரம்பரைக் குடிகளில் குவிந்துள்ளது; பிளத்தல், நெய்தல் பணிகளில் பெரும்பகுதியைப் பெண்கள் செய்கின்றனர். இருபதாம் நூற்றாண்டிலிருந்து நெசவாளர் கூட்டுறவுச் சங்கமும் அரசு கைவினை நிறுவனங்களும் கோரை வழங்கல், தரப்படுத்தல், கடன், விற்பனையைக் கையாளுகின்றன.",
        "sources": [
            "Census of India handicrafts monographs",
            "Madras District Gazetteer, Tinnevelly",
            "Geographical Indications Registry, India",
            "Development Commissioner (Handicrafts) craft documentation"
        ],
        "content": r"""# The Weaving Community and Its Cooperative

**Who weaves.** Fine korai weaving at Pattamadai is a household occupation of the village's
Tamil-speaking **Labbai** Muslim families, among whom the skill passes from mother and grandmother to
daughter; splitting and weaving are largely women's work, carried on at home between domestic tasks,
while men have more often handled stalk purchase, transport and sale. Non-Muslim households in the
surrounding villages also weave coarser korai goods, so the community concentration is in the
superfine grades rather than in mat-making as such.

**Why a cooperative.** The craft's weak points are working capital and markets, not skill: a superfine
mat ties up weeks of labour before it earns anything, and raw korai must be bought in bulk at harvest.
A weavers' cooperative society at Pattamadai, together with state handicrafts bodies and the Tamil
Nadu handicrafts marketing network, has therefore taken on procuring and grading korai, advancing
credit against work in progress, buying finished mats at graded rates, and taking them to emporia and
exhibitions.

**Today.** The same institutional layer is the custodian of the Geographical Indication: GI protection
is held and policed collectively rather than by individual weavers. Reported problems are consistent
across sources — shrinking numbers of young weavers, competition from plastic mats, and pressure on
the river-margin korai plots themselves.
"""
    },
    {
        "slug": "place-pattamadai-ancient-thamirabarani-korai-mat-haven",
        "category": "place",
        "file": "place-pattamadai-ancient-thamirabarani-korai-mat-haven.md",
        "name_en": "Pattamadai: the Thamirabarani Village of Fine Korai Mats",
        "name_ta": "பட்டமடை: தாமிரபரணிக் கரையின் பழமையான கோரைப் பாய் ஊர்",
        "era": "Medieval to Modern Era",
        "year_start": 1000,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Pattamadai is a village in Tirunelveli district, Tamil Nadu, on the banks of the Thamirabarani at roughly 8.72 N, 77.50 E, whose name is synonymous with the superfine korai sleeping mat; its advantages are a perennial river for korai plots and soaking, a hereditary weaving community, and a marketing reputation now protected as a Geographical Indication.",
        "summary_ta": "பட்டமடை, திருநெல்வேலி மாவட்டத்தில் தாமிரபரணி ஆற்றின் கரையில் (ஏறத்தாழ 8.72 வடக்கு, 77.50 கிழக்கு) அமைந்த ஊர்; நுண்ணிய கோரைப் பாய்க்கு இதன் பெயரே அடையாளம். வற்றாத ஆறு, பரம்பரை நெசவுக் குடிகள், புவிசார் குறியீட்டால் பாதுகாக்கப்படும் வணிகப் புகழ் ஆகியவை இதன் வலிமைகள்.",
        "sources": [
            "Madras District Gazetteer, Tinnevelly",
            "Census of India village directories",
            "Geographical Indications Registry, India",
            "Development Commissioner (Handicrafts) craft documentation"
        ],
        "content": r"""# Pattamadai on the Thamirabarani

**Setting.** Pattamadai lies in Tirunelveli district of Tamil Nadu, on the Thamirabarani (Porunai)
a short way inland from Cheranmahadevi and Ambasamudram, at approximately **latitude 8.72 N,
longitude 77.50 E**. The landscape is classic **marutham** — a perennial river fed by the Western
Ghats' south-west monsoon catchment, canal-irrigated paddy, and waterlogged margins and abandoned
channels that will grow korai sedge where paddy will not.

**Why here.** Three conditions coincide. The river runs year-round, so korai plots can be kept under
shallow standing water through the dry Tirunelveli months, and split strands can be soaked and washed
in quantity. The old channel land is marginal for grain, making sedge the better return. And the
village holds a dense concentration of hereditary weaving households, so splitting, warping and
beating skills are available next door rather than imported.

**Reputation.** By the colonial period Pattamadai mats were being sent to exhibitions and emporia as a
district speciality, and the village name — not the material — became the brand; "a Pattamadai" means
a fine mat anywhere in Tamil Nadu. That reputation is now formalised as a Geographical Indication tied
to the locality.

**Pressures.** Korai acreage, river flow regulation, and the supply of young weavers are the recurring
concerns in modern craft reporting on the village.
"""
    }
]

EDGES = [
    [
        "text-sangam-paai-and-nanal-reed-mat-bedding-references",
        "attests",
        "technology-cotton-warp-korai-weft-frame-loom-paai-weaving",
        "material_culture",
        "Sangam Era",
        "Sangam poems attest that spread woven mats and reed bedding were everyday household goods, the long background to loom-woven mat craft.",
        "Perumpanarruppadai"
    ],
    [
        "concept-cyperus-pangorei-korai-sedge-ecology-on-thamirabarani-banks",
        "supplies",
        "concept-korai-stalk-splitting-boiling-and-natural-dye-absorption",
        "material_culture",
        "Ancient to Modern Era",
        "Cultivated korai beds supply the long three-angled stalks that splitting, boiling and dyeing turn into weaving strands.",
        "Flora of the Presidency of Madras (Gamble)"
    ],
    [
        "place-pattamadai-ancient-thamirabarani-korai-mat-haven",
        "hosts",
        "concept-cyperus-pangorei-korai-sedge-ecology-on-thamirabarani-banks",
        "material_culture",
        "Medieval to Modern Era",
        "Pattamadai's waterlogged river margins and old Thamirabarani channels host the korai sedge plots the craft depends on.",
        "Madras District Gazetteer, Tinnevelly"
    ],
    [
        "concept-korai-stalk-splitting-boiling-and-natural-dye-absorption",
        "prepares",
        "technology-cotton-warp-korai-weft-frame-loom-paai-weaving",
        "material_culture",
        "Medieval to Modern Era",
        "Split, boiled and dyed strands are the weft stock loaded into the frame loom; unsoftened stalks crack under the beater.",
        "Census of India handicrafts monographs"
    ],
    [
        "technology-cotton-warp-korai-weft-frame-loom-paai-weaving",
        "utilizes",
        "artifact-korai-splitting-knife-hardwood-beater-and-mat-loom-frame",
        "material_culture",
        "Medieval to Modern Era",
        "Mat weaving runs on a pegged frame, lease rods, a splitting blade and a flat hardwood beater.",
        "All India Handicrafts Board survey reports"
    ],
    [
        "technology-cotton-warp-korai-weft-frame-loom-paai-weaving",
        "produces",
        "artifact-pattamadai-pattu-paai-bridal-mat-and-storage-rolls",
        "material_culture",
        "Colonial to Modern Era",
        "Hand-inserted korai weft over counted cotton warp produces the bordered, name-woven gift mat.",
        "Development Commissioner (Handicrafts) craft documentation"
    ],
    [
        "technology-pattamadai-pattu-paai-superfine-strand-count-grading",
        "grades",
        "artifact-pattamadai-pattu-paai-bridal-mat-and-storage-rolls",
        "material_culture",
        "Colonial to Modern Era",
        "Strand-count and warp-spacing grading sorts finished mats from coarse household goods up to foldable silk grades.",
        "Geographical Indications Registry, India"
    ],
    [
        "institution-pattamadai-hereditary-korai-weaver-cooperative-society",
        "administers",
        "technology-pattamadai-pattu-paai-superfine-strand-count-grading",
        "material_culture",
        "Colonial to Modern Era",
        "The weavers' cooperative and state handicrafts bodies apply the grades, set purchase rates and hold the Geographical Indication.",
        "Census of India handicrafts monographs"
    ],
    [
        "institution-pattamadai-hereditary-korai-weaver-cooperative-society",
        "based_in",
        "place-pattamadai-ancient-thamirabarani-korai-mat-haven",
        "material_culture",
        "Colonial to Modern Era",
        "The hereditary Labbai weaving households and their cooperative society are concentrated in Pattamadai village itself.",
        "Madras District Gazetteer, Tinnevelly"
    ],
    [
        "concept-hygroscopic-sedge-aerenchyma-and-thermal-comfort-of-floor-mats",
        "explains",
        "artifact-pattamadai-pattu-paai-bridal-mat-and-storage-rolls",
        "material_culture",
        "Ancient to Modern Era",
        "Aerenchyma air voids and cellulose hygroscopy explain why the mat sleeps cool, and why it must be sunned and stored dry.",
        "Journal of Ethnobiology"
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
