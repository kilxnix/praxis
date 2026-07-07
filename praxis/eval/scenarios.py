"""Hard, non-expert client personas for the Phase 0 gate. These are deliberately
difficult (vague, rambling, jargon-heavy, defensive) — the point is to stress
Discovery, not to hand it cooperative interviews."""
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
        persona="brief and vague; gives three-word answers; assumes you already know how bakeries work; rarely volunteers detail unless asked a pointed question",
        truth="Orders come in by phone and a paper notebook; baker bakes from the notebook list each morning; spouse handles pickups and takes cash; leftover count is guessed and often wrong; ingredient reordering is done from memory when a shelf looks empty.",
    ),
    Scenario(
        key="rambling_agency",
        business="a small marketing agency",
        persona="rambles, tells stories, jumps between topics, over-explains the backstory before answering; friendly but hard to pin down",
        truth="Leads arrive via a web form into email; an account manager copies them into a spreadsheet; proposals are written in Google Docs from a rough template; invoicing is manual in QuickBooks; project status lives in people's heads and Slack threads.",
    ),
    Scenario(
        key="jargon_manufacturer",
        business="a small custom-parts machine shop",
        persona="answers in shop jargon and acronyms without explaining them; terse; assumes you know the trade",
        truth="Quotes come from emailed drawings; the owner estimates by hand; jobs get a paper traveler that follows the part; machinists log hours on a clipboard; finished parts are QC'd visually; shipping paperwork is retyped into the accounting system.",
    ),
    Scenario(
        key="defensive_founder",
        business="a subscription box startup",
        persona="guarded and a little suspicious of the interview; short answers; needs a reason before sharing; warms up only if the questions are concrete and respectful",
        truth="Signups hit Stripe; a founder exports CSVs weekly; fulfillment list is pasted into a 3PL portal; customer emails are handled in a shared inbox; churn is tracked in a spreadsheet updated when someone remembers.",
    ),
]
