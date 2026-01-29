"""
Test email parser locally with attachment support
"""
import json
import sys
import os
import uuid as uuid_module
import time

# Add lambda directory to path (using importlib since 'lambda' is a keyword)
import importlib.util
lambda_dir = os.path.join(os.path.dirname(__file__), 'lambda')
spec = importlib.util.spec_from_file_location("email_parser", os.path.join(lambda_dir, "email_parser.py"))
email_parser_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(email_parser_module)
sanitize_html = email_parser_module.sanitize_html

from email import policy
from email.parser import BytesParser

def parse_email_file(email_file_path):
    """Parse email from local file including attachments"""
    with open(email_file_path, 'rb') as f:
        email_content = f.read()
    
    msg = BytesParser(policy=policy.default).parsebytes(email_content)
    
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


def test_parser_with_file(email_file_path):
    """Test parser with a local email file - no DynamoDB required"""
    
    print(f"\n📧 Testing email parser with: {email_file_path}")
    print("=" * 60)
    
    # Parse email
    try:
        email_data = parse_email_file(email_file_path)
        
        print("\n📄 PARSED EMAIL DATA:")
        print(f"  From:    {email_data['from']}")
        print(f"  To:      {email_data['to']}")
        print(f"  Subject: {email_data['subject']}")
        print(f"  Text body length: {len(email_data['text_body'])} chars")
        print(f"  HTML body length: {len(email_data['html_body'])} chars")
        
        # Display text body preview
        if email_data['text_body']:
            print(f"\n📝 TEXT BODY PREVIEW:")
            preview = email_data['text_body'][:300]
            print(f"  {preview}{'...' if len(email_data['text_body']) > 300 else ''}")
        
        # Display HTML sanitization result
        if email_data['html_body']:
            print(f"\n🧹 SANITIZED HTML PREVIEW:")
            preview = email_data['html_body'][:300]
            print(f"  {preview}{'...' if len(email_data['html_body']) > 300 else ''}")
        
        # Display attachments
        attachments = email_data.get('attachments', [])
        print(f"\n📎 ATTACHMENTS ({len(attachments)} found):")
        if attachments:
            for i, att in enumerate(attachments, 1):
                print(f"  {i}. {att['filename']}")
                print(f"     Type: {att['content_type']}")
                print(f"     Size: {att['size']} bytes ({att['size']/1024:.1f} KB)")
                # Show content preview for text files
                if att['content_type'].startswith('text/'):
                    try:
                        content_preview = att['data'].decode('utf-8')[:100]
                        print(f"     Preview: {content_preview}...")
                    except:
                        print(f"     [Binary content]")
        else:
            print("  No attachments found")
        
        print("\n" + "=" * 60)
        print("✅ EMAIL PARSING TEST COMPLETE!")
        print("=" * 60)
        
        # Generate mock DynamoDB structure
        print("\n📋 MOCK DYNAMODB ITEM STRUCTURE:")
        mock_item = {
            'inbox_id': 'test-inbox-123',
            'email_id': str(uuid_module.uuid4()),
            'from': email_data['from'],
            'subject': email_data['subject'],
            'text_body': f"[{len(email_data['text_body'])} chars]",
            'html_body': f"[{len(email_data['html_body'])} chars]",
            'received_at': int(time.time()),
            'attachments': [
                {
                    'id': str(uuid_module.uuid4()),
                    'filename': att['filename'],
                    'content_type': att['content_type'],
                    'size': att['size'],
                    's3_key': f"attachments/test-inbox/email-id/{att['filename']}"
                }
                for att in attachments
            ]
        }
        print(json.dumps(mock_item, indent=2, default=str))
        
        return email_data
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_attachment_parser.py <email_file>")
        print("\nExamples:")
        print("  python test_attachment_parser.py test_email.eml")
        print("  python test_attachment_parser.py test_email_with_attachment.eml")
        sys.exit(1)
    
    test_parser_with_file(sys.argv[1])
