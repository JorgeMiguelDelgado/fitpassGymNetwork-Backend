# FitPass Gym — Roadmap de Arquitectura (8 Sesiones)

## Resumen del Plan

Este documento documenta el progreso en la evolución arquitectónica de FitPass Gym, desde un monolito modular hasta una arquitectura de microservicios con CQRS.

---

## 📊 Estado General

| Sesión | Rama | Estado | Objetivo |
|--------|------|--------|----------|
| ✅ II | `session-2-monolith-core` | DONE | Núcleo monolito: API base, persistencia, tests críticos |
| ✅ III | `session-3-ddd-refactor` | DONE | Refactor DDD con bounded contexts |
| ⏳ IV | `session-4-domain-events-broker` | PENDING | Eventos de dominio + event bus |
| ⏳ V | `session-5-saga-workflow` | PENDING | Saga multi-servicio con compensaciones |
| ⏳ VI | `session-6-extract-microservice` | PENDING | Extraer primer microservicio (payments) |
| ⏳ VII | `session-7-api-gateway` | PENDING | API Gateway centralizado |
| ⏳ VIII | `session-8-cqrs` | PENDING | CQRS con read models y proyecciones |

---

## ✅ Sesión II — Núcleo Monolito

**Branch:** `session-2-monolith-core`  
**Estado:** COMPLETADA

### Entregables

- ✅ API base con Django 6.0 y modularización clara
- ✅ Modelos de dominio (`FitnessClass`, `Booking`, `Gym`, `Product`, etc.)
- ✅ Servicios de aplicación (`book_class`, `cancel_booking`, `check_in`, `purchase_product`)
- ✅ PostgreSQL con schema inicial (2 migraciones)
- ✅ 4 tests unitarios de lógica de negocio
- ✅ 13 tests de integración para endpoints HTTP
- ✅ **Total: 17 tests pasando** ✓

### Flujos Validados

1. **Reserva y lista de espera:** Usuario reserva clase confirmada o en espera; promoción automática al cancelar
2. **Compra con promoción:** Compra producto, aplica descuento, registra vigencia
3. **Check-in:** Valida acceso vigente, abre puerta, registra entrada
4. **Búsqueda por ubicación:** Haversine distance para gyms cercanos

### Commit

```
704f596 session-2: Add HTTP endpoint integration tests for core monolith
```

---

## ✅ Sesión III — Refactor DDD

**Branch:** `session-3-ddd-refactor`  
**Estado:** COMPLETADA

### Entregables

- ✅ Value objects inmutables con invariantes:
  - `Money`: Amount + currency, operaciones aritméticas, descuentos
  - `Coordinates`: Lat/long con rango validado
  - `Position`: Posición en lista de espera
  - `Capacity`: Total + occupied con invariantes
- ✅ Aggregate roots con business rules:
  - `FitnessClassAggregate`: Validación de tiempo, cupo, estado
  - `BookingAggregate`: State machine (confirmed/waitlisted/cancelled/attended/no_show)
  - `ProductAggregate`: Product info + validación de compra
  - `PurchaseAggregate`: Vigencia, créditos, acceso validado
  - `PromotionAggregate`: Período de validez, aplicación de descuentos
  - `CheckInAggregate`: Registro de acceso con validación
- ✅ Domain services (pura lógica sin persistencia):
  - `SchedulingService`: book_class, cancel_and_promote, record_attendance
  - `CommerceService`: apply_promotion, create_purchase
  - `AccessService`: validate_access, create_checkin
- ✅ Domain events para event sourcing:
  - Scheduling: `BookingCreatedEvent`, `BookingCancelledEvent`, `UserPromotedFromWaitlistEvent`
  - Commerce: `ProductPurchasedEvent`, `AccessActivatedEvent`
  - Access: `CheckInRecordedEvent`, `AccessDeniedEvent`
- ✅ 47 tests de dominio (sin DB, sin HTTP)
- ✅ **Total: 51 tests pasando** ✓

### Flujos Validados a Nivel de Dominio

1. **Invariantes de Money:** No negativos, operaciones con currency matching
2. **State machine de Booking:** Transiciones válidas, promoción desde espera
3. **Capacidad de Clase:** Cálculo de espacios disponibles, bloqueo cuando llena
4. **Compra con Promoción:** Descuentos porcentuales, validación de período
5. **Acceso y Créditos:** Validación de vigencia, consumo de créditos

### Commit

```
010cba8 session-3: Implement DDD domain model with value objects and aggregates
```

---

## Futuras Sesiones (Resumen)

### Sesión IV — Eventos de Dominio + Event Bus
- Identificar eventos (`BookingCreated`, `PaymentApproved`, `WaitlistPromoted`)
- Event bus en memoria → migración a RabbitMQ
- Manejo de errores y reintentos

### Sesión V — Saga Multi-Servicio
- Orquestación/Coreografía para flujos complejos
- Compensaciones (rollback lógico)
- Trazabilidad de estados

### Sesión VI — Extraer Microservicio (Payments)
- Payments como microservicio independiente
- Base de datos propia
- Contratos API/eventos entre monolito y servicio

### Sesión VII — API Gateway
- Entrada única `/api`
- Enrutamiento inteligente
- Auth, rate-limit, logging centralizado

### Sesión VIII — CQRS
- Separar comandos y consultas
- Read models optimizadas
- Proyecciones desde eventos

---

## 🚀 Flujo de Trabajo (Por Sesión)

1. **Checkout develop, crear rama sesión**
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b session-X-description
   git push -u origin session-X-description
   ```

2. **Trabajar con pequeños commits**
   ```bash
   git commit -m "session-X: descripción"
   git push origin session-X-description
   ```

3. **Abrir PR y mergear a develop**
   - Pull request hacia `develop`
   - Merge after approve
   - Etiquetar con `vX-session-N`

4. **Cuando develop está estable: merge a main**
   ```bash
   git checkout main
   git pull origin main
   git merge --no-ff develop
   git tag v-session-N
   git push origin main --tags
   ```

---

## 📝 Notas

- **Modularización:** Ya existe en el código (7 módulos claros)
- **Tests:** Requiere cobertura > 80% para nuevas features
- **Migrations:** Validar con `python manage.py check && python manage.py makemigrations --check --dry-run`
- **Backward Compatibility:** Tablas mantienen `app_label = "gym"` para no renombrar en DB

