# pyBTCProxy
pyBTCProxy is a proxy application to run Core Lightning (CLN) and/or lnd with a pruned Bitcoin node

## lnd users please note this!
Please note that my motivation to write this script was to run my Core Lightning (CLN) node with a pruned Bitcoin node, so 99% of development and testing was done with CLN. I did a quick test run with an lnd instance, which started up, connected and synced the network graph via pyBTCProxy just like normal, but I did not check how lnd reacts if it tries to retrieve a block that was pruned (timeouts, retries etc.). I could need some help here, so please share your experience, if you run pyBTCProxy with lnd. Also, I didn't test pyBTCProxy with other bitcoin or lightning implementations like btcd or eclair.


## What and Why?
Theoretically CLN supports running with a pruned Bitcoin node not out-of-the-box. In reality however, after having openened a handful of lightning channels, it usually does not take very long until error like these start to appear in CLN's log file:

```
2024-03-27T12:28:40.220Z UNUSUAL plugin-bcli: bitcoin-cli -rpcconnect=... -rpcport=... -rpcuser=... -stdinrpcpass getblock 000000000000000000037c083a5da1f3362008a4cdd86e0f231d8956d2a14452 0 exited with status 1
2024-03-27T12:28:41.236Z UNUSUAL plugin-bcli: bitcoin-cli -rpcconnect=... -rpcport=... -rpcuser=... -stdinrpcpass getblock 000000000000000000037c083a5da1f3362008a4cdd86e0f231d8956d2a14452 0 exited with status 1
2024-03-27T12:28:42.254Z UNUSUAL plugin-bcli: bitcoin-cli -rpcconnect=... -rpcport=... -rpcuser=... -stdinrpcpass getblock 000000000000000000037c083a5da1f3362008a4cdd86e0f231d8956d2a14452 0 exited with status 1
2024-03-27T12:28:43.271Z UNUSUAL plugin-bcli: bitcoin-cli -rpcconnect=... -rpcport=... -rpcuser=... -stdinrpcpass getblock 000000000000000000037c083a5da1f3362008a4cdd86e0f231d8956d2a14452 0 exited with status 1
```
These messages will repeat endlessly and indicate that lightningd was trying to retrieve a block from bitcoind, which has already been pruned, and it retries to download that block every second (without success). 

pyBTCProxy works around this by acting as a proxy application, which will download a block from the internet if has already been pruned. Instead of connecting your lightningd or lnd instance to bitcoind, you connect them to pyBTCProxy which basically forwards all RPC calls to bitcoind and intercepts "getblock" calls to do some extra stuff (initiate the block download, if necessary). 

## Installation

You can either download the pyBTCProxy.py script manually and create the configuration by hand, or you can clone the repository and use the sample configuration as follows:

```
git clone https://github.com/martinneustein/pyBTCProxy
cd pyBTCProxy
cp proxy-sample.conf proxy.conf
```

When started, pyBTCProxy looks for a proxy.conf file in its current directory. It is mandatory to set dest_user and dest_pass in this config file, which are the credentials for bitcoind (can be found in bitcoin.conf of your bitcoind installation). All other configuration values are optional and will result in a pyBTCProxy listening on 127.0.0.1 port 8331 and connecting to bitcoind on 127.0.0.1 port 8332 (bitcoind's default values).

## Configuring your lightning daemon
Your lightning node needs to be configured to connect to pyBTCProxy instead of bitcoind.

### lightningd
CLN config (~/.lightning/config):

```
# pyBTCProxy
bitcoin-rpcconnect=127.0.0.1
bitcoin-rpcport=8331
bitcoin-rpcuser=<DOES_NOT_MATTER>
bitcoin-rpcpassword=<DOES_NOT_MATTER>
```

### lnd
lnd config (lnd.conf)

```
bitcoind.rpchost=127.0.0.1:8331
bitcoind.rpcuser=<DOES_NOT_MATTER>
bitcoind.rpcpass=<DOES_NOT_MATTER>
```

rpcuser and rpcpass[word] can be set to any value, as pyBTCProxy does no authenticate incoming requests will ignore them.



