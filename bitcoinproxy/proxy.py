import json
import random
import aiohttp
import asyncio
import time
import os
import configparser
import threading
import logging
from aiohttp import web, BasicAuth
#from simplecontext.appcontext import *

LOG = logging.getLogger(__name__)

class BTCProxy:

    def __init__(self):
        self.startTime = int(time.time())
        self.background_tasks = set()
        self.taskCounter = 0
        self.requestCounter = 0
        self.downloadBlockHashes = set()
        self.proxyconf = None
        self.session = None

    def start(self):
        #logging.basicConfig(filename='proxy.log', level=logging.DEBUG)
        logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

        LOG.debug('start()')
        main_base = os.path.dirname(__file__)
        proxyconf_file = os.path.join(main_base, "proxy.conf")
        LOG.debug(f"Opening config file " + proxyconf_file)

        _proxyconf = configparser.ConfigParser()
        proxyconf_list = _proxyconf.read(proxyconf_file)

        if (len(proxyconf_list) <1):
            LOG.error("WARN: No entries in config file " + proxyconf_file)
            exit
        
        self.proxyconf = _proxyconf

        serverThread = threading.Thread(target=self.run_server, args=(self.aiohttp_server(),))
        serverThread.start()
    #   x.join()

        statisticThread = threading.Thread(target=self.statistics)
        statisticThread.start()
    #   y.join()
        
    def aiohttp_server(self):
        app = web.Application()
        app.router.add_post('/', self.taskRequestHandler)
        runner = web.AppRunner(app)
        return runner

    def run_server(self, runner):
            LOG.info("Starting proxy server...")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(runner.setup())
            ipadress = self.getCfg('net','listen_ip')
            portnumber = self.getCfg('net', 'listen_port')

            site = web.TCPSite(runner, ipadress, portnumber)
            loop.run_until_complete(site.start())
            LOG.info(f"Proxy is Listening on {ipadress}:{portnumber}")
            loop.run_forever()

    async def taskRequestHandler(self, request):
        requestTask = asyncio.create_task(self._handle(request), name="Task#" + str(self.taskCounter))
        LOG.debug(f"{requestTask.get_name()}: Task created.")
        self.taskCounter += 1
        self.background_tasks.add(requestTask)
        requestTask.add_done_callback(self.background_tasks.discard)
        if not requestTask.cancelled():
            if not requestTask.done():
                LOG.debug(f"{requestTask.get_name()}: Task is not done yet...awaiting...")
                startTime = time.time()
                await requestTask
                stopTime = time.time()
                LOG.debug(f"{requestTask.get_name()}: Task is done, execution took " + str(stopTime-startTime) + "ms.")

            try:
                response = requestTask.result()
            except asyncio.InvalidStateError:
                LOG.error(f"{requestTask.get_name()}: Task is in invalid state!")
            except asyncio.CancelledError:
                LOG.error(f"{requestTask.get_name()}: Task was cancelled!")
            else:
                return response
                

    def statistics(self):
            LOG.info("Starting statistics thread...")
            statisticsTask = asyncio.create_task(self.statsTask(), name="Statistics Task#{self.taskCounter}")
            taskCounter += 1
            self.background_tasks.add(statisticsTask)
            statisticsTask.add_done_callback(background_tasks.discard)

    def statsTask(self):
        while True:
            if self.requestCounter != 0:
                now = int(time.time())
                d = divmod(now - self.startTime, 86400)
                h = divmod(d[1], 3600)
                m = divmod(h[1], 60)
                s = m[1]
                logStr = f"📊 Handled {self.requestCounter} requests in "
                logStr += str('%d days, %d hours, %d minutes, %d seconds. ' % (d[0], h[0], m[0], s))
                logStr += str(len(self.downloadBlockHashes)) + ' blocks were downloaded.'
                LOG.info(logStr)
                time.sleep(1800)
            else:
                logStr = "📊 No requests were forwarded so far."
                LOG.info(logStr)

                time.sleep(180)

    def getCfg(self, sectionName, valueName):
            if not sectionName in self.proxyconf:
                print("BTCProxy WARN: No section '{sectionName} in configuration.' in configuration file found. Was the config file loaded?")
                return None
            if not valueName in self.proxyconf[sectionName]:
                print("BTCProxy WARN: No parameter '{valueName} is configured in configuration.")
                return None
            return self.proxyconf[sectionName][valueName]



    async def handle_request(self, request):
        data = await request.text()
        self.requestCounter += 1
        request_json = json.loads(data)
        method = request_json.get('method', '')
        params = request_json.get('params', [])

        if method != 'gettxout':
            LOG.info(f"-> Incoming request {method} {params}")

        dest_user = self.getCfg('net','dest_user')
        dest_pass = self.getCfg('net','dest_pass')

        async with aiohttp.ClientSession(auth=BasicAuth(dest_user, dest_pass)) as self.session:
            if method == 'getblock':
                fakeParams = [params[0], params[1]]
                try:
                    response = await self.forward_request(self.session, method, fakeParams)
                except Exception as e:
                    LOG.error(f"Error forwarding getblock request: {str(e)}")
                    response = {'error': str(e)}

                responseText = await response.text()
                dictResponse = json.loads(responseText)
                if 'error' in dictResponse and dictResponse['error'] != None:
                    LOG.debug(f"Cannot retrieve block from bitcoind: {dictResponse}")
                    getBlockErrorResponse = await self.handle_getblock_error(self.session, fakeParams, response)
                    responseText = await getBlockErrorResponse.text()
                return web.Response(text=responseText, content_type='application/json')
            else:
                try:
                    response = await self.forward_request(self.session, method, params)
                except Exception as e:
                    LOG.error(f"Error forwarding generic request: {str(e)}")
#                    response = {'error': str(e)}
                responseText = await response.text()
                return web.Response(text=responseText, content_type='application/json')

    async def forward_request(self, session, method, params):
        destipadress = self.getCfg('net','dest_ip')
        destportnumber = self.getCfg('net','dest_port')
        url = f"http://{destipadress}:{destportnumber}"
        LOG.debug(f"Dest URL is {destipadress}:{destportnumber}")


        async with session.post(url, json={"method": method, "params": params}) as response:
            data = await response.text()
            LOG.debug(f"Response for forwarded request: {method}: {data[:200]}...{data[-200:]}")
            return response

    async def handle_getblock_error(self, session, params, errorResponse):
        errorResponseText = await errorResponse.text()
        errorDict = json.loads(errorResponseText)
        errorCode = errorDict['error']['code']
        errorMessage = errorDict['error']['message']
        blockhash = params[0]

        catchErrorCodes = [-5, -1]
        if errorCode not in catchErrorCodes:
            LOG.error(f"Unexpected Error {errorCode}: {errorMessage}")
        else:
            LOG.debug(
                f"Block {blockhash} not found, might have been pruned; select random peer to download from")
            peerInfoResp = await self.forward_request(session, 'getpeerinfo', [])
            peerInfoResponseText = await peerInfoResp.text()
            peerInfoDict = json.loads(peerInfoResponseText)
            if 'result' in peerInfoDict:
                peerEntries = peerInfoDict["result"]
                LOG.debug(f"Got {len(peerEntries)} peerIds")
                if len(peerEntries) == 0:
                    LOG.error("No peers to download from found. Is bitcoind connected to the internet?")
                else:
                    # select random entry
                    randomPeer = random.choice(peerEntries)
                    peer_id = randomPeer.get('id', '')
                    peer_addr = randomPeer.get('addr', '')
                    LOG.debug(f"Block {blockhash} will be downloaded from peer {peer_id} / {peer_addr}")
                    try:
                        getblockfrompeer_result = await self.forward_request(session, 'getblockfrompeer',
                                                                            [blockhash, peer_id])
                    except Exception as e:
                        LOG.error(f"Error calling getblockfrompeer: {str(e)}")
                        getblockfrompeer_result = {'error': str(e)}
                    getBlockFromPeerDict = json.loads(await getblockfrompeer_result.text())
                    LOG.debug(f"getBlockFromPeerDict:  {getBlockFromPeerDict}")

                    if 'error' in getBlockFromPeerDict and getBlockFromPeerDict['error'] != None:
                        errMessage = getBlockFromPeerDict['error']['message']
                        LOG.info(
                            f"🧈 Block ...{blockhash[30:]}: could not initiate download via peer {peer_id}: {errMessage}.")
                    else:
                        LOG.info(
                            f"🧈 Block ...{blockhash[30:]}: download initiated via peer id {peer_id} / {peer_addr}")
                        self.downloadBlockHashes.add(blockhash)

                        if self.waitForDownload:
                            LOG.debug(f"Waiting {self.waitForDownload}s for download...")
                            time.sleep(self.waitForDownload)
                    getBlockResponse = await self.forward_request(session, 'getblock', [blockhash, 0])
                    return getBlockResponse

    async def taskRequestHandler(self, request):
        requestTask = asyncio.create_task(self._handle(request), name="Task#" + str(self.taskCounter))
        LOG.debug(f"{requestTask.get_name()}: Task created.")
        self.taskCounter += 1
        self.background_tasks.add(requestTask)
        requestTask.add_done_callback(self.background_tasks.discard)
        if not requestTask.cancelled():
            if not requestTask.done():
                LOG.debug(f"{requestTask.get_name()}: Task is not done yet...awaiting...")
                startTime = time.time()
                await requestTask
                stopTime = time.time()
                LOG.debug(f"{requestTask.get_name()}: Task is done, execution took " + str(stopTime-startTime) + "ms.")

            try:
                response = requestTask.result()
            except asyncio.InvalidStateError:
                LOG.error(f"{requestTask.get_name()}: Task is in invalid state!")
            except asyncio.CancelledError:
                LOG.error(f"{requestTask.get_name()}: Task was cancelled!")
            else:
                return response
            
    async def _handle(self, request):
            response = await self.handle_request(request)
            return response

    
def main():
    proxy = BTCProxy()
    proxy.start()

if __name__ == "__main__":
    main()
