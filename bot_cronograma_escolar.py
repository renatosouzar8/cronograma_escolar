#!/usr/bin/env python3
"""
Bot Cronograma Escolar – lembrete 1 dia antes (14h) via Webhook no Render

Dependências (requirements.txt):
  python-telegram-bot[job-queue,webhooks]==20.8
  pytz==2024.1

Estrutura:
  ├── bot_cronograma_escolar.py   # este script
  ├── requirements.txt
  └── cronogramas/                # CSVs data;hora;titulo;descricao;local
"""

import os
import csv
import json
import logging
from datetime import datetime, date, time, timedelta
from pathlib import Path

import pytz
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ─── Configuração ──────────────────────────────────────────
# Token fornecido e webhook configurado
token = "7981598752:AAFCkvUV-b_9HogUDCMUBbjAdcGbLBt48lU"
HOUR = int(os.getenv("NOTIFICATION_HOUR", "14"))
PORT = int(os.getenv("PORT", "10000"))
DOMAIN = "https://cronograma-escolar.onrender.com"
WEBHOOK_URL = f"{DOMAIN}/{token}"

# Fuso horário e caminhos
TZ = pytz.timezone("America/Sao_Paulo")
BASE_DIR = Path(__file__).parent.resolve()
CRON_DIR = BASE_DIR / "cronogramas"
SUBS_FILE = BASE_DIR / "subscribers.json"

# Comandos para autocomplete
COMMANDS = [
    ("start",    "Começar a receber lembretes"),
    ("stop",     "Parar de receber lembretes"),
    ("hoje",     "Eventos que ocorrerão amanhã"),
    ("proximos", "Próximos eventos por cronograma"),
    ("menu",     "Mostrar menu de ajuda"),
]

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ─── post_init: limpa webhook pendente, registra comandos e define webhook ────
async def post_init(app):
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.bot.set_my_commands(COMMANDS)
    await app.bot.set_webhook(WEBHOOK_URL)
    log.info("Webhook limpo, comandos registrados e webhook definido em %s", WEBHOOK_URL)

# ─── Utilitários ───────────────────────────────────────────────

def parse_date(s: str) -> date | None:
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def load_events() -> list[dict]:
    events = []
    if not CRON_DIR.exists():
        log.warning("Pasta cronogramas/ não encontrada ou vazia.")
        return events

    for csv_path in CRON_DIR.glob("*.csv"):
        with csv_path.open(encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                d = parse_date(row.get("data", ""))
                if not d:
                    continue
                events.append({
                    "date": d,
                    "title": row.get("titulo") or "(sem título)",
                    "descr": row.get("descricao", "").strip(),
                    "local": row.get("local", "").strip(),
                    "src": csv_path.name,
                })
    log.info("Eventos lidos: %d", len(events))
    return events


def load_subs() -> list[int]:
    return json.loads(SUBS_FILE.read_text()) if SUBS_FILE.exists() else []


def save_subs(subs: list[int]):
    SUBS_FILE.write_text(json.dumps(subs))

# ─── Handlers de comando ────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    subs = load_subs()
    if cid not in subs:
        subs.append(cid)
        save_subs(subs)
    await update.message.reply_text(
        f"✅ Inscrito! Você receberá lembretes às {HOUR}h do dia anterior.\n"
        "Use /proximos, /hoje ou /menu."
    )


async def stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    subs = load_subs()
    if cid in subs:
        subs.remove(cid)
        save_subs(subs)
    await update.message.reply_text("🛑 Você foi removido e não receberá mais lembretes.")


async def proximos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(TZ).date()
    evs = [e for e in sorted(load_events(), key=lambda e: e["date"]) if e["date"] >= today]
    if not evs:
        await update.message.reply_text("Nenhum evento futuro encontrado.")
        return

    grupos: dict[str, list[dict]] = {}
    for e in evs:
        grupos.setdefault(e["src"], []).append(e)

    msgs = []
    LIMITE = 5
    for src, lista in grupos.items():
        nome = "Théo" if "theo" in src.lower() else "Liz"
        linhas = [f"*Próximos eventos – {nome}:*"]
        for ev in lista[:LIMITE]:
            linhas.append(f"• {ev['date'].strftime('%d/%m')}: {ev['title']}")
        msgs.append("\n".join(linhas))

    await update.message.reply_text("\n\n".join(msgs), parse_mode="Markdown")


async def hoje(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tomorrow = (datetime.now(TZ) + timedelta(days=1)).date()
    evs = [e for e in load_events() if e["date"] == tomorrow]
    if not evs:
        await update.message.reply_text("Não há eventos agendados para amanhã.")
        return

    grupos: dict[str, list[dict]] = {}
    for e in evs:
        grupos.setdefault(e["src"], []).append(e)

    partes = []
    for src, lista in grupos.items():
        nome = "Théo" if "theo" in src.lower() else "Liz"
        linhas = [f"*Eventos de amanhã – {nome}:*"]
        for ev in lista:
            linhas.append(f"• {ev['title']}")
        partes.append("\n".join(linhas))

    await update.message.reply_text("\n\n".join(partes), parse_mode="Markdown")


async def menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    teclas = [["/hoje", "/proximos"], ["/start", "/stop"]]
    kb = ReplyKeyboardMarkup(teclas, resize_keyboard=True, one_time_keyboard=True)
    texto = (
        "*Menu de comandos*\n\n"
        "📅 /hoje ‒ eventos de amanhã\n"
        "📆 /proximos ‒ próximos eventos por cronograma\n"
        "✅ /start ‒ receber lembretes\n"
        "⛔ /stop ‒ cancelar lembretes\n"
    )
    await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=kb)

# ─── Notificação agendada ────────────────────────────────────────────
async def notify(ctx: ContextTypes.DEFAULT_TYPE):
    ev = ctx.job.data
    msg = "🗓️ *Lembrete de amanhã!*\n"
    msg += f"*Data:* {ev['date'].strftime('%d/%m')}\n"
    msg += f"*Evento:* {ev['title']}\n"
    if ev["local"]:
        msg += f"*Local:* {ev['local']}\n"
    if ev["descr"]:
        msg += f"*Descrição:* {ev['descr']}\n"
    msg += f"\n📋 Cronograma: {ev['src']}"

    for cid in load_subs():
        await ctx.bot.send_message(cid, msg, parse_mode="Markdown")


def schedule_jobs(app):
    now = datetime.now(TZ)
    for ev in load_events():
        run_dt = datetime.combine(
            ev["date"] - timedelta(days=1),
            time(HOUR, 0),
            tzinfo=TZ
        )
        if run_dt > now:
            app.job_queue.run_once(notify, when=run_dt, data=ev)
            log.info("Agendado %s para %s", ev["title"], run_dt)

# ─── Inicialização via Webhook ─────────────────────────────────────────
if __name__ == "__main__":
    app = (
        ApplicationBuilder()
        .token(token)
        .post_init(post_init)
        .build()
    )

    # registra handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("proximos", proximos))
    app.add_handler(CommandHandler("hoje", hoje))
    app.add_handler(CommandHandler("menu", menu))

    # agenda lembretes
    schedule_jobs(app)

    log.info("Definindo webhook URL: %s", WEBHOOK_URL)
    log.info("Iniciando listener webhook na porta %d", PORT)
    # start webhook listener (não usar polling em ambiente de webhooks)
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        path=f"/{token}",
        webhook_url=WEBHOOK_URL,
        drop_pending_updates=True,
    )
