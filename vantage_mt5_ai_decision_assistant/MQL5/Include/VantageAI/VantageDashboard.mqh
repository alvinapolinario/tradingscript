//+------------------------------------------------------------------+
//| VantageDashboard.mqh                                             |
//| Compact on-chart advisory panel                                  |
//+------------------------------------------------------------------+
#ifndef VANTAGE_DASHBOARD_MQH
#define VANTAGE_DASHBOARD_MQH

#include "VantageTypes.mqh"
#include "VantageAccount.mqh"
#include "VantageDecision.mqh"
#include "VantageHistory.mqh"
#include "VantageGoldSMC.mqh"
#include "VantageLiquidityGrab.mqh"

class CVantageDashboard
  {
private:
   string m_prefix;
   int    m_x;
   int    m_y;

   void SetLabel(const string name, const int row, const string text, const color clr)
     {
      string id = m_prefix + name;
      if(ObjectFind(0, id) < 0)
        {
         ObjectCreate(0, id, OBJ_LABEL, 0, 0, 0);
         ObjectSetInteger(0, id, OBJPROP_CORNER, CORNER_LEFT_UPPER);
         ObjectSetInteger(0, id, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, id, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, id, OBJPROP_FONTSIZE, 8);
        }
      ObjectSetInteger(0, id, OBJPROP_XDISTANCE, m_x);
      ObjectSetInteger(0, id, OBJPROP_YDISTANCE, m_y + row * 14);
      ObjectSetString(0, id, OBJPROP_TEXT, text);
      ObjectSetInteger(0, id, OBJPROP_COLOR, clr);
     }

public:
   CVantageDashboard(void) : m_prefix("VAI_"), m_x(8), m_y(18) {}

   void Clear(void)
     {
      int total = ObjectsTotal(0, 0, -1);
      for(int i = total - 1; i >= 0; i--)
        {
         string name = ObjectName(0, i, 0, -1);
         if(StringFind(name, m_prefix) == 0)
            ObjectDelete(0, name);
        }
     }

   void Render(const VantageAccountInfo &acct,
               const VantageSymbolSpec &spec,
               const VantagePriceSnap &px,
               const string backend_status,
               const string candle_status,
               const VantageDecisionState &dec,
               const VantagePositionSummary &pos,
               const VantageRiskEstimate &risk,
               const string resp_ts,
               const string resp_age,
               const double equity,
               const double floating_pl_pct,
               const double float_profit_target_pct,
               const bool float_profit_target_hit,
               const int cal_year,
               const int cal_month,
               const double month_pl,
               const double month_pct,
               const int month_deals,
               const VantageTradeStats &stats,
               const VantagePullbackResult &pb,
               const bool show_pullback,
               const VantageGoldSMCResult &gsm,
               const bool show_gold_smc,
               const VantageLiquidityGrabResult &lg,
               const bool show_liq_grab)
     {
      int r = 0;
      color riskCol = clrSilver;
      if(dec.risk_status == "CRITICAL" || dec.exceeds_max_position_risk)
         riskCol = clrRed;
      else if(dec.risk_status == "VERY_HIGH" || dec.risk_status == "HIGH")
         riskCol = clrOrange;
      else if(dec.risk_status == "MODERATE")
         riskCol = clrGold;
      else if(dec.risk_status == "LOW")
         riskCol = clrLime;

      color floatCol = clrSilver;
      if(float_profit_target_hit)
         floatCol = clrLime;
      else if(floating_pl_pct < 0.0)
         floatCol = clrOrange;

      SetLabel("t0", r++, "Vantage MT5 AI Decision Assistant (ADVISORY)", clrAqua);
      SetLabel("t1", r++, "Broker: " + acct.company + " | " + acct.server, clrSilver);
      SetLabel("t2", r++, "Account: " + acct.login_masked + " | " + VantageMarginModeName(acct.margin_mode) + " | " + acct.currency, clrSilver);
      SetLabel("t3", r++, "Symbol: " + spec.symbol + " Digits:" + IntegerToString(spec.digits) +
               " Contract:" + DoubleToString(spec.contract_size, 0) +
               " Spread:" + IntegerToString(px.spread_points) + (px.high_spread ? " HIGH" : ""),
               px.high_spread ? clrOrange : clrWhite);
      SetLabel("t4", r++, "Backend: " + backend_status + " | Candle: " + candle_status, clrSilver);
      SetLabel("t5", r++, "Trend: " + dec.trend + " | Market State: " + dec.market_state, clrYellow);
      SetLabel("tbias", r++, "Chart Bias (" + IntegerToString(dec.bias_lookback) + " bars): Bullish " +
               DoubleToString(dec.bullish_pct, 1) + "% | Bearish " + DoubleToString(dec.bearish_pct, 1) + "%" +
               (dec.neutral_pct > 0.05 ? " | Flat " + DoubleToString(dec.neutral_pct, 1) + "%" : ""),
               (dec.bullish_pct >= dec.bearish_pct) ? clrLime : clrOrange);
      SetLabel("tind", r++, "Indicator Bias: Bullish " + DoubleToString(dec.indicator_bullish_pct, 1) +
               "% | Bearish " + DoubleToString(dec.indicator_bearish_pct, 1) + "%",
               (dec.indicator_bullish_pct >= dec.indicator_bearish_pct) ? clrLime : clrOrange);

      SetLabel("t6", r++, "New Entry Decision: " + dec.new_entry_decision, clrAqua);
      SetLabel("t7", r++, "Existing Position Decision: " + dec.existing_position_decision,
               (dec.existing_position_decision == "CRITICAL_RISK" || dec.existing_position_decision == "HOLD_WITH_CAUTION") ? clrOrange : clrWhite);

      string posline = "Positions: " + IntegerToString(pos.count);
      if(pos.has_position)
         posline += " | FloatPL=" + DoubleToString(pos.total_floating_pl, 2) +
                    " | BuyVol=" + DoubleToString(pos.total_buy_volume, 2);
      SetLabel("t8", r++, posline, clrSilver);

      SetLabel("teq", r++, "Equity: " + DoubleToString(equity, 2) +
               " | Floating P/L of Equity: " + DoubleToString(floating_pl_pct, 2) + "%", floatCol);
      SetLabel("tft", r++, "Float Profit Target: " + DoubleToString(float_profit_target_pct, 1) + "%" +
               (float_profit_target_hit ? "  << TARGET HIT — consider taking profit" : ""),
               float_profit_target_hit ? clrLime : clrSilver);

      SetLabel("t9", r++, "Position Risk Status: " + dec.risk_status, riskCol);
      if(risk.available && pos.has_position)
        {
         SetLabel("t10", r++, "Entry: " + DoubleToString(risk.entry, spec.digits) +
                  " | SL: " + DoubleToString(risk.sl, spec.digits), clrWhite);
         SetLabel("t11", r++, "Estimated SL Loss: " + DoubleToString(risk.money_at_risk, 2) + " USD", riskCol);
         SetLabel("t12", r++, "Equity Risk %: " + DoubleToString(risk.equity_risk_pct, 2) + "%", riskCol);
        }
      else
         SetLabel("t10", r++, "Risk: " + risk.status, clrOrange);

      SetLabel("t13", r++, "Immediate Support: " + dec.immediate_support, clrLime);
      SetLabel("t14", r++, "Recovery Level 1: " + dec.recovery_level_1 + " | Level 2: " + dec.recovery_level_2, clrSilver);
      SetLabel("t15", r++, "Bullish Confirmation: " + dec.bullish_confirmation, clrSilver);
      SetLabel("t16", r++, "Technical Invalidation: " + dec.technical_invalidation, clrOrange);
      SetLabel("t17", r++, "New Position Allowed: " + (dec.new_position_allowed ? "YES" : "NO") +
               " | Add Position Allowed: " + (dec.add_position_allowed ? "YES" : "NO"),
               (dec.new_position_allowed || dec.add_position_allowed) ? clrLime : clrRed);

      if(dec.exceeds_max_position_risk || dec.risk_status == "CRITICAL")
         SetLabel("twarn", r++, "WARNING: " + dec.risk_warning, clrRed);
      if(float_profit_target_hit)
         SetLabel("tfpwarn", r++, "PROFIT TARGET: Floating P/L reached " +
                  DoubleToString(float_profit_target_pct, 1) + "% of equity. Limit/take profit manually.", clrLime);

      color mCol = (month_pct > 0.0) ? clrLime : ((month_pct < 0.0) ? clrOrange : clrSilver);
      SetLabel("tcal", r++, "History " + IntegerToString(cal_year) + "." +
               (cal_month < 10 ? "0" : "") + IntegerToString(cal_month) + ": Month P/L " + DoubleToString(month_pl, 2) +
               " (" + DoubleToString(month_pct, 2) + "% eq) | Deals " + IntegerToString(month_deals) +
               " | See monitor calendar", mCol);

      if(stats.ok)
        {
         color wrCol = (stats.win_rate_pct >= 50.0) ? clrLime : clrOrange;
         SetLabel("tstat1", r++, "Trades: " + IntegerToString(stats.total_trades) +
                  " | W " + IntegerToString(stats.wins) + " / L " + IntegerToString(stats.losses) +
                  " / BE " + IntegerToString(stats.breakeven) +
                  " | WinRate " + DoubleToString(stats.win_rate_pct, 1) + "%", wrCol);
         SetLabel("tstat2", r++, "Net " + DoubleToString(stats.net_profit, 2) +
                  " | PF " + DoubleToString(stats.profit_factor, 2) +
                  " | MaxDD " + DoubleToString(stats.max_drawdown, 2) +
                  " (" + DoubleToString(stats.max_drawdown_pct, 1) + "%)" +
                  " | AvgWin " + DoubleToString(stats.avg_win, 2) +
                  " / AvgLoss " + DoubleToString(stats.avg_loss, 2), clrSilver);
        }

      if(show_pullback && pb.valid)
        {
         color pbCol = clrGold;
         if(pb.dominant_dir > 0) pbCol = clrLime;
         else if(pb.dominant_dir < 0) pbCol = clrOrange;
         SetLabel("tpb0", r++, "--- PULLBACK PROBABILITY (advisory) ---", clrAqua);
         SetLabel("tpb1", r++, "Trend: " + pb.dominant_trend +
                  " | PB " + DoubleToString(pb.pullback_prob, 0) +
                  "% Cont " + DoubleToString(pb.continuation_prob, 0) +
                  "% Cons " + DoubleToString(pb.consolidation_prob, 0) +
                  "% Rev " + DoubleToString(pb.reversal_prob, 0) + "%", pbCol);
         SetLabel("tpb2", r++, "Ext " + DoubleToString(pb.extension_score, 0) +
                  " | Strength " + DoubleToString(pb.trend_strength_score, 0) +
                  " | Quality " + DoubleToString(pb.pullback_quality, 0), clrSilver);
         SetLabel("tpb3", r++, "State: " + pb.market_state, clrYellow);
         SetLabel("tpb4", r++, StringSubstr(pb.short_reason != "" ? pb.short_reason : pb.explanation, 0, 90), clrSilver);
        }

      if(show_gold_smc && gsm.valid)
        {
         SetLabel("tsmc0", r++, "--- GOLD SMC INTELLIGENCE (advisory) ---", clrAqua);
         if(!gsm.gold_symbol_valid || !gsm.engine_enabled)
           {
            SetLabel("tsmc1", r++, StringSubstr(gsm.disable_reason != "" ? gsm.disable_reason : gsm.status_line, 0, 96), clrOrange);
            SetLabel("tsmc2", r++, "Status: " + gsm.status_line, clrSilver);
           }
         else
           {
            SetLabel("tsmc1", r++, "Symbol: " + gsm.base_symbol + " | " + gsm.status_line, clrLime);
            SetLabel("tsmc2", r++, "Macro " + SmcDirectionToString(gsm.macro_bias) +
                     " | H4 " + SmcDirectionToString(gsm.h4_bias) +
                     " | H1 " + SmcDirectionToString(gsm.h1_bias), clrYellow);
            SetLabel("tsmc3", r++, "M15 " + SmcDirectionToString(gsm.m15_bias) +
                     " | M5 " + SmcDirectionToString(gsm.m5_bias) +
                     " | Evt " + (gsm.latest_structure_event != "" ? gsm.latest_structure_event : "None"), clrSilver);
            SetLabel("tsmc4", r++, StringSubstr(gsm.m5_context != "" ? gsm.m5_context : gsm.structure_status, 0, 96), clrSilver);
            SetLabel("tsmc5", r++, "Draw " + (gsm.liquidity_draw != "" ? gsm.liquidity_draw : "—") +
                     " | BSL " + (gsm.nearest_bsl > 0 ? DoubleToString(gsm.nearest_bsl, _Digits) : "—") +
                     " | SSL " + (gsm.nearest_ssl > 0 ? DoubleToString(gsm.nearest_ssl, _Digits) : "—"), clrAqua);
            SetLabel("tsmc6", r++, "POI " + (gsm.primary_poi_dir != "" ? gsm.primary_poi_dir + " " : "") +
                     (gsm.primary_poi_type != "" ? gsm.primary_poi_type : "None") +
                     (gsm.entry_zone != "" ? " " + gsm.entry_zone : ""), clrWhite);
            SetLabel("tsmc7", r++, "PD " + (gsm.premium_discount != "" ? gsm.premium_discount : "—") +
                     " (" + DoubleToString(gsm.dealing_pct, 0) + "%)" +
                     " | OTE " + (gsm.price_in_ote ? "IN" : (gsm.poi_overlaps_ote ? "POI" : "out")) +
                     " | PO3 " + (gsm.po3_bias != "" && gsm.po3_bias != "None" ? gsm.po3_bias : "—"), clrAqua);
            SetLabel("tsmc8", r++, "Setup " + (gsm.setup_direction != "" ? gsm.setup_direction + " " : "") +
                     (gsm.setup_type != "" ? gsm.setup_type : "No Valid SMC Setup") +
                     " | " + DoubleToString(gsm.confidence_score, 0) + " (" + gsm.quality_grade + ")", clrWhite);
            SetLabel("tsmc9", r++, StringSubstr(
                     (gsm.entry_zone != "" ? "Entry " + gsm.entry_zone + " [" + gsm.entry_status + "] | " : "") +
                     (gsm.targets != "" ? gsm.targets : "") +
                     (gsm.estimated_rr > 0 ? " R:R " + DoubleToString(gsm.estimated_rr, 1) : ""), 0, 96), clrSilver);
            SetLabel("tsmc10", r++, StringSubstr(
                     (gsm.invalidation != "" ? "Inv " + gsm.invalidation : "") , 0, 96), clrMagenta);
            SetLabel("tsmc11", r++, StringSubstr(gsm.recommendation != "" ? gsm.recommendation : gsm.displacement_status, 0, 96), clrGold);
            if(gsm.last_alert != "")
               SetLabel("tsmc12", r++, StringSubstr("Alert: " + gsm.last_alert, 0, 96), clrOrange);
           }
        }

      if(show_liq_grab)
        {
         SetLabel("tlg0", r++, "--- LIQUIDITY GRAB MONITOR (advisory) ---", clrAqua);
         if(!lg.gold_symbol_valid && lg.disable_reason != "")
            SetLabel("tlg1", r++, StringSubstr(lg.disable_reason, 0, 96), clrOrange);
         else if(lg.status == LG_STATUS_NO_VALID_SETUP)
           {
            SetLabel("tlg1", r++, "Status: NO VALID SETUP | HTF " + lg.higher_timeframe_bias, clrSilver);
            SetLabel("tlg2", r++, "Session: " + lg.session_name + " | " + lg.action_guidance, clrGray);
           }
         else
           {
            SetLabel("tlg1", r++, "Status: " + lg.status_line + " | Score " + DoubleToString(lg.confidence_score, 0), clrYellow);
            SetLabel("tlg2", r++, "Dir: " + LgDirectionToString(lg.direction), clrWhite);
            SetLabel("tlg3", r++, "Level: " + lg.liquidity_level_type + " @ " +
                     DoubleToString(lg.liquidity_level_price, _Digits), clrSilver);
            SetLabel("tlg4", r++, "Sweep " + DoubleToString(lg.sweep_price, _Digits) +
                     " | MSS " + (lg.mss_detected ? "yes" : "no") +
                     " | Disp " + (lg.displacement_detected ? "yes" : "no"), clrSilver);
            SetLabel("tlg5", r++, StringSubstr(lg.action_guidance, 0, 96), clrGold);
            if(lg.news_restricted)
               SetLabel("tlg6", r++, "NEWS_RESTRICTED — reduced confidence", clrOrange);
           }
        }

      SetLabel("t18", r++, "Primary Action: " + dec.primary_action + " | Resp: " + resp_ts + " (" + resp_age + ")", clrYellow);
      SetLabel("t19", r++, "Mode: ADVISORY ONLY — never closes/modifies positions", clrGray);
      ChartRedraw(0);
     }
  };

#endif
//+------------------------------------------------------------------+
