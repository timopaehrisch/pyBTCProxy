import pytest
import os
import json
import asyncio
import random
import time
import logging
from typing import Dict
from unittest.mock import patch, mock_open
from aioresponses import aioresponses
import aiohttp
from aiohttp.web_exceptions import HTTPInternalServerError
from aiohttp import web
from unittest.mock import patch, MagicMock
from bitcoinproxy.proxy import BTCProxy

logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger(__name__)

def test_load_env_vars_pytest_env():
    assert os.environ["PRUNED_HOST"]
    assert os.environ["PRUNED_PORT"]
    assert os.environ["BITCOIN_USER"]
    assert os.environ["BITCOIN_PASSWORD"] != "CHANGE_ME"

@pytest.fixture
def btc_proxy():
    # Initialize the BTCProxy instance with a mocked config file
    proxy = BTCProxy(configFile='test.conf')
    return proxy


# Test 1: Initialization of BTCProxy class
def test_btcproxy_initialization():
    proxy = BTCProxy()
    assert proxy.startTime is not None
    assert proxy.background_tasks == set()
    assert proxy.taskCounter == 0
    assert proxy.requestCounter == 0
    assert proxy.downloadBlockHashes == set()
    assert proxy.conf is None
    assert proxy.session is None
    assert proxy.configFile is not None



# Test 2: Config file missing
def test_config_file_missing():
    proxy = BTCProxy('does_not_exist.conf')
    with pytest.raises(FileNotFoundError) as e_info:  # Expect a FileNotFoundError specifically
        proxy.start()
    
    # Check that the exception message is as expected
    assert "Config file not found" in str(e_info.value)
    assert proxy.conf is None

# Test 3: Open default config
def test_config_file_default():
    proxy = BTCProxy()  # Initialize without specifying a config file
    proxy.start()
#    with pytest.raises(FileNotFoundError) as e_info:  # Expect a FileNotFoundError specifically
#        proxy.start()
    
    # Check that the exception message is informative
#    assert "Config file not found" in str(e_info.value)
    assert proxy.conf is not None  # Ensure proxy.conf is populated with default

# Test 4: getCfg method - valid and invalid configuration
def test_getCfg_valid():
    proxy = BTCProxy()
    proxy.conf = {
        'net': {'listen_ip': '127.0.0.1', 'listen_port': '8080'}
    }
    assert proxy.getCfg('net', 'listen_ip') == '127.0.0.1'
    assert proxy.getCfg('net', 'listen_port') == '8080'

def test_getCfg_invalid():
    proxy = BTCProxy()
    proxy.conf = {}
    assert proxy.getCfg('net', 'listen_ip') is None




        
# Concurrency test for simultaneous requests
@pytest.mark.asyncio
async def test_concurrent_requests():
    proxy = BTCProxy()
    proxy.conf = {
        'net': {
            'listen_ip': '192.168.150.117',
            'listen_port': '8080',
            'dest_ip': os.environ["PRUNED_HOST"],
            'dest_port': os.environ["PRUNED_PORT"],
            'dest_user': os.environ["BITCOIN_USER"],
            'dest_pass': os.environ["BITCOIN_PASSWORD"]
        }, 
        'app': {
            'wait_for_download': 20
        }
    }
    proxy.start()

    async def make_request():
        async with aiohttp.ClientSession() as session:
            connector = aiohttp.TCPConnector(limit=100)
            # determine random block hash
            randomBlock = random.randrange(1, 300000, 3)
            async with session.post("http://10.0.0.3:8330", json={"method": "getblockhash", "params": [randomBlock]}) as responseBlock:
#                parameters = {'height': randomBlock}
#            async with session.request(method="POST", url="http://10.0.0.3:8330", params=parameters) as responseBlock:
                await asyncio.sleep(0.001)
                text = await responseBlock.text()
                LOG.info(f"responseBlock:{text}")
                dataBlock = await responseBlock.json()
                assert 'result' in dataBlock
                randomBlockHash = dataBlock['result']
                LOG.info(f"Determined {randomBlockHash} for block {randomBlock}")

            randSleep = random.randrange(1, 10)
            LOG.info(f"Sleeping {randSleep} seconds...")
            await asyncio.sleep(randSleep)
            LOG.info(f"Continuing for block {randomBlock}")
            
            async with aiohttp.ClientSession() as session2:

    #            async with session.request(method="POST",url="http://10.0.0.3:8330", params=randomBlockHash) as response:
                async with session2.post("http://10.0.0.3:8330", json={"method": "getblock", "params": [randomBlockHash]}) as response:
                    await asyncio.sleep(0.001)
                    text = await response.text()
                    LOG.info(f"response:{text}")
                    data = await response.json()
                    assert response.status == 200
                    assert 'result' in dataBlock
                    hexData = data['hex']
                    assert hexData
                    LOG.info("Retrieved block hex.")
                    return data
            
    # wait for proxy to start up
    LOG.info("Waiting for proxy to start up")
    time.sleep(2)

    numRequest = 1
    LOG.info(f"Creating {numRequest} getblockhash requests...")
    # Simulate multiple concurrent requests
    tasks = [make_request() for _ in range(numRequest)]
    LOG.info("getblockhash requests created. Now Executing.")

    results = await asyncio.gather(*tasks)
    LOG.info(f"getblockhash request tasks have been gathered.")

    for result in results:
        if 'error' in results:
            LOG.info(f"error in result is " + str(result['error']))

#            assert 'error' in result  # Check that no request results in an error
#            assert result['error'] is None

@pytest.mark.asyncio
async def test_task_request_handler_concurrent():
    proxy = BTCProxy()
    proxy.conf = {
       'net': {
            'listen_ip': '192.168.150.117',
            'listen_port': '8080',
            'dest_ip': os.environ["PRUNED_HOST"],
            'dest_port': os.environ["PRUNED_PORT"],
            'dest_user': os.environ["BITCOIN_USER"],
            'dest_pass': os.environ["BITCOIN_PASSWORD"]
        }
    }

    with patch.object(proxy, 'handle_request', return_value={'result': 'success'}) as mock_handle_request:
        async def create_request():
            request_data = {"method": "gettxout", "params": []}
            response = await proxy.taskRequestHandler(request_data)
            return response

        numRequest = 1
        LOG.info(f"Creating {numRequest} requests...")
        tasks = [create_request() for _ in range(numRequest)]
        LOG.info(f"Starting concurrent request tasks...")
        results = await asyncio.gather(*tasks)
        LOG.info(f"Tasks finished.")

        # Verify all tasks return the expected result
        for result in results:
            assert result['result'] == 'success'

