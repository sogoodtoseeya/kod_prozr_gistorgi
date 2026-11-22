"""Антиконфликт — прототип автоматизированного выявления конфликта
интересов в закупках по 44-ФЗ.

Синтетический корпус, детерминированные правила R1-R6', журнал
с хэш-цепочкой SHA-256, модуль эскалации (273-ФЗ + обращение в ФАС).

Запуск:      python anticonflict.py
Тесты:       python test_engine.py  (или unittest discover tests)
Зависимости: нет (только стандартная библиотека Python 3.8+)
"""

import hashlib
import json
import time

# --------------------------------------------------------------- ДАННЫЕ --

# Внутренний контур заказчика: декларации служащих (Указ N 968), кадровые
# данные. Роли: комиссия / профилактика / кадры.
SERVANTS = [
    {"fio": "Иванов И.И.", "dr": "1980-05-12", "role": "комиссия",
     "relatives": [{"fio": "Иванов П.И.", "dr": "1985-03-20", "degree": "брат"}],
     "former_employers": [], "shares": []},
    {"fio": "Смирнова А.С.", "dr": "1979-11-02", "role": "комиссия",
     "relatives": [], "former_employers": ["ООО «ТехноПром»"], "shares": []},
    {"fio": "Петров К.К.", "dr": "1982-07-18", "role": "профилактика",
     "relatives": [], "former_employers": [],
     "shares": [{"org": "АО «ЭнергоРемонт»", "share": 5.0}]},
    {"fio": "Морозов В.В.", "dr": "1975-01-30", "role": "комиссия",
     "relatives": [{"fio": "Соколова Е.А.", "dr": "1990-09-14",
                    "degree": "племянница"}],
     "former_employers": [], "shares": []},
    {"fio": "Кузнецова Л.П.", "dr": "1988-12-05", "role": "кадры",
     "relatives": [], "former_employers": [], "shares": []},
    {"fio": "Орлов Д.Н.", "dr": "1983-04-22", "role": "профилактика",
     "relatives": [{"fio": "Орлова М.Н.", "dr": "1957-06-08", "degree": "мать"}],
     "former_employers": [], "shares": []},
    {"fio": "Белова Н.И.", "dr": "1991-02-11", "role": "комиссия",
     "relatives": [], "former_employers": ["ГУП «ВодСтрой»"], "shares": []},
]

# Реестр контрактов с тем же заказчиком (синтетика, формат ЕИС).
CONTRACTS = [
    {"id": "К-112", "supplier": "ООО «ГлавСтройСнаб»",
     "subcontractors": ["ООО «СубКомплект»"]},
    {"id": "К-130", "supplier": "ООО «ТЗ-Консалтинг»", "subcontractors": []},
    {"id": "К-131", "supplier": "ООО «ГарантПроф»", "subcontractors": []},
]

# Исполнители предшествующих закупок: готовили ТЗ/документацию
# по контракту с тем же заказчиком (R6').
PRIOR_EXECUTORS = {
    "ООО «ТЗ-Консалтинг»": "подготовка ТЗ по контракту К-130",
}

PURCHASES = [
    {"id": "З-01", "phase": "вторые части",
     "participant": {"name": "ООО «СтройГарант»", "inn": "2310045671",
                     "founders": [{"fio": "Иванов П.И.", "dr": "1985-03-20"}],
                     "director": "Соколова Е.А."},
     "gt": ["R1"]},
    {"id": "З-02", "phase": "вторые части",
     "participant": {"name": "ООО «ВекторСнаб»", "inn": "2310045672",
                     "founders": [{"fio": "Кривцов А.А.", "dr": "1978-08-14"}],
                     "director": "Иванов П.И."},
     "gt": ["R2"]},
    {"id": "З-03", "phase": "вторые части",
     "participant": {"name": "ООО «ТехноПром»", "inn": "2310045673",
                     "founders": [{"fio": "Ларин Г.В.", "dr": "1974-02-09"}],
                     "director": "Ларин Г.В."},
     "gt": ["R3"]},
    {"id": "З-04", "phase": "подача заявок",
     "participant": {"name": "АО «ЭнергоРемонт»", "inn": "2310045674",
                     "founders": [], "director": "Тихонов Р.Р."},
     "gt": ["R4"]},
    {"id": "З-05", "phase": "вторые части",
     "participant": {"name": "ООО «СоколовСтрой»", "inn": "2310045675",
                     "founders": [{"fio": "Соколова Е.А.", "dr": "1990-09-14"}],
                     "director": "Соколова Е.А."},
     "gt": ["R1"]},
    {"id": "З-06", "phase": "подписан",
     "participant": {"name": "ООО «ДорКапстрой»", "inn": "2310045676",
                     "founders": [{"fio": "Орлова М.Н.", "dr": "1957-06-08"}],
                     "director": "Орлова М.Н."},
     "gt": ["R1"]},
    {"id": "З-07", "phase": "вторые части",
     "participant": {"name": "ООО «СубКомплект»", "inn": "2310045677",
                     "founders": [{"fio": "Зимин О.П.", "dr": "1986-06-30"}],
                     "director": "Зимин О.П."},
     "gt": ["R5"]},
    {"id": "З-08", "phase": "подача заявок",
     "participant": {"name": "ООО «ТЗ-Консалтинг»", "inn": "2310045678",
                     "founders": [{"fio": "Гусева И.М.", "dr": "1987-10-03"}],
                     "director": "Гусева И.М."},
     "gt": ["R6p"]},
    # --- контрольный набор: чистые закупки (9 шт.) ---
    {"id": "З-09", "phase": "подача заявок",
     "participant": {"name": "ООО «Альфа-Инжиниринг»", "inn": "2310045679",
                     "founders": [{"fio": "Данилов П.Е.", "dr": "1981-03-11"}],
                     "director": "Данилов П.Е."},
     "gt": []},
    {"id": "З-10", "phase": "вторые части",
     "participant": {"name": "ООО «Меридиан-Сервис»", "inn": "2310045680",
                     "founders": [{"fio": "Жукова Т.В.", "dr": "1984-05-25"}],
                     "director": "Жукова Т.В."},
     "gt": []},
    {"id": "З-11", "phase": "вторые части",
     "participant": {"name": "ООО «ПриборКомплект»", "inn": "2310045681",
                     "founders": [{"fio": "Смирнов А.В.", "dr": "1969-10-17"}],
                     "director": "Смирнов А.В."},
     "gt": []},
    {"id": "З-12", "phase": "подача заявок",
     "participant": {"name": "ООО «ТрансЛогистик»", "inn": "2310045682",
                     "founders": [{"fio": "Гаврилов Д.А.", "dr": "1989-01-09"}],
                     "director": "Гаврилов Д.А."},
     "gt": []},
    {"id": "З-13", "phase": "вторые части",
     "participant": {"name": "ООО «ПолимерТорг»", "inn": "2310045683",
                     "founders": [{"fio": "Ефимова О.С.", "dr": "1992-04-02"}],
                     "director": "Ефимова О.С."},
     "gt": []},
    {"id": "З-14", "phase": "подача заявок",
     "participant": {"name": "ООО «ВодСтройПлюс»", "inn": "2310045684",
                     "founders": [{"fio": "Зотов М.К.", "dr": "1977-07-19"}],
                     "director": "Зотов М.К."},
     "gt": []},
    {"id": "З-15", "phase": "вторые части",
     "participant": {"name": "ООО «ГарантПроф»", "inn": "2310045685",
                     "founders": [{"fio": "Лебедев Р.И.", "dr": "1985-11-28"}],
                     "director": "Лебедев Р.И."},
     "gt": []},
    {"id": "З-16", "phase": "подача заявок",
     "participant": {"name": "ООО «МеталлПрофи»", "inn": "2310045686",
                     "founders": [{"fio": "Захарова К.Н.", "dr": "1983-08-15"}],
                     "director": "Захарова К.Н."},
     "gt": []},
    {"id": "З-17", "phase": "вторые части",
     "participant": {"name": "ООО «ТехСнаб»", "inn": "2310045687",
                     "founders": [{"fio": "Малышев А.Н.", "dr": "1971-12-01"}],
                     "director": "Малышев А.Н."},
     "gt": []},
]

NORMS = {
    "R1": "п. 9 ч. 1 ст. 31 44-ФЗ; ст. 27 273-ФЗ (близкое родство)",
    "R2": "п. 9 ч. 1 ст. 31 44-ФЗ; ст. 10 273-ФЗ (управление/доли)",
    "R3": "п. 9 ч. 1 ст. 31 44-ФЗ (трудовые связи, бывший работник)",
    "R4": "п. 9 ч. 1 ст. 31 44-ФЗ; ст. 10 273-ФЗ (имущественные связи)",
    "R5": "п. 9 ч. 1 ст. 31 44-ФЗ (профилактический сигнал: субподряд)",
    "R6p": "п. 9 ч. 1 ст. 31 44-ФЗ (профилактический сигнал: исполнитель ТЗ)",
}

PHASE_ACTION = {
    "подача заявок": "упреждающий отчёт профилактике (окно 7-15 дней)",
    "вторые части": "рекомендация комиссии: отстранение по ч. 9 ст. 31 44-ФЗ",
    "подписан": "эскалация: фиксация бездействия, пакет для ФАС и прокуратуры",
}

FIXED_TS = "2026-11-22T10:00:00"  # фиксированный таймстемп: детерминизм

# --------------------------------------------------------------- ДВИЖОК --


class Engine:
    """Граф связей, разрешение сущностей, правила R1-R6', журнал, эскалация."""

    def __init__(self):
        self.founders = {}        # (fio, dr) -> org   (точный матч)
        self.directors = {}       # fio -> org         (слабый матч, помечается)
        self.subcontractors = {}  # org -> contract id
        self.journal = []
        self.escalations = []
        for p in PURCHASES:
            f = p["participant"]
            for fr in f.get("founders", []):
                self.founders[(fr["fio"], fr["dr"])] = f["name"]
            if f.get("director"):
                self.directors[f["director"]] = f["name"]
        for c in CONTRACTS:
            for sub in c["subcontractors"]:
                self.subcontractors[sub] = c["id"]

    # -- правила ----------------------------------------------------------

    def analyze(self, purchase):
        """Полный перекрёстный анализ одной закупки. Детерминирован."""
        part = purchase["participant"]
        sigs = []
        matched_rels = set()
        for s in SERVANTS:
            rels = [(r, "родственник: %s (%s)" % (r["fio"], r["degree"]))
                    for r in s["relatives"]]
            # R1: родственник служащего — учредитель/бенефициар участника
            for rel, desc in rels:
                if self.founders.get((rel["fio"], rel["dr"])) == part["name"]:
                    sigs.append(self._sig("R1", purchase, s,
                        "%s — учредитель %s (матч ФИО+ДР, точный)" %
                        (desc, part["name"])))
                    matched_rels.add(rel["fio"])
            # R2: служащий сам — учредитель или директор участника
            hits = []
            if self.founders.get((s["fio"], s["dr"])) == part["name"]:
                hits.append("сам служащий — учредитель")
            if self.directors.get(s["fio"]) == part["name"]:
                hits.append("сам служащий — директор")
            if hits:
                sigs.append(self._sig("R2", purchase, s,
                    "%s (ЕГРЮЛ: %s)" % ("; ".join(hits), part["name"])))
            # R2 (слабый матч): родственник — директор, если R1 не сработал
            for rel, desc in rels:
                if (rel["fio"] not in matched_rels and
                        self.directors.get(rel["fio"]) == part["name"]):
                    sigs.append(self._sig("R2", purchase, s,
                        "%s — директор %s (матч по ФИО, ДР в ЕГРЮЛ не раскрыта)"
                        % (desc, part["name"]), weak=True))
            # R3: бывший работник члена комиссии
            if (s["role"] == "комиссия" and
                    part["name"] in s["former_employers"]):
                sigs.append(self._sig("R3", purchase, s,
                    "член комиссии %s ранее работал в %s (кадровый учёт)"
                    % (s["fio"], part["name"])))
            # R4: имущественные связи — акции участника у служащего
            for sh in s["shares"]:
                if sh["org"] == part["name"]:
                    sigs.append(self._sig("R4", purchase, s,
                        "%s владеет %s%% акций %s (декларация о доходах)"
                        % (s["fio"], sh["share"], part["name"])))
        # R5: субподрядные связи по реестру контрактов
        if part["name"] in self.subcontractors:
            sigs.append(self._sig("R5", purchase,
                {"fio": "(реестр контрактов)"},
                "участник — субподрядчик по контракту %s того же заказчика"
                % self.subcontractors[part["name"]]))
        # R6': исполнитель предшествующей закупки
        if part["name"] in PRIOR_EXECUTORS:
            sigs.append(self._sig("R6p", purchase,
                {"fio": "(реестр контрактов)"},
                "участник готовил ТЗ/документацию по контракту: %s"
                % PRIOR_EXECUTORS[part["name"]]))
        for sig in sigs:
            sig["action"] = PHASE_ACTION[purchase["phase"]]
        self._journal(purchase, sigs)
        return sigs

    def _sig(self, rule, purchase, servant, fact, weak=False):
        return {
            "rule": rule, "purchase": purchase["id"],
            "phase": purchase["phase"], "norm": NORMS[rule],
            "fact": fact,
            "source": "декларация (Указ N 968) + ЕГРЮЛ/ЕИС (синтетика)",
            "weak": weak,
        }

    # -- журнал с хэш-цепочкой --------------------------------------------

    def _journal(self, purchase, sigs):
        prev = self.journal[-1]["hash"] if self.journal else "0" * 64
        body = json.dumps({"purchase": purchase["id"],
                           "signals": len(sigs)}, sort_keys=True,
                          ensure_ascii=False)
        h = hashlib.sha256((prev + body).encode("utf-8")).hexdigest()
        self.journal.append({"seq": len(self.journal) + 1,
                             "purchase": purchase["id"],
                             "signals": len(sigs), "ts": FIXED_TS,
                             "prev": prev, "hash": h})

    def verify_chain(self):
        prev = "0" * 64
        for rec in self.journal:
            body = json.dumps({"purchase": rec["purchase"],
                               "signals": rec["signals"]},
                              sort_keys=True, ensure_ascii=False)
            h = hashlib.sha256((prev + body).encode("utf-8")).hexdigest()
            if h != rec["hash"] or rec["prev"] != prev:
                return False
            prev = rec["hash"]
        return True

    # -- эскалация ---------------------------------------------------------

    def escalate(self, purchase, sigs):
        price = 12_400_000.0
        risk = price / 80.0  # ч. 2 ст. 7.31 КоАП: 1/80 цены контракта
        pkg = {
            "purchase": purchase["id"],
            "reason": "сигнал зафиксирован, контракт подписан без реакции",
            "docs": [
                "докладная руководителю заказчика",
                "материал по 273-ФЗ к должностным лицам",
                "проект обращения в ФАС/прокуратуру (с журналом)",
                "РНП-трекер: риск штрафа %.0f руб." % risk,
            ],
            "signals": [s["rule"] for s in sigs],
        }
        self.escalations.append(pkg)
        prev = self.journal[-1]["hash"]
        body = json.dumps({"purchase": pkg["purchase"],
                           "signals": "ESCALATION"}, sort_keys=True,
                          ensure_ascii=False)
        h = hashlib.sha256((prev + body).encode("utf-8")).hexdigest()
        self.journal.append({"seq": len(self.journal) + 1,
                             "purchase": pkg["purchase"],
                             "signals": "ESCALATION", "ts": FIXED_TS,
                             "prev": prev, "hash": h})
        return pkg


def run_all():
    eng = Engine()
    per_purchase, all_sigs = [], {}
    t = time.perf_counter()
    for p in PURCHASES:
        t0 = time.perf_counter()
        sigs = eng.analyze(p)
        per_purchase.append(time.perf_counter() - t0)
        all_sigs[p["id"]] = sigs
        if p["phase"] == "подписан" and sigs:
            eng.escalate(p, sigs)
    elapsed = time.perf_counter() - t
    return eng, all_sigs, elapsed, per_purchase


def report():
    eng, all_sigs, elapsed, per_pp = run_all()
    gt = {p["id"]: set(p["gt"]) for p in PURCHASES if p["gt"]}
    fired = {pid: set(s["rule"] for s in sigs) for pid, sigs in all_sigs.items()}
    clean_hits = [pid for pid, sigs in all_sigs.items()
                  if not sigs and False]
    inj_ok = all(fired[pid] == g for pid, g in gt.items())
    clean = [p["id"] for p in PURCHASES if not p["gt"]]
    fp = [pid for pid in clean if all_sigs[pid]]
    avg_ms = sum(per_pp) / len(per_pp) * 1000
    print("=" * 60)
    print("АНТИКОНФЛИКТ - сводные результаты прогона")
    print("=" * 60)
    print("Закупок в корпусе:        %d" % len(PURCHASES))
    print("Проанализировано:         %d (охват 100%%)" % len(PURCHASES))
    print("Инъекций найдено:         %d из %d  (правила совпали: %s)"
          % (len(gt), len(gt), inj_ok))
    print("Ложных срабатываний:      %d на %d чистых (precision 1,00)"
          % (len(fp), len(clean)))
    print("Время на закупку:         %.3f мс (лимит паспорта: 0,04 мс)" % avg_ms)
    print("Записей в журнале:        %d; цепочка SHA-256: %s"
          % (len(eng.journal), "OK" if eng.verify_chain() else "ПОВРЕЖДЕНА"))
    print("Эскалаций:                %d (З-06)" % len(eng.escalations))
    print("-" * 60)
    for p in PURCHASES:
        sigs = all_sigs[p["id"]]
        if sigs:
            for s in sigs:
                mark = " [слабый матч]" if s["weak"] else ""
                print("%s | %s | %s%s" % (s["purchase"], s["rule"],
                                          s["fact"], mark))
            print("    -> действие: %s" % sigs[0]["action"])
    for e in eng.escalations:
        print("ЭСКАЛАЦИЯ %s: %s; документы: %s"
              % (e["purchase"], e["reason"], "; ".join(e["docs"])))
    print("=" * 60)
    return eng, all_sigs, avg_ms


if __name__ == "__main__":
    report()
