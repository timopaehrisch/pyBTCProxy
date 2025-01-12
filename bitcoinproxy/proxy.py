import json
import random
import aiohttp
import asyncio
import time
import os
from configparser import ConfigParser
import threading
import logging
from aiohttp import web, BasicAuth, ClientSession
from rich.console import Console
from rich.theme import Theme


class LOGGING:
    def __init__(self) -> None:
        self.custom_theme = Theme(
            {
                "debug": "black",
                "info": "bold cyan",
                "warn": "magenta",
                "error": "bold red",
            }
        )
        self.console = Console(theme=self.custom_theme)

    def debug(self, message: str):
        self.console.print(message, style="debug")

    def info(self, message: str):
        self.console.print(message, style="info")

    def warn(self, message: str):
        self.console.print(message, style="warn")

    def error(self, message: str):
        self.console.print(message, style="error")


LOG = LOGGING()

logging.basicConfig(
    format="%(asctime)s %(levelname)s [pyBTC] %(message)s", level=logging.INFO
)
# LOG = logging.getLogger(__name__)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)


class BTCProxy:
    def __init__(self, configFile="proxy.conf") -> None:
        self.startTime: int = int(time.time())
        self.background_tasks = set()
        self.taskCounter: int = 0
        self.requestCounter: int = 0
        self.downloadBlockHashes = set[int]
        self.conf = None
        self.configFile = configFile

    def start(self) -> None:
        LOG.debug("start()")
        if self.conf is not None:
            LOG.debug("Configuration values already set.")
        else:
            main_base: str = os.path.dirname(__file__)
            configFileFullPath = os.path.join(main_base, self.configFile)
            LOG.info(f"Using config file {configFileFullPath}")
            parser = ConfigParser()
            if not parser.read(configFileFullPath):
                raise FileNotFoundError(f"Config file not found ({configFileFullPath})")
            else:
                parser.read(configFileFullPath)
                self.conf: ConfigParser = parser

        serverThread = threading.Thread(
            target=self.run_server, args=(self.aiohttp_server(),)
        )
        serverThread.start()

        statisticThread = threading.Thread(target=self.statistics)
        statisticThread.start()

    def aiohttp_server(self) -> web.AppRunner:
        app = web.Application()
        app.router.add_post("/", self.taskRequestHandler)
        runner = web.AppRunner(app)
        return runner

    def run_server(self, runner):
        LOG.info("Starting proxy server...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(runner.setup())
        listen_host = self.getCfg("net", "listen_ip")
        listen_portnumber = self.getCfg("net", "listen_port")
        forward_host = self.getCfg("net", "dest_ip")
        forward_portnumber = self.getCfg("net", "dest_port")
        LOG.info(
            f"Proxy is configured to listen on {listen_host}:{listen_portnumber} and forward to {forward_host}:{forward_portnumber}"
        )
        site = web.TCPSite(runner, listen_host, listen_portnumber)
        try:
            loop.run_until_complete(site.start())
        except Exception as err:
            LOG.info(f"Unexpected {err=}, {type(err)=}")
        LOG.info(
            f"Proxy is listening on {listen_host}:{listen_portnumber} and forwarding to {forward_host}:{forward_portnumber}"
        )
        loop.run_forever()

    async def taskRequestHandler(self, request) -> web.Response | None:
        requestTask = asyncio.create_task(
            self._handle(request), name="Task#" + str(self.taskCounter)
        )
        LOG.debug(f"{requestTask.get_name()}: Task created.")
        self.taskCounter += 1
        self.background_tasks.add(requestTask)
        requestTask.add_done_callback(self.background_tasks.discard)
        if not requestTask.cancelled():
            if not requestTask.done():
                LOG.debug(
                    f"{requestTask.get_name()}: Task is not done yet...awaiting..."
                )
                startTime = time.time()
                await requestTask
                stopTime = time.time()
                LOG.debug(
                    f"{requestTask.get_name()}: Task is done, execution took "
                    + str(stopTime - startTime)
                    + "ms."
                )

            try:
                response: web.Response = requestTask.result()
            except asyncio.InvalidStateError:
                LOG.error(f"{requestTask.get_name()}: Task is in invalid state!")
            except asyncio.CancelledError:
                LOG.error(f"{requestTask.get_name()}: Task was cancelled!")
            else:
                return response

    def statistics(self):
        LOG.info("Starting statistics thread...")
        statisticsTask = asyncio.create_task(
            self.statsTask(), name="Statistics Task#{self.taskCounter}"
        )
        self.taskCounter += 1
        self.background_tasks.add(statisticsTask)
        statisticsTask.add_done_callback(self.background_tasks.discard)

    def statsTask(self):
        while True:
            if self.requestCounter != 0:
                now = int(time.time())
                d = divmod(now - self.startTime, 86400)
                h = divmod(d[1], 3600)
                m = divmod(h[1], 60)
                s = m[1]
                logStr = f"📊 Handled {self.requestCounter} requests in "
                logStr += str(
                    "%d days, %d hours, %d minutes, %d seconds. "
                    % (d[0], h[0], m[0], s)
                )
                logStr += (
                    str(len(self.downloadBlockHashes)) + " blocks were downloaded."
                )
                LOG.info(logStr)
                time.sleep(1800)
            else:
                logStr = "📊 No requests were forwarded so far."
                LOG.info(logStr)

                time.sleep(180)

    def getCfg(self, sectionName, valueName) -> str:
        if not self.conf:
            LOG.info("Configuration has not been properly initiated.")
            return ""
        if sectionName  not in self.conf:
            LOG.error(f"No section with name {sectionName} found in configuration.")
            return ""
        if  valueName not in self.conf[sectionName]:
            LOG.error(f"No value with name '{valueName} found in configuration.")
            return ""
        return self.conf[sectionName][valueName]

    async def handle_request(self, request) -> web.Response:
        data = await request.text()
        self.requestCounter += 1
        request_json = json.loads(data)
        method: str = request_json.get("method", "")
        params: str = request_json.get("params", [])
        #        headers = request.headers
        headers = ""
        if method != "gettxout":
            LOG.info(f"-> Incoming request {method} {params} {headers}")
        dest_user: str = self.getCfg("net", "dest_user")
        dest_pass: str = self.getCfg("net", "dest_pass")
        async with aiohttp.ClientSession(
            auth=BasicAuth(dest_user, dest_pass)
        ) as session:
            if method == "getblock":
                callParams: list[str] = [params[0]]
                try:
                    response: web.Response = await self.forward_request(
                        session, method, callParams
                    )
                except Exception as e:
                    LOG.error(f"Error forwarding getblock request: {str(e)}")
                    response: dict[str, str] = {"error": str(e)}

                responseText: str = await response.text()
                #                LOG.info(f"responseText; {responseText}")
                responseJson = await response.json()
                if "error" in responseJson and responseJson["error"] is not None:
                    LOG.info(f"Cannot retrieve block from bitcoind: {responseJson}")
                    getBlockErrorResponse: (
                        web.Response | None
                    ) = await self.handle_getblock_error(session, callParams, response)
                    responseText: str = await getBlockErrorResponse.text()
                    content_type = getBlockErrorResponse.headers["Content-Type"]
                    return web.Response(
                        text=responseText, content_type=content_type, charset="utf-8"
                    )
                else:
                    content_type = response.headers["Content-Type"]
                    #                    return web.Response(text=responseText, content_type=content_type, charset='utf-8')
                    return web.json_response(text=responseText)
            else:
                try:
                    response: web.Response = await self.forward_request(
                        session, method, params
                    )
                except Exception as e:
                    LOG.error(f"Error forwarding generic request: {str(e)}")
                responseText = await response.text()
                #                return web.json_response(await response.json())
                return web.Response(
                    text=responseText, content_type="text/plain", charset="utf-8"
                )

    #                    response = {'error': str(e)}

    async def forward_request(
        self, session: ClientSession, method, params
    ) -> web.Response:
        destipadress: str = self.getCfg("net", "dest_ip")
        destportnumber: str = self.getCfg("net", "dest_port")
        url: str = f"http://{destipadress}:{destportnumber}"
        LOG.debug(f"Dest URL is {destipadress}:{destportnumber}")
        async with session.post(
            url, json={"method": method, "params": params}
        ) as response:
            data: str = await response.text()
            LOG.debug(
                f"Response for forwarded request {method}: {data[:200]}...{data[-200:]}"
            )
            return response

    async def handle_getblock_error(
        self, session: ClientSession, params: tuple[int, int], errorResponse
    ):
        errorResponseText: str = await errorResponse.text()
        errorDict: tuple[str, str] = json.loads(errorResponseText)
        errorCode: int = int(errorDict["error"]["code"])
        errorMessage: str = errorDict["error"]["message"]
        blockhash: int = params[0]

        catchErrorCodes = [-5, -1]
        if errorCode not in catchErrorCodes:
            LOG.error(f"Unexpected Error {errorCode}: {errorMessage}")
        else:
            LOG.debug(
                f"Block {blockhash} not found, might have been pruned; select random peer to download from"
            )
            peerInfoResp: web.Response = await self.forward_request(
                session, "getpeerinfo", []
            )
            peerInfoResponseText: str = await peerInfoResp.text()
            peerInfoDict: tuple[str, str] = json.loads(peerInfoResponseText)
            if "result" in peerInfoDict:
                peerEntries = peerInfoDict["result"]
                LOG.debug(f"Got {len(peerEntries)} peerIds")
                if len(peerEntries) == 0:
                    LOG.error(
                        "No peers to download from found. Is bitcoind connected to the internet?"
                    )
                else:
                    # select random entry
                    randomPeer = random.choice(peerEntries)
                    peer_id = randomPeer.get("id", "")
                    peer_addr = randomPeer.get("addr", "")
                    LOG.debug(
                        f"Block {blockhash} will be downloaded from peer {peer_id} / {peer_addr}"
                    )
                    try:
                        getblockfrompeer_result: web.Response = (
                            await self.forward_request(
                                session, "getblockfrompeer", [blockhash, peer_id]
                            )
                        )
                    except Exception as e:
                        LOG.error(f"Error calling getblockfrompeer: {str(e)}")
                        getblockfrompeer_result = {"error": str(e)}
                    getBlockFromPeerDict = json.loads(
                        await getblockfrompeer_result.text()
                    )
                    LOG.debug(f"getBlockFromPeerDict:  {getBlockFromPeerDict}")

                    if (
                        "error" in getBlockFromPeerDict
                        and getBlockFromPeerDict["error"] is not None
                    ):
                        errMessage = getBlockFromPeerDict["error"]["message"]
                        LOG.info(
                            f"🧈 Block ...{blockhash[30:]}: could not initiate download via peer {peer_id}: {errMessage}."
                        )
                    else:
                        LOG.info(
                            f"🧈 Block ...{blockhash[30:]}: download initiated via peer id {peer_id} / {peer_addr}"
                        )
                        self.downloadBlockHashes.add(blockhash)

                        waitForDownload = int(self.getCfg("app", "wait_for_download"))
                        if waitForDownload:
                            LOG.info(f"Waiting {waitForDownload}s to download block")
                            await asyncio.sleep(waitForDownload)
                    #                            LOG.info(f"Woke up!")
                    # retry getblock and just forward result. If we slept above, the block might have been downloaded in the meantime.
                    LOG.info(f"🧈 Retrying getblock call for block hash {blockhash}")
                    getBlockResponse = await self.forward_request(
                        session, "getblock", [blockhash, 0]
                    )

                    responseText = await getBlockResponse.text()
                    dictRetry = json.loads(responseText)
                    if dictRetry["result"] is not None:
                        LOG.info(f"🧈 Block {blockhash} has now been downloaded.")
                    return getBlockResponse



    async def _handle(self, request) -> web.Response:
        response: web.Response = await self.handle_request(request)
        return response


# def main():
#    proxy = BTCProxy()
#    proxy.start()

# if __name__ == "__main__":
#    main()
