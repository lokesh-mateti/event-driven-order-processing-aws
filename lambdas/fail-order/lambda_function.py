import boto3

dynamodb = boto3.resource('dynamodb')
orders_table = dynamodb.Table('orders')

def lambda_handler(event, context):
    order_id = event.get('orderId') or event.get('cause', {}).get('orderId')
    
    if order_id:
        orders_table.update_item(
            Key={'orderId': order_id},
            UpdateExpression='SET #s = :status',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':status': 'FAILED'}
        )
    
    return {**event, 'orderFailed': True}