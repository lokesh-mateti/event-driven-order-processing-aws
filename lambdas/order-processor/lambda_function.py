import json
import boto3
import uuid
import os
import socket
from datetime import datetime
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
orders_table = dynamodb.Table('orders')
products_table = dynamodb.Table('products')
sfn = boto3.client('stepfunctions')

REDIS_ENDPOINT = os.environ.get('REDIS_ENDPOINT', '')
REDIS_PORT = 6379
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN', '')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

def get_from_redis(key):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((REDIS_ENDPOINT, REDIS_PORT))
        s.send(f"GET {key}\r\n".encode())
        response = s.recv(4096).decode()
        s.close()
        if response.startswith('$-1'):
            return None
        lines = response.split('\r\n')
        return lines[1] if len(lines) > 1 else None
    except:
        return None

def set_in_redis(key, value, ttl=300):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((REDIS_ENDPOINT, REDIS_PORT))
        s.send(f"SETEX {key} {ttl} {value}\r\n".encode())
        s.recv(4096)
        s.close()
    except:
        pass

def lambda_handler(event, context):
    try:
        body = json.loads(event['body'])

        if not all(k in body for k in ['customerId', 'customerEmail', 'items']):
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing required fields'})
            }

        order_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()

        enriched_items = []
        for item in body['items']:
            product_id = item['productId']
            cache_key = f"product:{product_id}"

            cached = get_from_redis(cache_key)
            if cached:
                product = json.loads(cached)
                print(f"Cache hit for {product_id}")
            else:
                result = products_table.get_item(Key={'productId': product_id})
                product = result.get('Item', {})
                set_in_redis(cache_key, json.dumps(product, cls=DecimalEncoder))
                print(f"Cache miss for {product_id}, fetched from DynamoDB")

            enriched_items.append({**item, 'name': product.get('name', item.get('name', ''))})

        total = sum(item['price'] * item['quantity'] for item in body['items'])

        orders_table.put_item(Item={
            'orderId': order_id,
            'customerId': body['customerId'],
            'customerEmail': body['customerEmail'],
            'items': enriched_items,
            'total': str(total),
            'status': 'PENDING',
            'createdAt': timestamp
        })

        saga_input = {
            'orderId': order_id,
            'customerId': body['customerId'],
            'customerEmail': body['customerEmail'],
            'items': enriched_items,
            'total': str(total)
        }

        sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=order_id,
            input=json.dumps(saga_input)
        )

        return {
            'statusCode': 200,
            'body': json.dumps({
                'orderId': order_id,
                'status': 'PENDING',
                'total': total
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
