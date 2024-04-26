import configparser
import logging
import time

__all__ = [
    'ctx',
    'getConfigValue',
    'log',
    'BTCProxyContext',
]

def log():
    return ctx.logger

def getConfigValue(section, key):
    if isinstance(ctx.config[section][key], str):
        return ctx.config[section][key]
    print(f"config or config value {section}:{key} is not defined.")

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
        _conf.read('proxy.conf')

        # Section [net]
        if not isinstance(_conf['net']['listen_ip'], str):
            _conf['net']['listen_ip'] = '127.0.0.1'
        if not isinstance(_conf['net']['listen_port'], str):
            _conf['net']['listen_port'] = '8331'
        if not isinstance(_conf['net']['dest_ip'], str):
            _conf['net']['dest_ip'] = '127.0.0.1'
        if not isinstance(_conf['net']['dest_port'], str):
            _conf['net']['dest_port'] = '8332'
        if not isinstance(_conf['net']['dest_user'], str):
            print("You have to provide an RPC user in proxy.conf")
            exit
        if not isinstance(_conf['net']['dest_pass'], str):
            print("You have to provide an RPC password in proxy.conf")
            exit

        logging.basicConfig(level=logging.INFO)
        logFormatter = logging.Formatter(fmt=' %(name)s %(message)s')
        consoleHandler = logging.StreamHandler()
        consoleHandler.setLevel(logging.INFO)
        consoleHandler.setFormatter(logFormatter)
        logger = logging.getLogger('pyBTCProxy')

        if isinstance(_conf['app']['log_level'], str) and str(
                _conf['app']['log_level']).lower() == 'debug':
            consoleHandler.setLevel(logging.DEBUG)
        logger.handlers.clear()
        logger.addHandler(consoleHandler)
        logger.propagate = False

        # noisy aiohttp
        logging.getLogger('aiohttp').setLevel(logging.WARNING)


        if not isinstance(_conf['app']['wait_for_download'], str):
            _conf['app']['wait_for_download'] = '0'

        self.config = _conf
        self.logger = logger
        self.startTime = int(time.time())
        self.downloadBlockHashes = set()
        self.requestCounter = 0
        self.background_tasks = set()
        self.taskCounter = 0

        logger.info("Context successfully initialized.")


ctx = BTCProxyContext()
#ctx.initialize()