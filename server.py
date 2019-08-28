import eventlet
import minishogilib
import socketio

class Game:
    def __init__(self):
        self.position = None

        # Time limit
        self.timelimit = [0 for _ in range(2)]
        self.byoyomi = 0

        # Clients
        self.clients = []

class Client:
    def __init__(self):
        self.sid = None

def main(port=8000):
    game = Game()

    sio = socketio.Server()

    def ask_nextmove(sid):
        sio.emit('position', '<SFEN_POSITION>', room=sid)
        sio.emit('go', 'go btime <BTIME> wtime <WTIME> byoyomi <BYOYOMI>', room=sid)

    @sio.on('usi')
    def usi(sid, data):
        if len(game.clients) >= 2:
            sio.emit('error', 'The game has already started.', room=sid)
            return

        if not 'name' in data:
            sio.emit('error', 'You sent a request but name field was None.', room=sid)
            return

        if not 'author' in data:
            sio.emit('error', 'You sent a request but author field was None.', room=sid)
            return

        client = Client()
        client.sid = sid

        game.clients.append(client)

        sio.emit('info', 'Correctly accepted.', room=sid)

        if len(game.clients) == 2:
            # Two players sit down, so a game is starting
            # Initialization
            game.position = minishogilib.Position()
            game.position.set_start_position()

            # Ask a first move
            ask_nextmove(game.clients[0].sid)

    @sio.on('bestmove')
    def bestmove(sid, data):
        color = position.get_side_to_move()

        # An unknown player sent 'bestmove' command, so discard it
        if clients[color].sid != sid:
            return

        # Apply the sent move
        sfen_move = position.sfen_to_move(data)
        position.do_move(sfen_move)

        # Ask the other player to send a next move
        ask_nextmove(sid)

    app = socketio.WSGIApp(sio)
    eventlet.wsgi.server(eventlet.listen(('localhost', port)), app)

if __name__ == '__main__':
    main()
