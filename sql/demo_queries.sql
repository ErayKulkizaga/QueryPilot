-- 1. Potential missing index
SELECT id, email, full_name
FROM customers
WHERE email = 'demo@example.com';

-- 2. Join behavior
SELECT c.email, o.created_at, o.total_amount
FROM customers AS c
JOIN orders AS o ON o.customer_id = c.id
WHERE c.id BETWEEN 100 AND 120
ORDER BY o.created_at DESC;

-- 3. Aggregation and sort behavior
SELECT customer_id, sum(total_amount) AS lifetime_value
FROM orders
GROUP BY customer_id
ORDER BY lifetime_value DESC;

-- 4. Healthy primary-key lookup
SELECT id, email, full_name
FROM customers
WHERE id = 17;

