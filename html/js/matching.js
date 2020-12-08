var url = window.location.protocol + '//' + window.location.host + '/';
var socket = io(url);
var names = ['FirstProgramSelect','SecondProgramSelect']

var update = function() {
    socket.emit('update', function(game_data, client_data) {
        game_data.forEach(function(game) {
            var target = null;
            if (game['ongoing'] == true)
                target = document.getElementById('ongoing')
            else if(game['gameover'] != "")
                target = document.getElementById('finished')
            else
                target = document.getElementById('exception')
            var list = document.createElement('li');
            list.innerHTML = '<a href=' + game['link'] + '>' + game['player1'] + ' - ' + game['player2'] + '</a>';
            target.appendChild(list);
        });
        client_data.forEach(function(client){
            names.forEach(function(name) {
                var select = document.getElementById(name);
                var option = document.createElement('option');
                option.value = client['id'];
                option.text = client['name'];
                select.appendChild(option);
            });
        });
    });
};

var matching = function() {
    id = [];
    names.forEach(function(name) {
        var select = document.getElementById(name);
        id.push(select.value);
    });
    if (id[0] != id[1]) {
        socket.emit('matching', id);
        // update();
    }
};
