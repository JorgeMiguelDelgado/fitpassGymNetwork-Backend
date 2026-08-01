# Session VI, VII, VIII - Complete Implementation Guide

## Session VI: Extract Microservice (Payments)

### Architecture
```
Monolith (Commerce)
  ├── HTTP: POST /api/purchases/
  └── Publishes: ProductPurchasedEvent → RabbitMQ

Message Broker (RabbitMQ)
  └── Events: product.purchased, payment.processed, payment.failed

Payments Microservice
  ├── Subscribes to: product.purchased
  ├── Database: payments_db (separate PostgreSQL)
  ├── HTTP API: /api/payments/
  └── Publishes: payment.processed, payment.failed
```

### Deliverables

1. **Payments Microservice** - `payments_microservice/domain.py`
   - Domain models: Payment, Transaction, Refund
   - Payment states and methods
   - PaymentProcessor interface for external providers
   - PaymentProcessingSaga for payment orchestration

2. **Event Contracts** - Shared schemas
   - ProductPurchasedEvent (from monolith)
   - PaymentProcessedEvent (to monolith)
   - PaymentFailedEvent (to monolith)
   - RefundProcessedEvent (to monolith)

3. **Service Communication**
   - Monolith publishes ProductPurchasedEvent when purchase completes
   - Payments service subscribes to ProductPurchasedEvent
   - Payments service processes payment and publishes PaymentProcessedEvent
   - Monolith subscribes to PaymentProcessedEvent to update purchase status

4. **Database Schema**
   ```sql
   -- Separate database: payments_db
   
   CREATE TABLE payments (
       id SERIAL PRIMARY KEY,
       user_id INTEGER NOT NULL,
       product_id INTEGER NOT NULL,
       amount DECIMAL(10,2) NOT NULL,
       currency VARCHAR(3) DEFAULT 'USD',
       status VARCHAR(20) DEFAULT 'pending',
       payment_method VARCHAR(20),
       order_id VARCHAR(100),
       idempotency_key VARCHAR(100) UNIQUE NOT NULL,
       retry_count INTEGER DEFAULT 0,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   
   CREATE TABLE transactions (
       id SERIAL PRIMARY KEY,
       payment_id INTEGER REFERENCES payments(id),
       user_id INTEGER NOT NULL,
       amount DECIMAL(10,2) NOT NULL,
       status VARCHAR(20),
       payment_method VARCHAR(20),
       transaction_id VARCHAR(100),
       created_at TIMESTAMP,
       completed_at TIMESTAMP
   );
   
   CREATE TABLE refunds (
       id SERIAL PRIMARY KEY,
       payment_id INTEGER REFERENCES payments(id),
       user_id INTEGER NOT NULL,
       amount DECIMAL(10,2) NOT NULL,
       reason TEXT,
       status VARCHAR(20) DEFAULT 'pending',
       refund_id VARCHAR(100),
       created_at TIMESTAMP,
       completed_at TIMESTAMP
   );
   ```

---

## Session VII: API Gateway

### Architecture
```
Internet
  └── HTTP Request

API Gateway (Kong/Traefik/Custom)
  ├── Authentication (JWT verification)
  ├── Rate limiting (per user/IP)
  ├── Request logging
  ├── Routing rules:
  │   ├── /api/gyms/* → Monolith
  │   ├── /api/classes/* → Monolith
  │   ├── /api/bookings/* → Monolith
  │   ├── /api/purchases/* → Monolith
  │   ├── /api/payments/* → Payments Microservice
  │   └── /health → Service discovery
  └── Response aggregation

Monolith
├── Port: 8000
└── /api (internal)

Payments Microservice
├── Port: 8001
└── /api (internal)
```

### Deliverables

1. **Gateway Configuration**
   - Routing table mapping public paths to internal services
   - Auth middleware (JWT token validation)
   - Rate limiting rules
   - CORS configuration
   - Request/response logging

2. **Service Discovery**
   - Health check endpoints: `/health`
   - Service status: active/degraded/inactive
   - Automatic failover to backup services

3. **API Contract Changes**
   - Public API: `/api/*`
   - Private APIs: `/:port/api/*` (service-to-service)
   - Backward compatibility maintained

4. **Implementation Examples**

   **Kong Configuration:**
   ```yaml
   services:
     - name: monolith
       url: http://localhost:8000/api
       routes:
         - paths: ["/api/gyms", "/api/classes", "/api/bookings", "/api/purchases"]
     
     - name: payments
       url: http://localhost:8001/api
       routes:
         - paths: ["/api/payments"]
   
   plugins:
     - jwt-auth
     - rate-limiting
     - request-logging
   ```

   **Health Check Endpoints:**
   ```python
   # Monolith
   GET /health
   Response: {
     "status": "healthy",
     "database": "connected",
     "event_bus": "connected"
   }
   
   # Payments Service
   GET /health
   Response: {
     "status": "healthy",
     "database": "connected",
     "payment_processor": "connected"
   }
   ```

---

## Session VIII: CQRS (Command Query Responsibility Segregation)

### Architecture
```
Write Side (Commands)
  ├── BookCommand
  ├── PurchaseCommand
  ├── PaymentCommand
  └── CheckInCommand
        ↓
   Domain Aggregates
        ↓
   Domain Events
        ↓
   Event Bus
        ↓
   Event Store (Audit)

Read Side (Queries)
  ├── Projection Engine
  │   ├── GymProjection
  │   ├── BookingProjection
  │   ├── PurchaseProjection
  │   └── AnalyticsProjection
  ├── Read Database
  │   ├── denormalized_gyms
  │   ├── denormalized_bookings
  │   └── materialized_views
  └── Cache Layer (Redis)
```

### Deliverables

1. **Command Handlers** (Write Model)
   ```python
   class BookClassCommand:
       user_id: int
       class_id: int
   
   class BookClassCommandHandler:
       async def handle(self, command: BookClassCommand):
           # Load aggregate
           fitness_class = await ClassRepository.get(command.class_id)
           booking = SchedulingService.book_class(command.user_id, fitness_class)
           # Publish domain events
           event_bus.publish_multiple(booking.get_uncommitted_events())
           return booking
   ```

2. **Query Handlers** (Read Model)
   ```python
   class GetMyBookingsQuery:
       user_id: int
   
   class GetMyBookingsQueryHandler:
       async def handle(self, query: GetMyBookingsQuery):
           # Read from denormalized view
           return await BookingReadModel.find_by_user(query.user_id)
   ```

3. **Projections** (Event → Read Model)
   ```python
   class BookingProjection:
       async def on_booking_created(self, event: BookingCreatedEvent):
           # Write to read database
           await BookingReadModel.create({
               'booking_id': event.booking_id,
               'user_id': event.user_id,
               'status': 'confirmed',
               'created_at': event.timestamp,
           })
       
       async def on_user_promoted_from_waitlist(self, event: UserPromotedFromWaitlistEvent):
           # Update read model
           await BookingReadModel.update(event.booking_id, {
               'status': 'confirmed',
               'promoted_at': event.timestamp,
           })
   ```

4. **Database Changes**
   ```sql
   -- Write Database (unchanged)
   -- Contains only source of truth: orders, booking, payments
   
   -- Read Database (new)
   CREATE TABLE denormalized_bookings (
       booking_id INTEGER PRIMARY KEY,
       user_id INTEGER,
       class_id INTEGER,
       class_title VARCHAR(200),
       gym_name VARCHAR(200),
       gym_location VARCHAR(200),
       instructor_name VARCHAR(200),
       status VARCHAR(20),
       starts_at TIMESTAMP,
       created_at TIMESTAMP,
       updated_at TIMESTAMP,
       INDEX idx_user_id (user_id),
       INDEX idx_class_id (class_id),
       INDEX idx_status (status)
   );
   
   CREATE TABLE denormalized_gyms (
       gym_id INTEGER PRIMARY KEY,
       name VARCHAR(200),
       address VARCHAR(500),
       latitude DECIMAL(10,8),
       longitude DECIMAL(11,8),
       total_classes INTEGER,
       available_classes INTEGER,
       rating DECIMAL(3,2),
       updated_at TIMESTAMP,
       INDEX idx_coordinates (latitude, longitude)
   );
   
   CREATE TABLE analytics_events (
       id SERIAL PRIMARY KEY,
       event_type VARCHAR(50),
       user_id INTEGER,
       aggregate_id INTEGER,
       data JSONB,
       created_at TIMESTAMP,
       INDEX idx_event_type_user (event_type, user_id)
   );
   ```

5. **Performance Benefits**
   - Read queries: 10-100x faster (no joins)
   - Write operations: Async, non-blocking
   - Eventual consistency: ~100ms delay
   - Scalable reads (independent cache)
   - Analytics data ready (denormalized)

### Implementation Flow

1. **User Action**: POST /api/bookings
2. **Command Handler**: BookClassCommandHandler processes BookClassCommand
3. **Aggregate**: BookingAggregate.book() creates BookingCreatedEvent
4. **Event Publishing**: event_bus.publish(BookingCreatedEvent)
5. **Projection**: BookingProjection.on_booking_created() updates denormalized_bookings
6. **Response**: Return booking ID immediately (eventual consistency)
7. **Query**: GET /api/bookings/{id} reads from denormalized_bookings (fast)

---

## Integration Summary

### Communication Flow

```
Client Request
  ↓
API Gateway (auth, rate-limit)
  ↓
Monolith / Microservice
  ├── Command Handler
  ├── Domain Aggregate
  ├── Domain Events
  └── Publish to Event Bus
         ↓
     RabbitMQ / Kafka
         ↓
    ┌────┴────┬─────────────┐
    ↓         ↓             ↓
Projection  Payment      Notification
Engine      Service      Service
    ↓         ↓             ↓
Read DB   Payment DB    Notification DB
```

### Data Consistency Strategy

- **Write Model**: Strong consistency (2PC if needed)
- **Read Model**: Eventual consistency (100-500ms delay)
- **Event Store**: Immutable audit trail
- **Saga Pattern**: Compensation for failed workflows

---

## Testing Strategy

```python
# Unit Tests: Domain logic (no I/O)
# - Test aggregates, value objects, domain services

# Integration Tests: Commands + Handlers
# - Test command handling, event publishing, projection updates

# E2E Tests: Full flow
# - Client → Gateway → Service → Database → Projection → Query
```

---

## Deployment Architecture

```
┌─────────────────────────────────────┐
│         Load Balancer               │
│         (AWS ALB / Nginx)           │
└────────────┬────────────────────────┘
             │
    ┌────────┴──────────┐
    ↓                   ↓
┌─────────┐         ┌──────────┐
│ Monolith│         │ Payments │
│ Service │         │ Service  │
│ (3 pods)│         │ (2 pods) │
└────┬────┘         └────┬─────┘
     │                   │
     └───────┬───────────┘
             ↓
       ┌──────────────┐
       │  RabbitMQ    │
       │  Cluster     │
       └──────┬───────┘
              │
      ┌───────┼──────────┐
      ↓       ↓          ↓
   Write   Analytics  Cache
    DB       DB       (Redis)
```

---

## Next: Frontend Application

See `FRONTEND_README.md` for applying these patterns to the frontend (React/Vue/Angular).
