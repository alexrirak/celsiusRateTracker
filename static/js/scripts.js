$(document).ready(function() {
    $('#rateTable').DataTable( {
        ajax: {
            url: '/fetchCoinData',
            dataSrc: function (json) {
                var return_data = new Array();
                for(var i=0;i< json.length; i++) {
                    rateChange = parseFloat(json[i].latest_rate) - parseFloat(json[i].prior_rate);
                    return_data.push([
                        "<img class='coinLogo' src='" + json[i].image + "' alt='" + json[i].name + "' title='" + json[i].name + "'/><span style='display:none;'>" + json[i].name + "</span>",
                        json[i].coin,
                        json[i].latest_rate,
                        json[i].prior_rate,
                        [json[i].prior_rate ? rateChange > 0 ? "<span class='badge bg-success'>" + (rateChange * 100).toFixed(2) + " % </span>" : "<span class='badge bg-danger'>" +  (rateChange * 100).toFixed(2) + " % </span>" : "<span class='badge bg-secondary'>Unknown<sup>*</sup></span>",(rateChange * 100).toFixed(2)],
                        json[i].latest_date ? new Date(json[i].latest_date).toDateString() : "<span class='badge bg-secondary'>Unknown<sup>*</sup></span>"
                    ]);
                }
                return return_data;
            }
        },
        columns: [
            { },
            { },
            {
                render: function (data, type) {
                    return type === 'sort' ? data : (APRtoAPY(parseFloat(data)) * 100).toFixed(2) + " %";
                }
            },
            {
                render: function (data, type) {
                    return data ?  type === 'sort' ? data : (APRtoAPY(parseFloat(data)) * 100).toFixed(2) + " %" : "<span class='badge bg-secondary'>Unknown<sup>*</sup></span>";
                }
            },
            {
                render: function (data, type) {
                    return type === 'sort' ? data[1] : data[0];
                }
            },
            { }
            ]
    });
} );

/**
 * Converts APR to APY with ((1+(B4/52))^(52))-1
 * @param {float} apr_rate Interest rate to convert
 */
function APRtoAPY(apr_rate) {
    return (Math.pow((1 + (apr_rate / 52)), (52))) - 1
}