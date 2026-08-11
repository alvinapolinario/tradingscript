//+------------------------------------------------------------------+
//| VantageBoxTheory.mqh — Box Theory strategy (Gold / XAUUSD)       |
//+------------------------------------------------------------------+
#ifndef VANTAGE_BOX_THEORY_MQH
#define VANTAGE_BOX_THEORY_MQH

#include "VantageTypes.mqh"
#include "VantageBoxTheoryTypes.mqh"
#include "VantageGoldSMCValidator.mqh"

#define BOX_OBJ_PREFIX "VAI_BOX_"

class CVantageBoxTheory
  {
private:
   string                   m_symbol;
   VantageBoxTheoryConfig   m_cfg;
   CVantageGoldSymbolValidator m_validator;
   datetime                 m_last_entry_bar;
   VantageBoxTheoryResult   m_last;

   void Dbg(const string msg)
     {
      if(m_cfg.debug_log)
         Print("[BoxTheory] ", msg);
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

   double CalcAtrFromRates(const MqlRates &rates[], const int count, const int period=14)
     {
      if(count < 2) return MathMax(rates[0].high - rates[0].low, _Point);
      int n = MathMin(count, period + 1);
      double sum = 0.0;
      int trn = 0;
      for(int i = 0; i < n - 1; i++)
        {
         double tr = MathMax(rates[i].high - rates[i].low,
                             MathMax(MathAbs(rates[i].high - rates[i + 1].close),
                                     MathAbs(rates[i].low - rates[i + 1].close)));
         sum += tr;
         trn++;
        }
      return (trn > 0 ? sum / trn : MathMax(rates[0].high - rates[0].low, _Point));
     }

   bool CopyClosed(const ENUM_TIMEFRAMES tf, const int count, MqlRates &rates[])
     {
      ArraySetAsSeries(rates, true);
      int n = CopyRates(m_symbol, tf, 1, count, rates);
      return (n >= MathMax(10, count / 2));
     }

   double BodyRatio(const MqlRates &c) const
     {
      double rng = MathMax(c.high - c.low, _Point);
      return MathAbs(c.close - c.open) / rng;
     }

   bool IsBullish(const MqlRates &c) const { return c.close > c.open; }
   bool IsBearish(const MqlRates &c) const { return c.close < c.open; }

   string SignalStr(const ENUM_BOX_SIGNAL s) const
     {
      if(s == BOX_SIG_BUY) return "BUY";
      if(s == BOX_SIG_SELL) return "SELL";
      if(s == BOX_SIG_WATCH) return "WATCH";
      if(s == BOX_SIG_INVALID) return "INVALID";
      return "WAIT";
     }

   string StatusStr(const ENUM_BOX_STATUS s) const
     {
      switch(s)
        {
         case BOX_ST_VALID: return "VALID";
         case BOX_ST_BREAKOUT_UP: return "BREAKOUT_UP";
         case BOX_ST_BREAKOUT_DOWN: return "BREAKOUT_DOWN";
         case BOX_ST_RETESTING: return "RETESTING";
         case BOX_ST_CONFIRMED_BULL: return "CONFIRMED_BULLISH";
         case BOX_ST_CONFIRMED_BEAR: return "CONFIRMED_BEARISH";
         case BOX_ST_BULL_TRAP: return "BULL_TRAP";
         case BOX_ST_BEAR_TRAP: return "BEAR_TRAP";
         case BOX_ST_INVALIDATED: return "INVALIDATED";
         case BOX_ST_EXPIRED: return "EXPIRED";
         default: return "FORMING";
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

   void AppendEvent(string &events, const string ev)
     {
      if(events == "") events = ev;
      else events += "|" + ev;
     }

   bool DetectBox(const MqlRates &rates[], const int n, const double atr_v,
                  double &hi, double &lo, int &upper, int &lower, int &span,
                  datetime &start_t, datetime &end_t, double &inside_ratio, double &quality)
     {
      if(n < m_cfg.min_box_candles) return false;
      int max_span = MathMin(n, m_cfg.lookback_candles);
      double best_q = -1.0;
      bool found = false;
      double tol = m_cfg.touch_tolerance_atr * atr_v;

      for(span = m_cfg.min_box_candles; span <= max_span; span++)
        {
         hi = rates[0].high;
         lo = rates[0].low;
         for(int i = 0; i < span; i++)
           {
            if(rates[i].high > hi) hi = rates[i].high;
            if(rates[i].low < lo) lo = rates[i].low;
           }
         double height = hi - lo;
         if(height < m_cfg.min_box_height_atr * atr_v) continue;
         if(height > m_cfg.max_box_height_atr * atr_v) continue;

         upper = 0;
         lower = 0;
         int inside = 0;
         for(int j = 0; j < span; j++)
           {
            if(MathAbs(rates[j].high - hi) <= tol || MathAbs(rates[j].close - hi) <= tol) upper++;
            if(MathAbs(rates[j].low - lo) <= tol || MathAbs(rates[j].close - lo) <= tol) lower++;
            if(rates[j].close >= lo && rates[j].close <= hi) inside++;
           }
         if(upper < m_cfg.min_touches || lower < m_cfg.min_touches) continue;
         inside_ratio = (double)inside / (double)span;
         if(inside_ratio < m_cfg.min_inside_ratio) continue;

         quality = MathMin(100.0, 40.0 + MathMin(20.0, upper * 5.0) +
                               MathMin(20.0, lower * 5.0) + inside_ratio * 20.0);
         if(quality > best_q)
           {
            best_q = quality;
            start_t = rates[span - 1].time;
            end_t = rates[0].time;
            found = true;
           }
        }
      return found;
     }

   bool DetectBreakout(const double box_hi, const double box_lo, const MqlRates &rates[], const int n,
                       const datetime box_end, const double atr_v,
                       string &dir, double &price, datetime &bt, double &body_r)
     {
      double buf = m_cfg.breakout_buffer_atr * atr_v;
      for(int i = n - 1; i >= 0; i--)
        {
         if(rates[i].time <= box_end) continue;
         body_r = BodyRatio(rates[i]);
         if(rates[i].close > box_hi + buf && body_r >= m_cfg.min_breakout_body_ratio)
           {
            dir = "UP"; price = rates[i].close; bt = rates[i].time; return true;
           }
         if(rates[i].close < box_lo - buf && body_r >= m_cfg.min_breakout_body_ratio)
           {
            dir = "DOWN"; price = rates[i].close; bt = rates[i].time; return true;
           }
        }
      return false;
     }

   bool DetectFakeout(const double box_hi, const double box_lo, const MqlRates &rates[], const int n,
                      const datetime after_t, string &trap, datetime &tt)
     {
      for(int i = n - 1; i >= 0; i--)
        {
         if(rates[i].time <= after_t) continue;
         if(rates[i].high > box_hi && rates[i].close < box_hi)
           { trap = "BULL_TRAP"; tt = rates[i].time; return true; }
         if(rates[i].low < box_lo && rates[i].close > box_lo)
           { trap = "BEAR_TRAP"; tt = rates[i].time; return true; }
        }
      return false;
     }

   bool DetectRetest(const double box_hi, const double box_lo, const string br_dir,
                     const datetime br_time, const MqlRates &rates[], const int n, const double atr_v,
                     bool &detected, bool &confirmed, double &price, int &waited)
     {
      detected = false;
      confirmed = false;
      price = 0.0;
      waited = 0;
      double tol = m_cfg.retest_tolerance_atr * atr_v;
      int cnt = 0;
      for(int i = n - 1; i >= 0; i--)
        {
         if(rates[i].time <= br_time) continue;
         cnt++;
         if(cnt > m_cfg.max_retest_candles) break;
         if(br_dir == "UP")
           {
            bool near = (MathAbs(rates[i].low - box_hi) <= tol) ||
                        (rates[i].close >= box_hi - tol && rates[i].close <= box_hi + tol);
            if(!near) continue;
            detected = true;
            price = rates[i].close;
            confirmed = IsBullish(rates[i]) && rates[i].close >= box_hi - tol * 0.5;
            waited = cnt;
            if(confirmed || cnt >= m_cfg.confirmation_candles) return true;
           }
         else
           {
            bool near = (MathAbs(rates[i].high - box_lo) <= tol) ||
                        (rates[i].close >= box_lo - tol && rates[i].close <= box_lo + tol);
            if(!near) continue;
            detected = true;
            price = rates[i].close;
            confirmed = IsBearish(rates[i]) && rates[i].close <= box_lo + tol * 0.5;
            waited = cnt;
            if(confirmed || cnt >= m_cfg.confirmation_candles) return true;
           }
        }
      return detected;
     }

   bool DetectSweep(const double box_hi, const double box_lo, const MqlRates &rates[], const int n,
                    const datetime start_t, const datetime before_t, const double atr_v,
                    string &dir, double &sweep_price)
     {
      if(!m_cfg.liquidity_sweep_detection) return false;
      double tol = m_cfg.breakout_buffer_atr * atr_v;
      for(int i = n - 1; i >= 0; i--)
        {
         if(rates[i].time < start_t || rates[i].time > before_t) continue;
         if(rates[i].low < box_lo - tol && rates[i].close > box_lo)
           { dir = "SELL_SIDE"; sweep_price = rates[i].low; return true; }
         if(rates[i].high > box_hi + tol && rates[i].close < box_hi)
           { dir = "BUY_SIDE"; sweep_price = rates[i].high; return true; }
        }
      return false;
     }

   string HtfBias(const MqlRates &rates[], const int n)
     {
      if(n < 20) return "NEUTRAL";
      int ups = 0, downs = 0;
      for(int i = 0; i < 19; i++)
        {
         if(rates[i].close > rates[i + 1].close) ups++;
         else downs++;
        }
      if(ups >= downs + 6) return "BULLISH";
      if(downs >= ups + 6) return "BEARISH";
      return "NEUTRAL";
     }

   bool DetectFvgBull(const MqlRates &m5[], const double atr5)
     {
      if(ArraySize(m5) < 3) return false;
      MqlRates c1 = m5[2], c3 = m5[0];
      if(c3.low > c1.high && (c3.low - c1.high) >= 0.05 * atr5) return true;
      return false;
     }

   bool DetectFvgBear(const MqlRates &m5[], const double atr5)
     {
      if(ArraySize(m5) < 3) return false;
      MqlRates c1 = m5[2], c3 = m5[0];
      if(c3.high < c1.low && (c1.low - c3.high) >= 0.05 * atr5) return true;
      return false;
     }

   double ScoreSetup(const double box_q, const bool br_ok, const double body_r,
                     const bool rt_det, const bool rt_conf, const bool sweep_ok,
                     const bool fvg_ok, const string htf, const string br_dir,
                     string &reasons)
     {
      double score = 0.0;
      reasons = "";
      if(box_q >= 50.0) { score += 15.0; AppendReason(reasons, "Valid consolidation box"); }
      if(br_ok)
        {
         score += 40.0;
         AppendReason(reasons, br_dir == "UP" ? "Breakout candle close confirmed" : "Breakdown candle close confirmed");
         if(body_r >= 0.65) { score += 10.0; AppendReason(reasons, "Strong breakout body"); }
        }
      if(rt_det) { score += 10.0; AppendReason(reasons, "Retest of box boundary"); }
      if(rt_conf) { score += 10.0; AppendReason(reasons, "Retest confirmation candle"); }
      if(sweep_ok) AppendReason(reasons, "Liquidity sweep before breakout");
      if(sweep_ok) score += 10.0;
      if(fvg_ok) { score += 15.0; AppendReason(reasons, "FVG/iFVG confirmation"); }
      if(m_cfg.htf_confirmation)
        {
         if(htf == "BULLISH" && br_dir == "UP") { score += 15.0; AppendReason(reasons, "HTF bullish structure"); }
         else if(htf == "BEARISH" && br_dir == "DOWN") { score += 15.0; AppendReason(reasons, "HTF bearish structure"); }
         else if(htf != "NEUTRAL" &&
                 ((htf == "BEARISH" && br_dir == "UP") || (htf == "BULLISH" && br_dir == "DOWN")))
           {
            score -= m_cfg.countertrend_penalty;
            AppendReason(reasons, "Counter HTF structure penalty");
           }
        }
      return MathMax(0.0, MathMin(100.0, score));
     }

   void CalcRiskPlan(const string br_dir, const double box_hi, const double box_lo, const double box_mid,
                     const double box_height, const double br_price, const double rt_price,
                     const double atr_v, double &entry, double &sl, double &tp1, double &tp2, double &tp3, double &rr)
     {
      double buffer = m_cfg.sl_buffer_atr * atr_v;
      entry = (rt_price > 0.0 ? rt_price : br_price);
      if(br_dir == "UP")
        {
         if(m_cfg.sl_mode == "BOX_OPPOSITE") sl = box_lo - buffer;
         else if(m_cfg.sl_mode == "BOX_MID") sl = box_mid - buffer;
         else sl = box_hi - buffer;
         double risk = MathMax(entry - sl, atr_v * 0.1);
         tp1 = entry + m_cfg.tp_mult1 * box_height;
         tp2 = entry + m_cfg.tp_mult2 * box_height;
         tp3 = entry + m_cfg.tp_mult3 * box_height;
         rr = (risk > 0.0 ? MathAbs(tp2 - entry) / risk : 0.0);
        }
      else
        {
         if(m_cfg.sl_mode == "BOX_OPPOSITE") sl = box_hi + buffer;
         else if(m_cfg.sl_mode == "BOX_MID") sl = box_mid + buffer;
         else sl = box_lo + buffer;
         double risk = MathMax(sl - entry, atr_v * 0.1);
         tp1 = entry - m_cfg.tp_mult1 * box_height;
         tp2 = entry - m_cfg.tp_mult2 * box_height;
         tp3 = entry - m_cfg.tp_mult3 * box_height;
         rr = (risk > 0.0 ? MathAbs(entry - tp2) / risk : 0.0);
        }
     }

   void ClearObjects()
     {
      if(!m_cfg.show_chart_objects) return;
      int total = ObjectsTotal(0, 0, -1);
      for(int i = total - 1; i >= 0; i--)
        {
         string name = ObjectName(0, i, 0, -1);
         if(StringFind(name, BOX_OBJ_PREFIX) == 0)
            ObjectDelete(0, name);
        }
     }

   void DrawBox(const VantageBoxTheoryResult &r)
     {
      if(!m_cfg.show_chart_objects || !r.box_found) return;
      ClearObjects();
      string rn = BOX_OBJ_PREFIX + "RANGE";
      ObjectCreate(0, rn, OBJ_RECTANGLE, 0, r.box_start_time, r.box_high, r.box_end_time, r.box_low);
      ObjectSetInteger(0, rn, OBJPROP_COLOR, clrSteelBlue);
      ObjectSetInteger(0, rn, OBJPROP_FILL, true);
      ObjectSetInteger(0, rn, OBJPROP_BACK, true);
      if(r.breakout_detected)
        {
         string ln = BOX_OBJ_PREFIX + "BR";
         ObjectCreate(0, ln, OBJ_HLINE, 0, 0, r.breakout_price);
         ObjectSetInteger(0, ln, OBJPROP_COLOR, r.breakout_direction == "UP" ? clrLime : clrTomato);
        }
     }

   string BuildSignalId(const string sym, const datetime st, const datetime et, const string dir, const string ev) const
     {
      return sym + "|" + IntegerToString((int)st) + "|" + IntegerToString((int)et) + "|" + dir + "|" + ev;
     }

public:
   CVantageBoxTheory(void) : m_symbol(""), m_last_entry_bar(0) { ZeroMemory(m_last); }

   bool Init(const string symbol, const VantageBoxTheoryConfig &cfg)
     {
      m_symbol = symbol;
      m_cfg = cfg;
      m_last_entry_bar = 0;
      ZeroMemory(m_last);
      m_validator.Configure(cfg.gold_aliases, cfg.allow_suffix, cfg.allow_prefix);
      return true;
     }

   bool Evaluate(const bool force, VantageBoxTheoryResult &out)
     {
      string base = "";
      ZeroMemory(out);
      out.valid = false;
      out.engine_enabled = m_cfg.enable;
      out.symbol = m_symbol;
      out.base_symbol = m_symbol;
      out.strategy = "BOX_THEORY";
      out.signal = "WAIT";
      out.box_status = "FORMING";
      out.direction = "—";
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
         out.disable_reason = VANTAGE_BOXTHEORY_DISABLE_MSG;
         out.reasons = VANTAGE_BOXTHEORY_DISABLE_MSG;
         out.valid = true;
         return true;
        }
      out.gold_symbol_valid = true;
      out.base_symbol = base;

      MqlRates box_rates[], entry_rates[], struct_rates[];
      if(!CopyClosed(m_cfg.tf_box, m_cfg.lookback_candles + 5, box_rates) ||
         !CopyClosed(m_cfg.tf_entry, 80, entry_rates) ||
         !CopyClosed(m_cfg.tf_structure, 30, struct_rates))
        {
         out.reasons = "Insufficient history";
         out.valid = true;
         return true;
        }

      datetime bar_time = entry_rates[0].time;
      if(bar_time == m_last_entry_bar && !force) { out = m_last; return out.valid; }

      double spread = (double)SymbolInfoInteger(m_symbol, SYMBOL_SPREAD);
      if(spread > m_cfg.max_spread_pts)
         AppendReason(out.reasons, "High spread");

      double atr_box = GetAtr(m_cfg.tf_box);
      if(atr_box <= 0) atr_box = CalcAtrFromRates(box_rates, ArraySize(box_rates));
      double atr_entry = GetAtr(m_cfg.tf_entry);
      if(atr_entry <= 0) atr_entry = CalcAtrFromRates(entry_rates, ArraySize(entry_rates));

      int bn = MathMin(ArraySize(box_rates), m_cfg.lookback_candles);
      double bhi, blo, inside_ratio, box_q;
      int upper, lower, span;
      datetime bstart, bend;
      ENUM_BOX_STATUS status = BOX_ST_FORMING;
      ENUM_BOX_SIGNAL signal = BOX_SIG_WAIT;
      string events = "";
      string reasons = "";

      if(!DetectBox(box_rates, bn, atr_box, bhi, blo, upper, lower, span, bstart, bend, inside_ratio, box_q))
        {
         Dbg("No valid box");
         AppendReason(reasons, "No valid consolidation box detected.");
         out.valid = true;
         out.analysis_active = true;
         out.reasons = reasons;
         out.eval_bar_time = bar_time;
         out.current_price = SymbolInfoDouble(m_symbol, SYMBOL_BID);
         m_last_entry_bar = bar_time;
         m_last = out;
         return true;
        }

      out.box_found = true;
      out.box_high = bhi;
      out.box_low = blo;
      out.box_mid = (bhi + blo) / 2.0;
      out.box_height = bhi - blo;
      out.upper_touches = upper;
      out.lower_touches = lower;
      out.box_age = span;
      out.box_start_time = bstart;
      out.box_end_time = bend;

      if(span < m_cfg.min_box_candles)
        {
         status = BOX_ST_FORMING;
         signal = BOX_SIG_WAIT;
         AppendReason(reasons, "Box still forming.");
         Dbg("Box forming");
        }
      else
        {
         string trap = "";
         datetime trap_t = 0;
         string br_dir = "";
         double br_price = 0.0, body_r = 0.0;
         datetime br_time = 0;
         bool br_ok = DetectBreakout(bhi, blo, box_rates, bn, bend, atr_box, br_dir, br_price, br_time, body_r);

         if(!br_ok && DetectFakeout(bhi, blo, box_rates, bn, bend, trap, trap_t))
           {
            status = (trap == "BULL_TRAP" ? BOX_ST_BULL_TRAP : BOX_ST_BEAR_TRAP);
            signal = BOX_SIG_INVALID;
            AppendReason(reasons, trap);
            AppendEvent(events, trap);
            Dbg(trap);
           }
         else if(!br_ok)
           {
            status = BOX_ST_VALID;
            signal = BOX_SIG_WATCH;
            AppendReason(reasons, "Valid box — waiting for breakout.");
            AppendEvent(events, "BOX_DETECTED");
            Dbg("Box detected");
           }
         else
           {
            out.breakout_detected = true;
            out.breakout_direction = br_dir;
            out.breakout_price = br_price;
            out.breakout_time = br_time;
            status = (br_dir == "UP" ? BOX_ST_BREAKOUT_UP : BOX_ST_BREAKOUT_DOWN);
            AppendEvent(events, br_dir == "UP" ? "BOX_BREAKOUT" : "BOX_BREAKDOWN");

            if(DetectFakeout(bhi, blo, box_rates, bn, br_time, trap, trap_t))
              {
               status = (trap == "BULL_TRAP" ? BOX_ST_BULL_TRAP : BOX_ST_BEAR_TRAP);
               signal = BOX_SIG_INVALID;
               AppendReason(reasons, trap);
               AppendEvent(events, trap);
              }
            else
              {
               string sw_dir = "";
               double sw_price = 0.0;
               out.sweep_detected = DetectSweep(bhi, blo, box_rates, bn, bstart, br_time, atr_box, sw_dir, sw_price);
               if(out.sweep_detected) { out.sweep_direction = sw_dir; out.sweep_price = sw_price; }

               bool rt_det = false, rt_conf = false;
               double rt_price = 0.0;
               int rt_wait = 0;
               DetectRetest(bhi, blo, br_dir, br_time, entry_rates, ArraySize(entry_rates), atr_entry,
                            rt_det, rt_conf, rt_price, rt_wait);
               out.retest_detected = rt_det;
               out.retest_confirmed = rt_conf;
               out.retest_price = rt_price;

               string htf = HtfBias(struct_rates, ArraySize(struct_rates));
               out.htf_bias = htf;
               bool fvg_ok = false;
               if(m_cfg.fvg_confirmation)
                 fvg_ok = (br_dir == "UP" ? DetectFvgBull(entry_rates, atr_entry) : DetectFvgBear(entry_rates, atr_entry));
               out.fvg_confirmation = fvg_ok;

               double score = ScoreSetup(box_q, true, body_r, rt_det, rt_conf, out.sweep_detected, fvg_ok, htf, br_dir, reasons);
               out.confidence_score = score;
               out.signal_quality = QualityStr(score);

               bool require_rt = m_cfg.require_retest || m_cfg.entry_mode == "BREAKOUT_RETEST_MODE";
               if(require_rt && !rt_det)
                 {
                  status = BOX_ST_RETESTING;
                  signal = BOX_SIG_WAIT;
                  AppendReason(reasons, "Waiting for retest confirmation.");
                  AppendEvent(events, "RETEST_STARTED");
                  Dbg("Waiting for retest");
                 }
               else if(require_rt && rt_det && !rt_conf)
                 {
                  status = BOX_ST_RETESTING;
                  signal = BOX_SIG_WAIT;
                  AppendReason(reasons, "Retest detected — awaiting confirmation candle.");
                  Dbg("Retest detected");
                 }
               else if(score >= m_cfg.minimum_signal_score)
                 {
                  if(br_dir == "UP")
                    {
                     status = BOX_ST_CONFIRMED_BULL;
                     signal = BOX_SIG_BUY;
                     out.direction = "BUY";
                     AppendEvent(events, "BUY_CONFIRMED");
                     Dbg("BUY confirmed");
                    }
                  else
                    {
                     status = BOX_ST_CONFIRMED_BEAR;
                     signal = BOX_SIG_SELL;
                     out.direction = "SELL";
                     AppendEvent(events, "SELL_CONFIRMED");
                     Dbg("SELL confirmed");
                    }
                  if(m_cfg.block_countertrend)
                    {
                     if(htf == "BEARISH" && signal == BOX_SIG_BUY) { signal = BOX_SIG_WAIT; AppendReason(reasons, "Blocked counter HTF"); }
                     if(htf == "BULLISH" && signal == BOX_SIG_SELL) { signal = BOX_SIG_WAIT; AppendReason(reasons, "Blocked counter HTF"); }
                    }
                  CalcRiskPlan(br_dir, bhi, blo, out.box_mid, out.box_height, br_price, rt_price, atr_box,
                               out.entry, out.stop_loss, out.tp1, out.tp2, out.tp3, out.risk_reward);
                 }
               else
                 {
                  AppendReason(reasons, "Signal rejected — insufficient confidence");
                  Dbg("Signal rejected");
                 }
              }
           }
        }

      if(span > m_cfg.max_box_age_candles)
        {
         status = BOX_ST_EXPIRED;
         signal = BOX_SIG_INVALID;
         AppendReason(reasons, "Box expired — too old.");
        }

      out.signal = SignalStr(signal);
      out.box_status = StatusStr(status);
      out.status_line = out.signal;
      out.reasons = reasons;
      out.events = events;
      out.technical_narrative = reasons;
      out.action_guidance = (signal == BOX_SIG_BUY || signal == BOX_SIG_SELL ?
                             "Analysis only — no auto-trade." : out.action_guidance);
      out.eval_bar_time = bar_time;
      out.current_price = SymbolInfoDouble(m_symbol, SYMBOL_BID);
      out.analysis_active = true;
      out.valid = true;

      string last_ev = events;
      int p = StringFind(events, "|", 0);
      while(p >= 0) { last_ev = StringSubstr(events, p + 1); p = StringFind(events, "|", p + 1); }
      if(last_ev == "") last_ev = "BOX";
      out.signal_id = BuildSignalId(m_symbol, bstart, bend, out.direction, last_ev);

      DrawBox(out);
      m_last_entry_bar = bar_time;
      m_last = out;
      return true;
     }

   string EventsToJsonArray(const string events) const
     {
      if(events == "") return "[]";
      string parts[];
      int n = StringSplit(events, '|', parts);
      string j = "[";
      for(int i = 0; i < n; i++)
        {
         if(i > 0) j += ",";
         j += "\"" + JsonEscape(parts[i]) + "\"";
        }
      j += "]";
      return j;
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

   string ToJson(const VantageBoxTheoryResult &r) const
     {
      string j = "{";
      j += "\"module\":\"box_theory\",";
      j += "\"version\":\"" + VANTAGE_BOXTHEORY_VERSION + "\",";
      j += "\"strategy\":\"BOX_THEORY\",";
      j += "\"valid\":" + (r.valid ? "true" : "false") + ",";
      j += "\"gold_symbol_valid\":" + (r.gold_symbol_valid ? "true" : "false") + ",";
      j += "\"engine_enabled\":" + (r.engine_enabled ? "true" : "false") + ",";
      j += "\"analysis_active\":" + (r.analysis_active ? "true" : "false") + ",";
      j += "\"symbol\":\"" + JsonEscape(r.symbol) + "\",";
      j += "\"base_symbol\":\"" + JsonEscape(r.base_symbol) + "\",";
      j += "\"timeframe\":\"" + EnumToString(m_cfg.tf_box) + "\",";
      j += "\"entry_timeframe\":\"" + EnumToString(m_cfg.tf_entry) + "\",";
      j += "\"structure_timeframe\":\"" + EnumToString(m_cfg.tf_structure) + "\",";
      j += "\"direction\":\"" + JsonEscape(r.direction) + "\",";
      j += "\"status\":\"" + JsonEscape(r.box_status) + "\",";
      j += "\"box_status\":\"" + JsonEscape(r.box_status) + "\",";
      j += "\"signal\":\"" + JsonEscape(r.signal) + "\",";
      j += "\"signal_quality\":\"" + JsonEscape(r.signal_quality) + "\",";
      j += "\"confidence_score\":" + DoubleToString(r.confidence_score, 1) + ",";
      j += "\"confidence\":" + DoubleToString(r.confidence_score, 1) + ",";
      j += "\"htf_bias\":\"" + JsonEscape(r.htf_bias) + "\",";
      j += "\"current_price\":" + DoubleToString(r.current_price, _Digits) + ",";
      j += "\"box\":{";
      j += "\"high\":" + DoubleToString(r.box_high, _Digits);
      j += ",\"low\":" + DoubleToString(r.box_low, _Digits);
      j += ",\"mid\":" + DoubleToString(r.box_mid, _Digits);
      j += ",\"height\":" + DoubleToString(r.box_height, _Digits);
      j += ",\"upper_touches\":" + IntegerToString(r.upper_touches);
      j += ",\"lower_touches\":" + IntegerToString(r.lower_touches);
      j += ",\"age_candles\":" + IntegerToString(r.box_age);
      j += ",\"start_time\":" + IntegerToString((int)r.box_start_time);
      j += ",\"end_time\":" + IntegerToString((int)r.box_end_time);
      j += "},";
      j += "\"breakout\":{\"detected\":" + (r.breakout_detected ? "true" : "false");
      j += ",\"direction\":\"" + JsonEscape(r.breakout_direction) + "\"";
      j += ",\"price\":" + DoubleToString(r.breakout_price, _Digits);
      j += ",\"confirmed\":" + (r.breakout_detected ? "true" : "false");
      j += ",\"time\":" + IntegerToString((int)r.breakout_time) + "},";
      j += "\"retest\":{\"detected\":" + (r.retest_detected ? "true" : "false");
      j += ",\"confirmed\":" + (r.retest_confirmed ? "true" : "false");
      j += ",\"price\":" + DoubleToString(r.retest_price, _Digits) + "},";
      j += "\"liquidity_sweep\":{\"detected\":" + (r.sweep_detected ? "true" : "false");
      j += ",\"direction\":\"" + JsonEscape(r.sweep_direction) + "\"";
      j += ",\"sweep_price\":" + DoubleToString(r.sweep_price, _Digits) + "},";
      j += "\"fvg_confirmation\":" + (r.fvg_confirmation ? "true" : "false") + ",";
      j += "\"entry\":" + DoubleToString(r.entry, _Digits) + ",";
      j += "\"stop_loss\":" + DoubleToString(r.stop_loss, _Digits) + ",";
      j += "\"tp1\":" + DoubleToString(r.tp1, _Digits) + ",";
      j += "\"tp2\":" + DoubleToString(r.tp2, _Digits) + ",";
      j += "\"tp3\":" + DoubleToString(r.tp3, _Digits) + ",";
      j += "\"risk_reward\":" + DoubleToString(r.risk_reward, 2) + ",";
      j += "\"events\":" + EventsToJsonArray(r.events) + ",";
      j += "\"reasons\":" + ReasonsToJsonArray(r.reasons) + ",";
      j += "\"signal_id\":\"" + JsonEscape(r.signal_id) + "\",";
      j += "\"status_line\":\"" + JsonEscape(r.status_line) + "\",";
      j += "\"technical_narrative\":\"" + JsonEscape(r.technical_narrative) + "\",";
      j += "\"action_guidance\":\"" + JsonEscape(r.action_guidance) + "\",";
      j += "\"eval_bar_time\":" + IntegerToString((int)r.eval_bar_time);
      j += "}";
      return j;
     }

   void Release()
     {
      ClearObjects();
      m_symbol = "";
      m_last_entry_bar = 0;
      ZeroMemory(m_last);
     }
  };

#endif
