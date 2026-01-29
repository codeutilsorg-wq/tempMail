# AWS Deployment Guide for EasyTempInbox

This guide walks you through deploying EasyTempInbox to AWS.

## Prerequisites

- AWS Account
- AWS CLI installed and configured
- Domain name (e.g., easytempinbox.com)
- Python 3.9+

## Step 1: Create DynamoDB Tables

### Inboxes Table

```bash
aws dynamodb create-table \
    --table-name easytempinbox-inboxes \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
    --key-schema \
        AttributeName=id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1
```

### Enable TTL on Inboxes Table

```bash
aws dynamodb update-time-to-live \
    --table-name easytempinbox-inboxes \
    --time-to-live-specification \
        Enabled=true,AttributeName=expires_at \
    --region us-east-1
```

### Emails Table

```bash
aws dynamodb create-table \
    --table-name easytempinbox-emails \
    --attribute-definitions \
        AttributeName=inbox_id,AttributeType=S \
        AttributeName=email_id,AttributeType=S \
    --key-schema \
        AttributeName=inbox_id,KeyType=HASH \
        AttributeName=email_id,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1
```

## Step 2: Create S3 Bucket for Raw Emails

```bash
aws s3 mb s3://easytempinbox-raw-emails --region us-east-1
```

### Configure Lifecycle Policy

Create `lifecycle-policy.json`:

```json
{
    "Rules": [{
        "Id": "DeleteAfter48Hours",
        "Status": "Enabled",
        "Expiration": {
            "Days": 2
        }
    }]
}
```

Apply policy:

```bash
aws s3api put-bucket-lifecycle-configuration \
    --bucket easytempinbox-raw-emails \
    --lifecycle-configuration file://lifecycle-policy.json
```

## Step 3: Configure SES

### Verify Domain

```bash
aws ses verify-domain-identity \
    --domain easytempinbox.com \
    --region us-east-1
```

Add the verification TXT record to your DNS.

### Configure DKIM

```bash
aws ses verify-domain-dkim \
    --domain easytempinbox.com \
    --region us-east-1
```

Add the DKIM CNAME records to your DNS.

### Create Receipt Rule Set

```bash
aws ses create-receipt-rule-set \
    --rule-set-name easytempinbox-rules \
    --region us-east-1

aws ses set-active-receipt-rule-set \
    --rule-set-name easytempinbox-rules \
    --region us-east-1
```

### Create Receipt Rule

Create `receipt-rule.json`:

```json
{
    "Name": "store-emails-in-s3",
    "Enabled": true,
    "TlsPolicy": "Optional",
    "Recipients": ["easytempinbox.com"],
    "Actions": [{
        "S3Action": {
            "BucketName": "easytempinbox-raw-emails",
            "ObjectKeyPrefix": "emails/"
        }
    }],
    "ScanEnabled": true
}
```

Apply rule:

```bash
aws ses create-receipt-rule \
    --rule-set-name easytempinbox-rules \
    --rule file://receipt-rule.json \
    --region us-east-1
```

## Step 4: Deploy Email Parser Lambda

### Package Lambda

```bash
cd backend/lambda
pip install -r ../requirements.txt -t .
zip -r email_parser.zip .
```

### Create IAM Role

Create `lambda-trust-policy.json`:

```json
{
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {
            "Service": "lambda.amazonaws.com"
        },
        "Action": "sts:AssumeRole"
    }]
}
```

Create role:

```bash
aws iam create-role \
    --role-name easytempinbox-lambda-role \
    --assume-role-policy-document file://lambda-trust-policy.json
```

Attach policies:

```bash
aws iam attach-role-policy \
    --role-name easytempinbox-lambda-role \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam attach-role-policy \
    --role-name easytempinbox-lambda-role \
    --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess

aws iam attach-role-policy \
    --role-name easytempinbox-lambda-role \
    --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
```

### Create Lambda Function

```bash
aws lambda create-function \
    --function-name easytempinbox-email-parser \
    --runtime python3.9 \
    --role arn:aws:iam::YOUR_ACCOUNT_ID:role/easytempinbox-lambda-role \
    --handler email_parser.lambda_handler \
    --zip-file fileb://email_parser.zip \
    --timeout 30 \
    --memory-size 512 \
    --environment Variables="{DYNAMODB_INBOXES_TABLE=easytempinbox-inboxes,DYNAMODB_EMAILS_TABLE=easytempinbox-emails,S3_BUCKET_NAME=easytempinbox-raw-emails}" \
    --region us-east-1
```

### Add S3 Trigger

```bash
aws lambda add-permission \
    --function-name easytempinbox-email-parser \
    --statement-id s3-trigger \
    --action lambda:InvokeFunction \
    --principal s3.amazonaws.com \
    --source-arn arn:aws:s3:::easytempinbox-raw-emails \
    --region us-east-1

aws s3api put-bucket-notification-configuration \
    --bucket easytempinbox-raw-emails \
    --notification-configuration file://s3-notification.json
```

`s3-notification.json`:

```json
{
    "LambdaFunctionConfigurations": [{
        "LambdaFunctionArn": "arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:function:easytempinbox-email-parser",
        "Events": ["s3:ObjectCreated:*"],
        "Filter": {
            "Key": {
                "FilterRules": [{
                    "Name": "prefix",
                    "Value": "emails/"
                }]
            }
        }
    }]
}
```

## Step 5: Deploy API Lambda

### Package API Lambda

```bash
cd backend/api
pip install -r ../requirements.txt -t .
zip -r api.zip .
```

### Create Lambda Function

```bash
aws lambda create-function \
    --function-name easytempinbox-api \
    --runtime python3.9 \
    --role arn:aws:iam::YOUR_ACCOUNT_ID:role/easytempinbox-lambda-role \
    --handler main.handler \
    --zip-file fileb://api.zip \
    --timeout 10 \
    --memory-size 512 \
    --environment Variables="{DYNAMODB_INBOXES_TABLE=easytempinbox-inboxes,DYNAMODB_EMAILS_TABLE=easytempinbox-emails,PRIMARY_DOMAIN=easytempinbox.com}" \
    --region us-east-1
```

## Step 6: Create API Gateway

### Create REST API

```bash
aws apigateway create-rest-api \
    --name easytempinbox-api \
    --region us-east-1
```

### Configure API Gateway (Manual via Console)

1. Go to API Gateway console
2. Create resources and methods
3. Integrate with Lambda function
4. Enable CORS
5. Deploy to stage (e.g., "prod")
6. Note the API Gateway URL

## Step 7: Deploy Frontend

### Create S3 Bucket for Frontend

```bash
aws s3 mb s3://easytempinbox-frontend --region us-east-1
```

### Configure for Static Website Hosting

```bash
aws s3 website s3://easytempinbox-frontend \
    --index-document index.html \
    --error-document index.html
```

### Update API URL in Frontend

Edit `frontend/js/app.js`:

```javascript
const API_BASE_URL = 'https://your-api-id.execute-api.us-east-1.amazonaws.com/prod';
```

### Upload Frontend

```bash
cd frontend
aws s3 sync . s3://easytempinbox-frontend --acl public-read
```

## Step 8: Configure CloudFront

### Create CloudFront Distribution

```bash
aws cloudfront create-distribution \
    --origin-domain-name easytempinbox-frontend.s3.amazonaws.com \
    --default-root-object index.html
```

### Configure Custom Domain

1. Request SSL certificate in ACM (us-east-1)
2. Add CNAME record in Route 53
3. Update CloudFront distribution with custom domain

## Step 9: Configure DNS

Add these records to your DNS:

```
# MX Record for SES
easytempinbox.com  MX  10  inbound-smtp.us-east-1.amazonaws.com

# SPF Record
easytempinbox.com  TXT  "v=spf1 include:amazonses.com ~all"

# DKIM Records (from SES verification)
[dkim-selector]._domainkey.easytempinbox.com  CNAME  [ses-dkim-value]

# CloudFront
easytempinbox.com  A  [cloudfront-distribution-domain]
```

## Step 10: Testing

1. Visit your domain
2. Generate an inbox
3. Send a test email
4. Verify email appears in inbox
5. Check CloudWatch logs for any errors

## Monitoring

### CloudWatch Alarms

```bash
# Lambda errors
aws cloudwatch put-metric-alarm \
    --alarm-name easytempinbox-lambda-errors \
    --alarm-description "Alert on Lambda errors" \
    --metric-name Errors \
    --namespace AWS/Lambda \
    --statistic Sum \
    --period 300 \
    --evaluation-periods 1 \
    --threshold 5 \
    --comparison-operator GreaterThanThreshold

# API Gateway 5xx errors
aws cloudwatch put-metric-alarm \
    --alarm-name easytempinbox-api-5xx \
    --alarm-description "Alert on API 5xx errors" \
    --metric-name 5XXError \
    --namespace AWS/ApiGateway \
    --statistic Sum \
    --period 300 \
    --evaluation-periods 1 \
    --threshold 10 \
    --comparison-operator GreaterThanThreshold
```

## Cost Optimization

- Use DynamoDB on-demand billing initially
- Enable S3 lifecycle policies
- Set Lambda reserved concurrency
- Use CloudFront caching

## Troubleshooting

### Emails not appearing

1. Check SES receipt rules
2. Verify S3 bucket permissions
3. Check Lambda CloudWatch logs
4. Verify DynamoDB tables exist

### API errors

1. Check API Gateway logs
2. Verify Lambda permissions
3. Check DynamoDB table names in environment variables

## Next Steps

- Set up monitoring dashboard
- Configure backup for DynamoDB
- Implement rate limiting at API Gateway
- Add CloudWatch alarms
- Set up CI/CD pipeline

---

**Deployment Complete!** 🎉

Your temporary email service is now live at `https://easytempinbox.com`
