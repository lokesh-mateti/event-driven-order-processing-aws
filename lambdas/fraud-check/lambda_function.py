import json
import boto3

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

def lambda_handler(event, context):
    order_id = event['orderId']
    total = float(event['total'])
    items = event['items']
    customer_id = event['customerId']
    customer_email = event.get('customerEmail', '')

    prompt = f"""You are a fraud detection system for an e-commerce platform. Analyze this order and return a JSON response only.

Order details:
- Order ID: {order_id}
- Customer ID: {customer_id}
- Customer Email: {customer_email}
- Total: ${total}
- Items: {json.dumps(items)}

Evaluate for:
1. Unusually high order total (>$500 is suspicious, >$2000 is high risk)
2. Unusually large quantity per item (>10 is suspicious, >50 is high risk)
3. Suspicious email domain (random strings, disposable email providers)
4. Price anomalies (extremely cheap prices for electronics could mean tampering)
5. Overall pattern suspicion

Respond ONLY with this JSON, no other text, no markdown backticks:
{{"fraud_score": 0.0, "risk_level": "low/medium/high", "reasons": ["reason1", "reason2"]}}"""

    response = bedrock.invoke_model(
        modelId='amazon.nova-micro-v1:0',
        contentType='application/json',
        accept='application/json',
        body=json.dumps({
            'messages': [
                {'role': 'user', 'content': [{'text': prompt}]}
            ]
        })
    )

    result = json.loads(response['body'].read())
    raw_text = result['output']['message']['content'][0]['text']

    # Clean up response
    clean_text = raw_text.strip()
    if '```' in clean_text:
        clean_text = clean_text.split('```')[1]
        if clean_text.startswith('json'):
            clean_text = clean_text[4:]
        clean_text = clean_text.strip()

    ai_response = json.loads(clean_text)

    fraud_score = ai_response['fraud_score']
    risk_level = ai_response['risk_level']
    reasons = ai_response['reasons']

    print(f"Order {order_id} — Fraud score: {fraud_score}, Risk: {risk_level}, Reasons: {reasons}")

    if fraud_score >= 0.7:
        raise Exception(f"Order {order_id} flagged as fraudulent. Score: {fraud_score}. Reasons: {', '.join(reasons)}")

    return {
        **event,
        'fraudScore': fraud_score,
        'riskLevel': risk_level,
        'fraudReasons': reasons,
        'fraudChecked': True
    }
