"""Payments microservice - Extract from Commerce bounded context.

This microservice handles all payment processing and transactions.
It communicates with the monolith via async events (RabbitMQ/Kafka).

Architecture:
- Standalone database (PostgreSQL)
- FastAPI for REST endpoints
- AsyncIO for event consumption
- Event schemas shared with monolith
"""

from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, validator


# ============================================================================
# Domain Models
# ============================================================================

class PaymentStatus(str, Enum):
    """Status of a payment."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    """Supported payment methods."""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PAYPAL = "paypal"
    BANK_TRANSFER = "bank_transfer"


class Transaction(BaseModel):
    """A financial transaction record."""
    id: Optional[int] = None
    payment_id: int
    user_id: int
    amount: Decimal
    currency: str = "USD"
    status: PaymentStatus = PaymentStatus.PENDING
    payment_method: PaymentMethod
    transaction_id: Optional[str] = None  # External processor ID
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @validator('amount')
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        return v
    
    class Config:
        use_enum_values = True


class Payment(BaseModel):
    """A payment record."""
    id: Optional[int] = None
    user_id: int
    product_id: int
    amount: Decimal
    currency: str = "USD"
    status: PaymentStatus = PaymentStatus.PENDING
    payment_method: PaymentMethod
    order_id: Optional[str] = None  # Reference to monolith order
    idempotency_key: str  # For deduplication
    retry_count: int = 0
    max_retries: int = 3
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @validator('amount')
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        return v
    
    class Config:
        use_enum_values = True


class Refund(BaseModel):
    """A refund record."""
    id: Optional[int] = None
    payment_id: int
    user_id: int
    amount: Decimal
    reason: str
    status: PaymentStatus = PaymentStatus.PENDING
    refund_id: Optional[str] = None  # External processor ID
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True


# ============================================================================
# API Schemas (Request/Response)
# ============================================================================

class CreatePaymentRequest(BaseModel):
    """Request to create a payment."""
    user_id: int
    product_id: int
    amount: Decimal
    currency: str = "USD"
    payment_method: PaymentMethod
    order_id: Optional[str] = None
    idempotency_key: str = Field(..., description="Unique key for deduplication")


class PaymentResponse(BaseModel):
    """Response containing payment details."""
    id: int
    user_id: int
    product_id: int
    amount: Decimal
    currency: str
    status: PaymentStatus
    payment_method: PaymentMethod
    created_at: datetime
    updated_at: datetime


class RefundRequest(BaseModel):
    """Request to refund a payment."""
    payment_id: int
    reason: str


class RefundResponse(BaseModel):
    """Response containing refund details."""
    id: int
    payment_id: int
    amount: Decimal
    status: PaymentStatus
    created_at: datetime


# ============================================================================
# Event Schemas (shared with monolith)
# ============================================================================

class ProductPurchasedEvent(BaseModel):
    """Event published by monolith when product is purchased."""
    event_type: str = "product.purchased"
    aggregate_id: int
    user_id: int
    product_id: int
    total_paid: Decimal
    timestamp: datetime


class PaymentProcessedEvent(BaseModel):
    """Event published by payments service when payment completes."""
    event_type: str = "payment.processed"
    aggregate_id: int
    payment_id: int
    user_id: int
    product_id: int
    amount: Decimal
    status: PaymentStatus
    timestamp: datetime


class PaymentFailedEvent(BaseModel):
    """Event published by payments service when payment fails."""
    event_type: str = "payment.failed"
    aggregate_id: int
    payment_id: int
    user_id: int
    reason: str
    timestamp: datetime


class RefundProcessedEvent(BaseModel):
    """Event published by payments service when refund completes."""
    event_type: str = "refund.processed"
    aggregate_id: int
    refund_id: int
    payment_id: int
    user_id: int
    amount: Decimal
    timestamp: datetime


# ============================================================================
# Service Contract (Payments Processing)
# ============================================================================

class PaymentProcessor:
    """Contract for payment processing (implement with Stripe, Square, etc.)."""
    
    async def charge(
        self,
        payment_id: int,
        amount: Decimal,
        currency: str,
        payment_method: PaymentMethod,
        idempotency_key: str,
    ) -> dict:
        """
        Process a charge against a payment method.
        
        Returns:
            {
                'success': bool,
                'transaction_id': str (if successful),
                'error': str (if failed),
            }
        """
        raise NotImplementedError
    
    async def refund(
        self,
        transaction_id: str,
        amount: Decimal,
    ) -> dict:
        """
        Process a refund.
        
        Returns:
            {
                'success': bool,
                'refund_id': str (if successful),
                'error': str (if failed),
            }
        """
        raise NotImplementedError


# ============================================================================
# Saga for Payment Processing
# ============================================================================

class PaymentProcessingSaga:
    """Orchestrates payment processing workflow with retries and compensation."""
    
    async def process_payment(
        self,
        payment: Payment,
        processor: PaymentProcessor,
    ) -> PaymentProcessedEvent:
        """
        Process a payment with retries and error handling.
        
        Saga Steps:
        1. Validate payment data
        2. Charge payment method
        3. Create transaction record
        4. Publish PaymentProcessedEvent
        5. On failure: retry up to max_retries, then publish PaymentFailedEvent
        """
        try:
            # Step 1: Validate payment
            if payment.status != PaymentStatus.PENDING:
                raise ValueError(f"Payment already {payment.status}")
            
            payment.status = PaymentStatus.PROCESSING
            
            # Step 2: Charge via external processor
            result = await processor.charge(
                payment_id=payment.id,
                amount=payment.amount,
                currency=payment.currency,
                payment_method=payment.payment_method,
                idempotency_key=payment.idempotency_key,
            )
            
            if not result['success']:
                payment.retry_count += 1
                if payment.retry_count >= payment.max_retries:
                    payment.status = PaymentStatus.FAILED
                    return PaymentFailedEvent(
                        aggregate_id=payment.id,
                        payment_id=payment.id,
                        user_id=payment.user_id,
                        reason=result.get('error', 'Payment processing failed'),
                        timestamp=datetime.utcnow(),
                    )
                # Retry: status remains PROCESSING
                raise Exception(f"Charge failed: {result.get('error')}")
            
            # Step 3: Create transaction record
            transaction = Transaction(
                payment_id=payment.id,
                user_id=payment.user_id,
                amount=payment.amount,
                currency=payment.currency,
                status=PaymentStatus.COMPLETED,
                payment_method=payment.payment_method,
                transaction_id=result['transaction_id'],
            )
            
            # Step 4: Mark payment as complete
            payment.status = PaymentStatus.COMPLETED
            payment.updated_at = datetime.utcnow()
            
            # Step 5: Emit event
            return PaymentProcessedEvent(
                aggregate_id=payment.id,
                payment_id=payment.id,
                user_id=payment.user_id,
                product_id=payment.product_id,
                amount=payment.amount,
                status=PaymentStatus.COMPLETED,
                timestamp=datetime.utcnow(),
            )
        
        except Exception as e:
            payment.status = PaymentStatus.FAILED
            return PaymentFailedEvent(
                aggregate_id=payment.id,
                payment_id=payment.id,
                user_id=payment.user_id,
                reason=str(e),
                timestamp=datetime.utcnow(),
            )
    
    async def process_refund(
        self,
        refund: Refund,
        transaction_id: str,
        processor: PaymentProcessor,
    ) -> RefundProcessedEvent:
        """
        Process a refund for a completed payment.
        """
        try:
            result = await processor.refund(
                transaction_id=transaction_id,
                amount=refund.amount,
            )
            
            if not result['success']:
                refund.status = PaymentStatus.FAILED
                raise Exception(result.get('error', 'Refund failed'))
            
            refund.status = PaymentStatus.COMPLETED
            refund.refund_id = result['refund_id']
            refund.completed_at = datetime.utcnow()
            
            return RefundProcessedEvent(
                aggregate_id=refund.id,
                refund_id=refund.id,
                payment_id=refund.payment_id,
                user_id=refund.user_id,
                amount=refund.amount,
                timestamp=datetime.utcnow(),
            )
        
        except Exception as e:
            refund.status = PaymentStatus.FAILED
            raise
