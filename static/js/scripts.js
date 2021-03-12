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
                        json[i].latest_date ? new Date(json[i].latest_date).toDateString() : "<span class='badge bg-secondary'>Unknown<sup>*</sup></span>",
                        "<button type='button' class='btn btn-outline-secondary btn-lg' data-bs-toggle='modal' data-bs-target='#signUpModal' data-bs-coin='" + json[i].coin + "'><i class='bi bi-alarm'></i></button>"
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
            { },
            { }
            ]
    });
    $(".form-check-input").change(function(){
        if ($( this ).is(":checked")) {
            className = "#img-" + $( this )[0].id
            $(className).parent().removeClass("grayOut")
        } else {
            className = "#img-" + $( this )[0].id
            $(className).parent().addClass("grayOut")
        }
    })
    $("#signUpModalSubmit").click(function(){

        $( this )[0].innerHTML = "<i class='bi bi-hourglass'></i>"
        $( "[data-bs-dismiss='modal']" ).prop("disabled",true);
        $("#signupEmailAlert").hide();
        $("#signupCoinAlert").hide();

        enableButtons = function() {
            $( "[data-bs-dismiss='modal']" ).prop("disabled",false);
            $("#signUpModalSubmit")[0].innerHTML = "Submit";
        }

        email = $("#signupEmail").val()
        if (!isEmail(email)) {
            $("#signupEmailAlert").show();
            enableButtons();
            return;
        }
        selectedCoins = []
        $(".form-check-input").each(function(){
            if($( this ).is(":checked")) {
                selectedCoins.push($( this )[0].id);
            }
        })
        if (selectedCoins.length == 0) {
            $("#signupCoinAlert").show();
            enableButtons();
            return;
        }
        request = {
            "email":email,
            "coins":selectedCoins
        }

        $.post({
            url:"/registerEmail",
            data: JSON.stringify(request),
            headers: { 'Content-Type': 'application/json' }},
            function(){
                $("#signupSuccess").show();
                $("#signupSuccess").delay(10000).fadeOut();
        }).fail(function() {
            $("#signupFailure").show();
            $("#signupFailure").delay(10000).fadeOut();
        }).always(function() {
            $(".form-check-input").each(function(){
                $( this ).prop('checked', false);
                className = "#img-" + $( this )[0].id;
                $(className).parent().addClass("grayOut");
            })
            $("#signupEmail").val("");
            enableButtons();
            bootstrap.Modal.getInstance(document.getElementById('signUpModal')).hide();
        });
    })

    var exampleModal = document.getElementById('signUpModal');
    exampleModal.addEventListener('show.bs.modal', function (event) {

      var coin = "#" + event.relatedTarget.getAttribute('data-bs-coin');

      $(coin).trigger('click');
    })
} );

/**
 * Converts APR to APY with ((1+(B4/52))^(52))-1
 * @param {float} apr_rate Interest rate to convert
 */
function APRtoAPY(apr_rate) {
    return (Math.pow((1 + (apr_rate / 52)), (52))) - 1
}

/**
 * Uses a Reg-Ex to verify if an email is valid
 * @param {string} email string to check
 */
function isEmail(email) {
  var regex = /^([a-zA-Z0-9_.+-])+\@(([a-zA-Z0-9-])+\.)+([a-zA-Z0-9]{2,4})+$/;
  return regex.test(email);
}