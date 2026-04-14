from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.organization import Organization


DEFAULT_ORGANIZATION_SLUG = "default"
DEFAULT_ORGANIZATION_NAME = "Default Organization"


class OrganizationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_slug(self, slug: str) -> Organization | None:
        return self.db.execute(select(Organization).where(Organization.slug == slug)).scalar_one_or_none()

    def get_default(self) -> Organization | None:
        return self.get_by_slug(DEFAULT_ORGANIZATION_SLUG)

    def get_or_create_default(self) -> Organization:
        organization = self.get_default()
        if organization is not None:
            return organization

        organization = Organization(
            slug=DEFAULT_ORGANIZATION_SLUG,
            name=DEFAULT_ORGANIZATION_NAME,
            display_name=DEFAULT_ORGANIZATION_NAME,
        )
        self.db.add(organization)
        self.db.flush()
        return organization


def get_or_create_default_organization(db: Session) -> Organization:
    return OrganizationRepository(db).get_or_create_default()
