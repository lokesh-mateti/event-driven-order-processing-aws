import json
import boto3
import os

ses = boto3.client('ses', region_name='us-east-1')
VERIFIED_EMAIL = os.environ.get('VERIFIED_EMAIL', '')

def lambda_handler(event, context):
    for record in event['Records']:
        body = json.loads(record['body'])
        detail = body['detail']
        
        ses.send_email(
            Source=VERIFIED_EMAIL,
            Destination={'ToAddresses': [detail['customerEmail']]},
            Message={
                'Subject': {'Data': f"Order Confirmed - {detail['orderId']}"},
                'Body': {
                    'Text': {
                        'Data': f"Your order {detail['orderId']} has been confirmed. Total: ${detail['total']}"
                    }
                }
            }
        )
        print(f"Email sent for order {detail['orderId']}")
    
    return {'statusCode': 200}