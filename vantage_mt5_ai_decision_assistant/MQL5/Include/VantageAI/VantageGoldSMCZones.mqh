//+------------------------------------------------------------------+
//| VantageGoldSMCZones.mqh                                          |
//| Phase 4 — Displacement, FVG, Inverse FVG, OB, Breaker, Mitigation|
//| Closed bars only — advisory                                      |
//+------------------------------------------------------------------+
#ifndef VANTAGE_GOLD_SMC_ZONES_MQH
#define VANTAGE_GOLD_SMC_ZONES_MQH

#include "VantageGoldSMCTypes.mqh"

#define GSMC_MAX_FVG 8
#define GSMC_MAX_OB  8

struct VantageGoldSMCFvg
  {
   bool   bullish;
   bool   inverse;
   datetime created;
   double upper;
   double lower;
   double mid;
   double ce;
   double atr_size;
   double mitigation_pct;
   ENUM_SMC_ZONE_STATUS status;
   double quality;
   ENUM_TIMEFRAMES tf;
  };

struct VantageGoldSMCOb
  {
   bool   bullish;
   bool   is_breaker;
   bool   is_mitigation;
   datetime created;
   double upper;
   double lower;
   double body_upper;
   double body_lower;
   double mid;
   double ce;
   double mitigation_pct;
   ENUM_SMC_ZONE_STATUS status;
   double quality;
   bool   with_sweep;
   bool   with_fvg;
   bool   with_structure;
   ENUM_TIMEFRAMES tf;
  };

class CVantageGoldSMCZones
  {
private:
   string               m_symbol;
   VantageGoldSMCConfig m_cfg;
   int                  m_h_atr_m15;
   int                  m_h_atr_h1;

   void Rel(int &h)
     {
      if(h != INVALID_HANDLE) { IndicatorRelease(h); h = INVALID_HANDLE; }
     }

   double Clamp(const double v, const double lo, const double hi)
     {
      if(v < lo) return lo;
      if(v > hi) return hi;
      return v;
     }

   double Atr(const int handle)
     {
      double a[];
      if(handle == INVALID_HANDLE) return 0.0;
      if(CopyBuffer(handle, 0, 1, 1, a) != 1) return 0.0;
      return a[0];
     }

   double DispScore(const MqlRates &bar, const double atr)
     {
      if(atr <= 0.0) return 0.0;
      double range = bar.high - bar.low;
      if(range <= 0.0) return 0.0;
      double body = MathAbs(bar.close - bar.open);
      double body_atr = body / atr;
      double range_atr = range / atr;
      double close_pos = (bar.close >= bar.open)
                         ? (bar.close - bar.low) / range
                         : (bar.high - bar.close) / range;
      double score = Clamp(body_atr / MathMax(0.01, m_cfg.min_displacement_atr), 0.0, 1.5) * 50.0
                     + Clamp(range_atr / 1.2, 0.0, 1.0) * 25.0
                     + Clamp(close_pos, 0.0, 1.0) * 25.0;
      return Clamp(score, 0.0, 100.0);
     }

   string DispLabel(const double score)
     {
      if(score >= 85.0) return "Exceptional displacement (" + DoubleToString(score, 0) + ")";
      if(score >= 70.0) return "Strong displacement (" + DoubleToString(score, 0) + ")";
      if(score >= 55.0) return "Moderate displacement (" + DoubleToString(score, 0) + ")";
      if(score >= 35.0) return "Weak displacement (" + DoubleToString(score, 0) + ")";
      return "No displacement (" + DoubleToString(score, 0) + ")";
     }

   void UpdateFvgMitigation(VantageGoldSMCFvg &f, MqlRates &rates[], const int n)
     {
      if(f.status == SMC_ZONE_INVALIDATED || f.status == SMC_ZONE_FLIPPED) return;
      double span = f.upper - f.lower;
      if(span <= 0) return;
      double worst = 0.0;
      for(int i = 0; i < n; i++)
        {
         if(rates[i].time <= f.created) break;
         if(f.bullish)
           {
            if(rates[i].low < f.upper)
              {
               double fill = (f.upper - MathMax(rates[i].low, f.lower)) / span;
               if(fill > worst) worst = fill;
              }
            if(rates[i].close < f.lower)
              {
               f.status = SMC_ZONE_INVALIDATED;
               f.mitigation_pct = 100.0;
               return;
              }
           }
         else
           {
            if(rates[i].high > f.lower)
              {
               double fill = (MathMin(rates[i].high, f.upper) - f.lower) / span;
               if(fill > worst) worst = fill;
              }
            if(rates[i].close > f.upper)
              {
               f.status = SMC_ZONE_INVALIDATED;
               f.mitigation_pct = 100.0;
               return;
              }
           }
        }
      f.mitigation_pct = Clamp(worst * 100.0, 0.0, 100.0);
      if(f.mitigation_pct >= 99.0) f.status = SMC_ZONE_FULLY_MITIGATED;
      else if(f.mitigation_pct >= 50.0) f.status = SMC_ZONE_PARTIALLY_MITIGATED;
      else if(f.mitigation_pct > 0.0) f.status = SMC_ZONE_TOUCHED;
      else f.status = SMC_ZONE_FRESH;
     }

   void TryInverseFvg(VantageGoldSMCFvg &f, MqlRates &rates[], const int n, const double atr)
     {
      if(!m_cfg.enable_inverse_fvg) return;
      if(f.status == SMC_ZONE_FLIPPED) return;
      if(n < 1 || atr <= 0) return;
      double ds = DispScore(rates[0], atr);
      if(ds < m_cfg.min_displacement_score) return;
      if(f.bullish && rates[0].close < f.lower)
        {
         f.bullish = false;
         f.inverse = true;
         f.status = SMC_ZONE_FLIPPED;
         f.quality = Clamp(f.quality * 0.85 + ds * 0.15, 0, 100);
        }
      else if(!f.bullish && rates[0].close > f.upper)
        {
         f.bullish = true;
         f.inverse = true;
         f.status = SMC_ZONE_FLIPPED;
         f.quality = Clamp(f.quality * 0.85 + ds * 0.15, 0, 100);
        }
     }

   int DetectFvgs(MqlRates &rates[], const int n, const double atr,
                  const ENUM_TIMEFRAMES tf, VantageGoldSMCFvg &out[], int &count)
     {
      count = 0;
      ArrayResize(out, 0);
      if(n < 5 || atr <= 0) return 0;
      const double min_gap = m_cfg.min_fvg_atr * atr;
      // series: 0=newest closed. FVG uses candles i+2, i+1, i (older to newer in time)
      // For series: candle1=i+2, candle2=i+1, candle3=i
      for(int i = 0; i < n - 3 && count < m_cfg.max_fvgs; i++)
        {
         // Bullish FVG: low[i] > high[i+2]
         if(rates[i].low > rates[i + 2].high)
           {
            double gap = rates[i].low - rates[i + 2].high;
            if(gap < min_gap) continue;
            double ds = DispScore(rates[i + 1], atr);
            if(m_cfg.fvg_require_displacement && ds < m_cfg.min_displacement_score) continue;
            VantageGoldSMCFvg f;
            ZeroMemory(f);
            f.bullish = true;
            f.created = rates[i + 1].time;
            f.lower = rates[i + 2].high;
            f.upper = rates[i].low;
            f.mid = 0.5 * (f.upper + f.lower);
            f.ce = f.lower + 0.5 * (f.upper - f.lower); // CE = midpoint for bullish FVG commonly
            f.atr_size = gap / atr;
            f.tf = tf;
            f.quality = Clamp(40.0 + ds * 0.4 + Clamp(f.atr_size, 0, 2) * 10.0, 0, 100);
            f.status = SMC_ZONE_FRESH;
            ArrayResize(out, count + 1);
            out[count++] = f;
           }
         // Bearish FVG: high[i] < low[i+2]
         if(rates[i].high < rates[i + 2].low)
           {
            double gap = rates[i + 2].low - rates[i].high;
            if(gap < min_gap) continue;
            double ds = DispScore(rates[i + 1], atr);
            if(m_cfg.fvg_require_displacement && ds < m_cfg.min_displacement_score) continue;
            VantageGoldSMCFvg f;
            ZeroMemory(f);
            f.bullish = false;
            f.created = rates[i + 1].time;
            f.upper = rates[i + 2].low;
            f.lower = rates[i].high;
            f.mid = 0.5 * (f.upper + f.lower);
            f.ce = f.upper - 0.5 * (f.upper - f.lower);
            f.atr_size = gap / atr;
            f.tf = tf;
            f.quality = Clamp(40.0 + ds * 0.4 + Clamp(f.atr_size, 0, 2) * 10.0, 0, 100);
            f.status = SMC_ZONE_FRESH;
            ArrayResize(out, count + 1);
            out[count++] = f;
           }
        }
      for(int k = 0; k < count; k++)
        {
         UpdateFvgMitigation(out[k], rates, n);
         TryInverseFvg(out[k], rates, n, atr);
        }
      return count;
     }

   void UpdateObMitigation(VantageGoldSMCOb &ob, MqlRates &rates[], const int n)
     {
      if(ob.status == SMC_ZONE_INVALIDATED) return;
      double hi = (m_cfg.ob_refinement_mode == 1) ? ob.body_upper : ob.upper;
      double lo = (m_cfg.ob_refinement_mode == 1) ? ob.body_lower : ob.lower;
      if(m_cfg.ob_refinement_mode == 2)
        {
         // CE band around midpoint
         double half = 0.25 * (hi - lo);
         hi = ob.mid + half;
         lo = ob.mid - half;
        }
      double span = hi - lo;
      if(span <= 0) return;
      double worst = 0.0;
      for(int i = 0; i < n; i++)
        {
         if(rates[i].time <= ob.created) break;
         if(ob.bullish)
           {
            if(rates[i].low <= hi && rates[i].high >= lo)
              {
               double fill = (hi - MathMax(rates[i].low, lo)) / span;
               if(fill > worst) worst = fill;
              }
            if(rates[i].close < lo)
              {
               ob.status = SMC_ZONE_INVALIDATED;
               ob.mitigation_pct = 100.0;
               if(m_cfg.enable_breaker)
                 {
                  // candidate breaker if next displacement closes back above
                 }
               return;
              }
           }
         else
           {
            if(rates[i].high >= lo && rates[i].low <= hi)
              {
               double fill = (MathMin(rates[i].high, hi) - lo) / span;
               if(fill > worst) worst = fill;
              }
            if(rates[i].close > hi)
              {
               ob.status = SMC_ZONE_INVALIDATED;
               ob.mitigation_pct = 100.0;
               return;
              }
           }
        }
      ob.mitigation_pct = Clamp(worst * 100.0, 0.0, 100.0);
      if(ob.mitigation_pct >= 99.0) { ob.status = SMC_ZONE_FULLY_MITIGATED; ob.is_mitigation = true; }
      else if(ob.mitigation_pct >= 40.0) { ob.status = SMC_ZONE_PARTIALLY_MITIGATED; ob.is_mitigation = true; }
      else if(ob.mitigation_pct > 0.0) ob.status = SMC_ZONE_TOUCHED;
      else ob.status = SMC_ZONE_FRESH;
     }

   int DetectOrderBlocks(MqlRates &rates[], const int n, const double atr,
                         const ENUM_TIMEFRAMES tf, VantageGoldSMCOb &out[], int &count,
                         const bool recent_sweep_bull_ctx, const bool recent_sweep_bear_ctx)
     {
      count = 0;
      ArrayResize(out, 0);
      if(n < 8 || atr <= 0) return 0;
      for(int i = 1; i < n - 3 && count < m_cfg.max_obs; i++)
        {
         double ds = DispScore(rates[i], atr);
         if(m_cfg.ob_require_displacement && ds < m_cfg.min_displacement_score)
            continue;
         // Bullish OB: displacement candle bullish; prior candle bearish (origin)
         if(rates[i].close > rates[i].open && rates[i + 1].close < rates[i + 1].open)
           {
            // Prefer break of recent high (structure intent)
            bool broke = (rates[i].close > rates[i + 2].high);
            if(!broke && ds < m_cfg.min_displacement_score + 10) continue;
            VantageGoldSMCOb ob;
            ZeroMemory(ob);
            ob.bullish = true;
            ob.created = rates[i + 1].time;
            ob.upper = rates[i + 1].high;
            ob.lower = rates[i + 1].low;
            ob.body_upper = MathMax(rates[i + 1].open, rates[i + 1].close);
            ob.body_lower = MathMin(rates[i + 1].open, rates[i + 1].close);
            ob.mid = 0.5 * (ob.upper + ob.lower);
            ob.ce = ob.lower + 0.5 * (ob.upper - ob.lower);
            ob.tf = tf;
            ob.with_structure = broke;
            ob.with_sweep = recent_sweep_bull_ctx;
            ob.quality = Clamp(35.0 + ds * 0.45 + (broke ? 10.0 : 0) + (ob.with_sweep ? 12.0 : 0), 0, 100);
            if(m_cfg.ob_prefer_sweep_origin && !ob.with_sweep)
               ob.quality *= 0.85;
            ArrayResize(out, count + 1);
            out[count++] = ob;
           }
         // Bearish OB
         if(rates[i].close < rates[i].open && rates[i + 1].close > rates[i + 1].open)
           {
            bool broke = (rates[i].close < rates[i + 2].low);
            if(!broke && ds < m_cfg.min_displacement_score + 10) continue;
            VantageGoldSMCOb ob;
            ZeroMemory(ob);
            ob.bullish = false;
            ob.created = rates[i + 1].time;
            ob.upper = rates[i + 1].high;
            ob.lower = rates[i + 1].low;
            ob.body_upper = MathMax(rates[i + 1].open, rates[i + 1].close);
            ob.body_lower = MathMin(rates[i + 1].open, rates[i + 1].close);
            ob.mid = 0.5 * (ob.upper + ob.lower);
            ob.ce = ob.upper - 0.5 * (ob.upper - ob.lower);
            ob.tf = tf;
            ob.with_structure = broke;
            ob.with_sweep = recent_sweep_bear_ctx;
            ob.quality = Clamp(35.0 + ds * 0.45 + (broke ? 10.0 : 0) + (ob.with_sweep ? 12.0 : 0), 0, 100);
            if(m_cfg.ob_prefer_sweep_origin && !ob.with_sweep)
               ob.quality *= 0.85;
            ArrayResize(out, count + 1);
            out[count++] = ob;
           }
        }
      for(int k = 0; k < count; k++)
         UpdateObMitigation(out[k], rates, n);

      // Breakers: invalidated OB then price reclaims opposite side with displacement
      if(m_cfg.enable_breaker && n >= 2)
        {
         double ds0 = DispScore(rates[0], atr);
         for(int k = 0; k < count; k++)
           {
            if(out[k].status != SMC_ZONE_INVALIDATED) continue;
            if(ds0 < m_cfg.min_displacement_score) continue;
            if(out[k].bullish && rates[0].close < out[k].lower)
              {
               // failed bullish OB → bearish breaker
               out[k].is_breaker = true;
               out[k].bullish = false;
               out[k].status = SMC_ZONE_FLIPPED;
               out[k].quality = Clamp(out[k].quality + 8.0, 0, 100);
              }
            else if(!out[k].bullish && rates[0].close > out[k].upper)
              {
               out[k].is_breaker = true;
               out[k].bullish = true;
               out[k].status = SMC_ZONE_FLIPPED;
               out[k].quality = Clamp(out[k].quality + 8.0, 0, 100);
              }
           }
        }
      return count;
     }

   int BestFvgIdx(VantageGoldSMCFvg &arr[], const int n, const ENUM_SMC_DIRECTION prefer)
     {
      int best = -1;
      double q = -1;
      for(int i = 0; i < n; i++)
        {
         if(arr[i].status == SMC_ZONE_FULLY_MITIGATED || arr[i].status == SMC_ZONE_INVALIDATED)
            continue;
         bool dir_ok = true;
         if(prefer == SMC_DIR_BEARISH && arr[i].bullish && !arr[i].inverse) dir_ok = false;
         if(prefer == SMC_DIR_BULLISH && !arr[i].bullish && !arr[i].inverse) dir_ok = false;
         double score = arr[i].quality;
         if(!dir_ok) score *= 0.55;
         if(arr[i].status == SMC_ZONE_FRESH) score += 8;
         if(score > q) { q = score; best = i; }
        }
      return best;
     }

   int BestObIdx(VantageGoldSMCOb &arr[], const int n, const ENUM_SMC_DIRECTION prefer)
     {
      int best = -1;
      double q = -1;
      for(int i = 0; i < n; i++)
        {
         if(arr[i].status == SMC_ZONE_FULLY_MITIGATED && !arr[i].is_breaker) continue;
         if(arr[i].status == SMC_ZONE_INVALIDATED && !arr[i].is_breaker) continue;
         bool dir_ok = true;
         if(prefer == SMC_DIR_BEARISH && arr[i].bullish) dir_ok = false;
         if(prefer == SMC_DIR_BULLISH && !arr[i].bullish) dir_ok = false;
         double score = arr[i].quality;
         if(!dir_ok) score *= 0.55;
         if(arr[i].is_breaker) score += 6;
         if(arr[i].status == SMC_ZONE_FRESH) score += 8;
         if(score > q) { q = score; best = i; }
        }
      return best;
     }

public:
   CVantageGoldSMCZones(void) : m_symbol(""), m_h_atr_m15(INVALID_HANDLE), m_h_atr_h1(INVALID_HANDLE)
     {
      ZeroMemory(m_cfg);
     }

   bool Init(const string symbol, const VantageGoldSMCConfig &cfg)
     {
      Release();
      m_symbol = symbol;
      m_cfg = cfg;
      if(m_cfg.min_fvg_atr <= 0.0) m_cfg.min_fvg_atr = 0.12;
      if(m_cfg.max_fvgs <= 0) m_cfg.max_fvgs = GSMC_MAX_FVG;
      if(m_cfg.max_obs <= 0) m_cfg.max_obs = GSMC_MAX_OB;
      if(m_cfg.max_fvgs > GSMC_MAX_FVG) m_cfg.max_fvgs = GSMC_MAX_FVG;
      if(m_cfg.max_obs > GSMC_MAX_OB) m_cfg.max_obs = GSMC_MAX_OB;
      m_h_atr_m15 = iATR(m_symbol, m_cfg.tf_confirm, m_cfg.atr_period);
      m_h_atr_h1 = iATR(m_symbol, m_cfg.tf_bias, m_cfg.atr_period);
      return (m_h_atr_m15 != INVALID_HANDLE && m_h_atr_h1 != INVALID_HANDLE);
     }

   void Release(void)
     {
      Rel(m_h_atr_m15);
      Rel(m_h_atr_h1);
     }

   bool Analyze(VantageGoldSMCResult &r)
     {
      MqlRates m15[];
      int n = CopyRates(m_symbol, m_cfg.tf_confirm, 1, 120, m15);
      if(n < 20) return false;
      ArraySetAsSeries(m15, true);
      double atr = Atr(m_h_atr_m15);
      if(atr <= 0.0) atr = Atr(m_h_atr_h1);
      if(atr <= 0.0) return false;

      double ds = DispScore(m15[0], atr);
      // blend with existing displacement string from structure if weak
      r.displacement_status = DispLabel(ds);

      bool sweep_bull_ctx = (StringFind(r.latest_liquidity_event, "Sell-Side swept") >= 0);
      bool sweep_bear_ctx = (StringFind(r.latest_liquidity_event, "Buy-Side swept") >= 0);

      VantageGoldSMCFvg fvgs[];
      VantageGoldSMCOb  obs[];
      int nf = 0, no = 0;
      DetectFvgs(m15, n, atr, m_cfg.tf_confirm, fvgs, nf);
      DetectOrderBlocks(m15, n, atr, m_cfg.tf_confirm, obs, no, sweep_bull_ctx, sweep_bear_ctx);

      // Tag OB with overlapping FVG
      for(int o = 0; o < no; o++)
        {
         for(int f = 0; f < nf; f++)
           {
            if(obs[o].bullish != fvgs[f].bullish) continue;
            if(obs[o].lower <= fvgs[f].upper && obs[o].upper >= fvgs[f].lower)
              {
               obs[o].with_fvg = true;
               obs[o].quality = Clamp(obs[o].quality + 10.0, 0, 100);
               break;
              }
           }
        }

      ENUM_SMC_DIRECTION prefer = r.h1_bias;
      if(prefer == SMC_DIR_NEUTRAL || prefer == SMC_DIR_CONFLICTING)
         prefer = r.h4_bias;

      int bi_f = BestFvgIdx(fvgs, nf, prefer);
      int bi_o = BestObIdx(obs, no, prefer);

      r.has_fresh_fvg = false;
      r.has_valid_ob = false;
      r.has_breaker = false;
      r.has_inverse_fvg = false;
      for(int i = 0; i < nf; i++)
        {
         if(fvgs[i].status == SMC_ZONE_FRESH || fvgs[i].status == SMC_ZONE_TOUCHED)
            r.has_fresh_fvg = true;
         if(fvgs[i].inverse) r.has_inverse_fvg = true;
        }
      for(int i = 0; i < no; i++)
        {
         if(obs[i].status == SMC_ZONE_FRESH || obs[i].status == SMC_ZONE_TOUCHED ||
            obs[i].status == SMC_ZONE_PARTIALLY_MITIGATED)
            r.has_valid_ob = true;
         if(obs[i].is_breaker) r.has_breaker = true;
        }

      // Summaries
      r.fvg_summary = (nf <= 0) ? "No qualifying FVG" :
                      IntegerToString(nf) + " FVG(s); best Q=" +
                      (bi_f >= 0 ? DoubleToString(fvgs[bi_f].quality, 0) : "—");
      r.order_block_summary = (no <= 0) ? "No qualifying order block" :
                              IntegerToString(no) + " OB(s); best Q=" +
                              (bi_o >= 0 ? DoubleToString(obs[bi_o].quality, 0) : "—");
      r.breaker_summary = r.has_breaker ? "Breaker present" : "No breaker";

      // Choose primary POI: prefer confluence OB+FVG, else higher quality
      double qf = (bi_f >= 0) ? fvgs[bi_f].quality : -1;
      double qo = (bi_o >= 0) ? obs[bi_o].quality : -1;
      bool use_ob = (qo >= qf && bi_o >= 0);
      if(bi_o >= 0 && obs[bi_o].with_fvg) use_ob = true;
      if(bi_f < 0 && bi_o >= 0) use_ob = true;
      if(bi_o < 0 && bi_f >= 0) use_ob = false;

      if(use_ob && bi_o >= 0)
        {
         VantageGoldSMCOb ob = obs[bi_o];
         r.primary_poi_type = ob.is_breaker ? "Breaker Block" :
                              (ob.is_mitigation ? "Mitigation Block" : "Order Block");
         r.primary_poi_dir = ob.bullish ? "Bullish" : "Bearish";
         r.primary_poi_status = SmcZoneStatusToString(ob.status);
         r.poi_upper = (m_cfg.ob_refinement_mode == 1) ? ob.body_upper : ob.upper;
         r.poi_lower = (m_cfg.ob_refinement_mode == 1) ? ob.body_lower : ob.lower;
         r.poi_mid = ob.mid;
         r.poi_ce = ob.ce;
         r.poi_mitigation_pct = ob.mitigation_pct;
         r.poi_quality = ob.quality;
         r.entry_zone = DoubleToString(r.poi_lower, _Digits) + "-" + DoubleToString(r.poi_upper, _Digits);
         r.invalidation = ob.bullish
                          ? ("M15 close below " + DoubleToString(ob.lower, _Digits))
                          : ("M15 close above " + DoubleToString(ob.upper, _Digits));
        }
      else if(bi_f >= 0)
        {
         VantageGoldSMCFvg f = fvgs[bi_f];
         r.primary_poi_type = f.inverse ? "Inverse FVG" : "Fair Value Gap";
         r.primary_poi_dir = f.bullish ? "Bullish" : "Bearish";
         r.primary_poi_status = SmcZoneStatusToString(f.status);
         r.poi_upper = f.upper;
         r.poi_lower = f.lower;
         r.poi_mid = f.mid;
         r.poi_ce = f.ce;
         r.poi_mitigation_pct = f.mitigation_pct;
         r.poi_quality = f.quality;
         r.entry_zone = DoubleToString(f.lower, _Digits) + "-" + DoubleToString(f.upper, _Digits);
         r.invalidation = f.bullish
                          ? ("M15 close below " + DoubleToString(f.lower, _Digits))
                          : ("M15 close above " + DoubleToString(f.upper, _Digits));
        }
      else
        {
         r.primary_poi_type = "None";
         r.primary_poi_dir = "Neutral";
         r.primary_poi_status = "";
         r.poi_upper = 0; r.poi_lower = 0; r.poi_mid = 0; r.poi_ce = 0;
         r.poi_mitigation_pct = 0; r.poi_quality = 0;
         r.entry_zone = "";
         r.invalidation = "";
        }

      r.engine_phase = 4;
      r.setup_phase = SmcPhaseToString(SMC_PHASE_POI_MAPPED);
      r.status_line = "ACTIVE – GOLD ONLY (Phase 4 POI)";
      r.setup_type = "No Valid SMC Setup";

      string narr = r.technical_narrative;
      if(narr != "") narr += " ";
      narr += r.displacement_status + ".";
      if(r.primary_poi_type != "None")
         narr += " Primary POI: " + r.primary_poi_dir + " " + r.primary_poi_type +
                 " " + DoubleToString(r.poi_lower, _Digits) + "-" + DoubleToString(r.poi_upper, _Digits) +
                 " (" + r.primary_poi_status + ", Q=" + DoubleToString(r.poi_quality, 0) + ").";
      else
         narr += " No qualifying FVG/OB after displacement filters.";
      narr += " An FVG or order block alone is not a complete setup — confluence scoring lands in Phase 6.";
      r.technical_narrative = narr;

      if(r.has_fresh_fvg) r.reasons_for += "Fresh/touched FVG;";
      if(r.has_valid_ob) r.reasons_for += "Valid order block;";
      if(r.has_breaker) r.reasons_for += "Breaker block;";
      if(ds >= m_cfg.min_displacement_score) r.reasons_for += "Displacement present;";
      r.reasons_against += "Setup score engine not active yet;";
      if(r.primary_poi_type == "None")
         r.reasons_against += "No qualifying POI;";
      if(StringFind(r.primary_poi_status, "mitigated") >= 0)
         r.reasons_against += "POI already mitigated;";

      r.recommendation = (r.primary_poi_type != "None")
         ? ("WAIT — monitor reaction at " + r.primary_poi_dir + " " + r.primary_poi_type +
            " (" + r.entry_zone + "). No scored setup yet.")
         : "WAIT — no qualifying FVG/OB. Continue tracking liquidity draw.";

      Print("[GoldSMC][ZONES] disp=", DoubleToString(ds, 0),
            " fvg=", nf, " ob=", no,
            " poi=", r.primary_poi_type, " ", r.primary_poi_dir);
      return true;
     }
  };

#endif
//+------------------------------------------------------------------+
