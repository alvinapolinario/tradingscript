//+------------------------------------------------------------------+
//| VantagePositions.mqh                                             |
//| Read-only position detection (hedging + netting)                 |
//| NEVER modifies positions                                         |
//+------------------------------------------------------------------+
#ifndef VANTAGE_POSITIONS_MQH
#define VANTAGE_POSITIONS_MQH

#include "VantageTypes.mqh"

bool VantageLoadPositions(const string symbol, VantagePositionSummary &sum)
  {
   ZeroMemory(sum);
   sum.count = 0;
   sum.total_buy_volume = 0.0;
   sum.total_sell_volume = 0.0;
   sum.weighted_avg_entry = 0.0;
   sum.total_floating_pl = 0.0;
   sum.total_swap = 0.0;
   sum.has_position = false;

   double wsum = 0.0;
   double vsum = 0.0;

   int total = PositionsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(!PositionSelectByTicket(ticket))
         continue;
      string pos_sym = PositionGetString(POSITION_SYMBOL);
      if(pos_sym != symbol)
         continue;
      if(sum.count >= VANTAGE_MAX_POSITIONS)
         break;

      VantagePositionRow row;
      ZeroMemory(row);
      row.ticket        = ticket;
      row.type          = PositionGetInteger(POSITION_TYPE);
      row.volume        = PositionGetDouble(POSITION_VOLUME);
      row.price_open    = PositionGetDouble(POSITION_PRICE_OPEN);
      row.price_current = PositionGetDouble(POSITION_PRICE_CURRENT);
      row.sl            = PositionGetDouble(POSITION_SL);
      row.tp            = PositionGetDouble(POSITION_TP);
      row.profit        = PositionGetDouble(POSITION_PROFIT);
      row.swap          = PositionGetDouble(POSITION_SWAP);
      row.time_open     = (datetime)PositionGetInteger(POSITION_TIME);
      row.comment       = PositionGetString(POSITION_COMMENT);
      row.magic         = PositionGetInteger(POSITION_MAGIC);

      sum.rows[sum.count] = row;
      sum.count++;
      sum.total_floating_pl += row.profit;
      sum.total_swap += row.swap;

      if(row.type == POSITION_TYPE_BUY)
         sum.total_buy_volume += row.volume;
      else
         sum.total_sell_volume += row.volume;

      wsum += row.price_open * row.volume;
      vsum += row.volume;
     }

   sum.has_position = (sum.count > 0);
   if(vsum > 0.0)
      sum.weighted_avg_entry = wsum / vsum;
   return true;
  }

string VantagePositionTypeName(const long t)
  {
   return (t == POSITION_TYPE_BUY) ? "BUY" : "SELL";
  }

string VantagePositionsToJson(const VantagePositionSummary &sum)
  {
   string j = "[";
   for(int i = 0; i < sum.count; i++)
     {
      if(i > 0) j += ",";
      j += "{";
      j += "\"ticket\":" + IntegerToString((long)sum.rows[i].ticket) + ",";
      j += "\"type\":\"" + VantagePositionTypeName(sum.rows[i].type) + "\",";
      j += "\"volume\":" + DoubleToJson(sum.rows[i].volume, 4) + ",";
      j += "\"price_open\":" + DoubleToJson(sum.rows[i].price_open, 8) + ",";
      j += "\"price_current\":" + DoubleToJson(sum.rows[i].price_current, 8) + ",";
      j += "\"sl\":" + DoubleToJson(sum.rows[i].sl, 8) + ",";
      j += "\"tp\":" + DoubleToJson(sum.rows[i].tp, 8) + ",";
      j += "\"profit\":" + DoubleToJson(sum.rows[i].profit, 4) + ",";
      j += "\"swap\":" + DoubleToJson(sum.rows[i].swap, 4) + ",";
      j += "\"time_open\":\"" + TimeToString(sum.rows[i].time_open, TIME_DATE|TIME_SECONDS) + "\",";
      j += "\"comment\":\"" + JsonEscape(sum.rows[i].comment) + "\",";
      j += "\"magic\":" + IntegerToString(sum.rows[i].magic);
      j += "}";
     }
   j += "]";
   return j;
  }

#endif
//+------------------------------------------------------------------+
