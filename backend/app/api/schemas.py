from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_MESSAGE_LENGTH = 12_000


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class MessageAnalysisRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("text")
    @classmethod
    def require_non_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message cannot be blank.")
        return value


class Finding(BaseModel):
    category: str
    explanation: str
    evidence: str
    page_number: int | None = None


class DocumentMetadata(BaseModel):
    page_count: int
    pages_with_text: int
    extraction_status: str
    size_bytes: int


class MessageAnalysisResponse(BaseModel):
    risk_level: RiskLevel
    findings: list[Finding]
    recommended_actions: list[str]
    disclaimer: str
    # Indicates which path actually produced the result; the UI must not infer this.
    analysis_type: str = "baseline_fallback"
    document_metadata: DocumentMetadata | None = None
