# Mobile App Authentication API Documentation

## Base URL
```
http://127.0.0.1:8088/api  (Development)
https://api.viwear.tech/api  (Production)
```

## Authentication Method
All authenticated endpoints require a JWT token in the Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

---

## Endpoints

### 1. Email/Password Login
**POST** `/api/auth/login/`

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

**Success Response (200):**
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  }
}
```

**Error Response (400/401):**
```json
{
  "error": "Invalid email or password"
}
```

---

### 2. Email/Password Signup
**POST** `/api/auth/signup/`

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "yourpassword",
  "first_name": "John",  // Optional
  "last_name": "Doe"     // Optional
}
```

**Success Response (201):**
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  }
}
```

**Error Response (400):**
```json
{
  "error": "User with this email already exists"
}
```
or
```json
{
  "error": "Password must be at least 8 characters long"
}
```

---

### 3. Google OAuth Authentication
**POST** `/api/auth/google/`

**Request Body:**
```json
{
  "token": "<google_id_token_from_mobile_sdk>"
}
```

**Note:** The mobile app should use Google Sign-In SDK to get an ID token, then send it to this endpoint.

**Success Response (200):**
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "user": {
    "id": 1,
    "email": "user@gmail.com",
    "first_name": "John",
    "last_name": "Doe"
  }
}
```

**Error Response (400/401):**
```json
{
  "error": "Invalid Google token: <error_message>"
}
```

---

### 4. Get Current User Info
**GET** `/api/auth/user/`

**Headers:**
```
Authorization: Bearer <your_jwt_token>
```

**Success Response (200):**
```json
{
  "id": 1,
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Error Response (401):**
```json
{
  "detail": "Authentication credentials were not provided."
}
```

---

### 5. Logout
**POST** `/api/auth/logout/`

**Headers:**
```
Authorization: Bearer <your_jwt_token>
```

**Success Response (200):**
```json
{
  "message": "Logged out successfully"
}
```

**Note:** The client should discard the token after logout. The token remains valid until it expires (30 days).

---

## Token Details

- **Token Type:** JWT (JSON Web Token)
- **Expiration:** 30 days
- **Algorithm:** HS256
- **Usage:** Include in `Authorization` header as `Bearer <token>`

---

## Testing Examples

### Using cURL

**Login:**
```bash
curl -X POST http://127.0.0.1:8088/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "testpassword123"}'
```

**Get User Info:**
```bash
curl -X GET http://127.0.0.1:8088/api/auth/user/ \
  -H "Authorization: Bearer <your_token_here>"
```

### Using JavaScript/Fetch

**Login:**
```javascript
const response = await fetch('http://127.0.0.1:8088/api/auth/login/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    email: 'test@example.com',
    password: 'testpassword123'
  })
});

const data = await response.json();
// Store data.token for future requests
```

**Authenticated Request:**
```javascript
const response = await fetch('http://127.0.0.1:8088/api/auth/user/', {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  }
});

const userData = await response.json();
```

---

## Error Handling

All endpoints return standard HTTP status codes:
- **200:** Success
- **201:** Created (signup)
- **400:** Bad Request (validation errors)
- **401:** Unauthorized (invalid credentials or missing token)
- **500:** Internal Server Error

Error responses follow this format:
```json
{
  "error": "Error message here"
}
```

---

## Notes for Mobile App Development

1. **Token Storage:** Store the JWT token securely (e.g., Keychain on iOS, Keystore on Android)
2. **Token Refresh:** Tokens expire after 30 days. Implement token refresh or re-authentication flow
3. **Google Sign-In:** Use the official Google Sign-In SDK for your platform to get the ID token
4. **Error Handling:** Always check response status codes and handle errors appropriately
5. **CORS:** CORS is configured to allow all origins in development. In production, configure specific origins.

---

## Environment Variables Needed

Make sure these are set in your `.env` file:
- `GOOGLE_CLIENT_ID` - Your Google OAuth client ID
- `GOOGLE_CLIENT_SECRET` - Your Google OAuth client secret (for web, not needed for mobile)
- `DJANGO_SECRET_KEY` - Django secret key (used for JWT signing)

---

