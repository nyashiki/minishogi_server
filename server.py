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
    def __init__(self, sfen = None):
        self.id = uuid.uuid4()

        self.position = minishogilib.Position()
        if sfen is None:
            self.position.set_start_position()
        else:
            self.position.set_sfen(sfen)

        # Initial position.
        self.initial_sfen = self.position.sfen(history=True)

        # Time limit.
        self.timelimit = [0 for _ in range(2)]
        self.byoyomi = 0
        self.inc = [0 for _ in range(2)]

        # Clients.
        self.clients = [None for _ in range(2)]

        # Stopwatch.
        self.stopwatch = [None for _ in range(2)]

        # Time consumption.
        self.consumption = []

        self.ongoing = False
        self.gameover = ''  # RESIGN, SENNICHITE, TIME_UP, or ILLEGAL_MOVE

        self.viewers = []

        self.tournament = None
        self.index = 0

    def setConfig(self, config):
        self.timelimit[0] = config['btime']
        self.timelimit[1] = config['wtime']
        self.byoyomi = config['byoyomi']
        self.inc[0] = config['binc']
        self.inc[1] = config['winc']

    def dump_csa(self):
        """Dump kif in CSA representation.

        # Returns:
            The string of CSA representation kif of the game.
        """
        data = []

        data.append('V2.2')
        data.append('N+{}'.format("" if self.clients[0] is None else self.clients[0].name))
        data.append('N-{}'.format("" if self.clients[1] is None else self.clients[1].name))
        data.append('P1-HI-KA-GI-KI-OU')
        data.append('P2 *  *  *  * -FU')
        data.append('P3 *  *  *  *  * ')
        data.append('P4+FU *  *  *  * ')
        data.append('P5+OU+KI+GI+KA+HI')
        data.append('+')

        csa_kif = self.position.get_csa_kif()

        for (ply, kif) in enumerate(csa_kif):
            if ply % 2 == 0:
                data.append('+{}'.format(kif))
            else:
                data.append('-{}'.format(kif))
            data.append('T{}'.format(self.consumption[ply]))

        data.append('%{}'.format(self.gameover))

        return '\n'.join(data)

    def dump_json(self):
        """Dump kif in JSON representation.

        # Returns:
            The string of JSON representation kif of the game.
        """
        data = { }

        data['player1'] = '(none)' if self.clients[0] is None else self.clients[0].name
        data['player2'] = '(none)' if self.clients[1] is None else self.clients[1].name
        data['pos'] = self.initial_sfen
        data['kif'] = self.position.sfen(history=True)
        data['gameover'] = 'on going' if self.gameover == '' else self.gameover
        data['index'] = self.index

        return json.dumps(data, indent=4)

class Tournament:
    def __init__(self, game_count):
        print("INFO: Create new tournament")
        # Players name
        self.names = ["" for _ in range(2)]

        # Players win count
        self.win = [0 for _ in range(2)]

        # The result of sente or gote win
        # '*' (on going), '+' (sente win), '-' (gote win), ' ' (wait for start)
        self.result = [' ' for _ in range(game_count)]

        # The result of games
        self.gameovers = ['' for _ in range(game_count)]

        # Reference of games
        self.games = [None for _ in range(game_count)]

    def gameover(self, game, winner):
        winner_player = (self.names[0] == game.clients[0].name) == winner
        self.win[winner_player] += 1
        # Set sente (+) or gote (-) win flag
        if winner == 0:
            self.result[game.index] = '+'
        else:
            self.result[game.index] = '-'
        self.gameovers[game.index] = game.gameover
        print('index= ', game.index, game.gameover, ' win=', self.win[0], ':', self.win[1], 'results "' + ''.join(self.result) + '"')

    def dump(self):
        current_time = '{0:%Y-%m-%d-%H%M%S}'.format(datetime.datetime.now())
        filename = '{}_{}_{}_trn.txt'.format(current_time, self.names[0], self.names[1])

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
        with open("log/tournaments/" + filename, "w") as f:
            f.write('player1= ' + self.names[0] + '\n')
            f.write('player2= ' + self.names[1] + '\n')
            f.write('win= ' + str(self.win[0]) + ':' + str(self.win[1]) + '\n')
            f.write('results "' + ''.join(self.result) + '"\n')        
            for i, g in enumerate(self.gameovers):
                f.write(str(i+1) + ". " + g + '\n')

class Client:
    def __init__(self):
        self.sid = None
        self.name = ""
        self.readyok = False
        self.disconnect = False

def main(port, config_json):
    with open(config_json) as f:
        config = json.load(f)

    games = []  # Hosting games
    tournaments = [] # Hosting tournaments
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
            'btime': game.timelimit[0],
            'wtime': game.timelimit[1],
            'byoyomi': game.byoyomi,
            'binc': game.inc[0],
            'winc': game.inc[1]
        }

        # Ask the client a next move.
        sio.emit('nextmove', data, namespace='/match', room=sid)

        # Begin to measure consumed time.
        game.stopwatch[color] = time.time_ns() // 1000000

    def quit_engine(sio, game, save=True):
        """Quit the client.

        # Arguments
            sio: socketio.Server()
            game: Game class.
            save: If true, save the CSA kif of the game.
        """

        # Abandon game result if game is not finished
        if game.tournament.result[game.index] == '*':
            game.tournament.result[game.index] = ' '

        # Return if game is already closed
        if game.ongoing == False:
            return        
        game.ongoing = False

        if save:
            current_time = '{0:%Y-%m-%d-%H%M%S}'.format(datetime.datetime.now())
            filename = '{}_{}_{}.json'.format(current_time,
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
                f.write(game.dump_json())

        if ' ' not in game.tournament.result or game.clients[0] is None or game.clients[1] is None:
            # Disconnect all clients if all games are going or finished, or any client disconnected
            if game.clients[0] is not None:
                sio.emit('disconnect', namespace='/match', room=game.clients[0].sid)
            if game.clients[1] is not None:
                sio.emit('disconnect', namespace='/match', room=game.clients[1].sid)
        else:
            # Restart new game
            sio.emit('restart_engine', namespace='/match', room=game.clients[0].sid)
            sio.emit('restart_engine', namespace='/match', room=game.clients[1].sid)

        # Save tournament result if all games are finished
        if ' ' not in game.tournament.result and '*' not in game.tournament.result:
            game.tournament.dump()
            print("INFO: Tournament finished")

    def display(game):
        """Send the current position of the game to viewer clients.
        """

        color = game.position.get_side_to_move()

        timelimit = {
            'btime': game.timelimit[0],
            'wtime': game.timelimit[1],
            'byoyomi': game.byoyomi,
            'binc': game.inc[0],
            'winc': game.inc[1]
        }

        for viewer in game.viewers:
            sio.emit('display', {
                'svg': None if game.position is None else game.position.to_svg(),
                'kif': game.position.get_csa_kif(),
                'sente': game.clients[0].name,
                'gote': game.clients[1].name,
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
            if game.clients[0] is not None and game.clients[0].sid == sid and game.clients[0].disconnect == False:
                game.clients[0].disconnect = True
                if game.gameover == '':
                    game.gameover = 'DISCONNECT'
                quit_engine(sio, game)

            elif game.clients[1] is not None and game.clients[1].sid == sid and game.clients[1].disconnect == False:
                game.clients[1].disconnect = True
                if game.gameover == '':
                    game.gameover = 'DISCONNECT'
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
                    'kif': game.dump_json(),
                    'filename': '{}_{}_{}.json'.format(current_time,
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

    @sio.on('tournament')
    def tournament(sid):
        """Returns tournament data.
        """
        data = []

        for t in tournaments:
            tournament_data = {
                'player1': t.names[0],
                'player2': t.names[1],
                'player1_win': t.win[0],
                'player2_win': t.win[1],
                'result': '"' + ''.join(t.result) + '"'
            }
            data.append(tournament_data)
        return data

    @sio.on('usi', namespace='/match')
    def usi(sid, data):
        """`usi` command is sent from a client.

        If a client sends `usi` command, it supposed that the client wants to have a match.
        """

        # A client sends `usi` commands, but the name field is None.
        if not 'name' in data:
            sio.emit('error', 'You sent a request but name field was None.',
                    namespace='/match', room=sid)
            return

        game = None
        if 'tournament' in config:
            tournament = None
            # Find is program is already joined to a tournament
            for t in tournaments:
                if (t.names[0] == data['name'] or t.names[1] == data['name']) and (' ' in t.result or '*' in t.result):
                    tournament = t
                    break
            # Find a tournament to join
            if tournament is None:
                for t in tournaments:
                    if t.names[1] == "":
                        tournament = t
                        tournament.names[1] = data['name']
                        break
            # Create a new tournament
            if tournament is None:
                tournament = Tournament(config['tournament'])
                tournament.names[0] = data['name']
                tournaments.append(tournament)

            client = Client()
            client.sid = sid
            client.name = data['name']

            # Find a room that current program haven't join in
            for g in tournament.games:
                if g is None or g.gameover != '':
                    continue
                elif g.clients[0] is None and g.clients[1].name != data['name']:
                    game = g
                    game.clients[0] = client
                    break
                elif g.clients[1] is None and g.clients[0].name != data['name']:
                    game = g
                    game.clients[1] = client
                    break

            if game is None:
                index = tournament.result.index(' ')
                if 'initial_positions' not in config:
                    initial_sfen = None
                elif config['swap_turn']:
                    position_id = math.floor(index / 2) % len(config['initial_positions'])
                    initial_sfen = config['initial_positions'][position_id]
                else:
                    position_id = index % len(config['initial_positions'])
                    initial_sfen = config['initial_positions'][position_id]
                game = Game(initial_sfen)
                game.setConfig(config)
                game.index = index

                if not config['swap_turn'] or (index % 2 != (client.name == tournament.names[0])):
                    game.clients[0] = client
                else:
                    game.clients[1] = client
                
                games.append(game)

                # Set 'on going' flag
                tournament.result[index] = '*'
                tournament.games[index] = game

            sid_game[sid] = game
            game.tournament = tournament

        else:
            # If there is a one-player reserved game, set the client as the second player.
            for g in games:
                if g.gameover == '' and g.gameover == '' and g.clients[1] is None:
                    game = g
                    break

            # If there is no one-player reserved game, set the client as the first player.
            if game is None:
                game = Game(None if 'initial_positions' not in config else config['initial_positions'][0])
                game.setConfig(config)
                games.append(game)

            sid_game[sid] = game

            # For some reason an on-going game is selected as the target game, but this is an error.
            if game.clients[1] is not None:
                sio.emit('error', 'The game has already started.',
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
            print("INFO: Create new game: index=", game.index, game.clients[0].name, "vs", game.clients[1].name)

            # Call isready and usinewgame.
            sio.emit('isready', namespace='/match', room=game.clients[0].sid)
            sio.emit('isready', namespace='/match', room=game.clients[1].sid)

    @sio.on('readyok', namespace='/match')
    def readyok(sid, data=None):
        """`readyok` message is sent from a client.
        """
        game = sid_game[sid]
        color = game.position.get_side_to_move()

        for client in game.clients:
            if client.sid == sid:
                client.readyok = True

        if game.clients[0].readyok and game.clients[1].readyok:
            # Send `usinewgame` message to the clients.
            sio.emit('usinewgame', namespace='/match', room=game.clients[0].sid)
            sio.emit('usinewgame', namespace='/match', room=game.clients[1].sid)

            # Ask a first move.
            game.ongoing = True
            ask_nextmove(game, color)

            display(game)

    @sio.on('bestmove', namespace='/match')
    def bestmove(sid, data):
        """`bestmove` message is sent from a client.
        """
        PLAYER_STR = ["SENTE", "GOTE"]

        game = sid_game[sid]

        color = game.position.get_side_to_move()

        # An unknown player sent 'bestmove' command, so discard it.
        if game.clients[color].sid != sid:
            return

        sfen_move = data

        # If the client resigns.
        if sfen_move == 'resign':
            game.gameover = PLAYER_STR[color] + '_RESIGN'
            game.tournament.gameover(game, int(not color))
            quit_engine(sio, game)
            display(game)
            return

        # Check whether the sent move is legal.
        legal_moves = game.position.generate_moves()
        if not sfen_move in [m.sfen() for m in legal_moves]:
            game.gameover = PLAYER_STR[color] + '_ILLEGAL_MOVE'
            game.tournament.gameover(game, int(not color))
            quit_engine(sio, game)
            display(game)
            return

        move = game.position.sfen_to_move(sfen_move)

        # Time consumption.
        current_time = time.time_ns() // 1000000
        elapsed = max(1, math.floor(current_time - game.stopwatch[color]))
        game.consumption.append(elapsed)

        if game.timelimit[color] > 0:
            m = min(game.timelimit[color], elapsed)
            game.timelimit[color] -= m
            elapsed -= m
            game.timelimit[color] += game.inc[color]

        if elapsed > game.byoyomi:
            # Lose by timelimit.
            game.gameover = PLAYER_STR[color] + '_TIME_UP'
            game.tournament.gameover(game, int(not color))
            quit_engine(sio, game)

        else:
            # Apply the sent move.
            game.position.do_move(move)

            # Is the game end?
            is_repetition, is_check_repetition, _ = game.position.is_repetition()
            legal_moves = game.position.generate_moves()
            if is_check_repetition:
                game.gameover = PLAYER_STR[color] + '_ILLEGAL_MOVE'
                game.tournament.gameover(game, int(not color))
                quit_engine(sio, game)

            elif is_repetition:
                game.gameover = PLAYER_STR[0] + '_SENNICHITE'
                game.tournament.gameover(game, 1)
                quit_engine(sio, game)

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
    eventlet.wsgi.server(eventlet.listen(('', port)), app, log_output=False)

if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option('-c', '--config', dest='config_json',
                      help='confile json file', default='./server.json')
    parser.add_option('-p', '--port', dest='port',
                      help='target port', type='int', default=8000)

    (options, args) = parser.parse_args()

    main(port=options.port, config_json=options.config_json)
