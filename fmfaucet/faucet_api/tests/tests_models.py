from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch, MagicMock
from datetime import timedelta
from faucet_api.models import FaucetRequest
from django.conf import settings


class FaucetRequestManagerTest(TestCase):

    def setUp(self):
        self.web3 = MagicMock()

        # Mock the get_transaction_count and other web3 methods
        self.web3.eth.get_transaction_count = MagicMock(return_value=1)
        self.web3.eth.account.sign_transaction = MagicMock()
        self.web3.eth.send_raw_transaction = MagicMock()

        self.ip_address = '127.0.0.1'
        self.wallet_address = '0xSomeTestWalletAddress'
        self.success = True

        # Create an initial FaucetRequest object
        FaucetRequest.objects.create(
            ip_address=self.ip_address,
            wallet_address=self.wallet_address,
            success=self.success,
            last_request_time=timezone.now() - timedelta(minutes=5)
        )

    @patch('faucet_api.models.timezone')
    def test_rate_limit_true(self, mock_timezone):
        # Mocking timezone to simulate a new request within the rate limit period
        mock_timezone.now.return_value = timezone.now()
        settings.RATE_LIMIT_PERIOD = 1  # 1 minute rate limit

        rate_limited = FaucetRequest.objects.rate_limit(
            ip_address=self.ip_address, wallet_address=self.wallet_address)

        self.assertTrue(rate_limited)

    @patch('faucet_api.models.timezone')
    def test_rate_limit_false(self, mock_timezone):
        # Mocking timezone to simulate a new request outside the rate limit period
        mock_timezone.now.return_value = timezone.now() + timedelta(minutes=10)
        settings.RATE_LIMIT_PERIOD = 1  # 1 minute rate limit

        rate_limited = FaucetRequest.objects.rate_limit(
            ip_address=self.ip_address, wallet_address=self.wallet_address)

        self.assertFalse(rate_limited)

    @patch('django.core.cache.cache.get')
    @patch('django.core.cache.cache.set')
    def test_execute_transaction_with_cached_nonce(self, mock_cache_set, mock_cache_get):
        # Simulate nonce in cache
        mock_cache_get.return_value = 2

        # Mock signing and sending transaction
        self.web3.eth.account.sign_transaction.return_value = MagicMock(raw_transaction=b'signed_tx')
        self.web3.eth.send_raw_transaction.return_value = b'tx_hash'

        # Execute transaction
        tx_hash = FaucetRequest.objects.execute_transaction(self.web3, self.wallet_address)

        # Verify nonce handling
        self.assertEqual(tx_hash, b'tx_hash')
        mock_cache_get.assert_called_with('wallet_nonce')
        mock_cache_set.assert_called_with('wallet_nonce', 3)

    @patch('django.core.cache.cache.get')
    @patch('django.core.cache.cache.set')
    def test_execute_transaction_without_cached_nonce(self, mock_cache_set, mock_cache_get):
        # Simulate cache miss for nonce
        mock_cache_get.return_value = None
        self.web3.eth.get_transaction_count.return_value = 5

        # Mock signing and sending transaction
        self.web3.eth.account.sign_transaction.return_value = MagicMock(raw_transaction=b'signed_tx')
        self.web3.eth.send_raw_transaction.return_value = b'tx_hash'

        # Execute transaction
        tx_hash = FaucetRequest.objects.execute_transaction(self.web3, self.wallet_address)

        # Verify nonce handling
        self.assertEqual(tx_hash, b'tx_hash')
        mock_cache_get.assert_called_with('wallet_nonce')
        self.web3.eth.get_transaction_count.assert_called_with(settings.SOURCE_WALLET)
        mock_cache_set.assert_called_with('wallet_nonce', 6)

    def test_faucet_stats(self):
        # Creating additional FaucetRequests for testing stats
        FaucetRequest.objects.create(
            ip_address='127.0.0.2',
            wallet_address='0xWalletAddress2',
            success=False,
            last_request_time=timezone.now()
        )

        FaucetRequest.objects.create(
            ip_address='127.0.0.3',
            wallet_address='0xWalletAddress3',
            success=True,
            last_request_time=timezone.now() - timedelta(hours=1)
        )

        successful, failed = FaucetRequest.objects.faucet_stats()

        self.assertEqual(successful, 2)
        self.assertEqual(failed, 1)
