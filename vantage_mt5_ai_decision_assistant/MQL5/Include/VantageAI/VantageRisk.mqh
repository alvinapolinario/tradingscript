//+------------------------------------------------------------------+
//| VantageRisk.mqh                                                  |
//| Broker-aware risk using tick size/value + OrderCalcProfit        |
//+------------------------------------------------------------------+
#ifndef VANTAGE_RISK_MQH
#define VANTAGE_RISK_MQH

#include "VantageTypes.mqh"
#include "VantageSymbol.mqh"

bool VantageCalcRiskFromLevels(const string symbol,
                               const VantageSymbolSpec &spec,
                               const ENUM_ORDER_TYPE order_type,
                               const double volume,
                               const double entry,
                               const double sl,
                               const double tp,
                               VantageRiskEstimate &risk)
  {
   ZeroMemory(risk);
   risk.entry = entry;
   risk.sl = sl;
   risk.tp = tp;
   risk.volume = volume;
   risk.available = false;
   risk.status = "RISK_CALCULATION_UNAVAILABLE";
   risk.last_error = 0;

   if(!spec.valid || volume <= 0.0 || entry <= 0.0)
     {
      risk.last_error = GetLastError();
      return false;
     }

   if(sl <= 0.0)
     {
      // No SL — money risk cannot be validated via OrderCalcProfit path for stop
      risk.status = "RISK_CALCULATION_UNAVAILABLE";
      risk.last_error = 0;
      Print("[VantageAI] Risk: SL missing — RISK_CALCULATION_UNAVAILABLE (no silent estimate).");
      return false;
     }

   risk.stop_distance_price = MathAbs(entry - sl);
   if(spec.point > 0.0)
      risk.stop_distance_points = risk.stop_distance_price / spec.point;
   else
      risk.stop_distance_points = 0.0;

   // Primary: broker OrderCalcProfit for stop outcome
   double profit_at_sl = 0.0;
   ResetLastError();
   if(!OrderCalcProfit(order_type, symbol, volume, entry, sl, profit_at_sl))
     {
      risk.last_error = GetLastError();
      risk.status = "RISK_CALCULATION_UNAVAILABLE";
      PrintFormat("[VantageAI] OrderCalcProfit(SL) failed err=%d — no silent gold-pip fallback.", risk.last_error);
      return false;
     }
   // Money at risk is magnitude of loss at SL
   risk.money_at_risk = MathAbs(profit_at_sl);

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity > 0.0)
      risk.equity_risk_pct = (risk.money_at_risk / equity) * 100.0;
   else
      risk.equity_risk_pct = 0.0;

   if(tp > 0.0)
     {
      double profit_at_tp = 0.0;
      ResetLastError();
      if(!OrderCalcProfit(order_type, symbol, volume, entry, tp, profit_at_tp))
        {
         risk.last_error = GetLastError();
         risk.status = "RISK_CALCULATION_UNAVAILABLE";
         PrintFormat("[VantageAI] OrderCalcProfit(TP) failed err=%d", risk.last_error);
         return false;
        }
      risk.reward_to_target = MathAbs(profit_at_tp);
      if(risk.money_at_risk > 0.0)
         risk.reward_risk_ratio = risk.reward_to_target / risk.money_at_risk;
     }

   double margin = 0.0;
   ResetLastError();
   if(!OrderCalcMargin(order_type, symbol, volume, entry, margin))
     {
      risk.last_error = GetLastError();
      risk.status = "RISK_CALCULATION_UNAVAILABLE";
      PrintFormat("[VantageAI] OrderCalcMargin failed err=%d", risk.last_error);
      return false;
     }
   risk.margin_required = margin;

   // Cross-check tick math (diagnostic only — OrderCalc* remains authoritative)
   if(spec.tick_size > 0.0)
     {
      double ticks = risk.stop_distance_price / spec.tick_size;
      double tick_val = (spec.tick_value_loss > 0.0) ? spec.tick_value_loss : spec.tick_value;
      if(tick_val <= 0.0)
        {
         risk.status = "RISK_CALCULATION_UNAVAILABLE";
         risk.last_error = GetLastError();
         Print("[VantageAI] Invalid tick value from broker — RISK_CALCULATION_UNAVAILABLE");
         return false;
        }
      double approx = ticks * tick_val * volume;
      // Soft consistency warning only
      if(risk.money_at_risk > 0.0 && MathAbs(approx - risk.money_at_risk) / risk.money_at_risk > 0.35)
         PrintFormat("[VantageAI] Note: tick approx (%.2f) differs from OrderCalcProfit (%.2f) — using OrderCalcProfit.",
                     approx, risk.money_at_risk);
     }

   risk.available = true;
   risk.status = "OK";
   return true;
  }

bool VantageCalcRiskFromOpenPosition(const string symbol,
                                     const VantageSymbolSpec &spec,
                                     const VantagePositionRow &pos,
                                     VantageRiskEstimate &risk)
  {
   ENUM_ORDER_TYPE ot = (pos.type == POSITION_TYPE_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   return VantageCalcRiskFromLevels(symbol, spec, ot, pos.volume, pos.price_open, pos.sl, pos.tp, risk);
  }

string VantageRiskToJson(const VantageRiskEstimate &risk)
  {
   string j = "{";
   j += "\"available\":" + (risk.available ? "true" : "false") + ",";
   j += "\"status\":\"" + JsonEscape(risk.status) + "\",";
   j += "\"last_error\":" + IntegerToString(risk.last_error) + ",";
   j += "\"stop_distance_price\":" + DoubleToJson(risk.stop_distance_price, 8) + ",";
   j += "\"stop_distance_points\":" + DoubleToJson(risk.stop_distance_points, 4) + ",";
   j += "\"money_at_risk\":" + DoubleToJson(risk.money_at_risk, 4) + ",";
   j += "\"equity_risk_pct\":" + DoubleToJson(risk.equity_risk_pct, 4) + ",";
   j += "\"reward_to_target\":" + DoubleToJson(risk.reward_to_target, 4) + ",";
   j += "\"reward_risk_ratio\":" + DoubleToJson(risk.reward_risk_ratio, 4) + ",";
   j += "\"margin_required\":" + DoubleToJson(risk.margin_required, 4) + ",";
   j += "\"entry\":" + DoubleToJson(risk.entry, 8) + ",";
   j += "\"sl\":" + DoubleToJson(risk.sl, 8) + ",";
   j += "\"tp\":" + DoubleToJson(risk.tp, 8) + ",";
   j += "\"volume\":" + DoubleToJson(risk.volume, 4);
   j += "}";
   return j;
  }

#endif
//+------------------------------------------------------------------+
