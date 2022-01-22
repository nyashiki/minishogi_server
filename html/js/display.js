var url = window.location.protocol + "//" + window.location.host + "/";
var id = window.location.search.slice(1);

var socket = io(url);

var timelimit = null;
var side_to_move = 0;
var think_start_time = null;
var ongoing = false;
var gameover = false;

socket.on("display", function(data) {
    document.getElementById("board").innerHTML = data["svg"];

    var record = document.getElementById("record");
    record.innerHTML = "";

    var ply = 0;
    data["kif"].forEach(function(item, index) {
        var option = document.createElement("option");
        option.text = item;
        record.add(option);
        ply++;
    });

    record.scrollTop = record.scrollHeight * Math.max(ply - 1, 0) / ply;

    timelimit = data["timelimit"];
    side_to_move = data["side_to_move"];

    think_start_time = new Date().getTime();

    ongoing = data["ongoing"];
    gameover = data["gameover"];

    sente = data["sente"];
    gote = data["gote"];

    document.getElementById("player").innerHTML = sente + " vs. " + gote;
    if (side_to_move == 0) {
        document.getElementById("btime").style.color = "red";
        document.getElementById("wtime").style.color = "black";
    }
    else {
        document.getElementById("btime").style.color = "black";
        document.getElementById("wtime").style.color = "red";
    }
    document.getElementById("btime").innerHTML = "先手残り " + timelimit["btime"] / 1000 + " 秒 秒読み " + timelimit["byoyomi"] / 1000 + " 秒";
    document.getElementById("wtime").innerHTML = "後手残り " + timelimit["wtime"] / 1000 + " 秒 秒読み " + timelimit["byoyomi"] / 1000 + " 秒";
    document.getElementById("info").innerHTML = gameover;
});

var display = function() {
    if (timelimit != null) {
        var remain_time = side_to_move == 0? timelimit["btime"] : timelimit["wtime"];
        var byoyomi = timelimit["byoyomi"];
        var binc = timelimit["binc"];
        var winc = timelimit["winc"];
        var current_time = new Date().getTime();

        if (ongoing && gameover == "") {
            var diff = current_time - think_start_time;
            var elapsed_ms = diff;

            if (remain_time > 0) {
                m = Math.min(remain_time, elapsed_ms);
                remain_time -= m;
                elapsed_ms -= m;
            }

            if (elapsed_ms > 0) {
                if (byoyomi > 0) {
                    byoyomi -= elapsed_ms;
                } else {
                    if (side_to_move == 0) {
                        binc -= elapsed_ms;
                    } else {
                        winc -= elapsed_ms;
                    }
                }
            }
        }

        if (side_to_move == 0) {
            document.getElementById("btime").innerHTML = "先手残り " + remain_time / 1000 + " 秒 秒読み " + byoyomi / 1000 + " 秒";
            document.getElementById("wtime").innerHTML = "後手残り " + timelimit["wtime"] / 1000 + " 秒 秒読み " + timelimit["byoyomi"] / 1000 + " 秒";
        } else {
            document.getElementById("btime").innerHTML = "先手残り " + timelimit["btime"] / 1000 + " 秒 秒読み " + timelimit["byoyomi"] / 1000 + " 秒";
            document.getElementById("wtime").innerHTML = "後手残り " + remain_time / 1000 + " 秒 秒読み " + byoyomi / 1000 + " 秒";
        }
    }
};

var download_json = function() {
    socket.emit("download", id, function (data) {
        download(data["kif"], data["filename"], "text/plain");
    });
};

setInterval(display, 900);
