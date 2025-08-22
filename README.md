# 📚 Library API

Django REST API for managing **books, borrowings, and payments** with integration of **Stripe** for online payments and
**Telegram** for notifications.  
Supports **JWT authentication**, **Celery background tasks**, and **Swagger/Redoc** API docs powered by drf-spectacular.

---

## 🚀 Features

- **Books**: CRUD for books (admin-only for write operations).
- **Borrowings**:
    - Users can borrow books (inventory automatically decreased).
    - On return, inventory is restored.
    - Overdue borrowings generate **fine payments** via Stripe.
    - Notifications sent to Telegram bot.
- **Payments**:
    - Stripe Checkout sessions for borrowings and fines.
    - Endpoints for renewing expired sessions, success/cancel callbacks.
- **Permissions**:
    - Books: anyone can list, authenticated users can retrieve, admin required for create/update/delete.
    - Borrowings: users see only their own, staff can filter by `user_id`.
    - Payments: users see only their own, staff see all.
- **Background tasks** with **Celery + Redis** (e.g. periodic checks, notifications).
- **OpenAPI schema & Swagger/Redoc UI** via drf-spectacular.

---

## 🛠️ Stack

- [Python 3.12](https://www.python.org/)
- [Django](https://www.djangoproject.com/) + [Django REST Framework](https://www.django-rest-framework.org/)
- [PostgreSQL](https://www.postgresql.org/) as database
- [Redis](https://redis.io/) as Celery broker/result backend
- [Celery](https://docs.celeryq.dev/) for async/background jobs
- [Stripe](https://stripe.com/) for payments
- [drf-spectacular](https://drf-spectacular.readthedocs.io/) for API schema/docs
- [Docker](https://www.docker.com/) + Docker Compose for environment management

---

## 🏃 How to run

### 1. Clone the repository

```bash
git clone https://github.com/yourname/library-api.git
cd library-api
```

### 2. Create .env file according to .env.sample
### 3. `docker-compose up --build`
### 4. create superuser 
    `docker compose exec web python manage.py createsuperuser`
### 5. Access the app:
    1. Django API: http://localhost:8000
    2. Swagger UI: http://localhost:8000/api/schema/swagger-ui/
### 6. Background services:
   1. Celery worker: runs automatically (celery -A library_service worker -l info)
   2. Celery beat: runs automatically for scheduled tasks
   3. Redis: runs as broker & result backend
   4. Postgres: persists data in Docker volume pg_data
### 7. Run tests `docker compose exec web pytest`



