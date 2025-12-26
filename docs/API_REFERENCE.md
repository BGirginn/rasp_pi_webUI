# API Reference - Pi Control Panel (AR-First)

## Base URL

```
https://<host>/api
```

## Authentication

All endpoints except `/api/auth/login` and `/api/auth/first-run/create-owner`
require a valid JWT access token.

### Headers

```http
Authorization: Bearer <access_token>
```

## Auth Endpoints (`/api/auth`)

### Login

```http
POST /api/auth/login
```

```json
{
  "username": "owner",
  "password": "your-password",
  "totp_code": "123456"
}
```

### Refresh Token

```http
POST /api/auth/refresh
```

Uses HttpOnly `refresh_token` cookie.

### Logout

```http
POST /api/auth/logout
```

### Current User

```http
GET /api/auth/me
```

### First-Run Owner Creation

```http
POST /api/auth/first-run/create-owner
```

```json
{
  "username": "owner",
  "password": "long-temporary-password"
}
```

Returns 409 if first-run is already complete.

## Actions API (`/api/actions`)

All mutations go through the Actions API.

### List Actions

```http
GET /api/actions
```

Returns actions filtered by current role.

### Execute Action

```http
POST /api/actions/execute
```

```json
{
  "action_id": "svc.restart",
  "params": { "service": "ssh" },
  "confirm": true
}
```

Response includes optional rollback info:

```json
{
  "success": true,
  "data": {},
  "rollback": {
    "job_id": "uuid",
    "due_in_seconds": 30
  }
}
```

### Confirm Rollback

```http
POST /api/actions/confirm
```

```json
{
  "rollback_job_id": "uuid"
}
```

## Read-Only Endpoints (Examples)

- `GET /api/resources`
- `GET /api/telemetry/current`
- `GET /api/logs`
- `GET /api/alerts`
- `GET /api/jobs`
- `GET /api/network/interfaces`
- `GET /api/devices`

## Deprecated Mutation Endpoints

These return `410 Gone` and should not be used:
- `POST /api/resources/{resource_id}/action`
- `POST /api/system/reboot`
- `POST /api/system/shutdown`
- `POST /api/system/update`
- `POST /api/network/wifi/toggle`
