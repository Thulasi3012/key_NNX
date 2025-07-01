from pydantic import BaseModel

class ConversationInput(BaseModel):
    conversation_id: str
    
from pydantic import BaseModel

class ReplaceKeywordResponse(BaseModel):
    message: str
    total_keywords: int
