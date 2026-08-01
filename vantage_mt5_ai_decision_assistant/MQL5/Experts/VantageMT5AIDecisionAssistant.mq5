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
#include <VantageAI/VantageGoldSMC.mqh>
#include <VantageAI/VantageLiquidityGrab.mqh>
#include <VantageAI/VantageBreakoutStructure.mqh>
#include <VantageAI/VantageMarketStateManager.mqh>
#include <VantageAI/VantageSwingStrategy.mqh>

//--- Explicit compile-time advisory guard (do not import Trade.mqh / CTrade)
#ifdef __MQL5__
  // Intentionally no #include <Trade/Trade.mqh>
#endif

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input group "A. Backend (local FastAPI)"
input string InpBackendUrl        = "http://187.77.142.118:8000"; // Backend base URL (VPS)
input string InpBearerToken       = "2ZGrxytB0N3X6AMWK4ghT8uwklcq5FPCsvEmj9Hzibnpf1LI"; // LOCAL_API_TOKEN — match backend/.env
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
input bool   InpApiOnlyUi         = false;  // Hide chart HUD/lines; data still sent via heartbeat/API
input bool   InpChartHideHorizontalLines = true; // Hide H-lines/trendlines; keep Gold SMC vertical zones
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

input group "M. Gold SMC Intelligence — Symbol Gate"
input bool   InpGoldSmcEnable       = true;
input string InpGoldSmcAliases      = "XAUUSD,GOLD"; // Comma-separated base aliases
input bool   InpGoldSmcAllowSuffix  = true;          // Allow .a .pro glued m etc.
input bool   InpGoldSmcAllowPrefix  = true;          // Allow m. / a_ prefixes
input bool   InpGoldSmcShowWarn     = true;          // Show non-gold disable warning on HUD
input bool   InpGoldSmcShowDash     = true;
input bool   InpGoldSmcShowChartObj = true;          // Draw VAI_GSMC_* chart objects

input group "N. Gold SMC Intelligence — Timeframes"
input ENUM_TIMEFRAMES InpGoldSmcTF_D1  = PERIOD_D1;
input ENUM_TIMEFRAMES InpGoldSmcTF_H4  = PERIOD_H4;
input ENUM_TIMEFRAMES InpGoldSmcTF_H1  = PERIOD_H1;
input ENUM_TIMEFRAMES InpGoldSmcTF_M15 = PERIOD_M15;
input ENUM_TIMEFRAMES InpGoldSmcTF_M5  = PERIOD_M5;
input ENUM_TIMEFRAMES InpGoldSmcTF_M1  = PERIOD_M1;

input group "O. Gold SMC Intelligence — Structure (Phase 2)"
input int    InpGoldSmcSwingLExt   = 5;      // External swing left bars
input int    InpGoldSmcSwingRExt   = 5;      // External swing right bars
input int    InpGoldSmcSwingLInt   = 2;      // Internal swing left bars
input int    InpGoldSmcSwingRInt   = 2;      // Internal swing right bars
input int    InpGoldSmcLookback    = 80;     // Structure lookback (closed bars)
input int    InpGoldSmcAtrPeriod   = 14;
input int    InpGoldSmcBreakMode   = 3;      // 0=wick 1=body 2=body+pen 3=body+disp (default)
input double InpGoldSmcMinPenAtr   = 0.05;   // Min close penetration in ATR
input double InpGoldSmcMinDispAtr  = 0.45;   // Body/ATR for displacement score
input double InpGoldSmcMinDispScore = 55.0;  // Min displacement score for BOS (0-100)

input group "P. Gold SMC Intelligence — Liquidity / Sessions (Phase 3)"
input int    InpGoldSmcUtcOffset   = 0;      // Broker/server hours ahead of UTC
input int    InpGoldSmcAsianStart  = 0;      // Asian start hour UTC
input int    InpGoldSmcAsianEnd    = 7;
input int    InpGoldSmcLondonStart = 7;
input int    InpGoldSmcLondonEnd   = 16;
input int    InpGoldSmcNyStart     = 12;
input int    InpGoldSmcNyEnd       = 21;
input bool   InpGoldSmcShowSession = true;
input bool   InpGoldSmcShowPrevDay = true;
input bool   InpGoldSmcShowPrevWk  = true;
input double InpGoldSmcEqualTolAtr = 0.08;   // Equal H/L tolerance (ATR)
input double InpGoldSmcApproachAtr = 0.35;   // Approaching distance (ATR)

input group "Q. Gold SMC Intelligence — FVG / Order Blocks (Phase 4)"
input double InpGoldSmcMinFvgAtr   = 0.12;   // Min FVG size (ATR)
input int    InpGoldSmcMaxFvg      = 6;
input int    InpGoldSmcMaxOb       = 6;
input bool   InpGoldSmcFvgNeedDisp = true;   // FVG requires displacement candle
input bool   InpGoldSmcObNeedDisp  = true;   // OB requires displacement
input bool   InpGoldSmcObPreferSwp = true;   // Prefer OB after liquidity sweep
input bool   InpGoldSmcEnableIFVG  = true;
input bool   InpGoldSmcEnableBrk   = true;
input int    InpGoldSmcObRefine    = 0;      // 0=full candle 1=body 2=CE band

input group "R. Gold SMC Intelligence — Context / OTE / PO3 (Phase 5)"
input bool   InpGoldSmcEnableOte   = true;
input double InpGoldSmcOteLow      = 0.618;  // OTE fib low (retracement)
input double InpGoldSmcOteMid      = 0.705;  // OTE fib mid (sweet spot)
input double InpGoldSmcOteHigh     = 0.790;  // OTE fib high
input bool   InpGoldSmcEnableInd   = true;   // Inducement heuristics
input bool   InpGoldSmcEnablePo3   = true;   // Power of Three (session-based)
input double InpGoldSmcDeepDisc    = 0.15;   // Deep discount ≤ this fraction of range
input double InpGoldSmcDeepPrem    = 0.85;   // Deep premium ≥ this fraction of range

input group "S. Gold SMC Intelligence — Setup Score (Phase 6)"
input double InpGoldSmcMinScore    = 45.0;   // Min score for named setup (else No Valid)
input double InpGoldSmcWHtf        = 15.0;   // Weight: H4/H1 alignment
input double InpGoldSmcWLiq        = 12.0;   // Weight: liquidity event
input double InpGoldSmcWDisp       = 12.0;   // Weight: displacement
input double InpGoldSmcWStruct     = 14.0;   // Weight: structure confirmation
input double InpGoldSmcWOb         = 10.0;   // Weight: order block
input double InpGoldSmcWFvg        = 8.0;    // Weight: FVG
input double InpGoldSmcWPd         = 7.0;    // Weight: premium/discount
input double InpGoldSmcWSess       = 5.0;    // Weight: session
input double InpGoldSmcWPdWk       = 4.0;    // Weight: PDH/PDL/PWH confluence
input double InpGoldSmcWOte        = 4.0;    // Weight: OTE
input double InpGoldSmcWLtf        = 6.0;    // Weight: LTF confirmation
input double InpGoldSmcWVol        = 3.0;    // Weight: spread/volatility

input group "T. Gold SMC Intelligence — Chart / Alerts (Phase 7)"
input bool   InpGoldSmcChartRange  = true;   // Dealing range + EQ + PD bands
input bool   InpGoldSmcChartLiq    = true;   // BSL/SSL + PDH/PDL/PWH/PWL
input bool   InpGoldSmcChartSess   = false;  // Asian/London/NY lines (can clutter)
input bool   InpGoldSmcChartPoi    = true;   // Primary POI rectangle
input bool   InpGoldSmcChartOte    = true;   // OTE zone
input bool   InpGoldSmcChartSetup  = true;   // Entry / invalidation / targets
input int    InpGoldSmcChartBars   = 80;     // Rectangle lookback bars
input bool   InpGoldSmcAlertEnable = false;
input bool   InpGoldSmcAlertPopup  = false;
input bool   InpGoldSmcAlertPush   = false;
input bool   InpGoldSmcAlertSound  = false;
input int    InpGoldSmcAlertCool   = 300;    // Alert cooldown seconds
input double InpGoldSmcAlertScore  = 75.0;   // Min score for confidence alert
input double InpGoldSmcAlertSpread = 120.0;  // Wide-spread alert (points)
input bool   InpGoldSmcDebug       = false;  // Verbose [GoldSMC][*] logs (Phase 8)

input group "U. Liquidity Grab Monitor — Core"
input bool   InpLiqGrabEnable      = true;   // Enable Liquidity Grab Detection
input bool   InpLiqGrabGoldOnly    = true;   // Gold / XAUUSD only
input string InpLiqGrabAliases     = "XAUUSD,GOLD";
input bool   InpLiqGrabAllowSuffix = true;
input bool   InpLiqGrabAllowPrefix = true;
input ENUM_TIMEFRAMES InpLiqGrabTFDetect = PERIOD_M5;
input ENUM_TIMEFRAMES InpLiqGrabTFConfirm = PERIOD_M5;
input ENUM_TIMEFRAMES InpLiqGrabTFConfirm2 = PERIOD_M15;
input ENUM_TIMEFRAMES InpLiqGrabTFContext = PERIOD_H1;
input ENUM_TIMEFRAMES InpLiqGrabTFMajor = PERIOD_H4;

input group "V. Liquidity Grab — Swings / ATR / Sweep"
input int    InpLiqGrabSwingLeft   = 3;
input int    InpLiqGrabSwingRight  = 3;
input int    InpLiqGrabAtrPeriod   = 14;
input double InpLiqGrabMinSweepAtr = 0.03;
input double InpLiqGrabMaxSweepAtr = 0.50;
input double InpLiqGrabSpreadMult  = 2.0;
input double InpLiqGrabEqualAtr    = 0.08;
input double InpLiqGrabApproachAtr = 0.35;
input double InpLiqGrabDispBodyAtr = 0.45;
input double InpLiqGrabStrongDisp  = 0.75;

input group "W. Liquidity Grab — Rejection / MSS"
input double InpLiqGrabMinWick     = 0.35;
input double InpLiqGrabWickBody    = 1.25;
input bool   InpLiqGrabCloseInside = true;
input int    InpLiqGrabRejectBars  = 1;
input bool   InpLiqGrabRequireMss  = true;
input bool   InpLiqGrabCloseMss    = true;
input int    InpLiqGrabMssBars      = 1;
input bool   InpLiqGrabInternalMss = true;
input int    InpLiqGrabConfirmWin  = 5;

input group "X. Liquidity Grab — Levels / Sessions"
input bool   InpLiqGrabPdLevels    = true;
input bool   InpLiqGrabPwLevels    = true;
input bool   InpLiqGrabSessions    = true;
input bool   InpLiqGrabSwings      = true;
input bool   InpLiqGrabEqual       = true;
input double InpLiqGrabMinStrength = 5.0;
input int    InpLiqGrabUtcOffset   = 0;
input int    InpLiqGrabAsianStart  = 0;
input int    InpLiqGrabAsianEnd    = 8;
input int    InpLiqGrabLondonStart = 7;
input int    InpLiqGrabLondonEnd   = 16;
input int    InpLiqGrabNyStart     = 12;
input int    InpLiqGrabNyEnd       = 21;
input bool   InpLiqGrabSessConf    = true;

input group "Y. Liquidity Grab — Score / News / Volume"
input bool   InpLiqGrabTickVol     = true;
input int    InpLiqGrabVolPeriod   = 20;
input double InpLiqGrabElevVol     = 1.35;
input double InpLiqGrabConfThresh  = 70.0;
input double InpLiqGrabHighConf    = 85.0;
input double InpLiqGrabCtPenalty   = 10.0;
input double InpLiqGrabNewsPenalty = 10.0;
input int    InpLiqGrabNewsBefore  = 15;
input int    InpLiqGrabNewsAfter   = 15;

input group "Z. Liquidity Grab — Chart / Alerts / HUD"
input bool   InpLiqGrabShowDash    = true;
input bool   InpLiqGrabChartObj    = true;
input int    InpLiqGrabChartBars   = 80;
input bool   InpLiqGrabAlertEnable = false;
input bool   InpLiqGrabAlertPopup  = false;
input bool   InpLiqGrabAlertPush   = false;
input bool   InpLiqGrabAlertSound  = false;
input int    InpLiqGrabAlertCool   = 300;
input bool   InpLiqGrabDebug       = false;

input group "AA. Breakout Structure — Core"
input bool   InpBosEnable          = true;
input bool   InpBosGoldOnly        = true;
input string InpBosAliases         = "XAUUSD,GOLD";
input bool   InpBosAllowSuffix     = true;
input bool   InpBosAllowPrefix     = true;

input group "AB. Breakout Structure — Timeframes"
input ENUM_TIMEFRAMES InpBosTF_H4  = PERIOD_H4;
input ENUM_TIMEFRAMES InpBosTF_H1  = PERIOD_H1;
input ENUM_TIMEFRAMES InpBosTF_M15 = PERIOD_M15;
input ENUM_TIMEFRAMES InpBosTF_M5  = PERIOD_M5;
input ENUM_TIMEFRAMES InpBosTF_M1  = PERIOD_M1;

input group "AC. Breakout Structure — Swings / BOS"
input int    InpBosSwingLeft       = 3;
input int    InpBosSwingRight      = 3;
input double InpBosMinSwingStr     = 20.0;
input int    InpBosAtrPeriod       = 14;
input double InpBosMinBosAtr       = 0.08;
input double InpBosMinBodyPct      = 0.45;

input group "AD. Breakout Structure — Trendline / Break / Retest"
input double InpBosMinBreakAtr    = 0.05;
input double InpBosMinBreakBody   = 0.40;
input int    InpBosMinTlTouches   = 3;
input double InpBosTlTouchAtr     = 0.12;
input int    InpBosRetestBars     = 8;
input double InpBosRetestTolAtr   = 0.15;

input group "AE. Breakout Structure — Scoring"
input double InpBosWStructure   = 20.0;
input double InpBosWTrendline   = 15.0;
input double InpBosWBreakout    = 15.0;
input double InpBosWRetest      = 15.0;
input double InpBosWFlip        = 10.0;
input double InpBosWLiquidity   = 10.0;
input double InpBosWFvg         = 5.0;
input double InpBosWOb          = 5.0;
input double InpBosWHtf         = 5.0;
input double InpBosRejectThresh = 75.0;

input group "AF. Breakout Structure — Chart / HUD"
input bool   InpBosShowDash     = true;
input bool   InpBosChartObj     = true;
input bool   InpBosAlertEnable  = false;
input int    InpBosAlertCool    = 300;
input bool   InpBosDebug        = false;

input group "AG. Market State Engine v2 — Core"
input bool   InpMseEnable       = true;
input bool   InpMseGoldOnly     = true;
input string InpMseAliases      = "XAUUSD,GOLD";

input group "AH. Market State — Timeframes"
input ENUM_TIMEFRAMES InpMseTF_H4  = PERIOD_H4;
input ENUM_TIMEFRAMES InpMseTF_H1  = PERIOD_H1;
input ENUM_TIMEFRAMES InpMseTF_M15 = PERIOD_M15;
input ENUM_TIMEFRAMES InpMseTF_M5  = PERIOD_M5;
input ENUM_TIMEFRAMES InpMseTF_M1  = PERIOD_M1;

input group "AI. Market State — Detection"
input int    InpMseSwingLeft    = 3;
input int    InpMseSwingRight   = 3;
input double InpMseMinSwingAtr  = 0.15;
input int    InpMseAtrPeriod    = 14;
input double InpMseMinBosAtr    = 0.08;
input double InpMseMinBodyPct   = 0.40;
input int    InpMseMinTlTouch   = 3;
input int    InpMseRetestBars   = 8;

input group "AJ. Market State — HUD / Chart"
input bool   InpMseShowDash     = true;
input bool   InpMseChartObj     = true;
input bool   InpMseDebug        = false;

input group "AK. Swing Strategy Engine — Core"
input bool   InpSwingEnable     = true;
input ENUM_SWING_STRAT_TRADE_MODE InpSwingTradeMode = SWING_TRADE_SWING; // Swing (multi-TF) or Scalping (M5 fast)
input bool   InpSwingGoldOnly   = true;
input string InpSwingAliases    = "XAUUSD,GOLD";

input group "AL. Swing Strategy — Timeframes"
input ENUM_TIMEFRAMES InpSwingTF_D1  = PERIOD_D1;
input ENUM_TIMEFRAMES InpSwingTF_H4  = PERIOD_H4;
input ENUM_TIMEFRAMES InpSwingTF_H1  = PERIOD_H1;
input ENUM_TIMEFRAMES InpSwingTF_M15 = PERIOD_M15;
input ENUM_TIMEFRAMES InpSwingTF_M5  = PERIOD_M5;

input group "AM. Swing Strategy — Detection"
input int    InpSwingDepthLeft  = 3;
input int    InpSwingDepthRight = 3;
input double InpSwingMinAtr     = 0.15;
input int    InpSwingMinCandles = 3;
input int    InpSwingAtrPeriod  = 14;
input double InpSwingAtrMult    = 0.35;
input double InpSwingMaxPbPct   = 68.0;
input double InpSwingMinBosAtr  = 0.08;
input double InpSwingMinBodyPct = 0.40;

input group "AN. Swing Strategy — Scoring / Risk"
input double InpSwingMinConf    = 72.0;
input double InpSwingMinRR      = 2.0;
input double InpSwingRsiBull    = 52.0;
input double InpSwingRsiBear    = 48.0;
input double InpSwingMacdMin    = 0.0;
input double InpSwingMinVolRat  = 1.05;

input group "AO. Swing Strategy — HUD / Chart"
input bool   InpSwingShowDash   = true;
input bool   InpSwingChartObj   = true;
input bool   InpSwingDebug      = false;

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
CVantageGoldSMC      g_goldsmc;
VantageGoldSMCResult g_gsmsnap;
CVantageLiquidityGrab g_liqgrab;
VantageLiquidityGrabResult g_liqgrabsnap;
CVantageBreakoutStructure g_breakout;
VantageBosResult g_bossnap;
CMarketStateManager g_marketstate;
VantageMseResult g_msesnap;
CVantageSwingStrategy g_swingstrat;
VantageSwingStratResult g_swingsnap;

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
//| Chart UI gates — InpApiOnlyUi hides all on-chart visuals         |
//+------------------------------------------------------------------+
bool WantMainDashboard(void)
  {
   return InpShowDashboard && !InpApiOnlyUi;
  }

bool WantModuleDashboard(void)
  {
   return !InpApiOnlyUi;
  }

bool WantModuleChart(void)
  {
   return !InpApiOnlyUi;
  }

bool WantChartHorizontalLines(void)
  {
   return !InpChartHideHorizontalLines && WantModuleChart();
  }

void ClearHorizontalChartLines(void)
  {
   const int total = ObjectsTotal(0, 0, -1);
   for(int i = total - 1; i >= 0; i--)
     {
      const string name = ObjectName(0, i, 0, -1);
      if(StringFind(name, "VAI_") != 0)
         continue;
      const long typ = ObjectGetInteger(0, name, OBJPROP_TYPE);
      if(typ == OBJ_HLINE || typ == OBJ_TREND)
         ObjectDelete(0, name);
     }
   ChartRedraw(0);
  }

void ClearAllChartVisuals(void)
  {
   g_dash.Clear();
   Comment("");
   const int total = ObjectsTotal(0, 0, -1);
   for(int i = total - 1; i >= 0; i--)
     {
      const string name = ObjectName(0, i, 0, -1);
      if(StringFind(name, "VAI_") == 0)
         ObjectDelete(0, name);
     }
   ChartRedraw(0);
  }

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
   if(g_gsmsnap.valid)
      j += ",\"gold_smc\":" + g_goldsmc.ToJson(g_gsmsnap);
   if(g_liqgrabsnap.valid)
      j += ",\"liquidity_grab\":" + g_liqgrab.ToJson(g_liqgrabsnap);
   if(g_bossnap.valid)
      j += ",\"breakout_structure\":" + g_breakout.ToJson(g_bossnap);
   if(g_msesnap.valid)
      j += ",\"market_state_engine\":" + g_marketstate.ToJson(g_msesnap);
   if(g_swingsnap.valid)
      j += ",\"swing_strategy\":" + g_swingstrat.ToJson(g_swingsnap);
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
   cfg.show_chart_objects = InpPbShowChartObj && WantModuleChart();
   cfg.show_dashboard = InpPbShowDash && WantModuleDashboard();
   cfg.show_hlines = WantChartHorizontalLines();
  }

void MaybeEvalPullback(const bool force)
  {
   if(!InpPullbackEnable)
      return;
   VantagePullbackResult r;
   if(g_pullback.Evaluate(force, r))
      g_pbsnap = r;
  }

void FillGoldSmcConfig(VantageGoldSMCConfig &cfg)
  {
   ZeroMemory(cfg);
   cfg.enable = InpGoldSmcEnable;
   cfg.approved_aliases = InpGoldSmcAliases;
   cfg.allow_broker_suffix = InpGoldSmcAllowSuffix;
   cfg.allow_broker_prefix = InpGoldSmcAllowPrefix;
   cfg.show_nongold_warning = InpGoldSmcShowWarn && WantModuleDashboard();
   cfg.show_dashboard = InpGoldSmcShowDash && WantModuleDashboard();
   const bool gsm_chart = WantModuleChart() && InpGoldSmcShowChartObj;
   cfg.show_chart_objects = gsm_chart;
   cfg.chart_show_hlines = WantChartHorizontalLines();
   cfg.tf_macro = InpGoldSmcTF_D1;
   cfg.tf_major = InpGoldSmcTF_H4;
   cfg.tf_bias = InpGoldSmcTF_H1;
   cfg.tf_confirm = InpGoldSmcTF_M15;
   cfg.tf_exec = InpGoldSmcTF_M5;
   cfg.tf_precision = InpGoldSmcTF_M1;
   cfg.swing_left_ext = InpGoldSmcSwingLExt;
   cfg.swing_right_ext = InpGoldSmcSwingRExt;
   cfg.swing_left_int = InpGoldSmcSwingLInt;
   cfg.swing_right_int = InpGoldSmcSwingRInt;
   cfg.structure_lookback = InpGoldSmcLookback;
   cfg.atr_period = InpGoldSmcAtrPeriod;
   int bm = InpGoldSmcBreakMode;
   if(bm < 0) bm = 0;
   if(bm > 3) bm = 3;
   cfg.break_mode = (ENUM_SMC_BREAK_MODE)bm;
   cfg.min_close_penetration_atr = InpGoldSmcMinPenAtr;
   cfg.min_displacement_atr = InpGoldSmcMinDispAtr;
   cfg.min_displacement_score = InpGoldSmcMinDispScore;
   cfg.server_utc_offset_hours = InpGoldSmcUtcOffset;
   cfg.asian_start_hour_utc = InpGoldSmcAsianStart;
   cfg.asian_end_hour_utc = InpGoldSmcAsianEnd;
   cfg.london_start_hour_utc = InpGoldSmcLondonStart;
   cfg.london_end_hour_utc = InpGoldSmcLondonEnd;
   cfg.ny_start_hour_utc = InpGoldSmcNyStart;
   cfg.ny_end_hour_utc = InpGoldSmcNyEnd;
   cfg.show_session_liquidity = InpGoldSmcShowSession;
   cfg.show_prev_day_liquidity = InpGoldSmcShowPrevDay;
   cfg.show_prev_week_liquidity = InpGoldSmcShowPrevWk;
   cfg.equal_tol_atr = InpGoldSmcEqualTolAtr;
   cfg.approach_atr = InpGoldSmcApproachAtr;
   cfg.min_fvg_atr = InpGoldSmcMinFvgAtr;
   cfg.max_fvgs = InpGoldSmcMaxFvg;
   cfg.max_obs = InpGoldSmcMaxOb;
   cfg.fvg_require_displacement = InpGoldSmcFvgNeedDisp;
   cfg.ob_require_displacement = InpGoldSmcObNeedDisp;
   cfg.ob_prefer_sweep_origin = InpGoldSmcObPreferSwp;
   cfg.enable_inverse_fvg = InpGoldSmcEnableIFVG;
   cfg.enable_breaker = InpGoldSmcEnableBrk;
   cfg.ob_refinement_mode = InpGoldSmcObRefine;
   cfg.enable_ote = InpGoldSmcEnableOte;
   cfg.ote_low_pct = InpGoldSmcOteLow;
   cfg.ote_mid_pct = InpGoldSmcOteMid;
   cfg.ote_high_pct = InpGoldSmcOteHigh;
   cfg.enable_inducement = InpGoldSmcEnableInd;
   cfg.enable_po3 = InpGoldSmcEnablePo3;
   cfg.deep_discount_pct = InpGoldSmcDeepDisc;
   cfg.deep_premium_pct = InpGoldSmcDeepPrem;
   cfg.min_setup_score = InpGoldSmcMinScore;
   cfg.w_htf_align = InpGoldSmcWHtf;
   cfg.w_liquidity = InpGoldSmcWLiq;
   cfg.w_displacement = InpGoldSmcWDisp;
   cfg.w_structure = InpGoldSmcWStruct;
   cfg.w_order_block = InpGoldSmcWOb;
   cfg.w_fvg = InpGoldSmcWFvg;
   cfg.w_premium_discount = InpGoldSmcWPd;
   cfg.w_session = InpGoldSmcWSess;
   cfg.w_pd_week = InpGoldSmcWPdWk;
   cfg.w_ote = InpGoldSmcWOte;
   cfg.w_ltf = InpGoldSmcWLtf;
   cfg.w_vol_spread = InpGoldSmcWVol;
   cfg.chart_show_range = gsm_chart && InpGoldSmcChartRange;
   cfg.chart_show_liquidity = gsm_chart && InpGoldSmcChartLiq;
   cfg.chart_show_sessions = gsm_chart && InpGoldSmcChartSess;
   cfg.chart_show_poi = gsm_chart && InpGoldSmcChartPoi;
   cfg.chart_show_ote = gsm_chart && InpGoldSmcChartOte;
   cfg.chart_show_setup = gsm_chart && InpGoldSmcChartSetup;
   cfg.chart_lookback_bars = InpGoldSmcChartBars;
   cfg.alert_enable = InpGoldSmcAlertEnable;
   cfg.alert_popup = InpGoldSmcAlertPopup;
   cfg.alert_push = InpGoldSmcAlertPush && !g_replay_mode;
   cfg.alert_sound = InpGoldSmcAlertSound;
   cfg.alert_cooldown_sec = InpGoldSmcAlertCool;
   cfg.alert_min_score = InpGoldSmcAlertScore;
   cfg.alert_spread_points = InpGoldSmcAlertSpread;
   cfg.debug_log = InpGoldSmcDebug;
}

void MaybeEvalGoldSmc(const bool force)
  {
   VantageGoldSMCResult r;
   if(g_goldsmc.Evaluate(force, r))
      g_gsmsnap = r;
  }

void FillLiquidityGrabConfig(VantageLiquidityGrabConfig &cfg)
  {
   ZeroMemory(cfg);
   cfg.enable = InpLiqGrabEnable;
   cfg.gold_only = InpLiqGrabGoldOnly;
   cfg.approved_aliases = InpLiqGrabAliases;
   cfg.allow_broker_suffix = InpLiqGrabAllowSuffix;
   cfg.allow_broker_prefix = InpLiqGrabAllowPrefix;
   cfg.tf_detect = InpLiqGrabTFDetect;
   cfg.tf_confirm = InpLiqGrabTFConfirm;
   cfg.tf_confirm2 = InpLiqGrabTFConfirm2;
   cfg.tf_context = InpLiqGrabTFContext;
   cfg.tf_major = InpLiqGrabTFMajor;
   cfg.swing_left = InpLiqGrabSwingLeft;
   cfg.swing_right = InpLiqGrabSwingRight;
   cfg.atr_period = InpLiqGrabAtrPeriod;
   cfg.min_sweep_atr = InpLiqGrabMinSweepAtr;
   cfg.max_sweep_atr = InpLiqGrabMaxSweepAtr;
   cfg.spread_mult = InpLiqGrabSpreadMult;
   cfg.equal_level_atr_mult = InpLiqGrabEqualAtr;
   cfg.approach_atr = InpLiqGrabApproachAtr;
   cfg.disp_body_atr = InpLiqGrabDispBodyAtr;
   cfg.strong_disp_atr = InpLiqGrabStrongDisp;
   cfg.min_wick_ratio = InpLiqGrabMinWick;
   cfg.min_wick_body_ratio = InpLiqGrabWickBody;
   cfg.require_close_back = InpLiqGrabCloseInside;
   cfg.rejection_confirm_bars = InpLiqGrabRejectBars;
   cfg.require_mss = InpLiqGrabRequireMss;
   cfg.require_close_mss = InpLiqGrabCloseMss;
   cfg.mss_confirm_bars = InpLiqGrabMssBars;
   cfg.allow_internal_mss = InpLiqGrabInternalMss;
   cfg.enable_pdh_pdl = InpLiqGrabPdLevels;
   cfg.enable_pwh_pwl = InpLiqGrabPwLevels;
   cfg.enable_session = InpLiqGrabSessions;
   cfg.enable_swing = InpLiqGrabSwings;
   cfg.enable_equal = InpLiqGrabEqual;
   cfg.min_level_strength = InpLiqGrabMinStrength;
   cfg.server_utc_offset_hours = InpLiqGrabUtcOffset;
   cfg.asian_start_utc = InpLiqGrabAsianStart;
   cfg.asian_end_utc = InpLiqGrabAsianEnd;
   cfg.london_start_utc = InpLiqGrabLondonStart;
   cfg.london_end_utc = InpLiqGrabLondonEnd;
   cfg.ny_start_utc = InpLiqGrabNyStart;
   cfg.ny_end_utc = InpLiqGrabNyEnd;
   cfg.session_confluence = InpLiqGrabSessConf;
   cfg.enable_tick_volume = InpLiqGrabTickVol;
   cfg.volume_avg_period = InpLiqGrabVolPeriod;
   cfg.elevated_volume_ratio = InpLiqGrabElevVol;
   cfg.confirmed_threshold = InpLiqGrabConfThresh;
   cfg.high_conf_threshold = InpLiqGrabHighConf;
   cfg.countertrend_penalty = InpLiqGrabCtPenalty;
   cfg.news_penalty = InpLiqGrabNewsPenalty;
   cfg.news_before_min = InpLiqGrabNewsBefore;
   cfg.news_after_min = InpLiqGrabNewsAfter;
   cfg.confirm_window_bars = InpLiqGrabConfirmWin;
   cfg.alert_enable = InpLiqGrabAlertEnable;
   cfg.alert_popup = InpLiqGrabAlertPopup;
   cfg.alert_push = InpLiqGrabAlertPush && !g_replay_mode;
   cfg.alert_sound = InpLiqGrabAlertSound;
   cfg.alert_cooldown_sec = InpLiqGrabAlertCool;
   cfg.show_chart_objects = InpLiqGrabChartObj && WantModuleChart();
   cfg.show_dashboard = InpLiqGrabShowDash && WantModuleDashboard();
   cfg.show_hlines = WantChartHorizontalLines();
   cfg.chart_retention_bars = InpLiqGrabChartBars;
   cfg.debug_log = InpLiqGrabDebug;
  }

void MaybeEvalLiquidityGrab(const bool force)
  {
   VantageLiquidityGrabResult r;
   if(g_liqgrab.Evaluate(force, r))
      g_liqgrabsnap = r;
  }

void FillBreakoutStructureConfig(VantageBosConfig &cfg)
  {
   ZeroMemory(cfg);
   cfg.enable = InpBosEnable;
   cfg.gold_only = InpBosGoldOnly;
   cfg.approved_aliases = InpBosAliases;
   cfg.allow_broker_suffix = InpBosAllowSuffix;
   cfg.allow_broker_prefix = InpBosAllowPrefix;
   cfg.tf_primary_h4 = InpBosTF_H4;
   cfg.tf_primary_h1 = InpBosTF_H1;
   cfg.tf_primary_m15 = InpBosTF_M15;
   cfg.tf_entry_m5 = InpBosTF_M5;
   cfg.tf_entry_m1 = InpBosTF_M1;
   cfg.swing_left = InpBosSwingLeft;
   cfg.swing_right = InpBosSwingRight;
   cfg.min_swing_strength = InpBosMinSwingStr;
   cfg.atr_period = InpBosAtrPeriod;
   cfg.min_bos_atr = InpBosMinBosAtr;
   cfg.min_body_pct = InpBosMinBodyPct;
   cfg.min_break_atr = InpBosMinBreakAtr;
   cfg.min_body_break_pct = InpBosMinBreakBody;
   cfg.min_tl_touches = InpBosMinTlTouches;
   cfg.tl_touch_atr = InpBosTlTouchAtr;
   cfg.min_tl_strength = 40.0;
   cfg.retest_max_bars = InpBosRetestBars;
   cfg.retest_tolerance_atr = InpBosRetestTolAtr;
   cfg.w_structure = InpBosWStructure;
   cfg.w_trendline = InpBosWTrendline;
   cfg.w_breakout = InpBosWBreakout;
   cfg.w_retest = InpBosWRetest;
   cfg.w_flip = InpBosWFlip;
   cfg.w_liquidity = InpBosWLiquidity;
   cfg.w_fvg = InpBosWFvg;
   cfg.w_ob = InpBosWOb;
   cfg.w_htf = InpBosWHtf;
   cfg.w_session = 5.0;
   cfg.reject_threshold = InpBosRejectThresh;
   cfg.show_chart = InpBosChartObj && WantModuleChart();
   cfg.show_dashboard = InpBosShowDash && WantModuleDashboard();
   cfg.show_hlines = WantChartHorizontalLines();
   cfg.alert_enable = InpBosAlertEnable;
   cfg.alert_cooldown_sec = InpBosAlertCool;
   cfg.debug_log = InpBosDebug;
  }

void MaybeEvalBreakoutStructure(const bool force)
  {
   VantageBosResult r;
   if(g_breakout.Evaluate(force, r))
      g_bossnap = r;
  }

void FillMarketStateConfig(VantageMseConfig &cfg)
  {
   ZeroMemory(cfg);
   cfg.enable = InpMseEnable;
   cfg.gold_only = InpMseGoldOnly;
   cfg.approved_aliases = InpMseAliases;
   cfg.allow_suffix = true;
   cfg.allow_prefix = true;
   cfg.tf_h4 = InpMseTF_H4;
   cfg.tf_h1 = InpMseTF_H1;
   cfg.tf_m15 = InpMseTF_M15;
   cfg.tf_m5 = InpMseTF_M5;
   cfg.tf_m1 = InpMseTF_M1;
   cfg.swing_left = InpMseSwingLeft;
   cfg.swing_right = InpMseSwingRight;
   cfg.min_swing_atr = InpMseMinSwingAtr;
   cfg.atr_period = InpMseAtrPeriod;
   cfg.min_bos_atr = InpMseMinBosAtr;
   cfg.min_body_pct = InpMseMinBodyPct;
   cfg.min_tl_touches = InpMseMinTlTouch;
   cfg.tl_touch_atr = 0.15;
   cfg.retest_max_bars = InpMseRetestBars;
   cfg.retest_tol_atr = 0.25;
   cfg.show_chart = InpMseChartObj && WantModuleChart();
   cfg.show_dashboard = InpMseShowDash && WantModuleDashboard();
   cfg.show_hlines = WantChartHorizontalLines();
   cfg.debug_log = InpMseDebug;
  }

void MaybeEvalMarketState(const bool force)
  {
   VantageMseResult r;
   if(g_marketstate.Evaluate(force, r))
      g_msesnap = r;
  }

void FillSwingStrategyConfig(VantageSwingStratConfig &cfg)
  {
   ZeroMemory(cfg);
   cfg.enable = InpSwingEnable;
   cfg.trade_mode = InpSwingTradeMode;
   cfg.gold_only = InpSwingGoldOnly;
   cfg.approved_aliases = InpSwingAliases;
   cfg.allow_suffix = true;
   cfg.allow_prefix = true;
   cfg.tf_d1 = InpSwingTF_D1;
   cfg.tf_h4 = InpSwingTF_H4;
   cfg.tf_h1 = InpSwingTF_H1;
   cfg.tf_m15 = InpSwingTF_M15;
   cfg.tf_m5 = InpSwingTF_M5;
   cfg.swing_left = InpSwingDepthLeft;
   cfg.swing_right = InpSwingDepthRight;
   cfg.min_swing_atr = InpSwingMinAtr;
   cfg.min_swing_candles = InpSwingMinCandles;
   cfg.atr_period = InpSwingAtrPeriod;
   cfg.atr_multiplier = InpSwingAtrMult;
   cfg.max_pullback_pct = InpSwingMaxPbPct;
   cfg.min_rr = InpSwingMinRR;
   cfg.min_confidence = InpSwingMinConf;
   cfg.rsi_bull = InpSwingRsiBull;
   cfg.rsi_bear = InpSwingRsiBear;
   cfg.macd_min_hist = InpSwingMacdMin;
   cfg.min_volume_ratio = InpSwingMinVolRat;
   cfg.bos_min_atr = InpSwingMinBosAtr;
   cfg.min_body_pct = InpSwingMinBodyPct;
   cfg.show_chart = InpSwingChartObj && WantModuleChart();
   cfg.show_dashboard = InpSwingShowDash && WantModuleDashboard();
   cfg.show_hlines = WantChartHorizontalLines();
   cfg.debug_log = InpSwingDebug;
  }

void MaybeEvalSwingStrategy(const bool force)
  {
   VantageSwingStratResult r;
   if(g_swingstrat.Evaluate(force, r))
      g_swingsnap = r;
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
   MaybeEvalGoldSmc(false);
   MaybeEvalLiquidityGrab(false);
   MaybeEvalBreakoutStructure(false);
   MaybeEvalMarketState(false);
   MaybeEvalSwingStrategy(false);

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

   if(!g_analysis.BuildSnapshotAt(g_tech, closed_time))
     {
      g_last_action = "DATA_UNAVAILABLE";
      g_note = "Failed to build technical snapshot for replay bar.";
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

   MaybeEvalPullback(false);
   MaybeEvalGoldSmc(false);
   MaybeEvalLiquidityGrab(false);
   MaybeEvalBreakoutStructure(false);
   MaybeEvalMarketState(false);
   MaybeEvalSwingStrategy(false);

   g_last_action = g_dec.primary_action;
   g_last_request_candle = closed_time;
   WriteBacktestSignalRow(closed_time);

   if(!WantMainDashboard() || (bool)MQLInfoInteger(MQL_OPTIMIZATION))
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
   if(!WantMainDashboard())
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
   MaybeEvalGoldSmc(false);
   MaybeEvalLiquidityGrab(false);
   MaybeEvalBreakoutStructure(false);
   MaybeEvalMarketState(false);
   MaybeEvalSwingStrategy(false);
   const bool show_gsm = WantModuleDashboard() && InpGoldSmcShowDash &&
                         (InpGoldSmcEnable || InpGoldSmcShowWarn) &&
                         g_gsmsnap.valid;
   const bool show_lg = WantModuleDashboard() && InpLiqGrabShowDash && InpLiqGrabEnable && g_liqgrabsnap.valid;
   const bool show_bos = WantModuleDashboard() && InpBosShowDash && InpBosEnable && g_bossnap.valid;
   const bool show_mse = WantModuleDashboard() && InpMseShowDash && InpMseEnable && g_msesnap.valid;
   const bool show_swing = WantModuleDashboard() && InpSwingShowDash && InpSwingEnable && g_swingsnap.valid;
   g_dash.Render(g_acct, g_spec, g_px, g_backend_status, g_candle_status, g_dec,
                 g_pos, g_risk, ts, age,
                 g_equity, g_floating_pl_pct, InpFloatProfitTargetPct, g_float_profit_target_hit,
                 g_pl_cal.year, g_pl_cal.month, g_pl_cal.month_pl, g_pl_cal.month_pct, g_pl_cal.month_deals,
                 g_trade_stats, g_pbsnap, WantModuleDashboard() && InpPbShowDash && InpPullbackEnable,
                 g_gsmsnap, show_gsm,
                 g_liqgrabsnap, show_lg,
                 g_bossnap, show_bos,
                 g_msesnap, show_mse,
                 g_swingsnap, show_swing);
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

   {
    VantageGoldSMCConfig gcfg;
    FillGoldSmcConfig(gcfg);
    if(!g_goldsmc.Init(_Symbol, gcfg))
       Print("[VantageAI] Gold SMC Intelligence init failed.");
    else
       MaybeEvalGoldSmc(true);
   }

   if(InpLiqGrabEnable)
     {
      VantageLiquidityGrabConfig lcfg;
      FillLiquidityGrabConfig(lcfg);
      if(!g_liqgrab.Init(_Symbol, lcfg))
         Print("[VantageAI] Liquidity Grab Monitor init failed.");
      else
         MaybeEvalLiquidityGrab(true);
     }

   if(InpBosEnable)
     {
      VantageBosConfig bcfg;
      FillBreakoutStructureConfig(bcfg);
      if(!g_breakout.Init(_Symbol, bcfg))
         Print("[VantageAI] Breakout Structure Engine init failed.");
      else
         MaybeEvalBreakoutStructure(true);
     }

   if(InpMseEnable)
     {
      VantageMseConfig mcfg;
      FillMarketStateConfig(mcfg);
      if(!g_marketstate.Init(_Symbol, mcfg))
         Print("[VantageAI] Market State Engine v2 init failed.");
      else
         MaybeEvalMarketState(true);
     }

   if(InpSwingEnable)
     {
      VantageSwingStratConfig scfg;
      FillSwingStrategyConfig(scfg);
      if(!g_swingstrat.Init(_Symbol, scfg))
         Print("[VantageAI] Swing Strategy Engine init failed.");
      else
         MaybeEvalSwingStrategy(true);
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
      EventSetTimer(1); // backup driver when tick model is sparse (e.g. Open prices on H1)
      Print("[VantageAI] Replay ready. Strategy Tester will log local signals (no WebRequest, no orders).");
      Print("[VantageAI] Use this EA — not VantageSwingExecutor. Expect 0 deals; check Journal + CSV.");
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
   if(InpApiOnlyUi)
     {
      ClearAllChartVisuals();
      Print("[VantageAI] API-only UI enabled — chart HUD/lines hidden; heartbeat + web UI unchanged.");
     }
   else if(InpChartHideHorizontalLines)
     {
      ClearHorizontalChartLines();
      Print("[VantageAI] Horizontal chart lines hidden — Gold SMC vertical zones kept; data still in API.");
     }
   MaybeSendHeartbeat();
   if(!InpApiOnlyUi)
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
   g_goldsmc.Release();
   g_liqgrab.Release();
   g_breakout.Release();
   g_marketstate.Release();
   g_swingstrat.Release();
   ClearAllChartVisuals();
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
     {
      ReplayDriveClosedBars();
      return;
     }

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
//| Replay — process every newly closed M30 bar (handles H1 chart)   |
//+------------------------------------------------------------------+
void ReplayDriveClosedBars(void)
  {
   datetime last_closed[];
   if(CopyTime(_Symbol, PERIOD_M30, 1, 1, last_closed) != 1)
      return;
   const datetime upto = last_closed[0];
   if(upto <= g_last_closed_candle)
      return;

   datetime times[];
   const int bars_avail = Bars(_Symbol, PERIOD_M30) - 1;
   const int want = (bars_avail > 5000 ? 5000 : bars_avail);
   if(want <= 0)
      return;
   const int n = CopyTime(_Symbol, PERIOD_M30, 1, want, times);
   if(n <= 0)
      return;

   for(int i = 0; i < n; i++)
     {
      if(times[i] <= g_last_closed_candle)
         continue;
      if(times[i] > upto)
         break;
      ProcessReplayBar(times[i]);
      g_last_closed_candle = times[i];
     }
  }

//+------------------------------------------------------------------+
//| Tick — live: prices only; replay: drive closed M30 bars          |
//+------------------------------------------------------------------+
void OnTick()
  {
   if(!g_replay_mode)
      return; // live analysis waits for closed candle via OnTimer

   ReplayDriveClosedBars();
  }

//+------------------------------------------------------------------+
//| End of advisory EA — no trade execution symbols below this line  |
//+------------------------------------------------------------------+
