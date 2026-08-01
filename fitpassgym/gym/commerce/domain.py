"""Domain model for Commerce bounded context.

Handles products, promotions, and purchases with money value objects.
"""

from datetime import datetime, timedelta
from typing import Optional

from django.utils import timezone

from ..shared.domain import AggregateRoot, DomainEvent, InvariantViolation, Money


class ProductKind:
    """Enumeration of product types."""
    MEMBERSHIP = "membership"
    DAY_PASS = "day_pass"
    TRAINING_PACKAGE = "training_package"


class AccessScope:
    """Enumeration of access scopes."""
    NATIONAL = "national"
    LOCAL = "local"
    VIRTUAL = "virtual"


# Domain Events
class ProductPurchasedEvent(DomainEvent):
    """Published when a product is purchased."""
    
    def __init__(self, purchase_id: int, user_id: int, product_id: int,
                 original_price: Money, final_price: Money,
                 promotion_applied: Optional[str], timestamp: datetime):
        super().__init__(purchase_id, timestamp)
        self.user_id = user_id
        self.product_id = product_id
        self.original_price = original_price
        self.final_price = final_price
        self.promotion_applied = promotion_applied


class AccessActivatedEvent(DomainEvent):
    """Published when a purchase activates access."""
    
    def __init__(self, purchase_id: int, valid_until: datetime, 
                 initial_credits: int, timestamp: datetime):
        super().__init__(purchase_id, timestamp)
        self.valid_until = valid_until
        self.initial_credits = initial_credits


# Aggregate Roots
class PromotionAggregate(AggregateRoot):
    """Promotion with business invariants."""
    
    def __init__(self, promotion_id: int, code: str, percent_off: int,
                 starts_at: datetime, ends_at: datetime):
        super().__init__()
        
        # Invariants
        if not (0 <= percent_off <= 100):
            raise InvariantViolation("Percent off must be 0-100")
        if ends_at <= starts_at:
            raise InvariantViolation("Promotion end must be after start")
        
        self.promotion_id = promotion_id
        self.code = code
        self.percent_off = percent_off
        self.starts_at = starts_at
        self.ends_at = ends_at
    
    def is_active(self, at_time: Optional[datetime] = None) -> bool:
        """Check if promotion is currently valid."""
        now = at_time or timezone.now()
        return self.starts_at <= now <= self.ends_at
    
    def apply_discount(self, price: Money) -> Money:
        """Apply promotion discount to a price."""
        if not self.is_active():
            raise InvariantViolation("This promotion is not active")
        
        return price.apply_percent_discount(self.percent_off)


class ProductAggregate(AggregateRoot):
    """Product (membership, day pass, package) with business rules."""
    
    def __init__(self, product_id: int, name: str, kind: str,
                 access_scope: str, price: Money, duration_days: int,
                 session_credits: Optional[int] = None,
                 active: bool = True):
        super().__init__()
        
        # Invariants
        if duration_days < 1:
            raise InvariantViolation("Duration must be at least 1 day")
        if session_credits is not None and session_credits < 0:
            raise InvariantViolation("Session credits cannot be negative")
        
        self.product_id = product_id
        self.name = name
        self.kind = kind
        self.access_scope = access_scope
        self.price = price
        self.duration_days = duration_days
        self.session_credits = session_credits or 0
        self.active = active
    
    def can_be_purchased(self) -> bool:
        """Check if product can be purchased."""
        return self.active


class PurchaseAggregate(AggregateRoot):
    """Purchase order aggregate with payment and access lifecycle."""
    
    def __init__(self, purchase_id: int, user_id: int, product: ProductAggregate,
                 amount: Money, valid_until: datetime, 
                 remaining_credits: int = 0, purchased_at: Optional[datetime] = None):
        super().__init__()
        
        # Invariants
        if amount.amount < 0:
            raise InvariantViolation("Amount cannot be negative")
        if remaining_credits < 0:
            raise InvariantViolation("Credits cannot be negative")
        
        self.purchase_id = purchase_id
        self.user_id = user_id
        self.product = product
        self.amount = amount
        self.valid_until = valid_until
        self.remaining_credits = remaining_credits
        self.purchased_at = purchased_at or timezone.now()
    
    def is_valid(self, at_time: Optional[datetime] = None) -> bool:
        """Check if purchase access is still valid."""
        now = at_time or timezone.now()
        return now <= self.valid_until
    
    def can_be_used_for_gym(self, gym_id: int) -> bool:
        """Check if purchase allows access to a specific gym.
        
        - National scope: allows any gym
        - Local scope: only the assigned gym
        - Virtual scope: no physical gym access
        """
        return self.product.access_scope == AccessScope.NATIONAL
    
    def consume_credit(self) -> None:
        """Consume one session credit for a check-in."""
        if self.remaining_credits <= 0:
            raise InvariantViolation("No session credits remaining")
        if not self.is_valid():
            raise InvariantViolation("Purchase has expired")
        
        self.remaining_credits -= 1
    
    def is_day_pass(self) -> bool:
        """Check if this is a day pass."""
        return self.product.kind == ProductKind.DAY_PASS


# Domain Services
class CommerceService:
    """Domain service for commerce operations."""
    
    @staticmethod
    def apply_promotion(product: ProductAggregate, price: Money, 
                       promotion: Optional[PromotionAggregate]) -> Money:
        """Calculate final price after optional promotion.
        
        Args:
            product: The product being purchased
            price: The base price
            promotion: Optional promotion to apply
        
        Returns:
            Final price after discount (if promotion applied)
        """
        if promotion and promotion.is_active():
            return promotion.apply_discount(price)
        return price
    
    @staticmethod
    def create_purchase(user_id: int, product: ProductAggregate,
                       payment_amount: Money, 
                       promotion: Optional[PromotionAggregate] = None) -> PurchaseAggregate:
        """Create a purchase with optional promotion.
        
        Args:
            user_id: User making the purchase
            product: Product being purchased
            payment_amount: Amount paid
            promotion: Optional promotion to apply
        
        Returns:
            PurchaseAggregate ready to be persisted
        """
        if not product.can_be_purchased():
            raise InvariantViolation("This product cannot be purchased")
        
        # Calculate validity period
        valid_until = timezone.now() + timedelta(days=product.duration_days)
        
        # Create purchase
        purchase = PurchaseAggregate(
            purchase_id=None,  # Assigned by repository
            user_id=user_id,
            product=product,
            amount=payment_amount,
            valid_until=valid_until,
            remaining_credits=product.session_credits,
        )
        
        purchase.record_event(
            ProductPurchasedEvent(
                purchase.purchase_id,
                user_id,
                product.product_id,
                product.price,
                payment_amount,
                promotion.code if promotion else None,
                timezone.now()
            )
        )
        
        purchase.record_event(
            AccessActivatedEvent(
                purchase.purchase_id,
                valid_until,
                product.session_credits,
                timezone.now()
            )
        )
        
        return purchase
