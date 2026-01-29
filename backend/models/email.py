"""
DynamoDB models for email management
"""
import uuid
from typing import Optional, List
from pydantic import BaseModel


class AttachmentInfo(BaseModel):
    """Attachment metadata model"""
    id: str
    filename: str
    content_type: str
    size: int
    s3_key: str


class Email(BaseModel):
    """Email model matching DynamoDB schema"""
    inbox_id: str
    email_id: str
    from_address: str
    subject: str
    text_body: str
    html_body: str
    received_at: int
    large_body_url: Optional[str] = None
    attachments: List[AttachmentInfo] = []
    
    @classmethod
    def create(cls, inbox_id: str, from_address: str, subject: str, 
               text_body: str, html_body: str, received_at: int,
               large_body_url: Optional[str] = None,
               attachments: List[AttachmentInfo] = None) -> 'Email':
        """Create a new email"""
        return cls(
            inbox_id=inbox_id,
            email_id=str(uuid.uuid4()),
            from_address=from_address,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            received_at=received_at,
            large_body_url=large_body_url,
            attachments=attachments or []
        )
    
    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format"""
        item = {
            'inbox_id': {'S': self.inbox_id},
            'email_id': {'S': self.email_id},
            'from': {'S': self.from_address},
            'subject': {'S': self.subject},
            'text_body': {'S': self.text_body},
            'html_body': {'S': self.html_body},
            'received_at': {'N': str(self.received_at)}
        }
        if self.large_body_url:
            item['large_body_url'] = {'S': self.large_body_url}
        if self.attachments:
            item['attachments'] = {'L': [
                {'M': {
                    'id': {'S': a.id},
                    'filename': {'S': a.filename},
                    'content_type': {'S': a.content_type},
                    'size': {'N': str(a.size)},
                    's3_key': {'S': a.s3_key}
                }} for a in self.attachments
            ]}
        return item
    
    @classmethod
    def from_dynamodb_item(cls, item: dict) -> 'Email':
        """Create Email from DynamoDB item"""
        attachments = []
        if 'attachments' in item:
            for att in item['attachments']['L']:
                att_data = att['M']
                attachments.append(AttachmentInfo(
                    id=att_data['id']['S'],
                    filename=att_data['filename']['S'],
                    content_type=att_data['content_type']['S'],
                    size=int(att_data['size']['N']),
                    s3_key=att_data['s3_key']['S']
                ))
        
        return cls(
            inbox_id=item['inbox_id']['S'],
            email_id=item['email_id']['S'],
            from_address=item['from']['S'],
            subject=item['subject']['S'],
            text_body=item['text_body']['S'],
            html_body=item['html_body']['S'],
            received_at=int(item['received_at']['N']),
            large_body_url=item.get('large_body_url', {}).get('S'),
            attachments=attachments
        )


class AttachmentResponse(BaseModel):
    """Response model for attachment info"""
    id: str
    filename: str
    content_type: str
    size: int


class EmailListItem(BaseModel):
    """Simplified email model for list view"""
    email_id: str
    from_address: str
    subject: str
    received_at: int
    has_html: bool
    attachment_count: int = 0


class EmailListResponse(BaseModel):
    """Response model for email listing"""
    emails: list[EmailListItem]
    count: int
    last_key: Optional[str] = None


class EmailDetailResponse(BaseModel):
    """Response model for email detail"""
    email_id: str
    from_address: str
    subject: str
    text_body: str
    html_body: str
    received_at: int
    large_body_url: Optional[str] = None
    attachments: List[AttachmentResponse] = []

