//+------------------------------------------------------------------+
//| VantagePullbackV2Logger.mqh                                    |
//| Milestone 6 — historical CSV logging + V1 shadow columns         |
//| Advisory-only — writes to MQL5/Files/                            |
//+------------------------------------------------------------------+
#ifndef VANTAGE_PULLBACK_V2_LOGGER_MQH
#define VANTAGE_PULLBACK_V2_LOGGER_MQH

#include "VantagePullback.mqh"
#include "VantagePullbackV2.mqh"

struct VantagePullbackV2LogConfig
  {
   bool   enable;
   bool   log_v1_shadow;
   string file_prefix;
  };

class CVantagePullbackV2Logger
  {
private:
   string                     m_symbol;
   VantagePullbackV2LogConfig m_cfg;
   int                        m_file;
   string                     m_filename;
   int                        m_rows;

   string CsvName(void) const
     {
      string prefix = m_cfg.file_prefix;
      if(prefix == "") prefix = "pullback_v2_shadow";
      return prefix + "_" + m_symbol + ".csv";
     }

   string Sanitize(const string s) const
     {
      string out = s;
      StringReplace(out, ",", ";");
      StringReplace(out, "\n", " ");
      StringReplace(out, "\r", " ");
      return out;
     }

   void WriteHeader(void)
     {
      FileWrite(m_file,
                "eval_time","symbol","dom_dir","ref_close","atr_m15",
                "protected_low","protected_high","horizon_tf","horizon_bars","threshold_atr",
                "v1_pullback_prob","v1_continuation_prob","v1_consolidation_prob","v1_reversal_prob","v1_market_state",
                "v2_pullback_score","v2_immediate_cont","v2_cont_after_pb","v2_reversal_risk",
                "v2_extension","v2_displacement","v2_entry_location",
                "v2_expected_depth","v2_expected_pullback_atr","v2_market_state","v2_depth_source");
     }

public:
   CVantagePullbackV2Logger(void) : m_symbol(""), m_file(INVALID_HANDLE), m_filename(""), m_rows(0)
     {
      ZeroMemory(m_cfg);
     }

   bool Init(const string symbol, const VantagePullbackV2LogConfig &cfg)
     {
      Release();
      m_symbol = symbol;
      m_cfg = cfg;
      if(!m_cfg.enable)
         return true;
      m_filename = CsvName();
      m_file = FileOpen(m_filename, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
      if(m_file == INVALID_HANDLE)
        {
         Print("[PullbackV2][CSV] open failed: ", m_filename, " err=", GetLastError());
         return false;
        }
      if(FileSize(m_file) <= 0)
         WriteHeader();
      else
         FileSeek(m_file, 0, SEEK_END);
      Print("[PullbackV2][CSV] journal: MQL5/Files/", m_filename);
      return true;
     }

   void Release(void)
     {
      if(m_file != INVALID_HANDLE)
        {
         FileClose(m_file);
         m_file = INVALID_HANDLE;
        }
     }

   int Rows(void) const { return m_rows; }
   string Filename(void) const { return m_filename; }

   bool WriteRow(const VantagePullbackV2Snapshot &v2,
                 const bool v1_active,
                 const VantagePullbackResult &v1,
                 const datetime eval_time)
     {
      if(!m_cfg.enable || m_file == INVALID_HANDLE || !v2.valid)
         return false;

      double v1_pb = 0, v1_cont = 0, v1_cons = 0, v1_rev = 0;
      string v1_state = "";
      if(m_cfg.log_v1_shadow && v1_active && v1.valid)
        {
         v1_pb = v1.pullback_prob;
         v1_cont = v1.continuation_prob;
         v1_cons = v1.consolidation_prob;
         v1_rev = v1.reversal_prob;
         v1_state = v1.market_state;
        }

      FileWrite(m_file,
                TimeToString(eval_time, TIME_DATE | TIME_MINUTES),
                v2.symbol,
                IntegerToString(v2.dominant_dir),
                DoubleToString(v2.reference_close, 8),
                DoubleToString(v2.atr_m15, 8),
                DoubleToString(v2.protected_low, 8),
                DoubleToString(v2.protected_high, 8),
                EnumToString(v2.horizon_tf),
                IntegerToString(v2.horizon_bars),
                DoubleToString(v2.pullback_threshold_atr, 3),
                DoubleToString(v1_pb, 1),
                DoubleToString(v1_cont, 1),
                DoubleToString(v1_cons, 1),
                DoubleToString(v1_rev, 1),
                Sanitize(v1_state),
                DoubleToString(v2.pullback_score, 1),
                DoubleToString(v2.immediate_continuation_score, 1),
                DoubleToString(v2.continuation_after_pullback_score, 1),
                DoubleToString(v2.reversal_risk_score, 1),
                DoubleToString(v2.extension_score, 1),
                DoubleToString(v2.displacement_score, 1),
                DoubleToString(v2.entry_location_score, 1),
                Sanitize(v2.expected_depth),
                DoubleToString(v2.expected_pullback_atr, 3),
                Sanitize(v2.market_state),
                Sanitize(v2.depth_source));
      m_rows++;
      FileFlush(m_file);
      return true;
     }
  };

#endif
