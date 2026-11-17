#!/usr/bin/env python3
"""
Harvester: Batch 44 - Ancient Tamil Black Pepper & Spice Cultivation, Curing and the Yavana Pepper Trade
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
        "slug": "text-sangam-verses-on-milagu-pepper-and-yavanar-gold-ships",
        "category": "text",
        "file": "text-sangam-verses-on-milagu-pepper-and-yavanar-gold-ships.md",
        "name_en": "Sangam Verses on Milagu (Black Pepper) and the Yavanar Ships That Brought Gold for It",
        "name_ta": "மிளகு வணிகமும் யவனர் பொன் கப்பல்களும் குறித்த சங்கப் பாடல் சான்றுகள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "The classical Tamil anthologies repeatedly name milagu (black pepper) as a hill crop of the Western Ghats slopes and describe Yavanar vessels arriving at Muciri with gold and departing laden with pepper sacks - the oldest indigenous testimony to the pepper trade.",
        "summary_ta": "அகநானூறு, புறநானூறு போன்ற சங்கத் தொகை நூல்கள் மலைச் சாரலில் விளைந்த மிளகை, யவனர் கப்பல்கள் பொன் கொண்டுவந்து மிளகு மூடைகளை ஏற்றிச் சென்ற முசிறித் துறையை ஆகியவற்றைக் குறிப்பிடும் பாடல்களின் தொகுப்பு.",
        "sources": [
            "Akananuru",
            "Purananuru",
            "Pattinappalai",
            "Perumpanarruppadai",
        ],
        "content": r"""# Sangam Verses on Milagu and the Yavanar Gold Ships

Black pepper enters Tamil literature as **milagu** - and its smaller wild relative **kurumilagu** -
long before any Greek or Roman writer described the trade.

**What the anthologies actually say (cited by title, not by verse number, because numbering varies
between editions):**

- **Akananuru** carries the most famous image of the trade: Yavanar ships (*yavanar kalam*) putting
  in at the Chera port of **Muciri** on the Periyar, bringing **gold** and carrying away **pepper**.
  The exchange is described as a heap-for-heap barter at the waterfront, not a coin purchase.
- **Purananuru** places pepper among the tribute and bounty of the hill chieftains, alongside
  sandalwood, agarwood, wild honey, and elephant tusk - pepper is consistently a *kurinji/mullai*
  hinterland product, never a wet-delta one.
- **Pattinappalai** and **Perumpanarruppadai**, in their catalogues of what the great ports and
  highland tracts yield, list pepper with other hill produce (*malai-charakku*) brought down by
  caravan to the coast.

**Why this matters.** The verses establish three facts independently of Mediterranean sources:
pepper was a *cultivated or managed* ghat-slope crop, it moved coastward through hill caravans, and
it was already being paid for in bullion by foreign ships. The Tamil term for that incoming gold,
**yavanar pon**, became a shorthand for the whole exchange. The poems give no tonnages and no
prices; those come later, from the Periplus and from Roman fiscal documents.
""",
    },
    {
        "slug": "concept-piper-nigrum-vine-botany-and-standard-tree-trellis-agronomy",
        "category": "concept",
        "file": "concept-piper-nigrum-vine-botany-and-standard-tree-trellis-agronomy.md",
        "name_en": "Piper Nigrum Vine Botany: Adventitious Clinging Roots, Spike Inflorescence & Living Standard-Tree Trellises",
        "name_ta": "மிளகுக் கொடியின் தாவரவியல்: ஒட்டுவேர்கள், கதிர் பூக்கும் முறை, தாங்கு மரத் தோட்டமுறை",
        "era": "Iron Age to Modern Era",
        "year_start": -1000,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Piper nigrum is a perennial woody climber native to the Western Ghats that grips a living support tree with adventitious root-cushions at each node and fruits on pendulous spikes; Tamil and Malayali growers trained it on jackfruit, Erythrina and Garcinia standards rather than on dead poles.",
        "summary_ta": "பைப்பர் நைகிரம் எனும் மிளகுக் கொடி, ஒவ்வொரு கணுவிலும் தோன்றும் ஒட்டுவேர்களால் பலா, முள்முருங்கை, கொடம்புளி போன்ற உயிருள்ள தாங்கு மரங்களில் ஏறி வளர்ந்து, தொங்கும் கதிர்களில் காய்ப்பதன் தாவரவியல் விளக்கம்.",
        "sources": [
            "Flora of the Presidency of Madras",
            "Hortus Malabaricus",
            "Indian Institute of Spices Research bulletins",
            "Journal of Ethnobiology",
        ],
        "content": r"""# Piper Nigrum: Vine Botany and Standard-Tree Trellis Agronomy

**The plant.** Black pepper is a perennial woody climber of the Piperaceae, indigenous to the
evergreen forests of the Western Ghats. It is not self-supporting. At every node the stem throws
**adventitious clinging roots** - short root-cushions that adhere to bark - so the vine ascends a
host trunk without twining or tendrils. Two shoot types matter to the cultivator: the long
**runner shoots** that climb and are cut for planting material, and the short lateral
**fruiting branches** that bear the crop.

**Flowering and fruit.** Flowers are borne on slender pendulous **spikes** hanging opposite each
leaf, each spike carrying several dozen to well over a hundred tiny flowers. Wild ghat pepper is
largely dioecious; the vines selected and propagated by growers are overwhelmingly
hermaphrodite, which is why cultivated spikes set fruit densely and forest vines often do not.
Spiking follows the first heavy rains of the southwest monsoon; the drupes then need roughly six
to eight months to mature.

**The living trellis.** Instead of dead poles, growers trained vines on living **standards**
(*thaangu maram*): jackfruit (*pala*), *Erythrina* (*mullu-murungai*), *Garcinia* (*kodampuli*),
and various forest trees left standing when a slope was opened. The standard supplies graduated
shade, its leaf-fall mulches the vine's shallow feeder roots, and - with legume standards -
nitrogen. Growers pollarded standards before the monsoon so light reached the fruiting laterals.
Vine spacing followed the surviving trees, which is why old pepper gardens look like thinned
forest rather than planted rows.
""",
    },
    {
        "slug": "concept-piperine-chemistry-and-enzymatic-blackening-of-sun-dried-pepper",
        "category": "concept",
        "file": "concept-piperine-chemistry-and-enzymatic-blackening-of-sun-dried-pepper.md",
        "name_en": "Piperine Pungency, Volatile Oil Aroma & the Enzymatic Browning That Turns Green Drupes Black",
        "name_ta": "பைப்பரின் காரமும், ஆவி எண்ணெய் நறுமணமும், வெயிலில் உலரும்போது மிளகு கறுப்பாதலும்",
        "era": "Iron Age to Modern Era",
        "year_start": -1000,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "A dried peppercorn's bite comes from the alkaloid piperine already present in the fruit, its aroma from a small fraction of volatile terpene oil, and its black wrinkled skin from polyphenol oxidase browning the pericarp during sun-drying - three separable properties that the old graders judged by taste, smell and look.",
        "summary_ta": "உலர்ந்த மிளகின் காரம் பைப்பரின் என்னும் வேதிப்பொருளால், நறுமணம் ஆவி எண்ணெய்களால், கறுப்புச் சுருக்கத் தோல் நொதிகளால் (பாலிபீனால் ஆக்சிடேஸ்) ஏற்படும் - இம்மூன்று வேறுபட்ட பண்புகளை மிளகு தரம் பார்ப்பவர்கள் சுவை, மணம், தோற்றத்தால் கணித்தனர்.",
        "sources": [
            "Indian Institute of Spices Research bulletins",
            "Journal of Food Science",
            "Pharmacographia Indica",
            "Journal of Agricultural and Food Chemistry",
        ],
        "content": r"""# Piperine, Volatile Oil and the Blackening of the Peppercorn

Three distinct properties are at work in a single corn, and conflating them is the commonest
error in popular accounts.

**1. Pungency is not made by drying.** The bite is **piperine**, an amide alkaloid that is already
synthesised in the growing drupe and concentrated mostly in the pericarp. Dry black pepper
typically runs a few percent piperine by weight; white pepper, whose skin has been soaked off, is
noticeably less pungent for exactly that reason. Drying removes water and so *raises the measured
percentage*, but it does not create piperine.

**2. Aroma is a small, fugitive fraction.** Only a low single-digit percentage of the dry corn is
**volatile oil** - a terpene mixture dominated by compounds such as sabinene, limonene, pinene and
beta-caryophyllene. It is this fraction that escapes when pepper is ground early, stored warm, or
over-dried, which is why pepper was traded whole and ground at the point of use.

**3. Blackness is an enzymatic wound reaction.** The green drupe's own **polyphenol oxidase** acts
on phenolic substrates in the pericarp once the fruit is detached and bruised; the oxidised
phenolics polymerise into dark pigments, and the shrinking skin wrinkles into the familiar
reticulate corn. The reaction wants warmth, oxygen and an intact enzyme - hence slow sun-drying
blackens evenly, while corns dried in deep shade or in a cold spell cure grey and patchy and were
down-graded.
""",
    },
    {
        "slug": "concept-yavanar-pon-bullion-exchange-and-muziris-pepper-customs-testimony",
        "category": "concept",
        "file": "concept-yavanar-pon-bullion-exchange-and-muziris-pepper-customs-testimony.md",
        "name_en": "Yavanar Pon: Roman Bullion-for-Pepper Exchange and the Muziris Papyrus & Periplus Testimony",
        "name_ta": "யவனர் பொன்: மிளகுக்கு ஈடாகப் பெற்ற உரோமப் பொன்னும், முசிறிப் பாப்பிரஸ், பெரிப்ளூஸ் சான்றுகளும்",
        "era": "Early Historic Period",
        "year_start": -50,
        "year_end": 300,
        "thinai": "neithal",
        "summary_en": "Greco-Roman buyers settled for Tamil pepper largely in gold and silver coin rather than goods, a one-way bullion drain attested by the Periplus, complained of by Pliny, documented administratively by the Muziris papyrus, and left in the ground as Roman coin hoards in the Kongu country.",
        "summary_ta": "யவனர் (கிரேக்க-உரோம) வணிகர்கள் தமிழ் மிளகுக்கு ஈடாகப் பெரும்பாலும் பொன், வெள்ளிக் காசுகளைக் கொடுத்தனர்; பெரிப்ளூஸ், பிளினி, முசிறிப் பாப்பிரஸ், கொங்கு நாட்டில் கிடைத்த உரோமக் காசுக் குவியல்கள் இதற்குச் சான்று.",
        "sources": [
            "Periplus Maris Erythraei",
            "Pliny, Natural History",
            "Vienna Muziris papyrus (published editions)",
            "Indian Archaeology - A Review",
        ],
        "content": r"""# Yavanar Pon: Paying for Pepper in Gold

**The asymmetry.** Rome wanted pepper; Tamilakam wanted comparatively little that Rome made. Wine,
glass, red-slipped tableware, coral and a few metals went east, but they never balanced the cargo
going west, and the remainder was settled in **coin**. The Tamil phrase for this incoming metal is
*yavanar pon* - Yavana gold.

**The testimony, in general terms:**

- The **Periplus Maris Erythraei** describes Muziris and Nelkynda as the pepper marts, notes that
  the pepper of the route comes from one limited inland district, and says that ships for these
  ports carry out **large quantities of coin**.
- **Pliny's Natural History** gives the Roman retail end - black pepper the cheapest of the three
  peppers sold, long pepper several times dearer - and complains of the sums annually drained to
  India for luxuries. His figures are rhetorical totals, not customs returns, and should be read
  as such.
- The **Muziris papyrus** (a second-century Greek document from Egypt) is an administrative and
  fiscal record concerning a ship returning from Muziris. Its value here is not a pepper tonnage -
  it preserves the *mechanics*: consignment valuation, agency, and the Roman quarter-tax
  (*tetarte*) levied on the cargo at the Egyptian end.
- **Roman coin hoards** recovered repeatedly from the Coimbatore-Pollachi-Karur belt sit squarely
  on the inland pepper roads, which is the archaeological counterpart of the literary claim.
""",
    },
    {
        "slug": "concept-palghat-gap-pepper-caravans-and-hinterland-collection-depots",
        "category": "concept",
        "file": "concept-palghat-gap-pepper-caravans-and-hinterland-collection-depots.md",
        "name_en": "Palghat Gap Pepper Caravans, Hill-Grower Collection Depots & the Two-Coast Transit of Malai-Charakku",
        "name_ta": "பாலக்காட்டுக் கணவாய் வழி மிளகுச் சாத்துகளும், மலைவாழ் விளைவோரிடம் சேகரிக்கும் நிலையங்களும்",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "mullai",
        "summary_en": "Pepper from the Anamalai and Nelliyampathy foothills was pooled at foothill depots from scattered hill growers, then moved by pack-bullock and head-load caravan either west through the Palghat Gap to Muziris or east across the Kongu plain to the Coromandel - the only low break in the Western Ghats making both options live.",
        "summary_ta": "ஆனைமலை, நெல்லியம்பதி சாரல்களில் மலைவாழ் மக்களிடம் மிளகைச் சேகரித்து, எருதுச் சாத்துகளில் பாலக்காட்டுக் கணவாய் வழியாக முசிறிக்கும், கிழக்கே கொங்கு வெளி வழியாகச் சோழ மண்டலக் கரைக்கும் கொண்டு சென்ற வணிக வழித்தட அமைப்பு.",
        "sources": [
            "Madras District Gazetteer, Coimbatore",
            "Periplus Maris Erythraei",
            "Ainnurruvar and Manigramam inscriptions (medieval corpus)",
            "Geological Survey of India",
        ],
        "content": r"""# Palghat Gap Pepper Caravans and the Foothill Collection Depots

**Why the Gap decides everything.** The Western Ghats run almost unbroken for hundreds of
kilometres, but at Palakkad the wall falls away into a low, broad saddle only tens of metres above
the plain. Loaded bullocks can walk through it; they cannot cross a ghat pass. Every discussion of
Kongu pepper is therefore a discussion of a single corridor linking the Coimbatore-Pollachi
plateau to the Bharathapuzha plain and on to the Periyar ports.

**How pepper was assembled.** Pepper does not come off an estate in the ancient record; it comes
in small lots. Hill households and forest-dwelling communities working vines on standards in the
Anamalai and Nelliyampathy slopes brought dried corns down as **head-loads** in bamboo baskets to
**foothill depots** - periodic markets at the break of slope where hill produce (*malai-charakku*)
met plains grain, salt, iron and cloth. Barter at this interface, rather than coin, is what the
Sangam poems describe.

**The caravan.** From the depot, pepper travelled in **pack-bullock convoys** - the same
*umanar*-style caravan institution that moved salt - in sacks slung in pairs, each animal carrying
a load a man could re-balance alone. Caravans moved in the dry months after the crop cured, which
is also when the Gap is passable and the Red Sea sailing season was shaping up at the coast.

Depot sites and toll arrangements are reconstructed from gazetteer-era route memory and medieval
inscriptions; the Sangam-period detail is literary and should be read as such.
""",
    },
    {
        "slug": "technology-monsoon-timed-pepper-harvest-blanching-and-drying-yards",
        "category": "technology",
        "file": "technology-monsoon-timed-pepper-harvest-blanching-and-drying-yards.md",
        "name_en": "Monsoon-Timed Pepper Harvest, Spike Threshing, Hot-Water Blanching & Sun-Drying Yards",
        "name_ta": "பருவமழை சார்ந்த மிளகு அறுவடை, கதிர் உதிர்த்தல், கொதிநீர்த் தோய்த்தல், வெயில் களம் உலர்த்துதல்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Pepper is cut when one or two drupes on a spike turn yellow-red, trodden or threshed off the stalk, optionally dipped in near-boiling water, then spread on mats in a sun-drying yard for several days until the corns rattle at roughly a tenth moisture - about three parts green giving one part black pepper.",
        "summary_ta": "கதிரில் ஒன்றிரண்டு காய் சிவக்கும் பக்குவத்தில் மிளகு அறுவடை செய்து, மிதித்து அல்லது அடித்துக் காய்களை உதிர்த்து, கொதிநீரில் சிறிது நேரம் தோய்த்து, பாய்களில் பரத்தி வெயிலில் பல நாள் உலர்த்திக் கறுப்பு மிளகாக்கும் முறை.",
        "sources": [
            "Indian Institute of Spices Research bulletins",
            "Madras District Gazetteer, Coimbatore",
            "Journal of Food Science",
            "Hortus Malabaricus",
        ],
        "content": r"""# Monsoon-Timed Harvest, Blanching and the Sun-Drying Yard

**Picking the moment.** The crop is cut in the dry months after the northeast rains withdraw,
roughly the Tamil *Margazhi-Panguni* window. The grower does not wait for a whole spike to ripen:
the signal is **one or two drupes on the spike turning yellow-orange to red**. Cut then, the
remaining green corns are mature enough to cure black and the spike has not yet begun shedding.
Left later, berries drop in the yard and the lot ends up with hollow, light corns.

**Threshing.** Cut spikes are heaped, then **trodden underfoot or beaten** on a mat so the drupes
part from the stalk; stalk fragments and leaf trash are winnowed out, and pepper is handled as
loose corns from here on.

**Blanching.** Dipping the threshed green corns briefly in **near-boiling water** - a short
immersion, not a cook - ruptures surface cells, washes off field dirt, kills surface microbes and
makes the subsequent blackening fast and uniform; it also shortens drying by a day or more. The
practice is well documented in colonial-era and modern Malabar-Kongu processing; how old it is
remains an open question, and plain sun-drying without any dip is the simpler and probably older
route.

**The drying yard.** Corns are spread a few centimetres deep on **bamboo or palmyra mats** (or a
swept clay floor), turned by foot or rake several times a day for three to five days of good sun,
and heaped under cover at night against dew. The lot is dry when corns rattle and will not dent -
roughly a tenth of their weight still water. **Green to black runs near three to one by weight**,
the figure every caravan and tax calculation was built on.
""",
    },
    {
        "slug": "technology-pepper-density-grading-winnowing-and-sieve-calibration",
        "category": "technology",
        "file": "technology-pepper-density-grading-winnowing-and-sieve-calibration.md",
        "name_en": "Pepper Grading by Bulk Density: Winnowing Out Light Berries, Sieve Sizing & Water-Float Tests",
        "name_ta": "மிளகு அடர்த்தி தரம்பிரித்தல்: தூற்றுதல், சல்லடை அளவுப் பிரிப்பு, நீர் மிதப்புச் சோதனை",
        "era": "Early Historic to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Dried pepper was graded by weight-per-volume rather than by looks: a winnowing fan blew away hollow light berries, nested sieves split bold corns from small, and a water dip separated sinkers from floaters - the three tests behind every garbled-versus-ungarbled distinction in the later trade.",
        "summary_ta": "உலர்ந்த மிளகை முறத்தில் தூற்றி வெற்றுக் காய்களை நீக்குதல், சல்லடைகளால் அளவு பிரித்தல், நீரில் இட்டு மிதப்பவற்றைப் பிரித்தல் ஆகிய மூன்று சோதனைகளால் அடர்த்தி அடிப்படையில் தரம் பிரித்த நுட்பம்.",
        "sources": [
            "Madras District Gazetteer, Coimbatore",
            "Indian Institute of Spices Research bulletins",
            "Pharmacographia Indica",
            "Journal of Agricultural and Food Chemistry",
        ],
        "content": r"""# Grading Pepper by Density, Sieve and Float

A buyer paying in gold needed a test he could run at the waterfront. All three traditional tests
measure the same underlying thing: **how much pepper is in a given volume of pepper**.

**1. The winnowing fan.** Cured corns are poured from a height or tossed from a flat
**winnowing fan** (*muram*) in the sea breeze. Stalk trash, skin flakes and above all the hollow,
poorly-filled **light berries** carry downwind while sound heavy corns fall in a near column.
Repeated passes are what "garbled" pepper means - cleaned of light and extraneous matter - as
against unsorted "ungarbled" bulk.

**2. Nested sieves.** Corns are then rocked through **graded sieves** of split cane, perforated
hide or, later, punched metal. The coarse screen holds back the **bold** corns, which command the
premium; the mid screen passes ordinary trade pepper; what falls through the finest screen is
pinheads and broken matter sold cheap or kept for domestic use. Sieve apertures were kept as
physical reference pieces in the warehouse, not as recorded numbers.

**3. The water dip.** A sample dropped into a pot of water settles into **sinkers and floaters**.
Sound corns sink; hollow and insect-bored corns float, as do corns that were picked immature. The
ratio of floaters, eyeballed, was the quick honesty check on a sack.

The upshot was a bulk-density standard: a fixed measure of good pepper weighs more. Modern grade
names in the Malabar-Kongu trade still rest on liter-weight and sieve fractions, which is the same
logic written down.
""",
    },
    {
        "slug": "artifact-milagu-koodai-panniers-stone-weights-and-sealed-pepper-jars",
        "category": "artifact",
        "file": "artifact-milagu-koodai-panniers-stone-weights-and-sealed-pepper-jars.md",
        "name_en": "Milagu-Koodai Pannier Baskets, Stone & Bronze Beam-Balance Weights and Sealed Pepper Storage Jars",
        "name_ta": "மிளகுக் கூடைகள், கற்-வெண்கல எடைக்கற்கள், முத்திரையிட்ட மிளகுச் சாடிகள்",
        "era": "Early Historic to Medieval Era",
        "year_start": -300,
        "year_end": 1500,
        "thinai": "mullai",
        "summary_en": "The material kit of the pepper trade: paired bamboo-and-rattan pannier baskets slung on a bullock, coir sacks, flat beam-balance pans with stone and bronze weight sets for weighing out bulk corns, and wide-mouthed clay jars sealed against the monsoon so cured pepper could not re-absorb moisture.",
        "summary_ta": "மிளகு வணிகத்தின் பொருட்கள்: எருதின் இருபுறமும் தொங்கவிடும் மூங்கில்-பிரம்புக் கூடைகள், கயிற்று மூடைகள், கற்-வெண்கல எடைக்கற்களுடன் கூடிய தட்டுத் துலாக்கோல், பருவமழைக் காற்றில் ஈரம் ஏறாமல் முத்திரையிட்ட அகன்ற வாய் மண் சாடிகள்.",
        "sources": [
            "Madras District Gazetteer, Coimbatore",
            "Indian Archaeology - A Review",
            "Periplus Maris Erythraei",
            "Journal of Ethnobiology",
        ],
        "content": r"""# The Pepper Trade's Material Kit: Baskets, Weights and Jars

**Panniers and sacks.** The unit of movement inland was the **pannier basket** (*koodai*) woven of
split bamboo (*moongil*) and rattan (*pirambu*), often coir-bound at the rim, slung in **matched
pairs** across a pack-bullock so the animal rode level and a single man could re-balance a load.
Hill growers carried smaller back-baskets with a tumpline down to the depot. For the sea leg
pepper went into coarse **coir or hemp sacks** (*moodai*) that could be stacked in a hold and
re-weighed on arrival. Baskets and sacks almost never survive archaeologically in this climate;
they are known from ethnographic continuity and from basket impressions and cordage fragments.

**Weighing.** Bulk pepper was sold by weight, on an **equal-arm beam balance** (*thulaakkol*) with
two flat pans suspended by cords, against sets of **shaped stone and cast bronze weights**. Stone
weights are a recurring small find at Tamil early-historic trade sites; bronze examples belong
more to the medieval and later trade. Note the honest limit: unit *names* for bulk spice weight
here are securely attested only from medieval inscriptions and colonial records, so no named
standard should be projected back onto the Sangam waterfront.

**Storage.** Cured pepper at roughly a tenth moisture is stable - but **hygroscopic**, and a humid
night pulls it back toward mould. Depots and port godowns therefore held it in wide-mouthed
**clay jars**, lidded and luted with clay or cloth and raised on stone or timber off the damp
floor; ventilated bamboo bins served the same end in the hills.
""",
    },
    {
        "slug": "institution-ainnurruvar-and-manigramam-spice-guild-pepper-factors",
        "category": "institution",
        "file": "institution-ainnurruvar-and-manigramam-spice-guild-pepper-factors.md",
        "name_en": "Ainnurruvar & Manigramam: Merchant Corporations as Pepper Factors, Warehousers and Weighing Authorities",
        "name_ta": "ஐநூற்றுவர், மணிக்கிராமம்: மிளகு கொள்முதல், சேமிப்பு, துலாப் பொறுப்பேற்ற வணிகக் குழுக்கள்",
        "era": "Early Historic to Medieval Era",
        "year_start": 100,
        "year_end": 1300,
        "thinai": "neithal",
        "summary_en": "Pepper moved through merchant corporations - the Ainnurruvar, Manigramam and Anjuvannam of the inscriptions - which advanced goods to hill growers, warehoused and re-graded lots at the ports, supplied the weighmen, and negotiated toll and anchorage with rulers; their names are medieval, their function older.",
        "summary_ta": "ஐநூற்றுவர், மணிக்கிராமம், அஞ்சுவண்ணம் போன்ற வணிகக் கூட்டமைப்புகள் மலைவாழ் விளைவோருக்கு முன்பணம்/பண்டம் கொடுத்து மிளகு கொள்முதல் செய்து, துறைமுகக் கிடங்குகளில் தரம் பிரித்து, துலாக்காரரை நியமித்து, சுங்கமும் துறைக்கட்டணமும் பேசித் தீர்த்த அமைப்புகள்.",
        "sources": [
            "Ainnurruvar and Manigramam inscriptions (medieval corpus)",
            "Kollam Syrian copper plates (published editions)",
            "South Indian Inscriptions",
            "Periplus Maris Erythraei",
        ],
        "content": r"""# Merchant Corporations as Pepper Factors

**What a guild actually did in the pepper chain.** A hill household could grow pepper; it could not
hold a crop for a sailing season, finance a caravan, or argue tolls with a king. Four functions
were corporate:

1. **Advance and offtake.** Goods - salt, iron tools, cloth, grain - were advanced to hill growers
   against the coming crop, which tied a season's pepper to a buyer before it was picked.
2. **Warehousing and re-grading.** Lots pooled at port godowns were re-winnowed and re-sieved to a
   single marketable grade, because a Yavana or Arab buyer bought against a sample.
3. **The weighmen and the scale.** The corporation supplied the **weighman** and the house's
   reference weights; control of the scale was a real privilege and a real revenue, and disputes
   over it appear in inscriptions.
4. **Toll, anchorage and protection.** Rights of passage, customs rates, and armed escort for
   caravans were negotiated collectively with local rulers and recorded on stone and copper.

**The honest chronology.** The corporate names we can read - **Ainnurruvar** (the Five Hundred of
Ayyavole), **Manigramam**, **Anjuvannam**, and the *nanadesi* "merchants of many lands" - come from
**medieval** Tamil and Kerala inscriptions and copper plates, roughly the ninth to thirteenth
centuries. The Periplus and the Sangam poems show organised intermediaries at Muziris centuries
earlier, but they do not give us those bodies' names or constitutions. The institution is older
than its documented titles; the titles should not be back-projected.
""",
    },
    {
        "slug": "place-anamalai-ancient-kongu-pepper-and-spice-haven",
        "category": "place",
        "file": "place-anamalai-ancient-kongu-pepper-and-spice-haven.md",
        "name_en": "Anamalai: Ancient Kongu Black Pepper & Spice Haven, Pollachi Foothill Depots and the Gateway to the Palghat Gap",
        "name_ta": "ஆனைமலை: பழமையான கொங்கு மிளகு, நறுமணப் பொருள் வணிகத் தலம்",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1500,
        "thinai": "mullai",
        "summary_en": "The Anamalai Hills and the Pollachi plain at their foot form the eastern-slope pepper country of the Kongu land: rain-shadowed foothill gardens of vines on standard trees, periodic hill-produce markets at the break of slope, and a short march to the Palghat Gap and the Periyar ports beyond.",
        "summary_ta": "ஆனைமலையும் அதன் அடிவாரப் பொள்ளாச்சி வெளியும் கொங்கு நாட்டின் மிளகுச் சாரல்; தாங்கு மரங்களில் ஏறிய மிளகுக் கொடித் தோட்டங்கள், மலைச்சரக்குச் சந்தைகள், பாலக்காட்டுக் கணவாய் வழிப் பயணம் ஆகியவை ஒருங்கிணைந்த வணிகத் தலம்.",
        "sources": [
            "Madras District Gazetteer, Coimbatore",
            "Akananuru",
            "Geological Survey of India",
            "Indian Institute of Spices Research bulletins",
        ],
        "content": r"""# Anamalai: The Kongu Pepper and Spice Haven

**Where.** Approximately **10.5800 N, 77.0200 E** - the Anamalai (Elephant Hills) massif and the
**Pollachi** plain at its eastern foot, in the modern **Coimbatore-Tiruppur / Pollachi belt** of
Tamil Nadu. Thinai: **mullai**, the pastoral-forest tract, shading into the kurinji hills above and
the irrigated marutham of the Noyyal-Amaravathi basins below.

**Why pepper grows here and not east of here.** The Anamalai front catches the southwest monsoon
on its upper and western faces and throws a sharp rain shadow over the plain. Pepper wants heavy
seasonal rain, shade-dappled light and soil that drains - exactly the lateritic foothill slopes
and valley heads from a few hundred up to about twelve hundred metres. A few tens of kilometres
east, on the dry Kongu plain, the vine will not carry a crop unirrigated. That is the practical
sense behind the Periplus noting that the route's pepper comes from one restricted inland
district.

**The haven's three layers.**
- **Gardens** - vines trained on jackfruit, *Erythrina* and *Garcinia* standards among retained
  forest trees, worked by hill households including forest-dwelling communities.
- **Depots** - periodic markets at the break of slope around the Pollachi tract, where
  *malai-charakku* (pepper, cardamom, honey, resins, hill medicinals) was exchanged for plains
  salt, iron, grain and cloth.
- **Transit** - a short haul from these depots to the **Palghat Gap**, and from the Gap to the
  Periyar ports; eastward, the same roads cross the Kongu plain to Karur and the Coromandel.

Roman gold hoards from the Pollachi-Coimbatore belt and the Sangam picture of Yavanar ships
trading gold for pepper are the two ends of this one corridor. Identifying specific ancient depot
sites remains route reconstruction, not excavation.
""",
    },
]

EDGES = [
    [
        "text-sangam-verses-on-milagu-pepper-and-yavanar-gold-ships",
        "documents",
        "concept-yavanar-pon-bullion-exchange-and-muziris-pepper-customs-testimony",
        "material_culture",
        "Sangam Era",
        "Sangam verses on Yavanar ships bringing gold to Muciri for pepper are the indigenous counterpart to the Greco-Roman bullion testimony.",
        "Akananuru",
    ],
    [
        "text-sangam-verses-on-milagu-pepper-and-yavanar-gold-ships",
        "celebrates",
        "place-anamalai-ancient-kongu-pepper-and-spice-haven",
        "material_culture",
        "Sangam Era",
        "The anthologies place milagu among the hill produce of the Ghats slopes that the Anamalai-Pollachi tract supplied.",
        "Purananuru",
    ],
    [
        "concept-piper-nigrum-vine-botany-and-standard-tree-trellis-agronomy",
        "governs",
        "technology-monsoon-timed-pepper-harvest-blanching-and-drying-yards",
        "material_culture",
        "Iron Age to Modern Era",
        "Spike-by-spike ripening on a monsoon-triggered vine is what forces the selective cut-when-one-berry-reddens harvest rule.",
        "Indian Institute of Spices Research bulletins",
    ],
    [
        "technology-monsoon-timed-pepper-harvest-blanching-and-drying-yards",
        "triggers",
        "concept-piperine-chemistry-and-enzymatic-blackening-of-sun-dried-pepper",
        "material_culture",
        "Iron Age to Modern Era",
        "Threshing, blanching and slow sun-drying are the operations that let polyphenol oxidase blacken the pericarp evenly.",
        "Journal of Food Science",
    ],
    [
        "technology-monsoon-timed-pepper-harvest-blanching-and-drying-yards",
        "precedes",
        "technology-pepper-density-grading-winnowing-and-sieve-calibration",
        "material_culture",
        "Early Historic to Modern Era",
        "Only a fully cured lot can be winnowed, sieved and float-tested, so drying sets the input to grading.",
        "Madras District Gazetteer, Coimbatore",
    ],
    [
        "technology-pepper-density-grading-winnowing-and-sieve-calibration",
        "utilizes",
        "artifact-milagu-koodai-panniers-stone-weights-and-sealed-pepper-jars",
        "material_culture",
        "Early Historic to Medieval Era",
        "Winnowing fans, reference sieves, beam-balance weight sets and sealed jars are the physical instruments of grading and holding.",
        "Indian Archaeology - A Review",
    ],
    [
        "place-anamalai-ancient-kongu-pepper-and-spice-haven",
        "hosts",
        "concept-piper-nigrum-vine-botany-and-standard-tree-trellis-agronomy",
        "material_culture",
        "Sangam to Medieval Era",
        "The lateritic, monsoon-fed Anamalai foothill slopes are the habitat in which vines were trained on living standard trees.",
        "Geological Survey of India",
    ],
    [
        "concept-palghat-gap-pepper-caravans-and-hinterland-collection-depots",
        "connects",
        "place-anamalai-ancient-kongu-pepper-and-spice-haven",
        "material_culture",
        "Sangam to Medieval Era",
        "Pack-bullock caravans linked the Anamalai foothill depots westward through the Palghat Gap and eastward across the Kongu plain.",
        "Madras District Gazetteer, Coimbatore",
    ],
    [
        "institution-ainnurruvar-and-manigramam-spice-guild-pepper-factors",
        "manages",
        "concept-palghat-gap-pepper-caravans-and-hinterland-collection-depots",
        "material_culture",
        "Early Historic to Medieval Era",
        "Merchant corporations financed the offtake, escorted the convoys and negotiated the tolls along the Gap corridor.",
        "South Indian Inscriptions",
    ],
    [
        "institution-ainnurruvar-and-manigramam-spice-guild-pepper-factors",
        "supplies",
        "concept-yavanar-pon-bullion-exchange-and-muziris-pepper-customs-testimony",
        "material_culture",
        "Early Historic to Medieval Era",
        "Guild factors assembled and re-graded the port lots that foreign buyers settled for in gold and silver coin.",
        "Periplus Maris Erythraei",
    ],
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
