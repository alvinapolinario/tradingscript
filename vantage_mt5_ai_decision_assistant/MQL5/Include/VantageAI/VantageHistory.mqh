//+------------------------------------------------------------------+
//| VantageHistory.mqh                                               |
//| Read-only closed-deal history → daily P/L calendar               |
//| NEVER opens/modifies trades                                      |
//+------------------------------------------------------------------+
#ifndef VANTAGE_HISTORY_MQH
#define VANTAGE_HISTORY_MQH

#include "VantageTypes.mqh"

#define VANTAGE_CAL_MAX_DAYS 31

struct VantageDayPl
  {
   int    day;          // 1..31
   double pl;           // closed net P/L (profit+swap+commission)
   double pct;          // pl / equity * 100
   int    deals;        // number of exit deals counted
  };

struct VantagePlCalendar
  {
   int    year;
   int    month;        // 1..12
   double equity_ref;   // equity used for % (current equity)
   string currency;
   int    day_count;
   VantageDayPl days[VANTAGE_CAL_MAX_DAYS];
   double month_pl;
   double month_pct;
   int    month_deals;
   bool   ok;
   string error;
  };

datetime VantageMonthStart(const int year, const int month)
  {
   MqlDateTime dt;
   ZeroMemory(dt);
   dt.year = year;
   dt.mon  = month;
   dt.day  = 1;
   dt.hour = 0;
   dt.min  = 0;
   dt.sec  = 0;
   return StructToTime(dt);
  }

datetime VantageMonthEndExclusive(const int year, const int month)
  {
   int y = year;
   int m = month + 1;
   if(m > 12)
     {
      m = 1;
      y++;
     }
   return VantageMonthStart(y, m);
  }

bool VantageIsTradingDeal(const long deal_type)
  {
   return(deal_type == DEAL_TYPE_BUY || deal_type == DEAL_TYPE_SELL);
  }

bool VantageIsExitDeal(const long entry)
  {
   return(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT || entry == DEAL_ENTRY_OUT_BY);
  }

// Build daily closed P/L for a calendar month (server time).
// pct = day_pl / equity_ref * 100 (equity_ref typically current ACCOUNT_EQUITY).
bool VantageBuildMonthPlCalendar(const int year,
                                 const int month,
                                 const double equity_ref,
                                 const string currency,
                                 const string symbol_filter, // "" = all symbols
                                 VantagePlCalendar &cal)
  {
   ZeroMemory(cal);
   cal.year = year;
   cal.month = month;
   cal.equity_ref = equity_ref;
   cal.currency = currency;
   cal.ok = false;

   if(year < 2000 || month < 1 || month > 12)
     {
      cal.error = "Invalid year/month";
      return false;
     }

   datetime from_t = VantageMonthStart(year, month);
   datetime to_t   = VantageMonthEndExclusive(year, month);
   if(!HistorySelect(from_t, to_t - 1))
     {
      cal.error = "HistorySelect failed err=" + IntegerToString(GetLastError());
      return false;
     }

   double day_pl[32];
   int    day_deals[32];
   ArrayInitialize(day_pl, 0.0);
   ArrayInitialize(day_deals, 0);

   const int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0)
         continue;

      long dtype = HistoryDealGetInteger(ticket, DEAL_TYPE);
      if(!VantageIsTradingDeal(dtype))
         continue;

      long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(!VantageIsExitDeal(entry))
         continue;

      if(symbol_filter != "")
        {
         string sym = HistoryDealGetString(ticket, DEAL_SYMBOL);
         if(sym != symbol_filter)
            continue;
        }

      datetime t = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
      if(t < from_t || t >= to_t)
         continue;

      MqlDateTime dt;
      TimeToStruct(t, dt);
      if(dt.year != year || dt.mon != month)
         continue;
      int d = dt.day;
      if(d < 1 || d > 31)
         continue;

      double net = HistoryDealGetDouble(ticket, DEAL_PROFIT)
                 + HistoryDealGetDouble(ticket, DEAL_SWAP)
                 + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      day_pl[d] += net;
      day_deals[d]++;
      cal.month_pl += net;
      cal.month_deals++;
     }

   cal.day_count = 0;
   for(int d = 1; d <= 31; d++)
     {
      if(day_deals[d] <= 0 && MathAbs(day_pl[d]) < 1e-12)
         continue;
      if(cal.day_count >= VANTAGE_CAL_MAX_DAYS)
         break;
      VantageDayPl row;
      ZeroMemory(row);
      row.day = d;
      row.pl = day_pl[d];
      row.deals = day_deals[d];
      row.pct = (equity_ref > 0.0) ? (day_pl[d] / equity_ref) * 100.0 : 0.0;
      cal.days[cal.day_count++] = row;
     }

   cal.month_pct = (equity_ref > 0.0) ? (cal.month_pl / equity_ref) * 100.0 : 0.0;
   cal.ok = true;
   cal.error = "";
   return true;
  }

string VantagePlCalendarToJson(const VantagePlCalendar &cal)
  {
   string j = "{";
   j += "\"year\":" + IntegerToString(cal.year) + ",";
   j += "\"month\":" + IntegerToString(cal.month) + ",";
   j += "\"equity_ref\":" + DoubleToString(cal.equity_ref, 2) + ",";
   j += "\"currency\":\"" + cal.currency + "\",";
   j += "\"month_pl\":" + DoubleToString(cal.month_pl, 2) + ",";
   j += "\"month_pct\":" + DoubleToString(cal.month_pct, 4) + ",";
   j += "\"month_deals\":" + IntegerToString(cal.month_deals) + ",";
   j += "\"ok\":" + (cal.ok ? "true" : "false") + ",";
   j += "\"days\":[";
   for(int i = 0; i < cal.day_count; i++)
     {
      if(i > 0) j += ",";
      j += "{";
      j += "\"d\":" + IntegerToString(cal.days[i].day) + ",";
      j += "\"pl\":" + DoubleToString(cal.days[i].pl, 2) + ",";
      j += "\"pct\":" + DoubleToString(cal.days[i].pct, 4) + ",";
      j += "\"deals\":" + IntegerToString(cal.days[i].deals);
      j += "}";
     }
   j += "]}";
   return j;
  }

//+------------------------------------------------------------------+
//| Account trading statistics (MQL report–style, closed exits only) |
//+------------------------------------------------------------------+
struct VantageTradeStats
  {
   bool   ok;
   string error;
   string currency;
   string symbol_filter;
   int    lookback_days;       // 0 = all history
   datetime from_time;
   datetime to_time;

   int    total_trades;
   int    wins;
   int    losses;
   int    breakeven;
   double win_rate_pct;        // wins / (wins+losses) * 100 (breakeven excluded from rate denom)
   double win_rate_incl_be_pct;// wins / total * 100

   double gross_profit;
   double gross_loss;          // negative or zero
   double net_profit;
   double profit_factor;       // gross_profit / |gross_loss|
   double expected_payoff;     // net / total
   double avg_win;
   double avg_loss;            // negative
   double largest_win;
   double largest_loss;
   double payoff_ratio;        // |avg_win / avg_loss|
   double recovery_factor;      // net / max_dd (if dd>0)

   double max_drawdown;        // money, peak-to-trough on cumulative closed P/L
   double max_drawdown_pct;    // vs equity_ref
   double equity_ref;

   int    max_consec_wins;
   int    max_consec_losses;
   int    current_streak;      // +wins / -losses
   string current_streak_type; // WIN | LOSS | NONE

   double avg_trade;
   double sharpe_approx;       // mean/stdev of trade returns (sample), 0 if n<2
  };

bool VantageBuildTradeStats(const int lookback_days,
                            const double equity_ref,
                            const string currency,
                            const string symbol_filter,
                            VantageTradeStats &st)
  {
   ZeroMemory(st);
   st.ok = false;
   st.currency = currency;
   st.symbol_filter = symbol_filter;
   st.lookback_days = lookback_days;
   st.equity_ref = equity_ref;
   st.current_streak_type = "NONE";
   st.to_time = TimeCurrent();
   st.from_time = 0;
   if(lookback_days > 0)
      st.from_time = st.to_time - (datetime)lookback_days * 86400;

   if(!HistorySelect(st.from_time, st.to_time))
     {
      st.error = "HistorySelect failed err=" + IntegerToString(GetLastError());
      return false;
     }

   // Collect exit nets chronologically
   double nets[];
   datetime times[];
   ArrayResize(nets, 0);
   ArrayResize(times, 0);

   const int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;

      long dtype = HistoryDealGetInteger(ticket, DEAL_TYPE);
      if(!VantageIsTradingDeal(dtype)) continue;

      long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(!VantageIsExitDeal(entry)) continue;

      if(symbol_filter != "")
        {
         string sym = HistoryDealGetString(ticket, DEAL_SYMBOL);
         if(sym != symbol_filter) continue;
        }

      datetime t = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
      if(st.from_time > 0 && t < st.from_time) continue;

      double net = HistoryDealGetDouble(ticket, DEAL_PROFIT)
                 + HistoryDealGetDouble(ticket, DEAL_SWAP)
                 + HistoryDealGetDouble(ticket, DEAL_COMMISSION);

      int n = ArraySize(nets);
      ArrayResize(nets, n + 1);
      ArrayResize(times, n + 1);
      nets[n] = net;
      times[n] = t;
     }

   // Sort by time ascending (simple insertion — trade counts are modest)
   int ntrades = ArraySize(nets);
   for(int i = 1; i < ntrades; i++)
     {
      double key = nets[i];
      datetime tk = times[i];
      int j = i - 1;
      while(j >= 0 && times[j] > tk)
        {
         nets[j + 1] = nets[j];
         times[j + 1] = times[j];
         j--;
        }
      nets[j + 1] = key;
      times[j + 1] = tk;
     }

   st.total_trades = ntrades;
   double sum = 0.0;
   double sum_sq = 0.0;
   double peak = 0.0;
   double cum = 0.0;
   double max_dd = 0.0;
   int consec_w = 0, consec_l = 0;
   int cur = 0;

   for(int i = 0; i < ntrades; i++)
     {
      double net = nets[i];
      sum += net;
      sum_sq += net * net;

      if(net > 1e-8)
        {
         st.wins++;
         st.gross_profit += net;
         if(net > st.largest_win) st.largest_win = net;
         consec_w++;
         consec_l = 0;
         if(consec_w > st.max_consec_wins) st.max_consec_wins = consec_w;
         cur = consec_w;
        }
      else if(net < -1e-8)
        {
         st.losses++;
         st.gross_loss += net; // negative
         if(net < st.largest_loss) st.largest_loss = net;
         consec_l++;
         consec_w = 0;
         if(consec_l > st.max_consec_losses) st.max_consec_losses = consec_l;
         cur = -consec_l;
        }
      else
        {
         st.breakeven++;
         consec_w = 0;
         consec_l = 0;
         cur = 0;
        }

      cum += net;
      if(cum > peak) peak = cum;
      double dd = peak - cum;
      if(dd > max_dd) max_dd = dd;
     }

   st.net_profit = sum;
   st.max_drawdown = max_dd;
   st.max_drawdown_pct = (equity_ref > 0.0) ? (max_dd / equity_ref) * 100.0 : 0.0;
   st.avg_trade = (ntrades > 0) ? (sum / ntrades) : 0.0;
   st.expected_payoff = st.avg_trade;

   int decided = st.wins + st.losses;
   st.win_rate_pct = (decided > 0) ? (100.0 * st.wins / decided) : 0.0;
   st.win_rate_incl_be_pct = (ntrades > 0) ? (100.0 * st.wins / ntrades) : 0.0;

   st.avg_win = (st.wins > 0) ? (st.gross_profit / st.wins) : 0.0;
   st.avg_loss = (st.losses > 0) ? (st.gross_loss / st.losses) : 0.0;

   double abs_loss = MathAbs(st.gross_loss);
   st.profit_factor = (abs_loss > 1e-8) ? (st.gross_profit / abs_loss) : ((st.gross_profit > 0.0) ? 999.0 : 0.0);
   st.payoff_ratio = (MathAbs(st.avg_loss) > 1e-8) ? (st.avg_win / MathAbs(st.avg_loss)) : 0.0;
   st.recovery_factor = (max_dd > 1e-8) ? (st.net_profit / max_dd) : ((st.net_profit > 0.0) ? 999.0 : 0.0);

   if(cur > 0) { st.current_streak = cur; st.current_streak_type = "WIN"; }
   else if(cur < 0) { st.current_streak = -cur; st.current_streak_type = "LOSS"; }
   else { st.current_streak = 0; st.current_streak_type = "NONE"; }

   if(ntrades >= 2)
     {
      double mean = sum / ntrades;
      double var = (sum_sq / ntrades) - (mean * mean);
      if(var < 0.0) var = 0.0;
      double stdev = MathSqrt(var);
      st.sharpe_approx = (stdev > 1e-8) ? (mean / stdev) : 0.0;
     }

   st.ok = true;
   st.error = "";
   return true;
  }

string VantageTradeStatsToJson(const VantageTradeStats &st)
  {
   string j = "{";
   j += "\"ok\":" + (st.ok ? "true" : "false") + ",";
   j += "\"currency\":\"" + st.currency + "\",";
   j += "\"symbol_filter\":\"" + st.symbol_filter + "\",";
   j += "\"lookback_days\":" + IntegerToString(st.lookback_days) + ",";
   j += "\"from_time\":\"" + TimeToString(st.from_time, TIME_DATE|TIME_SECONDS) + "\",";
   j += "\"to_time\":\"" + TimeToString(st.to_time, TIME_DATE|TIME_SECONDS) + "\",";
   j += "\"equity_ref\":" + DoubleToString(st.equity_ref, 2) + ",";
   j += "\"total_trades\":" + IntegerToString(st.total_trades) + ",";
   j += "\"wins\":" + IntegerToString(st.wins) + ",";
   j += "\"losses\":" + IntegerToString(st.losses) + ",";
   j += "\"breakeven\":" + IntegerToString(st.breakeven) + ",";
   j += "\"win_rate_pct\":" + DoubleToString(st.win_rate_pct, 2) + ",";
   j += "\"win_rate_incl_be_pct\":" + DoubleToString(st.win_rate_incl_be_pct, 2) + ",";
   j += "\"gross_profit\":" + DoubleToString(st.gross_profit, 2) + ",";
   j += "\"gross_loss\":" + DoubleToString(st.gross_loss, 2) + ",";
   j += "\"net_profit\":" + DoubleToString(st.net_profit, 2) + ",";
   j += "\"profit_factor\":" + DoubleToString(st.profit_factor, 3) + ",";
   j += "\"expected_payoff\":" + DoubleToString(st.expected_payoff, 4) + ",";
   j += "\"avg_win\":" + DoubleToString(st.avg_win, 2) + ",";
   j += "\"avg_loss\":" + DoubleToString(st.avg_loss, 2) + ",";
   j += "\"largest_win\":" + DoubleToString(st.largest_win, 2) + ",";
   j += "\"largest_loss\":" + DoubleToString(st.largest_loss, 2) + ",";
   j += "\"payoff_ratio\":" + DoubleToString(st.payoff_ratio, 3) + ",";
   j += "\"recovery_factor\":" + DoubleToString(st.recovery_factor, 3) + ",";
   j += "\"max_drawdown\":" + DoubleToString(st.max_drawdown, 2) + ",";
   j += "\"max_drawdown_pct\":" + DoubleToString(st.max_drawdown_pct, 2) + ",";
   j += "\"max_consec_wins\":" + IntegerToString(st.max_consec_wins) + ",";
   j += "\"max_consec_losses\":" + IntegerToString(st.max_consec_losses) + ",";
   j += "\"current_streak\":" + IntegerToString(st.current_streak) + ",";
   j += "\"current_streak_type\":\"" + st.current_streak_type + "\",";
   j += "\"avg_trade\":" + DoubleToString(st.avg_trade, 4) + ",";
   j += "\"sharpe_approx\":" + DoubleToString(st.sharpe_approx, 3);
   j += "}";
   return j;
  }

#endif
//+------------------------------------------------------------------+
