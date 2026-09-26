"""Contact enrichment.

* ``discover_contacts``  - visits an organisation's website (home page and,
  if needed, a contact page) and extracts a real email + LinkedIn URL.
* ``generate_email_patterns`` / ``guess_email`` - bonus feature: when no
  email is published, derive the most likely address from the domain.
  Generated addresses are clearly flagged as *unverified*.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .http_client import PoliteSession
from .models import Lead

log = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
LINKEDIN_RE = re.compile(
    r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:company|in|school)/[A-Za-z0-9_\-%.]+", re.I
)
CONTACT_PATHS = ("/contact", "/contact-us", "/contactus", "/about", "/about-us")

# Things that look like emails but are not contact addresses.
_BAD_EMAIL_PARTS = (
    "example.", "sentry.", "wixpress", "@2x", ".png", ".jpg", ".gif", ".svg",
    "noreply", "no-reply", "donotreply", "yourname", "email@", "name@", "user@",
    "domain.com", "@w3.org", "schema.org",
)
# Generic mailboxes, most-likely first, used when nothing is published.
ORG_MAILBOXES = ("info", "contact", "hello", "office", "admin")


def domain_of(url: str | None) -> str | None:
    """'https://www.Example.org/path' -> 'example.org'."""
    if not isinstance(url, str) or not url.strip():
        return None
    if "://" not in url:
        url = "http://" + url
    host = urlsplit(url).netloc.lower().split(":")[0]
    return host.removeprefix("www.") or None


def _is_plausible(email: str) -> bool:
    lowered = email.lower()
    return not any(bad in lowered for bad in _BAD_EMAIL_PARTS)


def _extract(html: str, base_url: str) -> tuple[set[str], str | None]:
    soup = BeautifulSoup(html, "lxml")
    emails: set[str] = set()
    linkedin: str | None = None
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("mailto:"):
            addr = href[7:].split("?")[0].strip()
            if EMAIL_RE.fullmatch(addr) and _is_plausible(addr):
                emails.add(addr.lower())
        elif linkedin is None:
            match = LINKEDIN_RE.match(urljoin(base_url, href))
            if match:
                linkedin = match.group(0).rstrip("/")
    # Plain-text addresses (not wrapped in mailto:)
    for addr in EMAIL_RE.findall(soup.get_text(" ")):
        if _is_plausible(addr):
            emails.add(addr.lower())
    if linkedin is None:
        match = LINKEDIN_RE.search(html)
        if match:
            linkedin = match.group(0).rstrip("/")
    return emails, linkedin


def _pick_email(emails: set[str], site_domain: str | None) -> str | None:
    if not emails:
        return None

    # Prefer addresses on the organisation's own domain, then generic mailboxes.
    def score(addr: str) -> tuple[int, int, str]:
        local, _, dom = addr.partition("@")
        same_domain = 0 if site_domain and dom.endswith(site_domain) else 1
        generic = 0 if local in ORG_MAILBOXES else 1
        return (same_domain, generic, addr)

    return sorted(emails, key=score)[0]


def discover_contacts(session: PoliteSession, website: str) -> tuple[str | None, str | None]:
    """Return ``(email, linkedin_url)`` found on the website, each may be None."""
    site_domain = domain_of(website)
    emails: set[str] = set()
    linkedin: str | None = None
    base = website.rstrip("/") + "/"
    pages = [website] + [urljoin(base, p.lstrip("/")) for p in CONTACT_PATHS]
    for url in pages:
        try:
            resp = session.get(url, timeout=10, allow_redirects=True)
        except Exception as exc:  # noqa: BLE001 - dead sites are expected
            log.debug("enrich %s: %s", url, type(exc).__name__)
            break  # if the home page is dead, contact pages will be too
        if resp.status_code != 200 or "html" not in resp.headers.get("Content-Type", ""):
            continue
        found, li = _extract(resp.text, url)
        emails |= found
        linkedin = linkedin or li
        if emails:  # good enough, stop crawling
            break
    return _pick_email(emails, site_domain), linkedin


def generate_email_patterns(
    domain: str, first_name: str | None = None, last_name: str | None = None
) -> list[str]:
    """Return likely email addresses for a domain, most probable first.

    For a person (``first_name``/``last_name`` given) the usual corporate
    conventions are produced; for an organisation the generic mailboxes.
    """
    domain = domain.lower().strip()
    if first_name and last_name:
        f, l = first_name.lower().strip(), last_name.lower().strip()
        patterns = [
            f"{f}.{l}", f"{f}{l}", f"{f[0]}{l}", f"{f}_{l}", f"{f}", f"{l}.{f}", f"{f[0]}.{l}",
        ]
    elif first_name:
        patterns = [first_name.lower().strip()]
    else:
        patterns = list(ORG_MAILBOXES)
    result: list[str] = []
    for p in patterns:
        addr = f"{p}@{domain}"
        if addr not in result:
            result.append(addr)
    return result


def guess_email(lead: Lead) -> Lead:
    """Fill ``lead.email`` with a generated pattern when none was found."""
    if lead.email:
        return lead
    domain = domain_of(lead.website)
    if domain:
        lead.email = generate_email_patterns(domain)[0]
        lead.email_status = "generated (unverified)"
    else:
        lead.email_status = "missing"
    return lead


def enrich_leads(leads: list[Lead], session: PoliteSession, workers: int = 8) -> list[Lead]:
    """Look up emails / LinkedIn for every lead that has a website, in parallel."""
    targets = [lead for lead in leads if lead.website and not lead.email]
    log.info("Enriching %d leads with websites (%d workers)", len(targets), workers)

    def work(lead: Lead) -> Lead:
        email, linkedin = discover_contacts(session, lead.website)  # type: ignore[arg-type]
        if email:
            lead.email, lead.email_status = email, "found"
        if linkedin and not lead.linkedin:
            lead.linkedin = linkedin
        return lead

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(work, lead): lead for lead in targets}
        for fut in as_completed(futures):
            lead = futures[fut]
            try:
                fut.result()
            except Exception as exc:  # noqa: BLE001
                log.warning("Enrichment failed for %s: %s", lead.name, exc)

    for lead in leads:
        guess_email(lead)
    found = sum(1 for lead in leads if lead.email_status == "found")
    log.info("Emails found on websites: %d / %d", found, len(targets))
    return leads
