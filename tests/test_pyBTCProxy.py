import pytest
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
            'listen_ip': '127.0.0.1',
            'listen_port': '8080',
            'dest_ip': '127.0.0.1',
            'dest_port': '8331',
            'dest_user': 'user',
            'dest_pass': 'password'
        }, 
        'app': {
            'wait_for_download': 20
        }
    }
        
    async with aiohttp.ClientSession() as session:
        async def make_request():
            # determine random block hash
            randomBlock = random.randrange(1, 300000, 3)
            async with session.post('http://192.168.150.117:8331', json={"method": "getblockhash", "params": [randomBlock]}) as responseBlock:
                await asyncio.sleep(0.001)
                dataBlock = await responseBlock.json()
                assert 'result' in dataBlock
                randomBlockHash = dataBlock['result']
#                return dataBlock
                time.sleep(1)

            async with session.post('http://192.168.150.117:8331', json={"method": "getblock", "params": ["blockhash", randomBlockHash]}) as response:
                assert response.status == 200
                data = await response.json()
                return data

        # Simulate multiple concurrent requests
        tasks = [make_request() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        
        for result in results:
            if 'error' in results:
                print(f"error in result is " + str(result['error']))

#            assert 'error' in result  # Check that no request results in an error
#            assert result['error'] is None

@pytest.mark.asyncio
async def test_task_request_handler_concurrent():
    proxy = BTCProxy()
    proxy.conf = {
        'net': {
            'listen_ip': '127.0.0.1',
            'listen_port': '8080',
            'dest_ip': '127.0.0.1',
            'dest_port': '8332',
            'dest_user': 'user',
            'dest_pass': 'password'
        }
    }

    with patch.object(proxy, 'handle_request', return_value={'result': 'success'}) as mock_handle_request:
        async def create_request():
            request_data = {"method": "gettxout", "params": []}
            response = await proxy.taskRequestHandler(request_data)
            return response

        numRequest = 100
        LOG.info(f"Creating {numRequest} requests...")
        tasks = [create_request() for _ in range(numRequest)]
        LOG.info(f"Starting concurrent request tasks...")
        results = await asyncio.gather(*tasks)
        LOG.info(f"Tasks finished.")

        # Verify all tasks return the expected result
        for result in results:
            assert result['result'] == 'success'

