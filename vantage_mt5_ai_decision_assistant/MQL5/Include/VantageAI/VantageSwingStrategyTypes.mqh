//+------------------------------------------------------------------+
//| VantageSwingStrategyTypes.mqh                                    |
//| Swing Strategy Engine — shared types (XAUUSD / Gold only)        |
//| Advisory-only — never opens, modifies, or closes trades          |
//+------------------------------------------------------------------+
#ifndef VANTAGE_SWING_STRATEGY_TYPES_MQH
#define VANTAGE_SWING_STRATEGY_TYPES_MQH

#define VANTAGE_SWING_STRAT_VERSION "1.0"
#define VANTAGE_SWING_STRAT_DISABLE_MSG \
  "Swing Strategy Engine is disabled. This module supports XAUUSD/Gold only."
#define SWING_STRAT_MAX_SWINGS 48

enum ENUM_SWING_STRAT_TREND
  {
   SWING_TREND_STRONG_BULL = 0,
   SWING_TREND_BULLISH,
   SWING_TREND_WEAK_BULL,
   SWING_TREND_SIDEWAYS,
   SWING_TREND_WEAK_BEAR,
   SWING_TREND_BEARISH,
   SWING_TREND_STRONG_BEAR
  };

enum ENUM_SWING_STRAT_PHASE
  {
   SWING_PHASE_UNKNOWN = 0,
   SWING_PHASE_IMPULSE,
   SWING_PHASE_PULLBACK,
   SWING_PHASE_CONTINUATION,
   SWING_PHASE_EXPANSION,
   SWING_PHASE_COMPRESSION,
   SWING_PHASE_RANGE
  };

enum ENUM_SWING_STRAT_TRADE_MODE
  {
   SWING_TRADE_SWING = 0,   // Multi-TF swing — STRONG SWING signals
   SWING_TRADE_SCALPING = 1  // M5/M15 fast profile — SCALP BUY/SELL
  };

enum ENUM_SWING_STRAT_SIGNAL
  {
   SWING_SIG_NO_TRADE = 0,
   SWING_SIG_WAIT,
   SWING_SIG_SWING_BUY,
   SWING_SIG_STRONG_SWING_BUY,
   SWING_SIG_SWING_SELL,
   SWING_SIG_STRONG_SWING_SELL,
   SWING_SIG_SCALP_BUY,
   SWING_SIG_SCALP_SELL
  };

enum ENUM_SWING_STRAT_ENTRY_QUALITY
  {
   SWING_EQ_AVOID = 0,
   SWING_EQ_WEAK,
   SWING_EQ_AVERAGE,
   SWING_EQ_GOOD,
   SWING_EQ_EXCELLENT
  };

enum ENUM_SWING_STRAT_SWING_LABEL
  {
   SWING_LBL_UNKNOWN = 0,
   SWING_LBL_HH, SWING_LBL_HL, SWING_LBL_LH, SWING_LBL_LL
  };

struct VantageSwingStratSwing
  {
   double price;
   datetime time;
   int    bar_index;
   double atr;
   double strength;
   bool   is_high;
   ENUM_SWING_STRAT_SWING_LABEL label;
   bool   external;
  };

struct VantageSwingStratConfig
  {
   bool   enable;
   ENUM_SWING_STRAT_TRADE_MODE trade_mode;
   bool   gold_only;
   string approved_aliases;
   bool   allow_suffix;
   bool   allow_prefix;
   ENUM_TIMEFRAMES tf_d1;
   ENUM_TIMEFRAMES tf_h4;
   ENUM_TIMEFRAMES tf_h1;
   ENUM_TIMEFRAMES tf_m15;
   ENUM_TIMEFRAMES tf_m5;
   int    swing_left;
   int    swing_right;
   double min_swing_atr;
   int    min_swing_candles;
   int    atr_period;
   double atr_multiplier;
   double max_pullback_pct;
   double min_rr;
   double min_confidence;
   double rsi_bull;
   double rsi_bear;
   double macd_min_hist;
   double min_volume_ratio;
   double bos_min_atr;
   double min_body_pct;
   bool   show_chart;
   bool   show_hlines;
   bool   show_dashboard;
   bool   debug_log;
  };

struct VantageSwingStratResult
  {
   bool   valid;
   bool   gold_symbol_valid;
   bool   engine_enabled;
   bool   analysis_active;
   string symbol;
   string base_symbol;
   string trade_mode;
   string disable_reason;
   string status_line;
   // Structure
   string market_structure;
   string internal_structure;
   string external_structure;
   string structure_regime;
   double trend_strength;
   // Trend
   string trend;
   ENUM_SWING_STRAT_TREND trend_class;
   double trend_score;
   // Swing
   string swing_direction;
   double current_swing_price;
   double previous_swing_price;
   datetime current_swing_time;
   datetime previous_swing_time;
   string current_phase;
   ENUM_SWING_STRAT_PHASE phase;
   // Scores
   double swing_score;
   double momentum_score;
   double smc_score;
   double liquidity_score;
   double breakout_score;
   double confidence;
   // SMC flags
   bool   bos_detected;
   bool   choch_detected;
   bool   liquidity_grab;
   bool   equal_high;
   bool   equal_low;
   bool   order_block;
   bool   fvg;
   bool   in_premium;
   bool   in_discount;
   string smc_summary;
   // Pullback
   double pullback_pct;
   string pullback_quality;
   bool   pullback_healthy;
   // Momentum
   double rsi_h1;
   double macd_hist_m15;
   double atr_h4;
   double atr_expansion;
   string momentum_summary;
   // Breakout
   bool   breakout_valid;
   string breakout_summary;
   // Entry
   ENUM_SWING_STRAT_ENTRY_QUALITY entry_quality;
   string entry_quality_label;
   string entry_explanation;
   // Risk
   double entry_zone_lo;
   double entry_zone_hi;
   double stop_loss;
   double invalidation;
   double tp1;
   double tp2;
   double tp3;
   double risk_reward;
   string risk_reward_label;
   double max_risk_zone;
   string max_risk_zone_label;
   // Decision
   ENUM_SWING_STRAT_SIGNAL signal_class;
   string signal;
   string reason;
   string market_explanation;
   string trade_bias;
   datetime eval_bar_m5;
   bool   chart_objects_active;
   int    engine_phase;
  };

string SwingStratTrendToString(const ENUM_SWING_STRAT_TREND t)
  {
   if(t == SWING_TREND_STRONG_BULL) return "Strong Bullish";
   if(t == SWING_TREND_BULLISH) return "Bullish";
   if(t == SWING_TREND_WEAK_BULL) return "Weak Bullish";
   if(t == SWING_TREND_SIDEWAYS) return "Sideways";
   if(t == SWING_TREND_WEAK_BEAR) return "Weak Bearish";
   if(t == SWING_TREND_BEARISH) return "Bearish";
   if(t == SWING_TREND_STRONG_BEAR) return "Strong Bearish";
   return "Sideways";
  }

string SwingStratTradeModeToString(const ENUM_SWING_STRAT_TRADE_MODE m)
  {
   if(m == SWING_TRADE_SCALPING) return "SCALPING";
   return "SWING";
  }

string SwingStratSignalToString(const ENUM_SWING_STRAT_SIGNAL s)
  {
   if(s == SWING_SIG_STRONG_SWING_BUY) return "STRONG SWING BUY";
   if(s == SWING_SIG_SWING_BUY) return "SWING BUY";
   if(s == SWING_SIG_STRONG_SWING_SELL) return "STRONG SWING SELL";
   if(s == SWING_SIG_SWING_SELL) return "SWING SELL";
   if(s == SWING_SIG_SCALP_BUY) return "SCALP BUY";
   if(s == SWING_SIG_SCALP_SELL) return "SCALP SELL";
   if(s == SWING_SIG_WAIT) return "WAIT";
   return "NO TRADE";
  }

string SwingStratEntryQualityToString(const ENUM_SWING_STRAT_ENTRY_QUALITY q)
  {
   if(q == SWING_EQ_EXCELLENT) return "Excellent";
   if(q == SWING_EQ_GOOD) return "Good";
   if(q == SWING_EQ_AVERAGE) return "Average";
   if(q == SWING_EQ_WEAK) return "Weak";
   return "Avoid";
  }

string SwingStratPhaseToString(const ENUM_SWING_STRAT_PHASE p)
  {
   if(p == SWING_PHASE_IMPULSE) return "Impulse";
   if(p == SWING_PHASE_PULLBACK) return "Pullback";
   if(p == SWING_PHASE_CONTINUATION) return "Continuation";
   if(p == SWING_PHASE_EXPANSION) return "Expansion";
   if(p == SWING_PHASE_COMPRESSION) return "Compression";
   if(p == SWING_PHASE_RANGE) return "Range";
   return "Unknown";
  }

string SwingStratLabelToString(const ENUM_SWING_STRAT_SWING_LABEL l)
  {
   if(l == SWING_LBL_HH) return "HH";
   if(l == SWING_LBL_HL) return "HL";
   if(l == SWING_LBL_LH) return "LH";
   if(l == SWING_LBL_LL) return "LL";
   return "—";
  }

#endif
