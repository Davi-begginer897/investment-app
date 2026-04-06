import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

st.set_page_config(
    page_title="Sistema de Investimentos",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS para deixar bonito
st.markdown("""
<style>
body {
    background-color: #0e1117;
    color: white;
}

.metric-box {
    background-color: #1c1f26;
    padding: 15px;
    border-radius: 10px;
    text-align: center;
}

</style>
""", unsafe_allow_html=True)

st.sidebar.title("📊 Sistema de Investimentos")

ativos = st.sidebar.text_input(
    "Digite os ativos",
    "PETR4.SA, VALE3.SA"
)

periodo = st.sidebar.selectbox(
    "Período",
    ["3mo", "6mo", "1y"]
)

botao = st.sidebar.button("🚀 Analisar")

st.title("📊 Dashboard de Investimentos")
st.caption("Análise completa com dados técnicos + fundamentalistas + macro")
ativos = st.text_input("Digite os ativos (ex: PETR4.SA, VALE3.SA, ITUB4.SA)")

# =========================
# MACRO
# =========================
def get_macro():
    try:
        selic = requests.get(
            "https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados/ultimos/1?formato=json"
        ).json()[0]["valor"]
        return float(selic)
    except:
        return None

# =========================
# SENTIMENTO
# =========================
def get_vix():
    try:
        vix = yf.Ticker("^VIX").history(period="1d")["Close"].iloc[-1]
        return vix
    except:
        return None

# =========================
# SCORE
# =========================
def calcular_score(info, df):
    if df.empty:
        return 0

    score = 0

    # FUNDAMENTOS
    if info.get("trailingPE") and info["trailingPE"] < 15:
        score += 1
    if info.get("returnOnEquity") and info["returnOnEquity"] > 0.15:
        score += 1
    if info.get("enterpriseToEbitda") and info["enterpriseToEbitda"] < 10:
        score += 1

    # TÉCNICO
    df["SMA50"] = df["Close"].rolling(50).mean()
    df["RSI"] = 100 - (100 / (1 + df["Close"].pct_change().rolling(14).mean()))

    df = df.dropna()

    if df.empty:
        return score

    last = df.iloc[-1]

    close = float(last["Close"].values[0])
    sma50 = float(last["SMA50"].values[0])
    rsi = float(last["RSI"].values[0])

    if close > sma50:
        score += 1
    if rsi < 70:
        score += 1

    return score

# =========================
# PORTFOLIO
# =========================
def otimizar_portfolio(returns_dict):
    ativos = list(returns_dict.keys())
    retornos = np.column_stack(list(returns_dict.values()))

    melhor_sharpe = -999
    melhor_peso = None

    for _ in range(2000):
        pesos = np.random.random(len(ativos))
        pesos /= np.sum(pesos)

        retorno = np.sum(np.mean(retornos, axis=0) * pesos)
        risco = np.sqrt(np.dot(pesos.T, np.dot(np.cov(retornos.T), pesos)))

        sharpe = retorno / risco

        if sharpe > melhor_sharpe:
            melhor_sharpe = sharpe
            melhor_peso = pesos

    return dict(zip(ativos, melhor_peso))

# =========================
# EXECUÇÃO
# =========================
if botao:

    lista = [a.strip() for a in ativos.split(",")]

    resultados = []

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🌎 Cenário Macro")
        selic = get_macro()
        if selic:
            st.write(f"Selic: {selic}%")

        vix = get_vix()
        if vix:
            st.write(f"VIX (Medo): {vix:.2f}")

    for ativo in lista:
        try:
            ticker = yf.Ticker(ativo)
            try:
                info = ticker.info
            except Exception as e:
                st.warning(f"{ativo}: erro ao buscar fundamentos (limite da API)")
                info = {}
            try:
                df = yf.download(ativo, period="6mo")
            except:
                 st.error(f"Erro ao baixar dados de {ativo}")
                 continue
            
            if df.empty:
                st.write(f"{ativo} sem dados disponíveis")
                continue

            score = calcular_score(info, df)

            if score >= 6:
                decisao = "FORTE COMPRA"
            elif score >= 4:
                decisao = "NEUTRO"
            else:
                decisao = "FRACO"

            resultados.append({
                "Ativo": ativo,
                "Score": score,
                "Decisão": decisao,
                "P/L": info.get("trailingPE"),
                "ROE": info.get("returnOnEquity"),
                "EV/EBITDA": info.get("enterpriseToEbitda")
            })

            with col2:
                st.subheader(f"📈 {ativo}")
            df["SMA50"] = df["Close"].rolling(50).mean()
            st.line_chart(df[["Close", "SMA50"]])
        except Exception as e:
            st.write(f"Erro ao analisar {ativo}")
            st.write(e)

    df_result = pd.DataFrame(resultados)

    if not df_result.empty and "Score" in df_result.columns:
        df_result = df_result.sort_values(by="Score", ascending=False)

        st.subheader("📊 Resultado da Análise")
        st.dataframe(df_result)
    else:
        st.error("Nenhum ativo foi analisado corretamente. Verifique os códigos digitados.")
        st.stop()

    st.subheader("📊 Resultado da Análise")

    col1, col2, col3 = st.columns(3)

    with col1:
          st.metric("Ativos analisados", len(df_result))

    with col2:
          st.metric("Melhor Score", df_result["Score"].max())

    with col3:
          st.metric("Média Score", round(df_result["Score"].mean(), 2))

    st.dataframe(df_result)

    # DOWNLOAD
    csv = df_result.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Baixar Excel", csv, "analise.csv", "text/csv")

    # CARTEIRA
    top_ativos = df_result[df_result["Score"] >= 4]["Ativo"]

    if len(top_ativos) > 0:
        returns_dict = {}

        for ativo in top_ativos:
            df = yf.download(ativo, period="6mo")
            returns_dict[ativo] = df["Close"].pct_change().dropna()

        pesos = otimizar_portfolio(returns_dict)

        st.subheader("💼 Carteira Sugerida")

        for ativo, peso in pesos.items():
            st.write(f"{ativo}: {peso:.2%}")
