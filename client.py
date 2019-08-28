import socketio

def main(ip='localhost', port=8000):
    sio = socketio.Client()

    @sio.event
    def connect():
        sio.emit('usi', {'name': 'name', 'author': 'author'})

    @sio.on('error')
    def error(message):
        print('ERROR: {}'.format(message))
        exit(0)

    @sio.on('info')
    def info(message):
        print('INFO: {}'.format(message))

    @sio.on('position')
    def position(sfen_position):
        # Send position command to the process
        pass

    @sio.on('go')
    def go(command):
        # Send go command to the process
        pass

    @sio.event
    def disconnect():
        print('disconnected from server')

    url = 'http://{}:{}'.format(ip, port)
    sio.connect(url)
    sio.wait()

if __name__ == '__main__':
    main()
