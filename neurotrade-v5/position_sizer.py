"""
position_sizer.py — Position Sizing Dinamic (Kelly adaptat)
Investim mai mult cand confidence e mare, mai putin cand e mediu.
"""
import logging
from config import POSITION_SIZING, MAX_POSITION_USD

log = logging.getLogger("PositionSizer")


def get_cash_pct(confidence: int) -> float:
    """
    Returneaza procentul din cash de investit
    in functie de confidence Gemini.
    """
    for (low, high), pct in POSITION_SIZING.items():
        if low <= confidence <= high:
            return pct
    # Default daca nu se incadreaza (sub 65 nu se executa oricum)
    return 0.10


def calc_quantity(confidence: int, cash: float, price: float) -> int:
    """
    Calculeaza numarul de actiuni de cumparat.

    Args:
        confidence: scorul Gemini (65-100)
        cash: cash disponibil in cont
        price: pretul curent al actiunii

    Returns:
        numarul de actiuni (minim 1, sau 0 daca insuficient)
    """
    if cash < price:
        log.warning(f"Cash insuficient: ${cash:.2f} < ${price:.2f}")
        return 0

    pct = get_cash_pct(confidence)
    invest_amount = min(cash * pct, MAX_POSITION_USD)

    if invest_amount < price:
        # Daca suma calculata e sub pretul unei actiuni, incearca cu minimul
        if cash >= price:
            invest_amount = price  # cumpara cel putin 1 actiune
        else:
            return 0

    qty = int(invest_amount / price)
    actual_invest = qty * price

    log.info(
        f"PositionSizer: confidence={confidence}% → "
        f"{pct*100:.0f}% din cash (${cash:.2f}) = "
        f"${invest_amount:.2f} → {qty} actiuni @ ${price:.2f} = ${actual_invest:.2f}"
    )
    return max(1, qty)
