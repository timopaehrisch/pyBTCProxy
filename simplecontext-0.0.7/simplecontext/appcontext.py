import configparser
import logging
import time
import asyncio


__all__ = [
    'ctx',
    'AppContext',
    'LOG'
]

class AppContext:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppContext, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.initialize()

    def initialize(self):
        # load config and/or set default values
        _conf = configparser.ConfigParser()
        conf_file = 'simplecontext/appcontext.conf' 
        conf_list = _conf.read(conf_file)
        if (len(conf_list) <1):
            print("WARN: No entries in config file " + conf_file)

        if not 'net' in _conf:
            print("WARN: No 'net' section in config values. Was the config file loaded?")
            _conf['net'] = {}
 
        logFormatter = logging.Formatter(fmt=' %(name)s %(message)s')
        consoleHandler = logging.StreamHandler()
        consoleHandler.setLevel(logging.INFO)
        consoleHandler.setFormatter(logFormatter)
        logger = logging.getLogger('SimpleAppContext')

        if not 'app' in _conf:
            _conf['app'] = {}

        logging.basicConfig(level=logging.INFO)
        if 'log_level' in _conf['app'] and str(_conf['app']['log_level']).lower() == 'debug':
            consoleHandler.setLevel(logging.DEBUG)
        logger.handlers.clear()
        logger.addHandler(consoleHandler)
        logger.propagate = False

        self.config = _conf
        self.logger = logger
        self.startTime = int(time.time())
        self.background_tasks = set()
        self.taskCounter = 0

       # initialize statistics task
        asyncio.run(self._runStatsTask())

        logger.info("initialized.")

    async def _runStatsTask(self):
        statisticsTask = asyncio.create_task(self.statsTask(), name="Statistics Task#{self.taskCounter}")
        self.taskCounter += 1
        self.background_tasks.add(statisticsTask)
        statisticsTask.add_done_callback(self.background_tasks.discard)

    async def statsTask(self):
        while True:
            logStr = "StatsTask initiated"
            self.logger.info(logStr)
            await asyncio.sleep(1800)

  

ctx = AppContext()
LOG = ctx.logger
