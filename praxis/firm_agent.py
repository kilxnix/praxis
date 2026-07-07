"""A firm agent that is a PERSON, not a function call.

Each agent has a stable identity (a name, a role, and a way of thinking — a real character,
not a task string) and a MEMORY of what they have come to understand about THIS specific
business, built up as they watch the engagement unfold. When they make a call, they reason
from that accumulated understanding — the way a real consultant who has sat with a client for
an hour reasons — instead of reading a flattened map once and emitting a label.

The memory is the point. It is what makes an agent's judgment personal to this one business
and this one owner, and it is what a learning loop later grows across engagements.
"""
from dataclasses import dataclass, field


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

    def __init__(self, identity: Identity, client):
        self.identity = identity
        self.client = client
        self.memory = AgentMemory()

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


def assemble_firm(client):
    """Bring the firm to life for one engagement: five people, each with a blank memory of
    this business they are about to get to know."""
    return {ident.key: FirmAgent(ident, client) for ident in ROSTER}
