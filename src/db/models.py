from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class IssueMaster(Base):
    __tablename__ = "issue_master"
    __table_args__ = (
        UniqueConstraint("series_id", "sort_order", name="unique_series_release"),
    )

    master_issue_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # noqa: UP045
    issue_number: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    type: Mapped[str] = mapped_column(String(40), nullable=False, default="MAIN_RELEASE")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PRE_FOC")
    foc_date: Mapped[date] = mapped_column(Date, nullable=False)
    publisher: Mapped[str] = mapped_column(String(100), nullable=False, default="Unknown")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    variants: Mapped[list[IssueVariant]] = relationship(
        back_populates="master", cascade="all, delete-orphan"
    )


class IssueVariant(Base):
    __tablename__ = "issue_variants"

    variant_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    master_issue_id: Mapped[int] = mapped_column(
        ForeignKey("issue_master.master_issue_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    locg_issue_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    variant_type: Mapped[str] = mapped_column(String(50), nullable=False)
    cover_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # noqa: UP045
    retail_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)  # noqa: UP045
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # noqa: UP045
    current_pull_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    days_to_foc: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    master: Mapped[IssueMaster] = relationship(back_populates="variants")
    snapshots: Mapped[list[IssueSnapshot]] = relationship(
        back_populates="variant", cascade="all, delete-orphan"
    )
    velocity_flags: Mapped[Optional[IssueVelocityFlags]] = relationship(  # noqa: UP045
        back_populates="variant", uselist=False, cascade="all, delete-orphan"
    )


class IssueSnapshot(Base):
    __tablename__ = "issue_snapshots"

    # Integer PK keeps SQLite autoincrement working; Postgres schema uses BIGSERIAL.
    snapshot_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    locg_issue_id: Mapped[int] = mapped_column(
        ForeignKey("issue_variants.locg_issue_id", ondelete="CASCADE"),
        nullable=False,
    )
    pull_count: Mapped[int] = mapped_column(Integer, nullable=False)
    days_to_foc: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    variant: Mapped[IssueVariant] = relationship(back_populates="snapshots")


class IssueVelocityFlags(Base):
    __tablename__ = "issue_velocity_flags"

    locg_issue_id: Mapped[int] = mapped_column(
        ForeignKey("issue_variants.locg_issue_id", ondelete="CASCADE"),
        primary_key=True,
    )
    evaluation_mode: Mapped[str] = mapped_column(String(100), nullable=False)
    current_pull_count: Mapped[int] = mapped_column(Integer, nullable=False)
    net_growth_since_discovery: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delta_3d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    acceleration_3d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_early_breakout: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    demand_tier: Mapped[str] = mapped_column(
        String(50), nullable=False, default="UNFLAGGED"
    )
    velocity_state: Mapped[str] = mapped_column(String(50), nullable=False, default="STABLE")
    last_evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    variant: Mapped[IssueVariant] = relationship(back_populates="velocity_flags")
