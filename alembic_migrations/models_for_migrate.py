"""
SQLAlchemy-модели ТОЛЬКО для Alembic (миграции).
Runtime продолжает использовать pg_db_utils/psycopg2; эти модели нигде не используются в коде.
Импорт из main.py после создания db, чтобы db.metadata содержал таблицы.
"""
from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Column, Date, Float, Integer, Numeric, Text
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import DateTime

# Импорт после создания db в main (при импорте этого модуля из main db уже есть)
from src.main import db  # noqa: I001


class UserService(db.Model):
    __tablename__ = "userservices"
    __table_args__ = {"extend_existing": True}
    id = Column(Text, primary_key=True)
    business_id = Column(Text, nullable=False)
    user_id = Column(Text, nullable=True)
    name = Column(Text, nullable=False)
    description = Column(Text)
    category = Column(Text)
    keywords = Column(JSONB)
    price = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


class FinancialTransaction(db.Model):
    __tablename__ = "financialtransactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('income', 'expense')",
            name="ck_financialtransactions_transaction_type",
        ),
        {"extend_existing": True},
    )
    id = Column(Text, primary_key=True)
    business_id = Column(Text, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    description = Column(Text)
    transaction_type = Column(Text, nullable=False)
    transaction_date = Column(Date, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class FinancialMetric(db.Model):
    __tablename__ = "financialmetrics"
    __table_args__ = {"extend_existing": True}
    id = Column(Text, primary_key=True)
    business_id = Column(Text, nullable=False)
    metric_name = Column(Text, nullable=False)
    metric_value = Column(Numeric(10, 2), nullable=False)
    period = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class Card(db.Model):
    __tablename__ = "cards"
    __table_args__ = {"extend_existing": True}
    id = Column(Text, primary_key=True)
    business_id = Column(Text, nullable=True)
    user_id = Column(Text, nullable=True)
    url = Column(Text)
    title = Column(Text)
    address = Column(Text)
    phone = Column(Text)
    site = Column(Text)
    rating = Column(Float)
    reviews_count = Column(Integer)
    categories = Column(Text)
    overview = Column(Text)
    products = Column(Text)
    news = Column(Text)
    photos = Column(Text)
    features_full = Column(Text)
    competitors = Column(Text)
    hours = Column(Text)
    hours_full = Column(Text)
    report_path = Column(Text)
    seo_score = Column(Integer)
    ai_analysis = Column(JSONB)
    recommendations = Column(JSONB)
    version = Column(Integer, default=1)
    is_latest = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


class ScreenshotAnalysis(db.Model):
    __tablename__ = "screenshot_analyses"
    __table_args__ = {"extend_existing": True}
    id = Column(Text, primary_key=True)
    business_id = Column(Text, nullable=False)
    screenshot_path = Column(Text)
    analysis_result = Column(JSONB)
    analysis_type = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
