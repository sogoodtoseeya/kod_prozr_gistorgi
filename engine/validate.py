# -*- coding: utf-8 -*-
# Слепая валидация движка: сравнение с эталоном golden_cases.csv.
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rules_engine import run

def main(data_dir='data', out_dir='.'):
    sig = run(data_dir)
    with open(os.path.join(data_dir, 'golden_cases.csv'), encoding='utf-8-sig') as f:
        golden = list(csv.DictReader(f, delimiter=';'))
    sig_map = {(s['auction_id'], s['applicant_id']): s for s in sig}
    gold_map = {(g['auction_id'], g['applicant_id']): g for g in golden}
    matched, rule_mis, prio_mis, fp = 0, [], [], []
    for key, g in gold_map.items():
        s = sig_map.get(key)
        if s is None:
            continue
        ok_rules = set(s['rules'].split(';')) == set(g['rules'].split(';'))
        ok_prio = s['priority'] == g['priority']
        if ok_rules and ok_prio:
            matched += 1
        if not ok_rules:
            rule_mis.append((g['case_id'], g['rules'], s['rules']))
        if not ok_prio:
            prio_mis.append((g['case_id'], g['priority'], s['priority']))
    for key, s in sig_map.items():
        if key not in gold_map:
            fp.append(key)
    fn = [g['case_id'] for key, g in gold_map.items() if key not in sig_map]
    recall = matched / len(gold_map) if gold_map else 0
    precision = matched / len(sig_map) if sig_map else 0
    lines = []
    lines.append('ОТЧЁТ ВАЛИДАЦИИ ДВИЖКА ПРАВИЛ «ПРОЗРАЧНЫЕ ТОРГИ»')
    lines.append('Сверка сигналов с эталоном golden_cases.csv (30 случаев)')
    lines.append('')
    lines.append('Сигналов сформировано: %d' % len(sig))
    lines.append('Золотых случаев:        %d' % len(gold_map))
    lines.append('Полных совпадений:      %d' % matched)
    lines.append('recall    = %.2f' % recall)
    lines.append('precision = %.2f' % precision)
    lines.append('FP (лишние сигналы):    %d' % len(fp))
    lines.append('FN (пропущенные):       %d' % len(fn))
    lines.append('Расхождений по правилам:   %d' % len(rule_mis))
    lines.append('Расхождений по приоритету: %d' % len(prio_mis))
    if rule_mis:
        lines.append('Правила: ' + str(rule_mis))
    if prio_mis:
        lines.append('Приоритеты: ' + str(prio_mis))
    if fn:
        lines.append('FN: ' + str(fn))
    if fp:
        lines.append('FP: ' + str(fp))
    lines.append('')
    lines.append('Вывод: ' + ('движок воспроизводит эталон полностью.' if matched == len(gold_map) and not fp else 'есть расхождения — см. выше.'))
    report = '\n'.join(lines)
    with open(os.path.join(out_dir, 'validation_report.txt'), 'w', encoding='utf-8') as f:
        f.write(report)
    print(report)

if __name__ == '__main__':
    d = sys.argv[1] if len(sys.argv) > 1 else 'data'
    o = sys.argv[2] if len(sys.argv) > 2 else '.'
    main(d, o)
