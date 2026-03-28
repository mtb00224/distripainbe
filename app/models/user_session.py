from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserSession(Base):
    """Tracks each login event with device info for usage analytics."""
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    livreur_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("livreurs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # user_type: 'livreur' | 'acolyte'
    user_type: Mapped[str] = mapped_column(String(20), nullable=False, default="livreur")
    # acolyte_id: set when an acolyte logs in
    acolyte_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # device_type: 'mobile', 'tablet', 'desktop'
    device_type: Mapped[str] = mapped_column(String(20), nullable=False, default="desktop")
    # platform: 'iOS', 'Android', 'Windows', 'macOS', 'Linux', 'unknown'
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    # browser: 'Chrome', 'Firefox', 'Safari', etc.
    browser: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    logged_in_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
