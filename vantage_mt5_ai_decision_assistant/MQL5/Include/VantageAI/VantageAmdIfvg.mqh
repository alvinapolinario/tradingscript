//+------------------------------------------------------------------+
//| VantageAmdIfvg.mqh — AMD + iFVG strategy (Gold / XAUUSD)         |
//+------------------------------------------------------------------+
#ifndef VANTAGE_AMD_IFVG_MQH
#define VANTAGE_AMD_IFVG_MQH

#include "VantageTypes.mqh"
#include "VantageAmdIfvgTypes.mqh"
#include "VantageGoldSMCValidator.mqh"

#define AMD_OBJ_PREFIX "VAI_AMDIFVG_"

class CVantageAmdIfvg
  {
private:
   string                  m_symbol;
   VantageAmdIfvgConfig    m_cfg;
   CVantageGoldSymbolValidator m_validator;
   datetime                m_last_m5_bar;
   VantageAmdIfvgResult    m_last;

   double GetAtr(const ENUM_TIMEFRAMES tf, const int period=14)
     {
      int h = iATR(m_symbol, tf, period);
      if(h == INVALID_HANDLE) return 0.0;
      double b[];
      ArraySetAsSeries(b, true);
      if(CopyBuffer(h, 0, 1, 1, b) < 1) { IndicatorRelease(h); return 0.0; }
      IndicatorRelease(h);
      return b[0];
     }

   bool CopyClosed(const ENUM_TIMEFRAMES tf, const int count, MqlRates &rates[])
     {
      ArraySetAsSeries(rates, true);
      int n = CopyRates(m_symbol, tf, 1, count, rates);
      return (n >= count / 2);
     }

   string DecisionStr(const ENUM_AMDIFVG_DECISION d) const
     {
      if(d == AMDIFVG_DEC_BUY) return "BUY";
      if(d == AMDIFVG_DEC_SELL) return "SELL";
      if(d == AMDIFVG_DEC_WAIT) return "WAIT";
      return "NO_TRADE";
     }

   string SetupStateStr(const ENUM_AMDIFVG_SETUP_STATE s) const
     {
      switch(s)
        {
         case AMDIFVG_ST_ACCUMULATION: return "ACCUMULATION_DETECTED";
         case AMDIFVG_ST_WAIT_SWEEP: return "WAITING_FOR_LIQUIDITY_SWEEP";
         case AMDIFVG_ST_MANIPULATION: return "MANIPULATION_DETECTED";
         case AMDIFVG_ST_WAIT_DISP: return "WAITING_FOR_DISPLACEMENT";
         case AMDIFVG_ST_WAIT_MSS: return "WAITING_FOR_MSS";
         case AMDIFVG_ST_WAIT_IFVG: return "WAITING_FOR_IFVG_INVERSION";
         case AMDIFVG_ST_WAIT_RETRACE: return "WAITING_FOR_RETRACE";
         case AMDIFVG_ST_ENTRY_ZONE: return "ENTRY_ZONE_ACTIVE";
         case AMDIFVG_ST_INVALIDATED: return "INVALIDATED";
         case AMDIFVG_ST_EXPIRED: return "EXPIRED";
         default: return "SEARCHING_FOR_ACCUMULATION";
        }
     }

   void ClearObjects()
     {
      if(!m_cfg.show_chart_objects) return;
      int total = ObjectsTotal(0, 0, -1);
      for(int i = total - 1; i >= 0; i--)
        {
         string name = ObjectName(0, i, 0, -1);
         if(StringFind(name, AMD_OBJ_PREFIX) == 0)
            ObjectDelete(0, name);
        }
     }

   void DrawSetup(const VantageAmdIfvgResult &r)
     {
      if(!m_cfg.show_chart_objects) return;
      ClearObjects();
      if(r.acc_detected)
        {
         string rn = AMD_OBJ_PREFIX + "ACC";
         ObjectCreate(0, rn, OBJ_RECTANGLE, 0, TimeCurrent() - PeriodSeconds(m_cfg.tf_setup) * 20, r.acc_high,
                      TimeCurrent(), r.acc_low);
         ObjectSetInteger(0, rn, OBJPROP_COLOR, clrDimGray);
         ObjectSetInteger(0, rn, OBJPROP_FILL, true);
         ObjectSetInteger(0, rn, OBJPROP_BACK, true);
        }
      if(r.ifvg_detected)
        {
         string zn = AMD_OBJ_PREFIX + "IFVG";
         ObjectCreate(0, zn, OBJ_RECTANGLE, 0, TimeCurrent() - PeriodSeconds(m_cfg.tf_entry) * 10, r.ifvg_upper,
                      TimeCurrent() + PeriodSeconds(m_cfg.tf_entry) * 5, r.ifvg_lower);
         ObjectSetInteger(0, zn, OBJPROP_COLOR, r.ifvg_direction == "BEARISH" ? clrIndianRed : clrMediumSeaGreen);
         ObjectSetInteger(0, zn, OBJPROP_FILL, true);
         ObjectSetInteger(0, zn, OBJPROP_BACK, true);
        }
     }

public:
   CVantageAmdIfvg(void) : m_symbol(""), m_last_m5_bar(0) { ZeroMemory(m_last); }

   bool Init(const string symbol, const VantageAmdIfvgConfig &cfg)
     {
      m_symbol = symbol;
      m_cfg = cfg;
      m_last_m5_bar = 0;
      ZeroMemory(m_last);
      m_validator.Configure(cfg.gold_aliases, cfg.allow_suffix, cfg.allow_prefix);
      return true;
     }

   bool Evaluate(const bool force, VantageAmdIfvgResult &out)
     {
      string base = "";
      ZeroMemory(out);
      out.valid = false;
      out.engine_enabled = m_cfg.enable;
      out.symbol = m_symbol;
      out.base_symbol = m_symbol;
      out.decision = "NO_TRADE";
      out.setup_state = SetupStateStr(AMDIFVG_ST_SEARCH);
      out.amd_phase = "SEARCHING";
      out.action_guidance = "Advisory only — confirm on closed candles.";

      if(!m_cfg.enable)
        {
         out.disable_reason = "Engine disabled";
         return false;
        }

      if(!m_validator.IsApprovedGoldSymbol(m_symbol, base))
        {
         out.gold_symbol_valid = false;
         out.base_symbol = base;
         out.disable_reason = VANTAGE_AMDIFVG_DISABLE_MSG;
         out.reasoning = VANTAGE_AMDIFVG_DISABLE_MSG;
         out.valid = true;
         return true;
        }
      out.gold_symbol_valid = true;
      out.base_symbol = base;

      MqlRates m15[], m5[];
      if(!CopyClosed(m_cfg.tf_setup, 80, m15) || !CopyClosed(m_cfg.tf_entry, 80, m5))
        {
         out.reasoning = "Insufficient history";
         out.valid = true;
         return true;
        }

      datetime bar_time = m5[0].time;
      bool new_bar = (bar_time != m_last_m5_bar);
      if(!new_bar && !force) { out = m_last; return out.valid; }

      double atr15 = GetAtr(m_cfg.tf_setup);
      double atr5 = GetAtr(m_cfg.tf_entry);
      if(atr15 <= 0) atr15 = m15[0].high - m15[0].low;
      if(atr5 <= 0) atr5 = m5[0].high - m5[0].low;

      double spread = (double)SymbolInfoInteger(m_symbol, SYMBOL_SPREAD);
      if(spread > m_cfg.max_spread_pts)
         out.warnings = "High spread;";

      // Accumulation on M15 window
      int w = MathMin(ArraySize(m15), m_cfg.acc_max_candles);
      double rh = m15[0].high, rl = m15[0].low;
      for(int i = 0; i < w; i++)
        {
         if(m15[i].high > rh) rh = m15[i].high;
         if(m15[i].low < rl) rl = m15[i].low;
        }
      double width = rh - rl;
      out.acc_detected = (w >= m_cfg.acc_min_candles && width <= m_cfg.acc_max_width_atr * atr15);
      out.acc_high = rh;
      out.acc_low = rl;
      out.acc_quality = out.acc_detected ? 70.0 : 0.0;

      ENUM_AMDIFVG_SETUP_STATE st = out.acc_detected ? AMDIFVG_ST_WAIT_SWEEP : AMDIFVG_ST_SEARCH;
      ENUM_AMDIFVG_PHASE phase = out.acc_detected ? AMDIFVG_PH_ACCUMULATION : AMDIFVG_PH_SEARCH;
      string narr = "";
      string trade_bias = "";

      // Manipulation sweep on latest M15 bar
      if(out.acc_detected)
        {
         MqlRates c = m15[0];
         double sup = c.high - rh;
         double sdn = rl - c.low;
         if(sup >= m_cfg.sweep_min_atr * atr15 && sup <= m_cfg.sweep_max_atr * atr15 && c.close < rh)
           {
            out.manip_detected = true;
            out.manip_direction = "BUY_SIDE_SWEEP";
            out.manip_sweep_price = c.high;
            out.manip_quality = 75.0;
            trade_bias = "BEARISH";
            st = AMDIFVG_ST_MANIPULATION;
            phase = AMDIFVG_PH_MANIPULATION;
            narr += "Buy-side sweep above accumulation; ";
           }
         else if(sdn >= m_cfg.sweep_min_atr * atr15 && sdn <= m_cfg.sweep_max_atr * atr15 && c.close > rl)
           {
            out.manip_detected = true;
            out.manip_direction = "SELL_SIDE_SWEEP";
            out.manip_sweep_price = c.low;
            out.manip_quality = 75.0;
            trade_bias = "BULLISH";
            st = AMDIFVG_ST_MANIPULATION;
            phase = AMDIFVG_PH_MANIPULATION;
            narr += "Sell-side sweep below accumulation; ";
           }
        }

      // FVG + iFVG on M5 (3-candle)
      if(ArraySize(m5) >= 3)
        {
         MqlRates c1 = m5[2], c2 = m5[1], c3 = m5[0];
         if(c3.low > c1.high)
           {
            double gap = c3.low - c1.high;
            if(gap >= m_cfg.fvg_min_gap_atr * atr5)
              {
               out.ifvg_orig_direction = "BULLISH";
               out.ifvg_lower = c1.high;
               out.ifvg_upper = c3.low;
               if(m_cfg.ifvg_require_body_close && c3.close < c1.high - m_cfg.ifvg_min_break_atr * atr5)
                 {
                  out.ifvg_detected = true;
                  out.ifvg_direction = "BEARISH";
                  st = AMDIFVG_ST_WAIT_RETRACE;
                  narr += "Bullish FVG inverted bearish; ";
                 }
              }
           }
         if(c3.high < c1.low)
           {
            double gap = c1.low - c3.high;
            if(gap >= m_cfg.fvg_min_gap_atr * atr5)
              {
               out.ifvg_orig_direction = "BEARISH";
               out.ifvg_lower = c3.high;
               out.ifvg_upper = c1.low;
               if(m_cfg.ifvg_require_body_close && c3.close > c1.low + m_cfg.ifvg_min_break_atr * atr5)
                 {
                  out.ifvg_detected = true;
                  out.ifvg_direction = "BULLISH";
                  st = AMDIFVG_ST_WAIT_RETRACE;
                  narr += "Bearish FVG inverted bullish; ";
                 }
              }
           }
        }

      if(out.ifvg_detected)
        {
         out.ifvg_mid = (out.ifvg_lower + out.ifvg_upper) / 2.0;
         double bid = SymbolInfoDouble(m_symbol, SYMBOL_BID);
         if(bid >= out.ifvg_lower && bid <= out.ifvg_upper)
           {
            st = AMDIFVG_ST_ENTRY_ZONE;
            out.ifvg_retests = 1;
           }
        }

      // MSS heuristic on M5
      if(out.manip_detected && ArraySize(m5) >= 5)
        {
         double body = MathAbs(m5[0].close - m5[0].open);
         if(body >= m_cfg.disp_min_body_atr * atr5)
           {
            out.mss_detected = true;
            out.mss_direction = trade_bias;
            out.mss_level = trade_bias == "BEARISH" ? m5[1].low : m5[1].high;
            phase = AMDIFVG_PH_DISTRIBUTION;
            st = AMDIFVG_ST_WAIT_IFVG;
            narr += "Displacement after manipulation; ";
           }
        }

      double conf = 0.0;
      if(out.acc_detected) conf += 10.0;
      if(out.manip_detected) conf += 20.0;
      if(out.mss_detected) conf += 20.0;
      if(out.ifvg_detected) conf += 25.0;
      if(st == AMDIFVG_ST_ENTRY_ZONE) conf += 15.0;
      out.confidence = MathMin(100.0, conf);

      ENUM_AMDIFVG_DECISION dec = AMDIFVG_DEC_NO_TRADE;
      if(out.confidence >= m_cfg.min_trade_score && st == AMDIFVG_ST_ENTRY_ZONE)
        {
         if(out.ifvg_direction == "BULLISH" && trade_bias == "BULLISH") dec = AMDIFVG_DEC_BUY;
         else if(out.ifvg_direction == "BEARISH" && trade_bias == "BEARISH") dec = AMDIFVG_DEC_SELL;
         else dec = AMDIFVG_DEC_WAIT;
        }
      else if(out.confidence >= 55.0 || out.manip_detected)
         dec = AMDIFVG_DEC_WAIT;

      out.decision = DecisionStr(dec);
      out.setup_state = SetupStateStr(st);
      out.amd_phase = phase == AMDIFVG_PH_DISTRIBUTION ? "DISTRIBUTION" :
                      (phase == AMDIFVG_PH_MANIPULATION ? "MANIPULATION" :
                      (phase == AMDIFVG_PH_ACCUMULATION ? "ACCUMULATION" : "SEARCHING"));
      out.htf_bias = "NEUTRAL";
      out.recommendation = out.decision;
      out.status_line = out.decision;
      out.technical_narrative = narr;
      out.reasoning = narr;
      out.eval_bar_m5 = bar_time;
      out.engine_phase = 1;
      out.analysis_active = true;
      out.valid = true;
      out.chart_objects_active = m_cfg.show_chart_objects;

      if(out.ifvg_detected)
        {
         out.entry_low = out.ifvg_lower;
         out.entry_high = out.ifvg_upper;
         out.preferred_entry = m_cfg.ifvg_use_midpoint ? out.ifvg_mid :
            (out.ifvg_direction == "BEARISH" ? out.ifvg_upper : out.ifvg_lower);
         if(dec == AMDIFVG_DEC_SELL)
           {
            out.stop_loss = out.manip_detected ? out.manip_sweep_price + 0.2 * atr5 : out.ifvg_upper + 0.3 * atr5;
            out.invalidation = out.stop_loss;
            out.tp1 = out.preferred_entry - (out.stop_loss - out.preferred_entry);
            out.tp2 = out.acc_low;
           }
         if(dec == AMDIFVG_DEC_BUY)
           {
            out.stop_loss = out.manip_detected ? out.manip_sweep_price - 0.2 * atr5 : out.ifvg_lower - 0.3 * atr5;
            out.invalidation = out.stop_loss;
            out.tp1 = out.preferred_entry + (out.preferred_entry - out.stop_loss);
            out.tp2 = out.acc_high;
           }
        }

      DrawSetup(out);
      m_last_m5_bar = bar_time;
      m_last = out;
      return true;
     }

   string ToJson(const VantageAmdIfvgResult &r) const
     {
      string j = "{";
      j += "\"module\":\"amd_ifvg\",";
      j += "\"version\":\"" + VANTAGE_AMDIFVG_VERSION + "\",";
      j += "\"valid\":" + (r.valid ? "true" : "false") + ",";
      j += "\"gold_symbol_valid\":" + (r.gold_symbol_valid ? "true" : "false") + ",";
      j += "\"engine_enabled\":" + (r.engine_enabled ? "true" : "false") + ",";
      j += "\"analysis_active\":" + (r.analysis_active ? "true" : "false") + ",";
      j += "\"symbol\":\"" + JsonEscape(r.symbol) + "\",";
      j += "\"strategy\":\"AMD_IFVG\",";
      j += "\"decision\":\"" + JsonEscape(r.decision) + "\",";
      j += "\"setup_state\":\"" + JsonEscape(r.setup_state) + "\",";
      j += "\"amd_phase\":\"" + JsonEscape(r.amd_phase) + "\",";
      j += "\"higher_timeframe_bias\":\"" + JsonEscape(r.htf_bias) + "\",";
      j += "\"confidence\":" + DoubleToString(r.confidence, 1) + ",";
      j += "\"accumulation\":{\"detected\":" + (r.acc_detected ? "true" : "false");
      j += ",\"range_high\":" + DoubleToString(r.acc_high, _Digits);
      j += ",\"range_low\":" + DoubleToString(r.acc_low, _Digits);
      j += ",\"quality_score\":" + DoubleToString(r.acc_quality, 1) + "},";
      j += "\"manipulation\":{\"detected\":" + (r.manip_detected ? "true" : "false");
      j += ",\"direction\":\"" + JsonEscape(r.manip_direction) + "\"";
      j += ",\"sweep_price\":" + DoubleToString(r.manip_sweep_price, _Digits);
      j += ",\"quality_score\":" + DoubleToString(r.manip_quality, 1) + "},";
      j += "\"market_structure\":{\"shift_detected\":" + (r.mss_detected ? "true" : "false");
      j += ",\"direction\":\"" + JsonEscape(r.mss_direction) + "\"";
      j += ",\"broken_level\":" + DoubleToString(r.mss_level, _Digits) + "},";
      j += "\"ifvg\":{\"detected\":" + (r.ifvg_detected ? "true" : "false");
      j += ",\"direction\":\"" + JsonEscape(r.ifvg_direction) + "\"";
      j += ",\"original_fvg_direction\":\"" + JsonEscape(r.ifvg_orig_direction) + "\"";
      j += ",\"lower_boundary\":" + DoubleToString(r.ifvg_lower, _Digits);
      j += ",\"upper_boundary\":" + DoubleToString(r.ifvg_upper, _Digits);
      j += ",\"midpoint\":" + DoubleToString(r.ifvg_mid, _Digits);
      j += ",\"retest_count\":" + IntegerToString(r.ifvg_retests) + "},";
      j += "\"entry\":{\"entry_low\":" + DoubleToString(r.entry_low, _Digits);
      j += ",\"entry_high\":" + DoubleToString(r.entry_high, _Digits);
      j += ",\"preferred_entry\":" + DoubleToString(r.preferred_entry, _Digits) + "},";
      j += "\"risk\":{\"stop_loss\":" + DoubleToString(r.stop_loss, _Digits);
      j += ",\"risk_percentage\":" + DoubleToString(m_cfg.risk_percent, 2) + "},";
      j += "\"status_line\":\"" + JsonEscape(r.status_line) + "\",";
      j += "\"recommendation\":\"" + JsonEscape(r.recommendation) + "\",";
      j += "\"technical_narrative\":\"" + JsonEscape(r.technical_narrative) + "\",";
      j += "\"action_guidance\":\"" + JsonEscape(r.action_guidance) + "\",";
      j += "\"reasoning\":[\"" + JsonEscape(r.reasoning) + "\"],";
      j += "\"eval_bar_m5\":" + IntegerToString((int)r.eval_bar_m5) + ",";
      j += "\"engine_phase\":" + IntegerToString(r.engine_phase);
      j += "}";
      return j;
     }

   void Release()
     {
      ClearObjects();
      m_symbol = "";
      m_last_m5_bar = 0;
      ZeroMemory(m_last);
     }
  };

#endif
