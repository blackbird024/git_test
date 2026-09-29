//+------------------------------------------------------------------+
//| APEX_Cartera_NAS100.mq5                                          |
//| Cartera validada del proyecto, automatizada para CUENTA DEMO:    |
//|  1) ZONA_RUIDO_MNQ_v1.0 (edges/zona_ruido_mnq.md), intradía       |
//|  2) RSI(2) de Connors (edges/nq_rsi2.md), swing diario           |
//| Validadas con futuros NQ; aquí se aplican al CFD NAS100.         |
//| Diferencias con el backtest: precio del CFD (no del futuro),     |
//| volumen de ticks en el VWAP, spread y swap en vez de comisión.   |
//+------------------------------------------------------------------+
#property copyright "Proyecto APEX (uso en demo)"
#property version   "1.00"

#include <Trade/Trade.mqh>

//--- Entradas
input group "Tamaño y horario"
input double DineroPorPunto     = 2.0;   // Dinero de la cuenta por punto (1 MNQ = 2 $/punto)
input int    DesfaseServidorNY  = 7;     // Horas servidor - Nueva York (Pepperstone MT5: 7)
input group "Zona de ruido (intradía)"
input bool   ActivarZonaRuido   = true;
input int    DiasRuido          = 14;    // Días para la media del ruido
input int    MinDiasRuido       = 10;    // Mínimo de días con dato
input long   MagicZona          = 290901;
input group "RSI(2) (swing, mantiene posiciones de noche)"
input bool   ActivarRSI2        = true;
input double RsiEntrada         = 20.0;  // Compra si RSI(2) < este valor y cierre > SMA(200)
input double RsiSalida          = 70.0;  // Cierra si RSI(2) > este valor
input int    MaxSesiones        = 5;     // o tras este número de sesiones
input long   MagicRSI           = 290902;
input group "Avisos por Telegram (opcional)"
input string TelegramToken      = "";    // Se queda en tu MT5; nunca lo pongas en el código
input string TelegramChatId     = "";

//--- Constantes de la sesión regular de NY (minutos desde las 09:30)
#define MIN_SESION        390
#define PRIMER_CHEQUEO    30     // 10:00 NY
#define ULTIMO_CHEQUEO    360    // 15:30 NY
#define CADA              30

CTrade trade;

//--- Estado del día (zona de ruido)
int    g_dia        = 0;         // fecha NY (AAAAMMDD) preparada
bool   g_listo      = false;
double g_apertura   = 0, g_cierreAnt = 0;
double g_sigma[MIN_SESION];
int    g_ultimoChequeo = -1;
bool   g_cerradoFin    = false;
datetime g_ultimoIntento = 0;       // para no reintentar la preparación más de una vez por minuto

//--- RSI(2)
int      h_rsi = INVALID_HANDLE, h_sma = INVALID_HANDLE;
datetime g_ultimaD1 = 0;          // última vela diaria ya resuelta
datetime g_reintentoRSI = 0;      // si una orden falla (mercado cerrado), se reintenta cada minuto

//+------------------------------------------------------------------+
datetime AhoraNY()                 { return TimeCurrent() - DesfaseServidorNY * 3600; }
datetime NYaServidor(datetime ny)  { return ny + DesfaseServidorNY * 3600; }
int      FechaNY(datetime ny)      { MqlDateTime t; TimeToStruct(ny, t); return t.year * 10000 + t.mon * 100 + t.day; }
datetime InicioDiaNY(datetime ny)  { MqlDateTime t; TimeToStruct(ny, t); t.hour = 0; t.min = 0; t.sec = 0; return StructToTime(t); }
int      MinutoSesion(datetime ny) { MqlDateTime t; TimeToStruct(ny, t); return (t.hour - 9) * 60 + t.min - 30; }

double Lotes()
{
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double paso = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(tv <= 0 || ts <= 0 || paso <= 0) return vmin;
   double lotes = DineroPorPunto / (tv / ts);              // dinero por punto con 1 lote = tv/ts
   lotes = MathRound(lotes / paso) * paso;
   return MathMax(vmin, MathMin(vmax, lotes));
}

void Telegram(string texto)
{
   Print(texto);
   if(TelegramToken == "" || TelegramChatId == "" || MQLInfoInteger(MQL_TESTER)) return;
   string url = "https://api.telegram.org/bot" + TelegramToken + "/sendMessage";
   string t = texto;
   StringReplace(t, "\\", "\\\\"); StringReplace(t, "\"", "\\\""); StringReplace(t, "\n", "\\n");
   string cuerpo = "{\"chat_id\":\"" + TelegramChatId + "\",\"text\":\"" + t + "\"}";
   char datos[], resp[]; string cab;
   int n = StringToCharArray(cuerpo, datos, 0, WHOLE_ARRAY, CP_UTF8);
   ArrayResize(datos, n - 1);                                            // sin el 0 final
   int r = WebRequest("POST", url, "Content-Type: application/json\r\n", 5000, datos, resp, cab);
   if(r != 200) Print("Telegram: error ", r, " (¿añadiste https://api.telegram.org en Herramientas > Opciones > Asesores?)");
}

void Registrar(string estrategia, string accion, double precio, string motivo)
{
   int f = FileOpen("APEX_registro.csv", FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(f == INVALID_HANDLE) return;
   if(FileSize(f) == 0) FileWrite(f, "hora_servidor", "hora_NY", "estrategia", "accion", "precio", "motivo");
   FileSeek(f, 0, SEEK_END);
   FileWrite(f, TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS), TimeToString(AhoraNY(), TIME_DATE | TIME_SECONDS),
             estrategia, accion, DoubleToString(precio, _Digits), motivo);
   FileClose(f);
}

// Dirección de la posición abierta con ese magic (1, -1 o 0)
int Posicion(long magic)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != magic) continue;
      return PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
   }
   return 0;
}

datetime AperturaPosicion(long magic)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk != 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magic)
         return (datetime)PositionGetInteger(POSITION_TIME);
   }
   return 0;
}

bool Cerrar(long magic, string estrategia, string motivo)
{
   bool ok = true;
   trade.SetExpertMagicNumber(magic);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != magic) continue;
      if(trade.PositionClose(tk))
      {
         Registrar(estrategia, "CERRAR", trade.ResultPrice(), motivo);
         Telegram("🔴 " + estrategia + ": CERRADA a " + DoubleToString(trade.ResultPrice(), _Digits) + " (" + motivo + ")");
      }
      else { ok = false; Print(estrategia, ": error al cerrar ", trade.ResultRetcode()); }
   }
   return ok;
}

bool Abrir(long magic, int dir, string estrategia, string motivo)
{
   trade.SetExpertMagicNumber(magic);
   double lotes = Lotes();
   bool ok = dir == 1 ? trade.Buy(lotes, _Symbol) : trade.Sell(lotes, _Symbol);
   if(ok && (trade.ResultRetcode() == TRADE_RETCODE_DONE || trade.ResultRetcode() == TRADE_RETCODE_PLACED))
   {
      Registrar(estrategia, dir == 1 ? "COMPRAR" : "VENDER", trade.ResultPrice(), motivo);
      Telegram((dir == 1 ? "🟢 " : "🟠 ") + estrategia + ": " + (dir == 1 ? "COMPRA " : "VENTA ") + DoubleToString(lotes, 2) +
               " lotes a " + DoubleToString(trade.ResultPrice(), _Digits) + " (" + motivo + ")");
      return true;
   }
   Print(estrategia, ": error al abrir ", trade.ResultRetcode());
   return false;
}

//+------------------------------------------------------------------+
//| Zona de ruido                                                    |
//+------------------------------------------------------------------+
// Velas de 1M de la sesión regular (09:30-16:00 NY) de un día NY, indexadas por minuto (0..389). Devuelve cuántas hay.
int VelasSesion(datetime inicioDiaNY, int hastaMin, MqlRates &por_min[], bool &hay[])
{
   ArrayResize(por_min, MIN_SESION); ArrayResize(hay, MIN_SESION); ArrayInitialize(hay, false);
   datetime desde = NYaServidor(inicioDiaNY + 9 * 3600 + 30 * 60);
   datetime hasta = desde + (hastaMin + 1) * 60 - 1;
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_M1, desde, hasta, r);
   int cuenta = 0;
   for(int i = 0; i < n; i++)
   {
      int m = MinutoSesion(r[i].time - DesfaseServidorNY * 3600);
      if(m < 0 || m > hastaMin || m >= MIN_SESION) continue;
      por_min[m] = r[i]; hay[m] = true; cuenta++;
   }
   return cuenta;
}

// Prepara sigma (media de |cierre/apertura - 1| por minuto en los DiasRuido días anteriores), apertura y cierre anterior.
bool PrepararDia(datetime ahoraNY)
{
   datetime hoy = InicioDiaNY(ahoraNY);
   MqlRates velas[]; bool hay[];
   if(VelasSesion(hoy, 0, velas, hay) == 0 || !hay[0]) return false;      // aún no hay vela de las 09:30
   g_apertura = velas[0].open;

   double suma[MIN_SESION]; int cnt[MIN_SESION];
   ArrayInitialize(suma, 0); ArrayInitialize(cnt, 0);
   int dias = 0; g_cierreAnt = 0;
   for(int k = 1; k <= 40 && dias < DiasRuido; k++)                      // hacia atrás hasta reunir DiasRuido sesiones
   {
      datetime d = hoy - k * 86400;
      MqlRates v[]; bool h[];
      if(VelasSesion(d, MIN_SESION - 1, v, h) < 60) continue;            // fin de semana, festivo o sin datos
      int m0 = -1;
      for(int m = 0; m < MIN_SESION; m++) if(h[m]) { m0 = m; break; }
      double ap = v[m0].open;
      if(dias == 0) { for(int m = MIN_SESION - 1; m >= 0; m--) if(h[m]) { g_cierreAnt = v[m].close; break; } }
      for(int m = 0; m < MIN_SESION; m++)
         if(h[m]) { suma[m] += MathAbs(v[m].close / ap - 1.0); cnt[m]++; }
      dias++;
   }
   if(dias < MinDiasRuido || g_cierreAnt <= 0) { Print("Zona de ruido: historia insuficiente (", dias, " días)"); return false; }
   for(int m = 0; m < MIN_SESION; m++) g_sigma[m] = cnt[m] >= MinDiasRuido ? suma[m] / cnt[m] : EMPTY_VALUE;

   string txt = "📊 Zona de ruido NAS100 " + TimeToString(hoy, TIME_DATE) + ": apertura " + DoubleToString(g_apertura, _Digits) +
                ", cierre anterior " + DoubleToString(g_cierreAnt, _Digits) + "\nHora NY | banda sup | banda inf";
   for(int c = PRIMER_CHEQUEO; c <= ULTIMO_CHEQUEO; c += CADA)
   {
      double s = g_sigma[c - 1];
      if(s == EMPTY_VALUE) continue;
      txt += StringFormat("\n%02d:%02d | %s | %s", 9 + (30 + c) / 60, (30 + c) % 60,
                          DoubleToString(MathMax(g_apertura, g_cierreAnt) * (1 + s), _Digits),
                          DoubleToString(MathMin(g_apertura, g_cierreAnt) * (1 - s), _Digits));
   }
   Telegram(txt);
   return true;
}

void Chequeo(datetime ahoraNY, int minuto)
{
   MqlRates v[]; bool h[];
   VelasSesion(InicioDiaNY(ahoraNY), minuto - 1, v, h);
   if(!h[minuto - 1] || g_sigma[minuto - 1] == EMPTY_VALUE) { Print("Zona de ruido: sin vela o sin sigma en el minuto ", minuto - 1); return; }
   // VWAP de la sesión con volumen de ticks, hasta la vela anterior (incluida)
   double pv = 0, vol = 0;
   for(int m = 0; m < minuto; m++)
      if(h[m]) { double tip = (v[m].high + v[m].low + v[m].close) / 3.0; pv += tip * (double)v[m].tick_volume; vol += (double)v[m].tick_volume; }
   double vwap = vol > 0 ? pv / vol : v[minuto - 1].close;
   double p = v[minuto - 1].close, s = g_sigma[minuto - 1];
   double sup = MathMax(g_apertura, g_cierreAnt) * (1 + s), inf = MathMin(g_apertura, g_cierreAnt) * (1 - s);
   string info = StringFormat("precio %s, bandas %s / %s, VWAP %s", DoubleToString(p, _Digits), DoubleToString(sup, _Digits),
                              DoubleToString(inf, _Digits), DoubleToString(vwap, _Digits));
   int pos = Posicion(MagicZona);
   if(pos == 1 && p < MathMax(sup, vwap))       { if(Cerrar(MagicZona, "Zona de ruido", "trailing: " + info)) pos = 0; }
   else if(pos == -1 && p > MathMin(inf, vwap)) { if(Cerrar(MagicZona, "Zona de ruido", "trailing: " + info)) pos = 0; }
   if(pos == 0)
   {
      if(p > sup)      Abrir(MagicZona, 1, "Zona de ruido", "sobre la banda superior: " + info);
      else if(p < inf) Abrir(MagicZona, -1, "Zona de ruido", "bajo la banda inferior: " + info);
   }
}

void ProcesarZona()
{
   datetime ny = AhoraNY();
   MqlDateTime t; TimeToStruct(ny, t);
   if(t.day_of_week == 0 || t.day_of_week == 6) return;
   int dia = FechaNY(ny), minuto = MinutoSesion(ny);
   if(dia != g_dia)
   {
      if(Posicion(MagicZona) != 0) Cerrar(MagicZona, "Zona de ruido", "posición de otro día");
      g_dia = dia; g_listo = false; g_ultimoChequeo = -1; g_cerradoFin = false;
   }
   if(minuto < 0 || minuto >= MIN_SESION + 5) return;
   if(!g_listo)
   {
      if(TimeCurrent() - g_ultimoIntento < 60) return;
      g_ultimoIntento = TimeCurrent();
      g_listo = PrepararDia(ny);
      if(!g_listo) return;
   }
   // Cierre de fin de sesión: 15:59:50 NY (el backtest usa el cierre de la vela de las 15:59)
   if(!g_cerradoFin && (minuto > MIN_SESION - 1 || (minuto == MIN_SESION - 1 && t.sec >= 50)))
   {
      g_cerradoFin = true;
      if(Posicion(MagicZona) != 0) Cerrar(MagicZona, "Zona de ruido", "fin de sesión");
      return;
   }
   // Chequeos a las HH:00 y HH:30 de 10:00 a 15:30 NY, una sola vez, en los primeros 2 minutos
   int c = (minuto / CADA) * CADA;
   if(c >= PRIMER_CHEQUEO && c <= ULTIMO_CHEQUEO && c > g_ultimoChequeo && minuto - c < 2)
   {
      g_ultimoChequeo = c;
      Chequeo(ny, c);
   }
}

//+------------------------------------------------------------------+
//| RSI(2)                                                           |
//+------------------------------------------------------------------+
void ProcesarRSI()
{
   datetime d1 = iTime(_Symbol, PERIOD_D1, 0);
   if(d1 == 0 || d1 == g_ultimaD1) return;                               // solo al abrir una vela diaria nueva
   if(TimeCurrent() - g_reintentoRSI < 60) return;
   g_reintentoRSI = TimeCurrent();
   double rsi[1], sma[1];
   if(CopyBuffer(h_rsi, 0, 1, 1, rsi) != 1 || CopyBuffer(h_sma, 0, 1, 1, sma) != 1) return;   // aún calculando
   bool hecho = true;
   double cierre = iClose(_Symbol, PERIOD_D1, 1);
   string info = StringFormat("RSI(2)=%.1f, cierre %s, SMA200 %s", rsi[0], DoubleToString(cierre, _Digits), DoubleToString(sma[0], _Digits));
   if(Posicion(MagicRSI) == 1)
   {
      int sesiones = iBarShift(_Symbol, PERIOD_D1, AperturaPosicion(MagicRSI));   // sesiones completas desde la entrada
      if(rsi[0] > RsiSalida)          hecho = Cerrar(MagicRSI, "RSI(2)", "RSI > " + DoubleToString(RsiSalida, 0) + ": " + info);
      else if(sesiones >= MaxSesiones) hecho = Cerrar(MagicRSI, "RSI(2)", IntegerToString(sesiones) + " sesiones: " + info);
      else Print("RSI(2): sigue la posición (", sesiones, " sesiones). ", info);
   }
   else if(cierre > sma[0] && rsi[0] < RsiEntrada)
      hecho = Abrir(MagicRSI, 1, "RSI(2)", "señal: " + info);
   else
      Print("RSI(2): sin señal. ", info);
   if(hecho) g_ultimaD1 = d1;                                            // si falló, se reintenta en un minuto
}

//+------------------------------------------------------------------+
int OnInit()
{
   if(ActivarZonaRuido && ActivarRSI2 && AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
   {
      Alert("La cuenta no es de cobertura (hedging): las dos estrategias se compensarían entre sí. Usa una cuenta hedging o activa solo una.");
      return INIT_PARAMETERS_INCORRECT;
   }
   h_rsi = iRSI(_Symbol, PERIOD_D1, 2, PRICE_CLOSE);                      // RSI de Wilder, como en el backtest
   h_sma = iMA(_Symbol, PERIOD_D1, 200, 0, MODE_SMA, PRICE_CLOSE);
   if(h_rsi == INVALID_HANDLE || h_sma == INVALID_HANDLE) return INIT_FAILED;
   g_ultimaD1 = iTime(_Symbol, PERIOD_D1, 0);                             // no actuar sobre la vela ya empezada al arrancar
   trade.SetDeviationInPoints(20);
   EventSetTimer(1);
   Telegram(StringFormat("🤖 EA APEX iniciado en %s. Lotes por operación: %.2f (%.2f por punto). Hora NY ahora: %s",
                         _Symbol, Lotes(), DineroPorPunto, TimeToString(AhoraNY(), TIME_DATE | TIME_MINUTES)));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   if(h_rsi != INVALID_HANDLE) IndicatorRelease(h_rsi);
   if(h_sma != INVALID_HANDLE) IndicatorRelease(h_sma);
}

void Procesar()
{
   if(ActivarZonaRuido) ProcesarZona();
   if(ActivarRSI2)      ProcesarRSI();
}

void OnTick()  { Procesar(); }
void OnTimer() { Procesar(); }
//+------------------------------------------------------------------+
