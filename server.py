import eventlet
import math
import minishogilib
from optparse import OptionParser
import os
import simplejson as json
import socketio
import time


class Game:
    def __init__(self):
        self.position = minishogilib.Position()
        self.position.set_start_position()

        # Time limit
        self.timelimit = [0 for _ in range(2)]
        self.byoyomi = 0

        # Clients
        self.clients = []

        # Stopwatch
        self.stopwatch = [None for _ in range(2)]

        self.ongoing = False
        self.gameover = False

class Client:
    def __init__(self):
        self.sid = None
        self.readyok = False

def main(port, config_json):
    game = Game()

    with open(config_json) as f:
        config = json.load(f)

    game.timelimit[0] = config['btime'] // 1000
    game.timelimit[1] = config['wtime'] // 1000
    game.byoyomi = config['byoyomi'] // 1000

    sio = socketio.Server()

    def ask_nextmove(color):
        sid = game.clients[color].sid

        data = {
            'position': game.position.sfen(True),
            'btime': game.timelimit[0] * 1000,
            'wtime': game.timelimit[1] * 1000,
            'byoyomi': game.byoyomi * 1000
        }

        sio.emit('nextmove', data, namespace='/match', room=sid)

        game.stopwatch[color] = time.time()

    def display():
        # about timelimit
        color = game.position.get_side_to_move()

        timelimit  = {
            'btime': game.timelimit[0],
            'wtime': game.timelimit[1],
            'byoyomi': game.byoyomi
        }

        sio.emit('display', {
            'svg': None if game.position is None else game.position.to_svg(),
            'kif': game.position.get_kif(),
            'timelimit': timelimit,
            'side_to_move': color,
            'ongoing': game.ongoing,
            'gameover': game.gameover
        })

    @sio.event
    def connect(sid, data=None):
        display()

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
            # Two players sit down, so a game is starting.
            # Initialization
            game.position = minishogilib.Position()
            game.position.set_start_position()

            # Call isready and usinewgame
            sio.emit('isready', namespace='/match', room=game.clients[0].sid)
            sio.emit('isready', namespace='/match', room=game.clients[1].sid)

    @sio.on('readyok', namespace='/match')
    def readyok(sid, data=None):
        for client in game.clients:
            if client.sid == sid:
                client.readyok = True

        if game.clients[0].readyok and game.clients[1].readyok:
            sio.emit('usinewgame', namespace='/match', room=game.clients[0].sid)
            sio.emit('usinewgame', namespace='/match', room=game.clients[1].sid)

            # Ask a first move
            game.ongoing = True
            ask_nextmove(0)

            display()

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
            game.gameover = True

        move = game.position.sfen_to_move(sfen_move)

        # check whether the sent move is legal
        legal_moves = game.position.generate_moves()
        if not move.sfen() in [m.sfen() for m in legal_moves]:
            print('ILLEGAL MOVE')
            sio.emit('disconnect', namespace='/match')
            game.gameover = True

        # time consumption
        current_time = time.time()
        elapsed = math.ceil(current_time - game.stopwatch[color])

        if game.timelimit[color] > 0:
            m = min(game.timelimit[color], elapsed)
            game.timelimit[color] -= m
            elapsed -= m

        # ToDo: lose by timelimit

        # Apply the sent move
        game.position.do_move(move)

        # Is the game end?
        is_repetition, is_check_repetition = game.position.is_repetition()
        legal_moves = game.position.generate_moves()
        if is_check_repetition:
            print('CHECK REPETITION')
            sio.emit('disconnect', namespace='/match')
            game.gameover = True

        elif is_repetition:
            print('REPETITION')
            sio.emit('disconnect', namespace='/match')
            game.gameover = True

        elif len(legal_moves) == 0:
            print('NO LEGAL MOVE')
            sio.emit('disconnect', namespace='/match')
            game.gameover = True

        else:
            # Ask the other player to send a next move
            ask_nextmove(1 - color)

        display()

    static_files = {
        '/': './index.html',
        '/css/': './css/',
        '/js/': './js/'
    }
    app = socketio.WSGIApp(sio, static_files=static_files)
    eventlet.wsgi.server(eventlet.listen(('', port)), app)

if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option('-c', '--config', dest='config_json', help='confile json file', default='./server.json')
    parser.add_option('-p', '--port', dest='port', help='target port', type='int', default=8000)

    (options, args) = parser.parse_args()

    main(port=options.port, config_json=options.config_json)
