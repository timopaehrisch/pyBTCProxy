import json
import logging
import socket
import sys
import threading
import time
from termcolor import colored
from blessings import Terminal

class LightningRPCClient:
    def __init__(self):
        self.rpc_socket_path = "/mnt/hdd/user_homes/bitcoin/.lightning/bitcoin/lightning-rpc"
        self.rpc_socket = None
        self.terminal = Terminal()

    def _connect(self):
        try:
            self.rpc_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.rpc_socket.connect(self.rpc_socket_path)
            logging.info("Connected to Lightning RPC socket.")
            return True
        except Exception as e:
            logging.error(f"Failed to connect to Lightning RPC socket: {str(e)}")
            return False

    def _rpc_call(self, method, params=None):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params if params is not None else [],
        }
        try:
            self.rpc_socket.sendall(json.dumps(payload).encode("utf-8"))
            logging.info(f"Sent RPC request: {method}")
            response = self.rpc_socket.recv(4096).decode("utf-8")
            logging.info(f"Received RPC response: {response}")
            return json.loads(response)
        except Exception as e:
            logging.error(f"RPC call failed: {str(e)}")
            return None

    def get_info(self):
        while True:
            if not self._connect():
                return
            response = self._rpc_call("getinfo")
            if response:
                logging.info("Received 'getinfo' response.")
                self._print_response("getinfo", response)
            time.sleep(5)

    def list_peers(self):
        while True:
            if not self._connect():
                return
            response = self._rpc_call("listpeers")
            if response:
                logging.info("Received 'listpeers' response.")
                self._print_response("listpeers", response)
            time.sleep(5)

    def close_connection(self):
        if self.rpc_socket:
            self.rpc_socket.close()
            logging.info("Closed connection to Lightning RPC socket.")

    def animated_counter(self):
        for i in range(5, 0, -1):
            print(self.terminal.move_y(20))
            print(self.terminal.move_x(0))
            print(self.terminal.clear_eos())
            print(f"Updating in {i} seconds...")
            time.sleep(1)

    def _print_response(self, method, response):
        with self.terminal.fullscreen():
            if method == "getinfo":
                y_pos = 0
            elif method == "listpeers":
                y_pos = int(self.terminal.height / 2)

            print(self.terminal.move_y(y_pos))
            print(self.terminal.move_x(0))
            print(self.terminal.clear_eos())
            print(colored(f"{method.upper()} RESPONSE", "yellow" if method == "getinfo" else "green"))

            lines = json.dumps(response, indent=4).split('\n')[:10]
            for line in lines:
                print(line)

if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    client = LightningRPCClient()

    # Run get_info and list_peers in separate threads
    get_info_thread = threading.Thread(target=client.get_info)
    list_peers_thread = threading.Thread(target=client.list_peers)

    get_info_thread.start()
    list_peers_thread.start()

    counter_thread = threading.Thread(target=client.animated_counter)
    counter_thread.start()

    get_info_thread.join()
    list_peers_thread.join()
    counter_thread.join()

    client.close_connection()
