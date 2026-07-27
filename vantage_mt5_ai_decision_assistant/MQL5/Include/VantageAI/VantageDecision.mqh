//+------------------------------------------------------------------+
//| VantageDecision.mqh                                              |
//| Local new-entry vs position-risk classification (advisory)       |
//+------------------------------------------------------------------+
#ifndef VANTAGE_DECISION_MQH
#define VANTAGE_DECISION_MQH

#include "VantageTypes.mqh"

struct VantageDecisionState
  {
   string trend;
   string market_state;
   string new_entry_decision;
   string existing_position_decision;
   string risk_status;
   bool   exceeds_max_position_risk;
   bool   new_position_allowed;
   bool   add_position_allowed;
   string immediate_support;
   string recovery_level_1;
   string recovery_level_2;
   string bullish_confirmation;
   string technical_invalidation;
   string risk_warning;
   string primary_action;
   string note;
   double bullish_pct;
   double bearish_pct;
   double neutral_pct;
   int    bias_lookback;
   double indicator_bullish_pct;
   double indicator_bearish_pct;
  };

string VantageClassifyRiskStatus(const double equity_risk_pct,
                                 const bool has_position,
                                 const bool risk_available,
                                 const double low_max,
                                 const double mod_max,
                                 const double high_max,
                                 const double very_high_max)
  {
   if(!has_position)
      return "NONE";
   if(!risk_available)
      return "UNAVAILABLE";
   if(equity_risk_pct < low_max) return "LOW";
   if(equity_risk_pct < mod_max) return "MODERATE";
   if(equity_risk_pct < high_max) return "HIGH";
   if(equity_risk_pct < very_high_max) return "VERY_HIGH";
   return "CRITICAL";
  }

void VantageBuildLocalDecision(const VantageTechnicalSnap &tech,
                               const VantagePositionSummary &pos,
                               const VantageRiskEstimate &risk,
                               const VantagePriceSnap &px,
                               const string trend_name,
                               const double max_position_risk_pct,
                               const double risk_low_max,
                               const double risk_mod_max,
                               const double risk_high_max,
                               const double risk_vh_max,
                               const double rsi_exhaust,
                               const double imm_sup_lo,
                               const double imm_sup_hi,
                               const double recovery_1,
                               const double recovery_2,
                               const double bullish_conf,
                               VantageDecisionState &out,
                               const int price_digits = 2)
  {
   ZeroMemory(out);
   out.trend = trend_name;
   const int digs = (price_digits < 0 ? 2 : price_digits);
   out.immediate_support = DoubleToString(imm_sup_lo, digs) + "-" + DoubleToString(imm_sup_hi, digs);
   out.recovery_level_1 = DoubleToString(recovery_1, digs);
   out.recovery_level_2 = DoubleToString(recovery_2, digs);
   out.bullish_confirmation = DoubleToString(bullish_conf, digs);
   out.new_position_allowed = false;
   out.add_position_allowed = false;
   out.risk_warning = "";

   bool risk_ok = risk.available && risk.status == "OK";
   out.risk_status = VantageClassifyRiskStatus(risk.equity_risk_pct, pos.has_position, risk_ok,
                                               risk_low_max, risk_mod_max, risk_high_max, risk_vh_max);
   out.exceeds_max_position_risk = (pos.has_position && risk_ok && risk.equity_risk_pct >= max_position_risk_pct);

   if(trend_name == "BEARISH" && tech.rsi14 <= rsi_exhaust)
      out.market_state = "BEARISH_EXHAUSTED";
   else if(tech.retest_pending || tech.structure_note != "")
      out.market_state = (StringFind(tech.structure_note, "IMPULSE") >= 0 ? "BEARISH_IMPULSE" : trend_name);
   else if(px.high_spread)
      out.market_state = "HIGH_SPREAD";
   else
      out.market_state = trend_name;

   // Existing position
   if(!pos.has_position)
      out.existing_position_decision = "NONE";
   else if(!risk_ok)
      out.existing_position_decision = "POSITION_DATA_UNAVAILABLE";
   else if(out.risk_status == "CRITICAL" || out.exceeds_max_position_risk)
     {
      out.risk_warning = "Position risk exceeds configured maximum. Do not add exposure or widen the stop.";
      if(pos.total_floating_pl < 0.0)
         out.existing_position_decision = "CRITICAL_RISK";
      else
         out.existing_position_decision = "HOLD_WITH_CAUTION";
     }
   else if(out.risk_status == "HIGH" || out.risk_status == "VERY_HIGH")
      out.existing_position_decision = "HOLD_WITH_CAUTION";
   else if(pos.total_floating_pl > 0.0 && tech.bear_reject && trend_name == "BEARISH")
      out.existing_position_decision = "PROTECT_PROFIT";
   else if(pos.total_floating_pl < 0.0 && (tech.oversized_candle || trend_name == "BEARISH"))
      out.existing_position_decision = "EXIT_WARNING";
   else
      out.existing_position_decision = "HOLD";

   if(pos.has_position && risk.sl > 0.0)
     {
      if(pos.total_buy_volume >= pos.total_sell_volume)
         out.technical_invalidation = "Close below SL " + DoubleToString(risk.sl, 2);
      else
         out.technical_invalidation = "Close above SL " + DoubleToString(risk.sl, 2);
     }
   else if(trend_name == "BEARISH")
      out.technical_invalidation = "Break and hold above " + out.bullish_confirmation;

   // New entry (mirrors backend rule engine — used live as fallback + Strategy Tester)
   if(px.high_spread)
      out.new_entry_decision = "HIGH_SPREAD";
   else if(out.exceeds_max_position_risk || out.risk_status == "CRITICAL")
      out.new_entry_decision = "RISK_BLOCKED";
   else if(pos.has_position)
      out.new_entry_decision = "NO_NEW_TRADE";
   else if(tech.retest_pending ||
           StringFind(tech.structure_note, "IMPULSE") >= 0 ||
           StringFind(tech.structure_note, "MULTI_LEVEL") >= 0)
      out.new_entry_decision = "WAIT";
   else if(out.market_state == "BEARISH_EXHAUSTED")
      out.new_entry_decision = "NO_NEW_TRADE";
   else if(trend_name == "BULLISH" && tech.bull_reject && tech.rsi14 < 60.0)
      out.new_entry_decision = "BUY_ALLOWED";
   else if(trend_name == "BEARISH" && tech.bear_reject && tech.rsi14 > rsi_exhaust)
      out.new_entry_decision = "SELL_ALLOWED";
   else if(tech.support_break)
      out.new_entry_decision = "WAIT";
   else
      out.new_entry_decision = "NO_NEW_TRADE";

   out.new_position_allowed = (out.new_entry_decision == "BUY_ALLOWED" || out.new_entry_decision == "SELL_ALLOWED");
   out.add_position_allowed = false;

   if(out.existing_position_decision == "CRITICAL_RISK")
      out.primary_action = "CRITICAL_RISK";
   else if(out.existing_position_decision == "HOLD_WITH_CAUTION")
      out.primary_action = "HOLD_WITH_CAUTION";
   else if(out.existing_position_decision == "PROTECT_PROFIT")
      out.primary_action = "PROTECT_PROFIT";
   else if(out.existing_position_decision == "EXIT_WARNING")
      out.primary_action = "EXIT_WARNING";
   else if(out.existing_position_decision == "HOLD")
      out.primary_action = "HOLD";
   else if(out.new_entry_decision == "HIGH_SPREAD")
      out.primary_action = "HIGH_SPREAD";
   else if(out.new_entry_decision == "WAIT")
      out.primary_action = "WAIT_FOR_RETEST";
   else if(out.new_entry_decision == "BUY_ALLOWED")
      out.primary_action = "BUY_WATCH";
   else if(out.new_entry_decision == "SELL_ALLOWED")
      out.primary_action = "SELL_WATCH";
   else if(out.new_entry_decision == "RISK_BLOCKED")
      out.primary_action = "NO_NEW_TRADE";
   else
      out.primary_action = "NO_NEW_TRADE";

   out.bullish_pct = tech.bullish_pct;
   out.bearish_pct = tech.bearish_pct;
   out.neutral_pct = tech.neutral_pct;
   out.bias_lookback = tech.bias_lookback;
   out.indicator_bullish_pct = tech.indicator_bullish_pct;
   out.indicator_bearish_pct = tech.indicator_bearish_pct;

   out.note = out.risk_warning;
  }

#endif
//+------------------------------------------------------------------+
