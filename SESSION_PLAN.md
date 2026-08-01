# FitPass Gym - 8-Session Architecture Roadmap

## Executive Summary

This document tracks the evolution of FitPass Gym from a monolithic Django application to a microservices architecture with Domain-Driven Design, Event Sourcing, and CQRS patterns.

## Session Status Overview

| Session | Name | Status | Tests | Commits |
|---------|------|--------|-------|---------|
| II | Monolith Core | ✅ DONE | 17 | `3a5876f` |
| III | DDD Refactor | ✅ DONE | 51 | (merged) |
| IV | Event Bus & Handlers | ✅ DONE | 68 | `6cb2622` |
| V | Saga Workflow | ✅ DONE | 68 | `0d4ed79` |
| VI | Extract Microservice | 🚀 IN_PROGRESS | - | - |
| VII | API Gateway | ⏳ PENDING | - | - |
| VIII | CQRS | ⏳ PENDING | - | - |

---

## Session II: Monolith Core ✅

**Objective**: Establish base monolithic API with core business logic

**Deliverables**:
- ✅ Core models: User, Gym, FitnessClass, Booking, Purchase, etc.
- ✅ REST API endpoints for main workflows
- ✅ PostgreSQL persistence
- ✅ 13 HTTP integration tests covering all endpoints
- ✅ 4 unit tests for services

**Key Files**:
- `fitpassgym/gym/models.py` - Domain models
- `fitpassgym/gym/scheduling/services.py` - Booking logic
- `fitpassgym/gym/tests_integration.py` - 13 integration tests

**Outcome**: Monolithic API base with tested endpoints (17 tests passing)

---

## Session III: DDD Refactor ✅

**Objective**: Extract pure domain logic into domain layer with value objects and aggregates

**Deliverables**:
- ✅ Value objects: Money (currency-aware), Coordinates, Position, Capacity
- ✅ Aggregates: BookingAggregate, FitnessClassAggregate, ProductAggregate, etc.
- ✅ Domain services: SchedulingService, CommerceService, AccessService
- ✅ Domain events: BookingCreatedEvent, UserPromotedFromWaitlistEvent, etc.
- ✅ 47 domain layer tests (no DB/HTTP)

**Key Files**:
- `fitpassgym/gym/shared/domain.py` - Base domain infrastructure (272 lines)
- `fitpassgym/gym/scheduling/domain.py` - Scheduling aggregates (371 lines)
- `fitpassgym/gym/commerce/domain.py` - Commerce aggregates (280 lines)
- `fitpassgym/gym/access/domain.py` - Access aggregates (155 lines)
- `fitpassgym/gym/tests_domain.py` - 47 domain tests

**Technical Highlights**:
- Immutable value objects with frozen dataclasses
- State machine in BookingAggregate (CONFIRMED→ATTENDED/NO_SHOW, WAITLISTED→CONFIRMED)
- Invariant validation in __post_init__ methods
- Pure domain logic (no Django imports in domain layer)

**Outcome**: Domain layer decoupled from infrastructure (51 tests passing)

---

## Session IV: Event Bus & Handlers ✅

**Objective**: Implement event sourcing infrastructure with pub/sub event bus

**Deliverables**:
- ✅ In-memory EventBus with publish/subscribe/history
- ✅ Event handler registry with NotificationEventHandler, AuditEventHandler
- ✅ UserPromotedFromWaitlistEvent triggers notification creation
- ✅ 13 event bus tests covering all scenarios
- ✅ Integration of event publishing in scheduling services

**Key Files**:
- `fitpassgym/gym/shared/events.py` - EventBus infrastructure (170 lines)
- `fitpassgym/gym/shared/event_handlers.py` - Event handlers (124 lines)
- `fitpassgym/gym/tests_events.py` - 13 event bus tests
- `fitpassgym/gym/scheduling/services.py` - Modified to publish events

**Technical Highlights**:
- Thread-safe in-memory event bus (ready for RabbitMQ/Kafka migration)
- Handlers registered by event type with exception handling
- Event history tracking for debugging
- Global singleton pattern with reset for testing

**Outcome**: Event infrastructure ready for microservices (68 tests passing)

---

## Session V: Saga Workflow ✅

**Objective**: Implement saga pattern for multi-step distributed workflows with automatic compensation

**Deliverables**:
- ✅ SagaOrchestrator with step execution and compensation
- ✅ SagaBuilder for fluent saga definition
- ✅ Automatic reverse-order compensation on step failure
- ✅ 12 saga tests covering orchestration and compensation
- ✅ Example sagas: booking_with_payment, transfer_between_classes

**Key Files**:
- `fitpassgym/gym/shared/sagas.py` - Saga orchestration framework (234 lines)
- `fitpassgym/gym/example_sagas.py` - Complete business process examples (221 lines)
- `fitpassgym/gym/tests_sagas.py` - 12 saga tests

**Technical Highlights**:
- Orchestration pattern (centralized saga coordinator)
- Automatic reversal in reverse order on step failure
- Context and results passed through step chain
- Ready for coreography pattern (event-driven) in future

**Test Coverage**:
- Simple saga execution with step chaining
- Failed step triggers compensation
- Compensation executes in reverse order
- Context and results passing between steps

**Outcome**: Saga infrastructure ready for complex workflows (68 tests passing)

---

## Session VI: Extract Microservice 🚀

**Objective**: Extract first bounded context (Payments) into independent microservice

**Planned Deliverables**:
- [ ] Payments microservice with own database
- [ ] API contracts for monolith ↔ payments communication
- [ ] Event publishing to message broker (RabbitMQ/Kafka)
- [ ] Deployment configuration
- [ ] Integration tests for monolith + payments flow

**Architecture**:
```
Monolith (Commerce bounded context)
├── Models (Purchase, Product, Promotion)
├── Pricing logic
└── Events: ProductPurchasedEvent → RabbitMQ

Message Broker (RabbitMQ/Kafka)
└── Events published by monolith

Payments Microservice (new)
├── Models (Payment, Transaction)
├── Payment processing logic
└── Subscribes to ProductPurchasedEvent
```

**Key Decisions**:
- Extract Payments (Commerce) as first microservice
- Use async messaging for monolith ↔ service communication
- Keep shared event schemas in both services
- Maintain DB consistency with saga pattern

---

## Session VII: API Gateway ⏳

**Objective**: Add centralized entry point for monolith + microservices

**Planned Deliverables**:
- [ ] API Gateway service (Kong, Traefik, or custom)
- [ ] Routing rules: `/api/*` → appropriate service
- [ ] Auth/authorization enforcement
- [ ] Rate limiting and logging
- [ ] Health checks per service

**Architecture**:
```
Client Requests
↓
API Gateway (/api)
├── /api/gyms/* → Monolith
├── /api/classes/* → Monolith
├── /api/bookings/* → Monolith
├── /api/payments/* → Payments Microservice
└── /api/orders/* → Orders Microservice (future)
```

---

## Session VIII: CQRS ⏳

**Objective**: Separate read and write models for scalability

**Planned Deliverables**:
- [ ] Command handlers (writes) - separate from queries
- [ ] Read model projections from events
- [ ] Materialized views (denormalized reads)
- [ ] Eventual consistency implementation
- [ ] Performance metrics (read latency improvement)

**Architecture**:
```
Write Side (Commands)
├── BookCommand
├── PurchaseCommand
└── CheckInCommand
        ↓
   Domain Aggregates
   & Domain Events
        ↓
   Event Bus

Read Side (Queries)
├── Projection layer
├── Materialized views
├── Caching
└── Read replicas
```

---

## Test Summary

| Test Category | Session II | Session III | Session IV | Session V | Total |
|---------------|-----------|-----------|-----------|----------|-------|
| Unit Tests | 4 | 4 | 4 | 4 | 16 |
| Integration | 13 | 13 | 13 | 13 | 52 |
| Domain Tests | - | 47 | 47 | 47 | 141 |
| Event Bus Tests | - | - | 13 | 13 | 26 |
| Saga Tests | - | - | - | 12 | 12 |
| **Total** | **17** | **51** | **68** | **68** | **247** |

---

## Technology Stack

### Current (Sessions II-V)
- **Framework**: Django 6.0 (monolith)
- **Database**: PostgreSQL
- **Event Bus**: In-memory (ready for RabbitMQ/Kafka)
- **Testing**: Django TestCase, SimpleTestCase
- **Python**: 3.14+
- **App Label**: `gym` (backward compatible)

### Session VI+
- **Message Broker**: RabbitMQ or Kafka
- **Microservices**: FastAPI or Django
- **API Gateway**: Kong, Traefik, or custom
- **Distributed Tracing**: OpenTelemetry (optional)

---

## Key Architectural Principles

1. **Domain-Driven Design**: Business logic isolated in pure Python domain layer
2. **Event Sourcing**: State changes tracked as immutable events
3. **Saga Pattern**: Multi-step workflows with automatic compensation
4. **Async Messaging**: Decoupled services via event bus
5. **Backward Compatibility**: `app_label="gym"` preserves existing tables
6. **Testability**: Three layers of tests (unit/integration/domain)

---

## Running the Tests

```bash
# All tests (247 total)
python manage.py test fitpassgym.gym

# By session
python manage.py test fitpassgym.gym.tests  # Session II (unit + integration)
python manage.py test fitpassgym.gym.tests_domain  # Session III (47 tests)
python manage.py test fitpassgym.gym.tests_events  # Session IV (13 tests)
python manage.py test fitpassgym.gym.tests_sagas  # Session V (12 tests)
```

---

## Next Steps (Session VI)

1. Create payments service skeleton
2. Extract Payment domain into separate microservice
3. Set up RabbitMQ/Kafka for event publishing
4. Implement API contracts for payments service
5. Add integration tests for monolith + payments workflow
6. Deploy payments service independently

---

## Future Considerations

- Event store database for audit trail
- Dead letter queues for failed events
- Circuit breakers for service resilience
- Metrics and monitoring per service
- Multi-region deployment
- Event versioning strategy
- CQRS read model snapshots

---

**Last Updated**: Session V Complete (2024)
**Next Session**: Session VI - Extract Microservice
