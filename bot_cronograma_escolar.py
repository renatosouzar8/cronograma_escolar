#!/usr/bin/env python3
"""
Função melhorada para carregamento de eventos de cronogramas.
Este snippet deve substituir a função load_events() no seu código principal.
"""

def load_events() -> list[dict]:
    events = []
    if not CRON_DIR.exists():
        log.warning("Pasta cronogramas/ não encontrada ou vazia.")
        return events

    # Lista todos os arquivos CSV encontrados
    csv_files = list(CRON_DIR.glob("*.csv"))
    log.info("Arquivos CSV encontrados: %s", [f.name for f in csv_files])
    
    if not csv_files:
        log.warning("Nenhum arquivo CSV encontrado na pasta cronogramas/")
        return events

    for csv_path in csv_files:
        log.info("Processando arquivo: %s", csv_path.name)
        try:
            with csv_path.open(encoding="utf-8-sig") as f:
                # Registra os primeiros bytes para verificar BOM e codificação
                content = f.read()
                log.info("Tamanho do arquivo %s: %d bytes", csv_path.name, len(content))
                
                # Reinicia a posição do arquivo para leitura com DictReader
                f.seek(0)
                
                reader = csv.DictReader(f, delimiter=";")
                if not reader.fieldnames:
                    log.error("Arquivo %s não tem cabeçalhos válidos", csv_path.name)
                    continue
                
                log.info("Cabeçalhos encontrados: %s", reader.fieldnames)
                
                arquivo_events = []
                for i, row in enumerate(reader):
                    log.info("Processando linha %d: %s", i+1, row)
                    d = parse_date(row.get("data", ""))
                    if not d:
                        log.warning("Data inválida na linha %d: %s", i+1, row.get("data"))
                        continue
                    
                    arquivo_events.append({
                        "date": d,
                        "title": row.get("titulo") or "(sem título)",
                        "descr": row.get("descricao", "").strip(),
                        "local": row.get("local", "").strip(),
                        "src": csv_path.name,
                    })
                
                log.info("Eventos lidos do arquivo %s: %d", csv_path.name, len(arquivo_events))
                events.extend(arquivo_events)
        except Exception as e:
            log.error("Erro ao ler arquivo %s: %s", csv_path, e)
    
    log.info("Total de eventos lidos: %d", len(events))
    
    # Registra todos os eventos para depuração
    for i, ev in enumerate(events):
        log.info("Evento %d: %s em %s (fonte: %s)", 
                i+1, ev["title"], ev["date"].strftime("%d/%m/%Y"), ev["src"])
    
    return events

# Função melhorada para verificar eventos de amanhã
async def hoje(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    log.info("Comando /hoje recebido de %s", update.effective_chat.id)
    try:
        tomorrow = (datetime.now(TZ) + timedelta(days=1)).date()
        log.info("Verificando eventos para amanhã: %s", tomorrow.strftime("%d/%m/%Y"))
        
        all_events = load_events()
        log.info("Total de eventos carregados: %d", len(all_events))
        
        evs = [e for e in all_events if e["date"] == tomorrow]
        log.info("Eventos encontrados para amanhã: %d", len(evs))
        
        if not evs:
            log.info("Nenhum evento para amanhã")
            await update.message.reply_text("Não há eventos agendados para amanhã.")
            return

        # Registra os eventos encontrados
        for i, ev in enumerate(evs):
            log.info("Evento de amanhã %d: %s (fonte: %s)", 
                     i+1, ev["title"], ev["src"])

        grupos: dict[str, list[dict]] = {}
        for e in evs:
            grupos.setdefault(e["src"], []).append(e)

        log.info("Grupos encontrados: %s", list(grupos.keys()))

        partes = []
        for src, lista in grupos.items():
            nome = "Théo" if "theo" in src.lower() else "Liz"
            log.info("Processando grupo %s (%s): %d eventos", src, nome, len(lista))
            
            linhas = [f"*Eventos de amanhã – {nome}:*"]
            for ev in lista:
                linhas.append(f"• {ev['title']}")
            partes.append("\n".join(linhas))

        await update.message.reply_text("\n\n".join(partes), parse_mode="Markdown")
        log.info("Resposta de /hoje enviada")
    except Exception as e:
        log.error("Erro ao processar comando /hoje: %s", e)
        await update.message.reply_text("Ocorreu um erro. Por favor, tente novamente.")
