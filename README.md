# FitPass Gym API

Backend Django para sedes, clases, lista de espera, asistencia, check-in, productos,
promociones y entrenamiento virtual.

## Inicio rápido

```powershell
pip install -r requirements.txt
$env:POSTGRES_PASSWORD="tu-clave-postgres"
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

La conexión predeterminada usa PostgreSQL en `localhost:5432`, base de datos
`fitpass` y usuario `postgres`. Todos los valores se pueden cambiar con las
variables mostradas en `.env.example`; Django no carga archivos `.env`
automáticamente, por lo que deben exportarse en el entorno antes de arrancar.

La administración está en `/admin/` y la API en `/api/`. Los endpoints que modifican
datos requieren una sesión Django autenticada. Los gateways de pago y puertas usados
localmente son simulados y se sustituyen mediante `FITPASS_PAYMENT_GATEWAY` y
`FITPASS_DOOR_GATEWAY`.

## Endpoints

- `GET /api/gyms/nearby/?lat=-16.5&lon=-68.15&radius_km=10`
- `GET /api/classes/?gym_id=1`
- `POST /api/classes/{id}/bookings/`
- `POST /api/bookings/{id}/cancel/`
- `POST /api/bookings/{id}/attendance/` con `{"attended": true}`
- `POST /api/gyms/{id}/check-ins/`
- `GET /api/products/`
- `POST /api/products/{id}/purchases/` con `payment_token` y `promotion_code` opcional
- `GET /api/workouts/`
