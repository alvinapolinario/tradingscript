//+------------------------------------------------------------------+
//| VantageMarketStateTypes.mqh                                      |
//| Institutional Market State Engine v2 — shared types (Gold only)  |
//| Advisory-only — never opens, modifies, or closes trades          |
//+------------------------------------------------------------------+
#ifndef VANTAGE_MARKET_STATE_TYPES_MQH
#define VANTAGE_MARKET_STATE_TYPES_MQH

#define VANTAGE_MSE_VERSION "2.0"
#define VANTAGE_MSE_DISABLE_MSG \
  "Market State Engine v2 is disabled. This module supports XAUUSD/Gold only."
#define MSE_MAX_SWINGS 48
#define MSE_MAX_TIMELINE 24
#define MSE_MAX_EVENTS 32

// Generic lifecycle (dashboard never shows "None" — use WAITING)
enum ENUM_MSE_LIFECYCLE
  {
   MSE_LC_WAITING = 0,
   MSE_LC_POTENTIAL,
   MSE_LC_CONFIRMED,
   MSE_LC_RETESTING,
   MSE_LC_CONTINUATION,
   MSE_LC_APPROACHING,
   MSE_LC_FAILED,
   MSE_LC_INVALIDATED,
   MSE_LC_EXPIRED,
   MSE_LC_BUILDING,
   MSE_LC_VALID,
   MSE_LC_BROKEN,
   MSE_LC_WAITING_RETEST,
   MSE_LC_CONFIRMED_FLIP
  };

enum ENUM_MSE_CONTEXT
  {
   MSE_CTX_UNKNOWN = 0,
   MSE_CTX_TRENDING,
   MSE_CTX_RANGING,
   MSE_CTX_EXPANSION,
   MSE_CTX_COMPRESSION,
   MSE_CTX_ACCUMULATION,
   MSE_CTX_DISTRIBUTION
  };

enum ENUM_MSE_SWING_LABEL
  {
   MSE_SWING_UNKNOWN = 0,
   MSE_SWING_HH, MSE_SWING_HL, MSE_SWING_LH, MSE_SWING_LL
  };

enum ENUM_MSE_BOS_STATE
  {
   MSE_BOS_WAITING = 0,
   MSE_BOS_POTENTIAL,
   MSE_BOS_CONFIRMED,
   MSE_BOS_CONTINUATION,
   MSE_BOS_INVALIDATED
  };

enum ENUM_MSE_CHOCH_STATE
  {
   MSE_CHOCH_WAITING = 0,
   MSE_CHOCH_POTENTIAL,
   MSE_CHOCH_CONFIRMED,
   MSE_CHOCH_REVERSAL,
   MSE_CHOCH_INVALIDATED
  };

enum ENUM_MSE_TL_STATE
  {
   MSE_TL_BUILDING = 0,
   MSE_TL_VALID,
   MSE_TL_BROKEN,
   MSE_TL_RETESTING,
   MSE_TL_CONFIRMED_REVERSAL,
   MSE_TL_EXPIRED,
   MSE_TL_DEACTIVATED
  };

enum ENUM_MSE_BREAKOUT_KIND
  {
   MSE_BRK_HORIZONTAL = 0,
   MSE_BRK_TRENDLINE,
   MSE_BRK_CHANNEL,
   MSE_BRK_TRIANGLE,
   MSE_BRK_MA
  };

enum ENUM_MSE_FLIP_STATE
  {
   MSE_FLIP_WAITING = 0,
   MSE_FLIP_BROKEN,
   MSE_FLIP_WAITING_RETEST,
   MSE_FLIP_RETESTING,
   MSE_FLIP_CONFIRMED,
   MSE_FLIP_CONTINUATION,
   MSE_FLIP_FAILED
  };

enum ENUM_MSE_LIQ_STATE
  {
   MSE_LIQ_WAITING = 0,
   MSE_LIQ_POTENTIAL_SWEEP,
   MSE_LIQ_CONFIRMED_SWEEP,
   MSE_LIQ_CONTINUATION,
   MSE_LIQ_INVALIDATED
  };

struct VantageMseSwing
  {
   double price;
   datetime time;
   int    bar_index;
   double atr;
   double strength;
   double confidence;
   bool   is_high;
   ENUM_MSE_SWING_LABEL label;
  };

struct VantageMseBreakoutTrack
  {
   ENUM_MSE_BREAKOUT_KIND kind;
   ENUM_MSE_LIFECYCLE     lifecycle;
   string                 label;
   string                 reason;
   double                 level;
   datetime               event_time;
  };

struct VantageMseTimelineEntry
  {
   datetime time;
   string   event;
   string   detail;
  };

struct VantageMseConfig
  {
   bool   enable;
   bool   gold_only;
   string approved_aliases;
   bool   allow_suffix;
   bool   allow_prefix;
   ENUM_TIMEFRAMES tf_h4;
   ENUM_TIMEFRAMES tf_h1;
   ENUM_TIMEFRAMES tf_m15;
   ENUM_TIMEFRAMES tf_m5;
   ENUM_TIMEFRAMES tf_m1;
   int    swing_left;
   int    swing_right;
   double min_swing_atr;
   int    atr_period;
   double min_bos_atr;
   double min_body_pct;
   int    min_tl_touches;
   double tl_touch_atr;
   int    retest_max_bars;
   double retest_tol_atr;
   bool   show_chart;
   bool   show_hlines;
   bool   show_dashboard;
   bool   debug_log;
  };

struct VantageMseMlOutput
  {
   double trend_continuation_pct;
   double failed_breakout_pct;
   double deep_pullback_pct;
   double retest_success_pct;
   double liquidity_sweep_pct;
   double false_breakout_pct;
   string distribution_summary;
  };

struct VantageMseResult
  {
   bool   valid;
   bool   gold_symbol_valid;
   bool   engine_enabled;
   bool   analysis_active;
   string symbol;
   string base_symbol;
   string status_line;
   string disable_reason;
   string market_context;
   string context_reason;
   // Structure
   string structure_h4;
   string structure_h1;
   string structure_m15;
   ENUM_MSE_BOS_STATE bos_state;
   string bos_label;
   string bos_reason;
   ENUM_MSE_CHOCH_STATE choch_state;
   string choch_label;
   string choch_reason;
   // Trendline
   ENUM_MSE_TL_STATE tl_bull_state;
   ENUM_MSE_TL_STATE tl_bear_state;
   string tl_bull_label;
   string tl_bear_label;
   string tl_reason;
   double tl_strength;
   int    tl_touches;
   // Breakouts (lifecycle labels — never "None")
   string horizontal_breakout;
   string horizontal_reason;
   string trendline_breakout;
   string trendline_brk_reason;
   string channel_breakout;
   string ma_breakout;
   // Retest
   string retest_status;
   string retest_reason;
   // S/R flip
   string sbr_status;
   string sbr_reason;
   string rbs_status;
   string rbs_reason;
   // Liquidity
   string liquidity_status;
   string liquidity_reason;
   // ML
   VantageMseMlOutput ml;
   double institutional_probability;
   // Scoring (progressive)
   double confidence_score;
   string score_breakdown;
   string signal_lifecycle;
   string lifecycle_reason;
   // Timeline
   string timeline_json;
   // Narrative
   string what_happened;
   string what_is_happening;
   string what_is_next;
   string missing_confirmations;
   string recommendation;
   datetime eval_bar_m5;
   int    engine_phase;
   bool   chart_objects_active;
  };

string MseLifecycleToString(const ENUM_MSE_LIFECYCLE lc)
  {
   if(lc == MSE_LC_POTENTIAL) return "Potential";
   if(lc == MSE_LC_CONFIRMED) return "Confirmed";
   if(lc == MSE_LC_RETESTING) return "Retesting";
   if(lc == MSE_LC_CONTINUATION) return "Continuation";
   if(lc == MSE_LC_APPROACHING) return "Approaching";
   if(lc == MSE_LC_FAILED) return "Failed";
   if(lc == MSE_LC_INVALIDATED) return "Invalidated";
   if(lc == MSE_LC_EXPIRED) return "Expired";
   if(lc == MSE_LC_BUILDING) return "Building";
   if(lc == MSE_LC_VALID) return "Valid";
   if(lc == MSE_LC_BROKEN) return "Broken";
   if(lc == MSE_LC_WAITING_RETEST) return "Waiting Retest";
   if(lc == MSE_LC_CONFIRMED_FLIP) return "Confirmed Flip";
   return "Waiting";
  }

string MseContextToString(const ENUM_MSE_CONTEXT c)
  {
   if(c == MSE_CTX_TRENDING) return "Trending";
   if(c == MSE_CTX_RANGING) return "Ranging";
   if(c == MSE_CTX_EXPANSION) return "Expansion";
   if(c == MSE_CTX_COMPRESSION) return "Compression";
   if(c == MSE_CTX_ACCUMULATION) return "Accumulation";
   if(c == MSE_CTX_DISTRIBUTION) return "Distribution";
   return "Unknown";
  }

string MseSwingLabelToString(const ENUM_MSE_SWING_LABEL l)
  {
   if(l == MSE_SWING_HH) return "HH";
   if(l == MSE_SWING_HL) return "HL";
   if(l == MSE_SWING_LH) return "LH";
   if(l == MSE_SWING_LL) return "LL";
   return "—";
  }

#endif
