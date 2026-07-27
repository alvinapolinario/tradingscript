//+------------------------------------------------------------------+
//| VantageM5Desk.mqh                                                |
//| M5 Alignment Desk feed: H1 bias · M15 structure · M5 trigger     |
//| EMA 20/50/200 · ATR/ADX 14 · R:R · news window · setup age       |
//| Advisory-only — no trade execution                               |
//+------------------------------------------------------------------+
#ifndef VANTAGE_M5_DESK_MQH
#define VANTAGE_M5_DESK_MQH

#include "VantageTypes.mqh"
#include "VantageSymbol.mqh"
#include "VantageRisk.mqh"

struct VantageM5DeskSnap
  {
   bool   valid;
   string h1_bias;
   string m15_structure;
   string m5_trigger;
   bool   h1_m15_aligned;
   double adx14;
   double atr14;
   double ema20;
   double ema50;
   double ema200;
   bool   ema_stack_ok;
   bool   m5_closed_confirmed;
   int    setup_age_m5;
   double reward_risk_ratio;
   double planned_equity_risk_pct;
   bool   news_available;
   bool   news_blocked;
   int    minutes_to_high_impact;
   int    max_spread_points;
   string allowed_direction; // BUY | SELL | NONE
   string note;
  };

class CVantageM5Desk
  {
private:
   string          m_symbol;
   int             m_hEma20_m5;
   int             m_hEma50_m5;
   int             m_hEma200_m5;
   int             m_hAtr_m5;
   int             m_hAdx_m5;
   int             m_hEma20_m15;
   int             m_hEma50_m15;
   int             m_hEma200_m15;
   int             m_hEma20_h1;
   int             m_hEma50_h1;
   int             m_hEma200_h1;
   datetime        m_setup_bar_time;
   string          m_setup_dir;
   int             m_news_before_min;
   int             m_news_after_min;
   double          m_min_adx;
   double          m_min_rr;
   double          m_risk_pct;
   int             m_max_setup_age;

   bool Copy1(const int handle, const int buffer, const int shift, double &out_v)
     {
      out_v = 0.0;
      if(handle == INVALID_HANDLE)
         return false;
      double a[];
      if(CopyBuffer(handle, buffer, shift, 1, a) != 1)
         return false;
      out_v = a[0];
      return MathIsValidNumber(out_v);
     }

   string BiasFromEma(const double close_px, const double e20, const double e50, const double e200)
     {
      if(close_px <= 0.0 || e20 <= 0.0 || e50 <= 0.0 || e200 <= 0.0)
         return "NEUTRAL";
      const bool bull = (close_px > e20 && e20 > e50 && e50 > e200);
      const bool bear = (close_px < e20 && e20 < e50 && e50 < e200);
      if(bull)
         return "BULLISH";
      if(bear)
         return "BEARISH";
      // Soft bias: price vs medium + medium vs trend
      if(close_px > e50 && e50 >= e200)
         return "BULLISH";
      if(close_px < e50 && e50 <= e200)
         return "BEARISH";
      return "NEUTRAL";
     }

   bool ClosedClose(const ENUM_TIMEFRAMES tf, double &out_close, datetime &out_time)
     {
      out_close = 0.0;
      out_time = 0;
      MqlRates r[];
      if(CopyRates(m_symbol, tf, 1, 1, r) != 1)
         return false;
      out_close = r[0].close;
      out_time = r[0].time;
      return (out_close > 0.0 && out_time > 0);
     }

   void ReleaseHandle(int &h)
     {
      if(h != INVALID_HANDLE)
        {
         IndicatorRelease(h);
         h = INVALID_HANDLE;
        }
     }

   // High-impact economic calendar near now (USD for gold/BTC desk).
   void EvalNewsWindow(VantageM5DeskSnap &snap)
     {
      snap.news_available = false;
      snap.news_blocked = false;
      snap.minutes_to_high_impact = -1;

      datetime now = TimeTradeServer();
      if(now <= 0)
         now = TimeCurrent();
      const datetime from = now - (datetime)(m_news_after_min * 60);
      const datetime to   = now + (datetime)(m_news_before_min * 60) + 3600; // peek 1h past block start

      MqlCalendarValue values[];
      ResetLastError();
      int n = CalendarValueHistory(values, from, to, NULL, "USD");
      if(n < 0)
        {
         // Calendar unavailable on some brokers / offline — leave news_available=false
         return;
        }
      snap.news_available = true;

      int best_minutes = 100000;
      bool blocked = false;
      for(int i = 0; i < n; i++)
        {
         MqlCalendarEvent ev;
         if(!CalendarEventById(values[i].event_id, ev))
            continue;
         if(ev.importance < CALENDAR_IMPORTANCE_HIGH)
            continue;

         datetime ev_time = (datetime)values[i].time;
         if(ev_time <= 0)
            continue;

         const long delta_sec = (long)ev_time - (long)now;
         const int mins = (int)(delta_sec / 60);

         // Block: within before-window ahead, or within after-window past
         if(delta_sec >= 0 && mins <= m_news_before_min)
            blocked = true;
         if(delta_sec < 0 && (-mins) <= m_news_after_min)
            blocked = true;

         if(delta_sec >= 0 && mins < best_minutes)
            best_minutes = mins;
        }

      snap.news_blocked = blocked;
      if(best_minutes < 100000)
         snap.minutes_to_high_impact = best_minutes;
      else
         snap.minutes_to_high_impact = -1;
     }

   void EvalRiskSetup(const string direction,
                      const double atr,
                      const double mid,
                      const VantageSymbolSpec &spec,
                      VantageM5DeskSnap &snap)
     {
      snap.reward_risk_ratio = 0.0;
      snap.planned_equity_risk_pct = m_risk_pct;

      if(atr <= 0.0 || mid <= 0.0 || !spec.valid)
         return;

      const int digits = spec.digits;
      double entry = NormalizeDouble(mid, digits);
      double sl = 0.0;
      double tp = 0.0;
      ENUM_ORDER_TYPE otype = ORDER_TYPE_BUY;

      if(direction == "BUY")
        {
         sl = NormalizeDouble(entry - 1.0 * atr, digits);
         tp = NormalizeDouble(entry + m_min_rr * atr, digits);
         otype = ORDER_TYPE_BUY;
        }
      else if(direction == "SELL")
        {
         sl = NormalizeDouble(entry + 1.0 * atr, digits);
         tp = NormalizeDouble(entry - m_min_rr * atr, digits);
         otype = ORDER_TYPE_SELL;
        }
      else
        {
         // Neutral — still report theoretical R:R of playbook ATR geometry
         snap.reward_risk_ratio = m_min_rr;
         return;
        }

      if(sl <= 0.0 || tp <= 0.0)
         return;

      // Geometric R:R from ATR multiples (authoritative for desk playbook)
      const double risk_dist = MathAbs(entry - sl);
      const double reward_dist = MathAbs(tp - entry);
      if(risk_dist > 0.0)
         snap.reward_risk_ratio = reward_dist / risk_dist;

      // Size for playbook risk % using broker calc when possible
      double vol = spec.volume_min > 0.0 ? spec.volume_min : 0.01;
      VantageRiskEstimate trial;
      if(VantageCalcRiskFromLevels(m_symbol, spec, otype, vol, entry, sl, tp, trial) &&
         trial.available && trial.money_at_risk > 0.0)
        {
         const double equity = AccountInfoDouble(ACCOUNT_EQUITY);
         if(equity > 0.0 && m_risk_pct > 0.0)
           {
            const double target_money = equity * (m_risk_pct / 100.0);
            double sized = vol * (target_money / trial.money_at_risk);
            if(spec.volume_step > 0.0)
               sized = MathFloor(sized / spec.volume_step) * spec.volume_step;
            if(sized < spec.volume_min)
               sized = spec.volume_min;
            if(spec.volume_max > 0.0 && sized > spec.volume_max)
               sized = spec.volume_max;

            VantageRiskEstimate sized_risk;
            if(VantageCalcRiskFromLevels(m_symbol, spec, otype, sized, entry, sl, tp, sized_risk) &&
               sized_risk.available)
              {
               snap.planned_equity_risk_pct = sized_risk.equity_risk_pct;
               if(sized_risk.reward_risk_ratio > 0.0)
                  snap.reward_risk_ratio = sized_risk.reward_risk_ratio;
              }
           }
         else if(trial.reward_risk_ratio > 0.0)
            snap.reward_risk_ratio = trial.reward_risk_ratio;
        }

      if(snap.reward_risk_ratio <= 0.0)
         snap.reward_risk_ratio = m_min_rr;
     }

public:
   CVantageM5Desk(void)
     {
      m_symbol = "";
      m_hEma20_m5 = m_hEma50_m5 = m_hEma200_m5 = INVALID_HANDLE;
      m_hAtr_m5 = m_hAdx_m5 = INVALID_HANDLE;
      m_hEma20_m15 = m_hEma50_m15 = m_hEma200_m15 = INVALID_HANDLE;
      m_hEma20_h1 = m_hEma50_h1 = m_hEma200_h1 = INVALID_HANDLE;
      m_setup_bar_time = 0;
      m_setup_dir = "";
      m_news_before_min = 30;
      m_news_after_min = 15;
      m_min_adx = 20.0;
      m_min_rr = 2.0;
      m_risk_pct = 0.50;
      m_max_setup_age = 3;
     }

   bool Init(const string symbol,
             const int news_before_min = 30,
             const int news_after_min = 15,
             const double min_adx = 20.0,
             const double min_rr = 2.0,
             const double risk_pct = 0.50,
             const int max_setup_age = 3)
     {
      Release();
      m_symbol = symbol;
      m_news_before_min = news_before_min;
      m_news_after_min = news_after_min;
      m_min_adx = min_adx;
      m_min_rr = min_rr;
      m_risk_pct = risk_pct;
      m_max_setup_age = max_setup_age;

      m_hEma20_m5  = iMA(m_symbol, PERIOD_M5, 20, 0, MODE_EMA, PRICE_CLOSE);
      m_hEma50_m5  = iMA(m_symbol, PERIOD_M5, 50, 0, MODE_EMA, PRICE_CLOSE);
      m_hEma200_m5 = iMA(m_symbol, PERIOD_M5, 200, 0, MODE_EMA, PRICE_CLOSE);
      m_hAtr_m5    = iATR(m_symbol, PERIOD_M5, 14);
      m_hAdx_m5    = iADX(m_symbol, PERIOD_M5, 14);

      m_hEma20_m15  = iMA(m_symbol, PERIOD_M15, 20, 0, MODE_EMA, PRICE_CLOSE);
      m_hEma50_m15  = iMA(m_symbol, PERIOD_M15, 50, 0, MODE_EMA, PRICE_CLOSE);
      m_hEma200_m15 = iMA(m_symbol, PERIOD_M15, 200, 0, MODE_EMA, PRICE_CLOSE);

      m_hEma20_h1  = iMA(m_symbol, PERIOD_H1, 20, 0, MODE_EMA, PRICE_CLOSE);
      m_hEma50_h1  = iMA(m_symbol, PERIOD_H1, 50, 0, MODE_EMA, PRICE_CLOSE);
      m_hEma200_h1 = iMA(m_symbol, PERIOD_H1, 200, 0, MODE_EMA, PRICE_CLOSE);

      if(m_hEma20_m5 == INVALID_HANDLE || m_hEma50_m5 == INVALID_HANDLE || m_hEma200_m5 == INVALID_HANDLE ||
         m_hAtr_m5 == INVALID_HANDLE || m_hAdx_m5 == INVALID_HANDLE ||
         m_hEma20_m15 == INVALID_HANDLE || m_hEma50_m15 == INVALID_HANDLE || m_hEma200_m15 == INVALID_HANDLE ||
         m_hEma20_h1 == INVALID_HANDLE || m_hEma50_h1 == INVALID_HANDLE || m_hEma200_h1 == INVALID_HANDLE)
        {
         Print("[VantageAI] M5 desk indicator init failed err=", GetLastError());
         Release();
         return false;
        }
      return true;
     }

   void Release(void)
     {
      ReleaseHandle(m_hEma20_m5);
      ReleaseHandle(m_hEma50_m5);
      ReleaseHandle(m_hEma200_m5);
      ReleaseHandle(m_hAtr_m5);
      ReleaseHandle(m_hAdx_m5);
      ReleaseHandle(m_hEma20_m15);
      ReleaseHandle(m_hEma50_m15);
      ReleaseHandle(m_hEma200_m15);
      ReleaseHandle(m_hEma20_h1);
      ReleaseHandle(m_hEma50_h1);
      ReleaseHandle(m_hEma200_h1);
      m_setup_bar_time = 0;
      m_setup_dir = "";
     }

   bool Evaluate(const VantageSymbolSpec &spec,
                 const int max_spread_points,
                 VantageM5DeskSnap &snap)
     {
      snap.valid = false;
      snap.h1_bias = "NEUTRAL";
      snap.m15_structure = "NEUTRAL";
      snap.m5_trigger = "NEUTRAL";
      snap.h1_m15_aligned = false;
      snap.adx14 = 0.0;
      snap.atr14 = 0.0;
      snap.ema20 = 0.0;
      snap.ema50 = 0.0;
      snap.ema200 = 0.0;
      snap.ema_stack_ok = false;
      snap.m5_closed_confirmed = false;
      snap.setup_age_m5 = 0;
      snap.reward_risk_ratio = 0.0;
      snap.planned_equity_risk_pct = m_risk_pct;
      snap.news_available = false;
      snap.news_blocked = false;
      snap.minutes_to_high_impact = -1;
      snap.allowed_direction = "NONE";
      snap.max_spread_points = max_spread_points;
      snap.note = "";

      if(m_symbol == "" || m_hAdx_m5 == INVALID_HANDLE)
        {
         snap.note = "M5 desk not initialized";
         return false;
        }

      double c_h1 = 0, c_m15 = 0, c_m5 = 0;
      datetime t_h1 = 0, t_m15 = 0, t_m5 = 0;
      if(!ClosedClose(PERIOD_H1, c_h1, t_h1) ||
         !ClosedClose(PERIOD_M15, c_m15, t_m15) ||
         !ClosedClose(PERIOD_M5, c_m5, t_m5))
        {
         snap.note = "Insufficient M5/M15/H1 history";
         return false;
        }
      snap.m5_closed_confirmed = true;

      double e20h1, e50h1, e200h1;
      double e20m15, e50m15, e200m15;
      double e20m5, e50m5, e200m5;
      if(!Copy1(m_hEma20_h1, 0, 1, e20h1) || !Copy1(m_hEma50_h1, 0, 1, e50h1) || !Copy1(m_hEma200_h1, 0, 1, e200h1) ||
         !Copy1(m_hEma20_m15, 0, 1, e20m15) || !Copy1(m_hEma50_m15, 0, 1, e50m15) || !Copy1(m_hEma200_m15, 0, 1, e200m15) ||
         !Copy1(m_hEma20_m5, 0, 1, e20m5) || !Copy1(m_hEma50_m5, 0, 1, e50m5) || !Copy1(m_hEma200_m5, 0, 1, e200m5))
        {
         snap.note = "EMA buffers unavailable";
         return false;
        }

      if(!Copy1(m_hAtr_m5, 0, 1, snap.atr14) || !Copy1(m_hAdx_m5, 0, 1, snap.adx14))
        {
         snap.note = "ATR/ADX unavailable";
         return false;
        }

      snap.ema20 = e20m5;
      snap.ema50 = e50m5;
      snap.ema200 = e200m5;
      snap.h1_bias = BiasFromEma(c_h1, e20h1, e50h1, e200h1);
      snap.m15_structure = BiasFromEma(c_m15, e20m15, e50m15, e200m15);
      snap.m5_trigger = BiasFromEma(c_m5, e20m5, e50m5, e200m5);

      snap.h1_m15_aligned = (snap.h1_bias == snap.m15_structure &&
                             (snap.h1_bias == "BULLISH" || snap.h1_bias == "BEARISH"));

      if(snap.h1_m15_aligned)
        {
         snap.allowed_direction = (snap.h1_bias == "BULLISH" ? "BUY" : "SELL");
         snap.ema_stack_ok = (snap.m5_trigger == snap.h1_bias);
        }
      else
        {
         snap.allowed_direction = "NONE";
         snap.ema_stack_ok = false;
        }

      // Setup age: count completed M5 bars since alignment first appeared
      if(snap.h1_m15_aligned && snap.adx14 >= m_min_adx && snap.ema_stack_ok)
        {
         if(m_setup_bar_time == 0 || m_setup_dir != snap.allowed_direction)
           {
            m_setup_bar_time = t_m5;
            m_setup_dir = snap.allowed_direction;
           }
         int age = iBarShift(m_symbol, PERIOD_M5, m_setup_bar_time, true);
         // age at closed bar index: shift of setup bar minus 1 (current closed is shift 1)
         if(age < 0)
            snap.setup_age_m5 = 0;
         else
            snap.setup_age_m5 = MathMax(0, age - 1);
         if(snap.setup_age_m5 > m_max_setup_age)
            snap.note = "Setup aged out (>3 M5)";
        }
      else
        {
         m_setup_bar_time = 0;
         m_setup_dir = "";
         snap.setup_age_m5 = 0;
        }

      EvalRiskSetup(snap.allowed_direction, snap.atr14, c_m5, spec, snap);
      EvalNewsWindow(snap);

      snap.valid = true;
      if(snap.note == "")
        {
         if(!snap.h1_m15_aligned)
            snap.note = "Await H1+M15 alignment";
         else if(snap.adx14 < m_min_adx)
            snap.note = "ADX below minimum";
         else if(!snap.ema_stack_ok)
            snap.note = "M5 EMA stack disagrees";
         else if(snap.news_available && snap.news_blocked)
            snap.note = "High-impact news window";
         else
            snap.note = "Desk setup OK (advisory)";
        }
      return true;
     }

   string ToJson(const VantageM5DeskSnap &snap) const
     {
      string j = "{";
      j += "\"desk\":\"m5_alignment\",";
      j += "\"valid\":" + (snap.valid ? "true" : "false") + ",";
      j += "\"h1_bias\":\"" + JsonEscape(snap.h1_bias) + "\",";
      j += "\"m15_structure\":\"" + JsonEscape(snap.m15_structure) + "\",";
      j += "\"m5_trigger\":\"" + JsonEscape(snap.m5_trigger) + "\",";
      j += "\"h1_m15_aligned\":" + (snap.h1_m15_aligned ? "true" : "false") + ",";
      j += "\"adx14\":" + DoubleToJson(snap.adx14, 4) + ",";
      j += "\"atr14\":" + DoubleToJson(snap.atr14, 8) + ",";
      j += "\"ema20\":" + DoubleToJson(snap.ema20, 8) + ",";
      j += "\"ema50\":" + DoubleToJson(snap.ema50, 8) + ",";
      j += "\"ema200\":" + DoubleToJson(snap.ema200, 8) + ",";
      j += "\"ema_stack_ok\":" + (snap.ema_stack_ok ? "true" : "false") + ",";
      j += "\"m5_closed_confirmed\":" + (snap.m5_closed_confirmed ? "true" : "false") + ",";
      j += "\"setup_age_m5\":" + IntegerToString(snap.setup_age_m5) + ",";
      j += "\"reward_risk_ratio\":" + DoubleToJson(snap.reward_risk_ratio, 4) + ",";
      j += "\"planned_equity_risk_pct\":" + DoubleToJson(snap.planned_equity_risk_pct, 4) + ",";
      j += "\"max_spread_points\":" + IntegerToString(snap.max_spread_points) + ",";
      j += "\"allowed_direction\":\"" + JsonEscape(snap.allowed_direction) + "\",";
      j += "\"news_available\":" + (snap.news_available ? "true" : "false") + ",";
      if(snap.news_available)
        {
         j += "\"news_blocked\":" + (snap.news_blocked ? "true" : "false") + ",";
         j += "\"minutes_to_high_impact\":" + IntegerToString(snap.minutes_to_high_impact) + ",";
        }
      j += "\"note\":\"" + JsonEscape(snap.note) + "\"";
      j += "}";
      return j;
     }
  };

#endif // VANTAGE_M5_DESK_MQH
