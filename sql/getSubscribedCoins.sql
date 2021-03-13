SELECT CM.* FROM coinAlerts AS CA
LEFT JOIN coinMetaData AS CM ON CA.coin = CM.symbol
WHERE CA.active = 1 and CA.email  = "%s"