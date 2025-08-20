SELECT 
    e.id, 
    e.stripe_event_id, 
    e.type, 
    e.payment_id, 
    e.received_at, 
    p.order_id, 
    p.amount_received
FROM payment_events AS e 
LEFT JOIN payments AS p 
    ON e.payment_id=p.id
ORDER BY received_at DESC;



INSERT INTO orders 
    (id, currency, amount_due, status, created_at, updated_at)
VALUES 
    ('web0016737', 'usd', 5500, 'AWAITING_PAYMENT', datetime('now'), datetime('now'));