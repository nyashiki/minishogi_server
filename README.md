# Minishogi Server

This is an minishogi server program.

Two clients connect to the server and a match will be held.

# Usage

## Server

```bash
python3 server.py --port <PORT>
```

## Client

```bash
python3 client.py --ip <TARGET IP> --port <TARGET PORT>
```

## Watch the game

The server uses HTTP protocol and you can watch the game through your browser.

To watch the game, type following URL.

```
http://<TARGET IP>:<TARGET PORT>
```
