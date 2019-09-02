var url = window.location.protocol + "//" + window.location.host + "/";
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
});

var display = function() {
    var remain_time = side_to_move == 0? timelimit["btime"] : timelimit["wtime"];
    var byoyomi = timelimit["byoyomi"];
    var current_time = new Date().getTime();

    if (ongoing && !gameover) {
        var diff = current_time - think_start_time;
        var elapsed_seconds = Math.ceil(diff / 1000);

        if (remain_time > 0) {
            m = Math.min(remain_time, elapsed_seconds);
            remain_time -= m;
            elapsed_seconds -= m;
        }

        if (elapsed_seconds > 0) {
            byoyomi -= Math.ceil(elapsed_seconds);
        }
    }

    if (side_to_move == 0) {
        document.getElementById("btime").innerHTML = "先手残り " + remain_time + " 秒 秒読み " + byoyomi + " 秒";
        document.getElementById("wtime").innerHTML = "後手残り " + timelimit["wtime"] + " 秒 秒読み " + timelimit["byoyomi"] + " 秒";
    } else {
        document.getElementById("btime").innerHTML = "先手残り " + timelimit["btime"] + " 秒 秒読み " + timelimit["byoyomi"] + " 秒";
        document.getElementById("wtime").innerHTML = "後手残り " + remain_time + " 秒 秒読み " + byoyomi + " 秒";
    }
};

var download_csa = function() {
    socket.emit("download", function (data) {
        download(data["kif"], data["filename"], "text/plain");
    });
};

setInterval(display, 900);
