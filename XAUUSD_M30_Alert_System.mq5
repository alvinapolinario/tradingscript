//+------------------------------------------------------------------+
//|                              XAUUSD_M30_Alert_System.mq5         |
//|                XAUUSD M30 Market Structure and Alert System      |
//|                                                                  |
//| RISK DISCLAIMER:                                                 |
//| This indicator is a decision-support tool only. It does NOT      |
//| guarantee profit. Manage risk, verify signals with broader       |
//| market context, and trade at your own risk.                      |
//|                                                                  |
//| PLATFORM: MetaTrader 5 (MQL5) — NOT TradingView Pine Script      |
//+------------------------------------------------------------------+
#property copyright "XAU Alert System"
#property version   "1.00"
#property description "XAUUSD M30 Market Structure and Alert System for MT5"
#property description "Decision-support only. Not financial advice."
#property indicator_chart_window
#property indicator_buffers 8
#property indicator_plots   7

//--- plot MA
#property indicator_label1  "MA"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrOrange
#property indicator_style1  STYLE_SOLID
#property indicator_width1  2

//--- plot BB Upper
#property indicator_label2  "BB Upper"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrDodgerBlue
#property indicator_style2  STYLE_DOT
#property indicator_width2  1

//--- plot BB Basis
#property indicator_label3  "BB Basis"
#property indicator_type3   DRAW_LINE
#property indicator_color3  clrTeal
#property indicator_style3  STYLE_SOLID
#property indicator_width3  1

//--- plot BB Lower
#property indicator_label4  "BB Lower"
#property indicator_type4   DRAW_LINE
#property indicator_color4  clrDodgerBlue
#property indicator_style4  STYLE_DOT
#property indicator_width4  1

//--- plot Bull signals
#property indicator_label5  "Bull Signal"
#property indicator_type5   DRAW_ARROW
#property indicator_color5  clrLime
#property indicator_width5  2

//--- plot Bear signals
#property indicator_label6  "Bear Signal"
#property indicator_type6   DRAW_ARROW
#property indicator_color6  clrRed
#property indicator_width6  2

//--- plot Neutral / other
#property indicator_label7  "Other Signal"
#property indicator_type7   DRAW_ARROW
#property indicator_color7  clrMagenta
#property indicator_width7  2

//+------------------------------------------------------------------+
//| Enums                                                            |
//+------------------------------------------------------------------+
enum ENUM_MA_KIND
  {
   MA_KIND_EMA = 0, // EMA
   MA_KIND_SMA = 1  // SMA
  };

enum ENUM_REV_MODE
  {
   REV_ANY_ONE = 0, // Any one pattern
   REV_TWO_MIN = 1  // At least two confirmations
  };

//+------------------------------------------------------------------+
//| Inputs — A. General Settings                                     |
//+------------------------------------------------------------------+
input group "A. General Settings"
input bool           InpConfirmClose     = true;   // Confirm signals only at candle close
input bool           InpIntrabarMode     = false;  // Enable intrabar alert mode
input bool           InpDynAlerts        = true;   // Enable popup / push / email alerts
input bool           InpPushNotify       = false;  // Send push notification
input bool           InpEmailNotify      = false;  // Send email notification
input bool           InpMultiAlertPerBar = false;  // Allow multiple alerts per bar
input bool           InpShowLabels       = true;   // Show signal text labels
input bool           InpShowBgTrend      = false;  // Show background trend shading
input bool           InpShowDashboard    = true;   // Enable dashboard
input bool           InpAlertSound       = true;   // Play alert sound
input string         InpAlertSoundFile   = "alert.wav"; // Alert sound file

//+------------------------------------------------------------------+
//| Inputs — B. Important Price Levels                               |
//+------------------------------------------------------------------+
input group "B. Important Price Levels"
input double         InpImmSupHi         = 4105.00; // Immediate support high
input bool           InpShowImmSupHi     = true;    // Show immediate support high
input double         InpImmSupLo         = 4103.00; // Immediate support low
input bool           InpShowImmSupLo     = true;    // Show immediate support low
input double         InpMajBuyHi         = 4100.00; // Major buy-zone high
input bool           InpShowMajBuyHi     = true;    // Show major buy-zone high
input double         InpMajBuyLo         = 4095.00; // Major buy-zone low
input bool           InpShowMajBuyLo     = true;    // Show major buy-zone low
input double         InpSecSupport       = 4085.00; // Secondary support
input bool           InpShowSecSupport   = true;    // Show secondary support
input double         InpImmResist        = 4112.00; // Immediate resistance
input bool           InpShowImmResist    = true;    // Show immediate resistance
input double         InpDailyPivot       = 4124.29; // Daily pivot
input bool           InpShowDailyPivot   = true;    // Show daily pivot
input double         InpSecResist        = 4133.00; // Secondary resistance
input bool           InpShowSecResist    = true;    // Show secondary resistance
input double         InpUpperResist      = 4143.00; // Upper resistance
input bool           InpShowUpperResist  = true;    // Show upper resistance
input bool           InpShowBuyZoneShade = true;    // Shade major buy zone
input bool           InpShowImmSupShade  = true;    // Shade immediate support zone

//+------------------------------------------------------------------+
//| Inputs — C / D / E / F                                           |
//+------------------------------------------------------------------+
input group "C. Moving Average Settings"
input ENUM_MA_KIND   InpMAType           = MA_KIND_EMA; // MA type
input int            InpMALen            = 20;     // MA length
input bool           InpShowMA           = true;   // Show MA

input group "D. Bollinger Band Settings"
input int            InpBBLen            = 20;     // BB length
input double         InpBBMult           = 2.0;    // BB stdev multiplier
input bool           InpShowBB           = true;   // Show Bollinger Bands

input group "E. RSI Settings"
input int            InpRSILen           = 14;     // RSI length
input double         InpRSIOS            = 30.0;   // Oversold level
input double         InpRSIBearMom       = 40.0;   // Bearish momentum level
input double         InpRSIMid           = 50.0;   // Midline
input double         InpRSIBullMom       = 60.0;   // Bullish momentum level
input double         InpRSIOB            = 70.0;   // Overbought level

input group "F. Volume Settings"
input int            InpVolLen           = 20;     // Volume MA length
input double         InpVolMult          = 1.20;   // High-volume multiplier
input bool           InpReqVol           = true;   // Require volume confirmation

//+------------------------------------------------------------------+
//| Inputs — G. Candle Patterns                                      |
//+------------------------------------------------------------------+
input group "G. Candle Pattern Settings"
input bool           InpUseBullEngulf    = true;   // Detect bullish engulfing
input bool           InpUseBearEngulf    = true;   // Detect bearish engulfing
input bool           InpUseHammer        = true;   // Detect hammer
input bool           InpUseShootingStar  = true;   // Detect shooting star
input bool           InpUseBullReject    = true;   // Detect bullish rejection wick
input bool           InpUseBearReject    = true;   // Detect bearish rejection wick
input double         InpWickBodyRatio    = 2.0;    // Wick-to-body ratio
input double         InpMinBodyPct       = 20.0;   // Min body % of range

//+------------------------------------------------------------------+
//| Inputs — H. Structure / Trend                                    |
//+------------------------------------------------------------------+
input group "H. Market Structure & Trend"
input int            InpPivotLeft        = 3;      // Pivot left bars
input int            InpPivotRight       = 3;      // Pivot right bars
input int            InpTrendScoreNeed   = 3;      // Trend score threshold (of 5)
input ENUM_REV_MODE  InpRevConfirmMode   = REV_ANY_ONE; // Reversal pattern requirement
input double         InpPivotRetestTol   = 1.50;   // Pivot retest tolerance

//+------------------------------------------------------------------+
//| Inputs — I. Filters                                              |
//+------------------------------------------------------------------+
input group "I. Signal Filters"
input bool           InpUseSession       = false;  // Enable session filter
input string         InpSessionStart     = "00:00"; // Session start (HH:MM server)
input string         InpSessionEnd       = "23:59"; // Session end (HH:MM server)
input bool           InpUseDow           = false;  // Enable day-of-week filter
input bool           InpAllowMon         = true;   // Allow Monday
input bool           InpAllowTue         = true;   // Allow Tuesday
input bool           InpAllowWed         = true;   // Allow Wednesday
input bool           InpAllowThu         = true;   // Allow Thursday
input bool           InpAllowFri         = true;   // Allow Friday
input bool           InpAllowSat         = false;  // Allow Saturday
input bool           InpAllowSun         = false;  // Allow Sunday
input int            InpATRLen           = 14;     // ATR length
input bool           InpUseMinATR        = false;  // Enable minimum ATR filter
input double         InpMinATR           = 0.5;    // Minimum ATR
input bool           InpSuppressOversized = true;  // Suppress signals after oversized candle
input double         InpMaxCandleATRMult = 2.0;    // Max candle size (x ATR)
input int            InpCooldownBars     = 3;      // Alert cooldown (bars)

//+------------------------------------------------------------------+
//| Inputs — J. Visual                                               |
//+------------------------------------------------------------------+
input group "J. Visual Plots & Labels"
input bool           InpShowLblBuyRev    = true;   // Label: BUY REV
input bool           InpShowLblSupBreak  = true;   // Label: SUPPORT BREAK
input bool           InpShowLblRecovery  = true;   // Label: RECOVERY
input bool           InpShowLblPPBreak   = true;   // Label: PP BREAK
input bool           InpShowLblPPRetest  = true;   // Label: PP RETEST
input bool           InpShowLblReject    = true;   // Label: REJECTION
input bool           InpShowLblBullShift = true;   // Label: BULL SHIFT
input bool           InpShowLblBearShift = true;   // Label: BEAR SHIFT

//+------------------------------------------------------------------+
//| Buffers                                                          |
//+------------------------------------------------------------------+
double BufMA[];
double BufBBUpper[];
double BufBBBasis[];
double BufBBLower[];
double BufBullArrow[];
double BufBearArrow[];
double BufOtherArrow[];
double BufBBWidth[];   // hidden helper

//+------------------------------------------------------------------+
//| Indicator handles                                                |
//+------------------------------------------------------------------+
int hMA   = INVALID_HANDLE;
int hBB   = INVALID_HANDLE;
int hRSI  = INVALID_HANDLE;
int hATR  = INVALID_HANDLE;

//+------------------------------------------------------------------+
//| Runtime state                                                    |
//+------------------------------------------------------------------+
string   g_prefix        = "XAUAlert_";
string   g_prevTrend     = "NEUTRAL";
bool     g_pivotBroken   = false;
bool     g_pivotRetestDone = false;
datetime g_lastAlertBarTime = 0;
datetime g_lastSignalTime[16];
int      g_lastSignalBar[16];
int      g_lastProcessedBars = -1;
datetime g_lastIntrabarMinute = 0;

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
bool InZone(const double price, const double lo, const double hi)
  {
   double a = MathMin(lo, hi);
   double b = MathMax(lo, hi);
   return(price >= a && price <= b);
  }

double SafeDiv(const double num, const double den)
  {
   if(den == 0.0)
      return(0.0);
   return(num / den);
  }

string FormatPrice(const double v)
  {
   return(DoubleToString(v, _Digits));
  }

bool CanAlert(const int lastBar, const int curBar, const int cooldown)
  {
   if(lastBar < 0)
      return(true);
   return((curBar - lastBar) >= cooldown);
  }

bool IsPivotHigh(const int rates_total, const double &high[], const int center, const int left, const int right)
  {
   if(center - left < 0 || center + right >= rates_total)
      return(false);
   double v = high[center];
   for(int i = 1; i <= left; i++)
      if(high[center - i] >= v)
         return(false);
   for(int i = 1; i <= right; i++)
      if(high[center + i] > v)
         return(false);
   return(true);
  }

bool IsPivotLow(const int rates_total, const double &low[], const int center, const int left, const int right)
  {
   if(center - left < 0 || center + right >= rates_total)
      return(false);
   double v = low[center];
   for(int i = 1; i <= left; i++)
      if(low[center - i] <= v)
         return(false);
   for(int i = 1; i <= right; i++)
      if(low[center + i] < v)
         return(false);
   return(true);
  }

int ParseHHMM(const string hhmm)
  {
   string parts[];
   int n = StringSplit(hhmm, ':', parts);
   if(n < 2)
      return(0);
   return((int)StringToInteger(parts[0]) * 60 + (int)StringToInteger(parts[1]));
  }

bool InSession(const datetime t)
  {
   if(!InpUseSession)
      return(true);
   MqlDateTime dt;
   TimeToStruct(t, dt);
   int cur = dt.hour * 60 + dt.min;
   int a = ParseHHMM(InpSessionStart);
   int b = ParseHHMM(InpSessionEnd);
   if(a <= b)
      return(cur >= a && cur <= b);
   return(cur >= a || cur <= b); // overnight session
  }

bool DowOk(const datetime t)
  {
   if(!InpUseDow)
      return(true);
   MqlDateTime dt;
   TimeToStruct(t, dt);
   // day_of_week: 0=Sun ... 6=Sat
   switch(dt.day_of_week)
     {
      case 1: return(InpAllowMon);
      case 2: return(InpAllowTue);
      case 3: return(InpAllowWed);
      case 4: return(InpAllowThu);
      case 5: return(InpAllowFri);
      case 6: return(InpAllowSat);
      case 0: return(InpAllowSun);
     }
   return(true);
  }

double NearestSupport(const double px)
  {
   double best = EMPTY_VALUE;
   double gap  = 1.0e20;
   double lv[];
   bool sh[];
   ArrayResize(lv, 5);
   ArrayResize(sh, 5);
   lv[0]=InpImmSupHi; sh[0]=InpShowImmSupHi;
   lv[1]=InpImmSupLo; sh[1]=InpShowImmSupLo;
   lv[2]=InpMajBuyHi; sh[2]=InpShowMajBuyHi;
   lv[3]=InpMajBuyLo; sh[3]=InpShowMajBuyLo;
   lv[4]=InpSecSupport; sh[4]=InpShowSecSupport;
   for(int i=0;i<5;i++)
     {
      if(!sh[i] || lv[i] > px)
         continue;
      double g = px - lv[i];
      if(g < gap)
        {
         gap = g;
         best = lv[i];
        }
     }
   return(best);
  }

double NearestResistance(const double px)
  {
   double best = EMPTY_VALUE;
   double gap  = 1.0e20;
   double lv[];
   bool sh[];
   ArrayResize(lv, 4);
   ArrayResize(sh, 4);
   lv[0]=InpImmResist; sh[0]=InpShowImmResist;
   lv[1]=InpDailyPivot; sh[1]=InpShowDailyPivot;
   lv[2]=InpSecResist; sh[2]=InpShowSecResist;
   lv[3]=InpUpperResist; sh[3]=InpShowUpperResist;
   for(int i=0;i<4;i++)
     {
      if(!sh[i] || lv[i] < px)
         continue;
      double g = lv[i] - px;
      if(g < gap)
        {
         gap = g;
         best = lv[i];
        }
     }
   return(best);
  }

void DeleteObjectsByPrefix(const string prefix)
  {
   int total = ObjectsTotal(0, -1, -1);
   for(int i = total - 1; i >= 0; i--)
     {
      string name = ObjectName(0, i, -1, -1);
      if(StringFind(name, prefix) == 0)
         ObjectDelete(0, name);
     }
  }

void DrawHLine(const string name, const double price, const color clr, const int width, const bool show)
  {
   string n = g_prefix + name;
   if(!show)
     {
      ObjectDelete(0, n);
      ObjectDelete(0, n + "_lbl");
      return;
     }
   if(ObjectFind(0, n) < 0)
     {
      ObjectCreate(0, n, OBJ_HLINE, 0, 0, price);
      ObjectSetInteger(0, n, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, n, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, n, OBJPROP_WIDTH, width);
      ObjectSetInteger(0, n, OBJPROP_BACK, true);
      ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, n, OBJPROP_HIDDEN, true);
     }
   else
      ObjectSetDouble(0, n, OBJPROP_PRICE, price);

   string ln = n + "_lbl";
   datetime t = iTime(_Symbol, PERIOD_CURRENT, 0) + PeriodSeconds() * 3;
   if(ObjectFind(0, ln) < 0)
     {
      ObjectCreate(0, ln, OBJ_TEXT, 0, t, price);
      ObjectSetInteger(0, ln, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, ln, OBJPROP_FONTSIZE, 8);
      ObjectSetInteger(0, ln, OBJPROP_ANCHOR, ANCHOR_LEFT);
      ObjectSetInteger(0, ln, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, ln, OBJPROP_HIDDEN, true);
     }
   ObjectSetInteger(0, ln, OBJPROP_TIME, t);
   ObjectSetDouble(0, ln, OBJPROP_PRICE, price);
   ObjectSetString(0, ln, OBJPROP_TEXT, name + " " + FormatPrice(price));
  }

void DrawZone(const string name, const double hi, const double lo, const color clr, const bool show)
  {
   string n = g_prefix + name;
   if(!show)
     {
      ObjectDelete(0, n);
      return;
     }
   datetime t1 = iTime(_Symbol, PERIOD_CURRENT, Bars(_Symbol, PERIOD_CURRENT) - 1);
   datetime t2 = iTime(_Symbol, PERIOD_CURRENT, 0) + PeriodSeconds() * 5;
   if(ObjectFind(0, n) < 0)
     {
      ObjectCreate(0, n, OBJ_RECTANGLE, 0, t1, hi, t2, lo);
      ObjectSetInteger(0, n, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, n, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, n, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, n, OBJPROP_BACK, true);
      ObjectSetInteger(0, n, OBJPROP_FILL, true);
      ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, n, OBJPROP_HIDDEN, true);
     }
   else
     {
      ObjectSetInteger(0, n, OBJPROP_TIME, 0, t1);
      ObjectSetInteger(0, n, OBJPROP_TIME, 1, t2);
      ObjectSetDouble(0, n, OBJPROP_PRICE, 0, hi);
      ObjectSetDouble(0, n, OBJPROP_PRICE, 1, lo);
     }
  }

void PlaceSignalLabel(const string tag, const datetime t, const double price, const color clr, const bool show)
  {
   if(!InpShowLabels || !show)
      return;
   string n = g_prefix + "sig_" + tag + "_" + IntegerToString((int)t);
   if(ObjectFind(0, n) >= 0)
      return;
   ObjectCreate(0, n, OBJ_TEXT, 0, t, price);
   ObjectSetString(0, n, OBJPROP_TEXT, tag);
   ObjectSetInteger(0, n, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, n, OBJPROP_FONTSIZE, 8);
   ObjectSetInteger(0, n, OBJPROP_ANCHOR, ANCHOR_LOWER);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, n, OBJPROP_HIDDEN, true);
  }

void FireAlert(const string signalName, const string extra, const double closePx, const double rsi,
               const string trend, const string volState, const double nearSup, const double nearRes)
  {
   if(!InpDynAlerts)
      return;

   string msg = "XAU Alert | Symbol: " + _Symbol +
                " | TF: " + EnumToString(Period()) +
                " | Signal: " + signalName +
                " | Close: " + FormatPrice(closePx) +
                " | RSI: " + DoubleToString(rsi, 2) +
                " | Trend: " + trend +
                " | Volume: " + volState +
                " | Support: " + (nearSup == EMPTY_VALUE ? "n/a" : FormatPrice(nearSup)) +
                " | Resistance: " + (nearRes == EMPTY_VALUE ? "n/a" : FormatPrice(nearRes)) +
                extra;

   Alert(msg);
   if(InpAlertSound)
      PlaySound(InpAlertSoundFile);
   if(InpPushNotify)
      SendNotification(msg);
   if(InpEmailNotify)
      SendMail("XAU Alert: " + signalName, msg);
  }

void UpdateDashboard(const string trend, const double closePx, const string maStatus,
                     const string pivotStatus, const double rsi, const string rsiState,
                     const string volState, const double nearSup, const double nearRes,
                     const string activeSetup, const string confirmStatus)
  {
   if(!InpShowDashboard)
     {
      Comment("");
      return;
     }

   color trendClr = (trend == "BULLISH" ? clrLime : (trend == "BEARISH" ? clrRed : clrYellow));
   string tf = StringSubstr(EnumToString(Period()), 7); // PERIOD_M15 -> M15
   if(StringLen(tf) == 0)
      tf = EnumToString(Period());
   string text =
      "======== XAU Alert System ========\n" +
      "Symbol: " + _Symbol + "\n" +
      "Timeframe: " + tf + "\n" +
      "Trend: " + trend + "\n" +
      "Close: " + FormatPrice(closePx) + "\n" +
      "MA Status: " + maStatus + "\n" +
      "Daily Pivot: " + pivotStatus + "\n" +
      "RSI: " + DoubleToString(rsi, 2) + " (" + rsiState + ")\n" +
      "Volume: " + volState + "\n" +
      "Near Support: " + (nearSup == EMPTY_VALUE ? "-" : FormatPrice(nearSup)) + "\n" +
      "Near Resist: " + (nearRes == EMPTY_VALUE ? "-" : FormatPrice(nearRes)) + "\n" +
      "Active Setup: " + activeSetup + "\n" +
      "Confirmation: " + confirmStatus + "\n" +
      "==================================";
   Comment(text);
   trendClr = trendClr;
  }

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, BufMA,         INDICATOR_DATA);
   SetIndexBuffer(1, BufBBUpper,    INDICATOR_DATA);
   SetIndexBuffer(2, BufBBBasis,    INDICATOR_DATA);
   SetIndexBuffer(3, BufBBLower,    INDICATOR_DATA);
   SetIndexBuffer(4, BufBullArrow,  INDICATOR_DATA);
   SetIndexBuffer(5, BufBearArrow,  INDICATOR_DATA);
   SetIndexBuffer(6, BufOtherArrow, INDICATOR_DATA);
   SetIndexBuffer(7, BufBBWidth,    INDICATOR_CALCULATIONS);

   PlotIndexSetInteger(4, PLOT_ARROW, 233); // up
   PlotIndexSetInteger(5, PLOT_ARROW, 234); // down
   PlotIndexSetInteger(6, PLOT_ARROW, 159); // diamond

   ArraySetAsSeries(BufMA, true);
   ArraySetAsSeries(BufBBUpper, true);
   ArraySetAsSeries(BufBBBasis, true);
   ArraySetAsSeries(BufBBLower, true);
   ArraySetAsSeries(BufBullArrow, true);
   ArraySetAsSeries(BufBearArrow, true);
   ArraySetAsSeries(BufOtherArrow, true);
   ArraySetAsSeries(BufBBWidth, true);

   ENUM_MA_METHOD method = (InpMAType == MA_KIND_SMA ? MODE_SMA : MODE_EMA);
   hMA  = iMA(_Symbol, PERIOD_CURRENT, InpMALen, 0, method, PRICE_CLOSE);
   hBB  = iBands(_Symbol, PERIOD_CURRENT, InpBBLen, 0, InpBBMult, PRICE_CLOSE);
   hRSI = iRSI(_Symbol, PERIOD_CURRENT, InpRSILen, PRICE_CLOSE);
   hATR = iATR(_Symbol, PERIOD_CURRENT, InpATRLen);

   if(hMA == INVALID_HANDLE || hBB == INVALID_HANDLE || hRSI == INVALID_HANDLE || hATR == INVALID_HANDLE)
     {
      Print("XAU Alert System: failed to create indicator handles");
      return(INIT_FAILED);
     }

   for(int i = 0; i < 16; i++)
     {
      g_lastSignalBar[i] = -1;
      g_lastSignalTime[i] = 0;
     }

   IndicatorSetString(INDICATOR_SHORTNAME, "XAU Alert System");
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(hMA  != INVALID_HANDLE) IndicatorRelease(hMA);
   if(hBB  != INVALID_HANDLE) IndicatorRelease(hBB);
   if(hRSI != INVALID_HANDLE) IndicatorRelease(hRSI);
   if(hATR != INVALID_HANDLE) IndicatorRelease(hATR);
   DeleteObjectsByPrefix(g_prefix);
   Comment("");
  }

//+------------------------------------------------------------------+
//| OnCalculate                                                      |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
   if(rates_total < MathMax(InpMALen, MathMax(InpBBLen, MathMax(InpRSILen, InpATRLen))) + InpPivotLeft + InpPivotRight + 5)
      return(0);

   ArraySetAsSeries(time, true);
   ArraySetAsSeries(open, true);
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);
   ArraySetAsSeries(close, true);
   ArraySetAsSeries(tick_volume, true);
   ArraySetAsSeries(volume, true);

   double ma[], bbU[], bbM[], bbL[], rsi[], atr[];
   ArraySetAsSeries(ma, true);
   ArraySetAsSeries(bbU, true);
   ArraySetAsSeries(bbM, true);
   ArraySetAsSeries(bbL, true);
   ArraySetAsSeries(rsi, true);
   ArraySetAsSeries(atr, true);

   int need = rates_total;
   if(CopyBuffer(hMA, 0, 0, need, ma)  <= 0) return(0);
   if(CopyBuffer(hBB, 0, 0, need, bbM) <= 0) return(0); // basis
   if(CopyBuffer(hBB, 1, 0, need, bbU) <= 0) return(0); // upper
   if(CopyBuffer(hBB, 2, 0, need, bbL) <= 0) return(0); // lower
   if(CopyBuffer(hRSI,0, 0, need, rsi) <= 0) return(0);
   if(CopyBuffer(hATR,0, 0, need, atr) <= 0) return(0);

   // Volume SMA (tick volume preferred on FX/Gold CFDs)
   double volSma[];
   ArrayResize(volSma, rates_total);
   ArraySetAsSeries(volSma, true);
   for(int i = 0; i < rates_total; i++)
     {
      double sum = 0.0;
      int cnt = 0;
      for(int j = 0; j < InpVolLen; j++)
        {
         int idx = i + j;
         if(idx >= rates_total)
            break;
         double v = (double)tick_volume[idx];
         if(v > 0.0)
           {
            sum += v;
            cnt++;
           }
        }
      volSma[i] = (cnt > 0 ? sum / cnt : 0.0);
     }

   // Confirmed swing structure (non-repainting: only pivots with right bars complete)
   double lastSH = EMPTY_VALUE, prevSH = EMPTY_VALUE;
   double lastSL = EMPTY_VALUE, prevSL = EMPTY_VALUE;
   // Walk oldest -> newest so structure evolves correctly
   for(int i = rates_total - 1 - InpPivotLeft; i >= InpPivotRight; i--)
     {
      if(IsPivotHigh(rates_total, high, i, InpPivotLeft, InpPivotRight))
        {
         prevSH = lastSH;
         lastSH = high[i];
        }
      if(IsPivotLow(rates_total, low, i, InpPivotLeft, InpPivotRight))
        {
         prevSL = lastSL;
         lastSL = low[i];
        }
     }
   bool higherHigh = (lastSH != EMPTY_VALUE && prevSH != EMPTY_VALUE && lastSH > prevSH);
   bool lowerHigh  = (lastSH != EMPTY_VALUE && prevSH != EMPTY_VALUE && lastSH < prevSH);
   bool higherLow  = (lastSL != EMPTY_VALUE && prevSL != EMPTY_VALUE && lastSL > prevSL);
   bool lowerLow   = (lastSL != EMPTY_VALUE && prevSL != EMPTY_VALUE && lastSL < prevSL);
   bool bullStructure = higherHigh && higherLow;
   bool bearStructure = lowerHigh && lowerLow;

   // Draw static levels once per update
   DrawHLine("ImmSupHi", InpImmSupHi, clrLime, 1, InpShowImmSupHi);
   DrawHLine("ImmSupLo", InpImmSupLo, clrGreen, 1, InpShowImmSupLo);
   DrawHLine("BuyZoneHi", InpMajBuyHi, clrLime, 1, InpShowMajBuyHi);
   DrawHLine("BuyZoneLo", InpMajBuyLo, clrGreen, 1, InpShowMajBuyLo);
   DrawHLine("SecSupport", InpSecSupport, clrOlive, 1, InpShowSecSupport);
   DrawHLine("ImmResist", InpImmResist, clrRed, 1, InpShowImmResist);
   DrawHLine("DailyPivot", InpDailyPivot, clrMagenta, 2, InpShowDailyPivot);
   DrawHLine("SecResist", InpSecResist, clrMaroon, 1, InpShowSecResist);
   DrawHLine("UpperResist", InpUpperResist, clrPurple, 1, InpShowUpperResist);
   DrawZone("BuyZone", InpMajBuyHi, InpMajBuyLo, clrLime, InpShowBuyZoneShade);
   DrawZone("ImmSupZone", InpImmSupHi, InpImmSupLo, clrGreen, InpShowImmSupShade);

   int start = (prev_calculated > 1 ? rates_total - prev_calculated : rates_total - 2);
   if(start < 1)
      start = 1;
   if(start > rates_total - 2)
      start = rates_total - 2;

   // Process from older to newer for state machine correctness
   // For series arrays, larger index = older. We evaluate bar index 1 (last closed) primarily for alerts.
   // Fill plot buffers for visible history.
   for(int i = rates_total - 2; i >= 0; i--)
     {
      BufMA[i]         = (InpShowMA ? ma[i] : EMPTY_VALUE);
      BufBBUpper[i]    = (InpShowBB ? bbU[i] : EMPTY_VALUE);
      BufBBBasis[i]    = (InpShowBB ? bbM[i] : EMPTY_VALUE);
      BufBBLower[i]    = (InpShowBB ? bbL[i] : EMPTY_VALUE);
      BufBBWidth[i]    = bbU[i] - bbL[i];
      if(prev_calculated == 0)
        {
         BufBullArrow[i]  = EMPTY_VALUE;
         BufBearArrow[i]  = EMPTY_VALUE;
         BufOtherArrow[i] = EMPTY_VALUE;
        }
     }

   // --- Evaluate signal bar ---
   // Default non-repaint: use last closed bar (index 1). Intrabar: use forming bar (index 0).
   bool useForming = InpIntrabarMode && !InpConfirmClose;
   int  sig = (InpConfirmClose && !InpIntrabarMode) ? 1 : (useForming ? 0 : 1);
   if(sig >= rates_total - 2)
      return(rates_total);

   // Avoid re-processing the same closed bar repeatedly
   bool isNewClosedBar = (sig == 1 && time[1] != g_lastAlertBarTime);
   bool allowIntrabar  = (sig == 0);
   if(sig == 1 && !isNewClosedBar && prev_calculated != 0)
     {
      // Still refresh dashboard on forming bar
      // fall through only for dashboard using index 0 below after alert block skip
     }

   int i = sig;
   int i1 = i + 1;
   if(i1 >= rates_total)
      return(rates_total);

   double cBody     = MathAbs(close[i] - open[i]);
   double cRange    = high[i] - low[i];
   double upperWick = high[i] - MathMax(open[i], close[i]);
   double lowerWick = MathMin(open[i], close[i]) - low[i];
   double bodyPct   = SafeDiv(cBody, cRange) * 100.0;
   bool   isBullBar = close[i] > open[i];
   bool   isBearBar = close[i] < open[i];

   bool bullEngulf = InpUseBullEngulf && isBullBar && close[i1] < open[i1] &&
                     close[i] >= open[i1] && open[i] <= close[i1] && bodyPct >= InpMinBodyPct;
   bool bearEngulf = InpUseBearEngulf && isBearBar && close[i1] > open[i1] &&
                     close[i] <= open[i1] && open[i] >= close[i1] && bodyPct >= InpMinBodyPct;
   bool hammer = InpUseHammer && cRange > 0 && lowerWick >= cBody * InpWickBodyRatio &&
                 upperWick <= cBody * 0.5 && bodyPct >= InpMinBodyPct * 0.5 && close[i] >= open[i];
   bool shootingStar = InpUseShootingStar && cRange > 0 && upperWick >= cBody * InpWickBodyRatio &&
                       lowerWick <= cBody * 0.5 && bodyPct >= InpMinBodyPct * 0.5 && close[i] <= open[i];
   bool bullReject = InpUseBullReject && cRange > 0 && lowerWick > cBody &&
                     lowerWick >= cBody * InpWickBodyRatio * 0.75 && close[i] > open[i];
   bool bearReject = InpUseBearReject && cRange > 0 && upperWick > cBody &&
                     upperWick >= cBody * InpWickBodyRatio * 0.75 && close[i] < open[i];

   bool anyBullPat = bullEngulf || hammer || bullReject;
   bool anyBearPat = bearEngulf || shootingStar || bearReject;
   int  bullPatCount = (bullEngulf?1:0) + (hammer?1:0) + (bullReject?1:0);
   bool bullRevOk = (InpRevConfirmMode == REV_ANY_ONE) ? anyBullPat : (bullPatCount >= 2);

   bool maRising   = (i1 < rates_total && ma[i] > ma[i1]);
   bool maFalling  = (i1 < rates_total && ma[i] < ma[i1]);
   bool rsiRising  = (i1 < rates_total && rsi[i] > rsi[i1]);
   bool rsiFalling = (i1 < rates_total && rsi[i] < rsi[i1]);

   double volNow = (double)tick_volume[i];
   bool volAvailable = (volNow > 0.0 && volSma[i] > 0.0);
   bool isHighVol = volAvailable && (volNow > volSma[i] * InpVolMult);
   bool volOk = !InpReqVol || isHighVol || !volAvailable;
   string volState = (!volAvailable ? "N/A" : (isHighVol ? "High" : "Normal"));

   int bullScore =
      (close[i] > ma[i] ? 1 : 0) +
      (maRising ? 1 : 0) +
      (close[i] > bbM[i] ? 1 : 0) +
      (rsi[i] > InpRSIMid ? 1 : 0) +
      (bullStructure ? 1 : 0);
   int bearScore =
      (close[i] < ma[i] ? 1 : 0) +
      (maFalling ? 1 : 0) +
      (close[i] < bbM[i] ? 1 : 0) +
      (rsi[i] < InpRSIMid ? 1 : 0) +
      (bearStructure ? 1 : 0);

   bool isBullTrend = (bullScore >= InpTrendScoreNeed && bullScore > bearScore);
   bool isBearTrend = (bearScore >= InpTrendScoreNeed && bearScore > bullScore);
   string trendName = (isBullTrend ? "BULLISH" : (isBearTrend ? "BEARISH" : "NEUTRAL"));

   bool trendShiftBull = (trendName == "BULLISH" && g_prevTrend != "BULLISH");
   bool trendShiftBear = (trendName == "BEARISH" && g_prevTrend != "BEARISH");

   bool atrOk = !InpUseMinATR || (atr[i] >= InpMinATR);
   bool notOversized = !InpSuppressOversized || (cRange <= atr[i] * InpMaxCandleATRMult);
   bool filtersPass = InSession(time[i]) && DowOk(time[i]) && atrOk && notOversized;
   bool signalReady = InpIntrabarMode || !InpConfirmClose || (sig == 1);
   bool gate = signalReady && filtersPass;

   double buyZoneMid = (InpMajBuyLo + InpMajBuyHi) / 2.0;
   bool tradedInBuyZone = InZone(low[i], InpMajBuyLo, InpMajBuyHi) || low[i] <= InpMajBuyLo ||
                          InZone(close[i1], InpMajBuyLo, InpMajBuyHi);
   bool closedAboveZone = (close[i] > InpMajBuyHi || close[i] > buyZoneMid);
   double nearSup = NearestSupport(close[i]);
   double nearRes = NearestResistance(close[i]);
   bool nearSupportZone =
      InZone(low[i], InpMajBuyLo, InpMajBuyHi) ||
      InZone(low[i], InpImmSupLo, InpImmSupHi) ||
      InZone(close[i], InpMajBuyLo, InpImmSupHi) ||
      (nearSup != EMPTY_VALUE && MathAbs(close[i] - nearSup) <= atr[i]);

   // --- Stateful pivot retest ---
   bool pivotRetestFire = false;
   if(gate)
     {
      if(close[i] > InpDailyPivot && !g_pivotBroken)
        {
         g_pivotBroken = true;
         g_pivotRetestDone = false;
        }
      if(g_pivotBroken && !g_pivotRetestDone)
        {
         bool retestTouch = (low[i] <= InpDailyPivot + InpPivotRetestTol &&
                             low[i] >= InpDailyPivot - InpPivotRetestTol);
         bool closeAbove  = (close[i] > InpDailyPivot);
         bool bullishHold = isBullBar || bullReject || bullEngulf || hammer;
         if(retestTouch && closeAbove && bullishHold)
           {
            pivotRetestFire = true;
            g_pivotRetestDone = true;
           }
        }
      if(close[i] < InpDailyPivot - InpPivotRetestTol)
        {
         g_pivotBroken = false;
         g_pivotRetestDone = false;
        }
     }

   bool rawA1 = close[i] < InpImmSupLo && close[i1] >= InpImmSupLo &&
                close[i] < ma[i] && rsi[i] < InpRSIBearMom && rsiFalling && volOk;
   bool rawA2 = close[i] < InpMajBuyLo && close[i1] >= InpMajBuyLo &&
                isBearTrend && rsi[i] < InpRSIBearMom;
   bool rawA3 = tradedInBuyZone && closedAboveZone && bullRevOk &&
                rsiRising && rsi[i] > InpRSIOS && (!InpReqVol || isHighVol || !volAvailable);
   bool rawA4 = InZone(low[i], InpImmSupLo, InpImmSupHi) && close[i] > InpImmSupHi &&
                isBullBar && lowerWick > cBody && rsiRising;
   bool rsiOkRecovery = (rsi[i] > InpRSIMid && rsi[i1] <= InpRSIMid) || (rsiRising && rsi[i] > 45.0);
   bool rawA5 = close[i] > InpImmResist && close[i1] <= InpImmResist &&
                rsiOkRecovery && (close[i] > ma[i] || close[i] > bbM[i]) && volOk;
   bool rawA6 = close[i] > InpDailyPivot && close[i1] <= InpDailyPivot &&
                isBullBar && rsi[i] > InpRSIMid && close[i] > ma[i] && volOk;
   bool rawA7 = pivotRetestFire;
   bool rawA8 = high[i] >= InpImmResist && close[i] < InpImmResist &&
                (bearReject || bearEngulf || shootingStar) && rsi[i] < InpRSIMid;
   bool rawA9 = high[i] >= InpDailyPivot && close[i] < InpDailyPivot && anyBearPat &&
                (rsi[i] < InpRSIMid || (rsi[i] < InpRSIMid && rsi[i1] >= InpRSIMid)) &&
                (close[i] < ma[i] || (close[i1] >= ma[i1] && close[i] < ma[i]));
   bool bbExpanding = (BufBBWidth[i] > BufBBWidth[i1]);
   bool rawA10 = low[i] <= bbL[i] && close[i] > bbL[i] && close[i] < bbU[i] &&
                 anyBullPat && rsi[i] < InpRSIBearMom && rsiRising;
   bool rawA11 = close[i] < bbL[i] && bbExpanding && rsi[i] < InpRSIBearMom &&
                 (!InpReqVol || isHighVol || !volAvailable);
   bool rawA12 = (rsi[i] < InpRSIOS && rsi[i1] >= InpRSIOS);
   bool rawA13 = (rsi[i] > InpRSIOS && rsi[i1] <= InpRSIOS) && nearSupportZone && isBullBar;
   bool rawA14 = trendShiftBear;
   bool rawA15 = trendShiftBull;

   // Only fire alerts on new closed bar (or intrabar if enabled)
   bool processAlerts = gate && ((sig == 1 && isNewClosedBar) || (sig == 0 && allowIntrabar));

   bool fire[16];
   bool raws[16];
   for(int z = 0; z < 16; z++)
     {
      fire[z] = false;
      raws[z] = false;
     }
   raws[1]=rawA1; raws[2]=rawA2; raws[3]=rawA3; raws[4]=rawA4; raws[5]=rawA5;
   raws[6]=rawA6; raws[7]=rawA7; raws[8]=rawA8; raws[9]=rawA9; raws[10]=rawA10;
   raws[11]=rawA11; raws[12]=rawA12; raws[13]=rawA13; raws[14]=rawA14; raws[15]=rawA15;

   // Approximate current bar index from series perspective for cooldown
   int curBarIdx = Bars(_Symbol, PERIOD_CURRENT) - 1 - i;

   if(processAlerts)
     {
      bool cdOk = CanAlert(g_lastSignalBar[0], curBarIdx, InpCooldownBars);
      for(int a = 1; a <= 15; a++)
        {
         if(raws[a] && CanAlert(g_lastSignalBar[a], curBarIdx, InpCooldownBars) && cdOk)
            fire[a] = true;
        }

      // Priority selection
      string topSignal = "";
      int topPrio = 99;
      // P1
      if(fire[1]  && 1 < topPrio) { topSignal = "Bearish Support Break"; topPrio = 1; }
      if(fire[6]  && 1 < topPrio) { topSignal = "Daily Pivot Breakout"; topPrio = 1; }
      if(fire[14] && 1 < topPrio) { topSignal = "Trend Shift to Bearish"; topPrio = 1; }
      if(fire[15] && 1 < topPrio) { topSignal = "Trend Shift to Bullish"; topPrio = 1; }
      if(fire[2]  && 1 < topPrio) { topSignal = "Bearish Continuation"; topPrio = 1; }
      // P2
      if(fire[3]  && 2 < topPrio) { topSignal = "Bullish Reversal"; topPrio = 2; }
      if(fire[4]  && 2 < topPrio) { topSignal = "Support Hold"; topPrio = 2; }
      if(fire[5]  && 2 < topPrio) { topSignal = "Bullish Recovery"; topPrio = 2; }
      if(fire[7]  && 2 < topPrio) { topSignal = "Daily Pivot Retest Hold"; topPrio = 2; }
      if(fire[8]  && 2 < topPrio) { topSignal = "Bearish Rejection at Resistance"; topPrio = 2; }
      if(fire[9]  && 2 < topPrio) { topSignal = "Bearish Rejection at Pivot"; topPrio = 2; }
      if(fire[10] && 2 < topPrio) { topSignal = "Bullish Bollinger Reversal"; topPrio = 2; }
      if(fire[11] && 2 < topPrio) { topSignal = "Bearish Bollinger Continuation"; topPrio = 2; }
      // P3
      if(fire[12] && 3 < topPrio) { topSignal = "RSI Oversold Warning"; topPrio = 3; }
      if(fire[13] && 3 < topPrio) { topSignal = "RSI Recovery Signal"; topPrio = 3; }

      bool anyFire = (topSignal != "");

      // Visual markers
      if(fire[1] && InpShowLblSupBreak)
        {
         BufBearArrow[i] = high[i];
         PlaceSignalLabel("SUPPORT BREAK", time[i], high[i], clrRed, true);
        }
      if((fire[3] || fire[4] || fire[10]) && InpShowLblBuyRev)
        {
         BufBullArrow[i] = low[i];
         PlaceSignalLabel("BUY REV", time[i], low[i], clrLime, true);
        }
      if(fire[5] && InpShowLblRecovery)
        {
         BufBullArrow[i] = low[i];
         PlaceSignalLabel("RECOVERY", time[i], low[i], clrAqua, true);
        }
      if(fire[6] && InpShowLblPPBreak)
        {
         BufOtherArrow[i] = low[i];
         PlaceSignalLabel("PP BREAK", time[i], low[i], clrMagenta, true);
        }
      if(fire[7] && InpShowLblPPRetest)
        {
         BufOtherArrow[i] = low[i];
         PlaceSignalLabel("PP RETEST", time[i], low[i], clrMagenta, true);
        }
      if((fire[8] || fire[9]) && InpShowLblReject)
        {
         BufBearArrow[i] = high[i];
         PlaceSignalLabel("REJECTION", time[i], high[i], clrOrange, true);
        }
      if(fire[15] && InpShowLblBullShift)
        {
         BufBullArrow[i] = low[i];
         PlaceSignalLabel("BULL SHIFT", time[i], low[i], clrLime, true);
        }
      if(fire[14] && InpShowLblBearShift)
        {
         BufBearArrow[i] = high[i];
         PlaceSignalLabel("BEAR SHIFT", time[i], high[i], clrRed, true);
        }

      // Background trend shading on signal bar
      if(InpShowBgTrend)
        {
         string bg = g_prefix + "bg_" + IntegerToString((int)time[i]);
         if(ObjectFind(0, bg) < 0)
           {
            ObjectCreate(0, bg, OBJ_RECTANGLE, 0, time[i], high[i] * 1.0, time[i] + PeriodSeconds(), low[i]);
            color bgc = (isBullTrend ? clrGreen : (isBearTrend ? clrRed : clrNONE));
            ObjectSetInteger(0, bg, OBJPROP_COLOR, bgc);
            ObjectSetInteger(0, bg, OBJPROP_BACK, true);
            ObjectSetInteger(0, bg, OBJPROP_FILL, true);
            ObjectSetInteger(0, bg, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, bg, OBJPROP_HIDDEN, true);
           }
        }

      // Alerts
      if(InpMultiAlertPerBar)
        {
         if(fire[1])  FireAlert("Bearish Support Break", " | Next support: " + FormatPrice(InpMajBuyLo) + " / " + FormatPrice(InpSecSupport), close[i], rsi[i], trendName, volState, nearSup, nearRes);
         if(fire[2])  FireAlert("Bearish Continuation", " | Next support near " + FormatPrice(InpSecSupport), close[i], rsi[i], trendName, volState, nearSup, nearRes);
         if(fire[3])  FireAlert("Bullish Reversal", " | Target: " + FormatPrice(InpImmResist), close[i], rsi[i], trendName, volState, nearSup, nearRes);
         if(fire[4])  FireAlert("Support Hold", " | Target: " + FormatPrice(InpImmResist), close[i], rsi[i], trendName, volState, nearSup, nearRes);
         if(fire[5])  FireAlert("Bullish Recovery", " | Watch pivot " + FormatPrice(InpDailyPivot), close[i], rsi[i], trendName, volState, nearSup, nearRes);
         if(fire[6])  FireAlert("Daily Pivot Breakout", " | Watch " + FormatPrice(InpSecResist) + " / " + FormatPrice(InpUpperResist), close[i], rsi[i], trendName, volState, nearSup, nearRes);
         if(fire[7])  FireAlert("Daily Pivot Retest Hold", " | Valid above " + FormatPrice(InpDailyPivot), close[i], rsi[i], trendName, volState, nearSup, nearRes);
         if(fire[8])  FireAlert("Bearish Rejection at Resistance", " | Retest supports", close[i], rsi[i], trendName, volState, nearSup, nearRes);
         if(fire[9])  FireAlert("Bearish Rejection at Pivot", " | Favored below pivot", close[i], rsi[i], trendName, volState, nearSup, nearRes);
         if(fire[10]) FireAlert("Bullish Bollinger Reversal", "", close[i], rsi[i], trendName, volState, nearSup, nearRes);
         if(fire[11]) FireAlert("Bearish Bollinger Continuation", "", close[i], rsi[i], trendName, volState, nearSup, nearRes);
         if(fire[12]) FireAlert("RSI Oversold Warning", "", close[i], rsi[i], trendName, volState, nearSup, nearRes);
         if(fire[13]) FireAlert("RSI Recovery Signal", "", close[i], rsi[i], trendName, volState, nearSup, nearRes);
         if(fire[14]) FireAlert("Trend Shift to Bearish", "", close[i], rsi[i], trendName, volState, nearSup, nearRes);
         if(fire[15]) FireAlert("Trend Shift to Bullish", "", close[i], rsi[i], trendName, volState, nearSup, nearRes);
        }
      else if(anyFire)
        {
         string extra = "";
         if(topSignal == "Bearish Support Break")
            extra = " | Next support: " + FormatPrice(InpMajBuyLo) + " / " + FormatPrice(InpSecSupport);
         else if(topSignal == "Bearish Continuation")
            extra = " | Next support near " + FormatPrice(InpSecSupport);
         else if(topSignal == "Bullish Reversal" || topSignal == "Support Hold")
            extra = " | Target: " + FormatPrice(InpImmResist);
         else if(topSignal == "Bullish Recovery")
            extra = " | Watch pivot " + FormatPrice(InpDailyPivot);
         else if(topSignal == "Daily Pivot Breakout")
            extra = " | Watch " + FormatPrice(InpSecResist) + " / " + FormatPrice(InpUpperResist);
         else if(topSignal == "Daily Pivot Retest Hold")
            extra = " | Valid above " + FormatPrice(InpDailyPivot);
         FireAlert(topSignal, extra, close[i], rsi[i], trendName, volState, nearSup, nearRes);
        }

      for(int a = 1; a <= 15; a++)
        {
         if(fire[a])
            g_lastSignalBar[a] = curBarIdx;
        }
      if(anyFire)
         g_lastSignalBar[0] = curBarIdx;

      if(sig == 1)
         g_lastAlertBarTime = time[1];

      g_prevTrend = trendName;
     }

   // Active setup for dashboard — prioritize current market context over stale watch states.
   // Bugfix: price already BELOW buy-zone low was incorrectly labeled "Bullish Reversal Watch"
   // because tradedInBuyZone included low <= buyZoneLo. That watch applies only INSIDE the zone.
   bool insideBuyZone = InZone(low[i], InpMajBuyLo, InpMajBuyHi) || InZone(close[i], InpMajBuyLo, InpMajBuyHi);
   bool belowBuyZone  = (close[i] < InpMajBuyLo);
   bool atImmSupport  = InZone(low[i], InpImmSupLo, InpImmSupHi) || InZone(close[i], InpImmSupLo, InpImmSupHi);

   string activeSetup = "Neutral";
   if(rawA1 && gate)
      activeSetup = "Bearish Support Break";
   else if((rawA2 && gate) || (belowBuyZone && isBearTrend && rsi[i] < InpRSIBearMom))
      activeSetup = "Bearish Continuation";
   else if((rawA8 || rawA9) && gate)
      activeSetup = "Resistance Rejection";
   else if(rawA7 && gate)
      activeSetup = "Pivot Retest";
   else if(rawA6 && gate)
      activeSetup = "Pivot Breakout";
   else if(rawA5 && gate)
      activeSetup = "Recovery Above " + FormatPrice(InpImmResist);
   else if(rawA3 && gate)
      activeSetup = "Bullish Reversal Watch";
   else if((rawA4 && gate) || atImmSupport)
      activeSetup = "Support Test";
   else if(insideBuyZone && !closedAboveZone)
      activeSetup = "Bullish Reversal Watch";
   else if(belowBuyZone && rsi[i] <= InpRSIOS)
      activeSetup = "Bearish Continuation";   // oversold extension below zone — still bearish context
   else if(belowBuyZone)
      activeSetup = "Neutral";

   string rsiState =
      (rsi[i] <= InpRSIOS ? "Oversold" :
       (rsi[i] >= InpRSIOB ? "Overbought" :
        (rsi[i] > InpRSIBullMom ? "Bullish Mom" :
         (rsi[i] < InpRSIBearMom ? "Bearish Mom" :
          (rsi[i] >= InpRSIMid ? "Above Mid" : "Below Mid")))));

   string maStatus = (close[0] > ma[0] ? "Above" : "Below");
   string pivotStatus = (close[0] > InpDailyPivot ? "Above" : "Below");
   string confirmStatus = (InpIntrabarMode ? "Intrabar" : (sig == 1 ? "Confirmed" : "Forming"));

   // Live dashboard uses bar 0 for price readout; setup uses signal bar context above
   string liveVolState = (!((double)tick_volume[0] > 0.0 && volSma[0] > 0.0) ? "N/A" :
                          ((double)tick_volume[0] > volSma[0] * InpVolMult ? "High" : "Normal"));
   string liveTrend = trendName;
   int liveBullScore =
      (close[0] > ma[0] ? 1 : 0) + (ma[0] > ma[1] ? 1 : 0) + (close[0] > bbM[0] ? 1 : 0) +
      (rsi[0] > InpRSIMid ? 1 : 0) + (bullStructure ? 1 : 0);
   int liveBearScore =
      (close[0] < ma[0] ? 1 : 0) + (ma[0] < ma[1] ? 1 : 0) + (close[0] < bbM[0] ? 1 : 0) +
      (rsi[0] < InpRSIMid ? 1 : 0) + (bearStructure ? 1 : 0);
   if(liveBullScore >= InpTrendScoreNeed && liveBullScore > liveBearScore)
      liveTrend = "BULLISH";
   else if(liveBearScore >= InpTrendScoreNeed && liveBearScore > liveBullScore)
      liveTrend = "BEARISH";
   else
      liveTrend = "NEUTRAL";

   string liveRsiState =
      (rsi[0] <= InpRSIOS ? "Oversold" :
       (rsi[0] >= InpRSIOB ? "Overbought" :
        (rsi[0] > InpRSIBullMom ? "Bullish Mom" :
         (rsi[0] < InpRSIBearMom ? "Bearish Mom" :
          (rsi[0] >= InpRSIMid ? "Above Mid" : "Below Mid")))));

   // Recompute active setup on live bar 0 so dashboard matches what you see on chart
   bool liveInsideBuy = InZone(low[0], InpMajBuyLo, InpMajBuyHi) || InZone(close[0], InpMajBuyLo, InpMajBuyHi);
   bool liveBelowBuy  = (close[0] < InpMajBuyLo);
   bool liveAtImmSup  = InZone(low[0], InpImmSupLo, InpImmSupHi) || InZone(close[0], InpImmSupLo, InpImmSupHi);
   bool liveBearCont  = liveBelowBuy && (liveTrend == "BEARISH") && (rsi[0] < InpRSIBearMom);
   string liveSetup = "Neutral";
   if(liveBearCont || (liveBelowBuy && rsi[0] <= InpRSIOS))
      liveSetup = "Bearish Continuation";
   else if(liveAtImmSup)
      liveSetup = "Support Test";
   else if(liveInsideBuy)
      liveSetup = "Bullish Reversal Watch";
   else
      liveSetup = activeSetup;

   UpdateDashboard(liveTrend, close[0], maStatus, pivotStatus, rsi[0], liveRsiState,
                   liveVolState, NearestSupport(close[0]), NearestResistance(close[0]),
                   liveSetup, confirmStatus);

   ChartRedraw(0);
   return(rates_total);
  }
//+------------------------------------------------------------------+
