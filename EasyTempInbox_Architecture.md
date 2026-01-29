# EasyTempInbox.com — Technical Implementation Plan

## 🎯 Goal

Build a **temporary email service** focused on:

- SEO-first
- Traffic-first
- Low cost
- Serverless backend
- Simple frontend (HTML + JS)
- No ads initially
- Default inbox expiry = **1 hour**
- Scalable later to premium & API

---

## 🧱 Phase-1 Architecture (100% Serverless, SES-based)

```
Internet
   |
   | SMTP
   v
AWS SES (Inbound Email)
   |
   v
S3 (Stores raw emails)
   |
   v
Lambda (Python email parser)
   |
   v
DynamoDB (inboxes + emails)
   |
   v
API Gateway → Lambda (Python API)
   |
   v
Static Frontend (HTML + JS via CDN)
```

> NOTE: If AWS SES causes policy issues, we will replace SES with a **Tiny VPS SMTP server** that forwards emails to the same API endpoint. Only the input changes, rest stays same.

---

## 🧠 Key Technical Decisions

- Frontend: **Plain HTML + JS**
- Backend: **Python on AWS Lambda**
- Storage: **DynamoDB**
- Email receiving: **AWS SES Inbound**
- Raw mail storage: **S3**
- CDN/DNS: **Cloudflare**
- No AdSense until **5k+ monthly views**

---

## 🗄️ DynamoDB Schema

### Table: `inboxes`

| Field | Type |
|------|------|
| id | string (PK) |
| created_at | number (epoch) |
| expires_at | number (epoch, TTL enabled) |

TTL is enabled on:
```
expires_at
```

---

### Table: `emails`

| Field | Type |
|------|------|
| inbox_id | string (PK) |
| email_id | string (SK) |
| from | string |
| subject | string |
| text_body | string |
| html_body | string |
| received_at | number |

---

## ⏱️ Inbox Expiry

- Default: **1 hour (3600 sec)**
- API supports:
```
POST /api/inbox?ttl=7200
```
- Enforced limits:
  - Min: 10 minutes
  - Max: 24 hours

---

## 🌐 API Design

### Inbox ID Format
- **8-character alphanumeric** (lowercase)
- URL-safe characters only
- Example: `a7x9k2m4`
- Generated using secure random

---

### 1) Create Inbox

```
POST /api/inbox
POST /api/inbox?ttl=3600
```

Response:
```json
{
  "id": "a7x9k2m4",
  "address": "a7x9k2m4@easytempinbox.com",
  "expires_at": 1769500000
}
```

Error Response (429 - Rate Limit):
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many inbox creation requests",
  "retry_after": 3600
}
```

---

### 2) List Emails (with Pagination)

```
GET /api/inbox/{id}/emails
GET /api/inbox/{id}/emails?limit=20&lastKey=xyz
```

Response:
```json
{
  "emails": [
    {
      "email_id": "uuid",
      "from": "test@gmail.com",
      "subject": "Hello",
      "received_at": 1769499000,
      "has_html": true
    }
  ],
  "lastKey": "xyz",
  "count": 5
}
```

Error Response (404 - Not Found):
```json
{
  "error": "inbox_not_found",
  "message": "Inbox does not exist or has expired"
}
```

---

### 3) Get Email

```
GET /api/email/{inbox_id}/{email_id}
```

Response:
```json
{
  "email_id": "uuid",
  "from": "test@gmail.com",
  "subject": "Hello",
  "text_body": "Email content...",
  "html_body": "<p>Email content...</p>",
  "received_at": 1769499000,
  "large_body_url": null
}
```

If body is large (stored in S3):
```json
{
  "email_id": "uuid",
  "from": "test@gmail.com",
  "subject": "Hello",
  "text_body": "[Content too large]",
  "html_body": "[Content too large]",
  "received_at": 1769499000,
  "large_body_url": "https://presigned-s3-url..."
}
```

---

### 4) Get Inbox Status

```
GET /api/inbox/{id}/status
```

Response:
```json
{
  "id": "a7x9k2m4",
  "exists": true,
  "expires_at": 1769500000,
  "email_count": 5
}
```

**Purpose**: Lightweight endpoint for polling without fetching all emails

---

## 📨 Email Ingestion Flow

1. Someone sends email to:
```
abc123@easytempinbox.com
```

2. SES receives email
3. Stores raw email in S3
4. Triggers Lambda
5. Lambda:
   - Parses raw email
   - Extracts inbox_id from "To"
   - Checks inbox exists and not expired
   - Stores email in DynamoDB

---

## 📦 S3 Storage Strategy

- S3 Lifecycle Policy:
  - Auto-delete raw emails after **48 hours**
  - Prevents orphaned data accumulation
  - Reduces storage costs

---

## 📏 Email Size Limits

- SES inbound limit: **10 MB**
- DynamoDB item limit: **400 KB**
- Strategy for large emails:
  - Store email metadata in DynamoDB
  - Store full HTML/text body in S3
  - Reference S3 object in DynamoDB record
- Enforced limits:
  - Text body in DynamoDB: Max 100 KB
  - HTML body in DynamoDB: Max 200 KB
  - Larger bodies: Store in S3, return presigned URL

---

## 🧱 Email Parser Lambda (Responsibilities)

- Read S3 object
- Parse email using Python `email` library
- Extract:
  - To
  - From
  - Subject
  - Text body
  - HTML body
- **Sanitize HTML content** (prevent XSS attacks)
  - Use library like `bleach` or `html-sanitizer`
  - Strip dangerous tags (script, iframe, etc.)
- **Check email size**:
  - If body > 100KB → store in S3, save reference
  - If body ≤ 100KB → store directly in DynamoDB
- Validate inbox exists and not expired
- Store into `emails` table
- **Lambda Configuration**:
  - Timeout: 30 seconds
  - Memory: 512 MB
  - Reserved concurrency: 10 (prevent cost spikes)

---

## 🧹 Cleanup Strategy

- DynamoDB TTL auto-deletes expired inboxes
- Emails:
  - Phase-1: Periodic cleanup Lambda OR tolerate orphan records
  - Phase-2: Cascade delete

---

## 🛡️ Abuse Controls (Phase-1)

- **API Gateway Rate Limiting**:
  - Inbox creation: **10 requests/hour per IP**
  - Email polling: **60 requests/minute per inbox**
  - Email retrieval: **100 requests/minute per inbox**
- **TTL Limits Enforced**:
  - Min: 10 minutes (600 sec)
  - Max: 24 hours (86400 sec)
  - Default: 1 hour (3600 sec)
- **SES Controls**:
  - Block known OTP / bank domains (optional)
  - Receipt rules to validate inbox exists
- **Email Limits**:
  - Max emails per inbox: **50**
  - Max email size: **10 MB** (SES limit)
- **Security Headers**:
  - CORS policy: Restrict to domain only
  - HTTPS enforcement via CloudFront
  - Content-Security-Policy for HTML emails

---

## 💰 Cost Strategy

- Lambda + DynamoDB + S3:
  - ₹0 – ₹300/month initially
- No VPS cost
- No fixed infra cost

---

## 🖥️ Frontend Plan

- Pure HTML + JS
- Pages:

```
/index.html
/inbox.html?id=abc123
/temporary-email.html
/disposable-email.html
/10-minute-mail.html
/how-it-works.html
/privacy.html
/terms.html
```

- **JS Functionality**:
  - Calls API Gateway
  - **Polling Strategy**:
    - Use `/api/inbox/{id}/status` endpoint
    - Exponential backoff: Start 5s → Max 30s
    - Stop polling when inbox expires
  - Renders email list
  - Shows email content with sanitized HTML
  - **Copy-to-clipboard** button for email address
  - **Countdown timer** showing inbox expiry
  - **Auto-refresh** indicator
  
- **Performance**:
  - Minified JS/CSS
  - Browser caching headers (1 year for static assets)
  - Lazy load email content
  
- **SEO Meta Tags**:
  - Title, description, keywords per page
  - Open Graph tags
  - Structured data (Schema.org)

---

## 🔍 SEO Strategy

- Static pages for:
  - temp mail
  - temporary inbox
  - disposable email
  - 10 minute mail
  - throwaway email
- Each page links to main inbox generator

---

## 🚀 Phase Roadmap

### Phase-1:
- Serverless backend
- SES inbound
- HTML+JS frontend
- No ads

### Phase-2:
- Add more domains
- Add premium
- Add API
- Add login
- Possibly migrate SMTP to VPS

---

## ⚠️ Known Risk

- AWS SES may not like disposable email use case.
- Mitigation:
  - Switch to Tiny VPS SMTP when needed
  - Keep API & DB unchanged

---

## 🌐 Multi-Domain Strategy

### Overview
Separate **brand domain** (website) from **email domains** (inbox addresses) for cost efficiency and blacklist resilience.

### Phase-1: Single Domain (Launch)
- **Domain**: `easytempinbox.com`
- **Usage**: Both website AND email addresses
- **Example**: User visits `easytempinbox.com`, gets `abc123@easytempinbox.com`
- **Cost**: ₹1,500/year
- **Purpose**: Test product-market fit, validate architecture

### Phase-2: Multi-Domain (After Validation)

#### Brand Domain (Premium)
- **Domain**: `easytempinbox.com`
- **Usage**: Website, SEO, branding ONLY
- **Never used for email addresses**
- **Protected from blacklists**
- **Cost**: ₹1,500/year

#### Email Domains (Cheap, Disposable)
- **TLDs**: .xyz, .top, .site, .online, .space, .fun
- **Cost**: ₹100-400/domain/year
- **Quantity**: Start with 10, scale to 50+
- **Examples**:
  - quickmail.xyz
  - tempbox.top
  - inboxnow.site
  - mailtemp.online
  - fastmail.space
  - testbox.fun
  - devmail.tech
  - mailnow.live
  - inboxgo.xyz
  - tempgo.top

#### User Experience (Phase-2)
1. User visits `easytempinbox.com`
2. Creates inbox with ID: `abc123`
3. Selects email domain from dropdown
4. Gets email: `abc123@quickmail.xyz`
5. If domain blacklisted → Switch to `abc123@tempbox.top` (same inbox ID)

#### Cost Breakdown
- **Year 1**: 1 domain (easytempinbox.com) = ₹1,500
- **Year 2**: 1 brand + 10 email domains = ₹4,000
- **Year 3+**: 1 brand + 50 email domains = ₹12,000-15,000

#### Benefits
- ✅ **Blacklist Resilience**: If 10 domains blacklisted, 40 still work
- ✅ **Brand Protection**: easytempinbox.com never gets blacklisted
- ✅ **Cost Efficiency**: ₹12K/year vs ₹75K/year for 50 premium domains
- ✅ **Scalability**: Add 5 new domains/quarter as needed
- ✅ **Zero Downtime**: Continuous service even during blacklisting

#### Technical Implementation
- **DNS**: All email domains point to same SES inbound endpoint
- **Backend**: Single Lambda processes emails from all domains
- **Database**: Same DynamoDB stores all inboxes (domain-agnostic)
- **Frontend**: Domain selector dropdown in UI
- **API**: Accepts inbox_id@any_allowed_domain

#### Domain Health Monitoring
- Daily blacklist checks
- Auto-disable blacklisted domains in UI
- Alert admin when domain blacklisted
- Maintain minimum 20 active domains at all times

#### Domain Acquisition Strategy
- Buy during Black Friday/Cyber Monday (₹50-100/domain)
- Use bulk registration APIs (Namecheap, Porkbun)
- Automate DNS configuration via Route 53 API
- Retire domains after 2 years if heavily blacklisted

---

## 🛠️ AWS Services Used

- **SES** (Inbound email receiving)
- **S3** (Raw email storage with 48h lifecycle)
- **Lambda** (Python - email parser + API)
- **DynamoDB** (Inboxes + emails with TTL)
- **API Gateway** (REST API with rate limiting)
- **EventBridge** (Cleanup cron - optional)
- **CloudFront** (CDN - **required** for global performance)
- **CloudWatch** (Logs, metrics, alarms)
- **Route 53** (DNS management)
- **ACM** (SSL certificates)

---

## 🧪 Testing Checklist

### Functional Tests
- ✅ Create inbox via API
- ✅ Verify inbox ID format (8-char alphanumeric)
- ✅ Send test email to inbox
- ✅ Confirm:
  - S3 object created
  - Lambda triggered and executed
  - DynamoDB has email record
  - Email content sanitized
- ✅ Fetch inbox via API
- ✅ Test pagination with 50+ emails
- ✅ Wait 1 hour → Inbox auto-expires (TTL)
- ✅ S3 object deleted after 48 hours

### Security Tests
- ✅ Send email with XSS payload → Verify sanitization
- ✅ Send email with malicious HTML → Verify stripping
- ✅ Test rate limiting (exceed 10 inbox/hour)
- ✅ Test CORS policy enforcement
- ✅ Verify HTTPS-only access

### Performance Tests
- ✅ Load test: 100 concurrent inbox creations
- ✅ Load test: 1000 emails to single inbox
- ✅ Measure API latency (target: <500ms p95)
- ✅ Test Lambda cold start time
- ✅ Verify CloudFront caching

### Edge Cases
- ✅ Send 10MB email (max size)
- ✅ Send email to non-existent inbox
- ✅ Send email to expired inbox
- ✅ Create inbox with invalid TTL
- ✅ Test with HTML-only email (no text)
- ✅ Test with attachments (verify handling)

---

## � DNS & Domain Configuration

### Route 53 Setup
- **MX Record**:
  ```
  easytempinbox.com  MX  10  inbound-smtp.us-east-1.amazonaws.com
  ```
- **SPF Record**:
  ```
  easytempinbox.com  TXT  "v=spf1 include:amazonses.com ~all"
  ```
- **DKIM Records**: Generated by SES, add to Route 53
- **DMARC Record** (optional):
  ```
  _dmarc.easytempinbox.com  TXT  "v=DMARC1; p=none; rua=mailto:admin@easytempinbox.com"
  ```

### SES Domain Verification
- Verify domain ownership via TXT record
- Enable DKIM signing
- Configure receipt rule set for inbound emails

---

## 📊 Monitoring & Observability

### CloudWatch Metrics
- **Custom Metrics**:
  - Inbox creation rate (per hour)
  - Email ingestion rate (per minute)
  - Active inbox count
  - Email delivery latency
  - API response time (p50, p95, p99)
  
### CloudWatch Alarms
- Lambda error rate > 5%
- API Gateway 5xx errors > 10/min
- DynamoDB throttling events
- S3 storage > 10 GB (cost alert)
  
### CloudWatch Logs
- Lambda execution logs (retention: 7 days)
- API Gateway access logs
- Error logs with structured JSON

### Dashboards
- Real-time inbox creation graph
- Email processing pipeline health
- API latency heatmap
- Cost breakdown by service

---

## 🚀 Deployment Strategy

### Infrastructure as Code
- **Tool**: AWS SAM or Terraform
- **Resources**:
  - Lambda functions
  - DynamoDB tables
  - API Gateway
  - S3 buckets with lifecycle policies
  - CloudFront distribution
  - SES receipt rules

### CI/CD Pipeline
- **Source Control**: Git (GitHub/GitLab)
- **Pipeline Stages**:
  1. **Build**: Package Lambda code + dependencies
  2. **Test**: Run unit tests + integration tests
  3. **Deploy to Staging**: Test environment
  4. **Manual Approval**: Review staging results
  5. **Deploy to Production**: Blue-green deployment

### Environments
- **Development**: Local testing with LocalStack
- **Staging**: Full AWS stack with test domain
- **Production**: Live domain with monitoring

### Rollback Strategy
- Lambda versioning + aliases
- API Gateway stage rollback
- DynamoDB point-in-time recovery enabled

---

## 🏁 Success Criteria

### Functional Requirements
- ✅ Can generate inbox with custom TTL
- ✅ Can receive email via SES
- ✅ Can view email with sanitized HTML
- ✅ Auto expiry works (DynamoDB TTL)
- ✅ S3 cleanup works (48h lifecycle)
- ✅ Rate limiting prevents abuse
- ✅ Pagination works for 50+ emails

### Performance Requirements
- ✅ API latency < 500ms (p95)
- ✅ Email processing < 5 seconds
- ✅ Frontend loads < 2 seconds
- ✅ CloudFront cache hit rate > 80%

### Cost Requirements
- ✅ Monthly cost: 0 – 300
- ✅ Zero fixed infrastructure cost
- ✅ Cost monitoring alerts configured

### SEO Requirements
- ✅ All SEO pages live and indexed
- ✅ sitemap.xml generated
- ✅ robots.txt configured
- ✅ Meta tags on all pages
- ✅ Structured data implemented
- ✅ Mobile-responsive design
- ✅ Page speed score > 90

### Security Requirements
- ✅ HTTPS enforced
- ✅ HTML sanitization working
- ✅ CORS policy configured
- ✅ Rate limiting active
- ✅ No sensitive data logged

### Pre-Launch Checklist
- ✅ DNS records configured
- ✅ SES domain verified
- ✅ CloudWatch alarms set
- ✅ Monitoring dashboard created
- ✅ Error handling tested
- ✅ Load testing completed
- ✅ Security audit passed
- ✅ Privacy policy published
- ✅ Terms of service published