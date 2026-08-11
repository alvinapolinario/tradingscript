//+------------------------------------------------------------------+
//| VantageIct.mqh — ICT Strategy Engine (Gold / XAUUSD advisory)   |
//+------------------------------------------------------------------+
#ifndef VANTAGE_ICT_MQH
#define VANTAGE_ICT_MQH

#include "VantageTypes.mqh"
#include "VantageIctTypes.mqh"
#include "VantageGoldSMCValidator.mqh"

#define ICT_OBJ_PREFIX "VAI_ICT_"

class CVantageIct
  {
private:
   string                   m_symbol;
   VantageIctConfig         m_cfg;
   CVantageGoldSymbolValidator m_validator;
   datetime                 m_last_entry_bar;
   string                   m_last_state;
   VantageIctResult         m_last;

   void Dbg(const string msg)
     {
      if(m_cfg.debug_log)
         Print("[ICT] ", msg);
     }

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
      return (n >= MathMax(20, count / 2));
     }

   double BodyRatio(const MqlRates &c) const
     {
      double rng = MathMax(c.high - c.low, _Point);
      return MathAbs(c.close - c.open) / rng;
     }

   string DecisionStr(const ENUM_ICT_DECISION d) const
     {
      if(d == ICT_DEC_BUY) return "BUY";
      if(d == ICT_DEC_SELL) return "SELL";
      if(d == ICT_DEC_WAIT) return "WAIT";
      return "NO_TRADE";
     }

   string StateStr(const ENUM_ICT_SETUP_STATE s) const
     {
      switch(s)
        {
         case ICT_ST_LIQ_ID: return "LIQUIDITY_IDENTIFIED";
         case ICT_ST_LIQ_SWEPT: return "LIQUIDITY_SWEPT";
         case ICT_ST_WAIT_DISP: return "WAITING_FOR_DISPLACEMENT";
         case ICT_ST_DISP_OK: return "DISPLACEMENT_CONFIRMED";
         case ICT_ST_WAIT_MSS: return "WAITING_FOR_MSS";
         case ICT_ST_MSS_OK: return "MSS_CONFIRMED";
         case ICT_ST_WAIT_RETRACE: return "WAITING_FOR_RETRACE";
         case ICT_ST_ENTRY_ZONE: return "ENTRY_ZONE_ACTIVE";
         case ICT_ST_TRIGGERED: return "TRIGGERED";
         case ICT_ST_INVALIDATED: return "INVALIDATED";
         case ICT_ST_EXPIRED: return "EXPIRED";
         default: return "WAITING_FOR_LIQUIDITY";
        }
     }

   string QualityStr(const double score) const
     {
      if(score >= 85.0) return "VERY HIGH";
      if(score >= 70.0) return "HIGH";
      if(score >= 50.0) return "MODERATE";
      return "LOW";
     }

   void AppendReason(string &reasons, const string line)
     {
      if(reasons == "") reasons = line;
      else reasons += "|" + line;
     }

   bool IsPivotHigh(const MqlRates &rates[], const int i, const int left, const int right) const
     {
      if(i - left < 0 || i + right >= ArraySize(rates)) return false;
      for(int k = 1; k <= left; k++)
         if(rates[i].high <= rates[i - k].high) return false;
      for(int k = 1; k <= right; k++)
         if(rates[i].high <= rates[i + k].high) return false;
      return true;
     }

   bool IsPivotLow(const MqlRates &rates[], const int i, const int left, const int right) const
     {
      if(i - left < 0 || i + right >= ArraySize(rates)) return false;
      for(int k = 1; k <= left; k++)
         if(rates[i].low >= rates[i - k].low) return false;
      for(int k = 1; k <= right; k++)
         if(rates[i].low >= rates[i + k].low) return false;
      return true;
     }

   string MakeSetupId(const string bias, const datetime sweep_time) const
     {
      string side = (bias == "BULLISH" ? "B" : "S");
      return "ICT-" + m_symbol + "-M15-" + IntegerToString((int)sweep_time) + "-" + side;
     }

   string ReasonsToJsonArray(const string reasons) const
     {
      if(reasons == "") return "[]";
      string parts[];
      int n = StringSplit(reasons, '|', parts);
      string j = "[";
      for(int i = 0; i < n; i++)
        {
         if(i > 0) j += ",";
         j += "\"" + JsonEscape(parts[i]) + "\"";
        }
      j += "]";
      return j;
     }

public:
   CVantageIct(void) : m_symbol(""), m_last_entry_bar(0), m_last_state("") { ZeroMemory(m_last); }

   bool Init(const string symbol, const VantageIctConfig &cfg)
     {
      m_symbol = symbol;
      m_cfg = cfg;
      m_last_entry_bar = 0;
      m_last_state = "";
      ZeroMemory(m_last);
      m_validator.Configure(cfg.gold_aliases, cfg.allow_suffix, cfg.allow_prefix);
      return true;
     }

   bool Evaluate(const bool force, VantageIctResult &out)
     {
      string base = "";
      ZeroMemory(out);
      out.valid = false;
      out.engine_enabled = m_cfg.enable;
      out.symbol = m_symbol;
      out.base_symbol = m_symbol;
      out.strategy = "ICT";
      out.decision = "NO_TRADE";
      out.setup_state = StateStr(ICT_ST_WAIT_LIQ);
      out.status = out.setup_state;
      out.action_guidance = "Advisory only — confirm on closed candles.";

      if(!m_cfg.enable)
        {
         out.disable_reason = "Engine disabled";
         return false;
        }

      if(!IsApprovedDeskSymbol(m_symbol, base))
        {
         out.gold_symbol_valid = false;
         out.base_symbol = base;
         out.disable_reason = VANTAGE_ICT_DISABLE_MSG;
         out.valid = true;
         return true;
        }
      out.gold_symbol_valid = true;
      out.base_symbol = base;

      MqlRates m15[], m5[], h1[];
      if(!CopyClosed(m_cfg.tf_setup, m_cfg.lookback_bars, m15) || !CopyClosed(m_cfg.tf_entry, 30, m5))
        {
         AppendReason(out.reasons, "Insufficient closed-bar history");
         out.valid = true;
         out.analysis_active = false;
         return true;
        }
      CopyClosed(m_cfg.tf_bias, 40, h1);

      datetime bar_time = m15[0].time;
      bool new_bar = (bar_time != m_last_entry_bar);
      if(!new_bar && !force) { out = m_last; return out.valid; }

      double atr15 = GetAtr(m_cfg.tf_setup);
      double atr5 = GetAtr(m_cfg.tf_entry);
      if(atr15 <= 0) atr15 = m15[0].high - m15[0].low;
      if(atr5 <= 0) atr5 = m5[0].high - m5[0].low;

      double spread = (double)SymbolInfoInteger(m_symbol, SYMBOL_SPREAD);
      if(spread > m_cfg.max_spread_pts)
         AppendReason(out.reasons, "High spread environment");

      // HTF bias — simple H1 close vs EMA proxy (recent midpoint)
      double h1_mid = 0.0;
      int hn = MathMin(ArraySize(h1), 20);
      for(int i = 0; i < hn; i++) h1_mid += h1[i].close;
      h1_mid /= MathMax(1, hn);
      out.htf_bias_dir = (h1[0].close > h1_mid ? "BULLISH" : (h1[0].close < h1_mid ? "BEARISH" : "NEUTRAL"));
      out.htf_bias_conf = 65.0;
      out.htf_evidence = "H1 close vs 20-bar mean";

      // Liquidity pools — pivot swings
      double bsl = 0.0, ssl = 99999999.0;
      datetime bsl_t = 0, ssl_t = 0;
      int bsl_n = 0, ssl_n = 0;
      int lim = MathMin(ArraySize(m15) - m_cfg.pivot_right - 1, m_cfg.lookback_bars);
      for(int i = m_cfg.pivot_left; i < lim; i++)
        {
         if(IsPivotHigh(m15, i, m_cfg.pivot_left, m_cfg.pivot_right))
           {
            bsl_n++;
            if(m15[i].high > bsl) { bsl = m15[i].high; bsl_t = m15[i].time; }
           }
         if(IsPivotLow(m15, i, m_cfg.pivot_left, m_cfg.pivot_right))
           {
            ssl_n++;
            if(m15[i].low < ssl) { ssl = m15[i].low; ssl_t = m15[i].time; }
           }
        }
      out.bsl_count = bsl_n;
      out.ssl_count = ssl_n;
      if(bsl <= 0) bsl = m15[0].high;
      if(ssl >= 99999999.0) ssl = m15[0].low;

      ENUM_ICT_SETUP_STATE st = (bsl_n > 0 || ssl_n > 0) ? ICT_ST_LIQ_ID : ICT_ST_WAIT_LIQ;
      string trade_bias = "";
      MqlRates sweep_bar = m15[0];

      // Sweep on latest closed M15 bar
      if(bsl > 0 && sweep_bar.high > bsl + m_cfg.sweep_min_atr * atr15 &&
         sweep_bar.high <= bsl + m_cfg.sweep_max_atr * atr15 && sweep_bar.close < bsl)
        {
         out.sweep_detected = true;
         out.sweep_type = "BUY_SIDE";
         out.sweep_level = bsl;
         out.sweep_price = sweep_bar.high;
         out.sweep_quality = 78.0;
         out.sweep_time = sweep_bar.time;
         trade_bias = "BEARISH";
         st = ICT_ST_LIQ_SWEPT;
         AppendReason(out.reasons, "Buy-side liquidity sweep on closed M15");
        }
      else if(ssl > 0 && sweep_bar.low < ssl - m_cfg.sweep_min_atr * atr15 &&
              sweep_bar.low >= ssl - m_cfg.sweep_max_atr * atr15 && sweep_bar.close > ssl)
        {
         out.sweep_detected = true;
         out.sweep_type = "SELL_SIDE";
         out.sweep_level = ssl;
         out.sweep_price = sweep_bar.low;
         out.sweep_quality = 78.0;
         out.sweep_time = sweep_bar.time;
         trade_bias = "BULLISH";
         st = ICT_ST_LIQ_SWEPT;
         AppendReason(out.reasons, "Sell-side liquidity sweep on closed M15");
        }

      // Displacement after sweep
      if(out.sweep_detected)
        {
         double body = MathAbs(sweep_bar.close - sweep_bar.open);
         out.displacement_score = MathMin(100.0, (body / atr15) * 40.0);
         if(body >= m_cfg.disp_min_body_atr * atr15)
           {
            out.displacement = true;
            st = ICT_ST_DISP_OK;
            AppendReason(out.reasons, "Displacement candle after sweep");
           }
         else
            st = ICT_ST_WAIT_DISP;
        }

      // MSS — break recent structure
      if(out.displacement && trade_bias == "BEARISH")
        {
         double struct_low = m15[1].low;
         for(int j = 2; j < MathMin(8, ArraySize(m15)); j++)
            if(m15[j].low < struct_low) struct_low = m15[j].low;
         if(sweep_bar.close < struct_low)
           {
            out.mss_dir = "BEARISH";
            st = ICT_ST_MSS_OK;
            AppendReason(out.reasons, "Bearish MSS — closed below structure low");
           }
         else
            st = ICT_ST_WAIT_MSS;
        }
      if(out.displacement && trade_bias == "BULLISH")
        {
         double struct_high = m15[1].high;
         for(int j = 2; j < MathMin(8, ArraySize(m15)); j++)
            if(m15[j].high > struct_high) struct_high = m15[j].high;
         if(sweep_bar.close > struct_high)
           {
            out.mss_dir = "BULLISH";
            st = ICT_ST_MSS_OK;
            AppendReason(out.reasons, "Bullish MSS — closed above structure high");
           }
         else
            st = ICT_ST_WAIT_MSS;
        }

      // FVG on M5
      if(st >= ICT_ST_MSS_OK)
        {
         for(int i = 0; i < MathMin(ArraySize(m5) - 2, 12); i++)
           {
            if(trade_bias == "BEARISH" && m5[i + 2].low > m5[i].high + m_cfg.fvg_min_gap_atr * atr5)
              {
               out.fvg_detected = true;
               out.fvg_dir = "BEARISH";
               out.fvg_high = m5[i + 2].low;
               out.fvg_low = m5[i].high;
               out.fvg_mid = (out.fvg_high + out.fvg_low) * 0.5;
               st = ICT_ST_WAIT_RETRACE;
               AppendReason(out.reasons, "Bearish FVG detected on M5");
               break;
              }
            if(trade_bias == "BULLISH" && m5[i + 2].high < m5[i].low - m_cfg.fvg_min_gap_atr * atr5)
              {
               out.fvg_detected = true;
               out.fvg_dir = "BULLISH";
               out.fvg_high = m5[i].low;
               out.fvg_low = m5[i + 2].high;
               out.fvg_mid = (out.fvg_high + out.fvg_low) * 0.5;
               st = ICT_ST_WAIT_RETRACE;
               AppendReason(out.reasons, "Bullish FVG detected on M5");
               break;
              }
           }
        }

      double bid = SymbolInfoDouble(m_symbol, SYMBOL_BID);
      if(out.fvg_detected)
        {
         out.entry_low = out.fvg_low;
         out.entry_high = out.fvg_high;
         out.entry_mid = out.fvg_mid;
         if(bid >= out.entry_low && bid <= out.entry_high)
           {
            st = ICT_ST_ENTRY_ZONE;
            out.entry_status = "IN_ZONE";
            AppendReason(out.reasons, "Price inside FVG entry zone");
           }
         else
           {
            out.entry_status = "WAITING";
           }
        }

      // Trade plan
      if(out.fvg_detected && trade_bias == "BEARISH")
        {
         out.stop_loss = out.sweep_price + 0.15 * atr5;
         out.sl_reason = "Above sweep high";
         out.tp1 = out.entry_mid - (out.stop_loss - out.entry_mid) * m_cfg.minimum_rr;
         out.tp2 = ssl;
         double risk = MathMax(out.stop_loss - out.entry_mid, _Point);
         double reward = MathMax(out.entry_mid - out.tp1, _Point);
         out.risk_reward = reward / risk;
        }
      if(out.fvg_detected && trade_bias == "BULLISH")
        {
         out.stop_loss = out.sweep_price - 0.15 * atr5;
         out.sl_reason = "Below sweep low";
         out.tp1 = out.entry_mid + (out.entry_mid - out.stop_loss) * m_cfg.minimum_rr;
         out.tp2 = bsl;
         double risk = MathMax(out.entry_mid - out.stop_loss, _Point);
         double reward = MathMax(out.tp1 - out.entry_mid, _Point);
         out.risk_reward = reward / risk;
        }

      double conf = 0.0;
      if(out.htf_bias_dir == trade_bias) conf += 12.0;
      if(out.sweep_detected) conf += 22.0;
      if(out.displacement) conf += 18.0;
      if(out.mss_dir != "") conf += 18.0;
      if(out.fvg_detected) conf += 15.0;
      if(st == ICT_ST_ENTRY_ZONE) conf += 10.0;
      out.confidence = MathMin(100.0, conf);
      out.confidence_score = out.confidence;
      out.signal_quality = QualityStr(out.confidence);

      ENUM_ICT_DECISION dec = ICT_DEC_NO_TRADE;
      if(out.confidence >= m_cfg.min_confidence && st == ICT_ST_ENTRY_ZONE)
        {
         if(trade_bias == "BEARISH") dec = ICT_DEC_SELL;
         else if(trade_bias == "BULLISH") dec = ICT_DEC_BUY;
         else dec = ICT_DEC_WAIT;
        }
      else if(out.confidence >= 45.0 || out.sweep_detected)
         dec = ICT_DEC_WAIT;

      out.decision = DecisionStr(dec);
      out.direction = (dec == ICT_DEC_BUY ? "BUY" : (dec == ICT_DEC_SELL ? "SELL" : trade_bias));
      out.setup_state = StateStr(st);
      out.status = out.setup_state;
      if(out.sweep_detected)
         out.setup_id = MakeSetupId(trade_bias, out.sweep_time);
      out.premium_discount = (trade_bias == "BEARISH" ? "PREMIUM" : (trade_bias == "BULLISH" ? "DISCOUNT" : "EQUILIBRIUM"));
      out.session_name = "LIVE";
      out.eval_bar_time = bar_time;
      out.analysis_active = true;
      out.valid = true;
      out.technical_narrative = out.reasons;
      if(dec == ICT_DEC_SELL || dec == ICT_DEC_BUY)
         out.action_guidance = "ICT setup validated on closed bars — analysis only.";
      else if(st == ICT_ST_WAIT_RETRACE || st == ICT_ST_ENTRY_ZONE)
         out.action_guidance = "Waiting for retrace into FVG entry zone.";
      else
         out.action_guidance = "Monitoring ICT liquidity-first sequence.";

      string new_state = out.setup_state;
      out.state_changed = (m_last_state != "" && m_last_state != new_state);
      m_last_state = new_state;
      m_last_entry_bar = bar_time;
      m_last = out;
      return true;
     }

   string ToJson(const VantageIctResult &r) const
     {
      string tf = EnumToString(m_cfg.tf_setup);
      StringReplace(tf, "PERIOD_", "");
      string etf = EnumToString(m_cfg.tf_entry);
      StringReplace(etf, "PERIOD_", "");
      string j = "{";
      j += "\"module\":\"ict\",";
      j += "\"version\":\"" + VANTAGE_ICT_VERSION + "\",";
      j += "\"valid\":" + (r.valid ? "true" : "false") + ",";
      j += "\"gold_symbol_valid\":" + (r.gold_symbol_valid ? "true" : "false") + ",";
      j += "\"engine_enabled\":" + (r.engine_enabled ? "true" : "false") + ",";
      j += "\"analysis_active\":" + (r.analysis_active ? "true" : "false") + ",";
      j += "\"symbol\":\"" + JsonEscape(r.symbol) + "\",";
      j += "\"strategy\":\"ICT\",";
      j += "\"timeframe\":\"" + JsonEscape(tf) + "\",";
      j += "\"execution_timeframe\":\"" + JsonEscape(etf) + "\",";
      j += "\"timestamp\":" + IntegerToString((int)r.eval_bar_time) + ",";
      j += "\"status\":\"" + JsonEscape(r.status) + "\",";
      j += "\"setup_state\":\"" + JsonEscape(r.setup_state) + "\",";
      j += "\"decision\":\"" + JsonEscape(r.decision) + "\",";
      j += "\"direction\":\"" + JsonEscape(r.direction) + "\",";
      j += "\"confidence\":" + DoubleToString(r.confidence, 1) + ",";
      j += "\"confidence_score\":" + DoubleToString(r.confidence_score, 1) + ",";
      j += "\"signal_quality\":\"" + JsonEscape(r.signal_quality) + "\",";
      j += "\"state_changed\":" + (r.state_changed ? "true" : "false") + ",";
      j += "\"htf_bias\":{\"direction\":\"" + JsonEscape(r.htf_bias_dir) + "\",";
      j += "\"confidence\":" + DoubleToString(r.htf_bias_conf, 1) + ",";
      j += "\"evidence\":[\"" + JsonEscape(r.htf_evidence) + "\"]},";
      j += "\"liquidity\":{\"bsl_count\":" + IntegerToString(r.bsl_count);
      j += ",\"ssl_count\":" + IntegerToString(r.ssl_count);
      j += ",\"sweep_detected\":" + (r.sweep_detected ? "true" : "false");
      j += ",\"type\":\"" + JsonEscape(r.sweep_type) + "\"";
      j += ",\"level\":" + DoubleToString(r.sweep_level, _Digits);
      j += ",\"sweep_price\":" + DoubleToString(r.sweep_price, _Digits);
      j += ",\"quality_score\":" + DoubleToString(r.sweep_quality, 1) + "},";
      j += "\"structure\":{\"displacement\":" + (r.displacement ? "true" : "false");
      j += ",\"displacement_score\":" + DoubleToString(r.displacement_score, 1);
      j += ",\"mss\":\"" + JsonEscape(r.mss_dir) + "\"},";
      j += "\"fvg\":{\"direction\":\"" + JsonEscape(r.fvg_dir) + "\"";
      j += ",\"high\":" + DoubleToString(r.fvg_high, _Digits);
      j += ",\"low\":" + DoubleToString(r.fvg_low, _Digits);
      j += ",\"midpoint\":" + DoubleToString(r.fvg_mid, _Digits) + "},";
      j += "\"entry\":{\"zone_high\":" + DoubleToString(r.entry_high, _Digits);
      j += ",\"zone_low\":" + DoubleToString(r.entry_low, _Digits);
      j += ",\"midpoint\":" + DoubleToString(r.entry_mid, _Digits);
      j += ",\"status\":\"" + JsonEscape(r.entry_status) + "\"},";
      j += "\"stop_loss\":{\"price\":" + DoubleToString(r.stop_loss, _Digits);
      j += ",\"reason\":\"" + JsonEscape(r.sl_reason) + "\"},";
      j += "\"targets\":[{\"name\":\"TP1\",\"price\":" + DoubleToString(r.tp1, _Digits);
      j += "},{\"name\":\"TP2\",\"price\":" + DoubleToString(r.tp2, _Digits) + "}],";
      j += "\"risk_reward\":" + DoubleToString(r.risk_reward, 2) + ",";
      j += "\"premium_discount_zone\":\"" + JsonEscape(r.premium_discount) + "\",";
      j += "\"session\":\"" + JsonEscape(r.session_name) + "\",";
      j += "\"reasons\":" + ReasonsToJsonArray(r.reasons) + ",";
      j += "\"invalidations\":[],";
      j += "\"setup_id\":\"" + JsonEscape(r.setup_id) + "\",";
      j += "\"technical_narrative\":\"" + JsonEscape(r.technical_narrative) + "\",";
      j += "\"action_guidance\":\"" + JsonEscape(r.action_guidance) + "\",";
      j += "\"eval_bar_time\":" + IntegerToString((int)r.eval_bar_time);
      j += "}";
      return j;
     }

   void Release()
     {
      m_symbol = "";
      m_last_entry_bar = 0;
      m_last_state = "";
      ZeroMemory(m_last);
     }
  };

#endif
