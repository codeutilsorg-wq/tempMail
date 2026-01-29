"""
Test email parser locally by reading email files
"""
import json
import sys
import os
import boto3
from email import policy
from email.parser import BytesParser

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lambda.email_parser import sanitize_html

# Configure for local DynamoDB
dynamodb = boto3.client(
    'dynamodb',
    region_name='us-east-1',
    endpoint_url='http://localhost:8000',
    aws_access_key_id='test',
    aws_secret_access_key='test'
)

INBOXES_TABLE = 'easytempinbox-inboxes'
EMAILS_TABLE = 'easytempinbox-emails'


def parse_email_file(email_file_path):
    """Parse email from local file"""
    with open(email_file_path, 'rb') as f:
        email_content = f.read()
    
    msg = BytesParser(policy=policy.default).parsebytes(email_content)
    
    # Extract fields
    to_address = msg.get('To', '')
    from_address = msg.get('From', '')
    subject = msg.get('Subject', '(No Subject)')
    
    # Extract body
    text_body = ""
    html_body = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            
            if content_type == 'text/plain' and not text_body:
                text_body = part.get_content()
            elif content_type == 'text/html' and not html_body:
                html_body = part.get_content()
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
        'html_body': html_body or ""
    }


def store_email_in_dynamodb(inbox_id, email_data):
    """Store parsed email in local DynamoDB"""
    import uuid
    import time
    
    email_id = str(uuid.uuid4())
    received_at = int(time.time())
    
    item = {
        'inbox_id': {'S': inbox_id},
        'email_id': {'S': email_id},
        'from': {'S': email_data['from']},
        'subject': {'S': email_data['subject']},
        'text_body': {'S': email_data['text_body']},
        'html_body': {'S': email_data['html_body']},
        'received_at': {'N': str(received_at)}
    }
    
    dynamodb.put_item(TableName=EMAILS_TABLE, Item=item)
    
    print(f"✅ Stored email {email_id} for inbox {inbox_id}")
    return email_id


def create_test_inbox(inbox_id, ttl_seconds=3600):
    """Create test inbox in local DynamoDB"""
    import time
    
    now = int(time.time())
    
    item = {
        'id': {'S': inbox_id},
        'created_at': {'N': str(now)},
        'expires_at': {'N': str(now + ttl_seconds)}
    }
    
    try:
        dynamodb.put_item(TableName=INBOXES_TABLE, Item=item)
        print(f"✅ Created inbox {inbox_id}")
    except Exception as e:
        print(f"❌ Failed to create inbox: {e}")


def test_parser_with_file(email_file_path, inbox_id):
    """Test parser with a local email file"""
    
    print(f"\n📧 Testing email parser with {email_file_path}")
    print(f"📬 Target inbox: {inbox_id}\n")
    
    # Create test inbox
    create_test_inbox(inbox_id)
    
    # Parse email
    try:
        email_data = parse_email_file(email_file_path)
        
        print("📄 Parsed email data:")
        print(f"  From: {email_data['from']}")
        print(f"  To: {email_data['to']}")
        print(f"  Subject: {email_data['subject']}")
        print(f"  Text body length: {len(email_data['text_body'])} chars")
        print(f"  HTML body length: {len(email_data['html_body'])} chars")
        
        if email_data['html_body']:
            print(f"\n🧹 Sanitized HTML preview:")
            print(email_data['html_body'][:200] + "..." if len(email_data['html_body']) > 200 else email_data['html_body'])
        
        # Store in DynamoDB
        email_id = store_email_in_dynamodb(inbox_id, email_data)
        
        print(f"\n✅ Test complete! Email ID: {email_id}")
        print(f"\n💡 Test in frontend:")
        print(f"   1. Open http://localhost:8080")
        print(f"   2. Create inbox (or use existing)")
        print(f"   3. Email should appear in inbox list")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python test_email_parser.py <email_file> <inbox_id>")
        print("\nExample:")
        print("  python test_email_parser.py test_email.eml abc123")
        sys.exit(1)
    
    test_parser_with_file(sys.argv[1], sys.argv[2])
