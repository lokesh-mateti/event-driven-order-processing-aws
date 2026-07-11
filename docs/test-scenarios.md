# Test Scenarios

## Prerequisites
- OpenSearch + ElastiCache running (`terraform apply` in `/terraform`)
- Update `search-consumer` Lambda env var `OPENSEARCH_ENDPOINT` with Terraform output
- API URL from API Gateway → Stages → dev → Invoke URL

---

## Scenario 1 — Happy path (order confirmed)

**Expected:** Order flows through all saga steps including AI fraud check, email sent, order indexed in OpenSearch.

### 1. Place an order
```bash
curl -X POST https://YOUR_API_URL/dev/orders \
  -H "Content-Type: application/json" \
  -d '{"customerId": "CUST001", "customerEmail": "your@email.com", "items": [{"productId": "PROD001", "name": "Wireless Headphones", "price": 99, "quantity": 1}]}'
```

### 2. Verify Step Functions execution
- Step Functions → order-saga → latest execution
- All states should be green: ReserveInventory → FraudCheck → ProcessPayment → ConfirmOrder → OrderSucceeded
- Click FraudCheck state → verify fraud score is low (< 0.7) and risk level is "low"

### 3. Verify DynamoDB
- orders table → order status = `CONFIRMED`
- inventory table → PROD001 stock decremented by 1

### 4. Verify email
- Check inbox for order confirmation email from SES

### 5. Verify CloudWatch logs
- `/aws/lambda/email-consumer` → `Email sent for order...`
- `/aws/lambda/search-consumer` → `Indexed order..., status: 200`

### 6. Verify OpenSearch
- OpenSearch → Domains → order-search → Dev Tools → `GET /orders/_search`
- Confirm order document is present

---

## Scenario 2 — Insufficient stock (reserve fails)

**Expected:** Saga fails at ReserveInventory before reaching fraud check, order marked FAILED, inventory unchanged.

### 1. Check current stock
- DynamoDB → inventory table → PROD001 stock value

### 2. Place order with quantity greater than stock
```bash
curl -X POST https://YOUR_API_URL/dev/orders \
  -H "Content-Type: application/json" \
  -d '{"customerId": "CUST001", "customerEmail": "your@email.com", "items": [{"productId": "PROD001", "name": "Wireless Headphones", "price": 99, "quantity": 9999}]}'
```

### 3. Verify Step Functions execution
- ReserveInventory → orange (caught error)
- Execution goes directly to FailOrder → OrderFailed
- FraudCheck, ProcessPayment and ConfirmOrder never executed

### 4. Verify DynamoDB
- orders table → order status = `FAILED`
- inventory table → PROD001 stock unchanged

### 5. Verify no email sent
- No new email in inbox
- `/aws/lambda/email-consumer` → no new log entry

---

## Scenario 3 — Fraud detection (AI-powered)

**Expected:** Inventory reserved → AI flags order as fraudulent (score >= 0.7) → inventory released → order FAILED.

### 1. Note current PROD001 stock
- DynamoDB → inventory table → note current stock value

### 2. Place suspicious order
```bash
curl -X POST https://YOUR_API_URL/dev/orders \
  -H "Content-Type: application/json" \
  -d '{"customerId": "CUST999", "customerEmail": "xz93kd@tempmail.xyz", "items": [{"productId": "PROD001", "name": "Wireless Headphones", "price": 99, "quantity": 40}]}'
```

Fraud signals in this order:
- Suspicious email domain (`tempmail.xyz`)
- Bulk quantity (40 units)
- High total ($3960)
- Price anomaly flagged by AI

### 3. Verify Step Functions execution
- ReserveInventory → green (inventory reserved)
- FraudCheck → orange (caught error, fraud score >= 0.7)
- ReleaseInventoryAfterFraudFail → green (inventory released)
- FailOrder → green
- OrderFailed → red

### 4. Verify fraud reasons in Step Functions
- Click FraudCheck state → view error cause
- Shows fraud score, risk level, and AI-generated reasons

### 5. Verify compensation worked
- inventory table → PROD001 stock restored to original value
- orders table → order status = `FAILED`

### 6. Verify no email sent
- No confirmation email in inbox (EventBridge only fires on ORDER_CONFIRMED)

---

## Scenario 4 — Payment failure with compensation

**Expected:** Inventory reserved → fraud check passes → payment fails → inventory released → order FAILED.

### 1. Note current PROD001 stock
- DynamoDB → inventory table → note current stock value

### 2. Force payment failure
- Lambda → process-payment → change this line:
```python
if random.random() < 0.1:
```
to:
```python
if True:
```
- Deploy

### 3. Place an order
```bash
curl -X POST https://YOUR_API_URL/dev/orders \
  -H "Content-Type: application/json" \
  -d '{"customerId": "CUST001", "customerEmail": "your@email.com", "items": [{"productId": "PROD001", "name": "Wireless Headphones", "price": 99, "quantity": 1}]}'
```

### 4. Verify Step Functions execution
- ReserveInventory → green (stock decremented)
- FraudCheck → green (fraud score low, order looks legitimate)
- ProcessPayment → orange (caught error)
- ReleaseInventoryAfterPaymentFail → green (stock restored)
- FailOrder → green
- OrderFailed → red

### 5. Verify compensation worked
- inventory table → PROD001 stock = same value as step 1 (restored)
- orders table → order status = `FAILED`

### 6. Restore process-payment Lambda
- Change back to `if random.random() < 0.1:`
- Deploy

---

## Scenario 5 — ElastiCache cache hit vs miss

**Expected:** First product lookup hits DynamoDB (cache miss), subsequent lookups served from Redis (cache hit).

### 1. Place first order
Run any curl command from scenario 1.

### 2. Check CloudWatch
- `/aws/lambda/order-processor` → `Cache miss for PROD001, fetched from DynamoDB`

### 3. Place second order immediately
Run the same curl command again.

### 4. Check CloudWatch
- `/aws/lambda/order-processor` → `Cache hit for PROD001`

---

## Teardown

Run after each session to avoid charges (~$1-2/day for OpenSearch + ElastiCache):

```bash
cd terraform
terraform destroy
```

Type `yes`. This destroys only OpenSearch and ElastiCache.
Everything else (Lambda, DynamoDB, Step Functions, SQS, EventBridge, SES) stays running at zero idle cost.
