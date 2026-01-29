"""
DynamoDB models for inbox management
"""
import time
import secrets
import string
from typing import Optional
from pydantic import BaseModel


class Inbox(BaseModel):
    """Inbox model matching DynamoDB schema"""
    id: str
    created_at: int
    expires_at: int
    
    @staticmethod
    def generate_inbox_id(length: int = 8) -> str:
        """Generate a random inbox ID (8-character alphanumeric lowercase)"""
        alphabet = string.ascii_lowercase + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @classmethod
    def create(cls, ttl_seconds: int = 3600) -> 'Inbox':
        """Create a new inbox with specified TTL"""
        now = int(time.time())
        return cls(
            id=cls.generate_inbox_id(),
            created_at=now,
            expires_at=now + ttl_seconds
        )
    
    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format"""
        return {
            'id': {'S': self.id},
            'created_at': {'N': str(self.created_at)},
            'expires_at': {'N': str(self.expires_at)}
        }
    
    @classmethod
    def from_dynamodb_item(cls, item: dict) -> 'Inbox':
        """Create Inbox from DynamoDB item"""
        return cls(
            id=item['id']['S'],
            created_at=int(item['created_at']['N']),
            expires_at=int(item['expires_at']['N'])
        )
    
    def is_expired(self) -> bool:
        """Check if inbox has expired"""
        return int(time.time()) > self.expires_at
    
    def get_email_address(self, domain: str) -> str:
        """Get full email address for this inbox"""
        return f"{self.id}@{domain}"


class InboxCreateRequest(BaseModel):
    """Request model for creating an inbox"""
    ttl: Optional[int] = 3600  # Default 1 hour


class InboxCreateResponse(BaseModel):
    """Response model for inbox creation"""
    id: str
    address: str
    expires_at: int


class InboxStatusResponse(BaseModel):
    """Response model for inbox status"""
    id: str
    exists: bool
    expires_at: int
    email_count: int
