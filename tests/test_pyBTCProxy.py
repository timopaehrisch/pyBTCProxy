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
from aiohttp import web, BasicAuth
from unittest.mock import patch, MagicMock
from bitcoinproxy.proxy import BTCProxy

logging.basicConfig(format='%(asctime)s %(levelname)s [pyBTC] %(message)s', level=logging.DEBUG)
LOG = logging.getLogger(__name__)

def test_load_env_vars_pytest_env():
    assert os.environ["PRUNED_HOST"] != "CHANGE_ME"
    assert os.environ["PRUNED_PORT"] != "CHANGE_ME"
    assert os.environ["BITCOIN_USER"]
    assert os.environ["LISTEN_IP"]
    assert os.environ["LISTEN_PORT"]
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
            'listen_ip': os.environ["LISTEN_IP"],
            'listen_port': os.environ["LISTEN_PORT"],
            'dest_ip': os.environ["PRUNED_HOST"],
            'dest_port': os.environ["PRUNED_PORT"],
            'dest_user': os.environ["BITCOIN_USER"],
            'dest_pass': os.environ["BITCOIN_PASSWORD"]
        }, 
        'app': {
            'wait_for_download': 3
        }
    }
    
    proxy.start()
    blocks_pruned = []
    blocks_retrieved = []
    # Increase number and config value rpcworkqueue on your pruned node in allow more concurrent calls
    numRequest = 2

    async def make_request(requestNumber):
        async with aiohttp.ClientSession(auth=BasicAuth(os.environ["BITCOIN_USER"], os.environ["BITCOIN_PASSWORD"])) as session:
            # determine random block hash
            destHost = "http://" + os.environ["LISTEN_IP"] + ":" + os.environ["LISTEN_PORT"]
            randomBlockNumber = random.randrange(1, 490000, 3)
            async with session.post(destHost, json={"method": "getblockhash", "params": [randomBlockNumber]}) as responseBlock:
                await asyncio.sleep(0.001)
                dataBlockText = await responseBlock.text()
#                dataBlock = await responseBlock.json()
                dataBlock = json.loads(dataBlockText)
#                LOG.info(f"responseBlock:{dataBlock}")
                assert 'result' in dataBlock
                randomBlockHash = dataBlock['result']
                blockLogString = f"[{requestNumber}][Block {randomBlockNumber}" + "]"
                randSleep = random.randrange(1, 10)
                LOG.info(f"{blockLogString} Determined {randomBlockHash} for block {randomBlockNumber}, sleeping {randSleep} seconds.")
#                await session.close()
            
#            LOG.info(f"{blockLogString} Sleeping {randSleep} seconds...")
#            await asyncio.sleep(randSleep)
#            LOG.info(f"{blockLogString} woken up")
            
            async with aiohttp.ClientSession(auth=BasicAuth(os.environ["BITCOIN_USER"], os.environ["BITCOIN_PASSWORD"])) as session2:
                async with session2.post(destHost, json={"method": "getblock", "params": [randomBlockHash]}) as response:
                    await asyncio.sleep(0.001)
                    text = await response.text()
                    if (response.status != 200):
                        LOG.info(f"{blockLogString} response:{text}")
                    assert response.status == 200

#                    blockData = await response.json()
                    blockData = json.loads(text)
                    if blockData['result'] is None and blockData['error']['code'] == -1:
                        LOG.info(f"{blockLogString} is pruned")
                        blocks_pruned.append(randomBlockNumber)
                    else:
                        dataSize = len(blockData['result'])
                        LOG.info(f"{blockLogString} Retrieved block with size {dataSize}")
                        blocks_retrieved.append(randomBlockNumber)
#                    await session2.close()
                    return blockData
            
    # wait for proxy to start up
    await asyncio.sleep(2)

    LOG.info(f"Creating {numRequest} getblockhash/getblock requests...")
    # Simulate multiple concurrent requests
#    tasks = [make_request() for _ in range(numRequest)]
    tasks = []
    for reqNo in range(numRequest):
        tasks.append(make_request(reqNo))
    LOG.info("getblockhash/getblock requests created. Now Executing.")

    results = await asyncio.gather(*tasks)
    LOG.info(f"getblockhash/getblock request tasks have been gathered.")
    LOG.info(f"Results [Total/Downloaded/Pruned]: [{numRequest}/" + str(len(blocks_retrieved)) + "/" + str(len(blocks_pruned)) + "]")

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

        numRequest = 50
        LOG.info(f"Creating {numRequest} requests...")
        tasks = [create_request() for _ in range(numRequest)]
        LOG.info(f"Starting concurrent request tasks...")
        results = await asyncio.gather(*tasks)
        LOG.info(f"Tasks finished.")

        # Verify all tasks return the expected result
        for result in results:
            assert result['result'] == 'success'

