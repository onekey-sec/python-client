import datetime as dt
from uuid import UUID

from pydantic import BaseModel


class Tenant(BaseModel):
    id: UUID
    name: str


class FirmwareMetadata(BaseModel):
    name: str
    version: str | None = None
    release_date: dt.datetime | None = None
    notes: str | None = None
    vendor_name: str
    product_name: str
    product_category: str | None = None
    product_group_id: UUID
    analysis_configuration_id: UUID
