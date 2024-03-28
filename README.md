# pyBTCProxy
pyBTCProxy is a proxy application that facilitates the operation of Core Lightning (CLN), and potentially other Lightning implementations like lnd or Eclair, alongside a pruned Bitcoin node.

## Attention lnd and Eclair users, please take note of this!
Please be aware that my primary motivation for developing this script was to enable the operation of my Core Lightning (CLN) node alongside a pruned Bitcoin node. Consequently, approximately 99% of the development and testing was conducted using CLN. While I conducted a brief test with an lnd instance, which successfully initialized, connected, and synchronized the network graph through pyBTCProxy as expected, I did not thoroughly investigate how lnd reacts when attempting to retrieve pruned blocks (such as timeouts or retries). I would greatly appreciate any assistance or insights from users who have experience running pyBTCProxy with lnd, Eclair, or any other Lightning implementations. It's important to note that my testing of pyBTCProxy was exclusively conducted with the Bitcoin Core implementation of bitcoind.


## What? Why?
Typically, operating a Lightning node entails running a full Bitcoin node, commonly achieved through a Raspberry Pi setup equipped with a 1 or 2 TB SSD to accommodate the Bitcoin blockchain. However, opting for a virtual private server (VPS) with adequate resources to support the node software is an alternative, often costing just a few dollars per month. Conversely, obtaining approximately 1 TB of storage solely for the Bitcoin blockchain can significantly escalate expenses, exceeding a hundred dollars per month. Most budget-friendly VPS plans offer storage capacities ranging from 40 to 80 GB, sufficient for running a pruned Bitcoin node that retains around 50% (20-40 GB) of the latest blocks.

Theoretically, Core Lightning (CLN) (and lnd) are capable of running with a pruned Bitcoin node, albeit not directly supported out-of-the-box. However, in practice, after opening a few lightning channels, it is common to encounter errors like the following in CLN's log file:

```
2024-03-27T12:28:40.220Z UNUSUAL plugin-bcli: bitcoin-cli -rpcconnect=... -rpcport=... -rpcuser=... -stdinrpcpass getblock 000000000000000000037c083a5da1f3362008a4cdd86e0f231d8956d2a14452 0 exited with status 1
2024-03-27T12:28:41.236Z UNUSUAL plugin-bcli: bitcoin-cli -rpcconnect=... -rpcport=... -rpcuser=... -stdinrpcpass getblock 000000000000000000037c083a5da1f3362008a4cdd86e0f231d8956d2a14452 0 exited with status 1
2024-03-27T12:28:42.254Z UNUSUAL plugin-bcli: bitcoin-cli -rpcconnect=... -rpcport=... -rpcuser=... -stdinrpcpass getblock 000000000000000000037c083a5da1f3362008a4cdd86e0f231d8956d2a14452 0 exited with status 1
2024-03-27T12:28:43.271Z UNUSUAL plugin-bcli: bitcoin-cli -rpcconnect=... -rpcport=... -rpcuser=... -stdinrpcpass getblock 000000000000000000037c083a5da1f3362008a4cdd86e0f231d8956d2a14452 0 exited with status 1
```
These messages will continue to appear repeatedly, signaling that lightningd attempts to fetch a block from bitcoind, which has already been pruned. It retries to download that block every second without success.

pyBTCProxy addresses this issue by serving as a proxy application. It functions by retrieving a block from the internet if it has been pruned. Instead of connecting your lightningd or lnd instance directly to bitcoind, you establish the connection with pyBTCProxy. This intermediary forwards all RPC calls to bitcoind and intercepts 'getblock' calls to perform additional actions, such as initiating the block download when necessary.

Kixunil developed a similar application in Rust, but the project (https://github.com/Kixunil/btc-rpc-proxy) appears to be inactive, and the application ceased functioning some time ago due to interface changes. Since I lack proficiency in Rust to understand and address the issue, I opted to create a similar application in Python.

## Installation

You have two options for acquiring pyBTCProxy. Firstly, you can manually download the pyBTCProxy.py script and create the configuration settings manually. Alternatively, you can clone the repository and utilize the provided sample configuration as follows:

```
git clone https://github.com/martinneustein/pyBTCProxy
cd pyBTCProxy
cp proxy-sample.conf proxy.conf
pip3 install aiohttp configparser (TODO: Check if sufficient)
```

When initiated, pyBTCProxy searches for a proxy.conf file within its current directory. It's essential to configure dest_user and dest_pass in this file, which correspond to the credentials required by bitcoind (available in the bitcoin.conf file of your bitcoind installation). All other configuration parameters are optional. If left unspecified, pyBTCProxy will listen on 127.0.0.1 port 8331 and connect to bitcoind on 127.0.0.1 port 8332, utilizing bitcoind's default values.

## Configuring your lightning daemon
Ensure that your lightning node is configured to connect to pyBTCProxy instead of directly to bitcoind:

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
# pyBTCProxy
bitcoind.rpchost=127.0.0.1:8331
bitcoind.rpcuser=<DOES_NOT_MATTER>
bitcoind.rpcpass=<DOES_NOT_MATTER>
```

rpcuser and rpcpassword can be set to any value since pyBTCProxy does not authenticate incoming requests.

### Running

To start pyBTCProxy, simply execute the following command:

```
python3 pyBTCProxy.py
```

### systemd script

If you wish to start pyBTCProxy during system startup, create a file named /etc/systemd/system/pybtcproxy.service and include the following content:

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

and execute the following commands:

```
systemctl daemon-reload
systemctl enable pybtcproxy.service
```

Log output will go to syslog:

```
journalctl -f -u pybtcproxy -n 20
```

The verbosity of pyBTCProxy depends on the log_level configuration value. Setting it to 'debug' will result in extensive logging, while setting it to 'info' will keep the logging to a minimal.

A typical log output for a successful proxy operation and block download initiation would resemble the following:

```
pyBTCProxy 🧈 Block 00000000000000000001ebc605622d: download initiated via peer id 181 / mxf5qi7dfplca262...szyxllv6qd.onion:8333
pyBTCProxy 🧈 Block 00000000000000000001ebc605622d: download initiated via peer id 937 / 7i555ob2eqx...e2hojz5ibncirid.onion:8333
```

In this scenario, lightningd attempts to retrieve a block three times: The initial two attempts fail, prompting pyBTCProxy to initiate a block download from a random peer connected to bitcoind. During the third attempt, no log output is generated, indicating that the block has been successfully downloaded in the interim and returned to lightningd.

Occasionally pyBTCProxy prints out some stats to tell you it's alive:

```
pyBTCProxy 📊 Handled 300 requests in 0 days, 0 hours, 4 minutes, 16 seconds. 2 block downloads initiated.
```
