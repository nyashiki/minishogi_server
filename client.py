import logging
import os
import simplejson as json
import socketio
import subprocess

def send_message(engine, message, verbose=True):
    if verbose:
        print('>:', message)

    message = (message + '\n').encode('utf-8')
    engine.stdin.write(message)
    engine.stdin.flush()

def receive_message(engine, verbose=True):
    output = b''

    while True:
        read = engine.stdout.read(1)

        if output != b'' and (read == b'' or read == b'\n'):
            break

        output += read

    output = output.decode('utf-8').strip()

    if verbose:
        print("<:", output)

    return output

def main(ip='localhost', port=8000):
    with open('client.json') as f:
        config = json.load(f)

    usi_engine = subprocess.Popen(config['command'].split(), cwd=config['cwd'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    send_message(usi_engine, 'usi')

    engine_info = { }

    while True:
        output = receive_message(usi_engine).split()

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

    @sio.event
    def connect(data=None):
        sio.emit('usi', engine_info)

    @sio.on('error')
    def error(message):
        print('ERROR: {}'.format(message))
        exit(0)

    @sio.on('info')
    def info(message):
        print('INFO: {}'.format(message))

    @sio.on('isready')
    def isready(data):
        send_message(usi_engine, 'isready')

        while True:
            output = receive_message(usi_engine).split()

            if len(output) == 0:
                continue

            if output[0] == 'readyok':
                break

    @sio.on('usinewgame')
    def usinewgame(data):
        send_message(usi_engine, 'usinewgame')

    @sio.on('nextmove')
    def nextmove(data):
        sfen_position = 'position sfen ' + data['position']
        send_message(usi_engine, sfen_position)

        command = 'go btime {} wtime {} byoyomi {}'.format(data['btime'], data['wtime'], data['byoyomi'])
        send_message(usi_engine, command)

        while True:
            output = receive_message(usi_engine).split()

            if len(output) == 0:
                continue

            if output[0] == 'bestmove':
                sio.emit('bestmove', output[1])

    @sio.event
    def disconnect(data=None):
        send_message(usi_engine, 'quit')
        usi_engine.wait()
        os._exit(0)

    url = 'http://{}:{}'.format(ip, port)
    sio.connect(url)
    sio.wait()

if __name__ == '__main__':
    main()
