//+------------------------------------------------------------------+
//| VantageMT5AIDecisionAssistant.mq5                                |
//| Vantage MT5 AI Decision Assistant — ADVISORY ONLY                |
//|                                                                  |
//| FORBIDDEN in this EA: OrderSend, CTrade, PositionModify/Close,   |
//| pending orders, automatic SL/TP changes.                         |
//|                                                                  |
//| RISK DISCLAIMER: Decision-support only. Not financial advice.    |
//| Never auto-trades. Verify all recommendations independently.     |
//|                                                                  |
//| VERIFIED VANTAGE SYMBOL (attach EA to this chart):               |
//|   Symbol        : XAUUSD  (Gold vs US Dollar)                    |
//|   Digits        : 2                                              |
//|   Contract size : 100                                            |
//|   Spread        : Floating                                       |
//|   Stops level   : 20 points                                      |
//|   Volume        : min 0.01 / step 0.01 / max 100                 |
//|   Filling       : Immediate or Cancel                            |
//|   Calculation   : CFD Leverage | Execution: Market               |
//| Runtime still reads ALL of the above from SymbolInfo* — never    |
//| assume every Vantage account matches this exact profile.         |
//+------------------------------------------------------------------+
#property copyright "Vantage MT5 AI Decision Assistant"
#property version   "1.20"
#property description "Advisory-only AI decision assistant for Vantage MT5 XAUUSD"
#property description "Does NOT open, modify, or close trades."

#include <VantageAI/VantageTypes.mqh>
#include <VantageAI/VantageAccount.mqh>
#include <VantageAI/VantageSymbol.mqh>
#include <VantageAI/VantagePositions.mqh>
#include <VantageAI/VantagePendingOrders.mqh>
#include <VantageAI/VantageHistory.mqh>
#include <VantageAI/VantageRisk.mqh>
#include <VantageAI/VantageAnalysis.mqh>
#include <VantageAI/VantageDecision.mqh>
#include <VantageAI/VantageBackend.mqh>
#include <VantageAI/VantageDashboard.mqh>
#include <VantageAI/VantageNotify.mqh>
#include <VantageAI/VantageDiagnostics.mqh>
#include <VantageAI/VantageM5Desk.mqh>
#include <VantageAI/VantagePullback.mqh>

//--- Explicit compile-time advisory guard (do not import Trade.mqh / CTrade)
#ifdef __MQL5__
  // Intentionally no #include <Trade/Trade.mqh>
#endif

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input group "A. Backend (local FastAPI)"
input string InpBackendUrl        = "http://187.77.142.118:8000"; // Backend base URL (VPS)
input string InpBearerToken       = ""; // Paste LOCAL_API_TOKEN from backend/.env (do not commit secrets)
input int    InpHttpTimeoutMs     = 8000;   // WebRequest timeout (ms)
input int    InpMaxResponseAgeSec = 120;    // Max acceptable AI response age (sec)
input int    InpTimerSec          = 5;      // Timer poll (seconds)
input int    InpHeartbeatSec      = 15;     // Send monitor heartbeat every N seconds (0=disable)

input group "B. Symbol & Spread (use chart XAUUSD)"
input bool   InpRunGoldDiscovery  = true;   // Log gold symbol discovery (does not switch chart)
input double InpMaxSpreadPoints   = 50;     // Max spread in broker points (XAUUSD Digits=2 => 50 pts = 0.50); 0=disable

input group "C. Levels (gold defaults OR auto for BTC/other)"
input string InpLevelSource       = "AUTO_NON_GOLD"; // AUTO_NON_GOLD | AUTO | MANUAL
input double InpUpperResist       = 4143.00;
input double InpSecResist         = 4133.00;
input double InpDailyPivot        = 4124.29;
input double InpImmResist         = 4112.00;  // Bullish confirmation (MANUAL)
input double InpRecovery2         = 4105.00;  // Recovery Level 2 (MANUAL)
input double InpRecovery1         = 4100.00;  // Recovery Level 1 (MANUAL)
input double InpImmSupportHi      = 4090.00;  // Immediate support band high (MANUAL)
input double InpImmSupportLo      = 4088.00;  // Immediate support band low (MANUAL)
input double InpMajBuyHi          = 4100.00;
input double InpMajBuyLo          = 4095.00;
input double InpSecSupport        = 4085.00;
input double InpOversizedRangeATR = 1.5;
input double InpOversizedBodyATR  = 1.2;
input double InpRetestTol         = 1.50;
input double InpRsiExhaust        = 32.0;
input int    InpTrendNeed         = 3;
input int    InpBiasLookback      = 20;     // Closed candles for bullish/bearish %

input group "D. Notifications & UI"
input bool   InpShowDashboard     = true;
input bool   InpPushNotify        = false;
input int    InpNotifyCooldownSec = 300;     // Notification cooldown (seconds)
input bool   InpRunDiagnostics    = true;   // Run diagnostics on init

input group "E. Position risk thresholds (% equity at SL)"
input double InpRiskLowMaxPct     = 1.0;    // LOW if below this %
input double InpRiskModMaxPct     = 2.0;    // MODERATE if below this %
input double InpRiskHighMaxPct    = 5.0;    // HIGH if below this %
input double InpRiskVeryHighMaxPct = 10.0;  // VERY_HIGH if below this %; else CRITICAL
input double InpMaxPositionRiskPct = 2.0;   // Max allowed open-position equity risk %
input double InpFloatProfitTargetPct = 10.0; // Warn when floating profit >= this % of equity
input bool   InpCalendarChartSymbolOnly = false; // Calendar/stats: true=chart symbol only, false=all symbols
input int    InpStatsLookbackDays = 0;          // Trade stats lookback days (0=all history)

input group "F. Safety"
input bool   InpAdvisoryOnly      = true;   // MUST remain true — advisory enforcement

input group "G. Backtest / replay (Strategy Tester)"
input bool   InpBacktestMode        = false;            // Force local signal replay (also auto in tester)
input bool   InpBacktestLogSignals  = true;             // Write CSV signal journal
input string InpBacktestFilePrefix  = "vantage_signals"; // MQL5/Files/<prefix>_<SYMBOL>.csv

input group "H. M5 Alignment Desk (web /dashboard)"
input bool   InpM5DeskEnable        = true;   // Send M5/M15/H1 strategy feed on heartbeat
input double InpM5DeskMinAdx        = 20.0;   // Minimum ADX(14) on M5
input double InpM5DeskMinRR         = 2.0;    // Minimum reward:risk
input double InpM5DeskRiskPct       = 0.50;   // Playbook risk % of equity
input int    InpM5DeskNewsBefore    = 30;     // High-impact news block minutes before
input int    InpM5DeskNewsAfter     = 15;     // High-impact news block minutes after
input int    InpM5DeskMaxSetupAge   = 3;      // Max completed M5 candles for setup age

input group "I. Pullback Probability — Timeframes"
input bool             InpPullbackEnable     = true;
input ENUM_TIMEFRAMES  InpPullbackTF_H1      = PERIOD_H1;
input ENUM_TIMEFRAMES  InpPullbackTF_M15     = PERIOD_M15;
input ENUM_TIMEFRAMES  InpPullbackTF_M5      = PERIOD_M5;

input group "J. Pullback Probability — Indicators"
input int    InpPbEmaFast      = 20;
input int    InpPbEmaSlow      = 50;
input int    InpPbEmaLong      = 200;
input int    InpPbRsiPeriod    = 14;
input double InpPbRsiOB        = 70.0;
input double InpPbRsiOS        = 30.0;
input int    InpPbAtrPeriod    = 14;
input int    InpPbBbPeriod     = 20;
input double InpPbBbDev        = 2.0;
input int    InpPbAdxPeriod    = 14;
input double InpPbAdxMin       = 20.0;
input int    InpPbSwingLeft    = 3;
input int    InpPbSwingRight   = 3;

input group "K. Pullback Probability — Weights"
input double InpPbWRsiExtreme  = 10.0;
input double InpPbWRsiRecover  = 8.0;
input double InpPbWExtension   = 15.0;
input double InpPbWBb          = 10.0;
input double InpPbWEmaDist     = 10.0;
input double InpPbWCandle      = 8.0;
input double InpPbWDivergence  = 7.0;
input double InpPbWSr          = 7.0;
input double InpPbWStructure   = 10.0;
input double InpPbWAdx         = 8.0;
input double InpPbWMtf         = 7.0;

input group "L. Pullback Probability — Alerts / Display"
input bool   InpPbAlertPopup   = false;
input bool   InpPbAlertPush    = false;
input bool   InpPbAlertSound   = false;
input double InpPbThrPullback  = 65.0;
input double InpPbThrContinue  = 65.0;
input double InpPbThrReversal  = 55.0;
input double InpPbThrExtension = 75.0;
input int    InpPbAlertCoolSec = 300;
input int    InpPbUtcOffsetHrs = 0;
input bool   InpPbShowChartObj = true;
input bool   InpPbShowDash     = true;

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
VantageAccountInfo   g_acct;
VantageSymbolSpec    g_spec;
CVantageAnalysis     g_analysis;
CVantageBackend      g_backend;
CVantageDashboard    g_dash;
CVantageNotify       g_notify;
CVantageM5Desk       g_m5desk;
VantageM5DeskSnap    g_m5snap;
CVantagePullback     g_pullback;
VantagePullbackResult g_pbsnap;

datetime g_last_closed_candle = 0;
datetime g_last_request_candle = 0;
datetime g_last_heartbeat = 0;
string   g_last_action = "NO_NEW_TRADE";
string   g_backend_status = "UNKNOWN";
string   g_candle_status = "WAITING";
string   g_note = "";
VantageBackendReply g_reply;
VantageTechnicalSnap g_tech;
VantagePositionSummary g_pos;
VantagePendingOrderSummary g_pending;
VantageRiskEstimate g_risk;
VantagePriceSnap g_px;
VantageDecisionState g_dec;
string   g_last_risk_notify_key = "";
string   g_last_float_profit_notify_key = "";
double   g_equity = 0.0;
double   g_balance = 0.0;
double   g_floating_pl_pct = 0.0;
bool     g_float_profit_target_hit = false;
VantagePlCalendar g_pl_cal;
VantageTradeStats g_trade_stats;
datetime g_last_cal_build = 0;
int      g_cal_req_year = 0;   // 0 = use current server month
int      g_cal_req_month = 0;

// Active levels (manual gold map or auto ATR map for BTC/etc.)
VantageLevelConfig g_lvl;
string   g_level_source = "MANUAL";
double   g_lv_imm_lo = 0.0;
double   g_lv_imm_hi = 0.0;
double   g_lv_rec1 = 0.0;
double   g_lv_rec2 = 0.0;
double   g_lv_bull = 0.0;

// Replay / Strategy Tester signal journal
bool     g_replay_mode = false;
int      g_bt_file = INVALID_HANDLE;
string   g_bt_filename = "";
int      g_bt_rows = 0;
int      g_bt_buy = 0;
int      g_bt_sell = 0;
int      g_bt_wait = 0;
int      g_bt_none = 0;
bool     g_bt_summary_printed = false;

//+------------------------------------------------------------------+
//| Strategy Tester / forced local replay                            |
//+------------------------------------------------------------------+
bool IsReplayMode(void)
  {
   return (InpBacktestMode || (bool)MQLInfoInteger(MQL_TESTER) || (bool)MQLInfoInteger(MQL_OPTIMIZATION));
  }

bool WantAutoLevels(void)
  {
   string s = InpLevelSource;
   StringToUpper(s);
   StringTrimLeft(s);
   StringTrimRight(s);
   if(s == "MANUAL")
      return false;
   if(s == "AUTO")
      return true;
   // AUTO_NON_GOLD (default-friendly): auto for BTC/etc., manual gold map for XAU*
   if(s == "AUTO_NON_GOLD" || s == "")
      return !VantageNameLooksLikeGold(_Symbol);
   return !VantageNameLooksLikeGold(_Symbol);
  }

void ApplyManualLevels(void)
  {
   ZeroMemory(g_lvl);
   g_lv_imm_lo = InpImmSupportLo;
   g_lv_imm_hi = InpImmSupportHi;
   g_lv_rec1 = InpRecovery1;
   g_lv_rec2 = InpRecovery2;
   g_lv_bull = InpImmResist;
   g_lvl.upper_resist = InpUpperResist;
   g_lvl.sec_resist = InpSecResist;
   g_lvl.daily_pivot = InpDailyPivot;
   g_lvl.imm_resist = InpImmResist;
   g_lvl.imm_sup_hi = InpRecovery2;
   g_lvl.imm_sup_lo = InpRecovery1;
   g_lvl.maj_buy_hi = InpImmSupportHi;
   g_lvl.maj_buy_lo = InpImmSupportLo;
   g_lvl.sec_support = InpSecSupport;
   g_lvl.oversized_range_atr = InpOversizedRangeATR;
   g_lvl.oversized_body_atr = InpOversizedBodyATR;
   g_lvl.retest_tol = InpRetestTol;
   g_lvl.rsi_exhaust = InpRsiExhaust;
   g_lvl.pivot_left = 3;
   g_lvl.pivot_right = 3;
   g_lvl.trend_need = InpTrendNeed;
   g_lvl.bias_lookback = InpBiasLookback;
   g_level_source = "MANUAL";
   g_analysis.SetLevels(g_lvl);
  }

bool RefreshActiveLevels(const bool force_log)
  {
   if(!WantAutoLevels())
     {
      ApplyManualLevels();
      if(force_log)
         Print("[VantageAI] Levels MANUAL (", _Symbol, ") imm=", g_lv_imm_lo, "-", g_lv_imm_hi,
               " rec=", g_lv_rec1, "/", g_lv_rec2, " bull=", g_lv_bull);
      return true;
     }

   double mid = 0.0;
   if(!VantageCapturePrices(_Symbol, 0, g_px) || g_px.bid <= 0.0)
     {
      MqlRates r[];
      if(CopyRates(_Symbol, PERIOD_M30, 1, 1, r) == 1)
         mid = r[0].close;
     }
   else
      mid = (g_px.bid + g_px.ask) * 0.5;

   double atr = 0.0;
   if(g_tech.atr14 > 0.0)
      atr = g_tech.atr14;
   else
     {
      int h = iATR(_Symbol, PERIOD_M30, 14);
      if(h != INVALID_HANDLE)
        {
         double buf[];
         if(CopyBuffer(h, 0, 1, 1, buf) == 1)
            atr = buf[0];
         IndicatorRelease(h);
        }
     }

   if(mid <= 0.0)
     {
      ApplyManualLevels();
      return false;
     }
   if(atr <= 0.0)
      atr = MathMax(mid * 0.005, _Point * 50); // rough band if ATR not ready

   if(!VantageFillAutoLevels(mid, atr, g_spec.digits,
                             InpOversizedRangeATR, InpOversizedBodyATR, InpRsiExhaust,
                             InpTrendNeed, InpBiasLookback, g_lvl,
                             g_lv_imm_lo, g_lv_imm_hi, g_lv_rec1, g_lv_rec2, g_lv_bull))
      return false;
   g_level_source = "AUTO";
   g_analysis.SetLevels(g_lvl);
   if(force_log)
      Print("[VantageAI] Levels AUTO (", _Symbol, ") mid=", mid, " ATR=", atr,
            " imm=", g_lv_imm_lo, "-", g_lv_imm_hi,
            " rec=", g_lv_rec1, "/", g_lv_rec2, " bull=", g_lv_bull);
   return true;
  }

string BacktestCsvName(void)
  {
   string prefix = InpBacktestFilePrefix;
   if(prefix == "")
      prefix = "vantage_signals";
   return prefix + "_" + _Symbol + ".csv";
  }

bool OpenBacktestCsv(void)
  {
   if(!InpBacktestLogSignals)
      return true;
   g_bt_filename = BacktestCsvName();
   g_bt_file = FileOpen(g_bt_filename, FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_REWRITE, ',');
   if(g_bt_file == INVALID_HANDLE)
     {
      Print("[VantageAI] Backtest CSV open failed: ", g_bt_filename, " err=", GetLastError());
      return false;
     }
   FileWrite(g_bt_file,
             "time","symbol","bid","spread","trend","market_state",
             "bullish_pct","bearish_pct","rsi","action","new_entry","risk_status","note");
   Print("[VantageAI] Signal journal: MQL5/Files/", g_bt_filename);
   return true;
  }

void CloseBacktestCsv(void)
  {
   if(g_bt_file != INVALID_HANDLE)
     {
      FileClose(g_bt_file);
      g_bt_file = INVALID_HANDLE;
     }
  }

void WriteBacktestSignalRow(const datetime bar_time)
  {
   if(!InpBacktestLogSignals || g_bt_file == INVALID_HANDLE)
      return;
   string note = g_dec.note;
   StringReplace(note, ",", ";");
   StringReplace(note, "\n", " ");
   FileWrite(g_bt_file,
             TimeToString(bar_time, TIME_DATE | TIME_MINUTES),
             _Symbol,
             DoubleToString(g_px.bid, g_spec.digits),
             IntegerToString(g_px.spread_points),
             g_dec.trend,
             g_dec.market_state,
             DoubleToString(g_dec.bullish_pct, 1),
             DoubleToString(g_dec.bearish_pct, 1),
             DoubleToString(g_tech.rsi14, 2),
             g_dec.primary_action,
             g_dec.new_entry_decision,
             g_dec.risk_status,
             note);
   g_bt_rows++;
   if(g_dec.new_entry_decision == "BUY_ALLOWED") g_bt_buy++;
   else if(g_dec.new_entry_decision == "SELL_ALLOWED") g_bt_sell++;
   else if(g_dec.new_entry_decision == "WAIT" || g_dec.primary_action == "WAIT_FOR_RETEST") g_bt_wait++;
   else g_bt_none++;
  }

void PrintBacktestSummary(void)
  {
   if(g_bt_summary_printed)
      return;
   g_bt_summary_printed = true;
   Print("[VantageAI] === Signal backtest summary (advisory only — no deals) ===");
   Print("[VantageAI] Bars logged: ", g_bt_rows,
         " | BUY_ALLOWED: ", g_bt_buy,
         " | SELL_ALLOWED: ", g_bt_sell,
         " | WAIT: ", g_bt_wait,
         " | other: ", g_bt_none);
   if(g_bt_filename != "")
      Print("[VantageAI] CSV: Terminal MQL5/Files/", g_bt_filename,
            " (Strategy Tester: Tester/Agent-*/MQL5/Files/)");
  }

//+------------------------------------------------------------------+
//| Advisory enforcement — refuse to init if flag disabled           |
//+------------------------------------------------------------------+
bool EnforceAdvisoryMode(void)
  {
   if(!InpAdvisoryOnly)
     {
      Alert("Vantage AI: InpAdvisoryOnly is false. First release refuses to run. Live auto-trading is disabled.");
      Print("[VantageAI] FATAL: advisory mode must remain enabled.");
      return false;
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Build JSON payload (never includes full account login)           |
//+------------------------------------------------------------------+
string BuildAnalyzePayload(const VantageTechnicalSnap &tech,
                           const VantagePriceSnap &px,
                           const VantagePositionSummary &pos,
                           const VantageRiskEstimate &risk,
                           const string environment)
  {
   string j = "{";
   j += "\"schema_version\":\"1.0\",";
   j += "\"mode\":\"advisory_only\",";
   j += "\"broker\":{";
   j += "\"company\":\"" + JsonEscape(g_acct.company) + "\",";
   j += "\"server\":\"" + JsonEscape(g_acct.server) + "\",";
   j += "\"currency\":\"" + JsonEscape(g_acct.currency) + "\",";
   j += "\"margin_mode\":\"" + JsonEscape(VantageMarginModeName(g_acct.margin_mode)) + "\",";
   j += "\"account_login_masked\":\"" + JsonEscape(g_acct.login_masked) + "\"";
   // NOTE: full login intentionally omitted
   j += "},";
   j += "\"symbol\":{";
   j += "\"name\":\"" + JsonEscape(g_spec.symbol) + "\",";
   j += "\"digits\":" + IntegerToString(g_spec.digits) + ",";
   j += "\"point\":" + DoubleToJson(g_spec.point, 10) + ",";
   j += "\"tick_size\":" + DoubleToJson(g_spec.tick_size, 10) + ",";
   j += "\"tick_value\":" + DoubleToJson(g_spec.tick_value, 8) + ",";
   j += "\"tick_value_profit\":" + DoubleToJson(g_spec.tick_value_profit, 8) + ",";
   j += "\"tick_value_loss\":" + DoubleToJson(g_spec.tick_value_loss, 8) + ",";
   j += "\"contract_size\":" + DoubleToJson(g_spec.contract_size, 4) + ",";
   j += "\"volume_min\":" + DoubleToJson(g_spec.volume_min, 4) + ",";
   j += "\"volume_max\":" + DoubleToJson(g_spec.volume_max, 4) + ",";
   j += "\"volume_step\":" + DoubleToJson(g_spec.volume_step, 4) + ",";
   j += "\"stops_level\":" + IntegerToString(g_spec.stops_level) + ",";
   j += "\"freeze_level\":" + IntegerToString(g_spec.freeze_level) + ",";
   j += "\"spread_float\":" + (g_spec.spread_float ? "true" : "false") + ",";
   j += "\"trade_mode\":" + IntegerToString(g_spec.trade_mode) + ",";
   j += "\"trade_execution\":" + IntegerToString(g_spec.trade_execution) + ",";
   j += "\"filling_mode\":" + IntegerToString(g_spec.filling_mode);
   j += "},";
   j += "\"prices\":{";
   j += "\"bid\":" + DoubleToJson(px.bid, g_spec.digits) + ",";
   j += "\"ask\":" + DoubleToJson(px.ask, g_spec.digits) + ",";
   j += "\"last\":" + DoubleToJson(px.last, g_spec.digits) + ",";
   j += "\"spread_points\":" + IntegerToString(px.spread_points) + ",";
   j += "\"high_spread\":" + (px.high_spread ? "true" : "false") + ",";
   j += "\"server_time\":\"" + TimeToString(px.server_time, TIME_DATE|TIME_SECONDS) + "\",";
   j += "\"local_time\":\"" + TimeToString(px.local_time, TIME_DATE|TIME_SECONDS) + "\",";
   j += "\"utc_time\":\"" + TimeToString(px.utc_time, TIME_DATE|TIME_SECONDS) + "\"";
   j += "},";
   j += "\"candle\":{";
   j += "\"timeframe\":\"M30\",";
   j += "\"time\":\"" + TimeToString(tech.candle_time, TIME_DATE|TIME_SECONDS) + "\",";
   j += "\"open\":" + DoubleToJson(tech.open, g_spec.digits) + ",";
   j += "\"high\":" + DoubleToJson(tech.high, g_spec.digits) + ",";
   j += "\"low\":" + DoubleToJson(tech.low, g_spec.digits) + ",";
   j += "\"close\":" + DoubleToJson(tech.close, g_spec.digits) + ",";
   j += "\"volume\":" + DoubleToJson(tech.volume, 0);
   j += "},";
   j += "\"indicators\":{";
   j += "\"ema20\":" + DoubleToJson(tech.ema20, g_spec.digits) + ",";
   j += "\"ema50\":" + DoubleToJson(tech.ema50, g_spec.digits) + ",";
   j += "\"ema200\":" + DoubleToJson(tech.ema200, g_spec.digits) + ",";
   j += "\"bb_upper\":" + DoubleToJson(tech.bb_upper, g_spec.digits) + ",";
   j += "\"bb_middle\":" + DoubleToJson(tech.bb_middle, g_spec.digits) + ",";
   j += "\"bb_lower\":" + DoubleToJson(tech.bb_lower, g_spec.digits) + ",";
   j += "\"rsi14\":" + DoubleToJson(tech.rsi14, 4) + ",";
   j += "\"atr14\":" + DoubleToJson(tech.atr14, g_spec.digits) + ",";
   j += "\"volume_sma\":" + DoubleToJson(tech.volume_sma, 2);
   j += "},";
   j += "\"structure\":{";
   j += "\"trend\":\"" + g_analysis.TrendName(tech.trend) + "\",";
   j += "\"oversized_candle\":" + (tech.oversized_candle ? "true" : "false") + ",";
   j += "\"support_break\":" + (tech.support_break ? "true" : "false") + ",";
   j += "\"retest_pending\":" + (tech.retest_pending ? "true" : "false") + ",";
   j += "\"bear_reject\":" + (tech.bear_reject ? "true" : "false") + ",";
   j += "\"bull_reject\":" + (tech.bull_reject ? "true" : "false") + ",";
   j += "\"note\":\"" + JsonEscape(tech.structure_note) + "\",";
   j += "\"nearest_support\":\"" + JsonEscape(tech.nearest_support) + "\",";
   j += "\"nearest_resistance\":\"" + JsonEscape(tech.nearest_resistance) + "\",";
   j += "\"daily_pivot\":" + DoubleToJson(g_lvl.daily_pivot, g_spec.digits) + ",";
   j += "\"bullish_pct\":" + DoubleToJson(tech.bullish_pct, 2) + ",";
   j += "\"bearish_pct\":" + DoubleToJson(tech.bearish_pct, 2) + ",";
   j += "\"neutral_pct\":" + DoubleToJson(tech.neutral_pct, 2) + ",";
   j += "\"bias_lookback\":" + IntegerToString(tech.bias_lookback) + ",";
   j += "\"indicator_bullish_pct\":" + DoubleToJson(tech.indicator_bullish_pct, 2) + ",";
   j += "\"indicator_bearish_pct\":" + DoubleToJson(tech.indicator_bearish_pct, 2);
   j += "},";
   j += "\"levels\":{";
   j += "\"source\":\"" + JsonEscape(g_level_source) + "\",";
   j += "\"upper_resist\":" + DoubleToJson(g_lvl.upper_resist, g_spec.digits) + ",";
   j += "\"sec_resist\":" + DoubleToJson(g_lvl.sec_resist, g_spec.digits) + ",";
   j += "\"daily_pivot\":" + DoubleToJson(g_lvl.daily_pivot, g_spec.digits) + ",";
   j += "\"imm_support_lo\":" + DoubleToJson(g_lv_imm_lo, g_spec.digits) + ",";
   j += "\"imm_support_hi\":" + DoubleToJson(g_lv_imm_hi, g_spec.digits) + ",";
   j += "\"recovery_1\":" + DoubleToJson(g_lv_rec1, g_spec.digits) + ",";
   j += "\"recovery_2\":" + DoubleToJson(g_lv_rec2, g_spec.digits) + ",";
   j += "\"bullish_confirmation\":" + DoubleToJson(g_lv_bull, g_spec.digits);
   j += "},";
   j += "\"extra\":{";
   j += "\"risk_low_max_pct\":" + DoubleToJson(InpRiskLowMaxPct, 4) + ",";
   j += "\"risk_moderate_max_pct\":" + DoubleToJson(InpRiskModMaxPct, 4) + ",";
   j += "\"risk_high_max_pct\":" + DoubleToJson(InpRiskHighMaxPct, 4) + ",";
   j += "\"risk_very_high_max_pct\":" + DoubleToJson(InpRiskVeryHighMaxPct, 4) + ",";
   j += "\"max_position_risk_pct\":" + DoubleToJson(InpMaxPositionRiskPct, 4) + ",";
   j += "\"level_source\":\"" + JsonEscape(g_level_source) + "\"";
   j += "},";
   j += "\"positions\":{";
   j += "\"count\":" + IntegerToString(pos.count) + ",";
   j += "\"total_buy_volume\":" + DoubleToJson(pos.total_buy_volume, 4) + ",";
   j += "\"total_sell_volume\":" + DoubleToJson(pos.total_sell_volume, 4) + ",";
   j += "\"weighted_avg_entry\":" + DoubleToJson(pos.weighted_avg_entry, g_spec.digits) + ",";
   j += "\"total_floating_pl\":" + DoubleToJson(pos.total_floating_pl, 4) + ",";
   j += "\"items\":" + VantagePositionsToJson(pos);
   j += "},";
   j += "\"pending_orders\":" + VantagePendingOrdersBlobJson(g_pending) + ",";
   j += "\"risk\":" + VantageRiskToJson(risk) + ",";
   j += "\"environment\":\"" + JsonEscape(environment) + "\"";
   j += "}";
   return j;
  }

//+------------------------------------------------------------------+
//| Build heartbeat JSON for web monitor                             |
//+------------------------------------------------------------------+
string BuildHeartbeatPayload(void)
  {
   string j = "{";
   j += "\"ea_version\":\"" + VANTAGE_AI_VERSION + "\",";
   j += "\"company\":\"" + JsonEscape(g_acct.company) + "\",";
   j += "\"server\":\"" + JsonEscape(g_acct.server) + "\",";
   j += "\"account_login_masked\":\"" + JsonEscape(g_acct.login_masked) + "\",";
   j += "\"margin_mode\":\"" + JsonEscape(VantageMarginModeName(g_acct.margin_mode)) + "\",";
   j += "\"currency\":\"" + JsonEscape(g_acct.currency) + "\",";
   j += "\"symbol\":\"" + JsonEscape(g_spec.symbol) + "\",";
   j += "\"digits\":" + IntegerToString(g_spec.digits) + ",";
   j += "\"contract_size\":" + DoubleToJson(g_spec.contract_size, 2) + ",";
   j += "\"stops_level\":" + IntegerToString(g_spec.stops_level) + ",";
   j += "\"bid\":" + DoubleToJson(g_px.bid, g_spec.digits) + ",";
   j += "\"ask\":" + DoubleToJson(g_px.ask, g_spec.digits) + ",";
   j += "\"spread_points\":" + IntegerToString(g_px.spread_points) + ",";
   j += "\"high_spread\":" + (g_px.high_spread ? "true" : "false") + ",";
   j += "\"action\":\"" + JsonEscape(g_dec.primary_action) + "\",";
   j += "\"trend\":\"" + JsonEscape(g_dec.trend) + "\",";
   j += "\"bullish_pct\":" + DoubleToJson(g_dec.bullish_pct, 2) + ",";
   j += "\"bearish_pct\":" + DoubleToJson(g_dec.bearish_pct, 2) + ",";
   j += "\"neutral_pct\":" + DoubleToJson(g_dec.neutral_pct, 2) + ",";
   j += "\"bias_lookback\":" + IntegerToString(g_dec.bias_lookback) + ",";
   j += "\"indicator_bullish_pct\":" + DoubleToJson(g_dec.indicator_bullish_pct, 2) + ",";
   j += "\"indicator_bearish_pct\":" + DoubleToJson(g_dec.indicator_bearish_pct, 2) + ",";
   j += "\"candle_status\":\"" + JsonEscape(g_candle_status) + "\",";
   j += "\"backend_status\":\"" + JsonEscape(g_backend_status) + "\",";
   j += "\"position_count\":" + IntegerToString(g_pos.count) + ",";
   j += "\"total_buy_volume\":" + DoubleToJson(g_pos.total_buy_volume, 4) + ",";
   j += "\"total_sell_volume\":" + DoubleToJson(g_pos.total_sell_volume, 4) + ",";
   j += "\"pending_order_count\":" + IntegerToString(g_pending.count) + ",";
   j += "\"pending_orders\":" + VantagePendingOrdersBlobJson(g_pending) + ",";
   j += "\"floating_pl\":" + DoubleToJson(g_pos.total_floating_pl, 2) + ",";
   j += "\"equity\":" + DoubleToJson(g_equity, 2) + ",";
   j += "\"balance\":" + DoubleToJson(g_balance, 2) + ",";
   j += "\"floating_pl_pct_of_equity\":" + DoubleToJson(g_floating_pl_pct, 4) + ",";
   j += "\"float_profit_target_pct\":" + DoubleToJson(InpFloatProfitTargetPct, 4) + ",";
   j += "\"float_profit_target_hit\":" + (g_float_profit_target_hit ? "true" : "false") + ",";
   j += "\"nearest_support\":\"" + JsonEscape(g_dec.immediate_support) + "\",";
   j += "\"nearest_resistance\":\"" + JsonEscape(g_dec.recovery_level_1) + "\",";
   j += "\"note\":\"" + JsonEscape(g_dec.risk_warning) + "\",";
   j += "\"terminal_connected\":" + (g_acct.terminal_connected ? "true" : "false") + ",";
   j += "\"new_entry_decision\":\"" + JsonEscape(g_dec.new_entry_decision) + "\",";
   j += "\"existing_position_decision\":\"" + JsonEscape(g_dec.existing_position_decision) + "\",";
   j += "\"risk_status\":\"" + JsonEscape(g_dec.risk_status) + "\",";
   j += "\"equity_risk_pct\":" + DoubleToJson(g_risk.equity_risk_pct, 4) + ",";
   j += "\"estimated_sl_loss\":" + DoubleToJson(g_risk.money_at_risk, 4) + ",";
   j += "\"entry\":" + DoubleToJson(g_risk.entry, g_spec.digits) + ",";
   j += "\"sl\":" + DoubleToJson(g_risk.sl, g_spec.digits) + ",";
   j += "\"new_position_allowed\":" + (g_dec.new_position_allowed ? "true" : "false") + ",";
   j += "\"add_position_allowed\":" + (g_dec.add_position_allowed ? "true" : "false") + ",";
   j += "\"exceeds_max_position_risk\":" + (g_dec.exceeds_max_position_risk ? "true" : "false") + ",";
   j += "\"market_state\":\"" + JsonEscape(g_dec.market_state) + "\",";
   j += "\"risk_warning\":\"" + JsonEscape(g_dec.risk_warning) + "\",";
   j += "\"immediate_support\":\"" + JsonEscape(g_dec.immediate_support) + "\",";
   j += "\"recovery_level_1\":\"" + JsonEscape(g_dec.recovery_level_1) + "\",";
   j += "\"recovery_level_2\":\"" + JsonEscape(g_dec.recovery_level_2) + "\",";
   j += "\"bullish_confirmation\":\"" + JsonEscape(g_dec.bullish_confirmation) + "\",";
   j += "\"technical_invalidation\":\"" + JsonEscape(g_dec.technical_invalidation) + "\",";
   j += "\"level_source\":\"" + JsonEscape(g_level_source) + "\",";
   j += "\"pl_calendar\":" + VantagePlCalendarToJson(g_pl_cal) + ",";
   j += "\"trade_stats\":" + VantageTradeStatsToJson(g_trade_stats) + ",";
   {
      MqlDateTime now_srv;
      TimeToStruct(TimeCurrent(), now_srv);
      j += "\"server_year\":" + IntegerToString(now_srv.year) + ",";
      j += "\"server_month\":" + IntegerToString(now_srv.mon);
   }
   if(InpM5DeskEnable)
     {
      j += ",\"reward_risk_ratio\":" + DoubleToJson(g_m5snap.reward_risk_ratio, 4);
      j += ",\"strategy\":" + g_m5desk.ToJson(g_m5snap);
     }
   if(InpPullbackEnable && g_pbsnap.valid)
      j += ",\"pullback\":" + g_pullback.ToJson(g_pbsnap);
   j += "}";
   return j;
  }

void FillPullbackConfig(VantagePullbackConfig &cfg)
  {
   ZeroMemory(cfg);
   cfg.tf_h1 = InpPullbackTF_H1;
   cfg.tf_m15 = InpPullbackTF_M15;
   cfg.tf_m5 = InpPullbackTF_M5;
   cfg.ema_fast = InpPbEmaFast;
   cfg.ema_slow = InpPbEmaSlow;
   cfg.ema_long = InpPbEmaLong;
   cfg.rsi_period = InpPbRsiPeriod;
   cfg.rsi_ob = InpPbRsiOB;
   cfg.rsi_os = InpPbRsiOS;
   cfg.atr_period = InpPbAtrPeriod;
   cfg.bb_period = InpPbBbPeriod;
   cfg.bb_dev = InpPbBbDev;
   cfg.adx_period = InpPbAdxPeriod;
   cfg.adx_min = InpPbAdxMin;
   cfg.swing_left = InpPbSwingLeft;
   cfg.swing_right = InpPbSwingRight;
   cfg.w_rsi_extreme = InpPbWRsiExtreme;
   cfg.w_rsi_recovery = InpPbWRsiRecover;
   cfg.w_extension = InpPbWExtension;
   cfg.w_bb = InpPbWBb;
   cfg.w_ema_dist = InpPbWEmaDist;
   cfg.w_candle = InpPbWCandle;
   cfg.w_divergence = InpPbWDivergence;
   cfg.w_sr = InpPbWSr;
   cfg.w_structure = InpPbWStructure;
   cfg.w_adx_fall = InpPbWAdx;
   cfg.w_mtf = InpPbWMtf;
   cfg.alert_popup = InpPbAlertPopup;
   cfg.alert_push = InpPbAlertPush && !g_replay_mode;
   cfg.alert_sound = InpPbAlertSound;
   cfg.thr_pullback = InpPbThrPullback;
   cfg.thr_continuation = InpPbThrContinue;
   cfg.thr_reversal = InpPbThrReversal;
   cfg.thr_extension = InpPbThrExtension;
   cfg.alert_cooldown_sec = InpPbAlertCoolSec;
   cfg.server_utc_offset_hours = InpPbUtcOffsetHrs;
   cfg.show_chart_objects = InpPbShowChartObj;
   cfg.show_dashboard = InpPbShowDash;
  }

void MaybeEvalPullback(const bool force)
  {
   if(!InpPullbackEnable)
      return;
   VantagePullbackResult r;
   if(g_pullback.Evaluate(force, r))
      g_pbsnap = r;
  }

void RefreshPlCalendar(const bool force)
  {
   // Rebuild when forced, when minute elapsed, or when requested month differs from loaded
   bool month_changed = (g_cal_req_year > 0 && g_cal_req_month > 0 &&
                         (g_pl_cal.year != g_cal_req_year || g_pl_cal.month != g_cal_req_month));
   if(!force && !month_changed && g_last_cal_build > 0 && (TimeCurrent() - g_last_cal_build) < 60)
      return;

   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   int y = (g_cal_req_year > 0 ? g_cal_req_year : now.year);
   int m = (g_cal_req_month > 0 ? g_cal_req_month : now.mon);
   // Clamp: do not allow future months beyond server time
   if(y > now.year || (y == now.year && m > now.mon))
     {
      y = now.year;
      m = now.mon;
      g_cal_req_year = y;
      g_cal_req_month = m;
     }

   string filter = InpCalendarChartSymbolOnly ? _Symbol : "";
   double eq = (g_equity > 0.0) ? g_equity : AccountInfoDouble(ACCOUNT_EQUITY);
   string ccy = (g_acct.currency != "" ? g_acct.currency : AccountInfoString(ACCOUNT_CURRENCY));
   VantageBuildMonthPlCalendar(y, m, eq, ccy, filter, g_pl_cal);
   VantageBuildTradeStats(InpStatsLookbackDays, eq, ccy, filter, g_trade_stats);
   g_last_cal_build = TimeCurrent();
  }

void MaybeSendHeartbeat(void)
  {
   if(InpHeartbeatSec <= 0)
      return;
   if(g_replay_mode)
      return;
   if(g_last_heartbeat > 0 && (TimeCurrent() - g_last_heartbeat) < InpHeartbeatSec)
      return;
   RefreshActiveLevels(false);
   if(g_analysis.HasEnoughHistory(50))
      g_analysis.BuildSnapshot(g_tech);
   RebuildDecisionState(g_reply.ok);

   VantageCapturePrices(_Symbol, InpMaxSpreadPoints, g_px);
   VantageLoadPositions(_Symbol, g_pos);
   VantageLoadPendingOrders(_Symbol, g_spec, g_px, g_pending);
   RefreshEquityMetrics();
   RefreshPlCalendar(false);
   if(InpM5DeskEnable)
      g_m5desk.Evaluate(g_spec, (int)MathRound(InpMaxSpreadPoints), g_m5snap);
   else
      g_m5snap.valid = false;
   MaybeEvalPullback(false);

   static int s_last_pending_logged = -1;
   if(g_pending.count != s_last_pending_logged)
     {
      PrintFormat("[VantageAI] Pending orders on account: %d (OrdersTotal=%d)",
                  g_pending.count, OrdersTotal());
      s_last_pending_logged = g_pending.count;
     }

   int resp_y = 0, resp_m = 0;
   if(g_backend.Heartbeat(BuildHeartbeatPayload(), resp_y, resp_m))
     {
      g_last_heartbeat = TimeCurrent();
      if(g_backend_status == "OFFLINE" || g_backend_status == "OFFLINE/ERR")
         g_backend_status = "OK";
            if(resp_y >= 2000 && resp_m >= 1 && resp_m <= 12)
              {
               if(resp_y != g_cal_req_year || resp_m != g_cal_req_month ||
                  g_pl_cal.year != resp_y || g_pl_cal.month != resp_m)
                 {
                  g_cal_req_year = resp_y;
                  g_cal_req_month = resp_m;
                  RefreshPlCalendar(true);
                  int y2 = 0, m2 = 0;
                  g_backend.Heartbeat(BuildHeartbeatPayload(), y2, m2);
                 }
              }
     }
   else
     {
      g_backend_status = "OFFLINE";
      static datetime last_hb_err = 0;
      if(last_hb_err == 0 || (TimeCurrent() - last_hb_err) >= 60)
        {
         Print("[VantageAI] Heartbeat failed: ", g_backend.LastError());
         last_hb_err = TimeCurrent();
        }
     }
  }

//+------------------------------------------------------------------+
//| Rebuild local decision state (also used between candle analyzes) |
//+------------------------------------------------------------------+
void RebuildDecisionState(const bool prefer_backend_reply)
  {
   string trend_name = g_analysis.TrendName(g_tech.trend);
   VantageBuildLocalDecision(g_tech, g_pos, g_risk, g_px, trend_name,
                             InpMaxPositionRiskPct,
                             InpRiskLowMaxPct, InpRiskModMaxPct, InpRiskHighMaxPct, InpRiskVeryHighMaxPct,
                             InpRsiExhaust,
                             g_lv_imm_lo, g_lv_imm_hi,
                             g_lv_rec1, g_lv_rec2, g_lv_bull,
                             g_dec, g_spec.digits);

   if(prefer_backend_reply && g_reply.ok)
     {
      if(g_reply.trend != "") g_dec.trend = g_reply.trend;
      // Always keep local candle/indicator bias % (backend may omit)
      g_dec.bullish_pct = g_tech.bullish_pct;
      g_dec.bearish_pct = g_tech.bearish_pct;
      g_dec.neutral_pct = g_tech.neutral_pct;
      g_dec.bias_lookback = g_tech.bias_lookback;
      g_dec.indicator_bullish_pct = g_tech.indicator_bullish_pct;
      g_dec.indicator_bearish_pct = g_tech.indicator_bearish_pct;
      if(g_reply.market_state != "") g_dec.market_state = g_reply.market_state;
      if(g_reply.new_entry_decision != "") g_dec.new_entry_decision = g_reply.new_entry_decision;
      if(g_reply.existing_position_decision != "") g_dec.existing_position_decision = g_reply.existing_position_decision;
      if(g_reply.risk_status != "") g_dec.risk_status = g_reply.risk_status;
      if(g_reply.immediate_support != "") g_dec.immediate_support = g_reply.immediate_support;
      if(g_reply.recovery_level_1 != "") g_dec.recovery_level_1 = g_reply.recovery_level_1;
      if(g_reply.recovery_level_2 != "") g_dec.recovery_level_2 = g_reply.recovery_level_2;
      if(g_reply.bullish_confirmation != "") g_dec.bullish_confirmation = g_reply.bullish_confirmation;
      if(g_reply.technical_invalidation != "") g_dec.technical_invalidation = g_reply.technical_invalidation;
      if(g_reply.risk_warning != "") g_dec.risk_warning = g_reply.risk_warning;
      g_dec.new_position_allowed = g_reply.new_position_allowed;
      g_dec.add_position_allowed = g_reply.add_position_allowed;
      g_dec.exceeds_max_position_risk = g_reply.exceeds_max_position_risk;
      if(g_reply.action != "") g_dec.primary_action = g_reply.action;
     }

   g_last_action = g_dec.primary_action;
   g_note = g_dec.risk_warning;
  }

void MaybeNotifyRiskState(const datetime closed_time)
  {
   string key = g_dec.existing_position_decision + "|" + g_dec.risk_status + "|" +
                (g_dec.exceeds_max_position_risk ? "1" : "0");
   if(key == g_last_risk_notify_key)
      return;
   if(g_dec.risk_status == "CRITICAL" || g_dec.exceeds_max_position_risk ||
      g_dec.existing_position_decision == "CRITICAL_RISK" ||
      g_dec.existing_position_decision == "HOLD_WITH_CAUTION" ||
      g_dec.existing_position_decision == "EXIT_WARNING")
     {
      string msg = g_dec.risk_warning;
      if(msg == "")
         msg = "Existing=" + g_dec.existing_position_decision + " Risk=" + g_dec.risk_status +
               " EquityRisk=" + DoubleToString(g_risk.equity_risk_pct, 2) + "%";
      g_notify.MaybeNotify(g_dec.primary_action, msg, closed_time);
      g_last_risk_notify_key = key;
     }
  }

void RefreshEquityMetrics(void)
  {
   VantageLoadAccountInfo(g_acct);
   g_balance = g_acct.balance;
   g_equity = g_acct.equity;
   g_floating_pl_pct = 0.0;
   g_float_profit_target_hit = false;
   if(g_equity > 0.0)
      g_floating_pl_pct = (g_pos.total_floating_pl / g_equity) * 100.0;
   if(g_pos.has_position && g_floating_pl_pct >= InpFloatProfitTargetPct && InpFloatProfitTargetPct > 0.0)
      g_float_profit_target_hit = true;
  }

void MaybeNotifyFloatProfitTarget(const datetime closed_time)
  {
   string key = g_float_profit_target_hit ? "HIT" : "OK";
   if(key == g_last_float_profit_notify_key)
      return;
   if(g_float_profit_target_hit)
     {
      string msg = "Floating profit " + DoubleToString(g_floating_pl_pct, 2) +
                   "% of equity (target " + DoubleToString(InpFloatProfitTargetPct, 1) +
                   "%). Consider limiting/taking profit — advisory only.";
      g_notify.MaybeNotify("FLOAT_PROFIT_TARGET", msg, closed_time);
     }
   g_last_float_profit_notify_key = key;
  }

//+------------------------------------------------------------------+
//| Update risk from first open position (read-only)                 |
//+------------------------------------------------------------------+
void RefreshRisk(void)
  {
   ZeroMemory(g_risk);
   g_risk.status = "RISK_CALCULATION_UNAVAILABLE";
   g_risk.available = false;
   if(!g_pos.has_position)
     {
      g_risk.status = "OK";
      g_risk.available = true;
      RefreshEquityMetrics();
      return;
     }
   VantageCalcRiskFromOpenPosition(_Symbol, g_spec, g_pos.rows[0], g_risk);
   RefreshEquityMetrics();
  }

//+------------------------------------------------------------------+
//| Local closed-bar processing for Strategy Tester / replay         |
//+------------------------------------------------------------------+
void ProcessReplayBar(const datetime closed_time)
  {
   g_candle_status = "REPLAY";
   g_note = "";
   g_backend_status = "LOCAL_REPLAY";
   ZeroMemory(g_reply);
   g_reply.ok = false;
   RefreshActiveLevels(false);

   if(!g_analysis.HasEnoughHistory(220))
     {
      g_candle_status = "INCOMPLETE_HISTORY";
      g_last_action = "DATA_UNAVAILABLE";
      g_note = "Need more M30 history for EMA200 / structure.";
      WriteBacktestSignalRow(closed_time);
      return;
     }

   if(!g_analysis.BuildSnapshot(g_tech))
     {
      g_last_action = "DATA_UNAVAILABLE";
      g_note = "Failed to build technical snapshot.";
      WriteBacktestSignalRow(closed_time);
      return;
     }

   if(!VantageCapturePrices(_Symbol, InpMaxSpreadPoints, g_px))
     {
      // In tester, tick may be sparse — fall back to bar close
      g_px.bid = g_tech.close;
      g_px.ask = g_tech.close;
      g_px.spread_points = 0;
      g_px.high_spread = false;
     }

   VantageLoadPositions(_Symbol, g_pos);
   RefreshRisk();
   RebuildDecisionState(false); // local rules only — no WebRequest

   if(g_px.high_spread || g_dec.exceeds_max_position_risk || g_dec.risk_status == "CRITICAL")
     {
      g_dec.new_position_allowed = false;
      g_dec.add_position_allowed = false;
      if(g_dec.new_entry_decision == "BUY_ALLOWED" || g_dec.new_entry_decision == "SELL_ALLOWED")
         g_dec.new_entry_decision = (g_px.high_spread ? "HIGH_SPREAD" : "RISK_BLOCKED");
      if(g_dec.new_entry_decision == "HIGH_SPREAD")
         g_dec.primary_action = "HIGH_SPREAD";
      else if(g_dec.new_entry_decision == "RISK_BLOCKED")
         g_dec.primary_action = "NO_NEW_TRADE";
     }

   g_last_action = g_dec.primary_action;
   g_last_request_candle = closed_time;
   WriteBacktestSignalRow(closed_time);

   if(!InpShowDashboard || (bool)MQLInfoInteger(MQL_OPTIMIZATION))
      return;
   Comment("Vantage SIGNAL REPLAY | ", _Symbol, " M30\n",
           TimeToString(closed_time, TIME_DATE | TIME_MINUTES),
           " | ", g_dec.primary_action,
           " | entry=", g_dec.new_entry_decision,
           " | trend=", g_dec.trend,
           "\nCSV rows=", IntegerToString(g_bt_rows),
           " BUY=", IntegerToString(g_bt_buy),
           " SELL=", IntegerToString(g_bt_sell),
           "\nAdvisory only — no orders.");
  }

//+------------------------------------------------------------------+
//| Core closed-candle analysis cycle                                |
//+------------------------------------------------------------------+
void ProcessClosedCandle(const datetime closed_time)
  {
   if(g_replay_mode)
     {
      ProcessReplayBar(closed_time);
      return;
     }
   g_candle_status = "CLOSED_READY";
   g_note = "";
   RefreshActiveLevels(false);

   if(!g_analysis.HasEnoughHistory(220))
     {
      g_candle_status = "INCOMPLETE_HISTORY";
      g_last_action = "DATA_UNAVAILABLE";
      g_note = "Need more M30 history for EMA200 / structure.";
      return;
     }

   if(!g_analysis.BuildSnapshot(g_tech))
     {
      g_last_action = "DATA_UNAVAILABLE";
      g_note = "Failed to build technical snapshot from broker candles.";
      return;
     }

   if(!VantageCapturePrices(_Symbol, InpMaxSpreadPoints, g_px))
     {
      g_last_action = "DATA_UNAVAILABLE";
      g_note = "Failed to read broker tick.";
      return;
     }

   VantageLoadPositions(_Symbol, g_pos);
   VantageLoadPendingOrders(_Symbol, g_spec, g_px, g_pending);
   RefreshRisk();

   string environment = "NORMAL";
   if(g_px.high_spread)
      environment = "HIGH_SPREAD";
   if(g_spec.trade_mode == SYMBOL_TRADE_MODE_DISABLED)
      environment = "CLOSED_MARKET";

   if(g_last_request_candle == closed_time)
     {
      RebuildDecisionState(true);
      g_note = "Already analyzed this closed candle.";
      return;
     }

   string payload = BuildAnalyzePayload(g_tech, g_px, g_pos, g_risk, environment);
   VantageBackendReply reply;
   bool ok = g_backend.Analyze(payload, reply, InpMaxResponseAgeSec);
   g_last_request_candle = closed_time;
   g_reply = reply;

   if(!ok)
     {
      g_backend_status = "OFFLINE/ERR";
      g_note = g_backend.LastError();
      RebuildDecisionState(false);
      if(g_backend_status == "OFFLINE/ERR")
         g_dec.primary_action = "BACKEND_OFFLINE";
      g_last_action = g_dec.primary_action;
      MaybeNotifyRiskState(closed_time);
      MaybeNotifyFloatProfitTarget(closed_time);
      return;
     }

   g_backend_status = "OK";
   RebuildDecisionState(true);

   // Suppress new-entry allowances under high spread / critical risk (local hard gate)
   if(g_px.high_spread || g_dec.exceeds_max_position_risk || g_dec.risk_status == "CRITICAL")
     {
      g_dec.new_position_allowed = false;
      g_dec.add_position_allowed = false;
      if(g_dec.new_entry_decision == "BUY_ALLOWED" || g_dec.new_entry_decision == "SELL_ALLOWED")
         g_dec.new_entry_decision = (g_px.high_spread ? "HIGH_SPREAD" : "RISK_BLOCKED");
     }

   g_last_action = g_dec.primary_action;
   MaybeNotifyRiskState(closed_time);
   MaybeNotifyFloatProfitTarget(closed_time);
  }

//+------------------------------------------------------------------+
//| Refresh dashboard each timer tick                                |
//+------------------------------------------------------------------+
void RefreshDashboard(void)
  {
   if(!InpShowDashboard)
      return;
   VantageCapturePrices(_Symbol, InpMaxSpreadPoints, g_px);
   VantageLoadPositions(_Symbol, g_pos);
   RefreshRisk();
   RefreshPlCalendar(false);
   if(g_analysis.HasEnoughHistory(220))
      g_analysis.BuildSnapshot(g_tech);
   // Keep local risk classification fresh even between closed-candle analyzes
   RebuildDecisionState(g_reply.ok);

   string age = "n/a";
   if(g_reply.received_local > 0)
      age = IntegerToString((int)(TimeLocal() - g_reply.received_local)) + "s";
   string ts = (g_reply.timestamp_utc != "" ? g_reply.timestamp_utc : "n/a");

   MaybeEvalPullback(false);
   g_dash.Render(g_acct, g_spec, g_px, g_backend_status, g_candle_status, g_dec,
                 g_pos, g_risk, ts, age,
                 g_equity, g_floating_pl_pct, InpFloatProfitTargetPct, g_float_profit_target_hit,
                 g_pl_cal.year, g_pl_cal.month, g_pl_cal.month_pl, g_pl_cal.month_pct, g_pl_cal.month_deals,
                 g_trade_stats, g_pbsnap, InpPbShowDash && InpPullbackEnable);
  }

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(!EnforceAdvisoryMode())
      return INIT_FAILED;

   g_replay_mode = IsReplayMode();

   Print("[VantageAI] Starting Vantage MT5 AI Decision Assistant v", VANTAGE_AI_VERSION,
         " | ADVISORY-ONLY | Symbol=", _Symbol,
         (g_replay_mode ? " | SIGNAL REPLAY MODE" : " | LIVE/BACKEND MODE"));

   VantageLoadAccountInfo(g_acct);
   if(!g_replay_mode)
      VantageLogAccountDiagnostics(g_acct);

   // Always use attached chart symbol — never auto-switch
   if(!VantageLoadSymbolSpec(_Symbol, g_spec))
     {
      Print("[VantageAI] Symbol spec failed: ", g_spec.error);
      return INIT_FAILED;
     }
   VantageLogSymbolSpec(g_spec);
   if(!g_replay_mode)
      VantageLogXauusdReferenceProfile(_Symbol, g_spec);

   if(InpRunGoldDiscovery && !g_replay_mode)
     {
      string list = "";
      string first = VantageDiscoverGoldCandidates(list);
      Print("[VantageAI] Gold discovery (info only, chart unchanged): ", list,
            " | chart symbol in use: ", _Symbol, " | first candidate: ", first);
     }

   if(!g_analysis.Init(_Symbol, PERIOD_M30))
      return INIT_FAILED;

   if(InpM5DeskEnable)
     {
      if(!g_m5desk.Init(_Symbol,
                        InpM5DeskNewsBefore,
                        InpM5DeskNewsAfter,
                        InpM5DeskMinAdx,
                        InpM5DeskMinRR,
                        InpM5DeskRiskPct,
                        InpM5DeskMaxSetupAge))
         Print("[VantageAI] M5 Alignment Desk init failed — /dashboard gates will stay unknown.");
      else
         Print("[VantageAI] M5 Alignment Desk enabled (H1/M15/M5 feed → /dashboard).");
     }

   if(InpPullbackEnable)
     {
      VantagePullbackConfig pcfg;
      FillPullbackConfig(pcfg);
      if(!g_pullback.Init(_Symbol, pcfg))
         Print("[VantageAI] Pullback Probability Analyzer init failed.");
      else
         MaybeEvalPullback(true);
     }

   // Build chart-relative levels for BTC/etc. (AUTO) or gold manual map
   if(g_analysis.HasEnoughHistory(50))
      g_analysis.BuildSnapshot(g_tech);
   RefreshActiveLevels(true);

   g_backend.Configure(InpBackendUrl, InpBearerToken, InpHttpTimeoutMs);
   g_notify.Configure(InpPushNotify && !g_replay_mode, InpNotifyCooldownSec);

   if(g_replay_mode)
     {
      g_backend_status = "LOCAL_REPLAY";
      OpenBacktestCsv();
      // Start at 0 so the first closed M30 bar in the test range is logged
      g_last_closed_candle = 0;
      Print("[VantageAI] Replay ready. Strategy Tester will log local signals (no WebRequest, no orders).");
      return INIT_SUCCEEDED;
     }

   string health = "";
   if(g_backend.Health(health))
      g_backend_status = "OK";
   else
     {
      g_backend_status = "OFFLINE";
      g_note = g_backend.LastError();
      Print("[VantageAI] Backend health failed: ", g_note);
     }

   if(InpRunDiagnostics)
      VantageRunDiagnostics(_Symbol, g_spec, g_acct, g_backend, InpMaxSpreadPoints);

   // Seed last closed candle so we don't spam on attach mid-bar
   datetime t[];
   if(CopyTime(_Symbol, PERIOD_M30, 1, 1, t) == 1)
      g_last_closed_candle = t[0];

   EventSetTimer(MathMax(1, InpTimerSec));
   RefreshPlCalendar(true);
   MaybeSendHeartbeat();
   RefreshDashboard();
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| Expert deinitialization                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(g_replay_mode)
     {
      CloseBacktestCsv();
      PrintBacktestSummary();
     }
   g_analysis.Release();
   g_m5desk.Release();
   g_pullback.Release();
   g_dash.Clear();
   Comment("");
   Print("[VantageAI] Stopped. reason=", reason);
  }

//+------------------------------------------------------------------+
//| Tester end — flush summary                                       |
//+------------------------------------------------------------------+
double OnTester()
  {
   CloseBacktestCsv();
   PrintBacktestSummary();
   // Custom criterion: count of actionable watches (not P/L — advisory EA)
   return (double)(g_bt_buy + g_bt_sell);
  }

//+------------------------------------------------------------------+
//| Timer — detect newly closed M30 broker candle (live only)        |
//+------------------------------------------------------------------+
void OnTimer()
  {
   if(g_replay_mode)
      return;

   datetime t[];
   if(CopyTime(_Symbol, PERIOD_M30, 1, 1, t) != 1)
     {
      g_candle_status = "DATA_UNAVAILABLE";
      RefreshDashboard();
      return;
     }

   if(t[0] != g_last_closed_candle)
     {
      g_last_closed_candle = t[0];
      ProcessClosedCandle(t[0]);
     }
   else
     {
      g_candle_status = "WAITING";
      VantageCapturePrices(_Symbol, InpMaxSpreadPoints, g_px);
      VantageLoadPositions(_Symbol, g_pos);
      RefreshRisk();
      if(g_analysis.HasEnoughHistory(220))
         g_analysis.BuildSnapshot(g_tech);
      RebuildDecisionState(g_reply.ok);
      if(g_px.high_spread)
         MaybeNotifyRiskState(g_last_closed_candle);
      MaybeNotifyFloatProfitTarget(g_last_closed_candle);
     }
   RefreshDashboard();
   MaybeSendHeartbeat();
  }

//+------------------------------------------------------------------+
//| Tick — live: prices only; replay: drive closed M30 bars          |
//+------------------------------------------------------------------+
void OnTick()
  {
   if(!g_replay_mode)
      return; // live analysis waits for closed candle via OnTimer

   datetime t[];
   if(CopyTime(_Symbol, PERIOD_M30, 1, 1, t) != 1)
      return;

   if(t[0] == g_last_closed_candle)
      return;

   g_last_closed_candle = t[0];
   ProcessReplayBar(t[0]);
  }

//+------------------------------------------------------------------+
//| End of advisory EA — no trade execution symbols below this line  |
//+------------------------------------------------------------------+
