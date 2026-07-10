import boto3

dynamodb = boto3.resource('dynamodb')
inventory_table = dynamodb.Table('inventory')

def lambda_handler(event, context):
    items = event.get('items') or event.get('cause', {}).get('items', [])
    
    for item in items:
        inventory_table.update_item(
            Key={'productId': item['productId']},
            UpdateExpression='SET stock = stock + :qty',
            ExpressionAttributeValues={':qty': item['quantity']}
        )
    
    return {**event, 'inventoryReleased': True}
