import simplejson as json
import socketio
import subprocess

def main(ip='localhost', port=8000):
    with open('client.json') as f:
        config = json.load(f)

    usi_engine = subprocess.Popen(config['command'].split(), cwd=config['cwd'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    usi_engine.stdin.write(b'usi\n')
    usi_engine.stdin.flush()

    engine_info = { }

    while True:
        output = usi_engine.stdout.readline()
        output = output.decode('utf-8').split()

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
    def connect():
        sio.emit('usi', engine_info)

    @sio.on('error')
    def error(message):
        print('ERROR: {}'.format(message))
        exit(0)

    @sio.on('info')
    def info(message):
        print('INFO: {}'.format(message))

    @sio.on('nextmove')
    def nextmove(data):
        sfen_position = 'position sfen ' + data['position'] + '\n'

        usi_engine.stdin.write(sfen_position.encode('utf-8'))
        usi_engine.stdin.flush()

        command = 'go btime {} wtime {} byoyomi {}\n'.format(data['btime'], data['wtime'], data['byoyomi'])
        usi_engine.stdin.write(command.encode('utf-8'))
        usi_engine.stdin.flush()

        while True:
            output = usi_engine.stdout.readline()
            output = output.decode('utf-8').split()

            if len(output) > 0 and output[0] == 'bestmove':
                sio.emit('bestmove', output[1])

    @sio.event
    def disconnect():
        print('disconnected from server')

    url = 'http://{}:{}'.format(ip, port)
    sio.connect(url)
    sio.wait()

if __name__ == '__main__':
    main()
