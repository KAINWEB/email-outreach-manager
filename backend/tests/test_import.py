from pathlib import Path
from openpyxl import Workbook
from sqlalchemy import select
from app.models import Campaign, Recipient, SuppressionEntry
from app.services.import_service import inspect_file, import_campaign


def test_xlsx_import_validation(db, tmp_path: Path):
    path = tmp_path / "leads.xlsx"
    wb = Workbook(); ws = wb.active
    ws.append(["Почта получателя", "Компания", "Тема письма", "Текст получателю"])
    ws.append(["good@example.com", "A", "Hi A", "Body A"])
    ws.append(["good@example.com", "A2", "Hi A2", "Body A2"])
    ws.append(["bad-email", "B", "Hi B", "Body B"])
    ws.append(["blocked@example.com", "C", "Hi C", "Body C"])
    wb.save(path)

    db.add(SuppressionEntry(email="blocked@example.com", reason="test"))
    c = Campaign(name="Test", source_path=str(path), source_filename=path.name)
    db.add(c); db.commit(); db.refresh(c)
    inspection = inspect_file(str(path))
    assert inspection["suggested_mapping"]["email"] == "Почта получателя"
    result = import_campaign(db, c, {"email":"Почта получателя", "company":"Компания", "subject":"Тема письма", "message":"Текст получателю"})
    assert result["total"] == 4
    assert result["ready"] == 1
    assert result["duplicates"] == 1
    assert result["excluded"] == 1
    assert result["errors"] == 1
    recipients = db.scalars(select(Recipient).order_by(Recipient.id)).all()
    assert recipients[0].status == "READY"
    assert recipients[1].status == "SKIPPED"
    assert recipients[3].status == "UNSUBSCRIBED"


def test_semicolon_cp1251_csv_is_supported(tmp_path: Path):
    path = tmp_path / "leads.csv"
    content = "Почта получателя;Компания;Тема письма;Текст получателю\nlead@example.com;Компания А;Привет;Персональный текст\n"
    path.write_bytes(content.encode("cp1251"))
    inspection = inspect_file(str(path))
    assert inspection["headers"][0] == "Почта получателя"
    assert inspection["suggested_mapping"]["email"] == "Почта получателя"
    assert inspection["sample_rows"][0]["Компания"] == "Компания А"
