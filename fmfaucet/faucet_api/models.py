from django.db import models
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)

class FaucetRequestManager(models.Manager):
    def rate_limit(self, ip_address, wallet_address):
        logger.info(f"Checking for Rate limits for {ip_address} and {wallet_address}")
        # Using Q to filter for either the ip_address or wallet_address
        last_request = self.filter(
            Q(ip_address=ip_address) | Q(wallet_address=wallet_address),
            success=True
        ).last()

        if last_request and timezone.now() - last_request.last_request_time < timedelta(minutes=int(settings.RATE_LIMIT_PERIOD)):
            return True
        return False

    def execute_transaction(self, web3, wallet_address):
        # Send transaction (0.0001 Sepolia ETH)
        logger.info(f"Sending Eth to  {wallet_address}")

        nonce = cache.get('wallet_nonce')
        if nonce is None:
            # Fetch the nonce from the source wallet if not found in Redis
            nonce = web3.eth.get_transaction_count(settings.SOURCE_WALLET)

        # We are sending txn from one wallet. Multiple instances of this server should have different source wallet.
        # We should implememnt a queue to receive the requests, and process them asynchronously. Failed Transactions can be processed again depending on the error received.
        transaction = {
            'chainId': int(settings.CHAIN_ID),
            'to': wallet_address,
            'value': web3.to_wei(0.0001, 'ether'),
            'gas': 21000,
            'gasPrice': web3.to_wei('50', 'gwei'),
            'nonce': nonce,
        }
        signed_tx = web3.eth.account.sign_transaction(
            transaction, settings.WALLET_PRIVATE_KEY)
        new_nonce = nonce + 1
        cache.set('wallet_nonce', new_nonce)
        tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        return tx

    def faucet_stats(self):
        last_24_hours = timezone.now() - timedelta(hours=24)
        successful_transactions = FaucetRequest.objects.filter(
            success=True, last_request_time__gte=last_24_hours).count()
        failed_transactions = FaucetRequest.objects.filter(
            success=False, last_request_time__gte=last_24_hours).count()
        return successful_transactions, failed_transactions


class FaucetRequest(models.Model):
    ip_address = models.GenericIPAddressField(max_length=50)
    wallet_address = models.CharField(max_length=100)
    last_request_time = models.DateTimeField(auto_now_add=True)
    created_at_time = models.DateTimeField(auto_now_add=True)
    updated_at_time = models.DateTimeField(auto_now=True)
    success = models.BooleanField()
    failure_reason = models.CharField(max_length=200, null=True)

    objects = FaucetRequestManager()

    class Meta:
        indexes = [
            models.Index(fields=['ip_address']),
            models.Index(fields=['wallet_address']),
        ]
