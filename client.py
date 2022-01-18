import logging
from optparse import OptionParser
import os
import simplejson as json
import socketio
import subprocess
import threading
import queue
import time
import minishogilib


def send_message(engine, message, verbose=True):
    """Send message to the engine through standard input.

    # Arguments
        engine: An USI Minishogi engine.
        message: message sent to the engine.
        verbose: If true, print message in stdout.
    """
    if verbose:
        print('>:', message)

    message = (message + '\n').encode('utf-8')
    engine.stdin.write(message)
    engine.stdin.flush()

def message_reader(pipe, queue, verbose=True):
    """Receive message from the engine through standard output and store it.

    # Arguments
        pipe: stdout of the USI engine.
        queue: message queue to which stdout of the USI engine is stored.
        verbose: If true, print message in stdout.
    """
    with pipe:
        for line in iter(pipe.readline, b''):
            message = line.decode('utf-8').rstrip('\r\n')
            queue.put(message)

            if verbose:
                print('<:', message)

def receive_message(queue):
    """Output message from the queue.

    # Arguments
        queue: The queue that stores outputs of stdout of the USI engine.

    # Returns
        A line of stdout of the USI engine.
    """
    while queue.empty():
        continue

    message = queue.get()
    return message

def main(ip, port, config_json):
    with open(config_json) as f:
        config = json.load(f)

    state = minishogilib.Position()

    # Run an USI engine.
    usi_engine = subprocess.Popen(config['command'].split(), cwd=config['cwd'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    # Run a thread that receives outputs of stdout of the USI engine.
    message_queue = queue.Queue()
    threading.Thread(target=message_reader, args=[usi_engine.stdout, message_queue]).start()

    # Send usi command to the engine.
    send_message(usi_engine, 'usi')

    # Get engine information.
    engine_info = { }
    while True:
        output = receive_message(message_queue).split()

        if len(output) == 0:
            continue

        if output[0] == 'id':
            engine_info[output[1]] = output[2]

        if output[0] == 'usiok':
            break

    # Set USI options
    for option, value in config['option'].items():
        message = 'setoption name {} value {}'.format(option, value)
        send_message(usi_engine, message)

    # #########################################################################################
    # Socket-IO Events BEGIN
    # #########################################################################################
    sio = socketio.Client()

    @sio.event(namespace='/match')
    def connect(data=None):
        """Connect to the matching server.
        """
        sio.emit('usi', engine_info, namespace='/match')

    @sio.on('error', namespace='/match')
    def error(message):
        """An error message was sent from the server.
        """
        print('ERROR: {}'.format(message))
        os._exit(0)

    @sio.on('info', namespace='/match')
    def info(message):
        """An information message was sent from the server.
        """
        print('INFO: {}'.format(message))

    @sio.on('isready', namespace='/match')
    def isready(data=None):
        """`isready` message was sent from the server.

        If a client gets this message, the client has to send `isready` command to the USI engine,
        and waits until `readyok` command is sent.
        """
        send_message(usi_engine, 'isready')

        while True:
            output = receive_message(message_queue).split()

            if len(output) == 0:
                continue

            if output[0] == 'readyok':
                break

        # Send `readyok` message to the server.
        sio.emit('readyok', namespace='/match')

    @sio.on('usinewgame', namespace='/match')
    def usinewgame(data=None):
        """`usinewgame` message was sent from the server.

        If a client gets this message, the client has to send `usinewgame` command to the USI engine.
        """
        send_message(usi_engine, 'usinewgame')

    @sio.on('nextmove', namespace='/match')
    def nextmove(data):
        """`nextmove` message was sent from the server.

        If a client gets this message, the client has to ask the engine a next move.
        """
        think_start_time = time.time()

        if nextmove.ponder is not None:
            # If ponder is set, judge whether the ponder move is the same as the actual move.
            if nextmove.ponder == data['position'].split()[-1]:
                # If ponder is the same, send `ponderhit` command to the USI engine.
                send_message(usi_engine, 'ponderhit')
            else:
                # If ponder is not the same, send `stop` command to the USI engine.
                send_message(usi_engine, 'stop')
                nextmove.ponder = None

                # Wait until `bestmove` command is sent.
                # Note: this `bestmove` command is dummy, because the predicted ponder move is different from the actual given move.
                while True:
                    output = receive_message(message_queue).split()

                    if len(output) == 0:
                        continue

                    if output[0] == 'bestmove':
                        break

        # Sfen representation of the current position.
        sfen_position = 'position sfen ' + data['position']

        if nextmove.ponder is None:
            # Ask the USI engine a next move.
            send_message(usi_engine, sfen_position)

            if data['byoyomi'] > 0:
                command = 'go btime {} wtime {} byoyomi {}'.format(data['btime'], data['wtime'], data['byoyomi'])
            else:
                command = 'go btime {} wtime {} binc {} winc {}'.format(data['btime'], data['wtime'], data['binc'], data['winc'])

            prev_think_time = time.time()
            send_message(usi_engine, command)

        # Wait until `bestmove` command is sent.
        while True:
            output = receive_message(message_queue).split()

            if len(output) == 0:
                continue

            if output[0] == 'bestmove':
                sio.emit('bestmove', output[1], namespace='/match')

                # Calculate the remaining time while pondering.
                think_elapsed = time.time() - think_start_time
                state.set_sfen(data['position'])
                if state.get_side_to_move() == 0:
                    data['btime'] -= int(think_elapsed * 1000)
                else:
                    data['wtime'] -= int(think_elapsed * 1000)

                if len(output) >= 4 and output[2] == 'ponder':
                    # If ponder is sent, set ponder move and send `go ponder` command to the USI engine.
                    nextmove.ponder = output[3]
                    if sfen_position[-1] == '1' :
                        # If the position is the initial position, `moves` should be added.
                        ponder_position = '{} moves {} {}'.format(sfen_position, output[1], nextmove.ponder)
                    else:
                        ponder_position = '{} {} {}'.format(sfen_position, output[1], nextmove.ponder)

                    send_message(usi_engine, ponder_position)
                    if data['byoyomi'] > 0:
                        send_message(usi_engine, 'go ponder btime {} wtime {} byoyomi {}'.format(data['btime'], data['wtime'], data['byoyomi']))
                    else:
                        send_message(usi_engine, 'go ponder btime {} wtime {} binc {} winc {}'.format(data['btime'], data['wtime'], data['binc'], data['winc']))
                else:
                    nextmove.ponder = None

                break

    # Set ponder move to be None at initialization.
    nextmove.ponder = None

    @sio.event(namespace='/match')
    def disconnect(data=None):
        """Disconnect from the matching server.

        After disconnection, quit the USI engine and this client.
        """
        send_message(usi_engine, 'quit')
        usi_engine.wait()
        os._exit(0)

    # #########################################################################################
    # Socket-IO Events END
    # #########################################################################################

    url = 'http://{}:{}'.format(ip, port)
    sio.connect(url)
    sio.wait()

if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option('-c', '--config', dest='config_json', help='confile json file', default='./client.json')
    parser.add_option('-i', '--ip', dest='ip', help='target ip', default='localhost')
    parser.add_option('-p', '--port', dest='port', help='target port', type='int', default=8000)

    (options, args) = parser.parse_args()

    main(ip=options.ip, port=options.port, config_json=options.config_json)
