#!/usr/bin/env python3
# Ingestion harvester for Batch 23 Corpus 3: Clay-Retort Distillation & Aromatic Zymurgy
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
        "file": "knowledge/texts/text-malaipadukadam-aged-bamboo-tube-liquor-and-aromatic-theral-poetry.md",
        "slug": "text-malaipadukadam-aged-bamboo-tube-liquor-and-aromatic-theral-poetry",
        "category": "text",
        "name_en": "Malaipadukadam Verses on Aged Bamboo-Tube Liquor & Aromatic Theral Zymurgy",
        "name_ta": "\u0bae\u0bb2\u0bc8\u0baa\u0b9f\u0bc1\u0b95\u0b9f\u0bbe\u0bae\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd - \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b95\u0bc1\u0bb4\u0bbe\u0baf\u0bcd \u0bae\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd \u0bae\u0ba4\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0ba4\u0bcd \u0ba4\u0bc7\u0bb1\u0bb2\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -200,
        "year_end": 200,
        "thinai": "kurinji",
        "summary_en": "Malaipadukadam lines 170-185 describing Nannan Venman's montane hospitality: intoxicating aromatic liquor (Theral) brewed from wild honey, jackfruit, and rice malt, aged inside hollow bamboo internodes (Ambal) submerged in cool mountain streams.",
        "summary_ta": "\u0ba8\u0ba9\u0bcd\u0ba9\u0ba9\u0bcd \u0b9a\u0bc7\u0baf\u0bcd \u0ba8\u0ba9\u0bcd\u0ba9\u0ba9\u0bbf\u0ba9\u0bcd \u0bae\u0bb2\u0bc8\u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bb5\u0bbf\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bcb\u0bae\u0bcd\u0baa\u0bb2\u0bbf\u0bb2\u0bcd, \u0ba4\u0bc7\u0ba9\u0bcd, \u0baa\u0bb2\u0bbe \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb0\u0bbf\u0b9a\u0bbf \u0bae\u0bc1\u0bb3\u0bc8\u0b95\u0b9f\u0bcd\u0b9f\u0bbf \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b95\u0bc1\u0bb4\u0bbe\u0baf\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b87\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bb2\u0bc8\u0ba8\u0bc0\u0bb0\u0bcb\u0b9f\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bbf\u0ba4\u0bcd\u0ba4 \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0ba4\u0bcd \u0ba4\u0bc7\u0bb1\u0bb2\u0bcd \u0baa\u0bb1\u0bcd\u0bb1\u0bbf\u0baf \u0bae\u0bb2\u0bc8\u0baa\u0b9f\u0bc1\u0b95\u0b9f\u0bbe\u0bae\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Malaipadukadam lines 168-185",
            "Purananuru 24 (on Mattu and Theral)",
            "Sirupanarruppadai lines 235-245"
        ],
        "content": "# Malaipadukadam Verses on Aged Bamboo-Tube Liquor & Aromatic Theral Zymurgy\n\n## The Classical Epic of Montane Sounds & Hospitality\n*Malaipadukadam*, composed by Perunkundrur Perungausikanar in praise of chieftain Nannan Venman of the Naviram mountains (Javadi Hills), contains the most detailed poetic documentation of ancient montane biochemical zymurgy in Tamil literature:\n\n```\n\"\u0ba4\u0bc7\u0ba9\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4\u0bc1 \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4 \u0ba4\u0bc0\u0bae\u0bcd \u0b9a\u0bc1\u0bb5\u0bc8\u0ba4\u0bcd \u0ba4\u0bc7\u0bb1\u0bb2\u0bcd\n\u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0bb5\u0bbf\u0bb3\u0bc8\u0ba8\u0bcd\u0ba4 \u0bae\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0b95\u0bb3\u0bcd\u0bb3\u0bbf\u0ba9\u0bcd\n\u0b86\u0bae\u0bcd\u0baa\u0bb2\u0bcd \u0ba8\u0bbe\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bae\u0bbf\u0bb4\u0bcd\u0ba4\u0bc1\u0b95\u0bca\u0bb3\u0bcd \u0bb5\u0bb2\u0bcd\u0b9a\u0bbf...\"\n\u2014 \u0bae\u0bb2\u0bc8\u0baa\u0b9f\u0bc1\u0b95\u0b9f\u0bbe\u0bae\u0bcd 171-173\n```\n\n## Brewing & Bamboo Maturation (*Moongil-Kuzhai Muthirvu*)\nThe poem portrays a sophisticated fermentation protocol tailored to the cool montane microclimate of Kurinji:\n- **Fermentation Substrate**: Ripe mountain jackfruit (*Palacholai*), comb honey from *Perum-Theen*, and germinated paddy malt mashed in broad earthenware urns.\n- **Microbial Inoculation**: Natural wild yeasts hosted on Mahua (*Madhuca longifolia*) blossoms initiated spontaneous anaerobic fermentation.\n- **Subterranean Stream Aging**: Once initial alcohol conversion ceased, the liquor was decanted into hollow internodes of mature giant mountain bamboo (*Kal-Moongil*), sealed with herbal wax, and buried beside freezing mountain springs. The slow, refrigerated aging mellowed fusel alcohols into fragrant esters reminiscent of water-lilies (*Ambal-Naatram*).\n\n## Social & Ritual Functions\nSuch vintage liquor\u2014termed *Them-pihi* or *Theral*\u2014was offered to bardic troupes (*Kuthar*) and warriors upon reaching mountain citadels, celebrating communal solidarity and enduring endurance.",
        "chunks": [
            {
                "language": "en",
                "title": "Malaipadukadam Bamboo-Aged Theral & Montane Zymurgy",
                "content": "Malaipadukadam verses record the ancient Tamil art of brewing aromatic Theral from honey, jackfruit, and malt, matured inside sealed mountain bamboo tubes submerged in cold springs to develop refined floral bouquets."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0bb2\u0bc8\u0baa\u0b9f\u0bc1\u0b95\u0b9f\u0bbe\u0bae\u0bcd \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0bae\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd \u0ba4\u0bc7\u0bb1\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
                "content": "\u0bae\u0bb2\u0bc8\u0baa\u0b9f\u0bc1\u0b95\u0b9f\u0bbe\u0bae\u0bbf\u0bb2\u0bcd \u0ba8\u0ba9\u0bcd\u0ba9\u0ba9\u0bcd \u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0b95\u0bcd\u0b95\u0bb3\u0bcd \u0baa\u0bb2\u0bbe\u0b9a\u0bcd\u0b9a\u0bc1\u0bb3\u0bc8, \u0ba4\u0bc7\u0ba9\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4\u0bc1 \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b95\u0bc1\u0bb4\u0bbe\u0baf\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b87\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bb2\u0bc8 \u0b85\u0bb0\u0bc1\u0bb5\u0bbf\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b8a\u0bb1\u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bbf\u0ba4\u0bcd\u0ba4 \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0ba4\u0bcd \u0ba4\u0bc7\u0bb1\u0bb2\u0bbf\u0ba9\u0bcd \u0bb5\u0bbf\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bcb\u0bae\u0bcd\u0baa\u0bb2\u0bcd \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0b95\u0bbf\u0bb1\u0ba4\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-double-pot-clay-retort-hydro-distillation-and-vapor-condensation.md",
        "slug": "concept-double-pot-clay-retort-hydro-distillation-and-vapor-condensation",
        "category": "concept",
        "name_en": "Double-Pot Clay Retort Hydro-Distillation & Vapor Condensation Mechanics",
        "name_ta": "\u0b87\u0bb0\u0b9f\u0bcd\u0b9f\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0ba9\u0bc8 \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b86\u0bb5\u0bbf \u0b9a\u0bc1\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bc1\u0ba4\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Early Historic Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "neithal",
        "summary_en": "Early Historic pyrotechnic distillation technology utilizing stacked ceramic retorts, central condenser basins, and cold-water cooling lids to fractionally distill fermented wort into high-proof aromatic spirits (Mattu).",
        "summary_ta": "\u0b95\u0bc0\u0bb4\u0bcd\u0baa\u0bcd\u0baa\u0bbe\u0ba9\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b8a\u0bb1\u0bb2\u0bcd \u0b95\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf, \u0ba8\u0b9f\u0bc1\u0bb5\u0bbf\u0bb2\u0bcd \u0bb5\u0b9f\u0bbf\u0baf\u0bc1\u0bae\u0bcd \u0b86\u0bb5\u0bbf\u0baf\u0bc8\u0b9a\u0bcd \u0b9a\u0bc7\u0b95\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1, \u0bae\u0bc7\u0bb2\u0bcd\u0baa\u0bbe\u0ba9\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0bb3\u0bbf\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4 \u0ba8\u0bc0\u0bb0\u0bbe\u0bb2\u0bcd \u0b9a\u0bc1\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0b9a\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0ba4\u0bc1 \u0bb5\u0bc0\u0bb0\u0bbf\u0baf\u0bae\u0bbf\u0b95\u0bcd\u0b95 \u0bae\u0b9f\u0bcd\u0b9f\u0bc1 \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Purananuru 56 lines 15-22",
            "Excavations at Arikamedu Distillation Apparatus",
            "History of Indigenous Chemical Technology in South Asia"
        ],
        "content": "# Double-Pot Clay Retort Hydro-Distillation & Vapor Condensation Mechanics\n\n## Archaeological Evidence of Distillation Retorts\nExcavations at port sites such as Arikamedu and Alagankulam have yielded unique ceramic assemblies dating to the 2nd century BCE to 2nd century CE: perforated terracotta diaphragms, deep receiver bowls, and curved condensing lids matching classical Indian descriptions of the *Chullika-Yantra* (double-pot still).\n\n## The Tri-Chamber Condensation Apparatus\nThe indigenous distillation system operated on counter-current condensation thermodynamics:\n1. **Boiler Chamber (*Adip-Paanai*)**: The lowest earthenware urn containing fermented fruit or grain wash, placed directly over a controlled charcoal hearth at 80\u201390 \u00b0C.\n2. **Collector Basin (*Edai-Kinnam*)**: Suspended above the boiling wash on a perforated ceramic collar, designed to capture condensing distillate without allowing it to drip back into the boiling mash.\n3. **Cooling Condenser Lid (*Mael-Kuzhi Paanai*)**: A concave terracotta dish placed atop the apparatus filled with continuously replenished cold water.\n\n## Condensation Thermodynamics\n$$\\text{Alcoholic Vapor} \\xrightarrow{\\text{Cold Dish Contact}} \\text{High-Proof Condensate Drops} \\rightarrow \\text{Collector Basin}$$\nAs ethanol vapor rose from the boiler, it contacted the ice-cold underside of the water-filled upper dish, rapidly condensing into droplets that rolled down the apex into the central collection basin. This yielded concentrated liquor known in Sangam Tamil as *Mattu* (\u0bae\u0b9f\u0bcd\u0b9f\u0bc1) or *Kallin Theeravu*, with alcohol concentrations reaching 30% to 40% ABV.",
        "chunks": [
            {
                "language": "en",
                "title": "Double-Pot Ceramic Retort Distillation Thermodynamics",
                "content": "Archaeological finds at Arikamedu and Alagankulam demonstrate that ancient Tamils operated three-tiered ceramic distillation stills, using cold-water dish condensers to distill fermented mash into concentrated spirits."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b87\u0bb0\u0b9f\u0bcd\u0b9f\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0ba9\u0bc8 \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bb5\u0bc7\u0ba4\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
                "content": "\u0b85\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bae\u0bc7\u0b9f\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb4\u0b95\u0ba9\u0bcd\u0b95\u0bc1\u0bb3\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b95\u0ba3\u0bcd\u0b9f\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd, \u0ba8\u0bc0\u0bb0\u0bbe\u0bb5\u0bbf\u0baf\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0bb3\u0bbf\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4 \u0bae\u0bc7\u0bb2\u0bcd \u0baa\u0bbe\u0ba4\u0bcd\u0ba4\u0bbf\u0bb0\u0ba4\u0bcd\u0ba4\u0bbe\u0bb2\u0bcd \u0b9a\u0bc1\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf \u0bb5\u0bc0\u0bb0\u0bbf\u0baf\u0bae\u0bbf\u0b95\u0bcd\u0b95 \u0bae\u0b9f\u0bcd\u0b9f\u0bc1 \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4 \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bc8 \u0ba8\u0bbf\u0bb0\u0bc2\u0baa\u0bbf\u0b95\u0bcd\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-madhuca-longifolia-iluppai-flower-and-wild-honey-fermentation-zymurgy.md",
        "slug": "concept-madhuca-longifolia-iluppai-flower-and-wild-honey-fermentation-zymurgy",
        "category": "concept",
        "name_en": "Madhuca Longifolia (Iluppai) Flower & Wild Honey Fermentation Zymurgy",
        "name_ta": "\u0b87\u0bb2\u0bc1\u0baa\u0bcd\u0baa\u0bc8\u0baa\u0bcd \u0baa\u0bc2 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0ba4\u0bcd \u0ba4\u0bc7\u0ba9\u0bcd \u0ba8\u0bca\u0ba4\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0b89\u0baf\u0bbf\u0bb0\u0bcd\u0bb5\u0bc7\u0ba4\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "kurinji",
        "summary_en": "Biochemical process of fermenting sucrose- and fructose-rich corollas of the Mahua tree (Madhuca longifolia / Iluppai) combined with cliff honey (Malaithen) using wild Saccharomyces strains to brew aromatic Sangam mead.",
        "summary_ta": "\u0b87\u0ba9\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bbf\u0bb1\u0bc8\u0ba8\u0bcd\u0ba4 \u0b87\u0bb2\u0bc1\u0baa\u0bcd\u0baa\u0bc8\u0baa\u0bcd \u0baa\u0bc2\u0b95\u0bcd\u0b95\u0bb3\u0bc8 \u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0ba4\u0bcd \u0ba4\u0bc7\u0ba9\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0b95\u0bb3\u0bc1\u0b9f\u0ba9\u0bcd \u0b9a\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0b87\u0baf\u0bb1\u0bcd\u0b95\u0bc8\u0baf\u0bbe\u0ba9 \u0b88\u0bb8\u0bcd\u0b9f\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0ba8\u0bca\u0ba4\u0bbf\u0b95\u0bcd\u0b95 \u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0bae\u0bbf\u0b95\u0bcd\u0b95 \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2 \u0bae\u0ba4\u0bc1 \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Purananuru 392",
            "Perumpanarruppadai lines 275-285",
            "Ethnobotany of South Indian Forest Brewing Traditions"
        ],
        "content": "# Madhuca Longifolia (Iluppai) Flower & Wild Honey Fermentation Zymurgy\n\n## The Sacred Nectar of Iluppai Corollas\nIn ancient Tamil dry forests and montane foot-slopes, the deciduous *Iluppai* tree (*Madhuca longifolia*) produced fleshy, cream-colored floral corollas that fell at dawn like sweet rain. These blossoms contained extraordinarily high sugar concentrations\u2014up to 65% invert sugars by dry weight:\n\n- **Sugar Profile**: Rich in fructose and glucose that required no malting or enzymatic breakdown to ferment.\n- **Aromatic Esters**: Natural terpenes and essential oils providing a distinct musk-like bouquet.\n\n## Honey-Assisted Fermentation Matrix\nTo initiate fermentation:\n1. **Collection & Sun-Washing**: Freshly dropped Iluppai flowers were collected at dawn on woven mats and lightly sun-cured to concentrate juices.\n2. **Honey Synergism**: Cliff-honey (*Kurinji-Theen*) harvested by indigenous Kadar and Veddar tribes was blended into the mash, enriching yeast nutrients with trace pollen, minerals, and wild yeasts.\n3. **Clay Fermentation Urns (*Kalam*)**: The mash was sealed inside unglazed, smoke-sterilized earthenware urns buried neck-deep in red loam to maintain a stable 25 \u00b0C fermentation zone.\n\n## Zymurgical Kinetics\nOver 7 to 14 days, wild epiphytic yeasts converted the sugars into ethanol and aromatic secondary metabolites:\n$$\\text{C}_6\\text{H}_{12}\\text{O}_6 \\xrightarrow{\\text{Wild Yeasts}} 2\\text{C}_2\\text{H}_5\\text{OH} + 2\\text{CO}_2$$\nThe resulting beverage was golden-amber, sweetly intoxicating, and praised in *Perumpanarruppadai* as the premier hospitality drink of forest chieftains.",
        "chunks": [
            {
                "language": "en",
                "title": "Madhuca Flower Sugar Profile & Honey Mead Zymurgy",
                "content": "Ancient Tamil brewers exploited the 65% sugar content of fallen Iluppai flowers blended with wild cliff honey, conducting controlled loam-buried fermentation to produce fragrant floral mead."
            },
            {
                "language": "ta",
                "title": "\u0b87\u0bb2\u0bc1\u0baa\u0bcd\u0baa\u0bc8\u0baa\u0bcd \u0baa\u0bc2 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0ba9\u0bcd \u0ba8\u0bca\u0ba4\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
                "content": "\u0b87\u0baf\u0bb1\u0bcd\u0b95\u0bc8\u0baf\u0bbe\u0ba9 \u0b9a\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb0\u0bc8 \u0ba8\u0bbf\u0bb1\u0bc8\u0ba8\u0bcd\u0ba4 \u0b87\u0bb2\u0bc1\u0baa\u0bcd\u0baa\u0bc8\u0baa\u0bcd \u0baa\u0bc2\u0b95\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bae\u0bb2\u0bc8\u0ba4\u0bcd \u0ba4\u0bc7\u0ba9\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bae\u0ba3\u0bcd\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b87\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0baa\u0bc1\u0ba4\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba8\u0bca\u0ba4\u0bbf\u0b95\u0bcd\u0b95 \u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bae\u0ba4\u0bc1 \u0b9a\u0b99\u0bcd\u0b95 \u0b87\u0bb2\u0b95\u0bcd\u0b95\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0baa\u0bcb\u0bb1\u0bcd\u0bb1\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0b95\u0bbf\u0bb1\u0ba4\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-herbal-arishtam-decoction-and-bark-tannin-maturation-in-terracotta.md",
        "slug": "concept-herbal-arishtam-decoction-and-bark-tannin-maturation-in-terracotta",
        "category": "concept",
        "name_en": "Herbal Arishtam Decoction & Bark Tannin Maturation in Terracotta",
        "name_ta": "\u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8 \u0b85\u0bb0\u0bbf\u0bb7\u0bcd\u0b9f\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0bbf\u0ba8\u0bc0\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc8 \u0b95\u0bbe\u0bb0\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0bc8 \u0bae\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bae\u0bcd",
        "era": "Early Historic to Medieval Era",
        "year_start": -200,
        "year_end": 600,
        "thinai": "mullai",
        "summary_en": "Traditional Siddha and folk pharmaceutical zymurgy formulating self-generating fermented tonics (Arishtam / Asavam) brewed with decocted medicinal barks, Dhataki flowers (Woodfordia fruticosa), and long subterranean amphora storage.",
        "summary_ta": "\u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5 \u0bae\u0bb0\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bcd \u0b95\u0bb7\u0bbe\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0b9f\u0ba9\u0bcd \u0ba4\u0bbe\u0ba4\u0bcd\u0ba4\u0bbf\u0bb0\u0bbf\u0baa\u0bcd \u0baa\u0bc2\u0b95\u0bcd\u0b95\u0bb3\u0bcd \u0b9a\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0ba3\u0bcd\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0baa\u0bc1\u0ba4\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b9a\u0bc1\u0baf-\u0b9a\u0bbe\u0bb0\u0bbe\u0baf \u0b89\u0bb1\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0ba4\u0bcd\u0ba4 \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5 \u0b85\u0bb0\u0bbf\u0bb7\u0bcd\u0b9f \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Agasthiyar Gunavagadam Zymurgy Chapters",
            "Pathitrupathu 42",
            "Traditional Siddha Formularies of Tamil Nadu"
        ],
        "content": "# Herbal Arishtam Decoction & Bark Tannin Maturation in Terracotta\n\n## Medicinal Fermentation in Siddha Lore\nUnlike recreational intoxicants, ancient Tamil physicians developed medicated bio-ferments termed *Arishtams* (\u0b85\u0bb0\u0bbf\u0bb7\u0bcd\u0b9f\u0bae\u0bcd) and *Asavams* (\u0b86\u0b9a\u0bb5\u0bae\u0bcd). These preparations utilized low-level, self-generated alcohol (usually 5% to 10% ABV) as an all-natural preservative and solvent that extracted alcohol-soluble phytochemicals from dense woody barks.\n\n## Formulation Protocols\n1. **Kasayam (Decoction Base)**: Boiling therapeutic barks\u2014such as *Karungali* (Acacia catechu), *Pungam* (Pongamia pinnata), and *Vengai*\u2014in copper vessels until liquid volume reduced to one-fourth.\n2. **Kashaya Sugar Matrix**: Dissolving unrefined palm sugar (*Karupatti*) and sweet dried raisins (*Thiratchai*).\n3. **Bio-Inoculation with Dhataki (*Velampisin / Kattuk-Kanal*)**: Introducing dried flowers of *Woodfordia fruticosa* which carried specialized alcohol-tolerant yeast cultures capable of fermenting astringent tannin solutions.\n\n## Terracotta Micro-Oxygenation\nThe mixture was transferred to porous terracotta amphorae glazed internally with beeswax. Buried underground for 40 to 90 days, the earthenware walls permitted minute, controlled micro-oxygenation that polymerized harsh tannins, transforming bitter bark extracts into smooth, warming medicinal elixirs.",
        "chunks": [
            {
                "language": "en",
                "title": "Siddha Herbal Arishtam Formulation & Terracotta Maturation",
                "content": "Siddha medicinal brewing utilized boiled bark decoctions inoculated with Woodfordia flowers, fermenting inside buried earthenware jars where micro-oxygenation transformed tannins into self-preserving tonics."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0bbf\u0ba4\u0bcd\u0ba4 \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5 \u0b85\u0bb0\u0bbf\u0bb7\u0bcd\u0b9f \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0bae\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bc1\u0bae\u0bcd",
                "content": "\u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5 \u0bae\u0bb0\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bcd \u0b95\u0bb7\u0bbe\u0baf\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0ba4\u0bbe\u0ba4\u0bcd\u0ba4\u0bbf\u0bb0\u0bbf\u0baa\u0bcd \u0baa\u0bc2\u0b95\u0bcd\u0b95\u0bb3\u0bc8 \u0b87\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bbf\u0bb2\u0bb5\u0bb1\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0baa\u0bc1\u0ba4\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0b95\u0bc1\u0bb1\u0bc8\u0ba8\u0bcd\u0ba4 \u0b9a\u0ba4\u0bb5\u0bc0\u0ba4 \u0b9a\u0bc1\u0baf-\u0b9a\u0bbe\u0bb0\u0bbe\u0baf \u0b89\u0bb1\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0ba8\u0bc0\u0ba3\u0bcd\u0b9f \u0b95\u0bbe\u0bb2\u0bae\u0bcd \u0b95\u0bc6\u0b9f\u0bbe\u0ba4 \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8 \u0b85\u0bb0\u0bbf\u0bb7\u0bcd\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-subterranean-amphora-cellar-aging-and-bamboo-internode-storage.md",
        "slug": "concept-subterranean-amphora-cellar-aging-and-bamboo-internode-storage",
        "category": "concept",
        "name_en": "Subterranean Amphora Cellar Aging & Bamboo Internode Storage",
        "name_ta": "\u0ba8\u0bbf\u0bb2\u0bb5\u0bb1\u0bc8\u0baa\u0bcd \u0baa\u0bc1\u0ba4\u0bc8 \u0b9a\u0bbe\u0b9f\u0bbf \u0bae\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b95\u0ba3\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Early Historic Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "neithal",
        "summary_en": "Thermal stabilization engineering in Sangam wineries and taverns, employing buried Mediterranean double-handled amphorae and wax-sealed green bamboo internodes to mature spirits at constant 20-22 \u00b0C without oxidation.",
        "summary_ta": "\u0bae\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0ba4\u0bb0\u0bc8\u0b95\u0bcd\u0b95\u0b9f\u0bb2\u0bcd \u0b9a\u0bbe\u0b9f\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc6\u0bb4\u0bc1\u0b95\u0bc1 \u0baa\u0bc2\u0b9a\u0bbf\u0baf \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b95\u0ba3\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bc8 \u0ba8\u0bbf\u0bb2\u0bb5\u0bb1\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0baa\u0bc1\u0ba4\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, 20 \u0b9f\u0bbf\u0b95\u0bbf\u0bb0\u0bbf \u0bb5\u0bc6\u0baa\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0bae\u0ba4\u0bc1\u0bb5\u0bc8\u0b95\u0bcd \u0b95\u0bc6\u0b9f\u0bbe\u0bae\u0bb2\u0bcd \u0bae\u0bc1\u0ba4\u0bbf\u0bb0\u0b9a\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0ba4 \u0ba4\u0bbf\u0bb0\u0bbe\u0bb5\u0bbf\u0b9f \u0ba8\u0bbf\u0bb2\u0bb5\u0bb1\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbf\u0baf\u0bb2\u0bcd.",
        "sources": [
            "Purananuru 329",
            "Akananuru 157",
            "Archaeological Survey of India Excavations at Alagankulam Amphora Layers"
        ],
        "content": "# Subterranean Amphora Cellar Aging & Bamboo Internode Storage\n\n## Thermal Regulation in Tropical Climates\nA primary challenge confronting ancient Tamil winemakers in the scorching coastal plains of Neithal was runaway acetic acid spoilage (*Acetobacter* blooms) caused by ambient temperatures exceeding 35 \u00b0C. To produce smooth, shelf-stable beverages, vintners turned to sub-surface earth cellars.\n\n## Subterranean Amphora Cellars (*Pudhai-Kalam*)\nExcavations at Alagankulam and Arikamedu revealed vast cellars containing intact double-handled Roman and local pseudo-amphorae buried in rows up to their necks in sand and river silt:\n- **Thermal Inertia**: Earth burial maintained a steady temperature of 20\u201322 \u00b0C year-round, dampening tropical heat spikes.\n- **Resin Sealing (*Keezh-Poosu*)**: Amphora interiors were coated with conifer resin or shellac, preventing alcohol transpiration through porous terracotta walls.\n\n## Bamboo Internode Cask Storage (*Moongil-Kuzhai*)\nIn interior hill tracts, green bamboo culms served as organic aging casks:\n- **Vessel Structure**: A foot-long internode was punctured at one nodal septum, filled with strained liquor, and sealed with melted beeswax and dammar gum.\n- **Micro-Extraction**: Over months of underground storage, the liquor absorbed subtle silica and vanillin compounds from the inner bamboo pith, softening bitter notes into velvety smoothness.",
        "chunks": [
            {
                "language": "en",
                "title": "Subterranean Amphora Cellars & Bamboo Internode Casking",
                "content": "Tamil vintners defeated tropical heat spoilage by burying resin-coated amphorae and wax-sealed bamboo internodes in cool subterranean cellars, maintaining stable temperatures for smooth aging."
            },
            {
                "language": "ta",
                "title": "\u0ba8\u0bbf\u0bb2\u0bb5\u0bb1\u0bc8\u0b9a\u0bcd \u0b9a\u0bbe\u0b9f\u0bbf \u0bae\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b95\u0bc1\u0bb4\u0bbe\u0baf\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bcd",
                "content": "\u0b85\u0bb4\u0b95\u0ba9\u0bcd\u0b95\u0bc1\u0bb3\u0bae\u0bcd \u0ba8\u0bbf\u0bb2\u0bb5\u0bb1\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b89\u0bb0\u0bcb\u0bae \u0b9a\u0bbe\u0b9f\u0bbf\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b95\u0ba3\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0bae\u0ba3\u0bb2\u0bbf\u0bb2\u0bcd \u0baa\u0bc1\u0ba4\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1, \u0bb5\u0bc6\u0baa\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0bae\u0ba4\u0bc1 \u0b95\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0bb5\u0bbf\u0b9f\u0bbe\u0bae\u0bb2\u0bcd 20 \u0b9f\u0bbf\u0b95\u0bbf\u0bb0\u0bbf \u0b95\u0bc1\u0bb3\u0bbf\u0bb0\u0bbf\u0bb2\u0bcd \u0baa\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-alagankulam-mediterranean-amphora-and-distillation-retort-epigraphs.md",
        "slug": "insc-alagankulam-mediterranean-amphora-and-distillation-retort-epigraphs",
        "category": "inscription",
        "name_en": "Alagankulam Mediterranean Amphora & Distillation Retort Epigraphs",
        "name_ta": "\u0b85\u0bb4\u0b95\u0ba9\u0bcd\u0b95\u0bc1\u0bb3\u0bae\u0bcd \u0b89\u0bb0\u0bcb\u0bae \u0b9a\u0bbe\u0b9f\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Early Historic Sangam Era",
        "year_start": -200,
        "year_end": 200,
        "thinai": "neithal",
        "summary_en": "Archaeological discoveries and inscribed graffiti pottery from the Pandya port of Alagankulam, documenting Mediterranean wine imports, local distillation retorts, and bilingual merchant graffiti in Tamil-Brahmi and Greco-Roman scripts.",
        "summary_ta": "\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0bae\u0bbe\u0ba9 \u0b85\u0bb4\u0b95\u0ba9\u0bcd\u0b95\u0bc1\u0bb3\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b95\u0bbf\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4 \u0ba4\u0bae\u0bbf\u0bb4\u0bcd-\u0baa\u0bbf\u0bb0\u0bbe\u0bae\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bbf\u0bb0\u0bc7\u0b95\u0bcd\u0b95-\u0b89\u0bb0\u0bcb\u0bae \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0ba4\u0bcd\u0ba4 \u0bae\u0ba4\u0bc1\u0b9a\u0bcd \u0b9a\u0bbe\u0b9f\u0bbf\u0b95\u0bb3\u0bcd, \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0baa\u0bbe\u0ba9\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0ba3\u0bbf\u0b95 \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Tamil Nadu State Dept of Archaeology: Alagankulam Excavation Reports",
            "P. Shanmugam: Epigraphy of Tamil Maritime Trade",
            "Indian Archaeology - A Review 1991-95"
        ],
        "content": "# Alagankulam Mediterranean Amphora & Distillation Retort Epigraphs\n\n## Port Stratigraphy of Ancient Marungurpattinam\nAlagankulam, situated at the mouth of the Vaigai River near Ramanathapuram, was the premier maritime emporium of the Early Pandyas, celebrated in Sangam texts as *Marungurpattinam*. Stratified archaeological excavations revealed massive quantities of imported foreign ceramics alongside indigenous industrial wares.\n\n## Epigraphical & Ceramic Finds\n1. **Inscribed Rouletted Ware & Amphorae**: Over 500 sherds of Spanish and Italian wine amphorae retaining dried resinous residue, many bearing scratched Tamil-Brahmi personal names such as *'Kadhalan'* and *'Athan-Chathan'*.\n2. **Distillation Retort Shards**: Fragments of perforated terracotta condenser collars and collecting bowls with spouts, identical to apparatus used for fractional spirit distillation.\n3. **Bilingual Maritime Graffiti**: A ceramic shard bearing both Tamil-Brahmi letters and Roman cursive, indicating resident Mediterranean merchants and vintners collaborating with Pandya harbor authorities.\n\n## The Epicurean Exchange\nThese epigraphic finds verify *Purananuru* 56, where poet Nakkirar describes the Pandya king sipping chilled, aromatic foreign wine brought by Western ships (*Yavanar*) in ornate golden flagons, alongside fiery indigenous fermented *Theral*.",
        "chunks": [
            {
                "language": "en",
                "title": "Alagankulam Amphora Epigraphy & Distillation Retorts",
                "content": "Excavations at the Pandya port of Alagankulam uncovered Mediterranean wine amphorae with Tamil-Brahmi graffiti alongside indigenous ceramic distillation retorts, confirming maritime wine trade and distilling."
            },
            {
                "language": "ta",
                "title": "\u0b85\u0bb4\u0b95\u0ba9\u0bcd\u0b95\u0bc1\u0bb3\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0ba4\u0bc1\u0b9a\u0bcd \u0b9a\u0bbe\u0b9f\u0bbf\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0b95\u0bb2\u0b9a\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd",
                "content": "\u0bb5\u0bc8\u0b95\u0bc8 \u0bae\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bbe\u0bb0 \u0b85\u0bb4\u0b95\u0ba9\u0bcd\u0b95\u0bc1\u0bb3\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b95\u0ba3\u0bcd\u0b9f\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b89\u0bb0\u0bcb\u0bae \u0ba4\u0bbf\u0bb0\u0bbe\u0b9f\u0bcd\u0b9a\u0bc8 \u0bae\u0ba4\u0bc1\u0b9a\u0bcd \u0b9a\u0bbe\u0b9f\u0bbf\u0b95\u0bb3\u0bc1\u0bae\u0bcd, \u0ba4\u0bae\u0bbf\u0bb4\u0bcd-\u0baa\u0bbf\u0bb0\u0bbe\u0bae\u0bbf \u0baa\u0bca\u0bb1\u0bbf\u0ba4\u0bcd\u0ba4 \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0baa\u0bbe\u0ba9\u0bc8\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2 \u0bae\u0ba4\u0bc1 \u0bb5\u0ba3\u0bbf\u0b95\u0ba4\u0bcd\u0ba4\u0bc8 \u0b89\u0bb1\u0bc1\u0ba4\u0bbf\u0b9a\u0bc6\u0baf\u0bcd\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-arikamedu-pottery-graffiti-fermented-liquor-guild-charters.md",
        "slug": "insc-arikamedu-pottery-graffiti-fermented-liquor-guild-charters",
        "category": "inscription",
        "name_en": "Arikamedu Pottery Graffiti Fermented Liquor Guild Charters",
        "name_ta": "\u0b85\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bae\u0bc7\u0b9f\u0bc1 \u0bae\u0ba3\u0bcd\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0b95\u0bcd \u0b95\u0bc0\u0bb1\u0bb2\u0bcd \u0bae\u0ba4\u0bc1 \u0bb5\u0ba3\u0bbf\u0b95\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bc1 \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Early Historic Era",
        "year_start": -200,
        "year_end": 100,
        "thinai": "neithal",
        "summary_en": "Tamil-Brahmi potsherd graffiti and merchant tallies excavated at the warehouse quays of Arikamedu (Poduke), identifying commercial vintner guilds (*Kallu-Vaanikar*) and customs duty seals stamped on wine consignments.",
        "summary_ta": "\u0b85\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bae\u0bc7\u0b9f\u0bc1 \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95 \u0baa\u0ba3\u0bcd\u0b9f\u0b95\u0b9a\u0bbe\u0bb2\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bbf\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4 \u0ba4\u0bae\u0bbf\u0bb4\u0bcd-\u0baa\u0bbf\u0bb0\u0bbe\u0bae\u0bbf \u0b95\u0bc0\u0bb1\u0bb2\u0bcd \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bcd, \u0b95\u0bb3\u0bcd \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd \u0b95\u0bc1\u0bb4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0ba4\u0bc1\u0b95\u0bcd \u0b95\u0bca\u0bb3\u0bcd\u0b95\u0bb2\u0ba9\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b87\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b9a\u0bc1\u0b99\u0bcd\u0b95 \u0bb5\u0bb0\u0bbf \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0bb0\u0bc8\u0b95\u0bb3\u0bcd.",
        "sources": [
            "R.E.M. Wheeler: Arikamedu Excavation Report 1946",
            "Vimala Begley: The Ancient Port of Arikamedu",
            "Iravatham Mahadevan: Early Tamil Epigraphy"
        ],
        "content": "# Arikamedu Pottery Graffiti Fermented Liquor Guild Charters\n\n## The Emporium of Poduke\nArikamedu, located on the Ariyankuppam river lagoon 4 km south of Puducherry, was identified by the *Periplus of the Erythraean Sea* and Ptolemy as the major Indo-Roman trading station of *Poduke*. Sir Mortimer Wheeler's pioneering excavations uncovered extensive brick warehouse docks and subterranean wine storage cellars.\n\n## Guild Tallies & Merchant Epigraphy\nTamil-Brahmi graffiti inscribed on Black-and-Red ware jars and imported amphora necks reveal:\n- **Merchant Guild Inscriptions (*Kallu-Vaanikar*)**: Sherds reading *'Valuthi'* and *'Kollan-Kannan'*, identifying licensed distributors managing bonded liquor cellars.\n- **Customs Verification Seals**: Pottery stamps indicating payment of royal port transit duties (*Sungam*) before inland transit along the Pennaiyar river route to Kodumanal.\n- **Condenser Artifacts**: Distinct clay cooling pans and perforated steamer funnels used to enrich local toddy (*Kallu*) into potent distilled liquor for sailors and local chieftains.\n\n## Economic Integration\nThe epigraphical evidence establishes that fermented and distilled liquors were treated as high-value commodities subject to standard quality inspections, standardized volume measures, and state taxation.",
        "chunks": [
            {
                "language": "en",
                "title": "Arikamedu Vintner Guild Epigraphs & Port Wine Warehouses",
                "content": "Archaeological graffiti at Arikamedu identifies licensed vintner guilds (Kallu-Vaanikar) operating bonded warehouses and clay distillation retorts under royal customs supervision."
            },
            {
                "language": "ta",
                "title": "\u0b85\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bae\u0bc7\u0b9f\u0bc1 \u0b95\u0bb3\u0bcd \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0b99\u0bcd\u0b95 \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0bb0\u0bc8\u0b95\u0bb3\u0bc1\u0bae\u0bcd",
                "content": "\u0b85\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bae\u0bc7\u0b9f\u0bc1 \u0b85\u0b95\u0bb4\u0bbe\u0baf\u0bcd\u0bb5\u0bbf\u0bb2\u0bcd \u0b95\u0bbf\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4 \u0ba4\u0bae\u0bbf\u0bb4\u0bcd-\u0baa\u0bbf\u0bb0\u0bbe\u0bae\u0bbf \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bb3\u0bcd \u0bb5\u0ba3\u0bbf\u0b95\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0baa\u0bc6\u0baf\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd, \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95 \u0b9a\u0bc1\u0b99\u0bcd\u0b95 \u0bb5\u0bb0\u0bbf \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0bb0\u0bc8\u0b95\u0bb3\u0bc1\u0bae\u0bcd, \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0b95\u0bb2\u0ba9\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0b86\u0bb5\u0ba3\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0bb3\u0bcd\u0bb3\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-alagankulam-master-aromatic-distiller-mattu-sey-thalaivan.md",
        "slug": "char-alagankulam-master-aromatic-distiller-mattu-sey-thalaivan",
        "category": "character",
        "name_en": "Alagankulam Master Aromatic Distiller Mattu Sey Thalaivan",
        "name_ta": "\u0b85\u0bb4\u0b95\u0ba9\u0bcd\u0b95\u0bc1\u0bb3\u0bae\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bae\u0ba4\u0bc1 \u0bb5\u0b9f\u0bbf\u0baa\u0bcd\u0baa\u0bbe\u0bb3\u0bb0\u0bcd \u0bae\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bc6\u0baf\u0bcd \u0ba4\u0bb2\u0bc8\u0bb5\u0ba9\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "neithal",
        "summary_en": "Persona portraying the elite vintner and chemical pyrotechnician managing ceramic retort battery stills, assessing fermentation hydrometry, and concocting spiced spirits (Mattu) for the royal court of the Pandyas.",
        "summary_ta": "\u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0baa\u0bbe\u0ba9\u0bc8\u0b95\u0bb3\u0bc8 \u0b85\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbf, \u0b8a\u0bb1\u0bb2\u0bcd \u0baa\u0ba4\u0bae\u0bb1\u0bbf\u0ba8\u0bcd\u0ba4\u0bc1, \u0bae\u0bbf\u0bb3\u0b95\u0bc1, \u0b8f\u0bb2\u0bae\u0bcd \u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0bbf\u0baf \u0b89\u0baf\u0bb0\u0bcd\u0ba4\u0bb0 \u0bae\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0ba4\u0bc1\u0bb5\u0bc8 \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf \u0b85\u0bb0\u0b9a\u0bb5\u0bc8\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bae\u0ba4\u0bc1 \u0bb5\u0b9f\u0bbf\u0baa\u0bcd\u0baa\u0bbe\u0bb3\u0bb0\u0bbf\u0ba9\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bc1.",
        "sources": [
            "Purananuru 56",
            "Malaipadukadam 170-185",
            "Siddha Traditional Alchemy & Distillation Texts"
        ],
        "content": "# Alagankulam Master Aromatic Distiller Mattu Sey Thalaivan\n\n## Guild Archetype & Royal Appointment\nOperating in the cosmopolitan riverport of Alagankulam, *Mattu Sey Thalaivan* was a master of biochemical transformation. Appointed by the royal court of Korkai and Madurai, he supervised state wineries producing ceremonial spirits for victory celebrations (*Vettriyattu*).\n\n## Operational Science & Flavor Compounding\n1. **Wash Preparation**: Mashing germinated hill-paddy malt, crushed sugarcane molasses (*Pani-Vellam*), and dried Mahua blossoms in large fermenting vats.\n2. **Temperature Management**: Monitoring the gentle charcoal hearth beneath three-tiered clay stills, keeping the boiler below boiling water temperature ($100^\\circ\\text{C}$) to ensure pure ethanol-ester vapors without burning the wash.\n3. **Botanical Infusions**: Suspending perforated spice bags containing black pepper, cardamom, wild cinnamon bark, and vetiver roots in the path of the rising vapor, infusing the distillate with volatile terpenes.\n\n## Quality Testing\nThe master tested the proof of the distillate by casting droplets onto glowing charcoal: an instantaneous blue flame without smoke confirmed pure *Mattu* fit for royal presentation.",
        "chunks": [
            {
                "language": "en",
                "title": "Master Distiller Operations & Spiced Ethanol Fractionation",
                "content": "The Alagankulam master distiller supervised ceramic retort battery stills, regulating thermal vaporization and infusing rising ethanol vapors with cardamom and pepper to craft royal spiced spirits."
            },
            {
                "language": "ta",
                "title": "\u0b85\u0bb4\u0b95\u0ba9\u0bcd\u0b95\u0bc1\u0bb3\u0bae\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bae\u0b9f\u0bcd\u0b9f\u0bc1 \u0bb5\u0b9f\u0bbf\u0baa\u0bcd\u0baa\u0bbe\u0bb3\u0bb0\u0bbf\u0ba9\u0bcd \u0b85\u0bb1\u0bbf\u0bb5\u0bbf\u0baf\u0bb2\u0bcd",
                "content": "\u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b95\u0bb2\u0b9a\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0ba4\u0ba3\u0bb2\u0bcd \u0b85\u0ba9\u0bb2\u0bc8\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf, \u0b8f\u0bb2\u0b95\u0bcd\u0b95\u0bbe\u0baf\u0bcd, \u0bae\u0bbf\u0bb3\u0b95\u0bc1 \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0bae\u0bcd \u0b9a\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba8\u0bc0\u0bb2\u0b9a\u0bcd\u0b9a\u0bc1\u0b9f\u0bb0\u0bbf\u0bb2\u0bcd \u0b8e\u0bb0\u0bbf\u0baf\u0bc1\u0bae\u0bcd \u0ba4\u0bc2\u0baf \u0bae\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0ba4\u0bc1\u0bb5\u0bc8 \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4 \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bb5\u0b9f\u0bbf\u0baa\u0bcd\u0baa\u0bbe\u0bb3\u0bb0\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-javadi-hills-forest-herbal-fermenter-kattuk-kallu-mooppan.md",
        "slug": "char-javadi-hills-forest-herbal-fermenter-kattuk-kallu-mooppan",
        "category": "character",
        "name_en": "Javadi Hills Forest Herbal Fermenter Kattuk-Kallu Mooppan",
        "name_ta": "\u0b9a\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0bae\u0bb2\u0bc8\u0b95\u0bcd \u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8 \u0bae\u0ba4\u0bc1 \u0bae\u0bc2\u0baa\u0bcd\u0baa\u0ba9\u0bbe\u0bb0\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "kurinji",
        "summary_en": "Persona portraying the indigenous montane elder preserving ancestral knowledge of wild forest ferments, identifying nectar-bearing barks, harvesting cliff-honey, and aging herbal brews inside subterranean bamboo joints.",
        "summary_ta": "\u0b9a\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0bae\u0bb2\u0bc8\u0b95\u0bcd \u0b95\u0bbe\u0b9f\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0ba4\u0bc7\u0ba9\u0bcd, \u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bb0\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc8, \u0b87\u0bb2\u0bc1\u0baa\u0bcd\u0baa\u0bc8\u0baa\u0bcd \u0baa\u0bc2\u0b95\u0bcd\u0b95\u0bb3\u0bc8\u0b9a\u0bcd \u0b9a\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b95\u0ba3\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b87\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bb2\u0bc8\u0ba8\u0bc0\u0bb0\u0bcb\u0b9f\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bae\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0bb0\u0bae\u0bcd\u0baa\u0bb0\u0bbf\u0baf \u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0ba4\u0bc1 \u0bae\u0bc2\u0baa\u0bcd\u0baa\u0ba9\u0bbe\u0bb0\u0bcd.",
        "sources": [
            "Malaipadukadam lines 165-180",
            "Kuruntokai 258",
            "Ethnobotanical Surveys of the Javadi Hills Malayali Tribes"
        ],
        "content": "# Javadi Hills Forest Herbal Fermenter Kattuk-Kallu Mooppan\n\n## Indigenous Forest Lore\nIn the mist-covered peaks of the Javadi range (Naviram mountain), *Kattuk-Kallu Mooppan* lived as the hereditary keeper of botanical fermentation lore. Uninfluenced by urban court fashions, his brewing traditions were deeply entwined with forest ecology and ancestor veneration.\n\n## Gathering & Secret Formulations\n1. **Wild Inoculants**: Gathering dry lichen (*Kal-Paasi*) and crushed wild ginger roots that supplied wild yeasts capable of vigorous cold-temperature fermentation.\n2. **The Bamboo Cache**: Selecting green culms of giant male bamboo (*Kal-Moongil*), scraping internal nodal membranes, and sealing the herbal wash with tree dammar (*Vellai-Kungiliyam*).\n3. **Stream Aging Protocol**: Burying sealed bamboo flasks under river gravel in icy mountain waterfalls for six months, allowing water turbulence and steady chill to refine the liquor.\n\n## Healing & Feasting\nMooppan's aged brew was credited with curing fevers, restoring vigor to fatigued huntsmen, and sanctifying tribal harvest celebrations under the star-lit canopy of the Kurinji hills.",
        "chunks": [
            {
                "language": "en",
                "title": "Montane Herbal Fermentation & Cold Bamboo Aging",
                "content": "The Javadi forest elder utilized wild lichen inoculants and stream-cooled bamboo internodes to ferment potent medicinal brews from cliff-honey and forest barks."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0bae\u0bb2\u0bc8\u0b95\u0bcd \u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8 \u0bae\u0ba4\u0bc1 \u0bae\u0bc2\u0baa\u0bcd\u0baa\u0ba9\u0bbe\u0bb0\u0bcd",
                "content": "\u0baa\u0bbe\u0bb1\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0b9a\u0bbf, \u0bae\u0bb0\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc8, \u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0ba4\u0bcd \u0ba4\u0bc7\u0ba9\u0bcd \u0b86\u0b95\u0bbf\u0baf\u0bb5\u0bb1\u0bcd\u0bb1\u0bc8 \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b95\u0ba3\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b85\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b85\u0bb0\u0bc1\u0bb5\u0bbf \u0ba8\u0bc0\u0bb0\u0b9f\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0baa\u0bc1\u0ba4\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bc1\u0ba4\u0bbf\u0bb0\u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba8\u0bcb\u0baf\u0bcd \u0ba4\u0bc0\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0ba4\u0bc1\u0bb5\u0bc8 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0baa\u0bb4\u0b99\u0bcd\u0b95\u0bc1\u0b9f\u0bbf \u0bae\u0bc2\u0baa\u0bcd\u0baa\u0ba9\u0bbe\u0bb0\u0bbf\u0ba9\u0bcd \u0bae\u0bb0\u0baa\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/places/place-alagankulam-ancient-aromatic-distillation-and-amphora-haven.md",
        "slug": "place-alagankulam-ancient-aromatic-distillation-and-amphora-haven",
        "category": "place",
        "name_en": "Alagankulam: Ancient Aromatic Distillation, Amphora & Maritime Haven",
        "name_ta": "\u0b85\u0bb4\u0b95\u0ba9\u0bcd\u0b95\u0bc1\u0bb3\u0bae\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0ba8\u0bb1\u0bc1\u0bae\u0ba3 \u0bae\u0ba4\u0bc1 \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0bb0\u0bcb\u0bae \u0b9a\u0bbe\u0b9f\u0bbf\u0ba4\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0bae\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -400,
        "year_end": 300,
        "thinai": "neithal",
        "summary_en": "Major Early Historic seaport of the Pandyas at the mouth of the Vaigai River, renowned for massive Mediterranean amphora assemblages, indigenous distillation retorts, and trans-oceanic spice-liquor trade.",
        "summary_ta": "\u0bb5\u0bc8\u0b95\u0bc8 \u0bae\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bbe\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4 \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bbf\u0ba9\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0bae\u0bbe\u0ba9 \u0b85\u0bb4\u0b95\u0ba9\u0bcd\u0b95\u0bc1\u0bb3\u0bae\u0bcd, \u0b89\u0bb0\u0bcb\u0bae \u0bae\u0ba4\u0bc1\u0b9a\u0bcd \u0b9a\u0bbe\u0b9f\u0bbf\u0b95\u0bb3\u0bcd, \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0b89\u0bb2\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bb1\u0bc1\u0bae\u0ba3 \u0bae\u0ba4\u0bc1 \u0bb5\u0ba3\u0bbf\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0ba4\u0bbf\u0b95\u0bb4\u0bcd\u0ba8\u0bcd\u0ba4 \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Purananuru 56",
            "Tamil Nadu State Archaeology Alagankulam Monograph",
            "Ptolemy's Geography (Argari / Marungurpattinam)"
        ],
        "content": "# Alagankulam: Ancient Aromatic Distillation, Amphora & Maritime Haven\n\n## Geographical Setting at the Vaigai Estuary\nAlagankulam ($9.3500^\\circ\\text{ N}, 78.9833^\\circ\\text{ E}$) sits strategically on the northern shore of the Palk Bay, directly at the historic mouth of the sacred Vaigai River. This sheltered estuary allowed Roman, Persian, and Arab dhows to anchor safely within deep estuarine waters sheltered from the rough monsoonal surf of the open Bay of Bengal.\n\n## Port Infrastructure & Wineries\nExcavations over multiple seasons revealed an expansive commercial metropolis:\n- **Terracotta Brick Warehouses**: Substantial paved dock floors and storage godowns containing stratified rows of imported amphorae dating from the 2nd century BCE to the 1st century CE.\n- **Distillery Quarters**: Continuous layers of burnt charcoal, ash pits, perforated ceramic diaphragms, and condensation vessels confirming extensive domestic production of distilled spirits.\n- **Bilingual Cosmopolitanism**: Hundreds of inscribed potsherds in Tamil-Brahmi, Prakrit, and Latin reflecting a vibrant foreign merchant quarter.\n\n## Maritime Legacy\nAs the ocean outlet for royal wealth from the inland capital of Madurai, Alagankulam was a linchpin of the Indo-Mediterranean luxury trade, exchanging Tamil pearls, beryl, and spiced *Theral* for Mediterranean wine, Roman coinage, and copper flagons.",
        "chunks": [
            {
                "language": "en",
                "title": "Alagankulam Estuarine Harbor & Ancient Industrial Distillery",
                "content": "Situated at the mouth of the Vaigai, ancient Alagankulam served as the chief Pandya port for Roman wine imports and domestic ceramic retort distillation, connecting maritime commerce with the Madurai court."
            },
            {
                "language": "ta",
                "title": "\u0b85\u0bb4\u0b95\u0ba9\u0bcd\u0b95\u0bc1\u0bb3\u0bae\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0bae\u0bc1\u0bae\u0bcd \u0ba8\u0bb1\u0bc1\u0bae\u0ba3 \u0bae\u0ba4\u0bc1 \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0ba4\u0bb3\u0bae\u0bc1\u0bae\u0bcd",
                "content": "\u0bb5\u0bc8\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b89\u0bb0\u0bcb\u0bae \u0b9a\u0bbe\u0b9f\u0bbf\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0b89\u0bb3\u0bcd\u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0b95\u0bb2\u0b9a\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0ba8\u0bbf\u0bb1\u0bc8\u0ba8\u0bcd\u0ba4 \u0b85\u0bb4\u0b95\u0ba9\u0bcd\u0b95\u0bc1\u0bb3\u0bae\u0bcd, \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2\u0baa\u0bcd \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0baa\u0bc1\u0b95\u0bb4\u0bcd\u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0bae\u0ba4\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb5\u0ba3\u0bbf\u0b95\u0ba4\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0bae\u0bbe\u0b95\u0bc1\u0bae\u0bcd."
            }
        ]
    }
]
EDGES = [
    [
        "text-malaipadukadam-aged-bamboo-tube-liquor-and-aromatic-theral-poetry",
        "contrasts_zymurgy_technique",
        "concept-double-pot-clay-retort-hydro-distillation-and-vapor-condensation",
        "cultural",
        "Sangam Classical Era",
        "Malaipadukadam's aged bamboo-tube liquor and theral verses contrast hill fermentation against the coastal double-pot clay retort distillation craft",
        "Malaipadukadam lines 168-185"
    ],
    [
        "text-malaipadukadam-aged-bamboo-tube-liquor-and-aromatic-theral-poetry",
        "describes_substrate",
        "concept-madhuca-longifolia-iluppai-flower-and-wild-honey-fermentation-zymurgy",
        "cultural",
        "Sangam Classical Era",
        "Malaipadukadam describes the iluppai flower and wild honey substrate fermented by hill dwellers into aromatic liquor",
        "Malaipadukadam lines 168-185; Purananuru 24"
    ],
    [
        "concept-double-pot-clay-retort-hydro-distillation-and-vapor-condensation",
        "excavated_at",
        "place-alagankulam-ancient-aromatic-distillation-and-amphora-haven",
        "technological",
        "Early Historic Era",
        "Double-pot clay retort hydro-distillation and vapor-condensation apparatus recovered from the aromatic distillation layers of Alagankulam",
        "Tamil Nadu State Archaeology Alagankulam Monograph; Excavations at Arikamedu Distillation Apparatus"
    ],
    [
        "concept-madhuca-longifolia-iluppai-flower-and-wild-honey-fermentation-zymurgy",
        "formulated_by",
        "char-javadi-hills-forest-herbal-fermenter-kattuk-kallu-mooppan",
        "social",
        "Sangam Classical Era",
        "Iluppai flower and wild honey zymurgy formulated by the Javadi Hills forest herbal fermenter lineage of the kattuk kallu mooppan",
        "Malaipadukadam lines 165-180; Ethnobotanical Surveys of the Javadi Hills Malayali Tribes"
    ],
    [
        "concept-herbal-arishtam-decoction-and-bark-tannin-maturation-in-terracotta",
        "utilizes_aging",
        "concept-subterranean-amphora-cellar-aging-and-bamboo-internode-storage",
        "chemical",
        "Early Historic to Medieval Era",
        "Herbal arishtam decoctions and bark-tannin maturation relied on subterranean amphora cellar aging and bamboo internode storage for slow tannin polymerisation",
        "Agasthiyar Gunavagadam Zymurgy Chapters; Purananuru 329"
    ],
    [
        "concept-subterranean-amphora-cellar-aging-and-bamboo-internode-storage",
        "discovered_in_cellars",
        "place-alagankulam-ancient-aromatic-distillation-and-amphora-haven",
        "environmental",
        "Early Historic Era",
        "Subterranean amphora cellars and bamboo internode storage vessels discovered in the stratified amphora layers at Alagankulam",
        "Archaeological Survey of India Excavations at Alagankulam Amphora Layers; Akananuru 157"
    ],
    [
        "insc-alagankulam-mediterranean-amphora-and-distillation-retort-epigraphs",
        "unearthed_at",
        "place-alagankulam-ancient-aromatic-distillation-and-amphora-haven",
        "epigraphical",
        "Early Historic Sangam Era",
        "Mediterranean amphora and distillation retort epigraphs unearthed at the Alagankulam port excavation trenches",
        "Tamil Nadu State Dept of Archaeology: Alagankulam Excavation Reports; Indian Archaeology - A Review 1991-95"
    ],
    [
        "insc-arikamedu-pottery-graffiti-fermented-liquor-guild-charters",
        "attests_guild_distillation",
        "concept-double-pot-clay-retort-hydro-distillation-and-vapor-condensation",
        "epigraphical",
        "Early Historic Era",
        "Arikamedu pottery graffiti and fermented liquor guild charters attest organised guild control of double-pot clay retort distillation",
        "R.E.M. Wheeler: Arikamedu Excavation Report 1946; Iravatham Mahadevan: Early Tamil Epigraphy"
    ],
    [
        "char-alagankulam-master-aromatic-distiller-mattu-sey-thalaivan",
        "headquartered_at",
        "place-alagankulam-ancient-aromatic-distillation-and-amphora-haven",
        "social",
        "Sangam Classical Era",
        "The master aromatic distiller mattu sey thalaivan operated his retort workshops and amphora cellars from Alagankulam",
        "Purananuru 56; Malaipadukadam 170-185"
    ],
    [
        "char-javadi-hills-forest-herbal-fermenter-kattuk-kallu-mooppan",
        "exemplified_in",
        "text-malaipadukadam-aged-bamboo-tube-liquor-and-aromatic-theral-poetry",
        "cultural",
        "Sangam Classical Era",
        "The Javadi Hills forest herbal fermenter kattuk kallu mooppan is exemplified in Malaipadukadam's aged bamboo-tube liquor passages",
        "Malaipadukadam lines 165-180; Kuruntokai 258"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 23 Corpus 3: Clay-Retort Distillation & Aromatic Zymurgy into Moolam Chronicles & Life Graph...")

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
                properties = EXCLUDED.properties,
                created_at = NOW();
        """, (
            str(uuid.uuid4()),
            slug,
            d["category"],
            d["name_en"],
            d["name_ta"],
            d["era"],
            d["year_start"],
            d["year_end"],
            d["thinai"],
            d["summary_en"],
            d["summary_ta"],
            d["sources"],
            "historical_proof",
            props
        ))
        nodes_upserted += 1
        print(f"  ✓ Upserted node: {slug}")

    conn.commit()
    print(f"Phase 2 complete: {nodes_upserted} lore nodes upserted.")

    # Phase 3: Relational Cross-Domain Edges
    print(f"\n[Phase 3] Inserting {len(EDGES)} Relational Cross-Domain Edges...")
    edges_inserted = 0
    for edge in EDGES:
        src, rel, tgt, layer, era, desc, evidence = edge
        cur.execute("""
            DELETE FROM lore_edges 
            WHERE source_slug = %s AND target_slug = %s AND relation_type = %s;
        """, (src, tgt, rel))

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

    print(f"\n🎉 Batch 23 Corpus 3: Clay-Retort Distillation & Aromatic Zymurgy Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
