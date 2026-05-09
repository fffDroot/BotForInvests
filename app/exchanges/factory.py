from .crypto import CryptoExchangeWrapper
from .tinkoff import TinkoffExchangeWrapper

def get_exchange_wrapper(exchange_name: str, api_key: str, api_secret: str = None, passphrase: str = None):
    exchange_name = exchange_name.lower()

    if exchange_name == 'tinkoff':
        return TinkoffExchangeWrapper(token=api_key)
    else:
        # For ccxt supported exchanges
        return CryptoExchangeWrapper(
            exchange_id=exchange_name,
            api_key=api_key,
            secret=api_secret,
            passphrase=passphrase
        )
