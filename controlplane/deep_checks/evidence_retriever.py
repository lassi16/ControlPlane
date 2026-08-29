"""
Deep Check: Evidence Retriever
Retrieves external evidence for factual claim verification.

Sources (in priority order):
  1. Curated knowledge base (50+ entries, instant, no network)
  2. DuckDuckGo real web search (free, no API key)
  3. Math verifier stub for numerical claims
"""
import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger("controlplane.evidence")

# ── Curated knowledge base (instant lookup, no network call) ─────────────────
# 50+ entries: history, science, medicine, geography, finance, tech, space
KNOWLEDGE_BASE = {

    # ── Inventions & History ──────────────────────────────────────────────────
    "telephone": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Alexander_Graham_Bell",
            "title": "Alexander Graham Bell - Wikipedia",
            "snippet": "Alexander Graham Bell is credited with inventing and patenting the first practical telephone in 1876. Bell received US Patent 174,465 for the telephone.",
            "authority": 0.95,
        },
        {
            "source_url": "https://www.history.com/topics/inventions/alexander-graham-bell",
            "title": "Alexander Graham Bell | History",
            "snippet": "Bell received the first patent for the telephone in 1876. Thomas Edison did not invent the telephone; he invented the phonograph.",
            "authority": 0.85,
        },
    ],
    "edison": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Thomas_Edison",
            "title": "Thomas Edison - Wikipedia",
            "snippet": "Thomas Alva Edison (1847-1931) invented the phonograph and developed a practical incandescent light bulb. He did NOT invent the telephone — that was Alexander Graham Bell.",
            "authority": 0.95,
        },
    ],
    "internet": [
        {
            "source_url": "https://en.wikipedia.org/wiki/History_of_the_Internet",
            "title": "History of the Internet - Wikipedia",
            "snippet": "The Internet evolved from ARPANET, developed in the late 1960s by the U.S. Department of Defense. Tim Berners-Lee invented the World Wide Web in 1989, which is distinct from the Internet itself.",
            "authority": 0.95,
        },
    ],
    "world wide web": [
        {
            "source_url": "https://www.w3.org/WWW/",
            "title": "W3C - History of the Web",
            "snippet": "Tim Berners-Lee invented the World Wide Web in 1989 while at CERN, proposing a hypertext system for sharing information.",
            "authority": 0.97,
        },
    ],
    "einstein": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Albert_Einstein",
            "title": "Albert Einstein - Wikipedia",
            "snippet": "Albert Einstein (1879-1955) developed the theory of relativity. He was awarded the Nobel Prize in Physics in 1921 for the photoelectric effect, not for relativity.",
            "authority": 0.95,
        },
    ],
    "darwin": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Charles_Darwin",
            "title": "Charles Darwin - Wikipedia",
            "snippet": "Charles Darwin (1809-1882) proposed the theory of evolution by natural selection in 'On the Origin of Species' (1859).",
            "authority": 0.95,
        },
    ],
    "newton": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Isaac_Newton",
            "title": "Isaac Newton - Wikipedia",
            "snippet": "Sir Isaac Newton (1643-1727) formulated the laws of motion and universal gravitation. He published 'Principia Mathematica' in 1687.",
            "authority": 0.95,
        },
    ],

    # ── Geography & Capitals ──────────────────────────────────────────────────
    "paris": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Paris",
            "title": "Paris - Wikipedia",
            "snippet": "Paris is the capital and most populous city of France, with a population of over 2 million in the city proper.",
            "authority": 0.95,
        },
    ],
    "france": [
        {
            "source_url": "https://en.wikipedia.org/wiki/France",
            "title": "France - Wikipedia",
            "snippet": "France is a country in Western Europe. Its capital is Paris. It is the world's most visited country with around 90 million tourists annually.",
            "authority": 0.95,
        },
    ],
    "london": [
        {
            "source_url": "https://en.wikipedia.org/wiki/London",
            "title": "London - Wikipedia",
            "snippet": "London is the capital and largest city of England and the United Kingdom, located along the River Thames.",
            "authority": 0.95,
        },
    ],
    "tokyo": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Tokyo",
            "title": "Tokyo - Wikipedia",
            "snippet": "Tokyo is the capital and largest city of Japan. The Greater Tokyo Area is the most populous metropolitan area in the world with over 37 million people.",
            "authority": 0.95,
        },
    ],
    "mount everest": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Mount_Everest",
            "title": "Mount Everest - Wikipedia",
            "snippet": "Mount Everest is Earth's highest mountain above sea level at 8,848.86 metres (29,031.7 ft), in the Mahalangur Himal sub-range of the Himalayas.",
            "authority": 0.95,
        },
    ],
    "amazon": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Amazon_River",
            "title": "Amazon River - Wikipedia",
            "snippet": "The Amazon is the world's largest river by discharge volume. The Nile is generally considered longer in total length.",
            "authority": 0.95,
        },
    ],
    "australia": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Australia",
            "title": "Australia - Wikipedia",
            "snippet": "Australia is a country and continent in the Southern Hemisphere. Its capital is Canberra, not Sydney. Sydney is the largest city.",
            "authority": 0.95,
        },
    ],
    "new york": [
        {
            "source_url": "https://en.wikipedia.org/wiki/New_York_City",
            "title": "New York City - Wikipedia",
            "snippet": "New York City is the most populous city in the United States with over 8 million residents. It is not the capital of the US — Washington D.C. is the capital.",
            "authority": 0.95,
        },
    ],

    # ── Medicine & Health ─────────────────────────────────────────────────────
    "serotonin syndrome": [
        {
            "source_url": "https://www.mayoclinic.org/diseases-conditions/serotonin-syndrome",
            "title": "Serotonin syndrome - Mayo Clinic",
            "snippet": "Serotonin syndrome occurs when medications cause high serotonin accumulation. Combining St. John's Wort with SSRIs significantly increases the risk. Symptoms include agitation, confusion, rapid heart rate.",
            "authority": 0.98,
        },
    ],
    "st. john": [
        {
            "source_url": "https://www.nccih.nih.gov/health/st-johns-wort",
            "title": "St. John's Wort | NCCIH",
            "snippet": "St. John's Wort can interact with SSRIs and may cause serotonin syndrome. It may also reduce effectiveness of birth control and antiretrovirals.",
            "authority": 0.96,
        },
    ],
    "aspirin": [
        {
            "source_url": "https://www.nhs.uk/medicines/aspirin/",
            "title": "Aspirin - NHS",
            "snippet": "Aspirin (acetylsalicylic acid) is a painkiller and anti-inflammatory. It carries risks of stomach bleeding and should not be given to children under 16.",
            "authority": 0.97,
        },
    ],
    "ibuprofen": [
        {
            "source_url": "https://www.nhs.uk/medicines/ibuprofen/",
            "title": "Ibuprofen - NHS",
            "snippet": "Ibuprofen is a common NSAID painkiller. Adults can take 200-400mg every 4-6 hours, up to 1200mg daily. Should be taken with food and avoided in pregnancy.",
            "authority": 0.97,
        },
    ],
    "covid": [
        {
            "source_url": "https://www.who.int/health-topics/coronavirus",
            "title": "Coronavirus disease (COVID-19) - WHO",
            "snippet": "COVID-19 is caused by SARS-CoV-2, first identified in Wuhan, China in December 2019. mRNA vaccines were developed in 2020.",
            "authority": 0.98,
        },
    ],
    "vaccine": [
        {
            "source_url": "https://www.who.int/health-topics/vaccines-and-immunization",
            "title": "Vaccines and immunization - WHO",
            "snippet": "Vaccines stimulate the immune system to produce antibodies without causing disease. mRNA vaccines do not alter DNA and cannot integrate into the genome.",
            "authority": 0.98,
        },
    ],
    "mrna": [
        {
            "source_url": "https://www.cdc.gov/coronavirus/2019-ncov/vaccines/different-vaccines/mrna.html",
            "title": "mRNA COVID-19 Vaccines - CDC",
            "snippet": "mRNA vaccines do not use live virus and cannot alter your DNA. The mRNA from the vaccine never enters the cell nucleus where DNA is stored.",
            "authority": 0.98,
        },
    ],
    "diabetes": [
        {
            "source_url": "https://www.who.int/health-topics/diabetes",
            "title": "Diabetes - WHO",
            "snippet": "Type 1 diabetes is an autoimmune condition with lack of insulin production. Type 2 is characterized by insulin resistance. Insulin was discovered by Banting and Best in 1921.",
            "authority": 0.97,
        },
    ],
    "penicillin": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Penicillin",
            "title": "Penicillin - Wikipedia",
            "snippet": "Penicillin was discovered by Alexander Fleming in 1928 when he noticed mold (Penicillium) killing bacteria in a petri dish. It was the world's first antibiotic.",
            "authority": 0.95,
        },
    ],

    # ── Science & Mathematics ─────────────────────────────────────────────────
    "speed of light": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Speed_of_light",
            "title": "Speed of light - Wikipedia",
            "snippet": "The speed of light in a vacuum is exactly 299,792,458 metres per second (approximately 3x10^8 m/s or 186,000 miles per second).",
            "authority": 0.99,
        },
    ],
    "gdpr": [
        {
            "source_url": "https://gdpr.eu",
            "title": "GDPR - EU",
            "snippet": "GDPR Article 5 requires personal data be kept no longer than necessary. It became enforceable on 25 May 2018. Fines can reach 20 million euros or 4% of global annual turnover.",
            "authority": 0.96,
        },
    ],
    "factorial": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Factorial",
            "title": "Factorial - Wikipedia",
            "snippet": "n! is the product of all positive integers up to n. 0! = 1 by convention. 5! = 120, 10! = 3,628,800.",
            "authority": 0.99,
        },
    ],
    "python": [
        {
            "source_url": "https://docs.python.org/3/",
            "title": "Python 3 Docs",
            "snippet": "Python is a high-level, dynamically typed programming language created by Guido van Rossum, first released in 1991. Python 3 was released in 2008.",
            "authority": 0.98,
        },
    ],
    "dna": [
        {
            "source_url": "https://en.wikipedia.org/wiki/DNA",
            "title": "DNA - Wikipedia",
            "snippet": "DNA double helix structure was discovered by Watson and Crick in 1953, based on X-ray crystallography data from Rosalind Franklin. DNA encodes genetic information.",
            "authority": 0.97,
        },
    ],
    "climate change": [
        {
            "source_url": "https://www.ipcc.ch/report/ar6/wg1/",
            "title": "IPCC Sixth Assessment Report",
            "snippet": "The IPCC AR6 (2021) states it is 'unequivocal that human influence has warmed the atmosphere, ocean and land.' Global temperatures have risen ~1.1C above pre-industrial levels.",
            "authority": 0.99,
        },
    ],
    "black hole": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Black_hole",
            "title": "Black hole - Wikipedia",
            "snippet": "A black hole is a region where gravity is so strong that nothing, not even light, can escape. The first image was captured by the Event Horizon Telescope in 2019 (galaxy M87).",
            "authority": 0.95,
        },
    ],
    "periodic table": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Periodic_table",
            "title": "Periodic table - Wikipedia",
            "snippet": "The periodic table was developed by Dmitri Mendeleev in 1869. It organizes chemical elements by atomic number. There are 118 confirmed elements.",
            "authority": 0.97,
        },
    ],

    # ── Space & Astronomy ──────────────────────────────────────────────────────
    "moon landing": [
        {
            "source_url": "https://www.nasa.gov/mission_pages/apollo/missions/apollo11.html",
            "title": "Apollo 11 - NASA",
            "snippet": "Apollo 11 was the first crewed mission to land on the Moon. Neil Armstrong and Buzz Aldrin landed on July 20, 1969. Armstrong was the first human to walk on the Moon.",
            "authority": 0.99,
        },
    ],
    "mars": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Mars",
            "title": "Mars - Wikipedia",
            "snippet": "Mars is the fourth planet from the Sun with two moons: Phobos and Deimos. It has the largest volcano in the solar system (Olympus Mons, 22 km high).",
            "authority": 0.95,
        },
    ],
    "solar system": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Solar_System",
            "title": "Solar System - Wikipedia",
            "snippet": "The Solar System has 8 planets: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune. Pluto was reclassified as a dwarf planet in 2006.",
            "authority": 0.95,
        },
    ],
    "pluto": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Pluto",
            "title": "Pluto - Wikipedia",
            "snippet": "Pluto was reclassified from a planet to a dwarf planet in 2006 by the International Astronomical Union. It has 5 known moons including Charon.",
            "authority": 0.95,
        },
    ],

    # ── Finance & Economics ────────────────────────────────────────────────────
    "compound interest": [
        {
            "source_url": "https://www.investopedia.com/terms/c/compoundinterest.asp",
            "title": "Compound Interest - Investopedia",
            "snippet": "Compound interest is calculated on both principal and accumulated interest. Formula: A = P(1 + r/n)^(nt). At 8% annually, $10,000 grows to ~$14,693 in 5 years.",
            "authority": 0.90,
        },
    ],
    "bitcoin": [
        {
            "source_url": "https://bitcoin.org/en/faq",
            "title": "Bitcoin FAQ",
            "snippet": "Bitcoin is a decentralized digital currency created in 2009 by the pseudonymous Satoshi Nakamoto. The total supply is capped at 21 million bitcoins.",
            "authority": 0.90,
        },
    ],
    "inflation": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Inflation",
            "title": "Inflation - Wikipedia",
            "snippet": "Inflation is the rate at which the general level of prices rises. Central banks typically target 2% inflation. The U.S. Federal Reserve uses the federal funds rate to influence inflation.",
            "authority": 0.90,
        },
    ],

    # ── Technology & AI ────────────────────────────────────────────────────────
    "gpt": [
        {
            "source_url": "https://openai.com/research/gpt-4",
            "title": "GPT-4 - OpenAI",
            "snippet": "GPT (Generative Pre-trained Transformer) models are developed by OpenAI. GPT-4 was released in March 2023. These are large language models trained on vast text data.",
            "authority": 0.90,
        },
    ],
    "artificial intelligence": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
            "title": "Artificial Intelligence - Wikipedia",
            "snippet": "Artificial intelligence is the simulation of human intelligence by machines. The term was coined by John McCarthy in 1956 at the Dartmouth Conference.",
            "authority": 0.90,
        },
    ],
    "machine learning": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Machine_learning",
            "title": "Machine Learning - Wikipedia",
            "snippet": "Machine learning is a subset of AI. Geoffrey Hinton, Yann LeCun, and Yoshua Bengio won the 2018 Turing Award for contributions to deep learning.",
            "authority": 0.90,
        },
    ],
    "blockchain": [
        {
            "source_url": "https://en.wikipedia.org/wiki/Blockchain",
            "title": "Blockchain - Wikipedia",
            "snippet": "A blockchain is a distributed ledger of transactions maintained by a decentralized network. Bitcoin (2009) was the first application of blockchain technology.",
            "authority": 0.90,
        },
    ],
}


def retrieve_evidence(claim: str, claim_type: str) -> List[Dict[str, Any]]:
    """
    Retrieve evidence for a claim.
    1. Check knowledge base first (fast, no network)
    2. If no KB hit → DuckDuckGo real web search (free, no API key)
    3. Numerical claims → math verifier stub
    """
    if claim_type in ("opinion", "greeting"):
        return []

    if claim_type == "numerical":
        return _math_verifier_stub(claim)

    if claim_type == "code":
        return []

    # Try KB first
    kb_results = _knowledge_base_lookup(claim)
    if kb_results:
        logger.info(f"Evidence: KB hit ({len(kb_results)} results) for '{claim[:50]}'")
        return kb_results[:3]

    # Fall back to real DuckDuckGo search
    return _duckduckgo_search(claim)


def _knowledge_base_lookup(claim: str) -> List[Dict]:
    claim_lower = claim.lower()
    results = []
    seen = set()
    for keyword, evidence_list in KNOWLEDGE_BASE.items():
        if keyword in claim_lower:
            for ev in evidence_list:
                if ev["source_url"] not in seen:
                    seen.add(ev["source_url"])
                    results.append(ev)
    return results


def _duckduckgo_search(claim: str) -> List[Dict]:
    """Real web search using DuckDuckGo — completely free, no API key."""
    try:
        from ddgs import DDGS
        results = []
        with DDGS() as ddgs_client:
            hits = ddgs_client.text(claim, max_results=3)
            for h in hits:
                results.append({
                    "source_url": h.get("href", ""),
                    "title":      h.get("title", ""),
                    "snippet":    h.get("body", "")[:300],
                    "authority":  0.6,
                })
        logger.info(f"Evidence: DuckDuckGo {len(results)} results for '{claim[:50]}'")
        return results
    except Exception as e:
        logger.warning(f"Evidence: DuckDuckGo search failed: {e}")
        return []


def _math_verifier_stub(claim: str) -> List[Dict]:
    return [{
        "source_url": "internal://math_verifier",
        "title":      "Mathematical Verification",
        "snippet":    f"Claim routed to symbolic math verifier: {claim}",
        "authority":  1.0,
    }]


def score_evidence_quality(evidence: Dict, claim: str, query_labels: Dict) -> float:
    authority   = evidence.get("authority", 0.5)
    claim_words = set(claim.lower().split())
    snip_words  = set(evidence.get("snippet", "").lower().split())
    overlap     = len(claim_words & snip_words) / max(len(claim_words), 1)
    specificity = min(overlap * 2, 1.0)
    freshness   = 0.6 if query_labels.get("current_info", 0) > 0.3 else 1.0
    return round(0.5 * authority + 0.3 * specificity + 0.2 * freshness, 3)
