from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import uuid

class Game:
    def __init__(self):
        self.position = None

        # Time limit
        self.timelimit = [0 for _ in range(2)]
        self.byoyomi = 0

        # Clients
        self.clients = []

# Global game object
game = Game()

class Client:
    def __init__(self):
        self.id = None

class Hander(BaseHTTPRequestHandler):
    def do_GET(self):
        self.wfile.write(b'Position, kif and something will be here.')

    def do_POST(self):
        global game

        if self.path == '/match':
            length = self.headers.get('content-length')

            if length is not None:
                nbytes = int(length)
                post_data = self.rfile.read(nbytes)
                post_data = post_data.decode('utf-8')
                post_data = urllib.parse.parse_qs(post_data)

                if len(game.clients) >= 2:
                    self.send_response(406)
                    self.send_header('Content_Type', 'text/plain; charset=utf-8')
                    self.end_headers()
                    self.wfile.write('The game is already held.'.encode('utf-8'))
                    return

                if not 'name' in post_data:
                    self.send_response(406)
                    self.send_header('Content_Type', 'text/plain; charset=utf-8')
                    self.end_headers()
                    self.wfile.write('You send a request but name field is None.'.encode('utf-8'))
                    return

                if not 'author' in post_data:
                    self.send_response(406)
                    self.send_header('Content_Type', 'text/plain; charset=utf-8')
                    self.end_headers()
                    self.wfile.write('You send a request but author field is None.'.encode('utf-8'))
                    return

                self.send_response(200)
                self.send_header('Content_Type', 'text/plain; charset=utf-8')
                self.end_headers()

                client = Client()
                client.id = str(uuid.uuid4())
                game.clients.append(client)

                print(game.clients)

                self.wfile.write(client.id.encode('utf-8'))

def main(port=8000):
    server_address = ('localhost', port)
    httpd = HTTPServer(server_address, Hander)
    httpd.serve_forever()

if __name__ == '__main__':
    main()
