"""Data contract (F1/F2/D1). Published at /v1/contract (JSON Schema). Validated at the ingestion boundary."""
import json, time, uuid
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ecs.config import cfg
from ecs.obs import QUARANTINED


class Unit(str, Enum):
    kg = "kg"; pcs = "pcs"; set = "set"; litre = "litre"


class ClassifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    product_description: str = Field(min_length=10, max_length=500)
    materials: Optional[List[str]] = Field(default=None, max_length=10)
    destination_country: str = Field(pattern=r"^[A-Z]{2}$", description="ISO 3166-1 alpha-2, upper case")
    quantity: int = Field(ge=1, le=10_000_000)
    unit: Unit
    net_weight_kg: Optional[float] = Field(default=None, gt=0, le=1_000_000)
    declared_value_inr: float = Field(gt=0, le=1_000_000_000)

    @field_validator("product_description")
    @classmethod
    def _not_blank(cls, v):
        if not any(ch.isalpha() for ch in v):
            raise ValueError("must contain letters")
        return v.strip()

    @field_validator("materials")
    @classmethod
    def _materials(cls, v):
        if v is None:
            return v
        for m in v:
            if not (1 <= len(m) <= 40):
                raise ValueError("each material must be 1-40 chars")
        return v

    @model_validator(mode="after")
    def _cross(self):
        if self.unit == Unit.kg and self.net_weight_kg is not None and abs(self.net_weight_kg - self.quantity) > 1e-6:
            raise ValueError("unit is 'kg' so net_weight_kg must equal quantity when both are given")
        return self


def contract_schema():
    return ClassifyRequest.model_json_schema()


def validate(payload):
    """Returns (request_dict, None) or (None, [field errors])."""
    try:
        return ClassifyRequest.model_validate(payload).model_dump(mode="json"), None
    except ValidationError as e:
        return None, [{"field": ".".join(str(x) for x in err["loc"]) or "body", "error": err["msg"], "type": err["type"]}
                      for err in e.errors()]


def quarantine(payload, errors, reason="schema_validation"):
    """Store the rejected record with its field-level errors; do NOT discard (glossary: quarantine)."""
    import os
    rec = {"id": uuid.uuid4().hex[:12], "ts": time.time(), "reason": reason, "errors": errors, "payload": payload}
    os.makedirs(os.path.dirname(cfg.quarantine_path) or ".", exist_ok=True)
    with open(cfg.quarantine_path, "a") as f:
        f.write(json.dumps(rec, default=str) + "\n")
    QUARANTINED.labels(reason).inc()
    return rec["id"]
