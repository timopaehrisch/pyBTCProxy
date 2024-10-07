import configparser
import logging
import time
import asyncio


__all__ = [
    'ctx',
    'BTCProxyContext',
    'LOG'
]

class BTCProxyContext:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BTCProxyContext, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.initialize()

    def initialize(self):
        # load config and/or set default values
        _conf = configparser.ConfigParser()
        _conf.read('/Users/timopahrisch/Library/Python/3.11/lib/python/site-packages/bitcoinproxy/proxy.conf')

        if not 'net' in _conf:
            print("WARN: No 'net' section in config values. Was the config file loaded?")
            _conf['net'] = {}

        if not 'listen_ip' in _conf['net']:
            _conf['net']['listen_ip'] = '127.0.0.1'
        if not 'listen_port' in _conf['net']:
            _conf['net']['listen_port'] = '8331'
        if not 'dest_ip' in _conf['net']:
            _conf['net']['dest_ip'] = '127.0.0.1'
        if not 'dest_port' in _conf['net']:
            _conf['net']['dest_port'] = '8332'
        if not 'dest_user' in _conf['net']:
            print("You have to provide an RPC user in proxy.conf")
            exit
        if not 'dest_pass' in _conf['net']:
            print("You have to provide an RPC password in proxy.conf")
            exit

        logFormatter = logging.Formatter(fmt=' %(name)s %(message)s')
        consoleHandler = logging.StreamHandler()
        consoleHandler.setLevel(logging.INFO)
        consoleHandler.setFormatter(logFormatter)
        logger = logging.getLogger('pyBTCProxy')

        if not 'app' in _conf:
            _conf['app'] = {}

        logging.basicConfig(level=logging.INFO)
        if 'log_level' in _conf['app'] and str(_conf['app']['log_level']).lower() == 'debug':
            consoleHandler.setLevel(logging.DEBUG)
        logger.handlers.clear()
        logger.addHandler(consoleHandler)
        logger.propagate = False

        # noisy aiohttp
        logging.getLogger('aiohttp').setLevel(logging.WARNING)

        if not 'wait_for_download' in _conf['app']:
            _conf['app']['wait_for_download'] = '0'

        self.config = _conf
        self.logger = logger
        self.startTime = int(time.time())
        self.downloadBlockHashes = set()
        self.requestCounter = 0
        self.background_tasks = set()
        self.taskCounter = 0

       # initialize statistics task
        asyncio.run(self._runStatsTask())

        logger.info("Context initialized.")

    async def _runStatsTask(self):
        statisticsTask = asyncio.create_task(self.statsTask(), name="Statistics Task#{self.taskCounter}")
        self.taskCounter += 1
        self.background_tasks.add(statisticsTask)
        statisticsTask.add_done_callback(self.background_tasks.discard)

    async def statsTask(self):
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
                self.logger.info(logStr)
            await asyncio.sleep(1800)

    def getConfigValue(self, section, key):
        if isinstance(ctx.config[section][key], str):
            return ctx.config[section][key]
        LOG.error(f"config or config value {section}:{key} is not defined.")

ctx = BTCProxyContext()
LOG = ctx.logger
