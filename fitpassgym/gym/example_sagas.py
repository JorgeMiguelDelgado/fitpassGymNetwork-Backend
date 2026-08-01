"""Example sagas for FitPass Gym workflows.

These sagas demonstrate how to orchestrate multi-step business processes
with automatic compensation on failure.
"""

from decimal import Decimal
from django.utils import timezone

from fitpassgym.gym.shared.sagas import SagaBuilder
from fitpassgym.gym.shared.domain import Money
from fitpassgym.gym.scheduling.models import Booking, FitnessClass
from fitpassgym.gym.commerce.models import Purchase, Product
from fitpassgym.gym.access.models import CheckIn, Gym
from django.contrib.auth import get_user_model


User = get_user_model()


def create_booking_with_payment_saga():
    """Create a saga for booking a class with payment.
    
    Steps:
    1. Reserve spot in fitness class (compensate by releasing spot)
    2. Process payment (compensate by refunding)
    3. Create check-in access (compensate by removing access)
    
    If any step fails, previous steps are compensated automatically.
    """
    
    def reserve_spot_action(context, results):
        """Reserve a spot in the fitness class."""
        user = context['user']
        class_id = context['class_id']
        
        fitness_class = FitnessClass.objects.select_for_update().get(pk=class_id)
        
        if fitness_class.current_capacity >= fitness_class.capacity:
            raise ValueError("Class is at full capacity")
        
        booking = Booking.objects.create(
            user=user,
            fitness_class=fitness_class,
            status=Booking.Status.CONFIRMED,
        )
        
        # Update capacity
        fitness_class.current_capacity += 1
        fitness_class.save(update_fields=['current_capacity'])
        
        return {"booking_id": booking.id}
    
    def reserve_spot_compensation(context, result):
        """Release the reserved spot."""
        booking = Booking.objects.get(pk=result['booking_id'])
        fitness_class = booking.fitness_class
        
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=['status'])
        
        fitness_class.current_capacity -= 1
        fitness_class.save(update_fields=['current_capacity'])
    
    def process_payment_action(context, results):
        """Process payment for the booking."""
        user = context['user']
        amount = context.get('amount', Decimal('50.00'))
        
        # In a real system, this would call a payment processor
        # For now, we'll just simulate creating a purchase record
        product = Product.objects.first()  # Get any available product
        if not product:
            raise ValueError("No products available")
        
        purchase = Purchase.objects.create(
            user=user,
            product=product,
            total_paid=Money(amount, "USD").amount,
        )
        
        return {"purchase_id": purchase.id, "amount": str(amount)}
    
    def process_payment_compensation(context, result):
        """Refund the payment."""
        purchase = Purchase.objects.get(pk=result['purchase_id'])
        # Mark purchase as refunded (in real system, call payment processor)
        purchase.delete()
    
    def create_access_action(context, results):
        """Create access record for gym."""
        user = context['user']
        gym_id = context.get('gym_id')
        
        if not gym_id:
            raise ValueError("gym_id is required")
        
        gym = Gym.objects.get(pk=gym_id)
        checkin = CheckIn.objects.create(
            user=user,
            gym=gym,
        )
        
        return {"checkin_id": checkin.id}
    
    def create_access_compensation(context, result):
        """Remove access record."""
        checkin = CheckIn.objects.get(pk=result['checkin_id'])
        checkin.delete()
    
    saga = (
        SagaBuilder("booking_with_payment")
        .add_step(
            "reserve_spot",
            reserve_spot_action,
            reserve_spot_compensation,
        )
        .add_step(
            "process_payment",
            process_payment_action,
            process_payment_compensation,
        )
        .add_step(
            "create_access",
            create_access_action,
            create_access_compensation,
        )
        .build()
    )
    
    return saga


def create_transfer_between_classes_saga():
    """Create a saga for transferring a booking from one class to another.
    
    Steps:
    1. Cancel booking in original class
    2. Create booking in new class
    
    If step 2 fails, step 1 is compensated.
    """
    
    def cancel_original_booking_action(context, results):
        """Cancel the user's booking in the original class."""
        booking = Booking.objects.select_for_update().get(pk=context['booking_id'])
        
        if booking.status != Booking.Status.CONFIRMED:
            raise ValueError("Only confirmed bookings can be transferred")
        
        original_status = booking.status
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=['status'])
        
        # Release capacity
        booking.fitness_class.current_capacity -= 1
        booking.fitness_class.save(update_fields=['current_capacity'])
        
        return {
            "original_booking_id": booking.id,
            "original_status": original_status,
            "original_class_id": booking.fitness_class_id,
        }
    
    def cancel_original_booking_compensation(context, result):
        """Restore the original booking."""
        booking = Booking.objects.get(pk=result['original_booking_id'])
        booking.status = result['original_status']
        booking.save(update_fields=['status'])
        
        # Restore capacity
        fitness_class = booking.fitness_class
        fitness_class.current_capacity += 1
        fitness_class.save(update_fields=['current_capacity'])
    
    def book_new_class_action(context, results):
        """Create booking in new class."""
        user = context['user']
        new_class_id = context['new_class_id']
        
        new_fitness_class = FitnessClass.objects.select_for_update().get(pk=new_class_id)
        
        if new_fitness_class.current_capacity >= new_fitness_class.capacity:
            raise ValueError("New class is at full capacity")
        
        new_booking = Booking.objects.create(
            user=user,
            fitness_class=new_fitness_class,
            status=Booking.Status.CONFIRMED,
        )
        
        new_fitness_class.current_capacity += 1
        new_fitness_class.save(update_fields=['current_capacity'])
        
        return {"new_booking_id": new_booking.id}
    
    def book_new_class_compensation(context, result):
        """Cancel the new booking."""
        new_booking = Booking.objects.get(pk=result['new_booking_id'])
        new_booking.status = Booking.Status.CANCELLED
        new_booking.save(update_fields=['status'])
        
        new_booking.fitness_class.current_capacity -= 1
        new_booking.fitness_class.save(update_fields=['current_capacity'])
    
    saga = (
        SagaBuilder("transfer_between_classes")
        .add_step(
            "cancel_original_booking",
            cancel_original_booking_action,
            cancel_original_booking_compensation,
        )
        .add_step(
            "book_new_class",
            book_new_class_action,
            book_new_class_compensation,
        )
        .build()
    )
    
    return saga
