from django.urls import path
from . import views

urlpatterns = [
    path('faucet/fund', views.fund_wallet),
    path('faucet/stats', views.faucet_stats),
]
