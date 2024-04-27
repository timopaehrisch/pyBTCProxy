import json
import random
import aiohttp
import asyncio
import time
from aiohttp import web, BasicAuth
from .context import *

class BTCProxy:

    async def handle_request(self, request):
        data = await request.text()
        ctx.requestCounter += 1
        request_json = json.loads(data)
        method = request_json.get('method', '')
        params = request_json.get('params', [])

        if method != 'gettxout':
            LOG.debug(f"-> Incoming request {method} {params}")

        dest_user = ctx.getConfigValue('net','dest_user')
        dest_pass = ctx.getConfigValue('net','dest_pass')

        if method == 'getblock':
            async with aiohttp.ClientSession(auth=BasicAuth(dest_user, dest_pass)) as session:
                fakeParams = [params[0], params[1]]
                try:
                    response = await self.forward_request(session, method, fakeParams)
                except Exception as e:
                    LOG.error(f"Error forwarding getblock request: {str(e)}")
                    response = {'error': str(e)}

                responseText = await response.text()
                dictResponse = json.loads(responseText)
                if 'error' in dictResponse and dictResponse['error'] != None:
                    LOG.debug(f"Cannot retrieve block from bitcoind: {dictResponse}")
                    getBlockErrorResponse = await self.handle_getblock_error(session, fakeParams, response)
                    responseText = await getBlockErrorResponse.text()
                return web.Response(text=responseText, content_type='application/json')

        async with aiohttp.ClientSession(auth=BasicAuth(dest_user, dest_pass)) as session:
            try:
                response = await self.forward_request(session, method, params)
            except Exception as e:
                LOG.error(f"Error forwarding generic request: {str(e)}")
                response = {'error': str(e)}
            responseText = await response.text()
            return web.Response(text=responseText, content_type='application/json')

    async def forward_request(self, session, method, params):
        destipadress = ctx.getConfigValue('net','dest_ip')
        destportnumber = ctx.getConfigValue('net','dest_port')
        url = f"http://{destipadress}:{destportnumber}"

        async with session.post(url, json={"method": method, "params": params}) as response:
            data = await response.text()
            LOG.debug(f"Response from forward_request: {method}: {data}")
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


    def start(self):
        asyncio.run(self._runWebApp())

    async def _runWebApp(self):
        app = web.Application()
        app.router.add_post('/', self.taskRequestHandler)
        ipadress = ctx.getConfigValue('net','listen_ip')
        portnumber = ctx.getConfigValue('net', 'listen_port')
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, ipadress, portnumber)
        await site.start()
        LOG.info(f"Listening on {ipadress}:{portnumber}")
        await asyncio.Event().wait()  # Wait forever

    async def taskRequestHandler(self, request):
        requestTask = asyncio.create_task(self._handle(request), name="Request Task#" + str(ctx.taskCounter))
        ctx.taskCounter += 1
        ctx.background_tasks.add(requestTask)
        requestTask.add_done_callback(ctx.background_tasks.discard)
        if not requestTask.cancelled():
            if not requestTask.done():
                LOG.debug(f"{requestTask.get_name()}: Task is not done yet...awaiting...")
                await requestTask
                LOG.debug(f"{requestTask.get_name()}: Task is done.")

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
