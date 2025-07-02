from fastapi.responses import JSONResponse,StreamingResponse
from fastapi import FastAPI, HTTPException, Query,Depends,APIRouter,Body
from pydantic import BaseModel
from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from app.database.models import Transcription, Keyword, Conversation, Project,APIKey
from app.database.database import TranscriptionSessionLocal,get_db
import logging
from rapidfuzz import fuzz
import re
import io
import pandas as pd
from typing import List
import uuid
import json
from app.authentication.authen import generate_api_key, get_api_key, get_api_owner
from app.authentication.config import settings
from datetime import datetime
from collections import defaultdict

app = FastAPI(
    title="Comparative Transcription Service",
    description="Compare diarization text with categorized keywords from DB",
    version="1.0.0"
)

# Setup logger
logging.basicConfig(level=logging.INFO,format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Input model for replacing keywords
class KeywordBatch(BaseModel):
    project_id: int
    builder_name: str
    keywords: List[Dict[str, str]]  # Each item: {category: ..., keyword: ...}

# Pydantic models for API responses
class APIKeyCreate(BaseModel):
    owner_name: str
    owner_email: str
    description: str = None

class APIKeyInfo(BaseModel):
    key_id: str
    owner_name: str
    owner_email: str
    description: str = None
    is_active: bool
    created_at: datetime
    last_used: datetime = None

class APIKeyResponse(BaseModel):
    key_id: str
    api_key: str
    owner_name: str

import re
from fastapi import FastAPI, Query, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from fuzzywuzzy import fuzz
import logging

app = FastAPI()
logger = logging.getLogger(__name__)

def clean_text(text: str) -> str:
    return re.sub(r'[^a-zA-Z0-9 ]', '', text.casefold()).strip()


def get_fuzzy_score(keyword, text):
    partial = fuzz.partial_ratio(keyword, text)
    token = fuzz.token_set_ratio(keyword, text)
    return (partial + token) // 2  # average score

@app.post("/fetch_keywords_match", summary="Fuzzy match keywords with intelligent speaker tagging")
def fetch_keywords_match(
    conversation_id: str = Query(...),
    project_id: int = Query(...),
    builder_name: str = Query(...),
    session: Session = Depends(get_db),
    key: str = Depends(get_api_key)
):
    try:
        logger.info(f"Matching for convo={conversation_id}, project={project_id}, builder={builder_name}")
        owner = get_api_owner(key, session)

        # Validate conversation
        conversation = session.query(Conversation).filter_by(conversation_id=conversation_id).first()
        if not conversation:
            return JSONResponse(
                content={"Error code": "ERR-1001",
                         "Error message": "Conversation Id not Match",
                         "Conversation Id": f"{conversation_id}"},
                status_code=404)
        if conversation.project_id != project_id:
            return JSONResponse(
                content={"Error code": "ERR-1002",
                         "Error message": "The provided project ID doesn't correspond to this conversation.",
                        "Conversation Id": f"{conversation_id}",
                         "Project id": f"{project_id}"},
               status_code=404)

        # Validate project
        project = session.query(Project).filter_by(id=project_id, builder_name=builder_name.strip()).first()
        if not project:
            return JSONResponse(
                content={"Error code": "ERR-1003",
                         "Error message": "The provided project does not have an associated builder name",
                         "Conversation Id": f"{conversation_id}",
                         "Project id": f"{project_id}",
                         "Builder Name": f"{builder_name}"},
                status_code=404)

        # Get transcription
        transcription = session.query(Transcription).filter_by(conversation_id=conversation_id).first()
        if not transcription or not transcription.transcript_text:
            return JSONResponse(
                content={"Error code": "ERR-1004",
                         "Error message": "Transcription Not found for this conversation",
                         "Conversation Id": f"{conversation_id}",
                         "Project id": f"{project_id}",
                         "Builder Name": f"{builder_name}"},
                status_code=404)
        diarized_segments = transcription.diarized_segments or []

        # Manually assign roles
        agent_speaker = "Speaker_1"
        customer_speaker = "Speaker_0"

        # Fetch keywords
        keyword_obj = session.query(Keyword).filter_by(
            project_id=project_id,
            builder_name=builder_name.strip()
        ).first()

        if not keyword_obj or not keyword_obj.keywords:
            return JSONResponse(
                content={"Error code": "ERR-1005",
                         "Error message": "Keyword not found for the given project and builder",
                         "Project id": f"{project_id}",
                         "Builder Name": f"{builder_name}"},
                status_code=404)

        categorized_keywords = keyword_obj.keywords
        result = []

        # Fuzzy Match Logic
        for category, keyword_list in categorized_keywords.items():
            keyword_matches = []

            for keyword in keyword_list:
                keyword_clean = clean_text(keyword)
                agent_count = customer_count = 0
                agent_texts, customer_texts = [], []

                for segment in diarized_segments:
                    speaker = segment.get("speaker", "")
                    text = segment.get("text", "")
                    text_clean = clean_text(text)

                    score = get_fuzzy_score(keyword_clean, text_clean)
                    if score >= 85:
                        entry = {"text": text, "speaker": speaker}
                        if speaker == agent_speaker:
                            agent_count += 1
                            agent_texts.append(entry)
                        elif speaker == customer_speaker:
                            customer_count += 1
                            customer_texts.append(entry)

                keyword_matches.append({
                    "keyword": keyword,
                    "countBySpeaker": {
                        "Agent": {"count": agent_count, "text": agent_texts},
                        "Customer": {"count": customer_count, "text": customer_texts}
                    }
                })

            result.append({
                "category": category,
                "keywords": keyword_matches
            })

        return {
            "status": "success",
            "agent_id": conversation.agent_id,
            "conversation_id": conversation.conversation_id,
            "project_id": project.id,
            "builder_name": project.builder_name,
            "matched_Keywords": result,
            "diarized_text": diarized_segments,
            "agent_speaker": agent_speaker,
            "customer_speaker": customer_speaker
        }

    except Exception as e:
        logger.exception("Error in fetch_keywords_match")
        raise HTTPException(status_code=500, detail=str(e))

# Pydantic model for keyword list
class KeywordItem(BaseModel):
    category: str
    keyword: str

class KeywordPayload(BaseModel):
    keywords: List[KeywordItem]


@app.post("/keywords/replace", summary="Replace keywords as grouped JSON (category: [keywords]) for a builder and project")
def replace_keywords(
    project_id: int = Query(..., description="Project ID"),
    builder_name: str = Query(...,description="Builder name (case-sensitive)"),
    payload: KeywordPayload = ...,
    session: Session = Depends(get_db),
    key: str = Depends(get_api_key)
):
    try:
        owner = get_api_owner(key, session)  #  Who's updating
        builder_name_clean = builder_name.strip()

        # ✅ Validate the builder/project combo
        project = session.query(Project).filter_by(
            id=project_id, builder_name=builder_name_clean).first()
        if not project:
            # raise HTTPException(
            # status_code=404, detail=f"Project ID {project_id} and Builder name {builder_name} do not match.")
            return JSONResponse(
                content={"Error code": "ERR-1006",
                         "Error message": "Builder Name and Project_Id Does't not Match",
                         "Project id": f"{project_id}",
                         "Builder Name": f"{builder_name}"},
                status_code=404)

        # 🔁 Check existing keyword record
        existing = session.query(Keyword).filter(
            Keyword.project_id == project_id,
            Keyword.builder_name.ilike(builder_name_clean)
        ).first()

        # 🔧 Convert list to {category: [keywords]} dict
        keyword_dict = defaultdict(list)
        for item in payload.keywords:
            category = item.category.strip()
            keyword = item.keyword.strip()
            if category and keyword:
                keyword_dict[category].append(keyword)

        keyword_json = dict(keyword_dict)  # Convert from defaultdict

        if existing:
            existing.keywords = keyword_json
            existing.updated_on = datetime.utcnow()
            existing.updated_by = owner
            logger.info(
                f"✅ Updated keywords for project_id = {project_id}, builder_name ='{builder_name}'")
        else:
            new_entry = Keyword(
                project_id=project_id,
                builder_name=builder_name_clean,
                keywords=keyword_json,
                created_on=datetime.utcnow(),
                created_by=owner,
                updated_on=datetime.utcnow(),
                updated_by=owner
            )
            session.add(new_entry)
            logger.info(
                f"Inserted new keywords for project_id={project_id}, builder_name='{builder_name}'")

        session.commit()

        return {
            "message": "Keywords successfully replaced.",
            "total_categories": len(keyword_json),
            "total_keywords": sum(len(v) for v in keyword_json.values())
        }

    except Exception as e:
        session.rollback()
        logger.exception("Error replacing keywords JSON")
        return JSONResponse(
            content={"Error code": "ERR-1006",
                     "Error message": "Unable to replace keywords due to mismatched project ID and builder name.",
                     #  "Conversation Id": f"{conversation_id}",
                     "Project id": f"{project_id}",
                     "Builder Name": f"{builder_name}"},
            status_code=404)
        # raise HTTPException(status_code=500, detail=str(e))


# GET Endpoint: All keywords grouped by category
@app.get("/keywords", summary="Get keywords and categories for a builder and project")
def get_keywords(
    project_id: int = Query(..., description="Project ID"),
    builder_name: str = Query(...,
                              description="Builder name (case-insensitive)"),
    db: Session = Depends(get_db),
    key: str = Depends(get_api_key)
):
    try:
        logger.info(
            f"🔍 Fetching keywords for project_id={project_id}, builder_name={builder_name}")

        keyword_entry = db.query(Keyword).filter(
            and_(
                Keyword.project_id == project_id,
                Keyword.builder_name.ilike(builder_name.strip())
            )
        ).first()

        if not keyword_entry:
            logger.warning("No keywords found for this builder and project.")
            return JSONResponse(
                content={"Error code": "ERR-1005",
                         "Error message": "Keyword not found for this given project and builder",
                         #  "Conversation Id": f"{conversation_id}",
                         "Project id": f"{project_id}",
                         "Builder Name": f"{builder_name}"},
                status_code=404)
            # raise HTTPException(
            #     status_code=404, detail=f"No keywords found for this builder {builder_name} and project Id {project_id} .")

        raw_keywords = keyword_entry.keywords

        # If it's a string (JSON), convert it
        if isinstance(raw_keywords, str):
            try:
                raw_keywords = json.loads(raw_keywords)
            except json.JSONDecodeError:
                logger.error("❌ Invalid JSON format in keywords field.")
                raise HTTPException(
                    status_code=500, detail="Invalid keyword JSON format.")

        # Check final format is: Dict[str, List[str]]
        if not isinstance(raw_keywords, dict) or not all(isinstance(v, list) for v in raw_keywords.values()):
            logger.error(
                f"❌ Keyword data is not a valid dictionary of lists. Got: {raw_keywords}")
            raise HTTPException(
                status_code=500, detail="Keyword data is not a valid category-keyword mapping.")

        logger.info(
            f"✅ Returning keywords grouped under {len(raw_keywords)} categories.")
        return {
            "project_id": project_id,
            "builder_name": builder_name,
            "keywords_by_category": raw_keywords
        }

    except Exception as e:
        logger.exception("🔥 Unexpected error while fetching keywords.")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/get_builder_name", summary="Get builder name from conversation and project")
def get_builder_name(
    conversation_id: str = Query(..., description="The conversation ID"),
    project_id: int = Query(..., description="The project ID"),
    session: Session = Depends(get_db),
    # Ensure only authenticated users can access this endpoint
    key: str = Depends(get_api_key)
):
    with TranscriptionSessionLocal() as session:
        try:
            logger.info(
                f"Fetching builder_name for conversation_id={conversation_id}, project_id={project_id}")

            # 1. Validate the conversation
            conversation = session.query(Conversation).filter_by(
                conversation_id=conversation_id).first()
            if not conversation:
                return JSONResponse(
                content={"Error code": "ERR-1001",
                         "Error message": "Conversation Id does not exist for the given project",
                         "Conversation Id": f"{conversation_id}"},
                status_code=404)

            # 2. Check if the conversation's project_id matches
            if conversation.project_id != project_id:
                return JSONResponse(
                content={"Error code": "ERR-1002",
                         "Error message": "Project Id not Match For This Conversation",
                         "Conversation Id": f"{conversation_id}",
                         "Project id": f"{project_id}"},
               status_code=404)

            # 3. Fetch the builder_name from the project table
            project = session.query(Project).filter_by(id=project_id).first()
            if not project:
                return JSONResponse(
                content={"Error code": "ERR-1002",
                         "Error message": "The provided project ID doesn't correspond to this conversation.",
                         "Conversation Id": f"{conversation_id}",
                         "Project id": f"{project_id}"},
               status_code=404)

            logger.info(f"Found builder_name: {project.builder_name}")
            return {
                "project_id": project.id,
                "builder_name": project.builder_name
            }

        except Exception as e:
            logger.exception("Error while fetching builder_name")
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/download_keywords_match_excel", summary="Download matched keywords as Excel")
def download_keywords_match_excel(
    conversation_id: str = Query(...),
    project_id: int = Query(...),
    builder_name: str = Query(...),
    session: Session = Depends(get_db),
    key: str = Depends(get_api_key)
):
    try:
        owner = get_api_owner(key, session)

        # Step 1: Get conversation, project, transcription, and keywords
        conversation = session.query(Conversation).filter_by(
            conversation_id=conversation_id).first()
        if not conversation:
            return JSONResponse(
                content={"Error code": "ERR-1001",
                         "Error message": "Conversation Id does not exist for the given project",
                         "Conversation Id": f"{conversation_id}"},
                status_code=404)

        project = session.query(Project).filter_by(
            id=project_id, builder_name=builder_name.strip()).first()
        if not project:
            return JSONResponse(
                content={"Error code": "ERR-1002",
                         "Error message": "The provided project ID doesn't correspond to the conversation.",
                         "Conversation Id": f"{conversation_id}",
                         "Project id": f"{project_id}"},
               status_code=404)

        transcription = session.query(Transcription).filter_by(
            conversation_id=conversation_id).first()
        diarized_segments = transcription.diarized_segments or []

        keyword_obj = session.query(Keyword).filter_by(
            project_id=project_id, builder_name=builder_name.strip()
        ).first()
        if not keyword_obj or not keyword_obj.keywords:
            return JSONResponse(
                content={"Error code": "ERR-1005",
                         "Error message": "Keyword not found for this project and builder",
                         #  "Conversation Id": f"{conversation_id}",
                         "Project id": f"{project_id}",
                         "Builder Name": f"{builder_name}"},
                status_code=404)
            # raise HTTPException(404, detail="Keywords not found.")

        # Step 2: Prepare matching data
        categorized_keywords = keyword_obj.keywords
        agent_speakers = ["Speaker_1"]
        customer_speakers = ["Speaker_0"]

        records = []

        def clean_text(txt):
            return re.sub(r'[^a-zA-Z0-9 ]', '', txt.casefold()).strip().replace(" ", "")

        for category, keywords in categorized_keywords.items():
            for keyword in keywords:
                keyword_clean = clean_text(keyword)
                for segment in diarized_segments:
                    speaker = segment.get("speaker")
                    text = segment.get("text")
                    text_clean = clean_text(text)
                    if keyword_clean in text_clean:
                        speaker_type = "Agent" if speaker in agent_speakers else "Customer" if speaker in customer_speakers else "Unknown"
                        records.append({
                            "project_id": project_id,
                            "conversation_id": conversation_id,
                            "builder_name": builder_name,
                            "category": category,
                            "keyword": keyword,
                            "speaker": speaker_type,
                            "count": 1,
                            "matched_text": text
                        })

        # Step 3: Convert to Excel
        df = pd.DataFrame(records)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name="Matched Keywords", index=False)
        output.seek(0)

        return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 headers={"Content-Disposition": f"attachment; filename=matched_keywords_{conversation_id}.xlsx"})

    except Exception as e:
        return JSONResponse(
                content={"Error code": "ERR-1007",
                         "Error message": "Could not Generate Excel file for gIven conversation",
                         "Conversation Id": f"{conversation_id}",
                         "Project id": f"{project_id}",
                         "Builder Name": f"{builder_name}"},
                status_code=404)


@app.get("/List_keys", response_model=List[APIKeyInfo])
async def list_api_keys(
    db: Session = Depends(get_db),
    _: str = Depends(get_api_key)  # Only authenticated users can list keys
):
    """List all API keys (without showing the actual keys)."""
    keys = db.query(APIKey).all()
    return keys
