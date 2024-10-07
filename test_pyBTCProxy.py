from bitcoinproxy.proxy import BTCProxy

print("Testing pyBTCProxy...")

if __name__ == "__main__":
    rpc_proxy = BTCProxy()
    rpc_proxy.start()
    