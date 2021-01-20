$(function () {
    let form = $("#newDirForm")

    $.ajax({
        "method": "GET",
        "url": "/api/server/codecs",
        "dataType": "JSON"
    }).done(function (data) {
        let video_select = form.find("#vencoder")
        let audio_select = form.find("#aencoder")
        let subtitle_select = form.find("#sencoder")
        data["codecs"].forEach(codec => {
            if (codec.encoder != true) return;
            let option_element = $("<option>")
            option_element.text(codec.name)
            option_element.attr("value", codec.id)
            switch (codec.type) {
                case "V":
                    video_select.append(option_element)
                    break;
                case "A":
                    audio_select.append(option_element)
                    break;
                case "S":
                    subtitle_select.append(option_element)
                    break;
                default:
                    break;
            }
        });
    })

    form.submit(function (e) {
        e.preventDefault()
        $.ajax({
            "method": "POST",
            "url": "/api/dir/add",
            "dataType": "json",
            "data": {
                "path": form.find("#dir").val(),
                "aencoder": form.find("#aencoder").val(),
                "vencoder": form.find("#vencoder").val(),
                "sencoder": form.find("#sencoder").val()
            }
        }).done(function (data) {
            form.trigger("reset")
        })
    })
})