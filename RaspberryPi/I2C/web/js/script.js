/**
 * MeArm controller
 **/
var MeArm = {
    arm: {
        base: null,
        shoulder: null,
        wrist: null,
        grip: null
    },

    init: function() {
        console.log("In init...");
        ctl = $("div.control");
        Object.getOwnPropertyNames(this.arm)
            .forEach(function(joint, idx, array) {
                console.log(joint, " : ", MeArm.arm[join]);
            });
    }
};

$(document).ready(function() {

    /*
 $("#generate-string").click(function(e) {
   $.post("/services", {"length": $("input[name='length']").val()})
    .done(function(string) {
       $("#the-string").show();
       $("#the-string input").val(string);
    });
   e.preventDefault();
 });

 $("#replace-string").click(function(e) {
   $.ajax({
      type: "PUT",
      url: "/services",
      data: {"another_string": $("#the-string input").val()}
   })
   .done(function() {
      alert("Replaced!");
   });
   e.preventDefault();
 });

 $("#delete-string").click(function(e) {
   $.ajax({
      type: "DELETE",
      url: "/services"
   })
   .done(function() {
      $("#the-string").hide();
   });
   e.preventDefault();
 });
 */

    // Set up the controller
    MeArm.init();

});
