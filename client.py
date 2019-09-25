import logging
from optparse import OptionParser
import os
import simplejson as json
import socketio
import subprocess
import threading
import queue


def send_message(engine, message, verbose=True):
    if verbose:
        print('>:', message)

    message = (message + '\n').encode('utf-8')
    engine.stdin.write(message)
    engine.stdin.flush()

def message_reader(pipe, queue, verbose=True):
    with pipe:
        for line in iter(pipe.readline, b''):
            message = line.decode('utf-8').rstrip('\r\n')
            queue.put(message)

            if verbose:
                print('<:', message)

def receive_message(engine, queue):
    while queue.empty():
        continue

    message = queue.get()
    return message

def main(ip, port, config_json):
    with open(config_json) as f:
        config = json.load(f)

    usi_engine = subprocess.Popen(config['command'].split(), cwd=config['cwd'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    message_queue = queue.Queue()
    threading.Thread(target=message_reader, args=[usi_engine.stdout, message_queue]).start()

    send_message(usi_engine, 'usi')

    engine_info = { }

    while True:
        output = receive_message(usi_engine, message_queue).split()

        if len(output) == 0:
            continue

        if output[0] == 'id':
            engine_info[output[1]] = output[2]

        if output[0] == 'usiok':
            break

    # Set options
    for option, value in config['option'].items():
        message = 'setoption name {} value {}'.format(option, value)
        send_message(usi_engine, message)

    sio = socketio.Client()

    @sio.event(namespace='/match')
    def connect(data=None):
        sio.emit('usi', engine_info, namespace='/match')

    @sio.on('error', namespace='/match')
    def error(message):
        print('ERROR: {}'.format(message))
        os._exit(0)

    @sio.on('info', namespace='/match')
    def info(message):
        print('INFO: {}'.format(message))

    @sio.on('isready', namespace='/match')
    def isready(data):
        send_message(usi_engine, 'isready')

        while True:
            output = receive_message(usi_engine, message_queue).split()

            if len(output) == 0:
                continue

            if output[0] == 'readyok':
                break

        sio.emit('readyok', namespace='/match')

    @sio.on('usinewgame', namespace='/match')
    def usinewgame(data):
        send_message(usi_engine, 'usinewgame')

    @sio.on('nextmove', namespace='/match')
    def nextmove(data):
        if nextmove.ponder is not None:
            if nextmove.ponder == data['position'].split()[-1]:
                send_message(usi_engine, 'ponderhit')
            else:
                send_message(usi_engine, 'stop')
                nextmove.ponder = None

                # wait until 'bestmove' command is sent
                while True:
                    output = receive_message(usi_engine, message_queue).split()

                    if len(output) == 0:
                        continue

                    if output[0] == 'bestmove':
                        break

        sfen_position = 'position sfen ' + data['position']
        if nextmove.ponder is None:
            send_message(usi_engine, sfen_position)

            command = 'go btime {} wtime {} byoyomi {}'.format(data['btime'], data['wtime'], data['byoyomi'])
            send_message(usi_engine, command)

        while True:
            output = receive_message(usi_engine, message_queue).split()

            if len(output) == 0:
                continue

            if output[0] == 'bestmove':
                sio.emit('bestmove', output[1], namespace='/match')

                if len(output) >= 4 and output[2] == 'ponder':
                    nextmove.ponder = output[3]
                    ponder_position = '{} {} {}'.format(sfen_position, output[1], nextmove.ponder)

                    send_message(usi_engine, ponder_position)
                    send_message(usi_engine, 'go ponder')
                else:
                    nextmove.ponder = None

                break

    nextmove.ponder = None

    @sio.event(namespace='/match')
    def disconnect(data=None):
        send_message(usi_engine, 'quit')
        usi_engine.wait()
        os._exit(0)

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
