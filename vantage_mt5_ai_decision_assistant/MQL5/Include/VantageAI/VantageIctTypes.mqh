//+------------------------------------------------------------------+
//| VantageIctTypes.mqh — ICT strategy types (Gold / XAUUSD)         |
//+------------------------------------------------------------------+
#ifndef VANTAGE_ICT_TYPES_MQH
#define VANTAGE_ICT_TYPES_MQH

#define VANTAGE_ICT_VERSION "1.0"
#define VANTAGE_ICT_DISABLE_MSG \
  "ICT Strategy Engine supports XAUUSD/Gold only."

enum ENUM_ICT_DECISION
  {
   ICT_DEC_NO_TRADE = 0,
   ICT_DEC_WAIT,
   ICT_DEC_BUY,
   ICT_DEC_SELL
  };

enum ENUM_ICT_SETUP_STATE
  {
   ICT_ST_WAIT_LIQ = 0,
   ICT_ST_LIQ_ID,
   ICT_ST_LIQ_SWEPT,
   ICT_ST_WAIT_DISP,
   ICT_ST_DISP_OK,
   ICT_ST_WAIT_MSS,
   ICT_ST_MSS_OK,
   ICT_ST_WAIT_RETRACE,
   ICT_ST_ENTRY_ZONE,
   ICT_ST_TRIGGERED,
   ICT_ST_INVALIDATED,
   ICT_ST_EXPIRED
  };

struct VantageIctConfig
  {
   bool   enable;
   bool   gold_only;
   string gold_aliases;
   bool   allow_suffix;
   bool   allow_prefix;
   ENUM_TIMEFRAMES tf_bias;
   ENUM_TIMEFRAMES tf_setup;
   ENUM_TIMEFRAMES tf_entry;
   int    lookback_bars;
   int    pivot_left;
   int    pivot_right;
   double sweep_min_atr;
   double sweep_max_atr;
   double disp_min_body_atr;
   double fvg_min_gap_atr;
   double min_confidence;
   double minimum_rr;
   double max_spread_pts;
   bool   show_chart_objects;
   bool   show_dashboard;
   bool   debug_log;
  };

struct VantageIctResult
  {
   bool   valid;
   bool   gold_symbol_valid;
   bool   engine_enabled;
   bool   analysis_active;
   string symbol;
   string base_symbol;
   string disable_reason;
   string strategy;
   string decision;
   string direction;
   string setup_state;
   string status;
   string signal_quality;
   double confidence;
   double confidence_score;
   string htf_bias_dir;
   double htf_bias_conf;
   string htf_evidence;
   int    bsl_count;
   int    ssl_count;
   bool   sweep_detected;
   string sweep_type;
   double sweep_level;
   double sweep_price;
   double sweep_quality;
   datetime sweep_time;
   bool   displacement;
   double displacement_score;
   string mss_dir;
   bool   fvg_detected;
   string fvg_dir;
   double fvg_high;
   double fvg_low;
   double fvg_mid;
   double entry_low;
   double entry_high;
   double entry_mid;
   string entry_status;
   double stop_loss;
   string sl_reason;
   double tp1;
   double tp2;
   double risk_reward;
   string premium_discount;
   string session_name;
   string setup_id;
   string reasons;
   string invalidations;
   string timeline;
   string technical_narrative;
   string action_guidance;
   datetime eval_bar_time;
   bool   state_changed;
  };

#endif
