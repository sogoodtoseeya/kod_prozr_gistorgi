# -*- coding: utf-8 -*-
# Движок правил системы «Прозрачные торги».
# Читает ТОЛЬКО graph_edges.csv. Эталон golden_cases.csv движку недоступен (слепая валидация).
import csv, json, os, sys

PRIOR_RANK = {'низкий': 1, 'средний': 2, 'высокий': 3}
RANK_NAME = {3: 'высокий', 2: 'средний', 1: 'низкий'}

KIN_PRI = {'супруг': 'высокий', 'супруга': 'высокий', 'ребёнок': 'высокий', 'родитель': 'высокий',
           'брат': 'средний', 'сестра': 'средний'}  # остальное родство — низкий

EXPL = {
    'R1': 'Участник связан с администрацией договором на кадастровые работы по выставленному на торги участку. Правовое основание: ст. 10, 11 ФЗ-273 — обязанность служащих, принимающих решение о допуске, уведомить о личной заинтересованности и принять меры предотвращения КИ.',
    'R2': 'Участник — родственник действующего муниципального служащего администрации. Правовое основание: ст. 10, 11 ФЗ-273; ст. 14.1 ФЗ-25 «О муниципальной службе».',
    'R3': 'Учредитель организации-участника — родственник действующего муниципального служащего. Правовое основание: ст. 10, 11 ФЗ-273.',
    'R4': 'Участник или учредитель организации-участника — бывший сотрудник администрации. Правовое основание: ст. 10 ФЗ-273; риск «вращающихся дверей».',
    'R5': 'Заявку подал действующий муниципальный служащий администрации — совмещение ролей участника и организатора торгов. Правовое основание: п. 6 ч. 1 ст. 17 ФЗ-273.',
}

def load_edges(data_dir):
    edges = []
    with open(os.path.join(data_dir, 'graph_edges.csv'), encoding='utf-8-sig') as f:
        for row in csv.DictReader(f, delimiter=';'):
            edges.append(row)
    return edges

def run(data_dir='data'):
    employment_current, former = set(), {}
    kin_of_person, contracts_by_parcel = {}, {}
    founders_of_org, applications, auction_parcel = {}, [], {}
    for e in load_edges(data_dir):
        s, t, typ, a = e['source_id'], e['target_id'], e['edge_type'], e.get('attr', '')
        if typ == 'employment_current':
            employment_current.add(s)
        elif typ == 'former_employment':
            former.setdefault(s, []).append(t)
        elif typ == 'kinship' and s in employment_current:
            kin_of_person.setdefault(t, []).append((s, a))
        elif typ == 'contract':
            contracts_by_parcel.setdefault(t, []).append((s, a))
        elif typ == 'founder':
            founders_of_org.setdefault(t, []).append(s)
        elif typ == 'application':
            applications.append((s, t, a))
        elif typ == 'auction_parcel':
            auction_parcel[s] = t

    signals = []
    for applicant, auction, status in applications:
        rules, details = {}, []
        parcel = auction_parcel.get(auction)
        # R1: договор на кадастровые работы по выставленному участку
        if parcel:
            for holder, cid in contracts_by_parcel.get(parcel, []):
                if holder == applicant:
                    rules.setdefault('R1', 'высокий')
                    details.append('R1: договор %s на кадастровые работы по выставленному участку %s' % (cid, parcel))
        # R2 / R4a: физлицо
        if applicant.startswith('P-'):
            best_r2 = 0
            for emp, deg in kin_of_person.get(applicant, []):
                lvl = KIN_PRI.get(deg, 'низкий')
                if PRIOR_RANK[lvl] > best_r2:
                    best_r2 = PRIOR_RANK[lvl]
                details.append('R2: %s — %s действующего служащего %s (уровень: %s)' % (applicant, deg, emp, lvl))
            if best_r2:
                rules['R2'] = RANK_NAME[best_r2]
            for emp in former.get(applicant, []):
                rules.setdefault('R4', 'средний')
                details.append('R4: %s — бывший сотрудник администрации (%s)' % (applicant, emp))
        # R3 / R4b: организация
        if applicant.startswith('ORG-'):
            for fnd in founders_of_org.get(applicant, []):
                for emp, deg in kin_of_person.get(fnd, []):
                    rules.setdefault('R3', 'средний')
                    details.append('R3: учредитель %s — %s действующего служащего %s' % (fnd, deg, emp))
                for emp in former.get(fnd, []):
                    rules.setdefault('R4', 'средний')
                    details.append('R4: учредитель %s — бывший сотрудник администрации (%s)' % (fnd, emp))
        # R5: действующий служащий подал заявку
        if applicant.startswith('EMP-') and applicant in employment_current:
            rules.setdefault('R5', 'высокий')
            details.append('R5: заявку подал действующий муниципальный служащий — совмещение ролей')
        if not rules:
            continue
        prio = RANK_NAME[max(PRIOR_RANK[v] for v in rules.values())]
        rules_sorted = sorted(rules)
        signals.append({
            'signal_id': 'SIG-%03d' % (len(signals) + 1),
            'auction_id': auction,
            'applicant_id': applicant,
            'rules': ';'.join(rules_sorted),
            'priority': prio,
            'explanation': ' | '.join(details),
            'legal_basis': ' | '.join(EXPL[r] for r in rules_sorted),
            'human_comment': '',
            'status': 'новый',
        })
    return signals

if __name__ == '__main__':
    data = sys.argv[1] if len(sys.argv) > 1 else 'data'
    out = sys.argv[2] if len(sys.argv) > 2 else '.'
    sig = run(data)
    with open(os.path.join(out, 'signals.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(sig[0].keys()), delimiter=';')
        w.writeheader(); w.writerows(sig)
    with open(os.path.join(out, 'signals.json'), 'w', encoding='utf-8') as f:
        json.dump(sig, f, ensure_ascii=False, indent=2)
    print('Сигналов:', len(sig))
