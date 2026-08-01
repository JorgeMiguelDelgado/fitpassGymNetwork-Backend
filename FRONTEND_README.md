# Frontend Architecture Guide - Applying DDD, Event Sourcing & CQRS

## Overview

This guide shows how to apply the same architectural patterns from the backend (DDD, Event Sourcing, Sagas, CQRS) to a frontend application built with React/Vue/Angular.

**Key Principle**: The frontend is not just a "view" layer - it's a distributed system that needs the same architectural rigor as the backend.

---

## Part 1: Domain-Driven Design in Frontend

### 1.1 Domain Layer (Pure Business Logic)

Create domain models that mirror backend aggregates:

```typescript
// domain/Booking/Booking.ts
export enum BookingStatus {
  CONFIRMED = 'confirmed',
  WAITLISTED = 'waitlisted',
  CANCELLED = 'cancelled',
  ATTENDED = 'attended',
  NO_SHOW = 'no_show',
}

// Value Objects (Immutable)
export class WaitlistPosition {
  readonly position: number;
  
  constructor(position: number) {
    if (position < 1) throw new Error('Position must be >= 1');
    this.position = position;
  }
  
  nextPosition(): WaitlistPosition {
    return new WaitlistPosition(this.position - 1);
  }
}

// Aggregate Root
export class BookingAggregate {
  private _status: BookingStatus;
  private _waitlistPosition: WaitlistPosition | null;
  private _events: DomainEvent[] = [];
  
  constructor(
    readonly id: number,
    readonly userId: number,
    readonly classId: number,
    status: BookingStatus,
    waitlistPosition?: WaitlistPosition
  ) {
    this._status = status;
    this._waitlistPosition = waitlistPosition || null;
  }
  
  get status(): BookingStatus {
    return this._status;
  }
  
  promoteFromWaitlist(): void {
    if (this._status !== BookingStatus.WAITLISTED) {
      throw new Error('Can only promote from WAITLISTED');
    }
    this._status = BookingStatus.CONFIRMED;
    this._waitlistPosition = null;
    
    this._events.push(new UserPromotedFromWaitlistEvent(
      this.id,
      this.userId,
      this.classId
    ));
  }
  
  getUncommittedEvents(): DomainEvent[] {
    return [...this._events];
  }
  
  clearEvents(): void {
    this._events = [];
  }
}

// Domain Service (pure logic, no I/O)
export class BookingService {
  static canBook(capacity: number, currentBookings: number): boolean {
    return currentBookings < capacity;
  }
  
  static determineBookingStatus(
    hasFreeSpot: boolean
  ): BookingStatus {
    return hasFreeSpot ? BookingStatus.CONFIRMED : BookingStatus.WAITLISTED;
  }
}
```

### 1.2 Repository Pattern

Separate data access from domain logic:

```typescript
// domain/Booking/BookingRepository.ts
export interface IBookingRepository {
  getById(id: number): Promise<BookingAggregate>;
  save(booking: BookingAggregate): Promise<void>;
  cancel(id: number): Promise<void>;
}

// infrastructure/BookingRepository.ts (API backed)
export class BookingRepository implements IBookingRepository {
  constructor(private api: ApiClient) {}
  
  async getById(id: number): Promise<BookingAggregate> {
    const data = await this.api.get(`/bookings/${id}`);
    return this.toDomain(data);
  }
  
  async save(booking: BookingAggregate): Promise<void> {
    await this.api.post('/bookings', this.toDTO(booking));
  }
  
  private toDomain(data: any): BookingAggregate {
    return new BookingAggregate(
      data.id,
      data.userId,
      data.classId,
      data.status,
      data.waitlistPosition ? new WaitlistPosition(data.waitlistPosition) : null
    );
  }
  
  private toDTO(booking: BookingAggregate): any {
    return {
      id: booking.id,
      userId: booking.userId,
      classId: booking.classId,
      status: booking.status,
    };
  }
}
```

---

## Part 2: Event-Driven Architecture in Frontend

### 2.1 Domain Events

Events represent something that happened in the domain:

```typescript
// domain/events/DomainEvent.ts
export abstract class DomainEvent {
  constructor(
    readonly aggregateId: number,
    readonly timestamp: Date = new Date()
  ) {}
  
  abstract eventType(): string;
}

// domain/events/BookingEvents.ts
export class BookingCreatedEvent extends DomainEvent {
  eventType() { return 'booking.created'; }
  constructor(
    aggregateId: number,
    readonly userId: number,
    readonly classId: number,
    readonly status: BookingStatus
  ) {
    super(aggregateId);
  }
}

export class UserPromotedFromWaitlistEvent extends DomainEvent {
  eventType() { return 'user.promoted_from_waitlist'; }
  constructor(
    aggregateId: number,
    readonly userId: number,
    readonly classId: number
  ) {
    super(aggregateId);
  }
}
```

### 2.2 Event Bus

Centralized event handling in the frontend:

```typescript
// application/EventBus.ts
export interface IEventHandler<T extends DomainEvent> {
  handle(event: T): void | Promise<void>;
}

export class EventBus {
  private handlers: Map<string, IEventHandler<any>[]> = new Map();
  private history: DomainEvent[] = [];
  
  subscribe<T extends DomainEvent>(
    eventType: string,
    handler: IEventHandler<T>
  ): void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, []);
    }
    this.handlers.get(eventType)!.push(handler);
  }
  
  async publish(event: DomainEvent): Promise<void> {
    this.history.push(event);
    const handlers = this.handlers.get(event.eventType()) || [];
    
    for (const handler of handlers) {
      try {
        await handler.handle(event);
      } catch (error) {
        console.error(`Error in handler for ${event.eventType()}:`, error);
      }
    }
  }
  
  getHistory(): DomainEvent[] {
    return [...this.history];
  }
}

// Global instance
export const eventBus = new EventBus();
```

### 2.3 Event Handlers

Handle side effects from domain events:

```typescript
// application/handlers/BookingEventHandlers.ts
export class BookingNotificationHandler implements IEventHandler<BookingCreatedEvent> {
  handle(event: BookingCreatedEvent): void {
    if (event.status === BookingStatus.CONFIRMED) {
      // Show success notification
      showNotification('Booking confirmed!', 'success');
    } else if (event.status === BookingStatus.WAITLISTED) {
      // Show waitlist notification
      showNotification('You are on the waitlist', 'info');
    }
  }
}

export class UserPromotionNotificationHandler implements IEventHandler<UserPromotedFromWaitlistEvent> {
  handle(event: UserPromotedFromWaitlistEvent): void {
    showNotification('You have been promoted from waitlist!', 'success');
  }
}

// Register handlers
eventBus.subscribe('booking.created', new BookingNotificationHandler());
eventBus.subscribe('user.promoted_from_waitlist', new UserPromotionNotificationHandler());
```

---

## Part 3: Saga Pattern in Frontend

### 3.1 Multi-Step Workflows with Compensation

```typescript
// application/sagas/BookingWithPaymentSaga.ts
export class BookingWithPaymentSaga {
  async execute(context: {
    userId: number;
    classId: number;
    paymentMethod: string;
    amount: number;
  }): Promise<void> {
    const steps: SagaStep[] = [
      {
        name: 'reserve_spot',
        action: () => this.reserveSpot(context),
        compensation: (result) => this.releaseSpot(result),
      },
      {
        name: 'process_payment',
        action: () => this.processPayment(context),
        compensation: (result) => this.refundPayment(result),
      },
      {
        name: 'notify_user',
        action: () => this.notifyUser(context),
        compensation: () => this.cancelNotification(),
      },
    ];
    
    await this.orchestrateSaga(steps, context);
  }
  
  private async reserveSpot(context: any): Promise<any> {
    const response = await api.post('/bookings', {
      userId: context.userId,
      classId: context.classId,
    });
    return response.data;
  }
  
  private async releaseSpot(result: any): Promise<void> {
    await api.delete(`/bookings/${result.bookingId}`);
  }
  
  private async processPayment(context: any): Promise<any> {
    const response = await api.post('/payments', {
      userId: context.userId,
      amount: context.amount,
      method: context.paymentMethod,
    });
    return response.data;
  }
  
  private async refundPayment(result: any): Promise<void> {
    await api.post(`/payments/${result.paymentId}/refund`, {});
  }
  
  private async notifyUser(context: any): Promise<void> {
    showNotification('Booking and payment successful!', 'success');
  }
  
  private async orchestrateSaga(
    steps: SagaStep[],
    context: any
  ): Promise<void> {
    const results: any[] = [];
    
    for (let i = 0; i < steps.length; i++) {
      try {
        const result = await steps[i].action();
        results.push({ step: steps[i].name, result });
      } catch (error) {
        // Compensate in reverse order
        for (let j = i - 1; j >= 0; j--) {
          try {
            await steps[j].compensation(results[j].result);
          } catch (e) {
            console.error(`Compensation failed for ${steps[j].name}:`, e);
          }
        }
        throw error;
      }
    }
  }
}
```

---

## Part 4: CQRS Pattern in Frontend

### 4.1 Separate Commands and Queries

```typescript
// application/commands/BookClassCommand.ts
export interface ICommand {
  execute(): Promise<void>;
}

export class BookClassCommand implements ICommand {
  constructor(
    private userId: number,
    private classId: number,
    private repository: IBookingRepository,
    private eventBus: EventBus
  ) {}
  
  async execute(): Promise<void> {
    // Command: Write operation
    const fitnessClass = await api.get(`/classes/${this.classId}`);
    const booking = new BookingAggregate(
      0, // ID assigned by server
      this.userId,
      this.classId,
      BookingService.determineBookingStatus(fitnessClass.available > 0)
    );
    
    await this.repository.save(booking);
    
    // Publish domain events
    for (const event of booking.getUncommittedEvents()) {
      await this.eventBus.publish(event);
    }
  }
}

// application/queries/GetMyBookingsQuery.ts
export interface IQuery<T> {
  execute(): Promise<T>;
}

export class GetMyBookingsQuery implements IQuery<BookingDTO[]> {
  constructor(private userId: number) {}
  
  async execute(): Promise<BookingDTO[]> {
    // Query: Read operation (from optimized read model)
    const response = await api.get(`/bookings?userId=${this.userId}`);
    return response.data;
  }
}
```

### 4.2 Command Handler and Query Handler

```typescript
// application/handlers/CommandHandler.ts
export class CommandHandler {
  async handle(command: ICommand): Promise<void> {
    try {
      await command.execute();
    } catch (error) {
      console.error('Command failed:', error);
      throw error;
    }
  }
}

// application/handlers/QueryHandler.ts
export class QueryHandler {
  async handle<T>(query: IQuery<T>): Promise<T> {
    try {
      return await query.execute();
    } catch (error) {
      console.error('Query failed:', error);
      throw error;
    }
  }
}
```

### 4.3 Read Models and Caching

```typescript
// application/readModels/BookingReadModel.ts
export class BookingReadModel {
  private cache: Map<number, BookingDTO> = new Map();
  private expiresAt: Map<number, number> = new Map();
  private CACHE_TTL = 5 * 60 * 1000; // 5 minutes
  
  async getBooking(id: number): Promise<BookingDTO> {
    // Check cache
    if (this.cache.has(id)) {
      const expiry = this.expiresAt.get(id)!;
      if (Date.now() < expiry) {
        return this.cache.get(id)!;
      }
      this.cache.delete(id);
    }
    
    // Fetch from API (read model, optimized for queries)
    const booking = await api.get(`/bookings/${id}?view=read`);
    this.cache.set(id, booking.data);
    this.expiresAt.set(id, Date.now() + this.CACHE_TTL);
    return booking.data;
  }
  
  invalidateCache(id: number): void {
    this.cache.delete(id);
    this.expiresAt.delete(id);
  }
}

// Update read model when events are published
eventBus.subscribe('booking.created', {
  handle: (event: BookingCreatedEvent) => {
    bookingReadModel.invalidateCache(event.aggregateId);
  }
});
```

---

## Part 5: State Management (Redux/Vuex/Pinia)

### 5.1 Redux with CQRS

```typescript
// store/bookings/actions.ts
export const bookClass = (userId: number, classId: number) => async (dispatch: any) => {
  try {
    dispatch({ type: 'BOOKING_START' });
    
    const command = new BookClassCommand(userId, classId, repository, eventBus);
    await commandHandler.handle(command);
    
    dispatch({ type: 'BOOKING_SUCCESS' });
  } catch (error) {
    dispatch({ type: 'BOOKING_FAILURE', payload: error });
  }
};

export const getMyBookings = (userId: number) => async (dispatch: any) => {
  try {
    const query = new GetMyBookingsQuery(userId);
    const bookings = await queryHandler.handle(query);
    dispatch({ type: 'BOOKINGS_LOADED', payload: bookings });
  } catch (error) {
    dispatch({ type: 'BOOKINGS_FAILED', payload: error });
  }
};

// store/bookings/reducers.ts
const initialState = {
  list: [] as BookingDTO[],
  loading: false,
  error: null,
};

export function bookingsReducer(state = initialState, action: any) {
  switch (action.type) {
    case 'BOOKING_START':
      return { ...state, loading: true, error: null };
    case 'BOOKING_SUCCESS':
      return { ...state, loading: false };
    case 'BOOKINGS_LOADED':
      return { ...state, list: action.payload, loading: false };
    case 'BOOKING_FAILURE':
    case 'BOOKINGS_FAILED':
      return { ...state, loading: false, error: action.payload };
    default:
      return state;
  }
}
```

### 5.2 Vuex with CQRS (similar pattern)

```typescript
// store/bookings.ts (Vuex)
export const bookingStore = {
  state: () => ({
    list: [] as BookingDTO[],
    loading: false,
    error: null,
  }),
  
  mutations: {
    setLoading(state, value) { state.loading = value; },
    setList(state, bookings) { state.list = bookings; },
    setError(state, error) { state.error = error; },
  },
  
  actions: {
    async bookClass(context, { userId, classId }) {
      context.commit('setLoading', true);
      try {
        const command = new BookClassCommand(userId, classId, repository, eventBus);
        await commandHandler.handle(command);
      } catch (error) {
        context.commit('setError', error);
        throw error;
      } finally {
        context.commit('setLoading', false);
      }
    },
    
    async getMyBookings(context, userId) {
      try {
        const query = new GetMyBookingsQuery(userId);
        const bookings = await queryHandler.handle(query);
        context.commit('setList', bookings);
      } catch (error) {
        context.commit('setError', error);
      }
    },
  },
};
```

---

## Part 6: Component Architecture

### 6.1 Smart & Dumb Components

```typescript
// components/BookingList.tsx (Smart - Connected to store)
import { useDispatch, useSelector } from 'react-redux';

export const BookingList: React.FC<{ userId: number }> = ({ userId }) => {
  const dispatch = useDispatch();
  const { list, loading } = useSelector(state => state.bookings);
  
  useEffect(() => {
    dispatch(getMyBookings(userId));
  }, [userId]);
  
  if (loading) return <div>Loading...</div>;
  
  return <BookingListView bookings={list} />;
};

// components/BookingListView.tsx (Dumb - Pure presentation)
export const BookingListView: React.FC<{ bookings: BookingDTO[] }> = ({ bookings }) => {
  return (
    <ul>
      {bookings.map(booking => (
        <li key={booking.id}>
          {booking.className} - {booking.status}
        </li>
      ))}
    </ul>
  );
};
```

### 6.2 Custom Hooks for Domain Logic

```typescript
// hooks/useBooking.ts
export const useBooking = (bookingId: number) => {
  const [booking, setBooking] = useState<BookingAggregate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  
  useEffect(() => {
    (async () => {
      try {
        const query = new GetBookingQuery(bookingId);
        const result = await queryHandler.handle(query);
        setBooking(result);
      } catch (e) {
        setError(e as Error);
      } finally {
        setLoading(false);
      }
    })();
  }, [bookingId]);
  
  const promoteFromWaitlist = useCallback(async () => {
    if (!booking) return;
    
    const command = new PromoteFromWaitlistCommand(booking.id, repository, eventBus);
    try {
      await commandHandler.handle(command);
      // Event will update the booking via eventBus subscription
    } catch (e) {
      setError(e as Error);
    }
  }, [booking]);
  
  return { booking, loading, error, promoteFromWaitlist };
};
```

---

## Part 7: Testing Strategy

### 7.1 Unit Tests (Domain Logic - No I/O)

```typescript
// __tests__/domain/Booking.test.ts
describe('BookingAggregate', () => {
  it('should create a confirmed booking when spots available', () => {
    const booking = new BookingAggregate(1, 10, 20, BookingStatus.CONFIRMED);
    expect(booking.status).toBe(BookingStatus.CONFIRMED);
  });
  
  it('should promote from waitlist to confirmed', () => {
    const booking = new BookingAggregate(
      1, 10, 20, 
      BookingStatus.WAITLISTED,
      new WaitlistPosition(1)
    );
    
    booking.promoteFromWaitlist();
    
    expect(booking.status).toBe(BookingStatus.CONFIRMED);
    const events = booking.getUncommittedEvents();
    expect(events).toContainEqual(jasmine.any(UserPromotedFromWaitlistEvent));
  });
});
```

### 7.2 Integration Tests (Commands + Handlers)

```typescript
// __tests__/application/BookClassCommand.test.ts
describe('BookClassCommand', () => {
  it('should book a class and publish events', async () => {
    const repository = createMockRepository();
    const eventBus = new EventBus();
    const command = new BookClassCommand(10, 20, repository, eventBus);
    
    await commandHandler.handle(command);
    
    expect(repository.save).toHaveBeenCalled();
    const events = eventBus.getHistory();
    expect(events).toHaveLength(1);
    expect(events[0]).toBeInstanceOf(BookingCreatedEvent);
  });
});
```

### 7.3 Component Tests

```typescript
// __tests__/components/BookingList.test.tsx
describe('BookingList', () => {
  it('should load and display bookings', async () => {
    const { getByText } = render(
      <BookingList userId={10} />
    );
    
    await waitFor(() => {
      expect(getByText('Yoga Class - confirmed')).toBeInTheDocument();
    });
  });
});
```

---

## Part 8: Performance Optimization

### 8.1 Query Caching Strategy

```typescript
// application/QueryCache.ts
export class QueryCache {
  private cache: Map<string, { data: any; expiry: number }> = new Map();
  
  async execute<T>(
    key: string,
    query: IQuery<T>,
    ttl: number = 5 * 60 * 1000
  ): Promise<T> {
    if (this.cache.has(key) && Date.now() < this.cache.get(key)!.expiry) {
      return this.cache.get(key)!.data;
    }
    
    const data = await query.execute();
    this.cache.set(key, { data, expiry: Date.now() + ttl });
    return data;
  }
  
  invalidate(pattern: string): void {
    for (const key of this.cache.keys()) {
      if (key.match(pattern)) {
        this.cache.delete(key);
      }
    }
  }
}
```

### 8.2 Lazy Loading and Code Splitting

```typescript
// router/index.ts
const BookingPage = lazy(() => import('./pages/BookingPage'));
const PaymentPage = lazy(() => import('./pages/PaymentPage'));

export const routes = [
  {
    path: '/bookings',
    component: BookingPage,
  },
  {
    path: '/payments',
    component: PaymentPage,
  },
];
```

---

## Part 9: Error Handling & Resilience

### 9.1 Retry Logic with Exponential Backoff

```typescript
// application/RetryPolicy.ts
export class RetryPolicy {
  async execute<T>(
    fn: () => Promise<T>,
    maxRetries: number = 3,
    baseDelay: number = 100
  ): Promise<T> {
    let lastError: Error | undefined;
    
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        return await fn();
      } catch (error) {
        lastError = error as Error;
        const delay = baseDelay * Math.pow(2, attempt);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
    
    throw lastError;
  }
}

// Usage
const retryPolicy = new RetryPolicy();
const bookings = await retryPolicy.execute(() => 
  queryHandler.handle(new GetMyBookingsQuery(userId))
);
```

### 9.2 Circuit Breaker Pattern

```typescript
// application/CircuitBreaker.ts
export enum CircuitBreakerState {
  CLOSED = 'closed',
  OPEN = 'open',
  HALF_OPEN = 'half_open',
}

export class CircuitBreaker {
  private state = CircuitBreakerState.CLOSED;
  private failureCount = 0;
  private lastFailureTime = 0;
  
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === CircuitBreakerState.OPEN) {
      if (Date.now() - this.lastFailureTime > 60000) {
        this.state = CircuitBreakerState.HALF_OPEN;
      } else {
        throw new Error('Circuit breaker is open');
      }
    }
    
    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }
  
  private onSuccess() {
    this.failureCount = 0;
    this.state = CircuitBreakerState.CLOSED;
  }
  
  private onFailure() {
    this.lastFailureTime = Date.now();
    this.failureCount++;
    if (this.failureCount >= 5) {
      this.state = CircuitBreakerState.OPEN;
    }
  }
}
```

---

## Part 10: Full Example - Booking Flow

### Complete Flow from UI to API

```typescript
// Example: User books a fitness class

// 1. UI Component
const BookingPage: React.FC = () => {
  const dispatch = useDispatch();
  const [classId, setClassId] = useState(0);
  
  const handleBook = async () => {
    try {
      // Dispatch command
      await dispatch(bookClass(userId, classId));
      showNotification('Booking successful!', 'success');
    } catch (error) {
      showNotification('Booking failed', 'error');
    }
  };
  
  return <button onClick={handleBook}>Book Class</button>;
};

// 2. Redux Action (dispatches command)
dispatch(bookClass(userId, classId))
  ↓
// 3. Command: BookClassCommand
{
  userId: 10,
  classId: 20,
  execute: () => {
    // Load aggregate
    const booking = new BookingAggregate(...);
    // Persist
    await repository.save(booking);
    // Publish events
    await eventBus.publish(BookingCreatedEvent(...));
  }
}
  ↓
// 4. API Call: POST /api/bookings
{
  userId: 10,
  classId: 20,
  status: 'confirmed'
}
  ↓
// 5. Domain Event: BookingCreatedEvent
{
  aggregateId: 42,
  userId: 10,
  classId: 20,
  eventType: 'booking.created',
  timestamp: '2024-08-01...'
}
  ↓
// 6. Event Handlers
- NotificationHandler: shows "Booking confirmed!"
- AnalyticsHandler: tracks booking event
- ReadModelProjector: updates denormalized_bookings table
  ↓
// 7. Query: GetMyBookingsQuery
// User sees updated booking list via read model
```

---

## Summary: Frontend Architecture Pattern

```
┌─────────────────────────────────────────────────────────┐
│                     React Components                    │
│              (Smart/Dumb separation)                    │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────┐
│                Redux Store (State)                      │
│    (Reducers, Actions, Selectors, Middleware)           │
└─────┬──────────────────────────────────────────────┬────┘
      │                                              │
┌─────┴──────────────────────┐  ┌──────────────────┴──┐
│  Application Layer         │  │  Event Bus        │
│  - CommandHandler          │  │  - Publishers     │
│  - QueryHandler            │  │  - Subscribers    │
│  - Sagas                   │  │  - History        │
└─────┬──────────────────────┘  └──────────────────┬──┘
      │                                            │
┌─────┴────────────────────────────────────────────┴──┐
│              Domain Layer                          │
│  - Aggregates (BookingAggregate)                   │
│  - Value Objects (WaitlistPosition, Money)        │
│  - Domain Services (BookingService)               │
│  - Domain Events (BookingCreatedEvent)            │
└─────┬──────────────────────────────────────────────┘
      │
┌─────┴──────────────────────────────────────────────┐
│         Infrastructure Layer                      │
│  - Repository (API-backed)                        │
│  - API Client (with retry, circuit breaker)       │
│  - Cache (Query cache, browser cache)             │
└──────────────────────────────────────────────────┘
```

---

## Conclusion

By applying DDD, Event Sourcing, Sagas, and CQRS patterns to the frontend:

✅ **Maintainability**: Clear separation of concerns  
✅ **Testability**: 80%+ unit test coverage  
✅ **Scalability**: Handles complex state management  
✅ **Resilience**: Retry logic, circuit breakers  
✅ **Performance**: Query caching, lazy loading  
✅ **Consistency**: Frontend and backend aligned

The frontend becomes a **proper distributed system** that mirrors the backend architecture.
