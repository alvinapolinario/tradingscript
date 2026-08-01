//+------------------------------------------------------------------+
//| VantageSwingExecutor.mq5                                         |
//| Demo-only executor — polls backend for STRONG Swing Strategy     |
//| signals and places market orders via CTrade.                     |
//|                                                                  |
//| Requires: VantageMT5AIDecisionAssistant on demo (heartbeat).     |
//| RISK: Demo testing only — not financial advice.                  |
//+------------------------------------------------------------------+
#property copyright "Vantage Swing Executor"
#property version   "1.00"
#property description "Demo-only auto-execution for Swing Strategy STRONG signals"
#property strict

#include <VantageExecution/VantageExecutionTypes.mqh>
#include <VantageExecution/VantageExecutionClient.mqh>
#include <VantageExecution/VantageExecutionRisk.mqh>
#include <VantageExecution/VantageExecutionTrade.mqh>

//--- A. Connection
input group "A. Connection"
input string InpBackendUrl     = "http://187.77.142.118:8000";
input string InpApiToken       = "2ZGrxytB0N3X6AMWK4ghT8uwklcq5FPCsvEmj9Hzibnpf1LI";
input int    InpPollSeconds    = 5;
input int    InpRequestTimeoutMs = 8000;

//--- B. Safety
input group "B. Safety"
input bool   InpAllowLiveExecution = false;  // Must stay false; demo account still required
input long   InpMagicNumber    = 880001;
input int    InpMaxOpenPositions = 1;

//--- C. Risk
input group "C. Risk"
input double InpRiskPct        = 0.50;
input double InpMaxLot         = 1.0;
input int    InpMaxSpreadPoints = 450;

//--- D. Signal / Mode
input group "D. Signal / Mode"
input ENUM_EXEC_TRADE_MODE InpTradingMode = EXEC_MODE_SWING; // Swing or Scalping — must match advisory InpSwingTradeMode
input double InpMinConfidence  = 85.0;   // Swing default 85; use 72 for scalping
input ENUM_EXEC_TP_LEVEL InpTakeProfitLevel = EXEC_TP1;

//--- E. Logging
input group "E. Logging"
input bool   InpDebugLog       = true;
input bool   InpJournalCsv     = true;

CVantageExecutionClient g_client;
CVantageExecutionTrade  g_trade;
string g_csv_name = "";
int    g_poll_timer = 0;

bool IsDemoAccount(void)
  {
   long mode = AccountInfoInteger(ACCOUNT_TRADE_MODE);
   return (mode == ACCOUNT_TRADE_MODE_DEMO);
  }

bool EnforceDemoOnly(void)
  {
   if(!IsDemoAccount())
     {
      Alert("VantageSwingExecutor: DEMO account required. Refusing to run on live.");
      Print("[VantageExec] FATAL: not a demo account.");
      return false;
     }
   if(InpAllowLiveExecution)
     {
      Alert("VantageSwingExecutor: InpAllowLiveExecution must stay false.");
      Print("[VantageExec] FATAL: InpAllowLiveExecution is true.");
      return false;
     }
   return true;
  }

void LogDbg(const string msg)
  {
   if(InpDebugLog)
      Print("[VantageExec] ", msg);
  }

void JournalCsv(const string line)
  {
   if(!InpJournalCsv || g_csv_name == "")
      return;
   int h = FileOpen(g_csv_name, FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ, ',');
   if(h == INVALID_HANDLE)
      return;
   FileSeek(h, 0, SEEK_END);
   FileWriteString(h, line + "\r\n");
   FileClose(h);
  }

bool SendAck(const string signal_id, const string status, const ulong ticket, const string reason)
  {
   VantageExecAckResult req, rep;
   req.signal_id = signal_id;
   req.status = status;
   req.ticket = ticket;
   req.reason = reason;
   if(!g_client.SendAck(req, rep))
     {
      LogDbg("Ack failed: " + g_client.LastError());
      return false;
     }
   LogDbg("Ack " + status + " signal=" + signal_id);
   return true;
  }

string ExecModeToApi(const ENUM_EXEC_TRADE_MODE mode)
  {
   if(mode == EXEC_MODE_SCALPING) return "SCALPING";
   return "SWING";
  }

long ExecMagicForMode(const ENUM_EXEC_TRADE_MODE mode, const long base_magic)
  {
   if(mode == EXEC_MODE_SCALPING) return base_magic + 1;
   return base_magic;
  }

void ProcessPoll(void)
  {
   const long magic = ExecMagicForMode(InpTradingMode, InpMagicNumber);
   const int max_spread = (InpTradingMode == EXEC_MODE_SCALPING && InpMaxSpreadPoints > 250)
                          ? 250 : InpMaxSpreadPoints;

   if(ExecCountOpenPositions(_Symbol, magic) >= InpMaxOpenPositions)
     {
      LogDbg("Skip poll — max open positions reached.");
      return;
     }
   if(!ExecSpreadOk(_Symbol, max_spread))
     {
      LogDbg("Skip poll — spread too high.");
      return;
     }

   VantageExecOrderSpec spec;
   if(!g_client.PollNext(_Symbol, InpMinConfidence, ExecModeToApi(InpTradingMode), spec))
     {
      LogDbg("Poll failed: " + g_client.LastError());
      return;
     }
   if(!spec.valid)
      return;

   bool is_buy = (spec.side == "BUY");
   double entry = is_buy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(!ExecStopsLevelOk(_Symbol, entry, spec.stop_loss, spec.take_profit))
     {
      LogDbg("Skip — stops level violation.");
      SendAck(spec.signal_id, "SKIPPED", 0, "stops_level");
      return;
     }

   string err = "";
   double lot = ExecCalcRiskVolume(_Symbol, is_buy, entry, spec.stop_loss, InpRiskPct, InpMaxLot, err);
   if(lot <= 0.0)
     {
      LogDbg("Skip — lot calc: " + err);
      SendAck(spec.signal_id, "SKIPPED", 0, err);
      return;
     }

   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double sl = NormalizeDouble(spec.stop_loss, digits);
   double tp = NormalizeDouble(spec.take_profit, digits);
   string comment = "VExec|" + spec.signal_id;

   ulong ticket = 0;
   if(!g_trade.OpenMarket(_Symbol, is_buy, lot, sl, tp, comment, ticket))
     {
      LogDbg("Order rejected: " + g_trade.LastError());
      SendAck(spec.signal_id, "REJECTED", 0, g_trade.LastError());
      JournalCsv(TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS) + ",REJECTED," + spec.signal_id + "," + spec.side + "," + DoubleToString(lot, 2));
      return;
     }

   LogDbg(StringFormat("FILLED %s lot=%.2f ticket=%I64u sl=%.5f tp=%.5f", spec.side, lot, ticket, sl, tp));
   SendAck(spec.signal_id, "FILLED", ticket, "ok");
   JournalCsv(TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS) + ",FILLED," + spec.signal_id + "," + spec.side + "," + DoubleToString(lot, 2) + "," + IntegerToString((long)ticket));
  }

int OnInit(void)
  {
   if(!EnforceDemoOnly())
      return INIT_FAILED;

   g_client.Configure(InpBackendUrl, InpApiToken, InpRequestTimeoutMs);
   g_trade.Configure(ExecMagicForMode(InpTradingMode, InpMagicNumber), "VantageSwingExecutor");

   if(InpJournalCsv)
     {
      g_csv_name = "vantage_exec_" + _Symbol + ".csv";
      if(!FileIsExist(g_csv_name))
        {
         int h = FileOpen(g_csv_name, FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
         if(h != INVALID_HANDLE)
           {
            FileWriteString(h, "time_utc,status,signal_id,side,lot,ticket\r\n");
            FileClose(h);
           }
        }
     }

   int sec = InpPollSeconds;
   if(sec < 3)
      sec = 3;
   g_poll_timer = sec;
   EventSetTimer(g_poll_timer);

   Print("[VantageExec] Started v", VANTAGE_EXEC_VERSION,
         " | DEMO ONLY | Mode=", ExecModeToApi(InpTradingMode),
         " | Symbol=", _Symbol,
         " | Magic=", ExecMagicForMode(InpTradingMode, InpMagicNumber),
         " | Poll=", sec, "s");
   Print("[VantageExec] Allow WebRequest for: ", InpBackendUrl);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   Print("[VantageExec] Stopped reason=", reason);
  }

void OnTimer(void)
  {
   ProcessPoll();
  }

void OnTick(void)
  {
   // Timer-driven polling only
  }

//+------------------------------------------------------------------+
