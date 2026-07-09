import json
import boto3

dynamodb = boto3.resource('dynamodb')
orders_table = dynamodb.Table('orders')
eventbridge = boto3.client('events')

def lambda_handler(event, context):
    order_id = event['orderId']
    
    orders_table.update_item(
        Key={'orderId': order_id},
        UpdateExpression='SET #s = :status',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':status': 'CONFIRMED'}
    )
    
    eventbridge.put_events(
        Entries=[{
            'Source': 'order.service',
            'DetailType': 'ORDER_CONFIRMED',
            'Detail': json.dumps({
                'orderId': order_id,
                'customerId': event['customerId'],
                'customerEmail': event['customerEmail'],
                'total': event['total'],
                'items': event['items']
            }),
            'EventBusName': 'order-events'
        }]
    )
    
    return {**event, 'orderConfirmed': True}