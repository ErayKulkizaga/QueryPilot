SELECT setseed(0.42);

INSERT INTO customers (email, full_name, region, created_at)
SELECT
    CASE WHEN number = 17 THEN 'demo@example.com' ELSE md5(number::text) || '@example.test' END,
    'Demo Customer ' || number,
    (ARRAY['TR', 'DE', 'GB', 'US'])[1 + floor(random() * 4)::int],
    now() - random() * interval '730 days'
FROM generate_series(1, 25000) AS number;

INSERT INTO orders (customer_id, status, total_amount, created_at)
SELECT
    1 + floor(random() * 25000)::bigint,
    (ARRAY['new', 'paid', 'shipped', 'cancelled'])[1 + floor(random() * 4)::int],
    round((10 + random() * 990)::numeric, 2),
    now() - random() * interval '365 days'
FROM generate_series(1, 120000);

INSERT INTO support_events (customer_id, event_type, payload, created_at)
SELECT
    1 + floor(random() * 25000)::bigint,
    (ARRAY['ticket_opened', 'reply_sent', 'ticket_closed'])[1 + floor(random() * 3)::int],
    jsonb_build_object('channel', (ARRAY['email', 'chat', 'phone'])[1 + floor(random() * 3)::int]),
    now() - random() * interval '180 days'
FROM generate_series(1, 60000);

ANALYZE customers;
ANALYZE orders;
ANALYZE support_events;

