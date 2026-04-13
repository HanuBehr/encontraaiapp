from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import models  # noqa: F401
from app.enums import (
    ActivityAction,
    ContactType,
    ImportBatchStatus,
    ImportBatchType,
    LeadSourceType,
    LeadStatus,
)
from app.models.activity_log import ActivityLog
from app.models.app_setting import AppSetting
from app.models.import_batch import ImportBatch
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.raw_discovery_record import RawDiscoveryRecord
from app.services.normalization import normalize_business_name, normalize_domain, normalize_phone_br
from app.services.outreach import OutreachService
from app.services.scoring import ScoringService
from app.db import init_db, session_scope


DEMO_LEADS = [
    {
        "business_name": "Oficina Mecanica Silva",
        "category": "oficina mecanica",
        "address": "Rua das Oficinas, 120",
        "neighborhood": "Centro",
        "city": "Sao Paulo",
        "state": "SP",
        "website": "https://oficinasilva.example.com",
        "email": "contato@oficinasilva.example.com",
        "phone": "+55 11 99888-7766",
        "whatsapp": "+55 11 99888-7766",
        "material_profile": {
            "batteries": {"relevant": True, "confidence": 0.82, "matched_keywords": ["bateria"]},
            "repair_waste": {"relevant": True, "confidence": 0.76, "matched_keywords": ["residuo"]},
        },
    },
    {
        "business_name": "Auto Eletrica Vale",
        "category": "auto eletrica",
        "address": "Av. Brasil, 455",
        "neighborhood": "Jardim Paulista",
        "city": "Campinas",
        "state": "SP",
        "website": "https://autovale.example.com",
        "email": "atendimento@autovale.example.com",
        "phone": "+55 19 99777-1122",
        "whatsapp": "+55 19 99777-1122",
        "material_profile": {
            "batteries": {"relevant": True, "confidence": 0.9, "matched_keywords": ["baterias"]},
            "electronics": {"relevant": True, "confidence": 0.7, "matched_keywords": ["modulo"]},
        },
    },
    {
        "business_name": "Assistencia Tecnica Byte Rapido",
        "category": "assistencia tecnica",
        "address": "Rua da Informatica, 88",
        "neighborhood": "Centro",
        "city": "Sao Jose dos Campos",
        "state": "SP",
        "website": "https://byterapido.example.com",
        "email": "contato@byterapido.example.com",
        "phone": "+55 12 99123-4545",
        "whatsapp": "+55 12 99123-4545",
        "material_profile": {
            "electronics": {"relevant": True, "confidence": 0.92, "matched_keywords": ["placa", "cpu"]},
            "repair_waste": {"relevant": True, "confidence": 0.78, "matched_keywords": ["sucata"]},
        },
    },
]


def seed_demo() -> None:
    init_db()
    with session_scope() as db:
        existing = db.query(Lead).filter(Lead.lead_source_type == LeadSourceType.DEMO_SEED).count()
        if existing:
            print(f"Demo data already present ({existing} lead(s)).")
            return

        batch = ImportBatch(
            batch_type=ImportBatchType.DEMO_SEED,
            status=ImportBatchStatus.COMPLETED,
            source_provider="demo_seed",
            source_query="seed_demo",
            location_label="Sao Paulo / Campinas / Sao Jose dos Campos",
            input_payload={"source": "scripts/seed_demo.py"},
            record_count=len(DEMO_LEADS),
        )
        db.add(batch)
        db.flush()

        for index, payload in enumerate(DEMO_LEADS, start=1):
            phone = normalize_phone_br(payload["phone"])
            whatsapp = normalize_phone_br(payload["whatsapp"])
            lead = Lead(
                business_name=payload["business_name"],
                normalized_business_name=normalize_business_name(payload["business_name"]) or payload["business_name"].lower(),
                category=payload["category"],
                address=payload["address"],
                neighborhood=payload["neighborhood"],
                city=payload["city"],
                state=payload["state"],
                website=payload["website"],
                domain=normalize_domain(payload["website"]),
                email=payload["email"],
                phone=phone,
                whatsapp=whatsapp,
                source_provider="demo_seed",
                source_url=payload["website"],
                lead_source_type=LeadSourceType.DEMO_SEED,
                status=LeadStatus.NEW,
                material_profile=payload["material_profile"],
            )
            db.add(lead)
            db.flush()

            raw_record = RawDiscoveryRecord(
                import_batch_id=batch.id,
                lead_id=lead.id,
                provider="demo_seed",
                provider_record_id=f"demo-{index}",
                search_term=payload["category"],
                search_input=payload["city"],
                source_url=payload["website"],
                payload_json=payload,
            )
            db.add(raw_record)
            db.flush()
            db.add(
                LeadContact(
                    lead_id=lead.id,
                    contact_type=ContactType.EMAIL,
                    raw_value=payload["email"],
                    normalized_value=payload["email"],
                    source_url=payload["website"],
                    source_kind="demo_seed",
                    source_record_type="raw_discovery_record",
                    source_record_id=raw_record.id if raw_record else None,
                    confidence=0.9,
                    is_primary=True,
                )
            )
            db.add(
                LeadContact(
                    lead_id=lead.id,
                    contact_type=ContactType.WHATSAPP,
                    raw_value=payload["whatsapp"],
                    normalized_value=whatsapp,
                    source_url=payload["website"],
                    source_kind="demo_seed",
                    source_record_type="raw_discovery_record",
                    source_record_id=raw_record.id if raw_record else None,
                    confidence=0.88,
                    is_primary=True,
                )
            )
            db.add(
                ActivityLog(
                    lead_id=lead.id,
                    entity_type="lead",
                    entity_id=lead.id,
                    action=ActivityAction.IMPORTED,
                    actor="seed_demo",
                    message="Demo lead inserted.",
                    metadata_json={"batch_id": batch.id, "provider_record_id": f"demo-{index}"},
                )
            )

            ScoringService(db).score_lead_instance(lead)

        if not db.query(AppSetting).filter(AppSetting.key == "daily_email_limit").first():
            db.add(AppSetting(key="daily_email_limit", value={"value": 25}, description="Default daily email limit"))
        if not db.query(AppSetting).filter(AppSetting.key == "daily_whatsapp_limit").first():
            db.add(
                AppSetting(
                    key="daily_whatsapp_limit",
                    value={"value": 25},
                    description="Default daily WhatsApp limit",
                )
            )

        OutreachService(db).ensure_default_templates()

    print(f"Demo data seeded: {len(DEMO_LEADS)} leads.")


if __name__ == "__main__":
    seed_demo()
