//+------------------------------------------------------------------+
//| VantageBoxTheoryTypes.mqh — Box Theory strategy types (Gold)     |
//+------------------------------------------------------------------+
#ifndef VANTAGE_BOX_THEORY_TYPES_MQH
#define VANTAGE_BOX_THEORY_TYPES_MQH

#define VANTAGE_BOXTHEORY_VERSION "1.0"
#define VANTAGE_BOXTHEORY_DISABLE_MSG \
  "Box Theory Strategy is disabled. This module supports XAUUSD/Gold only."

enum ENUM_BOX_SIGNAL
  {
   BOX_SIG_WAIT = 0,
   BOX_SIG_WATCH,
   BOX_SIG_BUY,
   BOX_SIG_SELL,
   BOX_SIG_INVALID
  };

enum ENUM_BOX_STATUS
  {
   BOX_ST_FORMING = 0,
   BOX_ST_VALID,
   BOX_ST_BREAKOUT_UP,
   BOX_ST_BREAKOUT_DOWN,
   BOX_ST_RETESTING,
   BOX_ST_CONFIRMED_BULL,
   BOX_ST_CONFIRMED_BEAR,
   BOX_ST_BULL_TRAP,
   BOX_ST_BEAR_TRAP,
   BOX_ST_INVALIDATED,
   BOX_ST_EXPIRED
  };

struct VantageBoxTheoryConfig
  {
   bool   enable;
   bool   gold_only;
   string gold_aliases;
   bool   allow_suffix;
   bool   allow_prefix;
   ENUM_TIMEFRAMES tf_structure;
   ENUM_TIMEFRAMES tf_box;
   ENUM_TIMEFRAMES tf_entry;
   int    lookback_candles;
   int    min_box_candles;
   int    min_touches;
   double touch_tolerance_atr;
   double max_box_height_atr;
   double min_box_height_atr;
   double min_inside_ratio;
   double breakout_buffer_atr;
   double min_breakout_body_ratio;
   double retest_tolerance_atr;
   int    max_retest_candles;
   int    confirmation_candles;
   bool   require_retest;
   string entry_mode;
   int    max_box_age_candles;
   bool   liquidity_sweep_detection;
   bool   fvg_confirmation;
   bool   htf_confirmation;
   double minimum_signal_score;
   bool   block_countertrend;
   double countertrend_penalty;
   string sl_mode;
   double sl_buffer_atr;
   double tp_mult1;
   double tp_mult2;
   double tp_mult3;
   double max_spread_pts;
   bool   show_chart_objects;
   bool   show_dashboard;
   bool   debug_log;
  };

struct VantageBoxTheoryResult
  {
   bool   valid;
   bool   gold_symbol_valid;
   bool   engine_enabled;
   bool   analysis_active;
   string symbol;
   string base_symbol;
   string disable_reason;
   string strategy;
   string direction;
   string signal;
   string box_status;
   string signal_quality;
   double confidence_score;
   string htf_bias;
   double current_price;
   bool   box_found;
   double box_high;
   double box_low;
   double box_mid;
   double box_height;
   int    upper_touches;
   int    lower_touches;
   int    box_age;
   datetime box_start_time;
   datetime box_end_time;
   bool   breakout_detected;
   string breakout_direction;
   double breakout_price;
   datetime breakout_time;
   bool   retest_detected;
   bool   retest_confirmed;
   double retest_price;
   bool   sweep_detected;
   string sweep_direction;
   double sweep_price;
   bool   fvg_confirmation;
   double entry;
   double stop_loss;
   double tp1;
   double tp2;
   double tp3;
   double risk_reward;
   string events;
   string reasons;
   string signal_id;
   datetime eval_bar_time;
   string technical_narrative;
   string action_guidance;
   string status_line;
  };

#endif
