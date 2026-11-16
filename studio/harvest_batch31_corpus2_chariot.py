#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Temple Chariot Wheelwrighting, Timber Mechanics & Hydraulic Braking
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
        "file": "knowledge/texts/text-tevaram-tiruvarur-hymns-on-azhi-ther-processional-grandeur.md",
        "slug": "text-tevaram-tiruvarur-hymns-on-azhi-ther-processional-grandeur",
        "category": "text",
        "name_en": "Tevaram: Saivite Hymns on the Colossal Azhi Ther of Tiruvarur & Sacred Chariot Festivals",
        "name_ta": "\u0ba4\u0bc7\u0bb5\u0bbe\u0bb0\u0bae\u0bcd - \u0ba4\u0bbf\u0bb0\u0bc1\u0bb5\u0bbe\u0bb0\u0bc2\u0bb0\u0bcd \u0b86\u0bb4\u0bbf\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0bb5\u0bbf\u0bb4\u0bbe \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bbf\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd \u0bb5\u0ba3\u0bcd\u0b9f\u0bae\u0bbf\u0bb4\u0bcd \u0baa\u0ba4\u0bbf\u0b95\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Medieval Chola Era",
        "year_start": 600,
        "year_end": 1100,
        "thinai": "marutham",
        "summary_en": "Tevaram sacred devotional hymns of Appar and Sundarar depicting the cosmic grandeur, thunderous procession, and communal ecstasy of the mammoth Tiruvarur temple chariot.",
        "summary_ta": "\u0ba4\u0bbf\u0bb0\u0bc1\u0bb5\u0bbe\u0bb0\u0bc2\u0bb0\u0bcd \u0b86\u0bb4\u0bbf\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bbf\u0ba9\u0bcd \u0b95\u0bae\u0bcd\u0baa\u0bc0\u0bb0\u0bae\u0bbe\u0ba9 \u0baa\u0bb5\u0ba9\u0bbf, \u0ba8\u0bbe\u0ba9\u0bcd\u0b95\u0bc1 \u0bae\u0bbe\u0b9f\u0bb5\u0bc0\u0ba4\u0bbf\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b8e\u0bb4\u0bc1\u0bae\u0bcd \u0baa\u0bc7\u0bb0\u0bca\u0bb2\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bb2\u0bcd\u0bb2\u0bbe\u0baf\u0bbf\u0bb0\u0b95\u0bcd\u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bbe\u0ba9\u0bcb\u0bb0\u0bbf\u0ba9\u0bcd \u0baa\u0b95\u0bcd\u0ba4\u0bbf\u0baa\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc8 \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b85\u0baa\u0bcd\u0baa\u0bb0\u0bcd, \u0b9a\u0bc1\u0ba8\u0bcd\u0ba4\u0bb0\u0bb0\u0bcd \u0ba4\u0bc7\u0bb5\u0bbe\u0bb0\u0bae\u0bcd.",
        "sources": [
            "Tevaram Tirumurai 7",
            "Appar Tiruvarur Padikam",
            "Periyapuranam"
        ],
        "content": "# Tevaram: Saivite Hymns on the Colossal Azhi Ther of Tiruvarur\n\nThe 7th and 8th-century Saivite devotional canon Tevaram contains some of the earliest and most vivid poetic descriptions of the monumental temple chariot festival (Ther Thiruvizha) of Tiruvarur.\n\nSaint Sundaramurthi Nayanar and Appar sing of Lord Thyagaraja traversing the wide quadrangular avenues (mada-veedhi) of Tiruvarur in the soaring Azhi Ther. The poetry captures the sensory magnificence of the mobile temple: towering wooden tiers reaching into the heavens, ornate carved celestial figures, fluttering ceremonial pennants, and the earth-shaking rumble of colossal wooden wheels echoing across the Kaveri basin.\n\nThese sacred verses demonstrate that by the 7th century, temple chariot engineering in Tamil Nadu had achieved unparalleled architectural sophistication, serving as the spiritual, social, and technological centerpiece of urban civilization."
    },
    {
        "file": "knowledge/concepts/concept-ther-thatchu-ancient-tamil-sacred-temple-chariot-architecture-and-woodcraft.md",
        "slug": "concept-ther-thatchu-ancient-tamil-sacred-temple-chariot-architecture-and-woodcraft",
        "category": "concept",
        "name_en": "Ther-Thatchu: Sacred Temple Chariot Architecture, Vastu-Sastra & Mobile Woodcraft",
        "name_ta": "\u0ba4\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bc1 - \u0ba4\u0bbf\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0b9f\u0bcd\u0b9f\u0b9f\u0b95\u0bcd\u0b95\u0bb2\u0bc8, \u0b9a\u0bbf\u0bb1\u0bcd\u0baa \u0b9a\u0bbe\u0bb8\u0bcd\u0ba4\u0bbf\u0bb0\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0baf\u0b99\u0bcd\u0b95\u0bc1 \u0bae\u0bb0\u0bb5\u0bc7\u0bb2\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Sacred mechanical science of Tamil temple car architecture, synthesizing Silpa Sastras, interlocking timber joinery, and dynamic load-bearing engineering without metal fasteners.",
        "summary_ta": "\u0b9a\u0bbf\u0bb1\u0bcd\u0baa \u0b9a\u0bbe\u0bb8\u0bcd\u0ba4\u0bbf\u0bb0 \u0ba8\u0bc6\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8\u0b95\u0bb3\u0bcd, \u0b89\u0bb2\u0bcb\u0b95 \u0b86\u0ba3\u0bbf\u0b95\u0bb3\u0bb1\u0bcd\u0bb1 \u0bae\u0bb0\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0baf\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b8e\u0b9f\u0bc8\u0baf\u0bc8\u0baa\u0bcd \u0baa\u0b95\u0bbf\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bb3\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bae\u0bbf\u0bb4\u0bcd \u0ba4\u0bbf\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0b9f\u0bcd\u0b9f\u0b9f\u0b95\u0bcd\u0b95\u0bb2\u0bc8 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Manasara Silpa Sastra",
            "Kashyapa Silpa Sastra",
            "Tiruvarur Thatchu Manuals"
        ],
        "content": "# Ther-Thatchu: Sacred Temple Chariot Architecture & Woodcraft\n\nTher-Thatchu represents the specialized architectural discipline dedicated to designing, constructing, and maintaining colossal mobile wooden temple cars (ratha or ther). Unlike static granite shrines, a chariot must withstand immense dynamic vibrations, lateral centrifugal forces, and rotational shear.\n\nTamil master craftsmen (thatchar) designed chariots in rigorous accordance with classical architectural treatises such as the Manasara and Kashyapa Silpa Sastras. The car's geometry was laid out along a multi-tiered vertical axis: an octagonal or hexagonal plinth base (upapitha), the sculpted axle plinth (adhishthana), the sanctum carriage platform (garbhagriha), and the soaring multi-tiered pyramidal wooden vimana.\n\nThe entire structural framework was assembled using intricate interlocking mortise-and-tenon joints, dove-tail splices, and hardwood pegs (maravani), intentionally omitting rigid iron nails to permit slight dynamic flexure under extreme road loads without fracturing."
    },
    {
        "file": "knowledge/technologies/technology-azhi-ther-colossal-multitiered-wooden-processional-car-mechanics.md",
        "slug": "technology-azhi-ther-colossal-multitiered-wooden-processional-car-mechanics",
        "category": "technology",
        "name_en": "Azhi-Ther: Structural Mechanics & Dynamic Load Distribution of Colossal Temple Cars",
        "name_ta": "\u0b86\u0bb4\u0bbf\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd - \u0baa\u0bbf\u0bb0\u0bae\u0bcd\u0bae\u0bbe\u0ba3\u0bcd\u0b9f \u0ba4\u0bbf\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1 \u0b87\u0baf\u0b95\u0bcd\u0b95\u0bb5\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bb3\u0bc1 \u0baa\u0b99\u0bcd\u0b95\u0bc0\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Early Medieval to Modern Era",
        "year_start": 800,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Structural mechanics of monumental temple cars weighing over 300 metric tons and standing 90 feet high, featuring low center-of-gravity engineering and cantilevered wooden trusses.",
        "summary_ta": "300 \u0b9f\u0ba9\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b85\u0ba4\u0bbf\u0b95\u0bae\u0bbe\u0ba9 \u0b8e\u0b9f\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd 90 \u0b85\u0b9f\u0bbf \u0b89\u0baf\u0bb0\u0bae\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0baa\u0bbf\u0bb0\u0bae\u0bcd\u0bae\u0bbe\u0ba3\u0bcd\u0b9f \u0b86\u0bb4\u0bbf\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bbf\u0ba9\u0bcd \u0b95\u0bc1\u0bb1\u0bc8\u0ba8\u0bcd\u0ba4 \u0baa\u0bc1\u0bb5\u0bbf\u0baf\u0bc0\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bc8\u0baf \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bb3\u0bc1 \u0baa\u0b99\u0bcd\u0b95\u0bc0\u0b9f\u0bcd\u0b9f\u0bc1 \u0b87\u0baf\u0b95\u0bcd\u0b95\u0bb5\u0bbf\u0baf\u0bb2\u0bcd.",
        "sources": [
            "Tiruvarur Temple Inscriptions",
            "Government Museum Epigraphy",
            "Chola Engineering Records"
        ],
        "content": "# Azhi-Ther: Structural Mechanics of Colossal Temple Cars\n\nThe Azhi Ther of Tiruvarur stands as the pinnacle of historical Indian mobile timber engineering. Weighing over 300 to 450 metric tons and soaring to an overall decorated height of 96 feet, it is one of the largest movable wooden structures in human history.\n\nThe car's sheer mass demanded sophisticated structural mechanics. The center of gravity was deliberately concentrated within the lower third of the structure through massive solid hardwood timbers and dense transverse chassis beams, ensuring lateral overturning stability on uneven dirt roadways.\n\nDynamic load distribution relied upon cantilevered truss networks that transferred the vertical weight of the multi-tiered vimana downward onto four primary load-bearing wheel stations. Flexible coir binding and tensioning stays (kayir-kattu) stabilized the superstructure against high crosswinds during turning maneuvers."
    },
    {
        "file": "knowledge/technologies/technology-urulai-and-achu-composite-wooden-wheel-and-axle-load-bearing-system.md",
        "slug": "technology-urulai-and-achu-composite-wooden-wheel-and-axle-load-bearing-system",
        "category": "technology",
        "name_en": "Urulai & Achu: Composite Segmented Wooden Wheels, Forged Iron Tires & Axle Mechanics",
        "name_ta": "\u0b89\u0bb0\u0bc1\u0bb3\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0b9a\u0bcd\u0b9a\u0bc1 - \u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bb0\u0b9a\u0bcd\u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0bae\u0bcd, \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0b9a\u0bcd\u0b9a\u0bc1 \u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bc1 \u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Massive segmented composite hardwood wheels (urulai) up to 9 feet in diameter bound with forge-shrunk iron hoops, turning on forged steel axles to bear immense rolling loads.",
        "summary_ta": "9 \u0b85\u0b9f\u0bbf \u0bb5\u0bbf\u0b9f\u0bcd\u0b9f\u0bae\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0b95\u0b9f\u0bbf\u0ba9 \u0bae\u0bb0 \u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bcd (\u0b89\u0bb0\u0bc1\u0bb3\u0bc8), \u0b9a\u0bc2\u0b9f\u0bc7\u0bb1\u0bcd\u0bb1\u0bbf \u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bb3\u0bc1 \u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b85\u0b9a\u0bcd\u0b9a\u0bc1 \u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Silappadikaram 5.120",
            "Tirumurai Inscriptions",
            "Madras Journal of Literature & Science"
        ],
        "content": "# Urulai & Achu: Composite Wooden Wheel & Axle Mechanics\n\nThe immense weight of the temple car was supported by four monumental solid or segmented composite wooden wheels (urulai), each measuring between 8 and 9 feet in diameter and up to 3 feet in tread thickness. Fabricated from exceptionally dense, shock-resistant Iluppai (Madhuca longifolia) and Vengai (Pterocarpus marsupium) timber segments, the wheels were bound together with heavy internal dowels.\n\nTo prevent the wooden rims from splintering under ground pressures exceeding 50 kilograms per square centimeter, master blacksmiths forged seamless outer iron hoop bands (vatta-patti). Heated to cherry red in open charcoal trenches, the iron hoops expanded, were positioned around the wheel circumference, and were rapidly quenched with cold water, shrinking tightly to compress the wooden segments into an indestructible monolithic disc.\n\nThe wheels revolved on colossal axles (achu-maram) forged from wootz-refined steel or dense seasoned timber billets, heavily lubricated with castor and neem oils to minimize rotational bearing friction."
    },
    {
        "file": "knowledge/artifacts/artifact-ther-vadam-massive-braided-coconut-coir-processional-pull-ropes.md",
        "slug": "artifact-ther-vadam-massive-braided-coconut-coir-processional-pull-ropes",
        "category": "artifact",
        "name_en": "Ther-Vadam: Monumental Braided Coconut Coir Hauling Cables & Tensile Rigging",
        "name_ta": "\u0ba4\u0bc7\u0bb0\u0bcd \u0bb5\u0b9f\u0bae\u0bcd - \u0baa\u0bbf\u0bb0\u0bae\u0bcd\u0bae\u0bbe\u0ba3\u0bcd\u0b9f \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0ba4\u0bc6\u0ba9\u0bcd\u0ba9\u0b99\u0bcd\u0b95\u0bc0\u0bb1\u0bcd\u0bb1\u0bc1 \u0bb5\u0b9f\u0b95\u0bcd\u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0bb4\u0bc1\u0bb5\u0bbf\u0b9a\u0bc8\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Early Medieval to Modern Era",
        "year_start": 800,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Massive four-strand braided coconut coir hauling cables (ther-vadam) measuring 6 to 9 inches in diameter, engineered to transmit over 600 kN of pull force from thousands of devotees.",
        "summary_ta": "6 \u0bae\u0bc1\u0ba4\u0bb2\u0bcd 9 \u0b85\u0b99\u0bcd\u0b95\u0bc1\u0bb2 \u0ba4\u0b9f\u0bbf\u0bae\u0ba9\u0bc1\u0bae\u0bcd, \u0baa\u0bb2 \u0ba8\u0bc2\u0bb1\u0bc1 \u0bae\u0bc0\u0b9f\u0bcd\u0b9f\u0bb0\u0bcd \u0ba8\u0bc0\u0bb3\u0bae\u0bc1\u0bae\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0ba4\u0bc6\u0ba9\u0bcd\u0ba9\u0bc8 \u0ba8\u0bbe\u0bb0\u0bcd\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1 (\u0ba4\u0bc7\u0bb0\u0bcd \u0bb5\u0b9f\u0bae\u0bcd); \u0baa\u0bb2\u0bcd\u0bb2\u0bbe\u0baf\u0bbf\u0bb0\u0b95\u0bcd\u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bbe\u0ba9 \u0baa\u0b95\u0bcd\u0ba4\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd 600 \u0b95\u0bbf.\u0ba8\u0bbf\u0baf\u0bc2\u0b9f\u0bcd\u0b9f\u0ba9\u0bcd \u0b87\u0bb4\u0bc1\u0bb5\u0bbf\u0b9a\u0bc8\u0baf\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb5\u0b9f\u0baa\u0bcd\u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Periyapuranam Tiruvarur Charukkam",
            "Tiruvarur Temple Manuals",
            "Chola Epigraphs"
        ],
        "content": "# Ther-Vadam: Monumental Coconut Coir Hauling Cables\n\nMoving a 300-ton temple chariot required exceptional tensile rigging. The vehicle was propelled by four colossal hand-braided ropes known as ther-vadam, each measuring between 6 and 9 inches in diameter and spanning up to 300 meters in length.\n\nManufactured from seasoned coastal coconut coir fibers (thengai-naar) that had been re-retted in salt water and cured for optimal elasticity, the vadam was constructed using a four-strand hawser-laid helical twist. Coir was uniquely chosen for its high tensile strength, resistance to rot, high frictional grip for bare hands, and progressive elastic elongation that damped destructive sudden surge shocks.\n\nThe four cables were securely anchored to the chariot's heavy chassis beams via forged iron eye-bolts and deadman hitches. When stretched taut along the processional streets, each vadam accommodated 2,000 to 3,000 devotees, collectively channeling massive human mechanical power."
    },
    {
        "file": "knowledge/technologies/technology-aappu-thadukku-wooden-wedge-kinetic-braking-and-steering-chocks.md",
        "slug": "technology-aappu-thadukku-wooden-wedge-kinetic-braking-and-steering-chocks",
        "category": "technology",
        "name_en": "Aappu & Thadukku: Hardwood Kinetic Braking Wedges & Manual Steering Chocks",
        "name_ta": "\u0b86\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1 - \u0b95\u0b9f\u0bbf\u0ba9 \u0bae\u0bb0 \u0b87\u0baf\u0b95\u0bcd\u0b95\u0ba4\u0bcd \u0ba4\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0b86\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bbf\u0b9a\u0bc8\u0ba4\u0bbf\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Dynamic kinetic braking and steering system using tapered tamarind hardwood chocks (aappu) manually driven beneath revolving wheels to arrest momentum and negotiate sharp street corners.",
        "summary_ta": "\u0b9a\u0bc1\u0bb4\u0bb2\u0bc1\u0bae\u0bcd \u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b95\u0bc0\u0bb4\u0bcd \u0baa\u0bc1\u0bb3\u0bbf\u0baf\u0bae\u0bb0 \u0b86\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bc8\u0b9a\u0bcd \u0b9a\u0bc6\u0bb2\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf, \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd \u0bb5\u0bc7\u0b95\u0ba4\u0bcd\u0ba4\u0bc8\u0ba4\u0bcd \u0ba4\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba8\u0bbf\u0bb1\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0ba4\u0bc1\u0bae\u0bcd, \u0ba4\u0bbf\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bc1\u0ba9\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0ba4\u0bbf\u0b9a\u0bc8 \u0ba4\u0bbf\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0bb5\u0ba4\u0bc1\u0bae\u0bbe\u0ba9 \u0bae\u0bb0\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Tiruvarur Temple Festival Protocols",
            "Folk Engineering Archives",
            "Madras District Gazetters"
        ],
        "content": "# Aappu & Thadukku: Kinetic Braking & Steering Chocks\n\nA temple chariot possessing hundreds of tons of momentum has no mechanical steering linkage or on-board hydraulic brakes. Arresting the vehicle's rolling progress and negotiating right-angled street intersections required extraordinary physical skill and dynamic chock braking (aappu-adithal).\n\nA specialized guild of brake masters (aappu-silpigal) marched closely alongside the churning wheels, carrying heavy, wedge-shaped chocks (aappu or thadukku) carved from exceptionally fibrous and resilient tamarind hardwood (puliyamaram).\n\nTo brake the car, artisans deftly hurled wedges directly in front of the advancing wheels, utilizing friction and the chariot's own climbing weight to arrest forward momentum. To execute a 90-degree corner turn around temple streets, wedges were placed exclusively under the inside wheels, creating an impromptu pivot axis while devotees hauled on the outside vadam ropes to sweep the chariot around."
    },
    {
        "file": "knowledge/institutions/institution-ratha-kara-silpi-guild-chariot-wheelwright-and-carpentry-guilds.md",
        "slug": "institution-ratha-kara-silpi-guild-chariot-wheelwright-and-carpentry-guilds",
        "category": "institution",
        "name_en": "Ratha-Kara Silpi Guild: Chariot Wheelwright, Master Carpenter & Smith Guilds",
        "name_ta": "\u0bb0\u0ba4\u0b95\u0bbe\u0bb0 \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbf \u0b95\u0bbf\u0bb2\u0bcd\u0b9f\u0bc1 - \u0ba4\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bb0\u0bcd\u0b95\u0bb3\u0bcd, \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0b9a\u0bcd\u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0bc8\u0bb5\u0bbf\u0ba9\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bc1\u0bae\u0bae\u0bcd",
        "era": "Early Historic to Modern Era",
        "year_start": -300,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Sovereign artisan corporations of master wheelwrights, joiners, and ironsmiths (ratha-karas) endowed with royal land grants for temple chariot construction and maintenance.",
        "summary_ta": "\u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bbe\u0bb2 \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0baa\u0ba4\u0bbf\u0bb5\u0bc1 \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f, \u0ba4\u0bbf\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bb0\u0bbe\u0bae\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bbf\u0bb1\u0bcd\u0b95\u0bbe\u0b95 \u0bb5\u0bb0\u0bbf\u0bb5\u0bbf\u0bb2\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bbf\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0ba4\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc8\u0bb5\u0bbf\u0ba9\u0bc8\u0b9e\u0bb0\u0bcd \u0b95\u0bbf\u0bb2\u0bcd\u0b9f\u0bc1.",
        "sources": [
            "Uyyakondan Tirumalai Inscriptions",
            "Rajaraja I Chola Epigraphs",
            "Silpa Rathnam"
        ],
        "content": "# Ratha-Kara Silpi Guild: Chariot Wheelwright Corporations\n\nThe construction, repair, and seasonal commissioning of monumental temple cars were entrusted to hereditary artisan corporations known in Chola epigraphy as the Ratha-Kara Silpi Guild.\n\nRoyal stone charters from temples across Thanjavur and Tiruchirappalli (such as the famed Uyyakondan Tirumalai inscription of Kulothunga Chola I) record extensive state privileges granted to these master artisans. Guild members enjoyed hereditary titles, tax-exempt agricultural land allotments (thatcha-kaani), and exclusive legal authority to practice architectural woodcraft, metallurgy, and vehicle mechanics.\n\nThe guild coordinated a rigorous division of labor: master sculptors (sirpacharyas) carved mythological friezes, wheelwrights machined heavy running gear, and iron-smiths cast axles and shrunk wheel tires, maintaining an unbroken tradition of sacred kinetic engineering."
    },
    {
        "file": "knowledge/concepts/concept-maram-thernthu-eduthal-sacred-timber-selection-curing-and-oil-tempering.md",
        "slug": "concept-maram-thernthu-eduthal-sacred-timber-selection-curing-and-oil-tempering",
        "category": "concept",
        "name_en": "Maram-Thernthu-Eduthal: Sacred Timber Selection, Water-Soaking & Oil Curing Physics",
        "name_ta": "\u0bae\u0bb0\u0bae\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc1 \u0b8e\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd - \u0ba4\u0bbf\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd \u0bae\u0bb0\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0bb5\u0bc1, \u0ba8\u0bc0\u0bb0\u0bcd \u0baa\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc8\u0bb2\u0b95\u0bcd \u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Dendrological science of identifying mature heartwood timbers (Iluppai, Vengai, Teak), water submersion curing, and herbal oil impregnation to prevent warping, rot, and borer attacks.",
        "summary_ta": "\u0bae\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4 \u0b87\u0bb2\u0bc1\u0baa\u0bcd\u0baa\u0bc8, \u0bb5\u0bc7\u0b99\u0bcd\u0b95\u0bc8, \u0ba4\u0bc7\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1, \u0b86\u0bb1\u0bcd\u0bb1\u0bc1 \u0ba8\u0bc0\u0bb0\u0bbf\u0bb2\u0bcd \u0b95\u0bbf\u0b9f\u0ba4\u0bcd\u0ba4\u0bbf\u0baa\u0bcd \u0baa\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf, \u0bb5\u0bc7\u0baa\u0bcd\u0baa\u0bc6\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd \u0ba4\u0bc8\u0bb2\u0bae\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bbf \u0b85\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bb2\u0bcd \u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0bb5\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Varahamihira Brihat Samhita",
            "Kashyapa Silpa Sastra",
            "Traditional Woodcraft Oral Lore"
        ],
        "content": "# Maram-Thernthu-Eduthal: Sacred Timber Selection & Curing\n\nTemple chariot engineering depended entirely upon rigorous dendrological selection and curing of specific hardwood varieties, a specialized science termed maram-thernthu-eduthal.\n\nMaster craftsmen conducted thorough inspections of ancient forests, harvesting only fully mature heartwood trees during the waning moon when sap moisture was at its lowest. Different components required distinct mechanical properties: shock-absorbent, dense Iluppai (Madhuca longifolia) was reserved for wheels and wheel hubs; high-flexural-strength Vengai (Pterocarpus marsupium) and Rosewood for axles and chassis beams; and lightweight, stable Teak (Tectona grandis) for sculpted superstructures.\n\nOnce felled, timber logs underwent extended curing: submerged in flowing riverbeds or temple tanks for up to two years to dissolve sap sugars and tannins, followed by slow atmospheric shade-drying. Finally, the finished timbers were deeply impregnated with boiling infusions of neem, sesame, and pungam oils, rendering the wood immune to fungal decay, dry rot, and wood-boring insects."
    },
    {
        "file": "knowledge/artifacts/artifact-kudam-and-aaram-iron-reinforced-wheel-hubs-and-radial-struts.md",
        "slug": "artifact-kudam-and-aaram-iron-reinforced-wheel-hubs-and-radial-struts",
        "category": "artifact",
        "name_en": "Kudam & Aaram: Cast-Iron Reinforced Wheel Hubs, Bronze Bushings & Radial Struts",
        "name_ta": "\u0b95\u0bc1\u0b9f\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b86\u0bb0\u0bae\u0bcd - \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0bb5\u0bb3\u0bc8\u0baf \u0bae\u0bc8\u0baf\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0bae\u0bcd, \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bbe\u0baf\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b86\u0bb0\u0b95\u0bcd\u0b95\u0bbe\u0bb2\u0bcd \u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bbf\u0b95\u0bb3\u0bcd",
        "era": "Medieval to Modern Era",
        "year_start": 800,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Mechanical wheel naves (kudam) reinforced with shrink-fitted wrought iron hoops, fitted with friction-reducing bronze journal sleeves and radiating hardwood spokes (aaram).",
        "summary_ta": "\u0ba4\u0bc7\u0bb0\u0bcd\u0b9a\u0bcd \u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0bae\u0bc8\u0baf\u0baa\u0bcd \u0baa\u0b95\u0bc1\u0ba4\u0bbf\u0baf\u0bbe\u0ba9 \u0b95\u0bc1\u0b9f\u0bae\u0bcd, \u0b9a\u0bc1\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0bb5\u0bb3\u0bc8\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bcd, \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0ba4\u0bcd \u0ba4\u0bc7\u0baf\u0bcd\u0bae\u0bbe\u0ba9\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bbe\u0baf\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b86\u0bb0\u0b95\u0bcd\u0b95\u0bbe\u0bb2\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Silpa Rathnam Chapter 14",
            "Tiruvarur Inscriptions",
            "Traditional Silpi Treatises"
        ],
        "content": "# Kudam & Aaram: Wheel Hubs & Radial Struts\n\nThe central nave or hub of the temple chariot wheel, known as the kudam, represents one of the most mechanically stressed components in traditional timber engineering, receiving hundreds of tons of concentrated axle loads.\n\nCarved from cylindrical blocks of dense Iluppai rootwood, the kudam was bored with a central axle aperture and reinforced externally with multiple concentric red-hot shrunk wrought-iron collar bands (kudathu-valayam) to counteract splitting forces.\n\nTo eliminate wood-on-metal frictional burning, the central axle bore was lined with a cast bronze journal sleeve bushing (venkala-kuzhai), constantly fed with animal tallow or sesame lubricant. Radiating outward from the hub were dense wooden spokes or mortised structural segments (aaram) that dispersed radial compression forces evenly across the entire rim perimeter."
    },
    {
        "file": "knowledge/places/place-tiruvarur-ancient-monumental-temple-chariot-and-wheelwright-haven.md",
        "slug": "place-tiruvarur-ancient-monumental-temple-chariot-and-wheelwright-haven",
        "category": "place",
        "name_en": "Tiruvarur: Ancient Monumental Temple Chariot, Wheelwrighting & Azhi Ther Haven",
        "name_ta": "\u0ba4\u0bbf\u0bb0\u0bc1\u0bb5\u0bbe\u0bb0\u0bc2\u0bb0\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b86\u0bb4\u0bbf\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd, \u0ba4\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bc1 \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0bb2\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0ba8\u0b95\u0bb0\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Venerable agrarian capital of the Kaveri delta, celebrated throughout civilizational history as the epic home of the colossal 96-foot Tiruvarur Azhi Ther and master chariot silpi guilds.",
        "summary_ta": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0b9f\u0bc6\u0bb2\u0bcd\u0b9f\u0bbe\u0bb5\u0bbf\u0ba9\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bbe\u0bb2\u0baa\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0ba8\u0b95\u0bb0\u0bcd; \u0b89\u0bb2\u0b95\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb4\u0bcd\u0baa\u0bc6\u0bb1\u0bcd\u0bb1 96 \u0b85\u0b9f\u0bbf \u0b89\u0baf\u0bb0 \u0b86\u0bb4\u0bbf\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd, \u0bae\u0bbe\u0b9f\u0bb5\u0bc0\u0ba4\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bc1\u0b95\u0bcd \u0b95\u0bb2\u0bc8\u0b95\u0bcd\u0b95\u0bc1 \u0baa\u0bc1\u0b95\u0bb4\u0bcd\u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Tiruvarur Temple Inscriptions",
            "Tevaram",
            "Periyapuranam"
        ],
        "content": "# Tiruvarur: Monumental Chariot Haven\n\nTiruvarur, nestled in the fertile agrarian heartland of the Kaveri delta, holds an unparalleled position in the cultural and mechanical history of Tamil Nadu as the sovereign capital of sacred temple chariot engineering.\n\nHome to the ancient Sri Vanmikanathar / Thyagarajaswami temple complex, the city's urban plan was specifically engineered around chariot processions: four massive, perfectly leveled, quadrangular avenues (Ratha Veedhi / Mada Veedhi) designed with sufficient width and gentle corners to accommodate the massive sweep of the 300-ton Azhi Ther.\n\nTiruvarur maintained dedicated artisan quarters for the Ratha-Kara guilds, timber storehouses, and rope-spinning grounds, serving as the benchmark standard of mobile temple architecture across South India."
    }
]
EDGES = [
    [
        "concept-ther-thatchu-ancient-tamil-sacred-temple-chariot-architecture-and-woodcraft",
        "GOVERNS",
        "technology-azhi-ther-colossal-multitiered-wooden-processional-car-mechanics",
        "core",
        "Prehistoric to Modern Era",
        "Principles of sacred architecture and modular timber joinery govern the mechanical assembly of the Azhi Ther.",
        "Manasara Silpa Sastra"
    ],
    [
        "technology-azhi-ther-colossal-multitiered-wooden-processional-car-mechanics",
        "UTILIZES",
        "technology-urulai-and-achu-composite-wooden-wheel-and-axle-load-bearing-system",
        "core",
        "Early Medieval to Modern Era",
        "The multi-hundred-ton chariot distributes its colossal rolling weight upon composite wooden wheels and forged axles.",
        "Tiruvarur Temple Manuals"
    ],
    [
        "artifact-ther-vadam-massive-braided-coconut-coir-processional-pull-ropes",
        "PROXIMATE_TO",
        "technology-azhi-ther-colossal-multitiered-wooden-processional-car-mechanics",
        "core",
        "Early Medieval to Modern Era",
        "Monumental coir hauling ropes transmit thousands of kilonewtons of human pulling force to propel the chariot.",
        "Periyapuranam Tiruvarur Charukkam"
    ],
    [
        "technology-aappu-thadukku-wooden-wedge-kinetic-braking-and-steering-chocks",
        "ARRESTS",
        "technology-azhi-ther-colossal-multitiered-wooden-processional-car-mechanics",
        "core",
        "Prehistoric to Modern Era",
        "Hardwood kinetic braking wedges manually arrest the rolling momentum of the advancing chariot.",
        "Tiruvarur Festival Protocols"
    ],
    [
        "text-tevaram-tiruvarur-hymns-on-azhi-ther-processional-grandeur",
        "CELEBRATES",
        "place-tiruvarur-ancient-monumental-temple-chariot-and-wheelwright-haven",
        "core",
        "Medieval Chola Era",
        "Tevaram devotional hymns praise the cosmic splendor and communal ecstasy of Tiruvarur's chariot festival.",
        "Tevaram Tirumurai 7"
    ],
    [
        "institution-ratha-kara-silpi-guild-chariot-wheelwright-and-carpentry-guilds",
        "PRESERVES",
        "concept-ther-thatchu-ancient-tamil-sacred-temple-chariot-architecture-and-woodcraft",
        "core",
        "Early Historic to Modern Era",
        "Artisan guilds transmitted canons of timber selection, joinery, and chariot design across generations.",
        "Uyyakondan Tirumalai Epigraphs"
    ],
    [
        "concept-maram-thernthu-eduthal-sacred-timber-selection-curing-and-oil-tempering",
        "SUPPLIES",
        "technology-urulai-and-achu-composite-wooden-wheel-and-axle-load-bearing-system",
        "core",
        "Prehistoric to Modern Era",
        "Cured, water-soaked, and oil-treated Iluppai and Vengai heartwoods are crafted into indestructible wheels.",
        "Kashyapa Silpa Sastra"
    ],
    [
        "artifact-kudam-and-aaram-iron-reinforced-wheel-hubs-and-radial-struts",
        "INTEGRATES_WITH",
        "technology-urulai-and-achu-composite-wooden-wheel-and-axle-load-bearing-system",
        "core",
        "Medieval to Modern Era",
        "Iron-shrunk wheel hubs, bronze journal sleeve bushings, and radial struts form the core mechanics of the wheel.",
        "Silpa Rathnam Chapter 14"
    ],
    [
        "technology-azhi-ther-colossal-multitiered-wooden-processional-car-mechanics",
        "CENTERED_AT",
        "place-tiruvarur-ancient-monumental-temple-chariot-and-wheelwright-haven",
        "core",
        "Early Medieval to Modern Era",
        "The world-famous colossal 96-foot Azhi Ther is stationed and operated exclusively at Tiruvarur.",
        "Tiruvarur Inscriptions"
    ],
    [
        "institution-ratha-kara-silpi-guild-chariot-wheelwright-and-carpentry-guilds",
        "BASED_AT",
        "place-tiruvarur-ancient-monumental-temple-chariot-and-wheelwright-haven",
        "core",
        "Early Historic to Modern Era",
        "Sovereign master chariot silpi corporations maintained ancestral quarters and workshops at Tiruvarur.",
        "Chola Epigraphs"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Ancient Tamil Temple Chariot Wheelwrighting, Timber Mechanics & Hydraulic Braking into Moolam Chronicles & Life Graph...")

    # Phase 1: Write Markdown Files
    print("\n[Phase 1] Writing 10 Markdown Knowledge Dossiers...")
    for d in DOSSIERS:
        full_path = os.path.join(MOOLAM_KNOWLEDGE, d["file"])
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        print(f"  ✓ Wrote: {d['file']}")

    # Phase 2: PostgreSQL Lore Nodes Upsert
    print(f"\n[Phase 2] Connecting to PostgreSQL at {DB_URL}...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

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
            d["era"], d["year_start"], d["year_end"], d["thinai"],
            d["summary_en"], d["summary_ta"], d["sources"], "core", props
        ))
        nodes_upserted += 1
        print(f"  ✓ Upserted node: {slug}")

    conn.commit()
    print(f"Phase 2 complete: {nodes_upserted} nodes upserted.")

    # Phase 3: PostgreSQL Lore Edges Insertion
    print("\n[Phase 3] Inserting 10 Lore Graph Relationships...")
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
        print(f"  ✓ Linked: ({src}) --[{rel}]--> ({tgt})")

    conn.commit()
    print(f"Phase 3 complete: {edges_inserted} edges processed.")

    # Phase 4: Vector Embeddings
    print("\n[Phase 4] Generating 1024-dim BGE-M3 Embeddings via Ollama...")
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

    print(f"\n🎉 Ancient Tamil Temple Chariot Wheelwrighting, Timber Mechanics & Hydraulic Braking Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
