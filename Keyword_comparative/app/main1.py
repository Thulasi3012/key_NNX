from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Conversation, Keyword
from rapidfuzz import fuzz
import re

app = FastAPI()

class MatchRequest(BaseModel):
    project_id: int
    builder_name: str
    conversation_id: str

def clean_text(text: str) -> str:
    return re.sub(r'[^a-zA-Z0-9 ]', '', text.lower()).strip()

def fuzzy_match(text: str, keyword: str, threshold: int = 85) -> bool:
    """
    Fuzzy matches cleaned text with keyword using partial ratio.
    """
    text_clean = clean_text(text)
    keyword_clean = clean_text(keyword)
    return fuzz.partial_ratio(text_clean, keyword_clean) >= threshold

def match_keywords(diarized_text: List[Dict[str, str]], keyword_json: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    result = []
    for category_name, keywords in keyword_json.items():
        matched_keywords = []

        for keyword in keywords:
            agent_matches = []
            customer_matches = []

            for entry in diarized_text:
                text = entry.get("text", "")
                speaker = entry.get("speaker", "")

                if fuzzy_match(text, keyword):
                    match_entry = {"text": text, "speaker": speaker}
                    if speaker == "Speaker_0":
                        customer_matches.append(match_entry)
                    else:
                        agent_matches.append(match_entry)

            matched_keywords.append({
                "keyword": keyword,
                "countBySpeaker": {
                    "Agent": {"count": len(agent_matches), "text": agent_matches},
                    "Customer": {"count": len(customer_matches), "text": customer_matches}
                }
            })

        result.append({
            "category": category_name,
            "keywords": matched_keywords
        })

    return result

@app.post("/match_keywords")
def get_matched_keywords(request: MatchRequest):
    db: Session = SessionLocal()
    convo = db.query(Conversation).filter_by(conversation_id=request.conversation_id).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    keywords_entry = db.query(Keyword).filter_by(project_id=request.project_id, builder_name=request.builder_name).first()
    if not keywords_entry:
        raise HTTPException(status_code=404, detail="Keywords not found")

    try:
        matched = match_keywords(convo.diarized_text, keywords_entry.keywords)
        return {
            "conversation_id": convo.conversation_id,
            "project_id": request.project_id,
            "builder_name": request.builder_name,
            "matched_keywords": matched,
            "diarized_text": convo.diarized_text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
