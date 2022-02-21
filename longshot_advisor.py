#!/usr/bin/env python3

import datetime
from dateutil import parser
import math
from operator import itemgetter
import requests

from scipy.stats import norm


def get_debiased_price(price):
    """Return the price after correcting for favorite-longshot bias.

    See "Forecasting Elections: Comparing Prediction Markets, Polls, and
    their Biases." by David Rothschild, Public Opinion Quarterly, Vol. 73,
    No. 5 2009.
    """
    return norm.cdf(1.64 * norm.ppf(price))


def get_contract_data():
    markets = requests.get(
        "https://www.predictit.org/api/marketdata/all/").json()["markets"]
    contracts = []
    for market in markets:
        if market['status'] != 'Open':
            continue
        for contract in market["contracts"]:
            for key, key_name in (('bestBuyYesCost', 'Yes'), ('bestBuyNoCost', 'No')):
                price = contract[key]
                if price is None:
                    continue
                debiased_price = get_debiased_price(price)
                profit_per_share = debiased_price - price
                total_profit = math.floor(850 / price) * profit_per_share
                total_profit_minus_fees = .9 * total_profit

                date_end = contract['dateEnd']
                if date_end in ("NA", "N/A"):
                    date_end = None
                else:
                    try:
                        date_end = parser.parse(date_end)
                    except parser.ParserError:
                        # There are a few dates that look like "02/25/2022
                        # 11:00:00 AM (ET)". We'll ignore the time portion.
                        date_end = datetime.datetime.strptime(
                            date_end[:10], "%m/%d/%Y")

                contracts.append({
                    'market_name': market["name"],
                    'contract_name': contract["name"] if len(market['contracts']) > 1 else None,
                    'contract_key': key_name,
                    'price': price,
                    'debiased_price': round(debiased_price, 2),
                    'profit_per_share': round(profit_per_share, 2),
                    'total_profit': round(total_profit, 2),
                    'total_profit_minus_fees': round(total_profit_minus_fees, 2),
                    'url': market['url'],
                    "end_date": date_end,
                })
    return contracts


if __name__ == '__main__':
    data = get_contract_data()
    data.sort(key=itemgetter('total_profit'), reverse=True)

    print("Top 5 most profitable contracts:")
    for contract in data[:5]:
        print(f"\n{contract['market_name']}:\n{contract['url']}")
        if contract['contract_name'] is None:
            print(f"\t{contract['contract_key']}")
        else:
            print(f"\t{contract['contract_name']}: {contract['contract_key']}")
        print(f"\tProfit: ${contract['total_profit']}, "
              f"Minus fees: ${contract['total_profit_minus_fees']}, "
              f"Price: ${contract['price']}, "
              f"Debiased Price: ${contract['debiased_price']}")
        if contract['end_date'] is not None:
            print(f"\tEnd date: {contract['end_date']}")
