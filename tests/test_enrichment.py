from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests

from app.config import Settings
from app.enums import ContactType, ImportBatchStatus, ImportBatchType, LeadSourceType, LeadStatus
from app.models.import_batch import ImportBatch
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.lead_enrichment_record import LeadEnrichmentRecord
from app.models.raw_discovery_record import RawDiscoveryRecord
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
    def __init__(self, responses: dict[str, FakeResponse], *, default_status_code: int | None = 404) -> None:
        self.responses = responses
        self.default_status_code = default_status_code

    def get(self, url: str, **kwargs) -> FakeResponse:
        if url not in self.responses:
            if self.default_status_code is not None:
                return FakeResponse(
                    url=url,
                    text="<html><body>Not found</body></html>",
                    status_code=self.default_status_code,
                )
            raise requests.RequestException(f"No fake response for {url}")
        return self.responses[url]


def _cloudflare_email(value: str) -> str:
    key = 0x12
    return f"{key:02x}" + "".join(f"{ord(character) ^ key:02x}" for character in value)


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


def test_extract_public_page_data_finds_hidden_and_obfuscated_emails() -> None:
    encoded_cloudflare_email = _cloudflare_email("cloud@empresa.com.br")
    html = f"""
    <html>
      <head>
        <script type="application/ld+json">{{"email": "vendas@empresa.com.br"}}</script>
        <meta name="reply-to" content="orcamento@empresa.com.br">
      </head>
      <body>
        <a href="mailto:financeiro%40empresa.com.br">Financeiro</a>
        <div data-contact="sac%40empresa.com.br"></div>
        <p>Comercial: comercial [arroba] empresa [ponto] com [ponto] br</p>
        <span class="__cf_email__" data-cfemail="{encoded_cloudflare_email}"></span>
      </body>
    </html>
    """

    result = extract_public_page_data(html, "https://example.com/")
    emails = {item["normalized_value"] for item in result.extracted_fields["emails"]}

    assert {
        "vendas@empresa.com.br",
        "orcamento@empresa.com.br",
        "financeiro@empresa.com.br",
        "sac@empresa.com.br",
        "comercial@empresa.com.br",
        "cloud@empresa.com.br",
    }.issubset(emails)


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


def test_enrichment_service_follows_discovered_same_host_contact_pages(db_session) -> None:
    lead = Lead(
        business_name="Empresa com Atendimento",
        normalized_business_name=normalize_business_name("Empresa com Atendimento") or "empresa com atendimento",
        category="materiais para construcao",
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
                text='<html><body><a href="/suporte/comercial">Fale com o suporte comercial</a></body></html>',
            ),
            "https://example.com/suporte/comercial": FakeResponse(
                url="https://example.com/suporte/comercial",
                text="<html><body>Contato comercial: vendas@example.com</body></html>",
            ),
        }
    )

    settings = Settings(APP_ENV="test", DATABASE_URL="sqlite://", EXPORT_DIR="./data/exports", GOOGLE_API_KEY="")
    service = EnrichmentService(db_session, settings, http_session=fake_http)

    result = service.enrich_lead(lead.id, actor="test")

    refreshed_lead = db_session.get(Lead, lead.id)
    source_urls = {
        row.source_url
        for row in db_session.query(LeadEnrichmentRecord).filter(LeadEnrichmentRecord.lead_id == lead.id).all()
    }

    assert result.pages_fetched >= 2
    assert refreshed_lead is not None
    assert refreshed_lead.email == "vendas@example.com"
    assert "https://example.com/suporte/comercial" in source_urls


def test_enrichment_service_batch_summary_counts_contacts_and_skips(db_session) -> None:
    lead_with_site = Lead(
        business_name="Empresa Publica",
        normalized_business_name=normalize_business_name("Empresa Publica") or "empresa publica",
        category="materiais para construcao",
        city="Sao Paulo",
        state="SP",
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=LeadStatus.NEW,
        website="https://batch.example.com",
    )
    lead_without_site = Lead(
        business_name="Empresa Sem Site",
        normalized_business_name=normalize_business_name("Empresa Sem Site") or "empresa sem site",
        category="materiais para construcao",
        city="Sao Paulo",
        state="SP",
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=LeadStatus.NEW,
    )
    db_session.add_all([lead_with_site, lead_without_site])
    db_session.commit()
    db_session.refresh(lead_with_site)
    db_session.refresh(lead_without_site)

    fake_http = FakeHTTPSession(
        {
            "https://batch.example.com/robots.txt": FakeResponse(
                url="https://batch.example.com/robots.txt",
                text="User-agent: *\nAllow: /\n",
                content_type="text/plain",
            ),
            "https://batch.example.com": FakeResponse(
                url="https://batch.example.com",
                text="""
                <html><body>
                <a href="mailto:vendas@batch.example.com">Email</a>
                <a href="https://wa.me/5511987654321">WhatsApp</a>
                <a href="https://instagram.com/batchexample">Instagram</a>
                <form action="/contato"></form>
                </body></html>
                """,
            ),
        }
    )

    settings = Settings(APP_ENV="test", DATABASE_URL="sqlite://", EXPORT_DIR="./data/exports", GOOGLE_API_KEY="")
    service = EnrichmentService(db_session, settings, http_session=fake_http)

    response = service.enrich_lead_ids(
        [lead_with_site.id, lead_without_site.id],
        actor="test",
        scope_label="selected leads",
    )

    assert response.processed == 2
    assert response.summary.requested == 2
    assert response.summary.emails_found == 1
    assert response.summary.whatsapps_found == 1
    assert response.summary.instagrams_found == 1
    assert response.summary.contact_forms_found == 1
    assert response.summary.skipped_no_website == 1
    assert response.summary.errors == 0


def test_enrichment_service_batch_continues_after_lead_exception(db_session, monkeypatch) -> None:
    good_lead = Lead(
        business_name="Empresa Boa",
        normalized_business_name=normalize_business_name("Empresa Boa") or "empresa boa",
        category="materiais para construcao",
        city="Sao Paulo",
        state="SP",
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=LeadStatus.NEW,
        website="https://good.example.com",
    )
    broken_lead = Lead(
        business_name="Empresa Quebrada",
        normalized_business_name=normalize_business_name("Empresa Quebrada") or "empresa quebrada",
        category="materiais para construcao",
        city="Sao Paulo",
        state="SP",
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=LeadStatus.NEW,
        website="https://broken.example.com",
    )
    db_session.add_all([good_lead, broken_lead])
    db_session.commit()
    db_session.refresh(good_lead)
    db_session.refresh(broken_lead)

    fake_http = FakeHTTPSession(
        {
            "https://good.example.com/robots.txt": FakeResponse(
                url="https://good.example.com/robots.txt",
                text="User-agent: *\nAllow: /\n",
                content_type="text/plain",
            ),
            "https://good.example.com": FakeResponse(
                url="https://good.example.com",
                text='<html><body><a href="mailto:vendas@good.example.com">Email</a></body></html>',
            ),
        }
    )

    settings = Settings(APP_ENV="test", DATABASE_URL="sqlite://", EXPORT_DIR="./data/exports", GOOGLE_API_KEY="")
    service = EnrichmentService(db_session, settings, http_session=fake_http)
    original_enrich_lead = service.enrich_lead

    def flaky_enrich_lead(lead_id: int, *, actor: str = "system"):
        if lead_id == broken_lead.id:
            raise RuntimeError("parser failed on public page")
        return original_enrich_lead(lead_id, actor=actor)

    monkeypatch.setattr(service, "enrich_lead", flaky_enrich_lead)

    response = service.enrich_lead_ids(
        [good_lead.id, broken_lead.id],
        actor="test",
        scope_label="selected leads",
        continue_on_error=True,
    )

    assert response.processed == 2
    assert response.summary.requested == 2
    assert response.summary.processed == 2
    assert response.summary.success_count == 1
    assert response.summary.errors == 1
    assert response.summary.failed_lead_ids == [broken_lead.id]
    assert response.results[0].success is True
    assert response.results[1].success is False
    assert response.results[1].business_name == "Empresa Quebrada"
    assert response.results[1].error_message == "parser failed on public page"


def test_enrichment_service_enriches_latest_import_batch(db_session) -> None:
    old_lead = Lead(
        business_name="Old Batch Lead",
        normalized_business_name=normalize_business_name("Old Batch Lead") or "old batch lead",
        category="materiais para construcao",
        city="Sao Paulo",
        state="SP",
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=LeadStatus.NEW,
        website="https://old.example.com",
    )
    new_lead = Lead(
        business_name="New Batch Lead",
        normalized_business_name=normalize_business_name("New Batch Lead") or "new batch lead",
        category="materiais para construcao",
        city="Sao Paulo",
        state="SP",
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=LeadStatus.NEW,
        website="https://new.example.com",
    )
    db_session.add_all([old_lead, new_lead])
    db_session.flush()

    now = datetime.now(timezone.utc)
    old_batch = ImportBatch(
        batch_type=ImportBatchType.DISCOVERY,
        status=ImportBatchStatus.COMPLETED,
        source_provider="test",
        source_query="old",
        location_label="SP",
        record_count=1,
        completed_at=now - timedelta(days=1),
    )
    new_batch = ImportBatch(
        batch_type=ImportBatchType.DISCOVERY,
        status=ImportBatchStatus.COMPLETED,
        source_provider="test",
        source_query="new",
        location_label="SP",
        record_count=1,
        completed_at=now,
    )
    db_session.add_all([old_batch, new_batch])
    db_session.flush()
    db_session.add_all(
        [
            RawDiscoveryRecord(
                import_batch_id=old_batch.id,
                lead_id=old_lead.id,
                provider="test",
                provider_record_id="old-1",
                payload_json={},
            ),
            RawDiscoveryRecord(
                import_batch_id=new_batch.id,
                lead_id=new_lead.id,
                provider="test",
                provider_record_id="new-1",
                payload_json={},
            ),
        ]
    )
    db_session.commit()
    db_session.refresh(new_lead)

    fake_http = FakeHTTPSession(
        {
            "https://new.example.com/robots.txt": FakeResponse(
                url="https://new.example.com/robots.txt",
                text="User-agent: *\nAllow: /\n",
                content_type="text/plain",
            ),
            "https://new.example.com": FakeResponse(
                url="https://new.example.com",
                text='<html><body><a href="mailto:new@example.com">Email</a></body></html>',
            ),
        }
    )

    settings = Settings(APP_ENV="test", DATABASE_URL="sqlite://", EXPORT_DIR="./data/exports", GOOGLE_API_KEY="")
    service = EnrichmentService(db_session, settings, http_session=fake_http)

    response = service.enrich_latest_import_batch(actor="test")

    refreshed_new_lead = db_session.get(Lead, new_lead.id)
    refreshed_old_lead = db_session.get(Lead, old_lead.id)

    assert response.processed == 1
    assert response.summary.scope_label == f"latest import batch {new_batch.id}"
    assert response.summary.emails_found == 1
    assert refreshed_new_lead is not None
    assert refreshed_new_lead.email == "new@example.com"
    assert refreshed_old_lead is not None
    assert refreshed_old_lead.last_enriched_at is None
