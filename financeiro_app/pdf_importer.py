import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from pypdf import PdfReader


MONTHS_PT = {
    "jan": 1,
    "fev": 2,
    "mar": 3,
    "abr": 4,
    "mai": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "set": 9,
    "out": 10,
    "nov": 11,
    "dez": 12,
}


@dataclass
class ReceiptData:
    receipt_type: str
    source: str
    occurrence_date: date
    amount: float
    receiver_name: str
    payer_name: str
    receiver_bank: str
    payer_bank: str
    transaction_id: str
    raw_text: str


# Compatibilidade com versões anteriores que importavam PicPayReceiptData.
PicPayReceiptData = ReceiptData


def extract_pdf_text(pdf_path: str | Path) -> str:
    """Extrai texto de PDFs simples de comprovante.

    O PyPDF é puro Python e funciona bem no Railway/Windows sem depender de Poppler.
    Observação: se o arquivo for uma imagem escaneada dentro do PDF, será necessário OCR.
    """
    reader = PdfReader(str(pdf_path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages).strip()


def _clean(text: str) -> str:
    # Alguns PDFs trazem caracteres privados no lugar de : ou hífen.
    text = text.replace("\ue092", ":").replace("\ue088", "-").replace("", ":").replace("", "-")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _line_after(lines: list[str], label: str) -> str:
    label_norm = label.strip().lower()
    for idx, line in enumerate(lines):
        if line.strip().lower() == label_norm and idx + 1 < len(lines):
            return lines[idx + 1].strip()
    return ""


def _value_after_label(lines: list[str], label: str, stop_labels: set[str] | None = None) -> str:
    """Lê valor que pode estar na mesma linha do rótulo ou na próxima linha.

    Ex.: "Valor R$ 30,00" ou "Valor\nR$ 30,00".
    """
    stop_labels = {s.lower() for s in (stop_labels or set())}
    label_norm = label.strip().lower()
    for idx, line in enumerate(lines):
        current = line.strip()
        lower = current.lower()
        if lower == label_norm:
            for candidate in lines[idx + 1 : idx + 4]:
                cand = candidate.strip()
                if cand.lower() in stop_labels:
                    break
                if cand:
                    return cand
        if lower.startswith(label_norm + " ") or lower.startswith(label_norm + ":"):
            value = re.sub(rf"^{re.escape(label)}\s*:?\s*", "", current, flags=re.IGNORECASE).strip()
            if value:
                return value
    return ""


def _section_value(lines: list[str], section: str, label: str) -> str:
    """Lê um campo dentro de uma seção visual como Destino/Origem."""
    section_norm = section.lower()
    label_norm = label.lower()
    start = None
    for idx, line in enumerate(lines):
        if line.lower() == section_norm:
            start = idx + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for idx in range(start, len(lines)):
        if lines[idx].lower() in {"destino", "origem", "dados bancários do recebedor", "ouvidoria", "sac"}:
            end = idx
            break
    section_lines = lines[start:end]
    for idx, line in enumerate(section_lines):
        lower = line.lower()
        if lower == label_norm and idx + 1 < len(section_lines):
            return section_lines[idx + 1].strip()
        if lower.startswith(label_norm + " ") or lower.startswith(label_norm + ":"):
            return re.sub(rf"^{re.escape(label)}\s*:?\s*", "", line, flags=re.IGNORECASE).strip()
    return ""


def _bank_after_person(lines: list[str], label: str) -> str:
    """No comprovante PicPay, depois de Para/De vem nome, documento e banco."""
    label_norm = label.strip().lower()
    for idx, line in enumerate(lines):
        if line.strip().lower() == label_norm:
            for candidate in lines[idx + 2 : idx + 7]:
                upper = candidate.upper()
                if "PAGAMENTOS" in upper or "PICPAY" in upper or "BANCO" in upper or "CAIXA" in upper or "NU " in upper:
                    return candidate.strip()
    return ""


def _parse_date(text: str) -> Optional[date]:
    # PicPay: 27/mai/2026
    match = re.search(r"(\d{1,2})/([a-zç]{3})/(\d{4})", text, flags=re.IGNORECASE)
    if match:
        day = int(match.group(1))
        month = MONTHS_PT.get(match.group(2).lower())
        year = int(match.group(3))
        if month:
            return date(year, month, day)

    # Nubank: 02 MAI 2026 - 18:21:54
    match = re.search(r"(\d{1,2})\s+([a-zç]{3})\s+(\d{4})", text, flags=re.IGNORECASE)
    if match:
        day = int(match.group(1))
        month = MONTHS_PT.get(match.group(2).lower())
        year = int(match.group(3))
        if month:
            return date(year, month, day)

    # Fallback: 02/05/2026
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if match:
        return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    return None


def _parse_amount(text: str) -> Optional[float]:
    match = re.search(r"R\$\s*([0-9\.]+,[0-9]{2})", text)
    if not match:
        return None
    value = match.group(1).replace(".", "").replace(",", ".")
    return float(value)


def _parse_transaction_id(lines: list[str], text: str) -> str:
    # Primeiro tenta rótulo explícito.
    value = _value_after_label(lines, "ID da transação") or _value_after_label(lines, "ID da transacao")
    if value:
        # Alguns PDFs quebram o ID em duas linhas; junta o próximo pedaço se parecer continuação.
        for idx, line in enumerate(lines):
            if line.lower() in {"id da transação", "id da transacao"} and idx + 2 < len(lines):
                second = lines[idx + 2].strip()
                if re.fullmatch(r"[A-Za-z0-9]{8,}", second):
                    value = value + second
                break
        return re.sub(r"\s+", "", value)

    # Fallback para IDs Pix começando com E e longos.
    match = re.search(r"\b(E[A-Za-z0-9]{20,})\b", re.sub(r"\s+", "", text))
    return match.group(1) if match else ""


def parse_picpay_receipt(pdf_path: str | Path) -> ReceiptData:
    raw = extract_pdf_text(pdf_path)
    text = _clean(raw)
    lines = _lines(text)

    if "Comprovante de Pix" not in text or "PICPAY" not in text.upper():
        raise ValueError("O PDF não parece ser um comprovante Pix do PicPay.")

    amount = _parse_amount(text)
    occurrence_date = _parse_date(text)
    receiver_name = _line_after(lines, "Para")
    payer_name = _line_after(lines, "De")
    receiver_bank = _bank_after_person(lines, "Para")
    payer_bank = _bank_after_person(lines, "De")
    transaction_id = _parse_transaction_id(lines, text)

    missing = []
    if amount is None:
        missing.append("valor")
    if occurrence_date is None:
        missing.append("data")
    if not receiver_name:
        missing.append("recebedor")
    if not transaction_id:
        missing.append("ID da transação")
    if missing:
        raise ValueError("Não consegui ler estes campos do comprovante PicPay: " + ", ".join(missing))

    return ReceiptData(
        receipt_type="pix_picpay",
        source="PicPay",
        occurrence_date=occurrence_date,
        amount=amount,
        receiver_name=receiver_name,
        payer_name=payer_name,
        receiver_bank=receiver_bank,
        payer_bank=payer_bank,
        transaction_id=transaction_id,
        raw_text=text,
    )


def parse_nubank_receipt(pdf_path: str | Path) -> ReceiptData:
    raw = extract_pdf_text(pdf_path)
    text = _clean(raw)
    lines = _lines(text)
    upper = text.upper()

    looks_like_nubank = "COMPROVANTE DE TRANSFER" in upper or "NU PAGAMENTOS" in upper or "NUBANK" in upper
    if not looks_like_nubank:
        raise ValueError("O PDF não parece ser um comprovante de transferência Nubank.")

    amount = _parse_amount(text)
    occurrence_date = _parse_date(text)
    receiver_name = _section_value(lines, "Destino", "Nome") or _line_after(lines, "Nome")
    payer_name = _section_value(lines, "Origem", "Nome")
    receiver_bank = _section_value(lines, "Destino", "Instituição") or _section_value(lines, "Destino", "Instituicao")
    payer_bank = _section_value(lines, "Origem", "Instituição") or _section_value(lines, "Origem", "Instituicao")
    transaction_id = _parse_transaction_id(lines, text)

    missing = []
    if amount is None:
        missing.append("valor")
    if occurrence_date is None:
        missing.append("data")
    if not receiver_name:
        missing.append("nome do destino")
    if not transaction_id:
        missing.append("ID da transação")
    if missing:
        raise ValueError("Não consegui ler estes campos do comprovante Nubank: " + ", ".join(missing))

    return ReceiptData(
        receipt_type="pix_nubank",
        source="Nubank",
        occurrence_date=occurrence_date,
        amount=amount or 0.0,
        receiver_name=receiver_name,
        payer_name=payer_name,
        receiver_bank=receiver_bank,
        payer_bank=payer_bank,
        transaction_id=transaction_id,
        raw_text=text,
    )


def parse_financial_receipt(pdf_path: str | Path) -> ReceiptData:
    """Detecta automaticamente comprovantes suportados.

    Suportados nesta versão:
    - PicPay Pix em PDF
    - Nubank/Nu Pagamentos Pix/transferência em PDF
    """
    raw = _clean(extract_pdf_text(pdf_path))
    upper = raw.upper()
    if "PICPAY" in upper:
        return parse_picpay_receipt(pdf_path)
    if "NU PAGAMENTOS" in upper or "NUBANK" in upper or "COMPROVANTE DE TRANSFER" in upper:
        return parse_nubank_receipt(pdf_path)
    raise ValueError("Banco/padrão não reconhecido. Por enquanto leio comprovantes PDF do PicPay e Nubank.")


def build_transaction_from_receipt(data: ReceiptData) -> dict:
    receiver = data.receiver_name or "Recebedor"
    bank = f" ({data.receiver_bank})" if data.receiver_bank else ""
    label = "Nubank" if data.source.lower().startswith("nubank") else data.source
    return {
        "description": f"Pix {label} para {receiver}{bank}",
        "category": "Pix / Transferência",
        "amount": data.amount,
        "type": "expense",
        "occurrence_date": data.occurrence_date,
    }


def build_transaction_from_picpay(data: ReceiptData) -> dict:
    return build_transaction_from_receipt(data)
