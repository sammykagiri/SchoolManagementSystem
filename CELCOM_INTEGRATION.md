# School Management System - Celcom Africa SMS Integration

## SMS Service Configuration

The system has been updated to use Celcom Africa instead of Twilio for SMS services. 

### Required Environment Variables

Add the following variables to your `.env` file:

```env
# Celcom Africa SMS Settings
CELCOM_URL_SENDSMS=https://api.celcomafrica.com/sendsms
CELCOM_URL_GETBALANCE=https://api.celcomafrica.com/getbalance
CELCOM_API_KEY=your-celcom-api-key
CELCOM_PARTNER_ID=your-partner-id
CELCOM_SHORTCODE=your-shortcode
CELCOM_COMPANY_PHONE=254xxxxxxxxx
```

### Phone Number Format

The system automatically validates and formats phone numbers to the Kenyan format (254xxxxxxxxx):
- `+254712345678` → `254712345678`
- `0712345678` → `254712345678`
- `712345678` → `254712345678`

### API Response Codes

The system handles the following Celcom Africa API response codes:
- `200`: Successful Request Call
- `1001`: Invalid sender id
- `1002`: Network not allowed
- `1003`: Invalid mobile number
- `1004`: Low bulk credits
- `1005`: Failed. System error
- `1006`: Invalid credentials
- `1007`: Failed. System error
- `1008`: No Delivery Report
- `1009`: Unsupported data type
- `1010`: Unsupported request type
- `4090`: Internal Error. Try again after 5 minutes
- `4091`: No Partner ID is Set
- `4092`: No API KEY Provided
- `4093`: Details Not Found

### Usage

The SMS service is automatically used by the communication system for:
- Payment receipt notifications
- Due date reminders
- Overdue payment notices

### Testing

To test the SMS service:

```python
from communications.services import SMSService

sms_service = SMSService()
result = sms_service.send_sms(
    recipient_phone="254712345678",
    content="Test message from School Management System"
)
print(f"SMS sent: {result}")
```

### Migration Notes

- Twilio dependency has been removed from `requirements.txt`
- All Twilio settings have been replaced with Celcom Africa settings
- The `twilio_sid` field in the database is now used to store Celcom Africa message IDs
- Phone number validation has been updated for Kenyan format
