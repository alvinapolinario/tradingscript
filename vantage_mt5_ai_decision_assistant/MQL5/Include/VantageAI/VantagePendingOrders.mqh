//+------------------------------------------------------------------+
//| VantagePendingOrders.mqh                                         |
//| Read-only pending order capture (all symbols on the account)     |
//| NEVER places, modifies, or deletes orders                        |
//+------------------------------------------------------------------+
#ifndef VANTAGE_PENDING_ORDERS_MQH
#define VANTAGE_PENDING_ORDERS_MQH

#include "VantageTypes.mqh"
#include "VantageSymbol.mqh"
#include "VantageRisk.mqh"

bool VantageIsPendingOrderType(const long t)
  {
   return(t == ORDER_TYPE_BUY_LIMIT || t == ORDER_TYPE_SELL_LIMIT ||
          t == ORDER_TYPE_BUY_STOP || t == ORDER_TYPE_SELL_STOP ||
          t == ORDER_TYPE_BUY_STOP_LIMIT || t == ORDER_TYPE_SELL_STOP_LIMIT);
  }

string VantagePendingOrderTypeName(const long t)
  {
   if(t == ORDER_TYPE_BUY_LIMIT)       return "BUY_LIMIT";
   if(t == ORDER_TYPE_SELL_LIMIT)      return "SELL_LIMIT";
   if(t == ORDER_TYPE_BUY_STOP)        return "BUY_STOP";
   if(t == ORDER_TYPE_SELL_STOP)       return "SELL_STOP";
   if(t == ORDER_TYPE_BUY_STOP_LIMIT)  return "BUY_STOP_LIMIT";
   if(t == ORDER_TYPE_SELL_STOP_LIMIT) return "SELL_STOP_LIMIT";
   return "UNKNOWN";
  }

// Loads every pending order on the account (not chart-only).
// chart_symbol / chart_spec / chart_px kept for API compat; used as fallback ticks.
bool VantageLoadPendingOrders(const string chart_symbol,
                              const VantageSymbolSpec &chart_spec,
                              const VantagePriceSnap &chart_px,
                              VantagePendingOrderSummary &sum)
  {
   ZeroMemory(sum);
   sum.count = 0;

   int total = OrdersTotal();
   for(int i = 0; i < total; i++)
     {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0)
         continue;
      if(!OrderSelect(ticket))
         continue;

      long otype = OrderGetInteger(ORDER_TYPE);
      if(!VantageIsPendingOrderType(otype))
         continue;
      if(sum.count >= VANTAGE_MAX_PENDING)
         break;

      string ord_sym = OrderGetString(ORDER_SYMBOL);
      VantageSymbolSpec ospec;
      bool have_spec = VantageLoadSymbolSpec(ord_sym, ospec);
      if(!have_spec && ord_sym == chart_symbol)
        {
         ospec = chart_spec;
         have_spec = chart_spec.valid;
        }

      double bid = SymbolInfoDouble(ord_sym, SYMBOL_BID);
      double ask = SymbolInfoDouble(ord_sym, SYMBOL_ASK);
      if(bid <= 0.0 && ask <= 0.0 && ord_sym == chart_symbol)
        {
         bid = chart_px.bid;
         ask = chart_px.ask;
        }
      double mid = 0.0;
      if(bid > 0.0 && ask > 0.0)
         mid = (bid + ask) * 0.5;
      else if(bid > 0.0)
         mid = bid;
      else
         mid = ask;

      VantagePendingOrderRow row;
      ZeroMemory(row);
      row.ticket        = ticket;
      row.symbol        = ord_sym;
      row.digits        = have_spec ? ospec.digits : (int)SymbolInfoInteger(ord_sym, SYMBOL_DIGITS);
      row.type          = otype;
      row.volume        = OrderGetDouble(ORDER_VOLUME_CURRENT);
      if(row.volume <= 0.0)
         row.volume = OrderGetDouble(ORDER_VOLUME_INITIAL);
      row.price_open    = OrderGetDouble(ORDER_PRICE_OPEN);
      row.sl            = OrderGetDouble(ORDER_SL);
      row.tp            = OrderGetDouble(ORDER_TP);
      row.time_setup    = (datetime)OrderGetInteger(ORDER_TIME_SETUP);
      row.comment       = OrderGetString(ORDER_COMMENT);
      row.magic         = OrderGetInteger(ORDER_MAGIC);
      row.bid           = bid;
      row.ask           = ask;
      row.price_current = mid;
      row.distance_price = (mid > 0.0 && row.price_open > 0.0)
                           ? MathAbs(row.price_open - mid) : 0.0;
      double point = have_spec ? ospec.point : SymbolInfoDouble(ord_sym, SYMBOL_POINT);
      if(point > 0.0)
         row.distance_points = row.distance_price / point;
      else
         row.distance_points = 0.0;

      row.risk_available = false;
      row.risk_status = "RISK_CALCULATION_UNAVAILABLE";
      row.money_at_risk = 0.0;
      row.equity_risk_pct = 0.0;
      row.reward_risk_ratio = 0.0;
      row.margin_required = 0.0;

      if(have_spec && row.sl > 0.0 && row.volume > 0.0 && row.price_open > 0.0)
        {
         VantageRiskEstimate risk;
         ENUM_ORDER_TYPE ot = (ENUM_ORDER_TYPE)otype;
         if(VantageCalcRiskFromLevels(ord_sym, ospec, ot, row.volume,
                                      row.price_open, row.sl, row.tp, risk))
           {
            row.risk_available = true;
            row.risk_status = risk.status;
            row.money_at_risk = risk.money_at_risk;
            row.equity_risk_pct = risk.equity_risk_pct;
            row.reward_risk_ratio = risk.reward_risk_ratio;
            row.margin_required = risk.margin_required;
           }
         else
           {
            row.risk_status = risk.status;
           }
        }

      sum.rows[sum.count] = row;
      sum.count++;
     }
   return true;
  }

string VantagePendingOrdersToJson(const VantagePendingOrderSummary &sum)
  {
   string j = "[";
   for(int i = 0; i < sum.count; i++)
     {
      if(i > 0) j += ",";
      int dig = sum.rows[i].digits > 0 ? sum.rows[i].digits : 5;
      j += "{";
      j += "\"ticket\":" + IntegerToString((long)sum.rows[i].ticket) + ",";
      j += "\"symbol\":\"" + JsonEscape(sum.rows[i].symbol) + "\",";
      j += "\"digits\":" + IntegerToString(dig) + ",";
      j += "\"type\":\"" + VantagePendingOrderTypeName(sum.rows[i].type) + "\",";
      j += "\"volume\":" + DoubleToJson(sum.rows[i].volume, 4) + ",";
      j += "\"price_open\":" + DoubleToJson(sum.rows[i].price_open, dig) + ",";
      j += "\"price_current\":" + DoubleToJson(sum.rows[i].price_current, dig) + ",";
      j += "\"bid\":" + DoubleToJson(sum.rows[i].bid, dig) + ",";
      j += "\"ask\":" + DoubleToJson(sum.rows[i].ask, dig) + ",";
      j += "\"sl\":" + DoubleToJson(sum.rows[i].sl, dig) + ",";
      j += "\"tp\":" + DoubleToJson(sum.rows[i].tp, dig) + ",";
      j += "\"time_setup\":\"" + TimeToString(sum.rows[i].time_setup, TIME_DATE|TIME_SECONDS) + "\",";
      j += "\"comment\":\"" + JsonEscape(sum.rows[i].comment) + "\",";
      j += "\"magic\":" + IntegerToString(sum.rows[i].magic) + ",";
      j += "\"distance_price\":" + DoubleToJson(sum.rows[i].distance_price, dig) + ",";
      j += "\"distance_points\":" + DoubleToJson(sum.rows[i].distance_points, 4) + ",";
      j += "\"risk_available\":" + (sum.rows[i].risk_available ? "true" : "false") + ",";
      j += "\"risk_status\":\"" + JsonEscape(sum.rows[i].risk_status) + "\",";
      j += "\"money_at_risk\":" + DoubleToJson(sum.rows[i].money_at_risk, 4) + ",";
      j += "\"equity_risk_pct\":" + DoubleToJson(sum.rows[i].equity_risk_pct, 4) + ",";
      j += "\"reward_risk_ratio\":" + DoubleToJson(sum.rows[i].reward_risk_ratio, 4) + ",";
      j += "\"margin_required\":" + DoubleToJson(sum.rows[i].margin_required, 4);
      j += "}";
     }
   j += "]";
   return j;
  }

string VantagePendingOrdersBlobJson(const VantagePendingOrderSummary &sum)
  {
   string j = "{";
   j += "\"count\":" + IntegerToString(sum.count) + ",";
   j += "\"scope\":\"account\",";
   j += "\"items\":" + VantagePendingOrdersToJson(sum);
   j += "}";
   return j;
  }

#endif
//+------------------------------------------------------------------+
