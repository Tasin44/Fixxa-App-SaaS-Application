"""
Test API Server for Fixxa AI
=============================
A simple FastAPI server to test the AI module with Postman.
This is ONLY for testing - backend developer will create real Django endpoints.

Run: python api_server.py
Then test with Postman at http://localhost:8000
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
import uvicorn
import os
from pathlib import Path
import shutil

# Import AI module
from fixxa_ai import (
    process_audio_from_file,
    natural_language_query,
    check_database_health
)

# Temporary audio storage
TEMP_DIR = Path("temp_audio")
TEMP_DIR.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    yield
    # Shutdown - clean up temp files
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)


app = FastAPI(title="Fixxa AI Test Server", lifespan=lifespan)

# Mock user ID for testing (replace with real auth in Django)
TEST_USER_ID = "fa830eb7-310e-4f9f-bb35-dff1d77e072d"


class ChatRequest(BaseModel):
    question: str


def get_current_user(authorization: str = Header(None)) -> str:
    """Mock authentication - returns test user ID"""
    if not authorization:
        raise HTTPException(status_code=401, detail="No authorization header")
    # In real Django, this would validate JWT and return request.user.id
    return TEST_USER_ID


@app.get("/")
def root():
    """API info"""
    return {
        "name": "Fixxa AI Test Server",
        "status": "running",
        "endpoints": {
            "health": "GET /api/health/",
            "process_audio": "POST /api/voice/process/",
            "chat": "POST /api/chat/"
        }
    }


@app.get("/api/health/")
def health_check():
    """Check if AI module and database are working"""
    try:
        health = check_database_health()
        
        return JSONResponse({
            "ai_module": "operational",
            "database": health,
            "message": "All systems operational"
        })
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "ai_module": "error",
                "error": str(e)
            }
        )


@app.post("/api/voice/process/")
async def process_voice_note(
    audio: UploadFile = File(...),
    user_id: str = Depends(get_current_user)
):
    """
    Process uploaded audio file and extract client details.
    
    This is what the Django backend will implement.
    """
    temp_file = None
    
    try:
        # Validate file type
        if not audio.filename.endswith(('.mp3', '.wav', '.m4a', '.ogg', '.webm')):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Use: mp3, wav, m4a, ogg, or webm"
            )
        
        # Save uploaded file temporarily
        temp_file = TEMP_DIR / audio.filename
        with temp_file.open("wb") as f:
            shutil.copyfileobj(audio.file, f)
        
        # Process with AI module
        result = process_audio_from_file(
            file_path=str(temp_file),
            document_type="client_details"
        )
        
        if result['success']:
            client_data = result['extracted_data']
            
            return JSONResponse({
                "success": True,
                "transcription": result['transcription'],
                "client_data": {
                    # Client info
                    "client_name": client_data.client_name,
                    "phone_number": client_data.phone_number,
                    "address": client_data.address,
                    "email": client_data.email,
                    
                    # Quote/Invoice info
                    "issue_date": client_data.issue_date,
                    "due_date": client_data.due_date,
                    "duration_unit": client_data.duration_unit,
                    "service_location": client_data.service_location,
                    "discount_amount": client_data.discount_amount,
                    "discount_type": client_data.discount_type,
                    "vat_rate": client_data.vat_rate,
                    
                    # Items (proper field names for database)
                    "items": [
                        {
                            "quote_description": item.quote_description,
                            "service_type": item.service_type,
                            "service_duration": item.service_duration,
                            "service_rate": item.service_rate,
                            "material_name": item.material_name,
                            "quantity": item.quantity,
                            "unit_price": item.unit_price
                        }
                        for item in client_data.items
                    ] if client_data.items else [],
                    
                    # Legacy fields (for backward compatibility)
                    "service_type": client_data.service_type,
                    "issue_description": client_data.issue_description,
                    "estimated_cost": client_data.estimated_cost,
                    "appointment_date": client_data.appointment_date,
                    "notes": client_data.notes
                },
                "message": "Audio processed successfully"
            })
        else:
            raise HTTPException(
                status_code=500,
                detail=result['error']
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Clean up temporary file
        if temp_file and temp_file.exists():
            temp_file.unlink()


@app.post("/api/chat/")
def chat_with_database(
    request: ChatRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Answer natural language questions about the database.
    
    This is what the Django backend will implement.
    """
    try:
        result = natural_language_query(
            user_id=user_id,
            question=request.question
        )
        
        if result['success']:
            return JSONResponse({
                "success": True,
                "question": request.question,
                "answer": result['answer'],
                "sql_query": result['sql_query'],
                "raw_result": str(result.get('result', ''))
            })
        else:
            raise HTTPException(
                status_code=500,
                detail=result['error']
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  Fixxa AI Test Server")
    print("="*60)
    print(f"\n  🚀 Starting server at http://localhost:8000")
    print(f"  📚 API docs at http://localhost:8000/docs")
    print(f"\n  Test with Postman:")
    print(f"  - Import POSTMAN_COLLECTION.json")
    print(f"  - Set base_url = http://localhost:8000")
    print(f"  - Set token = any-value (mock auth)")
    print(f"\n  Press Ctrl+C to stop\n")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
