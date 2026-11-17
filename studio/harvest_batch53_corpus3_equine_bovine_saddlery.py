#!/usr/bin/env python3
"""
Harvester: Batch 53 - Ancient Tamil Equine & Bovine Saddlery, Mookkanangkayiru Nasal-Halter Biomechanics, Brass Salli-Mani Acoustics & Anthiyur Fair Craft
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
        "slug": "text-sangam-ahananuru-and-nedunalvaadai-on-pallanam-saddles-thalaiyattam-and-kinkini-bells",
        "category": "text",
        "file": "text-sangam-ahananuru-and-nedunalvaadai-on-pallanam-saddles-thalaiyattam-and-kinkini-bells.md",
        "name_en": "Sangam Ahananuru, Nedunalvaadai & Maduraikanchi on Pallanam Saddles, Thalaiyattam Plumes & Kinkini Bells",
        "name_ta": "அகநானூறு, நெடுநல்வாடை மற்றும் மதுரைக்காஞ்சியில் பல்லணம் (சேணம்), தலையாட்டம் மற்றும் கிண்கிணி மணிகள்",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "mullai",
        "summary_en": "Classical Tamil poetic accounts in Ahananuru, Kuruntokai, Nedunalvaadai, Maduraikanchi, and Perumpanarruppadai describing caparisoned horses and draught bulls outfitted with padded saddles (pallanam / senam), crimson yak-hair headstalls (thalaiyattam), foam-flecked iron bits (kadivalam), and resonant bronze bells (kinkini / mani).",
        "summary_ta": "அகநானூறு, குறுந்தொகை, நெடுநல்வாடை, மதுரைக்காஞ்சி மற்றும் பெரும்பாணாற்றுப்படையில் விவரிக்கப்படும் குதிரைகளின் பல்லணம் (சேணம்), செந்நிறத் தலையாட்டம், கடிவாளம் மற்றும் காளைகளின் கழுத்து மணி, கிண்கிணி.",
        "sources": [
            "Ahananuru",
            "Nedunalvaadai",
            "Maduraikanchi",
            "Perumpanarruppadai",
            "Kuruntokai"
        ],
        "content": "# Sangam Literature on Pallanam Saddles, Thalaiyattam & Kinkini Bells\n\nThe Sangam anthologies and *Pattuppattu* idylls contain rich technical vocabulary describing equine and bovine harness hardware used in war, chariotry, and agrarian transport:\n\n**Poetic & Technical Attestations:**\n- **Equine Saddlery (*Pallanam*), Bits & Plumes**: *Nedunalvaadai* and *Maduraikanchi* describe battle steeds wearing contoured saddles (*pallanam* or *senam*), crimson-dyed forehead plumes (*thalaiyattam* / *chuval-ani*), and iron curb/snaffle bits (*kadivalam* or *vaai-poottu*) chomped until white foam (*vilaalar*) drips onto their chests.\n- **Chariot & Bullock Bells (*Mani* & *Kinkini*)**: *Ahananuru* and *Kuruntokai* recount how returning charioteers binds or muzzles the bronze bells (*mani*) and cluster ankle-bells (*kinkini* / *sathangai*) of their horses and bulls so the loud ringing does not disturb nesting birds or alert village guards."
    },
    {
        "slug": "concept-mookkanangkayiru-nasal-septum-mechanoreceptor-leverage-and-bovine-steering-biomechanics",
        "category": "concept",
        "file": "concept-mookkanangkayiru-nasal-septum-mechanoreceptor-leverage-and-bovine-steering-biomechanics.md",
        "name_en": "Mookkanangkayiru Nasal-Septum Mechanoreceptor Sensitivity & Cranial Lever Biomechanics",
        "name_ta": "மூக்கணாங்கயிறு நாசித் தடுப்பு நரம்பு உணர்திறனும் தலைத் திருப்ப நெம்புகோல் உயிரியக்கவியலும்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Anatomical and biomechanical principles of the Tamil bovine nose-rope (mookkanangkayiru) paired with the poll head-halter (valaiyak-kayiru): piercing the thin, densely innervated yet avascular membranous window behind the rostral nasal cartilage to achieve maximum moment-arm leverage over the cervical spine with minimal hand force.",
        "summary_ta": "காளைகளின் மூக்குத் தடுப்பின் இரத்த நாளமற்ற மெல்லிய சவ்வில் துளையிட்டு மூக்கணாங்கயிறு மற்றும் வளையக்கயிறு கட்டுவதன் மூலம் குறைந்த விசையில் 600 கிலோ எடையுள்ள காளையைத் திருப்பும் உயிரியக்கவியல்.",
        "sources": [
            "Veterinary Anatomy & Restraint Biomechanics of Zebu Cattle (Bos indicus)",
            "Littlewood Livestock of Southern India (Kangayam & Bargur Cattle)",
            "ICAR Draught Animal Harness and Steering Studies"
        ],
        "content": "# Mookkanangkayiru Nasal-Septum & Cranial Lever Biomechanics\n\nA mature Kangayam or Bargur bullock possesses immense neck musculature capable of overpowering a simple neck collar, yet a single driver steers a pair of bulls using light finger tension on the *Mookkanangkayiru* (nasal halter rope):\n\n**Anatomical & Lever Mechanics:**\n- **Trigeminal Mechanoreceptor Density**: The small membranous region just caudal to the alar cartilage of the bovine nostrils is virtually devoid of major blood vessels or hyaline cartilage, allowing clean healing when pierced, yet is richly supplied by sensory branches of the infraorbital (trigeminal $V_2$) nerve.\n- **Maximal Cranial Moment Arm**: Because the nose-rope acts at the extreme anterior tip of the skull ($\\approx 45\\text{ cm}$ forward of the atlanto-occipital joint pivot), a gentle $20\\text{ N}$ lateral tug generates a high yaw torque that turns the head, while the companion poll-loop (*valaiyak-kayiru* passing behind the horns) absorbs heavy braking loads so the nasal septum is never torn."
    },
    {
        "slug": "concept-salli-mani-globular-cattle-bell-helmholtz-resonance-and-forest-herd-localization",
        "category": "concept",
        "file": "concept-salli-mani-globular-cattle-bell-helmholtz-resonance-and-forest-herd-localization.md",
        "name_en": "Salli-Mani Globular Bronze Bell Helmholtz Resonance & Forest Herd Acoustic Localization",
        "name_ta": "சல்லி மணி (வெண்கல உருண்டை மணி) ஹெல்ம்ஹோல்ட்ஸ் ஒலி அதிர்வும் வன மேய்ச்சல் ஒலி அடையாள அறிவியலும்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Acoustic physics of closed-shell globular bronze rumble bells (salli-mani / salangai) and flared sheet-metal cowbells (kotta-mani): coupling cavity Helmholtz resonance through a narrow equatorial lip-slit with high-Q bell-metal shell modes excited by an internal loose pellet (ul-naakku) for long-range forest herd tracking.",
        "summary_ta": "உட்புறம் உருளும் இரும்புக் குண்டு (உள் நாக்கு) மற்றும் குறுகிய வாய்ப் பிளவு கொண்ட வெண்கலச் சல்லி மணியின் ஒலி அதிர்வெண் இயற்பியலும், அடர்ந்த காட்டில் மேயும் கால்நடைகளை ஒலி கொண்டு கண்டறியும் முறையும்.",
        "sources": [
            "Acoustics of Crotal (Rumble) Bells & Helmholtz Shell Resonators",
            "Thurston Ethnographic Notes on Southern India: Pastoral Bells",
            "Bargur & Kolli Hills Forest Grazing Ecology"
        ],
        "content": "# Salli-Mani Globular Bell Acoustics & Forest Herd Localization\n\nPastoralists grazing semi-wild *Bargur*, *Alambadi*, and *Pulikulam* cattle in scrub jungles outfit lead animals with two acoustically distinct bell classes—cast bronze crotal bells (*Salli-Mani*) and riveted sheet-iron clapper bells (*Kotta-Mani*):\n\n**Acoustic & Ecological Principles:**\n- **Coupled Shell & Helmholtz Resonance**: A *Salli-Mani* is a thick-walled hollow bronze sphere or oblate ellipsoid split along its lower hemisphere by a narrow throat slot (*vaai*) terminating in twin circular stress-relief holes. As the internal loose iron ball (*ul-naakku*) rolls and impacts the lip edges with every stride, it excites both high-frequency metallic shell modes ($1.5-3.5\\text{ kHz}$ from the $80:20$ copper-tin bronze) and a lower cavity Helmholtz resonance.\n- **Acoustic Herd Signatures**: Low-frequency *kotta-mani* thuds ($400-700\\text{ Hz}$) diffract around dense thorny trees over $1\\text{ km}$, while matched chords of neck *salli-mani* allow a herdsman to tell at night whether a bull is cud-chewing, walking, or fleeing a predator."
    },
    {
        "slug": "concept-equine-kadivalam-jointed-bit-oral-bar-pressure-and-angavadi-stirrup-equilibrium",
        "category": "concept",
        "file": "concept-equine-kadivalam-jointed-bit-oral-bar-pressure-and-angavadi-stirrup-equilibrium.md",
        "name_en": "Equine Kadivalam Jointed-Bit Diastema Mechanics, Panju-Senam Load Distribution & Angavadi Stirrups",
        "name_ta": "குதிரைக் கடிவாள வாயழுத்த இயற்பியல், பஞ்சு மெத்தை சேண எடைப் பகிர்வு மற்றும் அங்கவடி சமநிலை",
        "era": "Sangam to Nayak Era",
        "year_start": -200,
        "year_end": 1800,
        "thinai": "mullai",
        "summary_en": "Biomechanical interface between rider and horse in traditional Tamil equitation: positioning the jointed iron bit (kadivalam) across the toothless mandibular diastema bars, distributing rider weight across the epaxial back muscles via a spine-clearing quilted cotton pad (panju-metthai-senam), and toe-ring vs full-arch stirrup (angavadi) kinematics.",
        "summary_ta": "குதிரையின் பற்களற்ற தாடை இடைவெளியில் அமரும் கடிவாளத்தின் விசைச் செயல்பாடு, முதுகெலும்பை உறுத்தாமல் எடையைப் பகிரும் பஞ்சு மெத்தை சேணம் மற்றும் அங்கவடி (கால் மிதி) சமநிலை அறிவியல்.",
        "sources": [
            "Jean Deloche Horses and Riding Equipment in Indian Art",
            "Sarasvati Mahal Library Asva-Sastra (Equine Treatises of Thanjavur)",
            "Nayak & Chola Cavalry Relief Iconography"
        ],
        "content": "# Equine Kadivalam Bit Mechanics, Panju-Senam & Angavadi Equilibrium\n\nAs documented by historian Jean Deloche across Tamil temple reliefs and *Asva-Sastra* manuscripts, South Indian equine tack evolved specifically for agile tropical horses and hot climates:\n\n**Equitation Biomechanics:**\n- **Diastema Bar & Tongue Pressure (*Kadivalam*)**: The forged iron mouthpiece (*kadivalam*) rests in the natural toothless gap (*diastema* or \"bars\") between the horse's incisors and premolars. A central figure-eight ring joint creates a nutcracker action that transfers rein tension smoothly onto the edges of the tongue and mandibular bars.\n- **Spine-Clearing Quilted Pad (*Panju-Metthai-Senam*) & Angavadi**: Rather than a rigid unpadded wooden tree that traps sweat and galls the withers in tropical heat, traditional Tamil saddles use twin thick bolsters stuffed with *ilavam-panju* (kapok) or raw cotton stitched parallel to the spine, creating a ventilated central channel over the spinous processes while suspending brass or iron stirrups (*angavadi*) under the rider's center of mass."
    },
    {
        "slug": "technology-bovine-nasal-septum-piercing-horn-paring-and-three-strand-mookkanangkayiru-twisting",
        "category": "technology",
        "file": "technology-bovine-nasal-septum-piercing-horn-paring-and-three-strand-mookkanangkayiru-twisting.md",
        "name_en": "Mookku-Kuthuthal Septum Piercing, Kombu-Seevuthal Horn Paring & Three-Strand Halter Twisting",
        "name_ta": "காளை மூக்குக் குத்துதல், கொம்பு சீவி எண்ணெய் இடுதல் மற்றும் மூக்கணாங்கயிறு திரிக்கும் தொழில்நுட்பம்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Traditional pastoral husbandry and cordage craft for training young bulls: piercing the nasal septum with a tapered iron needle (thulai-oosi), curing with turmeric and neem oil, reverse-plying soft cotton/hemp/coir nose-ropes (mookkanangkayiru) and head-halters (valaiyak-kayiru), and shaving/oiling horns (kombu-seevuthal) for symmetric curvature.",
        "summary_ta": "இளம் காளைகளுக்குத் துளை ஊசியால் மூக்குக் குத்தி மஞ்சள்-வேப்பெண்ணெய் இட்டு ஆற்றுதல், உறுத்தாத பருத்தி மற்றும் சணல் மூக்கணாங்கயிறு திரித்தல், கொம்பு சீவி ஆமணக்கு எண்ணெய் தடவும் நுட்பம்.",
        "sources": [
            "Ethnoveterinary Practices of Kongu Nadu & Madurai Cattle Breeders",
            "Kangayam Cattle Husbandry Manuals",
            "Traditional Fibre & Rope Craft of Tamil Nadu"
        ],
        "content": "# Septum Piercing, Kombu-Seevuthal Horn Shaping & Halter Twisting\n\nTransforming a spirited young *Kangayam* or *Umblachery* bull calf into a responsive cart or plough animal involves three specialized rural crafts executed between $12$ and $24\\text{ months}$ of age:\n\n**Husbandry & Cordage Techniques:**\n- **Mookku-Kuthuthal & Antiseptic Curing**: The calf is restrained with a soft rope hitch (*தாம்புக்கயிறு*), and a veteran cattle-handler pierces the thin nasal septum window in a single swift thrust using a tapered iron bodkin (*thulai-oosi*) or fire-hardened *karuvelam* needle. A thin starter cord soaked in turmeric powder, slaked lime, and neem/gingelly oil is threaded through and rotated daily for a week until epithelialization completes.\n- **Three-Strand Halter Plying & Kombu-Seevuthal**: Ropemakers twist three strands of combed cotton, sunn-hemp (*sanal*), or retted coir using a hand-whirled wooden spinner (*ராட்டினம்*) into a smooth, non-abrasive *mookkanangkayiru* finished with a spliced eye-loop. Simultaneously, horn-shavers (*Kombu-Seevubavar*) pare outer flaky keratin layers from the bull's horns with a curved draw-knife (*kombu-kathi*), heat-massage the horn core with castor oil, and bind temporary bamboo splints to guide symmetrical upward curvature."
    },
    {
        "slug": "technology-cire-perdue-salli-mani-bell-casting-and-panju-metthai-cotton-saddle-quilting",
        "category": "technology",
        "file": "technology-cire-perdue-salli-mani-bell-casting-and-panju-metthai-cotton-saddle-quilting.md",
        "name_en": "Enclosed-Pellet Salli-Mani Bronze Bell Casting & Multi-Ply Cotton Saddle Quilting",
        "name_ta": "உள்நாக்கு வைத்த வெண்கலச் சல்லி மணி வார்ப்பு மற்றும் பஞ்சு மெத்தை சேணம் தைக்கும் தொழில்நுட்பம்",
        "era": "Medieval to Modern Era",
        "year_start": 800,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Foundry and saddlery manufacturing technologies: casting hollow bronze salli-mani bells with an already-enclosed loose iron clapper ball by encapsulating the iron pellet inside a friable clay-and-charcoal core before pouring molten bell-metal, alongside heavy cotton-webbing girth weaving and kapok-quilted horse saddle assembly.",
        "summary_ta": "வெண்கலச் சல்லி மணியின் உள்ளேயே இரும்புக் குண்டு இருக்குமாறு களிமண் கரு வைத்து வார்க்கும் கொல்லர் நுட்பமும், தடித்த பருத்தி நாடா மற்றும் இலவம்பஞ்சு கொண்டு குதிரைச் சேணம் தைக்கும் கலையும்.",
        "sources": [
            "Cire-Perdue & Sand-Casting of Bronze Cattle Bells in Tamil Nadu",
            "Artisans of Erode, Gobichettipalayam & Nachiyarkoil",
            "Traditional Indian Saddlery & Harness Making"
        ],
        "content": "# Enclosed-Pellet Salli-Mani Bell Casting & Cotton Saddle Quilting\n\nA persistent puzzle to casual observers is how a solid iron clapper ball (*ul-naakku*) gets inside a one-piece cast bronze *Salli-Mani* whose narrow slit is less than a third of the ball's diameter:\n\n**Foundry & Saddlery Processes:**\n- **Core-Encapsulated Pellet Casting**: The bell-founder first wraps a pre-forged spherical iron pellet (or rounded river pebble) inside a ball of sandy clay mixed with charred paddy husk. Small clay chaplet pins hold this inner core centered inside the outer wax or two-part loam mold while molten bell-metal ($78\\%\\text{ Cu}, 22\\%\\text{ Sn}$) is poured around it. Once cooled, the smith pokes a pointed iron rod through the narrow bottom sound-slit, pulverizes and shakes out the friable sandy clay core, and leaves the solid iron pellet trapped permanently inside the resonant bronze cavity.\n- **Panju-Metthai Saddle & Nada-Pattai Weaving**: Saddlers weave $10\\text{ cm}$-wide heavy cotton cinch webbing (*nada-pattai*) on pit-looms, quilt multi-layer canvas and woollen broadcloth bolsters stuffed with compressed cotton/kapok over a leather-bound bamboo/wood gullet arch, and rivet forged iron stirrup bars and crupper rings."
    },
    {
        "slug": "artifact-kombu-kuppi-turned-brass-horn-ferrules-netri-pattam-cowrie-forehead-bands-and-salli-mani-collars",
        "category": "artifact",
        "file": "artifact-kombu-kuppi-turned-brass-horn-ferrules-netri-pattam-cowrie-forehead-bands-and-salli-mani-collars.md",
        "name_en": "Kombu-Kuppi Turned Brass Horn-Caps, Cowrie Netri-Pattam Forehead Bands & Salli-Mani Neck Straps",
        "name_ta": "பித்தளைக் கொம்புக் குப்பி, சோழி பதித்த நெற்றிப்பட்டம் மற்றும் சல்லி மணித் தோல் கழுத்துப் பட்டைகள்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Ceremonial and protective bovine trappings of Tamil Nadu: lathe-turned conical brass and silver horn-tip finials (kombu-kuppi / magudam) preventing horn splitting, cowrie-shell and glass-bead forehead caparisons (netri-pattam), and thick buffalo-hide collars strung with graduated bronze salli-mani rumble bells.",
        "summary_ta": "மாட்டுப் பொங்கல் மற்றும் ரெக்ளாப் பந்தயக் காளைகளின் கொம்பு நுனியில் பூட்டப்படும் பித்தளைக் கொம்புக் குப்பி, சோழி மற்றும் பாசி மணிகள் கோர்த்த நெற்றிப்பட்டம், வெண்கலச் சல்லி மணி மாலைகள்.",
        "sources": [
            "Government Museum Chennai Ethnographic & Pastoral Ornament Collection",
            "Mattu Pongal & Jallikattu Material Culture Studies",
            "Kongu Nadu Pastoral Heritage Archives"
        ],
        "content": "# Kombu-Kuppi Brass Horn-Caps, Netri-Pattam & Salli-Mani Collars\n\nDuring *Mattu Pongal*, temple cattle processions, and rural *Rekla* races, prize bullocks are dressed in a complete panoply of protective metal and textile ornaments:\n\n**Bovine Regalia Artifacts:**\n- **Kombu-Kuppi (*Kombu-Poon*)**: Hollow conical ferrules ($10-18\\text{ cm}$ long) cast in brass or silver and turned on a lathe with stepped lotus rings, terminating in an acorn finial or a loop holding silk tassels (*kuncham*) and miniature jingle bells. Cemented onto pared horn tips with melted lac (*arakku*) or cross-pinned, they protect the horn apex from splintering during *eruthu-kattu* or fence impacts.\n- **Cowrie Netri-Pattam & Salli-Mani Collars**: Across the forehead between the horns ties the *Netri-Pattam*—a triangular crimson felt pad stitched with white marine cowrie shells (*sozhi*, *Monetaria moneta*), brass studs, and a central evil-eye mirror. Around the dewlap hangs a heavy leather or braided nylon/cotton collar (*kanda-mani*) carrying $12$ to $24$ graduated bronze *salli-mani* bells."
    },
    {
        "slug": "artifact-panju-metthai-quilted-horse-saddles-jointed-iron-kadivalam-bits-and-brass-angavadi-stirrups",
        "category": "artifact",
        "file": "artifact-panju-metthai-quilted-horse-saddles-jointed-iron-kadivalam-bits-and-brass-angavadi-stirrups.md",
        "name_en": "Panju-Metthai Quilted Horse Saddles, Jointed Iron Kadivalam Bridles & Cast Brass Angavadi Stirrups",
        "name_ta": "பஞ்சு மெத்தை குதிரைச் சேணம், மூட்டு இரும்புக் கடிவாளம் மற்றும் வார்ப்புப் பித்தளை அங்கவடிகள்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Traditional Tamil equine harness assemblage: the deep-seated quilted cotton and embroidered felt saddle (panju-metthai-senam / pallanam) with braided cotton breast-collar (maar-pattai) and crupper, tinned-iron jointed snaffle/curb bits (kadivalam), and cast brass arch stirrups (angavadi) used on rural riding horses and temple mounts.",
        "summary_ta": "கிராமப்புறக் குதிரைகள் மற்றும் ஆலய ஊர்வலப் புரவிகளுக்குப் பூட்டப்படும் பஞ்சு மெத்தை சேணம், மார்புப் பட்டை, மூட்டு இணைப்பு கொண்ட இரும்புக் கடிவாளம் மற்றும் பித்தளை அங்கவடிகள்.",
        "sources": [
            "Jean Deloche Horses and Riding Equipment in Indian Art",
            "Thanjavur Maratha & Madurai Nayak Armoury & Stable Inventories",
            "Anthiyur Horse Fair Saddlery Documentation"
        ],
        "content": "# Panju-Metthai Quilted Horse Saddles, Kadivalam Bits & Angavadi Stirrups\n\nTraditional Tamil horsemen—from village *Gramani* riders and *Mariamman/Ayyanar* festival mounts to hill-pack pony handlers—utilize a distinctive textile-dominant saddlery system:\n\n**Equine Harness Components:**\n- **Panju-Metthai-Senam (Quilted Saddle)**: Built over a high-pommeled, high-cantled wooden or bamboo arch padded with thick multi-layered cotton batting (*panju-metthai*) and faced with brightly piped crimson, green, or indigo woollen felt (*banath*), secured by dual woven cotton girths (*nada-pattai*), a tasseled breast-collar (*maar-pattai*), and a tail crupper (*val-pattai*).\n- **Jointed Iron Kadivalam & Cast Brass Angavadi**: The bridle headstall (*thalai-kattu*), woven from flat dyed cotton tape adorned with brass rosettes (*சூரியப் பூ*) and cowries, holds a tinned wrought-iron jointed bit (*kadivalam*). Suspended from heavy braided cotton or leather leathers are wide-tread cast brass or iron stirrups (*angavadi*) that support barefoot or sandaled riders."
    },
    {
        "slug": "institution-kudirai-chettiar-horse-traders-kangayam-breeder-guilds-and-aadi-anthiyur-cattle-shandy",
        "category": "institution",
        "file": "institution-kudirai-chettiar-horse-traders-kangayam-breeder-guilds-and-aadi-anthiyur-cattle-shandy.md",
        "name_en": "Kudirai-Chettiar Horse Guilds, Korangadu Pastoral Lineages & Aadi Livestock Shandy Institutions",
        "name_ta": "குதிரைச் செட்டியார் வணிகக் குழுக்கள், கொரங்காடு மேய்ச்சல் மரபு மற்றும் ஆடி மாதக் கால்நடைச் சந்தைகள்",
        "era": "Chola to Modern Era",
        "year_start": 900,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Mercantile and pastoral institutions sustaining equine and bovine culture in Tamil Nadu: medieval Kudirai-Chettiar horse-trading corporations recorded in stone inscriptions, fenced Korangadu Acacia-Cenchrus pasture estates of Kongu Nadu breeding Kangayam bulls, and annual temple-linked livestock shandies (Anthiyur, Kanniseri, and Madurai).",
        "summary_ta": "கல்வெட்டுகளில் குறிக்கப்படும் குதிரைச் செட்டியார் வணிகக் குழுக்கள், கொங்கு நாட்டுக் காங்கேயம் காளைகளை வளர்க்கும் 'கொரங்காடு' மேய்ச்சல் நில அமைப்பு மற்றும் ஆடி மாத அந்தியூர் குதிரை-மாட்டுச் சந்தை மரபு.",
        "sources": [
            "South Indian Inscriptions (Kudirai-Chettiar & Malaimandalam Horse Traders)",
            "Nicholson Manual of the Coimbatore District (Korangadu Pastures)",
            "Historical Records of the Anthiyur Gurunathaswamy Festival Shandy"
        ],
        "content": "# Kudirai-Chettiar Guilds, Korangadu Lineages & Aadi Livestock Shandies\n\nThe breeding, trading, and outfitting of draught cattle and riding horses in Tamil Nadu have been organized for centuries through specialized merchant guilds, fenced pasture commons, and annual temple fairs:\n\n**Mercantile & Pastoral Institutions:**\n- **Kudirai-Chettiars & Korangadu Breeders**: Chola and Pandya inscriptions celebrate the *Kudirai-Chettiars* who imported and outfitted cavalry and riding mounts across Tamilakam. In the dry *mullai* uplands of Kongu Nadu, agrarian families maintain live-fenced (*kiluvai* / *Commiphora berryi* hedged) calcareous pastures called *Korangadu* seeded with *Kolukattai* grass (*Cenchrus ciliaris*) and *Vellai-Velam* (*Acacia leucophloea*) to rear prized *Kangayam* bulls.\n- **Annual Temple Livestock Shandies (*Maattu-Sandhai*)**: Timed to the month of *Aadi* (August) and *Thai/Maasi* festivals, massive multi-day livestock fairs at Anthiyur, Tiruvannamalai, Kalugumalai, and Madurai bring together breeders, veterinary nose-piercers, horn-shavers, bell-founders, and saddlers in a single regulated marketplace."
    },
    {
        "slug": "place-anthiyur-ancient-kongu-gurunathaswamy-horse-and-cattle-fair-saddlery-haven",
        "category": "place",
        "file": "place-anthiyur-ancient-kongu-gurunathaswamy-horse-and-cattle-fair-saddlery-haven.md",
        "name_en": "Anthiyur: Ancient Kongu Gurunathaswamy Horse & Cattle Fair, Saddlery & Brass-Bell Haven",
        "name_ta": "அந்தியூர் - கொங்கு நாட்டுக் குருநாதசுவாமி குதிரை-மாட்டுச் சந்தை மற்றும் சேணக் கலைத் தளம்",
        "era": "Medieval Kongu to Modern Era",
        "year_start": 1200,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Historic market town of Anthiyur (lat 11.5760, lng 77.5890, thinai: mullai) at the foothills of the Bargur hills in Erode district of Kongu Nadu, famous across South India for the annual Aadi Gurunathaswamy Temple Horse and Cattle Fair and its vast bazaar of traditional horse saddles, nose-ropes, horn-caps, and bronze salli-mani bells.",
        "summary_ta": "ஈரோடு மாவட்டம் பர்கூர் மலை அடிவாரத்தில் அமைந்த அந்தியூர் (அட்சரேகை 11.5760, தீர்க்கரேகை 77.5890): நூற்றாண்டுகள் பழமையான ஆடி மாதக் குருநாதசுவாமி கோவில் குதிரை-மாட்டுச் சந்தை மற்றும் அணிகலன் சந்தையின் மையம்.",
        "sources": [
            "Coimbatore District Gazetteer: Bhavani & Anthiyur Taluks",
            "Ethnography of the Anthiyur Gurunathaswamy Temple Aadi Perunthiruvizha",
            "National Bureau of Animal Genetic Resources: Bargur & Kangayam Tracts"
        ],
        "content": "# Anthiyur: Gurunathaswamy Horse & Cattle Fair and Saddlery Haven\n\nSituated at latitude $11.5760^\\circ\\text{ N}$, longitude $77.5890^\\circ\\text{ E}$ in the *mullai* foothills where the Bargur mountain range meets the Bhavani river plains of Erode district, Anthiyur hosts South India's most famous traditional equine and bovine gathering—the *Anthiyur Gurunathaswamy Temple Horse and Cattle Fair*:\n\n**Historical & Artisanal Prominence:**\n- **Convergence of Breeds (Bargur, Kangayam & Kathiawari/Marwari)**: Held annually for four days during the Tamil month of *Aadi* (August) around the forest shrine of *Adhi Perumal / Gurunathaswamy* (a tradition traced back to medieval Kongu Chola, Vijayanagara-Nayak, and Tipu Sultan cavalry remount camps), the fair gathers thousands of trotting *Bargur* hill cattle, mighty *Kangayam* draught bulls, and dancing *avadhi/sevalai* riding horses.\n- **The Grand Saddlery & Bell Bazaar**: Entire avenues of the fairground are occupied by hereditary *Thol-Kaarar* (leatherworkers), *Kayiru-Thirikkaravar* (rope-twisters), and *Kanchar* (bell-founders) selling tens of thousands of dyed *mookkanangkayiru* nose-ropes, *netri-pattam* cowrie bands, turned brass *kombu-kuppi* horn-caps, resonant bronze *salli-mani* bells, and embroidered *panju-metthai* horse saddles."
    }
]

EDGES = [
    [
        "text-sangam-ahananuru-and-nedunalvaadai-on-pallanam-saddles-thalaiyattam-and-kinkini-bells",
        "documents",
        "artifact-panju-metthai-quilted-horse-saddles-jointed-iron-kadivalam-bits-and-brass-angavadi-stirrups",
        "material_culture",
        "Sangam to Medieval Era",
        "Nedunalvaadai, Maduraikanchi, and Ahananuru document contoured pallanam saddles, thalaiyattam plumes, and iron kadivalam bits.",
        "Nedunalvaadai & Ahananuru"
    ],
    [
        "concept-mookkanangkayiru-nasal-septum-mechanoreceptor-leverage-and-bovine-steering-biomechanics",
        "governs",
        "technology-bovine-nasal-septum-piercing-horn-paring-and-three-strand-mookkanangkayiru-twisting",
        "material_culture",
        "Iron Age to Modern Era",
        "Trigeminal mechanoreceptor sensitivity and cranial moment-arm leverage govern nasal septum piercing and three-strand mookkanangkayiru rigging.",
        "ICAR Draught Animal Studies"
    ],
    [
        "concept-salli-mani-globular-cattle-bell-helmholtz-resonance-and-forest-herd-localization",
        "governs",
        "technology-cire-perdue-salli-mani-bell-casting-and-panju-metthai-cotton-saddle-quilting",
        "material_culture",
        "Iron Age to Modern Era",
        "Coupled Helmholtz cavity and bronze shell resonance govern the slit geometry and enclosed iron clapper casting of salli-mani bells.",
        "Acoustics of Crotal Bells"
    ],
    [
        "concept-equine-kadivalam-jointed-bit-oral-bar-pressure-and-angavadi-stirrup-equilibrium",
        "guides",
        "artifact-panju-metthai-quilted-horse-saddles-jointed-iron-kadivalam-bits-and-brass-angavadi-stirrups",
        "material_culture",
        "Sangam to Nayak Era",
        "Mandibular diastema bar mechanics and spine-clearing dorsal load distribution guide the design of jointed kadivalam bits and quilted panju-metthai saddles.",
        "Deloche Horses in Indian Art"
    ],
    [
        "technology-bovine-nasal-septum-piercing-horn-paring-and-three-strand-mookkanangkayiru-twisting",
        "prepares",
        "artifact-kombu-kuppi-turned-brass-horn-ferrules-netri-pattam-cowrie-forehead-bands-and-salli-mani-collars",
        "material_culture",
        "Sangam to Modern Era",
        "Kombu-seevuthal horn paring and hot castor-oil shaping prepare bullock horn tips for cementing lathe-turned brass kombu-kuppi ferrules.",
        "Kongu Pastoral Ethnography"
    ],
    [
        "technology-cire-perdue-salli-mani-bell-casting-and-panju-metthai-cotton-saddle-quilting",
        "fabricates",
        "artifact-kombu-kuppi-turned-brass-horn-ferrules-netri-pattam-cowrie-forehead-bands-and-salli-mani-collars",
        "material_culture",
        "Medieval to Modern Era",
        "Core-encapsulated bronze bell casting fabricates the graduated salli-mani rumble bells strung on leather cattle neck-collars.",
        "Tamil Nadu Bell-Founders Survey"
    ],
    [
        "technology-cire-perdue-salli-mani-bell-casting-and-panju-metthai-cotton-saddle-quilting",
        "produces",
        "artifact-panju-metthai-quilted-horse-saddles-jointed-iron-kadivalam-bits-and-brass-angavadi-stirrups",
        "material_culture",
        "Medieval to Modern Era",
        "Pit-loom cotton girth weaving and kapok bolster quilting produce traditional panju-metthai horse saddles and breast-collars.",
        "Traditional Indian Saddlery"
    ],
    [
        "institution-kudirai-chettiar-horse-traders-kangayam-breeder-guilds-and-aadi-anthiyur-cattle-shandy",
        "markets",
        "artifact-kombu-kuppi-turned-brass-horn-ferrules-netri-pattam-cowrie-forehead-bands-and-salli-mani-collars",
        "material_culture",
        "Chola to Modern Era",
        "Annual Aadi livestock shandies and Korangadu breeder guilds market thousands of brass horn-caps, cowrie forehead bands, and bronze cattle bells.",
        "Coimbatore District Manual"
    ],
    [
        "place-anthiyur-ancient-kongu-gurunathaswamy-horse-and-cattle-fair-saddlery-haven",
        "hosts",
        "institution-kudirai-chettiar-horse-traders-kangayam-breeder-guilds-and-aadi-anthiyur-cattle-shandy",
        "material_culture",
        "Medieval Kongu to Modern Era",
        "Anthiyur at the Bargur foothills hosts the centuries-old Aadi Gurunathaswamy Horse and Cattle Fair and South India's premier saddlery bazaar.",
        "Coimbatore District Gazetteer"
    ],
    [
        "text-sangam-ahananuru-and-nedunalvaadai-on-pallanam-saddles-thalaiyattam-and-kinkini-bells",
        "celebrates",
        "place-anthiyur-ancient-kongu-gurunathaswamy-horse-and-cattle-fair-saddlery-haven",
        "material_culture",
        "Sangam to Medieval Era",
        "Classical accounts of caparisoned steeds and bell-adorned Mullai bulls celebrate the equestrian and pastoral heritage preserved at Anthiyur.",
        "Maduraikanchi & Kongu Chronicles"
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
