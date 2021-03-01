SELECT
 cr.coin,
 (SELECT MAX(insert_datetime) FROM coinRates crdt WHERE crdt.coin = cr.coin LIMIT 1) as latest_date,
 (SELECT rate FROM coinRates crr WHERE crr.coin = cr.coin AND crr.insert_datetime = latest_date LIMIT 1) as latest_rate,
 (SELECT MAX(insert_datetime) FROM coinRates crdt2 WHERE crdt2.coin = cr.coin AND crdt2.insert_datetime != latest_date LIMIT 1) as prior_date,
 (SELECT rate FROM coinRates crr2 WHERE crr2.coin = cr.coin AND crr2.insert_datetime = prior_date LIMIT 1) as prior_rate,
 cm.name, cm.image
FROM coinRates cr
left join coinMetaData cm on cr.coin = cm.symbol
GROUP BY cr.coin