//+------------------------------------------------------------------+
//| VantageExecutionTrade.mqh                                        |
//| CTrade wrapper for demo market orders                            |
//+------------------------------------------------------------------+
#ifndef VANTAGE_EXECUTION_TRADE_MQH
#define VANTAGE_EXECUTION_TRADE_MQH

#include <Trade/Trade.mqh>

class CVantageExecutionTrade
  {
private:
   CTrade m_trade;
   string m_last_error;

   ENUM_ORDER_TYPE_FILLING ResolveFilling(const string symbol)
     {
      int fill = (int)SymbolInfoInteger(symbol, SYMBOL_FILLING_MODE);
      if((fill & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK)
         return ORDER_FILLING_FOK;
      if((fill & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC)
         return ORDER_FILLING_IOC;
      return ORDER_FILLING_RETURN;
     }

public:
   CVantageExecutionTrade(void) : m_last_error("") {}

   void Configure(const long magic, const string comment)
     {
      m_trade.SetExpertMagicNumber(magic);
      m_trade.SetDeviationInPoints(30);
      m_trade.SetTypeFilling(ResolveFilling(_Symbol));
      m_trade.SetAsyncMode(false);
      m_trade.LogLevel(LOG_LEVEL_ERRORS);
     }

   string LastError(void) const { return m_last_error; }

   bool OpenMarket(
      const string symbol,
      const bool is_buy,
      const double volume,
      const double sl,
      const double tp,
      const string comment,
      ulong &ticket
     )
     {
      m_last_error = "";
      ticket = 0;
      m_trade.SetTypeFilling(ResolveFilling(symbol));
      bool ok = false;
      if(is_buy)
         ok = m_trade.Buy(volume, symbol, 0.0, sl, tp, comment);
      else
         ok = m_trade.Sell(volume, symbol, 0.0, sl, tp, comment);
      if(!ok)
        {
         m_last_error = m_trade.ResultRetcodeDescription();
         return false;
        }
      ticket = m_trade.ResultOrder();
      if(ticket == 0)
         ticket = m_trade.ResultDeal();
      return true;
     }
  };

#endif
