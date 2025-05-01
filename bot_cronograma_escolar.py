#!/usr/bin/env python3
"""
Bot Cronograma Escolar – lembrete 1 dia antes (14h) via Webhook no Render

Dependências (requirements.txt):
  python-telegram-bot[job-queue,webhooks]==20.8
  pytz==2024.1
  python-dotenv==1.0.1

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
    MessageHandler,
    filters,
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
    ("status",   "Verificar status do webhook"),
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
    
    # Registra detalhes do webhook antes de configurá-lo
    webhook_info = await app.bot.get_webhook_info()
    log.info("Status atual do webhook: %s", webhook_info)
    
    # Configura o webhook
    result = await app.bot.set_webhook(WEBHOOK_URL)
    log.info("Resultado da configuração do webhook: %s", result)
    
    # Verifica se o webhook foi configurado corretamente
    webhook_info = await app.bot.get_webhook_info()
    log.info("Status do webhook após configuração: %s", webhook_info)
    
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
    log.info("Carregando assinantes de %s", SUBS_FILE)
    if SUBS_FILE.exists():
        content = SUBS_FILE.read_text()
        log.info("Conteúdo do arquivo de assinantes: %s", content)
        return json.loads(content) 
    else:
        log.warning("Arquivo de assinantes não encontrado")
        return []


def save_subs(subs: list[int]):
    log.info("Salvando %d assinantes em %s", len(subs), SUBS_FILE)
    SUBS_FILE.write_text(json.dumps(subs))

# ─── Handlers de comando ────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    log.info("Comando /start recebido de %s", update.effective_chat.id)
    cid = update.effective_chat.id
    subs = load_subs()
    if cid not in subs:
        subs.append(cid)
        save_subs(subs)
        log.info("Usuário %s inscrito com sucesso", cid)
    else:
        log.info("Usuário %s já estava inscrito", cid)
    await update.message.reply_text(
        f"✅ Inscrito! Você receberá lembretes às {HOUR}h do dia anterior.\n"
        "Use /proximos, /hoje ou /menu."
    )


async def stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    log.info("Comando /stop recebido de %s", update.effective_chat.id)
    cid = update.effective_chat.id
    subs = load_subs()
    if cid in subs:
        subs.remove(cid)
        save_subs(subs)
        log.info("Usuário %s removido com sucesso", cid)
    else:
        log.info("Usuário %s não estava inscrito", cid)
    await update.message.reply_text("🛑 Você foi removido e não receberá mais lembretes.")


async def proximos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    log.info("Comando /proximos recebido de %s", update.effective_chat.id)
    today = datetime.now(TZ).date()
    evs = [e for e in sorted(load_events(), key=lambda e: e["date"]) if e["date"] >= today]
    if not evs:
        log.info("Nenhum evento futuro encontrado")
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
    log.info("Resposta de /proximos enviada")


async def hoje(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    log.info("Comando /hoje recebido de %s", update.effective_chat.id)
    tomorrow = (datetime.now(TZ) + timedelta(days=1)).date()
    evs = [e for e in load_events() if e["date"] == tomorrow]
    if not evs:
        log.info("Nenhum evento para amanhã")
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
    log.info("Resposta de /hoje enviada")


async def menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    log.info("Comando /menu recebido de %s", update.effective_chat.id)
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
    log.info("Resposta de /menu enviada")


# Novo comando para verificar o status do webhook
async def status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    log.info("Comando /status recebido de %s", update.effective_chat.id)
    webhook_info = await ctx.bot.get_webhook_info()
    info_text = (
        f"*Status do Webhook*\n\n"
        f"URL: `{webhook_info.url}`\n"
        f"Mensagens pendentes: {webhook_info.pending_update_count}\n"
    )
    
    if webhook_info.last_error_date:
        error_date = datetime.fromtimestamp(webhook_info.last_error_date, TZ).strftime('%Y-%m-%d %H:%M:%S')
        info_text += f"Último erro: {error_date}\n"
        info_text += f"Mensagem de erro: {webhook_info.last_error_message}\n"
    else:
        info_text += "Sem erros recentes.\n"
    
    info_text += f"\nInscritos: {len(load_subs())}"
    
    await update.message.reply_text(info_text, parse_mode="Markdown")
    log.info("Resposta de /status enviada")


# Handler para registrar todas as mensagens recebidas
async def echo_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    log.info("Mensagem recebida: '%s' de %s", update.message.text, update.effective_chat.id)
    await update.message.reply_text(f"Recebi sua mensagem: {update.message.text}")
    log.info("Resposta de echo enviada")

# ─── Notificação agendada ────────────────────────────────────────────
async def notify(ctx: ContextTypes.DEFAULT_TYPE):
    ev = ctx.job.data
    log.info("Enviando notificação para o evento: %s", ev["title"])
    msg = "🗓️ *Lembrete de amanhã!*\n"
    msg += f"*Data:* {ev['date'].strftime('%d/%m')}\n"
    msg += f"*Evento:* {ev['title']}\n"
    if ev["local"]:
        msg += f"*Local:* {ev['local']}\n"
    if ev["descr"]:
        msg += f"*Descrição:* {ev['descr']}\n"
    msg += f"\n📋 Cronograma: {ev['src']}"

    subs = load_subs()
    log.info("Enviando notificação para %d assinantes", len(subs))
    for cid in subs:
        try:
            await ctx.bot.send_message(cid, msg, parse_mode="Markdown")
            log.info("Notificação enviada para %s", cid)
        except Exception as e:
            log.error("Erro ao enviar notificação para %s: %s", cid, e)


def schedule_jobs(app):
    now = datetime.now(TZ)
    log.info("Agendando lembretes (hora atual: %s)", now)
    for ev in load_events():
        run_dt = datetime.combine(
            ev["date"] - timedelta(days=1),
            time(HOUR, 0),
            tzinfo=TZ
        )
        if run_dt > now:
            app.job_queue.run_once(notify, when=run_dt, data=ev)
            log.info("Agendado %s para %s", ev["title"], run_dt)
        else:
            log.info("Evento %s ignorado (já passou: %s)", ev["title"], run_dt)

# ─── Inicialização via Webhook ─────────────────────────────────────────
if __name__ == "__main__":
    log.info("Iniciando aplicação...")
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
    app.add_handler(CommandHandler("status", status))
    
    # Este handler captura todas as mensagens que não são comandos
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_all))

    # agenda lembretes
    schedule_jobs(app)

    log.info("Definindo webhook URL: %s", WEBHOOK_URL)
    log.info("Iniciando listener webhook na porta %d", PORT)
    # start webhook listener (não usar polling em ambiente de webhooks)
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL,
        drop_pending_updates=True,
    )
