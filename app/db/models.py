import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.config import get_settings

DIM = get_settings().embedding_dim


class Base(DeclarativeBase):
    pass


class VisualIndex(Base):
    __tablename__ = "project_visual_indices"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), index=True)
    image_url: Mapped[str] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text))
    detailed_description: Mapped[str] = mapped_column(Text)
    embedding_vector: Mapped[list[float]] = mapped_column(Vector(DIM))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class AuditReport(Base):
    __tablename__ = "project_audit_reports"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), index=True)
    scope_text: Mapped[str] = mapped_column(Text)
    report_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class IndexJob(Base):
    __tablename__ = "project_index_jobs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    total_images: Mapped[int] = mapped_column(Integer, default=0)
    processed_images: Mapped[int] = mapped_column(Integer, default=0)
    succeeded_images: Mapped[int] = mapped_column(Integer, default=0)
    failed_images: Mapped[int] = mapped_column(Integer, default=0)
    error_log: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
