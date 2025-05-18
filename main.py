import asyncio
from playwright.async_api import async_playwright
import requests
from datetime import datetime

# --- Configurações do Telegram ---
TOKEN = "8103053127:AAF3bObah8glNl6VPEyOhW6ndBwk5AA5kzU"
CHAT_ID = "-1002407164281"

# --- URLs das imagens ---
IMG_B = "Bac%20Bo/B.png"
IMG_P = "Bac%20Bo/P.png"
IMG_T = "Bac%20Bo/TIE.png"

# --- Configurações ---
SIMULACAO = False  # True para simular localmente
FALHAS_CONSECUTIVAS = 0
ultimo_sinal = None
alerta_precoce_ativo = None  # Novo: salva qual padrão estamos acompanhando

# --- Logger ---
def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

# --- Envio de mensagem Telegram com Markdown e som ---
def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown",
        "disable_notification": False
    }
    requests.post(url, data=data)

# --- Verifica padrão e retorna tipo + empate + tamanho da sequência ---
def analisar_sequencia(sequencia):
    for tamanho in range(7, 5, -1):  # 7 e 6
        ultimos = sequencia[:tamanho]
        cores = [s for s in ultimos if s != "T"]
        num_empates = ultimos.count("T")

        if num_empates > 2:
            continue  # ignora sequência com mais de 2 empates

        if all(c == "B" for c in cores):
            return "B", num_empates > 0, tamanho
        if all(c == "P" for c in cores):
            return "P", num_empates > 0, tamanho
    return None, False, 0

# --- Função principal ---
async def verificar_padroes():
    global ultimo_sinal, FALHAS_CONSECUTIVAS, alerta_precoce_ativo

    if SIMULACAO:
        log("🔁 Rodando em modo de simulação.")
        sequencia = ["B", "T", "B", "B", "T", "B", "B", "B", "P"]
    else:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            for tentativa in range(3):
                try:
                    await page.goto("https://casinoscores.com/pt-br/bac-bo/", timeout=10000)
                    break
                except:
                    log("⚠️ Erro ao carregar site, tentando novamente...")
                    await asyncio.sleep(3)
            else:
                log("❌ Site indisponível após 3 tentativas.")
                FALHAS_CONSECUTIVAS += 1
                return

            await page.wait_for_timeout(4000)

            imagens = await page.query_selector_all("img")
            if not imagens or len(imagens) < 10:
                log("⚠️ Estrutura HTML pode ter mudado! Menos de 10 imagens.")
                FALHAS_CONSECUTIVAS += 1
                return

            sequencia = []
            for img in imagens:
                if len(sequencia) >= 20:
                    break
                src = await img.get_attribute("src")
                if not src:
                    continue
                if IMG_B in src:
                    sequencia.append("B")
                elif IMG_P in src:
                    sequencia.append("P")
                elif IMG_T in src:
                    sequencia.append("T")

            await browser.close()

    if len(sequencia) < 6:
        log("⚠️ Poucos dados para análise.")
        return

    resultado, tem_tie, tamanho = analisar_sequencia(sequencia)

    if resultado and tamanho >= 6:
        sinal = f"{resultado}_{'T' if tem_tie else 'NT'}"
        chave_sinal = f"{sinal}_{tamanho}"

        if not ultimo_sinal or not ultimo_sinal.startswith(sinal) or int(ultimo_sinal.split("_")[-1]) < tamanho:
            tipo = "🟥" if resultado == "B" else "🟦"
            nome = "**Banca**" if resultado == "B" else "**Player**"
            empates = " com empates no meio" if tem_tie else " seguidas"
            alerta = "⚠️ *Alerta precoce:* " if tamanho == 6 else ""
            mensagem = f"{alerta}{tipo} {tamanho} vitórias {nome}{empates}"

            enviar_telegram(mensagem)
            ultimo_sinal = chave_sinal
            alerta_precoce_ativo = resultado  # Salva padrão monitorado
            FALHAS_CONSECUTIVAS = 0
            log(f"📢 Sinal enviado: {mensagem}")
        else:
            log("🔄 Sinal repetido. Nenhum novo alerta enviado.")
    else:
        log("✅ Nenhum padrão relevante encontrado.")
        # Checar se padrão monitorado foi quebrado
        if alerta_precoce_ativo:
            primeira_cor_util = next((s for s in sequencia if s in ["B", "P"]), None)
            if primeira_cor_util and primeira_cor_util != alerta_precoce_ativo:
                tipo = "🟥" if primeira_cor_util == "B" else "🟦"
                nome = "**Banca**" if primeira_cor_util == "B" else "**Player**"
                mensagem = f"✅ O padrão anterior foi quebrado! Nova vitória para {tipo} {nome}"
                enviar_telegram(mensagem)
                log(f"💡 Padrão quebrado detectado: {mensagem}")
                alerta_precoce_ativo = None
        ultimo_sinal = None

# --- Loop de monitoramento ---
async def monitorar():
    global FALHAS_CONSECUTIVAS
    while True:
        try:
            await verificar_padroes()
        except Exception as e:
            log(f"💥 Erro crítico: {e}")
            FALHAS_CONSECUTIVAS += 1

        if FALHAS_CONSECUTIVAS >= 3:
            enviar_telegram("⚠️ O robô encontrou *3 falhas consecutivas*. Verifique o funcionamento!")
            FALHAS_CONSECUTIVAS = 0

        await asyncio.sleep(60)

# --- Início ---
enviar_telegram("🚀 Robô de monitoramento *iniciado* com sucesso.")
asyncio.run(monitorar())
