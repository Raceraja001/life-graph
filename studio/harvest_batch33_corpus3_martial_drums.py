#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Military Drum Acoustics, Membrane Tensioning & War Resonators
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
        "file": "knowledge/texts/text-purananuru-50-verses-on-consecrated-war-drums-and-sacred-murasu-couches.md",
        "slug": "text-purananuru-50-verses-on-consecrated-war-drums-and-sacred-murasu-couches",
        "category": "text",
        "name_en": "Purananuru 50: Mosikeeranar Verses on Consecrated War Drums & Sacred Murasu Couches",
        "name_ta": "\u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 50 - \u0bae\u0bcb\u0b9a\u0bbf\u0b95\u0bc0\u0bb0\u0ba9\u0bbe\u0bb0\u0bcd \u0baa\u0bbe\u0b9f\u0bbf\u0baf \u0bb5\u0bc0\u0bb0\u0bae\u0bc1\u0bb0\u0b9a\u0bc1, \u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bbf\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb0\u0b9a \u0b95\u0bcc\u0bb0\u0bb5\u0bae\u0bcd",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "mullai",
        "summary_en": "Classical Sangam verses by Mosikeeranar describing the sacred anointed status of royal war drums (veera-murasu) resting on swan-down couches, and King Peruncheral Irumporai fanning the poet.",
        "summary_ta": "\u0bae\u0ba9\u0bcd\u0ba9\u0bb0\u0bbf\u0ba9\u0bcd \u0bb5\u0bc6\u0bb1\u0bcd\u0bb1\u0bbf \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0bb5\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0ba9\u0bbf\u0ba4 \u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bbf\u0bb2\u0bbf\u0bb2\u0bcd \u0b85\u0bb1\u0bbf\u0baf\u0bbe\u0ba4\u0bc1 \u0b89\u0bb1\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0baa\u0bc1\u0bb2\u0bb5\u0bb0\u0bcd \u0bae\u0bcb\u0b9a\u0bbf\u0b95\u0bc0\u0bb0\u0ba9\u0bbe\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1, \u0b9a\u0bc7\u0bb0 \u0bae\u0ba9\u0bcd\u0ba9\u0ba9\u0bcd \u0b95\u0bb5\u0bb0\u0bbf \u0bb5\u0bc0\u0b9a\u0bbf \u0b95\u0bcc\u0bb0\u0bb5\u0bbf\u0ba4\u0bcd\u0ba4 \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd.",
        "sources": [
            "Purananuru 50",
            "Pathittruppathu 17",
            "Akananuru 83"
        ],
        "content": "# Purananuru 50: Consecrated War Drums & Sacred Couches\n\nPurananuru 50, composed by the Sangam poet Mosikeeranar, preserves one of the most famous historical episodes illustrating the supreme sacred and martial sanctity of the Tamil war drum (veera-murasu).\n\nThe poet, exhausted from travel, unwittingly fell asleep upon a cushioned, garlanded couch in the palace of the Chera monarch Peruncheral Irumporai. This couch was reserved exclusively for the consecrated royal war drum while it had been taken to the river for ceremonial ritual bathing.\n\nAwakening to find the sovereign king personally fanning him with a yak-tail whisk instead of executing him for desecration, Mosikeeranar immortalized the sovereign cult of the drum: the murasu was revered as the spiritual heart of the army, embodying the monarch's sovereignty, honor, and martial fortune."
    },
    {
        "file": "knowledge/concepts/concept-veera-murasu-martial-acoustic-warfare-and-low-frequency-resonance.md",
        "slug": "concept-veera-murasu-martial-acoustic-warfare-and-low-frequency-resonance",
        "category": "concept",
        "name_en": "Veera-Murasu: Martial Acoustic Warfare, Low-Frequency Infrasound & Resonator Physics",
        "name_ta": "\u0bb5\u0bc0\u0bb0\u0bae\u0bc1\u0bb0\u0b9a\u0bc1 - \u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3 \u0b92\u0bb2\u0bbf \u0b85\u0bb2\u0bc8 \u0b87\u0baf\u0bb1\u0bcd\u0baa\u0bbf\u0baf\u0bb2\u0bcd, \u0bae\u0bc0\u0baf\u0bca\u0bb2\u0bbf \u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0bb3\u0bb5\u0bbf\u0baf\u0bb2\u0bcd \u0ba4\u0bbe\u0b95\u0bcd\u0b95\u0bae\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -600,
        "year_end": 1800,
        "thinai": "mullai",
        "summary_en": "Martial acoustic science of massive kettle-shaped cauldron drums (veera-murasu) projecting high-energy low-frequency sonic shockwaves (30-60 Hz) across kilometers of battlefield terrain.",
        "summary_ta": "\u0baa\u0bbf\u0bb0\u0bae\u0bcd\u0bae\u0bbe\u0ba3\u0bcd\u0b9f \u0bae\u0bb0\u0b95\u0bcd \u0b95\u0bca\u0baa\u0bcd\u0baa\u0bb0\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bbe\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf, 30-60 \u0bb9\u0bc6\u0bb0\u0bcd\u0b9f\u0bcd\u0bb8\u0bcd \u0b95\u0bc1\u0bb1\u0bc8\u0ba8\u0bcd\u0ba4 \u0b85\u0bb2\u0bc8\u0bb5\u0bb0\u0bbf\u0b9a\u0bc8 \u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bc1\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b8e\u0ba4\u0bbf\u0bb0\u0bbf\u0baa\u0bcd \u0baa\u0b9f\u0bc8\u0b95\u0bb3\u0bc8 \u0b85\u0b9a\u0bcd\u0b9a\u0bc1\u0bb1\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0ba4\u0bae\u0bbf\u0bb4\u0bb0\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3 \u0b92\u0bb2\u0bbf \u0b85\u0bb1\u0bbf\u0bb5\u0bbf\u0baf\u0bb2\u0bcd.",
        "sources": [
            "Purananuru 50",
            "Silappadikaram Arangetrukathai",
            "Acoustical Studies of Ancient Indian Membranophones"
        ],
        "content": "# Veera-Murasu: Martial Acoustic Warfare & Resonance Physics\n\nThe veera-murasu was not merely a musical instrument; it was an advanced acoustic weapon of psychological and tactical command engineered by ancient Tamil martial civilizations.\n\nStanding as a massive hemispherical or cauldron-shaped hardwood kettle drum, the murasu was struck with heavy curved wooden mallets (kuru-kole). The combination of a large air cavity volume (exceeding 200 liters) and a tightly tensioned heavy bullock membrane produced fundamental resonant frequencies in the 30 to 60 Hertz range.\n\nThese low-frequency acoustic shockwaves possessed extraordinary atmospheric propagation qualities: penetrating terrain obstacles, river mists, and enemy formations for miles. Crucially, infrasonic frequencies near human chest-wall and skull resonance induced palpable physical vibrations, elevating friendly soldier adrenaline while striking visceral disorientation and panic into opposing ranks and war elephants."
    },
    {
        "file": "knowledge/technologies/technology-var-pinithal-twisted-leather-thong-radial-tensioning-mechanics.md",
        "slug": "technology-var-pinithal-twisted-leather-thong-radial-tensioning-mechanics",
        "category": "technology",
        "name_en": "Var-Pinithal: Twisted Leather Thong Radial Tensioning & Helical Bracing Mechanics",
        "name_ta": "\u0bb5\u0bbe\u0bb0\u0bcd \u0baa\u0bbf\u0ba3\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd - \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0ba4\u0bcb\u0bb2\u0bcd \u0bb5\u0bbe\u0bb0\u0bcd \u0b86\u0bb0\u0bc8\u0b95\u0bcd\u0b95\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc0\u0bb0\u0bbe\u0ba9 \u0b87\u0bb4\u0bc1\u0bb5\u0bbf\u0b9a\u0bc8\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "mullai",
        "summary_en": "Helical skin-tensioning mechanics (var-pinithal) utilizing continuous braided raw bull-hide thongs (var) laced between perimeter hoops to achieve uniform radial membrane tension exceeding 15 kN.",
        "summary_ta": "\u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b8e\u0bb0\u0bc1\u0ba4\u0bc1\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bcd \u0bb5\u0bbe\u0bb0\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1, \u0b95\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bbe\u0b95 \u0b87\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bbf \u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bc1\u0b95\u0bcd\u0b95\u0bc1 15 \u0b95\u0bbf\u0bb2\u0bcb\u0ba8\u0bbf\u0baf\u0bc2\u0b9f\u0bcd\u0b9f\u0ba9\u0bcd \u0b9a\u0bc0\u0bb0\u0bbe\u0ba9 \u0b87\u0bb4\u0bc1\u0bb5\u0bbf\u0b9a\u0bc8\u0baf\u0bc8 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0bbf\u0ba3\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Pathittruppathu 17",
            "Malaipadukadam 4",
            "Traditional Instrument Craftsmanship Texts"
        ],
        "content": "# Var-Pinithal: Twisted Leather Thong Tensioning\n\nAchieving the deep, thunderous acoustic voice of a royal war drum demanded immense, evenly distributed tension across its thick bovine drumhead, achieved through the specialized craft of var-pinithal.\n\nMaster instrument craftsmen cut continuous spiral thongs (var) from the thick neck hides of mature working bullocks. While wet, these raw leather cords were twisted into three-ply braids and laced in a complex zig-zag radial pattern between the iron-reinforced hoop ring of the membrane and the base of the drum shell.\n\nAs the laced leather thongs dried and shrank under tension, they exerted tremendous cumulative radial pull, stretching the heavy hide uniformly over the shell lip without wrinkling. Hardwood tension pegs or sliding leather sleeves (kootu) were driven along the thongs, allowing commanders to fine-tune drumhead pitch according to ambient humidity and temperature before battle."
    },
    {
        "file": "knowledge/artifacts/artifact-murasu-marunthu-iron-oxide-and-cooked-rice-acoustic-tuning-paste.md",
        "slug": "artifact-murasu-marunthu-iron-oxide-and-cooked-rice-acoustic-tuning-paste",
        "category": "artifact",
        "name_en": "Murasu-Marunthu: Iron Oxide, Fermented Rice & Tamarind Acoustic Tuning Paste",
        "name_ta": "\u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0bae\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 - \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bc1\u0b95\u0bb3\u0bcd, \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4 \u0b9a\u0bbe\u0ba4\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0bb3\u0bbf \u0b95\u0bb2\u0ba8\u0bcd\u0ba4 \u0b92\u0bb2\u0bbf\u0b9a\u0bcd \u0b9a\u0bc1\u0bb0\u0bc1\u0ba4\u0bbf \u0baa\u0b9a\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "mullai",
        "summary_en": "Viscoelastic acoustic mass-loading paste (murasu-marunthu / sorrow) compounded from magnetic iron slag powder, cooked glutinous rice, and tamarind pulp applied to the drumhead center.",
        "summary_ta": "\u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bbf\u0ba9\u0bcd \u0bae\u0bc8\u0baf\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0baa\u0bc2\u0b9a\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bc2\u0bb3\u0bcd, \u0b9a\u0bcb\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0bb3\u0bbf \u0b95\u0bb2\u0ba8\u0bcd\u0ba4 \u0baa\u0b9a\u0bc8; \u0b87\u0ba4\u0bc1 \u0ba4\u0bc7\u0bb5\u0bc8\u0baf\u0bb1\u0bcd\u0bb1 \u0b92\u0bb2\u0bbf\u0b95\u0bb3\u0bc8 \u0b85\u0b9f\u0b95\u0bcd\u0b95\u0bbf \u0b86\u0bb4\u0bae\u0bbe\u0ba9 \u0ba8\u0bbe\u0ba4\u0ba4\u0bcd\u0ba4\u0bc8 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd.",
        "sources": [
            "Silappadikaram Uraiperukathai",
            "Sangam Musicology Treatise",
            "Indian Membranophone Acoustics"
        ],
        "content": "# Murasu-Marunthu: Acoustic Tuning Paste\n\nA fundamental acoustic defect of circular vibrating membranes is the generation of non-harmonic higher overtones, which produce harsh, clattering, disharmonious sound. Ancient Tamil instrument makers solved this through the formulation of murasu-marunthu (acoustic tuning paste).\n\nThe paste was formulated by grinding magnetic iron oxide filings (karumbon-churna) or wootz crucible slag with cooked sticky rice starch (soru) and boiled tamarind pulp into a dense, viscoelastic pitch. This paste was carefully applied in circular concentric layers directly onto the geometric center of the drumhead membrane.\n\nThe added central mass loaded the primary fundamental vibration mode while damping chaotic dissonant side-modes. This converted the raw percussive skin impact into a rich, deep, thunderous harmonic boom (marudha-murasu) capable of carrying across enormous open-air battlefield distances."
    },
    {
        "file": "knowledge/technologies/technology-thannumai-and-thudi-infantry-rhythm-signaling-and-hourglass-resonators.md",
        "slug": "technology-thannumai-and-thudi-infantry-rhythm-signaling-and-hourglass-resonators",
        "category": "technology",
        "name_en": "Thannumai & Thudi: Infantry Rhythmic Signaling, Variable-Pitch Hourglass Resonators",
        "name_ta": "\u0ba4\u0ba3\u0bcd\u0ba3\u0bc1\u0bae\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc1\u0b9f\u0bbf - \u0ba4\u0bb0\u0bc8\u0baa\u0bcd\u0baa\u0b9f\u0bc8 \u0b85\u0ba3\u0bbf\u0bb5\u0b95\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0ba4\u0bbe\u0bb3 \u0b9a\u0bae\u0bbf\u0b95\u0bcd\u0b9e\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc8 \u0bb5\u0b9f\u0bbf\u0bb5 \u0bae\u0bc1\u0bb4\u0bb5\u0bc1",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "mullai",
        "summary_en": "Tactical battlefield signaling drums: cylindrical barrel-shaped thannumai coordinating infantry march cadences and waist-braced variable-pitch hourglass thudi drums signaling ambushes.",
        "summary_ta": "\u0baa\u0b9f\u0bc8 \u0ba8\u0b95\u0bb0\u0bcd\u0bb5\u0bc1\u0b95\u0bb3\u0bc8 \u0bb5\u0bb4\u0bbf\u0ba8\u0b9f\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0b87\u0bb0\u0bc1\u0baa\u0bc1\u0bb1 \u0bae\u0bc1\u0bb4\u0bb5\u0bc1 \u0ba4\u0ba3\u0bcd\u0ba3\u0bc1\u0bae\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bbf\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0b95\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0b85\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0ba4\u0bcd\u0ba4\u0bbe\u0bb2\u0bcd \u0b9a\u0bc1\u0bb0\u0bc1\u0ba4\u0bbf \u0bae\u0bbe\u0bb1\u0bcd\u0bb1\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0bb5\u0bc7\u0b9f\u0bb0\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3\u0ba4\u0bcd \u0ba4\u0bc1\u0b9f\u0bbf.",
        "sources": [
            "Purananuru 270",
            "Akananuru 83",
            "Pathittruppathu 40"
        ],
        "content": "# Thannumai & Thudi: Tactical Signaling Drums\n\nAlongside the monumental sovereign war drum (murasu), ancient Tamil military organization utilized tactical battlefield drums: the thannumai and the thudi.\n\nThe thannumai was a large, horizontal barrel drum slung from the neck of marching drummers. Struck with palms and stiff wooden sticks, its crisp, syncopated rhythms dictated infantry step paces, shield wall advances, and spear charges, functioning as the acoustic nervous system of regular army formations.\n\nThe thudi was a compact, waist-pinched hourglass wooden drum favored by guerrilla hill fighters, Maravars, and border scouts. Carved with a narrow waist, its lacing cords could be squeezed by the player's forearm while striking, dynamically modulating pitch and timbre to broadcast complex coded tactical alarms across rugged ravines."
    },
    {
        "file": "knowledge/institutions/institution-murasu-kottuvar-guild-hereditary-military-drummers-and-heralds.md",
        "slug": "institution-murasu-kottuvar-guild-hereditary-military-drummers-and-heralds",
        "category": "institution",
        "name_en": "Murasu-Kottuvar Guild: Hereditary Military Drummers, State Heralds & Royal Honors",
        "name_ta": "\u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bcd\u0b9f\u0bc1\u0bb5\u0bbe\u0bb0\u0bcd \u0b95\u0bbf\u0bb2\u0bcd\u0b9f\u0bc1 - \u0baa\u0bb0\u0bae\u0bcd\u0baa\u0bb0\u0bc8 \u0b85\u0bb0\u0b9a \u0baa\u0bcb\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bb1\u0bc8 \u0bae\u0bc1\u0bb4\u0b99\u0bcd\u0b95\u0bc1\u0bb5\u0bcb\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb0\u0b9a\u0bc1 \u0b85\u0bb1\u0bbf\u0bb5\u0bbf\u0baa\u0bcd\u0baa\u0bbe\u0bb3\u0bb0\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Early Historic to Medieval Era",
        "year_start": -400,
        "year_end": 1400,
        "thinai": "mullai",
        "summary_en": "Elite hereditary warrior-artisan guild of master military drummers (murasu-kottuvar) endowed with tax-exempt land grants (murasu-kaani), royal insignia, and front-line battlefield honors.",
        "summary_ta": "\u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0bae\u0bc1\u0bb0\u0b9a\u0bb1\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1 \u0b86\u0ba3\u0bc8\u0baf\u0bbf\u0b9f\u0bc1\u0bae\u0bcd \u0b89\u0bb0\u0bbf\u0bae\u0bc8, \u0b85\u0bb0\u0b9a \u0b95\u0bcc\u0bb0\u0bb5\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bb0\u0bbf\u0bb5\u0bbf\u0bb2\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bbf\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bcd (\u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0b95\u0bcd \u0b95\u0bbe\u0ba3\u0bbf) \u0baa\u0bc6\u0bb1\u0bcd\u0bb1\u0bc1 \u0bb5\u0bbe\u0bb4\u0bcd\u0ba8\u0bcd\u0ba4 \u0baa\u0bcb\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bb1\u0bc8 \u0bae\u0bc1\u0bb4\u0b99\u0bcd\u0b95\u0bc1\u0bb5\u0bcb\u0bb0\u0bcd \u0b95\u0bbf\u0bb2\u0bcd\u0b9f\u0bc1.",
        "sources": [
            "Pudukkottai State Inscriptions",
            "Purananuru 50",
            "Chola Military Inscriptions"
        ],
        "content": "# Murasu-Kottuvar Guild: Military Drummer Corporations\n\nThe custody, consecration, and performance of the royal war drum was vested exclusively in the prestigious hereditary guild of the Murasu-Kottuvar (master drummers and heralds).\n\nOccupying an elite position in royal retinues, these warrior-musicians were endowed with hereditary tax-free estates known in epigraphical records as murasu-kaani or uvachari-kaani. In peacetime, they sounded the three canonical royal drums: the Kodai-Murasu (charity drum proclaiming gifts), the Manra-Murasu (judicial drum summoning assemblies), and the Vetri-Murasu (victory drum celebrating conquest).\n\nIn wartime, guild masters marched directly behind royal chariots and elephant vanguards, fearless in the line of spear fire, channeling the commander's battle orders through codified drum cadences that turned chaotic melee into coordinated martial maneuvers."
    },
    {
        "file": "knowledge/concepts/concept-porvai-thol-bovine-hide-liming-shaving-and-acoustic-membrane-curing.md",
        "slug": "concept-porvai-thol-bovine-hide-liming-shaving-and-acoustic-membrane-curing",
        "category": "concept",
        "name_en": "Porvai-Thol: Bovine Hide Processing, Controlled Shaving & Acoustic Membrane Curing",
        "name_ta": "\u0baa\u0bcb\u0bb0\u0bcd\u0bb5\u0bc8\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bcd - \u0b95\u0bbe\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0b8a\u0bb1\u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd, \u0b9a\u0bc0\u0bb5\u0bc1\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bb2\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "mullai",
        "summary_en": "Traditional membranophone leather processing: selection of prime working bullock hides, lime-water unhairing, thickness-calibrated scraping, and acoustic oil impregnation.",
        "summary_ta": "\u0bae\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4 \u0b95\u0bbe\u0bb3\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0ba4\u0b9f\u0bbf\u0bae\u0ba9\u0bbe\u0ba9 \u0ba4\u0bcb\u0bb2\u0bc8\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1, \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0ba8\u0bc0\u0bb0\u0bbf\u0bb2\u0bcd \u0b8a\u0bb1\u0bcd\u0bb1\u0bbf \u0bae\u0baf\u0bbf\u0bb0\u0bcd \u0ba8\u0bc0\u0b95\u0bcd\u0b95\u0bbf, \u0b9a\u0bae\u0b9a\u0bcd\u0b9a\u0bc0\u0bb0\u0bbe\u0b95\u0b9a\u0bcd \u0b9a\u0bc0\u0bb5\u0bbf \u0b92\u0bb2\u0bbf \u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0ba4\u0bcd \u0ba4\u0b95 \u0baa\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0ba4\u0bcb\u0bb2\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Purananuru 382",
            "Malaipadukadam 10",
            "Traditional Leather Processing Manuals"
        ],
        "content": "# Porvai-Thol: Acoustic Membrane Processing\n\nThe acoustic response and physical resilience of a war drum depended upon the delicate preparation of its vibrating membrane, termed porvai-thol.\n\nTanners selected hides exclusively from vigorous, mature working bullocks or male water buffalo, favoring the back and flank sections which possessed dense, uniform collagen fiber bundles. The hide was steeped in mild slaked-lime solutions (sunnambu-neer) to dissolve keratin hair roots without degrading structural collagen elasticity.\n\nOnce unhaired, master craftsmen stretched the wet pelt on wooden drying frames and meticulously shaved the flesh side using curved scraping knives (thol-cheevukathi). The membrane thickness was calibrated with micro-level precision: thicker at the peripheral clamping rims for mechanical strength, and subtly tapered toward the active vibrating zone."
    },
    {
        "file": "knowledge/artifacts/artifact-murasu-kattu-hollowed-vengai-heartwood-cauldron-resonator-shells.md",
        "slug": "artifact-murasu-kattu-hollowed-vengai-heartwood-cauldron-resonator-shells",
        "category": "artifact",
        "name_en": "Murasu-Kattu: Monolithic Hollowed Vengai Heartwood Cauldron Drum Shells",
        "name_ta": "\u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1 - \u0b95\u0bc1\u0b9f\u0bc8\u0ba8\u0bcd\u0ba4 \u0bb5\u0bc7\u0b99\u0bcd\u0b95\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb0\u0b95\u0bcd \u0b95\u0bca\u0baa\u0bcd\u0baa\u0bb0\u0bc8 \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0b89\u0b9f\u0bb2\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "mullai",
        "summary_en": "Monumental hemispherical drum bodies (murasu-kattu) hollowed from monolithic billets of mature Vengai, Rosewood, or Teak heartwood, with wall thickness engineered for acoustic containment.",
        "summary_ta": "\u0bae\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4 \u0bb5\u0bc7\u0b99\u0bcd\u0b95\u0bc8 \u0b85\u0bb2\u0bcd\u0bb2\u0ba4\u0bc1 \u0ba4\u0bc7\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0b9f\u0bcd\u0b9f\u0bc8\u0baf\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1 \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0bbf\u0bb0\u0bae\u0bcd\u0bae\u0bbe\u0ba3\u0bcd\u0b9f \u0b95\u0bca\u0baa\u0bcd\u0baa\u0bb0\u0bc8 \u0bb5\u0b9f\u0bbf\u0bb5 \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0b89\u0b9f\u0bb2\u0bcd; \u0b92\u0bb2\u0bbf \u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bc1\u0b95\u0bb3\u0bc8 \u0b89\u0bb3\u0bcd\u0bb5\u0bbe\u0b99\u0bcd\u0b95\u0bbf\u0baa\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1.",
        "sources": [
            "Purananuru 50",
            "Silappadikaram 5.15",
            "Tamil Musical Artifact Archives"
        ],
        "content": "# Murasu-Kattu: Monolithic Resonator Shells\n\nThe acoustic chamber of the war drum, termed the murasu-kattu, was sculpted from a single solid cylinder of exceptionally dense, acoustic hardwood: primarily Vengai (Pterocarpus marsupium), Rosewood (Itti), or Jackwood (Palaa).\n\nCarvers hollowed the internal cavity using curved adzes and gouges, creating a parabolic hemispherical interior that funneled standing sound waves toward the open membrane head. The wall thickness was tapered with structural foresight: thick and robust at the base to prevent harmonic damping when resting on its stand, and profiled with a smooth, rounded bearing lip at the rim over which the drumhead vibrated without chaffing.\n\nThe finished wooden shell was cured through smoking with aromatic resins (kungiliyam) and rubbed with boiling neem and castor oils, rendering the wood immune to fungal attack and climatic splitting during long military campaigns."
    },
    {
        "file": "knowledge/concepts/concept-infrasonic-battlefield-shockwaves-and-morale-disruption-mechanics.md",
        "slug": "concept-infrasonic-battlefield-shockwaves-and-morale-disruption-mechanics",
        "category": "concept",
        "name_en": "Infrasonic Battlefield Shockwaves: Psycho-Acoustic Warfare & Morale Disruption",
        "name_ta": "\u0bae\u0bc0\u0baf\u0bca\u0bb2\u0bbf \u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3 \u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bb2\u0bc8\u0b95\u0bb3\u0bcd - \u0b89\u0bb3\u0bb5\u0bbf\u0baf\u0bb2\u0bcd \u0b92\u0bb2\u0bbf\u0ba4\u0bcd \u0ba4\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b8e\u0ba4\u0bbf\u0bb0\u0bbf\u0baa\u0bcd \u0baa\u0b9f\u0bc8 \u0ba8\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bae\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "mullai",
        "summary_en": "Psycho-acoustic tactical doctrine: utilizing synchronized batteries of heavy war drums emitting infrasonic pressure waves to terrorize opposing cavalry horses, elephants, and front-line troops.",
        "summary_ta": "\u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b92\u0bb0\u0bc7 \u0ba8\u0bc7\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0bae\u0bc1\u0bb0\u0b9a\u0bc1\u0b95\u0bb3\u0bc8 \u0bae\u0bc1\u0bb4\u0b99\u0bcd\u0b95\u0bbf, \u0bae\u0ba9\u0bbf\u0ba4 \u0b89\u0b9f\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0bb2\u0b99\u0bcd\u0b95\u0bc1\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b95\u0bbe\u0ba4\u0bc1\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b85\u0baa\u0bcd\u0baa\u0bbe\u0bb1\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bae\u0bc0\u0baf\u0bca\u0bb2\u0bbf \u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bc1\u0b95\u0bb3\u0bbe\u0bb2\u0bcd \u0b8e\u0ba4\u0bbf\u0bb0\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0b95\u0bc1\u0ba4\u0bbf\u0bb0\u0bc8, \u0baf\u0bbe\u0ba9\u0bc8\u0baa\u0bcd \u0baa\u0b9f\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0ba8\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0ba4\u0bcd\u0ba4\u0bc8 \u0b8f\u0bb1\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0b89\u0bb3\u0bb5\u0bbf\u0baf\u0bb2\u0bcd \u0baa\u0bcb\u0bb0\u0bcd.",
        "sources": [
            "Pathittruppathu 17",
            "Kalavali Narpathu 5",
            "Military Psycho-Acoustics Studies"
        ],
        "content": "# Infrasonic Battlefield Shockwaves & Morale Disruption\n\nAncient Tamil military treatises recognize the psychological power of coordinated acoustic strikes on the battlefield, a discipline codified in the deployment of the veera-murasu batteries.\n\nWhen multiple colossal drums were struck simultaneously by veteran teams in pounding synchronization, the emitted sound produced intense low-frequency atmospheric pressure pulses. Unlike high-pitched trumpet fanfares which dissipate rapidly, these low-frequency acoustic shockwaves penetrated deep into opposing battle lines.\n\nAt physiological levels, prolonged exposure to high-decibel infrasound induces visceral somatic sensations: vibrating the chest cavity, triggering vestibular nausea, and causing profound neuro-chemical anxiety and dread. Animals\u2014especially war elephants and cavalry stallions possessing acute infrasonic sensitivity\u2014often broke formation in terror, allowing Tamil spear phalanxes to exploit the resulting confusion."
    },
    {
        "file": "knowledge/places/place-alangudi-ancient-pudukkottai-martial-drum-haven.md",
        "slug": "place-alangudi-ancient-pudukkottai-martial-drum-haven",
        "category": "place",
        "name_en": "Alangudi: Ancient Pudukkottai Martial Drum, Hero Stone & Percussion Haven",
        "name_ta": "\u0b86\u0bb2\u0b99\u0bcd\u0b95\u0bc1\u0b9f\u0bbf - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0baa\u0bc1\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bc8 \u0bb5\u0bc0\u0bb0\u0bae\u0bc1\u0bb0\u0b9a\u0bc1, \u0ba8\u0b9f\u0bc1\u0b95\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bb1\u0bc8\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb2\u0bbf\u0b9f\u0bae\u0bcd",
        "era": "Early Historic to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "mullai",
        "summary_en": "Historic martial settlement in Pudukkottai district celebrated across Tamil military history for its warrior traditions, consecrated heroic stones, and heritage instrument crafting guilds.",
        "summary_ta": "\u0baa\u0bc1\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bc8 \u0b9a\u0bc0\u0bae\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bbf\u0b95\u0bcd\u0b95 \u0bb5\u0bc0\u0bb0\u0bb0\u0bcd \u0ba4\u0bb3\u0bae\u0bcd; \u0ba8\u0b9f\u0bc1\u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bcd, \u0bae\u0bb1\u0bb5\u0bb0\u0bcd \u0bae\u0bb0\u0baa\u0bc1, \u0baa\u0bcb\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bb1\u0bc8 \u0bae\u0bc1\u0bb4\u0b99\u0bcd\u0b95\u0bc1\u0bb5\u0bcb\u0bb0\u0bcd \u0b95\u0bbf\u0bb2\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb0\u0b9a\u0bc1 \u0b95\u0bc8\u0bb5\u0bbf\u0ba9\u0bc8\u0baa\u0bcd \u0baa\u0ba3\u0bcd\u0baa\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Pudukkottai Inscriptions Vol I",
            "Hero Stone Epigraphs",
            "Tamil Martial Culture Monograph"
        ],
        "content": "# Alangudi: Ancient Martial Drum & Percussion Haven\n\nAlangudi, nestled in the historic warrior country of Pudukkottai in central Tamil Nadu, holds an enduring place in Tamil military history as a preeminent center of martial drum craftsmanship and heroic percussive culture.\n\nSurrounded by ancient dryland scrub forests (Mullai/Palai tract) populated by legendary Maravar and Kallar martial lineages, Alangudi was a primary arsenal where master instrument artisans fabricated the heavy timber shells and treated bull-hide membranes of war drums.\n\nNumerous hero stones (nadukal) and temple inscriptions in the surrounding area commemorate brave drummers (murasu-kottuvar) who fell in historic clashes, their instruments carved on the stone reliefs beside their heroic weapons, immortalizing Alangudi as the heartbeat of ancient Tamil martial acoustics."
    }
]
EDGES = [
    [
        "concept-veera-murasu-martial-acoustic-warfare-and-low-frequency-resonance",
        "UTILIZES",
        "artifact-murasu-kattu-hollowed-vengai-heartwood-cauldron-resonator-shells",
        "core",
        "Prehistoric to Modern Era",
        "The war drum utilizes hollowed monolithic Vengai heartwood cauldrons as its acoustic resonator.",
        "Purananuru 50"
    ],
    [
        "technology-var-pinithal-twisted-leather-thong-radial-tensioning-mechanics",
        "TENSIONS",
        "concept-porvai-thol-bovine-hide-liming-shaving-and-acoustic-membrane-curing",
        "core",
        "Prehistoric to Modern Era",
        "Twisted bull-hide leather thongs radially lace and tension the acoustic bovine drumhead.",
        "Pathittruppathu 17"
    ],
    [
        "artifact-murasu-marunthu-iron-oxide-and-cooked-rice-acoustic-tuning-paste",
        "TUNES",
        "concept-veera-murasu-martial-acoustic-warfare-and-low-frequency-resonance",
        "core",
        "Prehistoric to Modern Era",
        "Iron oxide and cooked rice tuning paste damps dissonant overtones and tunes fundamental resonance.",
        "Silappadikaram Uraiperukathai"
    ],
    [
        "text-purananuru-50-verses-on-consecrated-war-drums-and-sacred-murasu-couches",
        "DOCUMENTS",
        "concept-veera-murasu-martial-acoustic-warfare-and-low-frequency-resonance",
        "core",
        "Sangam Era",
        "Purananuru 50 documents the consecrated sovereign status and sacred couch of the Chera war drum.",
        "Purananuru 50"
    ],
    [
        "institution-murasu-kottuvar-guild-hereditary-military-drummers-and-heralds",
        "SOUNDS",
        "concept-veera-murasu-martial-acoustic-warfare-and-low-frequency-resonance",
        "core",
        "Early Historic to Medieval Era",
        "Hereditary military drummer guilds sounded the war drums to transmit tactical battlefield orders.",
        "Pudukkottai Inscriptions"
    ],
    [
        "concept-veera-murasu-martial-acoustic-warfare-and-low-frequency-resonance",
        "GENERATES",
        "concept-infrasonic-battlefield-shockwaves-and-morale-disruption-mechanics",
        "core",
        "Prehistoric to Modern Era",
        "High-energy low-frequency resonance from war drums generates infrasonic shockwaves that terrorize enemy ranks.",
        "Kalavali Narpathu 5"
    ],
    [
        "technology-thannumai-and-thudi-infantry-rhythm-signaling-and-hourglass-resonators",
        "COMPLEMENTS",
        "concept-veera-murasu-martial-acoustic-warfare-and-low-frequency-resonance",
        "core",
        "Prehistoric to Modern Era",
        "Infantry rhythm drums and hourglass scout drums complement the strategic war drum in tactical signaling.",
        "Akananuru 83"
    ],
    [
        "concept-porvai-thol-bovine-hide-liming-shaving-and-acoustic-membrane-curing",
        "COVERS",
        "artifact-murasu-kattu-hollowed-vengai-heartwood-cauldron-resonator-shells",
        "core",
        "Prehistoric to Modern Era",
        "Calibrated bullock hide membranes cover the open mouth of the hollowed hardwood resonator shell.",
        "Malaipadukadam 10"
    ],
    [
        "concept-veera-murasu-martial-acoustic-warfare-and-low-frequency-resonance",
        "CONSECRATED_AT",
        "place-alangudi-ancient-pudukkottai-martial-drum-haven",
        "core",
        "Early Historic to Modern Era",
        "Martial war drums and sacred percussion instruments were consecrated and fabricated at Alangudi.",
        "Hero Stone Epigraphs"
    ],
    [
        "institution-murasu-kottuvar-guild-hereditary-military-drummers-and-heralds",
        "BASED_AT",
        "place-alangudi-ancient-pudukkottai-martial-drum-haven",
        "core",
        "Early Historic to Medieval Era",
        "Sovereign military drummer corporations and percussion guilds maintained ancestral quarters at Alangudi.",
        "Pudukkottai State Inscriptions"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Ancient Tamil Military Drum Acoustics, Membrane Tensioning & War Resonators into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Ancient Tamil Military Drum Acoustics, Membrane Tensioning & War Resonators Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
