SELECT CM.* FROM coinAlerts AS CA
LEFT JOIN coinMetaData AS CM ON CA.coin = CM.symbol
WHERE CA.email  = "%s"