//+------------------------------------------------------------------+
//| VantageExecutionRisk.mqh                                         |
//| Lot sizing from equity risk % (demo executor)                    |
//+------------------------------------------------------------------+
#ifndef VANTAGE_EXECUTION_RISK_MQH
#define VANTAGE_EXECUTION_RISK_MQH

double ExecNormalizeVolume(const string symbol, double volume)
  {
   double vmin = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double vstep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(vstep <= 0.0)
      vstep = 0.01;
   if(volume < vmin)
      volume = vmin;
   if(volume > vmax)
      volume = vmax;
   volume = MathFloor(volume / vstep) * vstep;
   if(volume < vmin)
      volume = vmin;
   return volume;
  }

double ExecCalcRiskVolume(
   const string symbol,
   const bool is_buy,
   const double entry,
   const double stop_loss,
   const double risk_pct,
   const double max_lot,
   string &err
  )
  {
   err = "";
   if(risk_pct <= 0.0 || entry <= 0.0 || stop_loss <= 0.0)
     {
      err = "Invalid risk inputs";
      return 0.0;
     }
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double risk_money = equity * risk_pct / 100.0;
   if(risk_money <= 0.0)
     {
      err = "Risk money <= 0";
      return 0.0;
     }

   ENUM_ORDER_TYPE otype = is_buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   double loss_one_lot = 0.0;
   if(!OrderCalcProfit(otype, symbol, 1.0, entry, stop_loss, loss_one_lot))
     {
      err = "OrderCalcProfit failed";
      return 0.0;
     }
   if(MathAbs(loss_one_lot) < 0.0000001)
     {
      err = "SL distance too small";
      return 0.0;
     }
   double lot = risk_money / MathAbs(loss_one_lot);
   if(max_lot > 0.0 && lot > max_lot)
      lot = max_lot;
   lot = ExecNormalizeVolume(symbol, lot);
   return lot;
  }

int ExecCountOpenPositions(const string symbol, const long magic)
  {
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL) != symbol)
         continue;
      if((long)PositionGetInteger(POSITION_MAGIC) != magic)
         continue;
      count++;
     }
   return count;
  }

bool ExecSpreadOk(const string symbol, const int max_spread_points)
  {
   if(max_spread_points <= 0)
      return true;
   long spread = SymbolInfoInteger(symbol, SYMBOL_SPREAD);
   return (spread <= max_spread_points);
  }

bool ExecStopsLevelOk(const string symbol, const double entry, const double sl, const double tp)
  {
   long stops = SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   if(point <= 0.0)
      return false;
   double min_dist = stops * point;
   if(MathAbs(entry - sl) < min_dist)
      return false;
   if(MathAbs(tp - entry) < min_dist)
      return false;
   return true;
  }

#endif
