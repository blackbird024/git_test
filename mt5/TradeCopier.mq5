//+------------------------------------------------------------------+
//| TradeCopier.mq5                                                   |
//| Copiador de operaciones entre terminales MT5 del mismo ordenador. |
//|                                                                   |
//| - MASTER: publica sus posiciones abiertas en un archivo de la     |
//|   carpeta común de MetaTrader (Common\Files) cada medio segundo.  |
//| - SLAVE: lee ese archivo y replica las posiciones: abre, cierra,  |
//|   cierres parciales y stop-loss / take-profit.                    |
//| - El lote se adapta al balance de cada cuenta y a un multiplicador|
//|   (0.5 = la mitad de riesgo, útil para challenges).               |
//| - Si el master deja de actualizar, el slave no toca nada.         |
//| - Límite de pérdida diaria propio en cada slave.                  |
//+------------------------------------------------------------------+
#property copyright "git_test"
#property version   "1.00"
#property description "Copiador de operaciones entre cuentas MT5 del mismo ordenador o VPS"

#include <Trade/Trade.mqh>

enum CopierMode { COPIER_MASTER = 0, COPIER_SLAVE = 1 };
enum LotMode    { LOTS_BALANCE_RATIO = 0, LOTS_MULTIPLIER = 1 };

input group "General"
input CopierMode InpMode    = COPIER_MASTER; // Modo: MASTER (origen) o SLAVE (copia)
input string     InpChannel = "IBS";       // Canal: el mismo nombre en el master y en sus slaves

input group "Master"
input long   InpMasterMagic = 0;           // Copiar solo este número mágico (0 = todas las posiciones)

input group "Slave: tamaño"
input LotMode InpLotMode    = LOTS_BALANCE_RATIO; // Lote: proporcional al balance, o lote del master x multiplicador
input double  InpMultiplier = 1.0;                // Multiplicador (0.5 = la mitad de riesgo)

input group "Slave: símbolos"
input string InpSymbolSuffix = "";   // Sufijo de los símbolos en esta cuenta (p. ej. ".a")
input string InpSymbolMap    = "";   // Equivalencias, p. ej. "NAS100=US100,XAUUSD=GOLD"

input group "Slave: seguridad"
input bool   InpCopySLTP        = true;  // Copiar stop-loss y take-profit
input int    InpMaxStaleSeconds = 30;    // Si el master no actualiza en este tiempo, no se toca nada
input double InpMaxDailyLossPct = 3.5;   // Pérdida diaria máxima: cierra las copias y para ese día (0 = no)
input bool   InpDemoOnly        = true;  // Solo cuentas demo (los challenges suelen serlo)

struct MasterPosition
  {
   ulong  ticket;
   string symbol;
   int    type;
   double volume;
   double sl;
   double tp;
  };

CTrade         trade;
MasterPosition masterPositions[];
double         masterBalance  = 0;
datetime       masterStamp    = 0;
datetime       equityDay      = 0;
double         dayStartEquity = 0;
bool           dailyLossHit   = false;

string FileName()             { return "TradeCopier_" + InpChannel + ".csv"; }
string GvPrefix()             { return "TC_" + InpChannel + "_"; }
string GvName(ulong ticket)   { return GvPrefix() + IntegerToString((long)ticket); }

//+------------------------------------------------------------------+
//| MASTER                                                            |
//+------------------------------------------------------------------+
void MasterPublish()
  {
   string tmp = FileName() + ".tmp";
   int h = FileOpen(tmp, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE)
      return;
   FileWriteString(h, IntegerToString((long)TimeGMT()) + ";" +
                   DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + "\r\n");
   int count = 0;
   for(int i = 0; i < PositionsTotal(); i++)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(InpMasterMagic != 0 && PositionGetInteger(POSITION_MAGIC) != InpMasterMagic)
         continue;
      FileWriteString(h, IntegerToString((long)ticket) + ";" +
                      PositionGetString(POSITION_SYMBOL) + ";" +
                      IntegerToString(PositionGetInteger(POSITION_TYPE)) + ";" +
                      DoubleToString(PositionGetDouble(POSITION_VOLUME), 8) + ";" +
                      DoubleToString(PositionGetDouble(POSITION_SL), 8) + ";" +
                      DoubleToString(PositionGetDouble(POSITION_TP), 8) + "\r\n");
      count++;
     }
   FileClose(h);
   // reemplazo atómico para que el slave nunca lea un archivo a medias
   FileMove(tmp, FILE_COMMON, FileName(), FILE_COMMON | FILE_REWRITE);
   Comment(StringFormat("TradeCopier MASTER  canal \"%s\"\nPosiciones publicadas: %d", InpChannel, count));
  }

//+------------------------------------------------------------------+
//| SLAVE                                                             |
//+------------------------------------------------------------------+
bool ReadMaster()
  {
   int h = FileOpen(FileName(), FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON |
                    FILE_SHARE_READ | FILE_SHARE_WRITE);
   if(h == INVALID_HANDLE)
      return false;
   string parts[];
   if(StringSplit(FileReadString(h), ';', parts) < 2)
     {
      FileClose(h);
      return false;
     }
   masterStamp   = (datetime)StringToInteger(parts[0]);
   masterBalance = StringToDouble(parts[1]);
   ArrayResize(masterPositions, 0);
   while(!FileIsEnding(h))
     {
      if(StringSplit(FileReadString(h), ';', parts) < 6)
         continue;
      int n = ArraySize(masterPositions);
      ArrayResize(masterPositions, n + 1);
      masterPositions[n].ticket = (ulong)StringToInteger(parts[0]);
      masterPositions[n].symbol = parts[1];
      masterPositions[n].type   = (int)StringToInteger(parts[2]);
      masterPositions[n].volume = StringToDouble(parts[3]);
      masterPositions[n].sl     = StringToDouble(parts[4]);
      masterPositions[n].tp     = StringToDouble(parts[5]);
     }
   FileClose(h);
   return true;
  }

bool MasterHas(ulong ticket)
  {
   for(int i = 0; i < ArraySize(masterPositions); i++)
      if(masterPositions[i].ticket == ticket)
         return true;
   return false;
  }

//--- símbolo del master -> símbolo de esta cuenta
string MapSymbol(string symbol)
  {
   string pairs[];
   int n = StringSplit(InpSymbolMap, ',', pairs);
   for(int i = 0; i < n; i++)
     {
      string kv[];
      if(StringSplit(pairs[i], '=', kv) != 2)
         continue;
      StringTrimLeft(kv[0]);
      StringTrimRight(kv[0]);
      StringTrimLeft(kv[1]);
      StringTrimRight(kv[1]);
      if(kv[0] == symbol)
        {
         symbol = kv[1];
         break;
        }
     }
   return symbol + InpSymbolSuffix;
  }

double TargetLots(string symbol, double masterLots)
  {
   double lots = masterLots * InpMultiplier;
   if(InpLotMode == LOTS_BALANCE_RATIO && masterBalance > 0)
      lots *= AccountInfoDouble(ACCOUNT_BALANCE) / masterBalance;
   double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   double minV = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxV = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0)
      return 0;
   lots = MathFloor(lots / step + 1e-9) * step;
   if(lots < minV)
      return 0;
   return MathMin(lots, maxV);
  }

//--- posición de esta cuenta que copia el ticket del master (0 si no hay)
ulong FindCopy(ulong masterTicket)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == (long)masterTicket &&
         GlobalVariableCheck(GvName(masterTicket)))
         return ticket;
     }
   return 0;
  }

void CheckDailyLoss()
  {
   datetime today = iTime(_Symbol, PERIOD_D1, 0);
   if(today != equityDay)
     {
      equityDay      = today;
      dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      dailyLossHit   = false;
     }
   if(InpMaxDailyLossPct > 0 && !dailyLossHit &&
      AccountInfoDouble(ACCOUNT_EQUITY) <= dayStartEquity * (1 - InpMaxDailyLossPct / 100.0))
     {
      dailyLossHit = true;
      Alert("TradeCopier: pérdida diaria de ", DoubleToString(InpMaxDailyLossPct, 1),
            "% alcanzada. Se cierran las copias y no se copia más hoy.");
     }
  }

void SlaveSync()
  {
   CheckDailyLoss();
   if(!ReadMaster())
     {
      Comment("TradeCopier SLAVE: no se encuentra el archivo del master (canal \"", InpChannel, "\")");
      return;
     }
   long age = (long)TimeGMT() - (long)masterStamp;
   if(age > InpMaxStaleSeconds)
     {
      Comment(StringFormat("TradeCopier SLAVE: el master no actualiza desde hace %d s; no se toca nada", (int)age));
      return;
     }

   // 1) cerrar copias cuyo original ya no existe (o todas si se alcanzó la pérdida diaria)
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      long  magic  = PositionGetInteger(POSITION_MAGIC);
      if(ticket == 0 || magic <= 0 || !GlobalVariableCheck(GvName((ulong)magic)))
         continue;
      if(dailyLossHit || !MasterHas((ulong)magic))
         trade.PositionClose(ticket);
     }

   // 2) olvidar originales que ya se cerraron en el master
   for(int g = GlobalVariablesTotal() - 1; g >= 0; g--)
     {
      string name = GlobalVariableName(g);
      if(StringFind(name, GvPrefix()) != 0)
         continue;
      ulong ticket = (ulong)StringToInteger(StringSubstr(name, StringLen(GvPrefix())));
      if(!MasterHas(ticket) && FindCopy(ticket) == 0)
         GlobalVariableDel(name);
     }

   // 3) abrir copias nuevas y ajustar las existentes
   int copies = 0;
   for(int k = 0; k < ArraySize(masterPositions) && !dailyLossHit; k++)
     {
      string symbol = MapSymbol(masterPositions[k].symbol);
      if(!SymbolSelect(symbol, true))
         continue;
      double target = TargetLots(symbol, masterPositions[k].volume);
      double sl = InpCopySLTP ? masterPositions[k].sl : 0;
      double tp = InpCopySLTP ? masterPositions[k].tp : 0;
      ulong copy = FindCopy(masterPositions[k].ticket);

      if(copy == 0)
        {
         // ya copiada y cerrada aquí (stop propio o pérdida diaria): no se reabre
         if(GlobalVariableCheck(GvName(masterPositions[k].ticket)) || target <= 0)
            continue;
         trade.SetExpertMagicNumber((long)masterPositions[k].ticket);
         bool sent = (masterPositions[k].type == POSITION_TYPE_BUY)
                     ? trade.Buy(target, symbol, 0, sl, tp, "CPY " + InpChannel)
                     : trade.Sell(target, symbol, 0, sl, tp, "CPY " + InpChannel);
         if(sent && trade.ResultRetcode() == TRADE_RETCODE_DONE)
            GlobalVariableSet(GvName(masterPositions[k].ticket), (double)TimeCurrent());
         continue;
        }

      copies++;
      if(!PositionSelectByTicket(copy))
         continue;
      double volume = PositionGetDouble(POSITION_VOLUME);
      double step   = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
      if(target > 0 && volume - target >= step - 1e-9)   // cierre parcial en el master
         trade.PositionClosePartial(copy, MathFloor((volume - target) / step + 1e-9) * step);
      double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      if(InpCopySLTP && (MathAbs(PositionGetDouble(POSITION_SL) - sl) > point ||
                         MathAbs(PositionGetDouble(POSITION_TP) - tp) > point))
         trade.PositionModify(copy, sl, tp);
     }

   Comment(StringFormat("TradeCopier SLAVE  canal \"%s\"\nMaster: %d posiciones (hace %d s)\n"
                        "Copias abiertas: %d%s", InpChannel, ArraySize(masterPositions), (int)age, copies,
                        dailyLossHit ? "\n** PÉRDIDA DIARIA ALCANZADA: sin copiar hasta mañana **" : ""));
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpMode == COPIER_SLAVE && InpDemoOnly &&
      AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
     {
      Alert("TradeCopier: la cuenta no es DEMO y InpDemoOnly está activo. EA detenido.");
      return INIT_FAILED;
     }
   trade.SetDeviationInPoints(50);
   EventSetMillisecondTimer(InpMode == COPIER_MASTER ? 500 : 1000);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   Comment("");
  }

void OnTimer()
  {
   if(InpMode == COPIER_MASTER)
      MasterPublish();
   else
      SlaveSync();
  }
//+------------------------------------------------------------------+
