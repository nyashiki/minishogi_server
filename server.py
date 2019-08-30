import eventlet
import minishogilib
import os
import simplejson as json
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

    with open('server.json') as f:
        config = json.load(f)

    def ask_nextmove(sid):
        data = {
            'position': game.position.sfen(True),
            'btime': config['btime'],
            'wtime': config['wtime'],
            'byoyomi': config['byoyomi']
        }

        sio.emit('nextmove', data, namespace='/match', room=sid)

    @sio.on('usi', namespace='/match')
    def usi(sid, data):
        if len(game.clients) >= 2:
            sio.emit('error', 'The game has already started.', namespace='/match', room=sid)
            return

        if not 'name' in data:
            sio.emit('error', 'You sent a request but name field was None.', namespace='/match', room=sid)
            return

        if not 'author' in data:
            sio.emit('error', 'You sent a request but author field was None.', namespace='/match', room=sid)
            return

        client = Client()
        client.sid = sid

        game.clients.append(client)

        sio.emit('info', 'Correctly accepted.', namespace='/match', room=sid)

        if len(game.clients) == 2:
            # Two players sit down, so a game is starting
            # Initialization
            game.position = minishogilib.Position()
            game.position.set_start_position()

            # Call isready and usinewgame
            sio.emit('isready', namespace='/match')
            sio.emit('usinewgame', namespace='/match')

            game.position.print()

            # Ask a first move
            ask_nextmove(game.clients[0].sid)

    # ToDo: @sio.event disconnect()

    @sio.on('bestmove', namespace='/match')
    def bestmove(sid, data):
        color = game.position.get_side_to_move()

        # An unknown player sent 'bestmove' command, so discard it
        if game.clients[color].sid != sid:
            return

        sfen_move = data

        if sfen_move == 'resign':
            print('RESIGN')
            sio.emit('disconnect', namespace='/match')
            os._exit(0)

        move = game.position.sfen_to_move(sfen_move)

        # check whether the sent move is legal
        legal_moves = game.position.generate_moves()
        if not move.sfen() in [m.sfen() for m in legal_moves]:
            print(move.sfen())
            print([m.sfen() for m in legal_moves])
            print('ILLEGAL MOVE')
            sio.emit('disconnect', namespace='/match')
            os._exit(0)

        # Apply the sent move
        game.position.do_move(move)
        game.position.print()

        # Is the game end?
        is_repetition, is_check_repetition = game.position.is_repetition()
        legal_moves = game.position.generate_moves()
        if is_check_repetition:
            print('CHECK REPETITION')
            sio.emit('disconnect', namespace='/match')
            os._exit(0)

        elif is_repetition:
            print('REPETITION')
            sio.emit('disconnect', namespace='/match')
            os._exit(0)

        if len(legal_moves) == 0:
            print('NO LEGAL MOVE')
            sio.emit('disconnect', namespace='/match')
            os._exit(0)

        # Ask the other player to send a next move
        ask_nextmove(game.clients[1 - color].sid)

    app = socketio.WSGIApp(sio)
    eventlet.wsgi.server(eventlet.listen(('localhost', port)), app)

if __name__ == '__main__':
    main()
