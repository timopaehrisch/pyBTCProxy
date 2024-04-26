import unittest
import asyncio
from aiohttp.test_utils import make_mocked_request
from unittest.mock import patch, MagicMock
from bitcoinproxy.proxy import BTCProxy

class TestBTCProxy(unittest.TestCase):
    def setUp(self):
        self.proxy = BTCProxy()
        self.loop = asyncio.get_event_loop()

    @patch('bitcoinproxy.proxy.log')
    @patch('bitcoinproxy.proxy.aiohttp.ClientSession.post')
    def test_handle_request_getblock(self, mock_post, mock_log):
        request_data = '{"method": "getblock", "params": ["block_hash", 0]}'
        request = make_mocked_request('POST', '/', text=request_data)
        self.proxy.forward_request = MagicMock(return_value=asyncio.Future())
        self.proxy.forward_request.return_value.set_result(MagicMock(text=asyncio.Future()))
        response = self.loop.run_until_complete(self.proxy.handle_request(request))
        self.assertTrue(response.status == 200)
        self.assertTrue(mock_log.info.called)

    @patch('bitcoinproxy.proxy.log')
    @patch('bitcoinproxy.proxy.aiohttp.ClientSession.post')
    def test_forward_request(self, mock_post, mock_log):
        fake_response = MagicMock()
        fake_response.text = asyncio.Future()
        fake_response.text.set_result('{"result": "fake_result"}')
        mock_session = MagicMock()
        mock_post.return_value.__aenter__.return_value = fake_response
        result = self.loop.run_until_complete(self.proxy.forward_request(mock_session, 'method', ['param']))
        self.assertEqual(result, fake_response)

    @patch('bitcoinproxy.proxy.log')
    @patch('bitcoinproxy.proxy.aiohttp.ClientSession.post')
    def test_handle_getblock_error(self, mock_post, mock_log):
        fake_peer_info = '{"result": [{"id": "peer_id", "addr": "peer_addr"}]}'
        fake_getblock_result = '{"error": {"code": -5, "message": "fake_error"}}'
        mock_post.side_effect = [
            asyncio.Future(),
            asyncio.Future(),
            asyncio.Future(),
            asyncio.Future()
        ]
        mock_post.return_value.text.return_value = asyncio.Future()
        mock_post.return_value.text.return_value.set_result(fake_peer_info)
        mock_response = MagicMock()
        mock_response.text = asyncio.Future()
        mock_response.text.set_result(fake_getblock_result)
        result = self.loop.run_until_complete(self.proxy.handle_getblock_error(None, ['block_hash'], mock_response))
        self.assertTrue('fake_error' in result)

    @patch('bitcoinproxy.proxy.log')
    def test_init_config(self, mock_log):
        self.proxy.initConfig()
        self.assertIsNotNone(self.proxy.config)

    @patch('bitcoinproxy.proxy.log')
    @patch('bitcoinproxy.proxy.asyncio.run')
    def test_start(self, mock_run, mock_log):
        self.proxy.run_server = MagicMock(return_value=asyncio.Future())
        self.loop.run_until_complete(self.proxy.start())
        self.assertTrue(self.proxy.run_server.called)

    @patch('bitcoinproxy.proxy.log')
    @patch('bitcoinproxy.proxy.asyncio.run')
    def test_run_server(self, mock_run, mock_log):
        self.proxy.statsLoop = MagicMock()
        self.proxy.statsLoop.return_value = asyncio.Future()
        self.proxy.statsLoop.return_value.set_result(None)
        self.loop.run_until_complete(self.proxy._run_server(MagicMock(), '127.0.0.1', 8080))
        self.assertTrue(self.proxy.statsLoop.called)

    @patch('bitcoinproxy.proxy.log')
    @patch('bitcoinproxy.proxy.asyncio.run')
    def test_multiple_requests(self, mock_run, mock_log):
        async def make_request():
            request_data = '{"method": "getblock", "params": ["block_hash", 0]}'
            request = make_mocked_request('POST', '/', text=request_data)
            response = await self.proxy.handle_request(request)
            self.assertTrue(response.status == 200)

        tasks = [make_request() for _ in range(10)]
        self.loop.run_until_complete(asyncio.gather(*tasks))

if __name__ == '__main__':
    unittest.main()
