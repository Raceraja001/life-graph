#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Shipwright Hull Joinery, Tenon Planking & Caulking Resins
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
        "file": "knowledge/texts/text-perumpanattruppadai-verses-on-oceanic-masted-vessels-and-shipwright-harbors.md",
        "slug": "text-perumpanattruppadai-verses-on-oceanic-masted-vessels-and-shipwright-harbors",
        "category": "text",
        "name_en": "Perumpanattruppadai: Classical Sangam Verses on Oceanic Masted Vessels & Shipwright Harbors",
        "name_ta": "\u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0ba3\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc8 - \u0b86\u0bb4\u0bcd\u0b95\u0b9f\u0bb2\u0bcd \u0ba8\u0bbe\u0bb5\u0bbe\u0baf\u0bcd, \u0b95\u0bc2\u0bae\u0bcd\u0baa\u0bca\u0b9f\u0bc1 \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "neithal",
        "summary_en": "Classical Sangam verses by Kadiyalur Uruthirankannanar describing colossal seagoing vessels with towering masts, billowing sails, and active coastal shipwright yards.",
        "summary_ta": "\u0bb5\u0bbe\u0ba9\u0bb3\u0bbe\u0bb5\u0bbf\u0baf \u0b95\u0bc2\u0bae\u0bcd\u0baa\u0bc1, \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b86\u0bb4\u0bcd\u0b95\u0b9f\u0bb2\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0b95\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0b9f\u0bb2\u0bcb\u0bb0\u0ba4\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b89\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0bb0\u0b99\u0bcd\u0b95\u0ba3\u0bcd\u0ba3\u0ba9\u0bbe\u0bb0\u0bbf\u0ba9\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0ba3\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc8.",
        "sources": [
            "Perumpanattruppadai 319-351",
            "Maduraikanchi 320",
            "Purananuru 30"
        ],
        "content": "# Perumpanattruppadai: Classical Sangam Verses on Oceanic Masted Vessels\n\nIn the ancient Sangam anthology Perumpanattruppadai, composed by Kadiyalur Uruthirankannanar in praise of the Thondaimaan king Ilandhiraiyan, classical Tamil literature offers vivid poetic documentation of oceanic naval architecture.\n\nThe poet describes majestic seagoing merchant vessels (naavaai / marakkalam) anchored in deep estuaries. With their towering timber masts (koombu) reaching toward the clouds, billowing multi-layered sails, and massive hull timbers, these ships resembled mountain ridges rising from the sea.\n\nThe text celebrates the ceaseless activity of coastal shipyards, where master shipwrights shaped monumental timbers, fitted planks with precision joinery, and launched ocean-going vessels destined for Southeast Asia, Sri Lanka, and the Roman world."
    },
    {
        "file": "knowledge/concepts/concept-kappal-kattu-ancient-tamil-edge-joined-tenon-and-sewn-hull-mechanics.md",
        "slug": "concept-kappal-kattu-ancient-tamil-edge-joined-tenon-and-sewn-hull-mechanics",
        "category": "concept",
        "name_en": "Kappal-Kattu: Ancient Tamil Edge-Joined Tenon & Sewn-Plank Naval Architecture",
        "name_ta": "\u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1 - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0ba4\u0bae\u0bbf\u0bb4\u0bb0\u0bcd \u0bb5\u0bbf\u0bb3\u0bbf\u0bae\u0bcd\u0baa\u0bc1 \u0b87\u0ba3\u0bc8 \u0ba8\u0bbe\u0bb5\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc8\u0baf\u0bb2\u0bcd \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Prehistoric to Modern Era",
        "year_start": -600,
        "year_end": 1900,
        "thinai": "neithal",
        "summary_en": "Advanced maritime naval architecture combining edge-joined pegged mortise-and-tenon planking with flexible coconut coir stitches, yielding resilient elastic hulls able to absorb oceanic waves.",
        "summary_ta": "\u0bae\u0bb0\u0baa\u0bcd\u0baa\u0bb2\u0b95\u0bc8\u0b95\u0bb3\u0bc8 \u0bae\u0bb0 \u0b86\u0ba3\u0bbf \u0ba8\u0bbe\u0bb5\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0ba4\u0bc6\u0ba9\u0bcd\u0ba9\u0b99\u0bcd\u0b95\u0baf\u0bbf\u0bb1\u0bcd\u0bb1\u0bbf\u0ba9\u0bbe\u0bb2\u0bcd \u0ba4\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b87\u0ba3\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bc6\u0b95\u0bbf\u0bb4\u0bcd\u0bb5\u0bc1\u0ba4\u0bcd\u0ba4\u0ba9\u0bcd\u0bae\u0bc8 \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0baa\u0bc1\u0b9a\u0bbe\u0bb0\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0b9f\u0b95\u0bcd\u0b95\u0bb2\u0bc8.",
        "sources": [
            "Periplus Maris Erythraei 60",
            "Silappadikaram 10",
            "Ancient Indian Naval Architecture Studies"
        ],
        "content": "# Kappal-Kattu: Edge-Joined Tenon & Sewn Hull Architecture\n\nKappal-Kattu refers to the ancient Tamil science of wooden naval architecture developed to construct durable, ocean-crossing commercial and naval craft.\n\nRather than relying on brittle iron nails that rapidly corrode in tropical marine salinity, Tamil shipwrights developed a composite joinery system. Heavy planks of wild jackfruit (Artocarpus heterophyllus) and teak were edge-joined using precision hardwood mortise-and-tenon splines locked in place with internal wooden dowels (maravani).\n\nAlong the plank seams, paired diagonal perforations were bored through the inner edges. Heavy strands of three-ply coconut coir yarn (kayiru) were stitched through these holes over a wadding of coconut husk fiber. This unique sewn-plank construction endowed the hull with extraordinary longitudinal elasticity, allowing the vessel to flex organically over violent oceanic swell without springing leaks or breaking ribs."
    },
    {
        "file": "knowledge/technologies/technology-marakkalam-and-vangam-multi-decked-transoceanic-wooden-cargo-hulls.md",
        "slug": "technology-marakkalam-and-vangam-multi-decked-transoceanic-wooden-cargo-hulls",
        "category": "technology",
        "name_en": "Marakkalam & Vangam: Multi-Decked Transoceanic Wooden Cargo Hulls & Ballasts",
        "name_ta": "\u0bae\u0bb0\u0b95\u0bcd\u0b95\u0bb2\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0b99\u0bcd\u0b95\u0bae\u0bcd - \u0baa\u0bb2 \u0ba4\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0b86\u0bb4\u0bcd\u0b95\u0b9f\u0bb2\u0bcd \u0b9a\u0bb0\u0b95\u0bcd\u0b95\u0bc1\u0b95\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bbf\u0bb2\u0bc8\u0ba4\u0bcd\u0ba4\u0ba9\u0bcd\u0bae\u0bc8 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Early Historic to Medieval Era",
        "year_start": -300,
        "year_end": 1400,
        "thinai": "neithal",
        "summary_en": "Colossal multi-decked seagoing merchant vessels (marakkalam and vangam) displacing 300 to 500 metric tons, engineered for trans-oceanic navigation across the Bay of Bengal to Malacca.",
        "summary_ta": "300 \u0bae\u0bc1\u0ba4\u0bb2\u0bcd 500 \u0b9f\u0ba9\u0bcd \u0b9a\u0bb0\u0b95\u0bcd\u0b95\u0bc1 \u0b9a\u0bc1\u0bae\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bbf\u0bb1\u0ba9\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f, \u0baa\u0bb2 \u0b85\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0b89\u0b9f\u0bc8\u0baf \u0b86\u0bb4\u0bcd\u0b95\u0b9f\u0bb2\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd\u0b95\u0bb3\u0bcd (\u0bb5\u0b99\u0bcd\u0b95\u0bae\u0bcd, \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0bb2\u0bae\u0bcd); \u0bb5\u0b99\u0bcd\u0b95\u0b95\u0bcd \u0b95\u0b9f\u0bb2\u0bc8\u0b95\u0bcd \u0b95\u0b9f\u0ba8\u0bcd\u0ba4\u0bc1 \u0bae\u0bb2\u0bbe\u0b95\u0bcd\u0b95\u0bbe \u0bb5\u0bb0\u0bc8 \u0b9a\u0bc6\u0ba9\u0bcd\u0bb1 \u0ba8\u0bbe\u0bb5\u0bbe\u0baf\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Manimekalai 11.80",
            "Chinese Song Dynasty Maritime Annals",
            "Chola Naval Inscriptions"
        ],
        "content": "# Marakkalam & Vangam: Multi-Decked Transoceanic Vessels\n\nThe largest vessels of ancient and medieval Tamil maritime commerce were known as the marakkalam (heavy timber ship) and vangam (spacious ocean transport), celebrated in classical literature and foreign chronicles.\n\nThese vessels measured up to 30 to 45 meters in length and carried displacements of 300 to 500 metric tons. Constructed with multi-tiered transverse decks, they accommodated hundreds of merchants, crew, water cisterns, and voluminous cargo holds filled with textiles, spices, ceramics, and aromatics.\n\nThe hull was built on a deep central spine keel (keel-maram) carved from dense Ceylon ironwood (Poovam) or Shorea robusta, which stabilized the ship against lateral leeway drift. Compartmentalized bulkheads divided the lower hold, containing sea water ingress in case of collision and ensuring trans-oceanic voyages across the Indian Ocean."
    },
    {
        "file": "knowledge/artifacts/artifact-kungiliyam-and-ennai-boiled-dammar-resin-and-fish-oil-marine-caulking.md",
        "slug": "artifact-kungiliyam-and-ennai-boiled-dammar-resin-and-fish-oil-marine-caulking",
        "category": "artifact",
        "name_en": "Kungiliyam & Ennai: Boiled Dammar Resin, Lime & Fish Oil Marine Waterproof Caulking",
        "name_ta": "\u0b95\u0bc1\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bbf\u0baf\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b8e\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd - \u0bae\u0bb0\u0baa\u0bcd\u0baa\u0bbf\u0b9a\u0bbf\u0ba9\u0bcd, \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc0\u0ba9\u0bcd \u0ba8\u0bc6\u0baf\u0bcd \u0b95\u0b9f\u0bb2\u0bcd \u0ba8\u0bc0\u0bb0\u0bcd\u0baa\u0bc1\u0b95\u0bbe \u0b95\u0bbe\u0bb0\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "neithal",
        "summary_en": "Indigenous marine caulking compound (kungiliyam-pal) made by boiling dammar tree resins, slaked shell lime, and pelagic shark/ray liver oil into an impermeable elastic pitch.",
        "summary_ta": "\u0b95\u0bc1\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bbf\u0baf \u0bae\u0bb0\u0baa\u0bcd\u0baa\u0bbf\u0b9a\u0bbf\u0ba9\u0bcd, \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf\u0b9a\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0bb1\u0bbe \u0b95\u0bb2\u0bcd\u0bb2\u0bc0\u0bb0\u0bb2\u0bcd \u0ba8\u0bc6\u0baf\u0bcd\u0baf\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0ba4\u0bbf\u0b95\u0bcd\u0b95 \u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd, \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0baa\u0bb2\u0b95\u0bc8 \u0b87\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0baa\u0bc2\u0b9a\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0ba8\u0bc0\u0bb0\u0bcd\u0baa\u0bc1\u0b95\u0bbe \u0bae\u0bb0\u0baa\u0bc1\u0b9a\u0bbe\u0bb0\u0bcd \u0b95\u0bbe\u0bb0\u0bc8.",
        "sources": [
            "Siddha Maritime Treatises",
            "Ibn Battuta Travels",
            "Adirampattinam Shipyard Archives"
        ],
        "content": "# Kungiliyam & Ennai: Marine Waterproof Caulking\n\nA critical technological key to the seaworthiness of Tamil stitched and pegged wooden hulls was the formulation of waterproof caulking compounds (kungiliyam-pal or pitch).\n\nShipwrights formulated this marine pitch by boiling natural dammar resin (kungiliyam) extracted from Shorea robusta or Canarium strictum trees in heavy iron cauldrons, blending it with rich animal lipids\u2014specifically shark liver oil (meen-nei) or ray fish liver fat. To provide body and setting strength, finely calcined marine oyster shell lime (sunnambu) and pulverized coir dust were mixed into the bubbling mass.\n\nWhile still molten, this viscous elastic compound was forced into every plank seam, joint spline, and stitching hole using wooden tamping irons. Upon cooling, it formed an impenetrable, flexible, rubbery gasket that bonded aggressively to timber fibers, expanding slightly when wetted to maintain a hermetic seal against relentless sea-water pressure."
    },
    {
        "file": "knowledge/technologies/technology-sukkaan-and-paai-maram-axial-quarter-rudders-and-woven-mat-rigging.md",
        "slug": "technology-sukkaan-and-paai-maram-axial-quarter-rudders-and-woven-mat-rigging",
        "category": "technology",
        "name_en": "Sukkaan & Paai-Maram: Twin Axial Quarter-Rudders & Woven Pandanus Mat Sails",
        "name_ta": "\u0b9a\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0ba9\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0bae\u0bcd - \u0b87\u0bb0\u0b9f\u0bcd\u0b9f\u0bc8\u0baa\u0bcd \u0baa\u0b95\u0bcd\u0b95\u0bb5\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0b9a\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0ba9\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bbe\u0bb4\u0bc8\u0baa\u0bcd\u0baa\u0bbe\u0baf\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Steering and propulsion mechanics of ancient Tamil vessels: twin heavy quarter steering rudders (sukkaan) operated via tiller lines and multi-masted woven pandanus mat sails.",
        "summary_ta": "\u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bbf\u0ba9\u0bcd \u0b87\u0bb0\u0bc1\u0baa\u0bc1\u0bb1\u0bae\u0bc1\u0bae\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0b95\u0bcd\u0b95\u0bb5\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0ba4\u0bcd \u0ba4\u0bc1\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0ba9\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bb2\u0ba4\u0bcd\u0ba4 \u0b95\u0bbe\u0bb1\u0bcd\u0bb1\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba4\u0bbe\u0bb4\u0bc8 \u0ba8\u0bbe\u0bb0\u0bcd\u0baa\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0 \u0b87\u0baf\u0b95\u0bcd\u0b95\u0bae\u0bcd.",
        "sources": [
            "Silappadikaram 13.175",
            "Manimekalai 4",
            "Traditional Tamil Maritime Vocabulary Studies"
        ],
        "content": "# Sukkaan & Paai-Maram: Steering Mechanics & Rigging\n\nNavigating massive multi-decked wooden ships across monsoon wind belts demanded efficient steering and aerodynamic rigging.\n\nTamil ships utilized twin axial quarter-rudders (sukkaan / thuzhavu), suspended from heavy cross-beams at the port and starboard quarters of the stern. Operated by helmsmen using cross-tillers and leather steering cables, these large hydrodynamic foils provided powerful turning leverage even in heavy following seas.\n\nPropulsion was derived from two or three towering stepped timber masts (paai-maram). The rigging hoisted large square and lateen sails woven from treated pandanus leaves (thazhai-paai) or dense cotton canvas treated with bark tannins. By adjusting brace lines (theruppu-kayiru), Tamil navigators tacked close to the wind, exploiting seasonal trade winds to cross the open ocean."
    },
    {
        "file": "knowledge/institutions/institution-marakkar-kappal-thatchar-corporation-guild-of-naval-shipwrights.md",
        "slug": "institution-marakkar-kappal-thatchar-corporation-guild-of-naval-shipwrights",
        "category": "institution",
        "name_en": "Marakkar & Kappal-Thatchar Corporation: Hereditary Guild of Naval Shipwrights",
        "name_ta": "\u0bae\u0bb0\u0bc8\u0b95\u0bcd\u0b95\u0bbe\u0baf\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bb0\u0bcd \u0b95\u0bbf\u0bb2\u0bcd\u0b9f\u0bc1 - \u0bae\u0bb0\u0baa\u0bc1\u0b9a\u0bbe\u0bb0\u0bcd \u0b95\u0b9f\u0bb1\u0bcd\u0baa\u0b9f\u0bc8\u0b95\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0bb5\u0bcb\u0bb0\u0bcd \u0b95\u0bc8\u0bb5\u0bbf\u0ba9\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bc1\u0bae\u0bae\u0bcd",
        "era": "Early Historic to Modern Era",
        "year_start": -300,
        "year_end": 1900,
        "thinai": "neithal",
        "summary_en": "Autonomous artisan corporation of master ship architects, plankwrights, and caulkers (kappal-thatchar) governing drydock construction, naval standards, and maritime trade alliances.",
        "summary_ta": "\u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bb0\u0bcd\u0b95\u0bb3\u0bcd, \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0b95\u0bcd \u0b95\u0bc8\u0bb5\u0bbf\u0ba9\u0bc8\u0b9e\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0b89\u0bb0\u0bbf\u0bae\u0bc8\u0baf\u0bbe\u0bb3\u0bb0\u0bcd\u0b95\u0bb3\u0bc8 \u0b92\u0ba9\u0bcd\u0bb1\u0bbf\u0ba3\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b87\u0baf\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0ba4\u0ba9\u0bcd\u0ba9\u0bbe\u0b9f\u0bcd\u0b9a\u0bbf \u0b95\u0b9f\u0bb1\u0bcd\u0baa\u0b9f\u0bc8 \u0bb5\u0ba3\u0bbf\u0b95\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bc1\u0bae\u0bae\u0bcd.",
        "sources": [
            "Nagapattinam Chola Epigraphs",
            "Palk Bay Oral Traditions",
            "Dutch East India Company Records"
        ],
        "content": "# Marakkar & Kappal-Thatchar Corporation: Naval Shipwright Guild\n\nThe construction of oceanic vessels was organized under the hereditary guild authority of the Kappal-Thatchar (shipwright carpenters) in close coordination with coastal maritime families (Marakkars and Parathavars).\n\nOperating in sheltered estuaries, lagoons, and sandy creeks along Palk Bay and the Coromandel coast, the guild maintained dedicated shipyards (kappal-thalam or thoni-kudil). The guild regulated the entire production cycle: dispatching scouts to forest reserves to mark suitable timber trunks, calibrating hull ratios according to traditional measurement verses (kappal-sastiram), and supervising hundreds of apprentices.\n\nRoyal charters from the Chola and Pandya crowns granted these shipwright corporations tax exemptions, timber rights in state forests, and shares in overseas voyages, anchoring Tamil naval power across Indian Ocean history."
    },
    {
        "file": "knowledge/concepts/concept-paara-kal-ballast-stone-trim-and-hydrodynamic-keel-stability.md",
        "slug": "concept-paara-kal-ballast-stone-trim-and-hydrodynamic-keel-stability",
        "category": "concept",
        "name_en": "Paara-Kal: Granite Ballast Stone Trim, Bilge Pumping & Metacentric Stability",
        "name_ta": "\u0baa\u0bbe\u0bb1\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bcd - \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0ba8\u0bbf\u0bb2\u0bc8\u0baa\u0bcd\u0baa\u0bbe\u0bb0\u0b95\u0bcd \u0b95\u0bb2\u0bcd, \u0b85\u0b9f\u0bbf\u0ba8\u0bc0\u0bb0\u0bcd \u0b87\u0bb1\u0bc8\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bbf\u0ba4\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bbf\u0bb2\u0bc8\u0ba4\u0bcd\u0ba4\u0ba9\u0bcd\u0bae\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "neithal",
        "summary_en": "Naval stability mechanics using dressed granite ballast stones (paara-kal) laid in the lowest hold to lower the center of gravity and maintain metacentric righting moments.",
        "summary_ta": "\u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bbf\u0ba9\u0bcd \u0b85\u0b9f\u0bbf\u0baa\u0bcd\u0baa\u0b95\u0bc1\u0ba4\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0baa\u0bbe\u0bb1\u0bc8\u0b95\u0bb3\u0bc8 \u0b85\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbf \u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 (\u0ba8\u0bbf\u0bb2\u0bc8\u0baa\u0bcd\u0baa\u0bbe\u0bb0\u0bae\u0bcd), \u0baa\u0bc1\u0bb5\u0bbf\u0baf\u0bc0\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bc8\u0baf\u0ba4\u0bcd\u0ba4\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0bb1\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0b95\u0b9f\u0bb2\u0bcd \u0b95\u0bca\u0ba8\u0bcd\u0ba4\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bbf\u0bb2\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0b95\u0bb5\u0bbf\u0bb4\u0bbe\u0bae\u0bb2\u0bcd \u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bbf\u0bb2\u0bc8\u0ba4\u0bcd\u0ba4\u0ba9\u0bcd\u0bae\u0bc8 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Archaeological Marine Excavations in Tamil Nadu",
            "Purananuru 30",
            "Ancient Shipbuilding Treatises"
        ],
        "content": "# Paara-Kal: Ballast Stone Trim & Metacentric Stability\n\nMaintaining the upright stability of high-sided wooden cargo vessels under rolling ocean swell required precise control of deadweight ballast (paara-kal).\n\nTamil shipwrights loaded tons of smooth, dressed granite stones and river boulders into the lowest bilge compartment directly above the keel timbers before loading commercial cargo. This substantial ballast weight lowered the vessel's vertical center of gravity, significantly expanding its metacentric height.\n\nAs the ship rolled under heavy beam waves, the low-set ballast generated powerful righting moments, preventing catastrophic capsize. Marine archaeological surveys across South and Southeast Asian waters frequently locate these unmistakable Tamil granite ballast mounds, marking ancient shipwrecks and revealing precise ballast stowage patterns."
    },
    {
        "file": "knowledge/artifacts/artifact-irumbu-aani-and-maravani-corrosion-resistant-bronze-and-copper-sheathing-clenches.md",
        "slug": "artifact-irumbu-aani-and-maravani-corrosion-resistant-bronze-and-copper-sheathing-clenches",
        "category": "artifact",
        "name_en": "Irumbu-Aani & Maravani: Copper Clenches, Hardwood Treenails & Lead Sheathing",
        "name_ta": "\u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0b86\u0ba3\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0bb5\u0bbe\u0ba3\u0bbf - \u0ba4\u0bbe\u0bae\u0bbf\u0bb0\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0bc8 \u0b86\u0ba3\u0bbf, \u0b95\u0b9f\u0bbf\u0ba9 \u0bae\u0bb0 \u0b86\u0ba3\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b88\u0baf\u0ba4\u0bcd \u0ba4\u0b95\u0b9f\u0bc1 \u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Early Historic to Modern Era",
        "year_start": -300,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Non-corrosive marine fasteners: through-driven hardwood treenails (maravani), hammered copper clench bolts, and beaten lead hull sheathing plates resisting marine mollusks.",
        "summary_ta": "\u0b89\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc0\u0bb0\u0bbe\u0bb2\u0bcd \u0b85\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bbe\u0ba4 \u0b95\u0b9f\u0bbf\u0ba9 \u0bae\u0bb0 \u0b86\u0ba3\u0bbf\u0b95\u0bb3\u0bcd (\u0bae\u0bb0\u0bb5\u0bbe\u0ba3\u0bbf), \u0b85\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4 \u0ba4\u0b9f\u0bcd\u0b9f\u0bc8\u0baf\u0bbe\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0ba4\u0bbe\u0bae\u0bbf\u0bb0 \u0b86\u0ba3\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bc1\u0bb4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b88\u0baf\u0ba4\u0bcd \u0ba4\u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0baa\u0bcd \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1.",
        "sources": [
            "Poompuhar Underwater Artifact Catalog",
            "Periplus of the Erythraean Sea",
            "Siddha Metal Science"
        ],
        "content": "# Irumbu-Aani & Maravani: Marine Fasteners & Copper Sheathing\n\nWhere mechanical fastening through thick frames was mandatory, Tamil shipwrights selected corrosion-resistant metallurgy over plain wrought iron.\n\nPlank-to-frame fastenings utilized long, cylindrical hardwood treenails (maravani) carved from dense Acacia (Karuvelam) or Teak. Once driven through pre-drilled holes in the hull planks and internal ribs, small wooden wedges were driven into both split ends of the pin, locking the timbers together in a permanent grip that swelled tighter in water.\n\nFor critical stem and sternpost reinforcements, blacksmiths forged annealed copper and bronze through-bolts and clench nails that resisted saltwater oxidation. On deep-sea vessels, the underwater hull was clad in thin sheets of cold-hammered lead or copper, protecting the structural timbers from destructive marine shipworm (teredo navalis) infestations."
    },
    {
        "file": "knowledge/concepts/concept-maram-kaindhal-saline-timber-seasoning-and-marine-borer-immunization.md",
        "slug": "concept-maram-kaindhal-saline-timber-seasoning-and-marine-borer-immunization",
        "category": "concept",
        "name_en": "Maram-Kaindhal: Saline Timber Seasoning, Smoke Curing & Borer Resistance",
        "name_ta": "\u0bae\u0bb0\u0bae\u0bcd \u0b95\u0bbe\u0baf\u0bcd\u0ba8\u0bcd\u0ba4\u0bb2\u0bcd - \u0b89\u0baa\u0bcd\u0baa\u0bc1\u0ba8\u0bc0\u0bb0\u0bcd \u0bae\u0bb0\u0baa\u0bcd \u0baa\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd, \u0baa\u0bc1\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0baa\u0bcd\u0baa\u0bc1\u0bb4\u0bc1 \u0ba4\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "neithal",
        "summary_en": "Dendrological marine preservation: long-term salt-water immersion of hull timbers followed by smoldering cashew-oil smoke treatment to immunize against rot and marine mollusks.",
        "summary_ta": "\u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0bae\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0ba8\u0bc0\u0ba3\u0bcd\u0b9f \u0b95\u0bbe\u0bb2\u0bae\u0bcd \u0b95\u0b9f\u0bb2\u0bcd\u0ba8\u0bc0\u0bb0\u0bbf\u0bb2\u0bcd \u0b8a\u0bb1\u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b9a\u0bbe\u0bb1\u0bc1\u0ba8\u0bc0\u0b95\u0bcd\u0b95\u0bbf, \u0bae\u0bc1\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0bbf \u0b8e\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd \u0baa\u0bc1\u0b95\u0bc8\u0baf\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bb0\u0baa\u0bcd\u0baa\u0bc1\u0bb4\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc2\u0b9e\u0bcd\u0b9a\u0bc8 \u0b85\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bb2\u0bcd \u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0bb0\u0bae\u0bcd\u0baa\u0bb0\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bb2\u0bcd.",
        "sources": [
            "Traditional Shipwright Oral Lore",
            "Kappal Sastiram",
            "Madras Fisheries Bulletin 1920"
        ],
        "content": "# Maram-Kaindhal: Saline Timber Seasoning & Marine Preservation\n\nAn ocean-going vessel built from unseasoned green wood would warp, shrink, and disintegrate within months of service. Ancient Tamil shipwrights practiced an extensive biological timber conditioning protocol known as maram-kaindhal.\n\nFelled tree trunks of Teak, Jackwood, Poovam, and Vengai were first rafted into estuarine lagoons and submerged in saline mud for a full year. The saline water chemically displaced fermentable sap sugars and starch compounds that would otherwise attract wood-boring insects and fungus.\n\nFollowing extraction and air drying under thatch sheds, the sawn planks were stacked in smoke chambers where smoldering fires fueled with dried coconut husks, neem leaves, and cashew nut shell oil (kollu-ennai) were maintained for weeks. The hot phenolic smoke deeply impregnated the wood pores, creating an oily, chemically unpalatable barrier that repelled shipworms and ensured multi-decade service life."
    },
    {
        "file": "knowledge/places/place-adirampattinam-ancient-marakkalam-shipwright-and-caulking-haven.md",
        "slug": "place-adirampattinam-ancient-marakkalam-shipwright-and-caulking-haven",
        "category": "place",
        "name_en": "Adirampattinam: Ancient Marakkalam Shipwright, Marine Caulking & Palk Bay Haven",
        "name_ta": "\u0b85\u0ba4\u0bbf\u0bb0\u0bbe\u0bae\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bae\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bc1, \u0b95\u0bbe\u0bb0\u0bc8 \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bc0\u0bb0\u0bbf\u0ba3\u0bc8\u0ba4\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0bae\u0bcd",
        "era": "Early Medieval to Modern Era",
        "year_start": 800,
        "year_end": 1900,
        "thinai": "neithal",
        "summary_en": "Historic maritime harbor on Palk Bay in Thanjavur district, celebrated for over a millennium as the preeminent center of Tamil ocean shipwrightry, timber drydocks, and marakkalam construction.",
        "summary_ta": "\u0baa\u0bbe\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bc0\u0bb0\u0bbf\u0ba3\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0baa\u0bc1\u0b95\u0bb4\u0bcd\u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0bae\u0bcd; \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd \u0ba8\u0bbe\u0bb5\u0bbe\u0baf\u0bcd\u0b95\u0bb3\u0bcd, \u0bb5\u0bbe\u0ba4\u0bc8\u0baa\u0bcd \u0baa\u0b9f\u0b95\u0bc1\u0b95\u0bb3\u0bcd, \u0b95\u0bc1\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bbf\u0baf\u0b95\u0bcd \u0b95\u0bbe\u0bb0\u0bc8 \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bb2\u0bcb\u0bb0 \u0bb5\u0ba3\u0bbf\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Adirampattinam Port Records",
            "Chola Maritime Inscriptions",
            "Ibn Battuta Rihla"
        ],
        "content": "# Adirampattinam: Ancient Shipwright & Caulking Haven\n\nAdirampattinam, situated along the tranquil, shallow waters of Palk Bay in the southern Kaveri delta, holds an illustrious place in Indian maritime history as a premier sanctuary of traditional wooden shipbuilding.\n\nProtected from turbulent oceanic surf by natural sand spits and estuarine channels, Adirampattinam provided an ideal protected lagoon environment for constructing, launching, and careening large ocean-going vessels. For generations, master Muslim Marakkar and Tamil shipwright communities constructed mammoth marakkalams, multi-oared padagus, and swift fishing vathais.\n\nThe town was renowned across the Indian Ocean as the primary supplier of specialized marine caulking pitch (kungiliyam-pal), seasoned ship timbers, and maritime rigging, maintaining active trade links with Malacca, Sumatra, Ceylon, and the Persian Gulf."
    }
]
EDGES = [
    [
        "concept-kappal-kattu-ancient-tamil-edge-joined-tenon-and-sewn-hull-mechanics",
        "CONSTRUCTS",
        "technology-marakkalam-and-vangam-multi-decked-transoceanic-wooden-cargo-hulls",
        "core",
        "Prehistoric to Modern Era",
        "Pegged mortise-and-tenon and sewn-plank joinery forms the structural foundation of oceanic cargo hulls.",
        "Ancient Indian Naval Architecture"
    ],
    [
        "artifact-kungiliyam-and-ennai-boiled-dammar-resin-and-fish-oil-marine-caulking",
        "WATERPROOFS",
        "technology-marakkalam-and-vangam-multi-decked-transoceanic-wooden-cargo-hulls",
        "core",
        "Prehistoric to Modern Era",
        "Boiled dammar resin and shark oil caulking hermetically seals the seams of seagoing wooden vessels.",
        "Siddha Maritime Treatises"
    ],
    [
        "technology-sukkaan-and-paai-maram-axial-quarter-rudders-and-woven-mat-rigging",
        "STEERS",
        "technology-marakkalam-and-vangam-multi-decked-transoceanic-wooden-cargo-hulls",
        "core",
        "Prehistoric to Modern Era",
        "Twin axial quarter-rudders provide directional control and steer multi-hundred-ton ocean cargo ships.",
        "Silappadikaram 13.175"
    ],
    [
        "text-perumpanattruppadai-verses-on-oceanic-masted-vessels-and-shipwright-harbors",
        "CELEBRATES",
        "technology-marakkalam-and-vangam-multi-decked-transoceanic-wooden-cargo-hulls",
        "core",
        "Sangam Era",
        "Perumpanattruppadai verses celebrate the majestic presence and towering masts of oceanic Tamil ships.",
        "Perumpanattruppadai 319-351"
    ],
    [
        "institution-marakkar-kappal-thatchar-corporation-guild-of-naval-shipwrights",
        "PRESERVES",
        "concept-kappal-kattu-ancient-tamil-edge-joined-tenon-and-sewn-hull-mechanics",
        "core",
        "Early Historic to Modern Era",
        "Hereditary shipwright corporations preserved and transmitted secret canons of naval joinery across generations.",
        "Nagapattinam Chola Epigraphs"
    ],
    [
        "concept-paara-kal-ballast-stone-trim-and-hydrodynamic-keel-stability",
        "STABILIZES",
        "technology-marakkalam-and-vangam-multi-decked-transoceanic-wooden-cargo-hulls",
        "core",
        "Prehistoric to Modern Era",
        "Granite ballast stones laid deep in the bilge lower the center of gravity and ensure metacentric stability.",
        "Purananuru 30"
    ],
    [
        "artifact-irumbu-aani-and-maravani-corrosion-resistant-bronze-and-copper-sheathing-clenches",
        "FASTENS",
        "concept-kappal-kattu-ancient-tamil-edge-joined-tenon-and-sewn-hull-mechanics",
        "core",
        "Early Historic to Modern Era",
        "Hardwood treenails and copper clenches mechanically secure hull planks to heavy structural frames.",
        "Poompuhar Underwater Catalog"
    ],
    [
        "concept-maram-kaindhal-saline-timber-seasoning-and-marine-borer-immunization",
        "SUPPLIES",
        "technology-marakkalam-and-vangam-multi-decked-transoceanic-wooden-cargo-hulls",
        "core",
        "Prehistoric to Modern Era",
        "Saline-soaked and smoke-cured timbers provide rot-resistant structural wood for hull fabrication.",
        "Kappal Sastiram"
    ],
    [
        "technology-marakkalam-and-vangam-multi-decked-transoceanic-wooden-cargo-hulls",
        "BUILT_AT",
        "place-adirampattinam-ancient-marakkalam-shipwright-and-caulking-haven",
        "core",
        "Early Medieval to Modern Era",
        "Transoceanic wooden ships and deep-sea merchant vessels were constructed at the Adirampattinam drydocks.",
        "Adirampattinam Port Records"
    ],
    [
        "institution-marakkar-kappal-thatchar-corporation-guild-of-naval-shipwrights",
        "LOCATED_AT",
        "place-adirampattinam-ancient-marakkalam-shipwright-and-caulking-haven",
        "core",
        "Early Historic to Modern Era",
        "Prominent master shipbuilder and caulking guilds maintained ancestral yards and docks at Adirampattinam.",
        "Palk Bay Oral Traditions"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Ancient Tamil Shipwright Hull Joinery, Tenon Planking & Caulking Resins into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Ancient Tamil Shipwright Hull Joinery, Tenon Planking & Caulking Resins Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
