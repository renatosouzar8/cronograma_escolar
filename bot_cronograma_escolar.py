#!/usr/bin/env python3
"""
Bot Cronograma Escolar – lembrete 1 dia antes às 14 h
Versão 26 abr 2025 (compacto, estável)

Dependências (requirements.txt)
───────────────────────────────
python-telegram-bot[job-queue]==20.8
pytz==2024.1
python-dotenv==1.0.1

Estrutura
─────────
📂 cronogramas/   → CSVs (data;hora;titulo;descricao;local)  
.subscribers.json → criado automaticamente
.env              → TELEGRAM_TOKEN=…  NOTIFICATION_HOUR=14

Principais comandos
──────────────────
/start      – inscrever‑se para lembretes
/stop       – cancelar lembretes
/hoje       – eventos de amanhã (agrupados por cronograma)
/proximos   – próximos 5 eventos de cada cronograma
/menu       – mostra menu com botões rápidos
"""
import csv, json, os, logging
from datetime import datetime, date, time, timedelta
from pathlib import Path

import pytz
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
)

# ─── Config ──────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN") or exit("Falta TELEGRAM_TOKEN no .env")
TZ = pytz.timezone("America/Sao_Paulo")
HOUR = int(os.getenv("NOTIFICATION_HOUR", 14))
CRON_DIR = Path("cronogramas")
SUBS_FILE = Path("subscribers.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ─── Helper functions ───────────────────────────────────

def parse_date(txt: str) -> date | None:
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(txt.strip(), fmt).date()
        except ValueError:
            pass
    return None


def load_events():
    events = []
    for csv_path in CRON_DIR.glob("*.csv"):
        with csv_path.open(encoding="utf-8-sig") as f:
            for row in csv.DictReader(f, delimiter=";"):
                d = parse_date(row.get("data", ""))
                if not d:
                    continue
                events.append(
                    {
                        "date": d,
                        "title": row.get("titulo") or "(sem título)",
                        "local": row.get("local", "").strip(),
                        "descr": row.get("descricao", "").strip(),
                        "src": csv_path.name,
                    }
                )
    log.info("Eventos lidos: %d", len(events))
    return events


def load_subs():
    return json.loads(SUBS_FILE.read_text()) if SUBS_FILE.exists() else []


def save_subs(lst):
    SUBS_FILE.write_text(json.dumps(lst))


def nome_cronograma(src: str) -> str:
    return "Théo" if "theo" in src.lower() else "Liz"

# ─── Comandos ───────────────────────────────────────────
async def start(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = upd.effective_chat.id
    subs = load_subs()
    if cid not in subs:
        subs.append(cid)
        save_subs(subs)
    await upd.message.reply_text(
        "Inscrito! Receberá lembretes às 14 h do dia anterior. Use /menu para ver opções."
    )


async def stop(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = upd.effective_chat.id
    subs = load_subs()
    if cid in subs:
        subs.remove(cid)
        save_subs(subs)
    await upd.message.reply_text("Você foi removido e não receberá mais lembretes.")


async def proximos(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(TZ).date()
    grupos: dict[str, list[dict]] = {}
    for ev in sorted(load_events(), key=lambda e: e["date"]):
        if ev["date"] < today:
            continue
        grupos.setdefault(ev["src"], []).append(ev)

    if not grupos:
        await upd.message.reply_text("Nenhum evento futuro encontrado.")
        return

    LIMITE = 5
    blocos = []
    for src, lista in grupos.items():
        linhas = [f"*Próximos eventos – {nome_cronograma(src)}:*"]
        for ev in lista[:LIMITE]:
            linhas.append(f"• {ev['date'].strftime('%d/%m')}: {ev['title']}")
        blocos.append("\n".join(linhas))

    await upd.message.reply_text("\n\n".join(blocos), parse_mode="Markdown")


async def hoje(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    amanha = (datetime.now(TZ) + timedelta(days=1)).date()
    grupos: dict[str, list[dict]] = {}
    for ev in load_events():
        if ev["date"] == amanha:
            grupos.setdefault(ev["src"], []).append(ev)

    if not grupos:
        await upd.message.reply_text("Não há eventos agendados para amanhã.")
        return

    blocos = []
    for src, lista in grupos.items():
        linhas = [f"*Eventos de amanhã – {nome_cronograma(src)}:*"]
        for ev in lista:
            linhas.append(f"• {ev['title']}")
        blocos.append("\n".join(linhas))

    await upd.message.reply_text("\n\n".join(blocos), parse_mode="Markdown")


async def menu(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    teclas = [["/hoje", "/proximos"], ["/start", "/stop"]]
    kb = ReplyKeyboardMarkup(teclas, resize_keyboard=True, one_time_keyboard=True)
    msg = (
        "*Menu de comandos*\n\n"
        "📅 /hoje – eventos que ocorrerão amanhã\n"
        "📆 /proximos – próximos 5 eventos por cronograma\n"
        "✅ /start – receber lembretes\n"
        "⛔ /stop – parar lembretes\n"
    )
    await upd.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)


# ─── Notificação ───────────────────────────────────────
async def notify(ctx: ContextTypes.DEFAULT_TYPE):
    e = ctx.job.data
    header = "[Théo](https://example.com)" if "theo" in e["src"].lower() else "[Liz](https://example.com)"
    msg = (
        f"🗓️ *Lembrete de amanhã!* {header}\n\n"
        f"*Evento:* {e['title']}\n"
        f"*Data:* {e['date'].strftime('%d/%m')}"
    )
    if e["local"]:
        msg += f"\n*Local:* {e['local']}"
    if e["descr"]:
        msg += f"\n*Descrição:* {e['descr']}"

    for cid in load_subs():
        await ctx.bot.send_message(cid, msg, parse_mode="Markdown")


# ─── Registrar comandos globais ─────────────────────────
COMMANDS = [
    ("start", "Começar a receber lembretes"),
    ("stop", "Parar de receber lembretes"),
    ("hoje", "Eventos que ocorrerão amanhã"),
    ("proximos", "Próximos eventos"),
    ("menu", "Mostrar menu de ajuda"),
]

async def post_init(app):
    await app.bot.set_my_commands(COMMANDS)

# ─── Main ───────────────────────────────────────────────
def main():
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    # handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("hoje", hoje))
    app.add_handler(CommandHandler("proximos", proximos))
    app.add_handler(CommandHandler("menu", menu))

    # agenda
    now = datetime.now(TZ)
    for e in load_events():
        run_dt = datetime.combine(e["date"] - timedelta(days=1), time(HOUR, 0), tzinfo=TZ)
        if run_dt > now:
            app.job_queue.run_once(notify, when=run_dt, data=e)
            log.info("Agendado %s para %s", e["title"], run_dt)

    log.info("Bot pronto. /start para começar. Horário=%dh", HOUR)
    app.run_polling()


if __name__ == "__main__":
    if not CRON_DIR.exists():
        log.warning("Pasta cronogramas/ não encontrada ou vazia.")
    main()
