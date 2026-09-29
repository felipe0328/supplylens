from supplylens.database.database import Base
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
