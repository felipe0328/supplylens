from datetime import datetime
from uuid import UUID, uuid7

from sqlalchemy import DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from supplylens.database.database import Base
from supplylens.domain.users import UserRole, UserStatus


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)

    email: Mapped[str] = mapped_column(nullable=False, unique=True)
    password_hash: Mapped[str]

    role: Mapped[UserRole] = mapped_column(default=UserRole.OPERATOR)
    status: Mapped[UserStatus] = mapped_column(default=UserStatus.PENDING)

    accepted_by: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )

    pending_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
