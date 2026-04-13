from __future__ import annotations

import requests

from app.config import Settings
from app.enums import ContactType, LeadSourceType, LeadStatus
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.lead_enrichment_record import LeadEnrichmentRecord
from app.services.enrichment import EnrichmentService, extract_public_page_data
from app.services.normalization import normalize_business_name


class FakeResponse:
    def __init__(
        self,
        *,
        url: str,
        text: str,
        status_code: int = 200,
        content_type: str = "text/html; charset=utf-8",
    ) -> None:
        self.url = url
        self.text = text
        self.status_code = status_code
        self.headers = {"content-type": content_type}


class FakeHTTPSession:
    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.responses = responses

    def get(self, url: str, **kwargs) -> FakeResponse:
        if url not in self.responses:
            raise requests.RequestException(f"No fake response for {url}")
        return self.responses[url]


def test_extract_public_page_data_finds_contacts_and_signals() -> None:
    html = """
    <html>
      <body>
        <a href="mailto:contato@oficina.com.br">Email</a>
        <a href="tel:+5511987654321">Ligar</a>
        <a href="https://wa.me/5511987654321">WhatsApp</a>
        <a href="https://instagram.com/oficina">Instagram</a>
        <form action="/fale-conosco"></form>
        <p>Trabalhamos com baterias, eletrônica automotiva e manutenção.</p>
      </body>
    </html>
    """

    result = extract_public_page_data(html, "https://example.com/")

    assert result.extracted_fields["emails"]
    assert result.extracted_fields["phones"]
    assert result.extracted_fields["whatsapps"]
    assert result.extracted_fields["instagram_links"]
    assert result.extracted_fields["contact_form_urls"]
    assert result.material_signals["batteries"]["relevant"] is True
    assert result.material_signals["electronics"]["relevant"] is True


def test_enrichment_service_updates_lead_and_stores_history(db_session) -> None:
    lead = Lead(
        business_name="Oficina Reversa",
        normalized_business_name=normalize_business_name("Oficina Reversa") or "oficina reversa",
        category="oficina mecânica",
        city="Sao Paulo",
        state="SP",
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=LeadStatus.NEW,
        website="https://example.com",
    )
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_http = FakeHTTPSession(
        {
            "https://example.com/robots.txt": FakeResponse(
                url="https://example.com/robots.txt",
                text="User-agent: *\nAllow: /\n",
                content_type="text/plain",
            ),
            "https://example.com": FakeResponse(
                url="https://example.com",
                text="""
                <html><body>
                <a href="mailto:contato@oficinareversa.com.br">contato@oficinareversa.com.br</a>
                <a href="tel:+5511912345678">Telefone</a>
                <a href="https://api.whatsapp.com/send?phone=5511912345678">WhatsApp</a>
                <a href="https://instagram.com/oficinareversa">Instagram</a>
                <p>Coleta de baterias, eletrônica e sucata de manutenção.</p>
                </body></html>
                """,
            ),
            "https://example.com/": FakeResponse(
                url="https://example.com/",
                text="<html><body>Homepage</body></html>",
            ),
            "https://example.com/contato": FakeResponse(
                url="https://example.com/contato",
                text='<html><body><form action="/contato/form"></form></body></html>',
            ),
        }
    )

    settings = Settings(APP_ENV="test", DATABASE_URL="sqlite://", EXPORT_DIR="./data/exports", GOOGLE_API_KEY="")
    service = EnrichmentService(db_session, settings, http_session=fake_http)

    result = service.enrich_lead(lead.id, actor="test")

    refreshed_lead = db_session.get(Lead, lead.id)
    contacts = db_session.query(LeadContact).filter(LeadContact.lead_id == lead.id).all()
    enrichments = (
        db_session.query(LeadEnrichmentRecord)
        .filter(LeadEnrichmentRecord.lead_id == lead.id)
        .all()
    )

    assert result.contacts_added >= 4
    assert refreshed_lead is not None
    assert refreshed_lead.email == "contato@oficinareversa.com.br"
    assert refreshed_lead.whatsapp == "+5511912345678"
    assert refreshed_lead.last_enriched_at is not None
    assert any(contact.contact_type == ContactType.CONTACT_FORM for contact in contacts)
    assert enrichments
