#!/bin/sh
#% SYNOPSIS
#+    ${SCRIPT_NAME} [pair_count]
#%
#% DESCRIPTION
#%    Execute multiple pairs of clients
#%
#%    [pair_count]     the number of pairs of clients will be executed

for ((i=0;i<$1;i++)); do
    python3.7 client.py --config client1.json > /dev/null &
    sleep 0.3
    python3.7 client.py --config client2.json > /dev/null &
    sleep 0.3
done