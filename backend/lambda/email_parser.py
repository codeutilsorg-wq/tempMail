"""
Lambda function to parse incoming emails from SES via S3
"""
import os
import json
import email
import time
import boto3
import bleach
from email import policy
from email.parser import BytesParser

# AWS clients
s3 = boto3.client('s3')
dynamodb = boto3.client('dynamodb')

# Configuration
INBOXES_TABLE = os.getenv('DYNAMODB_INBOXES_TABLE', 'easytempinbox-inboxes')
EMAILS_TABLE = os.getenv('DYNAMODB_EMAILS_TABLE', 'easytempinbox-emails')
S3_BUCKET = os.getenv('S3_BUCKET_NAME', 'easytempinbox-raw-emails')
MAX_TEXT_BODY_SIZE = int(os.getenv('MAX_TEXT_BODY_SIZE', '102400'))  # 100KB
MAX_HTML_BODY_SIZE = int(os.getenv('MAX_HTML_BODY_SIZE', '204800'))  # 200KB
MAX_EMAILS_PER_INBOX = int(os.getenv('MAX_EMAILS_PER_INBOX', '50'))

# HTML sanitization settings
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 'b', 'i', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'blockquote', 'code', 'pre', 'hr', 'div', 'span', 'ul', 'ol', 'li',
    'a', 'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'font', 'center',
    'sup', 'sub', 'small', 'big', 'abbr', 'address'
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target'],
    'img': ['src', 'alt', 'title', 'width', 'height', 'style'],
    'div': ['class', 'style', 'align'],
    'span': ['class', 'style'],
    'p': ['class', 'style', 'align'],
    'table': ['class', 'style', 'width', 'border', 'cellpadding', 'cellspacing'],
    'td': ['colspan', 'rowspan', 'style', 'width', 'align', 'valign'],
    'th': ['colspan', 'rowspan', 'style', 'width', 'align', 'valign'],
    'tr': ['style'],
    'font': ['color', 'size', 'face'],
    '*': ['class']
}

# Allowed URL protocols for href and src
ALLOWED_PROTOCOLS = ['http', 'https', 'mailto', 'tel']


def sanitize_html(html_content: str) -> str:
    """Sanitize HTML content to prevent XSS attacks"""
    if not html_content:
        return ""
    
    return bleach.clean(
        html_content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True
    )


def extract_inbox_id_from_email(to_address: str) -> str:
    """Extract inbox ID from email address"""
    # Format: inbox_id@domain.com
    if '@' in to_address:
        return to_address.split('@')[0].strip('<>').lower()
    return to_address


def check_inbox_exists(inbox_id: str) -> bool:
    """Check if inbox exists and is not expired"""
    try:
        response = dynamodb.get_item(
            TableName=INBOXES_TABLE,
            Key={'id': {'S': inbox_id}}
        )
        
        if 'Item' not in response:
            return False
        
        expires_at = int(response['Item']['expires_at']['N'])
        return time.time() < expires_at
    except Exception as e:
        print(f"Error checking inbox: {e}")
        return False


def count_emails_in_inbox(inbox_id: str) -> int:
    """Count number of emails in inbox"""
    try:
        response = dynamodb.query(
            TableName=EMAILS_TABLE,
            KeyConditionExpression='inbox_id = :inbox_id',
            ExpressionAttributeValues={':inbox_id': {'S': inbox_id}},
            Select='COUNT'
        )
        return response.get('Count', 0)
    except Exception as e:
        print(f"Error counting emails: {e}")
        return 0


def parse_email_from_s3(bucket: str, key: str) -> dict:
    """Parse email from S3 object"""
    # Get email from S3
    response = s3.get_object(Bucket=bucket, Key=key)
    raw_email = response['Body'].read()
    
    # Parse email
    msg = BytesParser(policy=policy.default).parsebytes(raw_email)
    
    # Extract fields
    to_address = msg.get('To', '')
    from_address = msg.get('From', '')
    subject = msg.get('Subject', '(No Subject)')
    
    # Extract body and attachments
    text_body = ""
    html_body = ""
    attachments = []
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = part.get_content_disposition()
            
            # Check if this is an attachment
            if content_disposition == 'attachment' or (content_disposition == 'inline' and part.get_filename()):
                filename = part.get_filename()
                if filename:
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            attachments.append({
                                'filename': filename,
                                'content_type': content_type,
                                'size': len(payload),
                                'data': payload
                            })
                    except Exception as e:
                        print(f"Error extracting attachment {filename}: {e}")
            elif content_type == 'text/plain' and not text_body:
                try:
                    text_body = part.get_content()
                except:
                    text_body = ""
            elif content_type == 'text/html' and not html_body:
                try:
                    html_body = part.get_content()
                except:
                    html_body = ""
    else:
        content_type = msg.get_content_type()
        if content_type == 'text/plain':
            text_body = msg.get_content()
        elif content_type == 'text/html':
            html_body = msg.get_content()
    
    # Sanitize HTML
    if html_body:
        html_body = sanitize_html(html_body)
    
    return {
        'to': to_address,
        'from': from_address,
        'subject': subject,
        'text_body': text_body or "",
        'html_body': html_body or "",
        'attachments': attachments
    }


def store_email_in_dynamodb(inbox_id: str, email_data: dict):
    """Store parsed email in DynamoDB and attachments in S3"""
    import uuid
    
    email_id = str(uuid.uuid4())
    received_at = int(time.time())
    
    # Check body sizes
    text_body = email_data['text_body']
    html_body = email_data['html_body']
    large_body_url = None
    
    # If bodies are too large, truncate and add note
    if len(text_body) > MAX_TEXT_BODY_SIZE:
        text_body = text_body[:MAX_TEXT_BODY_SIZE] + "\n\n[Content truncated - too large]"
    
    if len(html_body) > MAX_HTML_BODY_SIZE:
        html_body = html_body[:MAX_HTML_BODY_SIZE] + "\n\n<!-- Content truncated - too large -->"
    
    # Process attachments - save to S3 and collect metadata
    attachment_metadata = []
    attachments = email_data.get('attachments', [])
    
    for idx, attachment in enumerate(attachments):
        try:
            # Generate S3 key for attachment
            attachment_id = str(uuid.uuid4())
            s3_key = f"attachments/{inbox_id}/{email_id}/{attachment_id}/{attachment['filename']}"
            
            # Upload to S3
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=attachment['data'],
                ContentType=attachment['content_type'],
                Metadata={
                    'inbox_id': inbox_id,
                    'email_id': email_id,
                    'original_filename': attachment['filename']
                }
            )
            
            # Store metadata (no binary data)
            attachment_metadata.append({
                'M': {
                    'id': {'S': attachment_id},
                    'filename': {'S': attachment['filename']},
                    'content_type': {'S': attachment['content_type']},
                    'size': {'N': str(attachment['size'])},
                    's3_key': {'S': s3_key}
                }
            })
            
            print(f"Saved attachment {attachment['filename']} to s3://{S3_BUCKET}/{s3_key}")
        except Exception as e:
            print(f"Error saving attachment {attachment.get('filename', 'unknown')}: {e}")
    
    # Store in DynamoDB
    item = {
        'inbox_id': {'S': inbox_id},
        'email_id': {'S': email_id},
        'from': {'S': email_data['from']},
        'subject': {'S': email_data['subject']},
        'text_body': {'S': text_body},
        'html_body': {'S': html_body},
        'received_at': {'N': str(received_at)}
    }
    
    # Add attachments metadata if present
    if attachment_metadata:
        item['attachments'] = {'L': attachment_metadata}
    
    if large_body_url:
        item['large_body_url'] = {'S': large_body_url}
    
    dynamodb.put_item(TableName=EMAILS_TABLE, Item=item)
    
    print(f"Stored email {email_id} for inbox {inbox_id}")


def lambda_handler(event, context):
    """
    Lambda handler for SES email processing
    
    Triggered by S3 event when SES stores email
    """
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # Parse S3 event
        for record in event['Records']:
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']
            
            print(f"Processing email from s3://{bucket}/{key}")
            
            # Parse email
            email_data = parse_email_from_s3(bucket, key)
            
            # Extract inbox ID
            inbox_id = extract_inbox_id_from_email(email_data['to'])
            print(f"Inbox ID: {inbox_id}")
            
            # Check if inbox exists and not expired
            if not check_inbox_exists(inbox_id):
                print(f"Inbox {inbox_id} does not exist or has expired")
                continue
            
            # Check email limit
            email_count = count_emails_in_inbox(inbox_id)
            if email_count >= MAX_EMAILS_PER_INBOX:
                print(f"Inbox {inbox_id} has reached maximum email limit ({MAX_EMAILS_PER_INBOX})")
                continue
            
            # Store email
            store_email_in_dynamodb(inbox_id, email_data)
            
            print(f"Successfully processed email for inbox {inbox_id}")
        
        return {
            'statusCode': 200,
            'body': json.dumps('Email processed successfully')
        }
    
    except Exception as e:
        print(f"Error processing email: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }
