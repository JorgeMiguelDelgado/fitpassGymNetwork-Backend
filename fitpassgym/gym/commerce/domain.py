"""Commerce bounded context domain logic."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.utils import timezone

from fitpassgym.gym.shared.domain import (
    AggregateRoot,
    DomainEvent,
    InvariantViolation,
    Money,
)


@dataclass
class ProductPurchasedEvent(DomainEvent):
    """Event published when a product is purchased."""
    user_id: int
    product_id: int
    total_paid: Decimal


@dataclass
class AccessActivatedEvent(DomainEvent):
    """Event published when access is activated."""
    user_id: int
    product_id: int


class ProductAggregate(AggregateRoot):
    """Aggregate for gym products (passes, day passes, etc.)."""
    
    def __init__(
        self,
        product_id: int,
        name: str,
        price: Money,
        valid_days: int,
    ):
        super().__init__(product_id)
        self.name = name
        self._price = price
        self.valid_days = valid_days
    
    @property
    def price(self) -> Money:
        return self._price


class PromotionAggregate(AggregateRoot):
    """Aggregate for discount promotions."""
    
    def __init__(
        self,
        promotion_id: int,
        code: str,
        discount_percentage: Decimal,
    ):
        super().__init__(promotion_id)
        self.code = code
        self._discount_percentage = discount_percentage
        
        if discount_percentage < 0 or discount_percentage > 100:
            raise InvariantViolation("Discount percentage must be 0-100")
    
    @property
    def discount_percentage(self) -> Decimal:
        return self._discount_percentage
    
    def calculate_discount(self, amount: Money) -> Money:
        """Calculate discount amount for a given price."""
        discount_amount = amount.amount * (self._discount_percentage / 100)
        return Money(discount_amount, amount.currency)


class PurchaseAggregate(AggregateRoot):
    """Aggregate for purchase transactions."""
    
    def __init__(
        self,
        purchase_id: int,
        user_id: int,
        product_id: int,
        total_paid: Money,
        valid_until: datetime,
        credits_granted: Decimal = Decimal("0"),
    ):
        super().__init__(purchase_id)
        self.user_id = user_id
        self.product_id = product_id
        self._total_paid = total_paid
        self.valid_until = valid_until
        self._credits_granted = credits_granted
    
    @property
    def total_paid(self) -> Money:
        return self._total_paid
    
    @property
    def credits_granted(self) -> Decimal:
        return self._credits_granted
    
    def is_valid(self) -> bool:
        """Check if purchase is still valid."""
        return timezone.now() <= self.valid_until
    
    def consume_credit(self, amount: Decimal) -> None:
        """Consume credits from the purchase."""
        if amount > self._credits_granted:
            raise InvariantViolation("Insufficient credits")
        self._credits_granted -= amount


class CommerceService:
    """Service for commerce business logic (stateless domain service)."""
    
    @staticmethod
    def apply_promotion(
        product_price: Money,
        promotion: PromotionAggregate,
    ) -> Money:
        """Apply a promotion to a product price."""
        discount = promotion.calculate_discount(product_price)
        return product_price.subtract(discount)
    
    @staticmethod
    def create_purchase(
        user_id: int,
        product: ProductAggregate,
        promotion: PromotionAggregate = None,
    ) -> PurchaseAggregate:
        """
        Create a purchase with optional promotion.
        
        Returns a PurchaseAggregate.
        """
        price = product.price
        if promotion:
            price = CommerceService.apply_promotion(price, promotion)
        
        valid_until = timezone.now() + timezone.timedelta(days=product.valid_days)
        
        # For now, credits granted = price amount (simplified)
        purchase = PurchaseAggregate(
            purchase_id=None,  # Assigned by persistence layer
            user_id=user_id,
            product_id=product.id,
            total_paid=price,
            valid_until=valid_until,
            credits_granted=price.amount,
        )
        
        purchase.add_event(
            ProductPurchasedEvent(
                aggregate_id=None,  # Assigned by persistence layer
                user_id=user_id,
                product_id=product.id,
                total_paid=price.amount,
                timestamp=timezone.now(),
            )
        )
        
        return purchase
