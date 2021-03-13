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

});