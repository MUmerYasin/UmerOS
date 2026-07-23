import asyncio
import json
import unittest

from network import AINetworkQoS, DNSResolver, HTTPClient, NetworkStack, TCPClient, TCPServer


class NetworkSubsystemTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.servers = []

    async def asyncTearDown(self):
        for server in self.servers:
            server.close()
            await server.wait_closed()

    async def test_dns_resolver_accepts_literal_ip(self):
        resolver = DNSResolver()

        addresses = await resolver.resolve_all("127.0.0.1")

        self.assertEqual(addresses, ["127.0.0.1"])

    async def test_http_client_get_and_json_via_loopback(self):
        body = json.dumps({"system": "umeros", "online": True}).encode("utf-8")

        async def handle_http(reader, writer):
            await reader.read(65536)
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                + f"Content-Length: {len(body)}\r\n".encode("ascii")
                + b"Connection: close\r\n\r\n"
                + body
            )
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(handle_http, "127.0.0.1", 0)
        self.servers.append(server)
        port = server.sockets[0].getsockname()[1]
        url = f"http://127.0.0.1:{port}/status"
        client = HTTPClient()

        response = await client.get(url)
        parsed = await client.fetch_json(url)

        self.assertEqual(response["status"], 200)
        self.assertIn("umeros", response["body"])
        self.assertEqual(parsed["system"], "umeros")
        self.assertTrue(parsed["online"])

    async def test_tcp_server_client_round_trip(self):
        server = TCPServer(port=0)
        await server.start()
        client = TCPClient()

        response = await client.connect(server.host, server.port, b"hello")

        await server.stop()
        self.assertEqual(response, b"ACK:hello")

    async def test_network_stack_can_send_tcp(self):
        server = TCPServer(port=0)
        await server.start()
        stack = NetworkStack()
        stack.start()

        response = await stack.send_tcp("127.0.0.1", server.port, b"internet-ready")

        await stack.stop()
        await server.stop()
        self.assertEqual(response, b"ACK:internet-ready")

    async def test_network_stack_fetch_url_uses_http_facade(self):
        body = b"UmerOS network online"

        async def handle_http(reader, writer):
            await reader.read(65536)
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/plain\r\n"
                + f"Content-Length: {len(body)}\r\n".encode("ascii")
                + b"Connection: close\r\n\r\n"
                + body
            )
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(handle_http, "127.0.0.1", 0)
        self.servers.append(server)
        port = server.sockets[0].getsockname()[1]
        stack = NetworkStack()

        text = await stack.fetch_url(f"http://127.0.0.1:{port}/")

        self.assertEqual(text, "UmerOS network online")

    def test_qos_classifies_common_internet_flows(self):
        qos = AINetworkQoS()

        self.assertEqual(qos.classify_connection("example.com", 443), "web_browse")
        self.assertEqual(qos.classify_connection("zoom.us", 443), "video_conference")
        self.assertGreater(qos.get_priority("video_conference"), qos.get_priority("download"))


if __name__ == "__main__":
    unittest.main()
