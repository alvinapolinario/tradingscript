//+------------------------------------------------------------------+
//| VantageTypes.mqh                                                 |
//| Shared types for Vantage MT5 AI Decision Assistant               |
//| ADVISORY-ONLY — no trade execution                               |
//+------------------------------------------------------------------+
#ifndef VANTAGE_TYPES_MQH
#define VANTAGE_TYPES_MQH

#define VANTAGE_AI_VERSION "1.2.0"
#define VANTAGE_MAX_POSITIONS 64
#define VANTAGE_MAX_PENDING   64
#define VANTAGE_MAX_CANDLES   300

//--- Advisory actions (must match backend enum)
enum ENUM_VANTAGE_ACTION
  {
   VACT_HOLD = 0,
   VACT_HOLD_WITH_CAUTION,
   VACT_PROTECT_PROFIT,
   VACT_EXIT_WARNING,
   VACT_WAIT_FOR_RETEST,
   VACT_BUY_WATCH,
   VACT_SELL_WATCH,
   VACT_NO_TRADE,
   VACT_HIGH_SPREAD,
   VACT_DATA_UNAVAILABLE,
   VACT_BACKEND_OFFLINE,
   VACT_RISK_CALCULATION_UNAVAILABLE,
   VACT_CRITICAL_RISK,
   VACT_NO_NEW_TRADE
  };

enum ENUM_VANTAGE_TREND
  {
   VTREND_BULLISH = 0,
   VTREND_BEARISH,
   VTREND_NEUTRAL
  };

enum ENUM_VANTAGE_CANDLE_STATUS
  {
   VCANDLE_WAITING = 0,
   VCANDLE_CLOSED_READY,
   VCANDLE_INCOMPLETE_HISTORY,
   VCANDLE_CLOSED_MARKET
  };

struct VantageAccountInfo
  {
   string company;
   string server;
   string currency;
   long   login;
   string login_masked;
   long   margin_mode;       // ACCOUNT_MARGIN_MODE
   bool   trade_allowed_acct;
   bool   terminal_connected;
   bool   terminal_trade_allowed;
   bool   mql_trade_allowed;
   bool   looks_like_vantage;
   string vantage_warning;
   bool   is_hedging;
   double balance;
   double equity;
   double margin;
   double free_margin;
  };

struct VantageSymbolSpec
  {
   string symbol;
   int    digits;
   double point;
   double tick_size;
   double tick_value;
   double tick_value_profit;
   double tick_value_loss;
   double contract_size;
   double volume_min;
   double volume_max;
   double volume_step;
   int    stops_level;
   int    freeze_level;
   int    spread_points;
   bool   spread_float;
   int    trade_mode;
   int    trade_execution;
   int    filling_mode;
   int    expiration_mode;
   bool   valid;
   string error;
  };

struct VantagePriceSnap
  {
   double   bid;
   double   ask;
   double   last;
   double   mid;
   double   spread_price;
   int      spread_points;
   datetime server_time;
   datetime local_time;
   datetime utc_time;
   bool     high_spread;
  };

struct VantagePositionRow
  {
   ulong    ticket;
   long     type;          // POSITION_TYPE_BUY / SELL
   double   volume;
   double   price_open;
   double   price_current;
   double   sl;
   double   tp;
   double   profit;
   double   swap;
   datetime time_open;
   string   comment;
   long     magic;
  };

struct VantagePositionSummary
  {
   int                count;
   VantagePositionRow rows[VANTAGE_MAX_POSITIONS];
   double             total_buy_volume;
   double             total_sell_volume;
   double             weighted_avg_entry;
   double             total_floating_pl;
   double             total_swap;
   bool               has_position;
  };

struct VantagePendingOrderRow
  {
   ulong    ticket;
   string   symbol;
   int      digits;
   long     type;             // ORDER_TYPE_* pending
   double   volume;
   double   price_open;
   double   price_current;
   double   bid;
   double   ask;
   double   sl;
   double   tp;
   datetime time_setup;
   string   comment;
   long     magic;
   double   distance_price;
   double   distance_points;
   bool     risk_available;
   string   risk_status;
   double   money_at_risk;
   double   equity_risk_pct;
   double   reward_risk_ratio;
   double   margin_required;
  };

struct VantagePendingOrderSummary
  {
   int                     count;
   VantagePendingOrderRow rows[VANTAGE_MAX_PENDING];
  };

struct VantageRiskEstimate
  {
   bool     available;
   string   status;            // OK | RISK_CALCULATION_UNAVAILABLE
   int      last_error;
   double   stop_distance_price;
   double   stop_distance_points;
   double   money_at_risk;
   double   equity_risk_pct;
   double   reward_to_target;
   double   reward_risk_ratio;
   double   margin_required;
   double   entry;
   double   sl;
   double   tp;
   double   volume;
  };

struct VantageTechnicalSnap
  {
   double ema20;
   double ema50;
   double ema200;
   double bb_upper;
   double bb_middle;
   double bb_lower;
   double rsi14;
   double atr14;
   double volume;
   double volume_sma;
   bool   oversized_candle;
   bool   support_break;
   bool   retest_pending;
   bool   bear_reject;
   bool   bull_reject;
   string nearest_support;
   string nearest_resistance;
   double nearest_support_price;
   double nearest_resistance_price;
   ENUM_VANTAGE_TREND trend;
   string structure_note;
   datetime candle_time;
   double  close;
   double  open;
   double  high;
   double  low;
   double  bullish_pct;          // % bullish closed candles in lookback
   double  bearish_pct;          // % bearish closed candles in lookback
   double  neutral_pct;          // % doji / flat candles in lookback
   int     bias_lookback;        // bars used for % calculation
   double  indicator_bullish_pct; // % of trend votes bullish (0-100)
   double  indicator_bearish_pct; // % of trend votes bearish (0-100)
  };

struct VantageBackendReply
  {
   bool   ok;
   string action;
   string rationale;
   string trend;
   string environment;
   string market_state;
   string new_entry_decision;
   string existing_position_decision;
   string risk_status;
   string immediate_support;
   string recovery_level_1;
   string recovery_level_2;
   string bullish_confirmation;
   string technical_invalidation;
   string risk_warning;
   bool   new_position_allowed;
   bool   add_position_allowed;
   bool   exceeds_max_position_risk;
   string nearest_support;
   string nearest_resistance;
   string timestamp_utc;
   int    http_code;
   string error;
   datetime received_local;
   int    age_seconds;
   bool   stale;
   double estimated_money_risk;
   double equity_risk_pct;
   double entry;
   double sl;
  };

string VantageActionToString(const ENUM_VANTAGE_ACTION a)
  {
   switch(a)
     {
      case VACT_HOLD: return "HOLD";
      case VACT_HOLD_WITH_CAUTION: return "HOLD_WITH_CAUTION";
      case VACT_PROTECT_PROFIT: return "PROTECT_PROFIT";
      case VACT_EXIT_WARNING: return "EXIT_WARNING";
      case VACT_WAIT_FOR_RETEST: return "WAIT_FOR_RETEST";
      case VACT_BUY_WATCH: return "BUY_WATCH";
      case VACT_SELL_WATCH: return "SELL_WATCH";
      case VACT_NO_TRADE: return "NO_TRADE";
      case VACT_HIGH_SPREAD: return "HIGH_SPREAD";
      case VACT_DATA_UNAVAILABLE: return "DATA_UNAVAILABLE";
      case VACT_BACKEND_OFFLINE: return "BACKEND_OFFLINE";
      case VACT_RISK_CALCULATION_UNAVAILABLE: return "RISK_CALCULATION_UNAVAILABLE";
      case VACT_CRITICAL_RISK: return "CRITICAL_RISK";
      case VACT_NO_NEW_TRADE: return "NO_NEW_TRADE";
     }
   return "NO_NEW_TRADE";
  }

ENUM_VANTAGE_ACTION VantageActionFromString(const string s)
  {
   if(s == "HOLD") return VACT_HOLD;
   if(s == "HOLD_WITH_CAUTION") return VACT_HOLD_WITH_CAUTION;
   if(s == "PROTECT_PROFIT") return VACT_PROTECT_PROFIT;
   if(s == "EXIT_WARNING") return VACT_EXIT_WARNING;
   if(s == "WAIT_FOR_RETEST") return VACT_WAIT_FOR_RETEST;
   if(s == "BUY_WATCH") return VACT_BUY_WATCH;
   if(s == "SELL_WATCH") return VACT_SELL_WATCH;
   if(s == "NO_TRADE") return VACT_NO_TRADE;
   if(s == "HIGH_SPREAD") return VACT_HIGH_SPREAD;
   if(s == "DATA_UNAVAILABLE") return VACT_DATA_UNAVAILABLE;
   if(s == "BACKEND_OFFLINE") return VACT_BACKEND_OFFLINE;
   if(s == "RISK_CALCULATION_UNAVAILABLE") return VACT_RISK_CALCULATION_UNAVAILABLE;
   if(s == "CRITICAL_RISK") return VACT_CRITICAL_RISK;
   if(s == "NO_NEW_TRADE") return VACT_NO_NEW_TRADE;
   return VACT_NO_NEW_TRADE;
  }

string MaskAccountLogin(const long login)
  {
   string raw = IntegerToString(login);
   int n = StringLen(raw);
   if(n <= 4)
      return "****";
   string masked = "";
   for(int i = 0; i < n - 4; i++)
      masked += "*";
   masked += StringSubstr(raw, n - 4, 4);
   return masked;
  }

string JsonEscape(const string s)
  {
   string o = s;
   StringReplace(o, "\\", "\\\\");
   StringReplace(o, "\"", "\\\"");
   StringReplace(o, "\n", "\\n");
   StringReplace(o, "\r", "\\r");
   StringReplace(o, "\t", "\\t");
   return o;
  }

string DoubleToJson(const double v, const int digits = 8)
  {
   if(!MathIsValidNumber(v))
      return "null";
   return DoubleToString(v, digits);
  }

#endif
//+------------------------------------------------------------------+
