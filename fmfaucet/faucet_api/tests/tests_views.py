import os
from django.test import TestCase
from rest_framework.test import APIClient
from django.utils import timezone
from web3 import Web3
from unittest.mock import patch, MagicMock
from faucet_api.models import FaucetRequest
from datetime import timedelta
from django.core.cache import cache
from django.conf import settings

class FaucetApiTest(TestCase):
    def setUp(self):
        # Setup test client
        self.client = APIClient()
        self.wallet_address = "0x0000000000000000000000000000000000000000"
        self.ip_address = "127.0.0.1"

        # Mock web3 setup
        self.web3_mock = patch('faucet_api.views.web3', autospec=True).start()
        self.web3_mock.eth.get_transaction_count.return_value = 1

        # Mock `sign_transaction`
        self.signed_transaction_mock = MagicMock()
        self.signed_transaction_mock.raw_transaction = b"0xmockedrawtransaction"
        self.web3_mock.eth.account.sign_transaction.return_value = self.signed_transaction_mock

        self.web3_mock.eth.send_raw_transaction.return_value = b"0xmockedtxhash"

    def tearDown(self):
        patch.stopall()

    def test_fund_wallet_rate_limit(self):
        # Create a FaucetRequest within 1 minute (to simulate rate limiting)
        FaucetRequest.objects.create(ip_address=self.ip_address, wallet_address=self.wallet_address, success=True, last_request_time=timezone.now())

        # Send the second request (should be rate-limited)
        response = self.client.post('/api/v1/faucet/fund', {'wallet_address': self.wallet_address}, REMOTE_ADDR=self.ip_address)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data['error'], 'Rate limit exceeded. Try again later.')

    @patch('faucet_api.views.cache.set')
    def test_fund_wallet_invalid_transaction(self, mock_cache_set):
        # Simulate a failure in sending the transaction (e.g., invalid wallet)
        self.web3_mock.eth.send_raw_transaction.side_effect = Exception("Invalid wallet address")

        response = self.client.post('/api/v1/faucet/fund', {'wallet_address': self.wallet_address}, REMOTE_ADDR=self.ip_address)
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)

        # Ensure FaucetRequest is created with failure status
        faucet_request = FaucetRequest.objects.filter(wallet_address=self.wallet_address).last()
        self.assertIsNotNone(faucet_request)
        self.assertFalse(faucet_request.success)

    def test_faucet_stats(self):
        # Create some successful and failed FaucetRequest entries
        FaucetRequest.objects.create(ip_address=self.ip_address, wallet_address=self.wallet_address, success=True, last_request_time=timezone.now())
        FaucetRequest.objects.create(ip_address=self.ip_address, wallet_address=self.wallet_address, success=False, last_request_time=timezone.now())

        response = self.client.get('/api/v1/faucet/stats')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['successful_transactions'], 1)
        self.assertEqual(response.data['failed_transactions'], 1)
