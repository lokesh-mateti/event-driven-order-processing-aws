import json
import boto3
import os
from datetime import datetime
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import urllib3

def lambda_handler(event, context):
    endpoint = os.environ.get('OPENSEARCH_ENDPOINT', '')
    session = boto3.Session()
    credentials = session.get_credentials()
    region = 'us-east-1'
    
    http = urllib3.PoolManager()
    
    for record in event['Records']:
        body = json.loads(record['body'])
        detail = body['detail']
        order_id = detail['orderId']
        
        doc = {
            'orderId': order_id,
            'customerId': detail['customerId'],
            'customerEmail': detail['customerEmail'],
            'total': detail['total'],
            'items': detail['items'],
            'indexedAt': datetime.utcnow().isoformat()
        }
        
        url = f"https://{endpoint}/orders/_doc/{order_id}"
        doc_bytes = json.dumps(doc).encode('utf-8')
        
        request = AWSRequest(method='PUT', url=url, data=doc_bytes, headers={'Content-Type': 'application/json'})
        SigV4Auth(credentials, 'es', region).add_auth(request)
        
        signed_headers = dict(request.headers)
        response = http.request('PUT', url, body=doc_bytes, headers=signed_headers)
        
        print(f"Indexed order {order_id}, status: {response.status}")
    
    return {'statusCode': 200}