# Session VII - API Gateway
## Centralized Entry Point for All Microservices

### Overview
The API Gateway is a centralized entry point for all client requests. It handles:
- **Routing**: Directs requests to appropriate services (monolith, payments, etc.)
- **Authentication**: JWT token validation and refresh
- **Rate Limiting**: Per-user/tier request limiting
- **Health Checks**: Service discovery and failover
- **Load Balancing**: Distribute traffic across service instances (future)

### Architecture

```
┌─────────────────────────────────────────────┐
│        Client (Frontend/Mobile)             │
└────────────────────┬────────────────────────┘
                     │
                     ↓ HTTP
    ┌────────────────────────────────┐
    │    API Gateway (Port 8000)     │
    ├────────────────────────────────┤
    │ - Request validation           │
    │ - JWT authentication           │
    │ - Rate limiting                │
    │ - Service routing              │
    │ - Load balancing               │
    │ - Health checks                │
    └────┬────────────┬──────────────┘
         │            │
    ┌────┴──┐    ┌────┴──────┐
    ↓       ↓    ↓           ↓
  ┌──────────────┐  ┌────────────────────┐
  │   Monolith   │  │ Payments Service   │
  │ (Port 8000)  │  │  (Port 8001)       │
  └──────────────┘  └────────────────────┘
         │                  │
         ↓                  ↓
  ┌──────────────┐  ┌────────────────────┐
  │ PostgreSQL   │  │ PostgreSQL         │
  │ (monolith)   │  │ (payments)         │
  └──────────────┘  └────────────────────┘
```

### API Routes

#### Monolith Routes
```
GET    /api/gyms              - List gyms
GET    /api/gyms/:id          - Get gym details
GET    /api/classes           - List classes
POST   /api/classes           - Create class
GET    /api/bookings          - User bookings
POST   /api/bookings          - Book class
DELETE /api/bookings/:id      - Cancel booking
GET    /api/users             - User profile
PUT    /api/users             - Update profile
GET    /api/schedules         - Class schedule
```

#### Payments Microservice Routes
```
POST   /api/payments          - Create payment
GET    /api/payments/:id      - Get payment status
GET    /api/transactions      - List transactions
POST   /api/refunds           - Request refund
GET    /api/refunds/:id       - Get refund status
```

#### Authentication Routes
```
POST   /auth/login            - Login (returns JWT)
POST   /auth/refresh          - Refresh token
POST   /auth/logout           - Logout
```

#### Gateway Meta Routes
```
GET    /health                - Gateway health + all services
GET    /health/:service       - Check specific service
GET    /metrics               - Gateway metrics
```

### Authentication

#### JWT Token Structure
```json
{
  "sub": "user123",
  "email": "user@example.com",
  "tier": "standard",
  "roles": ["user"],
  "exp": 1691234567,
  "iat": 1690629767
}
```

#### Login Flow
```
1. POST /auth/login {"email": "...", "password": "..."}
   ↓
2. Validate credentials against user service
   ↓
3. Generate JWT token
   ↓
4. Return access_token with 7-day expiry
```

#### Request with Token
```
GET /api/gyms
Authorization: Bearer <jwt_token>
```

### Rate Limiting

#### Tier-based Limits (requests/minute)
- **anonymous**: 10 req/min (no token)
- **standard**: 100 req/min (default user)
- **premium**: 1000 req/min (paid tier)

#### Rate Limit Headers
```
X-RateLimit-Limit:     100
X-RateLimit-Remaining: 45
X-RateLimit-Reset:     1691234567
```

### Health Checks

#### Gateway Health
```json
GET /health
{
  "status": "healthy",
  "timestamp": "2026-08-01T14:40:00",
  "services": {
    "monolith": {
      "status": "healthy",
      "last_check": "2026-08-01T14:39:59"
    },
    "payments": {
      "status": "healthy",
      "last_check": "2026-08-01T14:39:59"
    }
  }
}
```

#### Service-Specific Health
```json
GET /health/payments
{
  "service": "payments",
  "status": "healthy",
  "timestamp": "2026-08-01T14:40:00"
}
```

### Error Responses

#### Authentication Error (401)
```json
{
  "detail": "Invalid token"
}
```

#### Rate Limit Exceeded (429)
```json
{
  "detail": "Rate limit exceeded",
  "retry_after": 45
}
```

#### Service Unavailable (503)
```json
{
  "detail": "Service payments is unavailable"
}
```

#### Not Found (404)
```json
{
  "detail": "Resource not found"
}
```

### Configuration

#### Environment Variables
```bash
JWT_SECRET=your-secret-key-change-in-production
JWT_ALGORITHM=HS256

MONOLITH_URL=http://localhost:8000
PAYMENTS_URL=http://localhost:8001
ORDERS_URL=http://localhost:8002
ANALYTICS_URL=http://localhost:8003

RATE_LIMIT_DEFAULT=100
RATE_LIMIT_ANONYMOUS=10
RATE_LIMIT_PREMIUM=1000

HEALTH_CHECK_INTERVAL=30  # seconds
```

#### Service Registration
```python
SERVICES = {
    "monolith": "http://localhost:8000",
    "payments": "http://localhost:8001",
    "orders": "http://localhost:8002",
    "analytics": "http://localhost:8003",
}
```

### Deployment Options

#### Option 1: Python FastAPI (Recommended for MVP)
- Lightweight, fast, native Python
- Easy to integrate with existing Django monolith
- Single process or multiple workers with uvicorn

```bash
uvicorn api_gateway.main:app --host 0.0.0.0 --port 8000 --workers 4
```

#### Option 2: Kong API Gateway (Production)
Kong is an open-source API gateway built on Nginx:
- Advanced routing, plugins, rate limiting
- Built-in logging, monitoring, authentication
- Scales horizontally

```yaml
# kong.yml
services:
  - name: monolith
    url: http://localhost:8001
    routes:
      - paths: ["/api/gyms", "/api/classes", "/api/bookings"]
  
  - name: payments
    url: http://localhost:8002
    routes:
      - paths: ["/api/payments", "/api/transactions"]
```

#### Option 3: Traefik (Cloud-Native)
Traefik is a modern reverse proxy with Kubernetes support:
- Auto-discovery of services
- Built-in SSL/TLS termination
- Dashboard for monitoring

```yaml
# traefik.yml
entryPoints:
  web:
    address: ":80"

backends:
  monolith:
    servers:
      monolith-server:
        url: "http://localhost:8001"
  
  payments:
    servers:
      payments-server:
        url: "http://localhost:8002"

frontends:
  monolith-routes:
    backend: monolith
    routes:
      MonolithRoute:
        rule: "PathPrefix:/api/gyms,/api/classes,/api/bookings"
  
  payments-routes:
    backend: payments
    routes:
      PaymentsRoute:
        rule: "PathPrefix:/api/payments,/api/transactions"
```

### Monitoring & Observability

#### Metrics to Track
```python
# Request metrics
- Total requests
- Requests per service
- Average response time
- Error rate
- Rate limit violations

# Service metrics
- Service health status
- Service response time
- Service error rate
- Service availability (uptime %)

# Authentication metrics
- Login attempts
- Failed authentications
- Token refreshes
- Expired token attempts
```

#### Log Format
```
[2026-08-01 14:40:00] INFO: → GET /api/gyms
[2026-08-01 14:40:00.123] INFO: ← GET /api/gyms 200 (0.123s)
[2026-08-01 14:40:01] INFO: Auth header from user_id=123
[2026-08-01 14:40:02] WARN: Rate limit exceeded for user_id=456
[2026-08-01 14:40:03] ERROR: Service unavailable: payments
```

### Testing

Run tests:
```bash
pytest api_gateway/tests.py -v
```

Test coverage includes:
- JWT authentication (valid, expired, invalid tokens)
- Rate limiting (limits, tiers, remaining requests)
- Service routing (monolith, payments, unknown)
- Health checks (individual and all services)
- Error handling (401, 429, 503, 404)
- Middleware (headers, logging)

### Security Considerations

1. **JWT Security**
   - Use strong secret key (change in production)
   - Rotate keys periodically
   - Use HTTPS for all requests
   - Short expiration times (7 days default)

2. **Rate Limiting**
   - Prevent DDoS attacks
   - Protect services from overload
   - Fair resource allocation

3. **CORS**
   - Configure allowed origins
   - Restrict HTTP methods
   - Control exposed headers

4. **Input Validation**
   - Validate all request inputs
   - Sanitize for injection attacks
   - Use request signing for sensitive operations

5. **Service Authentication**
   - Internal service-to-service auth (mTLS or API keys)
   - Never expose service URLs to clients
   - Use internal network for service communication

### Future Enhancements

- [ ] API versioning (/api/v1/, /api/v2/)
- [ ] GraphQL support
- [ ] Service mesh integration (Istio)
- [ ] Advanced load balancing algorithms
- [ ] Circuit breaker pattern for service failures
- [ ] Request/response transformation
- [ ] API documentation generation (OpenAPI/Swagger)
- [ ] Distributed tracing (OpenTelemetry)
- [ ] Advanced caching strategies
- [ ] Request replay and debugging
