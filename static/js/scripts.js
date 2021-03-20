$(document).ready(function() {
    var rateTable = $('#rateTable').DataTable( {
        ajax: {
            url: '/fetchCoinData',
            dataSrc: function (json) {
                var return_data = new Array();
                for(var i=0;i< json.length; i++) {
                    convertToCel = $("#celSlider").is(":checked");
                    rateChange = convertToCel
                        ? APRtoAPY(inKindToCel(parseFloat(json[i].latest_rate))) - APRtoAPY(inKindToCel(parseFloat(json[i].prior_rate)))
                        : APRtoAPY(parseFloat(json[i].latest_rate)) - APRtoAPY(parseFloat(json[i].prior_rate));
                    return_data.push([
                        "<img class='coinLogo' src='" + json[i].image + "' alt='" + json[i].name + "' title='" + json[i].name + "'/><span style='display:none;'>" + json[i].name + "</span>",
                        json[i].coin,
                        convertToCel ? APRtoAPY(inKindToCel(parseFloat(json[i].latest_rate))) : APRtoAPY(parseFloat(json[i].latest_rate)),
                        convertToCel ? APRtoAPY(inKindToCel(parseFloat(json[i].prior_rate))) : APRtoAPY(parseFloat(json[i].prior_rate)),
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
                    return type === 'sort' ? data : (parseFloat(data) * 100).toFixed(2) + " %";
                }
            },
            {
                render: function (data, type) {
                    return data ?  type === 'sort' ? data : (parseFloat(data) * 100).toFixed(2) + " %" : "<span class='badge bg-secondary'>Unknown<sup>*</sup></span>";
                }
            },
            {
                render: function (data, type) {
                    return type === 'sort' ? data[1] : data[0];
                }
            },
            { },
            { }
            ],
        initComplete: function(){
                $("#rateTable_filter").parent()
                    .html("<div class=\"row\">" +
                            "<div class=\"col-sm-12 col-md-6\">" +
                                "<input type=\"checkbox\" data-onlabel=\"CEL Rate\" data-offlabel=\"In-Kind Rate\" data-onstyle=\"outline-warning\" data-offstyle=\"outline-secondary\" data-width=\"175\" data-size=\"sm\" id='celSlider'>" +
                            "</div>" +
                            "<div class=\"col-sm-12 col-md-6\">" +
                            $("#rateTable_filter").parent().html() +
                            "</div>" +
                        "</div>");
                 document.getElementById('celSlider').switchButton();
                 $("#celSlider").change(function(){
                    rateTable.ajax.reload();
                });
        }
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
        $("#dots").show();

        enableButtons = function() {
            $( "[data-bs-dismiss='modal']" ).prop("disabled",false);
            $("#signUpModalSubmit")[0].innerHTML = "Submit";
            $("#dots").hide();
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

    var signupModal = document.getElementById('signUpModal');
    signupModal.addEventListener('show.bs.modal', function (event) {

      var coin = "#" + event.relatedTarget.getAttribute('data-bs-coin');

      if (!$(coin).is(":checked")) {
          $(coin).trigger('click');
      }
    })

    $("[data-coin]").click(function(){
        var coin = "#" + $( this )[0].getAttribute('data-coin');
        $(coin).trigger('click');
    });

    $('#signUpModal').keypress(function (e) {
     var key = e.which;
     if(key == 13)  // the enter key code
      {
        $("#signUpModalSubmit").click();
      }
    });
} );

/**
 * Converts APR to APY with ((1+(B4/52))^(52))-1
 * @param {float} apr_rate Interest rate to convert
 */
function APRtoAPY(apr_rate) {
    return (Math.pow((1 + (apr_rate / 52)), (52))) - 1
}

/**
 * Converts in-kind to cel rate with R*1.3
 * @param {float} apr_rate Interest rate to convert
 */
function inKindToCel(apr_rate) {
    return apr_rate * 1.3
}

/**
 * Uses a Reg-Ex to verify if an email is valid
 * @param {string} email string to check
 */
function isEmail(email) {
  var regex = /^([a-zA-Z0-9_.+-])+\@(([a-zA-Z0-9-])+\.)+([a-zA-Z0-9]{2,4})+$/;
  return regex.test(email);
}