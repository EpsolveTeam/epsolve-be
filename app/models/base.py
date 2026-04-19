from sqlmodel import SQLModel

# Import semua model di sini agar terdeteksi oleh Alembic
# Contoh:
# from app.models.ticket import Ticket
# from app.models.knowledge import Knowledge
from app.models.user import User
from sqlmodel import SQLModel
from app.models.ticket import Ticket
from app.models.chat_log import ChatLog
from app.models.knowledge import KnowledgeBase