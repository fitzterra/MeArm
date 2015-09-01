var arm = {
    apiBase: "/services/",

    queue: 0,

    updateJointCallBack: function(jqXHR, status) {
        var q = $("form fieldset div.q");
        this.queue -= 1;
        console.log(this.queue);
        q.text(this.queue);
        if(this.queue==0) {
            q.toggle();
        }
        // If not success, log it.
        if (status !== "success") {
            console.log("Ajax failed: ", jqXHR.responseText);
        }
    },
    
    updateJoint: function(joint, pos) {
        // Only allow one request to the server at a time
        if(this.queue>0) {
            return;
        }
        // The queue indicator
        var q = $("form fieldset div.q");
        // Increment the queue counter and update the indicator
        this.queue += 1;
        q.text(this.queue);
        // Toggle the queue indicator on if there is any requests on the queue
        if(this.queue==1) {
            q.toggle();
        }

        // Set up the ajax options for the call to the REST endpoint to update
        // the joint angle
        var opts = {
            url: this.apiBase+joint,
            complete: this.updateJointCallBack,
            context: this,
            contentType: "application/json",
            data: JSON.stringify({pos: pos}),
            method: "PUT"
        };
        // Call the REST endpoint to set the joint angle
        $.ajax(opts);
        //window.setTimeout($.proxy(this.updateJointCallBack, this), 400);
    },

    sliderChanged: function(event) {
        var context = event.data.context;

        // Update the slider current position output indicator
        $(this).next("output").val(this.value + "°");
        context.updateJoint(this.name, parseInt(this.value));
    },

    init: function() {
        console.log("here we go...");
        // Add position updater for range sliders
        $("input[type='range']").on("input", {context: this}, this.sliderChanged);

        // Set up each slider's min and max values
        var joints = ["base", "shoulder", "wrist", "grip"];
        //var joints = ["base"];
        for (var s of joints) {
            $.ajax({
                url: this.apiBase+s+"/info",
                async: false,
                success: function(data, textStatus, jqXHR) {
                    console.log(s, " : ", data);
                    var j = $("form li input[name='"+s+"']");
                    j.attr({min: data.min, value: data.pos, max: data.max})
                        .prop("disabled", false)
                        .next("output").val(data.pos + "°");;
                },
                error: function(jqXHR, textStatus, errThrown) {
                    console.log("Error getting "+s+" info: ", jqXHR.responseText);
                }
            });
        }
    }
}

$(document).ready(function() {
    arm.init();
});
