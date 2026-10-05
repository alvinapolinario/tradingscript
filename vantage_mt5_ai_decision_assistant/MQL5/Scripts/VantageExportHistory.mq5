//+------------------------------------------------------------------+
//| VantageExportHistory.mq5                                         |
//| Export M5 bars (with per-bar spread) for the offline strategy     |
//| scorecard:  python -m app.research.cli --csv <file>              |
//|                                                                  |
//| Output: MQL5/Files/<InpFileName> (or Common/Files when           |
//| InpCommonFolder=true). Columns:                                  |
//|   time (server epoch), open, high, low, close, tick_volume,      |
//|   spread (points), spread_price (price units)                    |
//|                                                                  |
//| CopyRates cannot return more bars than Tools → Options → Charts  |
//| → "Max bars in chart". Raise it (e.g. Unlimited) for 2–3 years.  |
//+------------------------------------------------------------------+
#property copyright "Vantage MT5 AI Decision Assistant"
#property version   "1.00"
#property description "Export M5 OHLC + spread history to CSV for strategy research"
#property script_show_inputs
#property strict

input string   InpSymbol       = "";                    // Symbol (empty = chart symbol)
input datetime InpFrom         = D'2023.01.01 00:00';
input datetime InpTo           = 0;                     // 0 = now
input string   InpFileName     = "";                    // empty = <symbol>_M5.csv
input bool     InpCommonFolder = false;

void OnStart()
  {
   string symbol = (InpSymbol == "") ? _Symbol : InpSymbol;
   datetime to = (InpTo == 0) ? TimeCurrent() : InpTo;
   string file = (InpFileName == "") ? symbol + "_M5.csv" : InpFileName;
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);

   if(!SymbolSelect(symbol, true) || point <= 0.0)
     {
      Print("[Export] Unknown symbol: ", symbol);
      return;
     }

   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   ResetLastError();
   int n = CopyRates(symbol, PERIOD_M5, InpFrom, to, rates);
   if(n <= 0)
     {
      Print("[Export] CopyRates failed (", GetLastError(), "). Open an M5 chart of ", symbol,
            ", scroll back to load history, and raise Max bars in chart.");
      return;
     }

   int flags = FILE_WRITE | FILE_CSV | FILE_ANSI;
   if(InpCommonFolder)
      flags |= FILE_COMMON;
   int h = FileOpen(file, flags, ',');
   if(h == INVALID_HANDLE)
     {
      Print("[Export] Cannot open ", file, " (", GetLastError(), ")");
      return;
     }
   FileWrite(h, "time", "open", "high", "low", "close", "tick_volume", "spread", "spread_price");
   for(int i = 0; i < n; i++)
     {
      FileWrite(h,
                (long)rates[i].time,
                DoubleToString(rates[i].open, digits),
                DoubleToString(rates[i].high, digits),
                DoubleToString(rates[i].low, digits),
                DoubleToString(rates[i].close, digits),
                (long)rates[i].tick_volume,
                rates[i].spread,
                DoubleToString(rates[i].spread * point, digits));
     }
   FileClose(h);

   string where = InpCommonFolder ? TerminalInfoString(TERMINAL_COMMONDATA_PATH) : TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5";
   PrintFormat("[Export] %d M5 bars %s → %s written to %s\\Files\\%s",
               n, TimeToString(rates[0].time), TimeToString(rates[n - 1].time), where, file);
   if(rates[0].time > InpFrom + 7 * 86400)
      Print("[Export] Note: history starts later than requested — raise Max bars in chart and rerun.");
  }
//+------------------------------------------------------------------+
