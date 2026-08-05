//+------------------------------------------------------------------+
//| VantageAmdIfvgTypes.mqh — AMD + iFVG strategy types (Gold only)  |
//+------------------------------------------------------------------+
#ifndef VANTAGE_AMD_IFVG_TYPES_MQH
#define VANTAGE_AMD_IFVG_TYPES_MQH

#define VANTAGE_AMDIFVG_VERSION "1.0"
#define VANTAGE_AMDIFVG_DISABLE_MSG \
  "AMD + iFVG Strategy is disabled. This module supports XAUUSD/Gold only."

enum ENUM_AMDIFVG_DECISION
  {
   AMDIFVG_DEC_NO_TRADE = 0,
   AMDIFVG_DEC_WAIT,
   AMDIFVG_DEC_BUY,
   AMDIFVG_DEC_SELL
  };

enum ENUM_AMDIFVG_SETUP_STATE
  {
   AMDIFVG_ST_SEARCH = 0,
   AMDIFVG_ST_ACCUMULATION,
   AMDIFVG_ST_WAIT_SWEEP,
   AMDIFVG_ST_MANIPULATION,
   AMDIFVG_ST_WAIT_DISP,
   AMDIFVG_ST_WAIT_MSS,
   AMDIFVG_ST_WAIT_IFVG,
   AMDIFVG_ST_WAIT_RETRACE,
   AMDIFVG_ST_ENTRY_ZONE,
   AMDIFVG_ST_INVALIDATED,
   AMDIFVG_ST_EXPIRED
  };

enum ENUM_AMDIFVG_PHASE
  {
   AMDIFVG_PH_SEARCH = 0,
   AMDIFVG_PH_ACCUMULATION,
   AMDIFVG_PH_MANIPULATION,
   AMDIFVG_PH_DISTRIBUTION
  };

struct VantageAmdIfvgConfig
  {
   bool   enable;
   bool   gold_only;
   string gold_aliases;
   bool   allow_suffix;
   bool   allow_prefix;
   ENUM_TIMEFRAMES tf_macro;
   ENUM_TIMEFRAMES tf_bias;
   ENUM_TIMEFRAMES tf_setup;
   ENUM_TIMEFRAMES tf_entry;
   int    pivot_left;
   int    pivot_right;
   int    acc_min_candles;
   int    acc_max_candles;
   double acc_max_width_atr;
   int    acc_min_touches;
   double sweep_min_atr;
   double sweep_max_atr;
   bool   sweep_require_reentry;
   double disp_min_body_atr;
   double fvg_min_gap_atr;
   double ifvg_min_break_atr;
   bool   ifvg_require_body_close;
   int    ifvg_max_retests;
   bool   ifvg_use_midpoint;
   double min_rr;
   double min_trade_score;
   double risk_percent;
   double max_spread_pts;
   string entry_mode;
   double chase_max_atr;
   bool   show_chart_objects;
   bool   show_dashboard;
   bool   show_hlines;
   bool   debug_log;
  };

struct VantageAmdIfvgResult
  {
   bool   valid;
   bool   gold_symbol_valid;
   bool   engine_enabled;
   bool   analysis_active;
   string symbol;
   string base_symbol;
   string disable_reason;
   string decision;
   string setup_state;
   string amd_phase;
   string htf_bias;
   double confidence;
   bool   acc_detected;
   double acc_high;
   double acc_low;
   double acc_quality;
   bool   manip_detected;
   string manip_direction;
   double manip_sweep_price;
   double manip_quality;
   bool   mss_detected;
   string mss_direction;
   double mss_level;
   bool   ifvg_detected;
   string ifvg_direction;
   string ifvg_orig_direction;
   double ifvg_lower;
   double ifvg_upper;
   double ifvg_mid;
   int    ifvg_retests;
   double entry_low;
   double entry_high;
   double preferred_entry;
   double stop_loss;
   double tp1;
   double tp2;
   double invalidation;
   string recommendation;
   string technical_narrative;
   string action_guidance;
   string status_line;
   string reasoning;
   string warnings;
   datetime eval_bar_m5;
   int    engine_phase;
   bool   chart_objects_active;
  };

#endif
