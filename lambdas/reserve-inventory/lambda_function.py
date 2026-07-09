import json
import boto3
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource('dynamodb')
inventory_table = dynamodb.Table('inventory')

def lambda_handler(event, context):
    order_id = event['orderId']
    items = event['items']
    
    for item in items:
        product_id = item['productId']
        quantity = item['quantity']
        
        try:
            inventory_table.update_item(
                Key={'productId': product_id},
                UpdateExpression='SET stock = stock - :qty',
                ConditionExpression=Attr('stock').gte(quantity),
                ExpressionAttributeValues={':qty': quantity}
            )
        except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
            raise Exception(f'Insufficient stock for {product_id}')
    
    return {**event, 'inventoryReserved': True}