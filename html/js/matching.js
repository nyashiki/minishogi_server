var get_matching = function() {
    var url = window.location.protocol + "//" + window.location.host + "/";
    var socket = io(url);

    socket.emit("matching", function (data) {
        var pending = document.getElementById("pending");
        var ongoing = document.getElementById("ongoing");
        var finished = document.getElementById("finished");

        data.forEach(function(element) {
            var target = null;

            if (element["ongoing"] == true) {
                target = document.getElementById("ongoing");
            } else {
                if (element["gameover"] == "") {
                    target = document.getElementById("pending");
                } else {
                    target = document.getElementById("finished");
                }
            }

            var list = document.createElement("li");
            list.innerHTML = "<a href=" + element["link"] + ">" + element["player1"] + " - " + element["player2"] + "</a>";
            if (element["gameover"])
                list.innerHTML += " [" + element["gameover"] + "]";
            target.appendChild(list);
        });
    });

    socket.emit("tournament", function (data) {
        data.forEach(function(element) {
            var list = document.createElement("li");
            list.innerHTML = "<a style='white-space: pre;'>" + element["player1"] + " vs. " + element["player2"] + "<br>"
                                + "win " + element["player1_win"] + " : " + element["player2_win"] + "<br>" 
                                + "results " + element["result"] + "</a>";
            document.getElementById("tournament").appendChild(list);
        });
    });
};
