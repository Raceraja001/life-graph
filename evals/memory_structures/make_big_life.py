"""Build test_life_big.json: the small test life plus ~1,000 everyday messages.

The same person, questions and right answers as test_life.json; the extra
messages are what a real life adds around the facts that matter: work days,
films, outings, errands, cricket scores, and facts about OTHER people (a
colleague's phone, a friend's home, a co-worker also called Priya). None of
them changes a right answer; the ones about other people are there to catch a
method that mixes up whose fact is whose.

Deterministic (fixed seed): every run builds the same file.

    python evals/memory_structures/make_big_life.py
"""

from __future__ import annotations

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


def fill(template: str, rng: random.Random) -> str:
    out = template
    for k, vals in FILL.items():
        while "{" + k + "}" in out:
            out = out.replace("{" + k + "}", rng.choice(vals), 1)
    return out


def main() -> None:
    rng = random.Random(SEED)
    base = json.loads((HERE / "test_life.json").read_text(encoding="utf-8"))
    start, end = date(2025, 1, 1), date(2026, 10, 29)
    days = (end - start).days
    kinds = list(WEIGHTS)
    extra = []
    for i in range(EXTRA):
        kind = rng.choices(kinds, weights=[WEIGHTS[k] for k in kinds])[0]
        d = start + timedelta(days=rng.randrange(days + 1))
        extra.append(
            {
                "id": f"f{i + 1:04d}",
                "date": d.isoformat(),
                "kind": kind,
                "text": fill(rng.choice(T[kind]), rng),
            }
        )
    big = dict(base)
    big["about"] = (
        base["about"] + " BIG version: the same facts and questions plus "
        f"{EXTRA} everyday messages (make_big_life.py, seed {SEED}); none changes a right answer."
    )
    big["messages"] = sorted(base["messages"] + extra, key=lambda m: (m["date"], m["id"]))
    (HERE / "test_life_big.json").write_text(
        json.dumps(big, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(len(big["messages"]), "messages")


if __name__ == "__main__":
    main()
