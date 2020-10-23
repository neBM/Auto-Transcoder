$(function () {
    $("form#addDir").submit(function (e) {
        e.preventDefault()
        form = $("form#addDir")
        e_dir = form.find("#directory")
        path = e_dir.val()
        e_dir.val("")
        $.ajax({
            "method": "POST",
            "url": "/api/dirs/insert",
            "data": {
                "path": path
            },
            "dataType": "json"
        }).done(function (data) {
            console.log(data)
        })
    })
})
