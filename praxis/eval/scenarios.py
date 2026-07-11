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
    Scenario(
        key="solo_lawyer",
        business="a solo attorney handling small-business and estate clients",
        persona="precise and busy; speaks in short careful sentences and assumes you know legal process, but answers accurately when asked plainly",
        truth="New clients call or email for a consult; the lawyer takes handwritten notes during intake calls and types them up later; contracts and wills are drafted from prior templates in Word and reviewed clause by clause by hand; deadlines and court dates are tracked in a paper calendar and a spreadsheet; time is logged on a timesheet and invoiced monthly in QuickBooks; client documents are filed in labeled folders on a shared drive.",
    ),
    Scenario(
        key="hvac_tech",
        business="a two-van residential HVAC repair company",
        persona="plain-spoken and rushed between jobs; uses trade shorthand and gives short answers, but describes the real process when asked directly",
        truth="Customers call or text for repairs; the owner schedules jobs in a paper book and texts the address to the tech; on site the tech diagnoses the unit, takes photos of the equipment and model plates, and writes needed parts on a paper ticket; parts are ordered by phone from a supplier; the invoice is hand-written on site and later re-entered into QuickBooks; maintenance-reminder follow-ups are tracked from memory.",
    ),
    Scenario(
        key="therapy_clinic",
        business="a small physical-therapy clinic with three therapists",
        persona="warm but harried; jumps between patients and paperwork, but lands on the real answer",
        truth="Patients are booked by phone into a scheduling app; each session the therapist writes notes on paper and types them into the patient record that evening; insurance authorizations are checked by phone and logged in a spreadsheet; billing codes are entered by hand from the session notes; appointment reminders are called or texted manually the day before; no-shows are common and re-booked ad hoc.",
    ),
    Scenario(
        key="event_videographer",
        business="a solo event videographer covering weddings and corporate events",
        persona="creative and a bit scattered; talks about the craft first, then admits the admin when pressed; answers are truthful and concrete once pinned down",
        truth="Inquiries come in via Instagram DMs and a website form into Gmail; she replies and books dates in a Google Calendar she keeps by hand; on shoot day she films 6–10 hours of footage on two cameras; the CORE work is reviewing and selecting usable clips from thousands of minutes of raw footage in Premiere — she says she spends entire nights scrubbing timelines and it takes 20–40 hours per wedding; she assembles a highlight film and a longer cut, exports, and uploads to a client gallery (Pixieset); contracts are Word templates she customizes per couple; invoices go out from Wave after delivery; follow-ups for testimonials are remembered, not tracked.",
    ),
    Scenario(
        key="residential_realtor",
        business="a solo residential real estate agent",
        persona="upbeat and salesy at first, then frank about the grind when asked directly; short answers when between showings, truthful and concrete",
        truth="Leads arrive from Zillow, Facebook, and open-house sign-in sheets into her phone and a shared Gmail; she logs each lead by hand into a Google Sheet CRM; she schedules showings and open houses in a paper planner and Google Calendar; on listing day a photographer delivers 80–150 property photos and she spends 2–3 hours every listing night picking the best shots and writing the MLS description from her walkthrough notes; she re-types property facts (beds, baths, sqft, taxes) from the assessor printout into the MLS form; offers come in as PDFs by email and she tracks contingencies and deadlines on sticky notes and a whiteboard; contracts are DocuSign templates she fills from the offer; closed deals get commission checked against a spreadsheet; follow-up for past clients and annual check-ins is remembered, not systematized.",
    ),
]
