//+------------------------------------------------------------------+
//| VantageExecutionTypes.mqh                                        |
//| Shared types for Vantage Swing Executor (demo default, live opt-in)|
//+------------------------------------------------------------------+
#ifndef VANTAGE_EXECUTION_TYPES_MQH
#define VANTAGE_EXECUTION_TYPES_MQH

#define VANTAGE_EXEC_VERSION "1.1.0"

enum ENUM_EXEC_TRADE_MODE
  {
   EXEC_MODE_SWING = 0,    // STRONG SWING BUY/SELL
   EXEC_MODE_SCALPING = 1  // SCALP BUY/SELL
  };

enum ENUM_EXEC_TP_LEVEL
  {
   EXEC_TP1 = 0,
   EXEC_TP2 = 1,
   EXEC_TP3 = 2
  };

struct VantageExecOrderSpec
  {
   string signal_id;
   string symbol;
   string side;
   string order_type;
   double stop_loss;
   double take_profit;
   double confidence;
   long   eval_bar_m5;
   int    expires_in_sec;
   bool   valid;
  };

struct VantageExecAckResult
  {
   bool   ok;
   string signal_id;
   string status;
   ulong  ticket;
   string reason;
   string account_mode;
   int    http_code;
   string error;
  };

#endif
