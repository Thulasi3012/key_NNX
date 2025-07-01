from sqlalchemy import Column, String, ForeignKey, Text, Integer,DateTime, Boolean, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSON,JSONB
from datetime import datetime
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship, declarative_base

# Define Base
Base = declarative_base()

# Define CallAnalysis
class CallAnalysis(Base):
    __tablename__ = "call_analysis"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    # Define the reverse relationship to Project
    project = relationship("Project", back_populates="calls")

# Define Project (can now reference CallAnalysis safely)
class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, unique=True)
    builder_name = Column(String)
    location = Column(String)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # makes a relationshio between project and call_anaysis table 
    conversations = relationship("Conversation", back_populates="project")
    calls = relationship("CallAnalysis", back_populates="project")  # works now ✅

# Conversation (uses project_id ForeignKey)
class Conversation(Base):
    __tablename__ = "conversations"
    conversation_id = Column(String(100), primary_key=True)
    agent_id = Column(String(100))
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    transcriptions = relationship("Transcription", back_populates="conversation")
    project = relationship("Project", back_populates="conversations")

# Transcription table 
class Transcription(Base):
    __tablename__ = "transcriptions"
    transcription_id = Column(String(100), primary_key=True)
    conversation_id = Column(String(100), ForeignKey("conversations.conversation_id"))
    transcript_text = Column(Text)
    diarized_segments = Column(JSONB)

    conversation = relationship("Conversation", back_populates="transcriptions")

# Keyword table 
class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, nullable=False)
    builder_name = Column(String, nullable=False)
    keywords = Column(JSONB, nullable=False)  # Now this will store: { "Category": [keyword1, keyword2] }
    created_on = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String)
    updated_on = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String)

    __table_args__ = (
        UniqueConstraint('project_id', 'builder_name', name='unique_builder_project'),
    )


    
    
#table to store A API key and values 
class APIKey(Base):
    __tablename__ = "api_keys"
    
    key_id = Column(String(100), primary_key=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    owner_name = Column(String(255), nullable=False)
    owner_email = Column(String(255))
    description = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    last_used = Column(TIMESTAMP(timezone=True))
    
    def __repr__(self):
        return f"<APIKey {self.key_id} - {self.owner_name}>"