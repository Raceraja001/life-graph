#!/usr/bin/env python3
# Ingestion harvester for Batch 25 Corpus 3: War Drum Membranophones & Barrel Joinery
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
        "file": "knowledge/texts/text-purananuru-royal-war-drum-bed-and-murasu-reverence-poetry.md",
        "slug": "text-purananuru-royal-war-drum-bed-and-murasu-reverence-poetry",
        "category": "text",
        "name_en": "Purananuru Verses on the Royal War Drum Bed, Thunderous Murasu & Sacred Reverence",
        "name_ta": "\u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd - \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0b95\u0b9f\u0bcd\u0b9f\u0bbf\u0bb2\u0bcd, \u0b87\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bb0\u0bb2\u0bcd \u0bb5\u0bc0\u0bb0\u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0ba9\u0bbf\u0ba4 \u0bb5\u0bb4\u0bbf\u0baa\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bc6\u0bb1\u0bbf",
        "era": "Sangam Classical Era",
        "year_start": -200,
        "year_end": 200,
        "thinai": "mullai",
        "summary_en": "Purananuru 50 by Mosikiranar describing the sacred war drum bed (Murasu-Kattil) of the Chera king: an exhausted bard sleeping on the consecrated drum couch draped in tiger skins, spared from execution because the monarch revered poets.",
        "summary_ta": "\u0bae\u0bcb\u0b9a\u0bbf\u0b95\u0bc0\u0bb0\u0ba9\u0bbe\u0bb0\u0bcd \u0baa\u0bbe\u0b9f\u0bbf\u0baf \u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 50-\u0b86\u0bae\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd: \u0b9a\u0bc7\u0bb0 \u0bae\u0ba9\u0bcd\u0ba9\u0ba9\u0bbf\u0ba9\u0bcd \u0baa\u0bc1\u0bb2\u0bbf\u0ba4\u0bcd\u0ba4\u0bcb\u0bb2\u0bcd \u0bb5\u0bbf\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4 \u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bbf\u0bb2\u0bbf\u0bb2\u0bcd \u0b85\u0bb1\u0bbf\u0baf\u0bbe\u0ba4\u0bc1 \u0ba4\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0baa\u0bc1\u0bb2\u0bb5\u0bb0\u0bc8 \u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bbe\u0ba4\u0bc1 \u0b95\u0bb5\u0bb0\u0bbf \u0bb5\u0bc0\u0b9a\u0bbf\u0baf \u0baa\u0bc6\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0ba9\u0bcd\u0bae\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0b9f\u0bbf\u0bae\u0bc1\u0bb4\u0b95\u0bcd\u0b95 \u0bb5\u0bc0\u0bb0\u0bae\u0bc1\u0bb0\u0b9a\u0bbf\u0ba9\u0bcd \u0baa\u0bc1\u0ba9\u0bbf\u0ba4\u0bae\u0bcd.",
        "sources": [
            "Purananuru 50 (Mosikiranar on Cheraman Peruncheral Irumporai)",
            "Pathitrupathu 30",
            "Silappathikaram Kadaladukathai lines 130-145"
        ],
        "content": "# Purananuru Verses on the Royal War Drum Bed, Thunderous Murasu & Sacred Reverence\n\n## The Sacred Sovereignity of the Murasu\nIn the martial ethos of ancient Tamilakam, the royal war drum\u2014the *Veera-Murasu* (\u0bb5\u0bc0\u0bb0\u0bae\u0bc1\u0bb0\u0b9a\u0bc1)\u2014was not an ordinary musical instrument, but the physical embodiment of the state's divine sovereignty, ranking alongside the royal umbrella (*Venkottrak-Kudai*) and scepter (*Sengol*).\n\n```\n\"\u0b95\u0ba3\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bc1 \u0b87\u0bb0\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0b9f\u0bc8 \u0bb5\u0bbf\u0baf\u0ba9\u0bcd \u0b95\u0bb3\u0ba4\u0bcd\u0ba4\u0bc1\n\u0b85\u0ba3\u0bcd\u0ba3\u0bb2\u0bcd \u0baf\u0bbe\u0ba9\u0bc8 \u0b85\u0ba3\u0bbf \u0ba8\u0bc1\u0ba4\u0bb2\u0bcd \u0baa\u0bbe\u0baf\n\u0b87\u0b9f\u0bbf \u0bae\u0bc1\u0bb4\u0b99\u0bcd\u0b95\u0bc1 \u0b95\u0bc1\u0bb0\u0bb2 \u0bb5\u0bc0\u0bb0 \u0bae\u0bc1\u0bb0\u0b9a\u0bc1...\"\n\u2014 \u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 50:1-4\n```\n\nIn *Purananuru* 50, the poet Mosikiranar recounts arriving exhausted at the palace of Cheraman Peruncheral Irumporai. Seeing a luxurious couch covered in swan down and soft tiger skins, the poet fell into a deep slumber\u2014unaware that this was the consecrated bed (*Murasu-Kattil*) where the sacred war drum rested while being taken for ritual bathing. The monarch, finding the poet asleep on the sacred couch, spared his life and gently fanned him with a yak-tail whisk (*Kavari*).\n\n## The Three Sacred Drums of Tamil Monarchs\nTamil statecraft recognized three distinct consecrated drums:\n1. **Veera-Murasu (\u0bb5\u0bc0\u0bb0\u0bae\u0bc1\u0bb0\u0b9a\u0bc1)**: The great battle drum beaten to mobilize armies and declare victory.\n2. **Kodaik-Kural Murasu (\u0b95\u0bca\u0b9f\u0bc8\u0bae\u0bc1\u0bb0\u0b9a\u0bc1)**: Sounded at dawn to announce imperial charity, feeding of poets, and cancellation of debts.\n3. **Makkal-Murasu / Nyaya-Murasu (\u0ba8\u0bbf\u0baf\u0bbe\u0baf\u0bae\u0bc1\u0bb0\u0b9a\u0bc1)**: Sounded at the palace gate to summon petitioners to the king's hall of justice.",
        "chunks": [
            {
                "language": "en",
                "title": "Purananuru Sacred War Drum Bed & Royal Murasu Sovereignty",
                "content": "Purananuru 50 captures the sacred reverence accorded to the Tamil royal war drum (Veera-Murasu), resting on an elevated tiger-skin couch as an embodiment of divine statecraft and military mobilization."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bcd\u0bb1\u0bbf\u0bb2\u0bcd \u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0b9a\u0bc7\u0bb0 \u0bae\u0ba9\u0bcd\u0ba9\u0ba9\u0bcd \u0bae\u0bbe\u0ba3\u0bcd\u0baa\u0bc1\u0bae\u0bcd",
                "content": "\u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 50-\u0bb2\u0bcd \u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bbf\u0bb2\u0bbf\u0bb2\u0bcd \u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4 \u0baa\u0bc1\u0bb2\u0bb5\u0bb0\u0bcd \u0bae\u0bcb\u0b9a\u0bbf\u0b95\u0bc0\u0bb0\u0ba9\u0bbe\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b9a\u0bc7\u0bb0\u0bae\u0bbe\u0ba9\u0bcd \u0b95\u0bb5\u0bb0\u0bbf \u0bb5\u0bc0\u0b9a\u0bbf\u0baf \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bc1\u0bae\u0bcd, \u0b87\u0b9f\u0bbf\u0bae\u0bc1\u0bb4\u0b95\u0bcd\u0b95 \u0bb5\u0bc0\u0bb0\u0bae\u0bc1\u0bb0\u0b9a\u0bbf\u0bb1\u0bcd\u0b95\u0bc1\u0b9a\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0bc1\u0ba9\u0bbf\u0ba4 \u0ba8\u0bc0\u0bb0\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0b9f\u0b99\u0bcd\u0b95\u0bc1\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-resonant-jackfruit-wood-barrel-hollowing-and-acoustic-chambers.md",
        "slug": "concept-resonant-jackfruit-wood-barrel-hollowing-and-acoustic-chambers",
        "category": "concept",
        "name_en": "Resonant Jackfruit Wood Barrel Hollowing & Acoustic Chamber Mechanics",
        "name_ta": "\u0baa\u0bb2\u0bbe \u0bae\u0bb0\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0bc8\u0b9a\u0bb2\u0bcd \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0b89\u0b9f\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b92\u0bb2\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0b8e\u0ba4\u0bbf\u0bb0\u0bca\u0bb2\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Iron Age to Sangam Era",
        "year_start": -400,
        "year_end": 200,
        "thinai": "kurinji",
        "summary_en": "Woodworking mechanics of carving monolithic percussion barrels (*Muzhavu* / *Murasu*) from seasoned Jackfruit tree heartwood (Artocarpus heterophyllus / Pala-maram) and Vengai, hollowing internal parabolic acoustic sound chambers to maximize bass resonance.",
        "summary_ta": "\u0b85\u0b9f\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4 \u0baa\u0bb2\u0bbe \u0bae\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0bb5\u0bc8\u0bb0\u0baa\u0bcd \u0baa\u0b95\u0bc1\u0ba4\u0bbf\u0baf\u0bc8 \u0b89\u0bb3\u0bbf \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b95\u0bc1\u0b9f\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1, \u0baa\u0bbe\u0bb0\u0baa\u0bcb\u0bb2\u0bbf\u0b95\u0bcd \u0bb5\u0bb3\u0bc8\u0bb5\u0bc1 \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0b8e\u0ba4\u0bbf\u0bb0\u0bca\u0bb2\u0bbf\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bbf\u0bb5\u0bc8 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bbf \u0b86\u0bb4\u0bcd\u0ba8\u0bcd\u0ba4 \u0baa\u0bbe\u0bb8\u0bcd \u0b92\u0bb2\u0bbf\u0baf\u0bc8 \u0b8e\u0bb4\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bcd \u0baa\u0bb4\u0b99\u0bcd\u0b95\u0bbe\u0bb2 \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0b89\u0b9f\u0bb2\u0bcd \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Malaipadukadam lines 2-15",
            "Perumpanarruppadai lines 260-270",
            "Acoustic Engineering of Traditional Indian Membranophones"
        ],
        "content": "# Resonant Jackfruit Wood Barrel Hollowing & Acoustic Chamber Mechanics\n\n## Material Selection: The Acoustic Superiority of Jackfruit Wood\nIn traditional Tamil percussion manufacture (*Thol-Karuvi-Akkam*), the primary timber for monumental drum bodies was mature *Pala* (*Artocarpus heterophyllus*):\n- **Cellular Porosity & Acoustic Damping**: Jackfruit heartwood possesses a uniform ring-porous cellular matrix that absorbs harsh high-frequency vibrations while providing warm, sustained lower-mid harmonic resonance.\n- **Resistance to Splintering**: Interlocking grain fibers prevent longitudinal splitting when the drumhead is tightened under multi-ton leather thong tension.\n\n## Parabolic Chamber Hollowing (*Kudai-Vettu*)\n1. **Log Seasoning**: Solid tree trunks were soaked in river mud for six months, then shaded-dried to prevent warping.\n2. **Lathe Turning & Internal Scooping**: Artisans hollowed the internal cavity using curved gouge chisels (*Kudaichal-Uli*).\n3. **Parabolic Acoustic Geometry**: Rather than a straight cylinder, the internal barrel was carved with a bulbous, parabolic profile. Sound waves generated by the drumhead bounced off the curved internal walls, focusing pressure waves downward toward the smaller base aperture, dramatically boosting low-frequency sound projection ($50\\text{ Hz} - 120\\text{ Hz}$).",
        "chunks": [
            {
                "language": "en",
                "title": "Jackfruit Wood Barrel Acoustic Hollowing & Parabolic Geometry",
                "content": "Drum artisans carved monolithic barrels from seasoned Jackfruit heartwood, sculpting internal parabolic chambers that amplified fundamental low-frequency bass resonances across long distances."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bb2\u0bbe \u0bae\u0bb0\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0bc8\u0b9a\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0b8e\u0ba4\u0bbf\u0bb0\u0bca\u0bb2\u0bbf\u0baa\u0bcd\u0baa\u0bbf\u0baf\u0bb2\u0bcd",
                "content": "\u0bb5\u0baf\u0ba4\u0bbe\u0ba9 \u0baa\u0bb2\u0bbe \u0bae\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0b89\u0b9f\u0bcd\u0b95\u0bc1\u0bb4\u0bbf\u0bb5\u0bc8 \u0b89\u0bb3\u0bbf \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0bb5\u0bb3\u0bc8\u0bb5\u0bbe\u0b95\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1, \u0b92\u0bb2\u0bbf \u0b85\u0bb2\u0bc8\u0b95\u0bb3\u0bcd \u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc1 \u0b87\u0b9f\u0bbf\u0bae\u0bc1\u0bb4\u0b95\u0bcd\u0b95 \u0baa\u0bbe\u0bb8\u0bcd \u0b92\u0bb2\u0bbf\u0baf\u0bc8\u0baa\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb5\u0b95\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0b95\u0bb3\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-cured-bullock-hide-tanning-and-twisted-leather-thong-tensioning.md",
        "slug": "concept-cured-bullock-hide-tanning-and-twisted-leather-thong-tensioning",
        "category": "concept",
        "name_en": "Cured Bullock-Hide Tanning & Twisted Leather-Thong Tensioning Mechanics",
        "name_ta": "\u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bcd\u0b9f \u0b8e\u0bb0\u0bc1\u0ba4\u0bc1\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0bb5\u0bbe\u0bb0\u0bcd \u0b87\u0bb4\u0bc1\u0bb5\u0bbf\u0b9a\u0bc8 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Early Historic Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "mullai",
        "summary_en": "Biomechanical tanning protocols curing thick bullock and wild buffalo hides with Acacia bark tannins, scraping membranes to uniform micrometer thickness, and stretching drumheads under cross-braced raw-leather lacing thongs (*Vaar*).",
        "summary_ta": "\u0b95\u0bb0\u0bc1\u0bb5\u0bc7\u0bb2 \u0bae\u0bb0\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc8\u0b9a\u0bcd \u0b9a\u0bbe\u0bb1\u0bcd\u0bb1\u0bbf\u0bb2\u0bcd \u0b8e\u0bb0\u0bc1\u0ba4\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bc6\u0bb0\u0bc1\u0bae\u0bc8\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bcd\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1, \u0b9a\u0bae\u0b9a\u0bcd\u0b9a\u0bc0\u0bb0\u0bbe\u0b95\u0b9a\u0bcd \u0b9a\u0bc0\u0bb5\u0bbf, \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba4\u0bcb\u0bb2\u0bcd \u0bb5\u0bbe\u0bb0\u0bcd\u0b95\u0bb3\u0bbe\u0bb2\u0bcd (\u0bb5\u0bbe\u0bb0\u0bcd) \u0b95\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0b95 \u0b87\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0baa\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0b95\u0bb2\u0bc8.",
        "sources": [
            "Purananuru 386",
            "Mullaippattu lines 50-65",
            "Ethnoarchaeological Leathercraft & Drum Membranology"
        ],
        "content": "# Cured Bullock-Hide Tanning & Twisted Leather-Thong Tensioning Mechanics\n\n## The Tensile Demands of Battlefield Membranophones\nA war drum membrane must withstand violent blows from heavy curved wooden beaters (*Kuru-thadi*) without puncturing or losing tension in humid or rain-soaked campaign conditions.\n\n## Tanning & Membrane Preparation (*Thol-Padan*)\n1. **Hide Selection**: Using the prime dorsal skin of mature fighting bulls or wild gaur (*Kattu-Erumai*), known for dense collagen bundling.\n2. **Vegetable Bark Tanning**: Soaking raw hides in pits filled with crushed bark of *Karuvelam* (*Acacia nilotica*) and *Avaram* (*Senna auriculata*). The botanical tannins cross-linked collagen fibers, rendering the skin waterproof and rot-resistant.\n3. **Wet-Stretching & Shaving (*Varip-Palam*)**: The hydrated hide was stretched across flat timber frames and scraped with crescent knives (*Vaar-kathi*) to achieve uniform thickness across the entire acoustic aperture.\n\n## Multi-Ton Leather Thong Tensioning (*Vaar-Kattu*)\nThick buffalo rawhide was cut in continuous spiral strips, twisted into dense ropes, and laced in zigzag V-patterns between top and bottom hoop rings. Driven wooden wedges (*Kozhai*) hammered under the leather laces increased hoop tension, raising drumhead pitch to an unearthly, battle-ready roar.",
        "chunks": [
            {
                "language": "en",
                "title": "Vegetable Tanned Bullock Hide & Wedge-Tensioned Leather Lacing",
                "content": "War drum makers tanned bullock hides with Acacia tannins for waterproof durability, securing membranes with cross-braced rawhide lacing thongs (Vaar) tuned via hammered wooden wedges."
            },
            {
                "language": "ta",
                "title": "\u0b8e\u0bb0\u0bc1\u0ba4\u0bc1\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bcb\u0bb2\u0bcd \u0bb5\u0bbe\u0bb0\u0bcd \u0b87\u0bb4\u0bc1\u0bb5\u0bbf\u0b9a\u0bc8",
                "content": "\u0b95\u0bb0\u0bc1\u0bb5\u0bc7\u0bb2\u0bae\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc8\u0ba4\u0bcd \u0ba4\u0ba3\u0bcd\u0ba3\u0bc0\u0bb0\u0bbf\u0bb2\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba4\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4 \u0b95\u0bbe\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bc8, \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0ba4\u0bcb\u0bb2\u0bcd \u0bb5\u0bbe\u0bb0\u0bcd\u0b95\u0bb3\u0bbe\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bbf, \u0bae\u0bb0\u0b95\u0bcd \u0b95\u0bc1\u0b9a\u0bcd\u0b9a\u0bbf\u0b95\u0bb3\u0bc8\u0b9a\u0bcd \u0b9a\u0bc6\u0bb0\u0bc1\u0b95\u0bbf \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bbf \u0b85\u0ba4\u0bbf\u0bb0\u0bc1\u0bae\u0bcd \u0bb5\u0b95\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b87\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-black-mineral-paste-tuning-slug-acoustics-maru-on-drumhead.md",
        "slug": "concept-black-mineral-paste-tuning-slug-acoustics-maru-on-drumhead",
        "category": "concept",
        "name_en": "Black Mineral Paste Tuning Slug Acoustics (Maru / Karun-Chanthu) on Drumheads",
        "name_ta": "\u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb4\u0bb5\u0bc1\u0ba4\u0bcd \u0ba4\u0b9f\u0bcd\u0b9f\u0bbf\u0bb2\u0bcd \u0b95\u0bb0\u0bc1\u0b9e\u0bcd\u0b9a\u0bbe\u0ba8\u0bcd\u0ba4\u0bc1 \u0bae\u0bb0\u0bc1 \u0baa\u0bca\u0ba4\u0bbf\u0bb5\u0bc1 \u0b92\u0bb2\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -200,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Acoustic mass-loading technology applying concentric circular layers of black mineral paste (*Maru* / *Karanai* / *Karun-Chanthu*)\u2014formulated from magnetized iron ore dust, boiled rice paste, and plant resin\u2014onto the center of drum membranes to produce tuned harmonic overtones.",
        "summary_ta": "\u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bbe\u0ba4\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0b9f\u0bbf, \u0bb5\u0bc6\u0ba8\u0bcd\u0ba4 \u0b9a\u0bcb\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0b9a\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0baa\u0bcd\u0baa\u0bbf\u0b9a\u0bbf\u0ba9\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4\u0bc1 \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb4\u0bb5\u0bc1\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bbf\u0ba9\u0bcd \u0ba8\u0b9f\u0bc1\u0bb5\u0bbf\u0bb2\u0bcd \u0bb5\u0b9f\u0bcd\u0b9f\u0bae\u0bbe\u0b95\u0baa\u0bcd \u0baa\u0bc2\u0b9a\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0b95\u0bb0\u0bc1\u0b9e\u0bcd\u0b9a\u0bbe\u0ba8\u0bcd\u0ba4\u0bc1 \u0bae\u0bb0\u0bc1, \u0b87\u0bb0\u0bc8\u0b9a\u0bcd\u0b9a\u0bb2\u0bc8 \u0ba8\u0bc0\u0b95\u0bcd\u0b95\u0bbf \u0ba4\u0bc1\u0bb2\u0bcd\u0bb2\u0bbf\u0baf\u0bae\u0bbe\u0ba9 \u0b9a\u0bc1\u0bb0\u0bc1\u0ba4\u0bbf\u0baf\u0bc8\u0ba4\u0bcd \u0ba4\u0bb0\u0bc1\u0bae\u0bcd \u0b92\u0bb2\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0b95\u0bb2\u0bc8.",
        "sources": [
            "Purananuru 386",
            "Malaipadukadam lines 5-10",
            "Acoustics of the Indian Mridangam and Traditional Tuning Pastes (C.V. Raman Studies)"
        ],
        "content": "# Black Mineral Paste Tuning Slug Acoustics (Maru / Karun-Chanthu) on Drumheads\n\n## The Nobel-Prize Physics of Indian Drumhead Acoustics\nA circular stretched membrane natively vibrates with Bessel function modes, producing discordant non-harmonic frequencies ($1.0, 1.59, 2.14, 2.30$). Sir C.V. Raman famously proved that ancient Indian drum makers overcame this mathematical limitation by applying a centered composite mass load\u2014the *Maru* (\u0bae\u0bb0\u0bc1) or *Karun-Chanthu* (\u0b95\u0bb0\u0bc1\u0b9e\u0bcd\u0b9a\u0bbe\u0ba8\u0bcd\u0ba4\u0bc1).\n\n$$\\sigma(r) = \\text{Variable surface density reducing exponentially from center to rim} \\rightarrow \\text{Harmonic Overtones } (f_0, 2f_0, 3f_0, 4f_0)$$\n\n## Composition of Ancient Maru Paste\nIn Sangam texts (*Purananuru* 386, *Malaipadukadam*), this black tuning slug is celebrated as *Man-Pootheetha Muzhavu* (\u0bae\u0ba3\u0bcd\u0baa\u0bc2\u0b9a\u0bbf\u0baf \u0bae\u0bc1\u0bb4\u0bb5\u0bc1):\n1. **Heavy Mineral Filler**: Black magnetite iron sand (*Kanik-Kal thool*) or pulverized manganese ore panned from river gravels.\n2. **Organic Binder**: Starchy glutinous paste of boiled hill-paddy rice (*Kootu-Choru*) and astringent gum of the *Karamaram* tree.\n3. **Application Protocol**: Applied in ultra-thin concentric rings while rubbing with smooth river pebbles, allowing each layer to dry before adding the next.\n\n## Musical & Martial Acoustic Results\nThe loading shifts harmonic overtones into whole-number integer multiples ($1:2:3:4:5$), turning a raw percussive bang into a singing, thunderous pitch audible for leagues across battlefields.",
        "chunks": [
            {
                "language": "en",
                "title": "Maru Black Mineral Tuning Paste & Harmonic Overtones",
                "content": "Sangam drum makers applied concentric circular layers of iron-ore dust and boiled rice paste (Maru / Karun-Chanthu) to drumheads, mass-loading the membrane to transform inharmonic clangs into melodic overtones."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0bc1\u0bb4\u0bb5\u0bc1\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bbf\u0bb2\u0bcd \u0b95\u0bb0\u0bc1\u0b9e\u0bcd\u0b9a\u0bbe\u0ba8\u0bcd\u0ba4\u0bc1 \u0bae\u0bb0\u0bc1 \u0baa\u0bca\u0ba4\u0bbf\u0bb5\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
                "content": "\u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bbe\u0ba4\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0b9f\u0bbf\u0baf\u0bc1\u0bae\u0bcd \u0b9a\u0bcb\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0b9a\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4\u0bc1 \u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bbf\u0ba9\u0bcd \u0ba8\u0b9f\u0bc1\u0bb5\u0bbf\u0bb2\u0bcd \u0baa\u0bc2\u0b9a\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0bc1, \u0b87\u0baf\u0bb1\u0bcd\u0baa\u0bbf\u0baf\u0bb2\u0bcd \u0bb5\u0bbf\u0ba4\u0bbf\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b8f\u0bb1\u0bcd\u0baa \u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb3\u0bc8 \u0b9a\u0bc0\u0bb0\u0bae\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b87\u0b9f\u0bbf \u0baa\u0bcb\u0ba9\u0bcd\u0bb1 \u0b87\u0ba9\u0bbf\u0baf \u0ba8\u0bbe\u0ba4\u0ba4\u0bcd\u0ba4\u0bc8 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bbf\u0baf\u0ba4\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-military-drum-acoustic-wave-propagation-and-battlefield-signals.md",
        "slug": "concept-military-drum-acoustic-wave-propagation-and-battlefield-signals",
        "category": "concept",
        "name_en": "Military Drum Acoustic Wave Propagation & Battlefield Tactical Signals",
        "name_ta": "\u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3 \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0b92\u0bb2\u0bbf \u0baa\u0bb0\u0bb5\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0bb0\u0bbe\u0ba3\u0bc1\u0bb5 \u0b9a\u0bae\u0bbf\u0b95\u0bcd\u0b9e\u0bc8\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Sangam Classical Era",
        "year_start": -200,
        "year_end": 200,
        "thinai": "palai",
        "summary_en": "Acoustic communication systems in Sangam warfare: generating high-decibel infrasonic and low-frequency sonic shock waves (50-100 Hz) that penetrated jungle foliage and terrain relief to broadcast tactical commands across square leagues.",
        "summary_ta": "\u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bbe\u0b9f\u0bc1\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bae\u0bb2\u0bc8\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b8a\u0b9f\u0bc1\u0bb0\u0bc1\u0bb5\u0bbf \u0baa\u0bb2 \u0bae\u0bc8\u0bb2\u0bcd \u0ba4\u0bc2\u0bb0\u0bae\u0bcd \u0b92\u0bb2\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bbe\u0bb4\u0bcd-\u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bc6\u0ba3\u0bcd \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0b92\u0bb2\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0baa\u0b9f\u0bc8 \u0ba8\u0b95\u0bb0\u0bcd\u0bb5\u0bc1, \u0ba4\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbf\u0ba9\u0bcd\u0bb5\u0bbe\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b9a\u0bae\u0bbf\u0b95\u0bcd\u0b9e\u0bc8\u0b95\u0bb3\u0bc8 \u0b85\u0ba9\u0bc1\u0baa\u0bcd\u0baa\u0bbf\u0baf \u0ba4\u0b95\u0bb5\u0bb2\u0bcd \u0ba4\u0bca\u0b9f\u0bb0\u0bcd\u0baa\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Purananuru 270 & 285",
            "Pathitrupathu 68",
            "Studies in Ancient Indian Military Acoustic Communications"
        ],
        "content": "# Military Drum Acoustic Wave Propagation & Battlefield Tactical Signals\n\n## Low-Frequency Atmospheric Propagation\nDuring large-scale military campaigns across rocky Palai and Mullai terrains, visual signals (smoke or banners) were easily obscured by dust clouds and dense deciduous canopy. Ancient commanders relied upon low-frequency acoustic transmission ($50\\text{ Hz} - 100\\text{ Hz}$) generated by monumental *Veera-Murasu*.\n\n$$\\text{Attenuation } \\alpha \\propto f^2 \\rightarrow \\text{Low frequencies suffer minimal atmospheric and canopy attenuation}$$\n\nBecause acoustic absorption by vegetation decreases dramatically with lower frequencies, thunderous war drum beats could propagate 5 to 10 kilometers without losing coherence.\n\n## Tactical Acoustic Codes (*Murasu-Mozhi*)\nSangam armies developed a standardized cadence dictionary:\n- **Padai-Koodu (\u0baa\u0b9f\u0bc8\u0b95\u0bcd\u0b95\u0bc2\u0b9f\u0bc1 - Mobilization)**: Slow, thunderous single beats spaced at five-second intervals summoning scattered divisions to the standard.\n- **Por-Muzhakkam (\u0baa\u0bcb\u0bb0\u0bcd\u0bae\u0bc1\u0bb4\u0b95\u0bcd\u0b95\u0bae\u0bcd - Full Attack Charge)**: Rapid, polyrhythmic rolling beats executed with double curved mallets accelerating infantry velocity.\n- **Kodi-Pinnani (\u0b95\u0bca\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bbf\u0ba9\u0bcd\u0ba9\u0ba3\u0bbf - Orderly Withdrawal)**: High-cadence syncopated taps paired with brass aerophones (*Kombu*) directing tactical rear-guard retreats.",
        "chunks": [
            {
                "language": "en",
                "title": "Battlefield Infrasonic Drum Propagation & Tactical Acoustic Cadences",
                "content": "Sangam military commanders utilized low-frequency acoustic propagation (50-100 Hz) from monumental Veera-Murasu drums to broadcast mobilization, charge, and retreat commands across kilometers of battlefield terrain."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3 \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0b92\u0bb2\u0bbf \u0baa\u0bb0\u0bb5\u0bb2\u0bc1\u0bae\u0bcd \u0baa\u0b9f\u0bc8 \u0b9a\u0bae\u0bbf\u0b95\u0bcd\u0b9e\u0bc8\u0b95\u0bb3\u0bc1\u0bae\u0bcd",
                "content": "\u0b95\u0bbe\u0b9f\u0bc1\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0bb4\u0bc1\u0ba4\u0bbf\u0baa\u0bcd \u0baa\u0bc1\u0baf\u0bb2\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0ba4\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf \u0bae\u0bc8\u0bb2\u0bcd \u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b95\u0bc7\u0b9f\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bbe\u0bb4\u0bcd\u0ba8\u0bcd\u0ba4 \u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bc6\u0ba3\u0bcd \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0b92\u0bb2\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0ba4\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbf\u0ba9\u0bcd\u0bb5\u0bbe\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bb3\u0bc8\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0b9f\u0bc8\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b85\u0ba9\u0bc1\u0baa\u0bcd\u0baa\u0bbf\u0baf \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2 \u0b89\u0ba4\u0bcd\u0ba4\u0bbf."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-thakadoor-athiyaman-war-drum-and-arsenal-epigraphs.md",
        "slug": "insc-thakadoor-athiyaman-war-drum-and-arsenal-epigraphs",
        "category": "inscription",
        "name_en": "Thakadoor Athiyaman War Drum & Royal Arsenal Epigraphs",
        "name_ta": "\u0ba4\u0b95\u0b9f\u0bc2\u0bb0\u0bcd \u0b85\u0ba4\u0bbf\u0baf\u0bae\u0bbe\u0ba9\u0bcd \u0bb5\u0bc0\u0bb0\u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b86\u0baf\u0bc1\u0ba4\u0b95\u0bcd \u0b95\u0bb3 \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Iron Age to Sangam Era",
        "year_start": -200,
        "year_end": 100,
        "thinai": "mullai",
        "summary_en": "Tamil-Brahmi and hero-stone (*Nadukal*) epigraphs from the fortress capital of Thakadoor (Dharmapuri), recording chieftain Athiyaman Neduman Anji's consecrated war drums, ritual armories, and drum-maker endowments.",
        "summary_ta": "\u0ba4\u0b95\u0b9f\u0bc2\u0bb0\u0bcd \u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bc8\u0baa\u0bcd \u0baa\u0b95\u0bc1\u0ba4\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0ba3\u0bcd\u0b9f\u0bb1\u0bbf\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba8\u0b9f\u0bc1\u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bae\u0bbf\u0bb4\u0bcd-\u0baa\u0bbf\u0bb0\u0bbe\u0bae\u0bbf \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd, \u0b85\u0ba4\u0bbf\u0baf\u0bae\u0bbe\u0ba9\u0bcd \u0ba8\u0bc6\u0b9f\u0bc1\u0bae\u0bbe\u0ba9\u0bcd \u0b85\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0bb5\u0bc0\u0bb0\u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0bb5\u0bb4\u0bbf\u0baa\u0bbe\u0b9f\u0bc1, \u0b86\u0baf\u0bc1\u0ba4\u0b95\u0bcd \u0b95\u0bbf\u0b9f\u0b99\u0bcd\u0b95\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0b9a\u0bc6\u0baf\u0bcd\u0ba4 \u0b95\u0bae\u0bcd\u0bae\u0bbe\u0bb3\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Jambai Tamil-Brahmi Inscriptions of Athiyaman",
            "Dharmapuri Hero Stones Epigraphs (State Dept of Archaeology)",
            "Purananuru 87-104 Historical Context"
        ],
        "content": "# Thakadoor Athiyaman War Drum & Royal Arsenal Epigraphs\n\n## The Citadel of Thakadoor\nThakadoor (modern Dharmapuri, $12.1300^\\circ\\text{ N}, 78.1600^\\circ\\text{ E}$) was the fortified redoubt of the Athiyaman dynasty, celebrated in Sangam literature for resisting the combined siege of the Chera monarchs. Positioned on the gateway between the northern Mysore plateau and the Tamil plains, it was a nexus of military metallurgy and martial music.\n\n## Epigraphic Discoveries\n- **Jambai Tamil-Brahmi Inscriptions**: Confirming the imperial title *'Satiyaputo Athiyan Nedumaan Anji'*, attesting his paramountcy.\n- **Hero-Stone Epigraphs (*Murasuk-Katti Nadukal*)**: Excavated memorials in the Dharmapuri valley portraying fallen warriors alongside carved iconography of two-headed war drums, commemorating champions who defended the royal drum corps during night ambushes.\n- **Drum Guild Grants**: Inscriptions recording land allocations (*Murasu-Kaani*) gifted to hereditary percussion founders and leather curriers responsible for outfitting royal military forces.",
        "chunks": [
            {
                "language": "en",
                "title": "Thakadoor Athiyaman War Drum Epigraphy & Hero-Stone Memorials",
                "content": "Tamil-Brahmi and hero-stone epigraphs from Thakadoor document the royal war drums of chieftain Athiyaman Neduman Anji, recording land grants (Murasu-Kaani) given to drum-making guilds."
            },
            {
                "language": "ta",
                "title": "\u0ba4\u0b95\u0b9f\u0bc2\u0bb0\u0bcd \u0b85\u0ba4\u0bbf\u0baf\u0bae\u0bbe\u0ba9\u0bcd \u0bb5\u0bc0\u0bb0\u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0ba8\u0b9f\u0bc1\u0b95\u0bb1\u0bcd \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
                "content": "\u0ba4\u0bb0\u0bc1\u0bae\u0baa\u0bc1\u0bb0\u0bbf \u0b9c\u0bae\u0bcd\u0baa\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0b9f\u0bc1\u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bcd \u0b85\u0ba4\u0bbf\u0baf\u0bae\u0bbe\u0ba9\u0bcd \u0ba8\u0bc6\u0b9f\u0bc1\u0bae\u0bbe\u0ba9\u0bcd \u0b85\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0bb5\u0bc0\u0bb0\u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0baa\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bc8, \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0b95\u0bbe\u0ba4\u0bcd\u0ba4 \u0bb5\u0bc0\u0bb0\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba4\u0bbf\u0baf\u0bbe\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0b95\u0bcd \u0b95\u0bbe\u0ba3\u0bbf \u0ba8\u0bbf\u0bb2\u0b95\u0bcd\u0b95\u0bca\u0b9f\u0bc8\u0b95\u0bb3\u0bc8 \u0b86\u0bb5\u0ba3\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-kodumanal-graffiti-percussion-instrument-and-drum-charters.md",
        "slug": "insc-kodumanal-graffiti-percussion-instrument-and-drum-charters",
        "category": "inscription",
        "name_en": "Kodumanal Graffiti Percussion Instrument & Drum Artifact Epigraphs",
        "name_ta": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bcd \u0b95\u0bc0\u0bb1\u0bb2\u0bcd \u0bae\u0ba3\u0bcd\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bcd \u0b95\u0bb0\u0bc1\u0bb5\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0bb0\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Iron Age to Sangam Era",
        "year_start": -300,
        "year_end": 100,
        "thinai": "mullai",
        "summary_en": "Excavated ceramic graffiti and bronze fittings from Kodumanal depicting barrel drums (*Muzhavu*), tensioning hoops, and Tamil-Brahmi donor names inscribed on ceremonial bell-metal cymbals and drum tuning hammers.",
        "summary_ta": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bcd \u0b85\u0b95\u0bb4\u0bbe\u0baf\u0bcd\u0bb5\u0bbf\u0bb2\u0bcd \u0b95\u0bbf\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4 \u0b95\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0bc1-\u0b9a\u0bbf\u0bb5\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0ba3\u0bcd\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b89\u0bb3\u0bcd\u0bb3 \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb4\u0bb5\u0bc1\u0b95\u0bcd \u0b95\u0bc1\u0bb1\u0bbf\u0baf\u0bc0\u0b9f\u0bc1\u0b95\u0bb3\u0bcd, \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0bb5\u0bb3\u0bc8\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bae\u0bbf\u0bb4\u0bcd-\u0baa\u0bbf\u0bb0\u0bbe\u0bae\u0bbf \u0baa\u0bca\u0bb1\u0bbf\u0ba4\u0bcd\u0ba4 \u0b9a\u0bc1\u0bb0\u0bc1\u0ba4\u0bbf \u0b9a\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bb2\u0bcd\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Excavations at Kodumanal (Tamil Nadu State Dept of Archaeology)",
            "K. Rajan: Early Historic Archaeology of Kongu",
            "Indian Archaeology Review 1989-90"
        ],
        "content": "# Kodumanal Graffiti Percussion Instrument & Drum Artifact Epigraphs\n\n## Kongu Metallurgical Hub of Musical Instruments\nBeyond iron swords and semi-precious carnelian beads, the industrial metropolis of Kodumanal on the Noyyal River manufactured precision musical instrument hardware supplying the courts of Karur and Madurai.\n\n## Archaeological & Epigraphic Yield\n1. **Ceramic Drum Graffiti**: Megalithic Black-and-Red ware vessels incised with barrel-drum motifs displaying distinct cross-laced tension thongs and central circular *Maru* tuning spots.\n2. **Bronze Tensioning Hoops (*Mani-Valaiyam*)**: Excavated cast bronze rings that secured leather drumheads over wooden barrel lips, preventing tension wood collapse.\n3. **Inscribed Tuning Hammers (*Thiruthu-Kuru-thadi*)**: Small bronze and iron hammers bearing short Tamil-Brahmi names (*'Varathan'*, *'Kannan'*), used by master acousticians to tap drum wedges to modulate pitch during royal ceremonies.",
        "chunks": [
            {
                "language": "en",
                "title": "Kodumanal Ceramic Drum Graffiti & Bronze Tuning Hardware",
                "content": "Excavations at Kodumanal revealed pottery graffiti depicting cross-laced drums with Maru tuning spots alongside physical bronze drum hoops and inscribed tuning hammers from the 3rd century BCE."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bcd \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0b95\u0bc0\u0bb1\u0bb2\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0b9a\u0bc1\u0bb0\u0bc1\u0ba4\u0bbf\u0b9a\u0bcd \u0b9a\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bb2\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd",
                "content": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bbf\u0bb2\u0bcd \u0b95\u0bbf\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4 \u0bae\u0ba3\u0bcd\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0b95\u0bcd \u0b95\u0bc0\u0bb1\u0bb2\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bbe\u0ba3\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb4\u0bb5\u0bc1\u0b95\u0bcd \u0b95\u0bc1\u0bb1\u0bbf\u0baf\u0bc0\u0b9f\u0bc1\u0b95\u0bb3\u0bc1\u0bae\u0bcd, \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0bb5\u0bb3\u0bc8\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2 \u0b87\u0b9a\u0bc8\u0b95\u0bcd\u0b95\u0bb0\u0bc1\u0bb5\u0bbf\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bc8 \u0b89\u0bb1\u0bc1\u0ba4\u0bbf\u0b9a\u0bc6\u0baf\u0bcd\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-thakadoor-master-war-drum-artisan-murasu-seivon-kollan.md",
        "slug": "char-thakadoor-master-war-drum-artisan-murasu-seivon-kollan",
        "category": "character",
        "name_en": "Thakadoor Master War Drum Artisan Murasu Seivon Kollan",
        "name_ta": "\u0ba4\u0b95\u0b9f\u0bc2\u0bb0\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bb5\u0bc0\u0bb0\u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0b9a\u0bc6\u0baf\u0bcd\u0bb5\u0bcb\u0ba9\u0bcd \u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0b9a\u0bc6\u0baf\u0bcd\u0bb5\u0bcb\u0ba9\u0bcd \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0ba9\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "mullai",
        "summary_en": "Persona portraying the elite master artisan in the royal armories of Thakadoor, commanding jackfruit wood hollowing, bullock hide curing, and acoustic maru formulation for chieftain Athiyaman's war drums.",
        "summary_ta": "\u0b85\u0ba4\u0bbf\u0baf\u0bae\u0bbe\u0ba9\u0bbf\u0ba9\u0bcd \u0b86\u0baf\u0bc1\u0ba4\u0b95\u0bcd \u0b95\u0bb3\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0baa\u0bb2\u0bbe \u0bae\u0bb0\u0ba4\u0bcd\u0ba4\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1, \u0b95\u0bbe\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bc8\u0baa\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1, \u0b95\u0bb0\u0bc1\u0b9e\u0bcd\u0b9a\u0bbe\u0ba8\u0bcd\u0ba4\u0bc1 \u0bae\u0bb0\u0bc1 \u0baa\u0bca\u0ba4\u0bbf\u0ba8\u0bcd\u0ba4\u0bc1 \u0b87\u0b9f\u0bbf\u0bae\u0bc1\u0bb4\u0b95\u0bcd\u0b95 \u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0b95\u0bb3\u0bc8 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bc8\u0b9e\u0bb0\u0bbf\u0ba9\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bc1.",
        "sources": [
            "Purananuru 50 & 87",
            "Malaipadukadam 2-15",
            "Oral Traditions of Kongu Temple Instrument Makers"
        ],
        "content": "# Thakadoor Master War Drum Artisan Murasu Seivon Kollan\n\n## The Master of the Royal Sovereign Voice\nServing in the citadel armory of Thakadoor, *Murasu Seivon Kollan* was revered as a priest-engineer whose craft gave voice to the kingdom's military resolve. His workshop was surrounded by curing pits, seasoning timber stacks, and iron foundries.\n\n## Art of the War Drum Assembly\n1. **The Tree Selection Ritual**: Seeking centuries-old Jackfruit trees on the hillsides of Kollimalai; offering prayers before felling to ensure the wood spirit entered the drum barrel.\n2. **Membrane Stretching (*Thol-Porppu*)**: Soaking tanned bullock hide in curd and plant resin, stretching it across the barrel mouth with eight pairs of wooden levers until tension reached resonance threshold.\n3. **Applying the Maru**: Grinding magnetized black river iron sand into cooked rice paste; applying concentric circles onto the drum face with agate pebbles until the drum boomed in perfect unison with the palace ceremonial conch.",
        "chunks": [
            {
                "language": "en",
                "title": "Master War Drum Artisan Construction Sequence & Tuning Rituals",
                "content": "At Thakadoor, the master drum maker selected sacred jackfruit logs, lever-stretched tanned bullock membranes, and layered magnetic iron sand Maru pastes to craft Athiyaman's thunderous war drums."
            },
            {
                "language": "ta",
                "title": "\u0ba4\u0b95\u0b9f\u0bc2\u0bb0\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0b9a\u0bc6\u0baf\u0bcd\u0bb5\u0bcb\u0ba9\u0bbf\u0ba9\u0bcd \u0b95\u0bb2\u0bc8\u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
                "content": "\u0baa\u0bb2\u0bbe \u0bae\u0bb0\u0ba4\u0bcd\u0ba4\u0bc8\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1, \u0b95\u0bbe\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bc8 \u0ba8\u0bc6\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bcb\u0bb2\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b87\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bbf, \u0b95\u0bbe\u0ba8\u0bcd\u0ba4 \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0b9f\u0bbf \u0bae\u0bb0\u0bc1 \u0baa\u0bc2\u0b9a\u0bbf \u0b85\u0ba4\u0bbf\u0baf\u0bae\u0bbe\u0ba9\u0bbf\u0ba9\u0bcd \u0b87\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bb0\u0bb2\u0bcd \u0bb5\u0bc0\u0bb0\u0bae\u0bc1\u0bb0\u0b9a\u0bc8 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b86\u0b9a\u0bcd\u0b9a\u0bbe\u0bb0\u0bbf."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-sangam-court-percussion-acoustician-muzhavu-isai-paanan.md",
        "slug": "char-sangam-court-percussion-acoustician-muzhavu-isai-paanan",
        "category": "character",
        "name_en": "Sangam Court Percussion Acoustician Muzhavu Isai Paanan",
        "name_ta": "\u0b9a\u0b99\u0bcd\u0b95 \u0b85\u0bb0\u0b9a\u0bb5\u0bc8 \u0bae\u0bc1\u0bb4\u0bb5\u0bc1 \u0b87\u0b9a\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0ba3\u0ba9\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Persona portraying the elite hereditary bard-percussionist who tuned the Muzhavu barrel drum to vocal pitches, synchronized polyrhythmic meters for court dancers, and accompanied bardic recitations of classical epics.",
        "summary_ta": "\u0b85\u0bb0\u0b9a\u0bb5\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0bae\u0bc1\u0bb4\u0bb5\u0bc1\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bc8 \u0b9a\u0bc1\u0bb0\u0bc1\u0ba4\u0bbf\u0b95\u0bcd\u0b95\u0bc1 \u0b8f\u0bb1\u0bcd\u0baa \u0b87\u0b9a\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0bb5\u0bbf\u0bb1\u0bb2\u0bbf\u0baf\u0bb0\u0bbf\u0ba9\u0bcd \u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bbf\u0baf\u0ba4\u0bcd\u0ba4\u0bbf\u0bb1\u0bcd\u0b95\u0bc1 \u0ba4\u0bbe\u0bb3\u0bae\u0bcd \u0b85\u0bae\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0b9a\u0b99\u0bcd\u0b95\u0baa\u0bcd \u0baa\u0bc1\u0bb2\u0bb5\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b95\u0bb5\u0bbf\u0ba4\u0bc8\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0ba4\u0bbe\u0bb3 \u0ba8\u0baf\u0bae\u0bcd \u0b9a\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b87\u0b9a\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0ba3\u0ba9\u0bcd.",
        "sources": [
            "Silappathikaram Arangetrukathai",
            "Malaipadukadam lines 1-20",
            "Purananuru 386"
        ],
        "content": "# Sangam Court Percussion Acoustician Muzhavu Isai Paanan\n\n## The Master of Rhythmic Ragas\nTraveling between the royal courts of the Cheras, Cholas, and Pandyas, the *Muzhavu Isai Paanan* represented the acoustic virtuosity of Tamil classical performing arts. He carried his beloved *Muzhavu* (barrel drum) inside a padded cotton case (*Urai*).\n\n## Acoustic Tuning Discipline\n- **Moisture Warming**: Warming the drumhead before performance over glowing embers to tension the hide to match the singer's keynote (*Kural* / Sa).\n- **Clay Paste Modulation**: Adjusting a dab of moist clay paste (*Manni*) on the bass drumhead right before stepping onto the stage to deepen the resonant sustain.\n- **Finger Technique (*Kai-Vagai*)**: Striking the drumhead with seven distinct hand positions\u2014slaps, rim strokes, muted bass palms, and finger flutters\u2014generating micro-tonal patterns that mirrored the emotional nuances of Sangam poetry.",
        "chunks": [
            {
                "language": "en",
                "title": "Court Percussionist Acoustician Muzhavu Tuning & Hand Strikes",
                "content": "The Sangam court percussionist tuned the clay-loaded Muzhavu drum over embers to match vocal keynotes, executing intricate rhythmic finger strokes to accompany court dance and epic poetry."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0b99\u0bcd\u0b95 \u0b85\u0bb0\u0b9a\u0bb5\u0bc8 \u0bae\u0bc1\u0bb4\u0bb5\u0bc1 \u0b87\u0b9a\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0ba3\u0ba9\u0bbf\u0ba9\u0bcd \u0b95\u0bc8\u0bb5\u0ba3\u0bcd\u0ba3\u0bae\u0bcd",
                "content": "\u0bae\u0bc1\u0bb4\u0bb5\u0bc1\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bc8 \u0b85\u0ba9\u0bb2\u0bbf\u0bb2\u0bcd \u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bbf \u0b9a\u0bc1\u0bb0\u0bc1\u0ba4\u0bbf \u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0bbf, \u0b95\u0bc8\u0bb5\u0bbf\u0bb0\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0b99\u0bcd\u0b95\u0bb3\u0bbe\u0bb2\u0bcd \u0ba4\u0bbe\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0b8e\u0bb4\u0bc1\u0baa\u0bcd\u0baa\u0bbf, \u0bb5\u0bbf\u0bb1\u0bb2\u0bbf\u0baf\u0bb0\u0bcd \u0b86\u0b9f\u0bcd\u0b9f\u0ba4\u0bcd\u0ba4\u0bbf\u0bb1\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc6\u0bb0\u0bc1\u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0bbf\u0baf \u0b85\u0bb0\u0b9a\u0bb5\u0bc8 \u0b87\u0b9a\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0ba3\u0ba9\u0bbf\u0ba9\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/places/place-thakadoor-ancient-royal-war-drum-and-arsenal-haven.md",
        "slug": "place-thakadoor-ancient-royal-war-drum-and-arsenal-haven",
        "category": "place",
        "name_en": "Thakadoor: Ancient Royal War Drum, Arsenal & Military Citadel Haven",
        "name_ta": "\u0ba4\u0b95\u0b9f\u0bc2\u0bb0\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0bb5\u0bc0\u0bb0\u0bae\u0bc1\u0bb0\u0b9a\u0bc1, \u0b86\u0baf\u0bc1\u0ba4\u0b95\u0bcd \u0b95\u0bb3\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0b9a\u0bb1\u0bc8\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Iron Age to Sangam Era",
        "year_start": -300,
        "year_end": 600,
        "thinai": "mullai",
        "summary_en": "Historic capital citadel of the Athiyaman chieftains (Dharmapuri), famed for impregnable ramparts, martial foundries, royal war-drum sanctuaries (*Murasu-Kattil*), and hero-stone memorials commemorating epic Sangam battles.",
        "summary_ta": "\u0b85\u0ba4\u0bbf\u0baf\u0bae\u0bbe\u0ba9\u0bcd \u0ba8\u0bc6\u0b9f\u0bc1\u0bae\u0bbe\u0ba9\u0bcd \u0b85\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0ba4\u0bcd \u0ba4\u0bb2\u0bc8\u0ba8\u0b95\u0bb0\u0bae\u0bbe\u0ba9 \u0ba4\u0b95\u0b9f\u0bc2\u0bb0\u0bcd (\u0ba4\u0bb0\u0bc1\u0bae\u0baa\u0bc1\u0bb0\u0bbf), \u0baa\u0bc1\u0b95\u0bb4\u0bcd\u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bc8 \u0b85\u0b95\u0bb4\u0bbf\u0b95\u0bb3\u0bcd, \u0b86\u0baf\u0bc1\u0ba4\u0baa\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bb1\u0bc8\u0b95\u0bb3\u0bcd, \u0bb5\u0bc0\u0bb0\u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bbf\u0bb2\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0b9f\u0bc1\u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bcd \u0ba8\u0bbf\u0bb1\u0bc8\u0ba8\u0bcd\u0ba4 \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Purananuru 87-104",
            "Tagadur Yattirai Epic Fragments",
            "Archaeological Survey of India Dharmapuri Fort Surveys"
        ],
        "content": "# Thakadoor: Ancient Royal War Drum, Arsenal & Military Citadel Haven\n\n## Strategic Gateway Topography\nThakadoor ($12.1300^\\circ\\text{ N}, 78.1600^\\circ\\text{ E}$) occupies a strategic defile nestled between the Shevaroy and Melagiri hill ranges on the northwestern plateau of Tamilakam. This natural gateway controlled transit between the fertile plains of the Palar and Kaveri valleys and the Deccan plateau.\n\n## The Epic Citadel of Tagadur Yattirai\nCelebrated in the lost Sangam martial epic *Tagadur Yattirai* and praised by Avvaiyar in *Purananuru*:\n- **Triple-Ringed Ramparts**: Guarded by stone walls and deep ditches where siege engines and arrow slits defended the royal keep.\n- **The Murasu Sanctuary (*Murasuk-Kottam*)**: An elevated stone pavilion where the royal war drum was bathed with holy water, anointed with sandal paste, and garlanded with *Uzhinjai* flowers before campaigns.\n- **Foundry Quarter**: Smelting tuyeres, bloomery slag cakes, and carpenter yards manufacturing chariot wheels, bows, and thunderous drum barrels.\n\n## Hero-Stone Heritage\nThe countryside surrounding Thakadoor boasts the densest concentration of inscribed Sangam and Post-Sangam hero stones (*Nadukal*) in India, preserving the memory of warriors who died defending the drum and cattle herds of the realm.",
        "chunks": [
            {
                "language": "en",
                "title": "Thakadoor Strategic Military Citadel & Murasu Sanctuary Topography",
                "content": "Strategically positioned on the northwestern plateau gateway, ancient Thakadoor (Dharmapuri) housed the impregnable fortress citadel of Athiyaman, featuring royal war-drum sanctuaries and military foundries."
            },
            {
                "language": "ta",
                "title": "\u0ba4\u0b95\u0b9f\u0bc2\u0bb0\u0bcd \u0bb5\u0bc0\u0bb0\u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0b95\u0bcd \u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0baa\u0bc1\u0bb5\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
                "content": "\u0b85\u0ba4\u0bbf\u0baf\u0bae\u0bbe\u0ba9\u0bbf\u0ba9\u0bcd \u0ba4\u0bb2\u0bc8\u0ba8\u0b95\u0bb0\u0bbe\u0ba9 \u0ba4\u0b95\u0b9f\u0bc2\u0bb0\u0bcd, \u0bae\u0bb2\u0bc8\u0ba4\u0bcd\u0ba4\u0bca\u0b9f\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0b9f\u0bc1\u0bb5\u0bc7 \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4 \u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0b95\u0bcd \u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bcd, \u0b86\u0baf\u0bc1\u0ba4 \u0b89\u0bb2\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0b9f\u0bc1\u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bcd \u0ba8\u0bbf\u0bb1\u0bc8\u0ba8\u0bcd\u0ba4 \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bbf\u0b95\u0bcd\u0b95 \u0baa\u0bcb\u0bb0\u0bcd\u0baa\u0bcd \u0baa\u0bbe\u0b9a\u0bb1\u0bc8\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bbe\u0b95\u0bc1\u0bae\u0bcd."
            }
        ]
    }
]
EDGES = [
    [
        "text-purananuru-royal-war-drum-bed-and-murasu-reverence-poetry",
        "canonizes_sacred_murasu",
        "concept-resonant-jackfruit-wood-barrel-hollowing-and-acoustic-chambers",
        "cultural",
        "Sangam Classical Era",
        "Purananuru poetry reveres the consecrated war drum resting on tiger skins.",
        "Purananuru 50"
    ],
    [
        "text-purananuru-royal-war-drum-bed-and-murasu-reverence-poetry",
        "attests_battlefield_acoustics",
        "concept-military-drum-acoustic-wave-propagation-and-battlefield-signals",
        "military",
        "Sangam Classical Era",
        "The verse describes thunderous drumbeats echoing across war zones.",
        "Pathitrupathu 30"
    ],
    [
        "concept-resonant-jackfruit-wood-barrel-hollowing-and-acoustic-chambers",
        "assembled_at",
        "place-thakadoor-ancient-royal-war-drum-and-arsenal-haven",
        "industrial",
        "Iron Age to Sangam Era",
        "Monolithic jackfruit drum barrels were carved at Thakadoor arsenals.",
        "Tagadur Yattirai"
    ],
    [
        "concept-cured-bullock-hide-tanning-and-twisted-leather-thong-tensioning",
        "applied_to_barrel",
        "concept-resonant-jackfruit-wood-barrel-hollowing-and-acoustic-chambers",
        "mechanical",
        "Early Historic Era",
        "Tanned bullock hide was lever-stretched across jackfruit barrels.",
        "Purananuru 386"
    ],
    [
        "concept-black-mineral-paste-tuning-slug-acoustics-maru-on-drumhead",
        "modulates_resonance",
        "concept-resonant-jackfruit-wood-barrel-hollowing-and-acoustic-chambers",
        "acoustic",
        "Sangam Classical Era",
        "The black Maru mineral paste tuned drumhead harmonic overtones.",
        "C.V. Raman Indian Drum Studies"
    ],
    [
        "concept-military-drum-acoustic-wave-propagation-and-battlefield-signals",
        "signaled_from",
        "place-thakadoor-ancient-royal-war-drum-and-arsenal-haven",
        "military",
        "Sangam Classical Era",
        "Athiyaman's commanders broadcast acoustic commands across the Thakadoor defiles.",
        "Purananuru 270"
    ],
    [
        "insc-thakadoor-athiyaman-war-drum-and-arsenal-epigraphs",
        "inscribed_at",
        "place-thakadoor-ancient-royal-war-drum-and-arsenal-haven",
        "epigraphical",
        "Iron Age to Sangam Era",
        "Thakadoor hero-stones commemorate champions defending the royal drum.",
        "Jambai Epigraphs"
    ],
    [
        "insc-kodumanal-graffiti-percussion-instrument-and-drum-charters",
        "documents_drum_hardware",
        "concept-cured-bullock-hide-tanning-and-twisted-leather-thong-tensioning",
        "archaeological",
        "Iron Age to Sangam Era",
        "Kodumanal excavations yielded bronze drum tensioning hoops.",
        "Kodumanal Excavations"
    ],
    [
        "char-thakadoor-master-war-drum-artisan-murasu-seivon-kollan",
        "headquartered_at",
        "place-thakadoor-ancient-royal-war-drum-and-arsenal-haven",
        "guild_membership",
        "Sangam Classical Era",
        "The master drum maker operated in the royal armory of Thakadoor.",
        "Oral History of Kongu Instrument Makers"
    ],
    [
        "char-sangam-court-percussion-acoustician-muzhavu-isai-paanan",
        "tunes_instrument_from",
        "char-thakadoor-master-war-drum-artisan-murasu-seivon-kollan",
        "artistic",
        "Sangam Classical Era",
        "Court acousticians tuned drums crafted by master drum artisans.",
        "Silappathikaram Arangetrukathai"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 25 Corpus 3: War Drum Membranophones & Barrel Joinery into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 25 Corpus 3: War Drum Membranophones & Barrel Joinery Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
