$(function() {
    $("input#device_name").on("change", function() {
        $("#device_name_field").text(this.value)
    })
    $("input#device_ip").on("change", function() {
        $("#device_ip_field").text(this.value)
    })
    $("select#device_role").on("change", function() {
        const role = $(this).children("option:selected")[0].value
        const image_holder = $("#device_role_field")
        image_holder.removeClass("fa-lightbulb fa-shuffle fa-chart-simple fa-arrow-up-right-dots");
        switch (role) {
            case "mixed":
                image_holder.addClass("fa-lightbulb")
                break
            case "led":
                image_holder.addClass("fa-chart-simple")
                break
            case "relay":
                image_holder.addClass("fa-shuffle")
                break
            case "sensor":
                image_holder.addClass("fa-arrow-up-right-dots")
                break
            default:
                break
        }
    })
    $("#add-device-button").on("click", function() {    
        const device_name = $("input#device_name").val()
        const device_ip = $("input#device_ip").val()
        const device_role = $("select#device_role").children("option:selected")[0].value
        $.ajax({
            type: "POST",
            url: "/add-device",
            data: {
                device_name: device_name,
                device_ip: device_ip,
                device_role: device_role,
            },
            success: function(response) {
                if (response.status == "success") {
                    window.location.href = "/"
                } else {
                    if (response.message) {
                        alert(response.message)
                    } else {
                        alert("Error adding device")
                    }
                }
            },
            error: function() {
                alert("Error adding device")
            }
        })
    })
})