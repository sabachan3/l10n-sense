"""Hand-written mini apps for the context gate: English UI strings whose right translation
depends on where they are used. Each target lists Japanese fragments that show the right
sense (`accept`) and fragments that show a wrong sense (`reject`).

These measure how easily a translator takes the wrong sense, with and without code context.
They are built around ambiguity on purpose, so the error rate here is not the error rate of
ordinary apps.
"""


def target(key, sense, accept, reject):
    return {"key": key, "sense": sense, "accept": accept, "reject": reject}


APPS = [
    {"name": "tournament", "about": "Kingdom vs Kingdom (KvK) tournament tracker for a strategy game",
     "strings": {"nav.home": "Home", "kvk.draw": "KvK draw", "kvk.drawSchedule": "Draw schedule",
                 "kvk.seed": "Seed", "kvk.round": "Round {n}", "kvk.kingdoms": "Kingdoms", "common.refresh": "Refresh"},
     "code": """export function KvkDraw({ kingdoms, seeds }: Props) {
  // Shows which kingdoms were drawn against each other for the next KvK season.
  const pairings = usePairings(kingdoms, seeds);
  return (<section><h2>{t('kvk.draw')}</h2><p>{t('kvk.drawSchedule')}: {nextDrawDate}</p>
    {pairings.map(p => <Pairing key={p.id} a={p.a} b={p.b} seedA={<Badge>{t('kvk.seed')} {p.seedA}</Badge>} />)}</section>);
}""",
     "targets": [target("kvk.draw", "the bracket draw that decides match-ups", ["抽選", "組み合わせ", "組合せ", "マッチング"], ["引き分け", "描"]),
                 target("kvk.drawSchedule", "when the bracket draw happens", ["抽選", "組み合わせ", "組合せ"], ["引き分け", "描"]),
                 target("kvk.seed", "tournament seeding", ["シード"], ["種"])]},
    {"name": "results", "about": "Football league results table",
     "strings": {"table.win": "Win", "table.draw": "Draw", "table.loss": "Loss", "table.points": "Points",
                 "stats.saves": "Saves", "stats.title": "Player stats", "match.title": "Match"},
     "code": """export function Standings({ rows }: Props) {
  return (<table><thead><tr><th>{t('table.win')}</th><th>{t('table.draw')}</th><th>{t('table.loss')}</th><th>{t('table.points')}</th></tr></thead>
    {rows.map(r => <tr><td>{r.won}</td><td>{r.drawn}</td><td>{r.lost}</td><td>{r.pts}</td></tr>)}</table>);
}
export function KeeperStats({ keeper }: Props) { // goalkeeper: shots stopped
  return <dl><dt>{t('stats.saves')}</dt><dd>{keeper.shotsSaved}</dd></dl>;
}
export const Fixture = ({ m }: Props) => <h3>{t('match.title')}: {m.home} vs {m.away}</h3>;""",
     "targets": [target("table.draw", "a tied match", ["引き分け", "引分", "分け", "ドロー"], ["抽選", "描"]),
                 target("stats.saves", "shots stopped by the goalkeeper", ["セーブ"], ["保存", "節約"]),
                 target("match.title", "a game between two teams", ["試合", "対戦", "マッチ"], ["一致"])]},
    {"name": "canvas", "about": "Browser drawing tool",
     "strings": {"tool.draw": "Draw", "tool.fill": "Fill", "tool.stroke": "Stroke", "layer.order": "Order",
                 "file.export": "Export", "edit.undo": "Undo"},
     "code": """const TOOLS = [
  { id: 'pen', label: t('tool.draw'), icon: <PenIcon /> },          // freehand pen
  { id: 'bucket', label: t('tool.fill'), icon: <BucketIcon /> },    // paint bucket colour
  { id: 'outline', label: t('tool.stroke'), icon: <LineIcon /> },   // outline colour and width
];
export const LayerMenu = () => <Menu label={t('layer.order')}><Item>Bring to front</Item><Item>Send to back</Item></Menu>;""",
     "targets": [target("tool.draw", "draw with a pen", ["描", "ペン", "ドロー"], ["引き分け", "抽選"]),
                 target("tool.fill", "fill a shape with colour", ["塗り"], ["記入", "入力", "満た"]),
                 target("tool.stroke", "outline of a shape", ["線", "ストローク"], ["脳卒中", "打"]),
                 target("layer.order", "stacking order of layers", ["順", "重ね"], ["注文"])]},
    {"name": "shop", "about": "Online store checkout",
     "strings": {"nav.order": "Order", "address.state": "State", "item.free": "Free", "promo.save": "Save {percent}%",
                 "cart.title": "Cart", "pay.charge": "Charge"},
     "code": """export function OrderSummary({ order }: Props) {
  return (<div><h1>{t('nav.order')} #{order.number}</h1>
    <AddressForm><label>{t('address.state')}<select>{US_STATES.map(s => <option>{s}</option>)}</select></label></AddressForm>
    {order.shippingFee === 0 && <span className="shipping">{t('item.free')}</span>}
    <Badge>{t('promo.save', { percent: order.discountPercent })}</Badge>
    <p>{t('pay.charge')}: {formatMoney(order.total)}</p></div>);  // amount billed to the card
}""",
     "targets": [target("nav.order", "a purchase order", ["注文"], ["順"]),
                 target("address.state", "state in a postal address", ["州", "都道府県"], ["状態", "ステータス"]),
                 target("item.free", "costs nothing", ["無料"], ["自由", "空き", "フリー"]),
                 target("promo.save", "discount", ["オフ", "割引", "お得", "引き", "OFF"], ["保存"]),
                 target("pay.charge", "amount billed", ["請求", "料金", "お支払", "支払", "決済", "課金"], ["充電"])]},
    {"name": "parking", "about": "Parking spot and meeting room availability",
     "strings": {"spot.free": "Free", "spot.taken": "Taken", "room.book": "Book", "room.capacity": "Capacity",
                 "spot.lot": "Lot", "filter.all": "All"},
     "code": """export function SpotGrid({ spots }: Props) {
  return (<>{spots.map(s => <Spot key={s.id} className={s.occupied ? 'red' : 'green'}>{s.occupied ? t('spot.taken') : t('spot.free')}</Spot>)}
    <h3>{t('spot.lot')} B2</h3>   {/* which parking lot */}
    <Button onClick={() => reserve(room)}>{t('room.book')}</Button></>);
}""",
     "targets": [target("spot.free", "not occupied", ["空"], ["無料", "自由", "フリー"]),
                 target("room.book", "reserve", ["予約"], ["本", "書籍", "ブック"]),
                 target("spot.lot", "a parking lot", ["駐車場", "区画", "エリア"], ["ロット", "たくさん", "多"])]},
    {"name": "device", "about": "Smart battery monitor",
     "strings": {"battery.charge": "Charge", "battery.current": "Current", "device.state": "State",
                 "battery.cells": "Cells", "device.name": "Device name", "battery.health": "Health"},
     "code": """export function BatteryCard({ b }: Props) {
  return (<Card><Row label={t('battery.charge')} value={`${b.percent}%`} />
    <Row label={t('battery.current')} value={`${b.amps} A`} />
    <Row label={t('device.state')} value={b.online ? 'online' : 'offline'} />
    <Row label={t('battery.cells')} value={b.cellCount} /></Card>);
}""",
     "targets": [target("battery.charge", "battery charge level", ["充電", "残量"], ["請求", "料金"]),
                 target("battery.current", "electric current in amperes", ["電流"], ["現在"]),
                 target("device.state", "device status", ["状態", "ステータス"], ["州", "都道府県"]),
                 target("battery.cells", "battery cells", ["セル"], ["細胞", "独房"])]},
    {"name": "editor", "about": "Code editor find panel",
     "strings": {"find.matchCase": "Match case", "view.wrap": "Wrap", "find.replace": "Replace",
                 "find.wholeWord": "Whole word", "edit.case": "Case", "find.next": "Next"},
     "code": """export function FindBar() {
  return (<Bar><Toggle on={caseSensitive}>{t('find.matchCase')}</Toggle><Toggle on={wholeWord}>{t('find.wholeWord')}</Toggle>
    <Toggle on={softWrap}>{t('view.wrap')}</Toggle>   {/* soft-wrap long lines */}
    <Menu label={t('edit.case')}><Item>UPPERCASE</Item><Item>lowercase</Item></Menu></Bar>);
}""",
     "targets": [target("find.matchCase", "case-sensitive search", ["大文字", "小文字"], ["試合", "ケースに", "場合", "事例"]),
                 target("view.wrap", "wrap long lines", ["折り返"], ["包", "ラップ"]),
                 target("edit.case", "letter case", ["大文字", "小文字"], ["ケース", "場合", "事例", "事件"])]},
    {"name": "voice", "about": "Voice memo recorder",
     "strings": {"rec.record": "Record", "rec.track": "Track", "rec.volume": "Volume", "rec.pitch": "Pitch",
                 "rec.clear": "Clear", "rec.share": "Share"},
     "code": """export function Recorder() {
  return (<><RoundButton onClick={startMicrophone}>{t('rec.record')}</RoundButton>
    <Slider label={t('rec.volume')} min={0} max={100} /><Slider label={t('rec.pitch')} unit="semitones" />
    <h4>{t('rec.track')} 1</h4><Button onClick={deleteAllTakes}>{t('rec.clear')}</Button></>);
}""",
     "targets": [target("rec.record", "record audio", ["録音"], ["記録", "レコード"]),
                 target("rec.track", "an audio track", ["トラック"], ["追跡"]),
                 target("rec.volume", "loudness", ["音量", "ボリューム"], ["体積", "容積", "巻"]),
                 target("rec.pitch", "musical pitch", ["ピッチ", "音程", "音の高さ"], ["投球", "売り込み", "提案"])]},
    {"name": "shipping", "about": "Parcel shipping dashboard",
     "strings": {"ship.track": "Track", "ship.volume": "Volume", "ship.weight": "Weight", "ship.label": "Label",
                 "ship.due": "Due", "ship.carrier": "Carrier"},
     "code": """export function ParcelRow({ p }: Props) {
  return (<tr><td>{p.id}</td><td>{t('ship.weight')}: {p.kg} kg</td><td>{t('ship.volume')}: {p.m3} m³</td>
    <td>{t('ship.due')}: {formatDate(p.deliverBy)}</td>
    <td><a href={carrierUrl(p.trackingNumber)}>{t('ship.track')}</a></td></tr>);
}""",
     "targets": [target("ship.track", "follow a parcel", ["追跡"], ["トラック", "曲"]),
                 target("ship.volume", "cubic size", ["体積", "容積"], ["音量", "ボリューム"]),
                 target("ship.due", "delivery deadline", ["期限", "期日", "予定"], ["未払", "支払"])]},
    {"name": "bank", "about": "Personal banking",
     "strings": {"acct.balance": "Balance", "acct.statement": "Statement", "acct.interest": "Interest",
                 "acct.check": "Check", "acct.transfer": "Transfer", "acct.savings": "Savings"},
     "code": """export function AccountPage({ a }: Props) {
  return (<><Stat label={t('acct.balance')} value={money(a.available)} /><Stat label={t('acct.interest')} value={`${a.apr}%`} />
    <Link to="/pdf/monthly">{t('acct.statement')}</Link>
    <Button onClick={openCamera}>{t('acct.check')}</Button>   {/* deposit a paper cheque by photo */}</>);
}""",
     "targets": [target("acct.balance", "money in the account", ["残高"], ["バランス", "均衡"]),
                 target("acct.statement", "monthly account statement", ["明細"], ["声明", "ステートメント", "文"]),
                 target("acct.interest", "interest rate", ["利息", "金利", "利子", "利率"], ["興味", "関心"]),
                 target("acct.check", "a paper cheque", ["小切手"], ["確認", "チェック"])]},
    {"name": "social", "about": "Social profile settings",
     "strings": {"profile.interests": "Interests", "profile.handle": "Handle", "profile.bio": "Bio",
                 "profile.following": "Following", "profile.block": "Block", "profile.tip": "Tip"},
     "code": """export function ProfileForm({ user }: Props) {
  return (<Form><Field label={t('profile.handle')} prefix="@" value={user.username} />
    <TagInput label={t('profile.interests')} suggestions={['music', 'hiking', 'cooking']} />
    <Callout icon="bulb" title={t('profile.tip')}>Add a photo so friends can find you.</Callout>
    <Danger onClick={() => blockUser(other)}>{t('profile.block')}</Danger></Form>);
}""",
     "targets": [target("profile.interests", "hobbies and topics", ["興味", "関心", "趣味"], ["利息", "金利", "利子"]),
                 target("profile.handle", "username", ["ユーザー名", "ハンドル", "ID"], ["取っ手", "処理", "対処"]),
                 target("profile.tip", "a helpful hint", ["ヒント", "コツ", "Tips", "ワンポイント"], ["チップ", "先端"]),
                 target("profile.block", "block a user", ["ブロック"], ["塊", "区画"])]},
    {"name": "restaurant", "about": "Restaurant bill splitting",
     "strings": {"bill.tip": "Tip", "bill.check": "Check", "bill.party": "Party of {n}", "bill.split": "Split",
                 "bill.table": "Table", "bill.total": "Total"},
     "code": """export function Bill({ bill }: Props) {
  return (<><h2>{t('bill.check')} · {t('bill.table')} {bill.tableNo}</h2><p>{t('bill.party', { n: bill.guests })}</p>
    <Row label={t('bill.tip')}><Percent options={[10, 15, 20]} /></Row>
    <Button onClick={divideEvenly}>{t('bill.split')}</Button></>);
}""",
     "targets": [target("bill.tip", "gratuity", ["チップ"], ["ヒント", "コツ", "先端"]),
                 target("bill.check", "the restaurant bill", ["会計", "伝票", "勘定"], ["確認", "チェック", "小切手"]),
                 target("bill.party", "a group of guests", ["名", "人"], ["パーティー", "政党"]),
                 target("bill.split", "split the bill", ["割り勘", "分割", "分け"], ["スプリット", "裂"])]},
    {"name": "meetings", "about": "HR and meeting tools",
     "strings": {"hr.leave": "Leave", "call.leave": "Leave", "meet.minutes": "Minutes", "meet.chair": "Chair",
                 "meet.agenda": "Agenda", "hr.review": "Review"},
     "code": """export function LeavePanel({ me }: Props) {  // paid time off
  return <Stat label={t('hr.leave')} value={`${me.daysOffLeft} days`} />;
}
export function CallControls() {
  return <Button color="red" onClick={hangUp}>{t('call.leave')}</Button>;
}
export function MeetingDoc({ m }: Props) {
  return (<><Link to={m.notesUrl}>{t('meet.minutes')}</Link><p>{t('meet.chair')}: {m.chairperson}</p></>);
}""",
     "targets": [target("hr.leave", "time off work", ["休暇", "休み", "有給"], ["退出", "退席", "離れ", "去"]),
                 target("call.leave", "leave the call", ["退出", "退室", "退席", "終了", "抜け"], ["休暇"]),
                 target("meet.minutes", "written record of a meeting", ["議事録"], ["分"]),
                 target("meet.chair", "the person who runs the meeting", ["議長", "司会", "進行"], ["椅子", "いす", "チェア"])]},
    {"name": "weather", "about": "Weather and notifications",
     "strings": {"sky.clear": "Clear", "sky.fair": "Fair", "notif.clear": "Clear", "wind.light": "Light",
                 "sky.title": "Conditions", "notif.title": "Notifications"},
     "code": """const SKY = { 0: t('sky.clear'), 1: t('sky.fair'), 2: 'Cloudy', 3: 'Rain' };  // WMO sky condition codes
export function Wind({ kmh }: Props) { return <span>{kmh < 12 ? t('wind.light') : 'Strong'}</span>; }
export function NotificationTray({ items }: Props) {
  return <header>{t('notif.title')}<Button onClick={dismissAll}>{t('notif.clear')}</Button></header>;
}""",
     "targets": [target("sky.clear", "clear sky", ["晴", "快晴"], ["クリア", "消去", "明確", "削除"]),
                 target("sky.fair", "fair weather", ["晴"], ["公平", "フェア", "見本市", "普通"]),
                 target("notif.clear", "dismiss all notifications", ["クリア", "消去", "削除", "消す"], ["晴", "明確"]),
                 target("wind.light", "weak wind", ["弱", "微風", "穏やか"], ["ライト", "光", "照明", "軽い"])]},
    {"name": "fantasy", "about": "Fantasy sports league and mail",
     "strings": {"league.draft": "Draft", "mail.draft": "Draft", "league.pick": "Pick", "league.trade": "Trade",
                 "mail.inbox": "Inbox", "league.bench": "Bench"},
     "code": """export function DraftRoom({ league }: Props) {  // managers take turns choosing players
  return (<><h1>{t('league.draft')}</h1><p>{t('league.pick')} #{league.currentPick}</p><Roster title={t('league.bench')} players={subs} /></>);
}
export function MailFolders() {
  return <nav><a>{t('mail.inbox')}</a><a>{t('mail.draft')}</a></nav>;  // unsent messages
}""",
     "targets": [target("league.draft", "player draft", ["ドラフト"], ["下書き", "草案"]),
                 target("mail.draft", "unsent message", ["下書き"], ["ドラフト", "草案"]),
                 target("league.bench", "reserve players", ["ベンチ", "控え"], ["長椅子", "作業台"]),
                 target("league.pick", "a draft pick", ["指名", "ピック"], ["選ぶ", "拾"])]},
]
