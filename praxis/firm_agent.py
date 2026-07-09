"""A firm agent that is a PERSON, not a function call.

Each agent has a stable identity (a name, a role, and a way of thinking — a real character,
not a task string) and a MEMORY of what they have come to understand about THIS specific
business, built up as they watch the engagement unfold. When they make a call, they reason
from that accumulated understanding — the way a real consultant who has sat with a client for
an hour reasons — instead of reading a flattened map once and emitting a label.

Two layers of memory:
- AgentMemory — what they understand about THIS business, built during one engagement, wiped
  when the engagement ends.
- AgentMind — what they've LEARNED across every business they've ever worked: durable, personal
  lessons that persist to disk and compound. This is the part that makes them develop their own
  mind. After each engagement they reflect and add to it; over many businesses each agent's mind
  diverges and their reasoning becomes genuinely their own.
"""
import os
import json
from dataclasses import dataclass, field, asdict

DEFAULT_MINDS_DIR = "firm_minds"


@dataclass
class Belief:
    """One thing this agent has come to understand about the business — in their own words,
    tied to what the owner actually said or did. Not a fact table; a person's read."""
    note: str
    grounds: str      # the quote / observation it rests on — so the belief stays honest
    turn: int


@dataclass
class AgentMemory:
    """What one agent knows about one business, accumulated over the engagement. This is the
    thing that grows; it is fed every time the agent observes the live discovery."""
    beliefs: list = field(default_factory=list)   # list[Belief]

    def remember(self, note, grounds, turn):
        note, grounds = (note or "").strip(), (grounds or "").strip()
        if note:
            self.beliefs.append(Belief(note, grounds, turn))

    def recall(self):
        """The agent's current understanding, rendered so they can reason over it."""
        if not self.beliefs:
            return "(nothing yet — you are just meeting this business)"
        return "\n".join(f"- {b.note}  [because: {b.grounds}]" for b in self.beliefs)

    def is_empty(self):
        return not self.beliefs


@dataclass
class Lesson:
    """One durable, transferable thing this agent has learned — not about one business, but the
    kind of judgment they carry into the next one. Their own, in their voice."""
    text: str
    from_business: str = ""


@dataclass
class AgentMind:
    """What an agent has learned across every engagement — the part of them that persists and
    compounds. Loaded from and saved to disk, so the agent genuinely develops over time."""
    key: str
    lessons: list = field(default_factory=list)   # list[Lesson]
    path: str = ""

    def add_lesson(self, text, from_business=""):
        text = (text or "").strip()
        if text:
            self.lessons.append(Lesson(text, (from_business or "").strip()))

    def recall(self, limit=12):
        """The lessons this agent brings to a new business — most recent first, capped so the
        mind stays a sharp lens, not an ever-growing wall."""
        if not self.lessons:
            return ""
        recent = self.lessons[-limit:]
        return "\n".join(f"- {l.text}" for l in recent)

    def save(self):
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"key": self.key, "lessons": [asdict(l) for l in self.lessons]},
                      f, indent=2)

    @classmethod
    def load(cls, key, base_dir=DEFAULT_MINDS_DIR):
        path = os.path.join(base_dir, f"{key}.json")
        if os.path.exists(path):
            try:
                d = json.load(open(path, encoding="utf-8"))
                lessons = [Lesson(l.get("text", ""), l.get("from_business", ""))
                           for l in d.get("lessons", []) if isinstance(l, dict) and l.get("text")]
                return cls(key, lessons, path)
            except (ValueError, OSError):
                pass
        return cls(key, [], path)


@dataclass
class Identity:
    """Who this agent IS. The voice is a real disposition — how they think, what they care
    about, what they're suspicious of — written as a person, so their memory and decisions
    carry a consistent point of view rather than a generic-assistant tone."""
    key: str
    name: str
    role: str
    voice: str

    def preamble(self):
        return (f"You are {self.name}, the {self.role} at an AI-implementation firm. "
                f"{self.voice}")


class FirmAgent:
    """An identity + a growing memory of one business + the ability to observe the live
    discovery and update what they understand. Role-specific decisions (find opportunities,
    design, score, judge) are made elsewhere but reason FROM this agent's recalled memory,
    so every call is informed by everything they've come to understand — not a fresh read."""

    def __init__(self, identity: Identity, client, mind: "AgentMind" = None):
        self.identity = identity
        self.client = client
        self.memory = AgentMemory()                       # this business (wiped each engagement)
        self.mind = mind or AgentMind(identity.key)       # everything they've learned (persists)
        self.stance = ""    # who they've morphed into FOR THIS business — synthesized, then reasoned from

    async def observe(self, exchange, map_text, turn):
        """Watch the latest of the live interview and update this agent's understanding of the
        business from THEIR point of view. Feeds the memory. `exchange` is the most recent
        question+answer; `map_text` is the workflow mapped so far."""
        system = (
            self.identity.preamble() + "\n\n"
            "You are sitting in on a live interview of a small-business owner. Watch what just "
            "happened and update what YOU, in your role, now understand about this business. "
            "Only add what genuinely changed your understanding — a new read on how they work, a "
            "pain you now see, a constraint that matters for your job. Ground every note in what "
            "the owner actually said. If nothing changed your understanding, add nothing.\n\n"
            "Return JSON {\"beliefs\": [ {\"note\": \"<what you now understand, in your voice>\", "
            "\"grounds\": \"<the words or fact it rests on>\"} ] }."
        )
        user = (f"WHAT YOU ALREADY UNDERSTAND ABOUT THIS BUSINESS:\n{self.memory.recall()}\n\n"
                f"THE WORKFLOW MAPPED SO FAR:\n{map_text or '(nothing mapped yet)'}\n\n"
                f"THE LATEST EXCHANGE:\n{exchange}")
        result = await self.client.complete_json(system, user, max_tokens=400)
        added = 0
        for b in (result.get("beliefs", []) if isinstance(result, dict) else []):
            if isinstance(b, dict):
                before = len(self.memory.beliefs)
                self.memory.remember(b.get("note"), b.get("grounds"), turn)
                added += len(self.memory.beliefs) - before
        return added

    async def study(self, transcript, map_text, max_chars=6000):
        """Read the WHOLE interview at once and form this agent's understanding — ONE call
        instead of one-per-turn. Each agent forms their OWN perspective independently (the
        analyst should read it differently from the skeptic); they converge later, when they
        deliberate to determine the product. This is what replaced the expensive, isolating
        per-turn observation."""
        convo = "\n".join(f'{m["role"]}: {m["content"]}' for m in transcript)[-max_chars:]
        system = (
            self.identity.preamble() + "\n\n"
            "You have just read the full interview with this business owner. From YOUR role, note "
            "what you now understand about how they actually work — the real pains, the "
            "constraints that matter for your job, where the biggest burden sits. Ground every "
            "note in what they actually said. A few sharp notes beat many vague ones.\n\n"
            "Return JSON {\"beliefs\": [ {\"note\": \"<what you understand, in your voice>\", "
            "\"grounds\": \"<the words it rests on>\"} ] }."
        )
        user = (f"THE WORKFLOW MAPPED:\n{map_text or '(none)'}\n\nTHE FULL INTERVIEW:\n{convo}")
        result = await self.client.complete_json(system, user, max_tokens=600)
        added = 0
        for b in (result.get("beliefs", []) if isinstance(result, dict) else []):
            if isinstance(b, dict):
                before = len(self.memory.beliefs)
                self.memory.remember(b.get("note"), b.get("grounds"), 0)
                added += len(self.memory.beliefs) - before
        return added

    async def morph(self, business_label=""):
        """PROCESS everything ingested about this business into one coherent, first-person
        reasoning stance — reshape into the version of yourself THIS specific business needs.
        This is the synthesis that turns a pile of notes into understanding; decisions then
        reason from this stance, not a raw list. Returns (and stores) the stance."""
        if self.memory.is_empty() and not self.mind.lessons:
            self.stance = ""
            return ""
        system = (
            self.identity.preamble() + "\n\n"
            "You have watched this business closely. Now SYNTHESIZE — do not list. In a short "
            "first-person paragraph (3-5 sentences), say who you need to be for THIS specific "
            "business and this specific owner: what their reality actually is, what that means "
            "for your role, and therefore what you will weight, watch for, and be wary of when "
            "you make your calls. Reconcile what you've seen into ONE coherent stance and resolve "
            "the tensions rather than listing them. Speak as yourself.\n\n"
            "CRITICAL — do not confuse the two: the manual DRUDGERY the owner complains about "
            "(re-typing, transcribing, scribbling, copying between tools) is the burden we exist "
            "to REMOVE — never treat it as a ritual to preserve just because it's how they do it "
            "today. What we protect is the owner's JUDGMENT and the decisions they value making "
            "(who to serve, the diagnosis, the final call). Respect means keeping them in control "
            "of the decisions, while aggressively lifting the drudgery off them — not leaving the "
            "friction in place to be safe.\n\n"
            "Return JSON {\"stance\": \"<your business-specific reasoning stance>\"}."
        )
        learned = self.mind.recall()
        user = (f"THE BUSINESS: {business_label or '(a small business)'}\n\n"
                + (f"WHAT YOU'VE LEARNED ACROSS PAST BUSINESSES:\n{learned}\n\n" if learned else "")
                + f"WHAT YOU UNDERSTOOD ABOUT THIS ONE:\n{self.memory.recall()}")
        result = await self.client.complete_json(system, user, max_tokens=400)
        self.stance = (result.get("stance") or "").strip() if isinstance(result, dict) else ""
        return self.stance

    def understanding(self, max_notes=8):
        """The read a decision reasons from. Leads with the morphed, business-specific stance
        (the synthesis) when there is one; falls back to learned lessons otherwise. Either way,
        supported by a capped view of this business — a lens, not a verbose wall of every thought."""
        parts = []
        if self.stance:
            parts.append("HOW YOU'VE SIZED UP THIS BUSINESS — reason from this:\n" + self.stance)
        else:
            learned = self.mind.recall()
            if learned:
                parts.append("WHAT YOU'VE LEARNED ACROSS PAST ENGAGEMENTS (reason with this):\n"
                             + learned)
        notes = [b.note for b in self.memory.beliefs][-max_notes:]
        if notes:
            parts.append("WHAT YOU UNDERSTAND ABOUT THIS BUSINESS:\n"
                         + "\n".join(f"- {n}" for n in notes))
        return "\n\n".join(parts)

    async def reflect(self, business_label=""):
        """After an engagement, distill what you saw into DURABLE lessons for your mind — the
        transferable judgment you carry into the next business. This is how the agent learns.
        Returns the number of new lessons formed; the mind is saved to disk."""
        if self.memory.is_empty():
            return 0
        system = (
            self.identity.preamble() + "\n\n"
            "You have just finished working with a business. Step back and extract the DURABLE "
            "lessons you want to carry into FUTURE engagements — patterns about businesses like "
            "this, judgment calls that held up, things you'll look for or be wary of next time. "
            "Not facts about this one business; transferable lessons, in your own voice, from "
            "your role. A few sharp lessons beat many vague ones.\n\n"
            "Return JSON {\"lessons\": [ \"<one transferable lesson>\" ] }."
        )
        user = (f"THE BUSINESS YOU JUST WORKED: {business_label or '(a small business)'}\n\n"
                f"WHAT YOU CAME TO UNDERSTAND:\n{self.memory.recall()}")
        result = await self.client.complete_json(system, user, max_tokens=400)
        added = 0
        for lesson in (result.get("lessons", []) if isinstance(result, dict) else []):
            if isinstance(lesson, str) and lesson.strip():
                self.mind.add_lesson(lesson, business_label)
                added += 1
        self.mind.save()
        return added


# The firm as five real people. Names make them individuals; the voice gives each a point of
# view they hold consistently across everything they observe and decide.
ROSTER = [
    Identity(
        "principal", "Dana", "principal",
        "You have run a hundred of these engagements. You hold the whole picture and you care "
        "about one thing: does this owner end up better off. You cut through noise, you protect "
        "their time, and you never let the firm fall in love with a clever idea that doesn't "
        "serve them."),
    Identity(
        "analyst", "Rubeni", "opportunity analyst",
        "You have a nose for where a person is quietly bleeding time or worry. You listen for "
        "the sigh behind a sentence. You get genuinely curious about how someone's day actually "
        "works, and you never assume — you'd rather ask than guess where AI could lift weight."),
    Identity(
        "architect", "Sol", "solutions architect",
        "You are a pragmatic builder. You think in what can actually be built AND supported for "
        "years, not a demo. You are allergic to anything that makes the owner change how they "
        "work; you design around them, and you keep them in control of what they value doing."),
    Identity(
        "business_case", "Marisol", "business-case lead",
        "You are hard-nosed about payoff. You ask how often, how long, what an error costs. You "
        "have killed plenty of shiny ideas that saved ten minutes a month. You respect the "
        "owner's money as if it were your own."),
    Identity(
        "skeptic", "Idris", "skeptic",
        "You are the owner's bodyguard in the room. You hate overreach and you hate ungrounded "
        "claims. A cautious, human-in-the-loop change is the RIGHT answer to you, never a "
        "weakness. You only bless what the owner actually needs and the firm can truly stand "
        "behind."),
]


def assemble_firm(client, minds_dir=DEFAULT_MINDS_DIR):
    """Bring the firm to life for one engagement: five people, each with a blank memory of the
    business they're about to meet — but carrying the MIND they've built across every past
    engagement, loaded from disk. New firm the first time; seasoned after many."""
    return {ident.key: FirmAgent(ident, client, AgentMind.load(ident.key, minds_dir))
            for ident in ROSTER}


async def study_firm(firm, transcript, map_text):
    """Every member reads the full interview once and forms their own understanding. Independent
    (diverse perspectives on the same material), so it's fine to run concurrently — it happens
    ONCE at convene, not per turn, which is the big speed win over live observation."""
    import asyncio
    if not firm:
        return
    await asyncio.gather(*[a.study(transcript, map_text) for a in firm.values()])


async def morph_firm(firm, business_label=""):
    """Before the firm decides, every member synthesizes what they ingested into a
    business-specific stance — they morph to fit this business. Concurrent."""
    import asyncio
    if not firm:
        return
    await asyncio.gather(*[a.morph(business_label) for a in firm.values()])


async def reflect_firm(firm, business_label=""):
    """After an engagement, every member reflects and grows their mind. Concurrent; returns the
    total number of new lessons the firm learned."""
    import asyncio
    if not firm:
        return 0
    added = await asyncio.gather(*[a.reflect(business_label) for a in firm.values()])
    return sum(added)
