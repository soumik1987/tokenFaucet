from django.shortcuts import render
from django.conf import settings
from django.core.cache import cache

# Create your views here.
from rest_framework.decorators import api_view
from rest_framework.response import Response
from web3 import Web3
from .models import FaucetRequest
import os
import logging

logger = logging.getLogger(__name__)
web3 = Web3(Web3.HTTPProvider(settings.SEPOLIA_RPC_URL))


@api_view(['POST'])
def fund_wallet(request):
    wallet_address = request.data.get('wallet_address')
    ip_address = request.META.get('REMOTE_ADDR')
    # Check rate limit
    logger.info(f'Fund request received for {wallet_address} and {ip_address}')
    if FaucetRequest.objects.rate_limit(ip_address, wallet_address):
        return Response(
            {"error": "Rate limit exceeded. Try again later."}, status=429)

    try:
        tx_hash = FaucetRequest.objects.execute_transaction(
            web3, wallet_address)
        # Create transaction in the database
        FaucetRequest.objects.create(
            ip_address=ip_address,
            wallet_address=wallet_address,
            success=True)
        return Response({"tx_hash": web3.to_hex(tx_hash)}, status=200)
    # [TODO] handle specific errors
    except Exception as e:
        FaucetRequest.objects.create(
            ip_address=ip_address,
            wallet_address=wallet_address,
            success=False, failure_reason=str(e))
        cache.set('wallet_nonce', web3.eth.get_transaction_count(settings.SOURCE_WALLET))
        return Response({"error": str(e)}, status=400)


@api_view(['GET'])
def faucet_stats(request):
    logger.info('Stats request received')
    successful_transactions, failed_transactions = FaucetRequest.objects.faucet_stats()

    return Response({
        "successful_transactions": successful_transactions,
        "failed_transactions": failed_transactions,
    }, status=200)
