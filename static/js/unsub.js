$(document).ready(function() {

    $("#unsubscribeButton").click(function () {
        var emailId = $( this )[0].getAttribute('data-unsub');
        $.ajax({
            url: emailId,
            type: 'DELETE',
            success: function() {
                $("#unsubscribeSuccess").show();
                $("#unsubscribeButton").hide();
            }
        }).fail(function() {
            $("#unsubscribeFailure").show();
            $("#unsubscribeButton").hide();
        }).always(function() {
            setTimeout(function(){ window.location = $(location).attr('protocol') + "//" + $(location).attr('host') }, 8000);
        });
    });

    $("#unsubscribeContinueButton").click(function () {
        $("#unsubscribeFailure").hide();
        email = $("#unsubscribeEmail").val()

        if (!isEmail(email)) {
            $("#unsubscribeFailure").show();
            return;
        }

        $.get( "/unsubscribeCheck/"+email, function(data) {
            window.location = data.emailId
        }).fail(function() {
            $("#unsubscribeFailure").show();
        })



    });

});

/**
 * Uses a Reg-Ex to verify if an email is valid
 * @param {string} email string to check
 */
function isEmail(email) {
  var regex = /^([a-zA-Z0-9_.+-])+\@(([a-zA-Z0-9-])+\.)+([a-zA-Z0-9]{2,4})+$/;
  return regex.test(email);
}