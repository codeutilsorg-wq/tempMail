# Local Testing Guide for EasyTempInbox

This guide shows you how to test EasyTempInbox locally without deploying to AWS.

---

## 🎯 Testing Strategy

### **What You Can Test Locally:**
- ✅ Frontend UI (fully functional)
- ✅ API endpoints (with mock data)
- ✅ Email parsing logic (with test files)
- ✅ HTML sanitization
- ✅ Data models

### **What Requires AWS:**
- ❌ Actual email receiving (SES)
- ❌ DynamoDB storage (can use local DynamoDB)
- ❌ S3 storage (can use LocalStack)

---

## Option 1: Frontend-Only Testing (Easiest)

### **Test the UI without backend**

```bash
# Navigate to frontend
cd frontend

# Start local server
python -m http.server 8080

# Open browser
# Visit: http://localhost:8080
```

**What works:**
- UI layout and styling
- Button interactions
- Form validation
- Responsive design

**What doesn't work:**
- API calls (will fail gracefully)
- Email creation
- Email listing

**Use case:** Perfect for UI/UX testing and design iteration

---

## Option 2: Backend API Testing (Recommended)

### **Run FastAPI locally with mock DynamoDB**

#### **Step 1: Install dependencies**

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### **Step 2: Install DynamoDB Local (Optional)**

```bash
# Download DynamoDB Local
# https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html

# Or use Docker
docker run -p 8000:8000 amazon/dynamodb-local
```

#### **Step 3: Create local tables**

```bash
# Create inboxes table
aws dynamodb create-table \
    --table-name easytempinbox-inboxes \
    --attribute-definitions AttributeName=id,AttributeType=S \
    --key-schema AttributeName=id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --endpoint-url http://localhost:8000

# Create emails table
aws dynamodb create-table \
    --table-name easytempinbox-emails \
    --attribute-definitions \
        AttributeName=inbox_id,AttributeType=S \
        AttributeName=email_id,AttributeType=S \
    --key-schema \
        AttributeName=inbox_id,KeyType=HASH \
        AttributeName=email_id,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --endpoint-url http://localhost:8000
```

#### **Step 4: Configure environment**

Create `backend/.env`:

```bash
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
DYNAMODB_INBOXES_TABLE=easytempinbox-inboxes
DYNAMODB_EMAILS_TABLE=easytempinbox-emails
PRIMARY_DOMAIN=localhost
```

#### **Step 5: Modify API to use local DynamoDB**

Edit `backend/api/main.py` (add after imports):

```python
import os

# For local testing
if os.getenv('LOCAL_TESTING') == 'true':
    dynamodb = boto3.client(
        'dynamodb',
        region_name='us-east-1',
        endpoint_url='http://localhost:8000',
        aws_access_key_id='test',
        aws_secret_access_key='test'
    )
else:
    dynamodb = boto3.client('dynamodb', region_name=os.getenv('AWS_REGION', 'us-east-1'))
```

#### **Step 6: Run API server**

```bash
cd backend/api
LOCAL_TESTING=true uvicorn main:app --reload --port 8001
```

#### **Step 7: Update frontend API URL**

Edit `frontend/js/app.js` (line 7):

```javascript
const API_BASE_URL = 'http://localhost:8001';
```

#### **Step 8: Test API**

```bash
# Create inbox
curl -X POST http://localhost:8000/api/inbox \
  -H "Content-Type: application/json" \
  -d '{"ttl": 3600}'

# Response: {"id":"abc123","address":"abc123@localhost","expires_at":1234567890}

# List emails (will be empty)
curl http://localhost:8000/api/inbox/abc123/emails

# Get inbox status
curl http://localhost:8000/api/inbox/abc123/status
```

---

## Option 3: Email Parsing Testing (Most Complete)

### **Test email parser with local SMTP server**

#### **Option 3A: Using MailHog (Recommended)**

**MailHog** is a fake SMTP server perfect for testing.

##### **Install MailHog**

**Windows:**
```bash
# Download from: https://github.com/mailhog/MailHog/releases
# Run MailHog.exe
```

**macOS:**
```bash
brew install mailhog
mailhog
```

**Linux:**
```bash
# Download binary
wget https://github.com/mailhog/MailHog/releases/download/v1.0.1/MailHog_linux_amd64
chmod +x MailHog_linux_amd64
./MailHog_linux_amd64
```

**Docker:**
```bash
docker run -d -p 1025:1025 -p 8025:8025 mailhog/mailhog
```

##### **MailHog URLs**
- SMTP Server: `localhost:1025`
- Web UI: `http://localhost:8025`

##### **Send test email**

```python
# test_send_email.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_test_email(to_address):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Test Email'
    msg['From'] = 'test@example.com'
    msg['To'] = to_address
    
    text = "This is a test email"
    html = "<html><body><h1>Test Email</h1><p>This is a test</p></body></html>"
    
    msg.attach(MIMEText(text, 'plain'))
    msg.attach(MIMEText(html, 'html'))
    
    # Send via MailHog
    with smtplib.SMTP('localhost', 1025) as server:
        server.send_message(msg)
    
    print(f"Email sent to {to_address}")

# Usage
send_test_email('abc123@localhost')
```

##### **View email in MailHog**
1. Open `http://localhost:8025`
2. See your test email
3. Download raw email for parser testing

---

#### **Option 3B: Using smtp4dev**

**smtp4dev** is another excellent local SMTP server with a nice UI.

##### **Install smtp4dev**

**Docker:**
```bash
docker run -d -p 3000:80 -p 2525:25 rnwood/smtp4dev
```

**Standalone:**
```bash
# Download from: https://github.com/rnwood/smtp4dev/releases
```

##### **smtp4dev URLs**
- SMTP Server: `localhost:2525`
- Web UI: `http://localhost:3000`

---

#### **Option 3C: Using Python's built-in SMTP server**

**Simplest option, but no web UI**

```bash
# Start SMTP debug server
python -m smtpd -n -c DebuggingServer localhost:1025
```

This prints all emails to console.

---

## Option 4: Complete Local Testing Setup

### **Full local environment with email flow**

#### **Step 1: Start all services**

**Terminal 1: DynamoDB Local**
```bash
docker run -p 8000:8000 amazon/dynamodb-local
```

**Terminal 2: MailHog**
```bash
docker run -p 1025:1025 -p 8025:8025 mailhog/mailhog
```

**Terminal 3: API Server**
```bash
cd backend/api
LOCAL_TESTING=true uvicorn main:app --reload --port 8000
```

**Terminal 4: Frontend**
```bash
cd frontend
python -m http.server 8080
```

#### **Step 2: Create test email parser script**

Create `backend/test_email_parser.py`:

```python
"""
Test email parser locally by reading email files
"""
import json
import sys
from lambda.email_parser import parse_email_from_s3, store_email_in_dynamodb

def test_parser_with_file(email_file_path, inbox_id):
    """Test parser with a local email file"""
    
    # Read email file
    with open(email_file_path, 'rb') as f:
        email_content = f.read()
    
    # Mock S3 response
    class MockS3Response:
        def __init__(self, content):
            self.content = content
        
        class Body:
            def __init__(self, content):
                self.content = content
            
            def read(self):
                return self.content
        
        def __getitem__(self, key):
            if key == 'Body':
                return self.Body(self.content)
    
    # Parse email (you'll need to modify parse_email_from_s3 to accept content directly)
    # For now, manually parse
    from email import policy
    from email.parser import BytesParser
    
    msg = BytesParser(policy=policy.default).parsebytes(email_content)
    
    email_data = {
        'to': msg.get('To', ''),
        'from': msg.get('From', ''),
        'subject': msg.get('Subject', ''),
        'text_body': '',
        'html_body': ''
    }
    
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                email_data['text_body'] = part.get_content()
            elif part.get_content_type() == 'text/html':
                email_data['html_body'] = part.get_content()
    else:
        if msg.get_content_type() == 'text/plain':
            email_data['text_body'] = msg.get_content()
        elif msg.get_content_type() == 'text/html':
            email_data['html_body'] = msg.get_content()
    
    print(f"Parsed email: {json.dumps(email_data, indent=2)}")
    
    # Store in DynamoDB (if local DynamoDB is running)
    try:
        store_email_in_dynamodb(inbox_id, email_data)
        print(f"Stored email in DynamoDB for inbox {inbox_id}")
    except Exception as e:
        print(f"Failed to store in DynamoDB: {e}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python test_email_parser.py <email_file> <inbox_id>")
        sys.exit(1)
    
    test_parser_with_file(sys.argv[1], sys.argv[2])
```

#### **Step 3: Create sample email file**

Create `backend/test_email.eml`:

```
From: test@example.com
To: abc123@localhost
Subject: Test Email
Content-Type: multipart/alternative; boundary="boundary123"

--boundary123
Content-Type: text/plain; charset="utf-8"

This is a test email in plain text.

--boundary123
Content-Type: text/html; charset="utf-8"

<html>
<body>
<h1>Test Email</h1>
<p>This is a <strong>test email</strong> in HTML.</p>
<script>alert('XSS')</script>
</body>
</html>

--boundary123--
```

#### **Step 4: Test parser**

```bash
cd backend
python test_email_parser.py test_email.eml abc123
```

This will:
1. Parse the email file
2. Sanitize HTML (remove `<script>` tag)
3. Store in local DynamoDB

#### **Step 5: Verify in frontend**

1. Open `http://localhost:8080`
2. Create inbox with ID `abc123`
3. Email should appear in inbox
4. Verify HTML is sanitized (no script tag)

---

## Option 5: Using LocalStack (Advanced)

**LocalStack** emulates AWS services locally.

### **Install LocalStack**

```bash
pip install localstack
```

### **Start LocalStack**

```bash
localstack start
```

### **Configure services**

```bash
# Create S3 bucket
aws --endpoint-url=http://localhost:4566 s3 mb s3://easytempinbox-raw-emails

# Create DynamoDB tables
aws --endpoint-url=http://localhost:4566 dynamodb create-table ...

# Configure SES (limited support)
aws --endpoint-url=http://localhost:4566 ses verify-email-identity --email-address test@example.com
```

---

## 🧪 Testing Checklist

### **Frontend Testing**
- [ ] UI loads correctly
- [ ] Generate button works
- [ ] Email address displays
- [ ] Copy button works
- [ ] Countdown timer works
- [ ] Responsive on mobile

### **API Testing**
- [ ] Create inbox endpoint
- [ ] List emails endpoint
- [ ] Get email endpoint
- [ ] Inbox status endpoint
- [ ] Error handling
- [ ] CORS headers

### **Email Parser Testing**
- [ ] Parse plain text email
- [ ] Parse HTML email
- [ ] Parse multipart email
- [ ] HTML sanitization works
- [ ] XSS prevention works
- [ ] Email size limits work

### **Integration Testing**
- [ ] Create inbox via API
- [ ] Send email via SMTP
- [ ] Email appears in inbox
- [ ] Email details load correctly
- [ ] Countdown timer accurate
- [ ] Inbox expires correctly

---

## 🎯 Recommended Testing Workflow

### **Day 1: Frontend**
1. Test UI locally
2. Verify responsive design
3. Test all interactions

### **Day 2: API**
1. Set up local DynamoDB
2. Run API server
3. Test all endpoints with curl/Postman

### **Day 3: Email Parsing**
1. Set up MailHog
2. Create test email files
3. Test parser with various email formats

### **Day 4: Integration**
1. Connect all pieces
2. Test full flow
3. Fix any issues

### **Day 5: Deploy to AWS**
1. Follow deployment guide
2. Test with real emails
3. Monitor CloudWatch logs

---

## 🐛 Troubleshooting

### **API won't start**
- Check Python version (3.9+)
- Verify all dependencies installed
- Check port 8000 is free

### **DynamoDB connection fails**
- Verify DynamoDB Local is running
- Check endpoint URL
- Verify table names match

### **Emails not parsing**
- Check email file format
- Verify MIME structure
- Check for encoding issues

### **Frontend can't reach API**
- Verify API_BASE_URL is correct
- Check CORS configuration
- Verify API server is running

---

## 📚 Useful Tools

### **Email Testing**
- **MailHog**: https://github.com/mailhog/MailHog
- **smtp4dev**: https://github.com/rnwood/smtp4dev
- **Mailtrap**: https://mailtrap.io (cloud-based)

### **API Testing**
- **Postman**: https://www.postman.com
- **Insomnia**: https://insomnia.rest
- **curl**: Command-line HTTP client

### **AWS Local**
- **LocalStack**: https://localstack.cloud
- **DynamoDB Local**: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html

---

## 🚀 Quick Start Commands

**Fastest way to test locally:**

```bash
# Terminal 1: Start MailHog
docker run -p 1025:1025 -p 8025:8025 mailhog/mailhog

# Terminal 2: Start DynamoDB
docker run -p 8000:8000 amazon/dynamodb-local

# Terminal 3: Start API
cd backend/api
LOCAL_TESTING=true uvicorn main:app --reload

# Terminal 4: Start Frontend
cd frontend
python -m http.server 8080

# Browser: http://localhost:8080
# MailHog UI: http://localhost:8025
```

---

**Happy Testing!** 🧪
