"""Difficult-but-coherent non-expert client personas for the Phase 0 gate. The personas
modulate SPEAKING STYLE (brief, talkative, jargon-heavy, guarded) — they do NOT license
incoherence. Each client describes a real, consistent workflow; the difficulty is in how
they say it, not in producing word-salad."""
from dataclasses import dataclass


@dataclass
class Scenario:
    key: str
    business: str
    persona: str
    truth: str


SCENARIOS = [
    Scenario(
        key="vague_baker",
        business="a two-person neighborhood bakery",
        persona="plain-spoken and brief; gives short answers and assumes you know how a small bakery works, so you often have to ask a pointed follow-up to get the specifics — but every answer is truthful and concrete",
        truth="Orders come in by phone and get written in a paper notebook; the baker bakes from the notebook list each morning; the spouse handles customer pickups and takes cash; the leftover count is estimated by eye at close; ingredients are reordered from a supplier by phone when a shelf runs low.",
    ),
    Scenario(
        key="rambling_agency",
        business="a small marketing agency",
        persona="warm and talkative; adds a bit of backstory and takes a sentence to get to the point, but always lands on the real, concrete answer",
        truth="Leads arrive through a website form into a shared email inbox; an account manager copies each lead into a spreadsheet; proposals are written in Google Docs from a template; invoices are created by hand in QuickBooks; project status is tracked in Slack threads and a Trello board.",
    ),
    Scenario(
        key="jargon_manufacturer",
        business="a small custom-parts machine shop",
        persona="terse and uses shop-floor jargon and abbreviations, assuming you know the trade — but describes the real process accurately when asked to spell it out",
        truth="Quotes start from drawings emailed by the customer; the owner estimates the price by hand in a spreadsheet; each accepted job gets a paper traveler that follows the part; machinists log their hours on a clipboard at each station; finished parts are inspected visually against the drawing; shipping paperwork is typed into the accounting software.",
    ),
    Scenario(
        key="defensive_founder",
        business="a subscription box startup",
        persona="guarded and brief at first; wants concrete, respectful questions before opening up, but answers truthfully and specifically once asked directly",
        truth="Signups come in through Stripe; the founder exports a subscriber CSV from Stripe each week; the fulfillment list is uploaded into a third-party logistics (3PL) portal; customer emails are handled in a shared inbox; churn is tracked in a spreadsheet updated manually each week.",
    ),
]
