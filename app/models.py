import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Enum, DateTime, ForeignKey, UniqueConstraint, Text
)
from sqlalchemy.orm import declarative_base, relationship
from .extensions import db

# Using Flask-SQLAlchemy's declarative base
Base = db.Model

class OrderStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    PAID = "PAID"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"
    CANCELED = "CANCELED"

class PaymentStatus(str, enum.Enum):
    REQUIRES_PAYMENT_METHOD = "REQUIRES_PAYMENT_METHOD"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    CANCELED = "CANCELED"
    REQUIRES_ACTION = "REQUIRES_ACTION"

class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    external_ref = Column(String, nullable=True)
    currency = Column(String(3), nullable=False)
    amount_due = Column(Integer, nullable=False)
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.DRAFT)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    payments = relationship("Payment", back_populates="order", lazy="selectin")

class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=True)
    stripe_payment_intent_id = Column(String, unique=True, nullable=False)
    stripe_charge_id = Column(String, unique=True, nullable=True)
    stripe_customer_id = Column(String, nullable=True)

    amount_received = Column(Integer, nullable=False, default=0)
    currency = Column(String(3), nullable=False)
    status = Column(Enum(PaymentStatus), nullable=False)
    method_type = Column(String, nullable=True)
    card_brand = Column(String, nullable=True)
    card_last4 = Column(String(4), nullable=True)
    card_exp_month = Column(Integer, nullable=True)
    card_exp_year = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    order = relationship(
        "Order", 
        back_populates="payments", 
        lazy="joined"
    )
    events = relationship(
        "PaymentEvent",
        back_populates="payment",
        lazy="selectin",   # load related events efficiently
        cascade="all, delete-orphan"  # if payment is deleted, events go too
    )


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id = Column(String, primary_key=True)
    stripe_event_id = Column(String, unique=True, nullable=False)
    type = Column(String, nullable=False)
    payload = Column(Text, nullable=True)  # JSON string for cross-DB compatibility
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    payment_id = Column(String, ForeignKey("payments.id"), nullable=True)
    payment = relationship(
        "Payment", 
        back_populates="events"
        )