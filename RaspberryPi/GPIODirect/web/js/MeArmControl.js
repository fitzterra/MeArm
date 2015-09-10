var MeArm = {
    apiBase: "/services/",

    init: function() {
        // Initiliazite all sub-systems
        this.Access.init();
        this.Arm.init();
        this.Camera.init();
    }
}

MeArm.Access = {
    apiBase: MeArm.apiBase + "control/",
    elem: null,
    stickHolder: null,

    // Update the access display based on the stickHolder property
    updateAccess: function() {
        var getBut = $("button.getstick", this.elem),
            handle = $("input.user", this.elem),
            dropBut = $("button.dropstick", this.elem),
            infoDiv = $("div.hasstick", this.elem);

        // If the stick holder is not ME, then we show the grab button and hide
        // the other
        if(this.stickHolder != "me") {
            getBut.show();
            handle.show();
            dropBut.hide();
            infoDiv.hide();
            // If it is not null, then someone else has it
            if(this.stickHolder != null) {
                infoDiv
                    .empty()
                    .append("<p>Not available:</p><p>"+this.stickHolder+"</p>")
                    .show();
            }
        } else {
            // I hold the stick, allow me to drop it.
            dropBut.show();
            getBut.hide();
            handle.hide();
            infoDiv.hide();
        }

        // Update arm control stuff
        MeArm.Arm.refreshAllJoints();
        MeArm.Arm.updateLimitEditors();

    },

    getStick: function(event) {
        var me = event.data,
            // Get the name for user wanting to grab the stick
            user = $(this).next("input.user").val()
        event.preventDefault();
        $.ajax({
            url: me.apiBase,
            context: me,
            data: {name: user},
            success: function(data, textStatus, jqXHR) {
                console.log("I have the stick: ", data);
                this.stickHolder = "me";
                this.updateAccess();
            },
            error: function(jqXHR, textStatus, errThrown) {
                console.log("Error getting stick: ", jqXHR);
                this.stickHolder = jqXHR.responseJSON.message;
                this.updateAccess();
            }
        });
    },

    dropStick: function(event) {
        var me = event.data;
        event.preventDefault();
        $.ajax({
            url: me.apiBase,
            context: me,
            method: "DELETE",
            success: function(data, textStatus, jqXHR) {
                console.log("I have dropped the stick: ", textStatus);
                this.stickHolder = null;
                this.updateAccess();
            },
            error: function(jqXHR, textStatus, errThrown) {
                this.stickHolder = null;
                this.updateAccess();
                console.log("Error dropping stick: ", jqXHR);
            }
        });
    },

    init: function() {
        this.elem = $("form fieldset.access");

        // Add a click handler to the buttons
        $("button.getstick", this.elem)
            .click(this, this.getStick)
            .show();
        $("button.dropstick", this.elem)
            .click(this, this.dropStick)
            .hide();

    }
}

MeArm.Arm = {
    apiBase: MeArm.apiBase+"arm/",

    queue: 0,

    updateJointCallBack: function(jqXHR, status) {
        var q = $("form fieldset.arm div.q");
        this.queue -= 1;
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
        var q = $("form fieldset.arm div.q");
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

    limitEditing: function(event) {
        // Check for enter or escape press
        var esc = event.keyCode == 27,
            nl = event.keyCode == 13,
            el = event.target,
            key = String.fromCharCode(event.keyCode),
            kc = event.keyCode,
            joint = el.getAttribute('data-joint');

        // Restore the element on escape
        if(esc) {
            el.blur();
            event.data.refreshJoint(joint);
        } else if(nl) {
            // Get the joint and limit names
            var limit = el.getAttribute('data-limit'),
                val = parseInt(el.innerHTML),
                dat = {},
                me = event.data;

            dat[limit] = val;
            // Prevent the default key action
            event.preventDefault();
            console.log("Gonna update: ", joint, " - ", limit, " = ", val);
            $.ajax({
                url: me.apiBase+joint,
                context: me,
                contentType: "application/json",
                data: JSON.stringify(dat),
                method: "PUT",
                success: function(data, textStatus, jqXHR) {
                    // Update the slider
                    el.blur();
                    this.refreshJoint(joint);
                },
                error: function(jqXHR, textStatus, errThrown) {
                    el.blur();
                    console.log("Error setting "+joint+" "+limit+"value: ", jqXHR.responseText);
                    this.limitError($(el), joint);
                }
            });
        } else if(kc==37 || kc==39 || kc==8 || kc==46) {
            // Do nothing
            //console.log("allowing, left, right, backspace and delete.");
        } else if(key<"0" || key>"9") {
            // All oter non numer keys we ignore
            event.preventDefault();
        }
    },

    // Called on error for updating a limit
    limitError: function(elem, joint) {
        var me = this;
        // Add the invalid class for the animation
        elem.addClass("limitInvalid");
        // Set a timer to remove it
        setTimeout(function(){
            elem.removeClass("limitInvalid");
            me.refreshJoint(joint);
        }, 3000);
    },

    refreshAllJoints: function() {
        // Set up each slider's min, max, position values and enable/disable
        var joints = ["base", "shoulder", "wrist", "grip"];
        for (var s of joints) {
            this.refreshJoint(s);
        }
    },

    refreshJoint: function(joint) {
        $.ajax({
            url: this.apiBase+joint+"/info",
            async: false,
            success: function(data, textStatus, jqXHR) {
                // The slider
                var j = $("form.controls li input[name='"+joint+"']");
                j.attr({min: data.min, value: data.pos, max: data.max})
                    .prop("disabled", false)
                    .next("output").val(data.pos + "°");
                // The min and max controls
                $("form li div."+joint+".min").text(data.min);
                $("form li div."+joint+".max").text(data.max);
            },
            error: function(jqXHR, textStatus, errThrown) {
                console.log("Error getting "+joint+" info: ", jqXHR.responseText);
            }
        });
    },

    // Method to update the limit editors based on wether we have the control
    // stick or not. Also enables and disbales the sliders
    updateLimitEditors: function() {
        // Do I have it?
        var haveIt = MeArm.Access.stickHolder == "me";

        // Make them edititable based on whether I have the stick
        $("form.controls li div.limiter").each(function() {
            $(this).prop("contenteditable", haveIt);
        });

        // Make the sliders work or not
        $("form.controls li input[type='range']").each(function() {
            $(this).prop("disabled", !haveIt);
        });

    },

    init: function() {
        // Add position updater for range sliders
        $("input[type='range']").on("input", {context: this}, this.sliderChanged);

        // Refresh joint details
        this.refreshAllJoints();
        // Add a key handler to the joint limiters for when in edit mode
        $("form li div.limiter").keydown(this, this.limitEditing);
        // And update their editable status
        this.updateLimitEditors();
    }
}

MeArm.Camera = {
    apiBase: MeArm.apiBase+"camera/",

    data: {
        elem: null,
        videoURL: null
    },

    toggle: function(event) {
        var me = event.data;
        // Add or remove?
        var stream = $("img.stream", me.data.elem);
        if(stream.length != 0) {
            // The stream element is there. Remove it and return
            stream.remove();
            return;
        }
        // It's not there, so we add it
        me.data.elem.append("<img class='stream' src='"+me.data.videoURL+"'>");
    },

    init: function() {
        // Get my DOM element
        this.data.elem = $("div.camera");
        // Get control of the toggle button
        $("button.camToggle", this.data.elem).click(this, this.toggle);
        // Get the video URL
        $.ajax({
            url: this.apiBase+'URL',
            context: this,
            success: function(data, textStatus, jqXHR) {
                console.log(data);
                this.data.videoURL = data;
            }
        })

    }
};

$(document).ready(function() {
    MeArm.init();
});
