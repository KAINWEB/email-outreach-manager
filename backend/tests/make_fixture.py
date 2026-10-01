from pathlib import Path
from openpyxl import Workbook
p=Path(__file__).parent/'fixtures'; p.mkdir(exist_ok=True)
wb=Workbook();ws=wb.active;ws.append(['email','company','name','subject','message']);ws.append(['client1@example.com','Company A','Иван','Предложение для Company A','Индивидуальный текст №1']);ws.append(['client2@example.com','Company B','Анна','Идея для Company B','Индивидуальный текст №2']);wb.save(p/'sample_leads.xlsx')
print(p/'sample_leads.xlsx')
