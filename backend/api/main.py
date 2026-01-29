"""
FastAPI application for EasyTempInbox API
"""
import os
import sys
import time
import boto3
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from dotenv import load_dotenv

# Local testing setup: load config/.env and adjust import paths
if os.getenv('LOCAL_TESTING') == 'true':
    # Load environment variables from config/.env for local testing
    config_env_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', '.env')
    load_dotenv(config_env_path)
    # Add parent directory to path for local imports
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from models.inbox import (
        Inbox, InboxCreateRequest, InboxCreateResponse, InboxStatusResponse
    )
    from models.email import EmailListResponse, EmailListItem, EmailDetailResponse, Email, AttachmentResponse
else:
    # Production: models are packaged in the Lambda deployment
    from models.inbox import (
        Inbox, InboxCreateRequest, InboxCreateResponse, InboxStatusResponse
    )
    from models.email import EmailListResponse, EmailListItem, EmailDetailResponse, Email, AttachmentResponse

# Initialize FastAPI app
app = FastAPI(title="EasyTempInbox API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# AWS clients
#dynamodb = boto3.client('dynamodb', region_name=os.getenv('AWS_REGION', 'us-east-1'))
INBOXES_TABLE = os.getenv('DYNAMODB_INBOXES_TABLE', 'easytempinbox-inboxes')
EMAILS_TABLE = os.getenv('DYNAMODB_EMAILS_TABLE', 'easytempinbox-emails')

# Configuration
DEFAULT_TTL = int(os.getenv('DEFAULT_TTL_SECONDS', '3600'))
MIN_TTL = int(os.getenv('MIN_TTL_SECONDS', '600'))
MAX_TTL = int(os.getenv('MAX_TTL_SECONDS', '86400'))
PRIMARY_DOMAIN = os.getenv('PRIMARY_DOMAIN', 'easytempinbox.com')
S3_BUCKET = os.getenv('S3_BUCKET_NAME', 'easytempinbox-raw-emails')
if os.getenv('LOCAL_TESTING') == 'true':
    dynamodb = boto3.client(
        'dynamodb',
        region_name='us-east-1',
        endpoint_url='http://localhost:8000',
        aws_access_key_id='test',
        aws_secret_access_key='test'
    )
    s3 = boto3.client(
        's3',
        region_name='us-east-1',
        aws_access_key_id='test',
        aws_secret_access_key='test'
    )
else:
    dynamodb = boto3.client('dynamodb', region_name=os.getenv('AWS_REGION', 'us-east-1'))
    s3 = boto3.client('s3', region_name=os.getenv('AWS_REGION', 'us-east-1'))

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "service": "EasyTempInbox API"}


@app.post("/api/inbox", response_model=InboxCreateResponse)
async def create_inbox(request: InboxCreateRequest = InboxCreateRequest()):
    """
    Create a new temporary inbox
    
    Query Parameters:
    - ttl: Time to live in seconds (default: 3600, min: 600, max: 86400)
    """
    # Validate TTL
    ttl = request.ttl or DEFAULT_TTL
    if ttl < MIN_TTL or ttl > MAX_TTL:
        raise HTTPException(
            status_code=400,
            detail=f"TTL must be between {MIN_TTL} and {MAX_TTL} seconds"
        )
    
    # Create inbox
    inbox = Inbox.create(ttl_seconds=ttl)
    
    # Store in DynamoDB
    try:
        dynamodb.put_item(
            TableName=INBOXES_TABLE,
            Item=inbox.to_dynamodb_item()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create inbox: {str(e)}")
    
    return InboxCreateResponse(
        id=inbox.id,
        address=inbox.get_email_address(PRIMARY_DOMAIN),
        expires_at=inbox.expires_at
    )


@app.get("/api/inbox/{inbox_id}/emails", response_model=EmailListResponse)
async def list_emails(
    inbox_id: str,
    limit: int = Query(default=20, le=100),
    last_key: str = Query(default=None)
):
    """
    List all emails for an inbox
    
    Path Parameters:
    - inbox_id: The inbox ID
    
    Query Parameters:
    - limit: Maximum number of emails to return (default: 20, max: 100)
    - last_key: Pagination key from previous response
    """
    # Check if inbox exists
    try:
        response = dynamodb.get_item(
            TableName=INBOXES_TABLE,
            Key={'id': {'S': inbox_id}}
        )
        if 'Item' not in response:
            raise HTTPException(status_code=404, detail="Inbox not found or expired")
        
        inbox = Inbox.from_dynamodb_item(response['Item'])
        if inbox.is_expired():
            raise HTTPException(status_code=404, detail="Inbox has expired")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check inbox: {str(e)}")
    
    # Query emails
    try:
        query_params = {
            'TableName': EMAILS_TABLE,
            'KeyConditionExpression': 'inbox_id = :inbox_id',
            'ExpressionAttributeValues': {':inbox_id': {'S': inbox_id}},
            'Limit': limit,
            'ScanIndexForward': False  # Sort by received_at descending
        }
        
        if last_key:
            query_params['ExclusiveStartKey'] = {'inbox_id': {'S': inbox_id}, 'email_id': {'S': last_key}}
        
        response = dynamodb.query(**query_params)
        
        emails = []
        for item in response.get('Items', []):
            email = Email.from_dynamodb_item(item)
            emails.append(EmailListItem(
                email_id=email.email_id,
                from_address=email.from_address,
                subject=email.subject,
                received_at=email.received_at,
                has_html=bool(email.html_body)
            ))
        
        next_key = None
        if 'LastEvaluatedKey' in response:
            next_key = response['LastEvaluatedKey']['email_id']['S']
        
        return EmailListResponse(
            emails=emails,
            count=len(emails),
            last_key=next_key
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list emails: {str(e)}")


@app.get("/api/email/{inbox_id}/{email_id}", response_model=EmailDetailResponse)
async def get_email(inbox_id: str, email_id: str):
    """
    Get a specific email
    
    Path Parameters:
    - inbox_id: The inbox ID
    - email_id: The email ID
    """
    try:
        response = dynamodb.get_item(
            TableName=EMAILS_TABLE,
            Key={
                'inbox_id': {'S': inbox_id},
                'email_id': {'S': email_id}
            }
        )
        
        if 'Item' not in response:
            raise HTTPException(status_code=404, detail="Email not found")
        
        email = Email.from_dynamodb_item(response['Item'])
        
        # Convert attachments to response format
        attachments = [
            AttachmentResponse(
                id=att.id,
                filename=att.filename,
                content_type=att.content_type,
                size=att.size
            ) for att in email.attachments
        ]
        
        return EmailDetailResponse(
            email_id=email.email_id,
            from_address=email.from_address,
            subject=email.subject,
            text_body=email.text_body,
            html_body=email.html_body,
            received_at=email.received_at,
            large_body_url=email.large_body_url,
            attachments=attachments
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get email: {str(e)}")


@app.get("/api/inbox/{inbox_id}/status", response_model=InboxStatusResponse)
async def get_inbox_status(inbox_id: str):
    """
    Get inbox status (lightweight endpoint for polling)
    
    Path Parameters:
    - inbox_id: The inbox ID
    """
    try:
        # Get inbox
        inbox_response = dynamodb.get_item(
            TableName=INBOXES_TABLE,
            Key={'id': {'S': inbox_id}}
        )
        
        if 'Item' not in inbox_response:
            return InboxStatusResponse(
                id=inbox_id,
                exists=False,
                expires_at=0,
                email_count=0
            )
        
        inbox = Inbox.from_dynamodb_item(inbox_response['Item'])
        
        if inbox.is_expired():
            return InboxStatusResponse(
                id=inbox_id,
                exists=False,
                expires_at=inbox.expires_at,
                email_count=0
            )
        
        # Count emails
        count_response = dynamodb.query(
            TableName=EMAILS_TABLE,
            KeyConditionExpression='inbox_id = :inbox_id',
            ExpressionAttributeValues={':inbox_id': {'S': inbox_id}},
            Select='COUNT'
        )
        
        return InboxStatusResponse(
            id=inbox_id,
            exists=True,
            expires_at=inbox.expires_at,
            email_count=count_response.get('Count', 0)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get inbox status: {str(e)}")


@app.get("/api/attachment/{inbox_id}/{email_id}/{attachment_id}")
async def download_attachment(inbox_id: str, email_id: str, attachment_id: str):
    """
    Get a pre-signed URL to download an attachment
    
    Path Parameters:
    - inbox_id: The inbox ID
    - email_id: The email ID
    - attachment_id: The attachment ID
    """
    try:
        # Get email to find attachment
        response = dynamodb.get_item(
            TableName=EMAILS_TABLE,
            Key={
                'inbox_id': {'S': inbox_id},
                'email_id': {'S': email_id}
            }
        )
        
        if 'Item' not in response:
            raise HTTPException(status_code=404, detail="Email not found")
        
        email = Email.from_dynamodb_item(response['Item'])
        
        # Find the attachment
        attachment = None
        for att in email.attachments:
            if att.id == attachment_id:
                attachment = att
                break
        
        if not attachment:
            raise HTTPException(status_code=404, detail="Attachment not found")
        
        # Generate pre-signed URL (valid for 1 hour)
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': S3_BUCKET,
                'Key': attachment.s3_key,
                'ResponseContentDisposition': f'attachment; filename="{attachment.filename}"'
            },
            ExpiresIn=3600
        )
        
        return {
            "download_url": presigned_url,
            "filename": attachment.filename,
            "content_type": attachment.content_type,
            "size": attachment.size
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get attachment: {str(e)}")


# Lambda handler
handler = Mangum(app)
