# MedBridge Backend — API Reference

## Base URL

```
https://medbridge-backend.onrender.com
```

> Update once your Render service is live.

---

## Environment Variables

| Key | Description |
|-----|-------------|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anon/public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (bypasses RLS) |
| `GROQ_API_KEY` | Groq API key (`gsk_...`) |
| `MCP_SERVER_URL` | MCP server base URL |
| `MCP_SECRET_KEY` | Shared secret for MCP calls |
| `JWT_SECRET` | From Supabase → Settings → API → JWT Secret |

---

## Auth

All protected endpoints require:
```
Authorization: Bearer <supabase_jwt>
```

Public (no auth): `POST /auth/register`, `POST /auth/login`, `GET /health`,
`GET /doctors/search`, `GET /doctors/{id}`, `GET /doctors/{id}/availability`,
`GET /doctors/{id}/ratings`

---

## Endpoints

### Health
```
GET /health
```
**Response:** `{ "status": "ok", "service": "medbridge-backend" }`

---

### Auth

#### Register
```
POST /auth/register
```
**Body:**
```json
{
  "email": "user@example.com",
  "password": "secret123",
  "full_name": "Arun Kumar",
  "phone": "+919876543210",
  "role": "patient",              // patient | doctor | nurse | receptionist | admin
  "language_preference": "ta"
}
```
**Response:**
```json
{ "user_id": "uuid", "access_token": "eyJ...", "role": "patient" }
```

#### Login
```
POST /auth/login
```
**Body:** `{ "email": "...", "password": "..." }`

**Response:**
```json
{
  "access_token": "eyJ...",
  "user_id": "uuid",
  "role": "patient",
  "full_name": "Arun Kumar"
}
```

#### Logout
```
POST /auth/logout
Authorization: Bearer <token>
```
**Response:** `{ "success": true }`

---

### Doctors

#### Search Doctors
```
GET /doctors/search?symptoms=chest+pain&lat=13.08&lng=80.27&radius_km=20&specialization=Cardiologist&language=ta
```
Public. Returns top 5 doctors sorted by distance then rating.

**Response:**
```json
[
  {
    "doctor_id": "uuid",
    "name": "Dr. Arun Kumar",
    "specialization": "Cardiologist",
    "clinic_name": "Apollo Clinic",
    "clinic_address": "Anna Nagar, Chennai",
    "languages_spoken": ["Tamil", "English"],
    "rating": 4.8,
    "consultation_fee": 500,
    "distance_km": 3.2
  }
]
```

#### Get Doctor Profile
```
GET /doctors/{doctor_id}
```
Public. Returns full doctor profile + `availability_hint`.

#### Get Availability
```
GET /doctors/{doctor_id}/availability?date=2025-07-15
```
Public.

**Response:** `{ "available_slots": ["09:00", "09:30", "10:30", "14:00"] }`

#### Get Ratings
```
GET /doctors/{doctor_id}/ratings
```
Public.

**Response:**
```json
{
  "avg_rating": 4.6,
  "total_reviews": 38,
  "recent_reviews": [{ "rating": 5, "feedback": "...", "language": "en", "created_at": "..." }]
}
```

#### Update Doctor Profile
```
PUT /doctors/profile
Authorization: Bearer <doctor_token>
```
**Body (all fields optional):**
```json
{
  "specialization": "Cardiologist",
  "clinic_name": "City Heart Clinic",
  "clinic_address": "Anna Nagar, Chennai",
  "languages_spoken": ["Tamil", "English"],
  "consultation_fee": 600,
  "bio": "15 years experience in interventional cardiology"
}
```
**Response:** `{ "success": true }`

---

### Appointments

#### Book Appointment
```
POST /appointments
Authorization: Bearer <patient_token>
```
**Body:**
```json
{
  "doctor_id": "uuid",
  "scheduled_at": "2025-07-15T10:00:00+05:30",
  "symptoms_text": "Chest pain and shortness of breath",
  "symptoms_language": "en",
  "is_urgent": false
}
```
**Response:**
```json
{
  "appointment_id": "uuid",
  "status": "pending",
  "scheduled_at": "2025-07-15T10:00:00+05:30",
  "doctor_name": "Dr. Arun Kumar"
}
```

#### List Appointments
```
GET /appointments
Authorization: Bearer <token>
```
Returns appointments for current user based on role:
- **patient** → their own appointments (all, desc)
- **doctor** → their pending/confirmed appointments (asc)
- **nurse/receptionist** → their assigned doctor's upcoming appointments

#### Get Appointment
```
GET /appointments/{appointment_id}
Authorization: Bearer <token>
```

#### Update Appointment Status
```
PATCH /appointments/{appointment_id}/status
Authorization: Bearer <doctor/nurse/receptionist/admin_token>
```
**Body:**
```json
{ "status": "confirmed", "notes": "" }
// status: confirmed | cancelled | completed
// If status=completed, calls MCP complete_appointment and triggers 24h data cleanup
```

---

### Sub-accounts (Nurse / Receptionist)

#### Create Sub-account
```
POST /sub-accounts
Authorization: Bearer <doctor_token>
```
**Body:**
```json
{
  "email": "nurse@clinic.com",
  "full_name": "Priya S",
  "phone": "+919876500001",
  "role": "nurse"   // nurse | receptionist
}
```
**Response:**
```json
{
  "sub_account_id": "uuid",
  "email": "nurse@clinic.com",
  "role": "nurse",
  "temp_password": "randomly_generated",
  "message": "Sub-account created. Share the temp_password with the user to log in."
}
```

#### List Sub-accounts
```
GET /sub-accounts
Authorization: Bearer <doctor_token>
```

#### Deactivate Sub-account
```
DELETE /sub-accounts/{sub_account_id}
Authorization: Bearer <doctor_token>
```

---

### Documents

#### Upload Document Metadata
```
POST /documents/upload-meta
Authorization: Bearer <patient/doctor/nurse_token>
```
> Upload the actual file to Supabase Storage first, then call this endpoint with the resulting URL.

**Body:**
```json
{
  "patient_id": "uuid",
  "appointment_id": "uuid",         // optional
  "doc_type": "lab_report",         // lab_report | prescription | scan | other
  "file_url": "https://storage.supabase.co/...",
  "file_name": "blood_test.pdf",
  "description": "CBC report June 2025"
}
```
**Response:** `{ "document_id": "uuid" }`

#### List Documents
```
GET /documents
Authorization: Bearer <token>
```
Patients see their own documents. Doctors see consented documents.

#### Grant Doctor Access
```
POST /documents/{document_id}/grant-access
Authorization: Bearer <patient_token>
```
**Body:** `{ "doctor_id": "uuid" }`

#### Revoke Doctor Access
```
DELETE /documents/{document_id}/revoke-access/{doctor_id}
Authorization: Bearer <patient_token>
```

---

### Prescriptions

#### Create Prescription (generates PDF automatically)
```
POST /prescriptions
Authorization: Bearer <doctor_token>
```
**Body:**
```json
{
  "appointment_id": "uuid",
  "medicines": [
    {
      "name": "Aspirin",
      "dosage": "75mg",
      "frequency": "Once daily",
      "duration": "30 days",
      "instructions": "Take after food"
    }
  ],
  "notes": "Patient advised to rest and follow up in 2 weeks."
}
```
**Response:**
```json
{ "prescription_id": "uuid", "pdf_url": "https://storage.supabase.co/...", "success": true }
```

#### Get Prescription
```
GET /prescriptions/{appointment_id}
Authorization: Bearer <doctor/patient_token>
```
Returns prescription + medicine list.

---

### Reviews

#### Submit Review
```
POST /reviews
Authorization: Bearer <patient_token>
```
**Body:**
```json
{
  "appointment_id": "uuid",
  "rating": 5,
  "feedback_text": "Excellent consultation!",
  "feedback_language": "en"
}
```
> Appointment must have `status = "completed"`.

**Response:** `{ "success": true }`

---

### Notifications

#### List Unread Notifications
```
GET /notifications
Authorization: Bearer <token>
```
Returns up to 50 unread notifications for the current user.

**Response:**
```json
[
  {
    "id": "uuid",
    "title": "Appointment Confirmed",
    "body": "Your appointment with Dr. Kumar is confirmed.",
    "type": "appointment",
    "reference_id": "uuid",
    "is_read": false,
    "created_at": "2025-07-14T09:00:00Z"
  }
]
```

#### Mark Notification Read
```
PATCH /notifications/{notification_id}/read
Authorization: Bearer <token>
```

---

### Chat

#### REST Chat (single turn)
```
POST /chat
Authorization: Bearer <token>
```
**Body:**
```json
{
  "message": "I have chest pain, which doctor should I see?",
  "session_id": "uuid",    // optional — omit to start new session
  "lat": 10.7905,          // optional — for nearby doctor search
  "lng": 78.7047
}
```
**Response:**
```json
{
  "session_id": "uuid",
  "response": "These symptoms may indicate a cardiac issue. I found 3 cardiologists near you..."
}
```

#### WebSocket Streaming Chat
```
WS /chat/ws?session_id={uuid}&token={jwt}
```

**Connect:** Open WebSocket with session_id and JWT as query params.

**Send message:**
```json
{ "message": "I have a fever", "lat": 10.79, "lng": 78.70 }
```

**Receive chunks:**
```json
{ "chunk": "These symptoms", "done": false }
{ "chunk": " may indicate...", "done": false }
{ "chunk": "", "done": true, "full": "These symptoms may indicate..." }
```

**JavaScript example:**
```javascript
const ws = new WebSocket(
  `wss://medbridge-backend.onrender.com/chat/ws?session_id=${sessionId}&token=${accessToken}`
);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.chunk) appendToUI(data.chunk);
  if (data.done) finalizeMessage(data.full);
};

ws.send(JSON.stringify({
  message: "I have chest pain",
  lat: 10.7905,
  lng: 78.7047
}));
```

---

### Admin

#### List Pending Doctor Verifications
```
GET /admin/pending-doctors
Authorization: Bearer <admin_token>
```

#### Verify Doctor
```
PATCH /admin/doctors/{doctor_id}/verify
Authorization: Bearer <admin_token>
```

#### Get Audit Logs
```
GET /admin/audit-logs
Authorization: Bearer <admin_token>
```

#### Trigger Cleanup
```
POST /admin/cleanup
Authorization: Bearer <admin_token>
```
Calls MCP `cleanup_expired_shared_data`.

---

## Render Deployment

1. Push this repo to GitHub.
2. Go to [render.com](https://render.com) → **New → Web Service**.
3. Connect your GitHub repo.
4. Render auto-detects `render.yaml`. Confirm:
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Set all 7 environment variables in the Render dashboard (they are `sync: false`).
6. Deploy. Health check: `GET /health`.

---

## Important Notes for Frontend

- **Timestamps:** Always send `scheduled_at` in IST: `"2025-07-15T10:00:00+05:30"`
- **File uploads:** Upload files directly to Supabase Storage from the frontend, then call `POST /documents/upload-meta` with the resulting URL. Never proxy file bytes through this backend.
- **Session IDs:** Generate a UUID on the frontend for each chat session. Pass it in every `/chat` call to maintain conversation context.
- **WebSocket auth:** Pass the JWT as a query param `?token=...`. Do not put it in headers (browsers don't support WS auth headers).
- **Language detection:** The AI agent auto-detects user language. You don't need to send it explicitly in chat requests.
- **Doctor role after register:** Doctor accounts start as `is_verified=false`. They cannot be searched until an admin verifies them via `PATCH /admin/doctors/{id}/verify`.
- **CORS:** Currently `allow_origins=["*"]`. Tighten to your frontend domain before production.
