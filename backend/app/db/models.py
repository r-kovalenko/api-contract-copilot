from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (CheckConstraint("length(btrim(name)) > 0", name="ck_projects_name"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    contracts: Mapped[list["ApiContract"]] = relationship(
        back_populates="project", passive_deletes="all"
    )


class ApiContract(Base):
    __tablename__ = "api_contracts"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_contracts_project_version"),
        CheckConstraint("length(btrim(version)) > 0", name="ck_contracts_version"),
        CheckConstraint("openapi_version LIKE '3.%'", name="ck_contracts_openapi_version"),
        CheckConstraint(
            "jsonb_typeof(specification) = 'object'", name="ck_contracts_specification"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    version: Mapped[str] = mapped_column(String(100))
    openapi_version: Mapped[str] = mapped_column(String(20))
    specification: Mapped[dict[str, Any]] = mapped_column(JSONB)
    source_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    project: Mapped[Project] = relationship(back_populates="contracts")
