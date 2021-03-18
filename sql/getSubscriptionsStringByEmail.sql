SELECT GROUP_CONCAT(coin SEPARATOR ',') AS 'subs'
FROM coinAlerts
WHERE email = "%s"
GROUP BY email;