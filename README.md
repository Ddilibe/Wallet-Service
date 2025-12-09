# Wallet-Service
# Wallet Service API

## Overview
A robust and secure backend wallet service built with **FastAPI** and **SQLModel**, designed to manage user finances. This system facilitates secure deposits via **Paystack**, enables internal wallet-to-wallet transfers, provides comprehensive transaction history, and supports versatile authentication mechanisms including **JWT** for user access and a sophisticated **API Key management system** for service-to-service interactions.

## Features
- **FastAPI**: Leverages the high performance and intuitive design of FastAPI for building efficient API endpoints.
- **SQLModel**: An elegant ORM for database interactions, supporting both SQLite (for development) and PostgreSQL.
- **Paystack Integration**: Seamlessly handles wallet deposits via Paystack, incorporating mandatory webhook verification for transaction integrity.
- **JWT Authentication**: Users can authenticate through Google Sign-in, receiving JWTs for secure access to their wallet features.
- **API Key Management**: Provides granular control over service-to-service access with features like permission-based keys, expiration, rollover functionality, and active key limits.
- **Core Wallet Operations**: Manages fundamental wallet functionalities including balance inquiry, fund transfers between users, and detailed transaction history.
- **Alembic**: Utilizes Alembic for robust and trackable database migrations, ensuring smooth schema evolution.

## Getting Started

### Installation
To get a local copy up and running, follow these steps.

1.  **Clone the Repository**:
    ✨ Clone the project from GitHub:
    ```bash
    git clone git@github.com:Ddilibe/Wallet-Service.git
    cd Wallet-Service
    ```

2.  **Create and Activate Virtual Environment**:
    🐍 Ensure you have Python 3.12 installed, then create and activate a virtual environment:
    ```bash
    python3.12 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies**:
    📦 Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    # or if using uv
    # uv pip install -r requirements.txt
    ```

4.  **Database Migrations**:
    🚀 Apply the database migrations using Alembic to set up the schema:
    ```bash
    alembic upgrade head
    ```

5.  **Run the Application**:
    ▶️ Start the FastAPI application using Uvicorn:
    ```bash
    uvicorn main:app --reload
    ```
    The API will be accessible at `http://127.0.0.1:8000`.

### Environment Variables
Create a `.env` file in the project root based on `.env.example` and populate it with the following required environment variables:

-   `DATABASE_URL`: The connection string for your database. Example for SQLite: `sqlite+aiosqlite:///walletservice.db`. For PostgreSQL: `postgresql://user:password@host:port/database`.
-   `JWT_SECRET`: A strong, confidential key used for signing JWT tokens.
-   `JWT_ALGORITHM`: The algorithm used for JWT signing (e.g., `HS256`).
-   `JWT_EXPIRATION`: The expiration time for JWT tokens in seconds (e.g., `3600` for 1 hour).
-   `PAYSTACK_SECRET_KEY`: Your confidential Paystack secret key.
-   `PAYSTACK_PUBLIC_KEY`: Your Paystack public key.

Example `.env` configuration:
```
DATABASE_URL=sqlite+aiosqlite:///walletservice.db
JWT_SECRET=your_super_secret_jwt_key_here_please_change
JWT_ALGORITHM=HS256
JWT_EXPIRATION=3600
```

## Usage

Once the server is running, you can interact with the API endpoints using tools like `curl`, Postman, or through the interactive API documentation available at `http://127.0.0.1:8000/docs` (Swagger UI) or `http://127.0.0.1:8000/redoc` (ReDoc).

**Authentication**:
Users obtain a JWT token by initiating the Google OAuth flow. For service-to-service access, API keys can be generated.

1.  **Initiate Google Login (simulated)**:
    ```bash
    curl -X GET "http://127.0.0.1:8000/auth/google"
    # This would typically redirect to Google for authentication.
    ```
2.  **Handle Google Callback (simulated)**:
    ```bash
    curl -X GET "http://127.0.0.1:8000/auth/google/callback"
    # This would return a JWT token upon successful "login" in a real scenario.
    # For this example, assume you get a JWT_TOKEN for a user.
    ```

**API Key Generation**:
```bash
# Assuming you have a JWT_TOKEN from /auth/google/callback
curl -X POST "http://127.0.0.1:8000/keys/create" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
           "name": "my-service-key",
           "permissions": ["deposit", "read"],
           "expiry": "1D"
         }'
```
This will return an API key (e.g., `sk_xxxxxxxx.fingerprint`).

**Making a Deposit with API Key**:
```bash
# Using the API_KEY obtained from /keys/create
curl -X POST "http://127.0.0.1:8000/wallet/deposit" \
     -H "X-API-KEY: YOUR_API_KEY_WITH_DEPOSIT_PERM" \
     -H "Content-Type: application/json" \
     -d '{
           "amount": 100000
         }' # amount in kobo, e.g., 100000 = NGN 1000
```

## API Documentation
### Base URL
The API is served from the root path (`/`).

### Endpoints
#### GET /auth/google
Initiates the Google OAuth login flow.
**Request**:
No request body.
**Response**:
```json
{}
```
**Errors**:
- None explicitly defined in code, assumes successful redirection or basic HTTP errors.

#### GET /auth/google/callback
Handles the Google OAuth callback, logs in the user, creates a new user if necessary, and returns a JWT token.
**Request**:
No request body.
**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```
**Errors**:
- `401 Unauthorized`: If Google authentication fails or token is invalid.

#### POST /keys/create
Creates a new API key for the authenticated user with specified permissions and expiry. A user can have a maximum of 5 active API keys.
**Authentication**: JWT (user principal)
**Request**:
```json
{
  "name": "wallet-service-access",
  "permissions": ["deposit", "transfer", "read"],
  "expiry": "1D"
}
```
**Response**:
```json
{
  "expires_at": "2025-01-01T12:00:00Z"
}
```
**Errors**:
- `401 Unauthorized`: If not authenticated as a user.
- `400 Bad Request`: If the user already has 5 active API keys, or invalid expiry format.
- `403 Forbidden`: Insufficient permissions (if API key is used).

#### POST /keys/rollover
Creates a new API key with the same permissions as an existing *expired* key. The expired key must belong to the authenticated user.
**Authentication**: JWT (user principal)
**Request**:
```json
{
  "expired_key_id": 123,
  "expiry": "1M"
}
```
**Response**:
```json
{
  "api_key": "sk_live_newkeyhash.newfingerprint",
  "expires_at": "2025-02-01T12:00:00Z"
}
```
**Errors**:
- `401 Unauthorized`: If not authenticated as a user.
- `404 Not Found`: If the `expired_key_id` does not correspond to an API key owned by the user or is already revoked.
- `400 Bad Request`: If the specified API key is not yet expired.
- `403 Forbidden`: Insufficient permissions (if API key is used).

#### POST /wallet/deposit
Initializes a deposit transaction via Paystack. Returns an authorization URL for the user to complete payment.
**Authentication**: JWT (user principal) or API Key with `deposit` permission.
**Request**:
```json
{
  "amount": 5000
}
```
**Response**:
```json
{
  "reference": "ps_xxxxxxxxxxxxxx",
  "authorization_url": "https://paystack.co/checkout/..."
}
```
**Errors**:
- `401 Unauthorized`: If authentication fails.
- `403 Forbidden`: Insufficient permissions (if API key does not have `deposit` permission).
- `404 Not Found`: If the user's wallet is not found.
- `502 Bad Gateway`: If Paystack transaction initialization fails.

#### POST /wallet/paystack/webhook
Receives and processes Paystack webhook notifications. This endpoint verifies the Paystack signature and updates the transaction status and wallet balance upon successful payment.
**Request**:
Paystack webhook payload (example):
```json
{
  "event": "charge.success",
  "data": {
    "id": 123456789,
    "domain": "test",
    "status": "success",
    "reference": "ps_xxxxxxxxxxxxxx",
    "amount": 500000,
    "message": null,
    "gateway_response": "Successful",
    "paid_at": "2025-01-01T12:00:00.000Z",
    "created_at": "2025-01-01T11:50:00.000Z",
    "channel": "card",
    "currency": "NGN",
    "ip_address": "192.168.1.1",
    "metadata": {},
    "log": null,
    "fees": 7500,
    "customer": {
      "id": 987654,
      "first_name": "John",
      "last_name": "Doe",
      "email": "john.doe@example.com",
      "customer_code": "CUS_xxxxxxxxx",
      "phone": null,
      "metadata": null,
      "risk_action": "default"
    },
    "authorization": {
      "authorization_code": "AUTH_xxxxxxxx",
      "bin": "408408",
      "last4": "4081",
      "exp_month": "01",
      "exp_year": "2025",
      "channel": "card",
      "card_type": "visa ",
      "bank": "TEST BANK",
      "country_code": "NG",
      "brand": "visa",
      "reusable": true,
      "signature": "pk_test_xxxxxxxxxx",
      "account_name": null
    },
    "plan": null,
    "subaccount": null,
    "split": {},
    "order_id": null,
    "paidAt": "2025-01-01T12:00:00.000Z",
    "createdAt": "2025-01-01T11:50:00.000Z",
    "requested_amount": 500000,
    "pos_transaction_data": null,
    "source": {
      "type": "api"
    },
    "fees_breakdown": null,
    "transaction_date": "2025-01-01T12:00:00.000Z"
  }
}
```
**Response**:
```json
{
  "status": true
}
```
**Errors**:
- `400 Bad Request`: If `x-paystack-signature` header is missing or invalid.
- No explicit errors for transaction not found or already processed (idempotency handled by returning `{"status": true}`).

#### GET /wallet/deposit/{reference}/status
Retrieves the status of a specific deposit transaction. This endpoint does not credit wallets.
**Authentication**: JWT (user principal) or API Key with `read` permission.
**Request**:
No request body.
**Response**:
```json
{
  "reference": "ps_xxxxxxxxxxxxxx",
  "status": "success",
  "amount": 5000
}
```
**Errors**:
- `401 Unauthorized`: If authentication fails.
- `403 Forbidden`: Insufficient permissions (if API key does not have `read` permission).
- `404 Not Found`: If the transaction reference does not exist.

#### GET /wallet/balance
Retrieves the current balance of the authenticated user's wallet.
**Authentication**: JWT (user principal) or API Key with `read` permission.
**Request**:
No request body.
**Response**:
```json
{
  "balance": 15000.00
}
```
**Errors**:
- `401 Unauthorized`: If authentication fails.
- `403 Forbidden`: Insufficient permissions (if API key does not have `read` permission).
- `404 Not Found`: If the user's wallet is not found.

#### POST /wallet/transfer
Transfers a specified amount from the authenticated user's wallet to another user's wallet identified by their wallet number.
**Authentication**: JWT (user principal) or API Key with `transfer` permission.
**Request**:
```json
{
  "wallet_number": "4566678954356",
  "amount": 3000
}
```
**Response**:
```json
{
  "status": "success",
  "message": "Transfer completed"
}
```
**Errors**:
- `401 Unauthorized`: If authentication fails.
- `403 Forbidden`: Insufficient permissions (if API key does not have `transfer` permission).
- `404 Not Found`: If the recipient wallet is not found.
- `400 Bad Request`: If the sender has insufficient balance.

#### GET /wallet/transactions
Retrieves the transaction history for the authenticated user's wallet.
**Authentication**: JWT (user principal) or API Key with `read` permission.
**Request**:
No request body.
**Response**:
```json
[
  {
    "type": "deposit",
    "amount": 5000,
    "status": "success",
    "reference": "ps_xxxxxxxxxxxxxx"
  },
  {
    "type": "transfer",
    "amount": -3000,
    "status": "success",
    "reference": "tr_yyyyyyyyyyyyyy"
  },
  {
    "type": "transfer",
    "amount": 3000,
    "status": "success",
    "reference": "tr_yyyyyyyyyyyyyy"
  }
]
```
**Errors**:
- `401 Unauthorized`: If authentication fails.
- `403 Forbidden`: Insufficient permissions (if API key does not have `read` permission).
- `404 Not Found`: If the user's wallet is not found.

## Technologies Used

| Technology         | Description                                                          | Link                                                       |
| :----------------- | :------------------------------------------------------------------- | :--------------------------------------------------------- |
| **Python**         | Primary programming language                                         | [Python.org](https://www.python.org/)                      |
| **FastAPI**        | High-performance web framework for building APIs                     | [FastAPI.tiangolo.com](https://fastapi.tiangolo.com/)      |
| **SQLModel**       | ORM with Pydantic for defining database models                       | [SQLModel.tiangolo.com](https://sqlmodel.tiangolo.com/)    |
| **SQLAlchemy**     | SQL toolkit and ORM, underlying SQLModel                             | [SQLAlchemy.org](https://www.sqlalchemy.org/)              |
| **Alembic**        | Lightweight database migration tool for SQLAlchemy                   | [Alembic.sqlalchemy.org](https://alembic.sqlalchemy.org/)  |
| **PyJWT**          | Python implementation of JSON Web Tokens                             | [PyJWT](https://pyjwt.readthedocs.io/)                     |
| **Paystack API**   | Payment gateway for online transactions                              | [Paystack Developers](https://paystack.com/developers)     |
| **HTTpx**          | Next-generation HTTP client for Python                               | [HTTpx](https://www.python-httpx.org/)                     |
| **python-decouple**| Strict separation of settings from code                              | [Python-Decouple](https://pypi.org/project/python-decouple/)|
| **python-dotenv**  | Reads key-value pairs from a `.env` file                             | [Python-Dotenv](https://pypi.org/project/python-dotenv/)   |
| **Uvicorn**        | ASGI server for FastAPI applications                                 | [Uvicorn](https://www.uvicorn.org/)                        |
| **aiosqlite**      | Asynchronous SQLite driver                                           | [aiosqlite](https://pypi.org/project/aiosqlite/)           |
| **psycopg2-binary**| PostgreSQL database adapter for Python                               | [psycopg2-binary](https://pypi.org/project/psycopg2-binary/)|

## Author Info
- **GitHub**: [Ddilibe](https://github.com/Ddilibe)
- **LinkedIn**: [Your LinkedIn Profile](https://linkedin.com/in/yourprofile)
- **Twitter**: [Your Twitter Handle](https://twitter.com/yourhandle)

---
<p align="center">
  <a href="https://www.python.org/" target="_blank">
    <img src="https://img.shields.io/badge/Python-3.12-blue.svg" alt="Python Version">
  </a>
  <a href="https://fastapi.tiangolo.com/" target="_blank">
    <img src="https://img.shields.io/badge/FastAPI-0.124.0-009688.svg" alt="FastAPI Version">
  </a>
  <a href="https://sqlmodel.tiangolo.com/" target="_blank">
    <img src="https://img.shields.io/badge/SQLModel-0.0.27-red.svg" alt="SQLModel Version">
  </a>
  <a href="https://alembic.sqlalchemy.org/en/latest/" target="_blank">
    <img src="https://img.shields.io/badge/Alembic-1.17.2-orange.svg" alt="Alembic Version">
  </a>
  <img src="https://img.shields.io/badge/Status-Active-brightgreen" alt="Project Status">
</p>

[![Readme was generated by Dokugen](https://img.shields.io/badge/Readme%20was%20generated%20by-Dokugen-brightgreen)](https://www.npmjs.com/package/dokugen)