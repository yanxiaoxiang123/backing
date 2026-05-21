from mootdx.quotes import Quotes

# 标准市场
client = Quotes.factory(market='std', multithread=True, heartbeat=True)



# 分钟
client.minute(symbol='000001')