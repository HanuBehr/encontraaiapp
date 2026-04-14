from __future__ import annotations

from enum import Enum


class LeadStatus(str, Enum):
    NEW = "new"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    CONTACTED = "contacted"
    REPLIED = "replied"
    INTERESTED = "interested"
    CLOSED = "closed"
    NOT_INTERESTED = "not_interested"
    DO_NOT_CONTACT = "do_not_contact"


class LeadSourceType(str, Enum):
    GOOGLE_PLACES = "google_places"
    WEBSITE = "website"
    MANUAL_IMPORT = "manual_import"
    DEMO_SEED = "demo_seed"
    MERGED = "merged"


class CompanySizeFit(str, Enum):
    IDEAL_SME = "ideal_sme"
    POSSIBLE_SME = "possible_sme"
    LARGE_ENTERPRISE = "large_enterprise"
    UNKNOWN = "unknown"


class TradeType(str, Enum):
    VAREJO = "varejo"
    ATACADO = "atacado"
    DISTRIBUIDORA = "distribuidora"
    ECOMMERCE = "ecommerce"
    INDUSTRIA = "industria"
    CONSTRUCAO_CIVIL = "construcao_civil"
    UNKNOWN = "unknown"


class ImportBatchType(str, Enum):
    DISCOVERY = "discovery"
    MANUAL_IMPORT = "manual_import"
    DEMO_SEED = "demo_seed"


class ImportBatchStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ContactType(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    WHATSAPP = "whatsapp"
    INSTAGRAM = "instagram"
    CONTACT_FORM = "contact_form"


class OutreachChannel(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class TemplateKey(str, Enum):
    COLD_EMAIL = "cold_email"
    COLD_WHATSAPP = "cold_whatsapp"
    FOLLOW_UP_EMAIL = "follow_up_email"
    FOLLOW_UP_WHATSAPP = "follow_up_whatsapp"


class DraftStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"


class MessageStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class ActivityAction(str, Enum):
    DISCOVERED = "discovered"
    IMPORTED = "imported"
    ENRICHED = "enriched"
    DEDUPED = "deduped"
    SCORE_RECALCULATED = "score_recalculated"
    EXPORTED = "exported"
    DRAFT_GENERATED = "draft_generated"
    APPROVED_FOR_SEND = "approved_for_send"
    SENT = "sent"
    FAILED_SEND = "failed_send"
    STATUS_CHANGED = "status_changed"
    NOTE_ADDED = "note_added"
    LEAD_UPDATED = "lead_updated"
