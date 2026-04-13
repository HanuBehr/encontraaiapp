from __future__ import annotations

from datetime import date, datetime
from html import escape

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from app.config import get_settings
from app.db import SessionLocal
from app.enums import LeadSourceType, LeadStatus, TemplateKey
from app.repositories.lead_repository import LeadRepository
from app.schemas.discovery import DiscoveryPreviewResponse, DiscoverySearchRequest, DiscoverySearchResponse
from app.schemas.lead import LeadDetail, LeadListFilters, LeadSummary, LeadUpdateRequest
from app.schemas.outreach import DraftRead, TemplateRead
from app.services.crm import CRMService
from app.services.discovery import DiscoveryService
from app.services.dedupe import DedupeService
from app.services.enrichment import EnrichmentService
from app.services.export_excel import ExcelExportService
from app.services.normalization import normalize_tags
from app.services.outreach import OutreachService

settings = get_settings()

st.set_page_config(page_title="LeadFlow Workspace", layout="wide", initial_sidebar_state="expanded")

LEAD_PAGE_SIZE = 300
WORKFLOW_VIEWS = [
    "Action queue",
    "Ready for outreach",
    "Needs enrichment",
    "Follow-up due",
    "All leads",
]
SORT_OPTIONS = [
    "Recently updated",
    "Highest priority",
    "Follow-up date",
    "Business name",
]
DETAIL_SECTION_REVIEW = "Review & Enrich"
DETAIL_SECTION_DRAFTS = "Drafts"
DETAIL_SECTION_HISTORY = "History & Sources"
DETAIL_SECTION_OPTIONS = [
    DETAIL_SECTION_REVIEW,
    DETAIL_SECTION_DRAFTS,
    DETAIL_SECTION_HISTORY,
]
ACTIVE_STATUSES = {
    LeadStatus.NEW,
    LeadStatus.REVIEWED,
    LeadStatus.APPROVED,
    LeadStatus.CONTACTED,
    LeadStatus.REPLIED,
    LeadStatus.INTERESTED,
}
FOLLOW_UP_STATUSES = {
    LeadStatus.CONTACTED,
    LeadStatus.REPLIED,
    LeadStatus.INTERESTED,
}
ACTION_QUEUE_SCORE_MIN = 70
ACTIVE_STATUS_VALUES = {status.value for status in ACTIVE_STATUSES}
FOLLOW_UP_STATUS_VALUES = {status.value for status in FOLLOW_UP_STATUSES}
UNCONTACTED_STATUS_VALUES = {
    LeadStatus.NEW.value,
    LeadStatus.REVIEWED.value,
    LeadStatus.APPROVED.value,
}
DISCOVERY_LOCATION_MODES = ["City / neighborhood", "Coordinates"]
DISCOVERY_SEARCH_TERM_OPTIONS = [
    "oficina mecânica",
    "auto elétrica",
    "auto center",
    "desmanche",
    "autopeças",
    "assistência técnica",
    "manutenção de computadores",
    "eletrônica",
]
WORKFLOW_VIEW_DESCRIPTIONS = {
    "Action queue": "Best leads to review before first outreach: contactable, high-priority, and not yet contacted.",
    "Ready for outreach": "High-priority leads with email or WhatsApp already stored and no do-not-contact block.",
    "Needs enrichment": "Saved leads that still need a public contact refresh or stronger evidence before outreach.",
    "Follow-up due": "Saved leads with a due or overdue follow-up date.",
    "All leads": "Every saved lead that matches the current filters.",
}
def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        html {
            scrollbar-gutter: stable both-edges;
        }
        :root {
            color-scheme: light;
            --bg: #F7F5FB;
            --bg-secondary: #F2EEF8;
            --surface: #FFFFFF;
            --surface-strong: #FFFFFF;
            --surface-glass: rgba(255, 255, 255, 0.82);
            --border: #E8E2F1;
            --border-strong: #DCD3EA;
            --text: #151320;
            --muted: #9C96AE;
            --subtle: #6D6781;
            --lavender-50: #F3EEFF;
            --lavender-100: #EAE0FF;
            --lavender-200: #DCCBFF;
            --lavender-300: #CDB3FF;
            --lavender-400: #B996FF;
            --lavender-500: #A57BFF;
            --lavender-600: #8F63F2;
            --lavender-700: #7550D8;
            --lavender-800: #5F42B8;
            --accent: #8F63F2;
            --accent-soft: #EAE0FF;
            --accent-border: #DCCBFF;
            --good: #B9D8C4;
            --warn: #E8D4A8;
            --danger: #E7B7B7;
            --info: #CFC4F6;
            --focus: rgba(165, 123, 255, 0.14);
            --focus-border: rgba(143, 99, 242, 0.34);
            --shadow-soft: 0 10px 30px rgba(35, 24, 65, 0.06);
            --shadow: 0 18px 44px rgba(35, 24, 65, 0.08);
        }
        html, body, [data-testid="stAppViewContainer"], .stApp {
            background: transparent;
            color: var(--text);
            font-family: Inter, Geist, "SF Pro Text", "SF Pro Display", system-ui, sans-serif;
            font-feature-settings: "tnum" 1;
        }
        body {
            background: var(--bg);
        }
        header[data-testid="stHeader"] {
            background: transparent;
            height: 0;
        }
        div[data-testid="stToolbar"] { opacity: 0.18; }
        div[data-testid="stDecoration"] {
            display: none;
        }
        .block-container {
            max-width: 1440px;
            padding: 2rem 2rem 3.5rem;
            min-height: calc(100vh - 2.5rem);
        }
        section[data-testid="stSidebar"] {
            background: var(--bg-secondary);
            border-right: 1px solid var(--border);
            box-shadow: inset -1px 0 0 var(--border);
            min-width: 264px !important;
            max-width: 264px !important;
        }
        section[data-testid="stSidebar"] > div {
            background: transparent;
        }
        section[data-testid="stSidebar"] .block-container {
            padding: 1.5rem 1.2rem 1.5rem;
        }
        h1, h2, h3 {
            color: var(--text) !important;
            font-family: Inter, Geist, "SF Pro Display", system-ui, sans-serif;
            letter-spacing: -0.035em;
        }
        h2 {
            font-size: clamp(1.5rem, 2vw, 1.625rem);
            font-weight: 700;
            margin-bottom: 0.4rem;
        }
        h3 {
            font-size: 1.125rem;
            font-weight: 650;
            margin-bottom: 0.45rem;
        }
        p, label, .stMarkdown, div[data-testid="stMarkdownContainer"] p {
            color: var(--subtle);
            line-height: 1.6;
        }
        div[data-testid="stCaptionContainer"] p,
        .stCaption {
            color: var(--muted) !important;
            font-size: 0.86rem;
        }
        hr {
            border-color: var(--border) !important;
            opacity: 0.7;
        }
        details[data-testid="stExpander"] {
            border: 1px solid var(--border);
            border-radius: 20px;
            background: rgba(255, 255, 255, 0.9);
            overflow: hidden;
            box-shadow: 0 1px 2px rgba(35, 24, 65, 0.03);
        }
        div[data-testid="stMetric"] {
            background: #FFFFFF;
            border: 1px solid var(--border);
            border-radius: 24px;
            padding: 1rem 1.05rem;
            box-shadow: 0 1px 2px rgba(35, 24, 65, 0.03);
        }
        div[data-testid="stMetricLabel"] {
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.14em;
            font-size: 0.68rem;
        }
        div[data-testid="stMetricValue"] {
            color: var(--text);
            letter-spacing: -0.04em;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--surface);
            border: 1px solid var(--border) !important;
            border-radius: 24px;
            box-shadow: 0 1px 2px rgba(35, 24, 65, 0.03);
            content-visibility: auto;
            contain-intrinsic-size: 420px;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] > div {
            background: transparent;
        }
        div.stButton > button,
        div[data-testid="stFormSubmitButton"] > button,
        div[data-testid="stDownloadButton"] > button,
        div[data-testid="stLinkButton"] > a {
            min-height: 3rem;
            border-radius: 16px;
            border: 1px solid var(--border);
            background: #FFFFFF;
            color: var(--text) !important;
            font-weight: 650;
            letter-spacing: 0.01em;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9);
            transition: background-color 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
            text-decoration: none !important;
        }
        div.stButton > button:hover,
        div[data-testid="stFormSubmitButton"] > button:hover,
        div[data-testid="stDownloadButton"] > button:hover,
        div[data-testid="stLinkButton"] > a:hover {
            background: var(--lavender-50);
            border-color: var(--accent-border);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.92);
        }
        div.stButton > button:focus,
        div[data-testid="stFormSubmitButton"] > button:focus,
        div[data-testid="stDownloadButton"] > button:focus,
        div[data-testid="stLinkButton"] > a:focus {
            outline: none !important;
            border-color: var(--focus-border) !important;
            box-shadow: 0 0 0 4px var(--focus) !important;
        }
        button[kind="primary"] {
            background: var(--lavender-50) !important;
            color: var(--lavender-700) !important;
            border: 1px solid var(--lavender-200) !important;
            box-shadow: 0 1px 2px rgba(35, 24, 65, 0.03) !important;
        }
        button[kind="secondary"] {
            background: #FFFFFF !important;
        }
        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        div[data-baseweb="textarea"] > div,
        div[data-testid="stDateInput"] > div > div,
        div[data-testid="stNumberInput"] > div > div {
            background: #FFFFFF !important;
            border: 1px solid var(--border) !important;
            border-radius: 16px !important;
            box-shadow: none;
        }
        div[data-baseweb="input"] > div:has(input:focus),
        div[data-baseweb="select"] > div:has(input:focus),
        div[data-baseweb="textarea"] > div:has(textarea:focus),
        div[data-testid="stDateInput"] > div > div:has(input:focus),
        div[data-testid="stNumberInput"] > div > div:has(input:focus) {
            border-color: var(--focus-border) !important;
            box-shadow: 0 0 0 3px var(--focus) !important;
        }
        input, textarea {
            color: var(--text) !important;
        }
        input::placeholder, textarea::placeholder {
            color: var(--muted) !important;
        }
        div[data-baseweb="tag"] {
            background: var(--lavender-50) !important;
            border: 1px solid var(--lavender-200) !important;
            color: var(--lavender-700) !important;
            border-radius: 999px !important;
        }
        div[role="radiogroup"] {
            gap: 0.55rem;
        }
        div[role="radiogroup"] label[data-baseweb="radio"] {
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 0.55rem 0.85rem;
            min-height: 2.8rem;
            transition: border-color 0.18s ease, background-color 0.18s ease, box-shadow 0.18s ease;
        }
        div[role="radiogroup"] label[data-baseweb="radio"] > div:first-child {
            display: none;
        }
        div[role="radiogroup"] label[data-baseweb="radio"] p {
            color: var(--subtle) !important;
            font-weight: 600;
        }
        div[role="radiogroup"] label[data-baseweb="radio"]:hover {
            border-color: var(--accent-border);
            background: var(--lavender-50);
        }
        div[role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) {
            background: var(--lavender-50);
            border-color: var(--accent-border);
        }
        div[role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) p {
            color: var(--lavender-700) !important;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] {
            display: grid;
            gap: 0.6rem;
        }
        section[data-testid="stSidebar"] label[data-baseweb="radio"] {
            padding: 0.68rem 0.82rem;
            border-radius: 16px;
            background: rgba(255, 255, 255, 0.72);
            border-color: transparent;
            box-shadow: none;
        }
        section[data-testid="stSidebar"] label[data-baseweb="radio"]:hover {
            background: #FFFFFF;
            border-color: var(--accent-border);
        }
        section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {
            background: #FFFFFF;
            border-color: var(--accent-border);
            box-shadow: var(--shadow-soft);
        }
        section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) p {
            color: var(--text) !important;
        }
        label[data-baseweb="checkbox"] {
            background: #FFFFFF;
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 0.38rem 0.72rem;
        }
        label[data-baseweb="checkbox"]:has(input:checked) {
            background: var(--lavender-50);
            border-color: var(--accent-border);
        }
        div[data-testid="stDataFrame"],
        div[data-testid="stTable"] {
            background: #FFFFFF;
            border: 1px solid var(--border);
            border-radius: 24px;
            overflow: hidden;
            box-shadow: var(--shadow-soft);
            --gdg-accent-color: rgba(143, 99, 242, 0.82);
            --gdg-accent-fg-color: #FFFFFF;
            --gdg-bg-cell: #FFFFFF;
            --gdg-bg-cell-medium: #FBFAFE;
            --gdg-bg-header: #FAF8FD;
            --gdg-bg-header-has-focus: rgba(165, 123, 255, 0.1);
            --gdg-border-color: #E8E2F1;
            --gdg-horizontal-border-color: #F2EEF8;
            --gdg-text-dark: #151320;
            --gdg-text-medium: #6D6781;
            --gdg-text-header: #6D6781;
            --gdg-selection-color: rgba(165, 123, 255, 0.14);
        }
        div[data-testid="stDataFrame"] > div {
            background: transparent !important;
        }
        div[data-testid="stAlert"] {
            border-radius: 18px;
            border: 1px solid var(--border);
            background: rgba(255, 255, 255, 0.92);
        }
        code, pre {
            border-radius: 16px !important;
            border: 1px solid var(--border) !important;
            background: #F9FAFB !important;
        }
        .app-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            min-height: 72px;
            padding: 0.8rem 1.3rem;
            margin-bottom: 1.35rem;
            border: 1px solid var(--border-strong);
            border-radius: 24px;
            background: #FFFFFF;
            box-shadow: 0 10px 24px rgba(35, 24, 65, 0.04);
        }
        .app-header__left {
            display: flex;
            flex-direction: column;
            gap: 0.18rem;
        }
        .app-header__eyebrow,
        .page-hero__eyebrow,
        .feature-card__eyebrow,
        .sidebar-section-label {
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.75rem;
        }
        .app-header__title {
            color: var(--text);
            font-size: 1.12rem;
            font-weight: 700;
            letter-spacing: -0.03em;
            line-height: 1.1;
            margin: 0;
        }
        .app-header__actions {
            display: inline-flex;
            align-items: center;
            gap: 0.6rem;
        }
        .app-header__pill {
            display: inline-flex;
            align-items: center;
            min-height: 2.2rem;
            padding: 0.45rem 0.75rem;
            border-radius: 999px;
            border: 1px solid var(--border);
            background: #FFFFFF;
            color: var(--subtle);
            font-size: 0.78rem;
            font-weight: 650;
            letter-spacing: 0.01em;
        }
        .app-header__pill--accent {
            background: var(--lavender-50);
            border-color: var(--accent-border);
            color: var(--lavender-700);
        }
        .sidebar-brand {
            position: relative;
            overflow: hidden;
            padding: 0.95rem 0.95rem 1rem;
            margin-bottom: 0.9rem;
            border: 1px solid var(--border-strong);
            border-radius: 24px;
            background: #FFFFFF;
            box-shadow: var(--shadow-soft);
        }
        .sidebar-brand__badge {
            display: inline-flex;
            align-items: center;
            min-height: 1.85rem;
            padding: 0.28rem 0.68rem;
            border-radius: 999px;
            background: var(--lavender-50);
            border: 1px solid var(--lavender-200);
            color: var(--lavender-700);
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.75rem;
            font-weight: 650;
        }
        .sidebar-brand__title {
            color: var(--text);
            font-size: 1.08rem;
            font-weight: 700;
            letter-spacing: -0.04em;
            margin: 0.32rem 0 0.22rem;
        }
        .sidebar-brand__copy {
            color: var(--subtle);
            font-size: 0.82rem;
            line-height: 1.45;
        }
        .sidebar-section-label {
            margin: 0.8rem 0 0.45rem;
        }
        .section-heading {
            margin: 0.25rem 0 0.95rem;
        }
        .section-heading__title {
            color: var(--text);
            font-size: clamp(1.5rem, 2vw, 1.625rem);
            font-weight: 700;
            letter-spacing: -0.04em;
            line-height: 1.08;
            margin: 0;
        }
        .section-heading__summary {
            color: var(--subtle);
            font-size: 0.94rem;
            line-height: 1.55;
            margin-top: 0.32rem;
        }
        .page-hero {
            position: relative;
            overflow: hidden;
            padding: 1.5rem 1.5rem 1.4rem;
            margin-bottom: 0.9rem;
            border: 1px solid var(--border-strong);
            border-radius: 24px;
            background: #FFFFFF;
            box-shadow: var(--shadow-soft);
        }
        .page-hero__title {
            color: var(--text);
            font-size: clamp(2.2rem, 3vw, 2.375rem);
            line-height: 1.03;
            letter-spacing: -0.05em;
            margin: 0.4rem 0 0.55rem;
            font-weight: 750;
        }
        .page-hero__summary {
            max-width: 72ch;
            color: var(--subtle);
            line-height: 1.7;
            font-size: 0.94rem;
        }
        .hero-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.85rem;
            margin-top: 1rem;
        }
        .hero-grid__card {
            padding: 1rem;
            border: 1px solid var(--border);
            border-radius: 18px;
            background: #FCFBFE;
        }
        .hero-grid__label {
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.14em;
            font-size: 0.67rem;
            margin-bottom: 0.4rem;
        }
        .hero-grid__value {
            color: var(--text);
            line-height: 1.45;
            font-size: 0.92rem;
        }
        .kv-list {
            display: grid;
            gap: 0.65rem;
        }
        .kv-row {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 1rem;
            padding: 0.8rem 0.9rem;
            border: 1px solid var(--border);
            border-radius: 16px;
            background: #FCFBFE;
        }
        .kv-label {
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.68rem;
            line-height: 1.4;
        }
        .kv-value {
            color: var(--text);
            font-size: 0.92rem;
            line-height: 1.45;
            text-align: right;
        }
        .operator-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin: 0.2rem 0 1rem;
        }
        .operator-badge {
            display: inline-flex;
            align-items: center;
            min-height: 2rem;
            padding: 0.42rem 0.8rem;
            border-radius: 999px;
            border: 1px solid var(--border);
            background: #FFFFFF;
            color: var(--text);
            font-size: 0.78rem;
            font-weight: 650;
            letter-spacing: 0.01em;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9);
        }
        .operator-badge--neutral {
            color: var(--subtle);
        }
        .operator-badge--accent {
            background: var(--lavender-50);
            border-color: var(--accent-border);
            color: var(--lavender-700);
        }
        .operator-badge--good {
            background: rgba(185, 216, 196, 0.42);
            border-color: rgba(185, 216, 196, 0.9);
            color: var(--text);
        }
        .operator-badge--warn {
            background: rgba(232, 212, 168, 0.44);
            border-color: rgba(232, 212, 168, 0.94);
            color: var(--text);
        }
        .operator-badge--danger {
            background: rgba(231, 183, 183, 0.46);
            border-color: rgba(231, 183, 183, 0.94);
            color: var(--text);
        }
        .operator-badge--info {
            background: var(--lavender-100);
            border-color: var(--lavender-200);
            color: var(--lavender-700);
        }
        .notice-card,
        .feature-card {
            position: relative;
            overflow: hidden;
            border: 1px solid var(--border);
            border-radius: 20px;
            background: #FFFFFF;
            box-shadow: var(--shadow-soft);
        }
        .notice-card {
            padding: 0.95rem 1rem;
            margin: 0.2rem 0 0.95rem;
        }
        .notice-card__title {
            color: var(--text);
            font-size: 0.94rem;
            font-weight: 700;
            margin-bottom: 0.28rem;
        }
        .notice-card__body {
            color: var(--subtle);
            font-size: 0.9rem;
            line-height: 1.6;
        }
        .notice-card--good {
            border-color: rgba(185, 216, 196, 0.92);
            background: rgba(185, 216, 196, 0.28);
        }
        .notice-card--warn {
            border-color: rgba(232, 212, 168, 0.94);
            background: rgba(232, 212, 168, 0.28);
        }
        .notice-card--danger {
            border-color: rgba(231, 183, 183, 0.94);
            background: rgba(231, 183, 183, 0.28);
        }
        .notice-card--info {
            border-color: var(--lavender-200);
            background: rgba(207, 196, 246, 0.32);
        }
        .feature-card {
            padding: 1rem 1rem 1.05rem;
        }
        .feature-card__title {
            color: var(--text);
            font-size: 1.125rem;
            font-weight: 650;
            letter-spacing: -0.02em;
            margin: 0.38rem 0 0.35rem;
        }
        .feature-card__copy,
        .feature-card__meta {
            color: var(--subtle);
            font-size: 0.94rem;
            line-height: 1.6;
        }
        .feature-card__meta {
            color: var(--muted);
            margin-top: 0.5rem;
        }
        .feature-card--good {
            border-color: rgba(185, 216, 196, 0.92);
        }
        .feature-card--warn {
            border-color: rgba(232, 212, 168, 0.94);
        }
        .feature-card--danger {
            border-color: rgba(231, 183, 183, 0.94);
        }
        .feature-card--info {
            border-color: var(--lavender-200);
        }
        .step-card__items {
            display: grid;
            gap: 0.75rem;
            margin-top: 0.7rem;
        }
        .step-card__item {
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 0.75rem;
            align-items: start;
        }
        .step-card__index {
            display: inline-flex;
            justify-content: center;
            align-items: center;
            width: 1.8rem;
            height: 1.8rem;
            border-radius: 999px;
            border: 1px solid var(--lavender-200);
            background: var(--lavender-50);
            color: var(--lavender-700);
            font-size: 0.76rem;
            font-weight: 700;
        }
        .step-card__text {
            color: var(--subtle);
            font-size: 0.9rem;
            line-height: 1.55;
            padding-top: 0.1rem;
        }
        .guide-mini {
            padding: 0.9rem 0.92rem 0.95rem;
            border: 1px solid var(--border-strong);
            border-radius: 24px;
            background: #FFFFFF;
            box-shadow: var(--shadow-soft);
        }
        .guide-mini__title {
            color: var(--text);
            font-size: 0.92rem;
            font-weight: 680;
            margin: 0.32rem 0 0.55rem;
            letter-spacing: -0.02em;
        }
        .guide-mini__row {
            display: grid;
            grid-template-columns: 4.3rem 1fr;
            gap: 0.6rem;
            padding: 0.38rem 0;
            border-top: 1px solid var(--border);
        }
        .guide-mini__row:first-of-type {
            border-top: none;
        }
        .guide-mini__label {
            color: var(--lavender-700);
            font-size: 0.77rem;
            font-weight: 650;
        }
        .guide-mini__copy {
            color: var(--muted);
            font-size: 0.78rem;
            line-height: 1.45;
        }
        .overview-hero {
            position: relative;
            overflow: hidden;
            display: grid;
            grid-template-columns: minmax(0, 1.45fr) minmax(260px, 0.75fr);
            gap: 1rem;
            padding: 2rem;
            margin-bottom: 1.1rem;
            border: 1px solid var(--border-strong);
            border-radius: 24px;
            background: #FFFFFF;
            box-shadow: var(--shadow-soft);
        }
        .overview-hero__title {
            color: var(--text);
            font-size: clamp(3rem, 4vw, 3.25rem);
            line-height: 1.01;
            letter-spacing: -0.07em;
            font-weight: 800;
            margin: 0.35rem 0 0.78rem;
        }
        .overview-hero__summary {
            max-width: 60ch;
            color: var(--subtle);
            font-size: 0.94rem;
            line-height: 1.6;
            margin-bottom: 0.55rem;
        }
        .overview-hero__aside {
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            gap: 0.8rem;
            padding: 1.15rem 1.15rem 1.05rem;
            border: 1px solid var(--lavender-200);
            border-radius: 24px;
            background: var(--lavender-50);
        }
        .overview-hero__aside-label {
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.14em;
            font-size: 0.67rem;
        }
        .overview-hero__aside-value {
            color: var(--lavender-700);
            font-size: 1.2rem;
            font-weight: 720;
            letter-spacing: -0.04em;
            margin: 0.2rem 0 0.28rem;
        }
        .overview-hero__aside-copy {
            color: var(--subtle);
            font-size: 0.85rem;
            line-height: 1.55;
        }
        .workflow-card {
            height: 100%;
            padding: 1.15rem 1.1rem 1.05rem;
            border: 1px solid var(--border);
            border-radius: 24px;
            background: #FFFFFF;
            box-shadow: var(--shadow-soft);
        }
        .workflow-card__step {
            color: var(--lavender-700);
            text-transform: uppercase;
            letter-spacing: 0.14em;
            font-size: 0.65rem;
            margin-bottom: 0.55rem;
        }
        .workflow-card__title {
            color: var(--text);
            font-size: 1.125rem;
            font-weight: 650;
            letter-spacing: -0.02em;
            margin-bottom: 0.35rem;
        }
        .workflow-card__copy {
            color: var(--subtle);
            font-size: 0.94rem;
            line-height: 1.55;
        }
        .status-card {
            height: 100%;
            padding: 1.15rem 1.1rem 1.05rem;
            border: 1px solid var(--border);
            border-radius: 24px;
            background: #FFFFFF;
            box-shadow: var(--shadow-soft);
        }
        .status-card__header {
            display: flex;
            justify-content: space-between;
            gap: 0.75rem;
            align-items: center;
            margin-bottom: 0.85rem;
        }
        .status-card__title {
            color: var(--text);
            font-size: 1.125rem;
            font-weight: 650;
            letter-spacing: -0.02em;
        }
        .status-card__copy {
            color: var(--subtle);
            font-size: 0.94rem;
            line-height: 1.52;
            margin-bottom: 0.8rem;
        }
        .status-card__meta {
            color: var(--muted);
            font-size: 0.78rem;
            line-height: 1.45;
        }
        .metric-band {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.85rem;
            margin: 0.2rem 0 1.35rem;
        }
        .metric-card {
            padding: 1.2rem 1.15rem 1.12rem;
            border: 1px solid var(--border);
            border-radius: 24px;
            background: #FFFFFF;
            box-shadow: var(--shadow-soft);
        }
        .metric-card__label {
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.75rem;
            margin-bottom: 0.7rem;
        }
        .metric-card__value {
            color: var(--text);
            font-size: clamp(1.55rem, 2vw, 2rem);
            font-weight: 780;
            line-height: 1;
            letter-spacing: -0.05em;
            margin-bottom: 0.4rem;
        }
        .metric-card__meta {
            color: var(--subtle);
            font-size: 0.84rem;
            line-height: 1.45;
        }
        .operator-muted {
            color: var(--muted);
            font-size: 0.9rem;
        }
        @media (max-width: 900px) {
            .hero-grid {
                grid-template-columns: 1fr;
            }
            .page-hero,
            .app-header {
                padding: 1.15rem 1rem 1.1rem;
            }
            .overview-hero {
                grid-template-columns: 1fr;
                padding: 1.2rem 1rem 1.05rem;
            }
            .metric-band {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .block-container {
                padding: 1.2rem 1rem 2.4rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _init_session_state() -> None:
    defaults = {
        "data_revision": 0,
        "page": "Overview",
        "page_nav": "Overview",
        "selected_lead_id": None,
        "lead_detail_selected_id": None,
        "lead_queue_ids": [],
        "lead_queue_lookup": {},
        "lead_queue_label": "All loaded leads",
        "duplicate_preview_rows": None,
        "dedupe_results": None,
        "export_filename": None,
        "export_payload": None,
        "lead_workflow_view": "Action queue",
        "lead_search_term": "",
        "lead_sort_by": "Recently updated",
        "lead_queue_selected_id": None,
        "lead_quick_hide_duplicates": True,
        "lead_quick_require_contact": True,
        "lead_quick_high_score": True,
        "lead_quick_uncontacted": True,
        "lead_filter_city": "All",
        "lead_filter_status": "All",
        "lead_filter_category": "All",
        "lead_filter_source_type": "All",
        "lead_filter_score_range": (0, 100),
        "leads_has_email": "Any",
        "leads_has_whatsapp": "Any",
        "leads_do_not_contact": "Any",
        "lead_detail_section": DETAIL_SECTION_REVIEW,
        "discovery_location_mode": DISCOVERY_LOCATION_MODES[0],
        "discovery_city": "",
        "discovery_neighborhood": "",
        "discovery_postal_code": "",
        "discovery_location_label": "",
        "discovery_latitude": "",
        "discovery_longitude": "",
        "discovery_radius_m": 3000,
        "discovery_max_results_per_term": 10,
        "discovery_search_terms": [],
        "discovery_custom_terms": "",
        "discovery_preview_payload": None,
        "discovery_preview_request": None,
        "discovery_import_payload": None,
        "ui_flash": None,
        "queue_action_context": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    legacy_detail_sections = {
        "CRM & Enrichment": DETAIL_SECTION_REVIEW,
        "Evidence & Provenance": DETAIL_SECTION_HISTORY,
    }
    current_detail_section = st.session_state.get("lead_detail_section")
    if current_detail_section in legacy_detail_sections:
        st.session_state["lead_detail_section"] = legacy_detail_sections[current_detail_section]


def _normalize_enumish(value: object | None) -> str | None:
    normalized = getattr(value, "value", value)
    if normalized is None:
        return None
    return str(normalized)


def _humanize(value: object | None) -> str:
    normalized = _normalize_enumish(value)
    if normalized in (None, ""):
        return "-"
    return normalized.replace("_", " ").strip().title()


def _status_value(value: object | None) -> str | None:
    return _normalize_enumish(value)


def _status_in(value: object | None, allowed_values: set[str]) -> bool:
    normalized = _status_value(value)
    return normalized in allowed_values if normalized else False


def _option_index(options: list[str], value: str | None) -> int:
    if value in options:
        return options.index(value)
    return 0


def _resolve_lead_selection(available_ids: list[int], *candidates: object | None) -> int | None:
    for candidate in candidates:
        if isinstance(candidate, int) and candidate in available_ids:
            return candidate
    return available_ids[0] if available_ids else None


def _safe_text(value: object | None, *, fallback: str = "-") -> str:
    if value in (None, "", [], {}):
        return fallback
    return str(value)


def _render_key_value_grid(items: list[tuple[str, object | None]]) -> None:
    rows = "".join(
        (
            '<div class="kv-row">'
            f'<div class="kv-label">{escape(label)}</div>'
            f'<div class="kv-value">{escape(_safe_text(value))}</div>'
            "</div>"
        )
        for label, value in items
    )
    st.markdown(f'<div class="kv-list">{rows}</div>', unsafe_allow_html=True)


def _format_date(value: date | None) -> str:
    return value.strftime("%Y-%m-%d") if value else "-"


def _format_datetime(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else "-"


def _badge(text: str, tone: str = "neutral") -> str:
    return f'<span class="operator-badge operator-badge--{tone}">{escape(text)}</span>'


def _render_badges(items: list[tuple[str, str]]) -> None:
    if not items:
        return
    st.markdown(
        f'<div class="operator-badges">{"".join(_badge(text, tone) for text, tone in items)}</div>',
        unsafe_allow_html=True,
    )


def _render_notice(message: str, *, tone: str = "info", title: str | None = None) -> None:
    title_html = f'<div class="notice-card__title">{escape(title)}</div>' if title else ""
    st.markdown(
        (
            f'<div class="notice-card notice-card--{tone}">'
            f"{title_html}"
            f'<div class="notice-card__body">{escape(message)}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _render_feature_card(
    title: str,
    copy: str,
    *,
    tone: str = "neutral",
    eyebrow: str | None = None,
    meta: str | None = None,
) -> None:
    eyebrow_html = f'<div class="feature-card__eyebrow">{escape(eyebrow)}</div>' if eyebrow else ""
    meta_html = f'<div class="feature-card__meta">{escape(meta)}</div>' if meta else ""
    st.markdown(
        (
            f'<div class="feature-card feature-card--{tone}">'
            f"{eyebrow_html}"
            f'<div class="feature-card__title">{escape(title)}</div>'
            f'<div class="feature-card__copy">{escape(copy)}</div>'
            f"{meta_html}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _render_workflow_card(step: str, title: str, copy: str) -> None:
    st.markdown(
        (
            '<div class="workflow-card">'
            f'<div class="workflow-card__step">{escape(step)}</div>'
            f'<div class="workflow-card__title">{escape(title)}</div>'
            f'<div class="workflow-card__copy">{escape(copy)}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _render_status_card(title: str, state: str, copy: str, *, tone: str = "neutral", meta: str | None = None) -> None:
    meta_html = f'<div class="status-card__meta">{escape(meta)}</div>' if meta else ""
    st.markdown(
        (
            '<div class="status-card">'
            '<div class="status-card__header">'
            f'<div class="status-card__title">{escape(title)}</div>'
            f'{_badge(state, tone)}'
            "</div>"
            f'<div class="status-card__copy">{escape(copy)}</div>'
            f"{meta_html}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _render_metric_band(items: list[tuple[str, str, str]]) -> None:
    cards = "".join(
        (
            '<div class="metric-card">'
            f'<div class="metric-card__label">{escape(label)}</div>'
            f'<div class="metric-card__value">{escape(value)}</div>'
            f'<div class="metric-card__meta">{escape(meta)}</div>'
            "</div>"
        )
        for label, value, meta in items
    )
    st.markdown(f'<div class="metric-band">{cards}</div>', unsafe_allow_html=True)


def _render_section_intro(title: str, summary: str) -> None:
    st.markdown(
        f"""
        <div class="section-heading">
            <div class="section-heading__title">{escape(title)}</div>
            <div class="section-heading__summary">{escape(summary)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_step_card(title: str, steps: list[str], *, eyebrow: str | None = None, tone: str = "neutral") -> None:
    eyebrow_html = f'<div class="feature-card__eyebrow">{escape(eyebrow)}</div>' if eyebrow else ""
    steps_html = "".join(
        (
            '<div class="step-card__item">'
            f'<div class="step-card__index">{index}</div>'
            f'<div class="step-card__text">{escape(step)}</div>'
            "</div>"
        )
        for index, step in enumerate(steps, start=1)
    )
    st.markdown(
        (
            f'<div class="feature-card feature-card--{tone}">'
            f"{eyebrow_html}"
            f'<div class="feature-card__title">{escape(title)}</div>'
            f'<div class="step-card__items">{steps_html}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _boolean_state(value: bool, *, positive: str = "Ready", negative: str = "Blocked") -> tuple[str, str]:
    return (positive if value else negative, "good" if value else "danger")


def _format_database_label(database_url: str) -> str:
    if database_url.startswith("sqlite:///./"):
        return f"SQLite at {database_url.removeprefix('sqlite:///./')}"
    if database_url.startswith("sqlite:///"):
        return f"SQLite at {database_url.removeprefix('sqlite:///')}"
    return database_url


def _format_path_label(value: object | None) -> str:
    return _safe_text(value).replace("\\", "/")


def _render_overview_hero(*, next_step: str, next_copy: str) -> None:
    workflow_badges = "".join(
        _badge(text, tone)
        for text, tone in [
            ("Discovery", "accent"),
            ("Leads Review", "accent"),
            ("Lead Workspace", "accent"),
            ("Export", "accent"),
        ]
    )
    st.markdown(
        f"""
        <div class="overview-hero">
            <div>
                <div class="page-hero__eyebrow">Lead operations workspace</div>
                <div class="overview-hero__title">Review, qualify, and move leads with clarity.</div>
                <div class="overview-hero__summary">
                    Run discovery, review the queue, work one business at a time, and export without losing context.
                </div>
                <div class="operator-badges">{workflow_badges}</div>
            </div>
            <div class="overview-hero__aside">
                <div>
                    <div class="overview-hero__aside-label">Go next</div>
                    <div class="overview-hero__aside-value">{escape(next_step)}</div>
                    <div class="overview-hero__aside-copy">{escape(next_copy)}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def _render_operator_guide(container, *, expanded: bool = False) -> None:
    with container:
        st.markdown(
            """
            <div class="guide-mini">
                <div class="feature-card__eyebrow">Operator guide</div>
                <div class="guide-mini__title">Stay in a clean working rhythm.</div>
                <div class="guide-mini__row">
                    <div class="guide-mini__label">Discover</div>
                    <div class="guide-mini__copy">Find businesses and save the right matches.</div>
                </div>
                <div class="guide-mini__row">
                    <div class="guide-mini__label">Review</div>
                    <div class="guide-mini__copy">Triage the queue and enrich what matters.</div>
                </div>
                <div class="guide-mini__row">
                    <div class="guide-mini__label">Work</div>
                    <div class="guide-mini__copy">Open one lead, draft outreach, then export.</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_sidebar_brand() -> None:
    st.sidebar.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-brand__badge">LeadFlow</div>
            <div class="sidebar-brand__title">LeadFlow Workspace</div>
            <div class="sidebar-brand__copy">
                Discovery, review, and lead work in one shared workspace.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_app_header(page: str) -> None:
    st.markdown(
        f"""
        <div class="app-header">
            <div class="app-header__left">
                <div class="app-header__eyebrow">LeadFlow Workspace</div>
                <div class="app-header__title">{escape(page)}</div>
            </div>
            <div class="app-header__actions">
                <div class="app-header__pill">{escape(_humanize(settings.app_env))}</div>
                <div class="app-header__pill app-header__pill--accent">Shared workspace</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_page_intro(eyebrow: str, title: str, summary: str) -> None:
    st.markdown(
        f"""
        <div class="page-hero">
            <div class="page-hero__eyebrow">{escape(eyebrow)}</div>
            <div class="page-hero__title">{escape(title)}</div>
            <div class="page-hero__summary">{escape(summary)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _set_flash(page: str, message: str, *, tone: str = "success") -> None:
    st.session_state["ui_flash"] = {"page": page, "message": message, "tone": tone}


def _render_flash(page: str) -> None:
    payload = st.session_state.get("ui_flash")
    if not payload or payload.get("page") != page:
        return
    st.session_state["ui_flash"] = None
    tone = str(payload.get("tone") or "info")
    message = str(payload.get("message") or "")
    _render_notice(message, tone=tone, title="Status update")


def _tri_state_filter(label: str, key: str) -> bool | None:
    value = st.selectbox(label, ["Any", "Yes", "No"], index=0, key=key)
    if value == "Yes":
        return True
    if value == "No":
        return False
    return None


def _run_read(fn):
    db = SessionLocal()
    try:
        return fn(db)
    finally:
        db.close()


def _run_write(fn):
    db = SessionLocal()
    try:
        result = fn(db)
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _data_revision() -> int:
    return int(st.session_state.get("data_revision", 0))


def _bump_data_revision() -> None:
    st.session_state["data_revision"] = _data_revision() + 1


def _table_height(row_count: int, *, max_height: int = 560, row_height: int = 35) -> int:
    visible_rows = max(1, min(row_count, 12))
    return min(max_height, 46 + visible_rows * row_height)


@st.cache_data(show_spinner=False, ttl=120)
def _list_distinct_values_cached(revision: int) -> tuple[list[str], list[str]]:
    del revision

    def _reader(db):
        repo = LeadRepository(db)
        return repo.list_distinct_cities(), repo.list_distinct_categories()

    return _run_read(_reader)


def _list_distinct_values() -> tuple[list[str], list[str]]:
    return _list_distinct_values_cached(_data_revision())


@st.cache_data(show_spinner=False, ttl=120)
def _fetch_leads_cached(filters_payload: str, revision: int) -> tuple[int, list[dict]]:
    del revision
    filters = LeadListFilters.model_validate_json(filters_payload)

    def _reader(db):
        repo = LeadRepository(db)
        leads, total = repo.list_leads(filters)
        return total, [LeadSummary.model_validate(lead).model_dump(mode="json") for lead in leads]

    return _run_read(_reader)


def _fetch_leads(filters: LeadListFilters) -> tuple[int, list[LeadSummary]]:
    total, payloads = _fetch_leads_cached(filters.model_dump_json(), _data_revision())
    return total, [LeadSummary.model_validate(payload) for payload in payloads]


@st.cache_data(show_spinner=False, ttl=120)
def _fetch_overview_snapshot_cached(revision: int) -> tuple[dict[str, int], list[dict]]:
    del revision

    def _reader(db):
        repo = LeadRepository(db)
        metrics, recent_leads = repo.get_overview_snapshot(recent_limit=10)
        return metrics, [LeadSummary.model_validate(lead).model_dump(mode="json") for lead in recent_leads]

    return _run_read(_reader)


def _fetch_overview_snapshot() -> tuple[dict[str, int], list[LeadSummary]]:
    metrics, payloads = _fetch_overview_snapshot_cached(_data_revision())
    return metrics, [LeadSummary.model_validate(payload) for payload in payloads]


@st.cache_data(show_spinner=False, ttl=120)
def _fetch_lead_detail_cached(lead_id: int, revision: int) -> dict | None:
    del revision

    def _reader(db):
        repo = LeadRepository(db)
        lead = repo.get_detail(lead_id)
        return LeadDetail.model_validate(lead).model_dump(mode="json") if lead else None

    return _run_read(_reader)


def _fetch_lead_detail(lead_id: int) -> LeadDetail | None:
    payload = _fetch_lead_detail_cached(lead_id, _data_revision())
    return LeadDetail.model_validate(payload) if payload else None


def _update_lead(lead_id: int, payload: LeadUpdateRequest) -> LeadDetail:
    def _writer(db):
        service = CRMService(db)
        lead = service.update_lead(lead_id, payload, actor="streamlit")
        return LeadDetail.model_validate(lead)

    result = _run_write(_writer)
    _bump_data_revision()
    return result


def _enrich_lead(lead_id: int):
    def _writer(db):
        service = EnrichmentService(db, settings)
        return service.enrich_lead(lead_id, actor="streamlit")

    result = _run_write(_writer)
    _bump_data_revision()
    return result


def _enrich_batch(lead_ids: list[int]):
    def _writer(db):
        service = EnrichmentService(db, settings)
        return service.enrich_batch(lead_ids, actor="streamlit")

    result = _run_write(_writer)
    _bump_data_revision()
    return result


def _preview_duplicates(lead_ids: list[int]):
    def _reader(db):
        service = DedupeService(db)
        return service.preview_duplicates(lead_ids=lead_ids)

    return _run_read(_reader)


def _run_dedupe(lead_ids: list[int]):
    def _writer(db):
        service = DedupeService(db)
        return service.dedupe_batch(lead_ids=lead_ids, actor="streamlit")

    result = _run_write(_writer)
    _bump_data_revision()
    return result


@st.cache_data(show_spinner=False, ttl=120)
def _list_templates_cached(revision: int) -> list[dict]:
    del revision

    def _reader(db):
        service = OutreachService(db)
        return [TemplateRead.model_validate(template).model_dump(mode="json") for template in service.list_templates()]

    return _run_read(_reader)


def _list_templates():
    return [TemplateRead.model_validate(payload) for payload in _list_templates_cached(_data_revision())]


def _preview_draft(lead_id: int, template_key: TemplateKey):
    def _reader(db):
        service = OutreachService(db)
        return service.preview_draft(lead_id, template_key)

    return _run_read(_reader)


def _generate_draft(lead_id: int, template_key: TemplateKey):
    def _writer(db):
        service = OutreachService(db)
        return service.generate_draft(lead_id, template_key, actor="streamlit")

    result = _run_write(_writer)
    _bump_data_revision()
    return result


@st.cache_data(show_spinner=False, ttl=120)
def _list_drafts_cached(lead_id: int, revision: int) -> list[dict]:
    del revision

    def _reader(db):
        service = OutreachService(db)
        return [DraftRead.model_validate(draft).model_dump(mode="json") for draft in service.list_drafts_for_lead(lead_id)]

    return _run_read(_reader)


def _list_drafts(lead_id: int):
    return [DraftRead.model_validate(payload) for payload in _list_drafts_cached(lead_id, _data_revision())]


def _export_excel(filters: LeadListFilters):
    def _reader(db):
        service = ExcelExportService(db)
        return service.build_workbook(filters)

    return _run_read(_reader)


def _preview_discovery(request: DiscoverySearchRequest) -> DiscoveryPreviewResponse:
    def _reader(db):
        service = DiscoveryService(db, settings)
        return service.preview(request)

    return _run_read(_reader)


def _ingest_discovery(
    request: DiscoverySearchRequest,
    preview: DiscoveryPreviewResponse,
) -> DiscoverySearchResponse:
    def _writer(db):
        service = DiscoveryService(db, settings)
        return service.ingest_preview(request, preview)

    result = _run_write(_writer)
    _bump_data_revision()
    return result


@st.cache_data(show_spinner=False, ttl=120)
def _list_raw_records_cached(lead_id: int, revision: int) -> list[dict]:
    del revision

    def _reader(db):
        repo = LeadRepository(db)
        return [
            {
                "id": record.id,
                "import_batch_id": record.import_batch_id,
                "provider": record.provider,
                "provider_record_id": record.provider_record_id,
                "search_term": record.search_term,
                "search_input": record.search_input,
                "radius_m": record.radius_m,
                "source_url": record.source_url,
                "discovered_at": record.discovered_at,
                "payload_json": record.payload_json,
            }
            for record in repo.list_raw_records_for_lead(lead_id)
        ]

    return _run_read(_reader)


def _list_raw_records(lead_id: int) -> list[dict]:
    return _list_raw_records_cached(lead_id, _data_revision())


def _parse_discovery_terms(selected_terms: list[str], custom_terms_text: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    raw_terms = [*selected_terms, *custom_terms_text.replace("\n", ",").split(",")]
    for raw_term in raw_terms:
        term = raw_term.strip()
        normalized = term.lower()
        if not term or normalized in seen:
            continue
        seen.add(normalized)
        terms.append(term)
    return terms


def _build_discovery_location_query(city: str, neighborhood: str, postal_code: str) -> str:
    parts = [part.strip() for part in [neighborhood, city, postal_code] if part and part.strip()]
    return ", ".join(parts)


def _clear_discovery_results() -> None:
    st.session_state["discovery_preview_payload"] = None
    st.session_state["discovery_preview_request"] = None
    st.session_state["discovery_import_payload"] = None


def _has_direct_channel(lead: LeadSummary | LeadDetail) -> bool:
    return bool(lead.email or lead.whatsapp)


def _has_any_contact(lead: LeadSummary | LeadDetail) -> bool:
    return bool(lead.email or lead.whatsapp or lead.phone)


def _is_follow_up_due(lead: LeadSummary | LeadDetail) -> bool:
    return bool(lead.follow_up_date and lead.follow_up_date <= date.today())


def _is_uncontacted(lead: LeadSummary | LeadDetail) -> bool:
    return _status_in(lead.status, UNCONTACTED_STATUS_VALUES) and lead.last_contacted_at is None


def _contact_summary(lead: LeadSummary | LeadDetail) -> str:
    channels: list[str] = []
    if lead.email:
        channels.append("Email")
    if lead.whatsapp:
        channels.append("WhatsApp")
    elif lead.phone:
        channels.append("Phone")
    return " + ".join(channels) if channels else "No direct channel"


def _lead_option_label(lead: LeadSummary | LeadDetail) -> str:
    return (
        f"{lead.business_name} | {_safe_text(lead.city)} | "
        f"{_humanize(lead.status)} | Priority {lead.lead_score}"
    )


def _lead_next_step(lead: LeadSummary | LeadDetail) -> str:
    lead_status = _status_value(lead.status)
    if lead.do_not_contact:
        return "Do not contact is active. Keep outreach blocked and preserve the reason in notes."
    if lead_status == LeadStatus.NEW.value:
        return "Review fit, confirm the public evidence, and update the pipeline status."
    if not lead.last_enriched_at:
        return "Find more public contact info before outreach."
    if _is_follow_up_due(lead):
        return "A follow-up is due. Review the latest notes and prepare the next outreach draft."
    if _has_direct_channel(lead):
        return "A direct contact channel is available. Review the details and prepare the draft."
    if _has_any_contact(lead):
        return "A phone contact is available. Check whether a public contact refresh can find email or WhatsApp before drafting."
    return "Review the lead and capture the next operator step in notes."


def _render_lead_workspace_header(
    lead: LeadDetail,
    *,
    queue_label: str,
    queue_position: int,
    queue_total: int,
) -> None:
    subtitle_parts = [
        _safe_text(lead.category),
        f"{_safe_text(lead.city)} / {_safe_text(lead.state)}",
    ]
    meta_cards = [
        ("Queue context", f"{queue_label} | {queue_position} of {queue_total}"),
        ("Best contact path", _contact_summary(lead)),
        ("Next operator step", _lead_next_step(lead)),
    ]
    meta_html = "".join(
        (
            '<div class="hero-grid__card">'
            f'<div class="hero-grid__label">{escape(label)}</div>'
            f'<div class="hero-grid__value">{escape(value)}</div>'
            "</div>"
        )
        for label, value in meta_cards
    )
    st.markdown(
        f"""
        <div class="page-hero">
            <div class="page-hero__eyebrow">Lead workspace</div>
            <div class="page-hero__title">{escape(lead.business_name)}</div>
            <div class="page-hero__summary">{escape(" | ".join(subtitle_parts))}</div>
            <div class="hero-grid">{meta_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _apply_workflow_view(leads: list[LeadSummary], workflow_view: str) -> list[LeadSummary]:
    if workflow_view == "Action queue":
        return [
            lead
            for lead in leads
            if _status_in(lead.status, UNCONTACTED_STATUS_VALUES)
            and not lead.do_not_contact
            and _has_any_contact(lead)
            and lead.lead_score >= ACTION_QUEUE_SCORE_MIN
        ]
    if workflow_view == "Ready for outreach":
        return [
            lead
            for lead in leads
            if _status_in(lead.status, ACTIVE_STATUS_VALUES)
            and not lead.do_not_contact
            and _has_direct_channel(lead)
            and lead.lead_score >= ACTION_QUEUE_SCORE_MIN
        ]
    if workflow_view == "Needs enrichment":
        return [
            lead
            for lead in leads
            if _status_in(lead.status, ACTIVE_STATUS_VALUES)
            and not lead.do_not_contact
            and lead.last_enriched_at is None
        ]
    if workflow_view == "Follow-up due":
        return [
            lead
            for lead in leads
            if _status_in(lead.status, FOLLOW_UP_STATUS_VALUES)
            and not lead.do_not_contact
            and _is_follow_up_due(lead)
        ]
    return leads


def _matches_search(lead: LeadSummary, search_term: str) -> bool:
    if not search_term:
        return True
    search_value = search_term.lower().strip()
    haystack = " ".join(
        [
            lead.business_name,
            lead.category or "",
            lead.neighborhood or "",
            lead.city or "",
            lead.state or "",
            lead.website or "",
            lead.email or "",
            lead.phone or "",
            lead.whatsapp or "",
            _normalize_enumish(lead.status) or "",
            _normalize_enumish(lead.lead_source_type) or "",
        ]
    ).lower()
    return search_value in haystack


def _sort_leads(leads: list[LeadSummary], sort_by: str) -> list[LeadSummary]:
    if sort_by == "Highest priority":
        return sorted(
            leads,
            key=lambda lead: (-lead.lead_score, -(lead.updated_at.timestamp()), -lead.id),
        )
    if sort_by == "Follow-up date":
        return sorted(
            leads,
            key=lambda lead: (
                lead.follow_up_date is None,
                lead.follow_up_date or date.max,
                -lead.lead_score,
                lead.business_name.lower(),
            ),
        )
    if sort_by == "Business name":
        return sorted(leads, key=lambda lead: (lead.business_name.lower(), lead.id))
    return sorted(leads, key=lambda lead: (lead.updated_at.timestamp(), lead.id), reverse=True)


def _save_queue(leads: list[LeadSummary], queue_label: str) -> None:
    st.session_state["lead_queue_ids"] = [lead.id for lead in leads]
    st.session_state["lead_queue_lookup"] = {lead.id: _lead_option_label(lead) for lead in leads}
    st.session_state["lead_queue_label"] = queue_label


def _get_queue_ids(fallback_leads: list[LeadSummary]) -> list[int]:
    queue_ids = st.session_state.get("lead_queue_ids") or []
    if queue_ids:
        return queue_ids
    return [lead.id for lead in fallback_leads]


def _apply_workflow_defaults() -> None:
    workflow_view = st.session_state.get("lead_workflow_view", "Action queue")
    defaults_by_view = {
        "Action queue": {
            "lead_quick_hide_duplicates": True,
            "lead_quick_require_contact": True,
            "lead_quick_high_score": True,
            "lead_quick_uncontacted": True,
        },
        "Ready for outreach": {
            "lead_quick_hide_duplicates": True,
            "lead_quick_require_contact": True,
            "lead_quick_high_score": True,
            "lead_quick_uncontacted": False,
        },
        "Needs enrichment": {
            "lead_quick_hide_duplicates": True,
            "lead_quick_require_contact": False,
            "lead_quick_high_score": False,
            "lead_quick_uncontacted": False,
        },
        "Follow-up due": {
            "lead_quick_hide_duplicates": True,
            "lead_quick_require_contact": True,
            "lead_quick_high_score": False,
            "lead_quick_uncontacted": False,
        },
        "All leads": {
            "lead_quick_hide_duplicates": True,
            "lead_quick_require_contact": False,
            "lead_quick_high_score": False,
            "lead_quick_uncontacted": False,
        },
    }
    for key, value in defaults_by_view.get(workflow_view, {}).items():
        st.session_state[key] = value


def _clear_lead_search() -> None:
    st.session_state["lead_search_term"] = ""


def _reset_queue_filters() -> None:
    st.session_state["lead_filter_city"] = "All"
    st.session_state["lead_filter_status"] = "All"
    st.session_state["lead_filter_category"] = "All"
    st.session_state["lead_filter_source_type"] = "All"
    st.session_state["lead_filter_score_range"] = (0, 100)
    st.session_state["leads_has_email"] = "Any"
    st.session_state["leads_has_whatsapp"] = "Any"
    st.session_state["leads_do_not_contact"] = "Any"
    st.session_state["lead_search_term"] = ""
    _apply_workflow_defaults()
    st.session_state["lead_queue_selected_id"] = st.session_state.get("selected_lead_id")


def _sync_sidebar_page() -> None:
    st.session_state["page"] = st.session_state.get("page_nav", "Overview")


def _sync_detail_selected_lead() -> None:
    selected_lead_id = st.session_state.get("lead_detail_selected_id")
    st.session_state["selected_lead_id"] = selected_lead_id
    if selected_lead_id is not None:
        st.session_state["lead_queue_selected_id"] = selected_lead_id


def _apply_operator_quick_filters(
    leads: list[LeadSummary],
    *,
    hide_duplicates: bool,
    require_contact: bool,
    high_score_only: bool,
    only_uncontacted: bool,
) -> list[LeadSummary]:
    filtered: list[LeadSummary] = []
    for lead in leads:
        if hide_duplicates and lead.is_duplicate:
            continue
        if require_contact and not _has_any_contact(lead):
            continue
        if high_score_only and lead.lead_score < ACTION_QUEUE_SCORE_MIN:
            continue
        if only_uncontacted and not _is_uncontacted(lead):
            continue
        filtered.append(lead)
    return filtered


def _render_queue_action_context(filtered_lead_ids: list[int]) -> None:
    payload = st.session_state.get("queue_action_context")
    if not payload:
        return
    lead_id = payload.get("lead_id")
    action = payload.get("action")
    lead_name = payload.get("lead_name")
    if lead_id in filtered_lead_ids:
        st.session_state["queue_action_context"] = None
        return
    _render_notice(
        f"{lead_name} no longer matches the current queue after {action}.",
        tone="info",
        title="Queue context changed",
    )
    st.session_state["queue_action_context"] = None


def _queue_filter_badges(
    *,
    workflow_view: str,
    search_term: str,
    selected_city: str,
    selected_status: str,
    selected_category: str,
    selected_source_type: str,
    has_email: bool | None,
    has_whatsapp: bool | None,
    do_not_contact: bool | None,
    score_min: int,
    score_max: int,
    hide_duplicates: bool,
    require_contact: bool,
    high_score_only: bool,
    only_uncontacted: bool,
) -> list[tuple[str, str]]:
    badges: list[tuple[str, str]] = [(f"View: {workflow_view}", "info")]
    if search_term:
        badges.append((f'Search: "{search_term}"', "neutral"))
    if selected_city != "All":
        badges.append((f"City: {selected_city}", "neutral"))
    if selected_category != "All":
        badges.append((f"Category: {selected_category}", "neutral"))
    if selected_status != "All":
        badges.append((f"Status: {_humanize(selected_status)}", "neutral"))
    if selected_source_type != "All":
        badges.append((f"Source: {_humanize(selected_source_type)}", "neutral"))
    if has_email is True:
        badges.append(("Has email", "good"))
    elif has_email is False:
        badges.append(("No email", "warn"))
    if has_whatsapp is True:
        badges.append(("Has WhatsApp", "good"))
    elif has_whatsapp is False:
        badges.append(("No WhatsApp", "warn"))
    if do_not_contact is True:
        badges.append(("Do not contact only", "danger"))
    elif do_not_contact is False:
        badges.append(("Contactable only", "good"))
    if score_min > 0 or score_max < 100:
        badges.append((f"Priority range: {score_min}-{score_max}", "neutral"))
    if hide_duplicates:
        badges.append(("Hide duplicates", "neutral"))
    if require_contact:
        badges.append(("Require contact path", "good"))
    if high_score_only:
        badges.append((f"Priority {ACTION_QUEUE_SCORE_MIN}+", "good"))
    if only_uncontacted:
        badges.append(("Only not yet contacted", "warn"))
    return badges


def _build_filtered_queue(
    leads: list[LeadSummary],
    *,
    workflow_view: str,
    search_term: str,
    sort_by: str,
    hide_duplicates: bool,
    require_contact: bool,
    high_score_only: bool,
    only_uncontacted: bool,
) -> list[LeadSummary]:
    filtered = _apply_workflow_view(leads, workflow_view)
    filtered = _apply_operator_quick_filters(
        filtered,
        hide_duplicates=hide_duplicates,
        require_contact=require_contact,
        high_score_only=high_score_only,
        only_uncontacted=only_uncontacted,
    )
    if search_term.strip():
        filtered = [lead for lead in filtered if _matches_search(lead, search_term)]
    return _sort_leads(filtered, sort_by)


def _prepare_queue_display(filtered_leads: list[LeadSummary]) -> tuple[pd.DataFrame, dict[int, str], dict[str, int]]:
    rows: list[dict] = []
    lead_options: dict[int, str] = {}
    any_contact = 0
    needs_enrichment = 0
    follow_up_due = 0

    for lead in filtered_leads:
        if _has_any_contact(lead):
            any_contact += 1
        if lead.last_enriched_at is None and not lead.do_not_contact:
            needs_enrichment += 1
        if _is_follow_up_due(lead):
            follow_up_due += 1

        lead_options[lead.id] = _lead_option_label(lead)
        rows.append(
            {
                "ID": lead.id,
                "Business": lead.business_name,
                "Category": lead.category or "-",
                "City": lead.city or "-",
                "Source": _humanize(lead.lead_source_type),
                "Contact path": _contact_summary(lead),
                "Priority": lead.lead_score,
                "Status": _humanize(lead.status),
                "Follow-up": lead.follow_up_date,
                "Last enriched": lead.last_enriched_at,
                "DNC": lead.do_not_contact,
            }
        )

    return (
        pd.DataFrame.from_records(rows),
        lead_options,
        {
            "queue_size": len(filtered_leads),
            "any_contact": any_contact,
            "needs_enrichment": needs_enrichment,
            "follow_up_due": follow_up_due,
        },
    )


def _lead_table_rows(leads: list[LeadSummary]) -> list[dict]:
    return [
        {
            "ID": lead.id,
            "Business": lead.business_name,
            "Category": lead.category or "-",
            "City": lead.city or "-",
            "Source": _humanize(lead.lead_source_type),
            "Contact path": _contact_summary(lead),
            "Priority": lead.lead_score,
            "Status": _humanize(lead.status),
            "Follow-up": lead.follow_up_date,
            "Last enriched": lead.last_enriched_at,
            "DNC": lead.do_not_contact,
        }
        for lead in leads
    ]


def _score_rows(score_breakdown: dict) -> list[dict]:
    return [
        {
            "Signal": _humanize(key),
            "Points": payload.get("points"),
            "Reason": payload.get("reason"),
        }
        for key, payload in score_breakdown.items()
    ]


def _material_rows(material_profile: dict) -> list[dict]:
    return [
        {
            "Material": _humanize(key),
            "Relevant": payload.get("relevant", False),
            "Confidence": payload.get("confidence"),
            "Matched keywords": ", ".join(payload.get("matched_keywords") or []),
        }
        for key, payload in material_profile.items()
    ]


def _contact_rows(lead: LeadDetail) -> list[dict]:
    return [
        {
            "Type": _humanize(contact.contact_type),
            "Value": contact.raw_value,
            "Normalized": contact.normalized_value or "-",
            "Primary": contact.is_primary,
            "Confidence": round(contact.confidence, 2),
            "Label": contact.label or "-",
            "Source kind": contact.source_kind or "-",
            "Source URL": contact.source_url or "-",
            "Note": contact.note or "-",
            "Updated": contact.updated_at,
        }
        for contact in lead.contacts
    ]


def _activity_rows(lead: LeadDetail) -> list[dict]:
    return [
        {
            "When": activity.created_at,
            "Action": _humanize(activity.action),
            "Actor": activity.actor,
            "Message": activity.message or "-",
        }
        for activity in lead.activity_logs
    ]


def _enrichment_rows(lead: LeadDetail) -> list[dict]:
    return [
        {
            "Fetched": record.fetched_at,
            "Page type": record.page_type or "-",
            "HTTP": record.http_status,
            "Robots allowed": record.robots_allowed,
            "Source URL": record.source_url,
            "Note": record.note or "-",
        }
        for record in lead.enrichments
    ]


def _raw_record_rows(raw_records: list[dict]) -> list[dict]:
    return [
        {
            "Discovered": record["discovered_at"],
            "Provider": record["provider"],
            "Search term": record["search_term"] or "-",
            "Search input": record["search_input"] or "-",
            "Import batch": record["import_batch_id"],
            "Provider record": record["provider_record_id"] or "-",
            "Source URL": record["source_url"] or "-",
        }
        for record in raw_records
    ]


def _draft_rows(drafts) -> list[dict]:
    return [
        {
            "Created": draft.created_at,
            "Draft type": _humanize(draft.draft_type),
            "Channel": _humanize(draft.channel),
            "Status": _humanize(draft.status),
            "Subject": draft.subject or "-",
        }
        for draft in drafts
    ]


def _discovery_preview_rows(preview: DiscoveryPreviewResponse) -> list[dict]:
    rows: list[dict] = []
    for item in preview.items:
        candidate = item.candidate
        rows.append(
            {
                "Business": candidate.business_name,
                "Search term": item.search_term,
                "Category": candidate.category or "-",
                "Neighborhood": candidate.neighborhood or "-",
                "City": candidate.city or "-",
                "Phone": candidate.whatsapp or candidate.phone or "-",
                "Website": candidate.website,
                "Maps": candidate.google_maps_url or item.source_url,
            }
        )
    return rows


def _default_template_key_for_lead(lead: LeadDetail, template_keys: list[str]) -> str:
    if _status_in(lead.status, FOLLOW_UP_STATUS_VALUES):
        if TemplateKey.FOLLOW_UP_EMAIL.value in template_keys and lead.email:
            return TemplateKey.FOLLOW_UP_EMAIL.value
        if TemplateKey.FOLLOW_UP_WHATSAPP.value in template_keys and lead.whatsapp:
            return TemplateKey.FOLLOW_UP_WHATSAPP.value
    else:
        if TemplateKey.COLD_EMAIL.value in template_keys and lead.email:
            return TemplateKey.COLD_EMAIL.value
        if TemplateKey.COLD_WHATSAPP.value in template_keys and lead.whatsapp:
            return TemplateKey.COLD_WHATSAPP.value
    return template_keys[0]


_inject_styles()
_init_session_state()

pages = ["Overview", "Discovery", "Leads", "Lead Detail"]
if st.session_state.get("page") not in pages:
    st.session_state["page"] = "Overview"
if st.session_state.get("page_nav") != st.session_state["page"]:
    st.session_state["page_nav"] = st.session_state["page"]
_render_sidebar_brand()
st.sidebar.markdown('<div class="sidebar-section-label">Workspace</div>', unsafe_allow_html=True)
page = st.sidebar.radio(
    "Workspace",
    pages,
    key="page_nav",
    on_change=_sync_sidebar_page,
    label_visibility="collapsed",
)
page = st.session_state.get("page", page)
_render_operator_guide(st.sidebar, expanded=False)

if st.session_state.get("lead_queue_ids") and page in {"Leads", "Lead Detail"}:
    with st.sidebar.container(border=True):
        st.markdown("### Working queue")
        st.markdown(
            f"**{len(st.session_state['lead_queue_ids'])} lead(s)** in `{st.session_state['lead_queue_label']}`"
        )
        if st.session_state.get("selected_lead_id"):
            st.caption(f"Current lead: {st.session_state['selected_lead_id']}")

city_options: list[str] = []
category_options: list[str] = []
if page == "Leads":
    city_options, category_options = _list_distinct_values()
_render_app_header(page)

if page == "Discovery":
    _render_flash("Discovery")
    _render_page_intro(
        "Front door",
        "Discovery",
        "Search a target area, preview businesses, and save the right ones into your working lead queue.",
    )
    _render_badges(
        [
            (
                "Google Places ready" if settings.google_places_enabled else "Google Places blocked",
                "good" if settings.google_places_enabled else "danger",
            ),
            ("Preview before save", "info"),
            ("Raw source history on save", "neutral"),
            ("Discovery is read-only until saved", "neutral"),
        ]
    )

    discovery_form_col, discovery_status_col = st.columns([1.9, 1], gap="large")
    preview_requested = False

    with discovery_form_col:
        with st.container(border=True):
            st.markdown("### Discovery setup")
            st.caption("Define the target area, search language, and preview limits before running a read-only discovery pass.")
            with st.form("discovery_form"):
                location_mode = st.radio(
                    "Location mode",
                    options=DISCOVERY_LOCATION_MODES,
                    horizontal=True,
                    key="discovery_location_mode",
                )

                if location_mode == DISCOVERY_LOCATION_MODES[0]:
                    area_col1, area_col2, area_col3 = st.columns([1.3, 1, 0.9])
                    with area_col1:
                        st.text_input(
                            "City",
                            key="discovery_city",
                            placeholder="Campinas, SP",
                        )
                    with area_col2:
                        st.text_input(
                            "Neighborhood (optional)",
                            key="discovery_neighborhood",
                            placeholder="Barao Geraldo",
                        )
                    with area_col3:
                        st.text_input(
                            "CEP (optional)",
                            key="discovery_postal_code",
                            placeholder="13083-852",
                        )
                else:
                    area_col1, area_col2, area_col3 = st.columns([1, 1, 1.2])
                    with area_col1:
                        st.text_input(
                            "Latitude",
                            key="discovery_latitude",
                            placeholder="-22.9056",
                        )
                    with area_col2:
                        st.text_input(
                            "Longitude",
                            key="discovery_longitude",
                            placeholder="-47.0608",
                        )
                    with area_col3:
                        st.text_input(
                            "Location label (optional)",
                            key="discovery_location_label",
                            placeholder="Campinas - SP, Brasil",
                        )

                config_col1, config_col2 = st.columns(2)
                with config_col1:
                    st.slider(
                        "Radius (meters)",
                        min_value=500,
                        max_value=20000,
                        step=250,
                        key="discovery_radius_m",
                    )
                with config_col2:
                    st.number_input(
                        "Max results per term",
                        min_value=1,
                        max_value=20,
                        step=1,
                        key="discovery_max_results_per_term",
                    )

                st.markdown("### 2. Search categories")
                st.multiselect(
                    "Suggested categories",
                    options=DISCOVERY_SEARCH_TERM_OPTIONS,
                    key="discovery_search_terms",
                    placeholder="Choose one or more target categories",
                )
                st.text_area(
                    "Extra search terms (optional)",
                    key="discovery_custom_terms",
                    height=90,
                    placeholder="One per line or comma separated",
                )
                preview_requested = st.form_submit_button(
                    "Run discovery preview",
                    type="primary",
                    use_container_width=True,
                    disabled=not settings.google_places_enabled,
                )
            st.caption(
                "Discovery preview never writes data. Businesses are only created or updated after you explicitly save them as leads."
            )

    with discovery_status_col:
        provider_state, provider_tone = _boolean_state(settings.google_places_enabled)
        _render_feature_card(
            "Discovery readiness",
            "Google Places and geocoding are configured for area search, resolution, and preview."
            if settings.google_places_enabled
            else "Discovery is blocked until GOOGLE_API_KEY is configured for location resolution and business preview.",
            tone=provider_tone,
            eyebrow=provider_state,
            meta="Use city plus optional neighborhood or CEP for broad scans, or switch to coordinates when the radius is already known.",
        )
        _render_step_card(
            "How discovery works",
            [
                "Search a target area and category set.",
                "Preview the matched public businesses.",
                "Save the right businesses as leads.",
                "Continue in the Leads queue for review.",
            ],
            eyebrow="Operator flow",
            tone="info",
        )

    if preview_requested:
        terms = _parse_discovery_terms(
            st.session_state.get("discovery_search_terms", []),
            st.session_state.get("discovery_custom_terms", ""),
        )
        try:
            if not terms:
                raise ValueError("Select at least one search term before running discovery.")

            if st.session_state.get("discovery_location_mode") == DISCOVERY_LOCATION_MODES[0]:
                city = st.session_state.get("discovery_city", "").strip()
                if not city:
                    raise ValueError("Enter a city before running discovery.")
                request = DiscoverySearchRequest(
                    search_terms=terms,
                    location_query=_build_discovery_location_query(
                        city,
                        st.session_state.get("discovery_neighborhood", ""),
                        st.session_state.get("discovery_postal_code", ""),
                    ),
                    radius_m=int(st.session_state.get("discovery_radius_m", 3000)),
                    max_results_per_term=int(st.session_state.get("discovery_max_results_per_term", 10)),
                )
            else:
                latitude_text = st.session_state.get("discovery_latitude", "").strip().replace(",", ".")
                longitude_text = st.session_state.get("discovery_longitude", "").strip().replace(",", ".")
                if not latitude_text or not longitude_text:
                    raise ValueError("Enter both latitude and longitude before running discovery.")
                request = DiscoverySearchRequest(
                    search_terms=terms,
                    location_query=st.session_state.get("discovery_location_label", "").strip() or None,
                    latitude=float(latitude_text),
                    longitude=float(longitude_text),
                    radius_m=int(st.session_state.get("discovery_radius_m", 3000)),
                    max_results_per_term=int(st.session_state.get("discovery_max_results_per_term", 10)),
                )

            with st.spinner("Searching public businesses..."):
                preview = _preview_discovery(request)
            st.session_state["discovery_preview_request"] = request.model_dump(mode="json")
            st.session_state["discovery_preview_payload"] = preview.model_dump(mode="json")
            st.session_state["discovery_import_payload"] = None
            st.rerun()
        except (ValueError, ValidationError) as exc:
            st.error(str(exc))
        except Exception:
            st.error("Discovery preview could not be completed. Check the provider configuration and try again.")

    preview_request_payload = st.session_state.get("discovery_preview_request")
    preview_payload = st.session_state.get("discovery_preview_payload")
    import_payload = st.session_state.get("discovery_import_payload")
    preview_request = (
        DiscoverySearchRequest.model_validate(preview_request_payload) if preview_request_payload else None
    )
    preview_response = DiscoveryPreviewResponse.model_validate(preview_payload) if preview_payload else None
    import_response = DiscoverySearchResponse.model_validate(import_payload) if import_payload else None

    with st.container(border=True):
        st.markdown("### Preview results")
        if not preview_response:
            if settings.google_places_enabled:
                _render_notice(
                    "Search an area above to inspect public businesses before saving them as leads.",
                    tone="info",
                    title="No preview yet",
                )
            else:
                _render_notice(
                    "Discovery preview is unavailable until GOOGLE_API_KEY is configured.",
                    tone="danger",
                    title="Discovery blocked",
                )
        else:
            unique_candidates = len(
                {
                    item.provider_record_id
                    or item.candidate.google_place_id
                    or item.candidate.normalized_business_name
                    for item in preview_response.items
                }
            )
            _render_badges(
                [
                    (preview_response.resolved_location.label, "info"),
                    (f"{len(preview_response.items)} preview row(s)", "good"),
                    (f"{unique_candidates} unique business(es)", "neutral"),
                    (f"{preview_response.total_provider_results} provider result(s)", "neutral"),
                ]
            )
            st.caption(
                "Preview rows may repeat a business across search terms. Saving them as leads preserves the raw source history for every provider hit."
            )
            if preview_response.items:
                st.dataframe(
                    pd.DataFrame(_discovery_preview_rows(preview_response)),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Website": st.column_config.LinkColumn("Website"),
                        "Maps": st.column_config.LinkColumn("Maps"),
                    },
                )
            else:
                _render_notice(
                    "No businesses were found for the current search. Try different terms or a wider radius.",
                    tone="warn",
                    title="No matches found",
                )

            preview_action_col1, preview_action_col2 = st.columns(2)
            with preview_action_col1:
                ingest_requested = st.button(
                    "Save previewed businesses as leads",
                    type="primary",
                    use_container_width=True,
                    disabled=not bool(preview_response.items),
                )
            with preview_action_col2:
                clear_preview_requested = st.button(
                    "Discard preview",
                    use_container_width=True,
                )
            st.caption("Save to leads writes the lead records and keeps the raw discovery history linked to the batch.")

            if clear_preview_requested:
                _clear_discovery_results()
                st.rerun()

            if ingest_requested:
                try:
                    if not preview_request:
                        raise ValueError("Run a discovery preview before saving businesses as leads.")
                    with st.spinner("Saving discovered businesses..."):
                        response = _ingest_discovery(preview_request, preview_response)
                    st.session_state["discovery_import_payload"] = response.model_dump(mode="json")
                    _set_flash(
                        "Discovery",
                        (
                            f"Saved batch {response.batch_id}. "
                            f"Created: {response.created_leads}. Updated: {response.updated_leads}."
                        ),
                    )
                    st.rerun()
                except (ValueError, ValidationError) as exc:
                    st.error(str(exc))
                except Exception:
                    st.error("Saving the preview as leads could not be completed. Try the preview again.")

    with st.container(border=True):
        st.markdown("### Move into queue review")
        if not import_response:
            _render_notice(
                "No discovery batch has been saved in this session yet.",
                tone="info",
                title="Nothing saved yet",
            )
        else:
            _render_badges(
                [
                    (f"Batch {import_response.batch_id}", "info"),
                    (f"Created {import_response.created_leads}", "good"),
                    (f"Updated {import_response.updated_leads}", "warn" if import_response.updated_leads else "neutral"),
                    (f"{len(import_response.leads)} lead(s) ready", "good"),
                ]
            )
            st.caption(
                "These businesses are now saved as leads. Open the first one directly or jump to the Leads page with this batch saved as the working queue."
            )
            st.dataframe(
                pd.DataFrame(_lead_table_rows(import_response.leads)),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Priority": st.column_config.NumberColumn("Priority", min_value=0, max_value=100),
                    "Follow-up": st.column_config.DateColumn("Follow-up"),
                    "Last enriched": st.column_config.DatetimeColumn("Last enriched"),
                    "DNC": st.column_config.CheckboxColumn("DNC"),
                },
            )

            review_col1, review_col2 = st.columns(2)
            with review_col1:
                open_first_imported = st.button(
                    "Open first lead workspace",
                    type="primary",
                    use_container_width=True,
                )
            with review_col2:
                open_imported_queue = st.button(
                    "Open saved leads queue",
                    use_container_width=True,
                )

            queue_label = f"Discovery batch {import_response.batch_id}"
            first_imported_id = import_response.leads[0].id if import_response.leads else None
            if open_first_imported and first_imported_id is not None:
                _save_queue(import_response.leads, queue_label)
                st.session_state["selected_lead_id"] = first_imported_id
                st.session_state["lead_detail_selected_id"] = first_imported_id
                _set_flash("Lead Detail", f"Reviewing saved batch {import_response.batch_id}.")
                st.session_state["page"] = "Lead Detail"
                st.rerun()

            if open_imported_queue:
                _save_queue(import_response.leads, queue_label)
                st.session_state["lead_workflow_view"] = "All leads"
                _reset_queue_filters()
                st.session_state["lead_queue_selected_id"] = first_imported_id
                st.session_state["selected_lead_id"] = first_imported_id
                _set_flash(
                    "Leads",
                    f"Saved batch {import_response.batch_id} is ready for review. The working queue has been saved.",
                )
                st.session_state["page"] = "Leads"
                st.rerun()

elif page == "Overview":
    overview_metrics, recent_leads = _fetch_overview_snapshot()
    total = overview_metrics["total"]
    if not settings.google_places_enabled and total == 0:
        next_step = "System readiness"
        next_copy = "Configure Google Places first so Discovery can open the first working lead set."
    elif total == 0:
        next_step = "Discovery"
        next_copy = "Start by searching a target area and saving the first working queue."
    else:
        next_step = "Leads Review"
        next_copy = "Move into the queue, narrow the working set, and open the next business that deserves attention."

    _render_overview_hero(next_step=next_step, next_copy=next_copy)

    _render_metric_band(
        [
            ("Loaded leads", str(overview_metrics["total"]), "Businesses currently available in the workspace."),
            ("With email", str(overview_metrics["with_email"]), "Records in the workspace with email stored."),
            ("With WhatsApp", str(overview_metrics["with_whatsapp"]), "Records in the workspace with WhatsApp available."),
            ("Do not contact", str(overview_metrics["do_not_contact"]), "Records currently blocked from outreach."),
        ]
    )

    _render_section_intro("How the workspace flows", "Four steps take the operator from discovery to export.")
    workflow_cols = st.columns(4)
    workflow_cards = [
        (
            "01",
            "Discovery",
            "Search an area, preview public businesses, and save the right matches.",
        ),
        (
            "02",
            "Leads Review",
            "Review the saved queue, filter it fast, and keep the next lead obvious.",
        ),
        (
            "03",
            "Lead Workspace",
            "Work one business at a time across CRM review, evidence, and drafts.",
        ),
        (
            "04",
            "Export",
            "Prepare the current operating set as a clean Excel handoff.",
        ),
    ]
    for column, (step, title, copy) in zip(workflow_cols, workflow_cards, strict=False):
        with column:
            _render_workflow_card(step, title, copy)

    google_state, google_tone = _boolean_state(settings.google_places_enabled)
    sending_state, sending_tone = _boolean_state(settings.sending_enabled, positive="Enabled", negative="Guarded")
    db_copy = _format_database_label(settings.database_url)
    export_copy = _format_path_label(settings.export_path)

    _render_section_intro("System readiness", "The operational checks that matter most before working the queue.")
    readiness_cols = st.columns(4)
    with readiness_cols[0]:
        _render_status_card(
            "Google Places",
            google_state,
            "Area search and discovery preview are ready."
            if settings.google_places_enabled
            else "Discovery stays blocked until the provider key is configured.",
            tone=google_tone,
            meta="Area search and business preview",
        )
    with readiness_cols[1]:
        _render_status_card(
            "Sending controls",
            sending_state,
            "Outbound channels stay protected behind explicit review."
            if not settings.sending_enabled
            else "Configured channels can send after operator review is complete.",
            tone=sending_tone,
            meta=(
                f"Email {'On' if settings.email_sending_enabled else 'Off'} | "
                f"WhatsApp {'On' if settings.whatsapp_sending_enabled else 'Off'}"
            ),
        )
    with readiness_cols[2]:
        _render_status_card(
            "Database",
            "Connected",
            "Saved leads, evidence, enrichments, and history stay in the workspace database.",
            tone="good",
            meta=db_copy,
        )
    with readiness_cols[3]:
        _render_status_card(
            "Export path",
            "Ready",
            "Prepared workbooks write to the configured export directory.",
            tone="info",
            meta=export_copy,
        )

    with st.container(border=True):
        _render_section_intro("Recent leads", "The latest saved businesses in the current working set.")
        if recent_leads:
            overview_rows = [
                {
                    "Business": lead.business_name,
                    "City": lead.city or "-",
                    "Status": _humanize(lead.status),
                    "Priority": lead.lead_score,
                    "Contact": _contact_summary(lead),
                    "Last enriched": lead.last_enriched_at,
                }
                for lead in recent_leads
            ]
            st.dataframe(
                pd.DataFrame(overview_rows),
                use_container_width=True,
                hide_index=True,
                height=_table_height(len(overview_rows), max_height=420),
                column_config={
                    "Priority": st.column_config.NumberColumn("Priority", min_value=0, max_value=100),
                    "Last enriched": st.column_config.DatetimeColumn("Last enriched"),
                },
            )
        else:
            _render_notice(
                "No leads are saved yet. Start in Discovery to build the first working queue.",
                tone="info",
                title="No recent activity",
            )

elif page == "Leads":
    _render_flash("Leads")
    _render_page_intro(
        "Queue review",
        "Leads Review Queue",
        "Review saved businesses, narrow the working set, and open one lead at a time.",
    )
    _render_badges(
        [
            ("Working queue review", "info"),
            ("Batch enrich and cleanup", "neutral"),
            ("Export current working set", "good"),
        ]
    )

    with st.container(border=True):
        st.markdown("### Queue controls")
        st.caption("Adjust search and filters, then apply once to keep the queue responsive while typing.")

        workflow_view = st.radio(
            "Review lane",
            options=WORKFLOW_VIEWS,
            horizontal=True,
            key="lead_workflow_view",
            on_change=_apply_workflow_defaults,
        )
        st.caption(
            WORKFLOW_VIEW_DESCRIPTIONS.get(workflow_view, "Filter the working queue for the next operator action.")
        )

        city_filter_options = ["All"] + city_options
        category_filter_options = ["All"] + category_options
        status_filter_options = ["All"] + [status.value for status in LeadStatus]
        source_filter_options = ["All"] + [source.value for source in LeadSourceType]
        if st.session_state.get("lead_filter_city") not in city_filter_options:
            st.session_state["lead_filter_city"] = "All"
        if st.session_state.get("lead_filter_category") not in category_filter_options:
            st.session_state["lead_filter_category"] = "All"
        if st.session_state.get("lead_filter_status") not in status_filter_options:
            st.session_state["lead_filter_status"] = "All"
        if st.session_state.get("lead_filter_source_type") not in source_filter_options:
            st.session_state["lead_filter_source_type"] = "All"

        with st.form("lead_queue_filters_form"):
            toolbar_col1, toolbar_col2 = st.columns([2.4, 1.1])
            with toolbar_col1:
                search_term = st.text_input(
                    "Quick search",
                    key="lead_search_term",
                    placeholder="Business name, city, category, website, email, phone...",
                )
            with toolbar_col2:
                sort_by = st.selectbox("Sort results", SORT_OPTIONS, key="lead_sort_by")

            quick_col1, quick_col2, quick_col3, quick_col4 = st.columns(4)
            with quick_col1:
                hide_duplicates = st.checkbox("Hide duplicates", key="lead_quick_hide_duplicates")
            with quick_col2:
                require_contact = st.checkbox("Require any contact path", key="lead_quick_require_contact")
            with quick_col3:
                high_score_only = st.checkbox(
                    f"Priority {ACTION_QUEUE_SCORE_MIN}+",
                    key="lead_quick_high_score",
                )
            with quick_col4:
                only_uncontacted = st.checkbox("Only not yet contacted", key="lead_quick_uncontacted")
            st.caption(
                "Quick filters follow the selected review lane by default. City, category, source, and tighter priority ranges stay in Advanced filters."
            )

            with st.expander("Advanced filters", expanded=False):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    selected_city = st.selectbox(
                        "City",
                        city_filter_options,
                        key="lead_filter_city",
                    )
                    selected_status = st.selectbox(
                        "Exact status",
                        status_filter_options,
                        key="lead_filter_status",
                        format_func=lambda item: "All" if item == "All" else _humanize(item),
                    )
                with col2:
                    selected_category = st.selectbox(
                        "Category",
                        category_filter_options,
                        key="lead_filter_category",
                    )
                    selected_source_type = st.selectbox(
                        "Lead source",
                        source_filter_options,
                        key="lead_filter_source_type",
                        format_func=lambda item: "All" if item == "All" else _humanize(item),
                    )
                with col3:
                    has_email = _tri_state_filter("Has email", "leads_has_email")
                    has_whatsapp = _tri_state_filter("Has WhatsApp", "leads_has_whatsapp")
                with col4:
                    do_not_contact = _tri_state_filter("Do not contact", "leads_do_not_contact")
                    score_min, score_max = st.slider("Priority range", 0, 100, key="lead_filter_score_range")

            action_col1, action_col2, action_col3 = st.columns([1.1, 1, 1])
            with action_col1:
                st.form_submit_button("Apply queue filters", type="primary", use_container_width=True)
            with action_col2:
                st.caption("")
            with action_col3:
                st.caption("")

        toolbar_action_col1, toolbar_action_col2 = st.columns(2)
        with toolbar_action_col1:
            st.button(
                "Clear search",
                key="lead_queue_clear_search",
                on_click=_clear_lead_search,
                disabled=not bool(st.session_state.get("lead_search_term")),
                use_container_width=True,
            )
        with toolbar_action_col2:
            st.button(
                "Reset all filters",
                key="lead_queue_reset_quick_filters",
                on_click=_reset_queue_filters,
                use_container_width=True,
            )

    filters = LeadListFilters(
        city=None if selected_city == "All" else selected_city,
        status=None if selected_status == "All" else LeadStatus(selected_status),
        has_email=has_email,
        has_whatsapp=has_whatsapp,
        category=None if selected_category == "All" else selected_category,
        score_min=score_min,
        score_max=score_max,
        lead_source_type=None if selected_source_type == "All" else LeadSourceType(selected_source_type),
        do_not_contact=do_not_contact,
        limit=LEAD_PAGE_SIZE,
        offset=0,
    )

    total, leads = _fetch_leads(filters)
    filtered_leads = _build_filtered_queue(
        leads,
        workflow_view=workflow_view,
        search_term=search_term,
        sort_by=sort_by,
        hide_duplicates=hide_duplicates,
        require_contact=require_contact,
        high_score_only=high_score_only,
        only_uncontacted=only_uncontacted,
    )
    queue_df, lead_options, queue_stats = _prepare_queue_display(filtered_leads)
    with st.container(border=True):
        st.markdown("### Active filters")
        st.caption("Use reset above to clear the current queue lens and return to the broader working set.")
        _render_badges(
            _queue_filter_badges(
                workflow_view=workflow_view,
                search_term=search_term,
                selected_city=selected_city,
                selected_status=selected_status,
                selected_category=selected_category,
                selected_source_type=selected_source_type,
                has_email=has_email,
                has_whatsapp=has_whatsapp,
                do_not_contact=do_not_contact,
                score_min=score_min,
                score_max=score_max,
                hide_duplicates=hide_duplicates,
                require_contact=require_contact,
                high_score_only=high_score_only,
                only_uncontacted=only_uncontacted,
            )
        )
    _render_queue_action_context([lead.id for lead in filtered_leads])

    shown_count = queue_stats["queue_size"]
    loaded_count = len(leads)
    if total > loaded_count:
        st.caption(
            f"Showing {shown_count} lead(s) from the first {loaded_count} of {total} database matches. "
            "Use filters to narrow the queue further."
        )
    else:
        st.caption(f"Showing {shown_count} lead(s) from {total} database matches.")

    metrics = st.columns(4)
    metrics[0].metric("Queue size", queue_stats["queue_size"])
    metrics[1].metric("Any contact", queue_stats["any_contact"])
    metrics[2].metric("Needs enrichment", queue_stats["needs_enrichment"])
    metrics[3].metric("Follow-up due", queue_stats["follow_up_due"])

    if filtered_leads:
        results_col, action_col = st.columns([2.5, 1.4], gap="large")

        with results_col:
            with st.container(border=True):
                st.markdown("### Working queue")
                st.caption("The selected lead stays visible on the right so operators can scan the queue without losing context.")
                st.dataframe(
                    queue_df,
                    use_container_width=True,
                    hide_index=True,
                    height=_table_height(len(filtered_leads)),
                    column_config={
                        "Priority": st.column_config.NumberColumn("Priority", min_value=0, max_value=100),
                        "Follow-up": st.column_config.DateColumn("Follow-up"),
                        "Last enriched": st.column_config.DatetimeColumn("Last enriched"),
                        "DNC": st.column_config.CheckboxColumn("DNC"),
                    },
                )

        with action_col:
            lead_option_ids = list(lead_options.keys())
            queue_selected_id = _resolve_lead_selection(
                lead_option_ids,
                st.session_state.get("lead_queue_selected_id"),
                st.session_state.get("selected_lead_id"),
            )
            if st.session_state.get("lead_queue_selected_id") != queue_selected_id:
                st.session_state["lead_queue_selected_id"] = queue_selected_id
            with st.container(border=True):
                st.markdown("### Selected lead")
                selected_lead_id = st.selectbox(
                    "Open lead workspace",
                    options=lead_option_ids,
                    format_func=lambda item: lead_options[item],
                    key="lead_queue_selected_id",
                )
                st.caption(
                    "Keep the queue context while you inspect the next lead, refresh public contact data, or jump into the full workspace."
                )
            selected_lead = next(lead for lead in filtered_leads if lead.id == selected_lead_id)

            with st.container(border=True):
                st.markdown(f"**{selected_lead.business_name}**")
                st.markdown(
                    f'<div class="operator-muted">{_safe_text(selected_lead.category)} - '
                    f'{_safe_text(selected_lead.city)} / {_safe_text(selected_lead.state)}</div>',
                    unsafe_allow_html=True,
                )
                _render_badges(
                    [
                        (f"Status: {_humanize(selected_lead.status)}", "info"),
                        (f"Priority: {selected_lead.lead_score}", "good" if selected_lead.lead_score >= 70 else "warn"),
                        (
                            f"Contact: {_contact_summary(selected_lead)}",
                            "good" if _has_direct_channel(selected_lead) else "warn",
                        ),
                    ]
                )
                st.caption(_lead_next_step(selected_lead))

            with st.container(border=True):
                st.markdown("### Immediate actions")
                queue_action_col1, queue_action_col2 = st.columns(2)
                with queue_action_col1:
                    if st.button("Open workspace", type="primary", use_container_width=True):
                        queue_label = workflow_view
                        if search_term:
                            queue_label = f"{queue_label} + search"
                        _save_queue(filtered_leads, queue_label)
                        st.session_state["selected_lead_id"] = selected_lead_id
                        st.session_state["lead_detail_selected_id"] = selected_lead_id
                        st.session_state["page"] = "Lead Detail"
                        st.rerun()
                with queue_action_col2:
                    if st.button("Find more public contact info", use_container_width=True):
                        with st.spinner("Refreshing public contact info..."):
                            result = _enrich_lead(selected_lead_id)
                        st.session_state["lead_queue_selected_id"] = selected_lead_id
                        st.session_state["queue_action_context"] = {
                            "lead_id": selected_lead_id,
                            "lead_name": selected_lead.business_name,
                            "action": "the public contact refresh",
                        }
                        _set_flash(
                            "Leads",
                            (
                                f"Public contact refresh complete for {selected_lead.business_name}. "
                                f"Pages fetched: {result.pages_fetched}. Contacts added: {result.contacts_added}."
                            ),
                        )
                        st.rerun()
                st.caption("Open keeps the current queue context. Refresh adds public evidence to the selected lead.")

            with st.container(border=True):
                st.markdown("### Batch public contact refresh")
                batch_ids = st.multiselect(
                    "Selected leads",
                    options=list(lead_options.keys()),
                    format_func=lambda item: lead_options[item],
                )
                st.caption("Use this when several saved leads need a fresh pass over their public websites.")
                if st.button("Refresh public contact info for selected leads", use_container_width=True):
                    if not batch_ids:
                        _render_notice("Select at least one lead before running a batch refresh.", tone="warn")
                    else:
                        with st.spinner("Refreshing public contact info..."):
                            results = _enrich_batch(batch_ids)
                        _render_notice(
                            f"Refreshed public contact info for {len(results)} lead(s).",
                            tone="good",
                            title="Batch refresh complete",
                        )
                        st.dataframe(
                            pd.DataFrame([result.model_dump(mode="json") for result in results]),
                            use_container_width=True,
                            hide_index=True,
                            height=_table_height(len(results), max_height=420),
                        )

            with st.container(border=True):
                st.markdown("### Duplicate cleanup")
                st.caption("Preview likely duplicates first. Marking duplicates keeps raw history and provenance.")
                if st.button("Preview possible duplicates in shown leads", use_container_width=True):
                    preview = _preview_duplicates([lead.id for lead in filtered_leads])
                    st.session_state["duplicate_preview_rows"] = [
                        item.model_dump(mode="json") for item in preview.items
                    ]

                if st.button("Mark duplicates in shown leads", use_container_width=True):
                    results = _run_dedupe([lead.id for lead in filtered_leads])
                    _render_notice(
                        f"Duplicate cleanup processed {len(results)} pair(s).",
                        tone="good",
                        title="Duplicate cleanup complete",
                    )
                    st.session_state["dedupe_results"] = [result.model_dump(mode="json") for result in results]

            with st.container(border=True):
                st.markdown("### Export")
                st.caption("The workbook includes Leads, Outreach_Log, Templates, Settings, and Metadata.")
                if st.button("Prepare Excel workbook", use_container_width=True):
                    filename, payload = _export_excel(filters)
                    st.session_state["export_filename"] = filename
                    st.session_state["export_payload"] = payload
                    _render_notice("Excel workbook is ready.", tone="good", title="Export prepared")

                if st.session_state.get("export_payload"):
                    st.download_button(
                        "Download Excel workbook",
                        data=st.session_state["export_payload"],
                        file_name=st.session_state["export_filename"],
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )

        if st.session_state.get("duplicate_preview_rows"):
            with st.expander("Possible duplicate pairs", expanded=False):
                st.dataframe(
                    pd.DataFrame(st.session_state["duplicate_preview_rows"]),
                    use_container_width=True,
                    hide_index=True,
                    height=_table_height(len(st.session_state["duplicate_preview_rows"]), max_height=420),
                )

        if st.session_state.get("dedupe_results"):
            with st.expander("Duplicate cleanup results", expanded=False):
                st.dataframe(
                    pd.DataFrame(st.session_state["dedupe_results"]),
                    use_container_width=True,
                    hide_index=True,
                    height=_table_height(len(st.session_state["dedupe_results"]), max_height=420),
                )
    else:
        _render_notice("No leads matched the current queue view.", tone="info", title="Empty queue view")
        empty_col1, empty_col2 = st.columns(2)
        with empty_col1:
            st.button(
                "Clear search",
                key="lead_queue_empty_clear_search",
                on_click=_clear_lead_search,
                disabled=not bool(search_term),
                use_container_width=True,
            )
        with empty_col2:
            st.button(
                "Reset all filters",
                key="lead_queue_empty_reset_quick_filters",
                on_click=_reset_queue_filters,
                use_container_width=True,
            )
        st.caption("Advanced filters may also still be limiting the queue.")

else:
    _render_flash("Lead Detail")
    _render_badges(
        [
            ("Single-lead workspace", "info"),
            ("CRM review and enrich", "neutral"),
            ("Drafts and provenance", "good"),
        ]
    )

    _, lead_summaries = _fetch_leads(LeadListFilters(limit=LEAD_PAGE_SIZE, offset=0))
    if not lead_summaries:
        _render_notice("No leads available yet.", tone="info", title="Nothing to review")
    else:
        all_lookup = {lead.id: _lead_option_label(lead) for lead in lead_summaries}
        saved_queue_ids = st.session_state.get("lead_queue_ids") or []
        queue_ids = saved_queue_ids or _get_queue_ids(lead_summaries)
        queue_lookup = st.session_state.get("lead_queue_lookup") or all_lookup
        available_queue_ids = [lead_id for lead_id in queue_ids if lead_id in all_lookup]
        restored_saved_queue = False
        if not available_queue_ids:
            available_queue_ids = [lead.id for lead in lead_summaries]
            queue_lookup = all_lookup
            if saved_queue_ids:
                _save_queue(lead_summaries, "All loaded leads")
                restored_saved_queue = True

        if restored_saved_queue:
            _render_notice(
                "The saved working queue was no longer available, so navigation fell back to all loaded leads.",
                tone="warn",
                title="Queue restored",
            )

        current_lead_id = _resolve_lead_selection(
            available_queue_ids,
            st.session_state.get("lead_detail_selected_id"),
            st.session_state.get("selected_lead_id"),
        )
        if current_lead_id is None:
            _render_notice("No leads available in the current queue.", tone="info", title="Empty queue")
            st.stop()
        if st.session_state.get("selected_lead_id") != current_lead_id:
            st.session_state["selected_lead_id"] = current_lead_id
        if st.session_state.get("lead_detail_selected_id") != current_lead_id:
            st.session_state["lead_detail_selected_id"] = current_lead_id
        queue_index = available_queue_ids.index(current_lead_id)
        with st.container(border=True):
            nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([1, 1, 2, 2])
            with nav_col1:
                if st.button("Back to current queue", use_container_width=True):
                    st.session_state["lead_queue_selected_id"] = current_lead_id
                    st.session_state["page"] = "Leads"
                    st.rerun()
            with nav_col2:
                if st.button("Previous in queue", disabled=queue_index == 0, use_container_width=True):
                    previous_lead_id = available_queue_ids[queue_index - 1]
                    st.session_state["selected_lead_id"] = previous_lead_id
                    st.session_state["lead_detail_selected_id"] = previous_lead_id
                    st.session_state["lead_queue_selected_id"] = previous_lead_id
                    st.rerun()
            with nav_col3:
                selected_lead_id = st.selectbox(
                    "Lead in current queue",
                    options=available_queue_ids,
                    index=queue_index,
                    format_func=lambda item: queue_lookup.get(item, all_lookup[item]),
                    key="lead_detail_selected_id",
                    on_change=_sync_detail_selected_lead,
                )
            with nav_col4:
                current_index = available_queue_ids.index(selected_lead_id)
                if st.button(
                    "Next in queue",
                    disabled=current_index >= len(available_queue_ids) - 1,
                    use_container_width=True,
                ):
                    next_lead_id = available_queue_ids[current_index + 1]
                    st.session_state["selected_lead_id"] = next_lead_id
                    st.session_state["lead_detail_selected_id"] = next_lead_id
                    st.session_state["lead_queue_selected_id"] = next_lead_id
                    st.rerun()
        lead = _fetch_lead_detail(selected_lead_id)

        if lead is None:
            _render_notice("Lead not found.", tone="danger", title="Missing record")
        else:
            _render_lead_workspace_header(
                lead,
                queue_label=st.session_state.get("lead_queue_label", "All loaded leads"),
                queue_position=available_queue_ids.index(selected_lead_id) + 1,
                queue_total=len(available_queue_ids),
            )
            _render_badges(
                [
                    (f"Status: {_humanize(lead.status)}", "info"),
                    (f"Source: {_humanize(lead.lead_source_type)}", "neutral"),
                    (f"Priority: {lead.lead_score}", "good" if lead.lead_score >= 70 else "warn"),
                    ("Do not contact", "danger") if lead.do_not_contact else ("Contactable", "good"),
                    (
                        f"Follow-up: {_format_date(lead.follow_up_date)}",
                        "warn" if _is_follow_up_due(lead) else "neutral",
                    ),
                ]
            )

            if lead.do_not_contact:
                _render_notice(
                    "Do not contact is active for this lead. Keep outreach blocked.",
                    tone="danger",
                    title="Outreach blocked",
                )
            else:
                _render_notice(_lead_next_step(lead), tone="info", title="Next best step")
            st.caption(
                "Use Review & Enrich for notes, status, follow-up, and public contact refreshes. "
                "Use Drafts for pt-BR outreach copy, and History & Sources for public-data history."
            )

            metric_cols = st.columns(4)
            metric_cols[0].metric("Priority score", lead.lead_score)
            metric_cols[1].metric("Contacts", len(lead.contacts))
            metric_cols[2].metric("Last enriched", _format_datetime(lead.last_enriched_at))
            metric_cols[3].metric("Last contacted", _format_datetime(lead.last_contacted_at))

            with st.container(border=True):
                st.markdown("### Operator focus")
                focus_col1, focus_col2, focus_col3 = st.columns(3, gap="large")
                with focus_col1:
                    _render_feature_card(
                        "Do now",
                        _lead_next_step(lead),
                        tone="info",
                        eyebrow="Next action",
                    )
                with focus_col2:
                    if lead.do_not_contact:
                        readiness_copy = "Outreach is blocked by do not contact. Keep work inside CRM review only."
                    elif _has_direct_channel(lead):
                        readiness_copy = f"Direct path available via {_contact_summary(lead)}. Use Drafts after CRM review."
                    elif _has_any_contact(lead):
                        readiness_copy = "Only phone is available. Run a public contact refresh or inspect the evidence before drafting."
                    else:
                        readiness_copy = "No usable contact channel is stored yet. A public contact refresh is the next best action."
                    _render_feature_card(
                        "Draft readiness",
                        readiness_copy,
                        tone="warn" if not _has_direct_channel(lead) or lead.do_not_contact else "good",
                        eyebrow="Channel state",
                    )
                with focus_col3:
                    _render_feature_card(
                        "Evidence trail",
                        (
                            f"{len(lead.contacts)} contact record(s), {len(lead.enrichments)} enrichment run(s), "
                            f"and {len(lead.activity_logs)} activity log item(s) are stored."
                        ),
                        tone="good",
                        eyebrow="Stored evidence",
                        meta="Use History & Sources to confirm provenance before outreach decisions.",
                    )

            detail_section = st.radio(
                "Workspace section",
                DETAIL_SECTION_OPTIONS,
                horizontal=True,
                key="lead_detail_section",
            )

            if detail_section == DETAIL_SECTION_REVIEW:
                left_col, right_col = st.columns([1.1, 1.2], gap="large")

                with left_col:
                    with st.container(border=True):
                        st.markdown("### Contact snapshot")
                        _render_key_value_grid(
                            [
                                ("Email", lead.email),
                                ("Phone", lead.phone),
                                ("WhatsApp", lead.whatsapp),
                                ("Instagram", lead.instagram),
                                ("Website", lead.website),
                                ("Domain", lead.domain),
                            ]
                        )

                    with st.container(border=True):
                        st.markdown("### Lead snapshot")
                        _render_key_value_grid(
                            [
                                ("Category", lead.category),
                                ("Location", f"{_safe_text(lead.city)} / {_safe_text(lead.state)}"),
                                ("Neighborhood", lead.neighborhood),
                                ("Address", lead.address),
                                ("Postal code", lead.postal_code),
                                ("Owner", lead.owner),
                                ("Approved for send", lead.approved_for_send),
                                ("Created at", _format_datetime(lead.created_at)),
                                ("Updated at", _format_datetime(lead.updated_at)),
                            ]
                        )

                    with st.container(border=True):
                        st.markdown("### Links and source record")
                        link_col1, link_col2, link_col3 = st.columns(3)
                        with link_col1:
                            if lead.website:
                                st.link_button("Website", lead.website, use_container_width=True)
                        with link_col2:
                            if lead.google_maps_url:
                                st.link_button("Google Maps", lead.google_maps_url, use_container_width=True)
                        with link_col3:
                            if lead.source_url:
                                st.link_button("Source URL", lead.source_url, use_container_width=True)
                        _render_key_value_grid(
                            [
                                ("Source provider", lead.source_provider),
                                ("Google Place ID", lead.google_place_id),
                            ]
                        )
                        if lead.is_duplicate:
                            st.warning(
                                f"Marked as duplicate of lead `{lead.duplicate_of_lead_id}`. "
                                f"Reason: `{lead.duplicate_reason or '-'}`"
                            )

                with right_col:
                    with st.container(border=True):
                        st.markdown("### Review & enrich actions")
                        st.caption("Use the public contact refresh here to pull more public contact evidence into this saved lead.")
                        action_col1, action_col2 = st.columns(2)
                        with action_col1:
                            if st.button("Find more public contact info", type="primary", use_container_width=True):
                                with st.spinner("Refreshing public contact info..."):
                                    result = _enrich_lead(lead.id)
                                st.session_state["queue_action_context"] = {
                                    "lead_id": lead.id,
                                    "lead_name": lead.business_name,
                                    "action": "the public contact refresh",
                                }
                                _set_flash(
                                    "Lead Detail",
                                    (
                                        f"Public contact refresh complete for {lead.business_name}. "
                                        f"Pages fetched: {result.pages_fetched}. Contacts added: {result.contacts_added}."
                                    ),
                                )
                                st.rerun()
                        with action_col2:
                            _render_key_value_grid(
                                [
                                    ("Follow-up date", _format_date(lead.follow_up_date)),
                                    ("Best contact path", _contact_summary(lead)),
                                ]
                            )

                    with st.container(border=True):
                        st.markdown("### Review and CRM fields")
                        with st.form("lead_update_form"):
                            lead_status_value = _normalize_enumish(lead.status) or LeadStatus.NEW.value
                            status_options = [item.value for item in LeadStatus]
                            form_col1, form_col2 = st.columns(2)
                            with form_col1:
                                status = st.selectbox(
                                    "Pipeline status",
                                    options=status_options,
                                    index=_option_index(status_options, lead_status_value),
                                    format_func=_humanize,
                                )
                                tags_text = st.text_input(
                                    "Tags (comma separated)",
                                    value=", ".join(lead.tags),
                                    placeholder="prioridade_alta, baterias, inbound",
                                )
                            with form_col2:
                                use_follow_up_date = st.checkbox(
                                    "Set follow-up date",
                                    value=lead.follow_up_date is not None,
                                )
                                follow_up_date = st.date_input(
                                    "Follow-up date",
                                    value=lead.follow_up_date or date.today(),
                                    disabled=not use_follow_up_date,
                                )
                                do_not_contact_value = st.checkbox(
                                    "Do not contact",
                                    value=lead.do_not_contact,
                                )
                            notes = st.text_area(
                                "Operator notes",
                                value=lead.notes or "",
                                height=220,
                                placeholder="Capture review context, public evidence notes, and next actions...",
                            )
                            st.caption(
                                "If do not contact is enabled, the status is automatically moved to Do Not Contact."
                            )
                            submitted = st.form_submit_button("Save lead changes", type="primary")

                        if submitted:
                            updated = _update_lead(
                                lead.id,
                                LeadUpdateRequest(
                                    status=LeadStatus(status),
                                    notes=notes,
                                    tags=normalize_tags(
                                        [item.strip() for item in tags_text.split(",") if item.strip()]
                                    ),
                                    follow_up_date=follow_up_date if use_follow_up_date else None,
                                    do_not_contact=do_not_contact_value,
                                ),
                            )
                            st.session_state["queue_action_context"] = {
                                "lead_id": updated.id,
                                "lead_name": updated.business_name,
                                "action": "the CRM update",
                            }
                            _set_flash("Lead Detail", f"Lead {updated.id} updated.")
                            st.rerun()

                    with st.container(border=True):
                        st.markdown("### Priority score details")
                        st.caption(
                            "Priority score helps rank review order. It is a decision aid, not an automatic approval or sending rule."
                        )
                        material_rows = _material_rows(lead.material_profile)
                        score_rows = _score_rows(lead.score_breakdown)
                        if material_rows:
                            st.markdown("#### Relevance signals")
                            st.dataframe(
                                pd.DataFrame(material_rows),
                                use_container_width=True,
                                hide_index=True,
                                height=_table_height(len(material_rows), max_height=360),
                                column_config={
                                    "Relevant": st.column_config.CheckboxColumn("Relevant"),
                                    "Confidence": st.column_config.NumberColumn(
                                        "Confidence", min_value=0.0, max_value=1.0, format="%.2f"
                                    ),
                                },
                            )
                        else:
                            st.info("No material profile stored yet.")
                        if score_rows:
                            st.markdown("#### Score breakdown")
                            st.dataframe(
                                pd.DataFrame(score_rows),
                                use_container_width=True,
                                hide_index=True,
                                height=_table_height(len(score_rows), max_height=320),
                                column_config={
                                    "Points": st.column_config.NumberColumn("Points", format="%d"),
                                },
                            )

            if detail_section == DETAIL_SECTION_DRAFTS:
                st.info(
                    "Draft generation uses the stored templates and public lead data only. "
                    "Sending stays disabled unless the configured sending controls are enabled."
                )
                if not _has_direct_channel(lead):
                    st.warning(
                        "No email or WhatsApp is stored for this lead yet. Review the contact snapshot "
                        "or run a public contact refresh before relying on channel-specific draft work."
                    )
                st.caption(
                    "Choose a template, preview the copy against the current lead data, then save a draft record when it looks right."
                )

                templates = _list_templates()
                template_options = {
                    _normalize_enumish(template.key) or TemplateKey.COLD_EMAIL.value: template
                    for template in templates
                }
                template_keys = list(template_options.keys())
                if not template_keys:
                    st.warning("No templates are configured yet, so draft generation is unavailable.")
                else:
                    default_template_key = _default_template_key_for_lead(lead, template_keys)
                    selected_template_key = st.selectbox(
                        "Template",
                        options=template_keys,
                        index=_option_index(template_keys, default_template_key),
                        format_func=lambda item: template_options[item].name,
                    )
                    template = template_options[selected_template_key]
                    _render_badges(
                        [
                            (f"Suggested template: {template.name}", "info"),
                            (
                                f"Channel: {_humanize(template.channel)}",
                                "good" if _has_direct_channel(lead) else "warn",
                            ),
                        ]
                    )

                    preview_col, generate_col = st.columns(2)
                    with preview_col:
                        if st.button("Preview draft copy", use_container_width=True):
                            preview = _preview_draft(lead.id, TemplateKey(selected_template_key))
                            st.session_state[f"draft_preview_{lead.id}_{selected_template_key}"] = preview.model_dump(
                                mode="json"
                            )
                    with generate_col:
                        if st.button("Generate draft record", use_container_width=True):
                            _generate_draft(lead.id, TemplateKey(selected_template_key))
                            _set_flash("Lead Detail", "Draft generated.")
                            st.rerun()

                    preview_payload = st.session_state.get(f"draft_preview_{lead.id}_{selected_template_key}")
                    if preview_payload:
                        with st.container(border=True):
                            st.markdown("### Draft preview")
                            if preview_payload.get("subject"):
                                st.code(preview_payload["subject"], language="text")
                            st.code(preview_payload["body"], language="text")

                drafts = _list_drafts(lead.id)
                if drafts:
                    st.markdown("### Saved drafts")
                    st.dataframe(
                        pd.DataFrame(_draft_rows(drafts)),
                        use_container_width=True,
                        hide_index=True,
                        height=_table_height(len(drafts), max_height=420),
                        column_config={
                            "Created": st.column_config.DatetimeColumn("Created"),
                        },
                    )
                    with st.expander("Inspect saved draft bodies", expanded=False):
                        draft_ids = [draft.id for draft in drafts]
                        selected_draft_id = st.selectbox(
                            "Draft record",
                            options=draft_ids,
                            format_func=lambda item: next(
                                (
                                    f"Draft #{draft.id} | {_humanize(draft.draft_type)} | {_humanize(draft.status)}"
                                    for draft in drafts
                                    if draft.id == item
                                ),
                                str(item),
                            ),
                            key=f"draft_body_{lead.id}",
                        )
                        selected_draft = next(draft for draft in drafts if draft.id == selected_draft_id)
                        if selected_draft.subject:
                            st.code(selected_draft.subject, language="text")
                        st.code(selected_draft.body, language="text")
                else:
                    st.info("No drafts generated yet.")

            if detail_section == DETAIL_SECTION_HISTORY:
                raw_records = _list_raw_records(lead.id)
                evidence_metrics = st.columns(4)
                evidence_metrics[0].metric("Contacts", len(lead.contacts))
                evidence_metrics[1].metric("Activities", len(lead.activity_logs))
                evidence_metrics[2].metric("Enrichments", len(lead.enrichments))
                evidence_metrics[3].metric("Raw records", len(raw_records))
                top_col1, top_col2 = st.columns(2, gap="large")

                with top_col1:
                    st.markdown("### Contact evidence")
                    if lead.contacts:
                        st.dataframe(
                            pd.DataFrame(_contact_rows(lead)),
                            use_container_width=True,
                            hide_index=True,
                            height=_table_height(len(lead.contacts), max_height=420),
                            column_config={
                                "Primary": st.column_config.CheckboxColumn("Primary"),
                                "Confidence": st.column_config.NumberColumn(
                                    "Confidence", min_value=0.0, max_value=1.0, format="%.2f"
                                ),
                                "Updated": st.column_config.DatetimeColumn("Updated"),
                            },
                        )
                    else:
                        st.info("No contact evidence stored yet.")

                with top_col2:
                    st.markdown("### Activity log")
                    if lead.activity_logs:
                        st.dataframe(
                            pd.DataFrame(_activity_rows(lead)),
                            use_container_width=True,
                            hide_index=True,
                            height=_table_height(len(lead.activity_logs), max_height=420),
                            column_config={
                                "When": st.column_config.DatetimeColumn("When"),
                            },
                        )
                    else:
                        st.info("No activity logged yet.")

                st.markdown("### Public contact refresh history")
                if lead.enrichments:
                    st.dataframe(
                        pd.DataFrame(_enrichment_rows(lead)),
                        use_container_width=True,
                        hide_index=True,
                        height=_table_height(len(lead.enrichments), max_height=420),
                        column_config={
                            "Fetched": st.column_config.DatetimeColumn("Fetched"),
                            "Robots allowed": st.column_config.CheckboxColumn("Robots allowed"),
                        },
                    )
                else:
                    st.info("No public contact refresh history yet.")

                st.markdown("### Raw discovery history")
                if raw_records:
                    st.dataframe(
                        pd.DataFrame(_raw_record_rows(raw_records)),
                        use_container_width=True,
                        hide_index=True,
                        height=_table_height(len(raw_records), max_height=420),
                        column_config={
                            "Discovered": st.column_config.DatetimeColumn("Discovered"),
                        },
                    )
                    with st.expander("Inspect raw discovery payloads", expanded=False):
                        raw_record_ids = [record["id"] for record in raw_records]
                        selected_raw_record_id = st.selectbox(
                            "Discovery record",
                            options=raw_record_ids,
                            format_func=lambda item: next(
                                (
                                    f"Record #{record['id']} | {record['provider']} | batch {record['import_batch_id']}"
                                    for record in raw_records
                                    if record["id"] == item
                                ),
                                str(item),
                            ),
                            key=f"raw_payload_{lead.id}",
                        )
                        selected_raw_record = next(
                            record for record in raw_records if record["id"] == selected_raw_record_id
                        )
                        st.json(selected_raw_record["payload_json"], expanded=False)
                else:
                    st.info("No raw discovery records linked yet.")
