-- SQLite
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