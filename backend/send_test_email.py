"""
Send test emails to MailHog for local testing
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_test_email(to_address, subject="Test Email", smtp_host='localhost', smtp_port=1025):
    """
    Send a test email via local SMTP server (MailHog)
    
    Args:
        to_address: Email address to send to (e.g., 'abc123@localhost')
        subject: Email subject
        smtp_host: SMTP server host (default: localhost for MailHog)
        smtp_port: SMTP server port (default: 1025 for MailHog)
    """
    
    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = 'test@example.com'
    msg['To'] = to_address
    
    # Plain text version
    text = f"""
This is a test email sent to {to_address}.

This email contains:
- Plain text content
- HTML content
- Test data for inbox testing

Timestamp: {__import__('time').strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    # HTML version
    html = f"""
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        .header {{ background: #6366f1; color: white; padding: 20px; }}
        .content {{ padding: 20px; }}
        .footer {{ background: #f3f4f6; padding: 10px; text-align: center; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔒 Test Email</h1>
    </div>
    <div class="content">
        <h2>Hello from EasyTempInbox!</h2>
        <p>This is a <strong>test email</strong> sent to <code>{to_address}</code>.</p>
        
        <h3>Email Features:</h3>
        <ul>
            <li>✅ HTML rendering</li>
            <li>✅ Plain text fallback</li>
            <li>✅ XSS protection</li>
            <li>✅ Responsive design</li>
        </ul>
        
        <p>If you can see this, your email system is working! 🎉</p>
        
        <p><a href="https://example.com">Click here for more info</a></p>
    </div>
    <div class="footer">
        <p>Sent at: {__import__('time').strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
</body>
</html>
"""
    
    # Attach both versions
    msg.attach(MIMEText(text, 'plain'))
    msg.attach(MIMEText(html, 'html'))
    
    # Send email
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.send_message(msg)
        
        print(f"✅ Email sent successfully!")
        print(f"   To: {to_address}")
        print(f"   Subject: {subject}")
        print(f"   SMTP: {smtp_host}:{smtp_port}")
        print(f"\n💡 View in MailHog: http://localhost:8025")
        
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        print(f"\n💡 Make sure MailHog is running:")
        print(f"   docker run -p 1025:1025 -p 8025:8025 mailhog/mailhog")


def send_multiple_test_emails(inbox_id, count=3):
    """Send multiple test emails to the same inbox"""
    
    print(f"\n📧 Sending {count} test emails to inbox: {inbox_id}\n")
    
    for i in range(1, count + 1):
        send_test_email(
            to_address=f"{inbox_id}@localhost",
            subject=f"Test Email #{i}"
        )
        print()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python send_test_email.py <inbox_id> [count]")
        print("\nExamples:")
        print("  python send_test_email.py abc123")
        print("  python send_test_email.py abc123 5")
        print("\nMake sure MailHog is running:")
        print("  docker run -p 1025:1025 -p 8025:8025 mailhog/mailhog")
        sys.exit(1)
    
    inbox_or_email = sys.argv[1]
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    
    # Check if it's already a full email address or just an inbox ID
    if '@' in inbox_or_email:
        to_address = inbox_or_email
    else:
        to_address = f"{inbox_or_email}@localhost"
    
    if count == 1:
        send_test_email(to_address)
    else:
        for i in range(1, count + 1):
            send_test_email(to_address, subject=f"Test Email #{i}")
