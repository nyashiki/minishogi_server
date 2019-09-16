# Minishogi Server

This program hosts games of Minishogi (a variant of Shogi).

Minishogi engines can be used with client.py via [USI protocol](http://hgm.nubati.net/usi.html).

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


## Client

### Command
```bash
python3 client.py --ip <TARGET IP> --port <TARGET PORT> --config <CONFIG>
```

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
