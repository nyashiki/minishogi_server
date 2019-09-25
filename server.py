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

        # Time limit.
        self.timelimit = [0 for _ in range(2)]
        self.byoyomi = 0

        # Clients.
        self.clients = [None for _ in range(2)]

        # Stopwatch.
        self.stopwatch = [None for _ in range(2)]

        # Time consumption.
        self.consumption = []

        self.ongoing = False
        self.gameover = ''  # TORYO, SENNICHITE, TIME_UP, or ILLEGAL_MOVE

        self.viewers = []

class Client:
    def __init__(self):
        self.sid = None
        self.name = ""
        self.readyok = False
        self.disconnect = False

def dump_csa(game):
    """Dump kif in CSA representation.

    # Arguments:
        game: Game class.

    # Returns:
        The string of CSA representation kif of the game.
    """
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
        data.append('T{}'.format(game.consumption[ply]))

    data.append('%{}'.format(game.gameover))

    return '\n'.join(data)

def main(port, config_json):
    with open(config_json) as f:
        config = json.load(f)

    games = []  # Hosting games
    sid_game = { }  # Which game is this sid's player playing?

    sio = socketio.Server()

    def ask_nextmove(game, color):
        """Ask the client a next move.

        # Arguments
            game: Game class.
            color: the side to move (0=First player, 1=Second player).
        """
        sid = game.clients[color].sid

        # Set data that is sent to the client.
        data = {
            'position': game.position.sfen(True),
            'btime': game.timelimit[0] * 1000,
            'wtime': game.timelimit[1] * 1000,
            'byoyomi': game.byoyomi * 1000
        }

        # Ask the client a next move.
        sio.emit('nextmove', data, namespace='/match', room=sid)

        # Begin to measure consumed time.
        game.stopwatch[color] = time.time()

    def quit_engine(sio, game, save=True):
        """Quit the client.

        # Arguments
            sio: socketio.Server()
            game: Game class.
            save: If true, save the CSA kif of the game.
        """

        # Send `disconnect` message to the first player client.
        if game.clients[0] is not None:
            sio.emit('disconnect', namespace='/match', room=game.clients[0].sid)

        # Send `disconnect` message to the second player client.
        if game.clients[1] is not None:
            sio.emit('disconnect', namespace='/match', room=game.clients[1].sid)

        if save:
            current_time = '{0:%Y-%m-%d-%H%M%S}'.format(datetime.datetime.now())
            filename = '{}_{}_{}.csa'.format(current_time,
                                            "Player1" if game.clients[0] is None else game.clients[0].name,
                                            "Player2" if game.clients[1] is None else game.clients[1].name)

            # Replace not allowed characters for filename
            filename = (filename.replace(' ', '-')
                                .replace(';', '')
                                .replace(':', '')
                                .replace('\\', '')
                                .replace('/', '')
                                .replace('*', '')
                                .replace('?', '')
                                .replace('"', '')
                                .replace('<', '')
                                .replace('>', '')
                                .replace('|', '')
                                .replace("'", ''))

            with open('log/games/' + filename, 'w') as f:
                f.write(dump_csa(game))

    def display(game):
        """Send the current position of the game to viewer clients.
        """

        color = game.position.get_side_to_move()

        timelimit = {
            'btime': game.timelimit[0],
            'wtime': game.timelimit[1],
            'byoyomi': game.byoyomi
        }

        for viewer in game.viewers:
            sio.emit('display', {
                'svg': None if game.position is None else game.position.to_svg(),
                'kif': game.position.get_csa_kif(),
                'timelimit': timelimit,
                'side_to_move': color,
                'ongoing': game.ongoing,
                'gameover': game.gameover
            }, room=viewer)

    # #########################################################################################
    # Socket-IO Events BEGIN
    # #########################################################################################

    @sio.event
    def connect(sid, data=None):
        """A clients connects to this server.
        """
        if 'HTTP_REFERER' in data:
            split = data['HTTP_REFERER'].split('?')

            if len(split) > 1:
                # If id is specified, it supposed that a clients want to view the game.
                id = split[1]

                for game in games:
                    if id == str(game.id):
                        game.viewers.append(sid)
                        display(game)

                        break

    @sio.event
    def disconnect(sid, data=None):
        """A clients disconnects from this server.
        """
        for game in games:
            if game.clients[0] is not None and game.clients[0].sid == sid:
                game.clients[0].disconnect = True
                if game.gameover == '':
                    game.gameover = 'DISCONNECT'
                game.ongoing = False
                quit_engine(sio, game)

            elif game.clients[1] is not None and game.clients[1].sid == sid:
                game.clients[1].disconnect = True
                if game.gameover == '':
                    game.gameover = 'DISCONNECT'
                game.ongoing = False
                quit_engine(sio, game)

            else:
                # Someone leaves the room of a game.
                game.viewers = list(filter(lambda x: x != sid, game.viewers))

    @sio.on('download')
    def download(sid, id):
        """A viewer wants to download CSA kif.
        """
        for game in games:
            if id == str(game.id):
                current_time = '{0:%Y-%m-%d-%H%M%S}'.format(datetime.datetime.now())

                data = {
                    'kif': dump_csa(game),
                    'filename': '{}_{}_{}.csa'.format(current_time,
                                                    "Player1" if game.clients[0] is None else game.clients[0].name,
                                                    "Player2" if game.clients[1] is None else game.clients[1].name)
                }

                return data, 200

    @sio.on('matching')
    def matching(sid):
        """Returns matching data.
        """
        data = []

        for game in reversed(games):
            game_data = {
                'gameover': game.gameover,
                'ongoing': game.ongoing,
                'link': './view?{}'.format(game.id),
                'player1': "Player1" if game.clients[0] is None else game.clients[0].name,
                "player2": "Player2" if game.clients[1] is None else game.clients[1].name
            }

            data.append(game_data)
        return data

    @sio.on('usi', namespace='/match')
    def usi(sid, data):
        """`usi` command is sent from a client.

        If a client sends `usi` command, it supposed that the client wants to have a match.
        """
        # If there is a one-player reserved game, set the client as the second player.
        target_game = None
        for game in games:
            if game.gameover == '' and game.clients[1] is None:
                target_game = game
                break

        # If there is no one-player reserved game, set the client as the first player.
        if target_game is None:
            game = Game()
            game.timelimit[0] = config['btime'] // 1000
            game.timelimit[1] = config['wtime'] // 1000
            game.byoyomi = config['byoyomi'] // 1000
            game.id = uuid.uuid4()

            games.append(game)
        else:
            game = target_game

        sid_game[sid] = game

        # For some reason an on-going game is selected as the target game, but this is an error.
        if game.clients[1] is not None:
            sio.emit('error', 'The game has already started.',
                     namespace='/match', room=sid)
            return

        # A client sends `usi` commands, but the name field is None.
        if not 'name' in data:
            sio.emit('error', 'You sent a request but name field was None.',
                     namespace='/match', room=sid)
            return

        # A client sends `usi` commands, but the author field is None.
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
            # Initialization.
            game.position = minishogilib.Position()
            game.position.set_start_position()

            # Call isready and usinewgame.
            sio.emit('isready', namespace='/match', room=game.clients[0].sid)
            sio.emit('isready', namespace='/match', room=game.clients[1].sid)

    @sio.on('readyok', namespace='/match')
    def readyok(sid, data=None):
        """`readyok` message is sent from a client.
        """
        game = sid_game[sid]

        for client in game.clients:
            if client.sid == sid:
                client.readyok = True

        if game.clients[0].readyok and game.clients[1].readyok:
            # Send `usinewgame` message to the clients.
            sio.emit('usinewgame', namespace='/match',
                     room=game.clients[0].sid)
            sio.emit('usinewgame', namespace='/match',
                     room=game.clients[1].sid)

            # Ask a first move.
            game.ongoing = True
            ask_nextmove(game, 0)

            display(game)

    @sio.on('bestmove', namespace='/match')
    def bestmove(sid, data):
        """`bestmove` message is sent from a client.
        """
        game = sid_game[sid]

        color = game.position.get_side_to_move()

        # An unknown player sent 'bestmove' command, so discard it.
        if game.clients[color].sid != sid:
            return

        sfen_move = data

        # If the client resigns.
        if sfen_move == 'resign':
            print('RESIGN')
            quit_engine(sio, game)
            game.gameover = 'TORYO'
            game.ongoing = False
            display(game)
            return

        # Check whether the sent move is legal.
        legal_moves = game.position.generate_moves()
        if not sfen_move in [m.sfen() for m in legal_moves]:
            print('ILLEGAL MOVE')
            quit_engine(sio, game)
            game.gameover = 'ILLEGAL_MOVE'
            game.ongoing = False
            display(game)
            return

        move = game.position.sfen_to_move(sfen_move)

        # Time consumption.
        current_time = time.time()
        elapsed = max(1, math.floor(current_time - game.stopwatch[color]))

        if game.timelimit[color] > 0:
            m = min(game.timelimit[color], elapsed)
            game.timelimit[color] -= m
            elapsed -= m

        if elapsed > game.byoyomi:
            # Lose by timelimit.
            print('TIMEOUT')
            quit_engine(sio, game)
            game.ongoing = False
            game.gameover = 'TIME_UP'

        else:
            # Apply the sent move.
            game.position.do_move(move)

            game.consumption.append(elapsed)

            # Is the game end?
            is_repetition, is_check_repetition = game.position.is_repetition()
            legal_moves = game.position.generate_moves()
            if is_check_repetition:
                print('CHECK REPETITION')
                quit_engine(sio, game)
                game.ongoing = False
                game.gameover = 'ILLEGAL_MOVE'

            elif is_repetition:
                print('REPETITION')
                quit_engine(sio, game)
                game.ongoing = False
                game.gameover = 'SENNICHITE'

            else:
                # Ask the other player to send a next move.
                ask_nextmove(game, 1 - color)

        display(game)

    # #########################################################################################
    # Socket-IO Events END
    # #########################################################################################

    static_files = {
        '/': './html/index.html',
        '/view': './html/view.html',
        '/css/': './html/css/',
        '/js/': './html/js/'
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
