var get_matching = function() {
    var url = window.location.protocol + "//" + window.location.host + "/";
    var socket = io(url);

    socket.emit("matching", function (data) {
        var ongoing = document.getElementById("ongoing");
        var finished = document.getElementById("finished");

        data.forEach(function(element) {
            var target = document.getElementById(element["gameover"] === ""? "ongoing" : "finished");
            var list = document.createElement("li");
            list.innerHTML = "<a href=" + element["link"] + ">" + element["player1"] + " - " + element["player2"] + "</a>";
            target.appendChild(list);
        });
    });
};
