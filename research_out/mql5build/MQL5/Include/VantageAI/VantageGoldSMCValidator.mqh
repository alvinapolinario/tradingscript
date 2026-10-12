//+------------------------------------------------------------------+
//| VantageGoldSMCValidator.mqh                                      |
//| Strict Gold-only symbol gate (XAUUSD / GOLD + broker affixes)    |
//| Do NOT use VantageNameLooksLikeGold — it is intentionally loose  |
//+------------------------------------------------------------------+
#ifndef VANTAGE_GOLD_SMC_VALIDATOR_MQH
#define VANTAGE_GOLD_SMC_VALIDATOR_MQH

#include "VantageGoldSMCTypes.mqh"

#define VANTAGE_GOLD_SMC_DISABLE_MSG \
  "Gold SMC Intelligence Engine is disabled. This module supports XAUUSD/Gold only."

class CVantageGoldSymbolValidator
  {
private:
   string m_aliases[];           // upper-case base aliases
   int    m_alias_count;
   bool   m_allow_suffix;
   bool   m_allow_prefix;

   void ClearAliases(void)
     {
      ArrayResize(m_aliases, 0);
      m_alias_count = 0;
     }

   string TrimCopy(const string s)
     {
      string t = s;
      StringTrimLeft(t);
      StringTrimRight(t);
      return t;
     }

   string ToUpperCopy(const string s)
     {
      string t = s;
      StringToUpper(t);
      return t;
     }

   bool IsAlphaNum(const ushort ch)
     {
      return ((ch >= 'A' && ch <= 'Z') || (ch >= '0' && ch <= '9'));
     }

   // Strip trailing broker suffix: .a .pro .m _m -m etc. when allow_suffix
   string StripKnownSuffixes(const string upper)
     {
      if(!m_allow_suffix)
         return upper;
      string s = upper;
      // Vantage raw/ECN symbols: EURUSD+, XAUUSD+, USDJPY+
      while(StringLen(s) > 4 && StringGetCharacter(s, StringLen(s) - 1) == '+')
         s = StringSubstr(s, 0, StringLen(s) - 1);
      while(StringLen(s) > 4 && StringGetCharacter(s, StringLen(s) - 1) == '#')
         s = StringSubstr(s, 0, StringLen(s) - 1);
      // Repeated strip of common trailing patterns
      for(int pass = 0; pass < 4; pass++)
        {
         int n = StringLen(s);
         if(n < 2)
            break;
         // trailing single letter suffix glued: XAUUSDM / XAUUSDm already upper
         // Prefer punctuation-delimited suffixes first
         int dot = -1;
         for(int i = n - 1; i >= 0; i--)
           {
            ushort c = StringGetCharacter(s, i);
            if(c == '.' || c == '_' || c == '-')
              {
               dot = i;
               break;
              }
           }
         if(dot > 0 && dot < n - 1)
           {
            string tail = StringSubstr(s, dot + 1);
            // suffix must be short alnum (a, pro, raw, m, i, ecn…)
            if(StringLen(tail) <= 6)
              {
               s = StringSubstr(s, 0, dot);
               continue;
              }
           }
         // glued single trailing letter after a known alias length (e.g. XAUUSDm)
         // handled by MatchAliasAgainstCore below via progressive trim
         break;
        }
      return s;
     }

   // Strip leading broker prefix: m.XAUUSD, a_XAUUSD
   string StripKnownPrefixes(const string upper)
     {
      if(!m_allow_prefix)
         return upper;
      string s = upper;
      for(int pass = 0; pass < 3; pass++)
        {
         int n = StringLen(s);
         if(n < 3)
            break;
         int sep = -1;
         for(int i = 0; i < n && i < 4; i++)
           {
            ushort c = StringGetCharacter(s, i);
            if(c == '.' || c == '_' || c == '-')
              {
               sep = i;
               break;
              }
           }
         if(sep > 0 && sep < n - 1)
           {
            string head = StringSubstr(s, 0, sep);
            if(StringLen(head) <= 3)
              {
               s = StringSubstr(s, sep + 1);
               continue;
              }
           }
         break;
        }
      return s;
     }

   bool AliasExact(const string core)
     {
      for(int i = 0; i < m_alias_count; i++)
        {
         if(core == m_aliases[i])
            return true;
        }
      return false;
     }

   // Try exact alias, then peel short glued suffix letters (XAUUSDm → XAUUSD)
   bool MatchCore(const string candidate, string &out_base)
     {
      out_base = "";
      string c = candidate;
      if(AliasExact(c))
        {
         out_base = c;
         return true;
        }
      if(!m_allow_suffix)
         return false;
      // peel 1–2 trailing alnum chars if remainder is an alias
      for(int peel = 1; peel <= 2; peel++)
        {
         int n = StringLen(c);
         if(n <= peel + 3)
            break;
         bool ok_tail = true;
         for(int k = n - peel; k < n; k++)
           {
            if(!IsAlphaNum(StringGetCharacter(c, k)))
              {
               ok_tail = false;
               break;
              }
           }
         if(!ok_tail)
            break;
         string head = StringSubstr(c, 0, n - peel);
         if(AliasExact(head))
           {
            out_base = head;
            return true;
           }
        }
      return false;
     }

public:
   CVantageGoldSymbolValidator(void)
      : m_alias_count(0), m_allow_suffix(true), m_allow_prefix(true)
     {
     }

   void Configure(const string aliases_csv,
                  const bool allow_suffix,
                  const bool allow_prefix)
     {
      m_allow_suffix = allow_suffix;
      m_allow_prefix = allow_prefix;
      ClearAliases();
      string csv = aliases_csv;
      if(StringLen(TrimCopy(csv)) == 0)
         csv = "XAUUSD,GOLD";
      string parts[];
      int n = StringSplit(csv, ',', parts);
      for(int i = 0; i < n; i++)
        {
         string a = ToUpperCopy(TrimCopy(parts[i]));
         // Reject empty / unsafe wildcards; aliases must be pure alnum base names
         if(StringLen(a) < 3)
            continue;
         bool bad = false;
         for(int k = 0; k < StringLen(a); k++)
           {
            if(!IsAlphaNum(StringGetCharacter(a, k)))
              {
               bad = true;
               break;
              }
           }
         if(bad)
            continue;
         // Explicitly reject known false friends even if user lists them
         if(a == "XAGUSD" || a == "XAUEUR" || a == "GOLDENCOIN" || a == "EURUSD" ||
            a == "BTCUSD" || a == "US30" || a == "OIL" || a == "WTI" || a == "BRENT")
            continue;
         ArrayResize(m_aliases, m_alias_count + 1);
         m_aliases[m_alias_count++] = a;
        }
      if(m_alias_count == 0)
        {
         ArrayResize(m_aliases, 2);
         m_aliases[0] = "XAUUSD";
         m_aliases[1] = "GOLD";
         m_alias_count = 2;
        }
     }

   void ConfigureDesk(const bool allow_suffix = true, const bool allow_prefix = true)
     {
      m_allow_suffix = allow_suffix;
      m_allow_prefix = allow_prefix;
      ClearAliases();
      string desk[] = {"XAUUSD", "GOLD", "EURUSD", "USDJPY"};
      for(int i = 0; i < 4; i++)
        {
         ArrayResize(m_aliases, m_alias_count + 1);
         m_aliases[m_alias_count++] = desk[i];
        }
     }

   bool MatchDeskCore(const string symbol, string &out_base)
     {
      out_base = "";
      string u = ToUpperCopy(TrimCopy(symbol));
      if(StringLen(u) < 3)
         return false;

      if(u == "XAGUSD" || u == "XAUEUR" || u == "XAUGBP" || u == "XAUAUD" ||
         u == "GBPUSD" || u == "BTCUSD" || u == "ETHUSD" ||
         u == "US30" || u == "NAS100" || u == "OIL" || u == "USOIL" || u == "UKOIL" ||
         u == "GOLDENCOIN" || u == "SILVER" || u == "XAGUSD.A")
         return false;
      if(StringFind(u, "XAG") == 0)
         return false;
      if(StringFind(u, "GOLDEN") == 0)
         return false;

      string core = StripKnownPrefixes(u);
      core = StripKnownSuffixes(core);
      return MatchCore(core, out_base);
     }

   // Returns true only for approved spot-gold aliases (+ optional broker affixes)
   bool IsApprovedGoldSymbol(const string symbol, string &out_base)
     {
      out_base = "";
      string u = ToUpperCopy(TrimCopy(symbol));
      if(StringLen(u) < 3)
         return false;

      // Hard rejects — never allow via substring accidents
      if(u == "XAGUSD" || u == "XAUEUR" || u == "XAUGBP" || u == "XAUAUD" ||
         u == "EURUSD" || u == "GBPUSD" || u == "BTCUSD" || u == "ETHUSD" ||
         u == "US30" || u == "NAS100" || u == "OIL" || u == "USOIL" || u == "UKOIL" ||
         u == "GOLDENCOIN" || u == "SILVER" || u == "XAGUSD.A")
         return false;
      if(StringFind(u, "XAG") == 0)
         return false;
      if(StringFind(u, "GOLDEN") == 0)
         return false;

      string core = StripKnownPrefixes(u);
      core = StripKnownSuffixes(core);
      return MatchCore(core, out_base);
     }

   bool IsApprovedDeskSymbol(const string symbol, string &out_base)
     {
      CVantageGoldSymbolValidator desk;
      desk.ConfigureDesk(m_allow_suffix, m_allow_prefix);
      return desk.MatchDeskCore(symbol, out_base);
     }

   bool IsApprovedGoldSymbol(const string symbol)
     {
      string base;
      return IsApprovedGoldSymbol(symbol, base);
     }

   string DisableMessage(void) const
     {
      return VANTAGE_GOLD_SMC_DISABLE_MSG;
     }
  };

// Free-function convenience (uses temporary validator with defaults)
bool IsApprovedGoldSymbol(const string symbol)
  {
   CVantageGoldSymbolValidator v;
   v.Configure("XAUUSD,GOLD", true, true);
   return v.IsApprovedGoldSymbol(symbol);
  }

bool IsApprovedGoldSymbol(const string symbol, const string aliases_csv,
                          const bool allow_suffix, const bool allow_prefix,
                          string &out_base)
  {
   CVantageGoldSymbolValidator v;
   v.Configure(aliases_csv, allow_suffix, allow_prefix);
   return v.IsApprovedGoldSymbol(symbol, out_base);
  }

bool IsApprovedDeskSymbol(const string symbol, string &out_base)
  {
   CVantageGoldSymbolValidator v;
   v.ConfigureDesk(true, true);
   return v.MatchDeskCore(symbol, out_base);
  }

bool IsApprovedDeskSymbol(const string symbol)
  {
   string base;
   return IsApprovedDeskSymbol(symbol, base);
  }

#endif
//+------------------------------------------------------------------+
