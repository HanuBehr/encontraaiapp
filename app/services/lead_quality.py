from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.enums import CompanySizeFit, TradeType
from app.models.base import utcnow
from app.models.lead import Lead
from app.repositories.lead_repository import LeadRepository
from app.schemas.lead import LeadListFilters
from app.services.normalization import normalize_text


KNOWN_LARGE_ENTERPRISE_SIGNALS = (
    "walmart",
    "carrefour",
    "atacadao",
    "assai",
    "magazine luiza",
    "mercado livre",
    "amazon",
    "shopee",
    "americanas",
    "casas bahia",
    "madeira madeira",
    "pao de acucar",
    "extra hipermercado",
    "hipermercado extra",
)
ENTERPRISE_SCALE_CATEGORY_SIGNALS = (
    "hipermercado",
    "megastore",
    "shopping center",
    "shopping mall",
)
DISTRIBUTOR_SIGNALS = (
    "distribuidora",
    "distribuicao",
    "distributor",
)
WHOLESALE_SIGNALS = (
    "atacado",
    "atacadista",
    "wholesale",
)
ECOMMERCE_SIGNALS = (
    "e commerce",
    "ecommerce",
    "loja online",
    "online store",
    "marketplace",
)
INDUSTRY_SIGNALS = (
    "industria",
    "industrial",
    "fabrica",
    "manufacturer",
    "manufatura",
)
RETAIL_SIGNALS = (
    "loja",
    "store",
    "boutique",
    "showroom",
    "retail",
)


@dataclass(slots=True)
class LeadQualitySuggestion:
    company_size_fit: CompanySizeFit
    company_size_fit_explanation: str
    company_size_fit_metadata: dict[str, Any] = field(default_factory=dict)
    trade_type: TradeType = TradeType.UNKNOWN
    trade_type_explanation: str = "Trade type could not be determined from available lead data."
    trade_type_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LeadQualityResult:
    lead_id: int
    changed_fields: list[str]
    suggestion: LeadQualitySuggestion


@dataclass(slots=True)
class LeadQualityBatchResult:
    processed: int
    changed: int
    dry_run: bool
    results: list[LeadQualityResult]


class LeadQualityService:
    def __init__(self, db: Session, organization_id: int | None = None) -> None:
        self.db = db
        self.repository = LeadRepository(db, organization_id=organization_id)

    def evaluate_lead(self, lead: Lead) -> LeadQualitySuggestion:
        text = self._lead_text(lead)
        enterprise_match = self._first_match(text, KNOWN_LARGE_ENTERPRISE_SIGNALS)
        enterprise_category_match = self._first_match(text, ENTERPRISE_SCALE_CATEGORY_SIGNALS)
        trade_type, trade_explanation, trade_metadata = self._classify_trade_type(lead, text)
        fit, fit_explanation, fit_metadata = self._classify_company_size_fit(
            lead=lead,
            trade_type=trade_type,
            enterprise_match=enterprise_match,
            enterprise_category_match=enterprise_category_match,
        )
        return LeadQualitySuggestion(
            company_size_fit=fit,
            company_size_fit_explanation=fit_explanation,
            company_size_fit_metadata=fit_metadata,
            trade_type=trade_type,
            trade_type_explanation=trade_explanation,
            trade_type_metadata=trade_metadata,
        )

    def apply_to_lead(self, lead_id: int, *, overwrite: bool = False, dry_run: bool = False) -> LeadQualityResult:
        lead = self.repository.get_with_related(lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} not found in organization scope.")
        return self._apply_to_loaded_lead(lead, overwrite=overwrite, dry_run=dry_run)

    def apply_batch(
        self,
        *,
        lead_ids: Iterable[int] | None = None,
        filters: LeadListFilters | None = None,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> LeadQualityBatchResult:
        if lead_ids is not None:
            leads = self.repository.get_by_ids(lead_ids)
        else:
            leads = self.repository.list_all_leads(filters)

        results = [self._apply_to_loaded_lead(lead, overwrite=overwrite, dry_run=dry_run) for lead in leads]
        if not dry_run:
            self.db.flush()
        return LeadQualityBatchResult(
            processed=len(results),
            changed=sum(1 for result in results if result.changed_fields),
            dry_run=dry_run,
            results=results,
        )

    def _apply_to_loaded_lead(
        self,
        lead: Lead,
        *,
        overwrite: bool,
        dry_run: bool,
    ) -> LeadQualityResult:
        suggestion = self.evaluate_lead(lead)
        changed_fields = self._changed_fields(lead, suggestion, overwrite=overwrite)
        if not dry_run:
            self._apply_suggestion(lead, suggestion, changed_fields=changed_fields)
            self.db.flush()
        return LeadQualityResult(lead_id=lead.id, changed_fields=changed_fields, suggestion=suggestion)

    def _classify_company_size_fit(
        self,
        *,
        lead: Lead,
        trade_type: TradeType,
        enterprise_match: str | None,
        enterprise_category_match: str | None,
    ) -> tuple[CompanySizeFit, str, dict[str, Any]]:
        if enterprise_match:
            return (
                CompanySizeFit.LARGE_ENTERPRISE,
                f"Matched known enterprise-scale signal '{enterprise_match}'.",
                self._fit_metadata(
                    lead,
                    signal_type="known_large_chain",
                    matched_signal=enterprise_match,
                    direct_contact_count=self._direct_contact_count(lead),
                    location_signal_count=self._location_signal_count(lead),
                    trade_type=trade_type,
                ),
            )
        if enterprise_category_match:
            return (
                CompanySizeFit.LARGE_ENTERPRISE,
                f"Matched enterprise-scale category signal '{enterprise_category_match}'.",
                self._fit_metadata(
                    lead,
                    signal_type="enterprise_scale_category",
                    matched_signal=enterprise_category_match,
                    direct_contact_count=self._direct_contact_count(lead),
                    location_signal_count=self._location_signal_count(lead),
                    trade_type=trade_type,
                ),
            )

        direct_contact_count = self._direct_contact_count(lead)
        location_signal_count = self._location_signal_count(lead)
        has_market_classification = bool(lead.market_segment_id or lead.market_subsegment_id)
        known_trade_type = trade_type != TradeType.UNKNOWN

        if direct_contact_count >= 2 and location_signal_count >= 1:
            return (
                CompanySizeFit.IDEAL_SME,
                "Lead has multiple direct contact channels plus location evidence.",
                self._fit_metadata(
                    lead,
                    signal_type="contact_and_location_complete",
                    matched_signal=None,
                    direct_contact_count=direct_contact_count,
                    location_signal_count=location_signal_count,
                    trade_type=trade_type,
                ),
            )
        if has_market_classification and direct_contact_count >= 1 and location_signal_count >= 1:
            return (
                CompanySizeFit.IDEAL_SME,
                "Lead has explicit market classification plus direct contact and location evidence.",
                self._fit_metadata(
                    lead,
                    signal_type="market_classification_supported",
                    matched_signal=None,
                    direct_contact_count=direct_contact_count,
                    location_signal_count=location_signal_count,
                    trade_type=trade_type,
                ),
            )
        if direct_contact_count >= 1 or location_signal_count >= 1 or has_market_classification or known_trade_type:
            return (
                CompanySizeFit.POSSIBLE_SME,
                "Lead has partial business evidence, but not enough to confirm a strong SME profile yet.",
                self._fit_metadata(
                    lead,
                    signal_type="partial_business_evidence",
                    matched_signal=None,
                    direct_contact_count=direct_contact_count,
                    location_signal_count=location_signal_count,
                    trade_type=trade_type,
                ),
            )
        return (
            CompanySizeFit.UNKNOWN,
            "Not enough business evidence is available to classify company size fit.",
            self._fit_metadata(
                lead,
                signal_type="insufficient_evidence",
                matched_signal=None,
                direct_contact_count=direct_contact_count,
                location_signal_count=location_signal_count,
                trade_type=trade_type,
            ),
        )

    def _classify_trade_type(self, lead: Lead, text: str) -> tuple[TradeType, str, dict[str, Any]]:
        segment_key = self._related_key(getattr(lead, "market_segment", None))
        subsegment_text = self._related_text(getattr(lead, "market_subsegment", None))

        if segment_key == "varejo":
            return self._trade_result(TradeType.VAREJO, "Matched explicit market segment 'Varejo'.", "market_segment")
        if segment_key == "e_commerce":
            return self._trade_result(
                TradeType.ECOMMERCE,
                "Matched explicit market segment 'E-commerce'.",
                "market_segment",
            )
        if segment_key == "industria":
            return self._trade_result(TradeType.INDUSTRIA, "Matched explicit market segment 'Industria'.", "market_segment")
        if segment_key == "construcao_civil":
            return self._trade_result(
                TradeType.CONSTRUCAO_CIVIL,
                "Matched explicit market segment 'Construcao Civil'.",
                "market_segment",
            )
        if segment_key == "atacado_distribuidora":
            direct_text = self._lead_direct_text(lead)
            combined_trade_text = f"{subsegment_text} {direct_text}"
            distributor_match = self._first_match(combined_trade_text, DISTRIBUTOR_SIGNALS)
            if distributor_match:
                return self._trade_result(
                    TradeType.DISTRIBUIDORA,
                    f"Matched distributor signal '{distributor_match}' in an explicit Atacado/Distribuidora context.",
                    "subsegment_or_text",
                    distributor_match,
                )
            wholesale_match = self._first_match(combined_trade_text, WHOLESALE_SIGNALS)
            if wholesale_match:
                return self._trade_result(
                    TradeType.ATACADO,
                    f"Matched wholesale signal '{wholesale_match}' in an explicit Atacado/Distribuidora context.",
                    "subsegment_or_text",
                    wholesale_match,
                )
            return self._trade_result(
                TradeType.UNKNOWN,
                "Explicit Atacado/Distribuidora taxonomy is present, but the text does not distinguish wholesale from distributor.",
                "market_segment",
            )

        for trade_type, signals in [
            (TradeType.ECOMMERCE, ECOMMERCE_SIGNALS),
            (TradeType.DISTRIBUIDORA, DISTRIBUTOR_SIGNALS),
            (TradeType.ATACADO, WHOLESALE_SIGNALS),
            (TradeType.INDUSTRIA, INDUSTRY_SIGNALS),
            (TradeType.VAREJO, RETAIL_SIGNALS),
        ]:
            match = self._first_match(text, signals)
            if match:
                return self._trade_result(
                    trade_type,
                    f"Matched business-model signal '{match}' in lead text.",
                    "lead_text",
                    match,
                )

        return self._trade_result(
            TradeType.UNKNOWN,
            "Trade type could not be determined from available lead data.",
            "unknown",
        )

    def _changed_fields(
        self,
        lead: Lead,
        suggestion: LeadQualitySuggestion,
        *,
        overwrite: bool,
    ) -> list[str]:
        changed_fields: list[str] = []
        can_update_fit = overwrite or lead.company_size_fit in (None, "", CompanySizeFit.UNKNOWN.value)
        can_update_trade = overwrite or lead.trade_type in (None, "", TradeType.UNKNOWN.value)

        if can_update_fit and lead.company_size_fit != suggestion.company_size_fit.value:
            changed_fields.append("company_size_fit")
        if can_update_trade and lead.trade_type != suggestion.trade_type.value:
            changed_fields.append("trade_type")
        if can_update_fit and self._should_update_detail(lead.company_size_fit_explanation, overwrite=overwrite):
            changed_fields.append("company_size_fit_explanation")
        if can_update_fit and self._should_update_metadata(lead.company_size_fit_metadata_json, overwrite=overwrite):
            changed_fields.append("company_size_fit_metadata_json")
        if can_update_trade and self._should_update_detail(lead.trade_type_explanation, overwrite=overwrite):
            changed_fields.append("trade_type_explanation")
        if can_update_trade and self._should_update_metadata(lead.trade_type_metadata_json, overwrite=overwrite):
            changed_fields.append("trade_type_metadata_json")

        if overwrite:
            for field_name, value in [
                ("company_size_fit_explanation", suggestion.company_size_fit_explanation),
                ("company_size_fit_metadata_json", suggestion.company_size_fit_metadata),
                ("trade_type_explanation", suggestion.trade_type_explanation),
                ("trade_type_metadata_json", suggestion.trade_type_metadata),
            ]:
                current_value = getattr(lead, field_name)
                if current_value != value and field_name not in changed_fields:
                    changed_fields.append(field_name)

        if changed_fields:
            changed_fields.append("quality_classified_at")
        return list(dict.fromkeys(changed_fields))

    @staticmethod
    def _should_update_detail(current_value: str | None, *, overwrite: bool) -> bool:
        return overwrite or current_value in (None, "")

    @staticmethod
    def _should_update_metadata(current_value: dict[str, Any] | None, *, overwrite: bool) -> bool:
        return overwrite or current_value in (None, {})

    @staticmethod
    def _apply_suggestion(
        lead: Lead,
        suggestion: LeadQualitySuggestion,
        *,
        changed_fields: list[str],
    ) -> None:
        values = {
            "company_size_fit": suggestion.company_size_fit.value,
            "company_size_fit_explanation": suggestion.company_size_fit_explanation,
            "company_size_fit_metadata_json": suggestion.company_size_fit_metadata,
            "trade_type": suggestion.trade_type.value,
            "trade_type_explanation": suggestion.trade_type_explanation,
            "trade_type_metadata_json": suggestion.trade_type_metadata,
        }
        for field_name, value in values.items():
            if field_name in changed_fields:
                setattr(lead, field_name, value)
        if "quality_classified_at" in changed_fields:
            lead.quality_classified_at = utcnow()

    def _lead_text(self, lead: Lead) -> str:
        values = [
            lead.business_name,
            lead.normalized_business_name,
            lead.category,
            lead.website,
            lead.domain,
            " ".join(lead.tags or []),
            self._related_text(getattr(lead, "market_segment", None)),
            self._related_text(getattr(lead, "market_subsegment", None)),
        ]
        return normalize_text(" ".join(value for value in values if value)) or ""

    @staticmethod
    def _lead_direct_text(lead: Lead) -> str:
        values = [
            lead.business_name,
            lead.normalized_business_name,
            lead.category,
            lead.website,
            lead.domain,
            " ".join(lead.tags or []),
        ]
        return normalize_text(" ".join(value for value in values if value)) or ""

    @staticmethod
    def _related_key(value: object | None) -> str | None:
        key = str(getattr(value, "key", "") or "").strip()
        return key or None

    @staticmethod
    def _related_text(value: object | None) -> str:
        return normalize_text(
            " ".join(
                str(part)
                for part in [
                    getattr(value, "key", None),
                    getattr(value, "name", None),
                    getattr(value, "description", None),
                ]
                if part
            )
        ) or ""

    @staticmethod
    def _first_match(text: str, signals: Iterable[str]) -> str | None:
        haystack = f" {text} "
        return next(
            (
                signal
                for signal in signals
                if (normalized_signal := normalize_text(signal)) and f" {normalized_signal} " in haystack
            ),
            None,
        )

    @staticmethod
    def _direct_contact_count(lead: Lead) -> int:
        return sum(1 for value in [lead.email, lead.phone, lead.whatsapp, lead.website or lead.domain] if value)

    @staticmethod
    def _location_signal_count(lead: Lead) -> int:
        return sum(
            1
            for value in [
                lead.address,
                lead.city and lead.state,
                lead.google_maps_url or lead.google_place_id,
            ]
            if value
        )

    @staticmethod
    def _fit_metadata(
        lead: Lead,
        *,
        signal_type: str,
        matched_signal: str | None,
        direct_contact_count: int,
        location_signal_count: int,
        trade_type: TradeType,
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "matched_signal": matched_signal,
            "signal_type": signal_type,
            "market_segment_id": lead.market_segment_id,
            "market_subsegment_id": lead.market_subsegment_id,
            "direct_contact_count": direct_contact_count,
            "location_signal_count": location_signal_count,
            "trade_type": trade_type.value,
        }

    @staticmethod
    def _trade_result(
        trade_type: TradeType,
        explanation: str,
        signal_type: str,
        matched_signal: str | None = None,
    ) -> tuple[TradeType, str, dict[str, Any]]:
        return (
            trade_type,
            explanation,
            {
                "schema_version": 1,
                "signal_type": signal_type,
                "matched_signal": matched_signal,
            },
        )
