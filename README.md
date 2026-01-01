# FinancialSimulation

## Introduction

This is a backtesting program for your investing strategy.

It also supports real-time investing with low-medium frequency of operation.
In real-time case, you will receive an email to notify you to do detailed operation.

## Features

- [x] Easy to setup your own trading strategy and keep code clean.
- [x] Support yahooquery(US) and AKShare(CN).
- [x] Support cost simulation including commision, tax, and slippage.
- [x] Support T+1 for CN stocks.
- [x] Support trade next day to avoid future bias.
- [x] Support plotting.
- [x] Get detailed records for trading.
- [x] Hurst exponent utility support.
- [x] ......

## How to use

`main.py` provides a simple example of how to do simulation.

`daily_check.py` provides a simple example of how to do real-time investing.
You need to provide mailjet token to send emails.

Under `strategies/` there are examples about how to customize trading principles.

Congratulations! You can enjoy your trading right now!!!
