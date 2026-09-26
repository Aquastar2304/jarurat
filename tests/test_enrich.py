from lead_automation.enrich import _extract, _pick_email, domain_of, generate_email_patterns, guess_email
from lead_automation.models import Lead


def test_domain_of_strips_scheme_www_and_path():
    assert domain_of("https://www.Example.org/contact") == "example.org"
    assert domain_of("example.org") == "example.org"
    assert domain_of(None) is None
    assert domain_of(float("nan")) is None


def test_generate_email_patterns_for_organisation():
    patterns = generate_email_patterns("Example.org")
    assert patterns[0] == "info@example.org"
    assert "contact@example.org" in patterns
    assert len(patterns) == len(set(patterns))


def test_generate_email_patterns_for_person():
    patterns = generate_email_patterns("example.org", "Asha", "Rao")
    assert patterns[:3] == ["asha.rao@example.org", "asharao@example.org", "arao@example.org"]


def test_guess_email_marks_generated_and_missing():
    with_site = guess_email(Lead(name="A", source="t", website="https://www.a-org.in"))
    assert with_site.email == "info@a-org.in"
    assert with_site.email_status == "generated (unverified)"

    without = guess_email(Lead(name="B", source="t"))
    assert without.email is None and without.email_status == "missing"

    found = guess_email(Lead(name="C", source="t", email="x@c.org", email_status="found"))
    assert found.email == "x@c.org" and found.email_status == "found"


def test_extract_finds_mailto_plain_text_and_linkedin_and_ignores_junk():
    html = """
    <html><body>
      <a href="mailto:Contact@Org.in?subject=hi">mail</a>
      <p>Write to admin@org.in or see logo@2x.png</p>
      <a href="https://www.linkedin.com/company/org-in/">LinkedIn</a>
      <a href="mailto:noreply@org.in">no</a>
    </body></html>"""
    emails, linkedin = _extract(html, "https://org.in")
    assert emails == {"contact@org.in", "admin@org.in"}
    assert linkedin == "https://www.linkedin.com/company/org-in"


def test_pick_email_prefers_own_domain_and_generic_mailbox():
    emails = {"someone@gmail.com", "john@org.in", "info@org.in"}
    assert _pick_email(emails, "org.in") == "info@org.in"
    assert _pick_email(set(), "org.in") is None
