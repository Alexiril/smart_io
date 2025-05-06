function set_map_height() {
    const image = new Image()
    image.src = "/map-background"
    image.onload = function () {
        $(".map").css("height", `${image.height}px`)
    }
}

function make_devices_draggable() {
    const device = $(".device-on-map")
    device.on("mousedown", function (e) {
        draggable.startMoving(this, "map", e)
    })
    device.on("mouseup", function () {
        draggable.stopMoving("map")
        const device_id = $(this).data("device-id");
        $.ajax({
            url: "/set-device-position",
            type: "POST",
            data: JSON.stringify({
                device_id: device_id,
                coord_x: Math.round(this.style.left.replace('px', '')),
                coord_y: Math.round(this.style.top.replace('px', '')),
            }),
            contentType: "application/json",
            success: function (response) {
                console.log(response);
            },
            error: function (xhr, status, error) {
                console.error("Error moving device:", error)
            }
        })
    })
    device.on("contextmenu", function (e) {
        $(this).children(".device-short-settings").show()
        e.preventDefault()
    })
}

function lightness_to_text(lightness) {
    if (lightness < 40) {
        return "Полная темнота"
    }
    if (lightness < 800) {
        return "Темно"
    }
    if (lightness < 2000) {
        return "Средняя освещенность"
    }
    if (lightness < 3200) {
        return "Светло"
    }
    return "Очень светло"
}

function setting_data() {
    if (!$("#auto-update").prop('checked')) {
        return;
    }
    $.ajax({
        url: "/devices-data",
        type: "GET",
        dataType: "json",
        success: function (response) {
            const data = response
            for (const [device_id, value] of Object.entries(data)) {
                const line = $(`#device-${device_id}`);
                if (line.length == 0) {
                    continue;
                }
                const is_working = value.result == "success"
                const status_field = $(`.status-${device_id}`)
                status_field.removeClass("device-error device-okay")
                if (is_working) {
                    status_field.addClass("device-okay")
                    status_field.text("Работает")

                    $(`.lightness-${device_id}`).text(lightness_to_text(value.lightness))
                    $(`#relay-${device_id}`).text(value.relay_state)
                    $(`#led-${device_id}`).text(Math.round(value.led_state / 2.55))
                    $(`#led-range-${device_id}`).val(Math.round(value.led_state / 2.55))

                    $(`#error-${device_id}`).text("Отсутствует")
                } else {
                    status_field.addClass("device-error")
                    status_field.text("Не работает")

                    $(`#error-${device_id}`).text(value.error)
                }
            }
        },
        error: function (xhr, status, error) {
            console.error("Error fetching data from server:", error)
            return
        }
    })
}

$(function () {
    set_map_height()
    make_devices_draggable()
    setInterval(function () {
        setting_data()
    }, 3000)
    $(".show-additional-data").on("click", function () {
        const device_id = $(this).data("device-id");
        $(`#device-${device_id}-additional-info`).toggle()
    })
    $(".remove-device").on("click", function () {
        const device_id = $(this).data("device-id");
        $.ajax({
            url: "/remove-device",
            type: "POST",
            data: JSON.stringify({
                device_id: device_id,
            }),
            contentType: "application/json",
            success: function (response) {
                console.log(response);
                $(`#device-${device_id}`).remove()
                $(`#devices-amount`).text(parseInt($(`#devices-amount`).text()) - 1)
            },
            error: function (xhr, status, error) {
                console.error("Error removing device:", error)
            }
        })
    })
    $(".toggle-relay").on("click", function () {
        const device_id = $(this).data("device-id");
        $.ajax({
            url: "/toggle-relay",
            type: "POST",
            data: JSON.stringify({
                device_id: device_id,
            }),
            contentType: "application/json",
            success: function (response) {
                console.log(response);
            },
            error: function (xhr, status, error) {
                console.error("Error toggling relay:", error)
            }
        })
    })
    $(".set-led").on("click", function () {
        const device_id = $(this).data("device-id");
        const led_state = prompt("Enter LED brightness (from 0 to 100):", "50");
        $.ajax({
            url: "/set-led",
            type: "POST",
            data: JSON.stringify({
                device_id: device_id,
                brightness: `${Math.round(led_state * 2.55)}`, // Convert to 0-255 range
            }),
            contentType: "application/json",
            success: function (response) {
                console.log(response)
            },
            error: function (xhr, status, error) {
                console.error("Error setting LED state:", error)
            }
        })
    })
    $(".set-led-range").on("change", function () {
        const device_id = $(this).data("device-id");
        const led_state = $(this).val();
        $.ajax({
            url: "/set-led",
            type: "POST",
            data: JSON.stringify({
                device_id: device_id,
                brightness: `${Math.round(led_state * 2.55)}`, // Convert to 0-255 range
            }),
            contentType: "application/json",
            success: function (response) {
                console.log(response)
            },
            error: function (xhr, status, error) {
                console.error("Error setting LED state:", error)
            }
        })
    })
    $(".close-short-settings").on("click", function () {
        $(this).parents(".device-short-settings").hide()
    })
    $(".remove-event").on("click", function () {
        const event_id = $(this).data("event-id");
        $.ajax({
            url: "/remove-event",
            type: "POST",
            data: JSON.stringify({
                event_id: event_id,
            }),
            contentType: "application/json",
            success: function (response) {
                console.log(response);
                $(`#event-${event_id}`).remove()
                $(`#events-amount`).text(parseInt($(`#events-amount`).text()) - 1)
            },
            error: function (xhr, status, error) {
                console.error("Error removing event:", error)
            }
        })
    })
})