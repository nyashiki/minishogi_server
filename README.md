# Minishogi Server

This program hosts games of [Minishogi](https://en.wikipedia.org/wiki/Minishogi) (a variant of Shogi).

Minishogi engines can be used with client.py via [USI protocol](http://hgm.nubati.net/usi.html).

# Preparation

## install minishogilib

This program is based on [minishogilib](https://github.com/Nyashiki/minishogilib),
so you have to install minishogilib beforehand.

## install requirements

```
pip3 install -r requirements.txt
```

# Usage

## Server
### Command

```bash
python3 server.py --port <PORT> --config <CONFIG>
```

### Config
Default config file is server.json.

The config json file consits of the following:

- btime

    The amount of thinking time of the first player.
- wtime

    The amount of thinking time of the second player.
- byoyomi

    The amount of byo-yomi.
- tournament

    Enable tournament mode. The amount of games that server will play.
- swap_turn

    Only work in tournament mode. Play every position twice, and each player goes sente one time.
- initial_positions

    A list of the initial positions. The game position will start from the first of the list.
    In tournament mode, the positions will be used sequentially.


## Client

### Command
```bash
python3 client.py --ip <TARGET IP> --port <TARGET PORT> --config <CONFIG>
```

*TARGET IP* and *TARGET PORT* are the ip and port of the server.

### Config file
Default config file is client.json.

The config json file consists of the following:

- command

    The command to execute a Minishogi engine.
- cwd

    The working directory of the Minishogi engine.
- option

    The list of USI options.

    These options are sent to the engine via setoption command of USI protocol.

    e.g. ) setoption name UCI_Variant value minishogi
