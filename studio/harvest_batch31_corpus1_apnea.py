#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Pearl Diver Breath-Control & Subaquatic Physiology
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
        "file": "knowledge/texts/text-maduraikanchi-verses-on-gulf-of-mannar-subaquatic-pearl-harvesters.md",
        "slug": "text-maduraikanchi-verses-on-gulf-of-mannar-subaquatic-pearl-harvesters",
        "category": "text",
        "name_en": "Maduraikanchi: Classical Sangam Verses on Subaquatic Pearl Harvesters & Chank Divers",
        "name_ta": "\u0bae\u0ba4\u0bc1\u0bb0\u0bc8\u0b95\u0bcd\u0b95\u0bbe\u0b9e\u0bcd\u0b9a\u0bbf - \u0b86\u0bb4\u0bcd\u0b95\u0b9f\u0bb2\u0bcd \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bcb\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0bcb\u0bb0\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "neithal",
        "summary_en": "Maduraikanchi verses celebrating intrepid Parathavar divers descending into the tempestuous depths of the Gulf of Mannar to retrieve precious pearls and sacred sinistral chank shells.",
        "summary_ta": "\u0bae\u0ba4\u0bc1\u0bb0\u0bc8\u0b95\u0bcd\u0b95\u0bbe\u0b9e\u0bcd\u0b9a\u0bbf \u0ba8\u0bc6\u0baf\u0bcd\u0ba4\u0bb2\u0bcd \u0bb5\u0bb0\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0ba9\u0bcd\u0ba9\u0bbe\u0bb0\u0bcd \u0bb5\u0bb3\u0bc8\u0b95\u0bc1\u0b9f\u0bbe\u0bb5\u0bbf\u0ba9\u0bcd \u0b9a\u0bc1\u0bb4\u0bb2\u0bcd \u0ba8\u0bbf\u0bb1\u0bc8\u0ba8\u0bcd\u0ba4 \u0b86\u0bb4\u0bcd\u0b95\u0b9f\u0bb2\u0bbf\u0bb2\u0bcd \u0bae\u0bc2\u0bb4\u0bcd\u0b95\u0bbf, \u0b92\u0bb3\u0bbf\u0bb5\u0bc0\u0b9a\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0bb2\u0bae\u0bcd\u0baa\u0bc1\u0bb0\u0bbf\u0b9a\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0bc1\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b8e\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bb0\u0ba4\u0bb5\u0bb0\u0bcd \u0b95\u0bc1\u0bb2 \u0bae\u0bc2\u0bb4\u0bcd\u0b95\u0bbe\u0bb3\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba4\u0bbf\u0bb1\u0ba9\u0bc8\u0baa\u0bcd \u0baa\u0bcb\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9.",
        "sources": [
            "Maduraikanchi 134-148",
            "Akananuru 350",
            "Silappadikaram Kadalaadukathai"
        ],
        "content": "# Maduraikanchi: Classical Sangam Verses on Subaquatic Pearl Harvesters & Chank Divers\n\nThe classical Sangam anthology Maduraikanchi, sung by Mankudi Maruthanar in honor of the Pandyan king Nedunjeliyan, provides vivid poetic documentation of the bustling maritime economy and pearl fishery of the southern Tamil coast.\n\nThe text describes how seasoned Parathavar divers set out from coastal settlements before dawn aboard flotillas of canoes and catamarans. Plunging into the deep oceanic shelves (muthu-chalam) of the Gulf of Mannar, they defied benthic predators, dark whirlpools, and crushing water pressures to harvest wild oyster clusters (Pinctada fucata) and sacred marine chanks (Turbinella pyrum).\n\nThese verses highlight that pearl diving was not an individual pursuit but a highly coordinated communal science governed by deep ancestral knowledge of tides, lunar cycles, underwater bathymetry, and physical endurance."
    },
    {
        "file": "knowledge/concepts/concept-moochu-adakkal-ancient-tamil-apnea-and-lung-expansion-conditioning.md",
        "slug": "concept-moochu-adakkal-ancient-tamil-apnea-and-lung-expansion-conditioning",
        "category": "concept",
        "name_en": "Moochu-Adakkal: Ancient Tamil Breath-Holding, Lung Expansion & Hypercapnia Conditioning",
        "name_ta": "\u0bae\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1 \u0b85\u0b9f\u0b95\u0bcd\u0b95\u0bb2\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0ba4\u0bae\u0bbf\u0bb4\u0bb0\u0bcd \u0ba8\u0bc1\u0bb0\u0bc8\u0baf\u0bc0\u0bb0\u0bb2\u0bcd \u0b95\u0bca\u0bb3\u0bcd\u0bb3\u0bb3\u0bb5\u0bc1 \u0baa\u0baf\u0bbf\u0bb1\u0bcd\u0b9a\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1\u0b95\u0bcd\u0b95\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "neithal",
        "summary_en": "Somatic apnea methodology of Tamil pearl divers combining diaphragmatic pranayama, glossopharyngeal packing, and hypercapnia tolerance enabling subaquatic breath-holds of two to three minutes.",
        "summary_ta": "\u0ba4\u0bae\u0bbf\u0bb4\u0bb0\u0bcd \u0bae\u0bc2\u0bb4\u0bcd\u0b95\u0bbe\u0bb3\u0bb0\u0bcd \u0bae\u0bb0\u0baa\u0bbf\u0bb2\u0bcd \u0bb5\u0bbe\u0baf\u0bcd\u0bb5\u0bb4\u0bbf \u0b95\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0ba4\u0bbf\u0ba4\u0bb2\u0bcd, \u0b89\u0ba4\u0bb0\u0bb5\u0bbf\u0ba4\u0bbe\u0ba9\u0baa\u0bcd \u0baa\u0baf\u0bbf\u0bb1\u0bcd\u0b9a\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb0\u0bbf\u0baf\u0bae\u0bbf\u0bb2 \u0bb5\u0bbe\u0baf\u0bc1 \u0b8f\u0bb1\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bbf\u0bb1\u0ba9\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0ba8\u0bc0\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0b9f\u0bbf\u0baf\u0bbf\u0bb2\u0bcd 2 \u0bae\u0bc1\u0ba4\u0bb2\u0bcd 3 \u0ba8\u0bbf\u0bae\u0bbf\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bc2\u0b9a\u0bcd\u0b9a\u0b9f\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b89\u0b9f\u0bb1\u0bcd\u0baa\u0baf\u0bbf\u0bb1\u0bcd\u0b9a\u0bbf \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Maduraikanchi 138-142",
            "Thoothukudi Pearl Fishery Oral Archives",
            "Tirumandiram Pranayama"
        ],
        "content": "# Moochu-Adakkal: Ancient Tamil Breath-Holding & Lung Expansion Conditioning\n\nMoochu-Adakkal represents the rigorous somatic training developed over millennia by Tamil pearl and chank diving lineages along the Gulf of Mannar (Korkai, Kayal, and Kulasekharapatnam). Diver candidates began training in early boyhood, conditioned to remain subaquatic without artificial breathing apparatus.\n\nThe training regimen integrated deep diaphragmatic breathing akin to ancient Siddha pranayama, expanding vital lung capacity. Divers mastered glossopharyngeal inhalation (lung packing), gulping extra air volumes beyond total lung capacity to maximize oxygen stores prior to descent.\n\nCrucially, divers developed high neuro-chemical tolerance to hypercapnia (carbon dioxide accumulation) and hypoxia. Through daily repeated immersions, they suppressed the involuntary diaphragmatic spasms triggered by rising CO2 levels, allowing calm, focused benthic foraging for two to three minutes per dive."
    },
    {
        "file": "knowledge/technologies/technology-thoorvai-kal-granite-diving-sinker-stones-and-rope-retrieval.md",
        "slug": "technology-thoorvai-kal-granite-diving-sinker-stones-and-rope-retrieval",
        "category": "technology",
        "name_en": "Thoorvai-Kal: Granite Sinker Stones, Rapid Descent Ballasts & Coir Retrieval Lines",
        "name_ta": "\u0ba4\u0bc2\u0bb0\u0bcd\u0bb5\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bcd - \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b87\u0bb1\u0b99\u0bcd\u0b95\u0bc1 \u0b8e\u0b9f\u0bc8\u0b95\u0bcd\u0b95\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0bb4\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -600,
        "year_end": 1900,
        "thinai": "neithal",
        "summary_en": "Granite sinker ballast stones (thoorvai-kal) weighing 10-15 kg clasped between diver feet to accelerate descent down to 15 fathoms, paired with coir recovery ropes operated by boat tenders.",
        "summary_ta": "10 \u0bae\u0bc1\u0ba4\u0bb2\u0bcd 15 \u0b95\u0bbf\u0bb2\u0bcb \u0b8e\u0b9f\u0bc8\u0baf\u0bc1\u0bb3\u0bcd\u0bb3 \u0ba4\u0bc1\u0bb3\u0bc8\u0baf\u0bbf\u0b9f\u0bcd\u0b9f \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b87\u0bb1\u0b99\u0bcd\u0b95\u0bc1 \u0b8e\u0b9f\u0bc8\u0b95\u0bcd\u0b95\u0bb2\u0bcd (\u0ba4\u0bc2\u0bb0\u0bcd\u0bb5\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bcd), \u0ba8\u0bc0\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0b9f\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0bb5\u0bbf\u0bb0\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1 \u0b87\u0bb1\u0b99\u0bcd\u0b95\u0bb5\u0bc1\u0bae\u0bcd, \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0baa\u0b9f\u0b95\u0bc1\u0ba4\u0bcd \u0ba4\u0bcb\u0bb4\u0bb0\u0bbe\u0bb2\u0bcd \u0bae\u0bc0\u0ba3\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0b87\u0bb4\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bb5\u0bc1\u0bae\u0bcd \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Periplus of the Erythraean Sea",
            "Akananuru 210",
            "Duarte Barbosa Travelogues"
        ],
        "content": "# Thoorvai-Kal: Granite Sinker Stones & Rope Retrieval System\n\nThe fundamental mechanical aid in ancient Tamil pearl diving was the thoorvai-kal, a heavy, teardrop-shaped dressed granite or calcified limestone stone weighing between 10 and 15 kilograms. The stone had a bored perforation through its apex, threaded with a sturdy coir rope (thoorvai-kayiru).\n\nTo initiate a dive, the harvester stood on the outrigger or catamaran gunwale, slipped one foot into a stirrup loop attached to the sinker stone, took a final deep inhalation, and dropped into the ocean. The heavy ballast accelerated vertical descent through buoyant surface layers, achieving a descent velocity of 1.5 to 2 meters per second.\n\nThis rapid sink conserved the diver's precious muscular energy and oxygen reserves for benthic oyster collection. Upon reaching the seafloor (typically 5 to 15 fathoms), the diver slipped his foot free of the stone, and the topside boat assistant (thozhan) hauled the ballast stone back to the surface, leaving the diver free to crawl across the oyster bank."
    },
    {
        "file": "knowledge/concepts/concept-mammalian-dive-reflex-and-subaquatic-bradycardia-conditioning.md",
        "slug": "concept-mammalian-dive-reflex-and-subaquatic-bradycardia-conditioning",
        "category": "concept",
        "name_en": "Subaquatic Bradycardia Conditioning & Mammalian Dive Reflex in Tamil Divers",
        "name_ta": "\u0b86\u0bb4\u0bcd\u0b95\u0b9f\u0bb2\u0bcd \u0b87\u0ba4\u0baf\u0ba4\u0bcd\u0ba4\u0bc1\u0b9f\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0b9f\u0bcd\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0bb4\u0bcd\u0b95\u0bbe\u0bb3\u0bb0\u0bcd \u0b89\u0b9f\u0bb2\u0bcd \u0ba4\u0b95\u0bb5\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "neithal",
        "summary_en": "Physiological conditioning of the mammalian dive reflex among hereditary Tamil divers: profound facial immersion bradycardia, peripheral vasoconstriction, and splenic oxygen release.",
        "summary_ta": "\u0baa\u0bb0\u0bae\u0bcd\u0baa\u0bb0\u0bc8\u0ba4\u0bcd \u0ba4\u0bae\u0bbf\u0bb4\u0bcd \u0bae\u0bc2\u0bb4\u0bcd\u0b95\u0bbe\u0bb3\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0b9f\u0bae\u0bcd \u0b95\u0bc1\u0bb3\u0bbf\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4 \u0ba8\u0bc0\u0bb0\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bb5\u0bc1\u0b9f\u0ba9\u0bcd \u0b8f\u0bb1\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0b87\u0ba4\u0baf\u0ba4\u0bcd\u0ba4\u0bc1\u0b9f\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0b9f\u0bcd\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd (\u0baa\u0bbf\u0bb0\u0bbe\u0b9f\u0bbf\u0b95\u0bbe\u0bb0\u0bcd\u0b9f\u0bbf\u0baf\u0bbe), \u0b87\u0bb0\u0ba4\u0bcd\u0ba4 \u0ba8\u0bbe\u0bb3\u0b9a\u0bcd \u0b9a\u0bc1\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0ba3\u0bcd\u0ba3\u0bc0\u0bb0\u0bb2\u0bcd \u0b9a\u0bbf\u0bb5\u0baa\u0bcd\u0baa\u0ba3\u0bc1 \u0bb5\u0bc6\u0bb3\u0bbf\u0baf\u0bc0\u0b9f\u0bcd\u0b9f\u0bc1\u0ba4\u0bcd \u0ba4\u0b95\u0bb5\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1.",
        "sources": [
            "Sangam Physiological Studies",
            "Gulf of Mannar Diver Ethnography",
            "Natrinai 172"
        ],
        "content": "# Subaquatic Bradycardia Conditioning & Mammalian Dive Reflex\n\nHereditary Tamil pearl divers exhibited profound biological adaptation to the aquatic environment through lifelong activation of the mammalian dive reflex (MDR).\n\nUpon splashing cold sea water onto the face and submerging the ophthalmic branch of the trigeminal nerve, an immediate autonomic nervous reflex was triggered. The diver's heart rate experienced pronounced reflex bradycardia, dropping precipitously from a resting 75-80 beats per minute to as low as 35-40 beats per minute within 15 seconds of immersion.\n\nSimultaneously, intense peripheral vasoconstriction shunted oxygenated blood away from the limbs and non-vital muscular tissue, conserving the core oxygen pool exclusively for the brain, heart, and central nervous system. Furthermore, splenic contraction discharged concentrated reserves of oxygen-rich red blood cells into systemic circulation, extending safe benthic bottom time."
    },
    {
        "file": "knowledge/artifacts/artifact-mookku-channai-tortoiseshell-and-horn-diving-nose-clips.md",
        "slug": "artifact-mookku-channai-tortoiseshell-and-horn-diving-nose-clips",
        "category": "artifact",
        "name_en": "Mookku-Channai: Tortoiseshell, Buffalo Horn & Pliant Wooden Subaquatic Nose Clips",
        "name_ta": "\u0bae\u0bc2\u0b95\u0bcd\u0b95\u0bc1\u0b9a\u0bcd \u0b9a\u0ba9\u0bcd\u0ba9\u0bbe\u0baf\u0bcd - \u0b86\u0bae\u0bc8 \u0b93\u0b9f\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b8e\u0bb0\u0bc1\u0bae\u0bc8\u0b95\u0bcd\u0b95\u0bca\u0bae\u0bcd\u0baa\u0bc1 \u0b86\u0bb4\u0bcd\u0b95\u0b9f\u0bb2\u0bcd \u0bae\u0bc2\u0b95\u0bcd\u0b95\u0bc1 \u0b87\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbf",
        "era": "Sangam to Colonial Era",
        "year_start": -300,
        "year_end": 1850,
        "thinai": "neithal",
        "summary_en": "Traditional bifurcated compression nose clips carved from buffalo horn, tortoiseshell, or springy hardwood, lined with beeswax to maintain airtight nasal closure during rapid descents.",
        "summary_ta": "\u0b8e\u0bb0\u0bc1\u0bae\u0bc8\u0b95\u0bcd\u0b95\u0bca\u0bae\u0bcd\u0baa\u0bc1 \u0b85\u0bb2\u0bcd\u0bb2\u0ba4\u0bc1 \u0b86\u0bae\u0bc8 \u0b93\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bbe\u0bb2\u0bcd \u0b9a\u0bc6\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1, \u0ba4\u0bc7\u0ba9\u0bcd\u0bae\u0bc6\u0bb4\u0bc1\u0b95\u0bc1 \u0baa\u0bc2\u0b9a\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bae\u0bc2\u0b95\u0bcd\u0b95\u0bc1 \u0b87\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbf (\u0bae\u0bc2\u0b95\u0bcd\u0b95\u0bc1\u0b9a\u0bcd \u0b9a\u0ba9\u0bcd\u0ba9\u0bbe\u0baf\u0bcd), \u0b86\u0bb4\u0bcd\u0b95\u0b9f\u0bb2\u0bbf\u0bb2\u0bcd \u0ba8\u0bc0\u0bb0\u0bcd \u0bae\u0bc2\u0b95\u0bcd\u0b95\u0bbf\u0ba9\u0bc1\u0bb3\u0bcd \u0baa\u0bc1\u0b95\u0bbe\u0bae\u0bb2\u0bcd \u0ba4\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0bb0\u0bc1\u0bb5\u0bbf.",
        "sources": [
            "Marco Polo Travels Book III",
            "Akananuru 320",
            "Madras Fisheries Bureau Bulletin 1916"
        ],
        "content": "# Mookku-Channai: Tortoiseshell & Buffalo Horn Subaquatic Nose Clips\n\nThe mookku-channai was an essential personal diving artifact utilized by Gulf of Mannar pearl harvesters to maintain complete nasal seal during descent under severe hydrostatic pressure.\n\nHandcrafted by coastal artisans, the clip consisted of a flexible U-shaped bifurcated prong carved from seasoned water-buffalo horn or boiled hawksbill tortoiseshell. The interior clamping pads were lined with softened wild forest beeswax (thean-mezhugu) or natural tree resins to prevent chafing and slippage against wet skin.\n\nBy exerting steady bilateral compression across the alar cartilages, the mookku-channai completely barred salt water from entering the nasal cavity and sinuses, freeing both of the diver's hands for gripping the collection basket (koodai) and detaching stubborn oyster clusters from rocky reef outcrops."
    },
    {
        "file": "knowledge/concepts/concept-sevi-theerthal-tympanic-equalization-and-eustachian-clearing.md",
        "slug": "concept-sevi-theerthal-tympanic-equalization-and-eustachian-clearing",
        "category": "concept",
        "name_en": "Sevi-Theerthal: Tympanic Membrane Equalization & Eustachian Middle-Ear Clearance",
        "name_ta": "\u0b9a\u0bc6\u0bb5\u0bbf \u0ba4\u0bc0\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd - \u0ba8\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0ba4\u0bc1 \u0b85\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0b9a\u0bcd \u0b9a\u0bae\u0ba8\u0bbf\u0bb2\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc6\u0bb5\u0bbf\u0baa\u0bcd\u0baa\u0bb1\u0bc8 \u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "neithal",
        "summary_en": "Indigenous middle-ear equalization techniques (sevi-theerthal) utilizing voluntary swallow-jaw maneuvers and herbal ear ointments to equalize hydrostatic pressure up to 3.5 atmospheres.",
        "summary_ta": "\u0ba8\u0bc0\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0b9f\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0b87\u0bb1\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bcb\u0ba4\u0bc1 \u0b8f\u0bb1\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd 3.5 \u0bae\u0b9f\u0b99\u0bcd\u0b95\u0bc1 \u0ba8\u0bc0\u0bb0\u0bbf\u0baf\u0bb2\u0bcd \u0b85\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0ba4\u0bcd\u0ba4\u0bc8 \u0b88\u0b9f\u0bc1\u0b95\u0b9f\u0bcd\u0b9f, \u0ba4\u0bbe\u0b9f\u0bc8 \u0b85\u0b9a\u0bc8\u0bb5\u0bc1, \u0b89\u0bae\u0bbf\u0bb4\u0bcd\u0ba8\u0bc0\u0bb0\u0bcd \u0bb5\u0bbf\u0bb4\u0bc1\u0b99\u0bcd\u0b95\u0bc1\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0ba4\u0bcd \u0ba4\u0bc8\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0ba8\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0ba4\u0bc1 \u0b85\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0ba4\u0bcd\u0ba4\u0bc8\u0b9a\u0bcd \u0b9a\u0bae\u0ba9\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Agastya Siddha Maruthuvam",
            "Maduraikanchi 140",
            "Tuticorin Marine Heritage Records"
        ],
        "content": "# Sevi-Theerthal: Tympanic Membrane Equalization & Ear Clearance\n\nAs Tamil divers plunged to depths between 30 and 60 feet, ambient water pressure escalated from 1 to nearly 3 atmospheres, exerting intense inward compressive force against the delicate tympanic membranes (eardrums). Without rapid pressure equalization, divers faced agonizing middle-ear barotrauma or eardrum rupture.\n\nThe indigenous technique of sevi-theerthal involved continuous active clearing of the Eustachian tubes. Divers practiced jaw-thrusting movements, controlled swallowing, and guttural pharyngeal contractions (closely mirroring modern Frenzel and Valsalva equalization maneuvers) during every meter of descent.\n\nTo safeguard auditory canals against chronic salt irritation and external otitis, divers applied consecrated medicinal ear drops prepared from gingelly (sesame) oil infused with boiled garlic, calamus root (vasambu), and neem bark, preserving hearing acuity across decades of continuous diving."
    },
    {
        "file": "knowledge/institutions/institution-muthu-kuli-sangam-parathavar-diver-guild-and-chank-guilds.md",
        "slug": "institution-muthu-kuli-sangam-parathavar-diver-guild-and-chank-guilds",
        "category": "institution",
        "name_en": "Muthu-Kuli Sangam: Ancient Parathavar Pearl Harvester & Sacred Chank Diving Guilds",
        "name_ta": "\u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bbf\u0b9a\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0bae\u0bcd - \u0baa\u0bb0\u0ba4\u0bb5\u0bb0\u0bcd \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bcb\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bb2\u0bae\u0bcd\u0baa\u0bc1\u0bb0\u0bbf\u0b9a\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0bc1 \u0b8e\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bcb\u0bb0\u0bcd \u0bb5\u0ba3\u0bbf\u0b95\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bc1",
        "era": "Early Historic to Medieval Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "neithal",
        "summary_en": "Autonomous collegiate maritime guilds of Parathavar divers governing seasonal pearl oyster bank exploitation, fleet safety logistics, and royal royalty divisions in the Pandyan kingdom.",
        "summary_ta": "\u0bae\u0ba9\u0bcd\u0ba9\u0bbe\u0bb0\u0bcd \u0bb5\u0bb3\u0bc8\u0b95\u0bc1\u0b9f\u0bbe \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd \u0b95\u0bc1\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0bb0\u0bc1\u0bb5\u0b99\u0bcd\u0b95\u0bb3\u0bcd, \u0baa\u0b9f\u0b95\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf \u0b85\u0bb0\u0b9a\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0ba9 \u0baa\u0b99\u0bcd\u0b95\u0bc1\u0ba4\u0bcd \u0ba4\u0bc0\u0bb0\u0bcd\u0bb5\u0bc8 \u0b86\u0b95\u0bbf\u0baf\u0bb5\u0bb1\u0bcd\u0bb1\u0bc8 \u0ba8\u0bbf\u0bb0\u0bcd\u0bb5\u0b95\u0bbf\u0ba4\u0bcd\u0ba4 \u0baa\u0bb0\u0ba4\u0bb5\u0bb0\u0bcd \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bcb\u0bb0\u0bcd \u0ba4\u0ba9\u0bcd\u0ba9\u0bbe\u0b9f\u0bcd\u0b9a\u0bbf \u0bb5\u0ba3\u0bbf\u0b95\u0b95\u0bcd \u0b95\u0bbf\u0bb2\u0bcd\u0b9f\u0bc1.",
        "sources": [
            "Maduraikanchi 144",
            "Korkai Inscriptions",
            "Ibn Battuta Rihla"
        ],
        "content": "# Muthu-Kuli Sangam: Ancient Parathavar Pearl Diving Guilds\n\nThe Muthu-Kuli Sangam represented the formidable institutional framework through which the Parathavar maritime lineage organized and controlled the world's most lucrative natural pearl fisheries along the Gulf of Mannar.\n\nThe guild worked in close coordination with Pandyan crown officials, dispatching scouts to sample oyster banks (muthu-chalam) each spring. Once oyster maturity and pearl yield were confirmed, the guild proclaimed the official opening of the 30-to-40-day diving season, gathering thousands of divers, boatmen, gem merchants, and lapidaries.\n\nThe guild maintained strict operational protocols: determining daily catch quotas, coordinating emergency search and rescue craft, provisioning medical care on dive catamarans, and apportioning harvested oysters into standard tripartite shares\u2014one share for the ruling monarch, one for the diver and boat crew, and one for guild religious endowments and social safety nets."
    },
    {
        "file": "knowledge/concepts/concept-kadal-kattu-shark-protective-mantras-and-padi-safety-protocols.md",
        "slug": "concept-kadal-kattu-shark-protective-mantras-and-padi-safety-protocols",
        "category": "concept",
        "name_en": "Kadal-Kattu: Shark-Charming Mantras, Marine Hazard Rituals & Padi Dive Safety",
        "name_ta": "\u0b95\u0b9f\u0bb2\u0bcd\u0b95\u0b9f\u0bcd\u0b9f\u0bc1 - \u0b9a\u0bc1\u0bb1\u0bbe \u0b95\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0b9a\u0bcd \u0b9a\u0b9f\u0b99\u0bcd\u0b95\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bb1\u0bcd\u0baa\u0b9f\u0bc8 \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc6\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8\u0b95\u0bb3\u0bcd",
        "era": "Early Historic to Colonial Era",
        "year_start": -400,
        "year_end": 1850,
        "thinai": "neithal",
        "summary_en": "Traditional shark-charming rituals (kadal-kattu) combined with spotter-skiff safety cordons and communal signals protecting divers against benthic shark strikes.",
        "summary_ta": "\u0b86\u0bb4\u0bcd\u0b95\u0b9f\u0bb2\u0bcd \u0b9a\u0bc1\u0bb1\u0bbe\u0b95\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0bae\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0b9a\u0bcd \u0b9a\u0b9f\u0b99\u0bcd\u0b95\u0bc1\u0b95\u0bb3\u0bcd (\u0b95\u0b9f\u0bb2\u0bcd\u0b95\u0b9f\u0bcd\u0b9f\u0bc1) \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc7\u0bb2\u0bcd\u0ba4\u0bb3\u0b95\u0bcd \u0b95\u0ba3\u0bcd\u0b95\u0bbe\u0ba3\u0bbf\u0baa\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0b9f\u0b95\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0bae\u0bc2\u0bb4\u0bcd\u0b95\u0bbe\u0bb3\u0bb0\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0baa\u0bc1\u0b9a\u0bbe\u0bb0\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Marco Polo Travels Book III Chapter 16",
            "Maduraikanchi 145",
            "Ludovico di Varthema 1510"
        ],
        "content": "# Kadal-Kattu: Shark-Charming Mantras & Marine Safety Protocols\n\nIn the perilous waters of the Gulf of Mannar, shark attacks posed a severe occupational hazard to pearl divers. Ancient and medieval chroniclers, notably Marco Polo in 1292, recorded the profound institution of the kadal-kattu, overseen by hereditary shark-charmers (kadal-katti or pillai-katti).\n\nBefore any diver plunged into the sea, the charmer performed elaborate coastal propitiation rituals, casting protective mantras to 'blind the jaws' of ravenous tiger sharks and sawfish. Chroniclers noted that divers refused to enter the water without the charmer's presence and paid him a customary tribute of one oyster per boat load.\n\nBeneath this mystical veneer lay rigorous physical security measures: spotters on high catamaran masts vigilantly watched for dorsal fins in clear tropical waters, surface recovery boats formed protective perimeter cordons, and divers carried sharp obsidian or iron spikes attached to their waists for close-quarters defense."
    },
    {
        "file": "knowledge/concepts/concept-muthu-chalam-underwater-limestone-shoals-and-oyster-colony-mapping.md",
        "slug": "concept-muthu-chalam-underwater-limestone-shoals-and-oyster-colony-mapping",
        "category": "concept",
        "name_en": "Muthu-Chalam: Subaquatic Limestone Reef Bathymetry & Pinctada Oyster Colony Mapping",
        "name_ta": "\u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b9a\u0bcd\u0b9a\u0bb2\u0bae\u0bcd - \u0b95\u0b9f\u0bb2\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bb5\u0bb3\u0baa\u0bcd\u0baa\u0bbe\u0bb1\u0bc8 \u0b86\u0bb4\u0bb5\u0bb0\u0bc8\u0bb5\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd \u0b95\u0bbf\u0bb3\u0bbf\u0b9e\u0bcd\u0b9a\u0bb2\u0bcd \u0baa\u0b9f\u0bc1\u0b95\u0bc8 \u0bb5\u0bb0\u0bc8\u0bb5\u0bc1",
        "era": "Prehistoric to Modern Era",
        "year_start": -600,
        "year_end": 1900,
        "thinai": "neithal",
        "summary_en": "Indigenous hydrographic bathymetry of submerged calcified sandstone reefs (par / chalam) 6 to 12 miles offshore, monitoring oyster maturation, currents, and silt accumulation.",
        "summary_ta": "\u0b95\u0b9f\u0bb1\u0bcd\u0b95\u0bb0\u0bc8\u0baf\u0bbf\u0bb2\u0bbf\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 6 \u0bae\u0bc1\u0ba4\u0bb2\u0bcd 12 \u0bae\u0bc8\u0bb2\u0bcd \u0ba4\u0bca\u0bb2\u0bc8\u0bb5\u0bbf\u0bb2\u0bcd \u0b89\u0bb3\u0bcd\u0bb3 \u0b95\u0b9f\u0bb2\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bb5\u0bb3\u0baa\u0bcd\u0baa\u0bbe\u0bb1\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0b9f\u0bc1\u0b95\u0bc8\u0b95\u0bb3\u0bc8 (\u0baa\u0bbe\u0bb0\u0bcd / \u0b9a\u0bb2\u0bae\u0bcd) \u0ba4\u0bc1\u0bb2\u0bcd\u0bb2\u0bbf\u0baf\u0bae\u0bbe\u0b95 \u0bb5\u0bb0\u0bc8\u0baa\u0b9f\u0bae\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bbf\u0bb0\u0bcd\u0bb5\u0b95\u0bbf\u0ba4\u0bcd\u0ba4 \u0bae\u0bb0\u0baa\u0bc1 \u0bb5\u0bb0\u0bc8\u0bb5\u0bbf\u0baf\u0bb2\u0bcd.",
        "sources": [
            "Periplus Maris Erythraei 59",
            "Maduraikanchi 135",
            "James Hornell Pearl Fishery Survey 1905"
        ],
        "content": "# Muthu-Chalam: Subaquatic Limestone Reef Bathymetry\n\nThe Gulf of Mannar pearl fishery rested upon the remarkable indigenous science of muthu-chalam\u2014the mapping and ecological stewardship of underwater calcified sandstone banks known locally as par or chalam.\n\nThese natural oyster reefs, situated between 5 and 15 fathoms at distances of 6 to 12 nautical miles from the mainland shore, provided hard substrate upon which the spat of the pearl oyster (Pinctada fucata) could anchor with their strong byssus threads.\n\nTamil navigators maintained an elaborate mental hydrographic chart of these reefs, locating them accurately through coastal landmark triangulation (par-paarppathu), celestial stars, and sounding leads with tallow cups that sampled the seafloor sediment. They monitored cyclical oyster lifespans, enforcing multi-year fallow periods to prevent over-harvesting and ensure sustainable pearl regeneration."
    },
    {
        "file": "knowledge/places/place-kulasekharapatnam-ancient-pearl-diver-and-apnea-haven.md",
        "slug": "place-kulasekharapatnam-ancient-pearl-diver-and-apnea-haven",
        "category": "place",
        "name_en": "Kulasekharapatnam: Ancient Pandya Pearl Diving, Apnea Fleet & Maritime Haven",
        "name_ta": "\u0b95\u0bc1\u0bb2\u0b9a\u0bc7\u0b95\u0bb0\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bae\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bc1, \u0bae\u0bc2\u0bb4\u0bcd\u0b95\u0bbe\u0bb3\u0bb0\u0bcd \u0ba4\u0bb3\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc6\u0baf\u0bcd\u0ba4\u0bb2\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0bae\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "neithal",
        "summary_en": "Celebrated coastal port in southern Tamil Nadu, renowned as a primary seasonal staging harbor for Pandyan pearl diver fleets, diver training schools, and international gem trade.",
        "summary_ta": "\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd \u0baa\u0bc7\u0bb0\u0bb0\u0b9a\u0bbf\u0ba9\u0bcd \u0bae\u0bc1\u0ba4\u0ba9\u0bcd\u0bae\u0bc8 \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95 \u0ba8\u0b95\u0bb0\u0bcd; \u0bae\u0bc2\u0bb4\u0bcd\u0b95\u0bbe\u0bb3\u0bb0\u0bcd \u0baa\u0baf\u0bbf\u0bb1\u0bcd\u0b9a\u0bbf\u0b95\u0bcd \u0b95\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bcd, \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0baa\u0bcd \u0baa\u0bb0\u0bbf\u0bb5\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0ba9\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc6\u0baf\u0bcd\u0ba4\u0bb2\u0bcd \u0ba8\u0bbe\u0b95\u0bb0\u0bbf\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb2\u0bbf\u0b9f\u0bae\u0bcd.",
        "sources": [
            "Kulasekharapatnam Inscriptions",
            "Maduraikanchi",
            "Marco Polo Travels"
        ],
        "content": "# Kulasekharapatnam: Ancient Pearl Diver Haven\n\nKulasekharapatnam, situated on the tranquil shores of the Gulf of Mannar south of Korkai and Tiruchendur, flourished as an essential maritime hub for ancient and medieval Tamil pearl fisheries.\n\nEndowed with sheltered coastal lagoons and immediate access to the offshore pearl oyster banks (chalam), the harbor served as the seasonal encampment where thousands of Parathavar divers, tenders, and merchants gathered. Fleets of catamarans and padagu longboats lined the sandy beaches, departing in synchronized flotillas at dawn.\n\nThe city housed diver training academies where youths honed the rigorous art of moochu-adakkal and equalization in protected coastal waters. Excavations and epigraphical records confirm extensive commercial interactions with Roman, Arab, and Venetian traders who flocked to Kulasekharapatnam to purchase radiant Pandyan pearls."
    }
]
EDGES = [
    [
        "concept-moochu-adakkal-ancient-tamil-apnea-and-lung-expansion-conditioning",
        "REQUIRES",
        "concept-mammalian-dive-reflex-and-subaquatic-bradycardia-conditioning",
        "core",
        "Prehistoric to Modern Era",
        "Apnea breath-holding relies upon conditioned autonomic mammalian dive reflex and subaquatic bradycardia.",
        "Maduraikanchi 138-142"
    ],
    [
        "technology-thoorvai-kal-granite-diving-sinker-stones-and-rope-retrieval",
        "UTILIZES",
        "place-kulasekharapatnam-ancient-pearl-diver-and-apnea-haven",
        "core",
        "Prehistoric to Modern Era",
        "Granite sinker stones were manufactured and deployed from the coastal staging port of Kulasekharapatnam.",
        "Kulasekharapatnam Maritime Records"
    ],
    [
        "artifact-mookku-channai-tortoiseshell-and-horn-diving-nose-clips",
        "ENABLES",
        "concept-moochu-adakkal-ancient-tamil-apnea-and-lung-expansion-conditioning",
        "core",
        "Sangam to Colonial Era",
        "Airtight nasal compression clips allow divers to conserve oxygen and descend hands-free without water ingress.",
        "Marco Polo Travels Book III"
    ],
    [
        "text-maduraikanchi-verses-on-gulf-of-mannar-subaquatic-pearl-harvesters",
        "DOCUMENTS",
        "institution-muthu-kuli-sangam-parathavar-diver-guild-and-chank-guilds",
        "core",
        "Sangam Era",
        "Maduraikanchi provides foundational literary documentation of organized Parathavar diving corporations.",
        "Maduraikanchi 134-148"
    ],
    [
        "institution-muthu-kuli-sangam-parathavar-diver-guild-and-chank-guilds",
        "GOVERNS",
        "concept-muthu-chalam-underwater-limestone-shoals-and-oyster-colony-mapping",
        "core",
        "Early Historic to Medieval Era",
        "The diver guild systematically regulated access, fallow rotations, and harvest quotas across offshore oyster shoals.",
        "Korkai Inscriptions"
    ],
    [
        "concept-kadal-kattu-shark-protective-mantras-and-padi-safety-protocols",
        "SAFEGUARDS",
        "concept-moochu-adakkal-ancient-tamil-apnea-and-lung-expansion-conditioning",
        "core",
        "Early Historic to Colonial Era",
        "Shark protective rituals and surface perimeter boats safeguarded apnea divers from apex marine predators.",
        "Marco Polo Travels Chapter 16"
    ],
    [
        "concept-sevi-theerthal-tympanic-equalization-and-eustachian-clearing",
        "ENABLES",
        "concept-moochu-adakkal-ancient-tamil-apnea-and-lung-expansion-conditioning",
        "core",
        "Prehistoric to Modern Era",
        "Eustachian pressure equalization prevents debilitating barotrauma during high-velocity vertical descents.",
        "Agastya Siddha Maruthuvam"
    ],
    [
        "concept-muthu-chalam-underwater-limestone-shoals-and-oyster-colony-mapping",
        "LOCATED_AT",
        "place-kulasekharapatnam-ancient-pearl-diver-and-apnea-haven",
        "core",
        "Prehistoric to Modern Era",
        "Primary natural oyster shoals and coral reefs were mapped directly off the coast of Kulasekharapatnam.",
        "James Hornell Survey 1905"
    ],
    [
        "concept-moochu-adakkal-ancient-tamil-apnea-and-lung-expansion-conditioning",
        "PRACTICED_AT",
        "place-kulasekharapatnam-ancient-pearl-diver-and-apnea-haven",
        "core",
        "Prehistoric to Modern Era",
        "Apnea breath-holding academies and seasonal diving fleets were headquartered at Kulasekharapatnam.",
        "Maduraikanchi 144"
    ],
    [
        "institution-muthu-kuli-sangam-parathavar-diver-guild-and-chank-guilds",
        "ANCHORED_AT",
        "place-kulasekharapatnam-ancient-pearl-diver-and-apnea-haven",
        "core",
        "Early Historic to Medieval Era",
        "The collegiate diver guild maintained extensive harbor administration facilities at Kulasekharapatnam.",
        "Kulasekharapatnam Epigraphs"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Ancient Tamil Pearl Diver Breath-Control & Subaquatic Physiology into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Ancient Tamil Pearl Diver Breath-Control & Subaquatic Physiology Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
