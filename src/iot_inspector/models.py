from uuid import UUID
from pydantic import BaseModel


class Tenant(BaseModel):
    id: UUID
    name: str
