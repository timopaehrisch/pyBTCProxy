#from bitcoinproxy.proxy import BTCProxy
import bitcoinproxy.proxy

#import asyncio

#runner = asyncio.Runner()
#runner.run(self._runWebApp())
#runner.run(self.statistics())
#runner.close()

bitcoinproxy.proxy.start()



#rpc_proxy = BTCProxy()
#rpc_proxy.start()
#rpc_proxy.statistics()

#asyncio.run(rpc_proxy.start())
#asyncio.run(rpc.proxy.statistics())