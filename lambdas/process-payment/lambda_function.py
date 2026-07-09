import json
import random

def lambda_handler(event, context):
    order_id = event['orderId']
    total = float(event['total'])
    
    # Simulate payment processing (90% success rate)
    if random.random() < 0.1:
        raise Exception(f'Payment failed for order {order_id}')
    
    return {**event, 'paymentProcessed': True, 'paymentId': f'PAY-{order_id[:8]}'}