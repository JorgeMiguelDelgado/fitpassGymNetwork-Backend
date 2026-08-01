# Session VIII - CQRS (Command Query Responsibility Segregation)
## Separate Read and Write Models for Scalability and Performance

### Overview

CQRS is an architectural pattern that separates the model used to **update information** (write model) from the model used to **read information** (read model).

```
┌─────────────────────────────────────────────────────────────────┐
│                         CQRS Pattern                            │
├──────────────────────────────────┬──────────────────────────────┤
│        WRITE SIDE (Commands)     │      READ SIDE (Queries)     │
├──────────────────────────────────┼──────────────────────────────┤
│ - Optimized for consistency      │ - Optimized for speed        │
│ - Normalized schema              │ - Denormalized views         │
│ - ACID transactions              │ - Eventually consistent      │
│ - Complex validation             │ - Read-optimized indexes     │
│ - Domain logic enforcement       │ - Caching layer              │
│                                  │ - In-memory reads            │
└──────────────────────────────────┴──────────────────────────────┘
        ↓                                        ↑
   Commands                              Queries
   (BookClass)                          (GetMyBookings)
        ↓                                        ↑
┌──────────────────────────────────────────────────────┐
│             Domain Events                           │
│ (BookingCreatedEvent, PaymentProcessedEvent, ...)   │
│                     ↓                                │
│          Event Projections (Handlers)               │
│    Update denormalized read models from events      │
└──────────────────────────────────────────────────────┘
```

### Benefits

| Aspect | Benefit |
|--------|---------|
| **Performance** | 10-100x faster queries (denormalized views, caching) |
| **Scalability** | Read and write scales independently |
| **Complexity** | Command side handles validation; query side focuses on speed |
| **Flexibility** | Multiple read models optimized for different use cases |
| **Auditability** | All changes traceable through events |
| **Consistency** | Eventual consistency → higher throughput |

### Components

#### 1. Write Side (Commands)

Commands represent **intentions to change state**:
```python
@dataclass
class BookClassCommand:
    booking_id: str
    user_id: str
    class_id: str
    gym_id: str
    timestamp: datetime
```

Command Handlers execute business logic and produce events:
```python
class BookClassCommandHandler:
    def handle(self, command: BookClassCommand) -> str:
        # Validate command
        # Load aggregate from repository
        # Execute business logic (produces events)
        # Publish events
        # Return result
        return booking_id
```

Write Model characteristics:
- **Normalized schema** (3NF or higher)
- **ACID transactions** for consistency
- **Complex validation** and business rules
- **Domain-driven design** patterns

#### 2. Read Side (Queries)

Queries ask for information without changing state:
```python
@dataclass
class GetMyBookingsQuery:
    user_id: str
    status: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
```

Query Handlers execute simple lookups:
```python
class GetMyBookingsQueryHandler:
    def handle(self, query: GetMyBookingsQuery) -> List[DenormalizedBooking]:
        # Simple SELECT from read model (very fast)
        # No joins (already denormalized)
        # No validation
        # Return denormalized data
        return bookings
```

Read Models (Denormalized Views):
```
┌──────────────────────────────────────────┐
│      denormalized_bookings               │
├──────────────────────────────────────────┤
│ booking_id         PK                    │
│ user_id            FK (indexed)          │
│ class_id           FK                    │
│ class_name         (from Class aggregate)│
│ gym_id             FK                    │
│ gym_name           (from Gym aggregate)  │
│ trainer_id         FK                    │
│ trainer_name       (from Trainer)        │
│ status             (indexed)             │
│ payment_status     (indexed)             │
│ price              (aggregated)          │
│ created_at         (indexed)             │
│ updated_at                               │
└──────────────────────────────────────────┘
```

#### 3. Event Projections

Event Handlers update read models from domain events:

```python
class BookingProjection(EventProjection):
    def project(self, event: BookingCreatedEvent) -> None:
        # When BookingCreatedEvent occurs:
        # 1. Load booking aggregate
        # 2. Join with class, gym, trainer data
        # 3. Denormalize all related data
        # 4. INSERT into denormalized_bookings
        
        booking_data = fetch_booking_with_relations(event.booking_id)
        self.db.insert('denormalized_bookings', booking_data)
```

Projections run **asynchronously** after events:
```
1. Command executed → Event published (100ms)
2. Event bus routes event to handlers
3. Projections update read models (50-200ms more)
4. Client queries read model (10ms) ← Usually happens after projection
```

#### 4. Consistency Management

**Eventual Consistency**: Read models lag behind write model by 100-500ms

```python
class ConsistencyManager:
    def get_consistency_guarantee(self) -> str:
        """
        IMMEDIATE:      0ms delay (strong consistency)
        DELAYED_100MS:  ~100ms delay (good for most UIs)
        DELAYED_500MS:  ~500ms delay (acceptable for most)
        EVENTUAL:       >500ms delay (eventual)
        """
```

When to wait for consistency:
```python
# Critical operation: wait for read-after-write consistency
await consistency_manager.wait_for_consistency(event_id, timeout_ms=5000)

# Non-critical operation: return immediately
booking_id = execute_command(command)
return {"booking_id": booking_id}  # Client sees it immediately
```

### Implementation Pattern

#### Step 1: Define Command
```python
@dataclass
class BookClassCommand:
    booking_id: str
    user_id: str
    class_id: str
    gym_id: str
    timestamp: datetime
```

#### Step 2: Register Command Handler
```python
cqrs_bus = get_cqrs_bus()
handler = BookClassCommandHandler(event_bus=event_bus)
cqrs_bus.register_command_handler("BookClassCommand", handler)
```

#### Step 3: Execute Command (Write Side)
```python
command = BookClassCommand(...)
booking_id = cqrs_bus.execute_command(command)
# Returns immediately (event published async)
```

#### Step 4: Define Event Projection
```python
class BookingProjection(EventProjection):
    def project(self, event: BookingCreatedEvent):
        # Update read model
        booking_data = fetch_booking_with_relations(event.booking_id)
        db.insert('denormalized_bookings', booking_data)
```

#### Step 5: Register Projection
```python
projection = BookingProjection(db)
event_bus.subscribe(BookingCreatedEvent, projection.project)
```

#### Step 6: Define Query
```python
@dataclass
class GetMyBookingsQuery:
    user_id: str
    status: Optional[str] = None
```

#### Step 7: Register Query Handler
```python
handler = GetMyBookingsQueryHandler(read_model_db)
cqrs_bus.register_query_handler("GetMyBookingsQuery", handler)
```

#### Step 8: Execute Query (Read Side)
```python
query = GetMyBookingsQuery(user_id="u456", status="CONFIRMED")
bookings = cqrs_bus.execute_query(query)
# Returns from denormalized table (10-50ms, vs 100-500ms without CQRS)
```

### Database Schema

#### Write Database (Normalized)
```sql
-- Normalized schema for consistency
CREATE TABLE bookings (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    class_id UUID NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (class_id) REFERENCES classes(id)
);

CREATE TABLE classes (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    gym_id UUID NOT NULL,
    trainer_id UUID,
    capacity INT NOT NULL,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    FOREIGN KEY (gym_id) REFERENCES gyms(id)
);

CREATE TABLE gyms (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    city VARCHAR(100),
    address VARCHAR(500)
);
```

#### Read Database (Denormalized)
```sql
-- Denormalized schema for speed
CREATE TABLE denormalized_bookings (
    booking_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    class_id UUID NOT NULL,
    class_name VARCHAR(255),        -- Denormalized
    gym_id UUID NOT NULL,
    gym_name VARCHAR(255),           -- Denormalized
    trainer_id UUID,
    trainer_name VARCHAR(255),       -- Denormalized
    status VARCHAR(50) NOT NULL,
    payment_status VARCHAR(50),
    price DECIMAL(10,2),
    capacity_total INT,
    capacity_occupied INT,
    position_in_waitlist INT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    
    -- Indexes for common queries
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
);

CREATE TABLE analytics_events (
    event_id UUID PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,  -- booking_created, payment_processed
    gym_id UUID NOT NULL,
    user_id UUID,
    amount DECIMAL(10,2),
    timestamp TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_gym_id (gym_id),
    INDEX idx_event_type (event_type),
    INDEX idx_timestamp (timestamp)
);
```

### Performance Comparison

```
Query: Get user's bookings for next 30 days

WITHOUT CQRS (Normalized):
────────────────────────────
SELECT b.*, c.name, c.start_time, c.end_time, 
       g.name as gym_name, t.name as trainer_name
FROM bookings b
JOIN classes c ON b.class_id = c.id
JOIN gyms g ON c.gym_id = g.id
LEFT JOIN trainers t ON c.trainer_id = t.id
WHERE b.user_id = ? 
  AND c.start_time BETWEEN ? AND ?
  AND b.status = 'CONFIRMED'

Result: ~500ms (5 joins on large tables)

WITH CQRS (Denormalized):
──────────────────────────
SELECT * FROM denormalized_bookings
WHERE user_id = ? 
  AND status = 'CONFIRMED'
  AND created_at BETWEEN ? AND ?

Result: ~10ms (single table, indexed)

SPEEDUP: 50x faster! ✅
```

### Handling Eventual Consistency

#### Problem: Read-After-Write Staleness

User books class, then immediately queries for bookings. Projection hasn't run yet!

```
T0:00  User books class (Command)
T0:50  Read model updated (Projection)
T0:00  User refreshes bookings (Query)
       ↑ Booking NOT FOUND (reads old data)
```

#### Solution 1: Optimistic UI Update
```typescript
// Frontend
const booking = { booking_id: "b123", status: "CONFIRMED" };
setLocalBookings([...bookings, booking]);  // Show immediately
fetchBookings();  // Reconcile with server
```

#### Solution 2: Wait for Consistency
```python
# Backend
booking_id = execute_command(command)
await consistency_manager.wait_for_consistency(
    event_id=booking_id,
    timeout_ms=5000  # Max wait
)
return {"booking_id": booking_id}
```

#### Solution 3: Return from Write Model
```python
# Backend
booking_id = execute_command(command)
booking_data = load_from_write_db(booking_id)  # Strong consistency
return booking_data
```

### Testing CQRS

```python
def test_full_cqrs_flow():
    # Setup bus and handlers
    bus = CQRSBus()
    bus.register_command_handler("BookClassCommand", 
                                BookClassCommandHandler())
    bus.register_query_handler("GetMyBookingsQuery", 
                              GetMyBookingsQueryHandler())
    bus.register_projection(BookingProjection())
    
    # Execute command
    command = BookClassCommand(
        booking_id="b123",
        user_id="u456",
        class_id="c789",
        gym_id="g123",
        timestamp=datetime.now()
    )
    result = bus.execute_command(command)
    assert result == "b123"
    
    # Project event
    event = BookingCreatedEvent(
        aggregate_id="b123",
        user_id="u456",
        class_id="c789",
        gym_id="g123"
    )
    bus.project_event(event)
    
    # Query read model
    query = GetMyBookingsQuery(user_id="u456")
    bookings = bus.execute_query(query)
    assert len(bookings) > 0
    assert bookings[0].booking_id == "b123"
```

### Monitoring CQRS

Track these metrics:
```
Write Side:
- Command processing time (50-200ms typical)
- Command success/failure rate
- Events published per second

Read Side:
- Query execution time (10-50ms denormalized vs 100-500ms normalized)
- Cache hit rate
- Query result set size

Projections:
- Event projection latency (100-500ms)
- Projection error rate
- Events pending projection

Consistency:
- Read/write gap (should be < 1 second)
- Eventual consistency SLA violations
- Stale read complaints
```

### Production Deployment

#### Prerequisites
- Event bus (RabbitMQ/Kafka)
- Separate write database (PostgreSQL)
- Separate read database (PostgreSQL)
- Cache layer (Redis)

#### Deployment Steps
1. Deploy write side with new commands
2. Deploy event projections
3. Pre-populate read models from event history
4. Gradually switch traffic to read models
5. Monitor consistency metrics
6. Archive old normalized queries

### Troubleshooting

#### Problem: Read model out of sync with write model
```
Solution:
1. Check projection error logs
2. Replay events to read model
3. Increase timeout for consistency guarantee
```

#### Problem: Queries still slow despite CQRS
```
Solution:
1. Add database indexes on common query columns
2. Add Redis caching layer
3. Consider sharding read models
4. Review query complexity
```

#### Problem: Eventual consistency causing user confusion
```
Solution:
1. Use optimistic UI updates
2. Reduce projection latency
3. Show "data may be delayed" message
4. Implement read-after-write consistency for critical flows
```

### Next Steps

- [ ] Migrate all queries to CQRS read models
- [ ] Add Redis caching for frequently accessed data
- [ ] Implement event store for complete event history
- [ ] Add read model versioning for safe migrations
- [ ] Build admin tools for read model synchronization
- [ ] Implement cross-service projections (microservices)
