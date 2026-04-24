from sqlalchemy import Boolean, String, Integer, Enum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
import enum
from datetime import datetime, timezone


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ADMIN_BOULANGERIE = "admin_boulangerie"
    STAFF_BOULANGERIE = "staff_boulangerie"
    LIVREUR = "livreur"
    ACOLYTE_LIVREUR = "acolyte_livreur"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    email: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # =====================
    # Relations Inverses
    # =====================
    admin_boulangerie_profile: Mapped["AdminBoulangerie"] = relationship(
        "AdminBoulangerie", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    livreur_profile: Mapped["Livreur"] = relationship(
        "Livreur", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    staff_positions: Mapped[list["StaffBoulangerie"]] = relationship(
        "StaffBoulangerie", back_populates="user",
        foreign_keys="StaffBoulangerie.user_id",
        cascade="all, delete-orphan",
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, __import__("sqlalchemy").ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    device_type: Mapped[str] = mapped_column(String(20), default="desktop")
    platform: Mapped[str] = mapped_column(String(50), default="unknown")
    browser: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    logged_in_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship("User")
