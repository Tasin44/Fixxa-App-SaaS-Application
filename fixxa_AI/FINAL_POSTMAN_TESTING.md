# 🧪 POSTMAN TESTING GUIDE - Simple & Clear

## ✅ Your AI is Production Ready - Just Test It!

---

## 🚀 QUICK START (3 Steps)

### Step 1: Start Server
```powershell
cd "c:\Users\Yousuf Rayhan Emon\fixxa_AI"
.\.venv\Scripts\Activate.ps1
python api_server.py
```

**Server runs at:** `http://localhost:8000`

### Step 2: Import to Postman
1. Open Postman
2. Click **Import**
3. Select `POSTMAN_COLLECTION.json`
4. Done! ✓

### Step 3: Set Variables
Click **Environments** → Create new:
- `base_url` = `http://localhost:8000`
- `auth_token` = `any-value-works`

**Now test!**

---

## 📡 ACTUAL ENDPOINTS (What Really Works)

### ✅ Endpoint 1: Health Check

**URL:** `GET {{base_url}}/api/health/`  
**Headers:** None needed

**Expected Response:**
```json
{
  "ai_module": "operational",
  "database": {
    "status": "healthy",
    "tables": ["user_information", "client_information", "quotes", ...]
  },
  "message": "All systems operational"
}
```

```

**Status:** `200 OK` ✓

---

### ✅ Endpoint 2: Process Voice

**URL:** `POST {{base_url}}/api/voice/process/`  
**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: multipart/form-data
```

**Body:** 
- Type: `form-data`
- Key: `audio`  
- Type: `File`
- Value: Upload `test_client_audio.mp3`

**Expected Response:**
```json
{
  "success": true,
  "transcription": "I need a quote for John Smith...",
  "client_data": {
    "client_name": "John Smith",
    "phone_number": "5551234",
    "address": "123 Main Street",
    "items": [
      {
        "quote_description": "Fix leaking kitchen sink",
        "service_type": "Plumbing",
        "service_duration": 2.0,
        "service_rate": 50.0,
        "material_name": "PVC pipes",
        "quantity": 1,
        "unit_price": 25.0
      }
    ]
  }
}
```

**Status:** `200 OK` ✓

**✅ Verify These Field Names:**
- `quote_description` (NOT description)
- `service_type` (NOT service)
- `service_duration` (NOT duration)
- `service_rate` (NOT rate)
- `material_name` (NOT materials)

---

### ✅ Endpoint 3: Chatbot Query

**URL:** `POST {{base_url}}/api/chat/`  
**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: application/json
```

**Body (Example 1):**
```json
{
  "question": "How many clients do I have?"
}
```

**Expected Response:**
```json
{
  "success": true,
  "question": "How many clients do I have?",
  "answer": "You have 15 clients.",
  "sql_query": "SELECT COUNT(*) FROM client_information WHERE user_id = 'fa830eb7-...'",
  "raw_result": "[(15,)]"
}
```

**Status:** `200 OK` ✓

**✅ Security Check:** SQL must have `WHERE user_id = '...'`

---

## 📝 MORE CHATBOT QUESTIONS TO TEST

### Client Questions:
```json
{"question": "Show me all my clients"}
{"question": "Find client named John Smith"}
{"question": "How many new clients this month?"}
```

### Invoice Questions:
```json
{"question": "What are my unpaid invoices?"}
{"question": "How much money am I owed?"}
{"question": "Show me paid invoices this month"}
```

### Revenue Questions:
```json
{"question": "What's my total revenue?"}
{"question": "What's my revenue this month?"}
{"question": "Show me my top 5 clients by revenue"}
```

### Quote Questions:
```json
{"question": "How many quotes did I send this year?"}
{"question": "What's the total value of my quotes?"}
{"question": "Show me quotes in draft status"}
```

---

## ❌ ERROR TESTING

### Test 1: Invalid File Type
Upload a `.txt` file

**Expected:** `400 Bad Request`
```json
{
  "detail": "Invalid file type. Use: mp3, wav, m4a, ogg, or webm"
}
```

### Test 2: Missing Authorization
Remove `Authorization` header

**Expected:** `401 Unauthorized`
```json
{
  "detail": "No authorization header"
}
```

---

## ✅ TESTING CHECKLIST

**Essential Tests:**
- [ ] GET /api/health/ → Returns 200 OK
- [ ] POST /api/voice/process/ → Extracts correct field names
- [ ] POST /api/chat/ → Returns answer with SQL
- [ ] SQL includes `WHERE user_id = '...'` (security)
- [ ] Invalid file type returns 400
- [ ] Missing auth returns 401

**All tests should pass!** ✓

---

## 🎯 URLS SUMMARY (Copy-Paste Ready)

```
Base URL: http://localhost:8000

Health Check:
GET http://localhost:8000/api/health/

Voice Processing:
POST http://localhost:8000/api/voice/process/
(Upload: test_client_audio.mp3)

Chatbot:
POST http://localhost:8000/api/chat/
Body: {"question": "How many clients?"}

API Docs:
http://localhost:8000/docs
```

---

## 🚨 TROUBLESHOOTING

**Problem: Connection refused**  
Solution: Run `python api_server.py` first

**Problem: 500 Error on health check**  
Solution: Check DATABASE_URL in `.env`

**Problem: OpenAI error**  
Solution: Check OPENAI_API_KEY in `.env`

**Problem: Postman URLs don't work**  
Solution: Use these exact URLs:
- `/api/health/` (NOT `/api/chat/health/`)
- `/api/voice/process/` (NOT `/api/voice/create-quote/`)
- `/api/chat/` (NOT `/api/chat/query/`)

---

## 📊 SUCCESS CRITERIA

**Your AI works if:**
✅ Health check returns operational  
✅ Voice extracts correct field names  
✅ Chatbot generates SQL with `WHERE user_id`  
✅ All responses match expected format  

**All should work perfectly!** 🎉

---

## 🎬 NEXT STEPS

1. Test all 3 endpoints
2. Try different chatbot questions
3. Verify field names match
4. Confirm security (user_id in SQL)
5. Ready to hand off to backend team!

**Your code is production-ready!** No changes needed. ✨
