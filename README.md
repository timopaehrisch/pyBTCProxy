# pyBTCProxy
pyBTCProxy is a proxy application which allows Core Lightning (CLN, and possibly lnd, eclair or other Lightning implementations) to run with a pruned Bitcoin node.

## lnd and eclair users please read this!
Please note that my motivation to write this script was to run my Core Lightning (CLN) node with a pruned Bitcoin node, so 99% of development and testing was done with CLN. I did a quick test run with an lnd instance, which started up, connected and synced the network graph via pyBTCProxy just like normal, but I did not check how lnd reacts when it tries to retrieve a block that has been pruned (timeouts, retries etc.). I could need some help here, so please share your experience, if you run pyBTCProxy with lnd, eclair or anything else. I only tested pyBTCProxy with the Bitcoin Core implementation of bitcoind. 


## What and Why?
Usually running a Lightning node also requires to run a full Bitcoin node, which in a typical home setup is a Raspberry Pi with a 1 or 2 TB SSD to store the Bitcoin blockchain. While a VPS (virtual private server) with sufficient resources to run the node software is available for a couple of dollars per month, buying ~ 1 TB storage for the Bitcoin blockchain pushes prices quickly beyond a hundred dollars per month. The cheapest VPS usually come with 40 to 80 GB storage space, which would be enough to run a pruned Bitcoin node that keeps for instance 50% (20-40 GB) of the latest blocks.

Theoretically CLN (and lnd) support running with a pruned Bitcoin node not out-of-the-box. In reality however, after having openened a handful of lightning channels, it usually does not take very long until error like these start to appear in CLN's log file:

```
2024-03-27T12:28:40.220Z UNUSUAL plugin-bcli: bitcoin-cli -rpcconnect=... -rpcport=... -rpcuser=... -stdinrpcpass getblock 000000000000000000037c083a5da1f3362008a4cdd86e0f231d8956d2a14452 0 exited with status 1
2024-03-27T12:28:41.236Z UNUSUAL plugin-bcli: bitcoin-cli -rpcconnect=... -rpcport=... -rpcuser=... -stdinrpcpass getblock 000000000000000000037c083a5da1f3362008a4cdd86e0f231d8956d2a14452 0 exited with status 1
2024-03-27T12:28:42.254Z UNUSUAL plugin-bcli: bitcoin-cli -rpcconnect=... -rpcport=... -rpcuser=... -stdinrpcpass getblock 000000000000000000037c083a5da1f3362008a4cdd86e0f231d8956d2a14452 0 exited with status 1
2024-03-27T12:28:43.271Z UNUSUAL plugin-bcli: bitcoin-cli -rpcconnect=... -rpcport=... -rpcuser=... -stdinrpcpass getblock 000000000000000000037c083a5da1f3362008a4cdd86e0f231d8956d2a14452 0 exited with status 1
```
These messages will repeat endlessly and indicate that lightningd tries to retrieve a block from bitcoind, which has already been pruned, and it retries to download that block every second without success. 

pyBTCProxy works around this by acting as a proxy application, which will download a block from the internet if has already been pruned. Instead of connecting your lightningd or lnd instance to bitcoind, you connect it to pyBTCProxy which basically forwards all RPC calls to bitcoind and intercepts "getblock" calls to do some extra stuff (initiate the block download, if necessary). 

Kixunil wrote a similar app in Rust, but the project (https://github.com/Kixunil/btc-rpc-proxy) seems dead and the application stopped working a while ago due to interface changes. As I don't speak enough Rust to understand and fix it, I simply wrote a similar app in Python. 

## Installation

You can either download the pyBTCProxy.py script manually and create the configuration by hand, or you can clone the repository and use the sample configuration as follows:

```
git clone https://github.com/martinneustein/pyBTCProxy
cd pyBTCProxy
cp proxy-sample.conf proxy.conf
pip3 install aiohttp configparser (TODO: Check if sufficient)
```

When started, pyBTCProxy looks for a proxy.conf file in its current directory. It is mandatory to set dest_user and dest_pass in this config file, which are the credentials for bitcoind (can be found in bitcoin.conf of your bitcoind installation). All other configuration values are optional and will result in a pyBTCProxy listening on 127.0.0.1 port 8331 and connecting to bitcoind on 127.0.0.1 port 8332 (bitcoind's default values).

## Configuring your lightning daemon
Your lightning node needs to be configured to connect to pyBTCProxy instead of bitcoind.

### lightningd
CLN config (usually in ~/.lightning/config):

```
# pyBTCProxy
bitcoin-rpcconnect=127.0.0.1
bitcoin-rpcport=8331
bitcoin-rpcuser=<DOES_NOT_MATTER>
bitcoin-rpcpassword=<DOES_NOT_MATTER>
```

### lnd
lnd config (usually in ~/.lnd/lnd.conf)

```
bitcoind.rpchost=127.0.0.1:8331
bitcoind.rpcuser=<DOES_NOT_MATTER>
bitcoind.rpcpass=<DOES_NOT_MATTER>
```

rpcuser and rpcpass[word] can be set to any value, as pyBTCProxy does no authenticate incoming requests.


### Running

You can start pyBTCProxy by running

```
python3 pyBTCProxy.py
```

### systemd script

If you want to start pyRPCProxy during system startup, create ```/etc/systemd/system/pybtcproxy.service``` with the following content:

```
[Unit]
Description=pyBTCProxy Bitcoin RPC Proxy
After=bitcoind.service

[Service]
WorkingDirectory=/path/to/pyBTCProxy
ExecStart=python3 /path/to/pyBTCProxy

User=bitcoin
Group=bitcoin
Type=simple

[Install]
WantedBy=multi-user.target
```

and initialize during startup (Ubuntu):

```
systemctl daemon-reload
systemctl enable pybtcproxy.service
```

Log output will go to syslog:

```
journalctl -f -u pybtcproxy -n 20
```

Depending on the log_level configuration value pyBTCProxy will be either pretty noisy on 'debug' or very quiet on 'info'.

A typical log output for a successful proxy operation/block download initiation would look like this (log_level = info):

```
Mar 24 00:07:13 localhost python3[935646]: INFO:RpcProxy:🐙 Block 0000000000000000000228aea9b002ee968f2a7e560a448530c33488d8f50b3d Download initiated from peer 596 / lnw64dqngd....ru72vtyd.onion:8333
Mar 24 00:07:14 localhost python3[935646]: INFO:RpcProxy:🎯 Block 0000000000000000000228aea9b002ee968f2a7e560a448530c33488d8f50b3d Download initiated from peer 339 / 24.x.y.3:8333
```

Here, lightningd tries to retrieve a block three times: The first two tries fail and pyBTCProxy initiates a block download from a random peer bitcoind is connected to. The third try does not produce any log output, as the block has been downloaded in the meantime and was successfully returned to lightningd.
