//+------------------------------------------------------------------+
//| VantageNotify.mqh                                                |
//| Optional push notifications — state-change + cooldown only       |
//+------------------------------------------------------------------+
#ifndef VANTAGE_NOTIFY_MQH
#define VANTAGE_NOTIFY_MQH

#include "VantageTypes.mqh"

class CVantageNotify
  {
private:
   bool     m_enabled;
   int      m_cooldown_sec;
   string   m_last_action;
   datetime m_last_sent;
   datetime m_last_candle;

   bool IsNotifiable(const string action)
     {
      return(action == "BUY_WATCH" ||
             action == "SELL_WATCH" ||
             action == "BUY_ALLOWED" ||
             action == "SELL_ALLOWED" ||
             action == "HOLD_WITH_CAUTION" ||
             action == "EXIT_WARNING" ||
             action == "CRITICAL_RISK" ||
             action == "WAIT_FOR_RETEST" ||
             action == "WAIT" ||
             action == "HIGH_SPREAD" ||
             action == "RISK_BLOCKED" ||
             action == "BACKEND_OFFLINE" ||
             action == "FLOAT_PROFIT_TARGET");
     }

public:
   CVantageNotify(void) : m_enabled(false), m_cooldown_sec(300), m_last_sent(0), m_last_candle(0) {}

   void Configure(const bool enabled, const int cooldown_sec)
     {
      m_enabled = enabled;
      m_cooldown_sec = MathMax(0, cooldown_sec);
     }

   void MaybeNotify(const string action, const string message, const datetime closed_candle_time)
     {
      if(!m_enabled)
         return;
      if(!IsNotifiable(action))
         return;
      // One notification per closed candle for the same action stream
      if(closed_candle_time != 0 && closed_candle_time == m_last_candle && action == m_last_action)
         return;
      if(action == m_last_action && (TimeCurrent() - m_last_sent) < m_cooldown_sec)
         return;

      string msg = "Vantage AI: " + action + " | " + message;
      if(!SendNotification(msg))
         Print("[VantageAI] SendNotification failed err=", GetLastError());
      else
         Print("[VantageAI] Push sent: ", action);

      m_last_action = action;
      m_last_sent = TimeCurrent();
      m_last_candle = closed_candle_time;
     }
  };

#endif
//+------------------------------------------------------------------+
