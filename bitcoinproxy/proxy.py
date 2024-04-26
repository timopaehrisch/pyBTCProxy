import json
import random
import aiohttp
import logging 
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
            log().info(f"-> Incoming request {method} {params}")

        dest_user = getConfigValue('net','dest_user')
        dest_pass = getConfigValue('net','dest_pass')

        if method == 'getblock':
            async with aiohttp.ClientSession(auth=BasicAuth(dest_user, dest_pass)) as session:
                fakeParams = [params[0], params[1]]
                try:
                    response = await self.forward_request(session, method, fakeParams)
                except Exception as e:
                    log().error(f"Error forwarding getblock request: {str(e)}")
                    response = {'error': str(e)}

                responseText = await response.text()
                dictResponse = json.loads(responseText)
                if 'error' in dictResponse and dictResponse['error'] != None:
                    log().debug(f"Cannot retrieve block from bitcoind: {dictResponse}")
                    getBlockErrorResponse = await self.handle_getblock_error(session, fakeParams, response)
                    responseText = await getBlockErrorResponse.text()
                return web.Response(text=responseText, content_type='application/json')

        async with aiohttp.ClientSession(auth=BasicAuth(dest_user, dest_pass)) as session:
            try:
                response = await self.forward_request(session, method, params)
            except Exception as e:
                log().error(f"Error forwarding generic request: {str(e)}")
                response = {'error': str(e)}
            responseText = await response.text()
            return web.Response(text=responseText, content_type='application/json')

    async def forward_request(self, session, method, params):
        destipadress = getConfigValue('net','dest_ip')
        destportnumber = getConfigValue('net','dest_port')
        url = f"http://{destipadress}:{destportnumber}"

        async with session.post(url, json={"method": method, "params": params}) as response:
            data = await response.text()
            log().debug(f"Response from forward_request: {method}: {data}")
            return response

    async def handle_getblock_error(self, session, params, errorResponse):
        errorResponseText = await errorResponse.text()
        errorDict = json.loads(errorResponseText)
        errorCode = errorDict['error']['code']
        errorMessage = errorDict['error']['message']
        blockhash = params[0]

        catchErrorCodes = [-5, -1]
        if errorCode not in catchErrorCodes:
            log().error(f"Unexpected Error {errorCode}: {errorMessage}")
        else:
            log().debug(
                f"Block {blockhash} not found, might have been pruned; select random peer to download from")
            peerInfoResp = await self.forward_request(session, 'getpeerinfo', [])
            peerInfoResponseText = await peerInfoResp.text()
            peerInfoDict = json.loads(peerInfoResponseText)
            if 'result' in peerInfoDict:
                peerEntries = peerInfoDict["result"]
                log().debug(f"Got {len(peerEntries)} peerIds")
                if len(peerEntries) == 0:
                    log().error("No peers to download from found. Is bitcoind connected to the internet?")
                else:
                    # select random entry
                    randomPeer = random.choice(peerEntries)
                    peer_id = randomPeer.get('id', '')
                    peer_addr = randomPeer.get('addr', '')
                    log().debug(f"Block {blockhash} will be downloaded from peer {peer_id} / {peer_addr}")
                    try:
                        getblockfrompeer_result = await self.forward_request(session, 'getblockfrompeer',
                                                                             [blockhash, peer_id])
                    except Exception as e:
                        log().error(f"Error calling getblockfrompeer: {str(e)}")
                        getblockfrompeer_result = {'error': str(e)}
                    getBlockFromPeerDict = json.loads(await getblockfrompeer_result.text())
                    log().debug(f"getBlockFromPeerDict:  {getBlockFromPeerDict}")

                    if 'error' in getBlockFromPeerDict and getBlockFromPeerDict['error'] != None:
                        errMessage = getBlockFromPeerDict['error']['message']
                        log().info(
                            f"🧈 Block ...{blockhash[30:]}: could not initiate download via peer {peer_id}: {errMessage}.")
                    else:
                        log().info(
                            f"🧈 Block ...{blockhash[30:]}: download initiated via peer id {peer_id} / {peer_addr}")
                        self.downloadBlockHashes.add(blockhash)

                        if self.waitForDownload:
                            log().debug(f"Waiting {self.waitForDownload}s for download...")
                            time.sleep(self.waitForDownload)
                    getBlockResponse = await self.forward_request(session, 'getblock', [blockhash, 0])
                    return getBlockResponse

    async def statsLoop(self):
        while True:
            now = int(time.time())
            d = divmod(now - ctx.startTime, 86400)
            h = divmod(d[1], 3600)
            m = divmod(h[1], 60)
            s = m[1]
            logStr = f"📊 Handled {ctx.requestCounter} requests in "
            logStr += str('%d days, %d hours, %d minutes, %d seconds. ' % (d[0], h[0], m[0], s))
            logStr += str(len(ctx.downloadBlockHashes)) + ' blocks were downloaded.'
            if ctx.requestCounter != 0:
                log().info(logStr)
            await asyncio.sleep(1800)

    def start(self):
#        asyncio.run(self._start(), debug=True)
    
#    def _start(self):
        app = web.Application()
        app.router.add_post('/', self.handle_request)

        ipadress = getConfigValue('net','listen_ip')
        portnumber = getConfigValue('net', 'listen_port')

        # Start the event loop
        asyncio.run(self._run_server(app, ipadress, portnumber), debug=True)

    async def _run_server(self, app, ipadress, portnumber):
        # Start statsLoop asynchronously
        log().info(f"Created task Task#{ctx.taskCounter}")
        task = asyncio.create_task(self.statsLoop(), name="Statistics Task#{ctx.taskCounter}")
        ctx.taskCounter += 1
        ctx.background_tasks.add(task)
        task.add_done_callback(ctx.background_tasks.discard)


        # Run the web server
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, ipadress, portnumber)
        await site.start()
        log().info(f"Listening on {ipadress}:{portnumber}.bitcoinproxy/context.py")
        await asyncio.Event().wait()  # Wait forever
