import pytest
import json
import asyncio
from typing import Dict
from unittest.mock import patch, mock_open
from aioresponses import aioresponses
import aiohttp
from aiohttp.web_exceptions import HTTPInternalServerError
from aiohttp import web
from unittest.mock import patch, MagicMock
from bitcoinproxy.proxy import BTCProxy

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

