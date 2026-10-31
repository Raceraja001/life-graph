"""Build test_life_big.json: the small test life plus ~1,000 everyday messages.

The same person, questions and right answers as test_life.json; the extra
messages are what a real life adds around the facts that matter: work days,
films, outings, errands, cricket scores, and facts about OTHER people (a
colleague's phone, a friend's home, a co-worker also called Priya). None of
them changes a right answer; the ones about other people are there to catch a
method that mixes up whose fact is whose.

Deterministic (fixed seed): every run builds the same file.

    python evals/memory_structures/make_big_life.py            # test_life_big.json
    python evals/memory_structures/make_big_life.py --life 2   # test_life_2_big.json

``--life 2`` does the same for test_life_2.json (Kavitha, Madurai then
Coimbatore): QA work days, pickle batches, films, outings in the city she lived
in on that date, Tamil and Tanglish chatter, and other people's facts (a
friend's car, a colleague's phone, a daycare teacher also called Nila).
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 20261030
EXTRA = 1000

T = {
    "work": [
        "Long day at work, {n} meetings back to back.",
        "Spent the afternoon reviewing pull requests.",
        "Our sprint demo went well today.",
        "Production had a small incident this morning; fixed by noon.",
        "Wrote the design doc for the new {feature} feature.",
        "Interviewed a candidate for a backend role today.",
        "Pair-programmed with {colleague} on a tricky bug.",
        "The quarterly planning meeting ran over again.",
        "Spent the day on code cleanup; nothing exciting.",
        "Gave a short talk to the team about {topic}.",
    ],
    "others": [
        "My colleague Senthil just bought an iPhone 16.",
        "My friend Anil lives in Velachery now.",
        "Arjun's wife Kavya runs a bakery in Coimbatore.",
        "There's a new designer on my team, also called Priya.",
        "My neighbour Mr. Iyer drives a Tata Nexon EV.",
        "Senthil's daughter is learning the violin.",
        "Anil is moving to Pune for a new job.",
        "Gopal's team uses Python for most of their services.",
        "My cousin Ramesh got a job at Zoho.",
        "Kavya's bakery started delivering in Chennai too.",
        "Divya's friend Shalini visited them in Bangalore.",
        "Ravi is learning Japanese for a trip next year.",
        "My school friend Prakash opened a clinic in Madurai.",
        "Naveen's hospital is opening a new wing.",
        "Meena now leads the payments platform team.",
    ],
    "media": [
        "Watched {movie} last night; pretty good.",
        "Started reading {book}.",
        "Finished {book}; recommended.",
        "Listened to a long podcast about {topic} on my walk.",
        "Rewatched {movie} with the kids.",
    ],
    "outings": [
        "Took the kids to {place} this evening.",
        "Had lunch at {restaurant} with friends.",
        "Went to {place} on Sunday; it was crowded.",
        "Evening walk at {place}; nice weather.",
        "Visited a bookshop near {place}.",
    ],
    "errands": [
        "Need to pay the electricity bill this week.",
        "Spent {amount} rupees on groceries today.",
        "Got the car washed.",
        "Renewed the internet plan for another year.",
        "Ordered a new water purifier filter.",
        "Fixed the leaking kitchen tap myself.",
        "Paid the school bus fees for the term.",
    ],
    "cricket": [
        "We won our cricket match by {n} runs today.",
        "Lost a close cricket match today; scored {n}.",
        "Cricket practice was rained off.",
        "Scored {n} runs in today's match.",
    ],
    "kids": [
        "Anu won a prize in the drawing competition.",
        "Vicky learned to ride his cycle without help.",
        "Anu has a science project due next week.",
        "Vicky's class went on a trip to the zoo.",
        "Helped Anu with her maths homework.",
        "Vicky drew a picture of our car today.",
    ],
    "small_talk": [
        "Good morning!",
        "What's the weather tomorrow?",
        "Thanks, that's helpful.",
        "Tell me a joke.",
        "How many days until the weekend?",
        "Can you summarise the news?",
    ],
    "musings": [
        "Thinking about getting noise-cancelling headphones, maybe the Sony XM6.",
        "Maybe I should start running instead of walking.",
        "Not sure if I should repaint the living room.",
        "Considering a standing desk for home.",
        "Might try learning chess this year.",
    ],
    "health_small": [
        "Slept badly last night.",
        "Mild headache today; drank more water.",
        "Felt great after the walk this morning.",
        "Skipped my walk today because of rain.",
    ],
}
FILL = {
    "n": [str(x) for x in range(3, 61)],
    "feature": ["loan approval", "audit log", "export", "notifications", "risk scoring"],
    "colleague": ["Senthil", "Ravi", "Deepa", "Imran", "Karthika"],
    "topic": ["observability", "Kafka", "AI agents", "system design", "Rust", "testing"],
    "movie": [
        "Jailer",
        "Vikram Vedha",
        "Inception",
        "Interstellar",
        "96",
        "Super Deluxe",
        "Oppenheimer",
    ],
    "book": [
        "Atomic Habits",
        "Deep Work",
        "Ponniyin Selvan",
        "The Pragmatic Programmer",
        "Sapiens",
    ],
    "place": [
        "Marina beach",
        "Elliot's beach",
        "the Guindy park",
        "Phoenix mall",
        "Brodie Castle Road",
    ],
    "restaurant": ["Murugan Idli Shop", "Saravana Bhavan", "Sangeetha", "Ratna Cafe"],
    "amount": [str(x) for x in range(800, 4800, 150)],
}
WEIGHTS = {
    "work": 22,
    "others": 8,
    "media": 10,
    "outings": 10,
    "errands": 12,
    "cricket": 8,
    "kids": 10,
    "small_talk": 8,
    "musings": 5,
    "health_small": 7,
}


# ── test life 2 (Kavitha) ──────────────────────────────────────────
#: She moved from Madurai to Coimbatore on this date; outings follow her city.
MOVE_2 = date(2026, 1, 25)
T2 = {
    "work": [
        "Long day at work, {n} meetings back to back.",
        "Found a nasty bug in the {feature} screen today.",
        "Spent the afternoon writing test cases for the {feature} flow.",
        "Our release went out tonight; no rollbacks.",
        "Mentored a new tester today.",
        "Flaky tests ate my whole morning.",
        "Bug triage ran for two hours again.",
        "Automated {n} more regression tests this week.",
        "Office-la inniku full-aa meetings dhaan.",
    ],
    "pickles": [
        "Made {n} jars of {pickle} today.",
        "Packed {n} pickle orders for delivery this evening.",
        "Raw mango prices are up again at the market.",
        "A customer asked for less oil in the {pickle}.",
        "Inniku {pickle} {n} bottle pack panniten.",
        "Ran out of glass jars; ordered {n} more.",
    ],
    "others": [
        "My friend Deepa Sekar bought a Hyundai i20.",
        "Senthil's colleague Ganesh uses a Pixel 9.",
        "One of the teachers at Ilan's daycare is also called Nila.",
        "Revathi's daughter got into Anna University.",
        "Arun is thinking of moving to Bangalore someday.",
        "KR's husband works at a bank in Tiruppur.",
        "Swathi runs a physio clinic in Kothrud, Pune.",
        "Lakshmi's husband is a cardiologist.",
        "Senthil's amma Pushpa goes to the Meenakshi temple every Friday.",
        "Prakash has become a director at Velan Infotech.",
        "Deepa Iyer's son plays chess at the district level.",
        "அருணுக்கு பிரியாணி ரொம்ப பிடிக்கும்.",
        "செந்திலோட அண்ணன் முரளி துபாய்ல புது கார் வாங்கினார்.",
        "தீபா சேகர் புது கடை திறக்கலாமான்னு யோசிக்கிறாங்க.",
        "KR-ku coffee illaama mudiyaadhu, dhinamum moonu cup.",
    ],
    "media": [
        "Watched {movie} with Senthil last night.",
        "Reading {book} these days.",
        "Finished {book}; loved it.",
        "{movie} padam paathom, semma.",
    ],
    "outings": [
        "Took the kids to {place} this evening.",
        "Evening walk near {place}; nice breeze.",
        "Went to {place} on Sunday; very crowded.",
        "Had lunch at {restaurant} with Senthil.",
    ],
    "errands": [
        "Spent {amount} rupees on groceries today.",
        "Paid the electricity bill.",
        "Got the Baleno washed.",
        "Booked the gas cylinder.",
        "Paid Nila's school fees for the term.",
        "Recharged the internet plan.",
        "Kaaikari vaanga market pogaNum.",
    ],
    "kids": [
        "Nila got a star in her spelling test.",
        "Ilan threw his food on the floor again, haha.",
        "Nila's class went on a field trip.",
        "Helped Nila with her maths homework.",
        "Ilan has a cold today.",
        "நிலா இன்னைக்கு ஒரு அழகான படம் வரைஞ்சா.",
        "இலன் இன்னைக்கு ரொம்ப சேட்டை பண்ணான்.",
    ],
    "small_talk": [
        "Good morning!",
        "Nalaiku mazhai varuma?",
        "Inniku romba tired-aa irukku.",
        "Sari Jarvis, thanks!",
        "Tell me a joke.",
        "இன்னைக்கு என்ன கிழமை?",
    ],
    "musings": [
        "Maybe I should try Zumba.",
        "Thinking about a new sofa for the hall.",
        "Might start a small terrace garden.",
        "Not sure if we should get a second car.",
        "Oru naal Kerala trip pogalaam-nu thonudhu.",
    ],
    "health_small": [
        "Slept badly last night.",
        "Mild headache today; drank more water.",
        "Back pain after badminton.",
        "தலைவலி, இன்னைக்கு சீக்கிரம் தூங்கணும்.",
    ],
}
FILL2 = {
    "n": [str(x) for x in range(3, 61)],
    "feature": ["login", "claims", "payments", "reports", "dashboard", "onboarding"],
    "pickle": ["mango thokku", "lemon pickle", "garlic pickle", "paruppu podi", "idli podi"],
    "movie": ["Jailer", "Vikram", "Leo", "96", "Amaran", "Maharaja", "Ponniyin Selvan 2"],
    "book": ["Ponniyin Selvan", "Sivagamiyin Sabatham", "Atomic Habits", "Ikigai"],
    "restaurant": ["Murugan Idli Shop", "Sree Sabarees", "Hotel Anandha", "Kumar Mess"],
    "amount": [str(x) for x in range(800, 4800, 150)],
}
PLACES_2 = {
    "madurai": ["the Meenakshi temple", "Gandhi Museum", "Eco Park", "Thirumalai Nayakkar Mahal"],
    "coimbatore": ["Brookefields mall", "VOC Park", "Race Course", "Marudhamalai temple"],
}
WEIGHTS2 = {
    "work": 20,
    "pickles": 12,
    "others": 9,
    "media": 8,
    "outings": 9,
    "errands": 11,
    "kids": 11,
    "small_talk": 8,
    "musings": 5,
    "health_small": 7,
}


def fills_2(d: date) -> dict[str, list[str]]:
    city = "madurai" if d < MOVE_2 else "coimbatore"
    return {**FILL2, "place": PLACES_2[city]}


def fill(template: str, rng: random.Random, fills: dict[str, list[str]] | None = None) -> str:
    out = template
    for k, vals in (FILL if fills is None else fills).items():
        while "{" + k + "}" in out:
            out = out.replace("{" + k + "}", rng.choice(vals), 1)
    return out


#: name -> (base file, big file, seed, first filler date, last filler date, templates,
#: weights, fills: a fixed dict or a function of the date).
LIVES = {
    "1": (
        "test_life.json",
        "test_life_big.json",
        SEED,
        date(2025, 1, 1),
        date(2026, 10, 29),
        T,
        WEIGHTS,
        FILL,
    ),
    "2": (
        "test_life_2.json",
        "test_life_2_big.json",
        20261031,
        date(2025, 3, 1),
        date(2026, 10, 30),
        T2,
        WEIGHTS2,
        fills_2,
    ),
}


def main(life: str = "1") -> None:
    base_name, out_name, seed, start, end, templates, weights, fills = LIVES[life]
    rng = random.Random(seed)
    base = json.loads((HERE / base_name).read_text(encoding="utf-8"))
    days = (end - start).days
    kinds = list(weights)
    extra = []
    for i in range(EXTRA):
        kind = rng.choices(kinds, weights=[weights[k] for k in kinds])[0]
        d = start + timedelta(days=rng.randrange(days + 1))
        extra.append(
            {
                "id": f"f{i + 1:04d}",
                "date": d.isoformat(),
                "kind": kind,
                "text": fill(
                    rng.choice(templates[kind]), rng, fills(d) if callable(fills) else fills
                ),
            }
        )
    big = dict(base)
    big["about"] = (
        base["about"] + " BIG version: the same facts and questions plus "
        f"{EXTRA} everyday messages (make_big_life.py, seed {seed}); none changes a right answer."
    )
    big["messages"] = sorted(base["messages"] + extra, key=lambda m: (m["date"], m["id"]))
    (HERE / out_name).write_text(json.dumps(big, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(big["messages"]), "messages")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--life", choices=sorted(LIVES), default="1", help="which test life")
    main(ap.parse_args().life)
