import json
import random
import aiohttp
import logging
import time
import configparser 
from aiohttp import web, BasicAuth


class pyBTCProxy:
    def __init__(self):
        self.logger = logging.getLogger('pyBTCProxy')
        self.waitForDownload = 0
        self.config = None
        self.requestCounter = 0
        self.startTime = int(time.time())
        self.downloadBlockHashes = set()

    async def handle_request(self, request):
        data = await request.text()
        self.requestCounter += 1
        if ((self.requestCounter < 100 and self.requestCounter % 10 == 0) or self.requestCounter % 1009 == 0):
            self.logger.info(f"📊 Handled {self.requestCounter} requests in " + self.getStatsString())

        request_json = json.loads(data)
        method = request_json.get('method', '')
        params = request_json.get('params', [])

        # filter out gettxout
        if method != "gettxout":
            self.logger.debug(f"-> Incoming request {method} {params}")

        dest_user = self.config['net']['dest_user']
        dest_pass = self.config['net']['dest_pass']
        
        if method == 'getblock':
            async with aiohttp.ClientSession(auth=BasicAuth(dest_user, dest_pass)) as session:
                fakeParams = [params[0], params[1]]
                try:
                    response = await self.forward_request(session, method, fakeParams)
                except Exception as e:
                    self.logger.error(f"Error forwarding getblock request: {str(e)}")
                    response = {'error': str(e)}


                responseText = await response.text()
                dictResponse = json.loads(responseText)
                if 'error' in dictResponse and dictResponse['error'] != None:
                    self.logger.debug(f"Cannot retrieve block from bitcoind: {dictResponse}")
                    getBlockErrorResponse = await self.handle_getblock_error(session, fakeParams, response)
                    responseText = await getBlockErrorResponse.text()
                return web.Response(text=responseText)


        async with aiohttp.ClientSession(auth=BasicAuth(dest_user, dest_pass)) as session:
 
            try:
                response = await self.forward_request(session, method, params)
            except Exception as e:
                self.logger.error(f"Error forwarding generic request: {str(e)}")
                response = {'error': str(e)}
            responseText = await response.text()
            return web.Response(text=responseText, content_type='application/json')

    async def forward_request(self, session, method, params):
        destipadress = self.config['net']['dest_ip']
        destportnumber = self.config.getint('net', 'dest_port')
        url = f"http://{destipadress}:{destportnumber}"

        async with session.post(url, json={"method": method, "params": params}) as response:
            data = await response.text()
            self.logger.debug(f"Response from forward_request: {method}: {data}")
            return response
        
    async def handle_getblock_error(self, session, params, errorResponse):
        errorResponseText = await errorResponse.text()
        errorDict = json.loads(errorResponseText)
        errorCode = errorDict['error']['code']
        errorMessage = errorDict['error']['message']
        blockhash = params[0]

        catchErrorCodes = [-5, -1]
        if errorCode not in catchErrorCodes:
            self.logger.error(f"Unexpected Error {errorCode}: {errorMessage}")
        else:
            self.logger.debug(f"Block {blockhash} not found, might have been pruned; select random peer to download from")
            peerInfoResp = await self.forward_request(session, 'getpeerinfo', [])
            peerInfoResponseText = await peerInfoResp.text()
            peerInfoDict = json.loads(peerInfoResponseText)
            if 'result' in peerInfoDict:
                peerEntries = peerInfoDict["result"]
                self.logger.debug(f"Got {len(peerEntries)} peerIds")
                if len(peerEntries) == 0:
                    self.logger.error("No peers to download from found. Is bitcoind connected to the internet?")
                else:
                    # select random entry
                    randomPeer = random.choice(peerEntries)
                    peer_id = randomPeer.get('id', '')
                    peer_addr = randomPeer.get('addr', '')
                    self.logger.debug(f"Block {blockhash} will be downloaded from peer {peer_id} / {peer_addr}")
                    try:
                        getblockfrompeer_result = await self.forward_request(session, 'getblockfrompeer', [blockhash, peer_id])
                    except Exception as e:
                        self.logger.error(f"Error calling getblockfrompeer: {str(e)}")
                        getblockfrompeer_result = {'error': str(e)}
                    getBlockFromPeerDict = json.loads(await getblockfrompeer_result.text())
                    self.logger.debug(f"getBlockFromPeerDict:  {getBlockFromPeerDict}")

                    if 'error' in getBlockFromPeerDict and getBlockFromPeerDict['error'] != None:
                        errMessage = getBlockFromPeerDict['error']['message']
                        self.logger.info(f"🧈 Block ...{blockhash[30:]}: could not initiate download via peer {peer_id}: {errMessage}.")
                    else:
                        self.logger.info(f"🧈 Block ...{blockhash[30:]}: download initiated via peer id {peer_id} / {peer_addr}")
                        self.downloadBlockHashes.add(blockhash)

                        if self.waitForDownload:
                            self.logger.debug(f"Waiting {self.waitForDownload}s for download...")
                            time.sleep(self.waitForDownload)
                    getBlockResponse = await self.forward_request(session, 'getblock', [blockhash, 0])
                    return getBlockResponse

    def start(self):
        app = web.Application()
        app.router.add_post('/', self.handle_request)
        self.initConfig()
        ipadress = self.config['net']['listen_ip']
        portnumber = self.config.getint('net', 'listen_port')
        web.run_app(app, host=ipadress, port=portnumber)


    def initConfig(self):
        configuration = configparser.ConfigParser()
        configuration.read('proxy.conf')

        # Section [net]
        if not isinstance(configuration['net']['listen_ip'], str):
            configuration['net']['listen_ip'] = '127.0.0.1'
        if not isinstance(configuration['net']['listen_port'], str):
            configuration['net']['listen_port'] = '8331'
        if not isinstance(configuration['net']['dest_ip'], str):
            configuration['net']['dest_ip'] = '127.0.0.1'
        if not isinstance(configuration['net']['dest_port'], str):
            configuration['net']['dest_port'] = '8332'
        if not isinstance(configuration['net']['dest_user'], str):
            print("You have to provide an RPC user in proxy.conf")
            exit
        if not isinstance(configuration['net']['dest_pass'], str):
            print("You have to provide an RPC password in proxy.conf")
            exit

        # Section [app]
        logging.basicConfig(level=logging.INFO)

        logFormatter = logging.Formatter(fmt=' %(name)s %(message)s')
        consoleHandler = logging.StreamHandler()
        consoleHandler.setLevel(logging.INFO)
        consoleHandler.setFormatter(logFormatter)
        logger = logging.getLogger('pyBTCProxy')
 
        if isinstance(configuration['app']['log_level'], str) and str(configuration['app']['log_level']).lower() == 'debug':
            consoleHandler.setLevel(logging.DEBUG)
        logger.handlers.clear()
        logger.addHandler(consoleHandler)
        logger.propagate = False

        # noisy aiohttp
        logging.getLogger('aiohttp').setLevel(logging.WARNING)

        if isinstance(configuration['app']['wait_for_download'], str):
            self.waitForDownload = configuration.getint('app','wait_for_download')
        
        self.config = configuration

    def getStatsString(self):
        now = int(time.time())
        d = divmod(now-self.startTime,86400)
        h = divmod(d[1],3600)
        m = divmod(h[1],60)
        s = m[1]
        runStr = str('%d days, %d hours, %d minutes, %d seconds. ' % (d[0],h[0],m[0],s))
        runStr += str(len(self.downloadBlockHashes)) + ' block downloads initiated.'
        return runStr


if __name__ == "__main__":
    rpc_proxy = pyBTCProxy()
    rpc_proxy.start()
