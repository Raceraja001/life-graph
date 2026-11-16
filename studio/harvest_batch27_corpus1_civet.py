#!/usr/bin/env python3
# Ingestion harvester for Batch 27 Corpus 1: Civet Musk, Sandalwood Paste & Sacerdotal Unguents
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
        "file": "knowledge/texts/text-silappathikaram-fragrant-cosmetic-streets-and-javvadu-bazaars.md",
        "slug": "text-silappathikaram-fragrant-cosmetic-streets-and-javvadu-bazaars",
        "category": "text",
        "name_en": "Silappathikaram: Classical Verses on the Fragrant Cosmetic Bazaars & Javvadu Perfumers",
        "name_ta": "\u0b9a\u0bbf\u0bb2\u0baa\u0bcd\u0baa\u0ba4\u0bbf\u0b95\u0bbe\u0bb0\u0bae\u0bcd - \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0baa\u0bcd \u0baa\u0bc2\u0b99\u0bcd\u0b95\u0b9f\u0bc8 \u0bb5\u0bc0\u0ba4\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd",
        "era": "Post-Sangam to Classical Era",
        "year_start": 200,
        "year_end": 500,
        "thinai": "marutham",
        "summary_en": "Ilango Adigal's vivid poetic chronicle in Puhar and Madurai describing bustling merchant streets of the perfumers (Narumanak-Kadaigal), formulating civet musk (Javvadu), sandalwood paste (Santhanam), and aromatic resins.",
        "summary_ta": "\u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0ba4\u0bc1\u0bb0\u0bc8 \u0ba8\u0b95\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b9a\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1, \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9\u0bae\u0bcd, \u0b85\u0b95\u0bbf\u0bb2\u0bcd \u0b89\u0bb3\u0bcd\u0bb3\u0bbf\u0b9f\u0bcd\u0b9f \u0bb5\u0bbe\u0b9a\u0ba9\u0bc8\u0ba4\u0bcd \u0ba4\u0bbf\u0bb0\u0bb5\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0bb5\u0bbf\u0bb1\u0bcd\u0bb1 \u0ba8\u0bb1\u0bc1\u0bae\u0ba3 \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd \u0bb5\u0bc0\u0ba4\u0bbf\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0bb2\u0baa\u0bcd\u0baa\u0ba4\u0bbf\u0b95\u0bbe\u0bb0\u0bae\u0bcd.",
        "sources": [
            "Silappathikaram Indira Vizhavu Oor Edutha Kaathai",
            "Silappathikaram Maduraik Kaandam",
            "Sangam Cosmetic History"
        ],
        "content": "# Silappathikaram: Classical Verses on the Fragrant Cosmetic Bazaars & Javvadu Perfumers\n\n## The Cosmopolitan Aromatics of Puhar & Madurai\nIn the epic *Silappathikaram*, Prince-poet Ilango Adigal provides an opulent sensory portrait of ancient Tamil urban markets. The maritime metropolis of Poompuhar and the inland capital of Madurai maintained dedicated avenues for the perfumers and cosmetic compounders (*Narumanak-Kollan* / *Suva-Vanikar*):\n\n```\n\"\u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bae\u0bc1\u0bae\u0bcd \u0b9a\u0bbe\u0ba8\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bc8\u0baf\u0bc1\u0bae\u0bcd\n\u0bb5\u0ba3\u0bcd\u0ba3\u0bae\u0bc1\u0bae\u0bcd \u0bae\u0bbe\u0bb2\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0ba9\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1 \u0baa\u0bb2\u0bcd\u0b95\u0bcb\u0b9f\u0bbf\n\u0b9a\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0ba8\u0bb1\u0bc1\u0ba8\u0bc6\u0baf\u0bcd \u0b95\u0bae\u0bb4\u0bc1\u0bae\u0bcd \u0bb5\u0bc0\u0ba4\u0bbf\u0b95\u0bb3\u0bcd...\"\n\u2014 \u0b9a\u0bbf\u0bb2\u0baa\u0bcd\u0baa\u0ba4\u0bbf\u0b95\u0bbe\u0bb0\u0bae\u0bcd \u0b87\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0bb5\u0bbf\u0bb4\u0bb5\u0bc2\u0bb0\u0bcd \u0b8e\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4 \u0b95\u0bbe\u0ba4\u0bc8\n```\n\n## Sacerdotal & Courtesan Unguents\nThe text specifies specialized cosmetic preparations: fine sandalwood pastes ground on granitic grinding slabs (*Santhana-Kal*), golden civet pastes (*Javvadu*) scraped from highland forest civet glands, and sweet resinous fumigants (*Dhoopam*) burned during temple rituals and royal nocturnal banquets.",
        "chunks": [
            {
                "language": "en",
                "title": "Silappathikaram Fragrant Streets & Cosmetic Bazaars",
                "content": "Silappathikaram describes bustling aromatic bazaars in Puhar and Madurai selling civet musk, ground sandalwood paste, and fragrant fumigants."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0bbf\u0bb2\u0baa\u0bcd\u0baa\u0ba4\u0bbf\u0b95\u0bbe\u0bb0\u0bae\u0bcd \u0ba8\u0bb1\u0bc1\u0bae\u0ba3 \u0bb5\u0bc0\u0ba4\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0bb5\u0ba3\u0bbf\u0b95\u0bae\u0bcd",
                "content": "\u0baa\u0bc2\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0ba4\u0bc1\u0bb0\u0bc8 \u0ba8\u0bb1\u0bc1\u0bae\u0ba3 \u0b85\u0b99\u0bcd\u0b95\u0bbe\u0b9f\u0bbf \u0bb5\u0bc0\u0ba4\u0bbf\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b9a\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1, \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9\u0bae\u0bcd, \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bc8\u0b95\u0bb3\u0bcd \u0bb5\u0bbf\u0bb1\u0bcd\u0baa\u0ba9\u0bc8 \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0bbe\u0b9f\u0bcd\u0b9a\u0bbf\u0baf\u0bc8 \u0b9a\u0bbf\u0bb2\u0baa\u0bcd\u0baa\u0ba4\u0bbf\u0b95\u0bbe\u0bb0\u0bae\u0bcd \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bbf\u0bb1\u0ba4\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-civet-musk-extraction-and-sacerdotal-aromatic-blending-javvadu.md",
        "slug": "concept-civet-musk-extraction-and-sacerdotal-aromatic-blending-javvadu",
        "category": "concept",
        "name_en": "Civet Musk Secretion Extraction & Sacerdotal Aromatic Blending (Javvadu & Punugu)",
        "name_ta": "\u0baa\u0bc1\u0ba9\u0bc1\u0b95\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb0\u0baa\u0bcd\u0baa\u0bc1 \u0baa\u0bbf\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0bb5\u0bbe\u0b9a\u0ba9\u0bc8\u0ba4\u0bcd \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Sangam to Medieval Era",
        "year_start": -200,
        "year_end": 1200,
        "thinai": "kurinji",
        "summary_en": "Indigenous harvesting of glandular perineal secretions from captive or wild Asian palm civets (Punugu-Poonai) in the Javvadi and Kolli highlands, blended with saffron, camphor, and sandalwood into long-lasting sacerdotal Javvadu perfumes.",
        "summary_ta": "\u0b9c\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0bae\u0bb2\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bb5\u0bbe\u0bb4\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0ba9\u0bc1\u0b95\u0bc1\u0baa\u0bcd \u0baa\u0bc2\u0ba9\u0bc8\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b9a\u0bc1\u0bb0\u0baa\u0bcd\u0baa\u0bbf\u0b95\u0bb3\u0bbf\u0bb2\u0bbf\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0baa\u0bc1\u0ba9\u0bc1\u0b95\u0bc1 \u0b8e\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0b9a\u0bcd\u0b9a\u0bc8\u0b95\u0bcd \u0b95\u0bb1\u0bcd\u0baa\u0bc2\u0bb0\u0ba4\u0bcd\u0ba4\u0bc1\u0b9f\u0ba9\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4\u0bc1 \u0b9a\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0bb2\u0bc8.",
        "sources": [
            "Ethno-Botanical Surveys of Javvadi Hills",
            "Traditional Siddha Cosmetics",
            "Temple Ritual Formularies"
        ],
        "content": "# Civet Musk Secretion Extraction & Sacerdotal Aromatic Blending (Javvadu & Punugu)\n\n## Ecological Harvesting in the Eastern Ghats\nThe forested granitic ridges of the Javvadi and Kolli hills provided the natural habitat for the Asian palm civet and small Indian civet (*Viverricula indica*, known in classical Tamil as *Punugu-Poonai*). Forest tribes (*Malai-Kuravar*) gathered glandular perineal secretions naturally deposited by civets on aromatic resinous trees, or maintained gentle semi-captive enclosures to harvest the oily musk with smooth horn spoons.\n\n## The Chemistry of Javvadu Formulation\nRaw civet musk (*Punugu*), intensely animalic and heavy in civetone cyclic ketones, required delicate aging and fixation. Perfumers compounded it with cooling ground sandalwood oil, green edible camphor (*Pachai-Karpooram*), saffron filaments (*Kungumapoo*), and distilled screw-pine (*Thazhamboo*) essence. The resulting blend, celebrated as *Javvadu*, possessed extraordinary tenacity and warmth on human skin.\n\n## Sacerdotal & Temple Applications\nJavvadu functioned as an indispensable sacred unction across major Chola and Pandya sanctums, applied onto stone deities (*Thirumeni*) to preserve sacred stone surfaces while scenting inner sanctum ambiances with eternal fragrance.",
        "chunks": [
            {
                "language": "en",
                "title": "Civet Musk Secretion & Sacerdotal Javvadu Blending",
                "content": "Harvesting glandular civet secretions in the Javvadi hills and blending them with sandalwood and camphor formed the sacred Javvadu temple unguent."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bc1\u0ba9\u0bc1\u0b95\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb0\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0ba8\u0bb1\u0bc1\u0bae\u0ba3 \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8",
                "content": "\u0baa\u0bc1\u0ba9\u0bc1\u0b95\u0bc1\u0baa\u0bcd \u0baa\u0bc2\u0ba9\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0b9a\u0bcd \u0b9a\u0bc1\u0bb0\u0baa\u0bcd\u0baa\u0bc8 \u0b8e\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9\u0ba4\u0bcd\u0ba4\u0bc1\u0b9f\u0ba9\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4\u0bc1 \u0ba4\u0bc6\u0baf\u0bcd\u0bb5\u0bc0\u0b95 \u0b9a\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0ba4\u0bc8\u0bb2\u0bae\u0bbe\u0b95 \u0bae\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bb4\u0b99\u0bcd\u0b95\u0bbe\u0bb2\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-sandalwood-heartwood-stone-mortaring-and-cooling-paste-santhanam.md",
        "slug": "concept-sandalwood-heartwood-stone-mortaring-and-cooling-paste-santhanam",
        "category": "concept",
        "name_en": "Sandalwood Heartwood Stone Mortaring & Cooling Paste Therapeutics (Santhanam)",
        "name_ta": "\u0b9a\u0ba8\u0bcd\u0ba4\u0ba9\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc8 \u0b89\u0bb0\u0bc8\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0bb3\u0bbf\u0bb0\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1 \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bae\u0bcd",
        "era": "Sangam Era (c. 300 BCE \u2013 300 CE)",
        "year_start": -300,
        "year_end": 300,
        "thinai": "kurinji",
        "summary_en": "Mechanical circular mortaring of seasoned Santalum album heartwood billets against wet rough-grained granite grinding slabs (Santhana-Kal), producing fragrant cooling micro-emulsions applied for somatic thermoregulation.",
        "summary_ta": "\u0bae\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4 \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bc8 \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb2\u0bbf\u0bb2\u0bcd \u0ba8\u0bc0\u0bb0\u0bcd\u0bb5\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1 \u0b89\u0bb0\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b89\u0b9f\u0bb2\u0bcd \u0b89\u0bb7\u0bcd\u0ba3\u0ba4\u0bcd\u0ba4\u0bc8\u0ba4\u0bcd \u0ba4\u0ba3\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bae\u0bcd\u0baa\u0bc8 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Purananuru References to Santhanam",
            "Siddha Materia Medica",
            "Ancient Dravidian Hygiene"
        ],
        "content": "# Sandalwood Heartwood Stone Mortaring & Cooling Paste Therapeutics (Santhanam)\n\n## Sacred Heartwood of the Southern Mountains\nWhite sandalwood (*Santalum album*, indigenous *Ven-Santhanam*) grew abundantly across the mist-shrouded Western Ghats and Javvadi ranges. Matured trees aged over thirty years developed dense, oil-rich dark heartwood packed with santalol sesquiterpenes.\n\n## Rotary Water Grinding on Santhana-Kal\nPreparing the therapeutic paste required a specialized planar or dish-shaped granite stone (*Santhana-Kal*) dressed with a slightly roughened grain. The artisan dipped the end of the sandalwood billet into fresh cold water or rose water (*Panneer*) and executed continuous firm circular strokes. The shear friction liberated an ultra-smooth, creamy golden emulsion.\n\n## Somatic Thermoregulation & Social Etiquette\nIn the blistering tropical climate of Tamilakam, anointing the chest, neck, and forehead with chilled sandalwood paste provided profound evaporative cooling and anti-inflammatory relief. Heroic warriors smoothed it over their scarred battle chests before entering council halls.",
        "chunks": [
            {
                "language": "en",
                "title": "Sandalwood Heartwood Grinding & Cooling Santhanam Paste",
                "content": "Circular friction grinding of aged sandalwood heartwood on wet granite slabs produced cooling, aromatic emulsions for thermoregulation and adornment."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0ba8\u0bcd\u0ba4\u0ba9\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc8 \u0b89\u0bb0\u0bc8\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0b95\u0bcd \u0b95\u0bc1\u0bb3\u0bbf\u0bb0\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf \u0bae\u0bc1\u0bb1\u0bc8",
                "content": "\u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd\u0bb2\u0bbf\u0bb2\u0bcd \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc8\u0baf\u0bc8 \u0b89\u0bb0\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba8\u0bc6\u0bb1\u0bcd\u0bb1\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0bae\u0bbe\u0bb0\u0bcd\u0baa\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0baa\u0bc2\u0b9a\u0bbf \u0b89\u0b9f\u0bb2\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0bb3\u0bbf\u0bb0\u0bcd\u0bb5\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2 \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0baa\u0bcd \u0baa\u0bb4\u0b95\u0bcd\u0b95\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-aromatic-resin-incense-fixation-and-temple-fumigation-akil-dhoop.md",
        "slug": "concept-aromatic-resin-incense-fixation-and-temple-fumigation-akil-dhoop",
        "category": "concept",
        "name_en": "Aromatic Resin Incense Fixation & Temple Fumigation Pyrotechnics (Akil & Dhoopam)",
        "name_ta": "\u0b85\u0b95\u0bbf\u0bb2\u0bcd \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bc8 \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0ba4\u0bc2\u0baa\u0b95\u0bcd \u0b95\u0bb2\u0bc8",
        "era": "Sangam to Chola Era",
        "year_start": -200,
        "year_end": 1100,
        "thinai": "kurinji",
        "summary_en": "Thermal vaporization of fragrant oleoresins from infected Aquilaria agallocha heartwood (Akil), Dammar (Kungiliyam), and benzoin (Sambrani) over glowing coconut-shell charcoals for air purification and temple rituals.",
        "summary_ta": "\u0b85\u0b95\u0bbf\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc8, \u0b95\u0bc1\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bbf\u0baf\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbe\u0bae\u0bcd\u0baa\u0bbf\u0bb0\u0bbe\u0ba3\u0bbf \u0baa\u0bbf\u0b9a\u0bbf\u0ba9\u0bcd\u0b95\u0bb3\u0bc8 \u0ba4\u0ba3\u0bb2\u0bbf\u0bb2\u0bcd \u0b87\u0b9f\u0bcd\u0b9f\u0bc1 \u0bb5\u0bbe\u0b9a\u0ba9\u0bc8\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bc8\u0baf\u0bc8 \u0b8e\u0bb4\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2\u0ba4\u0bcd \u0ba4\u0bc2\u0baa \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Akananuru Incense Verses",
            "Chola Temple Ritual Manuals",
            "Aromatics of Southern India"
        ],
        "content": "# Aromatic Resin Incense Fixation & Temple Fumigation Pyrotechnics (Akil & Dhoopam)\n\n## Highland Resins: Akil & Kungiliyam\nThe mountain forests of Tamilakam yielded coveted oleoresinous woods and tree saps, foremost among them *Akil* (agarwood, formed by fungal infection of *Aquilaria* heartwood) and *Kungiliyam* (white and black dammar from *Canarium strictum*).\n\n## Charcoal Incense Censers (*Dhoopak-Kaal*)\nDuring twilight and midnight temple services, dried resin chips were sprinkled over red-hot coconut-shell charcoal embers housed in pierced bronze braziers (*Dhoopak-Kaal*). The volatile sesquiterpenoids vaporized into dense, curling plumes of fragrant, antimicrobial smoke.\n\n## Atmospheric Sanctification\nPoets in *Nedunalvaadai* describe elite women drying their fragrant washed tresses over perforated wicker baskets set atop smoldering Akil censers, infusing hair with eternal woody aroma.",
        "chunks": [
            {
                "language": "en",
                "title": "Aromatic Agarwood Akil Resins & Temple Dhoopam Fumigation",
                "content": "Vaporizing fungal-infected Akil agarwood and Kungiliyam dammar resins on charcoal braziers provided sacred antimicrobial fumigation."
            },
            {
                "language": "ta",
                "title": "\u0b85\u0b95\u0bbf\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bbf\u0baf \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0ba4\u0bcd \u0ba4\u0bc2\u0baa \u0bae\u0bc1\u0bb1\u0bc8",
                "content": "\u0b85\u0b95\u0bbf\u0bb2\u0bcd \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbe\u0bae\u0bcd\u0baa\u0bbf\u0bb0\u0bbe\u0ba3\u0bbf\u0baf\u0bc8 \u0ba4\u0ba3\u0bb2\u0bbf\u0bb2\u0bcd \u0b87\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba4\u0bc2\u0baa\u0bae\u0bcd \u0b8e\u0bb4\u0bc1\u0baa\u0bcd\u0baa\u0bbf \u0b95\u0bc2\u0ba8\u0bcd\u0ba4\u0bb2\u0bc8 \u0b89\u0bb2\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf\u0baf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd\u0b95\u0bb3\u0bc8 \u0baa\u0bc1\u0ba9\u0bbf\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0baf \u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-royal-cosmetic-unguent-anointing-and-cooling-therapeutics.md",
        "slug": "concept-royal-cosmetic-unguent-anointing-and-cooling-therapeutics",
        "category": "concept",
        "name_en": "Royal Cosmetic Unguent Anointing & Post-Bath Somatic Therapeutics (Thailak-Kaapu)",
        "name_ta": "\u0b85\u0bb0\u0b9a \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0ba4\u0bcd \u0ba4\u0bc8\u0bb2\u0b95\u0bcd \u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc0\u0bb0\u0bbe\u0b9f\u0bb2\u0bcd \u0baa\u0bbf\u0ba8\u0bcd\u0ba4\u0bc8\u0baf \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Sangam Era (c. 300 BCE \u2013 300 CE)",
        "year_start": -300,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Post-bath application of poly-herbal fragrant pastes comprising vetiver (Vettiver), spikenard (Jatamansi), wild turmeric (Kasthuri Manjal), and red lotus stamens to soothe skin and condition the body against tropical heat.",
        "summary_ta": "\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bbf\u0bb5\u0bc7\u0bb0\u0bcd, \u0b95\u0bb8\u0bcd\u0ba4\u0bc2\u0bb0\u0bbf \u0bae\u0b9e\u0bcd\u0b9a\u0bb3\u0bcd, \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0ba9\u0bcd\u0ba9\u0bbe\u0bb0\u0bbf \u0bb5\u0bc7\u0bb0\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4\u0bc1 \u0ba8\u0bc0\u0bb0\u0bbe\u0b9f\u0bb2\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0baa\u0bcd \u0baa\u0bbf\u0ba9\u0bcd \u0baa\u0bc2\u0b9a\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0b85\u0bb0\u0b9a \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0baa\u0bcd \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1.",
        "sources": [
            "Nedunalvaadai Verses on Royal Chambers",
            "Traditional Siddha Hygiene",
            "Sangam Medical Traditions"
        ],
        "content": "# Royal Cosmetic Unguent Anointing & Post-Bath Somatic Therapeutics (Thailak-Kaapu)\n\n## Multi-Botanical Unguent Formulation\nClassical royal hygiene mandated systematic post-bath anointing (*Thailak-Kaapu*). The master compounder blended cooling fibrous roots (*Vettiver*, *Nannari*), wild aromatic turmeric (*Kasthuri-Manjal*), and floral distillates into smooth unguent pastes.\n\n## Somatic Health & Pest Deterrence\nBeyond aesthetic luxury, these aromatic unguents exerted potent physiological benefits: lowering somatic core temperature, smoothing epidermal dehydration, and releasing natural essential oils that repelled mosquitoes and biting insects in riverine palaces.",
        "chunks": [
            {
                "language": "en",
                "title": "Royal Cosmetic Unguents & Post-Bath Anointing",
                "content": "Formulations of vetiver, sandalwood, and wild turmeric created cooling medicinal unguents for royal post-bath somatic therapeutics."
            },
            {
                "language": "ta",
                "title": "\u0b85\u0bb0\u0b9a \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0b95\u0bcd \u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0b9f\u0bb2\u0bcd\u0ba8\u0bb2\u0baa\u0bcd \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8",
                "content": "\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bbf\u0bb5\u0bc7\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb8\u0bcd\u0ba4\u0bc2\u0bb0\u0bbf \u0bae\u0b9e\u0bcd\u0b9a\u0bb3\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4 \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bae\u0bcd\u0baa\u0bc8 \u0ba8\u0bc0\u0bb0\u0bbe\u0b9f\u0bb2\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0baa\u0bcd \u0baa\u0bbf\u0ba9\u0bcd \u0baa\u0bc2\u0b9a\u0bbf \u0b89\u0b9f\u0bb2\u0bc8 \u0b95\u0bc1\u0bb3\u0bbf\u0bb0\u0bcd\u0bb5\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-thiruvannamalai-chola-fragrant-resin-and-sandalwood-endowments.md",
        "slug": "insc-thiruvannamalai-chola-fragrant-resin-and-sandalwood-endowments",
        "category": "inscription",
        "name_en": "Thiruvannamalai Chola Inscriptions on Sandalwood, Civet & Aromatic Endowments",
        "name_ta": "\u0ba4\u0bbf\u0bb0\u0bc1\u0bb5\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bb2\u0bc8 \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9, \u0b9a\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Imperial Chola Era (c. 950 \u2013 1150 CE)",
        "year_start": 950,
        "year_end": 1150,
        "thinai": "kurinji",
        "summary_en": "Temple wall epigraphs at Thiruvannamalai recording perpetual royal endowments for daily supplies of graded sandalwood logs, civet musk (Punugu), and camphor for deity anointing rituals.",
        "summary_ta": "\u0ba4\u0bbf\u0bb0\u0bc1\u0bb5\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bb2\u0bc8 \u0b85\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bb2\u0bc8\u0baf\u0bbe\u0bb0\u0bcd \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bbf\u0bb2\u0bcd \u0ba8\u0bbe\u0bb3\u0bcd\u0ba4\u0bcb\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0bb1\u0bc8\u0bb5\u0ba9\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9\u0b95\u0bcd \u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1, \u0baa\u0bc1\u0ba9\u0bc1\u0b95\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbe\u0bae\u0bcd\u0baa\u0bbf\u0bb0\u0bbe\u0ba3\u0bbf \u0bb5\u0bb4\u0b99\u0bcd\u0b95 \u0ba8\u0bbf\u0bb5\u0ba8\u0bcd\u0ba4\u0bae\u0bcd \u0b85\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4 \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "South Indian Inscriptions Vol. VIII",
            "Thiruvannamalai Epigraphic Corpus"
        ],
        "content": "# Thiruvannamalai Chola Inscriptions on Sandalwood, Civet & Aromatic Endowments\n\n## Temple Epigraphy of Sacred Fragrances\nThe great granite temple walls of Thiruvannamalai preserve detailed lithic records of aromatics endowed by Chola monarchs and guild donors.\n\n## Endowment Specifications\nInscriptions detail dedicated capital funds invested with local agrarian assemblies to purchase fixed monthly quantities of seasoned sandalwood (*Santhana-Kattai*), precious civet musk (*Punugu-Poonai-Nei*), and resinous Kungiliyam to sustain the daily eternal fragrances of the deity's sacred bath (*Thirumanjanam*).",
        "chunks": [
            {
                "language": "en",
                "title": "Thiruvannamalai Chola Epigraphs on Temple Aromatics",
                "content": "Thiruvannamalai inscriptions record perpetual Chola endowments funding daily provisions of sandalwood, civet musk, and camphor."
            },
            {
                "language": "ta",
                "title": "\u0ba4\u0bbf\u0bb0\u0bc1\u0bb5\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bb2\u0bc8 \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1",
                "content": "\u0b87\u0bb1\u0bc8\u0bb5\u0ba9\u0bbf\u0ba9\u0bcd \u0bb5\u0bb4\u0bbf\u0baa\u0bbe\u0b9f\u0bcd\u0b9f\u0bbf\u0bb1\u0bcd\u0b95\u0bc1 \u0ba8\u0bbe\u0bb3\u0bcd\u0ba4\u0bcb\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0ba9\u0bc1\u0b95\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95 \u0bb5\u0bb4\u0bbf\u0bb5\u0b95\u0bc8 \u0b9a\u0bc6\u0baf\u0bcd\u0ba4 \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bbe\u0bb2 \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1 \u0b86\u0bb5\u0ba3\u0b99\u0bcd\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-kudumiyanmalai-aromatic-paste-grinder-and-temple-perfumer-charters.md",
        "slug": "insc-kudumiyanmalai-aromatic-paste-grinder-and-temple-perfumer-charters",
        "category": "inscription",
        "name_en": "Kudumiyanmalai Epigraphs: Aromatic Paste Grinders & Temple Perfumer Rights",
        "name_ta": "\u0b95\u0bc1\u0b9f\u0bc1\u0bae\u0bbf\u0baf\u0bbe\u0ba9\u0bcd\u0bae\u0bb2\u0bc8 \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9 \u0b85\u0bb0\u0bc8\u0baa\u0bcd\u0baa\u0bbe\u0bb3\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0baa\u0bcd \u0baa\u0ba3\u0bbf\u0baf\u0bbe\u0bb3\u0bb0\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Early Medieval Pandya/Chola Era",
        "year_start": 700,
        "year_end": 1050,
        "thinai": "mullai",
        "summary_en": "Lithic charters documenting the hereditary rights, tax-exempt quarters, and daily grain shares of specialized sandalwood grinders (Santhanam Araippar) in temple services.",
        "summary_ta": "\u0b95\u0bc1\u0b9f\u0bc1\u0bae\u0bbf\u0baf\u0bbe\u0ba9\u0bcd\u0bae\u0bb2\u0bc8 \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bbf\u0bb2\u0bcd \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9\u0bae\u0bcd \u0b85\u0bb0\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1\u0baa\u0bcd \u0baa\u0bc2\u0b9a\u0bc1\u0bae\u0bcd \u0baa\u0ba3\u0bbf\u0b95\u0bcd\u0b95\u0bbe\u0b95 \u0ba8\u0bbf\u0bb2\u0bae\u0bc1\u0bae\u0bcd \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0bae\u0bc1\u0bae\u0bcd \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b8a\u0bb4\u0bbf\u0baf\u0bb0\u0bcd \u0baa\u0bb1\u0bcd\u0bb1\u0bbf\u0baf \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Inscriptions of the Pudukkottai State",
            "South Indian Temple Service Registries"
        ],
        "content": "# Kudumiyanmalai Epigraphs: Aromatic Paste Grinders & Temple Perfumer Rights\n\n## Institutionalized Temple Perfumers\nAt the rock-cut cave temple of Kudumiyanmalai, stone epigraphs record the official establishment of hereditary temple perfumers (*Santhanam Araippar*).\n\n## Operational Land Grants\nThe charters grant tax-free paddy lands (*Santhana-Pangu*) to artisans whose sole sacred duty was stone-mortaring pure sandalwood paste and formulating ceremonial unguents for daily liturgical unctions.",
        "chunks": [
            {
                "language": "en",
                "title": "Kudumiyanmalai Inscriptions on Sandalwood Grinders",
                "content": "Lithic charters at Kudumiyanmalai detail land grants and rights for hereditary artisans grinding sandalwood paste for temple rituals."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bc1\u0b9f\u0bc1\u0bae\u0bbf\u0baf\u0bbe\u0ba9\u0bcd\u0bae\u0bb2\u0bc8 \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9 \u0b85\u0bb0\u0bc8\u0baa\u0bcd\u0baa\u0bbe\u0bb3\u0bb0\u0bcd \u0ba8\u0bbf\u0bb2\u0b95\u0bcd\u0b95\u0bca\u0b9f\u0bc8 \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1",
                "content": "\u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0bb5\u0bb4\u0bbf\u0baa\u0bbe\u0b9f\u0bcd\u0b9f\u0bbf\u0bb1\u0bcd\u0b95\u0bbe\u0b95 \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9\u0bae\u0bcd \u0b85\u0bb0\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0ba3\u0bbf\u0baf\u0bbe\u0bb3\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba8\u0bbf\u0bb2 \u0b89\u0bb0\u0bbf\u0bae\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0b99\u0bcd\u0b95\u0bc1 \u0baa\u0bb1\u0bcd\u0bb1\u0bbf\u0baf \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0ba4\u0bbf\u0bb5\u0bc1\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-javvadhumalai-civet-and-sandalwood-harvester-malai-kuravar.md",
        "slug": "char-javvadhumalai-civet-and-sandalwood-harvester-malai-kuravar",
        "category": "character",
        "name_en": "Kooran Kuravan: Master Civet Tracker & Sandalwood Harvester of Javvadi",
        "name_ta": "\u0b95\u0bc2\u0bb0\u0ba9\u0bcd \u0b95\u0bc1\u0bb1\u0bb5\u0ba9\u0bcd - \u0b9c\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0bae\u0bb2\u0bc8 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0baa\u0bc1\u0ba9\u0bc1\u0b95\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9 \u0bb5\u0bc7\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bcd\u0b95\u0bbe\u0bb0\u0bb0\u0bcd",
        "era": "Sangam Era (c. 100 BCE \u2013 100 CE)",
        "year_start": -100,
        "year_end": 100,
        "thinai": "kurinji",
        "summary_en": "Legendary highland tribal elder possessing intimate knowledge of civet nocturnal scent markings, wild sandalwood grove maturation, and resin tapping across the Javvadi hill ranges.",
        "summary_ta": "\u0b9c\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0bae\u0bb2\u0bc8\u0ba4\u0bcd\u0ba4\u0bca\u0b9f\u0bb0\u0bbf\u0bb2\u0bcd \u0baa\u0bc1\u0ba9\u0bc1\u0b95\u0bc1\u0baa\u0bcd \u0baa\u0bc2\u0ba9\u0bc8\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bc1\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0ba3\u0bcd\u0b9f\u0bb1\u0bbf\u0ba8\u0bcd\u0ba4\u0bc1 \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0b9f\u0bcd\u0b95\u0bb3\u0bc8\u0b9a\u0bcd \u0b9a\u0bc7\u0b95\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4 \u0baa\u0bb4\u0b99\u0bcd\u0b95\u0bc1\u0b9f\u0bbf \u0bae\u0bc2\u0ba4\u0bcd\u0ba4\u0bb5\u0bb0\u0bcd.",
        "sources": [
            "Javvadi Forest Oral Epics",
            "Kurunji Tribal Ethnography"
        ],
        "content": "# Kooran Kuravan: Master Civet Tracker & Sandalwood Harvester of Javvadi\n\n## Master of the Highland Canopy\nKooran Kuravan belonged to the mountain Kuravar clan dwelling on the rugged granite peaks of the Javvadi hills. He navigated dense evergreen slopes to track nocturnal civets (*Punugu-Poonai*).\n\n## Sustainable Forest Harvesting\nKnowing the exact tree barks where civets rubbed their scent glands, Kooran scraped pristine raw musk using horn spatulas without harming the animals, supplying royal merchants in Kaveripoompattinam and Kanchipuram.",
        "chunks": [
            {
                "language": "en",
                "title": "Kooran Kuravan Master Civet Tracker Biography",
                "content": "Highland tribal elder Kooran Kuravan expertly tracked wild civet scent trails and harvested seasoned sandalwood in the Javvadi hills."
            },
            {
                "language": "ta",
                "title": "\u0b9c\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0bae\u0bb2\u0bc8 \u0bb5\u0bc7\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bcd\u0b95\u0bbe\u0bb0\u0bb0\u0bcd \u0b95\u0bc2\u0bb0\u0ba9\u0bcd \u0b95\u0bc1\u0bb1\u0bb5\u0ba9\u0bcd \u0bb5\u0bbe\u0bb4\u0bcd\u0b95\u0bcd\u0b95\u0bc8",
                "content": "\u0baa\u0bc1\u0ba9\u0bc1\u0b95\u0bc1\u0baa\u0bcd \u0baa\u0bc2\u0ba9\u0bc8\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc8\u0b95\u0bb3\u0bc8 \u0b85\u0bb1\u0bbf\u0ba8\u0bcd\u0ba4\u0bc1 \u0bb5\u0bbf\u0bb2\u0b99\u0bcd\u0b95\u0bc1\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0ba4\u0bc0\u0b99\u0bcd\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0bbf \u0baa\u0bc1\u0ba9\u0bc1\u0b95\u0bc1 \u0b9a\u0bc7\u0b95\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4 \u0b9c\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0bae\u0bb2\u0bc8\u0baa\u0bcd \u0baa\u0bb4\u0b99\u0bcd\u0b95\u0bc1\u0b9f\u0bbf\u0ba4\u0bcd \u0ba4\u0bb2\u0bc8\u0bb5\u0bb0\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-thanjavur-royal-perfumer-and-unguent-formulator-santhana-kollan.md",
        "slug": "char-thanjavur-royal-perfumer-and-unguent-formulator-santhana-kollan",
        "category": "character",
        "name_en": "Pugazhendhi Suva-Kollan: Imperial Court Perfumer & Unguent Formulator",
        "name_ta": "\u0baa\u0bc1\u0b95\u0bb4\u0bc7\u0ba8\u0bcd\u0ba4\u0bbf \u0b9a\u0bc1\u0bb5\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0ba9\u0bcd - \u0b9a\u0bcb\u0bb4 \u0b85\u0bb0\u0b9a\u0bb5\u0bc8 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0ba8\u0bb1\u0bc1\u0bae\u0ba3 \u0bb5\u0bbf\u0ba9\u0bc8\u0b9e\u0bb0\u0bcd",
        "era": "Imperial Chola Era (c. 1000 CE)",
        "year_start": 980,
        "year_end": 1040,
        "thinai": "marutham",
        "summary_en": "Master court perfumer who directed the royal cosmetic ateliers at Thanjavur, compounding exquisite floral attars, aged Javvadu musk, and cooling sandalwood pastes for Emperor Rajaraja Chola.",
        "summary_ta": "\u0ba4\u0b9e\u0bcd\u0b9a\u0bc8 \u0baa\u0bc6\u0bb0\u0bbf\u0baf \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0bcb\u0bb4 \u0b85\u0bb0\u0b9a\u0bb5\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb5\u0bbe\u0b9a\u0ba9\u0bc8\u0ba4\u0bcd \u0ba4\u0bc8\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9\u0b95\u0bcd \u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4 \u0bae\u0bc1\u0ba4\u0ba9\u0bcd\u0bae\u0bc8 \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0b95\u0bcd \u0b95\u0bb2\u0bc8\u0b9e\u0bb0\u0bcd.",
        "sources": [
            "Brihadisvara Temple Records",
            "Chola Palace Inscriptions"
        ],
        "content": "# Pugazhendhi Suva-Kollan: Imperial Court Perfumer & Unguent Formulator\n\n## Chief Compounder to the Imperial Cholas\nPugazhendhi Suva-Kollan managed the imperial perfume laboratories (*Thirumeni-Kappu Kottam*) of Thanjavur during the reign of Rajaraja Chola I.\n\n## Mastery of Fragrance Balancing\nPugazhendhi possessed supreme olfactory expertise, balancing volatile camphor top-notes with heavy civetone musk bases and deep sandalwood fixatives, creating sacred scents that defined the atmosphere of the great temple.",
        "chunks": [
            {
                "language": "en",
                "title": "Pugazhendhi Court Perfumer & Unguent Master",
                "content": "Imperial perfumer Pugazhendhi compounded elite sandalwood pastes, civet musks, and floral attars for the Chola court and Brihadisvara temple."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0bcb\u0bb4 \u0b85\u0bb0\u0b9a\u0bb5\u0bc8 \u0ba8\u0bb1\u0bc1\u0bae\u0ba3 \u0bb5\u0bbf\u0ba9\u0bc8\u0b9e\u0bb0\u0bcd \u0baa\u0bc1\u0b95\u0bb4\u0bc7\u0ba8\u0bcd\u0ba4\u0bbf",
                "content": "\u0ba4\u0b9e\u0bcd\u0b9a\u0bc8 \u0b85\u0bb0\u0ba3\u0bcd\u0bae\u0ba9\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bc6\u0bb0\u0bbf\u0baf \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b85\u0bb0\u0bbf\u0baf \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0ba4\u0bcd \u0ba4\u0bc8\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b9a\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b95\u0bb2\u0bc8\u0b9e\u0bb0\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/places/place-javvadhumalai-ancient-sandalwood-civet-and-aromatic-haven.md",
        "slug": "place-javvadhumalai-ancient-sandalwood-civet-and-aromatic-haven",
        "category": "place",
        "name_en": "Javvadi Hills: Ancient Sandalwood Forest, Civet Sanctuary & Aromatic Haven",
        "name_ta": "\u0b9c\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0bae\u0bb2\u0bc8 - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9 \u0bb5\u0ba9\u0bae\u0bcd, \u0baa\u0bc1\u0ba9\u0bc1\u0b95\u0bc1 \u0baa\u0bc1\u0b95\u0bb2\u0bbf\u0b9f\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1300,
        "thinai": "kurinji",
        "summary_en": "Highland mountain range in the northern Eastern Ghats renowned since classical antiquity for native sandalwood groves, wild civet populations, and aromatic resin harvests giving the mountain its eponymous name.",
        "summary_ta": "\u0b9a\u0ba8\u0bcd\u0ba4\u0ba9 \u0bae\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd, \u0baa\u0bc1\u0ba9\u0bc1\u0b95\u0bc1\u0baa\u0bcd \u0baa\u0bc2\u0ba9\u0bc8\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0ba8\u0bbf\u0bb1\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1 \u0ba4\u0ba9\u0ba4\u0bc1 \u0baa\u0bc6\u0baf\u0bb0\u0bbf\u0bb2\u0bc7\u0baf\u0bc7 \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0ba4\u0bcd\u0ba4\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1\u0bb3\u0bcd\u0bb3 \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bbf\u0b95\u0bcd\u0b95 \u0b9c\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0bae\u0bb2\u0bc8\u0ba4\u0bcd\u0ba4\u0bca\u0b9f\u0bb0\u0bcd.",
        "sources": [
            "Gazetteer of North Arcot",
            "Sangam Mountain Topography",
            "Botanical Surveys of Eastern Ghats"
        ],
        "content": "# Javvadi Hills: Ancient Sandalwood Forest, Civet Sanctuary & Aromatic Haven\n\n## Orography & Endemic Flora\nRising between the Palar and Ponnaiyar river valleys in northern Tamil Nadu, the Javvadi Hills (Javadi ranges) form an elevated granitic plateau cloaked in deciduous and scrub forests. The microclimate favored dense groves of high-yielding white sandalwood (*Santalum album*).\n\n## The Origin of the Eponymous Fragrance\nNamed directly after *Javvadu* (the aromatic civet musk compound), these hills were the primary geographic source from which ancient Tamil kings and Roman merchants obtained raw civet gland extracts, fragrant gums, and seasoned sandalwood billets.",
        "chunks": [
            {
                "language": "en",
                "title": "Javvadi Hills Sandalwood & Civet Aromatic Topography",
                "content": "The Javvadi Hills were ancient Tamilakam's premier highland source for white sandalwood, civet musk, and sacred aromatic resins."
            },
            {
                "language": "ta",
                "title": "\u0b9c\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0bae\u0bb2\u0bc8 \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0ba4\u0bcd \u0ba4\u0bb3 \u0baa\u0bc1\u0bb5\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
                "content": "\u0b9a\u0ba8\u0bcd\u0ba4\u0ba9 \u0bae\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0ba9\u0bc1\u0b95\u0bc1\u0baa\u0bcd \u0baa\u0bc2\u0ba9\u0bc8\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0baa\u0bc1\u0b95\u0bb2\u0bbf\u0b9f\u0bae\u0bbe\u0b95 \u0bb5\u0bbf\u0bb3\u0b99\u0bcd\u0b95\u0bbf \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb4\u0bcd \u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0b9c\u0bb5\u0bcd\u0bb5\u0bbe\u0ba4\u0bc1 \u0bae\u0bb2\u0bc8\u0ba4\u0bcd\u0ba4\u0bca\u0b9f\u0bb0\u0bcd."
            }
        ]
    }
]
EDGES = [
    [
        "char-javvadhumalai-civet-and-sandalwood-harvester-malai-kuravar",
        "located_in",
        "place-javvadhumalai-ancient-sandalwood-civet-and-aromatic-haven",
        "geography",
        "Sangam Era",
        "Harvested wild civet musk and mature sandalwood in the Javvadi hills",
        "Sangam Kurinji poems"
    ],
    [
        "char-thanjavur-royal-perfumer-and-unguent-formulator-santhana-kollan",
        "participated_in",
        "place-javvadhumalai-ancient-sandalwood-civet-and-aromatic-haven",
        "commerce",
        "Chola Era",
        "Procured high-grade sandalwood and civet secretions from Javvadi forest suppliers",
        "Brihadisvara epigraphs"
    ],
    [
        "concept-civet-musk-extraction-and-sacerdotal-aromatic-blending-javvadu",
        "practiced_by",
        "char-javvadhumalai-civet-and-sandalwood-harvester-malai-kuravar",
        "craft",
        "Sangam Era",
        "Tracked nocturnal civets and harvested glandular secretions safely",
        "Ethno-botanical records"
    ],
    [
        "concept-sandalwood-heartwood-stone-mortaring-and-cooling-paste-santhanam",
        "related_to",
        "concept-civet-musk-extraction-and-sacerdotal-aromatic-blending-javvadu",
        "cosmetics",
        "Sangam Era",
        "Sandalwood paste formed the cooling aromatic base for civet musk fixatives",
        "Traditional perfumery"
    ],
    [
        "concept-aromatic-resin-incense-fixation-and-temple-fumigation-akil-dhoop",
        "influenced",
        "concept-civet-musk-extraction-and-sacerdotal-aromatic-blending-javvadu",
        "pyrotechnics",
        "Sangam Era",
        "Oleoresinous Akil wood and Dammar resins complemented liquid unguents in temple worship",
        "Ritual manuals"
    ],
    [
        "concept-royal-cosmetic-unguent-anointing-and-cooling-therapeutics",
        "influenced",
        "concept-sandalwood-heartwood-stone-mortaring-and-cooling-paste-santhanam",
        "hygiene",
        "Sangam Era",
        "Somatic cooling ungents utilized freshly ground sandalwood paste as prime vehicle",
        "Siddha hygiene treatises"
    ],
    [
        "text-silappathikaram-fragrant-cosmetic-streets-and-javvadu-bazaars",
        "references",
        "concept-civet-musk-extraction-and-sacerdotal-aromatic-blending-javvadu",
        "literature",
        "Classical Era",
        "Celebrated aromatic bazaar streets selling civet musk, sandalwood, and incense",
        "Silappathikaram lines 13-25"
    ],
    [
        "insc-thiruvannamalai-chola-fragrant-resin-and-sandalwood-endowments",
        "evidenced_by",
        "concept-aromatic-resin-incense-fixation-and-temple-fumigation-akil-dhoop",
        "epigraphy",
        "Imperial Chola",
        "Charters confirmed perpetual endowments for daily sandalwood and incense",
        "South Indian Inscriptions"
    ],
    [
        "insc-kudumiyanmalai-aromatic-paste-grinder-and-temple-perfumer-charters",
        "evidenced_by",
        "char-thanjavur-royal-perfumer-and-unguent-formulator-santhana-kollan",
        "epigraphy",
        "Early Medieval",
        "Documented hereditary rights and land grants to master temple sandalwood grinders",
        "Pudukkottai Epigraphs"
    ],
    [
        "place-javvadhumalai-ancient-sandalwood-civet-and-aromatic-haven",
        "center_of",
        "concept-civet-musk-extraction-and-sacerdotal-aromatic-blending-javvadu",
        "geography",
        "Sangam to Chola",
        "Primary highland origin and namesake for the sacred civet perfume Javvadu",
        "Gazetteer records"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 27 Corpus 1: Civet Musk, Sandalwood Paste & Sacerdotal Unguents into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 27 Corpus 1: Civet Musk, Sandalwood Paste & Sacerdotal Unguents Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
