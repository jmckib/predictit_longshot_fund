#!/usr/bin/env python3

import csv
import datetime
from dateutil import parser
import math
from operator import itemgetter
import requests
import sys
import yaml

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
    # Market id => approximate end dates I've manually entered.
    market_end_dates = yaml.load(open("market_end_dates.yaml"),
                                 Loader=yaml.CLoader)
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

                end_date = contract['dateEnd']
                manual_end_date = False
                if end_date in ("NA", "N/A"):
                    end_date = market_end_dates.get(market["id"], None)
                    if end_date is not None:
                        end_date = datetime.datetime.strptime(
                            end_date, "%m/%d/%Y").date()
                        manual_end_date = True
                else:
                    try:
                        end_date = parser.parse(end_date).date()
                    except parser.ParserError:
                        # There are a few dates that look like "02/25/2022
                        # 11:00:00 AM (ET)". We'll ignore the time portion.
                        end_date = datetime.datetime.strptime(
                            end_date[:10], "%m/%d/%Y").date()
                contracts.append({
                    'market_name': market["name"],
                    'id': market["id"],
                    'manual_end_date': manual_end_date,
                    'contract_name': contract["name"] if len(market['contracts']) > 1 else None,
                    'contract_key': key_name,
                    'price': price,
                    'debiased_price': round(debiased_price, 2),
                    'profit_per_share': round(profit_per_share, 2),
                    'total_profit': round(total_profit, 2),
                    'total_profit_minus_fees': round(total_profit_minus_fees, 2),
                    'url': market['url'],
                    "end_date": end_date,
                })
    return contracts


if __name__ == '__main__':
    data = get_contract_data()
    fieldnames = ['market_name', 'id', 'contract_name', 'contract_key', 'price',
                  'debiased_price', 'profit_per_share', 'total_profit',
                  'total_profit_minus_fees', 'end_date', 'url']

    print("Profitable contracts expiring within two weeks:")
    two_weeks_from_now = (datetime.date.today() +
                          datetime.timedelta(days=14))
    with_dates = [
        item for item in data
        if item["end_date"] is not None
        and item["end_date"] < two_weeks_from_now
        and item["total_profit"] > 100
        and not item["manual_end_date"]
    ]
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames,
                            extrasaction="ignore")
    writer.writeheader()
    writer.writerows(with_dates)

    print("")
    print("The most profitable 100 contracts with no end date:")
    without_dates = [item for item in data if item["end_date"] is None
                     or item["manual_end_date"]]
    without_dates.sort(key=itemgetter('total_profit'), reverse=True)
    writer.writeheader()
    writer.writerows(without_dates[:100])
