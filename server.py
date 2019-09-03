import datetime
import eventlet
import math
import minishogilib
from optparse import OptionParser
import os
import simplejson as json
import socketio
import time
import uuid


class Game:
    def __init__(self):
        self.id = None

        self.position = minishogilib.Position()
        self.position.set_start_position()

        # Time limit
        self.timelimit = [0 for _ in range(2)]
        self.byoyomi = 0

        # Clients
        self.clients = [None for _ in range(2)]

        # Stopwatch
        self.stopwatch = [None for _ in range(2)]

        self.ongoing = False
        self.gameover = ''  # TORYO, SENNICHITE, TIME_UP, or ILLEGAL_MOVE


class Client:
    def __init__(self):
        self.sid = None
        self.name = ""
        self.readyok = False

def dump_csa(game):
    data = []

    data.append('V2.2')
    data.append('N+{}'.format("" if game.clients[0] is None else game.clients[0].name))
    data.append('N-{}'.format("" if game.clients[1] is None else game.clients[1].name))
    data.append('P1-HI-KA-GI-KI-OU')
    data.append('P2 *  *  *  * -FU')
    data.append('P3 *  *  *  *  * ')
    data.append('P4+FU *  *  *  * ')
    data.append('P5+OU+KI+GI+KA+HI')
    data.append('+')

    csa_kif = game.position.get_csa_kif()

    for (ply, kif) in enumerate(csa_kif):
        if ply % 2 == 0:
            data.append('+{}'.format(kif))
        else:
            data.append('-{}'.format(kif))

    data.append('%{}'.format(game.gameover))

    return '\n'.join(data)

def main(port, config_json):
    with open(config_json) as f:
        config = json.load(f)

    games = []

    sid_game = {

    }

    sio = socketio.Server()

    def ask_nextmove(game, color):
        sid = game.clients[color].sid

        data = {
            'position': game.position.sfen(True),
            'btime': game.timelimit[0] * 1000,
            'wtime': game.timelimit[1] * 1000,
            'byoyomi': game.byoyomi * 1000
        }

        sio.emit('nextmove', data, namespace='/match', room=sid)

        game.stopwatch[color] = time.time()

    def display(game):
        # about timelimit
        color = game.position.get_side_to_move()

        timelimit = {
            'btime': game.timelimit[0],
            'wtime': game.timelimit[1],
            'byoyomi': game.byoyomi
        }

        sio.emit('display', {
            'svg': None if game.position is None else game.position.to_svg(),
            'kif': game.position.get_csa_kif(),
            'timelimit': timelimit,
            'side_to_move': color,
            'ongoing': game.ongoing,
            'gameover': game.gameover
        })

    @sio.event
    def connect(sid, data=None):
        if len(games) > 0:
            display(games[0])

    @sio.on('download')
    def download(sid, data=None):
        # ToDo: Game = ...
        current_time = '{0:%Y-%m-%d-%H%M%S}'.format(datetime.datetime.now())

        data = {
            'kif': dump_csa(game),
            'filename': '{}_{}_{}.csa'.format(current_time,
                                              "Player1" if game.clients[0] is None else game.clients[0].name,
                                              "Player2" if game.clients[1] is None else game.clients[1].name)
        }

        return data, 200

    @sio.on('usi', namespace='/match')
    def usi(sid, data):
        print('COME HERE! {}'.format(sid))

        target_game = None
        for game in games:
            if game.clients[1] is None:
                target_game = game
                break

        if target_game is None:
            game = Game()
            game.timelimit[0] = config['btime'] // 1000
            game.timelimit[1] = config['wtime'] // 1000
            game.byoyomi = config['byoyomi'] // 1000

            game.id = uuid.uuid4()
        else:
            game = target_game

        games.append(game)
        sid_game[sid] = game

        if game.clients[1] is not None:
            sio.emit('error', 'The game has already started.',
                     namespace='/match', room=sid)
            return

        if not 'name' in data:
            sio.emit('error', 'You sent a request but name field was None.',
                     namespace='/match', room=sid)
            return

        if not 'author' in data:
            sio.emit('error', 'You sent a request but author field was None.',
                     namespace='/match', room=sid)
            return

        client = Client()
        client.sid = sid
        client.name = data['name']

        if game.clients[0] is None:
            game.clients[0] = client
        else:
            game.clients[1] = client

        sio.emit('info', 'Correctly accepted.', namespace='/match', room=sid)

        if game.clients[0] is not None and game.clients[1] is not None:
            # Two players sit down, so a game is starting.
            # Initialization
            game.position = minishogilib.Position()
            game.position.set_start_position()

            # Call isready and usinewgame
            sio.emit('isready', namespace='/match', room=game.clients[0].sid)
            sio.emit('isready', namespace='/match', room=game.clients[1].sid)

    @sio.on('readyok', namespace='/match')
    def readyok(sid, data=None):
        game = sid_game[sid]

        for client in game.clients:
            if client.sid == sid:
                client.readyok = True

        if game.clients[0].readyok and game.clients[1].readyok:
            sio.emit('usinewgame', namespace='/match',
                     room=game.clients[0].sid)
            sio.emit('usinewgame', namespace='/match',
                     room=game.clients[1].sid)

            # Ask a first move
            game.ongoing = True
            ask_nextmove(game, 0)

            display(game)

    @sio.on('bestmove', namespace='/match')
    def bestmove(sid, data):
        game = sid_game[sid]

        color = game.position.get_side_to_move()

        # An unknown player sent 'bestmove' command, so discard it
        if game.clients[color].sid != sid:
            return

        sfen_move = data

        if sfen_move == 'resign':
            print('RESIGN')
            sio.emit('disconnect', namespace='/match')
            game.gameover = 'TORYO'
            display(game)
            return

        # check whether the sent move is legal
        legal_moves = game.position.generate_moves()
        if not sfen_move in [m.sfen() for m in legal_moves]:
            print('ILLEGAL MOVE')
            sio.emit('disconnect', namespace='/match')
            game.gameover = 'ILLEGAL_MOVE'
            display(game)
            return

        move = game.position.sfen_to_move(sfen_move)

        # time consumption
        current_time = time.time()
        elapsed = math.ceil(current_time - game.stopwatch[color])

        if game.timelimit[color] > 0:
            m = min(game.timelimit[color], elapsed)
            game.timelimit[color] -= m
            elapsed -= m

        # lose by timelimit
        if elapsed > game.byoyomi:
            print('TIMEOUT')
            sio.emit('disconnect', namespace='/match')
            game.gameover = 'TIME_UP'

        else:
            # Apply the sent move
            game.position.do_move(move)

            # Is the game end?
            is_repetition, is_check_repetition = game.position.is_repetition()
            legal_moves = game.position.generate_moves()
            if is_check_repetition:
                print('CHECK REPETITION')
                sio.emit('disconnect', namespace='/match')
                game.gameover = 'ILLEGAL_MOVE'

            elif is_repetition:
                print('REPETITION')
                sio.emit('disconnect', namespace='/match')
                game.gameover = 'SENNICHITE'

            else:
                # Ask the other player to send a next move
                ask_nextmove(game, 1 - color)

        display(game)

    static_files = {
        '/': './index.html',
        '/css/': './css/',
        '/js/': './js/'
    }

    app = socketio.WSGIApp(sio, static_files=static_files)
    eventlet.wsgi.server(eventlet.listen(('', port)), app)

if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option('-c', '--config', dest='config_json',
                      help='confile json file', default='./server.json')
    parser.add_option('-p', '--port', dest='port',
                      help='target port', type='int', default=8000)

    (options, args) = parser.parse_args()

    main(port=options.port, config_json=options.config_json)
