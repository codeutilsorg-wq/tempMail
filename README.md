# EasyTempInbox

A serverless temporary email service built with AWS Lambda, DynamoDB, and SES.

## Features

- ✅ Generate temporary email addresses
- ✅ Auto-expiring inboxes (10 min - 24 hours)
- ✅ HTML email sanitization (XSS protection)
- ✅ Rate limiting
- ✅ Serverless architecture (AWS Lambda + DynamoDB)
- ✅ Modern, responsive UI

## Architecture

```
Internet → AWS SES → S3 → Lambda (Parser) → DynamoDB
                                              ↓
User → CloudFront → API Gateway → Lambda (API) → DynamoDB
```

## Project Structure

```
TempEmail/
├── backend/
│   ├── api/
│   │   └── main.py          # FastAPI application
│   ├── lambda/
│   │   └── email_parser.py  # SES email parser
│   ├── models/
│   │   ├── inbox.py         # Inbox data model
│   │   └── email.py         # Email data model
│   └── requirements.txt     # Python dependencies
├── frontend/
│   ├── index.html          # Main HTML page
│   ├── css/
│   │   └── style.css       # Styles
│   └── js/
│       └── app.js          # Frontend logic
├── config/
│   └── .env.example        # Environment variables template
└── docs/
    └── AWS_DEPLOYMENT.md   # Deployment guide
```

## Prerequisites

- Python 3.9+
- AWS Account
- AWS CLI configured
- Node.js (for local testing)

## Local Development

### Backend Setup

1. Create virtual environment:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp config/.env.example config/.env
# Edit config/.env with your AWS credentials
```

4. Run API locally:
```bash
cd backend/api
uvicorn main:app --reload
```

### Frontend Setup

1. Update API URL in `frontend/js/app.js`:
```javascript
const API_BASE_URL = 'http://localhost:8000'; // For local development
```

2. Serve frontend:
```bash
cd frontend
python -m http.server 8080
```

3. Open browser: `http://localhost:8080`

## AWS Deployment

See [docs/AWS_DEPLOYMENT.md](docs/AWS_DEPLOYMENT.md) for detailed deployment instructions.

### Quick Deployment Steps

1. **Create DynamoDB Tables**:
   - `easytempinbox-inboxes` (PK: id, TTL: expires_at)
   - `easytempinbox-emails` (PK: inbox_id, SK: email_id)

2. **Create S3 Bucket**:
   - `easytempinbox-raw-emails`
   - Enable lifecycle policy (delete after 48 hours)

3. **Configure SES**:
   - Verify domain
   - Set up receipt rule → S3
   - Configure DKIM, SPF

4. **Deploy Lambda Functions**:
   - Email Parser Lambda (triggered by S3)
   - API Lambda (behind API Gateway)

5. **Deploy Frontend**:
   - Upload to S3
   - Configure CloudFront

## Configuration

### Environment Variables

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret

# DynamoDB Tables
DYNAMODB_INBOXES_TABLE=easytempinbox-inboxes
DYNAMODB_EMAILS_TABLE=easytempinbox-emails

# S3 Bucket
S3_BUCKET_NAME=easytempinbox-raw-emails

# Domain
PRIMARY_DOMAIN=easytempinbox.com

# Limits
DEFAULT_TTL_SECONDS=3600
MIN_TTL_SECONDS=600
MAX_TTL_SECONDS=86400
MAX_EMAILS_PER_INBOX=50
```

## API Endpoints

### Create Inbox
```
POST /api/inbox
Body: { "ttl": 3600 }
Response: { "id": "abc123", "address": "abc123@easytempinbox.com", "expires_at": 1234567890 }
```

### List Emails
```
GET /api/inbox/{inbox_id}/emails?limit=20
Response: { "emails": [...], "count": 5 }
```

### Get Email
```
GET /api/email/{inbox_id}/{email_id}
Response: { "email_id": "...", "from_address": "...", "subject": "...", ... }
```

### Get Inbox Status
```
GET /api/inbox/{inbox_id}/status
Response: { "id": "...", "exists": true, "expires_at": 1234567890, "email_count": 5 }
```

## Security Features

- ✅ HTML sanitization (bleach library)
- ✅ Rate limiting
- ✅ TTL enforcement
- ✅ Email size limits
- ✅ CORS configuration
- ✅ HTTPS only (CloudFront)

## Testing

### Manual Testing

1. Create inbox via API
2. Send test email to generated address
3. Verify email appears in inbox
4. Check HTML sanitization
5. Wait for TTL expiry
6. Verify inbox auto-deletion

### Automated Testing

```bash
# Coming soon
pytest backend/tests/
```

## Monitoring

- CloudWatch Logs (Lambda execution)
- CloudWatch Metrics (API Gateway, Lambda)
- DynamoDB metrics
- S3 storage metrics

## Cost Estimate

- **Year 1**: ₹300-500/month
  - Lambda: ₹50-100
  - DynamoDB: ₹100-200
  - S3: ₹50-100
  - SES: ₹0 (receiving is free)
  - CloudFront: ₹50-100

## Roadmap

- [x] Phase 1: MVP (Single domain)
- [ ] Phase 2: Multi-domain support
- [ ] Phase 3: Premium tier
- [ ] Phase 4: API monetization
- [ ] Phase 5: Mobile app

## Contributing

Contributions welcome! Please open an issue or PR.

## License

MIT License

## Support

For issues or questions, please open a GitHub issue.

---

Built with ❤️ for privacy
