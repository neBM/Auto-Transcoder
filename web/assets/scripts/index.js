$(function () {
    refreshWorkersTable($("#workersTable"))
    setInterval(function () {refreshWorkersTable($("#workersTable"))}, 1000)
})
function refreshWorkersTable(table) {
    $.ajax({
        "method": "GET",
        "url": "/api/worker/list",
        "dataType": "JSON",
        "data": {
            "part": ["id", "status", "processingDetails", "fileDetails", "contentDetails"].join(",")
        }
    }).done(function (data) {
        let workerIds = data["workers"].map(worker => worker["id"])
        let workerRows = table.children("tbody").children("tr")
        workerRows.filter(function (i, e) {
            if (!workerIds.includes($(e).attr("workerId"))) {
                $(e).remove()
            }
        })
        Object.keys(data["workers"]).forEach(workerId => {
            let worker = data["workers"][workerId]
            var row
            if (workerRows.filter(`[workerId=${worker["id"]}]`).length <= 0) {
                row = $("<tr>")
                table.children("tbody").append(row)
                row.attr("workerId", worker["id"])
                row.append($("<th>").attr("scope", "row").text(worker.status.type))
                row.append($("<td>"))
                row.append($("<td>"))
                row.append($("<td>"))
            } else {
                row = workerRows.filter(`[workerId=${worker.id}]`)
            }

            row.children().eq(1).html(function () {
                let e_state = $("<span>")
                e_state.attr("data-content", worker.fileDetails == null ? "N/A" : worker.fileDetails.filePath)
                e_state.text(worker.status.state)
                switch (worker.status.state) {
                    case "RUNNING":
                        e_state.css("color", "green")
                        break;
                    case "FAILED":
                        e_state.css("color", "red")
                        break;
                    default:
                        break;
                }
                return e_state
            })

            if (worker.fileDetails == null) {
                row.children().eq(2).html(document.createTextNode("N/A"))
            } else {
                let pathParts = worker.fileDetails.filePath.split("/")
                let e_file = document.createTextNode("").innerHTML = pathParts[pathParts.length - 1]
                row.children().eq(2).html(e_file)
            }

            if (worker["processingDetails"] == null) {
                row.children().eq(3).html(document.createTextNode("N/A"))
            } else {
                var e_progress = row.children().eq(3).children(".progress")
                var e_progressBar
                if (e_progress.length <= 0) {
                    row.children().eq(3).html(function () {
                        e_progress = $("<div>")
                        e_progress.addClass("progress")
                        e_progressBar = $("<div>")
                        e_progressBar.addClass("progress-bar")
                        e_progressBar.attr("role", "progressbar")
                        e_progressBar.attr("aria-valuemin", "0")
                        e_progressBar.attr("aria-valuemax", "100")
                        e_progress.append(e_progressBar)
                        return e_progress
                    })
                } else {
                    e_progressBar = e_progress.children(".progress-bar")
                }
                let percent = (worker["processingDetails"]["out_time_us"] * 1e-6 * 100) / worker["contentDetails"]["format"]["duration"]
                e_progressBar.attr("aria-valuenow", percent)
                e_progressBar.css("width", `${percent}%`)
            }

        });
    })
}