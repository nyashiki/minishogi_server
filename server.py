from http.server import BaseHTTPRequestHandler, HTTPServer

class Hander(BaseHTTPRequestHandler):
    def do_GET(self):
        # ToDo
        pass

    def do_POST(self):
        # ToDo
        pass


def main(port=8000):
    server_address = ('localhost', port)
    httpd = HTTPServer(server_address, Hander)
    httpd.serve_forever()

if __name__ == '__main__':
    main()
