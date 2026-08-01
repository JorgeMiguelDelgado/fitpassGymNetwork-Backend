"""
API Gateway - Session VII
Central entry point for all microservices and monolith
Handles: routing, authentication, rate limiting, health checks
"""
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
import httpx
import jwt
from datetime import datetime, timedelta
from functools import lru_cache
import logging

app = FastAPI(title="FitPass Gym - API Gateway")
logger = logging.getLogger(__name__)

# Service URLs configuration
SERVICES = {
    "monolith": "http://localhost:8000",
    "payments": "http://localhost:8001",
    "orders": "http://localhost:8002",  # Future
    "analytics": "http://localhost:8003",  # Future
}

# JWT Configuration
JWT_SECRET = "your-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"

# Rate limiting configuration
RATE_LIMIT = {
    "default": 100,  # requests per minute
    "anonymous": 10,
    "premium": 1000,
}


class APIGatewayException(Exception):
    """Base exception for API Gateway"""
    pass


class RateLimitExceeded(APIGatewayException):
    """Rate limit exceeded"""
    pass


class ServiceUnavailable(APIGatewayException):
    """Service unavailable"""
    pass


class AuthenticationFailed(APIGatewayException):
    """Authentication failed"""
    pass


# ============ Authentication ============

def decode_jwt_token(token: str) -> dict:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationFailed("Token expired")
    except jwt.InvalidTokenError:
        raise AuthenticationFailed("Invalid token")


async def get_current_user(request: Request) -> dict:
    """Extract and validate user from request"""
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        # Anonymous user
        return {"user_id": None, "tier": "anonymous"}
    
    try:
        scheme, token = auth_header.split()
        if scheme.lower() != "bearer":
            raise AuthenticationFailed("Invalid auth scheme")
        
        user_data = decode_jwt_token(token)
        return {
            "user_id": user_data.get("sub"),
            "tier": user_data.get("tier", "standard"),
            "email": user_data.get("email"),
            "roles": user_data.get("roles", []),
        }
    except ValueError:
        raise AuthenticationFailed("Invalid authorization header")


# ============ Rate Limiting ============

class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self):
        self.requests = {}
    
    def is_allowed(self, user_id: str | None, tier: str) -> bool:
        """Check if user is within rate limit"""
        key = user_id or f"anon_{datetime.now().minute}"
        limit = RATE_LIMIT.get(tier, RATE_LIMIT["default"])
        
        if key not in self.requests:
            self.requests[key] = {"count": 0, "reset_time": datetime.now()}
        
        request_data = self.requests[key]
        
        # Reset counter if minute has passed
        if (datetime.now() - request_data["reset_time"]).seconds >= 60:
            request_data["count"] = 0
            request_data["reset_time"] = datetime.now()
        
        if request_data["count"] >= limit:
            return False
        
        request_data["count"] += 1
        return True
    
    def get_remaining(self, user_id: str | None, tier: str) -> int:
        """Get remaining requests for user"""
        key = user_id or f"anon_{datetime.now().minute}"
        limit = RATE_LIMIT.get(tier, RATE_LIMIT["default"])
        
        if key not in self.requests:
            return limit
        
        return max(0, limit - self.requests[key]["count"])


rate_limiter = RateLimiter()


async def check_rate_limit(request: Request, user: dict = Depends(get_current_user)):
    """Check if request is within rate limit"""
    if not rate_limiter.is_allowed(user["user_id"], user["tier"]):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    return user


# ============ Service Health Checks ============

class ServiceRegistry:
    """Track service health status"""
    
    def __init__(self):
        self.health = {service: {"status": "unknown", "last_check": None} 
                      for service in SERVICES}
    
    async def check_health(self, service_name: str) -> bool:
        """Check if service is healthy"""
        url = f"{SERVICES[service_name]}/health"
        
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(url)
                is_healthy = response.status_code == 200
                
                self.health[service_name] = {
                    "status": "healthy" if is_healthy else "unhealthy",
                    "last_check": datetime.now(),
                }
                return is_healthy
        except Exception as e:
            logger.error(f"Health check failed for {service_name}: {e}")
            self.health[service_name] = {
                "status": "unreachable",
                "last_check": datetime.now(),
            }
            return False
    
    async def check_all_services(self) -> dict:
        """Check all services"""
        for service in SERVICES:
            await self.check_health(service)
        return self.health
    
    def get_status(self, service_name: str) -> str:
        """Get last known status"""
        return self.health.get(service_name, {}).get("status", "unknown")


service_registry = ServiceRegistry()


# ============ Request Routing ============

class ServiceRouter:
    """Route requests to appropriate services"""
    
    ROUTES = {
        # Monolith routes
        "/api/gyms": "monolith",
        "/api/classes": "monolith",
        "/api/bookings": "monolith",
        "/api/users": "monolith",
        "/api/schedules": "monolith",
        
        # Payments Microservice
        "/api/payments": "payments",
        "/api/transactions": "payments",
        "/api/refunds": "payments",
        
        # Future services
        "/api/orders": "orders",
        "/api/analytics": "analytics",
    }
    
    def get_service(self, path: str) -> str:
        """Determine which service should handle this request"""
        for route_prefix, service in self.ROUTES.items():
            if path.startswith(route_prefix):
                return service
        raise ServiceUnavailable(f"No service found for path: {path}")
    
    async def route_request(self, request: Request) -> httpx.Response:
        """Forward request to appropriate service"""
        service_name = self.get_service(request.url.path)
        service_url = SERVICES[service_name]
        
        # Check service health
        if not await service_registry.check_health(service_name):
            raise ServiceUnavailable(f"Service {service_name} is unavailable")
        
        # Build target URL
        target_url = f"{service_url}{request.url.path}"
        if request.url.query:
            target_url += f"?{request.url.query}"
        
        # Forward request
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=dict(request.headers),
                content=await request.body() if request.method in ["POST", "PUT", "PATCH"] else None,
            )
        
        return response


router = ServiceRouter()


# ============ Middleware ============

@app.middleware("http")
async def add_gateway_headers(request: Request, call_next):
    """Add gateway-specific headers to responses"""
    response = await call_next(request)
    response.headers["X-Gateway-Version"] = "1.0.0"
    response.headers["X-Request-ID"] = request.headers.get("X-Request-ID", "unknown")
    response.headers["X-Forwarded-By"] = "api-gateway"
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests and responses"""
    start_time = datetime.now()
    
    logger.info(f"→ {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"← {request.method} {request.url.path} {response.status_code} ({duration:.3f}s)")
    
    return response


# ============ API Endpoints ============

@app.get("/health")
async def health_check():
    """Gateway health check"""
    service_status = await service_registry.check_all_services()
    
    all_healthy = all(s["status"] == "healthy" for s in service_status.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now().isoformat(),
        "services": service_status,
        "version": "1.0.0",
    }


@app.get("/health/{service_name}")
async def service_health(service_name: str):
    """Check specific service health"""
    if service_name not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
    
    is_healthy = await service_registry.check_health(service_name)
    
    return {
        "service": service_name,
        "status": "healthy" if is_healthy else "unhealthy",
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/auth/login")
async def login(credentials: dict):
    """
    Generate JWT token for user
    Expected payload: {"email": "user@example.com", "password": "..."}
    """
    # TODO: Validate credentials against user service
    email = credentials.get("email")
    
    token_payload = {
        "sub": "user_id_123",  # Should come from user service
        "email": email,
        "tier": "standard",
        "roles": ["user"],
        "exp": datetime.utcnow() + timedelta(days=7),
        "iat": datetime.utcnow(),
    }
    
    token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 7 * 24 * 3600,
    }


@app.post("/auth/refresh")
async def refresh_token(request: Request, user: dict = Depends(get_current_user)):
    """Refresh JWT token"""
    token_payload = {
        "sub": user["user_id"],
        "email": user["email"],
        "tier": user["tier"],
        "roles": user["roles"],
        "exp": datetime.utcnow() + timedelta(days=7),
        "iat": datetime.utcnow(),
    }
    
    token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 7 * 24 * 3600,
    }


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def gateway_route(
    request: Request,
    path: str,
    user: dict = Depends(check_rate_limit),
):
    """
    Main routing endpoint
    Routes all requests to appropriate microservice
    """
    try:
        # Route and forward request
        response = await router.route_request(request)
        
        return JSONResponse(
            status_code=response.status_code,
            content=response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
            headers=dict(response.headers),
        )
    
    except ServiceUnavailable as e:
        logger.error(f"Service unavailable: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    
    except RateLimitExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))
    
    except AuthenticationFailed as e:
        raise HTTPException(status_code=401, detail=str(e))
    
    except Exception as e:
        logger.error(f"Error routing request: {e}")
        raise HTTPException(status_code=500, detail="Internal gateway error")


@app.get("/metrics")
async def get_metrics():
    """Get gateway metrics"""
    return {
        "rate_limiter": {
            "tracked_users": len(rate_limiter.requests),
        },
        "services": service_registry.health,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
