var page = 0
var perPage = 30
$(function () {
    
    let filesTable = $("#filesTable")
    $("#pages").change(function (e) {
        e.preventDefault()
        page = $(this).val()
        refreshFilesTable(filesTable)
    })
    refreshFilesTable(filesTable)
    setInterval(function () {refreshFilesTable(filesTable)}, 3 * 1000)
})

var prevPages = 0
function doPages(pages) {
    if (pages == prevPages) {
        return
    }
    let e_pages = $("#pages")
    e_pages.change(function (e) {
        e.preventDefault()
        page = $(this).val()
        refreshFilesTable(table)
    })
    e_pages.children().remove()
    for (let index = 0; index < pages; index++) {
        const e_page = $("<option>")
        e_page.attr("value", index)
        e_page.text(index + 1)
        e_page.prop("selected", index == page)
        e_pages.append(e_page)
    }
}

function refreshFilesTable(table) {
    $.ajax({
        "method": "GET",
        "url": "/api/file/list",
        "dataType": "JSON",
        "data": {
            "page": page,
            "perPage": perPage
        }
    }).done(function (data) {
        doPages(data["pages"])
        let fileIds = data["files"].slice(page * perPage, (page * perPage) + perPage).map(file => file.uuid)
        let tableBody = table.children("tbody")
        tableBody.children().filter(function (i, e) {
            if (!fileIds.includes($(e).attr("fileId"))) {
                $(e).remove()
            }
        })
        for (let i = 0; i < data["files"].length; i++) {
            const file = data["files"][i]
            let tr = tableBody.children(`[fileId=${file.uuid}]`)
            let td_path, td_parent, td_cd
            if (tr.length <= 0) {
                tr = $("<tr>")
                tr.attr("fileId", file.uuid)
                td_path = $("<td>")
                tr.append(td_path)
                td_parent = $("<td>")
                tr.append(td_parent)
                td_cd = $("<td>")
                tr.append(td_cd)
                tableBody.append(tr)
            } else {
                td_path = tr.children().eq(0)
                td_parent = tr.children().eq(1)
                td_cd = tr.children().eq(2)
            }
            
            td_path.text(file.filePath.substr(file.parentDir.length))
            td_parent.text(file.parentDir)
            td_cd.html(function () {
                let streams_table = $("<table>")
                streams_table.addClass("table-sm")
                let stream_row
                file.streams.forEach(stream => {
                    stream_row = $("<tr>")
                    let type_cell = $("<td>")
                    type_cell.text(stream.codec_type)
                    let codec_cell = $("<td>")
                    codec_cell.text(stream.codec_long_name)
                    stream_row.append(type_cell)
                    stream_row.append(codec_cell)
                    streams_table.append(stream_row)
                });
                return streams_table
            })
        }
    })

}