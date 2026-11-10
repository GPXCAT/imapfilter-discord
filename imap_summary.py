"""把 `imapfilter -v` 的冗長 IMAP 對話紀錄整理成精簡的 Discord 摘要。"""
import re

DISCORD_LIMIT = 1900

# 例：C (3): 1003 SELECT "INBOX"   /   S (3): 1003 OK [READ-WRITE] Select completed
LINE_RE = re.compile(r'^([CS]) \((\d+)\): (.*)$')
CMD_RE = re.compile(r'^((?:UID\s+)?\S+)\s*(.*)$', re.IGNORECASE)
EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')

SERVER_ALIASES = {'Gimap': 'Gmail'}


def _count_uids(uid_set):
    """計算 UID 集合（例如 1,3,5:8）包含幾封信。"""
    total = 0
    for part in uid_set.split(','):
        if ':' in part:
            a, b = part.split(':', 1)
            total += abs(int(b) - int(a)) + 1 if a.isdigit() and b.isdigit() else 1
        elif part:
            total += 1
    return total


def _server_name(greeting):
    text = re.sub(r'\[.*?\]', '', greeting[len('* OK'):]).strip()
    first = text.split(' ', 1)[0] if text else '?'
    return SERVER_ALIASES.get(first, first)


def parse(raw):
    conns = {}      # 連線編號 -> 狀態
    pending = {}    # tag -> (連線編號, 指令, 參數)
    actions = {}    # (連線, 來源資料夾, 動作, 目的地) -> 信件數
    errors = []
    others = []

    def conn(cid):
        return conns.setdefault(cid, {
            'server': '?', 'user': None, 'login': None,
            'folders': [], 'current': None, 'login_pending': False,
        })

    for line in raw.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        m = LINE_RE.match(line)
        if not m:
            others.append(line.strip())
            continue

        direction, cid, body = m.groups()
        c = conn(cid)

        if direction == 'C':
            first = body.split(' ', 1)[0].upper()
            # imapfilter 會把 LOGIN 那行的 tag 和帳密遮掉："LOGIN * *"
            if first in ('LOGIN', 'AUTHENTICATE'):
                c['login_pending'] = True
                continue
            parts = body.split(' ', 1)
            if len(parts) < 2:
                continue
            cm = CMD_RE.match(parts[1])
            if cm:
                pending[parts[0]] = (cid, cm.group(1).upper(), cm.group(2))
            continue

        # ---- 伺服器回應 ----
        if body.startswith('*'):
            if body.startswith('* OK') and c['server'] == '?':
                c['server'] = _server_name(body)
            elif body.startswith(('* NO', '* BAD')):
                errors.append(f"[連線 {cid}] {body[2:]}")
            continue

        parts = body.split(' ', 2)
        if len(parts) < 2:
            continue
        tag, status = parts[0], parts[1].upper()
        text = parts[2] if len(parts) > 2 else ''

        if tag in pending:
            _, cmd, args = pending.pop(tag)
        elif c['login_pending']:
            cmd, args = 'LOGIN', ''
        else:
            continue
        if cmd == 'LOGIN':
            c['login_pending'] = False

        if status != 'OK':
            if cmd == 'LOGIN':
                c['login'] = False
            errors.append(f"[連線 {cid}] {cmd} {args}".rstrip() + f"：{status} {text}")
            continue

        if cmd == 'LOGIN':
            c['login'] = True
            em = EMAIL_RE.search(text)
            if em:
                c['user'] = em.group(0)
        elif cmd in ('SELECT', 'EXAMINE'):
            folder = args.strip().strip('"')
            c['current'] = folder
            if folder not in c['folders']:
                c['folders'].append(folder)
        elif cmd in ('UID MOVE', 'MOVE', 'UID COPY', 'COPY'):
            a = args.split(' ', 1)
            if len(a) == 2:
                verb = '移動' if 'MOVE' in cmd else '複製'
                key = (cid, c['current'], verb, a[1].strip().strip('"'))
                actions[key] = actions.get(key, 0) + _count_uids(a[0])
        elif cmd in ('UID STORE', 'STORE'):
            a = args.split(' ', 1)
            if len(a) == 2:
                flags = a[1]
                if '\\Deleted' in flags and flags.lstrip().startswith('+'):
                    verb = '標記刪除'
                elif '\\Seen' in flags and flags.lstrip().startswith('+'):
                    verb = '標記已讀'
                else:
                    verb = '變更旗標'
                key = (cid, c['current'], verb, None)
                actions[key] = actions.get(key, 0) + _count_uids(a[0])

    return {'conns': conns, 'actions': actions, 'errors': errors, 'others': others}


def _fit(lines, limit=DISCORD_LIMIT):
    """逐行加入，超過 Discord 字數上限時改成「省略 N 行」。"""
    out, size = [], 0
    for i, line in enumerate(lines):
        if size + len(line) + 1 > limit - 40:
            out.append(f"…（其餘 {len(lines) - i} 行已省略，完整內容見附檔）")
            break
        out.append(line)
        size += len(line) + 1
    return '\n'.join(out)


def has_problem(raw, returncode):
    r = parse(raw)
    return returncode != 0 or bool(r['errors']) or any(
        c['login'] is not True for c in r['conns'].values())


def format_summary(raw, returncode, title):
    r = parse(raw)
    problem = has_problem(raw, returncode)
    lines = [f"{'⚠️' if problem else '✅'} **{title}**"]

    if r['conns']:
        for cid in sorted(r['conns'], key=int):
            c = r['conns'][cid]
            name = c['server'] + (f"（{c['user']}）" if c['user'] else '')
            login = {True: '登入成功', False: '❌ 登入失敗', None: '❔ 未登入'}[c['login']]
            folders = f"｜{', '.join(c['folders'])}" if c['folders'] else ''
            lines.append(f"• 連線 {cid}｜{name}｜{login}{folders}")
    else:
        lines.append("• 沒有任何 IMAP 連線紀錄")

    if r['actions']:
        lines.append('')
        lines.append('📦 **郵件動作**')
        for (cid, src, verb, dest), n in r['actions'].items():
            where = f"{src} → {dest}" if dest else (src or '?')
            lines.append(f"• 連線 {cid}｜{where}：{verb} {n} 封")
    else:
        lines.append('📭 沒有郵件被移動或刪除')

    if r['errors']:
        lines.append('')
        lines.append('❌ **錯誤**')
        lines.extend(f"• {e}" for e in r['errors'])

    if r['others']:
        lines.append('')
        lines.append('📝 **其他訊息**')
        lines.append('```')
        lines.extend(r['others'][:15])
        if len(r['others']) > 15:
            lines.append(f"…（另有 {len(r['others']) - 15} 行）")
        lines.append('```')

    if returncode != 0:
        lines.append(f"結束代碼：`{returncode}`")

    text = _fit(lines)
    # 截斷可能把 ``` 切成單數，補上收尾避免格式跑掉
    if text.count('```') % 2:
        text += '\n```'
    return text
