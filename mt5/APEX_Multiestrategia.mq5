//+------------------------------------------------------------------+
//| APEX_Multiestrategia.mq5                                         |
//| Multiestrategia para CUENTA DEMO (NAS100) con gestor de riesgo   |
//| de cartera común. Solo incluye estrategias VALIDADAS:            |
//|  0) ZONA_RUIDO_MNQ_v1.0 (edges/zona_ruido_mnq.md), intradía       |
//|  1) RSI(2) de Connors (edges/nq_rsi2.md), swing diario           |
//| Estrategias probadas y RECHAZADAS (no se incluyen): SMC kill     |
//| zones, rango+London+VWAP, VWAP 15m, VWAP+EMAs, oro (zona ruido,  |
//| RSI2, pares oro/plata) y el bot de oferta/demanda de oro.        |
//|                                                                  |
//| Gestor de cartera (solo cuenta las operaciones de ESTE EA, por   |
//| sus magic numbers; otros bots de la cuenta no le afectan):       |
//|  - pérdida máxima diaria de la cartera -> no abre más hasta el   |
//|    día siguiente (NY); opcionalmente cierra lo abierto           |
//|  - caída máxima desde el máximo de la cartera -> cierra todo y   |
//|    se DETIENE hasta que el usuario lo reinicie a mano            |
//| Las salidas de las estrategias nunca se bloquean.                |
//|                                                                  |
//| Añadir una estrategia (solo si pasa el protocolo del proyecto):  |
//|  1) nuevo índice E_xxx y su fila en InicializarRegistro()        |
//|  2) su función ProcesarXxx() usando Abrir()/Cerrar()/Posicion()  |
//|  3) llamarla en Procesar()                                       |
//+------------------------------------------------------------------+
#property copyright "Proyecto APEX (uso en demo)"
#property version   "2.00"

#include <Trade/Trade.mqh>

//--- Entradas
input group "Horario"
input int    DesfaseServidorNY  = 7;       // Horas servidor - Nueva York (Pepperstone MT5: 7)
input group "Gestor de riesgo de la CARTERA (en dinero de la cuenta)"
input double PerdidaDiariaMax   = 1000.0;  // pérdida del día (cerrado + abierto) que bloquea NUEVAS entradas hasta mañana
                                           // (histórico 2015-2026 con 1+1 MNQ: 8 días en 11 años)
input double CaidaMaximaCartera = 5000.0;  // caída desde el máximo que DETIENE la cartera (PLAN_OPERATIVO: 5.000 $;
                                           // peor caída histórica del backtest con 1+1 MNQ: 4.713 $)
input bool   CerrarAlFrenarDia  = false;   // límite diario: false = solo bloquea entradas (no altera las reglas validadas)
input bool   CerrarAlDetener    = true;    // caída máxima: cerrar todo
input bool   ReiniciarFreno     = false;   // ponlo en true UNA vez para reanudar tras una detención (luego false)
input group "Zona de ruido (intradía)"
input bool   ActivarZonaRuido   = true;
input double DineroPorPuntoZona = 2.0;     // presupuesto: 1 MNQ = 2 $/punto
input int    DiasRuido          = 14;
input int    MinDiasRuido       = 10;
input long   MagicZona          = 290901;
input group "RSI(2) (swing, mantiene posiciones de noche)"
input bool   ActivarRSI2        = true;
input double DineroPorPuntoRSI  = 2.0;     // presupuesto: 1 MNQ = 2 $/punto
input double RsiEntrada         = 20.0;
input double RsiSalida          = 70.0;
input int    MaxSesiones        = 5;
input long   MagicRSI           = 290902;
input group "Avisos por Telegram (opcional)"
input string TelegramToken      = "";
input string TelegramChatId     = "";

//--- Registro de estrategias
#define N_ESTRATEGIAS 2
#define E_ZONA 0
#define E_RSI  1
struct Estrategia
{
   string nombre;
   long   magic;
   bool   activa;
   double dineroPorPunto;
};
Estrategia g_est[N_ESTRATEGIAS];

void InicializarRegistro()
{
   g_est[E_ZONA].nombre = "Zona de ruido"; g_est[E_ZONA].magic = MagicZona; g_est[E_ZONA].activa = ActivarZonaRuido; g_est[E_ZONA].dineroPorPunto = DineroPorPuntoZona;
   g_est[E_RSI].nombre  = "RSI(2)";        g_est[E_RSI].magic  = MagicRSI;  g_est[E_RSI].activa  = ActivarRSI2;      g_est[E_RSI].dineroPorPunto  = DineroPorPuntoRSI;
}

bool EsNuestro(long magic)
{
   for(int e = 0; e < N_ESTRATEGIAS; e++) if(g_est[e].magic == magic) return true;
   return false;
}

//--- Constantes de la sesión regular de NY (minutos desde las 09:30)
#define MIN_SESION        390
#define PRIMER_CHEQUEO    30
#define ULTIMO_CHEQUEO    360
#define CADA              30

CTrade trade;

//--- Estado de la zona de ruido
int      g_dia = 0;
bool     g_listo = false;
double   g_apertura = 0, g_cierreAnt = 0;
double   g_sigma[MIN_SESION];
int      g_ultimoChequeo = -1;
bool     g_cerradoFin = false;
datetime g_ultimoIntento = 0;

//--- Estado del RSI(2)
int      h_rsi = INVALID_HANDLE, h_sma = INVALID_HANDLE;
datetime g_ultimaD1 = 0;
datetime g_reintentoRSI = 0;

//--- Estado de la cartera (persistente en variables globales del terminal: sobrevive a reinicios)
string   GV_INICIO, GV_PICO, GV_DETENIDA;
int      g_diaCartera = 0;
double   g_pnlInicioDia = 0;
bool     g_frenadaHoy = false;
datetime g_ultimaRevision = 0;

//+------------------------------------------------------------------+
datetime AhoraNY()                 { return TimeCurrent() - DesfaseServidorNY * 3600; }
datetime NYaServidor(datetime ny)  { return ny + DesfaseServidorNY * 3600; }
int      FechaNY(datetime ny)      { MqlDateTime t; TimeToStruct(ny, t); return t.year * 10000 + t.mon * 100 + t.day; }
datetime InicioDiaNY(datetime ny)  { MqlDateTime t; TimeToStruct(ny, t); t.hour = 0; t.min = 0; t.sec = 0; return StructToTime(t); }
int      MinutoSesion(datetime ny) { MqlDateTime t; TimeToStruct(ny, t); return (t.hour - 9) * 60 + t.min - 30; }

double Lotes(int e)
{
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double paso = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(tv <= 0 || ts <= 0 || paso <= 0) return vmin;
   double lotes = g_est[e].dineroPorPunto / (tv / ts);
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
   ArrayResize(datos, n - 1);
   int r = WebRequest("POST", url, "Content-Type: application/json\r\n", 5000, datos, resp, cab);
   if(r != 200) Print("Telegram: error ", r, " (¿añadiste https://api.telegram.org en Herramientas > Opciones > Asesores?)");
}

// Registro de ejecuciones (solo registro: no interviene en ninguna decisión). v2 (30-sep-2026, forward testing):
// añade bid/ask justo antes de enviar la orden, spread, deal, lotes y magic. El motivo se guarda sin comas.
void Registrar(string estrategia, string accion, double precio, string motivo, double bid = 0, double ask = 0,
               ulong deal = 0, double lotes = 0, long magic = 0)
{
   int f = FileOpen("APEX_registro_v2.csv", FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(f == INVALID_HANDLE) return;
   if(FileSize(f) == 0) FileWrite(f, "hora_servidor", "hora_NY", "estrategia", "accion", "precio", "bid_previo", "ask_previo",
                                  "spread_previo", "deal", "lotes", "magic", "motivo");
   FileSeek(f, 0, SEEK_END);
   string m = motivo;
   StringReplace(m, ",", ";");
   FileWrite(f, TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS), TimeToString(AhoraNY(), TIME_DATE | TIME_SECONDS),
             estrategia, accion, DoubleToString(precio, _Digits), DoubleToString(bid, _Digits), DoubleToString(ask, _Digits),
             DoubleToString(ask - bid, _Digits), IntegerToString((long)deal), DoubleToString(lotes, 2), IntegerToString(magic), m);
   FileClose(f);
}

int Posicion(int e)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != g_est[e].magic) continue;
      return PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
   }
   return 0;
}

datetime AperturaPosicion(int e)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk != 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == g_est[e].magic)
         return (datetime)PositionGetInteger(POSITION_TIME);
   }
   return 0;
}

bool Cerrar(int e, string motivo)
{
   bool ok = true;
   trade.SetExpertMagicNumber(g_est[e].magic);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != g_est[e].magic) continue;
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double vol = PositionGetDouble(POSITION_VOLUME);
      if(trade.PositionClose(tk))
      {
         Registrar(g_est[e].nombre, "CERRAR", trade.ResultPrice(), motivo, bid, ask, trade.ResultDeal(), vol, g_est[e].magic);
         Telegram("🔴 " + g_est[e].nombre + ": CERRADA a " + DoubleToString(trade.ResultPrice(), _Digits) + " (" + motivo + ")");
      }
      else { ok = false; Print(g_est[e].nombre, ": error al cerrar ", trade.ResultRetcode()); }
   }
   return ok;
}

//+------------------------------------------------------------------+
//| Gestor de riesgo de la cartera                                   |
//+------------------------------------------------------------------+
// Resultado acumulado de ESTE EA desde que empezó a operar (cerrado + abierto, con swap y comisiones).
double PnLCartera()
{
   datetime desde = (datetime)GlobalVariableGet(GV_INICIO);
   double pnl = 0;
   if(HistorySelect(desde, TimeCurrent() + 60))
   {
      for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
      {
         ulong d = HistoryDealGetTicket(i);
         if(d == 0 || !EsNuestro(HistoryDealGetInteger(d, DEAL_MAGIC))) continue;
         pnl += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_SWAP) + HistoryDealGetDouble(d, DEAL_COMMISSION);
      }
   }
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !EsNuestro(PositionGetInteger(POSITION_MAGIC))) continue;
      pnl += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
   }
   return pnl;
}

void CerrarTodo(string motivo)
{
   for(int e = 0; e < N_ESTRATEGIAS; e++) if(Posicion(e) != 0) Cerrar(e, motivo);
}

bool CarteraDetenida() { return GlobalVariableGet(GV_DETENIDA) > 0.5; }

// Se llama cada pocos segundos: actualiza máximo, límite diario y detención.
void RevisarCartera()
{
   if(TimeCurrent() - g_ultimaRevision < 5) return;
   g_ultimaRevision = TimeCurrent();
   double pnl = PnLCartera();
   int hoy = FechaNY(AhoraNY());
   if(hoy != g_diaCartera) { g_diaCartera = hoy; g_pnlInicioDia = pnl; g_frenadaHoy = false; }
   double pico = GlobalVariableGet(GV_PICO);
   if(pnl > pico) { pico = pnl; GlobalVariableSet(GV_PICO, pico); }
   if(!CarteraDetenida() && pico - pnl >= CaidaMaximaCartera)
   {
      GlobalVariableSet(GV_DETENIDA, 1);
      GlobalVariablesFlush();
      if(CerrarAlDetener) CerrarTodo("cartera detenida: caída máxima");
      Telegram(StringFormat("⛔ CARTERA DETENIDA: caída de %.0f desde el máximo (límite %.0f). No abrirá más operaciones "
                            "hasta que la reinicies (ReiniciarFreno=true). Revisa antes si la estrategia sigue dentro de lo esperado.",
                            pico - pnl, CaidaMaximaCartera));
   }
   if(!g_frenadaHoy && g_pnlInicioDia - pnl >= PerdidaDiariaMax)
   {
      g_frenadaHoy = true;
      if(CerrarAlFrenarDia) CerrarTodo("límite de pérdida diaria de la cartera");
      Telegram(StringFormat("🟥 Límite diario de la cartera: %.0f hoy (límite %.0f). Sin nuevas entradas hasta mañana.",
                            g_pnlInicioDia - pnl, PerdidaDiariaMax));
   }
}

bool PuedeAbrir(int e, string &porque)
{
   if(!g_est[e].activa)   { porque = "estrategia desactivada"; return false; }
   if(CarteraDetenida())  { porque = "cartera detenida (caída máxima)"; return false; }
   if(g_frenadaHoy)       { porque = "límite de pérdida diaria de la cartera"; return false; }
   return true;
}

bool Abrir(int e, int dir, string motivo)
{
   string porque = "";
   if(!PuedeAbrir(e, porque)) { Print(g_est[e].nombre, ": entrada bloqueada (", porque, "). ", motivo); return true; }   // true: no reintentar
   trade.SetExpertMagicNumber(g_est[e].magic);
   double lotes = Lotes(e);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   bool ok = dir == 1 ? trade.Buy(lotes, _Symbol) : trade.Sell(lotes, _Symbol);
   if(ok && (trade.ResultRetcode() == TRADE_RETCODE_DONE || trade.ResultRetcode() == TRADE_RETCODE_PLACED))
   {
      Registrar(g_est[e].nombre, dir == 1 ? "COMPRAR" : "VENDER", trade.ResultPrice(), motivo, bid, ask, trade.ResultDeal(),
                lotes, g_est[e].magic);
      Telegram((dir == 1 ? "🟢 " : "🟠 ") + g_est[e].nombre + ": " + (dir == 1 ? "COMPRA " : "VENTA ") + DoubleToString(lotes, 2) +
               " lotes a " + DoubleToString(trade.ResultPrice(), _Digits) + " (" + motivo + ")");
      return true;
   }
   Print(g_est[e].nombre, ": error al abrir ", trade.ResultRetcode());
   return false;
}

//+------------------------------------------------------------------+
//| Estrategia 0: zona de ruido                                      |
//+------------------------------------------------------------------+
int VelasSesion(datetime inicioDiaNY, int hastaMin, MqlRates &por_min[], bool &hay[])
{
   ArrayResize(por_min, MIN_SESION); ArrayResize(hay, MIN_SESION);
   for(int m = 0; m < MIN_SESION; m++) hay[m] = false;
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

bool PrepararDia(datetime ahoraNY)
{
   datetime hoy = InicioDiaNY(ahoraNY);
   MqlRates velas[]; bool hay[];
   if(VelasSesion(hoy, 0, velas, hay) == 0 || !hay[0]) return false;
   g_apertura = velas[0].open;
   double suma[MIN_SESION]; int cnt[MIN_SESION];
   ArrayInitialize(suma, 0); ArrayInitialize(cnt, 0);
   int dias = 0; g_cierreAnt = 0;
   for(int k = 1; k <= 40 && dias < DiasRuido; k++)
   {
      datetime d = hoy - k * 86400;
      MqlRates v[]; bool h[];
      if(VelasSesion(d, MIN_SESION - 1, v, h) < 60) continue;
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
   double pv = 0, vol = 0;
   for(int m = 0; m < minuto; m++)
      if(h[m]) { double tip = (v[m].high + v[m].low + v[m].close) / 3.0; pv += tip * (double)v[m].tick_volume; vol += (double)v[m].tick_volume; }
   double vwap = vol > 0 ? pv / vol : v[minuto - 1].close;
   double p = v[minuto - 1].close, s = g_sigma[minuto - 1];
   double sup = MathMax(g_apertura, g_cierreAnt) * (1 + s), inf = MathMin(g_apertura, g_cierreAnt) * (1 - s);
   string info = StringFormat("precio %s, bandas %s / %s, VWAP %s", DoubleToString(p, _Digits), DoubleToString(sup, _Digits),
                              DoubleToString(inf, _Digits), DoubleToString(vwap, _Digits));
   int pos = Posicion(E_ZONA);
   if(pos == 1 && p < MathMax(sup, vwap))       { if(Cerrar(E_ZONA, "trailing: " + info)) pos = 0; }
   else if(pos == -1 && p > MathMin(inf, vwap)) { if(Cerrar(E_ZONA, "trailing: " + info)) pos = 0; }
   if(pos == 0)
   {
      if(p > sup)      Abrir(E_ZONA, 1, "sobre la banda superior: " + info);
      else if(p < inf) Abrir(E_ZONA, -1, "bajo la banda inferior: " + info);
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
      if(Posicion(E_ZONA) != 0) Cerrar(E_ZONA, "posición de otro día");
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
   if(!g_cerradoFin && (minuto > MIN_SESION - 1 || (minuto == MIN_SESION - 1 && t.sec >= 50)))
   {
      g_cerradoFin = true;
      if(Posicion(E_ZONA) != 0) Cerrar(E_ZONA, "fin de sesión");
      return;
   }
   int c = (minuto / CADA) * CADA;
   if(c >= PRIMER_CHEQUEO && c <= ULTIMO_CHEQUEO && c > g_ultimoChequeo && minuto - c < 2)
   {
      g_ultimoChequeo = c;
      Chequeo(ny, c);
   }
}

//+------------------------------------------------------------------+
//| Estrategia 1: RSI(2)                                             |
//+------------------------------------------------------------------+
void ProcesarRSI()
{
   datetime d1 = iTime(_Symbol, PERIOD_D1, 0);
   if(d1 == 0 || d1 == g_ultimaD1) return;
   if(TimeCurrent() - g_reintentoRSI < 60) return;
   g_reintentoRSI = TimeCurrent();
   double rsi[1], sma[1];
   if(CopyBuffer(h_rsi, 0, 1, 1, rsi) != 1 || CopyBuffer(h_sma, 0, 1, 1, sma) != 1) return;
   bool hecho = true;
   double cierre = iClose(_Symbol, PERIOD_D1, 1);
   string info = StringFormat("RSI(2)=%.1f, cierre %s, SMA200 %s", rsi[0], DoubleToString(cierre, _Digits), DoubleToString(sma[0], _Digits));
   if(Posicion(E_RSI) == 1)
   {
      int sesiones = iBarShift(_Symbol, PERIOD_D1, AperturaPosicion(E_RSI));
      if(rsi[0] > RsiSalida)           hecho = Cerrar(E_RSI, "RSI > " + DoubleToString(RsiSalida, 0) + ": " + info);
      else if(sesiones >= MaxSesiones) hecho = Cerrar(E_RSI, IntegerToString(sesiones) + " sesiones: " + info);
      else Print("RSI(2): sigue la posición (", sesiones, " sesiones). ", info);
   }
   else if(cierre > sma[0] && rsi[0] < RsiEntrada)
      hecho = Abrir(E_RSI, 1, "señal: " + info);
   else
      Print("RSI(2): sin señal. ", info);
   if(hecho) g_ultimaD1 = d1;
}

//+------------------------------------------------------------------+
int OnInit()
{
   InicializarRegistro();
   int activas = 0;
   for(int e = 0; e < N_ESTRATEGIAS; e++) if(g_est[e].activa) activas++;
   if(activas > 1 && AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
   {
      Alert("La cuenta no es de cobertura (hedging): las estrategias se compensarían entre sí. Usa una cuenta hedging o activa solo una.");
      return INIT_PARAMETERS_INCORRECT;
   }
   string base = StringFormat("APEX_%I64d_%s_", AccountInfoInteger(ACCOUNT_LOGIN), _Symbol);
   GV_INICIO = base + "inicio"; GV_PICO = base + "pico"; GV_DETENIDA = base + "detenida";
   if(!GlobalVariableCheck(GV_INICIO)) GlobalVariableSet(GV_INICIO, (double)TimeCurrent());
   if(!GlobalVariableCheck(GV_PICO))   GlobalVariableSet(GV_PICO, 0.0);
   if(ReiniciarFreno)
   {
      GlobalVariableSet(GV_DETENIDA, 0);
      GlobalVariableSet(GV_PICO, PnLCartera());         // el nuevo máximo es el punto de partida actual
      GlobalVariablesFlush();
      Telegram("♻️ Cartera reanudada a mano. Vuelve a poner ReiniciarFreno = false.");
   }
   h_rsi = iRSI(_Symbol, PERIOD_D1, 2, PRICE_CLOSE);
   h_sma = iMA(_Symbol, PERIOD_D1, 200, 0, MODE_SMA, PRICE_CLOSE);
   if(h_rsi == INVALID_HANDLE || h_sma == INVALID_HANDLE) return INIT_FAILED;
   g_ultimaD1 = iTime(_Symbol, PERIOD_D1, 0);
   trade.SetDeviationInPoints(20);
   g_diaCartera = FechaNY(AhoraNY());
   g_pnlInicioDia = PnLCartera();
   EventSetTimer(1);
   string est = "";
   for(int e = 0; e < N_ESTRATEGIAS; e++)
      est += StringFormat("\n- %s: %s, %.2f lotes (%.2f por punto)", g_est[e].nombre, g_est[e].activa ? "ACTIVA" : "desactivada",
                          Lotes(e), g_est[e].dineroPorPunto);
   Telegram(StringFormat("🤖 APEX Multiestrategia en %s. Hora NY: %s. Límite diario %.0f, caída máxima %.0f%s%s",
                         _Symbol, TimeToString(AhoraNY(), TIME_DATE | TIME_MINUTES), PerdidaDiariaMax, CaidaMaximaCartera,
                         CarteraDetenida() ? "\n⛔ LA CARTERA ESTÁ DETENIDA" : "", est));
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
   RevisarCartera();
   if(g_est[E_ZONA].activa) ProcesarZona();
   if(g_est[E_RSI].activa)  ProcesarRSI();
}

void OnTick()  { Procesar(); }
void OnTimer() { Procesar(); }
//+------------------------------------------------------------------+
