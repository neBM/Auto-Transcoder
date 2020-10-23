$(function() {

    workers = []

    setInterval(updateWorkers, 1000)

    function updateWorkers() {
        $.ajax({
            "method": "GET",
            "url": "/api/workers/list",
            "dataType": "JSON"
        }).done(function(data) {
            workers = Object.keys(data)
            e_workers = []
            prevWorkers = $("[dataDisplay=workers]").children()
            for (workerId in data) {
                const worker = data[workerId];
                row = $("[dataDisplay=workers]").children(`[workerId=${workerId}]`)
                if (row.length <= 0) {
                    row = $("<tr>").attr("workerType", worker["type"]).attr("workerId", workerId).addClass("worker").append(
                        $("<td>").addClass("item")
                        .append(
                            $("<span>").attr("dataDisplay", "workerType")
                        ).append(
                            $("<span>").attr("dataDisplay", "state").addClass("value")
                        ).append($("<span>").attr("dataDisplay", "path").addClass("key")).append(
                            $("<div>").attr("dataDisplay", "progress").addClass("progress")
                        )
                    )
                    $("[dataDisplay=workers]").append(row)
                }
                row.find(".progress").css("width", `${(worker["wu"]/worker["totalWu"]) * 100}%`)
                row.find("[dataDisplay=state]").attr("state", worker["state"])
                row.find("[dataDisplay=workerType]").text(worker["type"])
            }
            prevWorkers.each(function (prevWorkerId, prevWorker) {
                prevWorker = prevWorkers[prevWorkerId]
                workerId = $(prevWorker).attr("workerId")
                if (!workers.includes(workerId)) {
                    prevWorker.remove()
                }
            })

        })
    }
    updateWorkers()

})
