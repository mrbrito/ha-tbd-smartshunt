import asyncio
import unittest
from unittest.mock import AsyncMock, patch
from loader import load

transport=load('transport')

class PairingTests(unittest.IsolatedAsyncioTestCase):
    def client(self, reads, pair_result=None):
        return type('Client',(),{'read_gatt_char':AsyncMock(side_effect=reads), 'pair':AsyncMock(return_value=pair_result)})()

    async def test_normal_read_does_not_pair(self):
        c=self.client([b'data'])
        self.assertEqual(await transport.PairingReader().read(c,'a'),b'data')
        c.pair.assert_not_awaited()

    async def test_auth_pair_retry_none_and_true_results(self):
        for result in (None,True):
            c=self.client([Exception('Insufficient authentication'),b'data'],result)
            self.assertEqual(await transport.PairingReader().read(c,'a'),b'data')
            c.pair.assert_awaited_once()
            self.assertEqual(c.read_gatt_char.await_count,2)

    async def test_false_pair_result_rejected(self):
        c=self.client([Exception('GATT error 5')],False)
        with self.assertRaises(transport.PairingFailed):
            await transport.PairingReader().read(c,'a')
        self.assertEqual(c.read_gatt_char.await_count,1)

    async def test_unrelated_error_never_pairs(self):
        c=self.client([Exception('connection timed out')])
        with self.assertRaisesRegex(Exception,'timed out'):
            await transport.PairingReader().read(c,'a')
        c.pair.assert_not_awaited()

    async def test_unsupported(self):
        c=self.client([Exception('Insufficient authentication')]);c.pair.side_effect=NotImplementedError()
        with self.assertRaises(transport.PairingUnsupported):
            await transport.PairingReader().read(c,'a')

    async def test_timeout(self):
        c=self.client([Exception('Insufficient authentication')])
        async def slow(): await asyncio.sleep(1)
        c.pair.side_effect=slow
        with patch.object(transport,'PAIR_TIMEOUT',0.001):
            with self.assertRaisesRegex(transport.PairingFailed,'timed out'):
                await transport.PairingReader().read(c,'a')

    async def test_cooldown_and_separate_devices(self):
        reader=transport.PairingReader()
        c=self.client([Exception('GATT error: 5')]*3,False)
        for peer in ['a','a','b']:
            with self.assertRaises(transport.PairingFailed): await reader.read(c,peer)
        self.assertEqual(c.pair.await_count,2)

    async def test_second_read_auth_failure_does_not_loop(self):
        c=self.client([Exception('GATT error: 5')]*2)
        with self.assertRaisesRegex(transport.PairingFailed,'telemetry read failed'):
            await transport.PairingReader().read(c,'a')
        c.pair.assert_awaited_once()

    async def test_cancel_propagates(self):
        c=self.client([asyncio.CancelledError()])
        with self.assertRaises(asyncio.CancelledError): await transport.PairingReader().read(c,'a')
        c.pair.assert_not_awaited()

    def test_auth_detection(self):
        for text in ['GATT error: 5','GATT status=0x0f','Insufficient encryption','ESP_GATT_INSUF_AUTHENTICATION']:
            self.assertTrue(transport.authentication_required(Exception(text)))
        for text in ['error 5','GATT error: 50','GATT error: 133','timeout']:
            self.assertFalse(transport.authentication_required(Exception(text)))
        outer=Exception('wrapper');outer.__cause__=Exception('GATT error: 5')
        self.assertTrue(transport.authentication_required(outer))
