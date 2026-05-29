from pydantic import BaseModel, Field

# --- AI outputs ---
class VisionTagResult(BaseModel):
    tags: list[str]
    detailed_description: str

class DiscrepancyItem(BaseModel):
    issue_title: str
    evidence_description: str
    suggested_action: str
    related_image_url: str

class AmbiguityAlertItem(BaseModel):
    original_text: str
    risk_analysis: str
    recommended_phrasing: str

class SafetyEquipmentItem(BaseModel):
    equipment_name: str
    reason: str

class AuditReportSchema(BaseModel):
    discrepancies: list[DiscrepancyItem] = Field(default_factory=list)
    ambiguity_alerts: list[AmbiguityAlertItem] = Field(default_factory=list)
    safety_equipment_recommendations: list[SafetyEquipmentItem] = Field(default_factory=list)

# --- API requests ---
class IndexRequest(BaseModel):
    project_id: str
    image_urls: list[str]

class AuditRequest(BaseModel):
    project_id: str
    scope_text: str

class ChatRequest(BaseModel):
    project_id: str
    user_question: str

# --- API responses ---
class IndexResponse(BaseModel):
    status: str = "success"
    message: str = "Bulk image indexing initiated in background."
    project_id: str
    job_id: str
    total_images: int

class StatusResponse(BaseModel):
    project_id: str
    job_id: str | None
    status: str
    total_images: int
    processed_images: int
    succeeded_images: int
    failed_images: int

class AuditResponse(BaseModel):
    project_id: str
    status: str = "completed"
    audit_report: AuditReportSchema

class ChatResponse(BaseModel):
    answer_text: str
    reference_image_urls: list[str]
